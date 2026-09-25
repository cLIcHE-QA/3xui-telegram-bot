import asyncio
import logging
import secrets
import shutil
import time
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile

from backup_manager import BackupManager
from config import load_settings
from db import Database, UserRecord
from xui import XUIClient, XUIError, NodeInfo
from version import APP_VERSION
from versions_updates import versions_router
from bot_updates import bot_updates_router, reconcile_deploy_jobs
from system_backup import SystemBackupService
from subscription_proxy import SubscriptionProxy
from catalog_admin import catalog_router
from admin_observability import observability_router
from business_admin import business_router
from advanced_users import advanced_users_router
from inbound_admin import inbound_admin_router, inbound_list_view
from advanced_nodes import advanced_nodes_router
from host_control_ui import host_control_router, recover_control_jobs
from fleet_operations import fleet_router, recover_fleet_operations
from admin_auth import authorize_callback, get_admin_role
from inbound_policy import is_managed_inbound as inbound_is_managed
from audit import audit_from_call, audit_system
from runtime_jobs import backup_lock
from provisioning import ProvisioningEngine
from logs_alerts import logs_alerts_router, alert_monitor_loop
from logging_setup import configure_logging
from disaster_recovery import disaster_recovery_router, send_boot_restore_notice
from restore_manager import RestoreManager
from offsite_backup import replicate_with_job, service_from_settings
from admin_ui import AdminPanelSessionMiddleware, register_panel_message, render_callback, render_input
from admin_navigation import (
    admin_menu,
    infrastructure_menu,
    monitoring_menu,
    system_menu,
)
from node_ui import master_detail_keyboard, node_detail_keyboard
from node_admin import node_admin_router, nodes_menu, node_detail_text as _node_detail_text
from system_admin import system_admin_router, admin_master_detail
from storage_admin import storage_admin_router

settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
router = Router()
backup_manager = BackupManager(settings.db_path, settings.backup_dir, settings.backup_keep)
system_backup = SystemBackupService(backup_manager, settings.node_backup_targets, settings.host_control_targets)
offsite_restore_manager = RestoreManager(settings.db_path, settings.backup_dir)
offsite_backup = service_from_settings(settings, offsite_restore_manager)
provisioner = ProvisioningEngine(db, xui, settings)


def is_allowed(tg_id: int) -> bool:
    return tg_id in settings.allowed_telegram_ids or tg_id in settings.admin_telegram_ids

def is_admin(tg_id: int) -> bool:
    return tg_id in settings.admin_telegram_ids

def user_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Проверить inbound'ы", callback_data="inbounds")],
        [InlineKeyboardButton(text="🧪 Создать тестовый доступ", callback_data="create")],
        [InlineKeyboardButton(text="🔗 Моя подписка", callback_data="subscription")],
    ])

async def guard_message(message: Message) -> bool:
    if not message.from_user or not is_allowed(message.from_user.id):
        await message.answer("Нет доступа.")
        return False
    return True

async def guard_admin_call(call: CallbackQuery) -> bool:
    ok, _ = await authorize_callback(db, settings, call)
    return ok

def is_managed_inbound(i) -> bool:
    return inbound_is_managed(settings, i)

def choose_inbounds(inbounds):
    return [i for i in inbounds if i.enable and is_managed_inbound(i)]

def sub_url(sub_id: str) -> str:
    template = settings.compat_subscription_url_template or settings.subscription_url_template
    return template.format(sub_id=sub_id)

def fmt_date(ms: int) -> str:
    if not ms:
        return "без срока"
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def human_bytes(n: int) -> str:
    n = int(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024

@router.message(CommandStart())
async def start(message: Message):
    if not await guard_message(message):
        return
    await message.answer(f"3x-ui Telegram bot v{APP_VERSION}", reply_markup=user_menu())

@router.message(Command("admin"))
async def admin(message: Message):
    if not message.from_user:
        return
    role = await get_admin_role(db, settings, message.from_user.id)
    if role is None:
        await message.answer("Команда доступна только администратору.")
        return
    panel = await message.answer(f"⚙️ Admin Panel · {role}", reply_markup=admin_menu())
    register_panel_message(message.from_user.id, panel)

def _section_header(title: str, subtitle: str) -> str:
    return f"{title}\n\n{subtitle}"


def system_section_text() -> str:
    return _section_header(
        "⚙️ System",
        f"🤖 Bot: v{APP_VERSION}\n\n"
        "Фоновые задачи, backups, аудит, администраторы и настройки.",
    )


@router.callback_query(F.data == "admin:dashboard")
async def admin_dashboard(call: CallbackQuery):
    if not await guard_admin_call(call):
        return

    users = await db.list_users()
    now_ms = int(time.time() * 1000)
    active = sum(1 for u in users if not u.expiry_time or u.expiry_time > now_ms)
    soon = sum(
        1 for u in users
        if u.expiry_time and now_ms < u.expiry_time <= now_ms + 3 * 86400 * 1000
    )

    master_online = False
    master_detail = "offline"
    nodes: list[NodeInfo] = []
    nodes_error = None
    inbounds = []
    inbounds_error = None
    traffic_rows: list[dict] = []
    traffic_error = None
    online_clients: list[str] = []
    online_error = None

    try:
        await xui.server_status()
        master_online = True
        master_detail = "online"
    except XUIError as exc:
        master_detail = str(exc)[:120]

    try:
        nodes = await xui.nodes_list()
    except XUIError as exc:
        nodes_error = str(exc)[:120]

    try:
        inbounds = await xui.inbound_options()
    except XUIError as exc:
        inbounds_error = str(exc)[:120]

    monitoring_results = await asyncio.gather(
        xui.clients_list(),
        xui.online_clients(),
        return_exceptions=True,
    )
    traffic_result, online_result = monitoring_results
    if isinstance(traffic_result, Exception):
        traffic_error = str(traffic_result)[:120]
    else:
        traffic_rows = traffic_result
    if isinstance(online_result, Exception):
        online_error = str(online_result)[:120]
    else:
        online_clients = online_result

    remote_online = sum(1 for n in nodes if n.enable and n.status == "online")
    servers_total = 1 + len(nodes)
    servers_online = (1 if master_online else 0) + remote_online

    managed = [i for i in inbounds if is_managed_inbound(i)]
    managed_enabled = sum(1 for i in managed if i.enable)

    plans = await db.list_plans()
    server_groups = await db.list_server_groups()
    hosts = await db.list_hosts()
    active_plans = sum(1 for p in plans if p.active)
    default_plan = await provisioner.default_plan()
    enabled_hosts = sum(1 for h in hosts if h.enabled)
    payment_summary = await db.payment_summary()
    promo_codes = await db.list_promo_codes()
    active_alerts = await db.list_alert_states(active_only=True)
    now_s = int(time.time())
    active_promos = sum(
        1 for promo in promo_codes
        if promo.active
        and (not promo.expires_at or promo.expires_at >= now_s)
        and (not promo.max_uses or promo.uses_count < promo.max_uses)
    )

    latest = backup_manager.latest_backup()
    if latest:
        backup_text = latest.created_at.strftime("%Y-%m-%d %H:%M UTC")
    else:
        backup_text = "ещё не создан"

    lines = [
        "📊 Dashboard",
        "",
        "Users",
        f"👥 Всего: {len(users)}",
        f"🟢 Активные: {active}",
        f"⏳ Истекают < 3 дней: {soon}",
        "",
        "Infrastructure",
        f"{'🟢' if master_online else '🔴'} {settings.master_flag} {settings.master_name}: {master_detail}",
        f"🌍 Servers: {servers_online}/{servers_total} online",
    ]
    if inbounds_error:
        lines.append(f"⚠️ Inbounds: {inbounds_error}")
    else:
        lines.append(f"📡 Inbounds: {managed_enabled}/{len(managed)} enabled")
    if nodes_error:
        lines.append(f"⚠️ Nodes API: {nodes_error}")
    lines += [
        "",
        "Catalog",
        f"💎 Plans: {active_plans}/{len(plans)} active",
        f"⭐ Default /create: {default_plan.name if default_plan else 'trial legacy policy'}",
        f"🗂 Server Groups: {len(server_groups)}",
        f"🌐 Hosts: {enabled_hosts}/{len(hosts)} enabled",
        "",
        "Business",
        f"💳 Payments: {sum(payment_summary.get(k, 0) for k in ('pending', 'paid', 'refunded', 'cancelled'))} · paid {payment_summary.get('paid', 0)}",
        f"🎟 Promo Codes: {active_promos}/{len(promo_codes)} active",
        "",
        "Monitoring",
    ]
    if traffic_error:
        lines.append(f"⚠️ Traffic: {traffic_error}")
    else:
        traffic_total = 0
        for row in traffic_rows:
            traffic = row.get("traffic") if isinstance(row, dict) and isinstance(row.get("traffic"), dict) else {}
            traffic_total += int(traffic.get("up") or 0) + int(traffic.get("down") or 0)
        lines.append(f"📊 Traffic used: {human_bytes(traffic_total)}")
    if online_error:
        lines.append(f"⚠️ Online: {online_error}")
    else:
        lines.append(f"🟢 Online clients: {len(set(online_clients))}")
    lines.append(f"{'🚨' if active_alerts else '✅'} Active alerts: {len(active_alerts)}")
    lines += [
        "",
        "System",
        f"💾 Last backup: {backup_text}",
    ]

    await render_callback(call, "\n".join(lines), reply_markup=admin_menu())
    await call.answer()


@router.callback_query(F.data == "admin:subscriptions")
async def admin_subscriptions(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    users = await db.list_users()
    rows: list[list[InlineKeyboardButton]] = []
    for u in users[:40]:
        rows.append([InlineKeyboardButton(
            text=f"🔗 {u.email}",
            callback_data=f"adminsub:{u.telegram_id}",
        )])
    rows.append([InlineKeyboardButton(text="⬅ Dashboard", callback_data="admin:home")])
    text = (
        "🔗 Subscriptions\n\n"
        f"Всего подписок в локальной БД: {len(users)}\n"
        "Открой запись, чтобы получить текущий compatibility URL."
    )
    await render_callback(call, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data == "admin:section:infrastructure")
async def admin_infrastructure(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    await render_callback(call, 
        _section_header(
            "🌐 Infrastructure",
            "Управление панелями, нодами, inbound'ами, hosts и группами серверов.",
        ),
        reply_markup=infrastructure_menu(),
    )
    await call.answer()


@router.callback_query(F.data == "admin:section:monitoring")
async def admin_monitoring(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    await render_callback(call, 
        _section_header(
            "📈 Monitoring",
            "Трафик, online-состояние, здоровье системы и журналы.",
        ),
        reply_markup=monitoring_menu(),
    )
    await call.answer()


@router.callback_query(F.data == "admin:section:system")
async def admin_system(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    await render_callback(
        call,
        system_section_text(),
        reply_markup=system_menu(),
    )
    await call.answer()


@router.callback_query(F.data == "admin:infra:inbounds")
async def admin_infrastructure_inbounds(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    try:
        text, kb = await inbound_list_view()
        await render_callback(call, text, reply_markup=kb)
    except XUIError as exc:
        await render_callback(call, 
            f"📡 Inbounds\n\nОшибка 3x-ui: {exc}",
            reply_markup=infrastructure_menu(),
        )
    await call.answer()


@router.callback_query(F.data == "admin:coming:plans")
@router.callback_query(F.data == "admin:coming:hosts")
@router.callback_query(F.data == "admin:coming:servergroups")
async def admin_legacy_catalog_callback(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    target = {
        "admin:coming:plans": ("💎 Plans", "admin:plans"),
        "admin:coming:hosts": ("🌐 Hosts", "admin:hosts"),
        "admin:coming:servergroups": ("🗂 Server Groups", "admin:servergroups"),
    }[call.data]
    await render_callback(call, 
        "Этот раздел уже доступен в v3.9.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=target[0], callback_data=target[1])
        ]]),
    )
    await call.answer()


@router.callback_query(F.data == "admin:coming:traffic")
@router.callback_query(F.data == "admin:coming:online")
@router.callback_query(F.data == "admin:coming:jobs")
@router.callback_query(F.data == "admin:coming:audit")
@router.callback_query(F.data == "admin:coming:payments")
@router.callback_query(F.data == "admin:coming:promo")
@router.callback_query(F.data == "admin:coming:administrators")
@router.callback_query(F.data == "admin:coming:settings")
async def admin_legacy_v4_callback(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    target = {
        "admin:coming:traffic": ("📊 Traffic", "admin:traffic"),
        "admin:coming:online": ("🟢 Online", "admin:online"),
        "admin:coming:jobs": ("⚙️ Jobs", "admin:jobs"),
        "admin:coming:audit": ("🧾 Audit Log", "admin:audit"),
        "admin:coming:payments": ("💳 Payments", "admin:payments"),
        "admin:coming:promo": ("🎟 Promo Codes", "admin:promo"),
        "admin:coming:administrators": ("👮 Administrators", "admin:administrators"),
        "admin:coming:settings": ("🔧 Settings", "admin:settings"),
    }[call.data]
    await render_callback(call, 
        "Этот раздел уже доступен в текущей версии.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=target[0], callback_data=target[1])
        ]]),
    )
    await call.answer()


@router.callback_query(F.data == "admin:coming:logs")
async def admin_legacy_logs_callback(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    await render_callback(call, 
        "Раздел Logs уже доступен в текущей версии.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📜 Logs", callback_data="admin:logs")
        ]]),
    )
    await call.answer()


COMING_SOON = {
    "payments": ("💳 Payments", "Раздел Payments уже доступен."),
    "promo": ("🎟 Promo Codes", "Раздел Promo Codes уже доступен."),
    "panels": ("🖥 Panels", "Раздел панелей зарезервирован. Текущий Master продолжает работать без изменений."),
    "traffic": ("📊 Traffic", "Агрегация трафика будет добавлена на этапе Monitoring."),
    "online": ("🟢 Online", "Online-клиенты будут добавлены на этапе Monitoring."),
    "jobs": ("⚙️ Jobs", "Планировщик и история фоновых задач будут добавлены отдельно."),
    "audit": ("🧾 Audit Log", "Аудит административных действий будет добавлен отдельным модулем."),
    "administrators": ("👮 Administrators", "Раздел Administrators уже доступен."),
    "settings": ("🔧 Settings", "Раздел safe runtime Settings уже доступен."),
}


@router.callback_query(F.data.startswith("admin:coming:"))
async def admin_coming_soon(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    key = call.data.rsplit(":", 1)[-1]
    title, body = COMING_SOON.get(key, ("Раздел", "Раздел зарезервирован для следующего этапа."))
    if key in {"panels", "hosts", "servergroups"}:
        back = infrastructure_menu()
    elif key in {"traffic", "online", "logs"}:
        back = monitoring_menu()
    elif key in {"jobs", "audit", "administrators", "settings"}:
        back = system_menu()
    else:
        back = admin_menu()
    await render_callback(call, f"{title}\n\n{body}", reply_markup=back)
    await call.answer()


@router.callback_query(F.data == "admin:home")
async def admin_home(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    await render_callback(call, "⚙️ Admin Panel", reply_markup=admin_menu())
    await call.answer()

@router.message(Command("inbounds"))
async def inbounds_cmd(message: Message):
    if not await guard_message(message):
        return
    await show_inbounds(message)

@router.callback_query(F.data == "inbounds")
async def inbounds_cb(call: CallbackQuery):
    if not call.from_user or not is_allowed(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return
    await show_inbounds(call.message)
    await call.answer()

async def show_inbounds(message: Message):
    try:
        all_inbounds = await xui.inbound_options()
        chosen = choose_inbounds(all_inbounds)
        lines = [
            f"• ID #{i.id} | {i.port} | {i.protocol}\n  tag: {i.tag}\n  name: {i.remark}"
            for i in chosen
        ]
        await message.answer("Будут выданы:\n\n" + ("\n\n".join(lines) or "Ничего"))
    except XUIError as e:
        await message.answer(f"Ошибка 3x-ui: {e}")

@router.message(Command("create"))
async def create_cmd(message: Message):
    if not await guard_message(message):
        return
    await create_user(message.from_user.id, message)

@router.callback_query(F.data == "create")
async def create_cb(call: CallbackQuery):
    if not call.from_user or not is_allowed(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return
    await create_user(call.from_user.id, call.message)
    await call.answer()

async def create_user(tg_id: int, message: Message):
    existing = await db.get(tg_id)
    if existing:
        await message.answer(f"Уже создан:\n{sub_url(existing.sub_id)}")
        return
    try:
        panel_matches = await xui.get_client_by_tg_id(tg_id)
        if panel_matches:
            item = panel_matches[0]
            client = item.get("client", item)
            if client.get("email") and client.get("subId"):
                rec = UserRecord(
                    tg_id, client["email"], client["subId"],
                    int(client.get("expiryTime") or 0), int(time.time())
                )
                await db.put(rec)
                await message.answer(f"Восстановлен:\n{sub_url(rec.sub_id)}")
                return

        default_plan, policy = await provisioner.new_user_plan()
        now = int(time.time())
        provisioning_note = ""
        if default_plan and policy:
            inbound_ids = list(policy.actionable_inbound_ids)
            if not inbound_ids:
                await message.answer(
                    "Provisioning default Plan настроен, но сейчас нет доступных target inbound'ов. "
                    "Попроси администратора проверить Plan → Server Group → Nodes/Inbounds."
                )
                return
            duration_days = max(0, default_plan.duration_days)
            traffic_gb = max(0, default_plan.traffic_gb)
            ip_limit = max(0, default_plan.ip_limit)
            expiry = (now + duration_days * 86400) * 1000 if duration_days else 0
            provisioning_note = f"Plan: {default_plan.name}"
        else:
            chosen = choose_inbounds(await xui.inbound_options())
            if not chosen:
                await message.answer("Нет подходящих inbound'ов.")
                return
            inbound_ids = [i.id for i in chosen]
            try:
                duration_days = int(await db.get_runtime_setting("trial_days", str(settings.test_days)) or settings.test_days)
                traffic_gb = int(await db.get_runtime_setting("trial_traffic_gb", str(settings.test_traffic_gb)) or settings.test_traffic_gb)
                ip_limit = int(await db.get_runtime_setting("trial_ip_limit", str(settings.test_ip_limit)) or settings.test_ip_limit)
            except (TypeError, ValueError):
                duration_days = settings.test_days
                traffic_gb = settings.test_traffic_gb
                ip_limit = settings.test_ip_limit
            expiry = (now + duration_days * 86400) * 1000
            provisioning_note = "Trial legacy policy"

        username = ""
        if getattr(message, "chat", None) and getattr(message.chat, "username", None):
            username = message.chat.username.strip().lower()
        email = f"tg_{username}" if username else f"tg_{tg_id}"
        sid = secrets.token_urlsafe(18)
        await xui.create_client(
            email=email, telegram_id=tg_id, sub_id=sid,
            inbound_ids=inbound_ids,
            total_bytes=traffic_gb * 1024**3,
            expiry_time_ms=expiry, limit_ip=ip_limit,
            comment=f"Created by Telegram bot v{APP_VERSION} · {provisioning_note}",
            flow=settings.vless_flow,
        )
        if settings.vless_flow:
            await xui.bulk_adjust_clients([email], flow=settings.vless_flow)
        await db.put(UserRecord(tg_id, email, sid, expiry, now))
        if default_plan and policy:
            await db.upsert_user_profile(
                tg_id,
                plan_id=default_plan.id,
                server_group_id=default_plan.server_group_id,
                note="",
                preserve_unspecified=False,
            )
        lines = ["✅ Создан", "", sub_url(sid)]
        if default_plan and policy:
            lines += ["", f"💎 Plan: {default_plan.name}", f"📡 Inbounds: {', '.join(map(str, inbound_ids))}"]
            if policy.unavailable_members:
                lines.append("⏸ Часть нод недоступна; администратор сможет выполнить reconcile позже.")
        await message.answer("\n".join(lines))
    except XUIError as e:
        await message.answer(f"Ошибка 3x-ui: {e}")

@router.message(Command("subscription"))
async def sub_cmd(message: Message):
    if not await guard_message(message):
        return
    rec = await db.get(message.from_user.id)
    if rec:
        await message.answer(sub_url(rec.sub_id))
    else:
        await message.answer("Сначала /create")

@router.callback_query(F.data == "subscription")
async def sub_cb(call: CallbackQuery):
    if not call.from_user or not is_allowed(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return
    rec = await db.get(call.from_user.id)
    await render_callback(call, sub_url(rec.sub_id) if rec else "Сначала создай доступ.")
    await call.answer()

async def _seconds_until_backup_hour() -> float:
    now = datetime.now(timezone.utc)
    target = now.replace(
        hour=settings.backup_hour_utc,
        minute=0,
        second=0,
        microsecond=0,
    )
    if target <= now:
        target += timedelta(days=1)
    return max(1.0, (target - now).total_seconds())


async def automatic_backup_loop(bot: Bot):
    while True:
        await asyncio.sleep(await _seconds_until_backup_hour())
        run_id = await db.start_job_run(name="backup.daily", trigger="scheduled", actor_id=0)
        started = time.monotonic()
        try:
            async with backup_lock:
                result = await system_backup.create_full_backup()
            duration_ms = int((time.monotonic() - started) * 1000)
            await db.finish_job_run(
                run_id, status="success", duration_ms=duration_ms,
                details=f"{result.info.path.name}; {result.info.size} bytes; missing={len(result.missing)}",
            )
            await audit_system(
                db, "backup.create", target_type="backup", target_id=result.info.path.name,
                details=f"scheduled; size={result.info.size}; missing={len(result.missing)}",
            )
            logging.info(
                "Automatic backup created: %s (%d bytes)",
                result.info.path,
                result.info.size,
            )
            offsite_status, _, offsite_detail = await replicate_with_job(
                db,
                offsite_backup,
                result.info.path,
                trigger="scheduled",
                actor_id=0,
            )
            if offsite_status != "disabled":
                await audit_system(
                    db,
                    "backup.offsite.upload",
                    target_type="backup",
                    target_id=result.info.path.name,
                    details=offsite_detail,
                    success=offsite_status in {"success", "partial"},
                )
                if offsite_status == "failed":
                    logging.error("Off-site backup failed: %s", offsite_detail)
                else:
                    logging.info("Off-site backup %s: %s", offsite_status, result.info.path.name)
            if settings.backup_send_to_admins:
                for admin_id in settings.admin_telegram_ids:
                    try:
                        await bot.send_document(
                            admin_id,
                            FSInputFile(result.info.path),
                            caption=(
                                "💾 Ежедневный backup 3x-ui bot. "
                                "Архив содержит секреты."
                            ),
                        )
                    except Exception:
                        logging.exception("Could not send automatic backup to admin %s", admin_id)
        except asyncio.CancelledError:
            duration_ms = int((time.monotonic() - started) * 1000)
            await db.finish_job_run(
                run_id, status="failed", duration_ms=duration_ms, details="cancelled",
            )
            raise
        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            await db.finish_job_run(
                run_id, status="failed", duration_ms=duration_ms,
                details=f"{type(exc).__name__}: {exc}",
            )
            await audit_system(
                db, "backup.create", target_type="backup",
                details=f"scheduled failed: {type(exc).__name__}: {exc}", success=False,
            )
            logging.exception("Automatic backup failed")


async def _recover_deploy_after_health() -> None:
    recovered = await reconcile_deploy_jobs(wait_seconds=60)
    if recovered:
        logging.warning(
            "Recovered %d interrupted bot deployment jobs after health startup without mutation replay",
            recovered,
        )


async def main():
    configure_logging()
    await db.init()
    recovered_deploy = await reconcile_deploy_jobs(wait_seconds=0)
    if recovered_deploy:
        logging.warning(
            "Recovered %d interrupted bot deployment jobs without mutation replay",
            recovered_deploy,
        )
    recovered_control = await recover_control_jobs()
    if recovered_control:
        logging.warning(
            "Recovered %d interrupted Host Control jobs without mutation replay",
            recovered_control,
        )
    stale_jobs = await db.fail_stale_job_runs()
    if stale_jobs:
        logging.warning("Marked %d stale job runs as failed", stale_jobs)
    recovered_fleet = await recover_fleet_operations()
    if recovered_fleet:
        logging.warning("Recovered %d interrupted fleet operations without replay", recovered_fleet)

    proxy = SubscriptionProxy(
        db=db,
        upstream_template=settings.subscription_url_template,
        public_template=settings.compat_subscription_url_template,
        verify_tls=settings.verify_tls,
        host=settings.subscription_proxy_host,
        port=settings.subscription_proxy_port,
    )
    await proxy.start()
    deploy_recovery_task = (
        asyncio.create_task(_recover_deploy_after_health())
        if settings.deploy_agent_enabled else None
    )

    bot = Bot(settings.bot_token)
    await send_boot_restore_notice(bot)
    dp = Dispatcher()
    dp.callback_query.outer_middleware(AdminPanelSessionMiddleware())
    dp.include_router(router)
    dp.include_router(node_admin_router)
    dp.include_router(system_admin_router)
    dp.include_router(storage_admin_router)
    dp.include_router(versions_router)
    dp.include_router(bot_updates_router)
    dp.include_router(advanced_users_router)
    dp.include_router(advanced_nodes_router)
    dp.include_router(host_control_router)
    dp.include_router(fleet_router)
    dp.include_router(inbound_admin_router)
    dp.include_router(catalog_router)
    dp.include_router(observability_router)
    dp.include_router(logs_alerts_router)
    dp.include_router(disaster_recovery_router)
    dp.include_router(business_router)
    backup_task = (
        asyncio.create_task(automatic_backup_loop(bot))
        if settings.backup_enabled else None
    )
    alert_task = asyncio.create_task(alert_monitor_loop(bot))
    try:
        await dp.start_polling(bot)
    finally:
        for task in (backup_task, alert_task, deploy_recovery_task):
            if task:
                task.cancel()
        for task in (backup_task, alert_task, deploy_recovery_task):
            if task:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        await proxy.stop()

if __name__ == "__main__":
    asyncio.run(main())
