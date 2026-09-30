from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping, Protocol


class JobLike(Protocol):
    id: int
    name: str
    status: str


@dataclass(frozen=True)
class AttentionSummary:
    total: int
    lines: tuple[str, ...]


_JOB_PROBLEM_STATES = {"failed", "unknown", "interrupted"}
_INFRA_PROBLEM_STATES = {"unhealthy", "offline", "degraded", "unknown"}
_ROLLOUT_PROBLEM_STATES = {
    "failed",
    "unknown",
    "interrupted",
    "stopped_failed",
    "stopped_unknown",
}
_DRAIN_PROBLEM_STATES = {"partial", "failed", "unknown", "interrupted"}


def latest_rollout_problem_states(plans: Iterable[Mapping[str, object]]) -> tuple[str, ...]:
    effective = [
        plan for plan in plans
        if str(plan.get("state") or "").lower() not in {"review", "cancelled"}
    ]
    if not effective:
        return ()
    latest = max(
        effective,
        key=lambda plan: (
            int(plan.get("updated_at") or 0),
            int(plan.get("created_at") or 0),
            str(plan.get("id") or ""),
        ),
    )
    state = str(latest.get("state") or "").lower()
    return (state,) if state in _ROLLOUT_PROBLEM_STATES else ()


def latest_drain_problem_states(plans: Iterable[Mapping[str, object]]) -> tuple[str, ...]:
    latest_by_node: dict[int, Mapping[str, object]] = {}
    for plan in plans:
        try:
            node_id = int(plan.get("node_id") or 0)
        except (TypeError, ValueError):
            continue
        if node_id <= 0:
            continue
        state = str(plan.get("state") or "").lower()
        if state in {"review", "cancelled"}:
            continue
        current = latest_by_node.get(node_id)
        sort_key = (
            int(plan.get("updated_at") or 0),
            int(plan.get("created_at") or 0),
            str(plan.get("id") or ""),
        )
        current_key = (
            int(current.get("updated_at") or 0),
            int(current.get("created_at") or 0),
            str(current.get("id") or ""),
        ) if current is not None else (-1, -1, "")
        if sort_key > current_key:
            latest_by_node[node_id] = plan

    result: list[str] = []
    for node_id in sorted(latest_by_node):
        state = str(latest_by_node[node_id].get("state") or "").lower()
        if state in _DRAIN_PROBLEM_STATES:
            result.append(state)
    return tuple(result)


def latest_job_problem_statuses(runs: Iterable[JobLike]) -> tuple[str, ...]:
    """Return one current problem state per non-fleet job name.

    Job history is intentionally collapsed to the latest run for each name so an
    old failure does not remain an attention item after a later successful run.
    Fleet jobs are represented by their orchestration journals instead, avoiding
    duplicate counting of the same rollout/drain outcome.
    """
    latest: dict[str, str] = {}
    ordered = sorted(runs, key=lambda run: int(getattr(run, "id", 0)), reverse=True)
    for run in ordered:
        name = str(getattr(run, "name", "") or "").strip()
        if not name or name in latest or name.startswith("fleet."):
            continue
        latest[name] = str(getattr(run, "status", "") or "").strip().lower()
    return tuple(status for status in latest.values() if status in _JOB_PROBLEM_STATES)


def build_attention_summary(
    *,
    active_alerts: int,
    job_statuses: Iterable[str],
    infrastructure_states: Iterable[str],
    rollout_states: Iterable[str],
    drain_states: Iterable[str],
) -> AttentionSummary:
    """Build a bounded dashboard summary from already-known read-only states."""
    alerts = max(0, int(active_alerts))
    jobs = Counter(str(value or "").lower() for value in job_statuses)
    infra = Counter(str(value or "").lower() for value in infrastructure_states)
    rollout = Counter(str(value or "").lower() for value in rollout_states)
    drain = Counter(str(value or "").lower() for value in drain_states)

    jobs = Counter({key: jobs[key] for key in _JOB_PROBLEM_STATES if jobs[key]})
    infra = Counter({key: infra[key] for key in _INFRA_PROBLEM_STATES if infra[key]})
    rollout = Counter({key: rollout[key] for key in _ROLLOUT_PROBLEM_STATES if rollout[key]})
    drain = Counter({key: drain[key] for key in _DRAIN_PROBLEM_STATES if drain[key]})

    total = alerts + sum(jobs.values()) + sum(infra.values()) + sum(rollout.values()) + sum(drain.values())
    if total == 0:
        return AttentionSummary(total=0, lines=("✅ Требует внимания: нет",))

    lines = [f"⚠️ Требует внимания: {total}"]
    if alerts:
        lines.append(f"🚨 Активные оповещения: {alerts}")

    infra_parts: list[str] = []
    if infra["unhealthy"]:
        infra_parts.append(f"недоступно {infra['unhealthy']}")
    if infra["offline"]:
        infra_parts.append(f"не в сети {infra['offline']}")
    if infra["degraded"]:
        infra_parts.append(f"деградация {infra['degraded']}")
    if infra["unknown"]:
        infra_parts.append(f"неизвестно {infra['unknown']}")
    if infra_parts:
        icon = "🔴" if infra["unhealthy"] or infra["offline"] else "🟡"
        lines.append(f"{icon} Инфраструктура: " + " · ".join(infra_parts))

    job_parts: list[str] = []
    if jobs["failed"]:
        job_parts.append(f"ошибок {jobs['failed']}")
    if jobs["unknown"]:
        job_parts.append(f"неизвестно {jobs['unknown']}")
    if jobs["interrupted"]:
        job_parts.append(f"прервано {jobs['interrupted']}")
    if job_parts:
        icon = "🔴" if jobs["failed"] else "🟡"
        lines.append(f"{icon} Задания: " + " · ".join(job_parts))

    operation_parts: list[str] = []
    rollout_failed = rollout["failed"] + rollout["stopped_failed"]
    rollout_unknown = rollout["unknown"] + rollout["stopped_unknown"]
    if rollout_failed:
        operation_parts.append(f"обновление: ошибка {rollout_failed}")
    if rollout_unknown:
        operation_parts.append(f"обновление: неизвестно {rollout_unknown}")
    if rollout["interrupted"]:
        operation_parts.append(f"обновление: прервано {rollout['interrupted']}")
    if drain["partial"]:
        operation_parts.append(f"Drain: частично {drain['partial']}")
    if drain["failed"]:
        operation_parts.append(f"Drain: ошибка {drain['failed']}")
    if drain["unknown"]:
        operation_parts.append(f"Drain: неизвестно {drain['unknown']}")
    if drain["interrupted"]:
        operation_parts.append(f"Drain: прервано {drain['interrupted']}")
    if operation_parts:
        icon = "🔴" if rollout_failed or drain["failed"] else "🟡"
        lines.append(f"{icon} Операции с нодами: " + " · ".join(operation_parts))

    return AttentionSummary(total=total, lines=tuple(lines))
