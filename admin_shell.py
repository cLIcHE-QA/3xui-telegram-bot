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
    panel = await message.answer(f"⚙️ Панель администратора · {role}", reply_markup=admin_menu())
    register_panel_message(message.from_user.id, panel)

def _section_header(title: str, subtitle: str) -> str:
    return f"{title}\n\n{subtitle}"


def system_section_text() -> str:
    return _section_header(
        "⚙️ Система",
        f"🤖 Бот: v{APP_VERSION}\n\n"
        "Фоновые задачи, резервные копии, аудит, администраторы и настройки.",
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
    master_detail = "не в сети"
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
        master_detail = "в сети"
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
        "📊 Обзор",
        "",
        "Пользователи",
        f"👥 Всего: {len(users)}",
        f"🟢 Активные: {active}",
        f"⏳ Истекают < 3 дней: {soon}",
        "",
        "Инфраструктура",
        f"{'🟢' if master_online else '🔴'} {settings.master_flag} {settings.master_name}: {master_detail}",
        f"🌍 Серверы: {servers_online}/{servers_total} в сети",
    ]
    if inbounds_error:
        lines.append(f"⚠️ Inbound'ы: {inbounds_error}")
    else:
        lines.append(f"📡 Inbound'ы: {managed_enabled}/{len(managed)} включено")
    if nodes_error:
        lines.append(f"⚠️ Nodes API: {nodes_error}")
    lines += [
        "",
        "Каталог",
        f"💎 Тарифы: {active_plans}/{len(plans)} активных",
        f"⭐ По умолчанию для /create: {default_plan.name if default_plan else 'legacy trial policy'}",
        f"🗂 Группы серверов: {len(server_groups)}",
        f"🌐 Хосты: {enabled_hosts}/{len(hosts)} включено",
        "",
        "Бизнес",
        f"💳 Платежи: {sum(payment_summary.get(k, 0) for k in ('pending', 'paid', 'refunded', 'cancelled'))} · оплачено {payment_summary.get('paid', 0)}",
        f"🎟 Промокоды: {active_promos}/{len(promo_codes)} активных",
        "",
        "Мониторинг",
    ]
    if traffic_error:
        lines.append(f"⚠️ Трафик: {traffic_error}")
    else:
        traffic_total = 0
        for row in traffic_rows:
            traffic = row.get("traffic") if isinstance(row, dict) and isinstance(row.get("traffic"), dict) else {}
            traffic_total += int(traffic.get("up") or 0) + int(traffic.get("down") or 0)
        lines.append(f"📊 Использовано трафика: {human_bytes(traffic_total)}")
    if online_error:
        lines.append(f"⚠️ Статус online: {online_error}")
    else:
        lines.append(f"🟢 Клиентов в сети: {len(set(online_clients))}")
    lines.append(f"{'🚨' if active_alerts else '✅'} Активных оповещений: {len(active_alerts)}")
    lines += [
        "",
        "Система",
        f"💾 Последняя резервная копия: {backup_text}",
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
    rows.append([InlineKeyboardButton(text="⬅ Обзор", callback_data="admin:home")])
    text = (
        "🔗 Подписки\n\n"
        f"Всего подписок в локальной БД: {len(users)}\n"
        "Открой запись, чтобы получить текущий URL совместимости."
    )
    await render_callback(call, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@admin_shell_router.callback_query(F.data == "admin:section:infrastructure")
async def admin_infrastructure(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    await render_callback(call, 
        _section_header(
            "🌐 Инфраструктура",
            "Управление панелями, нодами, inbound'ами, хостами и группами серверов.",
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
            "📈 Мониторинг",
            "Трафик, состояние клиентов в сети, здоровье системы и журналы.",
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
            f"📡 Inbound'ы\n\nОшибка 3x-ui: {exc}",
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
        "admin:coming:plans": ("💎 Тарифы", "admin:plans"),
        "admin:coming:hosts": ("🌐 Хосты", "admin:hosts"),
        "admin:coming:servergroups": ("🗂 Группы серверов", "admin:servergroups"),
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
        "admin:coming:traffic": ("📊 Трафик", "admin:traffic"),
        "admin:coming:online": ("🟢 В сети", "admin:online"),
        "admin:coming:jobs": ("⚙️ Задания", "admin:jobs"),
        "admin:coming:audit": ("🧾 Журнал аудита", "admin:audit"),
        "admin:coming:payments": ("💳 Платежи", "admin:payments"),
        "admin:coming:promo": ("🎟 Промокоды", "admin:promo"),
        "admin:coming:administrators": ("👮 Администраторы", "admin:administrators"),
        "admin:coming:settings": ("🔧 Настройки", "admin:settings"),
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
        "Раздел «Журналы» уже доступен в текущей версии.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📜 Журналы", callback_data="admin:logs")
        ]]),
    )
    await call.answer()


COMING_SOON = {
    "payments": ("💳 Платежи", "Раздел «Платежи» уже доступен."),
    "promo": ("🎟 Промокоды", "Раздел «Промокоды» уже доступен."),
    "panels": ("🖥 Панели", "Раздел панелей зарезервирован. Текущий Master продолжает работать без изменений."),
    "traffic": ("📊 Трафик", "Агрегация трафика будет добавлена на этапе «Мониторинг»."),
    "online": ("🟢 В сети", "Клиенты в сети будут добавлены на этапе «Мониторинг»."),
    "jobs": ("⚙️ Задания", "Планировщик и история фоновых задач будут добавлены отдельно."),
    "audit": ("🧾 Журнал аудита", "Аудит административных действий будет добавлен отдельным модулем."),
    "administrators": ("👮 Администраторы", "Раздел «Администраторы» уже доступен."),
    "settings": ("🔧 Настройки", "Раздел безопасных runtime-настроек уже доступен."),
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
    await render_callback(call, "⚙️ Панель администратора", reply_markup=admin_menu())
    await call.answer()
