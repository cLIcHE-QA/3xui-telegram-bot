"""v4.10.0 Telegram UI for restricted 3x-ui host control."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import secrets
import time
import re

import aiohttp
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_auth import ROLE_RANK, authorize_callback, authorize_message
from admin_ui import render_callback, render_input
from audit import audit_from_call, audit_from_message, audit_system
from backup_manager import BackupManager
from config import HostControlTarget, load_settings
from db import Database
from host_control import HostControlClient, HostControlError, HostControlOperation
from system_backup import SystemBackupService
from xui import XUIClient, XUIError, XUIMutationError


settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
backup_manager = BackupManager(settings.db_path, settings.backup_dir, settings.backup_keep)
system_backup = SystemBackupService(backup_manager, settings.node_backup_targets, settings.host_control_targets)

host_control_router = Router(name="host_control")
TARGET_KEY = r"(?:m|n[1-9][0-9]{0,18})"
STOP_CONFIRM_TTL = 120.0


class HostControlStates(StatesGroup):
    stop_phrase = State()


@dataclass(frozen=True)
class ControlTarget:
    key: str
    name: str
    back_callback: str
    panel_client: XUIClient | None
    host_target: HostControlTarget | None
    node_id: int = 0


def _host_target_for(
    name: str,
    node_id: int | None = None,
    *,
    master: bool = False,
) -> HostControlTarget | None:
    if master:
        for target in settings.host_control_targets:
            if target.key == "MASTER":
                return target
    if node_id is not None:
        for target in settings.host_control_targets:
            if target.node_id == node_id:
                return target
    needle = name.strip().casefold()
    for target in settings.host_control_targets:
        if node_id is not None and target.node_id is not None:
            continue
        if target.name.strip().casefold() == needle:
            return target
    return None


def _host_client(target: HostControlTarget) -> HostControlClient:
    return HostControlClient(
        target.url,
        target.token,
        target.host_id,
        verify_tls=target.verify_tls,
    )


async def _resolve_target(key: str) -> ControlTarget:
    if key == "m":
        return ControlTarget(
            key="m",
            name=settings.master_name,
            back_callback="admin:master",
            panel_client=xui,
            host_target=_host_target_for(settings.master_name, master=True),
        )
    if not key.startswith("n") or not key[1:].isdigit():
        raise ValueError("invalid target")
    node_id = int(key[1:])
    node = await xui.node_get(node_id)
    if node.transitive:
        raise ValueError("Транзитная нода доступна только для чтения.")
    return ControlTarget(
        key=key,
        name=node.name,
        back_callback=f"admin:node:{node_id}",
        panel_client=system_backup.direct_client_for(node.name, getattr(node, "id", None)),
        host_target=_host_target_for(node.name, node.id),
        node_id=node_id,
    )


def _back(target: ControlTarget) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="⬅ Master" if target.key == "m" else "⬅ Нода",
            callback_data=target.back_callback,
        )
    ]])


def _confirm(target: ControlTarget, action: str, label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=label,
            callback_data=f"admin:hostctl:{target.key}:{action}:run",
        )],
        [InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:hostctl:{target.key}")],
    ])


def _screen_keyboard(target: ControlTarget, role: str | None, xray_running: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    rank = ROLE_RANK.get(role or "", 0)
    if target.host_target is not None and rank >= ROLE_RANK["admin"]:
        rows.append([
            InlineKeyboardButton(text="▶ Start service", callback_data=f"admin:hostctl:{target.key}:ss:ask"),
            InlineKeyboardButton(text="🔄 Restart service", callback_data=f"admin:hostctl:{target.key}:sr:ask"),
        ])
    if target.host_target is not None and rank >= ROLE_RANK["owner"]:
        rows.append([
            InlineKeyboardButton(text="⏹ Stop service", callback_data=f"admin:hostctl:{target.key}:sp:ask"),
        ])
    if target.panel_client is not None and rank >= ROLE_RANK["admin"]:
        rows.append([
            InlineKeyboardButton(text="♻️ Restart Panel process", callback_data=f"admin:hostctl:{target.key}:pr:ask"),
        ])
        rows.append([
            InlineKeyboardButton(
                text="🔄 Restart Xray" if xray_running else "▶ Start Xray",
                callback_data=f"admin:hostctl:{target.key}:xr:ask",
            ),
        ])
    if target.panel_client is not None and rank >= ROLE_RANK["owner"]:
        rows.append([
            InlineKeyboardButton(text="⏹ Stop Xray", callback_data=f"admin:hostctl:{target.key}:xs:ask"),
        ])
    rows.append([
        InlineKeyboardButton(
            text="⬅ Master" if target.key == "m" else "⬅ Нода",
            callback_data=target.back_callback,
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _panel_snapshot(client: XUIClient | None) -> tuple[bool, str, bool]:
    if client is None:
        return False, "direct admin connection not configured", False
    try:
        status = await client.server_status()
    except (XUIError, aiohttp.ClientError, TimeoutError):
        return False, "unavailable", False
    xray = status.get("xray") or {}
    state = str(xray.get("state") or "unknown").lower()
    running = state in {"running", "started", "online"}
    return True, state, running


async def _wait_panel_online(client: XUIClient, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ok, _, _ = await _panel_snapshot(client)
        if ok:
            return True
        await asyncio.sleep(1.0)
    return False


async def _verify_uncertain_panel_restart(client: XUIClient, timeout: float = 30.0) -> bool:
    """Require an observed API drop followed by recovery after a lost POST response."""
    deadline = time.monotonic() + timeout
    seen_down = False
    while time.monotonic() < deadline:
        ok, _, _ = await _panel_snapshot(client)
        if not ok:
            seen_down = True
        elif seen_down:
            return True
        await asyncio.sleep(0.75)
    return False


async def _finish_job(
    run_id: int,
    *,
    started: float,
    status: str,
    details: str,
) -> None:
    await db.finish_job_run(
        run_id,
        status=status,
        duration_ms=max(0, int((time.monotonic() - started) * 1000)),
        details=details,
    )


def _operation_details(target: ControlTarget, op: HostControlOperation) -> str:
    return (
        f"target={target.name}; operation_id={op.operation_id}; action={op.action}; "
        f"before={op.before}; after={op.after}; result={op.result}; error_code={op.error_code}"
    )


async def _run_service_action(target: ControlTarget, action: str, actor_id: int) -> tuple[str, bool, str]:
    if target.host_target is None:
        return "🔴 Host Control Agent для этого сервера не настроен.", False, "target_not_configured"
    if action in {"start", "restart"} and target.panel_client is None:
        return (
            "🔴 Direct admin connection к 3x-ui не настроен; post-condition Panel API проверить нельзя.",
            False,
            "panel_direct_connection_missing",
        )

    operation_id = secrets.token_hex(16)
    job_name = f"host_control.{action}"
    prepared_details = (
        f"target={target.name}; host_alias={target.host_target.key}; "
        f"operation_id={operation_id}; action={action}; result=prepared"
    )
    # Persist operation_id before POST so a bot crash cannot orphan the agent journal entry.
    run_id = await db.start_job_run(
        name=job_name,
        trigger="admin",
        actor_id=actor_id,
        details=prepared_details,
    )
    started = time.monotonic()
    client = _host_client(target.host_target)
    try:
        op = await client.execute(action, operation_id)
        details = _operation_details(target, op)
        if op.result == "failed":
            await _finish_job(run_id, started=started, status="failed", details=details)
            return f"🔴 {action} service: failed ({op.error_code or 'unknown'}).", False, details
        if op.result == "uncertain":
            await _finish_job(run_id, started=started, status="unknown", details=details)
            return (
                "🟡 Результат host-control не подтверждён. Команда повторно НЕ отправлялась.",
                False,
                details,
            )
        if op.result != "success":
            await _finish_job(run_id, started=started, status="unknown", details=details)
            return "🟡 Неожиданный результат host-control; повтор команды заблокирован.", False, details

        if action in {"start", "restart"}:
            assert target.panel_client is not None
            if not await _wait_panel_online(target.panel_client):
                details += "; panel_postcondition=unconfirmed"
                await _finish_job(run_id, started=started, status="unknown", details=details)
                return (
                    "🟡 systemd сообщает running, но Panel API не вернулся. Команда повторно НЕ отправлялась.",
                    False,
                    details,
                )
            details += "; panel_postcondition=online"

        await _finish_job(run_id, started=started, status="success", details=details)
        return f"✅ {action} service выполнен.", True, details
    except HostControlError as exc:
        status = "unknown" if exc.uncertain else "failed"
        details = (
            f"target={target.name}; operation_id={operation_id}; action={action}; "
            f"result={status}; error_code={exc.code or 'host_control_error'}"
        )
        await _finish_job(run_id, started=started, status=status, details=details)
        if exc.uncertain:
            return (
                "🟡 Результат не подтверждён. Mutation POST не повторялся; проверь статус вручную.",
                False,
                details,
            )
        return f"🔴 Host-control отклонил операцию ({exc.code or 'error'}).", False, details


_RECOVERY_OPERATION_ID = re.compile(r"(?:^|; )operation_id=([0-9a-f]{32})(?:;|$)")
_RECOVERY_ACTION = re.compile(r"(?:^|; )action=(start|stop|restart)(?:;|$)")
_RECOVERY_HOST_ALIAS = re.compile(r"(?:^|; )host_alias=([A-Z0-9_]+)(?:;|$)")


def _recovery_field(pattern: re.Pattern[str], details: str) -> str:
    match = pattern.search(details or "")
    return match.group(1) if match else ""


async def recover_control_jobs() -> int:
    """Resolve unfinished control jobs without ever replaying a mutation."""
    recovered = 0
    for job in await db.list_running_job_runs(limit=500):
        if job.name in {"panel.restart", "xray.stop", "xray.restart"}:
            details = (
                (job.details + "; " if job.details else "")
                + "result=uncertain; recovery=bot_restarted; mutation_not_retried=true"
            )
            duration_ms = max(0, (int(time.time()) - int(job.started_at)) * 1000)
            await db.finish_job_run(
                job.id,
                status="unknown",
                duration_ms=duration_ms,
                details=details,
            )
            await audit_system(
                db,
                f"{job.name}.recovered",
                target_type="host_control",
                details=details,
                success=False,
            )
            recovered += 1
            continue

        if job.name not in {
            "host_control.start",
            "host_control.stop",
            "host_control.restart",
        }:
            continue

        operation_id = _recovery_field(_RECOVERY_OPERATION_ID, job.details)
        action = _recovery_field(_RECOVERY_ACTION, job.details)
        alias = _recovery_field(_RECOVERY_HOST_ALIAS, job.details)
        target = next((item for item in settings.host_control_targets if item.key == alias), None)
        base_details = job.details or f"operation_id={operation_id}; action={action}"

        if not operation_id or not action or target is None:
            details = base_details + "; result=uncertain; recovery=metadata_missing; mutation_not_retried=true"
            status = "unknown"
        else:
            client = _host_client(target)
            try:
                operation = await client.get_operation(operation_id)
            except HostControlError as exc:
                operation = None
                details = (
                    base_details
                    + f"; result=uncertain; recovery=lookup_failed; error_code={exc.code or 'error'}"
                    + "; mutation_not_retried=true"
                )
                status = "unknown"
            else:
                if operation is None:
                    details = (
                        base_details
                        + "; result=uncertain; recovery=operation_not_found; mutation_not_retried=true"
                    )
                    status = "unknown"
                elif operation.action != action:
                    details = (
                        base_details
                        + "; result=uncertain; recovery=action_mismatch; mutation_not_retried=true"
                    )
                    status = "unknown"
                elif operation.result == "success":
                    details = _operation_details(
                        ControlTarget(
                            key="m" if target.key == "MASTER" else target.key,
                            name=target.name,
                            back_callback="",
                            panel_client=None,
                            host_target=target,
                        ),
                        operation,
                    ) + "; recovery=agent_journal"
                    status = "success"
                    if action in {"start", "restart"}:
                        panel_client = xui if target.key == "MASTER" else system_backup.direct_client_for(target.name, target.node_id)
                        panel_ok, _, _ = await _panel_snapshot(panel_client)
                        if not panel_ok:
                            details += "; panel_postcondition=unconfirmed"
                            status = "unknown"
                        else:
                            details += "; panel_postcondition=online"
                elif operation.result == "failed":
                    details = _operation_details(
                        ControlTarget(
                            key="m" if target.key == "MASTER" else target.key,
                            name=target.name,
                            back_callback="",
                            panel_client=None,
                            host_target=target,
                        ),
                        operation,
                    ) + "; recovery=agent_journal"
                    status = "failed"
                else:
                    details = _operation_details(
                        ControlTarget(
                            key="m" if target.key == "MASTER" else target.key,
                            name=target.name,
                            back_callback="",
                            panel_client=None,
                            host_target=target,
                        ),
                        operation,
                    ) + "; recovery=agent_journal; mutation_not_retried=true"
                    status = "unknown"

        duration_ms = max(0, (int(time.time()) - int(job.started_at)) * 1000)
        await db.finish_job_run(
            job.id,
            status=status,
            duration_ms=duration_ms,
            details=details,
        )
        await audit_system(
            db,
            f"{job.name}.recovered",
            target_type="host_control",
            target_id=target.name if target is not None else alias,
            details=details,
            success=status == "success",
        )
        recovered += 1
    return recovered


async def _run_panel_restart(target: ControlTarget, actor_id: int) -> tuple[str, bool, str]:
    if target.panel_client is None:
        return "🔴 Direct admin connection к 3x-ui не настроен.", False, "panel_direct_connection_missing"
    run_id = await db.start_job_run(name="panel.restart", trigger="admin", actor_id=actor_id)
    started = time.monotonic()
    dispatched = False
    uncertain_dispatch = False
    error_code = ""
    try:
        try:
            await target.panel_client.restart_panel()
            dispatched = True
        except XUIMutationError as exc:
            error_code = exc.code or ("lost_response" if exc.uncertain else "panel_rejected")
            if exc.uncertain:
                dispatched = True
                uncertain_dispatch = True
        except (aiohttp.ClientError, TimeoutError):
            dispatched = True
            uncertain_dispatch = True
            error_code = "lost_response"

        if not dispatched:
            details = f"target={target.name}; result=failed; error_code={error_code}"
            await _finish_job(run_id, started=started, status="failed", details=details)
            return "🔴 3x-ui отклонил Restart Panel process.", False, details

        if uncertain_dispatch:
            verified = await _verify_uncertain_panel_restart(target.panel_client)
        else:
            # Upstream schedules the restart after a short grace period.
            await asyncio.sleep(4.0)
            verified = await _wait_panel_online(target.panel_client)

        if verified:
            details = (
                f"target={target.name}; result=success; "
                f"dispatch={'uncertain_recovered' if uncertain_dispatch else 'accepted'}"
            )
            await _finish_job(run_id, started=started, status="success", details=details)
            return "✅ Restart Panel process подтверждён: Panel API снова online.", True, details

        details = (
            f"target={target.name}; result=uncertain; "
            f"dispatch={'lost_response' if uncertain_dispatch else 'accepted'}"
        )
        await _finish_job(run_id, started=started, status="unknown", details=details)
        return (
            "🟡 Restart Panel process не удалось подтвердить. POST повторно НЕ отправлялся.",
            False,
            details,
        )
    except Exception as exc:
        details = f"target={target.name}; result=failed; error={type(exc).__name__}"
        await _finish_job(run_id, started=started, status="failed", details=details)
        return "🔴 Ошибка Restart Panel process. Подробности доступны в локальном журнале.", False, details


async def _run_xray_action(target: ControlTarget, action: str, actor_id: int) -> tuple[str, bool, str]:
    if target.panel_client is None:
        return "🔴 Direct admin connection к 3x-ui не настроен.", False, "panel_direct_connection_missing"
    if action not in {"stop", "restart"}:
        return "🔴 Недопустимое Xray action.", False, "invalid_action"

    job_name = "xray.stop" if action == "stop" else "xray.restart"
    run_id = await db.start_job_run(name=job_name, trigger="admin", actor_id=actor_id)
    started = time.monotonic()
    try:
        try:
            if action == "stop":
                await target.panel_client.stop_xray()
            else:
                await target.panel_client.restart_xray()
        except XUIMutationError as exc:
            if exc.uncertain:
                details = (
                    f"target={target.name}; action={action}; result=uncertain; "
                    f"error_code={exc.code or 'lost_response'}"
                )
                await _finish_job(run_id, started=started, status="unknown", details=details)
                return (
                    "🟡 Ответ Xray operation не подтверждён. Запрос повторно НЕ отправлялся.",
                    False,
                    details,
                )
            details = (
                f"target={target.name}; action={action}; result=failed; "
                f"error_code={exc.code or 'panel_rejected'}"
            )
            await _finish_job(run_id, started=started, status="failed", details=details)
            return "🔴 3x-ui отклонил Xray operation.", False, details
        except (aiohttp.ClientError, TimeoutError):
            details = f"target={target.name}; action={action}; result=uncertain; error_code=lost_response"
            await _finish_job(run_id, started=started, status="unknown", details=details)
            return (
                "🟡 Ответ Xray operation потерян. Запрос повторно НЕ отправлялся.",
                False,
                details,
            )

        await asyncio.sleep(0.75)
        ok, state, running = await _panel_snapshot(target.panel_client)
        # Fail closed: an unknown/error Xray state is not proof that Stop worked.
        expected = state in {"stop", "stopped"} if action == "stop" else running
        if ok and expected:
            details = f"target={target.name}; action={action}; result=success; xray_state={state}"
            await _finish_job(run_id, started=started, status="success", details=details)
            return f"✅ Xray: {state}.", True, details

        details = f"target={target.name}; action={action}; result=uncertain; xray_state={state}"
        await _finish_job(run_id, started=started, status="unknown", details=details)
        return "🟡 Xray post-condition не подтверждён. Повтор запроса не выполнялся.", False, details
    except Exception as exc:
        details = f"target={target.name}; action={action}; result=failed; error={type(exc).__name__}"
        await _finish_job(run_id, started=started, status="failed", details=details)
        return "🔴 Ошибка Xray operation. Подробности доступны в локальном журнале.", False, details


async def _show_screen(call: CallbackQuery, key: str) -> None:
    ok, role = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    try:
        target = await _resolve_target(key)
    except (ValueError, XUIError) as exc:
        await call.answer("Target недоступен", show_alert=True)
        await render_callback(call, f"🔴 Не удалось открыть 3x-ui Control: {str(exc)[:240]}")
        return

    service_line = "⚪ Service: host-control не настроен"
    if target.host_target is not None:
        try:
            state = await _host_client(target.host_target).status()
            icon = "🟢" if state.state == "running" else "🟡" if state.state == "transitioning" else "🔴"
            service_line = f"{icon} Service: {state.state} · agent {state.agent_version or '?'}"
        except HostControlError as exc:
            service_line = f"🔴 Service: agent unavailable ({exc.code or 'error'})"

    panel_ok, xray_state, xray_running = await _panel_snapshot(target.panel_client)
    panel_line = "🟢 Panel API: online" if panel_ok else (
        "⚪ Panel API: direct admin connection не настроен"
        if target.panel_client is None else "🔴 Panel API: unavailable"
    )
    xray_line = (
        f"{'🟢' if xray_running else '🔴'} Xray Core: {xray_state}"
        if panel_ok else "⚪ Xray Core: unknown"
    )

    await render_callback(
        call,
        "\n".join([
            f"🧩 3x-ui Control · {target.name}",
            "",
            service_line,
            panel_line,
            xray_line,
            "",
            "Service actions идут только через restricted Host Control Agent.",
            "Panel/Xray actions идут только через штатный 3x-ui API.",
        ]),
        reply_markup=_screen_keyboard(target, role, xray_running),
    )
    await call.answer()


@host_control_router.callback_query(F.data.regexp(rf"^admin:hostctl:{TARGET_KEY}$"))
async def host_control_screen(call: CallbackQuery):
    key = (call.data or "").split(":")[2]
    await _show_screen(call, key)


@host_control_router.callback_query(F.data.regexp(rf"^admin:hostctl:{TARGET_KEY}:(?:ss|sr|pr|xs|xr):ask$"))
async def host_control_action_ask(call: CallbackQuery):
    parts = (call.data or "").split(":")
    key, action = parts[2], parts[3]
    minimum = "owner" if action == "xs" else "admin"
    ok, _ = await authorize_callback(db, settings, call, minimum=minimum)
    if not ok:
        return
    try:
        target = await _resolve_target(key)
    except (ValueError, XUIError) as exc:
        await call.answer(str(exc)[:180], show_alert=True)
        return

    prompts = {
        "ss": (
            f"▶ Запустить 3x-ui service на {target.name}?",
            "▶ Да, start service",
        ),
        "sr": (
            f"⚠️ Перезапустить 3x-ui service на {target.name}?\n\nPanel API кратковременно станет недоступен.",
            "🔄 Да, restart service",
        ),
        "pr": (
            f"⚠️ Выполнить штатный Restart Panel process на {target.name}?\n\n"
            "Будет отправлен ровно один POST /panel/api/setting/restartPanel.",
            "♻️ Да, restart panel",
        ),
        "xs": (
            f"⚠️ Остановить Xray Core на {target.name}?\n\nVPN через этот сервер перестанет работать.",
            "⏹ Да, stop Xray",
        ),
        "xr": (
            f"🔄 Restart / Start Xray Core на {target.name}?\n\nАктивные подключения могут кратковременно оборваться.",
            "🔄 Да, restart/start Xray",
        ),
    }
    text, label = prompts[action]
    await call.answer()
    await render_callback(call, text, reply_markup=_confirm(target, action, label))


@host_control_router.callback_query(F.data.regexp(rf"^admin:hostctl:{TARGET_KEY}:(?:ss|sr|pr|xs|xr):run$"))
async def host_control_action_run(call: CallbackQuery):
    parts = (call.data or "").split(":")
    key, action = parts[2], parts[3]
    minimum = "owner" if action == "xs" else "admin"
    ok, _ = await authorize_callback(db, settings, call, minimum=minimum)
    if not ok:
        return
    try:
        target = await _resolve_target(key)
    except (ValueError, XUIError) as exc:
        await call.answer(str(exc)[:180], show_alert=True)
        return

    actor_id = int(call.from_user.id if call.from_user else 0)
    await call.answer("Выполняю…")
    if action == "ss":
        message, success, details = await _run_service_action(target, "start", actor_id)
        audit_action = "host_control.start"
    elif action == "sr":
        message, success, details = await _run_service_action(target, "restart", actor_id)
        audit_action = "host_control.restart"
    elif action == "pr":
        message, success, details = await _run_panel_restart(target, actor_id)
        audit_action = "panel.restart"
    elif action == "xs":
        message, success, details = await _run_xray_action(target, "stop", actor_id)
        audit_action = "xray.stop"
    else:
        message, success, details = await _run_xray_action(target, "restart", actor_id)
        audit_action = "xray.restart"

    await audit_from_call(
        db,
        call,
        audit_action,
        target_type="host_control",
        target_id=target.name,
        details=details,
        success=success,
    )
    await render_callback(
        call,
        message + "\n\nОткрой экран контроля для свежего состояния.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧩 Обновить 3x-ui Control", callback_data=f"admin:hostctl:{target.key}")],
            [InlineKeyboardButton(
                text="⬅ Master" if target.key == "m" else "⬅ Нода",
                callback_data=target.back_callback,
            )],
        ]),
    )


@host_control_router.callback_query(F.data.regexp(rf"^admin:hostctl:{TARGET_KEY}:sp:ask$"))
async def host_control_stop_ask(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    key = (call.data or "").split(":")[2]
    try:
        target = await _resolve_target(key)
    except (ValueError, XUIError) as exc:
        await call.answer(str(exc)[:180], show_alert=True)
        return
    if target.host_target is None:
        await call.answer("Host Control Agent не настроен", show_alert=True)
        return

    nonce = secrets.token_hex(8)
    await state.set_state(HostControlStates.stop_phrase)
    await state.update_data(
        key=target.key,
        target_name=target.name,
        nonce=nonce,
        created=time.time(),
    )
    await call.answer()
    await render_callback(
        call,
        f"⛔ STOP 3x-ui service · {target.name}\n\n"
        "Это Owner-only операция. После stop Panel API будет недоступен, "
        "но Host Control Agent останется доступен для Start.\n\n"
        f"Для подтверждения отправь точную фразу:\nSTOP {target.name}\n\n"
        "Подтверждение одноразовое и действует 2 минуты.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:hostctl:{target.key}:stopcancel")
        ]]),
    )


@host_control_router.callback_query(F.data.regexp(rf"^admin:hostctl:{TARGET_KEY}:stopcancel$"))
async def host_control_stop_cancel(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    key = (call.data or "").split(":")[2]
    await state.clear()
    await _show_screen(call, key)


@host_control_router.message(HostControlStates.stop_phrase)
async def host_control_stop_phrase(message: Message, state: FSMContext):
    if not message.from_user:
        return
    ok, _ = await authorize_message(db, settings, message.from_user.id, minimum="owner")
    if not ok:
        await state.clear()
        await render_input(message, "Недостаточно прав. Stop service требует Owner.")
        return
    data = await state.get_data()
    key = str(data.get("key") or "")
    target_name = str(data.get("target_name") or "")
    created = float(data.get("created") or 0)
    nonce = str(data.get("nonce") or "")
    if not nonce or time.time() - created > STOP_CONFIRM_TTL:
        await state.clear()
        await render_input(message, "Подтверждение истекло. Открой 3x-ui Control заново.")
        return
    if (message.text or "") != f"STOP {target_name}":
        await render_input(message, f"Нужна точная фраза: STOP {target_name}")
        return

    # One-time confirmation: consume state BEFORE mutation dispatch.
    await state.clear()
    try:
        target = await _resolve_target(key)
    except (ValueError, XUIError) as exc:
        await render_input(message, f"🔴 Target недоступен: {str(exc)[:200]}")
        return
    if target.name != target_name:
        await render_input(message, "🔴 Target изменился после подтверждения. Stop заблокирован.")
        return

    result, success, details = await _run_service_action(target, "stop", int(message.from_user.id))
    await audit_from_message(
        db,
        message,
        "host_control.stop",
        target_type="host_control",
        target_id=target.name,
        details=f"confirm={nonce}; {details}",
        success=success,
    )
    await render_input(
        message,
        result,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🧩 3x-ui Control", callback_data=f"admin:hostctl:{target.key}")
        ]]),
    )
