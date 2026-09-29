"""Fleet operations for direct 3x-ui nodes.

v4.13 safety model:
- read-only health is available to every admin role;
- fleet mutations are Admin+;
- direct nodes are identified by stable node_id;
- rollout reuses the existing two-phase UpdateService;
- canary must succeed before the remaining nodes can continue;
- mutations are sequential and stop on the first failed/unknown result;
- interrupted jobs are never resumed automatically.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import time
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_auth import ROLE_RANK, authorize_callback
from admin_ui import render_callback
from audit import audit_system
from backup_manager import BackupManager
from config import HostControlTarget, load_settings
from db import Database
from host_control import HostControlClient, HostControlError
from node_drain import DrainPlanStore, NodeDrainBlocked, NodeDrainError, NodeDrainService, NodeDrainUnknown
from node_ui import node_display_name, node_status_text
from system_backup import SystemBackupService
from version_api import same_version
from version_service import UpdateError, safe_error
from versions_updates import (
    read_state,
    resolve_target,
    service as update_service,
    stable_version,
)
from xui import NodeInfo, XUIClient, XUIError


settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
backup_manager = BackupManager(settings.db_path, settings.backup_dir, settings.backup_keep)
system_backup = SystemBackupService(backup_manager, settings.node_backup_targets, settings.host_control_targets)
drain_service = NodeDrainService(db, xui, settings)
drain_store = DrainPlanStore(Path(settings.db_path).parent / "fleet")
fleet_router = Router(name="fleet_operations")

MAX_MUTATION_TARGETS = 20
HEALTH_TIMEOUT = 8.0
PLAN_ID_RE = re.compile(r"^[0-9a-f]{12}$")
rollout_lock = asyncio.Lock()


class FleetStates(StatesGroup):
    maintenance = State()
    rollout = State()


class FleetError(UpdateError):
    pass


class FleetMutationUnknown(FleetError):
    """A state-changing request may have reached the target; never retry it automatically."""


class FleetPlanStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)

    def _path(self, plan_id: str) -> Path:
        if not PLAN_ID_RE.fullmatch(plan_id or ""):
            raise FleetError("Некорректный ID плана обновления нод.")
        return self.root / f"rollout-{plan_id}.json"

    def save(self, plan: dict[str, Any]) -> None:
        path = self._path(str(plan["id"]))
        fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(self.root))
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(plan, handle, ensure_ascii=False, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)

    def get(self, plan_id: str) -> dict[str, Any]:
        path = self._path(plan_id)
        if not path.is_file():
            raise FleetError("План обновления нод не найден.")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FleetError("Журнал плана обновления недоступен для чтения; изменение заблокировано.") from exc
        if not isinstance(data, dict) or data.get("id") != plan_id:
            raise FleetError("Журнал плана обновления не прошёл проверку идентичности.")
        return data

    def list(self) -> list[dict[str, Any]]:
        plans: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("rollout-*.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict) and PLAN_ID_RE.fullmatch(str(data.get("id") or "")):
                plans.append(data)
        return plans


plan_store = FleetPlanStore(Path(settings.db_path).parent / "fleet")


def _keyboard(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=data) for label, data in row]
        for row in rows
    ])


def _call_binding(call: CallbackQuery) -> dict[str, int]:
    if not call.from_user or not isinstance(call.message, Message):
        raise FleetError("Открой /admin заново, чтобы создать новую сессию операций с нодами.")
    return {
        "actor": int(call.from_user.id),
        "chat": int(call.message.chat.id),
        "message": int(call.message.message_id),
    }


def _node_label(node: NodeInfo) -> str:
    if not node.enable:
        icon = "🛠"
    elif node.status == "online":
        icon = "🟢"
    elif node.status == "offline":
        icon = "🔴"
    else:
        icon = "🟡"
    return f"{icon} {node_display_name(node.name)} · ID {node.id}"


async def _direct_nodes() -> list[NodeInfo]:
    nodes = await xui.nodes_list()
    return [node for node in nodes if node.id > 0 and not node.transitive]


def _direct_target(node: NodeInfo):
    return system_backup.target_for(node.name, node.id)


def _host_target(node: NodeInfo) -> HostControlTarget | None:
    for target in settings.host_control_targets:
        if target.node_id == node.id:
            return target
    needle = node.name.strip().casefold()
    for target in settings.host_control_targets:
        if target.node_id is None and target.name.strip().casefold() == needle:
            return target
    return None


async def _assess_node(node: NodeInfo) -> dict[str, Any]:
    direct = _direct_target(node)
    host = _host_target(node)
    direct_binding = "missing"
    host_binding = "missing"
    if direct is not None:
        direct_binding = "node_id" if direct.node_id == node.id else "legacy_name"
    if host is not None:
        host_binding = "node_id" if host.node_id == node.id else "legacy_name"

    direct_online = False
    direct_error = ""
    if direct is not None:
        client = system_backup.direct_client_for(node.name, node.id)
        if client is not None:
            try:
                async with asyncio.timeout(HEALTH_TIMEOUT):
                    await client.server_status()
                direct_online = True
            except Exception as exc:
                direct_error = type(exc).__name__

    host_state = "missing"
    if host is not None:
        client = HostControlClient(
            host.url,
            host.token,
            host.host_id,
            verify_tls=host.verify_tls,
            timeout_seconds=HEALTH_TIMEOUT,
        )
        try:
            async with asyncio.timeout(HEALTH_TIMEOUT + 1):
                status = await client.status()
            host_state = status.state
        except (HostControlError, TimeoutError):
            host_state = "unavailable"

    stable = direct_binding == "node_id" and host_binding == "node_id"
    master_online = node.status == "online"
    ready = bool(
        node.enable
        and master_online
        and direct_online
        and host_state == "running"
        and stable
    )
    if not node.enable:
        state = "maintenance"
    elif ready:
        state = "healthy"
    elif not master_online:
        state = "offline"
    else:
        state = "degraded"

    drain_plan = drain_store.latest_for_node(node.id)
    drain_state = str((drain_plan or {}).get("state") or "")
    if not node.enable:
        if drain_state == "draining":
            state = "draining"
        elif drain_state == "drained":
            state = "drained"
        elif drain_state in {"partial", "unknown", "interrupted"}:
            state = "degraded"

    problems: list[str] = []
    if not node.enable and drain_state in {"partial", "unknown", "interrupted"}:
        problems.append(f"Node Drain={drain_state}")
    if not master_online:
        problems.append(f"Master={node_status_text(node.status)}")
    if not direct_online:
        problems.append("API прямого подключения недоступен" + (f" ({direct_error})" if direct_error else ""))
    if host_state != "running":
        problems.append(f"Host Control={_host_state_text(host_state)}")
    if direct_binding != "node_id":
        problems.append(f"Привязка Direct Admin={_binding_text(direct_binding)}")
    if host_binding != "node_id":
        problems.append(f"Привязка Host Control={_binding_text(host_binding)}")

    return {
        "node_id": node.id,
        "name": node.name,
        "enabled": node.enable,
        "master_status": node.status,
        "direct_online": direct_online,
        "direct_binding": direct_binding,
        "host_state": host_state,
        "host_binding": host_binding,
        "stable": stable,
        "ready": ready,
        "state": state,
        "problems": problems,
    }


async def _fleet_assessments(nodes: list[NodeInfo] | None = None) -> list[dict[str, Any]]:
    selected = nodes if nodes is not None else await _direct_nodes()
    if not selected:
        return []
    return list(await asyncio.gather(*(_assess_node(node) for node in selected)))


def _health_icon(state: str) -> str:
    return {
        "healthy": "🟢",
        "maintenance": "🛠",
        "draining": "🚧",
        "drained": "✅",
        "offline": "🔴",
        "degraded": "🟡",
    }.get(state, "🟡")


HEALTH_STATE_LABELS = {
    "healthy": "здоровы",
    "maintenance": "обслуживание",
    "draining": "выводится из трафика",
    "drained": "выведена из трафика",
    "offline": "не в сети",
    "degraded": "деградация",
}


BINDING_LABELS = {
    "node_id": "node_id",
    "legacy_name": "привязка по старому имени",
    "missing": "не настроена",
}


HOST_STATE_LABELS = {
    "running": "работает",
    "stopped": "остановлен",
    "transitioning": "переходное состояние",
    "unavailable": "недоступен",
    "missing": "не настроен",
}


RESULT_LABELS = {
    "success": "успешно",
    "skipped": "без изменений",
    "failed": "ошибка",
    "unknown": "неизвестно",
    "not_touched": "не затронута",
    "pending": "ожидает",
    "changed": "изменено",
    "cancelled": "отменено",
    "running": "выполняется",
}


PLAN_STATE_LABELS = {
    "review": "проверка",
    "canary_running": "контрольная нода: выполняется",
    "canary_passed": "контрольная нода: успешно",
    "running": "выполняется",
    "success": "успешно",
    "cancelled": "отменено",
    "stopped_unknown": "остановлено: результат неизвестен",
    "stopped_failed": "остановлено: ошибка",
    "interrupted": "прервано",
}


def _health_state_text(state: str) -> str:
    return HEALTH_STATE_LABELS.get(state, state or "неизвестно")


def _binding_text(value: str) -> str:
    return BINDING_LABELS.get(value, value or "не настроена")


def _host_state_text(value: str) -> str:
    return HOST_STATE_LABELS.get(value, value or "неизвестно")


def _result_text(value: str) -> str:
    return RESULT_LABELS.get(value, value or "неизвестно")


def _plan_state_text(value: str) -> str:
    return PLAN_STATE_LABELS.get(value, value or "неизвестно")


def _fleet_home_keyboard() -> InlineKeyboardMarkup:
    return _keyboard([
        [("🩺 Состояние нод", "admin:fleet:health")],
        [
            ("🛠 Включить обслуживание", "admin:fleet:mt:e"),
            ("▶ Выключить обслуживание", "admin:fleet:mt:x"),
        ],
        [("🚧 Вывести из трафика", "admin:fleet:drain")],
        [("🚀 Контролируемое обновление", "admin:fleet:rollout")],
        [("🧾 Задания по нодам", "admin:fleet:jobs")],
        [("⬅ Инфраструктура", "admin:section:infrastructure")],
    ])


@fleet_router.callback_query(F.data == "admin:fleet")
async def fleet_home(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    await state.clear()
    await call.answer()
    await render_callback(
        call,
        "🌐 Операции с нодами\n\n"
        "Массовые изменения выполняются только для нод с прямым подключением, последовательно и с блокировкой при неопределённости. "
        "Контролируемое обновление сначала проверяется на одной контрольной ноде и останавливается при первой ошибке или неизвестном результате.",
        reply_markup=_fleet_home_keyboard(),
    )


@fleet_router.callback_query(F.data == "admin:fleet:health")
async def fleet_health(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    await call.answer()
    await render_callback(call, "🩺 Проверяю ноды…")
    try:
        nodes = await _direct_nodes()
        assessments = await _fleet_assessments(nodes)
    except Exception as exc:
        await render_callback(call, f"🔴 Состояние нод: {safe_error(exc)}", reply_markup=_fleet_home_keyboard())
        return

    counts = {name: 0 for name in ("healthy", "maintenance", "draining", "drained", "degraded", "offline")}
    lines = ["🩺 Состояние нод", ""]
    for item in assessments:
        counts[item["state"]] = counts.get(item["state"], 0) + 1
    lines.append(
        f"🟢 Здоровы: {counts['healthy']} · 🛠 Обслуживание: {counts['maintenance']} · "
        f"🚧 Drain: {counts['draining']} · ✅ Drained: {counts['drained']} · "
        f"🟡 Деградация: {counts['degraded']} · 🔴 Не в сети: {counts['offline']}"
    )
    lines.append("")
    for item in assessments[:50]:
        lines.append(
            f"{_health_icon(item['state'])} {node_display_name(str(item['name']))} · {_health_state_text(str(item['state']))} · ID {item['node_id']}\n"
            f"   Master: {node_status_text(str(item['master_status']))} · Прямое подключение: "
            f"{'в сети' if item['direct_online'] else 'не в сети'} ({_binding_text(str(item['direct_binding']))}) · "
            f"Host Control: {_host_state_text(str(item['host_state']))} ({_binding_text(str(item['host_binding']))})"
        )
        if item["problems"]:
            lines.append("   " + "; ".join(item["problems"][:3]))
    if not assessments:
        lines.append("Прямые ноды не найдены.")
    if len(assessments) > 50:
        lines.append(f"\nПоказаны первые 50 из {len(assessments)}.")

    await render_callback(
        call,
        "\n".join(lines),
        reply_markup=_keyboard([
            [("🔄 Обновить", "admin:fleet:health")],
            [("⬅ Операции с нодами", "admin:fleet")],
        ]),
    )


def _drain_summary(review) -> str:
    target_ids = list(review.target_inbound_ids)
    target_text = ", ".join(f"#{value}" for value in target_ids[:20]) or "нет"
    if len(target_ids) > 20:
        target_text += f" · … ещё {len(target_ids) - 20}"
    blocker_counts: dict[str, int] = {}
    for item in review.users:
        if item.blocker:
            blocker_counts[item.blocker] = blocker_counts.get(item.blocker, 0) + 1
    blocker_text = ", ".join(
        f"{key}={value}" for key, value in sorted(blocker_counts.items())
    ) or "нет"
    return (
        f"Нода: {node_display_name(review.node_name)} · ID {review.node_id}\n"
        f"Target Inbounds: {target_text}\n"
        f"Затронуто пользователей: {review.affected_users}\n"
        f"Готовы к переносу: {review.movable_users}\n"
        f"Blockers: {review.blockers} · {blocker_text}"
    )


@fleet_router.callback_query(F.data == "admin:fleet:drain")
async def drain_home(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    await call.answer()
    try:
        nodes = await _direct_nodes()
    except Exception as exc:
        await render_callback(
            call,
            f"🔴 Node Drain: {safe_error(exc)}",
            reply_markup=_fleet_home_keyboard(),
        )
        return
    rows: list[list[tuple[str, str]]] = []
    lines = [
        "🚧 Node Drain",
        "",
        "Drain отдельно от maintenance: сначала блокируются новые назначения, затем пользователи переводятся на policy alternatives по правилу attach-before-detach.",
        "",
    ]
    for node in nodes[:50]:
        plan = drain_store.latest_for_node(node.id)
        state = str((plan or {}).get("state") or "")
        suffix = {
            "draining": " · 🚧 draining",
            "drained": " · ✅ drained",
            "partial": " · 🟡 partial",
            "unknown": " · 🟡 unknown",
            "interrupted": " · 🟡 interrupted",
        }.get(state, "")
        rows.append([(
            f"🌍 {node_display_name(node.name)} · ID {node.id}{suffix}",
            f"admin:fleet:drain:n{node.id}",
        )])
    if not rows:
        lines.append("Прямые ноды не найдены.")
    rows.append([("⬅ Операции с нодами", "admin:fleet")])
    await render_callback(call, "\n".join(lines), reply_markup=_keyboard(rows))


@fleet_router.callback_query(F.data.regexp(r"^admin:fleet:drain:n[1-9][0-9]{0,18}$"))
async def drain_preflight(call: CallbackQuery):
    ok, role = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    try:
        node_id = int((call.data or "").rsplit("n", 1)[1])
    except (TypeError, ValueError):
        await call.answer("Некорректный ID ноды", show_alert=True)
        return
    await call.answer()
    await render_callback(call, "🚧 Node Drain: выполняю read-only preflight…")
    try:
        review = await drain_service.review(node_id)
    except Exception as exc:
        await render_callback(
            call,
            f"🔴 Node Drain preflight: {safe_error(exc)}",
            reply_markup=_keyboard([
                [("⬅ Node Drain", "admin:fleet:drain")],
            ]),
        )
        return
    rows: list[list[tuple[str, str]]] = []
    latest = drain_store.latest_for_node(node_id)
    latest_state = str((latest or {}).get("state") or "")
    if ROLE_RANK.get(role or "", 0) >= ROLE_RANK["admin"]:
        label = (
            "▶ Продолжить после проверки"
            if latest_state in {"partial", "unknown", "interrupted"}
            else "➡ Подготовить Drain"
        )
        rows.append([(label, f"admin:fleet:drain:n{node_id}:prepare")])
    rows.append([("🔄 Обновить", f"admin:fleet:drain:n{node_id}")])
    rows.append([("⬅ Node Drain", "admin:fleet:drain")])
    await render_callback(
        call,
        "🚧 Node Drain · preflight\n\n"
        + _drain_summary(review)
        + "\n\nBlockers не мутируются. Active Xray sessions специально не обрываются.",
        reply_markup=_keyboard(rows),
    )


@fleet_router.callback_query(F.data.regexp(r"^admin:fleet:drain:n[1-9][0-9]{0,18}:prepare$"))
async def drain_prepare(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    try:
        node_id = int((call.data or "").split(":")[-2][1:])
        review = await drain_service.review(node_id)
        actor = int(call.from_user.id) if call.from_user else 0
        plan = drain_store.create(review, actor_id=actor)
    except Exception as exc:
        await call.answer(str(exc)[:180], show_alert=True)
        return
    await call.answer()
    await render_callback(
        call,
        "🚧 Node Drain · подтверждение\n\n"
        + _drain_summary(review)
        + "\n\nСначала нода будет исключена из новых назначений через maintenance primitive. "
          "Разрушительные операции Xray/service не выполняются.",
        reply_markup=_keyboard([
            [("✅ Начать Drain", f"admin:fleet:drain:{plan['id']}:run")],
            [("✖ Отмена", f"admin:fleet:drain:{plan['id']}:cancel")],
        ]),
    )


@fleet_router.callback_query(F.data.regexp(r"^admin:fleet:drain:[0-9a-f]{12}:cancel$"))
async def drain_cancel(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    plan_id = (call.data or "").split(":")[-2]
    try:
        plan = drain_store.get(plan_id)
        if str(plan.get("state")) != "review":
            raise NodeDrainError("Запущенный Drain нельзя отменить как неприменённый.")
        plan["state"] = "cancelled"
        plan["updated_at"] = int(time.time())
        drain_store.save(plan)
    except Exception as exc:
        await call.answer(str(exc)[:180], show_alert=True)
        return
    await call.answer("Отменено")
    await render_callback(call, "⏹ Node Drain отменён до mutation.", reply_markup=_fleet_home_keyboard())


@fleet_router.callback_query(F.data.regexp(r"^admin:fleet:drain:[0-9a-f]{12}:run$"))
async def drain_run(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    plan_id = (call.data or "").split(":")[-2]
    try:
        plan = drain_store.get(plan_id)
    except Exception as exc:
        await call.answer(str(exc)[:180], show_alert=True)
        return
    if str(plan.get("state")) != "review":
        await call.answer("Drain уже запускался; mutation не повторяется.", show_alert=True)
        return

    actor = int(call.from_user.id) if call.from_user else 0
    node_id = int(plan.get("node_id") or 0)
    await call.answer()
    await render_callback(call, "🚧 Node Drain: выполняю последовательно…")

    run_id = await db.start_job_run(
        name="fleet.drain",
        trigger="admin",
        actor_id=actor,
        details=f"plan={plan_id}; node={node_id}",
    )
    started = time.monotonic()
    plan["state"] = "draining"
    plan["job_id"] = run_id
    plan["updated_at"] = int(time.time())
    drain_store.save(plan)
    await db.add_audit(
        actor_id=actor,
        action="fleet.drain.started",
        target_type="node",
        target_id=str(node_id),
        details=f"plan={plan_id}",
    )

    results: dict[str, Any] = {}
    final_state = "partial"
    job_status = "failed"
    try:
        await _set_node_enabled(node_id, False)
        for item in plan.get("users") or []:
            telegram_id = int(item.get("telegram_id") or 0)
            if not telegram_id or not item.get("target_inbound_ids"):
                continue
            if item.get("blocker"):
                results[str(telegram_id)] = {"status": "blocked", "reason": str(item.get("blocker"))}
                continue
            try:
                outcome = await drain_service.evacuate_user(
                    node_id,
                    telegram_id,
                    target_inbound_ids=plan.get("target_inbound_ids") or [],
                )
                results[str(telegram_id)] = {"status": str(outcome.get("status") or "success")}
            except NodeDrainBlocked as exc:
                results[str(telegram_id)] = {"status": "blocked", "reason": str(exc)[:160]}
            except NodeDrainUnknown as exc:
                results[str(telegram_id)] = {"status": "unknown", "reason": str(exc)[:160]}
                final_state = "unknown"
                job_status = "unknown"
                break
            except Exception as exc:
                results[str(telegram_id)] = {"status": "failed", "reason": type(exc).__name__}

        if final_state != "unknown":
            post = await drain_service.review(
                node_id,
                target_inbound_ids=plan.get("target_inbound_ids") or [],
            )
            if post.affected_users == 0 and post.blockers == 0:
                final_state = "drained"
                job_status = "success"
            else:
                final_state = "partial"
                job_status = "failed"
            plan["remaining_affected"] = post.affected_users
            plan["remaining_blockers"] = post.blockers
    except FleetMutationUnknown as exc:
        final_state = "unknown"
        job_status = "unknown"
        results["_node"] = {"status": "unknown", "reason": str(exc)[:160]}
    except Exception as exc:
        final_state = "failed"
        job_status = "failed"
        results["_node"] = {"status": "failed", "reason": type(exc).__name__}

    plan["state"] = final_state
    plan["results"] = results
    plan["updated_at"] = int(time.time())
    drain_store.save(plan)
    details = (
        f"plan={plan_id}; node={node_id}; state={final_state}; "
        f"remaining={int(plan.get('remaining_affected') or 0)}; "
        f"blockers={int(plan.get('remaining_blockers') or 0)}"
    )
    await db.finish_job_run(
        run_id,
        status=job_status,
        duration_ms=max(0, int((time.monotonic() - started) * 1000)),
        details=details,
    )
    await db.add_audit(
        actor_id=actor,
        action=f"fleet.drain.{final_state}",
        target_type="node",
        target_id=str(node_id),
        details=details,
        success=final_state == "drained",
    )
    icon = {"drained": "✅", "partial": "🟡", "unknown": "🟡", "failed": "🔴"}.get(final_state, "•")
    await render_callback(
        call,
        f"{icon} Node Drain · {final_state}\n\n"
        f"Нода: ID {node_id}\n"
        f"Осталось назначений: {int(plan.get('remaining_affected') or 0)}\n"
        f"Blockers: {int(plan.get('remaining_blockers') or 0)}\n\n"
        "Active Xray sessions не обрывались специально. Разрушительные операции Xray/service не выполнялись.\n"
        "Возврат ноды: выключите обслуживание и выполните обычное policy-согласование; обратный replay Drain не выполняется.",
        reply_markup=_keyboard([
            [("🔄 Проверить", f"admin:fleet:drain:n{node_id}")],
            [("⬅ Операции с нодами", "admin:fleet")],
        ]),
    )


async def _selection_data(state: FSMContext) -> tuple[list[int], str, str]:
    data = await state.get_data()
    selected = []
    for value in data.get("fleet_selected", []):
        try:
            node_id = int(value)
        except (TypeError, ValueError):
            continue
        if node_id > 0 and node_id not in selected:
            selected.append(node_id)
    return selected, str(data.get("fleet_kind") or ""), str(data.get("fleet_mode") or "")


async def _start_selection(
    call: CallbackQuery,
    state: FSMContext,
    *,
    kind: str,
    mode: str,
) -> None:
    if kind == "maintenance":
        await state.set_state(FleetStates.maintenance)
    else:
        await state.set_state(FleetStates.rollout)
    await state.set_data({
        "fleet_kind": kind,
        "fleet_mode": mode,
        "fleet_selected": [],
    })
    await _render_selection(call, state)


async def _render_selection(call: CallbackQuery, state: FSMContext) -> None:
    selected, kind, mode = await _selection_data(state)
    nodes = await _direct_nodes()
    node_map = {node.id: node for node in nodes}
    selected = [node_id for node_id in selected if node_id in node_map]
    await state.update_data(fleet_selected=selected)

    title = "🛠 Обслуживание нод" if kind == "maintenance" else "🚀 Контролируемое обновление"
    mode_text = {
        ("maintenance", "e"): "Включить обслуживание",
        ("maintenance", "x"): "Выключить обслуживание",
        ("rollout", "p"): "3x-ui: последняя стабильная",
        ("rollout", "x"): "Ядро Xray",
    }.get((kind, mode), mode)

    rows: list[list[tuple[str, str]]] = []
    prefix = "admin:fleet:mt" if kind == "maintenance" else "admin:fleet:ro"
    for node in nodes[:50]:
        chosen = node.id in selected
        rows.append([(
            ("✅ " if chosen else "⬜ ") + f"{node_display_name(node.name)} · ID {node.id}",
            f"{prefix}:{mode}:n{node.id}",
        )])
    if selected:
        rows.append([(
            "➡ Проверить" if kind == "maintenance" or mode == "p" else "➡ Выбрать версию Xray",
            f"{prefix}:{mode}:review",
        )])
    rows.append([("✖ Отмена", "admin:fleet")])

    await render_callback(
        call,
        f"{title}\n\nРежим: {mode_text}\nВыбрано: {len(selected)}/{MAX_MUTATION_TARGETS}\n\n"
        "Выбери ноды с прямым подключением. Изменения ещё не выполняются.",
        reply_markup=_keyboard(rows),
    )


async def _toggle_selection(call: CallbackQuery, state: FSMContext, *, kind: str, mode: str, node_id: int) -> None:
    selected, stored_kind, stored_mode = await _selection_data(state)
    if (stored_kind, stored_mode) != (kind, mode):
        raise FleetError("Выбор нод устарел. Начни заново.")
    nodes = await _direct_nodes()
    valid = {node.id for node in nodes}
    if node_id not in valid:
        raise FleetError("Нода недоступна для прямого управления.")
    if node_id in selected:
        selected.remove(node_id)
    else:
        if len(selected) >= MAX_MUTATION_TARGETS:
            raise FleetError(f"За одно задание по нодам можно изменить не более {MAX_MUTATION_TARGETS} нод.")
        selected.append(node_id)
    await state.update_data(fleet_selected=selected)
    await _render_selection(call, state)


@fleet_router.callback_query(F.data.regexp(r"^admin:fleet:mt:(e|x)$"))
async def maintenance_start(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    await call.answer()
    mode = (call.data or "").rsplit(":", 1)[-1]
    await _start_selection(call, state, kind="maintenance", mode=mode)


@fleet_router.callback_query(F.data.regexp(r"^admin:fleet:mt:(e|x):n[1-9][0-9]{0,18}$"))
async def maintenance_toggle(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    await call.answer()
    parts = (call.data or "").split(":")
    try:
        await _toggle_selection(call, state, kind="maintenance", mode=parts[3], node_id=int(parts[4][1:]))
    except FleetError as exc:
        await call.answer(str(exc)[:180], show_alert=True)


@fleet_router.callback_query(F.data.regexp(r"^admin:fleet:mt:(e|x):review$"))
async def maintenance_review(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    selected, kind, mode = await _selection_data(state)
    if kind != "maintenance" or not selected:
        await call.answer("Выбор устарел", show_alert=True)
        return
    nodes = {node.id: node for node in await _direct_nodes()}
    names = [nodes[node_id].name for node_id in selected if node_id in nodes]
    desired = "обслуживание" if mode == "e" else "включена"
    await call.answer()
    await render_callback(
        call,
        "🛠 Обслуживание нод · проверка\n\n"
        f"Целевое состояние: {desired}\n"
        f"Ноды ({len(names)}): " + ", ".join(names) + "\n\n"
        "Операции выполняются последовательно. При неизвестном результате пакет останавливается; "
        "изменение автоматически не повторяется.",
        reply_markup=_keyboard([
            [("✅ Выполнить", f"admin:fleet:mt:{mode}:run")],
            [("⬅ Изменить выбор", f"admin:fleet:mt:{mode}")],
            [("✖ Отмена", "admin:fleet")],
        ]),
    )


async def _set_node_enabled(node_id: int, enabled: bool) -> str:
    node = await xui.node_get(node_id)
    if node.transitive:
        raise FleetError("Изменение транзитной ноды запрещено.")
    if node.enable == enabled:
        return "skipped"
    try:
        await xui.node_set_enable(node_id, enabled)
    except Exception as exc:
        raise FleetMutationUnknown(
            f"Результат изменения обслуживания ноды {node_id} неизвестен; запрос не повторялся ({type(exc).__name__})."
        ) from exc
    check = await xui.node_get(node_id)
    if check.enable != enabled:
        raise FleetMutationUnknown(
            f"Нода {node_id} не подтвердила запрошенное состояние обслуживания; запрос не повторялся."
        )
    return "changed"


@fleet_router.callback_query(F.data.regexp(r"^admin:fleet:mt:(e|x):run$"))
async def maintenance_run(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    selected, kind, stored_mode = await _selection_data(state)
    mode = (call.data or "").split(":")[3]
    if kind != "maintenance" or stored_mode != mode or not selected:
        await call.answer("Выбор устарел", show_alert=True)
        return
    desired_enabled = mode == "x"
    actor = int(call.from_user.id) if call.from_user else 0
    await call.answer()
    await render_callback(call, "🛠 Обслуживание нод: выполняю последовательно…")

    run_id = await db.start_job_run(
        name="fleet.maintenance",
        trigger="admin",
        actor_id=actor,
        details=f"mode={mode}; nodes={','.join(map(str, selected))}",
    )
    started = time.monotonic()
    await db.add_audit(
        actor_id=actor,
        action="fleet.maintenance.started",
        target_type="fleet",
        target_id=str(run_id),
        details=f"mode={mode}; nodes={','.join(map(str, selected))}",
    )
    results: list[str] = []
    status = "success"
    for index, node_id in enumerate(selected):
        try:
            outcome = await _set_node_enabled(node_id, desired_enabled)
            results.append(f"✅ n{node_id}: {_result_text(outcome)}")
        except FleetMutationUnknown as exc:
            results.append(f"🟡 n{node_id}: неизвестно")
            results.extend(f"⏸ n{pending}: не затронута" for pending in selected[index + 1:])
            status = "unknown"
            break
        except Exception as exc:
            results.append(f"🔴 n{node_id}: {type(exc).__name__}")
            results.extend(f"⏸ n{pending}: не затронута" for pending in selected[index + 1:])
            status = "failed"
            break

    details = f"mode={mode}; " + "; ".join(results)
    await db.finish_job_run(
        run_id,
        status=status,
        duration_ms=max(0, int((time.monotonic() - started) * 1000)),
        details=details[:1500],
    )
    await db.add_audit(
        actor_id=actor,
        action="fleet.maintenance.completed",
        target_type="fleet",
        target_id=str(run_id),
        details=details[:1500],
        success=status == "success",
    )
    await state.clear()
    await render_callback(
        call,
        "🛠 Обслуживание нод · результат\n\n" + "\n".join(results),
        reply_markup=_fleet_home_keyboard(),
    )


@fleet_router.callback_query(F.data == "admin:fleet:rollout")
async def rollout_home(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    await state.clear()
    await call.answer()
    await render_callback(
        call,
        "🚀 Контролируемое обновление\n\n"
        "Контрольная нода → явное продолжение → остальные ноды по одной. "
        "Для каждой ноды выполняются предварительная проверка обновления и проверенная резервная копия. "
        "При ошибке или неизвестном результате обновление останавливается, а проблемная нода остаётся в обслуживании.",
        reply_markup=_keyboard([
            [("⬆️ 3x-ui: последняя стабильная", "admin:fleet:ro:p")],
            [("⚡ Ядро Xray", "admin:fleet:ro:x")],
            [("⬅ Операции с нодами", "admin:fleet")],
        ]),
    )


@fleet_router.callback_query(F.data.regexp(r"^admin:fleet:ro:(p|x)$"))
async def rollout_start(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    await call.answer()
    mode = (call.data or "").rsplit(":", 1)[-1]
    await _start_selection(call, state, kind="rollout", mode=mode)


@fleet_router.callback_query(F.data.regexp(r"^admin:fleet:ro:(p|x):n[1-9][0-9]{0,18}$"))
async def rollout_toggle(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    await call.answer()
    parts = (call.data or "").split(":")
    try:
        await _toggle_selection(call, state, kind="rollout", mode=parts[3], node_id=int(parts[4][1:]))
    except FleetError as exc:
        await call.answer(str(exc)[:180], show_alert=True)


async def _common_xray_versions(node_ids: list[int]) -> list[str]:
    nodes = {node.id: node for node in await _direct_nodes()}
    lists: list[list[str]] = []
    for node_id in node_ids:
        node = nodes.get(node_id)
        if node is None:
            raise FleetError(f"Нода {node_id} исчезла.")
        assessment = await _assess_node(node)
        if not assessment["ready"]:
            raise FleetError(f"{node_display_name(node.name)} не готова к обновлению: " + "; ".join(assessment["problems"]))
        target = await resolve_target(f"n{node_id}")
        lists.append(await target.client.get_xray_versions())
    if not lists:
        return []
    common = set(lists[0])
    for values in lists[1:]:
        common.intersection_update(values)
    return [value for value in lists[0] if value in common]


@fleet_router.callback_query(F.data.regexp(r"^admin:fleet:ro:(p|x):review$"))
async def rollout_review(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    selected, kind, mode = await _selection_data(state)
    if kind != "rollout" or not selected:
        await call.answer("Выбор устарел", show_alert=True)
        return
    await call.answer()
    if mode == "x":
        await render_callback(call, "⚡ Проверяю общие версии Xray…")
        try:
            versions = await _common_xray_versions(selected)
        except Exception as exc:
            await render_callback(call, f"🔴 {safe_error(exc)}", reply_markup=_fleet_home_keyboard())
            return
        if not versions:
            await render_callback(
                call,
                "🔴 У выбранных нод нет общей версии Xray.",
                reply_markup=_fleet_home_keyboard(),
            )
            return
        rows = [[(f"📦 {value}", f"admin:fleet:ro:x:v:{value}")] for value in versions[:10]]
        rows.append([("⬅ Изменить выбор", "admin:fleet:ro:x")])
        await render_callback(
            call,
            "⚡ Контролируемое обновление Xray\n\nВыбери общую версию для всех выбранных нод. "
            "Показаны первые 10 общих версий.",
            reply_markup=_keyboard(rows),
        )
        return
    try:
        await _create_rollout_review(call, state, component="panel", desired="")
    except Exception as exc:
        await render_callback(call, f"🔴 {safe_error(exc)}", reply_markup=_fleet_home_keyboard())


@fleet_router.callback_query(F.data.regexp(r"^admin:fleet:ro:x:v:[A-Za-z0-9.-]+$"))
async def rollout_xray_version(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    selected, kind, mode = await _selection_data(state)
    if kind != "rollout" or mode != "x" or not selected:
        await call.answer("Выбор устарел", show_alert=True)
        return
    desired = (call.data or "").split(":")[-1]
    await call.answer()
    try:
        await _create_rollout_review(call, state, component="xray", desired=desired)
    except Exception as exc:
        await render_callback(call, f"🔴 {safe_error(exc)}", reply_markup=_fleet_home_keyboard())


async def _create_rollout_review(
    call: CallbackQuery,
    state: FSMContext,
    *,
    component: str,
    desired: str,
) -> None:
    selected, kind, _ = await _selection_data(state)
    if kind != "rollout" or not selected:
        raise FleetError("Выбор устарел.")
    binding = _call_binding(call)
    nodes = {node.id: node for node in await _direct_nodes()}
    pending: list[int] = []
    skipped: list[int] = []
    desired_by_node: dict[str, str] = {}
    names: dict[str, str] = {}

    await render_callback(call, "🚀 Проверяю готовность к обновлению и версии…")
    for node_id in selected:
        node = nodes.get(node_id)
        if node is None:
            raise FleetError(f"Нода {node_id} исчезла.")
        assessment = await _assess_node(node)
        if not assessment["ready"]:
            raise FleetError(f"{node_display_name(node.name)} не готова к обновлению: " + "; ".join(assessment["problems"]))
        target = await resolve_target(f"n{node_id}")
        snapshot = await read_state(target)
        if component == "panel":
            node_desired = await stable_version(target)
            current = snapshot.panel
        else:
            available = await target.client.get_xray_versions()
            if desired not in available:
                raise FleetError(f"{node_display_name(node.name)}: выбранная версия Xray недоступна.")
            node_desired = desired
            current = snapshot.xray
        desired_by_node[str(node_id)] = node_desired
        names[str(node_id)] = node.name
        if same_version(current, node_desired):
            skipped.append(node_id)
        else:
            pending.append(node_id)

    plan = {
        "id": secrets.token_hex(6),
        "actor": binding["actor"],
        "chat": binding["chat"],
        "message": binding["message"],
        "component": component,
        "selected": selected,
        "pending": pending,
        "skipped": skipped,
        "completed": [],
        "results": {},
        "desired": desired_by_node,
        "names": names,
        "canary": pending[0] if pending else 0,
        "state": "review" if pending else "success",
        "job_id": 0,
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
    }
    plan_store.save(plan)
    if not pending:
        await _start_rollout_job(plan)
        await _finish_rollout_job(plan, "success")
    await state.clear()
    await _render_plan(call, plan)


def _plan_status_icon(value: str) -> str:
    return {
        "success": "✅",
        "skipped": "⏭",
        "failed": "🔴",
        "unknown": "🟡",
        "not_touched": "⏸",
    }.get(value, "•")


def _plan_text(plan: dict[str, Any]) -> str:
    component = "3x-ui" if plan["component"] == "panel" else "Xray"
    lines = [
        f"🚀 Контролируемое обновление · {component}",
        "",
        f"План: {plan['id']}",
        f"Состояние: {_plan_state_text(str(plan['state']))}",
        f"Целей: {len(plan['selected'])} · ожидают: {len(plan['pending'])}",
    ]
    if plan.get("canary"):
        node_id = int(plan["canary"])
        lines.append(f"Контрольная нода: {plan['names'].get(str(node_id), 'нода')} · ID {node_id}")
    lines.append("")
    results = plan.get("results") or {}
    for node_id in plan["selected"]:
        raw = results.get(str(node_id))
        if raw:
            lines.append(
                f"{_plan_status_icon(str(raw.get('status')))} "
                f"{plan['names'].get(str(node_id), 'нода')} · {_result_text(str(raw.get('status') or ''))}"
            )
        elif node_id in plan.get("skipped", []):
            lines.append(f"⏭ {plan['names'].get(str(node_id), 'нода')} · уже актуальна")
        else:
            lines.append(f"• {plan['names'].get(str(node_id), 'нода')} · ожидает")
    return "\n".join(lines)


def _plan_keyboard(plan: dict[str, Any]) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = []
    if plan["state"] == "review" and plan.get("canary"):
        rows.append([("🐤 Запустить контрольную ноду", f"admin:fleet:run:{plan['id']}:canary")])
        rows.append([("✖ Отмена", f"admin:fleet:run:{plan['id']}:cancel")])
    elif plan["state"] == "canary_passed":
        rows.append([("✅ Продолжить остальные", f"admin:fleet:run:{plan['id']}:continue")])
        rows.append([("⏹ Завершить после контрольной ноды", f"admin:fleet:run:{plan['id']}:cancel")])
    rows.append([("🧾 Задания по нодам", "admin:fleet:jobs")])
    rows.append([("⬅ Операции с нодами", "admin:fleet")])
    return _keyboard(rows)


async def _render_plan(call: CallbackQuery, plan: dict[str, Any], prefix: str = "") -> None:
    text = (prefix + "\n\n" if prefix else "") + _plan_text(plan)
    sent = await render_callback(call, text, reply_markup=_plan_keyboard(plan))
    if isinstance(sent, Message) and int(plan.get("message") or 0) != sent.message_id:
        plan["message"] = sent.message_id
        plan["updated_at"] = int(time.time())
        plan_store.save(plan)


def _validate_plan_call(plan: dict[str, Any], call: CallbackQuery) -> None:
    binding = _call_binding(call)
    if (int(plan.get("actor") or 0), int(plan.get("chat") or 0)) != (
        binding["actor"], binding["chat"]
    ):
        raise FleetError("Этот план обновления принадлежит другой сессии администратора.")


async def _start_rollout_job(plan: dict[str, Any]) -> None:
    if int(plan.get("job_id") or 0):
        return
    plan["job_id"] = await db.start_job_run(
        name="fleet.rollout",
        trigger="admin",
        actor_id=int(plan["actor"]),
        details=(
            f"plan={plan['id']}; component={plan['component']}; "
            f"nodes={','.join(map(str, plan['selected']))}"
        ),
    )
    await db.add_audit(
        actor_id=int(plan["actor"]),
        action="fleet.rollout.started",
        target_type="fleet",
        target_id=plan["id"],
        details=f"component={plan['component']}; nodes={','.join(map(str, plan['selected']))}",
    )
    plan_store.save(plan)


async def _finish_rollout_job(plan: dict[str, Any], status: str) -> None:
    job_id = int(plan.get("job_id") or 0)
    if job_id:
        elapsed = max(0, (int(time.time()) - int(plan.get("created_at") or time.time())) * 1000)
        results = plan.get("results") or {}
        skipped = set(plan.get("skipped") or [])
        summary = "; ".join(
            f"n{node_id}={results.get(str(node_id), {}).get('status', 'skipped' if node_id in skipped else 'pending')}"
            for node_id in plan["selected"]
        )
        await db.finish_job_run(
            job_id,
            status=status,
            duration_ms=elapsed,
            details=f"plan={plan['id']}; {summary}"[:1500],
        )
    await db.add_audit(
        actor_id=int(plan["actor"]),
        action="fleet.rollout.completed",
        target_type="fleet",
        target_id=plan["id"],
        details=f"state={plan['state']}; component={plan['component']}",
        success=status == "success",
    )


async def _execute_rollout_node(
    plan: dict[str, Any],
    node_id: int,
    call: CallbackQuery,
) -> tuple[str, str]:
    node = await xui.node_get(node_id)
    assessment = await _assess_node(node)
    if not assessment["ready"]:
        return "failed", "доступность изменилась до предварительной проверки"

    key = f"n{node_id}"
    desired = str(plan["desired"][str(node_id)])
    ids = _call_binding(call)
    op = None
    try:
        op = await update_service.prepare(
            key,
            str(plan["component"]),
            desired,
            **ids,
        )
    except Exception as exc:
        return "failed", f"предварительная проверка: {safe_error(exc)}"

    try:
        await _set_node_enabled(node_id, False)
    except FleetMutationUnknown as exc:
        try:
            await update_service.cancel(op.nonce, **ids)
        except Exception:
            pass
        return "unknown", str(exc)
    except Exception as exc:
        try:
            await update_service.cancel(op.nonce, **ids)
        except Exception:
            pass
        return "failed", f"обслуживание: {safe_error(exc)}"

    try:
        target = await resolve_target(key)
        direct_state = await read_state(target)
        if not direct_state.healthy:
            try:
                await update_service.cancel(op.nonce, **ids)
            except Exception:
                pass
            return "failed", "проверка прямого подключения не пройдена после включения обслуживания; обновление не отправлялось"
    except Exception as exc:
        try:
            await update_service.cancel(op.nonce, **ids)
        except Exception:
            pass
        return "failed", f"проверка прямого подключения перед отправкой: {safe_error(exc)}"

    try:
        result = await update_service.execute(
            op.nonce,
            allow_prepared_maintenance=True,
            **ids,
        )
    except Exception as exc:
        return "unknown", f"выполнение обновления: {safe_error(exc)}"

    if result.state != "success":
        return ("unknown" if result.state in {"dispatching", "verifying", "unconfirmed"} else "failed",
                f"результат обновления={result.state}; operation={result.nonce}")

    try:
        await _set_node_enabled(node_id, True)
    except Exception as exc:
        return "unknown", f"обновление выполнено, но выход из обслуживания не подтверждён: {safe_error(exc)}"

    try:
        await xui.node_probe(node_id)
    except XUIError:
        pass
    return "success", f"operation={result.nonce}; целевая={result.desired}; фактическая={result.actual}"


async def _record_plan_result(
    plan: dict[str, Any],
    node_id: int,
    status: str,
    details: str,
) -> None:
    results = dict(plan.get("results") or {})
    results[str(node_id)] = {
        "status": status,
        "details": details[:500],
        "at": int(time.time()),
    }
    plan["results"] = results
    if status == "success" and node_id not in plan["completed"]:
        plan["completed"].append(node_id)
    if node_id in plan["pending"]:
        plan["pending"].remove(node_id)
    plan["updated_at"] = int(time.time())
    plan_store.save(plan)
    await db.add_audit(
        actor_id=int(plan["actor"]),
        action=f"fleet.rollout.node.{status}",
        target_type="node",
        target_id=str(node_id),
        details=f"plan={plan['id']}; {details}"[:1500],
        success=status == "success",
    )


@fleet_router.callback_query(F.data.regexp(r"^admin:fleet:run:[0-9a-f]{12}:(canary|continue|cancel)$"))
async def rollout_run(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    parts = (call.data or "").split(":")
    plan_id, action = parts[3], parts[4]
    try:
        plan = plan_store.get(plan_id)
        _validate_plan_call(plan, call)
    except FleetError as exc:
        await call.answer(str(exc)[:180], show_alert=True)
        return

    await call.answer()
    async with rollout_lock:
        plan = plan_store.get(plan_id)
        try:
            _validate_plan_call(plan, call)
            if action == "cancel":
                if plan["state"] not in {"review", "canary_passed"}:
                    raise FleetError("Этот план обновления больше нельзя отменить без ручной проверки.")
                plan["state"] = "cancelled"
                for node_id in list(plan["pending"]):
                    (plan.setdefault("results", {}))[str(node_id)] = {
                        "status": "not_touched",
                        "details": "отменено до отправки",
                        "at": int(time.time()),
                    }
                plan["pending"] = []
                plan["updated_at"] = int(time.time())
                plan_store.save(plan)
                await _start_rollout_job(plan)
                await _finish_rollout_job(plan, "cancelled")
                await _render_plan(call, plan, "⏹ Обновление остановлено оператором. Новые изменения не отправлялись.")
                return

            await _start_rollout_job(plan)

            if action == "canary":
                if plan["state"] != "review" or not plan.get("canary"):
                    raise FleetError("Контрольная нода недоступна для этого плана.")
                node_id = int(plan["canary"])
                plan["state"] = "canary_running"
                plan["updated_at"] = int(time.time())
                plan_store.save(plan)
                await _render_plan(call, plan, f"🐤 Контрольная нода: {plan['names'].get(str(node_id), 'нода')}…")
                status, details = await _execute_rollout_node(plan, node_id, call)
                await _record_plan_result(plan, node_id, status, details)
                if status == "success":
                    if plan["pending"]:
                        plan["state"] = "canary_passed"
                    else:
                        plan["state"] = "success"
                        await _finish_rollout_job(plan, "success")
                else:
                    plan["state"] = "stopped_unknown" if status == "unknown" else "stopped_failed"
                    for pending in list(plan["pending"]):
                        (plan.setdefault("results", {}))[str(pending)] = {
                            "status": "not_touched",
                            "details": "остановлено после ошибки контрольной ноды",
                            "at": int(time.time()),
                        }
                    plan["pending"] = []
                    await _finish_rollout_job(plan, "unknown" if status == "unknown" else "failed")
                plan["updated_at"] = int(time.time())
                plan_store.save(plan)
                await _render_plan(call, plan)
                return

            if action == "continue":
                if plan["state"] != "canary_passed":
                    raise FleetError("Перед продолжением требуется успешное обновление контрольной ноды.")
                plan["state"] = "running"
                plan["updated_at"] = int(time.time())
                plan_store.save(plan)
                while plan["pending"]:
                    node_id = int(plan["pending"][0])
                    await _render_plan(call, plan, f"🚀 Обновляю {plan['names'].get(str(node_id), 'нода')}…")
                    status, details = await _execute_rollout_node(plan, node_id, call)
                    await _record_plan_result(plan, node_id, status, details)
                    if status != "success":
                        plan["state"] = "stopped_unknown" if status == "unknown" else "stopped_failed"
                        for pending in list(plan["pending"]):
                            (plan.setdefault("results", {}))[str(pending)] = {
                                "status": "not_touched",
                                "details": "остановлено после ошибки",
                                "at": int(time.time()),
                            }
                        plan["pending"] = []
                        await _finish_rollout_job(plan, "unknown" if status == "unknown" else "failed")
                        break
                else:
                    plan["state"] = "success"
                    await _finish_rollout_job(plan, "success")
                plan["updated_at"] = int(time.time())
                plan_store.save(plan)
                await _render_plan(call, plan)
                return
        except Exception as exc:
            plan = plan_store.get(plan_id)
            if plan.get("state") in {"canary_running", "running"}:
                plan["state"] = "interrupted"
                plan["updated_at"] = int(time.time())
                plan_store.save(plan)
                await _finish_rollout_job(plan, "unknown")
            await _render_plan(call, plan, f"🔴 {safe_error(exc)}")


@fleet_router.callback_query(F.data == "admin:fleet:jobs")
async def fleet_jobs(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    await call.answer()
    rows = await db.list_job_runs(limit=100)
    fleet = [row for row in rows if row.name.startswith("fleet.")][:15]
    lines = ["🧾 Задания по нодам", ""]
    for row in fleet:
        icon = {
            "success": "✅",
            "failed": "🔴",
            "unknown": "🟡",
            "running": "⏳",
            "cancelled": "⏹",
        }.get(row.status, "•")
        lines.append(f"{icon} #{row.id} · {row.name} · {_result_text(row.status)}")
        if row.details:
            lines.append("   " + row.details[:180])
    if not fleet:
        lines.append("Заданий по нодам пока нет.")
    await render_callback(
        call,
        "\n".join(lines),
        reply_markup=_keyboard([
            [("🔄 Обновить", "admin:fleet:jobs")],
            [("⬅ Операции с нодами", "admin:fleet")],
        ]),
    )


async def recover_fleet_operations() -> int:
    """Mark interrupted fleet mutations unknown without replaying any mutation."""
    recovered = 0
    for plan in plan_store.list():
        if plan.get("state") not in {"canary_running", "running"}:
            continue
        plan["state"] = "interrupted"
        plan["updated_at"] = int(time.time())
        plan_store.save(plan)
        job_id = int(plan.get("job_id") or 0)
        if job_id:
            await db.finish_job_run(
                job_id,
                status="unknown",
                duration_ms=max(0, (int(time.time()) - int(plan.get("created_at") or time.time())) * 1000),
                details=f"plan={plan['id']}; process restarted; mutation_not_retried=true",
            )
        await audit_system(
            db,
            "fleet.rollout.recovered",
            target_type="fleet",
            target_id=str(plan["id"]),
            details="process restarted; rollout not resumed; mutation_not_retried=true",
            success=False,
        )
        recovered += 1

    for plan in drain_store.list():
        if plan.get("state") != "draining":
            continue
        plan["state"] = "interrupted"
        plan["updated_at"] = int(time.time())
        drain_store.save(plan)
        job_id = int(plan.get("job_id") or 0)
        if job_id:
            await db.finish_job_run(
                job_id,
                status="unknown",
                duration_ms=max(0, (int(time.time()) - int(plan.get("created_at") or time.time())) * 1000),
                details=f"plan={plan['id']}; process restarted; mutation_not_retried=true",
            )
        await audit_system(
            db,
            "fleet.drain.recovered",
            target_type="node",
            target_id=str(plan.get("node_id") or ""),
            details=f"plan={plan['id']}; process restarted; mutation_not_retried=true",
            success=False,
        )
        recovered += 1

    running = await db.list_running_job_runs(limit=500)
    for job in running:
        if job.name != "fleet.maintenance":
            continue
        await db.finish_job_run(
            job.id,
            status="unknown",
            duration_ms=max(0, (int(time.time()) - int(job.started_at)) * 1000),
            details=(job.details + "; " if job.details else "")
            + "process restarted; mutation_not_retried=true",
        )
        await audit_system(
            db,
            "fleet.maintenance.recovered",
            target_type="fleet",
            target_id=str(job.id),
            details="process restarted; batch not resumed; mutation_not_retried=true",
            success=False,
        )
        recovered += 1
    return recovered
