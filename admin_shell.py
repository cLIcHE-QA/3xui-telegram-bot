from __future__ import annotations

import asyncio
import time

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_auth import authorize_callback, get_admin_role
from admin_navigation import admin_menu, infrastructure_menu, monitoring_menu, system_menu
from admin_ui import register_panel_message, render_callback
from backup_manager import BackupManager
from config import load_settings
from db import Database
from inbound_admin import inbound_list_view
from inbound_policy import is_managed_inbound as inbound_is_managed
from provisioning import ProvisioningEngine
from version import APP_VERSION
from xui import NodeInfo, XUIClient, XUIError


settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
backup_manager = BackupManager(settings.db_path, settings.backup_dir, settings.backup_keep)
provisioner = ProvisioningEngine(db, xui, settings)

admin_shell_router = Router(name="admin_shell")


async def guard_admin_call(call: CallbackQuery) -> bool:
    ok, _ = await authorize_callback(db, settings, call)
    return ok

def is_managed_inbound(i) -> bool:
    return inbound_is_managed(settings, i)

def human_bytes(n: int) -> str:
    n = int(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024

@admin_shell_router.message(Command("admin"))
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


@admin_shell_router.callback_query(F.data == "admin:dashboard")
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


@admin_shell_router.callback_query(F.data == "admin:subscriptions")
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


@admin_shell_router.callback_query(F.data == "admin:section:infrastructure")
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


@admin_shell_router.callback_query(F.data == "admin:section:monitoring")
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


@admin_shell_router.callback_query(F.data == "admin:section:system")
async def admin_system(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    await render_callback(
        call,
        system_section_text(),
        reply_markup=system_menu(),
    )
    await call.answer()


@admin_shell_router.callback_query(F.data == "admin:infra:inbounds")
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


@admin_shell_router.callback_query(F.data == "admin:coming:plans")
@admin_shell_router.callback_query(F.data == "admin:coming:hosts")
@admin_shell_router.callback_query(F.data == "admin:coming:servergroups")
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


@admin_shell_router.callback_query(F.data == "admin:coming:traffic")
@admin_shell_router.callback_query(F.data == "admin:coming:online")
@admin_shell_router.callback_query(F.data == "admin:coming:jobs")
@admin_shell_router.callback_query(F.data == "admin:coming:audit")
@admin_shell_router.callback_query(F.data == "admin:coming:payments")
@admin_shell_router.callback_query(F.data == "admin:coming:promo")
@admin_shell_router.callback_query(F.data == "admin:coming:administrators")
@admin_shell_router.callback_query(F.data == "admin:coming:settings")
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


@admin_shell_router.callback_query(F.data == "admin:coming:logs")
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


@admin_shell_router.callback_query(F.data.startswith("admin:coming:"))
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


@admin_shell_router.callback_query(F.data == "admin:home")
async def admin_home(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    await render_callback(call, "⚙️ Admin Panel", reply_markup=admin_menu())
    await call.answer()
