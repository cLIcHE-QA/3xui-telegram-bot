"""System -> Versions & Updates: single-message UI and production adapters."""
from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
import re
import shutil
import time

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_auth import ROLE_RANK, authorize_callback, authorize_message
from admin_ui import render_callback, render_input
from backup_manager import BackupManager
from config import load_settings
from db import Database
from restore_manager import RestoreManager
from runtime_jobs import backup_lock
from system_backup import SystemBackupService
from update_backups import validate_database
from version import APP_VERSION
from version_api import VersionAPIError, latest_stable_panel, same_version
from version_service import (
    BackupReceipt, Operation, OperationStore, Target, UNCERTAIN_STATES,
    UpdateError, UpdateService, VersionState, file_hash, safe_error,
)
from xui import XUIClient

settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
backup_manager = BackupManager(settings.db_path, settings.backup_dir, settings.backup_keep)
system_backup = SystemBackupService(backup_manager, settings.node_backup_targets)
restore_manager = RestoreManager(settings.db_path, settings.backup_dir)
versions_router = Router(name="versions_updates")
store = OperationStore(Path(settings.db_path).parent / "updates")
KEY = r"(?:m|n[1-9][0-9]{0,18})"


class UnlockStates(StatesGroup):
    phrase = State()


def _target(key: str, name: str, client: XUIClient, identity: str = "", *, eligible: bool = True) -> Target:
    binding = "\0".join((key, name, client.base_url, client.token, str(client.verify_tls), identity))
    return Target(key, name, hashlib.sha256(binding.encode()).hexdigest(), client, eligible)


async def resolve_target(key: str) -> Target:
    if key == "m":
        return _target("m", settings.master_name, xui)
    if not re.fullmatch(KEY, key):
        raise UpdateError("Invalid target.")
    node = await xui.node_get(int(key[1:]))
    if node.transitive:
        raise UpdateError("Transitive nodes are read-only; use their own administrator.")
    client = system_backup.direct_client_for(node.name)
    if client is None:
        raise UpdateError("Direct admin connection required: configure this node in NODE_BACKUP_TARGETS.")
    identity = f"{node.scheme}|{node.address}|{node.port}|{node.base_path}"
    return _target(key, node.name, client, identity, eligible=node.enable and node.status == "online")


async def read_state(target: Target) -> VersionState:
    status = await target.client.version_status()
    raw = status.get("xray")
    core = raw if isinstance(raw, dict) else {}
    panel = ""
    try:
        info = await target.client.get_panel_update_info()
        panel = str(info.get("currentVersion") or "")
    except VersionAPIError:
        pass  # Xray status remains useful if the panel release lookup is unavailable.
    return VersionState(panel, str(core.get("version") or ""), str(core.get("state") or "unknown"))


async def stable_version(target: Target) -> str:
    return await latest_stable_panel(await target.client.get_panel_update_info())


def _write_private(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())


def _copy_private(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as output, source.open("rb") as source_file:
        shutil.copyfileobj(source_file, output)
        output.flush()
        os.fsync(output.fileno())


async def create_update_backup(target: Target, nonce: str) -> BackupReceipt:
    root = Path(settings.backup_dir) / "rescue" / "updates" / target.key
    async with backup_lock:
        if target.key == "m":
            result = await system_backup.create_full_backup()
            if result.missing:
                raise UpdateError("Full backup is incomplete. Fix missing components before updating.")
            info = await asyncio.to_thread(restore_manager.inspect_backup, result.info.path, deep=True)
            if not (info.valid and info.bot_db_ok and info.xui_db_ok and info.has_bot_env):
                raise UpdateError("Master full backup failed preflight; update blocked.")
            path = root / f"pre-update-{nonce}.tar.gz"
            await asyncio.to_thread(_copy_private, result.info.path, path)
        else:
            body, filename = await target.client.download_database()
            await asyncio.to_thread(validate_database, body, filename)
            suffix = ".dump" if filename.lower().endswith(".dump") else ".db"
            path = root / f"pre-update-{nonce}{suffix}"
            await asyncio.to_thread(_write_private, path, body)
    return BackupReceipt(str(path), await asyncio.to_thread(file_hash, path))


async def allowed(actor: int, minimum: str) -> bool:
    ok, _ = await authorize_message(db, settings, actor, minimum=minimum)
    return ok


async def record_operation(op: Operation, stage: str) -> None:
    action = "panel.update" if op.component == "panel" else "xray.install"
    if stage == "started":
        op.job_id = await db.start_job_run(name=action, trigger="admin", actor_id=op.actor)
    elif op.job_id and stage not in {"prepared", "cancelled"}:
        status = "success" if stage == "success" else "failed" if stage == "failed" else "unknown"
        await db.finish_job_run(
            op.job_id, status=status, duration_ms=max(0, int((time.time() - (op.started or op.created)) * 1000)),
            details=f"target={op.target}; expected={op.desired}; actual={op.actual}; outcome={stage}",
        )
    await db.add_audit(
        actor_id=op.acknowledged_by or op.actor, action=f"{action}.{stage}", target_type="server", target_id=op.target,
        details=(f"operation={op.nonce}; previous={op.previous}; target={op.desired}; "
                 f"actual={op.actual}; state={op.xray_state}; backup={Path(op.backup).name}; "
                 f"outcome={stage}; note={op.error}"),
        success=stage not in {"failed", "unconfirmed", "acknowledged"},
    )


service = UpdateService(
    store, resolve=resolve_target, snapshot=read_state, stable=stable_version,
    backup=create_update_backup, authorize=allowed, record=record_operation,
)


def keyboard(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=data) for label, data in row]
        for row in rows
    ])


def back(key: str = "") -> InlineKeyboardMarkup:
    return keyboard([[('Назад', f'admin:ver:target:{key}' if key else 'admin:versions')]])


def binding(call: CallbackQuery) -> dict[str, int]:
    if not isinstance(call.message, Message):
        raise UpdateError("Open /admin again to create a usable confirmation message.")
    return {"actor": call.from_user.id, "chat": call.message.chat.id, "message": call.message.message_id}


async def error_screen(call: CallbackQuery, exc: Exception, key: str = "") -> None:
    await render_callback(call, "Versions & Updates\n\n" + safe_error(exc), reply_markup=back(key))


def operation_text(op: Operation) -> str:
    labels = {
        "prepared": "Резервная копия проверена. Подтверди установку.",
        "success": "Обновление выполнено и проверено.",
        "failed": "Операция завершилась ошибкой. Проверь результат перед повторным запуском.",
        "cancelled": "Отменено. Запрос установки не отправлялся.",
        "expired": "Подтверждение истекло. Запрос установки не отправлялся.",
        "acknowledged": "Owner подтвердил ручную проверку. Повторная установка не запускалась.",
    }
    title = labels.get(op.state, "Результат не подтверждён. Повторная установка заблокирована.")
    return (f"{title}\n\nTarget: {op.target}\nComponent: {op.component}\n"
            f"Previous: {op.previous}\nSelected: {op.desired}\n"
            f"Observed: {op.actual or 'ещё не проверено'}\nXray: {op.xray_state}\n"
            f"Backup: {Path(op.backup).name or 'не создан'}\nOperation: {op.nonce}"
            + (f"\n\n{op.error}" if op.error else ""))


def operation_keyboard(op: Operation, role: str | None, call: CallbackQuery) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = []
    if (op.state == "prepared" and op.actor == call.from_user.id
            and ROLE_RANK.get(role or "", 0) >= ROLE_RANK["admin"]):
        if (isinstance(call.message, Message) and op.chat == call.message.chat.id
                and op.message == call.message.message_id):
            rows.append([("Подтвердить установку", f"admin:ver:run:{op.nonce}")])
        rows.append([("Отмена", f"admin:ver:cancel:{op.nonce}")])
    if op.state in UNCERTAIN_STATES:
        rows.append([("Проверить результат (без повтора)", f"admin:ver:check:{op.nonce}")])
        if role == "owner":
            rows.append([("Снять блокировку после ручной проверки", f"admin:ver:unlock:{op.nonce}")])
    rows.append([("К серверу", f"admin:ver:target:{op.target}")])
    return keyboard(rows)


@versions_router.callback_query(F.data == "admin:versions")
async def versions_home(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    await state.clear()
    await call.answer()
    master, nodes = await asyncio.gather(
        read_state(_target("m", settings.master_name, xui)), xui.nodes_list(), return_exceptions=True,
    )
    lines = [f"🧩 Versions & Updates | Bot {APP_VERSION}", "", settings.master_name]
    if isinstance(master, VersionState):
        lines += [f"3x-ui: {master.panel or 'недоступно'}", f"Xray: {master.xray or 'недоступно'} | {master.xray_state}"]
    else:
        lines.append("Не удалось получить версии Master.")
    rows = [[(settings.master_name, "admin:ver:target:m")]]
    if isinstance(nodes, list):
        for node in nodes[:30]:
            lines += ["", f"{node.name}: 3x-ui {node.panel_version or '?'} | Xray {node.xray_version or '?'}"]
            if node.id > 0 and not node.transitive:
                rows.append([(node.name, f"admin:ver:target:n{node.id}")])
        if len(nodes) > 30:
            lines.append(f"Показано 30 из {len(nodes)} нод; остальные доступны через Infrastructure.")
    else:
        lines += ["", "Не удалось получить список нод."]
    rows += [[("Обновить", "admin:versions")], [("System", "admin:section:system")]]
    await render_callback(call, "\n".join(lines)[:3900], reply_markup=keyboard(rows))


@versions_router.callback_query(F.data.regexp(rf"^admin:ver:target:({KEY})$"))
async def version_target(call: CallbackQuery, state: FSMContext):
    ok, role = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    await state.clear()
    await call.answer()
    key = (call.data or "").rsplit(":", 1)[-1]
    try:
        if key == "m":
            name, snapshot = settings.master_name, await read_state(_target("m", settings.master_name, xui))
        else:
            node = await xui.node_get(int(key[1:]))
            name = node.name
            snapshot = VersionState(node.panel_version, node.xray_version, node.xray_state)
        rows = [[("3x-ui update", f"admin:ver:panel:{key}")],
                [("Xray versions", f"admin:ver:xray:{key}:0")]]
        text = (f"{name}\n\n3x-ui: {snapshot.panel or 'недоступно'}\n"
                f"Xray: {snapshot.xray or 'недоступно'} | {snapshot.xray_state}\n\n"
                "Только ручные обновления: свежая проверенная копия и подтверждение.")
        op = store.get(key)
        if op and op.state in UNCERTAIN_STATES | {"prepared", "preparing", "checking"}:
            text += f"\n\nОперация: {op.state} ({op.nonce})"
            rows.append([("Статус операции", f"admin:ver:check:{op.nonce}")])
        rows += [[("Обновить", f"admin:ver:target:{key}")], [("Все серверы", "admin:versions")]]
        await render_callback(call, text, reply_markup=keyboard(rows))
    except Exception as exc:
        await error_screen(call, exc)


async def show_panel_screen(call: CallbackQuery, key: str) -> None:
    """Old node-update buttons lead here; their old confirmation never executes."""
    ok, role = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    await call.answer()
    try:
        target = await resolve_target(key)
        info = await target.client.get_panel_update_info()
        latest = await latest_stable_panel(info)
        current = str(info.get("currentVersion") or "")
        text = (f"3x-ui | {target.name}\n\nCurrent: {current or 'недоступно'}\n"
                f"Latest stable: {latest}\n\n"
                "Штатный updater перезапускает панель. VPN-сессии могут прерваться.\n"
                "Используется stable; сохранённая настройка канала не меняется.")
        rows = []
        if target.eligible and ROLE_RANK.get(role or "", 0) >= ROLE_RANK["admin"] and not same_version(current, latest):
            rows.append([("Создать backup и перейти к подтверждению", f"admin:ver:prepare:{key}:panel")])
        rows.append([("Назад", f"admin:ver:target:{key}")])
        await render_callback(call, text, reply_markup=keyboard(rows))
    except Exception as exc:
        await error_screen(call, exc, key)


@versions_router.callback_query(F.data.regexp(rf"^admin:ver:panel:({KEY})$"))
async def panel_screen(call: CallbackQuery):
    await show_panel_screen(call, (call.data or "").rsplit(":", 1)[-1])


@versions_router.callback_query(F.data.regexp(rf"^admin:ver:xray:({KEY}):[0-9]+$"))
async def xray_versions(call: CallbackQuery):
    ok, role = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    await call.answer()
    parts = (call.data or "").split(":")
    key, page = parts[-2], int(parts[-1])
    try:
        target = await resolve_target(key)
        values = await target.client.get_xray_versions()
        snapshot = await read_state(target)
        page = min(page, (len(values) - 1) // 8)
        rows = []
        can_change = target.eligible and ROLE_RANK.get(role or "", 0) >= ROLE_RANK["admin"]
        lines = [f"Xray Core | {target.name}", f"Current: {snapshot.xray or 'недоступно'}", "",
                 "Доступные версии из API 3x-ui (upgrade/downgrade):"]
        for value in values[page * 8:(page + 1) * 8]:
            current = same_version(value, snapshot.xray)
            label = value + (" | current" if current else "")
            lines.append(label)
            if can_change and not current:
                rows.append([(label, f"admin:ver:pick:{key}:{value}")])
        nav = []
        if page:
            nav.append(("Предыдущая", f"admin:ver:xray:{key}:{page - 1}"))
        if (page + 1) * 8 < len(values):
            nav.append(("Следующая", f"admin:ver:xray:{key}:{page + 1}"))
        if nav:
            rows.append(nav)
        rows.append([("Назад", f"admin:ver:target:{key}")])
        await render_callback(call, "\n".join(lines), reply_markup=keyboard(rows))
    except Exception as exc:
        await error_screen(call, exc, key)


async def prepare_screen(call: CallbackQuery, key: str, component: str, version: str = "") -> None:
    ok, role = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    await call.answer()
    try:
        ids = binding(call)
        await render_callback(call, "Создаю и проверяю свежую резервную копию. Установка ещё не запускалась.")
        op = await service.prepare(key, component, version, **ids)
        text = operation_text(op) + (
            "\n\nУстановка перезапускает сервисы и может прервать VPN-сессии. "
            "Старая версия может быть несовместима с текущей конфигурацией. "
            "Подтверждение действует 5 минут. После отмены резервная копия сохраняется."
        )
        sent = await render_callback(call, text, reply_markup=operation_keyboard(op, role, call))
        if isinstance(sent, Message) and sent.message_id != ids["message"]:
            await service.rebind(op.nonce, actor=ids["actor"], chat=ids["chat"],
                                 old_message=ids["message"], new_message=sent.message_id)
    except Exception as exc:
        await error_screen(call, exc, key)


@versions_router.callback_query(F.data.regexp(rf"^admin:ver:prepare:({KEY}):panel$"))
async def prepare_panel(call: CallbackQuery):
    await prepare_screen(call, (call.data or "").split(":")[-2], "panel")


@versions_router.callback_query(F.data.regexp(rf"^admin:ver:pick:({KEY}):[A-Za-z0-9.-]+$"))
async def prepare_xray(call: CallbackQuery):
    parts = (call.data or "").split(":")
    await prepare_screen(call, parts[-2], "xray", parts[-1])


@versions_router.callback_query(F.data.regexp(r"^admin:ver:(run|cancel|check):[0-9a-f]{16}$"))
async def operate(call: CallbackQuery):
    _, _, action, nonce = (call.data or "").split(":")
    ok, role = await authorize_callback(db, settings, call, minimum="read_only" if action == "check" else "admin")
    if not ok:
        return
    await call.answer()
    try:
        if action == "run":
            await render_callback(call, "Устанавливаю и проверяю. Не запускай другой update или restore на этом сервере.")
            op = await service.execute(nonce, **binding(call))
        elif action == "cancel":
            op = await service.cancel(nonce, **binding(call))
        else:
            op = await service.recheck(nonce, actor=call.from_user.id)
        await render_callback(call, operation_text(op), reply_markup=operation_keyboard(op, role, call))
    except Exception as exc:
        await error_screen(call, exc)


@versions_router.callback_query(F.data.regexp(r"^admin:ver:unlock:[0-9a-f]{16}$"))
async def unlock_start(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    nonce = (call.data or "").rsplit(":", 1)[-1]
    await state.set_state(UnlockStates.phrase)
    await state.update_data(update_nonce=nonce)
    await call.answer()
    await render_callback(
        call,
        "Сначала вручную убедись, что updater на сервере завершился. "
        "Это только снимает локальную блокировку — без повтора и без отката.\n\n"
        f"Введи точно: UNLOCK {nonce}",
        reply_markup=keyboard([[('Отмена', 'admin:versions')]]),
    )


@versions_router.message(UnlockStates.phrase)
async def unlock_finish(message: Message, state: FSMContext):
    if not message.from_user:
        return
    try:
        nonce = str((await state.get_data()).get("update_nonce") or "")
        op = await service.acknowledge(nonce, actor=message.from_user.id, phrase=(message.text or "").strip())
        await state.clear()
        await render_input(message, operation_text(op), reply_markup=back(op.target))
    except Exception as exc:
        await render_input(message, safe_error(exc), reply_markup=keyboard([[('Отмена', 'admin:versions')]]))
