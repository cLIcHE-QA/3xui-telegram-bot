from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from audit import audit_from_call
from admin_ui import filter_keyboard_for_role, render_callback, render_input
from admin_auth import authorize_callback
from backup_manager import BackupManager
from config import load_settings
from db import AuditRecord, Database, JobRunRecord
from ui_time import MSK, format_timestamp
from user_ui import user_label
from runtime_jobs import backup_lock
from system_backup import SystemBackupService
from restore_manager import RestoreManager
from offsite_backup import replicate_with_job, service_from_settings
from xui import XUIClient, XUIError

settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
backup_manager = BackupManager(settings.db_path, settings.backup_dir, settings.backup_keep)
system_backup = SystemBackupService(backup_manager, settings.node_backup_targets, settings.host_control_targets)
offsite_restore_manager = RestoreManager(settings.db_path, settings.backup_dir)
offsite_backup = service_from_settings(settings, offsite_restore_manager)
observability_router = Router(name="admin_observability")


async def guard(call: CallbackQuery) -> bool:
    ok, _ = await authorize_callback(db, settings, call)
    return ok


def human_bytes(value: int | float) -> str:
    n = max(0.0, float(value or 0))
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    for unit in units:
        if n < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(n)} {unit}"
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def utc_text(ts: int) -> str:
    if ts > 10_000_000_000:
        return format_timestamp(ts, milliseconds=True)
    return format_timestamp(ts)


def ago_text(ts: int) -> str:
    if not ts:
        return "никогда"
    if ts > 10_000_000_000:
        ts //= 1000
    delta = max(0, int(time.time()) - int(ts))
    if delta < 60:
        return "только что"
    if delta < 3600:
        return f"{delta // 60} мин назад"
    if delta < 86400:
        return f"{delta // 3600} ч назад"
    return f"{delta // 86400} дн назад"


def monitoring_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Мониторинг", callback_data="admin:section:monitoring")],
    ])


def system_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Система", callback_data="admin:section:system")],
    ])


@observability_router.callback_query(F.data == "admin:traffic")
async def traffic_view(call: CallbackQuery):
    if not await guard(call):
        return
    await call.answer("Собираю трафик…")
    try:
        clients = await xui.clients_list()
    except XUIError as exc:
        await render_callback(call, 
            f"📊 Трафик\n\n🔴 3x-ui: {str(exc)[:500]}",
            reply_markup=monitoring_back(),
        )
        return

    bot_users = {u.email: u for u in await db.list_users()}
    rows: list[tuple[int, str, int, int, int, bool]] = []
    total_up = 0
    total_down = 0
    finite_quota = 0
    finite_used = 0

    for client in clients:
        if not isinstance(client, dict):
            continue
        email = str(client.get("email") or "—")
        traffic = client.get("traffic") if isinstance(client.get("traffic"), dict) else {}
        up = safe_int(traffic.get("up"))
        down = safe_int(traffic.get("down"))
        used = up + down
        quota = safe_int(client.get("totalGB"))
        total_up += up
        total_down += down
        if quota > 0:
            finite_quota += quota
            finite_used += min(used, quota)
        rows.append((used, email, up, down, quota, email in bot_users))

    rows.sort(key=lambda item: item[0], reverse=True)
    lines = [
        "📊 Трафик",
        "",
        f"👥 Клиентов 3x-ui: {len(rows)}",
        f"👥 Пользователей бота: {len(bot_users)}",
        f"⬆ Отправлено: {human_bytes(total_up)}",
        f"⬇ Получено: {human_bytes(total_down)}",
        f"📊 Использовано: {human_bytes(total_up + total_down)}",
    ]
    if finite_quota:
        pct = min(999.9, finite_used * 100 / finite_quota)
        lines.append(f"🎯 Квоты с лимитом: {human_bytes(finite_used)} / {human_bytes(finite_quota)} ({pct:.1f}%)")

    lines += ["", "Больше всего трафика:"]
    if not rows:
        lines.append("— данных пока нет")
    else:
        for used, email, up, down, quota, known in rows[:12]:
            marker = "👤" if known else "•"
            rec = bot_users.get(email)
            profile = await db.get_user_profile(rec.telegram_id) if rec else None
            label = user_label(rec, profile) if rec else email
            if quota > 0:
                pct = min(999.9, used * 100 / quota)
                suffix = f" · {pct:.1f}% квоты"
            else:
                suffix = " · без лимита"
            lines.append(f"{marker} {label} — {human_bytes(used)}{suffix}")
        if len(rows) > 12:
            lines.append(f"… ещё {len(rows) - 12}")

    lines += [
        "",
        "ℹ️ Это накопительные счётчики 3x-ui с момента последнего сброса, не «трафик за сегодня».",
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:traffic")],
        [InlineKeyboardButton(text="⬅ Мониторинг", callback_data="admin:section:monitoring")],
    ])
    await render_callback(call, "\n".join(lines), reply_markup=filter_keyboard_for_role(kb, role))


@observability_router.callback_query(F.data == "admin:online")
async def online_view(call: CallbackQuery):
    if not await guard(call):
        return
    await call.answer("Проверяю клиентов в сети…")
    try:
        online, last_seen = await asyncio.gather(
            xui.online_clients(),
            xui.last_online(),
        )
    except XUIError as exc:
        await render_callback(call, 
            f"🟢 Клиенты в сети\n\n🔴 3x-ui: {str(exc)[:500]}",
            reply_markup=monitoring_back(),
        )
        return

    bot_users = {u.email: u for u in await db.list_users()}
    online_unique = sorted(set(online), key=str.casefold)
    lines = [
        "🟢 Клиенты в сети",
        "",
        f"👥 Сейчас подключено: {len(online_unique)}",
        f"👥 Из пользователей бота: {sum(1 for email in online_unique if email in bot_users)}",
        "",
    ]
    if online_unique:
        lines.append("Сейчас в сети:")
        for email in online_unique[:25]:
            rec = bot_users.get(email)
            profile = await db.get_user_profile(rec.telegram_id) if rec else None
            label = user_label(rec, profile) if rec else email
            suffix = f" · TG {rec.telegram_id}" if rec else ""
            lines.append(f"🟢 {label}{suffix}")
        if len(online_unique) > 25:
            lines.append(f"… ещё {len(online_unique) - 25}")
    else:
        lines.append("Сейчас клиентов в сети нет.")

    offline_recent = [
        (safe_int(ts), email)
        for email, ts in last_seen.items()
        if email not in set(online_unique) and safe_int(ts) > 0
    ]
    offline_recent.sort(reverse=True)
    if offline_recent:
        lines += ["", "Недавняя активность:"]
        for ts, email in offline_recent[:8]:
            rec = bot_users.get(email)
            profile = await db.get_user_profile(rec.telegram_id) if rec else None
            label = user_label(rec, profile) if rec else email
            lines.append(f"⚪ {label} — {ago_text(ts)}")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:online")],
        [InlineKeyboardButton(text="⬅ Мониторинг", callback_data="admin:section:monitoring")],
    ])
    await render_callback(call, "\n".join(lines), reply_markup=kb)


def next_backup_text() -> str:
    if not settings.backup_enabled:
        return "выключен"
    now = datetime.now(timezone.utc)
    target = now.replace(hour=settings.backup_hour_utc, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target.astimezone(MSK).strftime("%Y-%m-%d %H:%M MSK")


def job_status_icon(status: str) -> str:
    return {
        "success": "✅",
        "partial": "⚠️",
        "failed": "🔴",
        "running": "⏳",
    }.get((status or "").lower(), "⚪")


JOB_STATUS_LABELS = {
    "success": "успешно",
    "partial": "частично",
    "failed": "ошибка",
    "running": "выполняется",
    "unknown": "неизвестно",
    "cancelled": "отменено",
}


JOB_TRIGGER_LABELS = {
    "scheduled": "по расписанию",
    "admin": "администратор",
    "startup": "запуск",
    "manual": "вручную",
    "system": "система",
}


def job_status_text(status: str) -> str:
    value = (status or "").lower()
    return JOB_STATUS_LABELS.get(value, status or "неизвестно")


def job_trigger_text(trigger: str) -> str:
    value = (trigger or "").lower()
    return JOB_TRIGGER_LABELS.get(value, trigger or "—")


def job_line(run: JobRunRecord | None) -> str:
    if run is None:
        return "ещё не запускалась"
    duration = f"{run.duration_ms / 1000:.1f}s" if run.duration_ms else "—"
    return f"{job_status_icon(run.status)} {job_status_text(run.status)} · {utc_text(run.started_at)} · {duration}"


@observability_router.callback_query(F.data == "admin:jobs")
async def jobs_view(call: CallbackQuery):
    ok, role = await authorize_callback(db, settings, call)
    if not ok or role is None:
        return
    daily = await db.last_job_run("backup.daily")
    manual = await db.last_job_run("backup.manual")
    offsite = await db.last_job_run("backup.offsite")
    provision = await db.last_job_run("provision.reconcile_all")
    history = await db.list_job_runs(limit=8)
    lines = [
        "⚙️ Задания",
        "",
        "💾 Ежедневная резервная копия",
        f"{'🟢' if settings.backup_enabled else '⚪'} Статус расписания: {'включено' if settings.backup_enabled else 'выключено'}",
        f"⏭ Следующий запуск: {next_backup_text()}",
        f"🕘 Последний по расписанию: {job_line(daily)}",
        f"👤 Последний ручной: {job_line(manual)}",
        f"☁️ Последняя внешняя копия: {job_line(offsite) if settings.offsite_backup_enabled else 'выключена'}",
        "",
        "🧩 Согласование",
        f"🕘 Последнее согласование пользователей: {job_line(provision)}",
        "",
        "🕘 Последние запуски:",
    ]
    if history:
        for run in history:
            label = job_trigger_text(run.trigger)
            lines.append(
                f"{job_status_icon(run.status)} {run.name} · {label} · "
                f"{utc_text(run.started_at)} · {run.duration_ms / 1000:.1f}s"
            )
    else:
        lines.append("— история пока пуста")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶ Запустить резервное копирование", callback_data="admin:jobs:backup")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:jobs")],
        [InlineKeyboardButton(text="⬅ Система", callback_data="admin:section:system")],
    ])
    await render_callback(
        call,
        "\n".join(lines),
        reply_markup=filter_keyboard_for_role(kb, role),
    )
    await call.answer()


@observability_router.callback_query(F.data == "admin:jobs:backup")
async def jobs_run_backup(call: CallbackQuery):
    if not await guard(call):
        return
    if backup_lock.locked():
        await call.answer("Резервное копирование уже выполняется.", show_alert=True)
        return
    await call.answer("Запускаю резервное копирование…")
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
        detail = f"{result.info.path.name}; {result.info.size} bytes; missing={len(result.missing)}"
        await db.finish_job_run(run_id, status="success", duration_ms=duration_ms, details=detail)
        await audit_from_call(
            db,
            call,
            "backup.create",
            target_type="backup",
            target_id=result.info.path.name,
            details=f"manual job; size={result.info.size}; missing={len(result.missing)}",
        )
        offsite_status, _, offsite_detail = await replicate_with_job(
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
        offsite_line = ""
        if offsite_status == "success":
            offsite_line = "\n☁️ Внешняя копия: загружена и проверена"
        elif offsite_status == "partial":
            offsite_line = "\n⚠️ Внешняя копия: загружена и проверена, локальная резервная копия неполная"
        elif offsite_status == "failed":
            offsite_line = f"\n🔴 Внешняя копия: ошибка — {offsite_detail[:240]}"
        await render_callback(call, 
            "✅ Задание завершено.\n\n"
            f"Файл: {result.info.path.name}\n"
            f"Размер: {human_bytes(result.info.size)}\n"
            f"Время: {duration_ms / 1000:.1f}s"
            f"{offsite_line}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅ Задания", callback_data="admin:jobs")],
            ]),
        )
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
            details=f"manual job failed: {type(exc).__name__}: {exc}",
            success=False,
        )
        await render_callback(call, 
            f"🔴 Задание резервного копирования завершилось ошибкой: {type(exc).__name__}: {str(exc)[:500]}",
            reply_markup=system_back(),
        )


ACTION_LABELS = {
    "bot.update.started": "обновление бота: запущено",
    "bot.update.recovered": "обновление бота: итог восстановлен",
    "panel.update.prepared": "обновление 3x-ui: подготовлено",
    "panel.update.started": "обновление 3x-ui: запущено",
    "panel.update.success": "обновление 3x-ui: успешно",
    "panel.update.failed": "обновление 3x-ui: ошибка",
    "panel.update.unconfirmed": "обновление 3x-ui: результат не подтверждён",
    "panel.update.cancelled": "обновление 3x-ui: отменено",
    "panel.update.acknowledged": "обновление 3x-ui: неопределённость подтверждена",
    "xray.install.prepared": "установка Xray: подготовлена",
    "xray.install.started": "установка Xray: запущена",
    "xray.install.success": "установка Xray: успешно",
    "xray.install.failed": "установка Xray: ошибка",
    "xray.install.unconfirmed": "установка Xray: результат не подтверждён",
    "xray.install.cancelled": "установка Xray: отменена",
    "xray.install.acknowledged": "установка Xray: неопределённость подтверждена",
    "user.sync": "синхронизация пользователя",
    "user.extend": "продление пользователя",
    "user.disable": "отключение пользователя",
    "user.enable": "включение пользователя",
    "user.delete": "удаление пользователя",
    "users.sync_all": "синхронизация всех пользователей",
    "node.add": "добавление ноды",
    "node.maintenance": "изменение режима обслуживания ноды",
    "node.rename": "переименование ноды",
    "node.backup": "резервная копия ноды",
    "node.xray.restart": "перезапуск Xray на ноде",
    "node.panel.update": "обновление 3x-ui на ноде",
    "node.delete": "удаление ноды",
    "host_control.start": "запуск сервиса 3x-ui",
    "host_control.stop": "остановка сервиса 3x-ui",
    "host_control.restart": "перезапуск сервиса 3x-ui",
    "panel.restart": "перезапуск процесса панели 3x-ui",
    "xray.stop": "остановка Xray",
    "xray.restart": "запуск/перезапуск Xray",
    "backup.create": "создание резервной копии",
    "backup.download": "скачивание резервной копии",
    "backup.offsite.upload": "репликация внешней резервной копии",
    "plan.create": "создание тарифа",
    "plan.toggle": "изменение состояния тарифа",
    "plan.set_group": "изменение группы тарифа",
    "plan.delete": "удаление тарифа",
    "plan.default": "назначение тарифа по умолчанию",
    "server_group.inbound_mode": "изменение режима Inbounds группы",
    "server_group.inbound": "изменение Inbounds согласования группы",
    "user.provision.safe": "безопасное согласование пользователя",
    "user.provision.strict": "строгое согласование пользователя",
    "user.plan.provision": "применение тарифа и согласование",
    "users.provision_all": "согласование всех пользователей",
    "server_group.create": "создание группы серверов",
    "server_group.member": "изменение участника группы",
    "server_group.delete": "удаление группы серверов",
    "user_group.create": "создание группы пользователей",
    "user_group.rename": "переименование группы пользователей",
    "user_group.description.set": "изменение описания группы пользователей",
    "user_group.member.add": "добавление пользователя в группу",
    "user_group.member.remove": "удаление пользователя из группы",
    "user_group.delete": "удаление группы пользователей",
    "host.discover": "поиск хостов",
    "host.create": "создание хоста",
    "host.toggle": "изменение состояния хоста",
    "host.delete": "удаление хоста",
    "payment.create": "создание платежа",
    "payment.status": "изменение статуса платежа",
    "promo.create": "создание промокода",
    "promo.toggle": "изменение состояния промокода",
    "promo.delete": "удаление промокода",
    "administrator.upsert": "добавление администратора",
    "administrator.role": "изменение роли администратора",
    "administrator.toggle": "изменение состояния администратора",
    "administrator.delete": "удаление администратора",
    "settings.set": "изменение настройки",
    "settings.reset": "сброс настройки",
}


def audit_actor(item: AuditRecord) -> str:
    if item.actor_id == 0:
        return "система"
    if item.actor_username:
        return f"@{item.actor_username}"
    return f"TG {item.actor_id}"


def _audit_detail_fields(details: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in (details or "").split(";"):
        key, sep, value = part.strip().partition("=")
        if sep and key:
            fields[key.strip()] = value.strip()
    return fields


def _audit_summary(item: AuditRecord) -> str:
    details = (item.details or "").strip()
    if not details:
        return ""
    if item.action.startswith("bot.update."):
        fields = _audit_detail_fields(details)
        parts: list[str] = []
        if fields.get("release"):
            parts.append(f"релиз {fields['release']}")
        if fields.get("state"):
            parts.append(f"состояние {fields['state']}")
        if fields.get("observed"):
            parts.append(f"фактически {fields['observed']}")
        if fields.get("operation_id"):
            parts.append(f"операция {fields['operation_id'][:8]}")
        if parts:
            return " · ".join(parts)
    return details if len(details) <= 120 else details[:117] + "…"


@observability_router.callback_query(F.data == "admin:audit")
async def audit_first(call: CallbackQuery):
    await audit_page(call, 0)


@observability_router.callback_query(F.data.regexp(r"^admin:audit:\d+$"))
async def audit_paged(call: CallbackQuery):
    offset = int(call.data.rsplit(":", 1)[-1])
    await audit_page(call, offset)


async def audit_page(call: CallbackQuery, offset: int):
    if not await guard(call):
        return
    page_size = 12
    total = await db.count_audit()
    offset = max(0, min(offset, max(0, total - 1))) if total else 0
    items = await db.list_audit(limit=page_size, offset=offset)
    lines = ["🧾 Журнал аудита", "", f"Записей: {total}", ""]
    detail_rows: list[list[InlineKeyboardButton]] = []
    if not items:
        lines.append("Аудит пока пуст.")
    else:
        for item in items:
            icon = "✅" if item.success else "🔴"
            action = ACTION_LABELS.get(item.action, item.action)
            target = ""
            if item.target_type or item.target_id:
                target = f" · {item.target_type}:{item.target_id}".rstrip(":")
            lines.append(
                f"{icon} {utc_text(item.created_at)}\n"
                f"   {audit_actor(item)} · {action}{target}"
            )
            summary = _audit_summary(item)
            if summary:
                lines.append(f"   {summary}")
                if len(item.details or "") > 120 or item.action.startswith("bot.update."):
                    detail_rows.append([
                        InlineKeyboardButton(
                            text=f"🔎 {utc_text(item.created_at)} · {action}"[:64],
                            callback_data=f"admin:audit:item:{item.id}:{offset}",
                        )
                    ])

    rows: list[list[InlineKeyboardButton]] = []
    nav: list[InlineKeyboardButton] = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="⬅ Новее", callback_data=f"admin:audit:{max(0, offset - page_size)}"))
    if offset + page_size < total:
        nav.append(InlineKeyboardButton(text="➡ Старее", callback_data=f"admin:audit:{offset + page_size}"))
    if nav:
        rows.append(nav)
    rows.extend(detail_rows)
    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data=f"admin:audit:{offset}")])
    rows.append([InlineKeyboardButton(text="⬅ Система", callback_data="admin:section:system")])
    await render_callback(call, "\n".join(lines)[:3900], reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@observability_router.callback_query(F.data.regexp(r"^admin:audit:item:\d+:\d+$"))
async def audit_detail(call: CallbackQuery):
    if not await guard(call):
        return
    parts = (call.data or "").split(":")
    audit_id, offset = int(parts[-2]), int(parts[-1])
    item = await db.get_audit(audit_id)
    if item is None:
        await call.answer("Запись аудита не найдена.", show_alert=True)
        return
    icon = "✅" if item.success else "🔴"
    action = ACTION_LABELS.get(item.action, item.action)
    target = (
        f"{item.target_type}:{item.target_id}".rstrip(":")
        if item.target_type or item.target_id else "—"
    )
    text = (
        f"🧾 Запись аудита #{item.id}\n\n"
        f"{icon} {utc_text(item.created_at)}\n"
        f"Кто: {audit_actor(item)}\n"
        f"Действие: {action}\n"
        f"Код действия: {item.action}\n"
        f"Цель: {target}\n\n"
        "Подробности:\n"
        f"{item.details or '—'}"
    )
    await render_callback(
        call,
        text[:3900],
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅ Журнал аудита", callback_data=f"admin:audit:{offset}")
        ]]),
    )
    await call.answer()
