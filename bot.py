import asyncio
import logging
import secrets
import shutil
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit

import aiohttp

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile

from backup_manager import BackupManager
from config import load_settings
from db import Database, UserRecord
from xui import XUIClient, XUIError, NodeInfo
from system_backup import SystemBackupService
from subscription_proxy import SubscriptionProxy
from catalog_admin import catalog_router
from admin_observability import observability_router
from business_admin import business_router
from advanced_users import advanced_users_router
from inbound_admin import inbound_admin_router, inbound_list_view
from admin_auth import authorize_callback, authorize_message, get_admin_role
from audit import audit_from_call, audit_system
from runtime_jobs import backup_lock

settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
router = Router()
backup_manager = BackupManager(settings.db_path, settings.backup_dir, settings.backup_keep)
system_backup = SystemBackupService(backup_manager, settings.node_backup_targets)


class AddNodeStates(StatesGroup):
    name = State()
    url = State()
    token = State()
    review = State()


def is_allowed(tg_id: int) -> bool:
    return tg_id in settings.allowed_telegram_ids or tg_id in settings.admin_telegram_ids

def is_admin(tg_id: int) -> bool:
    return tg_id in settings.admin_telegram_ids

def user_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Проверить inbound'ы", callback_data="inbounds")],
        [InlineKeyboardButton(text="Создать тестовый доступ", callback_data="create")],
        [InlineKeyboardButton(text="Моя подписка", callback_data="subscription")],
    ])

def admin_menu() -> InlineKeyboardMarkup:
    """Production admin navigation.

    Existing operational callbacks remain unchanged; v3.8 only places them under
    stable top-level sections so later releases can fill the remaining modules
    without reshuffling the working actions again.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Dashboard", callback_data="admin:dashboard")],
        [
            InlineKeyboardButton(text="👥 Users", callback_data="admin:users"),
            InlineKeyboardButton(text="🔗 Subscriptions", callback_data="admin:subscriptions"),
        ],
        [
            InlineKeyboardButton(text="💳 Payments", callback_data="admin:payments"),
            InlineKeyboardButton(text="💎 Plans", callback_data="admin:plans"),
        ],
        [
            InlineKeyboardButton(text="🎟 Promo Codes", callback_data="admin:promo"),
            InlineKeyboardButton(text="🌐 Infrastructure", callback_data="admin:section:infrastructure"),
        ],
        [
            InlineKeyboardButton(text="📈 Monitoring", callback_data="admin:section:monitoring"),
            InlineKeyboardButton(text="⚙️ System", callback_data="admin:section:system"),
        ],
    ])


def infrastructure_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🖥 Panels", callback_data="admin:coming:panels"),
            InlineKeyboardButton(text="🌍 Nodes", callback_data="admin:nodes"),
        ],
        [
            InlineKeyboardButton(text="📡 Inbounds", callback_data="admin:infra:inbounds"),
            InlineKeyboardButton(text="🌐 Hosts", callback_data="admin:hosts"),
        ],
        [InlineKeyboardButton(text="🗂 Server Groups", callback_data="admin:servergroups")],
        [InlineKeyboardButton(text="⬅ Dashboard", callback_data="admin:home")],
    ])


def monitoring_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Traffic", callback_data="admin:traffic"),
            InlineKeyboardButton(text="🟢 Online", callback_data="admin:online"),
        ],
        [InlineKeyboardButton(text="🩺 System Health", callback_data="admin:health")],
        [InlineKeyboardButton(text="📜 Logs", callback_data="admin:coming:logs")],
        [InlineKeyboardButton(text="⬅ Dashboard", callback_data="admin:home")],
    ])


def system_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚙️ Jobs", callback_data="admin:jobs"),
            InlineKeyboardButton(text="💾 Backups", callback_data="admin:backups"),
        ],
        [InlineKeyboardButton(text="🧾 Audit Log", callback_data="admin:audit")],
        [InlineKeyboardButton(text="👮 Administrators", callback_data="admin:administrators")],
        [InlineKeyboardButton(text="🔧 Settings", callback_data="admin:settings")],
        [InlineKeyboardButton(text="⬅ Dashboard", callback_data="admin:home")],
    ])

def user_admin_keyboard(tg_id: int, enabled: bool = True) -> InlineKeyboardMarkup:
    state_btn = (
        InlineKeyboardButton(text="⛔ Отключить", callback_data=f"admindisable:{tg_id}")
        if enabled else
        InlineKeyboardButton(text="✅ Включить", callback_data=f"adminenable:{tg_id}")
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Расширенное управление", callback_data=f"admin:u:{tg_id}")],
        [InlineKeyboardButton(text="🔗 Подписка", callback_data=f"adminsub:{tg_id}")],
        [InlineKeyboardButton(text="🔄 Синхронизировать inbound'ы", callback_data=f"adminsync:{tg_id}")],
        [InlineKeyboardButton(text="➕ +30 дней", callback_data=f"adminextend:{tg_id}")],
        [state_btn],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admindelask:{tg_id}")],
        [InlineKeyboardButton(text="⬅ Пользователи", callback_data="admin:users")],
    ])

def confirm_delete_keyboard(tg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Да, удалить", callback_data=f"admindel:{tg_id}")],
        [InlineKeyboardButton(text="Отмена", callback_data=f"adminuser:{tg_id}")],
    ])

def confirm_sync_all_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Синхронизировать всех", callback_data="admin:syncall:run")],
        [InlineKeyboardButton(text="Отмена", callback_data="admin:home")],
    ])


def backup_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Создать сейчас", callback_data="admin:backup:create")],
        [InlineKeyboardButton(text="📥 Скачать bot.sqlite3", callback_data="admin:backup:botdb")],
        [InlineKeyboardButton(text="📦 Скачать полный backup", callback_data="admin:backup:full")],
        [InlineKeyboardButton(text="⬅ System", callback_data="admin:section:system")],
    ])

def _node_status_icon(node: NodeInfo) -> str:
    if not node.enable:
        return "⚪"
    if node.status == "online":
        return "🟢"
    if node.status == "offline":
        return "🔴"
    return "🟡"


def _xray_icon(node: NodeInfo) -> str:
    state = node.xray_state.lower()
    if state in {"running", "started", "online"}:
        return "🟢"
    if state in {"stopped", "failed", "error"}:
        return "🔴"
    return "🟡"


def _duration_text(seconds: int) -> str:
    seconds = max(0, int(seconds or 0))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days}д {hours}ч {minutes}м"
    return f"{hours}ч {minutes}м"


def _epoch_text(seconds: int) -> str:
    if not seconds:
        return "никогда"
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except (OSError, OverflowError, ValueError):
        return str(seconds)


def _node_display_name(name: str) -> str:
    value = (name or "Node").strip()
    lower = value.lower()
    if value.startswith(("🇫🇮", "🇳🇱", "🇩🇪", "🇸🇪", "🇳🇴", "🇫🇷", "🇬🇧", "🇺🇸")):
        return value
    country_flags = {
        "finland": "🇫🇮",
        "finnish": "🇫🇮",
        "netherlands": "🇳🇱",
        "germany": "🇩🇪",
        "sweden": "🇸🇪",
        "norway": "🇳🇴",
        "france": "🇫🇷",
        "uk": "🇬🇧",
        "united kingdom": "🇬🇧",
        "usa": "🇺🇸",
        "united states": "🇺🇸",
    }
    flag = country_flags.get(lower)
    return f"{flag} {value}" if flag else value


def _parse_node_url(raw: str) -> dict[str, object]:
    value = (raw or "").strip()
    if not value:
        raise ValueError("URL пустой")
    if "://" not in value:
        value = "https://" + value
    parsed = urlsplit(value)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError("схема должна быть http или https")
    if parsed.username or parsed.password:
        raise ValueError("логин/пароль в URL не поддерживаются")
    if not parsed.hostname:
        raise ValueError("не найден адрес сервера")
    try:
        port = parsed.port or (443 if scheme == "https" else 80)
    except ValueError as exc:
        raise ValueError("некорректный порт") from exc
    base_path = parsed.path or "/"
    if not base_path.startswith("/"):
        base_path = "/" + base_path
    # A copied browser URL normally ends in /panel/.  The node API expects
    # the web base path before that route, because the master appends
    # /panel/api/... itself.
    stripped = base_path.rstrip("/")
    if stripped.lower().endswith("/panel"):
        stripped = stripped[:-len("/panel")]
        base_path = stripped or "/"
    if not base_path.endswith("/"):
        base_path += "/"
    return {
        "scheme": scheme,
        "address": parsed.hostname,
        "port": int(port),
        "basePath": base_path,
    }


def _node_mutation_payload(data: dict[str, object]) -> dict[str, object]:
    return {
        "id": 0,
        "name": str(data["name"]),
        "remark": "",
        "scheme": str(data["scheme"]),
        "address": str(data["address"]),
        "port": int(data["port"]),
        "basePath": str(data["basePath"]),
        "apiToken": str(data["apiToken"]),
        "clearApiToken": False,
        "enable": True,
        "allowPrivateAddress": False,
        "inboundSyncMode": "all",
        "inboundTags": [],
        "outboundTag": "",
        "pinnedCertSha256": "",
        "tlsVerifyMode": str(data.get("tlsVerifyMode") or "verify"),
    }


def add_node_tls_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Проверять TLS", callback_data="admin:nodeadd:tls:verify")],
        [InlineKeyboardButton(text="⚠️ Не проверять TLS", callback_data="admin:nodeadd:tls:skip")],
        [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:nodeadd:cancel")],
    ])


def add_node_review_keyboard(tls_mode: str) -> InlineKeyboardMarkup:
    other = "skip" if tls_mode == "verify" else "verify"
    other_label = "⚠️ TLS без проверки" if other == "skip" else "✅ Проверять TLS"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Добавить ноду", callback_data="admin:nodeadd:save")],
        [InlineKeyboardButton(text="🔍 Проверить ещё раз", callback_data="admin:nodeadd:test")],
        [InlineKeyboardButton(text=other_label, callback_data=f"admin:nodeadd:tls:{other}")],
        [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:nodeadd:cancel")],
    ])


def add_node_retry_keyboard(tls_mode: str) -> InlineKeyboardMarkup:
    other = "skip" if tls_mode == "verify" else "verify"
    other_label = "⚠️ Попробовать без проверки TLS" if other == "skip" else "✅ Включить проверку TLS"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Проверить ещё раз", callback_data="admin:nodeadd:test")],
        [InlineKeyboardButton(text=other_label, callback_data=f"admin:nodeadd:tls:{other}")],
        [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:nodeadd:cancel")],
    ])


def nodes_menu(nodes: list[NodeInfo], master_online: bool = True) -> InlineKeyboardMarkup:
    master_icon = "🟢" if master_online else "🔴"
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(
            text=f"{settings.master_flag} {settings.master_name} · {master_icon} {'Online' if master_online else 'Offline'}",
            callback_data="admin:master",
        )]
    ]
    for node in nodes[:40]:
        suffix = " ↳" if node.transitive else ""
        text = f"{_node_status_icon(node)} {_node_display_name(node.name)}{suffix}"
        if node.id > 0 and not node.transitive:
            rows.append([InlineKeyboardButton(text=text, callback_data=f"admin:node:{node.id}")])
        else:
            rows.append([InlineKeyboardButton(text=text, callback_data="admin:nodes:noop")])
    rows.append([InlineKeyboardButton(text="➕ Добавить ноду", callback_data="admin:nodeadd:start")])
    rows.append([InlineKeyboardButton(text="🔄 Проверить все", callback_data="admin:nodes:refresh")])
    rows.append([InlineKeyboardButton(text="⬅ Infrastructure", callback_data="admin:section:infrastructure")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def master_detail_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Проверить", callback_data="admin:master")],
        [InlineKeyboardButton(text="⬅ Ноды", callback_data="admin:nodes")],
    ])


def node_detail_keyboard(node_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Проверить", callback_data=f"admin:node:{node_id}")],
        [InlineKeyboardButton(text="⬅ Ноды", callback_data="admin:nodes")],
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
    exact_ids = set(settings.inbound_ids)
    if i.protocol in set(settings.ignored_protocols):
        return False
    if i.tag.lower() in set(settings.ignored_tags) or i.tag.lower().startswith("api"):
        return False
    if exact_ids and i.id not in exact_ids:
        return False
    if settings.allowed_ports and i.port not in set(settings.allowed_ports):
        return False
    if settings.allowed_protocols and i.protocol not in set(settings.allowed_protocols):
        return False
    return True

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
    await message.answer("3x-ui Telegram bot v4.3.0", reply_markup=user_menu())

@router.message(Command("admin"))
async def admin(message: Message):
    if not message.from_user:
        return
    role = await get_admin_role(db, settings, message.from_user.id)
    if role is None:
        await message.answer("Команда доступна только администратору.")
        return
    await message.answer(f"⚙️ Admin Panel · {role}", reply_markup=admin_menu())

def _section_header(title: str, subtitle: str) -> str:
    return f"{title}\n\n{subtitle}"


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
    enabled_hosts = sum(1 for h in hosts if h.enabled)
    payment_summary = await db.payment_summary()
    promo_codes = await db.list_promo_codes()
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
    lines += [
        "",
        "System",
        f"💾 Last backup: {backup_text}",
    ]

    await call.message.answer("\n".join(lines), reply_markup=admin_menu())
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
    await call.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data == "admin:section:infrastructure")
async def admin_infrastructure(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    await call.message.answer(
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
    await call.message.answer(
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
    await call.message.answer(
        _section_header(
            "⚙️ System",
            "Фоновые задачи, backups, аудит, администраторы и настройки.",
        ),
        reply_markup=system_menu(),
    )
    await call.answer()


@router.callback_query(F.data == "admin:infra:inbounds")
async def admin_infrastructure_inbounds(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    try:
        text, kb = await inbound_list_view()
        await call.message.answer(text, reply_markup=kb)
    except XUIError as exc:
        await call.message.answer(
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
    await call.message.answer(
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
    await call.message.answer(
        "Этот раздел уже доступен в текущей версии.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=target[0], callback_data=target[1])
        ]]),
    )
    await call.answer()


COMING_SOON = {
    "payments": ("💳 Payments", "Раздел Payments уже доступен."),
    "promo": ("🎟 Promo Codes", "Раздел Promo Codes уже доступен."),
    "panels": ("🖥 Panels", "Раздел панелей зарезервирован. Текущий Master продолжает работать без изменений."),
    "traffic": ("📊 Traffic", "Агрегация трафика будет добавлена на этапе Monitoring."),
    "online": ("🟢 Online", "Online-клиенты будут добавлены на этапе Monitoring."),
    "logs": ("📜 Logs", "Просмотр журналов будет добавлен без изменения текущего Docker logging."),
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
    await call.message.answer(f"{title}\n\n{body}", reply_markup=back)
    await call.answer()


@router.callback_query(F.data == "admin:users")
async def admin_users(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    users = await db.list_users()
    rows = []
    for u in users[:40]:
        rows.append([InlineKeyboardButton(
            text=f"👤 {u.email} | TG {u.telegram_id}",
            callback_data=f"adminuser:{u.telegram_id}"
        )])
    rows.append([InlineKeyboardButton(text="☑️ Массовые действия", callback_data="admin:users:bulk")])
    rows.append([InlineKeyboardButton(text="🔄 Синхронизировать всех", callback_data="admin:syncall:ask")])
    rows.append([InlineKeyboardButton(text="📊 Статистика пользователей", callback_data="admin:stats")])
    rows.append([InlineKeyboardButton(text="⬅ Dashboard", callback_data="admin:home")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await call.message.answer(f"👥 Users\n\nПользователи в БД бота: {len(users)}", reply_markup=kb)
    await call.answer()

@router.callback_query(F.data == "admin:syncall:ask")
async def admin_sync_all_ask(call: CallbackQuery):
    if not await guard_admin_call(call):
        return

    users = await db.list_users()
    try:
        available = choose_inbounds(await xui.inbound_options())
        target_ids = sorted({i.id for i in available})
    except XUIError as e:
        await call.message.answer(f"Ошибка 3x-ui: {e}", reply_markup=admin_menu())
        await call.answer()
        return

    if not users:
        await call.message.answer("В локальной БД нет пользователей.", reply_markup=admin_menu())
        await call.answer()
        return
    if not target_ids:
        await call.message.answer(
            "После фильтрации в .env нет доступных inbound'ов. "
            "Проверь ALLOWED_PORTS, ALLOWED_PROTOCOLS и INBOUND_IDS.",
            reply_markup=admin_menu(),
        )
        await call.answer()
        return

    flow_note = settings.vless_flow or "не менять"
    await call.message.answer(
        "Глобальная синхронизация добавит всем пользователям из локальной БД "
        "все разрешённые inbound'ы, которых у них ещё нет, и синхронизирует VLESS flow.\n\n"
        f"Пользователей: {len(users)}\n"
        f"Целевые inbound ID: {', '.join(map(str, target_ids))}\n"
        f"VLESS flow: {flow_note}",
        reply_markup=confirm_sync_all_keyboard(),
    )
    await call.answer()


@router.callback_query(F.data == "admin:syncall:run")
async def admin_sync_all_run(call: CallbackQuery):
    if not await guard_admin_call(call):
        return

    users = await db.list_users()
    if not users:
        await call.message.answer("В локальной БД нет пользователей.", reply_markup=admin_menu())
        await call.answer()
        return

    try:
        available = choose_inbounds(await xui.inbound_options())
        target_ids = sorted({i.id for i in available})
        if not target_ids:
            await call.message.answer(
                "Нет разрешённых inbound'ов после фильтрации .env.",
                reply_markup=admin_menu(),
            )
            await call.answer()
            return

        emails = [u.email for u in users]
        result = await xui.bulk_attach_clients(emails, target_ids)
        obj = result.get("obj") or {}

        flow_result = None
        if settings.vless_flow:
            flow_result = await xui.bulk_adjust_clients(
                emails,
                flow=settings.vless_flow,
            )

        attached = obj.get("attached") or {}
        skipped = obj.get("skipped") or {}
        errors = obj.get("errors") or {}

        def count_entries(value):
            if isinstance(value, dict):
                return len(value)
            if isinstance(value, list):
                return len(value)
            return 0

        attached_count = count_entries(attached)
        skipped_count = count_entries(skipped)
        error_count = count_entries(errors)

        # Fallback summary for older response shapes.
        if attached_count == skipped_count == error_count == 0:
            attached_count = len(users)

        lines = [
            "✅ Глобальная синхронизация завершена.",
            "",
            f"Пользователей в БД: {len(users)}",
            f"Целевые inbound ID: {', '.join(map(str, target_ids))}",
            f"Обновлено/обработано: {attached_count}",
            f"Уже было привязано: {skipped_count}",
            f"Ошибок: {error_count}",
        ]
        if settings.vless_flow:
            lines.append(f"VLESS flow: {settings.vless_flow}")
            if flow_result is not None:
                flow_obj = flow_result.get("obj") or {}
                adjusted = flow_obj.get("adjusted")
                if adjusted is not None:
                    lines.append(f"Flow обработано: {adjusted}")

        if errors:
            preview = []
            if isinstance(errors, dict):
                for email, value in list(errors.items())[:10]:
                    preview.append(f"• {email}: {value}")
            elif isinstance(errors, list):
                preview = [f"• {x}" for x in errors[:10]]
            if preview:
                lines += ["", "Первые ошибки:"] + preview

        await call.message.answer("\n".join(lines), reply_markup=admin_menu())
        await audit_from_call(
            db, call, "users.sync_all", target_type="users", target_id=str(len(users)),
            details=f"inbounds={target_ids}; errors={error_count}; flow={settings.vless_flow or 'unchanged'}",
            success=(error_count == 0),
        )
    except XUIError as e:
        await audit_from_call(
            db, call, "users.sync_all", target_type="users", target_id=str(len(users)),
            details=f"3x-ui error: {e}", success=False,
        )
        await call.message.answer(
            "Не удалось выполнить глобальную синхронизацию.\n\n"
            f"Ошибка 3x-ui: {e}",
            reply_markup=admin_menu(),
        )

    await call.answer()


@router.callback_query(F.data == "admin:stats")
async def admin_stats(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    users = await db.list_users()
    now_ms = int(time.time() * 1000)
    active = sum(1 for u in users if not u.expiry_time or u.expiry_time > now_ms)
    soon = sum(1 for u in users if u.expiry_time and now_ms < u.expiry_time <= now_ms + 3*86400*1000)
    await call.message.answer(
        f"📊 Локальная БД\n\nВсего: {len(users)}\n"
        f"Не истекли: {active}\nИстекают за 3 дня: {soon}",
        reply_markup=admin_menu()
    )
    await call.answer()

def _public_health_url() -> str | None:
    template = settings.compat_subscription_url_template.strip()
    if not template:
        return None
    try:
        parts = urlsplit(template.format(sub_id="health-probe"))
    except ValueError:
        return None
    if not parts.scheme or not parts.netloc:
        return None
    return urlunsplit((parts.scheme, parts.netloc, "/healthz", "", ""))


async def _check_http(url: str, *, verify_tls: bool = True) -> tuple[bool, str]:
    timeout = aiohttp.ClientTimeout(total=6)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                url,
                ssl=None if verify_tls else False,
                allow_redirects=True,
            ) as resp:
                body = (await resp.text()).strip()
                if resp.status == 200:
                    return True, body[:80] or "HTTP 200"
                return False, f"HTTP {resp.status}"
    except (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError) as exc:
        return False, type(exc).__name__


def _memory_stats() -> tuple[int, int] | None:
    values: dict[str, int] = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as fh:
            for line in fh:
                key, raw = line.split(":", 1)
                if key in {"MemTotal", "MemAvailable"}:
                    values[key] = int(raw.strip().split()[0]) * 1024
    except (OSError, ValueError):
        return None
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    if not total:
        return None
    return total - available, total


def _uptime_text() -> str | None:
    try:
        seconds = int(float(open("/proc/uptime", "r", encoding="utf-8").read().split()[0]))
    except (OSError, ValueError, IndexError):
        return None
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days}д {hours}ч {minutes}м"
    return f"{hours}ч {minutes}м"


def _usage_line(label: str, used: int, total: int) -> str:
    pct = (used / total * 100) if total else 0
    return f"{label}: {human_bytes(used)} / {human_bytes(total)} ({pct:.0f}%)"


def _backup_status_text() -> str:
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
    names = system_backup.configured_node_names()
    if names:
        lines.append(f"Backup нод: {len(names)} — {', '.join(names)}")
    else:
        lines.append("Backup нод: не настроен")
    lines += ["", "⚠️ Полный архив содержит секреты (.env, x-ui.db и базы нод)."]
    return "\n".join(lines)


@router.callback_query(F.data == "admin:backups")
async def admin_backups(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    await call.message.answer(_backup_status_text(), reply_markup=backup_menu())
    await call.answer()


@router.callback_query(F.data == "admin:backup:create")
async def admin_backup_create(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    if backup_lock.locked():
        await call.answer("Backup уже выполняется.", show_alert=True)
        return
    await call.answer("Создаю backup…")
    run_id = await db.start_job_run(
        name="backup.manual", trigger="admin",
        actor_id=call.from_user.id if call.from_user else 0,
    )
    started = time.monotonic()
    try:
        async with backup_lock:
            result = await system_backup.create_full_backup()
        duration_ms = int((time.monotonic() - started) * 1000)
        await db.finish_job_run(
            run_id, status="success", duration_ms=duration_ms,
            details=f"{result.info.path.name}; {result.info.size} bytes; missing={len(result.missing)}",
        )
        await audit_from_call(
            db, call, "backup.create", target_type="backup",
            target_id=result.info.path.name,
            details=f"size={result.info.size}; missing={len(result.missing)}",
        )
        lines = [
            "✅ Полный backup создан.",
            f"Файл: {result.info.path.name}",
            f"Размер: {human_bytes(result.info.size)}",
            f"Включено: {', '.join(result.included) or 'нет'}",
        ]
        if result.missing:
            lines.append(f"⚠️ Не найдено: {', '.join(result.missing)}")
        await call.message.answer("\n".join(lines), reply_markup=backup_menu())
    except Exception as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        await db.finish_job_run(
            run_id, status="failed", duration_ms=duration_ms,
            details=f"{type(exc).__name__}: {exc}",
        )
        await audit_from_call(
            db, call, "backup.create", target_type="backup",
            details=f"{type(exc).__name__}: {exc}", success=False,
        )
        logging.exception("Manual backup failed")
        await call.message.answer(
            f"🔴 Не удалось создать backup: {type(exc).__name__}: {exc}",
            reply_markup=backup_menu(),
        )


@router.callback_query(F.data == "admin:backup:botdb")
async def admin_backup_botdb(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    await call.answer("Готовлю SQLite…")
    try:
        path = await asyncio.to_thread(backup_manager.create_bot_snapshot)
        await call.message.answer_document(
            FSInputFile(path),
            caption="Свежая консистентная копия bot.sqlite3",
        )
        await audit_from_call(
            db, call, "backup.download", target_type="bot.sqlite3",
            target_id=path.name, details="consistent SQLite snapshot",
        )
    except Exception as exc:
        await audit_from_call(
            db, call, "backup.download", target_type="bot.sqlite3",
            details=f"{type(exc).__name__}: {exc}", success=False,
        )
        logging.exception("Bot DB snapshot failed")
        await call.message.answer(f"🔴 Ошибка backup SQLite: {type(exc).__name__}: {exc}")


@router.callback_query(F.data == "admin:backup:full")
async def admin_backup_full(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    await call.answer("Готовлю архив…")
    try:
        info = await asyncio.to_thread(backup_manager.latest_backup)
        if info is None:
            if backup_lock.locked():
                await call.message.answer("Backup уже создаётся. Повтори скачивание чуть позже.")
                return
            async with backup_lock:
                result = await system_backup.create_full_backup()
            info = result.info
        await call.message.answer_document(
            FSInputFile(info.path),
            caption=(
                "Полный backup. Содержит секреты; храните файл в защищённом месте.\n"
                f"Создан: {info.created_at.strftime('%Y-%m-%d %H:%M UTC')}"
            ),
        )
        await audit_from_call(
            db, call, "backup.download", target_type="full", target_id=info.path.name,
            details=f"size={info.size}",
        )
    except Exception as exc:
        await audit_from_call(
            db, call, "backup.download", target_type="full",
            details=f"{type(exc).__name__}: {exc}", success=False,
        )
        logging.exception("Full backup download failed")
        await call.message.answer(f"🔴 Ошибка отправки backup: {type(exc).__name__}: {exc}")


def _node_detail_text(node: NodeInfo) -> str:
    status_icon = _node_status_icon(node)
    xray_icon = _xray_icon(node)
    lines = [
        f"🌍 {_node_display_name(node.name)}",
        "",
        f"{status_icon} Panel: {node.status}",
        f"{xray_icon} Xray: {node.xray_state}"
        + (f" {node.xray_version}" if node.xray_version else ""),
    ]
    if node.panel_version:
        lines.append(f"3x-ui: {node.panel_version}")
    if node.latency_ms:
        lines.append(f"Ping API: {node.latency_ms} ms")
    lines += [
        f"CPU: {node.cpu_pct:.1f}%",
        f"RAM: {node.mem_pct:.1f}%",
        f"Uptime: {_duration_text(node.uptime_secs)}",
        f"Inbound'ов: {node.inbound_count}",
        f"Клиентов: {node.client_count} · active {node.active_count} · online {node.online_count}",
        f"Последний heartbeat: {_epoch_text(node.last_heartbeat)}",
    ]
    if node.config_dirty:
        lines.append("🟡 Конфигурация ожидает синхронизации")
    if node.last_error:
        lines.append(f"⚠️ Node error: {node.last_error[:240]}")
    if node.xray_error:
        lines.append(f"⚠️ Xray error: {node.xray_error[:240]}")
    lines.append(
        "💾 Backup БД: "
        + ("настроен" if system_backup.has_target_for(node.name) else "не настроен")
    )
    if node.transitive:
        lines.append("ℹ️ Транзитная нода: read-only представление через родительскую ноду.")
    return "\n".join(lines)


@router.callback_query(F.data == "admin:nodes")
async def admin_nodes(call: CallbackQuery):
    if not await guard_admin_call(call):
        return

    master_online = False
    master_error = None
    try:
        await xui.server_status()
        master_online = True
    except XUIError as exc:
        master_error = str(exc)

    nodes: list[NodeInfo] = []
    nodes_error = None
    try:
        nodes = await xui.nodes_list()
    except XUIError as exc:
        nodes_error = str(exc)

    online = (1 if master_online else 0) + sum(
        1 for n in nodes if n.enable and n.status == "online"
    )
    total = 1 + len(nodes)
    text = f"🌍 Ноды\n\nСерверов: {total} · online: {online}"
    if not nodes and not nodes_error:
        text += (
            "\n\nПока зарегистрированных нод нет. "
            "Используй «➕ Добавить ноду», чтобы подключить сервер."
        )
    if master_error:
        text += f"\n\n⚠️ Master: {master_error[:180]}"
    if nodes_error:
        text += f"\n⚠️ Nodes API: {nodes_error[:180]}"

    await call.message.answer(text, reply_markup=nodes_menu(nodes, master_online))
    await call.answer()




@router.callback_query(F.data == "admin:nodeadd:start")
async def admin_node_add_start(call: CallbackQuery, state: FSMContext):
    if not await guard_admin_call(call):
        return
    await state.clear()
    await state.set_state(AddNodeStates.name)
    await call.message.answer(
        "➕ Добавление ноды\n\n"
        "Шаг 1/4. Отправь имя ноды.\n"
        "Например: Finland",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:nodeadd:cancel")]
        ]),
    )
    await call.answer()


@router.message(AddNodeStates.name)
async def admin_node_add_name(message: Message, state: FSMContext):
    if not message.from_user:
        return
    ok, _ = await authorize_message(db, settings, message.from_user.id, minimum="admin")
    if not ok:
        await state.clear()
        await message.answer("Недостаточно прав.")
        return
    name = (message.text or "").strip()
    if not name or len(name) > 64:
        await message.answer("Имя должно содержать от 1 до 64 символов.")
        return
    await state.update_data(name=name)
    await state.set_state(AddNodeStates.url)
    await message.answer(
        "Шаг 2/4. Отправь URL панели 3x-ui на ноде.\n\n"
        "Можно целиком, например:\n"
        "https://fi.example.com:2053/my-base/panel/\n\n"
        "Можно вставить URL прямо из браузера: завершающий /panel/ будет убран автоматически. "
        "Если схема не указана, будет использован https."
    )


@router.message(AddNodeStates.url)
async def admin_node_add_url(message: Message, state: FSMContext):
    if not message.from_user:
        return
    ok, _ = await authorize_message(db, settings, message.from_user.id, minimum="admin")
    if not ok:
        await state.clear()
        await message.answer("Недостаточно прав.")
        return
    try:
        parsed = _parse_node_url(message.text or "")
    except ValueError as exc:
        await message.answer(f"Не удалось разобрать URL: {exc}\nПопробуй ещё раз.")
        return
    await state.update_data(**parsed)
    await state.set_state(AddNodeStates.token)
    await message.answer(
        "Шаг 3/4. Отправь API token этой ноды.\n\n"
        "Токен 3x-ui является полным административным секретом. "
        "Сообщение с токеном бот попробует удалить сразу после получения."
    )


@router.message(AddNodeStates.token)
async def admin_node_add_token(message: Message, state: FSMContext):
    if not message.from_user:
        return
    ok, _ = await authorize_message(db, settings, message.from_user.id, minimum="admin")
    if not ok:
        await state.clear()
        await message.answer("Недостаточно прав.")
        return
    token = (message.text or "").strip()
    if len(token) < 8:
        await message.answer("Токен выглядит слишком коротким. Отправь API token ноды ещё раз.")
        return
    await state.update_data(apiToken=token)
    try:
        await message.delete()
    except Exception:
        pass
    await state.set_state(AddNodeStates.review)
    await message.answer(
        "Шаг 4/4. Как проверять TLS-сертификат ноды?\n\n"
        "Рекомендуется «Проверять TLS». Режим без проверки нужен только для "
        "временного теста или собственного сертификата.",
        reply_markup=add_node_tls_keyboard(),
    )


async def _node_add_test_and_show(call: CallbackQuery, state: FSMContext, tls_mode: str | None = None):
    data = await state.get_data()
    if not data.get("apiToken"):
        await state.clear()
        await call.message.answer("Сессия добавления ноды истекла. Начни добавление заново.", reply_markup=admin_menu())
        return
    if tls_mode:
        await state.update_data(tlsVerifyMode=tls_mode)
        data["tlsVerifyMode"] = tls_mode
    data.setdefault("tlsVerifyMode", "verify")
    payload = _node_mutation_payload(data)
    try:
        result = await xui.node_test(payload)
    except XUIError as exc:
        mode = str(data.get("tlsVerifyMode") or "verify")
        await call.message.answer(
            "🔴 Проверка ноды не прошла.\n\n"
            f"{str(exc)[:500]}\n\n"
            "Проверь URL/API token. Если на ноде собственный TLS-сертификат, "
            "можно временно попробовать режим без проверки.",
            reply_markup=add_node_retry_keyboard(mode),
        )
        return

    mode = str(data.get("tlsVerifyMode") or "verify")
    status = str(result.get("status") or "unknown").lower()
    status_icon = "🟢" if status == "online" else "🟡"
    lines = [
        "🔍 Проверка ноды завершена",
        "",
        f"Имя: {_node_display_name(str(data['name']))}",
        f"Адрес: {data['scheme']}://{data['address']}:{data['port']}{data['basePath']}",
        f"TLS: {mode}",
        f"{status_icon} Panel: {status}",
    ]
    if result.get("panelVersion"):
        lines.append(f"3x-ui: {result['panelVersion']}")
    if result.get("xrayState"):
        lines.append(f"Xray: {result['xrayState']} {result.get('xrayVersion') or ''}".rstrip())
    if result.get("latencyMs") is not None:
        lines.append(f"Ping API: {int(result.get('latencyMs') or 0)} ms")
    if result.get("cpuPct") is not None:
        lines.append(f"CPU: {float(result.get('cpuPct') or 0):.1f}%")
    if result.get("memPct") is not None:
        lines.append(f"RAM: {float(result.get('memPct') or 0):.1f}%")
    if result.get("error"):
        lines.append(f"⚠️ {str(result['error'])[:240]}")
    if result.get("xrayError"):
        lines.append(f"⚠️ Xray: {str(result['xrayError'])[:240]}")
    lines += ["", "Если всё верно, нажми «✅ Добавить ноду». "]
    await call.message.answer("\n".join(lines), reply_markup=add_node_review_keyboard(mode))


@router.callback_query(F.data.startswith("admin:nodeadd:tls:"))
async def admin_node_add_tls(call: CallbackQuery, state: FSMContext):
    if not await guard_admin_call(call):
        return
    mode = call.data.rsplit(":", 1)[-1]
    if mode not in {"verify", "skip"}:
        await call.answer("Некорректный TLS-режим", show_alert=True)
        return
    await call.answer("Проверяю соединение…")
    await _node_add_test_and_show(call, state, mode)


@router.callback_query(F.data == "admin:nodeadd:test")
async def admin_node_add_test(call: CallbackQuery, state: FSMContext):
    if not await guard_admin_call(call):
        return
    await call.answer("Проверяю соединение…")
    await _node_add_test_and_show(call, state)


@router.callback_query(F.data == "admin:nodeadd:save")
async def admin_node_add_save(call: CallbackQuery, state: FSMContext):
    if not await guard_admin_call(call):
        return
    data = await state.get_data()
    if not data.get("apiToken"):
        await state.clear()
        await call.answer("Сессия добавления истекла", show_alert=True)
        return
    payload = _node_mutation_payload(data)
    await call.answer("Добавляю ноду…")
    try:
        node = await xui.node_add(payload)
        try:
            probed = await xui.node_probe(node.id)
            if probed is not None:
                node = probed
        except XUIError:
            pass
    except XUIError as exc:
        await audit_from_call(
            db, call, "node.add", target_type="node",
            target_id=str(data.get("name") or ""),
            details=f"3x-ui error: {exc}", success=False,
        )
        await call.message.answer(
            "🔴 Не удалось добавить ноду.\n\n"
            f"Ошибка 3x-ui: {str(exc)[:500]}",
            reply_markup=add_node_review_keyboard(str(data.get("tlsVerifyMode") or "verify")),
        )
        return

    await audit_from_call(
        db, call, "node.add", target_type="node", target_id=str(node.id),
        details=f"name={node.name}; status={node.status}",
    )
    await state.clear()
    await call.message.answer(
        f"✅ Нода {_node_display_name(node.name)} добавлена.\n"
        f"Статус: {_node_status_icon(node)} {node.status}",
        reply_markup=node_detail_keyboard(node.id),
    )


@router.callback_query(F.data == "admin:nodeadd:cancel")
async def admin_node_add_cancel(call: CallbackQuery, state: FSMContext):
    if not await guard_admin_call(call):
        return
    await state.clear()
    await call.answer("Добавление отменено")
    await call.message.answer("Добавление ноды отменено.", reply_markup=admin_menu())


@router.callback_query(F.data == "admin:master")
async def admin_master_detail(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    await call.answer("Проверяю Master…")

    local_url = f"http://127.0.0.1:{settings.subscription_proxy_port}/healthz"
    public_url = _public_health_url()
    local_task = asyncio.create_task(_check_http(local_url, verify_tls=False))
    public_task = (
        asyncio.create_task(_check_http(public_url, verify_tls=settings.verify_tls))
        if public_url else None
    )

    status = None
    inbounds = None
    api_error = None
    try:
        status = await xui.server_status()
        inbounds = await xui.inbound_options()
    except XUIError as exc:
        api_error = str(exc)

    local_ok, local_detail = await local_task
    if public_task:
        public_ok, public_detail = await public_task
    else:
        public_ok, public_detail = False, "COMPAT URL не настроен"

    lines = [f"{settings.master_flag} {settings.master_name}"]
    lines.append(
        "🟢 Online · 3x-ui API" if status is not None else
        f"🔴 Offline · 3x-ui API — {(api_error or 'unknown error')[:160]}"
    )

    if status:
        xray = status.get("xray") or {}
        xray_state = str(xray.get("state") or "unknown").lower()
        xray_ok = xray_state in {"running", "started", "online"}
        xray_version = str(xray.get("version") or "")
        lines.append(
            f"{'🟢' if xray_ok else '🔴'} Xray: {xray_state}"
            + (f" {xray_version}" if xray_version else "")
        )
        cpu = status.get("cpu")
        if cpu is not None:
            lines.append(f"🧮 CPU: {float(cpu):.1f}%")
        mem = status.get("mem") or {}
        if mem.get("total"):
            lines.append(_usage_line("🧠 RAM", int(mem.get("current") or 0), int(mem["total"])))
        disk = status.get("disk") or {}
        if disk.get("total"):
            lines.append(_usage_line("💽 Disk", int(disk.get("current") or 0), int(disk["total"])))
        if status.get("uptime") is not None:
            lines.append(f"⏱ Uptime: {_duration_text(int(status.get('uptime') or 0))}")

    lines.append(f"{'🟢' if local_ok else '🔴'} Subscription proxy" + ("" if local_ok else f" — {local_detail}"))
    lines.append(f"{'🟢' if public_ok else '🔴'} Public subscription" + ("" if public_ok else f" — {public_detail}"))

    if inbounds is not None:
        managed = [i for i in inbounds if is_managed_inbound(i)]
        enabled = sum(1 for i in managed if i.enable)
        lines.append(f"🌐 Inbound'ы: {enabled}/{len(managed)} включено")

    users = await db.list_users()
    lines.append(f"👥 Пользователей в БД бота: {len(users)}")
    latest = await asyncio.to_thread(backup_manager.latest_backup)
    if latest:
        lines.append(
            "💾 Backup: "
            + latest.created_at.strftime("%Y-%m-%d %H:%M UTC")
            + f" ({human_bytes(latest.size)})"
        )
    else:
        lines.append("⚠️ Backup: ещё не создан")

    await call.message.answer("\n".join(lines), reply_markup=master_detail_keyboard())


@router.callback_query(F.data == "admin:nodes:noop")
async def admin_nodes_noop(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    await call.answer("Транзитная нода отображается только для мониторинга.")


@router.callback_query(F.data == "admin:nodes:refresh")
async def admin_nodes_refresh(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    await call.answer("Проверяю серверы…")

    master_online = False
    try:
        await xui.server_status()
        master_online = True
    except XUIError:
        pass

    try:
        current = await xui.nodes_list()
        direct = [n for n in current if n.id > 0 and not n.transitive]
        if direct:
            await asyncio.gather(
                *(xui.node_probe(n.id) for n in direct),
                return_exceptions=True,
            )
        nodes = await xui.nodes_list()
        online = (1 if master_online else 0) + sum(
            1 for n in nodes if n.enable and n.status == "online"
        )
        await call.message.answer(
            f"🌍 Ноды обновлены\n\nСерверов: {1 + len(nodes)} · online: {online}",
            reply_markup=nodes_menu(nodes, master_online),
        )
    except XUIError as exc:
        await call.message.answer(
            f"🌍 Ноды обновлены\n\n"
            f"{settings.master_flag} {settings.master_name}: "
            f"{'🟢 Online' if master_online else '🔴 Offline'}\n"
            f"⚠️ Nodes API: {str(exc)[:180]}",
            reply_markup=nodes_menu([], master_online),
        )


@router.callback_query(F.data.startswith("admin:node:"))
async def admin_node_detail(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    try:
        node_id = int(call.data.rsplit(":", 1)[1])
    except (TypeError, ValueError):
        await call.answer("Некорректный ID ноды", show_alert=True)
        return

    await call.answer("Проверяю ноду…")
    probe_error = None
    try:
        await xui.node_probe(node_id)
    except XUIError as exc:
        probe_error = str(exc)
    try:
        node = await xui.node_get(node_id)
    except XUIError as exc:
        await call.message.answer(f"🔴 Нода недоступна: {exc}", reply_markup=admin_menu())
        return

    text = _node_detail_text(node)
    if probe_error and not node.last_error:
        text += f"\n⚠️ Probe: {probe_error[:240]}"
    await call.message.answer(text, reply_markup=node_detail_keyboard(node_id))


@router.callback_query(F.data == "admin:health")
async def admin_health(call: CallbackQuery):
    if not await guard_admin_call(call):
        return

    await call.answer("Проверяю…")

    local_url = f"http://127.0.0.1:{settings.subscription_proxy_port}/healthz"
    public_url = _public_health_url()

    local_task = asyncio.create_task(_check_http(local_url, verify_tls=False))
    public_task = (
        asyncio.create_task(_check_http(public_url, verify_tls=settings.verify_tls))
        if public_url else None
    )

    inbounds = None
    server_status = None
    nodes: list[NodeInfo] = []
    nodes_error = None
    xui_error = None

    try:
        inbounds = await xui.inbound_options()
    except XUIError as exc:
        xui_error = str(exc)

    try:
        server_status = await xui.server_status()
    except XUIError as exc:
        if xui_error is None:
            xui_error = str(exc)

    try:
        nodes = await xui.nodes_list()
    except XUIError as exc:
        nodes_error = str(exc)
        nodes = []

    local_ok, local_detail = await local_task
    if public_task:
        public_ok, public_detail = await public_task
    else:
        public_ok, public_detail = False, "COMPAT URL не настроен"

    users = await db.list_users()
    lines = ["🩺 Состояние системы", "", f"{settings.master_flag} {settings.master_name}"]

    if inbounds is not None or server_status is not None:
        lines.append("🟢 3x-ui API / panel route")
    else:
        detail = (xui_error or "unknown error")[:160]
        lines.append(f"🔴 3x-ui API / panel route — {detail}")

    if server_status:
        xray_status = server_status.get("xray") or {}
        xray_state = str(xray_status.get("state") or "unknown").lower()
        xray_ok = xray_state in {"running", "started", "online"}
        xray_version = str(xray_status.get("version") or "")
        lines.append(
            f"{'🟢' if xray_ok else '🔴'} Xray: {xray_state}"
            + (f" {xray_version}" if xray_version else "")
        )

        awg = server_status.get("amneziawg") or {}
        if awg.get("configured"):
            lines.append(f"{'🟢' if awg.get('running') else '🔴'} AmneziaWG core")

        cpu = server_status.get("cpu")
        if cpu is not None:
            lines.append(f"🧮 CPU: {float(cpu):.1f}%")
        mem = server_status.get("mem") or {}
        if mem.get("total"):
            lines.append(_usage_line("🧠 RAM", int(mem.get("current") or 0), int(mem["total"])))
        disk = server_status.get("disk") or {}
        if disk.get("total"):
            lines.append(_usage_line("💽 Disk", int(disk.get("current") or 0), int(disk["total"])))
        if server_status.get("uptime") is not None:
            lines.append(f"⏱ Uptime: {_duration_text(int(server_status.get('uptime') or 0))}")

    lines.append(
        f"{'🟢' if local_ok else '🔴'} Subscription proxy (локально)"
        + ("" if local_ok else f" — {local_detail}")
    )
    lines.append(
        f"{'🟢' if public_ok else '🔴'} Subscription через nginx/TLS"
        + ("" if public_ok else f" — {public_detail}")
    )

    if inbounds is not None:
        managed = sorted(
            (i for i in inbounds if is_managed_inbound(i)),
            key=lambda i: (i.port, i.protocol, i.id),
        )
        lines += ["", "Inbound'ы master:"]
        if managed:
            for i in managed:
                icon = "🟢" if i.enable else "🔴"
                lines.append(f"{icon} {i.port} {i.protocol.upper()} — {i.remark}")
        else:
            lines.append("⚪ Нет inbound'ов после фильтров .env")

    lines += ["", "Nodes"]
    if nodes_error:
        lines.append(f"🔴 Nodes API — {nodes_error[:180]}")
    elif nodes:
        for node in nodes[:20]:
            icon = _node_status_icon(node)
            xicon = _xray_icon(node)
            node_line = (
                f"{icon} {node.name} · Xray {xicon} · "
                f"CPU {node.cpu_pct:.0f}% · RAM {node.mem_pct:.0f}%"
            )
            if node.latency_ms:
                node_line += f" · {node.latency_ms}ms"
            lines.append(node_line)
            lines.append(
                f"   clients {node.client_count} · online {node.online_count} · "
                f"inbounds {node.inbound_count} · up {_duration_text(node.uptime_secs)}"
            )
        if len(nodes) > 20:
            lines.append(f"… ещё {len(nodes) - 20}")
    else:
        lines.append("⚪ Удалённые ноды не зарегистрированы")

    lines += ["", f"👥 Пользователей в БД бота: {len(users)}"]
    latest_backup = await asyncio.to_thread(backup_manager.latest_backup)
    if latest_backup:
        lines.append(
            "💾 Последний backup: "
            + latest_backup.created_at.strftime("%Y-%m-%d %H:%M UTC")
            + f" ({human_bytes(latest_backup.size)})"
        )
    else:
        lines.append("⚠️ Backup: ещё не создан")

    if settings.node_backup_targets:
        lines.append(f"💾 Backup нод настроен: {len(settings.node_backup_targets)}")
    elif nodes:
        lines.append("⚠️ Backup БД нод: не настроен")

    await call.message.answer("\n".join(lines), reply_markup=monitoring_menu())


@router.callback_query(F.data == "admin:home")
async def admin_home(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    await call.message.answer("⚙️ Admin Panel", reply_markup=admin_menu())
    await call.answer()

@router.callback_query(F.data.startswith("adminuser:"))
async def admin_user(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    tg_id = int(call.data.split(":", 1)[1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    try:
        obj = await xui.get_client(rec.email)
        client = obj.get("client", obj)
        enabled = bool(client.get("enable", True))
        traffic = await xui.traffic(rec.email)
        up = int(traffic.get("up") or traffic.get("uplink") or 0)
        down = int(traffic.get("down") or traffic.get("downlink") or 0)
        total = int(client.get("totalGB") or 0)
        inbound_ids = obj.get("inboundIds") or []
        inbound_text = ", ".join(str(x) for x in inbound_ids) if inbound_ids else "нет"
        flow = str(client.get("flow") or "none")
        text = (
            f"👤 {rec.email}\n"
            f"Telegram ID: {rec.telegram_id}\n"
            f"Статус: {'✅ включён' if enabled else '⛔ отключён'}\n"
            f"Срок: {fmt_date(int(client.get('expiryTime') or rec.expiry_time))}\n"
            f"Лимит: {human_bytes(total) if total else 'без лимита'}\n"
            f"Использовано: {human_bytes(up + down)}\n"
            f"Flow: {flow}\n"
            f"Inbound ID: {inbound_text}\n"
            f"subId: {rec.sub_id}"
        )
    except XUIError as e:
        enabled = True
        text = f"👤 {rec.email}\nTelegram ID: {rec.telegram_id}\n\nОшибка 3x-ui: {e}"
    await call.message.answer(text, reply_markup=user_admin_keyboard(tg_id, enabled))
    await call.answer()

@router.callback_query(F.data.startswith("adminsub:"))
async def admin_sub(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    tg_id = int(call.data.split(":", 1)[1])
    rec = await db.get(tg_id)
    if rec:
        await call.message.answer(f"🔗 {rec.email}\n{sub_url(rec.sub_id)}")
    await call.answer()

@router.callback_query(F.data.startswith("adminsync:"))
async def admin_sync_inbounds(call: CallbackQuery):
    if not await guard_admin_call(call):
        return

    tg_id = int(call.data.split(":", 1)[1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return

    try:
        available = choose_inbounds(await xui.inbound_options())
        target_ids = sorted({i.id for i in available})

        if not target_ids:
            await call.message.answer(
                "После фильтрации в .env нет ни одного доступного inbound. "
                "Проверь ALLOWED_PORTS, ALLOWED_PROTOCOLS и INBOUND_IDS."
            )
            await call.answer()
            return

        obj = await xui.get_client(rec.email)
        current_ids = sorted({int(x) for x in (obj.get("inboundIds") or [])})
        current_set = set(current_ids)
        missing_ids = [x for x in target_ids if x not in current_set]

        if missing_ids:
            await xui.attach_client(rec.email, missing_ids)

        flow_synced = False
        if settings.vless_flow:
            await xui.bulk_adjust_clients(
                [rec.email],
                flow=settings.vless_flow,
            )
            flow_synced = True

        updated = await xui.get_client(rec.email)
        updated_ids = sorted({int(x) for x in (updated.get("inboundIds") or [])})
        updated_client = updated.get("client", updated)
        updated_flow = str(updated_client.get("flow") or "none")

        by_id = {i.id: i for i in available}
        details = []
        for inbound_id in missing_ids:
            i = by_id.get(inbound_id)
            if i:
                details.append(f"• #{i.id} — {i.port}/{i.protocol} — {i.remark}")
            else:
                details.append(f"• #{inbound_id}")

        lines = [f"✅ Синхронизация завершена для {rec.email}.", ""]
        if details:
            lines += ["Добавлены inbound'ы:"] + details + [""]
        else:
            lines += ["Новых inbound'ов не было — все уже привязаны.", ""]
        lines.append(f"Теперь привязан к ID: {', '.join(map(str, updated_ids))}")
        if flow_synced:
            lines.append(f"VLESS flow: {updated_flow}")

        await call.message.answer("\n".join(lines))
        await audit_from_call(
            db, call, "user.sync", target_type="user", target_id=rec.email,
            details=f"added={missing_ids}; inbounds={updated_ids}; flow={updated_flow}",
        )
    except XUIError as e:
        await audit_from_call(
            db, call, "user.sync", target_type="user", target_id=rec.email,
            details=f"3x-ui error: {e}", success=False,
        )
        await call.message.answer(
            "Не удалось синхронизировать inbound'ы/flow.\n\n"
            f"Ошибка 3x-ui: {e}"
        )

    await call.answer()


@router.callback_query(F.data.startswith("adminextend:"))
async def admin_extend(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    tg_id = int(call.data.split(":", 1)[1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Не найден.", show_alert=True)
        return
    try:
        obj = await xui.get_client(rec.email)
        client = obj.get("client", obj)
        current = int(client.get("expiryTime") or 0)
        now_ms = int(time.time() * 1000)
        base = max(current, now_ms)
        new_expiry = base + 30 * 86400 * 1000
        await xui.update_client(rec.email, expiryTime=new_expiry, enable=True)
        await db.update_expiry(tg_id, new_expiry)
        await audit_from_call(
            db, call, "user.extend", target_type="user", target_id=rec.email,
            details=f"+30 days; expiry={new_expiry}",
        )
        await call.message.answer(f"✅ {rec.email} продлён до {fmt_date(new_expiry)}")
    except XUIError as e:
        await audit_from_call(
            db, call, "user.extend", target_type="user", target_id=rec.email,
            details=f"3x-ui error: {e}", success=False,
        )
        await call.message.answer(f"Ошибка 3x-ui: {e}")
    await call.answer()

@router.callback_query(F.data.startswith("admindisable:"))
async def admin_disable(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    tg_id = int(call.data.split(":", 1)[1])
    rec = await db.get(tg_id)
    try:
        await xui.update_client(rec.email, enable=False)
        await audit_from_call(db, call, "user.disable", target_type="user", target_id=rec.email)
        await call.message.answer(f"⛔ {rec.email} отключён.")
    except (XUIError, AttributeError) as e:
        await audit_from_call(
            db, call, "user.disable", target_type="user",
            target_id=rec.email if rec else str(tg_id), details=str(e), success=False,
        )
        await call.message.answer(f"Ошибка: {e}")
    await call.answer()

@router.callback_query(F.data.startswith("adminenable:"))
async def admin_enable(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    tg_id = int(call.data.split(":", 1)[1])
    rec = await db.get(tg_id)
    try:
        await xui.update_client(rec.email, enable=True)
        await audit_from_call(db, call, "user.enable", target_type="user", target_id=rec.email)
        await call.message.answer(f"✅ {rec.email} включён.")
    except (XUIError, AttributeError) as e:
        await audit_from_call(
            db, call, "user.enable", target_type="user",
            target_id=rec.email if rec else str(tg_id), details=str(e), success=False,
        )
        await call.message.answer(f"Ошибка: {e}")
    await call.answer()

@router.callback_query(F.data.startswith("admindelask:"))
async def admin_del_ask(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    tg_id = int(call.data.split(":", 1)[1])
    rec = await db.get(tg_id)
    if rec:
        await call.message.answer(
            f"Удалить {rec.email} из 3x-ui и локальной БД?",
            reply_markup=confirm_delete_keyboard(tg_id)
        )
    await call.answer()

@router.callback_query(F.data.startswith("admindel:"))
async def admin_del(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    tg_id = int(call.data.split(":", 1)[1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Не найден.", show_alert=True)
        return
    try:
        await xui.delete_client(rec.email)
        await db.delete(tg_id)
        await audit_from_call(db, call, "user.delete", target_type="user", target_id=rec.email)
        await call.message.answer(f"🗑 {rec.email} удалён.")
    except XUIError as e:
        await audit_from_call(
            db, call, "user.delete", target_type="user", target_id=rec.email,
            details=f"3x-ui error: {e}", success=False,
        )
        await call.message.answer(f"Ошибка 3x-ui, локальная запись сохранена: {e}")
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

        chosen = choose_inbounds(await xui.inbound_options())
        if not chosen:
            await message.answer("Нет подходящих inbound'ов.")
            return
        now = int(time.time())
        try:
            trial_days = int(await db.get_runtime_setting("trial_days", str(settings.test_days)) or settings.test_days)
            trial_traffic_gb = int(await db.get_runtime_setting("trial_traffic_gb", str(settings.test_traffic_gb)) or settings.test_traffic_gb)
            trial_ip_limit = int(await db.get_runtime_setting("trial_ip_limit", str(settings.test_ip_limit)) or settings.test_ip_limit)
        except (TypeError, ValueError):
            trial_days = settings.test_days
            trial_traffic_gb = settings.test_traffic_gb
            trial_ip_limit = settings.test_ip_limit
        expiry = (now + trial_days * 86400) * 1000
        username = ""
        if getattr(message, "chat", None) and getattr(message.chat, "username", None):
            username = message.chat.username.strip().lower()
        email = f"tg_{username}" if username else f"tg_{tg_id}"
        sid = secrets.token_urlsafe(18)
        await xui.create_client(
            email=email, telegram_id=tg_id, sub_id=sid,
            inbound_ids=[i.id for i in chosen],
            total_bytes=trial_traffic_gb * 1024**3,
            expiry_time_ms=expiry, limit_ip=trial_ip_limit,
            comment="Created by Telegram bot v4.3.0",
            flow=settings.vless_flow,
        )
        # bulkAdjust is capability-aware in current 3x-ui: flow is applied where supported.
        if settings.vless_flow:
            await xui.bulk_adjust_clients([email], flow=settings.vless_flow)
        await db.put(UserRecord(tg_id, email, sid, expiry, now))
        await message.answer(f"✅ Создан\n\n{sub_url(sid)}")
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
    await call.message.answer(sub_url(rec.sub_id) if rec else "Сначала создай доступ.")
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


async def main():
    logging.basicConfig(level=logging.INFO)
    await db.init()
    stale_jobs = await db.fail_stale_job_runs()
    if stale_jobs:
        logging.warning("Marked %d stale job runs as failed", stale_jobs)

    proxy = SubscriptionProxy(
        db=db,
        upstream_template=settings.subscription_url_template,
        public_template=settings.compat_subscription_url_template,
        verify_tls=settings.verify_tls,
        host=settings.subscription_proxy_host,
        port=settings.subscription_proxy_port,
    )
    await proxy.start()

    bot = Bot(settings.bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    dp.include_router(advanced_users_router)
    dp.include_router(inbound_admin_router)
    dp.include_router(catalog_router)
    dp.include_router(observability_router)
    dp.include_router(business_router)
    backup_task = (
        asyncio.create_task(automatic_backup_loop(bot))
        if settings.backup_enabled else None
    )
    try:
        await dp.start_polling(bot)
    finally:
        if backup_task:
            backup_task.cancel()
            try:
                await backup_task
            except asyncio.CancelledError:
                pass
        await proxy.stop()

if __name__ == "__main__":
    asyncio.run(main())
