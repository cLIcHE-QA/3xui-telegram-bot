from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

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
from restore_manager import BackupInspection, RestoreError, RestoreManager
from system_backup import SystemBackupService
from xui import XUIClient, XUIError

settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
backup_manager = BackupManager(settings.db_path, settings.backup_dir, settings.backup_keep)
system_backup = SystemBackupService(backup_manager, settings.node_backup_targets, settings.host_control_targets)
restore_manager = RestoreManager(settings.db_path, settings.backup_dir)

disaster_recovery_router = Router(name="disaster_recovery")


class RestoreStates(StatesGroup):
    confirm = State()


def human_bytes(value: int | float) -> str:
    n = max(0.0, float(value or 0))
    units = ("B", "KB", "MB", "GB", "TB")
    for unit in units:
        if n < 1024 or unit == units[-1]:
            return f"{int(n)} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _backup_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Резервные копии", callback_data="admin:backups")],
    ])


def _restore_back(backup_id: str | None = None) -> InlineKeyboardMarkup:
    target = f"admin:restore:b:{backup_id}" if backup_id else "admin:restore"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Восстановление", callback_data=target)],
    ])


def _backup_by_id(backup_id: str) -> Path:
    return restore_manager.find_backup(backup_id)


def _inspection_summary(info: BackupInspection, *, deep: bool = False) -> str:
    manifest_version = str(info.manifest.get("version") or "—") if info.manifest else "—"
    lines = [
        "🧯 Аварийное восстановление",
        "",
        f"Резервная копия: {info.path.name}",
        f"Создан: {info.created_at.strftime('%Y-%m-%d %H:%M UTC')}",
        f"Размер: {human_bytes(info.size)}",
        f"Версия manifest: {manifest_version}",
        f"Архив: {'✅ корректен' if info.valid else '🔴 некорректен'}",
        "",
        "Компоненты:",
        f"{'✅' if info.has_bot_db else '—'} bot.sqlite3",
        f"{'✅' if info.has_xui_db else '—'} x-ui.db (Master)",
        f"{'✅' if info.has_bot_env else '—'} bot.env",
        f"{'✅' if info.nginx_files else '—'} nginx/ ({info.nginx_files} файлов)",
        f"{'✅' if info.nodes else '—'} БД нод ({len(info.nodes)})",
    ]
    if deep:
        if info.has_bot_db:
            lines.append(f"bot.sqlite3 quick_check: {'✅ успешно' if info.bot_db_ok else '🔴 ошибка'}")
        if info.has_xui_db:
            lines.append(f"x-ui.db quick_check: {'✅ успешно' if info.xui_db_ok else '🔴 ошибка'}")
        if info.panel_token_matches is True:
            lines.append("PANEL_API_TOKEN: ✅ совпадает с текущим")
        elif info.panel_token_matches is False:
            lines.append("PANEL_API_TOKEN: ⚠️ отличается от текущего")
        elif info.has_bot_env:
            lines.append("PANEL_API_TOKEN: ? не удалось сравнить")
    if info.nodes:
        lines += ["", "Ноды:"]
        for node in info.nodes[:20]:
            lines.append(f"• {node.name} · {node.database_filename}")
    if info.warnings:
        lines += ["", "⚠️ Предупреждения:"]
        lines.extend(f"• {x}" for x in info.warnings[:8])
    if info.errors:
        lines += ["", "🔴 Ошибки:"]
        lines.extend(f"• {x}" for x in info.errors[:8])
    return "\n".join(lines)


def _backup_actions(info: BackupInspection) -> InlineKeyboardMarkup:
    bid = info.backup_id
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="🧪 Проверка (dry-run / preflight)", callback_data=f"admin:restore:pre:{bid}")],
    ]
    if info.has_bot_db:
        rows.append([InlineKeyboardButton(text="🤖 Восстановить bot.sqlite3", callback_data=f"admin:restore:bot:{bid}")])
    if info.has_xui_db:
        rows.append([InlineKeyboardButton(text="🖥 Восстановить Master x-ui.db", callback_data=f"admin:restore:xui:{bid}")])
    for idx, node in enumerate(info.nodes[:20]):
        rows.append([InlineKeyboardButton(
            text=f"🌍 Восстановить ноду: {node.name}",
            callback_data=f"admin:restore:node:{bid}:{idx}",
        )])
    export_row: list[InlineKeyboardButton] = []
    if info.has_bot_env:
        export_row.append(InlineKeyboardButton(text="📥 bot.env", callback_data=f"admin:restore:env:{bid}"))
    if info.nginx_files:
        export_row.append(InlineKeyboardButton(text="📥 nginx/", callback_data=f"admin:restore:nginx:{bid}"))
    if export_row:
        rows.append(export_row)
    rows += [
        [InlineKeyboardButton(text="🕘 История восстановления", callback_data="admin:restore:history")],
        [InlineKeyboardButton(text="⬅ Резервные копии", callback_data="admin:backups")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@disaster_recovery_router.callback_query(F.data == "admin:restore")
async def restore_list(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    backups = restore_manager.list_backups()[:10]
    rows: list[list[InlineKeyboardButton]] = []
    lines = [
        "🧯 Аварийное восстановление",
        "",
        "Восстановление доступно только Owner. Перед любым опасным восстановлением выполняется preflight и создаётся rescue-копия текущего состояния.",
        "",
    ]
    if restore_manager.pending_bot_restore():
        lines.append("⚠️ Есть ожидающее восстановление bot.sqlite3. Не создавай второй запрос восстановления.")
        lines.append("")
    if not backups:
        lines.append("Полных резервных копий пока нет.")
    for path in backups:
        bid = restore_manager.backup_id(path)
        stat = path.stat()
        dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        rows.append([InlineKeyboardButton(
            text=f"{dt.strftime('%m-%d %H:%M')} · {human_bytes(stat.st_size)}",
            callback_data=f"admin:restore:b:{bid}",
        )])
    rows += [
        [InlineKeyboardButton(text="🕘 История восстановления", callback_data="admin:restore:history")],
        [InlineKeyboardButton(text="⬅ Резервные копии", callback_data="admin:backups")],
    ]
    await call.answer()
    await render_callback(call, "\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@disaster_recovery_router.callback_query(F.data.regexp(r"^admin:restore:b:[A-Za-z0-9._-]+$"))
async def restore_detail(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    bid = (call.data or "").split(":", 3)[3]
    try:
        path = _backup_by_id(bid)
        info = await asyncio.to_thread(restore_manager.inspect_backup, path)
    except Exception as exc:
        await call.answer("Резервная копия недоступна", show_alert=True)
        await render_callback(call, f"🔴 {type(exc).__name__}: {exc}", reply_markup=_backup_back())
        return
    await call.answer()
    await render_callback(call, _inspection_summary(info), reply_markup=_backup_actions(info))


@disaster_recovery_router.callback_query(F.data.regexp(r"^admin:restore:pre:[A-Za-z0-9._-]+$"))
async def restore_preflight(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    bid = (call.data or "").split(":", 3)[3]
    await call.answer("Проверяю архив…")
    try:
        path = _backup_by_id(bid)
        info = await asyncio.to_thread(
            restore_manager.inspect_backup,
            path,
            deep=True,
            current_panel_token=settings.panel_api_token,
        )
        await audit_from_call(
            db, call, "restore.preflight", target_type="backup", target_id=path.name,
            details=f"valid={info.valid}; nodes={len(info.nodes)}; warnings={len(info.warnings)}; errors={len(info.errors)}",
            success=info.valid,
        )
        status = "✅ Проверка завершена. Никакие данные не изменены." if info.valid else "🔴 Preflight не пройден. Восстановление заблокировано до исправления ошибок."
        await render_callback(call, 
            _inspection_summary(info, deep=True) + "\n\n" + status,
            reply_markup=_backup_actions(info),
        )
    except Exception as exc:
        await audit_from_call(
            db, call, "restore.preflight", target_type="backup", target_id=bid,
            details=f"{type(exc).__name__}: {exc}", success=False,
        )
        await render_callback(call, f"🔴 Ошибка preflight: {type(exc).__name__}: {exc}", reply_markup=_restore_back(bid))


async def _start_confirmation(
    call: CallbackQuery,
    state: FSMContext,
    *,
    action: str,
    backup_id: str,
    phrase: str,
    node_index: int | None = None,
    warning: str,
) -> None:
    await state.set_state(RestoreStates.confirm)
    await state.update_data(
        restore_action=action,
        backup_id=backup_id,
        phrase=phrase,
        node_index=node_index,
    )
    await call.answer()
    await render_callback(call, 
        warning
        + "\n\nЭто destructive-операция. Для второго подтверждения отправь отдельным сообщением точно:\n\n"
        + phrase,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:restore:cancel:{backup_id}")
        ]]),
    )


@disaster_recovery_router.callback_query(F.data.regexp(r"^admin:restore:bot:[A-Za-z0-9._-]+$"))
async def restore_bot_start(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    bid = (call.data or "").split(":", 3)[3]
    try:
        path = _backup_by_id(bid)
        info = await asyncio.to_thread(restore_manager.inspect_backup, path, deep=True)
        if not info.valid or info.bot_db_ok is not True:
            raise RestoreError("bot.sqlite3 не прошёл preflight")
    except Exception as exc:
        await call.answer("Восстановление заблокировано", show_alert=True)
        await render_callback(call, f"🔴 {type(exc).__name__}: {exc}", reply_markup=_restore_back(bid))
        return
    await _start_confirmation(
        call, state,
        action="bot", backup_id=bid, phrase="RESTORE BOT",
        warning=(
            "🤖 Восстановление bot.sqlite3\n\n"
            "Будет создан rescue snapshot текущей БД бота, затем контейнер бота автоматически перезапустится и до старта Python заменит SQLite. "
            "После запуска versioned SQLite migrations проверят и при необходимости обновят схему до версии текущего кода; состояния failed/running/newer schema блокируют startup fail-closed. .env, 3x-ui и nginx не изменяются."
        ),
    )


@disaster_recovery_router.callback_query(F.data.regexp(r"^admin:restore:xui:[A-Za-z0-9._-]+$"))
async def restore_xui_start(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    bid = (call.data or "").split(":", 3)[3]
    try:
        path = _backup_by_id(bid)
        info = await asyncio.to_thread(
            restore_manager.inspect_backup,
            path,
            deep=True,
            current_panel_token=settings.panel_api_token,
        )
        if not info.valid or info.xui_db_ok is not True:
            raise RestoreError("x-ui.db не прошёл preflight")
    except Exception as exc:
        await call.answer("Восстановление заблокировано", show_alert=True)
        await render_callback(call, f"🔴 {type(exc).__name__}: {exc}", reply_markup=_restore_back(bid))
        return
    phrase = "RESTORE XUI FORCE" if info.panel_token_matches is False else "RESTORE XUI"
    token_warning = (
        "\n\n⚠️ PANEL_API_TOKEN в резервной копии отличается от текущего. После восстановления бот может потерять доступ к 3x-ui. "
        "Из архива можно скачать bot.env для ручного восстановления токена."
        if info.panel_token_matches is False else ""
    )
    await _start_confirmation(
        call, state,
        action="xui", backup_id=bid, phrase=phrase,
        warning=(
            "🖥 Восстановление Master x-ui.db\n\n"
            "Перед импортом бот скачает свежую rescue-копию текущей базы Master. Затем база будет импортирована через штатный 3x-ui importDB с keepHostSettings=true. "
            "3x-ui перезапустит панель/Xray после импорта. bot.sqlite3 и nginx не меняются."
            + token_warning
        ),
    )


@disaster_recovery_router.callback_query(F.data.regexp(r"^admin:restore:node:[A-Za-z0-9._-]+:\d+$"))
async def restore_node_start(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    parts = (call.data or "").split(":")
    bid = parts[3]
    idx = int(parts[4])
    try:
        path = _backup_by_id(bid)
        info = await asyncio.to_thread(restore_manager.inspect_backup, path, deep=True)
        node = info.nodes[idx]
        if not info.valid:
            raise RestoreError("резервная копия не прошла preflight")
        if system_backup.direct_client_for(node.name, getattr(node, "id", None)) is None:
            raise RestoreError(
                f"Для {node.name} не настроен Direct Admin token в NODE_BACKUP_TARGETS; автоматическое восстановление запрещено."
            )
        data = await asyncio.to_thread(restore_manager.read_member, path, node.member_name)
        if node.database_filename.lower().endswith(".db"):
            ok_db, detail = restore_manager._sqlite_check_bytes(data)
            if not ok_db:
                raise RestoreError(f"node DB quick_check failed: {detail}")
    except Exception as exc:
        await call.answer("Восстановление ноды заблокировано", show_alert=True)
        await render_callback(call, f"🔴 {type(exc).__name__}: {exc}", reply_markup=_restore_back(bid))
        return
    await _start_confirmation(
        call, state,
        action="node", backup_id=bid, node_index=idx, phrase="RESTORE NODE",
        warning=(
            f"🌍 Восстановление ноды: {node.name}\n\n"
            "Перед импортом будет скачана rescue-копия текущей DB этой ноды. Затем используется штатный importDB с keepHostSettings=true. "
            "Нода перезапустит свою панель/Xray. Остальные ноды и Master не изменяются."
        ),
    )


@disaster_recovery_router.callback_query(F.data.regexp(r"^admin:restore:cancel:[A-Za-z0-9._-]+$"))
async def restore_cancel(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    bid = (call.data or "").split(":", 3)[3]
    await state.clear()
    await call.answer("Отменено")
    await render_callback(call, "Восстановление отменено. Данные не изменены.", reply_markup=_restore_back(bid))


async def _exit_for_bot_restore() -> None:
    await asyncio.sleep(2.0)
    os._exit(75)


@disaster_recovery_router.message(RestoreStates.confirm)
async def restore_confirm_message(message: Message, state: FSMContext):
    if not message.from_user:
        return
    ok, _ = await authorize_message(db, settings, message.from_user.id, minimum="owner")
    if not ok:
        await state.clear()
        await render_input(message, "Недостаточно прав.")
        return
    state_data = await state.get_data()
    phrase = str(state_data.get("phrase") or "")
    if (message.text or "").strip() != phrase:
        await render_input(message, f"Фраза не совпала. Восстановление не выполнено. Для подтверждения отправь точно: {phrase}")
        return
    action = str(state_data.get("restore_action") or "")
    bid = str(state_data.get("backup_id") or "")
    node_index = state_data.get("node_index")
    await state.clear()

    try:
        path = _backup_by_id(bid)
        info = await asyncio.to_thread(
            restore_manager.inspect_backup,
            path,
            deep=True,
            current_panel_token=settings.panel_api_token,
        )
        if not info.valid:
            raise RestoreError("Резервная копия больше не проходит preflight.")

        if action == "bot":
            marker = await asyncio.to_thread(
                restore_manager.stage_bot_restore,
                path,
                actor_id=message.from_user.id,
            )
            await audit_from_message(
                db, message, "restore.bot.schedule", target_type="backup", target_id=path.name,
                details=f"rescue={marker.get('rescue_path')}",
            )
            await render_input(message, 
                "✅ Восстановление bot.sqlite3 подготовлено.\n\n"
                "Контейнер бота перезапустится примерно через 2 секунды. На старте restore-bootstrap заменит БД атомарно; при ошибке старая БД останется, а бот всё равно запустится."
            )
            asyncio.create_task(_exit_for_bot_restore())
            return

        if action == "xui":
            if info.xui_db_ok is not True:
                raise RestoreError("x-ui.db не прошёл SQLite quick_check")
            archived = await asyncio.to_thread(restore_manager.read_member, path, "x-ui.db")
            current, current_name = await xui.download_database()
            rescue = await asyncio.to_thread(
                restore_manager.save_rescue_blob, "master-xui", current_name, current
            )
            await render_input(message, 
                f"💾 Rescue-копия текущего Master сохранена: {rescue.name}\nЗапускаю importDB…"
            )
            await xui.import_database(archived, "x-ui.db", keep_host_settings=True)
            await asyncio.to_thread(restore_manager.append_history, {
                "status": "success", "kind": "master-xui", "backup_id": bid,
                "actor_id": message.from_user.id, "rescue": str(rescue),
            })
            await audit_from_message(
                db, message, "restore.xui", target_type="backup", target_id=path.name,
                details=f"keepHostSettings=true; rescue={rescue.name}",
            )
            await render_input(message, 
                "✅ БД Master x-ui импортирована. 3x-ui перезапускает панель/Xray.\n\n"
                "Проверь через 5–10 секунд «Мониторинг → Состояние системы». Если API token из резервной копии отличался, возможно потребуется вернуть соответствующий PANEL_API_TOKEN в .env."
            )
            return

        if action == "node":
            idx = int(node_index)
            node = info.nodes[idx]
            client = system_backup.direct_client_for(node.name, getattr(node, "id", None))
            if client is None:
                raise RestoreError(f"Direct admin token для {node.name} не настроен")
            archived = await asyncio.to_thread(restore_manager.read_member, path, node.member_name)
            if node.database_filename.lower().endswith(".db"):
                ok_db, detail = restore_manager._sqlite_check_bytes(archived)
                if not ok_db:
                    raise RestoreError(f"node DB quick_check failed: {detail}")
            current, current_name = await client.download_database()
            rescue = await asyncio.to_thread(
                restore_manager.save_rescue_blob, f"node-{node.name}", current_name, current
            )
            await render_input(message, 
                f"💾 Rescue-копия текущей БД {node.name} сохранена: {rescue.name}\nЗапускаю importDB…"
            )
            await client.import_database(
                archived,
                node.database_filename,
                keep_host_settings=True,
            )
            await asyncio.to_thread(restore_manager.append_history, {
                "status": "success", "kind": "node-xui", "node": node.name,
                "backup_id": bid, "actor_id": message.from_user.id, "rescue": str(rescue),
            })
            await audit_from_message(
                db, message, "restore.node", target_type="node", target_id=node.name,
                details=f"backup={path.name}; keepHostSettings=true; rescue={rescue.name}",
            )
            await render_input(message, 
                f"✅ БД ноды {node.name} импортирована. Нода перезапускает панель/Xray.\n"
                "Через несколько секунд открой «Инфраструктура → Ноды» и выполни проверку. "
                "Если резервная копия содержала другой admin/API token, обнови соответствующий NODE_BACKUP_*_API_TOKEN в .env."
            )
            return

        raise RestoreError("Неизвестное действие восстановления")
    except Exception as exc:
        await asyncio.to_thread(restore_manager.append_history, {
            "status": "failed", "kind": action or "unknown", "backup_id": bid,
            "actor_id": message.from_user.id, "error": f"{type(exc).__name__}: {exc}",
        })
        await audit_from_message(
            db, message, "restore.failed", target_type="backup", target_id=bid,
            details=f"action={action}; {type(exc).__name__}: {exc}", success=False,
        )
        await render_input(message, f"🔴 Восстановление не выполнено: {type(exc).__name__}: {exc}", reply_markup=_restore_back(bid))


@disaster_recovery_router.callback_query(F.data.regexp(r"^admin:restore:env:[A-Za-z0-9._-]+$"))
async def restore_export_env(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    bid = (call.data or "").split(":", 3)[3]
    try:
        path = _backup_by_id(bid)
        out = await asyncio.to_thread(restore_manager.export_member, path, "bot.env", filename="bot.env")
        await call.message.answer_document(
            FSInputFile(out),
            caption="bot.env из резервной копии. Содержит секреты. Бот НЕ применяет его автоматически.",
        )
        try:
            out.unlink()
        except OSError:
            pass
        await audit_from_call(db, call, "restore.export_env", target_type="backup", target_id=path.name)
        await call.answer()
    except Exception as exc:
        await call.answer("Ошибка экспорта", show_alert=True)
        await render_callback(call, f"🔴 {type(exc).__name__}: {exc}", reply_markup=_restore_back(bid))


@disaster_recovery_router.callback_query(F.data.regexp(r"^admin:restore:nginx:[A-Za-z0-9._-]+$"))
async def restore_export_nginx(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    bid = (call.data or "").split(":", 3)[3]
    try:
        path = _backup_by_id(bid)
        out = await asyncio.to_thread(restore_manager.export_nginx_bundle, path)
        await call.message.answer_document(
            FSInputFile(out),
            caption=(
                "nginx/ из резервной копии. Автоматически НЕ применяется: восстанови вручную, затем обязательно `nginx -t` перед reload."
            ),
        )
        try:
            out.unlink()
        except OSError:
            pass
        await audit_from_call(db, call, "restore.export_nginx", target_type="backup", target_id=path.name)
        await call.answer()
    except Exception as exc:
        await call.answer("Ошибка экспорта", show_alert=True)
        await render_callback(call, f"🔴 {type(exc).__name__}: {exc}", reply_markup=_restore_back(bid))


@disaster_recovery_router.callback_query(F.data == "admin:restore:history")
async def restore_history(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    items = await asyncio.to_thread(restore_manager.recent_history, 12)
    lines = ["🕘 История восстановления", ""]
    if not items:
        lines.append("Восстановление ещё не запускалось.")
    for item in items:
        status = str(item.get("status") or "?")
        icon = "✅" if status == "success" else "🔴" if status == "failed" else "🟡"
        kind = str(item.get("kind") or "restore")
        node = str(item.get("node") or "")
        backup_id = str(item.get("backup_id") or "")
        at = str(item.get("at_utc") or "")[:19].replace("T", " ")
        suffix = f" · {node}" if node else ""
        lines.append(f"{icon} {at} · {kind}{suffix} · {backup_id}")
        if item.get("error"):
            lines.append(f"   {str(item.get('error'))[:180]}")
    await call.answer()
    await render_callback(call, "\n".join(lines), reply_markup=_backup_back())


async def send_boot_restore_notice(bot) -> None:
    """Notify break-glass owners about a bot DB restore performed before startup."""
    result = await asyncio.to_thread(restore_manager.consume_boot_result)
    if not result:
        return
    status = str(result.get("status") or "")
    if status == "success":
        text = (
            "✅ Аварийное восстановление: bot.sqlite3 восстановлена до запуска бота.\n"
            f"Резервная копия: {result.get('backup_name') or result.get('backup_id') or '—'}\n"
            f"Rescue-копия предыдущей БД: {Path(str(result.get('rescue') or '')).name or '—'}"
        )
    else:
        text = (
            "🔴 Аварийное восстановление: bot.sqlite3 НЕ восстановлена. Бот запущен со старой БД.\n"
            f"Ошибка: {result.get('error') or 'неизвестно'}"
        )
    for admin_id in settings.admin_telegram_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass
