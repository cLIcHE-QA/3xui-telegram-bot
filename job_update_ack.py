"""Read-only Deploy Agent evidence for acknowledging historical bot.update unknown.

This module never sends a deploy POST or changes a historical job result.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from deploy_control import DeployControlClient, DeployControlError, STATES


class JobLike(Protocol):
    name: str
    status: str
    details: str


_OPERATION_ID = re.compile(r"(?:^|; )operation_id=([0-9a-f]{32})(?:;|$)")
_RELEASE = re.compile(r"(?:^|; )release=(v\d+\.\d+\.\d+)(?:;|$)")
_SAFE_RELEASE = re.compile(r"v\d+\.\d+\.\d+(?:-rc\.\d+)?\Z")
_SHA = re.compile(r"[0-9a-f]{40}\Z")

REASON_LABELS = {
    "reviewed": "Проверены доступные сведения; исход операции не установлен",
    "recovered": "Текущий сервис восстановлен; исход старой операции не установлен",
    "insufficient": "Сведения агента недоступны; инцидент рассмотрен без вывода об исходе",
}

EVIDENCE_LABELS = {
    "metadata_missing": "в задании нет полной идентичности операции",
    "agent_unconfigured": "Deploy Agent не настроен",
    "journal_unavailable": "журнал Deploy Agent недоступен",
    "journal_missing": "операция в журнале не найдена",
    "journal_mismatch": "идентичность операции или релиза не совпала",
    "status_unavailable": "операция найдена, текущий статус недоступен",
    "journal_found": "запись операции найдена",
}


@dataclass(frozen=True)
class DeployEvidence:
    code: str
    operation_id: str = ""
    requested_release: str = ""
    agent_state: str = ""
    target_sha: str = ""
    current_release: str = ""
    current_sha: str = ""
    postcondition: str = "not_proven"

    def lines(self) -> list[str]:
        lines = [
            f"Журнал: {EVIDENCE_LABELS.get(self.code, 'не подтверждён')}",
            f"Исторический target: {self.requested_release or 'неизвестен'}",
        ]
        if self.operation_id:
            lines.append(f"Operation ID: {self.operation_id[:8]}…")
        if self.agent_state:
            lines.append(f"Состояние операции в агенте: {self.agent_state}")
        if self.target_sha:
            lines.append(f"Target SHA: {self.target_sha[:12]}")
        if self.current_release:
            lines.append(f"Сейчас развёрнут: {self.current_release}")
        if self.current_sha:
            lines.append(f"Сейчас SHA: {self.current_sha[:12]}")
        lines.append(
            "Текущая post-condition: "
            + ("healthy, релиз и SHA совпадают с target операции"
               if self.postcondition == "current_matches_target"
               else "не доказывает исход исторической операции")
        )
        return lines


async def correlate_deploy(
    job: JobLike,
    client: DeployControlClient | None,
) -> DeployEvidence:
    """GET-only correlation; never infers historical success from current health."""
    if job.name != "bot.update" or job.status != "unknown":
        raise ValueError("Only a historical bot.update unknown can be reviewed.")

    details = job.details or ""
    id_match = _OPERATION_ID.search(details)
    release_match = _RELEASE.search(details)
    op_id = id_match.group(1) if id_match else ""
    release = release_match.group(1) if release_match else ""
    base = {"operation_id": op_id, "requested_release": release}
    if not op_id or not release:
        return DeployEvidence("metadata_missing", **base)
    if client is None:
        return DeployEvidence("agent_unconfigured", **base)

    try:
        operation = await client.get_operation(op_id)
    except DeployControlError:
        return DeployEvidence("journal_unavailable", **base)
    if operation is None:
        return DeployEvidence("journal_missing", **base)
    if operation.operation_id != op_id or operation.release != release:
        return DeployEvidence("journal_mismatch", **base)

    agent_state = operation.state if operation.state in STATES else "unknown"
    target_sha = operation.target_sha if _SHA.fullmatch(operation.target_sha or "") else ""
    facts = dict(
        **base,
        agent_state=agent_state,
        target_sha=target_sha,
    )
    try:
        status = await client.status()
    except DeployControlError:
        return DeployEvidence("status_unavailable", **facts)

    current_release = status.current_release if _SAFE_RELEASE.fullmatch(status.current_release or "") else ""
    current_sha = status.current_sha if _SHA.fullmatch(status.current_sha or "") else ""
    matched = (
        agent_state == "success"
        and bool(target_sha)
        and current_release == release
        and current_sha == target_sha
        and status.health == "ok"
        and status.db == "ok"
        and status.connectivity == "ok"
        and not status.active_operation
    )
    return DeployEvidence(
        "journal_found", **facts,
        current_release=current_release,
        current_sha=current_sha,
        postcondition="current_matches_target" if matched else "not_proven",
    )
