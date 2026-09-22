from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from audit import audit_from_call
from admin_auth import authorize_callback
from backup_manager import BackupManager
from config import load_settings
from db import AuditRecord, Database, JobRunRecord
from runtime_jobs import backup_lock
from system_backup import SystemBackupService
from xui import XUIClient, XUIError

settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
backup_manager = BackupManager(settings.db_path, settings.backup_dir, settings.backup_keep)
system_backup = SystemBackupService(backup_manager, settings.node_backup_targets)
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
    if not ts:
        return "—"
    if ts > 10_000_000_000:  # tolerate millisecond timestamps
        ts //= 1000
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except (OSError, OverflowError, ValueError):
        return "—"


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
        [InlineKeyboardButton(text="⬅ Monitoring", callback_data="admin:section:monitoring")],
    ])


def system_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ System", callback_data="admin:section:system")],
    ])


@observability_router.callback_query(F.data == "admin:traffic")
async def traffic_view(call: CallbackQuery):
    if not await guard(call):
        return
    await call.answer("Собираю трафик…")
    try:
        clients = await xui.clients_list()
    except XUIError as exc:
        await call.message.answer(
            f"📊 Traffic\n\n🔴 3x-ui: {str(exc)[:500]}",
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
        "📊 Traffic",
        "",
        f"Клиентов 3x-ui: {len(rows)}",
        f"Пользователей бота: {len(bot_users)}",
        f"⬆ Upload: {human_bytes(total_up)}",
        f"⬇ Download: {human_bytes(total_down)}",
        f"Σ Использовано: {human_bytes(total_up + total_down)}",
    ]
    if finite_quota:
        pct = min(999.9, finite_used * 100 / finite_quota)
        lines.append(f"Квоты с лимитом: {human_bytes(finite_used)} / {human_bytes(finite_quota)} ({pct:.1f}%)")

    lines += ["", "Top traffic:"]
    if not rows:
        lines.append("— данных пока нет")
    else:
        for used, email, up, down, quota, known in rows[:12]:
            marker = "👤" if known else "•"
            if quota > 0:
                pct = min(999.9, used * 100 / quota)
                suffix = f" · {pct:.1f}% quota"
            else:
                suffix = " · unlimited"
            lines.append(f"{marker} {email} — {human_bytes(used)}{suffix}")
        if len(rows) > 12:
            lines.append(f"… ещё {len(rows) - 12}")

    lines += [
        "",
        "ℹ️ Это накопительные счётчики 3x-ui с момента последнего reset, не «трафик за сегодня».",
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:traffic")],
        [InlineKeyboardButton(text="⬅ Monitoring", callback_data="admin:section:monitoring")],
    ])
    await call.message.answer("\n".join(lines), reply_markup=kb)


@observability_router.callback_query(F.data == "admin:online")
async def online_view(call: CallbackQuery):
    if not await guard(call):
        return
    await call.answer("Проверяю online…")
    try:
        online, last_seen = await asyncio.gather(
            xui.online_clients(),
            xui.last_online(),
        )
    except XUIError as exc:
        await call.message.answer(
            f"🟢 Online\n\n🔴 3x-ui: {str(exc)[:500]}",
            reply_markup=monitoring_back(),
        )
        return

    bot_users = {u.email: u for u in await db.list_users()}
    online_unique = sorted(set(online), key=str.casefold)
    lines = [
        "🟢 Online",
        "",
        f"Сейчас подключено: {len(online_unique)}",
        f"Из пользователей бота: {sum(1 for email in online_unique if email in bot_users)}",
        "",
    ]
    if online_unique:
        lines.append("Сейчас online:")
        for email in online_unique[:25]:
            rec = bot_users.get(email)
            suffix = f" · TG {rec.telegram_id}" if rec else ""
            lines.append(f"🟢 {email}{suffix}")
        if len(online_unique) > 25:
            lines.append(f"… ещё {len(online_unique) - 25}")
    else:
        lines.append("Сейчас online-клиентов нет.")

    offline_recent = [
        (safe_int(ts), email)
        for email, ts in last_seen.items()
        if email not in set(online_unique) and safe_int(ts) > 0
    ]
    offline_recent.sort(reverse=True)
    if offline_recent:
        lines += ["", "Недавняя активность:"]
        for ts, email in offline_recent[:8]:
            lines.append(f"⚪ {email} — {ago_text(ts)}")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:online")],
        [InlineKeyboardButton(text="⬅ Monitoring", callback_data="admin:section:monitoring")],
    ])
    await call.message.answer("\n".join(lines), reply_markup=kb)


def next_backup_text() -> str:
    if not settings.backup_enabled:
        return "выключен"
    now = datetime.now(timezone.utc)
    target = now.replace(hour=settings.backup_hour_utc, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target.strftime("%Y-%m-%d %H:%M UTC")


def job_status_icon(status: str) -> str:
    return {
        "success": "✅",
        "failed": "🔴",
        "running": "⏳",
    }.get((status or "").lower(), "⚪")


def job_line(run: JobRunRecord | None) -> str:
    if run is None:
        return "ещё не запускалась"
    duration = f"{run.duration_ms / 1000:.1f}s" if run.duration_ms else "—"
    return f"{job_status_icon(run.status)} {run.status} · {utc_text(run.started_at)} · {duration}"


@observability_router.callback_query(F.data == "admin:jobs")
async def jobs_view(call: CallbackQuery):
    if not await guard(call):
        return
    daily = await db.last_job_run("backup.daily")
    manual = await db.last_job_run("backup.manual")
    history = await db.list_job_runs(limit=8)
    lines = [
        "⚙️ Jobs",
        "",
        "Daily backup",
        f"Статус расписания: {'🟢 enabled' if settings.backup_enabled else '⚪ disabled'}",
        f"Следующий запуск: {next_backup_text()}",
        f"Последний scheduled: {job_line(daily)}",
        f"Последний manual: {job_line(manual)}",
        "",
        "Последние запуски:",
    ]
    if history:
        for run in history:
            label = "scheduled" if run.trigger == "scheduled" else run.trigger
            lines.append(
                f"{job_status_icon(run.status)} {run.name} · {label} · "
                f"{utc_text(run.started_at)} · {run.duration_ms / 1000:.1f}s"
            )
    else:
        lines.append("— история пока пуста")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶ Запустить backup сейчас", callback_data="admin:jobs:backup")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:jobs")],
        [InlineKeyboardButton(text="⬅ System", callback_data="admin:section:system")],
    ])
    await call.message.answer("\n".join(lines), reply_markup=kb)
    await call.answer()


@observability_router.callback_query(F.data == "admin:jobs:backup")
async def jobs_run_backup(call: CallbackQuery):
    if not await guard(call):
        return
    if backup_lock.locked():
        await call.answer("Backup уже выполняется.", show_alert=True)
        return
    await call.answer("Запускаю backup…")
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
        await call.message.answer(
            "✅ Job завершён.\n\n"
            f"Файл: {result.info.path.name}\n"
            f"Размер: {human_bytes(result.info.size)}\n"
            f"Время: {duration_ms / 1000:.1f}s",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅ Jobs", callback_data="admin:jobs")],
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
        await call.message.answer(
            f"🔴 Backup job failed: {type(exc).__name__}: {str(exc)[:500]}",
            reply_markup=system_back(),
        )


ACTION_LABELS = {
    "user.sync": "sync user",
    "user.extend": "extend user",
    "user.disable": "disable user",
    "user.enable": "enable user",
    "user.delete": "delete user",
    "users.sync_all": "sync all users",
    "node.add": "add node",
    "backup.create": "create backup",
    "backup.download": "download backup",
    "plan.create": "create plan",
    "plan.toggle": "toggle plan",
    "plan.set_group": "set plan group",
    "plan.delete": "delete plan",
    "server_group.create": "create server group",
    "server_group.member": "change group member",
    "server_group.delete": "delete server group",
    "host.discover": "discover hosts",
    "host.create": "create host",
    "host.toggle": "toggle host",
    "host.delete": "delete host",
    "payment.create": "create payment",
    "payment.status": "change payment status",
    "promo.create": "create promo code",
    "promo.toggle": "toggle promo code",
    "promo.delete": "delete promo code",
    "administrator.upsert": "add administrator",
    "administrator.role": "change administrator role",
    "administrator.toggle": "toggle administrator",
    "administrator.delete": "delete administrator",
    "settings.set": "change setting",
    "settings.reset": "reset setting",
}


def audit_actor(item: AuditRecord) -> str:
    if item.actor_id == 0:
        return "system"
    if item.actor_username:
        return f"@{item.actor_username}"
    return f"TG {item.actor_id}"


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
    page_size = 15
    total = await db.count_audit()
    offset = max(0, min(offset, max(0, total - 1))) if total else 0
    items = await db.list_audit(limit=page_size, offset=offset)
    lines = ["🧾 Audit Log", "", f"Записей: {total}", ""]
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
            if item.details:
                detail = item.details if len(item.details) <= 140 else item.details[:137] + "…"
                lines.append(f"   {detail}")

    rows: list[list[InlineKeyboardButton]] = []
    nav: list[InlineKeyboardButton] = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="⬅ Новее", callback_data=f"admin:audit:{max(0, offset - page_size)}"))
    if offset + page_size < total:
        nav.append(InlineKeyboardButton(text="Старее ➡", callback_data=f"admin:audit:{offset + page_size}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data=f"admin:audit:{offset}")])
    rows.append([InlineKeyboardButton(text="⬅ System", callback_data="admin:section:system")])
    await call.message.answer("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()
