from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_ui import render_callback, render_input
from admin_auth import authorize_callback, authorize_message
from audit import audit_from_call, audit_from_message
from backup_manager import BackupManager
from config import load_settings
from db import Database
from system_backup import SystemBackupService
from xui import XUIClient, XUIError
from versions_updates import show_panel_screen

settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
backup_manager = BackupManager(settings.db_path, settings.backup_dir, settings.backup_keep)
system_backup = SystemBackupService(backup_manager, settings.node_backup_targets)

advanced_nodes_router = Router(name="advanced_nodes")


class NodeEditStates(StatesGroup):
    rename = State()


def _node_id_from_callback(data: str) -> int:
    # admin:nodectl:<id>:<action>
    parts = (data or "").split(":")
    if len(parts) < 4:
        raise ValueError("invalid node callback")
    return int(parts[2])


def _node_key(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, dict):
        value = value.get("id") or value.get("nodeId") or 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _node_update_payload(raw: dict[str, Any], *, name: str | None = None) -> dict[str, Any]:
    """Build the full NodeMutationRequest without exposing/replacing apiToken.

    3x-ui treats an omitted apiToken on update as "keep the stored token".  This
    is important because /nodes/get returns only hasApiToken, not the secret.
    """
    return {
        "id": int(raw.get("id") or 0),
        "name": (name if name is not None else str(raw.get("name") or "Node")).strip(),
        "remark": str(raw.get("remark") or ""),
        "scheme": str(raw.get("scheme") or "https"),
        "address": str(raw.get("address") or ""),
        "port": int(raw.get("port") or 0),
        "basePath": str(raw.get("basePath") or "/"),
        "clearApiToken": False,
        "enable": bool(raw.get("enable", True)),
        "allowPrivateAddress": bool(raw.get("allowPrivateAddress", False)),
        "inboundSyncMode": str(raw.get("inboundSyncMode") or "all"),
        "inboundTags": list(raw.get("inboundTags") or []),
        "outboundTag": str(raw.get("outboundTag") or ""),
        "pinnedCertSha256": str(raw.get("pinnedCertSha256") or ""),
        "tlsVerifyMode": str(raw.get("tlsVerifyMode") or "verify"),
    }


def _back(node_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Нода", callback_data=f"admin:node:{node_id}")],
    ])


def _confirm(node_id: int, action: str, label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=f"admin:nodectl:{node_id}:{action}:run")],
        [InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:node:{node_id}")],
    ])


@advanced_nodes_router.callback_query(F.data.regexp(r"^admin:nodectl:\d+:inbounds$"))
async def node_inbounds(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    node_id = _node_id_from_callback(call.data or "")
    try:
        node = await xui.node_get(node_id)
        inbounds = await xui.inbounds_list(slim=True)
    except XUIError as exc:
        await call.answer("Ошибка 3x-ui", show_alert=True)
        await render_callback(call, f"🔴 Не удалось получить inbound'ы: {exc}", reply_markup=_back(node_id))
        return

    selected = [ib for ib in inbounds if _node_key(ib.get("nodeId")) == node_id]
    rows: list[list[InlineKeyboardButton]] = []
    lines = [f"📡 Inbounds · {node.name}", "", f"Всего: {len(selected)}"]
    for ib in sorted(selected, key=lambda x: (int(x.get("port") or 0), int(x.get("id") or 0)))[:50]:
        iid = int(ib.get("id") or 0)
        icon = "🟢" if bool(ib.get("enable", True)) else "⚪"
        name = str(ib.get("remark") or ib.get("tag") or f"Inbound {iid}")
        proto = str(ib.get("protocol") or "?")
        port = int(ib.get("port") or 0)
        rows.append([InlineKeyboardButton(
            text=f"{icon} {name} · {port}/{proto}",
            callback_data=f"admin:inbound:{iid}",
        )])
    if len(selected) > 50:
        lines.append(f"Показаны первые 50 из {len(selected)}.")
    if not selected:
        lines.append("На ноде пока нет inbound'ов, известных master-панели.")
    rows.append([InlineKeyboardButton(text="⬅ Нода", callback_data=f"admin:node:{node_id}")])
    await call.answer()
    await render_callback(call, "\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@advanced_nodes_router.callback_query(F.data.regexp(r"^admin:nodectl:\d+:maintenance$"))
async def node_maintenance(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    node_id = _node_id_from_callback(call.data or "")
    try:
        node = await xui.node_get(node_id)
        new_enable = not node.enable
        await xui.node_set_enable(node_id, new_enable)
        try:
            await xui.node_probe(node_id)
        except XUIError:
            pass
        await audit_from_call(
            db, call, "node.maintenance", target_type="node", target_id=node_id,
            details=f"name={node.name}; enabled={new_enable}",
        )
    except XUIError as exc:
        await audit_from_call(
            db, call, "node.maintenance", target_type="node", target_id=node_id,
            details=str(exc), success=False,
        )
        await call.answer("Не удалось изменить режим", show_alert=True)
        await render_callback(call, f"🔴 3x-ui: {exc}", reply_markup=_back(node_id))
        return
    await call.answer("Нода включена" if new_enable else "Maintenance включён")
    await render_callback(call, 
        "✅ Нода возвращена в работу." if new_enable else
        "🛠 Maintenance включён. Master временно не использует ноду для синхронизации/управления.",
        reply_markup=_back(node_id),
    )


@advanced_nodes_router.callback_query(F.data.regexp(r"^admin:nodectl:\d+:rename$"))
async def node_rename_start(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    node_id = _node_id_from_callback(call.data or "")
    try:
        node = await xui.node_get(node_id)
    except XUIError as exc:
        await call.answer(str(exc)[:180], show_alert=True)
        return
    await state.set_state(NodeEditStates.rename)
    await state.update_data(node_id=node_id)
    await call.answer()
    await render_callback(call, 
        f"✏️ Rename node\n\nТекущее имя: {node.name}\n\nОтправь новое имя (1–64 символа).",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:nodectl:{node_id}:cancel")
        ]]),
    )


@advanced_nodes_router.callback_query(F.data.regexp(r"^admin:nodectl:\d+:cancel$"))
async def node_edit_cancel(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    node_id = _node_id_from_callback(call.data or "")
    await state.clear()
    await call.answer("Отменено")
    await render_callback(call, "Изменение ноды отменено.", reply_markup=_back(node_id))


@advanced_nodes_router.message(NodeEditStates.rename)
async def node_rename_finish(message: Message, state: FSMContext):
    if not message.from_user:
        return
    ok, _ = await authorize_message(db, settings, message.from_user.id, minimum="admin")
    if not ok:
        await state.clear()
        await render_input(message, "Недостаточно прав.")
        return
    data = await state.get_data()
    node_id = int(data.get("node_id") or 0)
    name = (message.text or "").strip()
    if not (1 <= len(name) <= 64) or "\n" in name:
        await render_input(message, "Имя должно содержать 1–64 символа одной строкой.")
        return
    try:
        raw = await xui.node_get_raw(node_id)
        old_name = str(raw.get("name") or "Node")
        had_backup_target = system_backup.has_target_for(old_name)
        had_host_control_target = any(
            target.name.strip().casefold() == old_name.strip().casefold()
            for target in settings.host_control_targets
        )
        await xui.node_update(node_id, _node_update_payload(raw, name=name))
        await audit_from_message(
            db, message, "node.rename", target_type="node", target_id=node_id,
            details=f"old={old_name}; new={name}",
        )
    except XUIError as exc:
        await audit_from_message(
            db, message, "node.rename", target_type="node", target_id=node_id,
            details=str(exc), success=False,
        )
        await render_input(message, f"🔴 Не удалось переименовать ноду: {exc}")
        return
    await state.clear()
    warnings: list[str] = []
    if old_name.casefold() != name.casefold():
        if had_backup_target:
            warnings.append(
                "обнови NODE_BACKUP_*_NODE_NAME: direct backup/Xray target был привязан к старому имени"
            )
        if had_host_control_target:
            warnings.append(
                "обнови HOST_CONTROL_*_NAME: Host Control target был привязан к старому имени"
            )
    suffix = "\n\n⚠️ " + "; ".join(warnings) + "." if warnings else ""
    await render_input(message, f"✅ Нода переименована: {name}{suffix}", reply_markup=_back(node_id))


@advanced_nodes_router.callback_query(F.data.regexp(r"^admin:nodectl:\d+:backup$"))
async def node_backup(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    node_id = _node_id_from_callback(call.data or "")
    try:
        node = await xui.node_get(node_id)
    except XUIError as exc:
        await call.answer(str(exc)[:180], show_alert=True)
        return
    if not system_backup.has_target_for(node.name):
        await call.answer("Backup target не настроен", show_alert=True)
        await render_callback(call, 
            "💾 Для backup этой ноды нужен отдельный admin-scope API token в NODE_BACKUP_TARGETS.\n"
            "Master специально не раскрывает сохранённый node-sync token.",
            reply_markup=_back(node_id),
        )
        return
    await call.answer("Создаю backup…")
    try:
        path = await system_backup.create_node_snapshot(node.name)
        await audit_from_call(
            db, call, "node.backup", target_type="node", target_id=node_id,
            details=f"name={node.name}; file={path.name}; bytes={path.stat().st_size}",
        )
        await call.message.answer_document(
            FSInputFile(path),
            caption=f"💾 Backup DB · {node.name}\nФайл содержит секретные данные. Храни его безопасно.",
            reply_markup=_back(node_id),
        )
    except Exception as exc:
        await audit_from_call(
            db, call, "node.backup", target_type="node", target_id=node_id,
            details=f"{type(exc).__name__}: {exc}", success=False,
        )
        await render_callback(call, f"🔴 Backup ноды не создан: {type(exc).__name__}: {exc}", reply_markup=_back(node_id))


@advanced_nodes_router.callback_query(F.data.regexp(r"^admin:nodectl:\d+:restartxray$"))
async def node_restart_xray_ask(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    node_id = _node_id_from_callback(call.data or "")
    try:
        node = await xui.node_get(node_id)
    except XUIError as exc:
        await call.answer(str(exc)[:180], show_alert=True)
        return
    if system_backup.direct_client_for(node.name) is None:
        await call.answer("Нет direct admin token", show_alert=True)
        await render_callback(call, 
            "🔄 Перезапуск Xray на удалённой ноде требует отдельного admin-scope API token, "
            "того же, который используется для NODE_BACKUP_TARGETS.",
            reply_markup=_back(node_id),
        )
        return
    await call.answer()
    await render_callback(call, 
        f"⚠️ Перезапустить Xray на {node.name}?\n\nАктивные подключения кратковременно оборвутся.",
        reply_markup=_confirm(node_id, "restartxray", "🔄 Да, restart Xray"),
    )


@advanced_nodes_router.callback_query(F.data.regexp(r"^admin:nodectl:\d+:restartxray:run$"))
async def node_restart_xray_run(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    node_id = _node_id_from_callback(call.data or "")
    try:
        node = await xui.node_get(node_id)
        client = system_backup.direct_client_for(node.name)
        if client is None:
            raise RuntimeError("direct admin token is not configured")
        await client.restart_xray()
        await audit_from_call(
            db, call, "node.xray.restart", target_type="node", target_id=node_id,
            details=f"name={node.name}",
        )
    except Exception as exc:
        await audit_from_call(
            db, call, "node.xray.restart", target_type="node", target_id=node_id,
            details=f"{type(exc).__name__}: {exc}", success=False,
        )
        await call.answer("Restart failed", show_alert=True)
        await render_callback(call, f"🔴 Xray restart: {type(exc).__name__}: {exc}", reply_markup=_back(node_id))
        return
    await call.answer("Xray restart отправлен")
    await render_callback(call, "✅ Команда restart Xray отправлена ноде.", reply_markup=_back(node_id))


@advanced_nodes_router.callback_query(F.data.regexp(r"^admin:nodectl:\d+:updatepanel$"))
@advanced_nodes_router.callback_query(F.data.regexp(r"^admin:nodectl:\d+:updatepanel:run$"))
async def node_update_panel_legacy(call: CallbackQuery):
    # Old keyboards cannot bypass the new backup, locking and confirmation gates.
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    node_id = _node_id_from_callback(call.data or "")
    await show_panel_screen(call, f"n{node_id}")


@advanced_nodes_router.callback_query(F.data.regexp(r"^admin:nodectl:\d+:deleteask$"))
async def node_delete_ask(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    node_id = _node_id_from_callback(call.data or "")
    try:
        node = await xui.node_get(node_id)
        inbounds = await xui.inbounds_list(slim=True)
        attached = [ib for ib in inbounds if _node_key(ib.get("nodeId")) == node_id]
    except XUIError as exc:
        await call.answer(str(exc)[:180], show_alert=True)
        return
    if attached:
        await call.answer("Сначала удали/detach inbound'ы", show_alert=True)
        await render_callback(call, 
            f"🛡 Ноду {node.name} нельзя удалить: к ней привязано inbound'ов: {len(attached)}.\n"
            "Сначала перенеси или удали их. 3x-ui также блокирует удаление ноды с привязанными inbound'ами.",
            reply_markup=_back(node_id),
        )
        return
    await call.answer()
    await render_callback(call, 
        f"🗑 Удалить ноду {node.name} из master 3x-ui?\n\n"
        "Это удалит регистрацию ноды на Master, но не удалит сам VPS/3x-ui на удалённом сервере.",
        reply_markup=_confirm(node_id, "delete", "⚠️ Да, удалить ноду"),
    )


@advanced_nodes_router.callback_query(F.data.regexp(r"^admin:nodectl:\d+:delete:run$"))
async def node_delete_run(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    node_id = _node_id_from_callback(call.data or "")
    name = f"#{node_id}"
    try:
        try:
            node = await xui.node_get(node_id)
            name = node.name
        except XUIError:
            pass
        await xui.node_delete(node_id)
        await audit_from_call(
            db, call, "node.delete", target_type="node", target_id=node_id,
            details=f"name={name}",
        )
    except XUIError as exc:
        await audit_from_call(
            db, call, "node.delete", target_type="node", target_id=node_id,
            details=str(exc), success=False,
        )
        await call.answer("Удаление не выполнено", show_alert=True)
        await render_callback(call, f"🔴 3x-ui: {exc}", reply_markup=_back(node_id))
        return
    await call.answer("Нода удалена")
    await render_callback(call, 
        f"✅ Нода {name} удалена из Master.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅ Ноды", callback_data="admin:nodes")],
        ]),
    )
