from __future__ import annotations

import asyncio
import logging
import time

from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile

from admin_auth import authorize_callback
from admin_navigation import backup_menu
from admin_ui import render_callback
from audit import audit_from_call
from backup_manager import BackupManager
from config import load_settings
from db import Database
from offsite_backup import replicate_with_job, service_from_settings
from restore_manager import RestoreManager
from runtime_jobs import backup_lock
from system_backup import SystemBackupService


settings = load_settings()
db = Database(settings.db_path)
backup_manager = BackupManager(
    settings.db_path,
    settings.backup_dir,
    settings.backup_keep,
)
system_backup = SystemBackupService(
    backup_manager,
    settings.node_backup_targets,
    settings.host_control_targets,
)
offsite_restore_manager = RestoreManager(settings.db_path, settings.backup_dir)
offsite_backup = service_from_settings(settings, offsite_restore_manager)

storage_admin_router = Router(name="storage_admin")


async def _guard(call: CallbackQuery) -> bool:
    ok, _ = await authorize_callback(db, settings, call)
    return ok


def human_bytes(value: int) -> str:
    n = int(value or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return "0 B"


def backup_status_text() -> str:
    items = backup_manager.list_backups()
    latest = items[0] if items else None
    lines = ["💾 Резервные копии", ""]
    if latest:
        ts = latest.created_at.strftime("%Y-%m-%d %H:%M UTC")
        lines.append(f"Последняя: {ts}")
        lines.append(f"Размер: {human_bytes(latest.size)}")
    else:
        lines.append("Последняя: ещё не создана")
    lines.append(f"Хранится полных копий: {len(items)} / {settings.backup_keep}")
    lines.append(f"Автоматически: {'включено' if settings.backup_enabled else 'выключено'}")
    if settings.backup_enabled:
        lines.append(f"Ежедневно: {settings.backup_hour_utc:02d}:00 UTC")
        if settings.backup_send_to_admins:
            lines.append("Отправка администраторам: включена")
    if settings.offsite_backup_enabled:
        lines.append(f"☁️ Внешняя копия: включена · шифрование · хранить {settings.offsite_backup_keep}")
    else:
        lines.append("☁️ Внешняя копия: выключена")
    names = system_backup.configured_node_names()
    if names:
        lines.append(f"Резервные копии нод: {len(names)} — {', '.join(names)}")
    else:
        lines.append("Резервные копии нод: не настроены")
    lines += ["", "⚠️ Полный архив содержит чувствительные данные."]
    return "\n".join(lines)


@storage_admin_router.callback_query(F.data == "admin:backups")
async def admin_backups(call: CallbackQuery):
    if not await _guard(call):
        return
    await render_callback(call, backup_status_text(), reply_markup=backup_menu())
    await call.answer()


@storage_admin_router.callback_query(F.data == "admin:backup:create")
async def admin_backup_create(call: CallbackQuery):
    if not await _guard(call):
        return
    if backup_lock.locked():
        await call.answer("Резервное копирование уже выполняется.", show_alert=True)
        return

    await call.answer("Создаю резервную копию…")
    run_id = await db.start_job_run(
        name="backup.manual",
        trigger="admin",
        actor_id=call.from_user.id if call.from_user else 0,
    )
    started = time.monotonic()

    try:
        async with backup_lock:
            result = await system_backup.create_full_backup()

        duration_ms = int((time.monotonic() - started) * 1000)
        await db.finish_job_run(
            run_id,
            status="success",
            duration_ms=duration_ms,
            details=(
                f"{result.info.path.name}; {result.info.size} bytes; "
                f"missing={len(result.missing)}"
            ),
        )
        await audit_from_call(
            db,
            call,
            "backup.create",
            target_type="backup",
            target_id=result.info.path.name,
            details=f"size={result.info.size}; missing={len(result.missing)}",
        )

        offsite_status, _offsite_result, offsite_detail = await replicate_with_job(
            db,
            offsite_backup,
            result.info.path,
            trigger="admin",
            actor_id=call.from_user.id if call.from_user else 0,
        )
        if offsite_status != "disabled":
            await audit_from_call(
                db,
                call,
                "backup.offsite.upload",
                target_type="backup",
                target_id=result.info.path.name,
                details=offsite_detail,
                success=offsite_status in {"success", "partial"},
            )

        lines = [
            "✅ Полная резервная копия создана.",
            f"Файл: {result.info.path.name}",
            f"Размер: {human_bytes(result.info.size)}",
            f"Включено: {', '.join(result.included) or 'нет'}",
        ]
        if offsite_status == "success":
            lines.append("☁️ Внешняя копия: загружена и проверена")
        elif offsite_status == "partial":
            lines.append("⚠️ Внешняя копия: загружена и проверена, локальная резервная копия неполная")
        elif offsite_status == "failed":
            lines.append(f"🔴 Внешняя копия: ошибка — {offsite_detail[:240]}")
        if result.missing:
            lines.append(f"⚠️ Не найдено: {', '.join(result.missing)}")

        await render_callback(call, "\n".join(lines), reply_markup=backup_menu())
    except Exception as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        await db.finish_job_run(
            run_id,
            status="failed",
            duration_ms=duration_ms,
            details=f"{type(exc).__name__}: {exc}",
        )
        await audit_from_call(
            db,
            call,
            "backup.create",
            target_type="backup",
            details=f"{type(exc).__name__}: {exc}",
            success=False,
        )
        logging.exception("Manual backup failed")
        await render_callback(
            call,
            f"🔴 Не удалось создать резервную копию: {type(exc).__name__}: {exc}",
            reply_markup=backup_menu(),
        )


@storage_admin_router.callback_query(F.data == "admin:backup:botdb")
async def admin_backup_botdb(call: CallbackQuery):
    if not await _guard(call):
        return
    await call.answer("Готовлю SQLite…")

    try:
        path = await asyncio.to_thread(backup_manager.create_bot_snapshot)
        await call.message.answer_document(
            FSInputFile(path),
            caption="Свежая консистентная копия bot.sqlite3",
        )
        await audit_from_call(
            db,
            call,
            "backup.download",
            target_type="bot.sqlite3",
            target_id=path.name,
            details="consistent SQLite snapshot",
        )
    except Exception as exc:
        await audit_from_call(
            db,
            call,
            "backup.download",
            target_type="bot.sqlite3",
            details=f"{type(exc).__name__}: {exc}",
            success=False,
        )
        logging.exception("Bot DB snapshot failed")
        await render_callback(
            call,
            f"🔴 Ошибка резервной копии SQLite: {type(exc).__name__}: {exc}",
        )


@storage_admin_router.callback_query(F.data == "admin:backup:full")
async def admin_backup_full(call: CallbackQuery):
    if not await _guard(call):
        return
    await call.answer("Готовлю архив…")

    try:
        info = await asyncio.to_thread(backup_manager.latest_backup)
        if info is None:
            if backup_lock.locked():
                await render_callback(
                    call,
                    "Резервная копия уже создаётся. Повтори скачивание чуть позже.",
                )
                return
            async with backup_lock:
                result = await system_backup.create_full_backup()
            info = result.info

        await call.message.answer_document(
            FSInputFile(info.path),
            caption=(
                "Полная резервная копия. Храните файл в защищённом месте.\n"
                f"Создан: {info.created_at.strftime('%Y-%m-%d %H:%M UTC')}"
            ),
        )
        await audit_from_call(
            db,
            call,
            "backup.download",
            target_type="full",
            target_id=info.path.name,
            details=f"size={info.size}",
        )
    except Exception as exc:
        await audit_from_call(
            db,
            call,
            "backup.download",
            target_type="full",
            details=f"{type(exc).__name__}: {exc}",
            success=False,
        )
        logging.exception("Full backup download failed")
        await render_callback(
            call,
            f"🔴 Ошибка отправки резервной копии: {type(exc).__name__}: {exc}",
        )
