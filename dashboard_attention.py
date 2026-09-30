from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping, Protocol


class JobLike(Protocol):
    id: int
    name: str
    status: str


class AlertLike(Protocol):
    code: str
    target: str
    active: int
    first_seen: int
    last_seen: int


@dataclass(frozen=True)
class AttentionSummary:
    total: int
    lines: tuple[str, ...]


@dataclass(frozen=True)
class AttentionItem:
    category: str
    stable_id: str
    status: str
    label: str
    context: str = ""
    updated_at: int = 0


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

_ALERT_LABELS = {
    "master_down": "Master / 3x-ui недоступен",
    "xray_down": "Xray не работает",
    "node_offline": "Нода не в сети",
    "job_failed": "Фоновое задание завершилось ошибкой",
    "disk_high": "Высокое использование диска",
    "backup_stale": "Резервная копия устарела",
}

_STATUS_LABELS = {
    "failed": "ошибка",
    "unknown": "неизвестно",
    "interrupted": "прервано",
    "offline": "не в сети",
    "unhealthy": "недоступно",
    "degraded": "деградация",
    "partial": "частично",
    "stopped_failed": "остановлено: ошибка",
    "stopped_unknown": "остановлено: неизвестно",
}


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_text(value: object, *, limit: int = 64) -> str:
    text = " ".join(str(value or "").replace("\x00", "").split())
    return text[:limit]


def latest_rollout_problem_plan(plans: Iterable[Mapping[str, object]]) -> Mapping[str, object] | None:
    effective = [
        plan for plan in plans
        if str(plan.get("state") or "").lower() not in {"review", "cancelled"}
    ]
    if not effective:
        return None
    latest = max(
        effective,
        key=lambda plan: (
            _int(plan.get("updated_at")),
            _int(plan.get("created_at")),
            str(plan.get("id") or ""),
        ),
    )
    state = str(latest.get("state") or "").lower()
    return latest if state in _ROLLOUT_PROBLEM_STATES else None


def latest_rollout_problem_states(plans: Iterable[Mapping[str, object]]) -> tuple[str, ...]:
    latest = latest_rollout_problem_plan(plans)
    if latest is None:
        return ()
    return (str(latest.get("state") or "").lower(),)


def latest_drain_problem_plans(plans: Iterable[Mapping[str, object]]) -> tuple[Mapping[str, object], ...]:
    latest_by_node: dict[int, Mapping[str, object]] = {}
    for plan in plans:
        node_id = _int(plan.get("node_id"))
        if node_id <= 0:
            continue
        state = str(plan.get("state") or "").lower()
        if state in {"review", "cancelled"}:
            continue
        current = latest_by_node.get(node_id)
        sort_key = (
            _int(plan.get("updated_at")),
            _int(plan.get("created_at")),
            str(plan.get("id") or ""),
        )
        current_key = (
            _int(current.get("updated_at")),
            _int(current.get("created_at")),
            str(current.get("id") or ""),
        ) if current is not None else (-1, -1, "")
        if sort_key > current_key:
            latest_by_node[node_id] = plan

    result: list[Mapping[str, object]] = []
    for node_id in sorted(latest_by_node):
        plan = latest_by_node[node_id]
        state = str(plan.get("state") or "").lower()
        if state in _DRAIN_PROBLEM_STATES:
            result.append(plan)
    return tuple(result)


def latest_drain_problem_states(plans: Iterable[Mapping[str, object]]) -> tuple[str, ...]:
    return tuple(
        str(plan.get("state") or "").lower()
        for plan in latest_drain_problem_plans(plans)
    )


def latest_job_problem_runs(runs: Iterable[JobLike]) -> tuple[JobLike, ...]:
    """Return the latest problematic run for each non-orchestration job name."""
    latest: dict[str, JobLike] = {}
    ordered = sorted(runs, key=lambda run: _int(getattr(run, "id", 0)), reverse=True)
    for run in ordered:
        name = str(getattr(run, "name", "") or "").strip()
        if not name or name in latest or name in {"fleet.rollout", "fleet.drain"}:
            continue
        latest[name] = run
    return tuple(
        run for run in latest.values()
        if str(getattr(run, "status", "") or "").strip().lower() in _JOB_PROBLEM_STATES
    )


def latest_job_problem_statuses(runs: Iterable[JobLike]) -> tuple[str, ...]:
    return tuple(
        str(getattr(run, "status", "") or "").strip().lower()
        for run in latest_job_problem_runs(runs)
    )


def build_attention_items(
    *,
    active_alerts: Iterable[AlertLike],
    job_runs: Iterable[JobLike],
    infrastructure: Iterable[Mapping[str, object]],
    rollout_plans: Iterable[Mapping[str, object]],
    drain_plans: Iterable[Mapping[str, object]],
) -> tuple[AttentionItem, ...]:
    """Build bounded, secret-free detail items from the same states as the summary."""
    items: list[AttentionItem] = []

    for alert in active_alerts:
        if not _int(getattr(alert, "active", 0)):
            continue
        code = _safe_text(getattr(alert, "code", ""), limit=40)
        target = _safe_text(getattr(alert, "target", ""), limit=48)
        if not code:
            continue
        category = "backups" if code == "backup_stale" else "alerts"
        label = _ALERT_LABELS.get(code, code)
        context = f"цель: {target}" if target else ""
        items.append(AttentionItem(
            category=category,
            stable_id=f"alert:{code}:{target or '-'}",
            status="failed",
            label=label,
            context=context,
            updated_at=_int(getattr(alert, "last_seen", 0)),
        ))

    for run in latest_job_problem_runs(job_runs):
        name = _safe_text(getattr(run, "name", ""), limit=56)
        status = str(getattr(run, "status", "") or "").strip().lower()
        category = "backups" if name.startswith("backup.") else "jobs"
        items.append(AttentionItem(
            category=category,
            stable_id=f"job:{name}:{_int(getattr(run, 'id', 0))}",
            status=status,
            label=name,
            context=_STATUS_LABELS.get(status, status),
            updated_at=_int(getattr(run, "finished_at", 0)) or _int(getattr(run, "started_at", 0)),
        ))

    for raw in infrastructure:
        status = str(raw.get("status") or "").lower()
        if status not in _INFRA_PROBLEM_STATES:
            continue
        stable_id = _safe_text(raw.get("stable_id"), limit=56) or "unknown"
        label = _safe_text(raw.get("label"), limit=72) or stable_id
        items.append(AttentionItem(
            category="infrastructure",
            stable_id=f"infra:{stable_id}",
            status=status,
            label=label,
            context=_STATUS_LABELS.get(status, status),
            updated_at=_int(raw.get("updated_at")),
        ))

    rollout = latest_rollout_problem_plan(rollout_plans)
    if rollout is not None:
        state = str(rollout.get("state") or "").lower()
        plan_id = _safe_text(rollout.get("id"), limit=32) or "latest"
        items.append(AttentionItem(
            category="operations",
            stable_id=f"rollout:{plan_id}",
            status=state,
            label="Контролируемое обновление нод",
            context=_STATUS_LABELS.get(state, state),
            updated_at=_int(rollout.get("updated_at")),
        ))

    for plan in latest_drain_problem_plans(drain_plans):
        state = str(plan.get("state") or "").lower()
        node_id = _int(plan.get("node_id"))
        plan_id = _safe_text(plan.get("id"), limit=32) or "latest"
        items.append(AttentionItem(
            category="operations",
            stable_id=f"drain:{node_id}:{plan_id}",
            status=state,
            label=f"Node Drain · node_id={node_id}",
            context=_STATUS_LABELS.get(state, state),
            updated_at=_int(plan.get("updated_at")),
        ))

    category_order = {"infrastructure": 0, "jobs": 1, "alerts": 2, "backups": 3, "operations": 4}
    return tuple(sorted(
        items,
        key=lambda item: (
            category_order.get(item.category, 99),
            -item.updated_at,
            item.stable_id,
        ),
    ))


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
