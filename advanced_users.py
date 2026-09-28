from __future__ import annotations

import asyncio
import secrets
import time
import re
import unicodedata

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_ui import render_callback, render_input
from admin_auth import authorize_callback, authorize_message
from admin_navigation import confirm_delete_keyboard
from inbound_policy import is_managed_inbound as inbound_is_managed
from audit import audit_from_call, audit_from_message
from config import load_settings
from db import Database, UserRecord
from ui_time import end_of_day_timestamp, format_timestamp
from user_ui import display_name_from_profile, user_label
from website_diagnostics import qr_png
from xui import XUIClient, XUIError, XUIMutationError
from provisioning import ProvisioningEngine

settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
advanced_users_router = Router(name="advanced_users")
provisioner = ProvisioningEngine(db, xui, settings)


class EditUserStates(StatesGroup):
    expiry = State()
    traffic = State()
    ip_limit = State()
    note = State()
    display_name = State()


RECONCILE_LABELS = {
    "safe": "Безопасное согласование",
    "strict": "Строгое согласование",
}


def reconcile_text(mode: str) -> str:
    return RECONCILE_LABELS.get(mode, mode)


INBOUND_MODE_LABELS = {
    "all_managed": "все управляемые",
    "selected": "выбранные",
}


def inbound_mode_text(mode: str) -> str:
    return INBOUND_MODE_LABELS.get(mode, mode)


def provisioning_source_text(source: str) -> str:
    if source == "user-profile":
        return "профиль пользователя"
    if source == "legacy-all-managed":
        return "режим совместимости «все управляемые»"
    if source.startswith("plan:"):
        return f"тариф #{source.split(':', 1)[1]}"
    return source


class BulkUserStates(StatesGroup):
    selecting = State()


class UserListStates(StatesGroup):
    search = State()


class CreateUserStates(StatesGroup):
    telegram_id = State()
    email = State()
    display_name = State()
    plan = State()
    review = State()


USER_LIST_PAGE_SIZE = 12


async def guard(call: CallbackQuery, *, minimum: str | None = None) -> bool:
    ok, _ = await authorize_callback(db, settings, call, minimum=minimum)
    return ok


async def guard_message(message: Message, state: FSMContext, *, minimum: str = "support") -> bool:
    if not message.from_user:
        await state.clear()
        return False
    ok, _ = await authorize_message(db, settings, message.from_user.id, minimum=minimum)
    if not ok:
        await state.clear()
        await render_input(message, "Недостаточно прав.")
        return False
    return True


def human_bytes(value: int) -> str:
    n = float(int(value or 0))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"


PAYMENT_STATUS_LABELS = {
    "pending": "🟡 Ожидает",
    "paid": "🟢 Оплачен",
    "refunded": "↩️ Возвращён",
    "cancelled": "⚪ Отменён",
}

USER_AUDIT_LABELS = {
    "user.extend": "⏳ Продлён срок",
    "user.expiry.set": "📅 Изменён срок",
    "user.traffic_limit.set": "📊 Изменён лимит трафика",
    "user.traffic.reset": "♻️ Сброшен трафик",
    "user.ip_limit.set": "📱 Изменён IP limit",
    "user.enable": "✅ Пользователь включён",
    "user.disable": "⛔ Пользователь отключён",
    "user.inbound.toggle": "📡 Изменён Inbound",
    "user.plan.set": "💎 Изменён тариф",
    "user.plan.apply": "💎 Применены параметры тарифа",
    "user.plan.provision": "🚀 Тариф и согласование",
    "user.provision.safe": "🚀 Безопасное согласование",
    "user.provision.strict": "⚠️ Строгое согласование",
    "user.server_group.set": "🗂 Изменена группа серверов",
    "user.subscription.rotate": "🔐 Перевыпущена подписка",
    "user.display_name.set": "✏️ Изменено имя",
    "user.note.set": "📝 Изменена заметка",
    "user.device.delete": "🗑 Удалено устройство",
    "user.create": "➕ Создан пользователь",
    "user.recover": "♻️ Восстановлена запись пользователя",
    "user.delete": "🗑 Удалён пользователь",
}

SENSITIVE_AUDIT_ACTIONS = {"user.subscription.rotate", "user.device.delete"}


def money_text(amount_minor: int, currency: str) -> str:
    amount = int(amount_minor)
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    whole, minor = divmod(amount, 100)
    value = f"{whole}" if minor == 0 else f"{whole}.{minor:02d}"
    return f"{sign}{value} {(currency or '').upper()}".strip()


def audit_summary_text(action: str, details: str) -> str:
    if action in SENSITIVE_AUDIT_ACTIONS:
        return "Подробности скрыты для защиты credentials/device identity."
    value = " ".join((details or "").split())
    return value if len(value) <= 180 else value[:177] + "…"


def fmt_date(ms: int) -> str:
    return format_timestamp(ms, milliseconds=True, empty="без срока")


def sub_url(sub_id: str) -> str:
    template = settings.compat_subscription_url_template or settings.subscription_url_template
    return template.format(sub_id=sub_id)


def is_managed_inbound(i) -> bool:
    return inbound_is_managed(settings, i)


def choose_inbounds(inbounds):
    return [i for i in inbounds if i.enable and is_managed_inbound(i)]


def normalize_display_name(value: str) -> str:
    raw = (value or "").strip()
    if raw == "-":
        return ""
    if not raw:
        raise ValueError("empty")
    if any(unicodedata.category(ch).startswith("C") for ch in raw):
        raise ValueError("control")
    normalized = " ".join(raw.split())
    if not normalized or len(normalized) > 64:
        raise ValueError("length")
    return normalized


def normalize_machine_email(value: str) -> str:
    raw = (value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", raw):
        raise ValueError("machine_email")
    return raw


def _panel_client(item: object) -> dict:
    if not isinstance(item, dict):
        return {}
    client = item.get("client", item)
    return client if isinstance(client, dict) else {}


async def _email_available(email: str) -> tuple[bool, str]:
    if await db.get_by_email(email):
        return False, "Такой технический email уже используется в БД бота."
    try:
        await xui.get_client(email)
    except XUIError as exc:
        if str(exc).startswith("Client not found:"):
            return True, ""
        raise
    return False, "Клиент с таким техническим email уже существует в 3x-ui."


async def _trial_create_values() -> tuple[int, int, int]:
    try:
        days = int(await db.get_runtime_setting("trial_days", str(settings.test_days)) or settings.test_days)
        traffic = int(
            await db.get_runtime_setting("trial_traffic_gb", str(settings.test_traffic_gb))
            or settings.test_traffic_gb
        )
        ip_limit = int(
            await db.get_runtime_setting("trial_ip_limit", str(settings.test_ip_limit))
            or settings.test_ip_limit
        )
    except (TypeError, ValueError):
        days = settings.test_days
        traffic = settings.test_traffic_gb
        ip_limit = settings.test_ip_limit
    return max(0, days), max(0, traffic), max(0, ip_limit)


async def _create_user_context(plan_id: int) -> dict[str, object]:
    if plan_id:
        plan = await db.get_plan(plan_id)
        if not plan or not plan.active:
            raise ValueError("Тариф недоступен.")
        policy = await provisioner.policy_for_plan(plan)
        inbound_ids = list(policy.actionable_inbound_ids)
        if not inbound_ids:
            raise ValueError("Для выбранного тарифа сейчас нет доступных целевых Inbounds.")
        return {
            "plan": plan,
            "plan_name": plan.name,
            "group_name": policy.group.name if policy.group else "не назначена",
            "server_group_id": plan.server_group_id,
            "duration_days": max(0, int(plan.duration_days)),
            "traffic_gb": max(0, int(plan.traffic_gb)),
            "ip_limit": max(0, int(plan.ip_limit)),
            "inbound_ids": inbound_ids,
            "unavailable_members": list(policy.unavailable_members),
        }

    chosen = choose_inbounds(await xui.inbound_options())
    if not chosen:
        raise ValueError("В режиме совместимости сейчас нет доступных управляемых Inbounds.")
    days, traffic, ip_limit = await _trial_create_values()
    return {
        "plan": None,
        "plan_name": "режим совместимости",
        "group_name": "не назначена",
        "server_group_id": None,
        "duration_days": days,
        "traffic_gb": traffic,
        "ip_limit": ip_limit,
        "inbound_ids": [int(item.id) for item in chosen],
        "unavailable_members": [],
    }


async def _create_plan_screen() -> tuple[str, InlineKeyboardMarkup]:
    plans = [plan for plan in await db.list_plans() if plan.active]
    default_plan = await provisioner.default_plan()
    rows: list[list[InlineKeyboardButton]] = []
    for plan in plans[:30]:
        marker = "⭐" if default_plan and plan.id == default_plan.id else "💎"
        rows.append([InlineKeyboardButton(
            text=f"{marker} {plan.name}",
            callback_data=f"admin:users:create:plan:{plan.id}",
        )])
    rows.append([InlineKeyboardButton(
        text="🧩 Режим совместимости",
        callback_data="admin:users:create:plan-compat",
    )])
    rows.append([InlineKeyboardButton(text="✖ Отмена", callback_data="admin:users")])
    text = (
        "💎 Тариф нового пользователя\n\n"
        "Выбери активный тариф. ⭐ отмечает тариф по умолчанию.\n"
        "Режим совместимости использует текущие trial-параметры и все управляемые Inbounds."
    )
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def _create_preview(data: dict[str, object], plan_id: int) -> tuple[str, InlineKeyboardMarkup]:
    ctx = await _create_user_context(plan_id)
    tg_id = int(data["telegram_id"])
    email = str(data["email"])
    display_name = str(data.get("display_name") or "")
    days = int(ctx["duration_days"])
    expiry = int((time.time() + days * 86400) * 1000) if days else 0
    traffic_gb = int(ctx["traffic_gb"])
    ip_limit = int(ctx["ip_limit"])
    inbound_ids = list(ctx["inbound_ids"])
    lines = [
        "➕ Новый пользователь",
        "",
        f"Telegram ID: {tg_id}",
        f"Email: {email}",
        f"Имя: {display_name or '—'}",
        f"Тариф: {ctx['plan_name']}",
        f"Группа серверов: {ctx['group_name']}",
        f"Срок: {fmt_date(expiry)}",
        f"Лимит трафика: {traffic_gb} GB" if traffic_gb else "Лимит трафика: без лимита",
        f"IP limit: {ip_limit}" if ip_limit else "IP limit: без лимита",
        f"Целевые Inbounds: {len(inbound_ids)}",
    ]
    unavailable = list(ctx.get("unavailable_members") or [])
    if unavailable:
        lines.append(f"⏸ Недоступные ноды: {len(unavailable)}")
    rows = [
        [InlineKeyboardButton(text="✅ Создать пользователя", callback_data="admin:users:create:run")],
        [InlineKeyboardButton(text="⬅ Изменить тариф", callback_data="admin:users:create:plans")],
        [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:users")],
    ]
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def back_user(tg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")],
    ])


def users_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Пользователи", callback_data="admin:users")],
    ])


def cancel_edit(tg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:u:{tg_id}")],
    ])


async def _display_label(rec: UserRecord) -> str:
    getter = getattr(db, "get_user_profile", None)
    profile = await getter(rec.telegram_id) if getter else None
    return user_label(rec, profile)


async def _profile_labels(tg_id: int) -> tuple[str, str, str, str]:
    profile = await db.get_user_profile(tg_id)
    plan_name = "не назначен"
    group_name = "не назначена"
    note = ""
    display_name = ""
    if profile:
        if profile.plan_id:
            plan = await db.get_plan(profile.plan_id)
            plan_name = plan.name if plan else f"#{profile.plan_id} (удалён)"
        if profile.server_group_id:
            group = await db.get_server_group(profile.server_group_id)
            group_name = group.name if group else f"#{profile.server_group_id} (удалена)"
        note = profile.note or ""
        display_name = getattr(profile, "display_name", "") or ""
    return plan_name, group_name, note, display_name


def _role_can_support(role: str | None) -> bool:
    return role in {"support", "admin", "owner"}


def _role_can_admin(role: str | None) -> bool:
    return role in {"admin", "owner"}


async def render_user(tg_id: int, role: str | None = "read_only") -> tuple[str, InlineKeyboardMarkup]:
    rec = await db.get(tg_id)
    if not rec:
        return "Пользователь не найден.", InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅ Пользователи", callback_data="admin:users")]
        ])

    plan_name, group_name, note, display_name = await _profile_labels(tg_id)
    provisioning_line = "🚀 Согласование: недоступно"
    enabled: bool | None = None
    try:
        policy = await provisioner.policy_for_user(tg_id)
        pobj = await xui.get_client(rec.email)
        pcurrent = {int(x) for x in (pobj.get("inboundIds") or [])}
        pdesired = set(policy.desired_inbound_ids)
        pmissing = len(pdesired - pcurrent)
        pextra = len((pcurrent & set(policy.managed_inbound_ids)) - pdesired)
        provisioning_line = f"🚀 Согласование: целевых {len(pdesired)} · не хватает {pmissing} · лишних {pextra}"
    except Exception as exc:
        provisioning_line = f"🚀 Согласование: ⚠️ {type(exc).__name__}"

    try:
        obj = await xui.get_client(rec.email)
        client = obj.get("client", obj)
        traffic = await xui.traffic(rec.email)
        up = int(traffic.get("up") or traffic.get("uplink") or 0)
        down = int(traffic.get("down") or traffic.get("downlink") or 0)
        total = int(client.get("totalGB") or 0)
        expiry = int(client.get("expiryTime") or rec.expiry_time or 0)
        limit_ip = int(client.get("limitIp") or 0)
        inbound_ids = sorted({int(x) for x in (obj.get("inboundIds") or [])})
        enabled = bool(client.get("enable", True))
        flow = str(client.get("flow") or "none")
        lines = [
            f"👤 {display_name or rec.email}",
            *([f"Email: {rec.email}"] if display_name else []),
            f"Telegram ID: {rec.telegram_id}",
            f"Статус: {'🟢 включён' if enabled else '⛔ отключён'}",
            "",
            f"💎 Тариф: {plan_name}",
            f"⏳ Срок: {fmt_date(expiry)}",
            f"📊 Трафик: {human_bytes(up + down)} / {human_bytes(total) if total else 'без лимита'}",
            f"🌐 Доступ: {group_name} · Inbounds {len(inbound_ids)}",
            provisioning_line,
            f"📱 Лимит IP: {limit_ip if limit_ip else 'без лимита'} · Flow: {flow}",
        ]
        if note:
            lines += ["", f"📝 Заметка: {note}"]
    except XUIError as exc:
        lines = [
            f"👤 {display_name or rec.email}",
            *([f"Email: {rec.email}"] if display_name else []),
            f"Telegram ID: {rec.telegram_id}",
            "",
            f"💎 Тариф: {plan_name}",
            f"🌐 Доступ: {group_name}",
            provisioning_line,
            "",
            f"⚠️ 3x-ui: {exc}",
        ]
        if note:
            lines += ["", f"📝 Заметка: {note}"]

    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text="💎 Тариф", callback_data=f"admin:u:planview:{tg_id}"),
            InlineKeyboardButton(text="⏳ Продлить", callback_data=f"adminextend:{tg_id}"),
        ],
        [
            InlineKeyboardButton(text="📅 Срок", callback_data=f"admin:u:expiryview:{tg_id}"),
            InlineKeyboardButton(text="📊 Трафик", callback_data=f"admin:u:trafficview:{tg_id}"),
        ],
        [
            InlineKeyboardButton(text="🌐 Доступ", callback_data=f"admin:u:access:{tg_id}"),
            InlineKeyboardButton(text="📱 Подключения", callback_data=f"admin:u:connections:{tg_id}"),
        ],
        [
            InlineKeyboardButton(text="🔗 Подписка", callback_data=f"admin:u:subview:{tg_id}"),
            InlineKeyboardButton(text="💳 Платежи", callback_data=f"admin:u:payments:{tg_id}"),
        ],
        [
            InlineKeyboardButton(text="🧾 Активность", callback_data=f"admin:u:activity:{tg_id}"),
            InlineKeyboardButton(text="✏️ Профиль", callback_data=f"admin:u:profile:{tg_id}"),
        ],
        [InlineKeyboardButton(text="👥 Группы", callback_data=f"admin:u:audgroups:{tg_id}")],
        [InlineKeyboardButton(text="⚙️ Ещё действия", callback_data=f"admin:u:more:{tg_id}")],
        [InlineKeyboardButton(text="⬅ Пользователи", callback_data="admin:users")],
    ]
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


async def _user_plan_view(tg_id: int, role: str | None) -> tuple[str, InlineKeyboardMarkup]:
    rec = await db.get(tg_id)
    if not rec:
        return "Пользователь не найден.", users_back()
    profile = await db.get_user_profile(tg_id)
    plan = await db.get_plan(profile.plan_id) if profile and profile.plan_id else None
    lines = [
        f"💎 Тариф · {await _display_label(rec)}",
        "",
        f"Текущий тариф: {plan.name if plan else 'не назначен'}",
    ]
    if plan:
        lines += [
            f"Срок тарифа: {plan.duration_days} дн.",
            f"Трафик: {plan.traffic_gb} GB" if plan.traffic_gb else "Трафик: без лимита",
            f"Лимит IP: {plan.ip_limit}" if plan.ip_limit else "Лимит IP: без лимита",
        ]
    rows: list[list[InlineKeyboardButton]] = []
    if _role_can_support(role):
        rows.append([InlineKeyboardButton(text="💎 Сменить тариф", callback_data=f"admin:u:plan:{tg_id}")])
        if plan:
            rows.append([InlineKeyboardButton(text="▶ Применить параметры тарифа", callback_data=f"admin:u:planapplyask:{tg_id}")])
            rows.append([InlineKeyboardButton(text="🚀 Тариф + согласование", callback_data=f"admin:u:planprovask:{tg_id}")])
    rows.append([InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


async def _user_expiry_view(tg_id: int, role: str | None) -> tuple[str, InlineKeyboardMarkup]:
    rec = await db.get(tg_id)
    if not rec:
        return "Пользователь не найден.", users_back()
    expiry = rec.expiry_time
    try:
        obj = await xui.get_client(rec.email)
        client = obj.get("client", obj)
        expiry = int(client.get("expiryTime") or expiry or 0)
    except XUIError:
        pass
    rows: list[list[InlineKeyboardButton]] = []
    if _role_can_support(role):
        rows.append([
            InlineKeyboardButton(text="➕ +30 дней", callback_data=f"adminextend:{tg_id}"),
            InlineKeyboardButton(text="📅 Установить дату", callback_data=f"admin:u:expiry:{tg_id}"),
        ])
    rows.append([InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")])
    return (
        f"📅 Срок · {await _display_label(rec)}\n\nТекущий срок: {fmt_date(expiry)}",
        InlineKeyboardMarkup(inline_keyboard=rows),
    )


async def _user_traffic_view(tg_id: int, role: str | None) -> tuple[str, InlineKeyboardMarkup]:
    rec = await db.get(tg_id)
    if not rec:
        return "Пользователь не найден.", users_back()
    lines = [f"📊 Трафик · {await _display_label(rec)}", ""]
    try:
        obj = await xui.get_client(rec.email)
        client = obj.get("client", obj)
        traffic = await xui.traffic(rec.email)
        up = int(traffic.get("up") or traffic.get("uplink") or 0)
        down = int(traffic.get("down") or traffic.get("downlink") or 0)
        total = int(client.get("totalGB") or 0)
        used = up + down
        lines += [
            f"Использовано: {human_bytes(used)}",
            f"Лимит: {human_bytes(total) if total else 'без лимита'}",
            f"Осталось: {human_bytes(max(0, total - used)) if total else 'без лимита'}",
        ]
    except XUIError as exc:
        lines.append(f"⚠️ 3x-ui: {exc}")
    rows: list[list[InlineKeyboardButton]] = []
    if _role_can_support(role):
        rows.append([InlineKeyboardButton(text="✏️ Изменить лимит", callback_data=f"admin:u:traffic:{tg_id}")])
        rows.append([InlineKeyboardButton(text="🔄 Сбросить трафик", callback_data=f"admin:u:resetask:{tg_id}")])
    rows.append([InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


async def _user_access_view(tg_id: int, role: str | None) -> tuple[str, InlineKeyboardMarkup]:
    rec = await db.get(tg_id)
    if not rec:
        return "Пользователь не найден.", users_back()
    _plan_name, group_name, _note, _display_name = await _profile_labels(tg_id)
    lines = [
        f"🌐 Доступ · {await _display_label(rec)}",
        "",
        f"Группа серверов: {group_name}",
    ]
    try:
        policy = await provisioner.policy_for_user(tg_id)
        obj = await xui.get_client(rec.email)
        current = {int(x) for x in (obj.get("inboundIds") or [])}
        desired = set(policy.desired_inbound_ids)
        lines += [
            f"Источник политики: {provisioning_source_text(policy.source)}",
            f"Целевые Inbounds: {len(desired)}",
            f"Текущие Inbounds: {len(current)}",
            f"Не хватает: {len(desired - current)}",
        ]
    except Exception as exc:
        lines.append(f"⚠️ Согласование: {type(exc).__name__}")
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="🚀 Согласование", callback_data=f"admin:u:prov:{tg_id}")],
        [InlineKeyboardButton(text="📡 Inbounds", callback_data=f"admin:u:inbounds:{tg_id}")],
    ]
    if _role_can_support(role):
        rows.insert(0, [InlineKeyboardButton(text="🗂 Группа серверов", callback_data=f"admin:u:group:{tg_id}")])
        rows.append([InlineKeyboardButton(text="⚙️ Параметры доступа", callback_data=f"admin:u:accesscfg:{tg_id}")])
    rows.append([InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


async def _user_subscription_view(tg_id: int, role: str | None) -> tuple[str, InlineKeyboardMarkup]:
    rec = await db.get(tg_id)
    if not rec:
        return "Пользователь не найден.", users_back()
    url = sub_url(rec.sub_id)
    rows = [
        [InlineKeyboardButton(text="🌐 Открыть ссылку", url=url)],
        [
            InlineKeyboardButton(text="🔗 Показать URL", callback_data=f"adminsub:{tg_id}"),
            InlineKeyboardButton(text="🔳 QR-код", callback_data=f"admin:u:subqr:{tg_id}"),
        ],
    ]
    if _role_can_admin(role):
        rows.append([InlineKeyboardButton(text="🔐 Перевыпустить ссылку", callback_data=f"admin:u:subrotateask:{tg_id}")])
    rows.append([InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")])
    return (
        f"🔗 Подписка · {await _display_label(rec)}\n\n"
        "Subscription identity сохраняется при обычном согласовании и изменяется только отдельной явной операцией.",
        InlineKeyboardMarkup(inline_keyboard=rows),
    )


async def _user_profile_view(tg_id: int, role: str | None) -> tuple[str, InlineKeyboardMarkup]:
    rec = await db.get(tg_id)
    if not rec:
        return "Пользователь не найден.", users_back()
    _plan_name, _group_name, note, display_name = await _profile_labels(tg_id)
    lines = [
        f"✏️ Профиль · {display_name or rec.email}",
        "",
        f"Telegram ID: {rec.telegram_id}",
        f"Email: {rec.email}",
        f"Отображаемое имя: {display_name or 'не задано'}",
        f"Заметка: {note or '—'}",
    ]
    rows: list[list[InlineKeyboardButton]] = []
    if _role_can_support(role):
        rows.append([
            InlineKeyboardButton(text="✏️ Имя", callback_data=f"admin:u:name:{tg_id}"),
            InlineKeyboardButton(text="📝 Заметка", callback_data=f"admin:u:note:{tg_id}"),
        ])
    rows.append([InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


async def _user_more_view(tg_id: int, role: str | None) -> tuple[str, InlineKeyboardMarkup]:
    rec = await db.get(tg_id)
    if not rec:
        return "Пользователь не найден.", users_back()
    enabled: bool | None = None
    try:
        obj = await xui.get_client(rec.email)
        enabled = bool((obj.get("client", obj)).get("enable", True))
    except XUIError:
        pass
    rows: list[list[InlineKeyboardButton]] = []
    if _role_can_support(role):
        if enabled is not None:
            rows.append([(
                InlineKeyboardButton(text="⛔ Отключить", callback_data=f"admindisable:{tg_id}")
                if enabled else
                InlineKeyboardButton(text="✅ Включить", callback_data=f"adminenable:{tg_id}")
            )])
        rows.append([InlineKeyboardButton(text="🔄 Сбросить трафик", callback_data=f"admin:u:resetask:{tg_id}")])
    if _role_can_admin(role):
        rows.append([InlineKeyboardButton(text="⚠️ Строгое согласование", callback_data=f"admin:u:provstrictask:{tg_id}")])
        rows.append([InlineKeyboardButton(text="🔐 Перевыпустить подписку", callback_data=f"admin:u:subrotateask:{tg_id}")])
        rows.append([InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admindelask:{tg_id}")])
    rows.append([InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")])
    return (
        f"⚙️ Ещё действия · {await _display_label(rec)}\n\n"
        "Здесь собраны lifecycle и destructive операции, доступные текущей роли.",
        InlineKeyboardMarkup(inline_keyboard=rows),
    )


def _fmt_optional_ms(value: object) -> str:
    try:
        timestamp = int(value or 0)
    except (TypeError, ValueError):
        return "—"
    if timestamp <= 0:
        return "—"
    return format_timestamp(timestamp, milliseconds=True, empty="—")


def _device_title(item: dict[str, object]) -> str:
    model = str(item.get("deviceModel") or "").strip()
    os_name = str(item.get("deviceOs") or "").strip()
    fingerprint = str(item.get("fingerprint") or "").strip()
    label = model or os_name or fingerprint or f"Устройство #{item.get('id') or '—'}"
    return label[:48]


async def _user_connections_view(tg_id: int, role: str | None) -> tuple[str, InlineKeyboardMarkup]:
    rec = await db.get(tg_id)
    if not rec:
        return "Пользователь не найден.", users_back()

    results = await asyncio.gather(
        xui.get_client(rec.email),
        xui.online_clients(),
        xui.last_online(),
        xui.client_hwids(rec.email),
        xui.client_ips(rec.email),
        return_exceptions=True,
    )
    client_result, online_result, last_result, hwid_result, ips_result = results

    limit_ip = "недоступно"
    if isinstance(client_result, dict):
        client = client_result.get("client", client_result)
        value = int(client.get("limitIp") or 0)
        limit_ip = str(value) if value else "без лимита"

    online_text = "⚪ неизвестно"
    if isinstance(online_result, list):
        online_text = "🟢 в сети" if rec.email in online_result else "⚪ не в сети"

    last_text = "—"
    if isinstance(last_result, dict):
        last_text = _fmt_optional_ms(last_result.get(rec.email))

    hwid_count = str(len(hwid_result)) if isinstance(hwid_result, list) else "недоступно"
    ip_count = str(len(ips_result)) if isinstance(ips_result, list) else "недоступно"

    lines = [
        f"📱 Подключения · {await _display_label(rec)}",
        "",
        f"Статус: {online_text}",
        f"Последняя активность: {last_text}",
        f"IP limit: {limit_ip}",
        "",
        f"Устройств: {hwid_count}",
        f"IP-адресов: {ip_count}",
    ]
    rows = [
        [
            InlineKeyboardButton(text="📱 Устройства", callback_data=f"admin:u:devices:{tg_id}"),
            InlineKeyboardButton(text="🌐 IP-адреса", callback_data=f"admin:u:ips:{tg_id}"),
        ],
        [InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")],
    ]
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


async def _user_devices_view(tg_id: int, role: str | None) -> tuple[str, InlineKeyboardMarkup]:
    rec = await db.get(tg_id)
    if not rec:
        return "Пользователь не найден.", users_back()
    try:
        devices = await xui.client_hwids(rec.email)
    except XUIError as exc:
        return (
            f"📱 Устройства · {await _display_label(rec)}\n\n⚠️ 3x-ui: {exc}",
            InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅ Подключения", callback_data=f"admin:u:connections:{tg_id}")
            ]]),
        )

    lines = [f"📱 Устройства · {await _display_label(rec)}", ""]
    rows: list[list[InlineKeyboardButton]] = []
    if not devices:
        lines.append("— зарегистрированных HWID устройств нет")
    else:
        for index, item in enumerate(devices[:30], start=1):
            device_id = int(item.get("id") or 0)
            title = _device_title(item)
            fingerprint = str(item.get("fingerprint") or "—")[:24]
            last_seen = _fmt_optional_ms(item.get("lastSeen"))
            lines += [
                f"{index}. {title}",
                f"   Fingerprint: {fingerprint}",
                f"   Последняя активность: {last_seen}",
            ]
            if device_id > 0:
                rows.append([InlineKeyboardButton(
                    text=f"📱 {index}. {title}"[:60],
                    callback_data=f"admin:u:device:{tg_id}:{device_id}",
                )])
        if len(devices) > 30:
            lines.append(f"… ещё {len(devices) - 30}")
    rows.append([InlineKeyboardButton(text="⬅ Подключения", callback_data=f"admin:u:connections:{tg_id}")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


async def _find_user_device(tg_id: int, device_id: int) -> tuple[UserRecord | None, dict[str, object] | None]:
    rec = await db.get(tg_id)
    if not rec:
        return None, None
    devices = await xui.client_hwids(rec.email)
    for item in devices:
        try:
            current_id = int(item.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if current_id == device_id:
            return rec, item
    return rec, None


@advanced_users_router.callback_query(F.data.startswith("admin:u:connections:"))
async def user_connections(call: CallbackQuery):
    await _render_user_section(call, _user_connections_view)


@advanced_users_router.callback_query(F.data.startswith("admin:u:devices:"))
async def user_devices(call: CallbackQuery):
    await _render_user_section(call, _user_devices_view)


@advanced_users_router.callback_query(F.data.regexp(r"^admin:u:device:\d+:\d+$"))
async def user_device_detail(call: CallbackQuery):
    ok, role = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    parts = call.data.split(":")
    tg_id, device_id = int(parts[-2]), int(parts[-1])
    try:
        rec, item = await _find_user_device(tg_id, device_id)
    except XUIError as exc:
        await render_callback(
            call,
            f"⚠️ 3x-ui: {exc}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅ Устройства", callback_data=f"admin:u:devices:{tg_id}")
            ]]),
        )
        await call.answer()
        return
    if not rec or not item:
        await call.answer("Устройство не найдено.", show_alert=True)
        return
    model = str(item.get("deviceModel") or "—")[:80]
    os_name = str(item.get("deviceOs") or "—")[:40]
    os_version = str(item.get("osVersion") or "")[:40]
    fingerprint = str(item.get("fingerprint") or "—")[:32]
    user_agent = str(item.get("userAgent") or "—").replace("\n", " ").replace("\r", " ")[:160]
    text = (
        f"📱 Устройство · {await _display_label(rec)}\n\n"
        f"Модель: {model}\n"
        f"ОС: {os_name}{(' ' + os_version) if os_version else ''}\n"
        f"Fingerprint: {fingerprint}\n"
        f"User-Agent: {user_agent}\n"
        f"Первое появление: {_fmt_optional_ms(item.get('firstSeen'))}\n"
        f"Последняя активность: {_fmt_optional_ms(item.get('lastSeen'))}"
    )
    rows: list[list[InlineKeyboardButton]] = []
    if _role_can_support(role):
        rows.append([InlineKeyboardButton(
            text="🗑 Удалить устройство",
            callback_data=f"admin:u:devdelask:{tg_id}:{device_id}",
        )])
    rows.append([InlineKeyboardButton(text="⬅ Устройства", callback_data=f"admin:u:devices:{tg_id}")])
    await render_callback(call, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@advanced_users_router.callback_query(F.data.regexp(r"^admin:u:devdelask:\d+:\d+$"))
async def user_device_delete_ask(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    parts = call.data.split(":")
    tg_id, device_id = int(parts[-2]), int(parts[-1])
    try:
        rec, item = await _find_user_device(tg_id, device_id)
    except XUIError as exc:
        await call.answer(str(exc)[:180], show_alert=True)
        return
    if not rec or not item:
        await call.answer("Устройство не найдено.", show_alert=True)
        return
    await render_callback(
        call,
        "⚠️ Удалить устройство?\n\n"
        f"{_device_title(item)}\n"
        "Пользователь сможет зарегистрировать устройство заново, "
        "если это разрешает текущий HWID limit.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ Удалить устройство", callback_data=f"admin:u:devdel:{tg_id}:{device_id}")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:u:device:{tg_id}:{device_id}")],
        ]),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.regexp(r"^admin:u:devdel:\d+:\d+$"))
async def user_device_delete(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    parts = call.data.split(":")
    tg_id, device_id = int(parts[-2]), int(parts[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    try:
        await xui.delete_client_hwid(rec.email, device_id)
        await audit_from_call(
            db, call, "user.device.delete",
            target_type="user", target_id=rec.email,
            details=f"device_id={device_id}",
        )
        await render_callback(
            call,
            "✅ Устройство удалено.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅ Устройства", callback_data=f"admin:u:devices:{tg_id}")
            ]]),
        )
    except XUIMutationError as exc:
        await audit_from_call(
            db, call, "user.device.delete",
            target_type="user", target_id=rec.email,
            details=f"device_id={device_id}; code={exc.code}; uncertain={exc.uncertain}",
            success=False,
        )
        message = (
            "⚠️ Итог удаления устройства неизвестен. Запрос не повторялся; обнови список устройств."
            if exc.uncertain else
            f"🔴 Удаление отклонено: {exc}"
        )
        await render_callback(
            call,
            message,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅ Устройства", callback_data=f"admin:u:devices:{tg_id}")
            ]]),
        )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:ips:"))
async def user_ips(call: CallbackQuery):
    if not await guard(call, minimum="read_only"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    try:
        entries = await xui.client_ips(rec.email)
        online = await xui.online_clients()
    except XUIError as exc:
        await render_callback(
            call,
            f"🌐 IP-адреса · {await _display_label(rec)}\n\n⚠️ 3x-ui: {exc}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅ Подключения", callback_data=f"admin:u:connections:{tg_id}")
            ]]),
        )
        await call.answer()
        return
    lines = [
        f"🌐 IP-адреса · {await _display_label(rec)}",
        "",
        f"Сейчас online: {'да' if rec.email in online else 'нет'}",
        "",
        "Данные 3x-ui:",
    ]
    if entries:
        lines.extend(f"• {entry[:160]}" for entry in entries[:40])
        if len(entries) > 40:
            lines.append(f"… ещё {len(entries) - 40}")
    else:
        lines.append("— IP-адресов нет")
    lines += ["", "ℹ️ IP/session не считается физическим устройством без HWID identity."]
    await render_callback(
        call,
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅ Подключения", callback_data=f"admin:u:connections:{tg_id}")
        ]]),
    )
    await call.answer()



async def _user_payments_view(tg_id: int, offset: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    rec = await db.get(tg_id)
    if not rec:
        return "Пользователь не найден.", users_back()
    page_size = 8
    total = await db.count_user_payments(tg_id)
    offset = max(0, min(int(offset), max(0, total - 1))) if total else 0
    items = await db.list_user_payments(tg_id, limit=page_size, offset=offset)
    totals = await db.paid_user_totals_by_currency(tg_id)
    paid_count = await db.count_user_payments_by_status(tg_id, "paid")
    paid_text = ", ".join(money_text(value, currency) for currency, value in sorted(totals.items())) or "—"
    lines = [
        f"💳 Платежи · {await _display_label(rec)}",
        "",
        f"Всего: {total}",
        f"Оплачено: {paid_count}",
        f"Суммы оплаченных: {paid_text}",
        "",
        "Последние операции:",
    ]
    rows: list[list[InlineKeyboardButton]] = []
    if items:
        for item in items:
            plan = await db.get_plan(item.plan_id) if item.plan_id else None
            lines.append(
                f"{PAYMENT_STATUS_LABELS.get(item.status, item.status)} · "
                f"{format_timestamp(item.created_at)} · {money_text(item.amount_minor, item.currency)} · "
                f"{plan.name if plan else 'без тарифа'}"
            )
            rows.append([InlineKeyboardButton(
                text=f"💳 #{item.id} · {money_text(item.amount_minor, item.currency)}",
                callback_data=f"admin:u:payment:{tg_id}:{item.id}",
            )])
    else:
        lines.append("— платежей пока нет")

    nav: list[InlineKeyboardButton] = []
    if offset > 0:
        nav.append(InlineKeyboardButton(
            text="⬅ Новее",
            callback_data=f"admin:u:payments:{tg_id}:{max(0, offset - page_size)}",
        ))
    if offset + page_size < total:
        nav.append(InlineKeyboardButton(
            text="➡ Старее",
            callback_data=f"admin:u:payments:{tg_id}:{offset + page_size}",
        ))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="📋 Все платежи", callback_data="admin:payments")])
    rows.append([InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")])
    return "\n".join(lines)[:3900], InlineKeyboardMarkup(inline_keyboard=rows)


@advanced_users_router.callback_query(F.data.regexp(r"^admin:u:payments:\d+(?::\d+)?$"))
async def user_payments_view(call: CallbackQuery):
    if not await guard(call):
        return
    parts = (call.data or "").split(":")
    tg_id = int(parts[3])
    offset = int(parts[4]) if len(parts) > 4 else 0
    text, kb = await _user_payments_view(tg_id, offset)
    await render_callback(call, text, reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(F.data.regexp(r"^admin:u:payment:\d+:\d+$"))
async def user_payment_detail(call: CallbackQuery):
    if not await guard(call):
        return
    parts = (call.data or "").split(":")
    tg_id, payment_id = int(parts[-2]), int(parts[-1])
    rec = await db.get(tg_id)
    item = await db.get_user_payment(tg_id, payment_id)
    if not rec or not item:
        await call.answer("Платёж не найден для этого пользователя.", show_alert=True)
        return
    plan = await db.get_plan(item.plan_id) if item.plan_id else None
    text = (
        f"💳 Платёж #{item.id} · {await _display_label(rec)}\n\n"
        f"Тариф: {plan.name if plan else 'не привязан'}\n"
        f"Сумма: {money_text(item.amount_minor, item.currency)}\n"
        f"Статус: {PAYMENT_STATUS_LABELS.get(item.status, item.status)}\n"
        f"Провайдер: {item.provider or '—'}\n"
        f"Дата: {format_timestamp(item.created_at)}"
    )
    await render_callback(
        call,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅ Платежи", callback_data=f"admin:u:payments:{tg_id}")
        ]]),
    )
    await call.answer()


async def _user_activity_view(tg_id: int, offset: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    rec = await db.get(tg_id)
    if not rec:
        return "Пользователь не найден.", users_back()
    page_size = 10
    total = await db.count_user_audit(tg_id, rec.email)
    offset = max(0, min(int(offset), max(0, total - 1))) if total else 0
    items = await db.list_user_audit(tg_id, rec.email, limit=page_size, offset=offset)
    lines = [f"🧾 Активность · {await _display_label(rec)}", "", f"Записей: {total}", ""]
    if not items:
        lines.append("Активность пока не зафиксирована.")
    else:
        for item in items:
            actor = f"@{item.actor_username}" if item.actor_username else (
                "система" if item.actor_id == 0 else f"TG {item.actor_id}"
            )
            label = USER_AUDIT_LABELS.get(item.action, item.action)
            icon = "✅" if item.success else "🔴"
            lines.append(f"{icon} {format_timestamp(item.created_at)} · {actor}")
            lines.append(label)
            summary = audit_summary_text(item.action, item.details)
            if summary:
                lines.append(summary)
            lines.append("")

    rows: list[list[InlineKeyboardButton]] = []
    nav: list[InlineKeyboardButton] = []
    if offset > 0:
        nav.append(InlineKeyboardButton(
            text="⬅ Новее",
            callback_data=f"admin:u:activity:{tg_id}:{max(0, offset - page_size)}",
        ))
    if offset + page_size < total:
        nav.append(InlineKeyboardButton(
            text="➡ Старее",
            callback_data=f"admin:u:activity:{tg_id}:{offset + page_size}",
        ))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")])
    return "\n".join(lines)[:3900], InlineKeyboardMarkup(inline_keyboard=rows)


@advanced_users_router.callback_query(F.data.regexp(r"^admin:u:activity:\d+(?::\d+)?$"))
async def user_activity_view(call: CallbackQuery):
    if not await guard(call):
        return
    parts = (call.data or "").split(":")
    tg_id = int(parts[3])
    offset = int(parts[4]) if len(parts) > 4 else 0
    text, kb = await _user_activity_view(tg_id, offset)
    await render_callback(call, text, reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(F.data.regexp(r"^admin:u:\d+$"))
async def user_advanced_card(call: CallbackQuery, state: FSMContext):
    ok, role = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    await state.clear()
    tg_id = int(call.data.rsplit(":", 1)[-1])
    text, kb = await render_user(tg_id, role)
    await render_callback(call, text, reply_markup=kb)
    await call.answer()


async def _render_user_section(call: CallbackQuery, renderer) -> None:
    ok, role = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    text, kb = await renderer(tg_id, role)
    await render_callback(call, text, reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:planview:"))
async def user_plan_view(call: CallbackQuery):
    await _render_user_section(call, _user_plan_view)


@advanced_users_router.callback_query(F.data.startswith("admin:u:expiryview:"))
async def user_expiry_view(call: CallbackQuery):
    await _render_user_section(call, _user_expiry_view)


@advanced_users_router.callback_query(F.data.startswith("admin:u:trafficview:"))
async def user_traffic_view(call: CallbackQuery):
    await _render_user_section(call, _user_traffic_view)


@advanced_users_router.callback_query(F.data.startswith("admin:u:access:"))
async def user_access_view(call: CallbackQuery):
    await _render_user_section(call, _user_access_view)


@advanced_users_router.callback_query(F.data.startswith("admin:u:subview:"))
async def user_subscription_view(call: CallbackQuery):
    await _render_user_section(call, _user_subscription_view)


@advanced_users_router.callback_query(F.data.startswith("admin:u:subqr:"))
async def user_subscription_qr(call: CallbackQuery):
    if not await guard(call, minimum="read_only"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    image = qr_png(sub_url(rec.sub_id))
    if call.message is not None:
        try:
            await call.bot.send_photo(
                call.message.chat.id,
                BufferedInputFile(image, filename="subscription-qr.png"),
                caption=f"🔳 QR подписки · {await _display_label(rec)}",
            )
            text = "🔳 QR-код подписки\n\nИзображение отправлено отдельным сообщением."
        except Exception:
            text = "🔳 QR-код подписки\n\n🔴 Не удалось отправить изображение."
    else:
        text = "🔳 QR-код подписки\n\n🔴 Сообщение недоступно."
    await render_callback(call, text, reply_markup=back_user(tg_id))
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:profile:"))
async def user_profile_view(call: CallbackQuery):
    await _render_user_section(call, _user_profile_view)


@advanced_users_router.callback_query(F.data.startswith("admin:u:more:"))
async def user_more_view(call: CallbackQuery):
    await _render_user_section(call, _user_more_view)


@advanced_users_router.callback_query(F.data.startswith("admin:u:accesscfg:"))
async def user_access_config(call: CallbackQuery):
    ok, role = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    limit_ip = "недоступно"
    flow = "недоступно"
    try:
        obj = await xui.get_client(rec.email)
        client = obj.get("client", obj)
        value = int(client.get("limitIp") or 0)
        limit_ip = str(value) if value else "без лимита"
        flow = str(client.get("flow") or "none")
    except XUIError:
        pass
    rows: list[list[InlineKeyboardButton]] = []
    if _role_can_support(role):
        rows.append([InlineKeyboardButton(text="📱 Изменить лимит IP", callback_data=f"admin:u:ip:{tg_id}")])
        if settings.vless_flow:
            rows.append([InlineKeyboardButton(
                text="🔄 Синхронизировать VLESS Flow",
                callback_data=f"admin:u:flowask:{tg_id}",
            )])
    rows.append([InlineKeyboardButton(text="⬅ Доступ", callback_data=f"admin:u:access:{tg_id}")])
    await render_callback(
        call,
        f"⚙️ Параметры доступа · {await _display_label(rec)}\n\n"
        f"Лимит IP: {limit_ip}\n"
        f"VLESS Flow: {flow}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:flowask:"))
async def user_flow_sync_ask(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    if not settings.vless_flow:
        await call.answer("VLESS Flow не настроен.", show_alert=True)
        return
    await render_callback(
        call,
        f"🔄 Синхронизировать VLESS Flow?\n\n{await _display_label(rec)}\n\n"
        "Будет обновлён только Flow. Inbounds не подключаются и не отключаются.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Синхронизировать Flow", callback_data=f"admin:u:flowrun:{tg_id}")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:u:accesscfg:{tg_id}")],
        ]),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:flowrun:"))
async def user_flow_sync_run(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    if not settings.vless_flow:
        await call.answer("VLESS Flow не настроен.", show_alert=True)
        return
    try:
        await xui.bulk_adjust_clients([rec.email], flow=settings.vless_flow)
        await audit_from_call(
            db,
            call,
            "user.flow.sync",
            target_type="user",
            target_id=rec.email,
            details="flow_configured=true; inbound_mutation=false",
        )
        await render_callback(
            call,
            "✅ VLESS Flow синхронизирован. Inbounds не изменялись.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅ Параметры доступа", callback_data=f"admin:u:accesscfg:{tg_id}")
            ]]),
        )
    except XUIError as exc:
        await audit_from_call(
            db,
            call,
            "user.flow.sync",
            target_type="user",
            target_id=rec.email,
            details=f"error={type(exc).__name__}",
            success=False,
        )
        await render_callback(
            call,
            f"🔴 Не удалось синхронизировать Flow: {exc}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅ Параметры доступа", callback_data=f"admin:u:accesscfg:{tg_id}")
            ]]),
        )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:expiry:"))
async def user_expiry_start(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    if not await db.get(tg_id):
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    await state.clear()
    await state.update_data(tg_id=tg_id)
    await state.set_state(EditUserStates.expiry)
    await render_callback(call, 
        "⏳ Изменение срока\n\n"
        "Введи:\n"
        "• +30 — добавить 30 дней к текущему сроку\n"
        "• 2026-12-31 — установить дату 23:59 MSK\n"
        "• 0 — без срока",
        reply_markup=cancel_edit(tg_id),
    )
    await call.answer()


@advanced_users_router.message(EditUserStates.expiry)
async def user_expiry_save(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    data = await state.get_data()
    tg_id = int(data["tg_id"])
    rec = await db.get(tg_id)
    if not rec:
        await state.clear()
        await render_input(message, "Пользователь не найден.", reply_markup=users_back())
        return
    raw = (message.text or "").strip()
    try:
        obj = await xui.get_client(rec.email)
        client = obj.get("client", obj)
        current = int(client.get("expiryTime") or rec.expiry_time or 0)
        now_ms = int(time.time() * 1000)
        if raw == "0":
            new_expiry = 0
        elif raw.startswith("+"):
            days = int(raw[1:])
            if not 1 <= days <= 3650:
                raise ValueError
            base = max(current, now_ms)
            new_expiry = base + days * 86400 * 1000
        else:
            new_expiry = end_of_day_timestamp(raw) * 1000
        await xui.update_client(rec.email, expiryTime=new_expiry)
        await db.update_expiry(tg_id, new_expiry)
        await audit_from_message(
            db, message, "user.expiry.set", target_type="user", target_id=rec.email,
            details=f"old={current}; new={new_expiry}",
        )
        await state.clear()
        await render_input(message, f"✅ Срок: {fmt_date(new_expiry)}", reply_markup=back_user(tg_id))
    except (ValueError, XUIError) as exc:
        if isinstance(exc, XUIError):
            await render_input(message, f"Ошибка 3x-ui: {exc}", reply_markup=cancel_edit(tg_id))
        else:
            await render_input(message, "Формат: +30, YYYY-MM-DD или 0.", reply_markup=cancel_edit(tg_id))


@advanced_users_router.callback_query(F.data.startswith("admin:u:traffic:"))
async def user_traffic_start(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    await state.clear()
    await state.update_data(tg_id=tg_id)
    await state.set_state(EditUserStates.traffic)
    await render_callback(call, 
        "📦 Новый лимит трафика в GB.\n0 = без лимита.\nНапример: 100",
        reply_markup=cancel_edit(tg_id),
    )
    await call.answer()


@advanced_users_router.message(EditUserStates.traffic)
async def user_traffic_save(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    data = await state.get_data()
    tg_id = int(data["tg_id"])
    rec = await db.get(tg_id)
    try:
        gb = int((message.text or "").strip())
        if not 0 <= gb <= 1_000_000:
            raise ValueError
        if not rec:
            raise XUIError("Пользователь не найден")
        await xui.update_client(rec.email, totalGB=gb * 1024**3)
        await audit_from_message(
            db, message, "user.traffic_limit.set", target_type="user", target_id=rec.email,
            details=f"traffic_gb={gb}",
        )
        await state.clear()
        await render_input(message, 
            f"✅ Лимит трафика: {gb} GB" if gb else "✅ Лимит трафика: без лимита",
            reply_markup=back_user(tg_id),
        )
    except ValueError:
        await render_input(message, "Введи целое число GB от 0 до 1000000.", reply_markup=cancel_edit(tg_id))
    except XUIError as exc:
        await render_input(message, f"Ошибка 3x-ui: {exc}", reply_markup=cancel_edit(tg_id))


@advanced_users_router.callback_query(F.data.startswith("admin:u:ip:"))
async def user_ip_start(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    await state.clear()
    await state.update_data(tg_id=tg_id)
    await state.set_state(EditUserStates.ip_limit)
    await render_callback(call, 
        "📱 Новый лимит IP.\n0 = без лимита.\nНапример: 2",
        reply_markup=cancel_edit(tg_id),
    )
    await call.answer()


@advanced_users_router.message(EditUserStates.ip_limit)
async def user_ip_save(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    data = await state.get_data()
    tg_id = int(data["tg_id"])
    rec = await db.get(tg_id)
    try:
        limit = int((message.text or "").strip())
        if not 0 <= limit <= 1000:
            raise ValueError
        if not rec:
            raise XUIError("Пользователь не найден")
        await xui.update_client(rec.email, limitIp=limit)
        await audit_from_message(
            db, message, "user.ip_limit.set", target_type="user", target_id=rec.email,
            details=f"limitIp={limit}",
        )
        await state.clear()
        await render_input(message, 
            f"✅ Лимит IP: {limit}" if limit else "✅ Лимит IP: без лимита",
            reply_markup=back_user(tg_id),
        )
    except ValueError:
        await render_input(message, "Введи целое число от 0 до 1000.", reply_markup=cancel_edit(tg_id))
    except XUIError as exc:
        await render_input(message, f"Ошибка 3x-ui: {exc}", reply_markup=cancel_edit(tg_id))


@advanced_users_router.callback_query(F.data.startswith("admin:u:name:"))
async def user_display_name_start(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    if not await db.get(tg_id):
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    await state.clear()
    await state.update_data(tg_id=tg_id)
    await state.set_state(EditUserStates.display_name)
    await render_callback(
        call,
        "✏️ Имя пользователя\n\n"
        "Введи отображаемое имя (до 64 символов).\n"
        "«-» очищает имя и возвращает отображение email.",
        reply_markup=cancel_edit(tg_id),
    )
    await call.answer()


@advanced_users_router.message(EditUserStates.display_name)
async def user_display_name_save(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    data = await state.get_data()
    tg_id = int(data["tg_id"])
    rec = await db.get(tg_id)
    if not rec:
        await state.clear()
        await render_input(message, "Пользователь не найден.", reply_markup=users_back())
        return
    try:
        display_name = normalize_display_name(message.text or "")
    except ValueError:
        await render_input(
            message,
            "Имя должно содержать 1–64 символа без управляющих символов. "
            "Используй «-», чтобы очистить имя.",
            reply_markup=cancel_edit(tg_id),
        )
        return
    old_profile = await db.get_user_profile(tg_id)
    old_name = (getattr(old_profile, "display_name", "") or "") if old_profile else ""
    await db.set_user_display_name(tg_id, display_name)
    action = "cleared" if not display_name else ("created" if not old_name else "changed")
    await audit_from_message(
        db,
        message,
        "user.display_name.set",
        target_type="user",
        target_id=rec.email,
        details=f"action={action}; old_length={len(old_name)}; new_length={len(display_name)}",
    )
    await state.clear()
    result = "✅ Имя очищено. Используется email." if not display_name else f"✅ Имя: {display_name}"
    await render_input(message, result, reply_markup=back_user(tg_id))


@advanced_users_router.callback_query(F.data.startswith("admin:u:note:"))
async def user_note_start(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    await state.clear()
    await state.update_data(tg_id=tg_id)
    await state.set_state(EditUserStates.note)
    await render_callback(call, 
        "📝 Введи внутреннюю заметку (до 500 символов).\n«-» очищает заметку.",
        reply_markup=cancel_edit(tg_id),
    )
    await call.answer()


@advanced_users_router.message(EditUserStates.note)
async def user_note_save(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    data = await state.get_data()
    tg_id = int(data["tg_id"])
    rec = await db.get(tg_id)
    note = (message.text or "").strip()
    if note == "-":
        note = ""
    if len(note) > 500:
        await render_input(message, "Максимум 500 символов.", reply_markup=cancel_edit(tg_id))
        return
    await db.set_user_note(tg_id, note)
    await audit_from_message(
        db, message, "user.note.set", target_type="user", target_id=rec.email if rec else str(tg_id),
        details=f"length={len(note)}",
    )
    await state.clear()
    await render_input(message, "✅ Заметка сохранена.", reply_markup=back_user(tg_id))


@advanced_users_router.callback_query(F.data.startswith("admin:u:plan:"))
async def user_plan_menu(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    plans = await db.list_plans()
    profile = await db.get_user_profile(tg_id)
    current = profile.plan_id if profile else None
    rows = [[InlineKeyboardButton(
        text=f"{'✅' if current is None else '⬜'} Без тарифа",
        callback_data=f"admin:u:planset:{tg_id}:0",
    )]]
    for plan in plans[:30]:
        icon = "✅" if current == plan.id else ("🟢" if plan.active else "⚪")
        rows.append([InlineKeyboardButton(
            text=f"{icon} {plan.name}", callback_data=f"admin:u:planset:{tg_id}:{plan.id}"
        )])
    rows.append([InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")])
    await render_callback(call, 
        "💎 Тариф\n\nНазначение здесь — административные метаданные. Лимиты 3x-ui не меняются автоматически.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:planset:"))
async def user_plan_set(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    parts = call.data.split(":")
    tg_id, plan_id = int(parts[-2]), int(parts[-1])
    rec = await db.get(tg_id)
    if plan_id and not await db.get_plan(plan_id):
        await call.answer("Тариф не найден.", show_alert=True)
        return
    await db.set_user_plan(tg_id, plan_id or None)
    plan = await db.get_plan(plan_id) if plan_id else None
    await audit_from_call(
        db, call, "user.plan.set", target_type="user", target_id=rec.email if rec else str(tg_id),
        details=f"plan_id={plan_id or None}; name={plan.name if plan else ''}",
    )
    await render_callback(call, 
        f"✅ Тариф: {plan.name if plan else 'не назначен'}", reply_markup=back_user(tg_id)
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:planapplyask:"))
async def user_plan_apply_ask(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    profile = await db.get_user_profile(tg_id)
    plan = await db.get_plan(profile.plan_id) if profile and profile.plan_id else None
    if not rec or not plan:
        await call.answer("Сначала назначь пользователю тариф.", show_alert=True)
        return
    await render_callback(call, 
        f"Применить тариф «{plan.name}» к {await _display_label(rec)}?\n\n"
        f"Срок станет: сейчас + {plan.duration_days} дней\n"
        f"Трафик: {plan.traffic_gb} GB{' (без лимита)' if plan.traffic_gb == 0 else ''}\n"
        f"Лимит IP: {plan.ip_limit if plan.ip_limit else 'без лимита'}\n\n"
        "Накопленный трафик не сбрасывается. Группа серверов сохраняется отдельно.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Применить", callback_data=f"admin:u:planapplyrun:{tg_id}")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:u:{tg_id}")],
        ]),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:planapplyrun:"))
async def user_plan_apply_run(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    profile = await db.get_user_profile(tg_id)
    plan = await db.get_plan(profile.plan_id) if profile and profile.plan_id else None
    if not rec or not plan:
        await call.answer("Тариф не найден.", show_alert=True)
        return
    expiry = int((time.time() + max(0, plan.duration_days) * 86400) * 1000) if plan.duration_days else 0
    try:
        await xui.update_client(
            rec.email,
            expiryTime=expiry,
            totalGB=max(0, plan.traffic_gb) * 1024**3,
            limitIp=max(0, plan.ip_limit),
        )
        await db.update_expiry(tg_id, expiry)
        if plan.server_group_id:
            await db.set_user_server_group(tg_id, plan.server_group_id)
        await audit_from_call(
            db, call, "user.plan.apply", target_type="user", target_id=rec.email,
            details=(
                f"plan_id={plan.id}; expiry={expiry}; traffic_gb={plan.traffic_gb}; "
                f"limit_ip={plan.ip_limit}; server_group_id={plan.server_group_id}"
            ),
        )
        await render_callback(call, 
            f"✅ Тариф «{plan.name}» применён к лимитам 3x-ui.", reply_markup=back_user(tg_id)
        )
    except XUIError as exc:
        await audit_from_call(
            db, call, "user.plan.apply", target_type="user", target_id=rec.email,
            details=f"error={exc}", success=False,
        )
        await render_callback(call, f"Ошибка 3x-ui: {exc}", reply_markup=back_user(tg_id))
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:group:"))
async def user_group_menu(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    groups = await db.list_server_groups()
    profile = await db.get_user_profile(tg_id)
    current = profile.server_group_id if profile else None
    rows = [[InlineKeyboardButton(
        text=f"{'✅' if current is None else '⬜'} Без группы",
        callback_data=f"admin:u:groupset:{tg_id}:0",
    )]]
    for group in groups[:30]:
        rows.append([InlineKeyboardButton(
            text=f"{'✅' if current == group.id else '⬜'} {group.name}",
            callback_data=f"admin:u:groupset:{tg_id}:{group.id}",
        )])
    rows.append([InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")])
    await render_callback(call, 
        "🗂 Группа серверов\n\nГруппа определяет целевой набор согласования. Само назначение не меняет 3x-ui мгновенно — используй «🚀 Согласование».",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:groupset:"))
async def user_group_set(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    parts = call.data.split(":")
    tg_id, group_id = int(parts[-2]), int(parts[-1])
    rec = await db.get(tg_id)
    if group_id and not await db.get_server_group(group_id):
        await call.answer("Группа не найдена.", show_alert=True)
        return
    await db.set_user_server_group(tg_id, group_id or None)
    group = await db.get_server_group(group_id) if group_id else None
    await audit_from_call(
        db, call, "user.server_group.set", target_type="user", target_id=rec.email if rec else str(tg_id),
        details=f"server_group_id={group_id or None}; name={group.name if group else ''}",
    )
    await render_callback(call, 
        f"✅ Группа серверов: {group.name if group else 'не назначена'}", reply_markup=back_user(tg_id)
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:prov:"))
async def user_provisioning_card(call: CallbackQuery):
    if not await guard(call, minimum="read_only"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    try:
        policy = await provisioner.policy_for_user(tg_id)
        obj = await xui.get_client(rec.email)
        current = {int(x) for x in (obj.get("inboundIds") or [])}
        desired = set(policy.desired_inbound_ids)
        managed = set(policy.managed_inbound_ids)
        missing = sorted(desired - current)
        actionable_missing = sorted(set(policy.actionable_inbound_ids) - current)
        extra = sorted((current & managed) - desired)
        lines = [
            f"🚀 Согласование · {await _display_label(rec)}",
            "",
            f"Источник: {provisioning_source_text(policy.source)}",
            f"Тариф: {policy.plan.name if policy.plan else 'не назначен'}",
            f"Группа серверов: {policy.group.name if policy.group else 'режим совместимости «все управляемые»'}",
            f"Режим Inbounds: {inbound_mode_text(policy.inbound_mode)}",
            "",
            f"Целевые: {len(desired)} · {', '.join(map(str, sorted(desired))) if desired else 'нет'}",
            f"Текущие: {len(current)} · {', '.join(map(str, sorted(current))) if current else 'нет'}",
            f"Не хватает: {len(missing)} · доступно сейчас: {len(actionable_missing)}",
            f"Лишних управляемых: {len(extra)}",
        ]
        if policy.unavailable_members:
            lines.append(f"Недоступные ноды: {', '.join(policy.unavailable_members)}")
        if policy.warnings:
            lines += ["", "Предупреждения:"] + [f"⚠️ {w}" for w in policy.warnings]
        rows = [
            [InlineKeyboardButton(text="✅ Безопасное согласование", callback_data=f"admin:u:provrun:{tg_id}:safe")],
            [InlineKeyboardButton(text="⚠️ Строгое согласование", callback_data=f"admin:u:provstrictask:{tg_id}")],
            [InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")],
        ]
        await render_callback(call, "\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception as exc:
        await render_callback(call, f"🔴 Согласование: {type(exc).__name__}: {exc}", reply_markup=back_user(tg_id))
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:provstrictask:"))
async def user_provisioning_strict_ask(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    await render_callback(call, 
        "⚠️ Строгое согласование не только добавит отсутствующие Inbounds, но и отключит управляемые Inbounds, которых нет в целевой политике.\n\nПродолжить?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ Да, строгое согласование", callback_data=f"admin:u:provrun:{tg_id}:strict")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:u:prov:{tg_id}")],
        ]),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.regexp(r"^admin:u:provrun:\d+:(safe|strict)$"))
async def user_provisioning_run(call: CallbackQuery):
    mode = call.data.rsplit(":", 1)[-1]
    minimum = "admin" if mode == "strict" else "support"
    if not await guard(call, minimum=minimum):
        return
    parts = call.data.split(":")
    tg_id = int(parts[-2])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    try:
        result = await provisioner.sync_user(tg_id, strict=(mode == "strict"), apply_plan_limits=False)
        await audit_from_call(
            db, call, f"user.provision.{mode}", target_type="user", target_id=rec.email,
            details=f"attached={result.attached_ids}; detached={result.detached_ids}; remaining={result.remaining_missing_ids}; extra={result.extra_ids}",
        )
        lines = [
            f"✅ {reconcile_text(mode)} завершено.",
            f"Подключены: {result.attached_ids or 'нет'}",
            f"Отключены: {result.detached_ids or 'нет'}",
            f"Всё ещё отсутствуют: {result.remaining_missing_ids or 'нет'}",
            f"Лишние управляемые: {result.extra_ids or 'нет'}",
        ]
        if result.policy.unavailable_members:
            lines.append(f"⏸ Недоступные ноды: {', '.join(result.policy.unavailable_members)}")
        await render_callback(call, "\n".join(lines), reply_markup=back_user(tg_id))
    except Exception as exc:
        await audit_from_call(db, call, f"user.provision.{mode}", target_type="user", target_id=rec.email, details=f"error={type(exc).__name__}: {exc}", success=False)
        await render_callback(call, f"🔴 Ошибка согласования: {type(exc).__name__}: {exc}", reply_markup=back_user(tg_id))
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:planprovask:"))
async def user_plan_provision_ask(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    profile = await db.get_user_profile(tg_id)
    plan = await db.get_plan(profile.plan_id) if profile and profile.plan_id else None
    if not plan:
        await call.answer("Сначала назначь тариф.", show_alert=True)
        return
    await render_callback(call, 
        f"Применить тариф «{plan.name}» к лимитам и выполнить безопасное согласование?\n\n"
        "Это обновит срок/трафик/лимит IP, назначит группу серверов тарифа и добавит отсутствующие Inbounds. Лишние Inbounds не удаляются.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Тариф + согласование", callback_data=f"admin:u:planprovrun:{tg_id}")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:u:{tg_id}")],
        ]),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:planprovrun:"))
async def user_plan_provision_run(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    try:
        result = await provisioner.sync_user(tg_id, strict=False, apply_plan_limits=True)
        await audit_from_call(
            db, call, "user.plan.provision", target_type="user", target_id=rec.email,
            details=f"plan={result.policy.plan.id if result.policy.plan else None}; attached={result.attached_ids}; remaining={result.remaining_missing_ids}",
        )
        await render_callback(call, 
            f"✅ Тариф + согласование завершены.\nДобавлены: {result.attached_ids or 'нет'}\nОстались отсутствующими: {result.remaining_missing_ids or 'нет'}",
            reply_markup=back_user(tg_id),
        )
    except Exception as exc:
        await audit_from_call(db, call, "user.plan.provision", target_type="user", target_id=rec.email, details=f"error={type(exc).__name__}: {exc}", success=False)
        await render_callback(call, f"🔴 Тариф + согласование: {type(exc).__name__}: {exc}", reply_markup=back_user(tg_id))
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:inbounds:"))
async def user_inbounds(call: CallbackQuery):
    if not await guard(call, minimum="read_only"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    try:
        all_inbounds = choose_inbounds(await xui.inbound_options())
        obj = await xui.get_client(rec.email)
        current = {int(x) for x in (obj.get("inboundIds") or [])}
        rows = []
        for inbound in all_inbounds[:40]:
            rows.append([InlineKeyboardButton(
                text=f"{'✅' if inbound.id in current else '⬜'} #{inbound.id} · {inbound.port}/{inbound.protocol} · {inbound.remark}",
                callback_data=f"admin:u:ibtoggle:{tg_id}:{inbound.id}",
            )])
        rows.append([InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")])
        await render_callback(call, 
            f"📡 Inbounds · {await _display_label(rec)}\n\nНажатие подключает/отключает пользователя от конкретного Inbound.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )
    except XUIError as exc:
        await render_callback(call, f"Ошибка 3x-ui: {exc}", reply_markup=back_user(tg_id))
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:ibtoggle:"))
async def user_inbound_toggle(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    parts = call.data.split(":")
    tg_id, inbound_id = int(parts[-2]), int(parts[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    try:
        obj = await xui.get_client(rec.email)
        current = {int(x) for x in (obj.get("inboundIds") or [])}
        allowed = {i.id for i in choose_inbounds(await xui.inbound_options())}
        if inbound_id in current:
            managed_current = current & allowed
            if inbound_id in managed_current and len(managed_current) <= 1:
                await call.answer("Нельзя отключить последний управляемый Inbound.", show_alert=True)
                return
            await xui.detach_client(rec.email, [inbound_id])
            action = "detach"
        else:
            if inbound_id not in allowed:
                await call.answer("Inbound не разрешён настройками бота.", show_alert=True)
                return
            await xui.attach_client(rec.email, [inbound_id])
            if settings.vless_flow:
                await xui.bulk_adjust_clients([rec.email], flow=settings.vless_flow)
            action = "attach"
        await audit_from_call(
            db, call, f"user.inbound.{action}", target_type="user", target_id=rec.email,
            details=f"inbound_id={inbound_id}",
        )
        await call.answer("Обновлено.")
        # Re-render the list as a new message so Telegram callback state stays simple.
        all_inbounds = choose_inbounds(await xui.inbound_options())
        updated = await xui.get_client(rec.email)
        now_ids = {int(x) for x in (updated.get("inboundIds") or [])}
        rows = [[InlineKeyboardButton(
            text=f"{'✅' if i.id in now_ids else '⬜'} #{i.id} · {i.port}/{i.protocol} · {i.remark}",
            callback_data=f"admin:u:ibtoggle:{tg_id}:{i.id}",
        )] for i in all_inbounds[:40]]
        rows.append([InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")])
        await render_callback(call, "📡 Inbounds обновлены.", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except XUIError as exc:
        await audit_from_call(
            db, call, "user.inbound.toggle", target_type="user", target_id=rec.email,
            details=f"inbound_id={inbound_id}; error={exc}", success=False,
        )
        await render_callback(call, f"Ошибка 3x-ui: {exc}", reply_markup=back_user(tg_id))


@advanced_users_router.callback_query(F.data.startswith("admin:u:resetask:"))
async def user_reset_ask(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    await render_callback(call, 
        f"Сбросить накопленный трафик {await _display_label(rec)} до 0?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Сбросить трафик", callback_data=f"admin:u:resetrun:{tg_id}")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:u:{tg_id}")],
        ]),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:resetrun:"))
async def user_reset_run(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    try:
        result = await xui.bulk_reset_traffic([rec.email])
        affected = int((result.get("obj") or {}).get("affected") or 0)
        await audit_from_call(
            db, call, "user.traffic.reset", target_type="user", target_id=rec.email,
            details=f"affected={affected}",
        )
        await render_callback(call, f"✅ Трафик сброшен. Затронуто записей: {affected}", reply_markup=back_user(tg_id))
    except XUIError as exc:
        await audit_from_call(
            db, call, "user.traffic.reset", target_type="user", target_id=rec.email,
            details=f"error={exc}", success=False,
        )
        await render_callback(call, f"Ошибка 3x-ui: {exc}", reply_markup=back_user(tg_id))
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:subrotateask:"))
async def user_sub_rotate_ask(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    await render_callback(call, 
        "🔐 Смена ID подписки\n\n"
        "Старый URL подписки перестанет работать. Уже импортированные конфиги в клиентах не удалятся, "
        "но обновлять их по старому URL будет нельзя.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ Сгенерировать новый subId", callback_data=f"admin:u:subrotaterun:{tg_id}")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:u:{tg_id}")],
        ]),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:subrotaterun:"))
async def user_sub_rotate_run(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    new_sid = ""
    for _ in range(5):
        candidate = secrets.token_urlsafe(18)
        if not await db.get_by_sub_id(candidate):
            new_sid = candidate
            break
    if not new_sid:
        await call.answer("Не удалось сгенерировать уникальный subId.", show_alert=True)
        return
    try:
        await xui.update_client(rec.email, subId=new_sid)
        await db.update_sub_id(tg_id, new_sid)
        await audit_from_call(
            db, call, "user.subscription.rotate", target_type="user", target_id=rec.email,
            details="subId rotated",
        )
        await render_callback(call, 
            f"✅ Новый URL подписки для {await _display_label(rec)}:\n{sub_url(new_sid)}",
            reply_markup=back_user(tg_id),
        )
    except XUIError as exc:
        await audit_from_call(
            db, call, "user.subscription.rotate", target_type="user", target_id=rec.email,
            details=f"error={exc}", success=False,
        )
        await render_callback(call, f"Ошибка 3x-ui: {exc}", reply_markup=back_user(tg_id))
    await call.answer()


# ---------------------------------------------------------------------
# Admin users overview / bulk orchestration
# ---------------------------------------------------------------------


async def _users_page_view(page: int, role: str | None) -> tuple[str, InlineKeyboardMarkup]:
    users = await db.list_users()
    pages = max(1, (len(users) + USER_LIST_PAGE_SIZE - 1) // USER_LIST_PAGE_SIZE)
    page = min(max(0, int(page)), pages - 1)
    visible = users[page * USER_LIST_PAGE_SIZE:(page + 1) * USER_LIST_PAGE_SIZE]

    rows: list[list[InlineKeyboardButton]] = []
    for user in visible:
        profile = await db.get_user_profile(user.telegram_id)
        rows.append([InlineKeyboardButton(
            text=f"👤 {user_label(user, profile)} · TG {user.telegram_id}",
            callback_data=f"admin:u:{user.telegram_id}",
        )])

    if pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"admin:users:page:{page - 1}"))
        nav.append(InlineKeyboardButton(
            text=f"{page + 1}/{pages}",
            callback_data="admin:users:noop",
        ))
        if page + 1 < pages:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"admin:users:page:{page + 1}"))
        rows.append(nav)

    if role in {"support", "admin", "owner"}:
        rows.append([
            InlineKeyboardButton(text="🔎 Поиск", callback_data="admin:users:search"),
            InlineKeyboardButton(text="➕ Создать", callback_data="admin:users:create"),
        ])
        rows.append([
            InlineKeyboardButton(text="☑️ Массовые действия", callback_data="admin:users:bulk"),
            InlineKeyboardButton(text="🚀 Согласовать всех", callback_data="admin:provision:all:ask"),
        ])
    else:
        rows.append([InlineKeyboardButton(text="🔎 Поиск", callback_data="admin:users:search")])
    rows.append([
        InlineKeyboardButton(text="👥 Группы пользователей", callback_data="admin:usergroups"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats"),
    ])
    rows.append([InlineKeyboardButton(text="⬅ Панель администратора", callback_data="admin:home")])

    text = (
        "👥 Пользователи\n\n"
        f"Пользователей: {len(users)}\n"
        f"Страница: {page + 1}/{pages}"
    )
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


@advanced_users_router.callback_query(F.data == "admin:users")
async def admin_users(call: CallbackQuery, state: FSMContext):
    ok, role = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    await state.clear()
    text, kb = await _users_page_view(0, role)
    await render_callback(call, text, reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(F.data.regexp(r"^admin:users:page:\d+$"))
async def admin_users_page(call: CallbackQuery):
    ok, role = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    page = int(call.data.rsplit(":", 1)[-1])
    text, kb = await _users_page_view(page, role)
    await render_callback(call, text, reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(F.data == "admin:users:noop")
async def admin_users_noop(call: CallbackQuery):
    if not await guard(call, minimum="read_only"):
        return
    await call.answer()


@advanced_users_router.callback_query(F.data == "admin:users:create")
async def admin_users_create_start(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    await state.clear()
    await state.set_state(CreateUserStates.telegram_id)
    await render_callback(
        call,
        "➕ Новый пользователь\n\nОтправь Telegram ID пользователя.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✖ Отмена", callback_data="admin:users")
        ]]),
    )
    await call.answer()


@advanced_users_router.message(CreateUserStates.telegram_id)
async def admin_users_create_telegram_id(message: Message, state: FSMContext):
    if not await guard_message(message, state, minimum="support"):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        await render_input(
            message,
            "Telegram ID должен быть положительным числом.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✖ Отмена", callback_data="admin:users")
            ]]),
        )
        return
    tg_id = int(raw)
    existing = await db.get(tg_id)
    if existing:
        await state.clear()
        await render_input(
            message,
            "Пользователь уже существует в БД бота.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👤 Открыть пользователя", callback_data=f"admin:u:{tg_id}")],
                [InlineKeyboardButton(text="⬅ Пользователи", callback_data="admin:users")],
            ]),
        )
        return
    try:
        panel_matches = await xui.get_client_by_tg_id(tg_id)
    except XUIError as exc:
        await render_input(
            message,
            f"⚠️ Не удалось проверить 3x-ui: {exc}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✖ Отмена", callback_data="admin:users")
            ]]),
        )
        return
    if panel_matches:
        valid = [
            _panel_client(item) for item in panel_matches
            if _panel_client(item).get("email") and _panel_client(item).get("subId")
        ]
        await state.clear()
        if len(valid) != 1:
            await render_input(
                message,
                "⚠️ В 3x-ui найдено несколько или неполных записей с этим Telegram ID. "
                "Автоматическое восстановление заблокировано.",
                reply_markup=users_back(),
            )
            return
        client = valid[0]
        await render_input(
            message,
            "⚠️ Клиент уже существует в 3x-ui.\n\n"
            f"Email: {client['email']}\n"
            f"Telegram ID: {tg_id}\n\n"
            "Новый remote client создан не будет.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="♻️ Восстановить запись бота",
                    callback_data=f"admin:users:create:recover:{tg_id}",
                )],
                [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:users")],
            ]),
        )
        return

    default_email = f"tg_{tg_id}"
    await state.update_data(telegram_id=tg_id, default_email=default_email)
    await state.set_state(CreateUserStates.email)
    await render_input(
        message,
        "Технический email 3x-ui\n\n"
        f"По умолчанию: {default_email}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Использовать предложенный",
                callback_data="admin:users:create:email-default",
            )],
            [InlineKeyboardButton(
                text="✏️ Ввести другой",
                callback_data="admin:users:create:email-custom",
            )],
            [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:users")],
        ]),
    )


async def _create_show_display_name(call: CallbackQuery, state: FSMContext, email: str) -> None:
    await state.update_data(email=email)
    await state.set_state(CreateUserStates.display_name)
    await render_callback(
        call,
        "Отображаемое имя\n\n"
        "Можно задать имя для админки. Технический email от этого не изменится.\n"
        "Отправь имя или нажми «Пропустить».",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="admin:users:create:display-skip")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:users")],
        ]),
    )


@advanced_users_router.callback_query(F.data == "admin:users:create:email-default")
async def admin_users_create_email_default(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    data = await state.get_data()
    if not data.get("telegram_id") or not data.get("default_email"):
        await state.clear()
        await call.answer("Сценарий создания устарел. Начни заново.", show_alert=True)
        return
    email = str(data["default_email"])
    try:
        available, reason = await _email_available(email)
    except XUIError as exc:
        await call.answer(f"Не удалось проверить email: {exc}", show_alert=True)
        return
    if not available:
        await call.answer(reason, show_alert=True)
        return
    await _create_show_display_name(call, state, email)
    await call.answer()


@advanced_users_router.callback_query(F.data == "admin:users:create:email-custom")
async def admin_users_create_email_custom(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    data = await state.get_data()
    if not data.get("telegram_id"):
        await state.clear()
        await call.answer("Сценарий создания устарел. Начни заново.", show_alert=True)
        return
    await state.set_state(CreateUserStates.email)
    await render_callback(
        call,
        "Технический email 3x-ui\n\n"
        "Введи значение из букв/цифр и символов ., _, - (до 64 символов).",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✖ Отмена", callback_data="admin:users")
        ]]),
    )
    await call.answer()


@advanced_users_router.message(CreateUserStates.email)
async def admin_users_create_email_message(message: Message, state: FSMContext):
    if not await guard_message(message, state, minimum="support"):
        return
    try:
        email = normalize_machine_email(message.text or "")
    except ValueError:
        await render_input(
            message,
            "Некорректный технический email. Разрешены буквы, цифры, ., _, -; максимум 64 символа.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✖ Отмена", callback_data="admin:users")
            ]]),
        )
        return
    try:
        available, reason = await _email_available(email)
    except XUIError as exc:
        await render_input(message, f"⚠️ Не удалось проверить 3x-ui: {exc}", reply_markup=users_back())
        return
    if not available:
        await render_input(message, reason, reply_markup=users_back())
        return
    await state.update_data(email=email)
    await state.set_state(CreateUserStates.display_name)
    await render_input(
        message,
        "Отображаемое имя\n\n"
        "Можно задать имя для админки. Отправь имя или нажми «Пропустить».",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="admin:users:create:display-skip")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:users")],
        ]),
    )


@advanced_users_router.callback_query(F.data == "admin:users:create:display-skip")
async def admin_users_create_display_skip(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    data = await state.get_data()
    if not data.get("telegram_id") or not data.get("email"):
        await state.clear()
        await call.answer("Сценарий создания устарел. Начни заново.", show_alert=True)
        return
    await state.update_data(display_name="")
    await state.set_state(CreateUserStates.plan)
    text, kb = await _create_plan_screen()
    await render_callback(call, text, reply_markup=kb)
    await call.answer()


@advanced_users_router.message(CreateUserStates.display_name)
async def admin_users_create_display_name(message: Message, state: FSMContext):
    if not await guard_message(message, state, minimum="support"):
        return
    try:
        display_name = normalize_display_name(message.text or "")
    except ValueError:
        await render_input(
            message,
            "Имя должно содержать 1–64 символа без управляющих символов.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏭ Пропустить", callback_data="admin:users:create:display-skip")],
                [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:users")],
            ]),
        )
        return
    await state.update_data(display_name=display_name)
    await state.set_state(CreateUserStates.plan)
    text, kb = await _create_plan_screen()
    await render_input(message, text, reply_markup=kb)


@advanced_users_router.callback_query(F.data == "admin:users:create:plans")
async def admin_users_create_plans(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    data = await state.get_data()
    if not data.get("telegram_id") or not data.get("email"):
        await state.clear()
        await call.answer("Сценарий создания устарел. Начни заново.", show_alert=True)
        return
    await state.set_state(CreateUserStates.plan)
    text, kb = await _create_plan_screen()
    await render_callback(call, text, reply_markup=kb)
    await call.answer()


async def _create_select_plan(call: CallbackQuery, state: FSMContext, plan_id: int) -> None:
    data = await state.get_data()
    if not data.get("telegram_id") or not data.get("email"):
        await state.clear()
        await call.answer("Сценарий создания устарел. Начни заново.", show_alert=True)
        return
    try:
        text, kb = await _create_preview(data, plan_id)
    except (ValueError, XUIError) as exc:
        await call.answer(str(exc), show_alert=True)
        return
    await state.update_data(plan_id=int(plan_id))
    await state.set_state(CreateUserStates.review)
    await render_callback(call, text, reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(F.data.regexp(r"^admin:users:create:plan:\d+$"))
async def admin_users_create_plan(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    await _create_select_plan(call, state, int(call.data.rsplit(":", 1)[-1]))


@advanced_users_router.callback_query(F.data == "admin:users:create:plan-compat")
async def admin_users_create_plan_compat(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    await _create_select_plan(call, state, 0)


@advanced_users_router.callback_query(F.data == "admin:users:create:run")
async def admin_users_create_run(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    data = await state.get_data()
    try:
        tg_id = int(data["telegram_id"])
        email = normalize_machine_email(str(data["email"]))
        display_name = str(data.get("display_name") or "")
        plan_id = int(data.get("plan_id") or 0)
    except (KeyError, TypeError, ValueError):
        await state.clear()
        await call.answer("Сценарий создания устарел. Начни заново.", show_alert=True)
        return

    if await db.get(tg_id):
        await state.clear()
        await call.answer("Пользователь уже появился в БД бота.", show_alert=True)
        return

    try:
        panel_matches = await xui.get_client_by_tg_id(tg_id)
        if panel_matches:
            await state.clear()
            await render_callback(
                call,
                "⚠️ Клиент уже появился в 3x-ui. Создание не повторялось. "
                "Запусти создание заново и используй восстановление записи.",
                reply_markup=users_back(),
            )
            await call.answer()
            return
        available, reason = await _email_available(email)
        if not available:
            await state.clear()
            await call.answer(reason, show_alert=True)
            return
        ctx = await _create_user_context(plan_id)
    except (XUIError, ValueError) as exc:
        await call.answer(f"Preflight не пройден: {exc}", show_alert=True)
        return

    duration_days = int(ctx["duration_days"])
    traffic_gb = int(ctx["traffic_gb"])
    ip_limit = int(ctx["ip_limit"])
    inbound_ids = list(ctx["inbound_ids"])
    now = int(time.time())
    expiry = int((now + duration_days * 86400) * 1000) if duration_days else 0
    sub_id = secrets.token_urlsafe(18)
    verified_after_uncertain = False

    try:
        await xui.create_client(
            email=email,
            telegram_id=tg_id,
            sub_id=sub_id,
            inbound_ids=inbound_ids,
            total_bytes=traffic_gb * 1024**3,
            expiry_time_ms=expiry,
            limit_ip=ip_limit,
            comment=f"Создано Admin Control Plane · {ctx['plan_name']}",
            flow=settings.vless_flow,
        )
    except XUIMutationError as exc:
        if not exc.uncertain:
            await audit_from_call(
                db,
                call,
                "user.create",
                target_type="user",
                target_id=email,
                details=f"result=rejected; code={exc.code}",
                success=False,
            )
            await state.clear()
            await render_callback(
                call,
                f"🔴 Создание отклонено: {exc}",
                reply_markup=users_back(),
            )
            await call.answer()
            return

        try:
            matches = await xui.get_client_by_tg_id(tg_id)
        except XUIError:
            matches = []
        proof = [
            _panel_client(item)
            for item in matches
            if _panel_client(item).get("email") == email
            and _panel_client(item).get("subId") == sub_id
        ]
        if len(proof) != 1:
            await audit_from_call(
                db,
                call,
                "user.create",
                target_type="user",
                target_id=email,
                details=f"result=unknown; code={exc.code}; mutation_not_retried=true",
                success=False,
            )
            await state.clear()
            await render_callback(
                call,
                "⚠️ Итог создания неизвестен. POST не повторялся. "
                "Проверь 3x-ui/список пользователей и затем запусти создание заново; "
                "если remote client существует, используй восстановление записи.",
                reply_markup=users_back(),
            )
            await call.answer()
            return
        verified_after_uncertain = True

    try:
        await db.put(UserRecord(tg_id, email, sub_id, expiry, now))
        await db.upsert_user_profile(
            tg_id,
            plan_id=plan_id or None,
            server_group_id=ctx.get("server_group_id"),
            note="",
            display_name=display_name,
            preserve_unspecified=False,
        )
    except Exception as exc:
        await audit_from_call(
            db,
            call,
            "user.create",
            target_type="user",
            target_id=email,
            details=f"remote_created=true; local_save_failed={type(exc).__name__}",
            success=False,
        )
        await state.clear()
        await render_callback(
            call,
            "⚠️ Remote client создан, но локальную запись сохранить не удалось. "
            "Не повторяй создание: запусти flow заново и используй восстановление записи.",
            reply_markup=users_back(),
        )
        await call.answer()
        return

    await audit_from_call(
        db,
        call,
        "user.create",
        target_type="user",
        target_id=email,
        details=(
            f"plan_id={plan_id or 'compat'}; inbound_count={len(inbound_ids)}; "
            f"verified_after_uncertain={str(verified_after_uncertain).lower()}"
        ),
    )
    await state.clear()
    await render_callback(
        call,
        f"✅ Пользователь создан.\n\nEmail: {email}\nTelegram ID: {tg_id}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="👤 Открыть пользователя",
                callback_data=f"admin:u:{tg_id}",
            )
        ]]),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.regexp(r"^admin:users:create:recover:\d+$"))
async def admin_users_create_recover(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    if await db.get(tg_id):
        await state.clear()
        await call.answer("Локальная запись уже существует.", show_alert=True)
        return
    try:
        matches = await xui.get_client_by_tg_id(tg_id)
    except XUIError as exc:
        await call.answer(f"Не удалось проверить 3x-ui: {exc}", show_alert=True)
        return
    valid = [
        _panel_client(item)
        for item in matches
        if _panel_client(item).get("email") and _panel_client(item).get("subId")
    ]
    if len(valid) != 1:
        await call.answer(
            "Восстановление заблокировано: remote identity неоднозначна.",
            show_alert=True,
        )
        return
    client = valid[0]
    email = str(client["email"])
    sub_id = str(client["subId"])
    expiry = int(client.get("expiryTime") or 0)
    if await db.get_by_email(email):
        await call.answer(
            "Этот email уже связан с другой локальной записью.",
            show_alert=True,
        )
        return
    await db.put(UserRecord(tg_id, email, sub_id, expiry, int(time.time())))
    await audit_from_call(
        db,
        call,
        "user.recover",
        target_type="user",
        target_id=email,
        details="source=3x-ui; explicit_recovery=true",
    )
    await state.clear()
    await render_callback(
        call,
        "✅ Локальная запись восстановлена из существующего клиента 3x-ui.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="👤 Открыть пользователя",
                callback_data=f"admin:u:{tg_id}",
            )
        ]]),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data == "admin:users:search")
async def admin_users_search(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="read_only"):
        return
    await state.clear()
    await state.set_state(UserListStates.search)
    await render_callback(
        call,
        "🔎 Поиск пользователя\n\n"
        "Введи Telegram ID, email или отображаемое имя.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✖ Отмена", callback_data="admin:users"),
        ]]),
    )
    await call.answer()


@advanced_users_router.message(UserListStates.search)
async def admin_users_search_message(message: Message, state: FSMContext):
    if not await guard_message(message, state, minimum="read_only"):
        return
    query = (message.text or "").strip()
    if not query:
        await render_input(
            message,
            "Введи Telegram ID, email или отображаемое имя.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✖ Отмена", callback_data="admin:users"),
            ]]),
        )
        return

    users = await db.search_users(query, limit=40)
    if not users:
        await render_input(
            message,
            f"🔎 Поиск пользователя\n\nПо запросу «{query[:80]}» ничего не найдено.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔎 Новый поиск", callback_data="admin:users:search")],
                [InlineKeyboardButton(text="⬅ Пользователи", callback_data="admin:users")],
            ]),
        )
        await state.clear()
        return

    rows: list[list[InlineKeyboardButton]] = []
    for user in users:
        profile = await db.get_user_profile(user.telegram_id)
        rows.append([InlineKeyboardButton(
            text=f"👤 {user_label(user, profile)} · TG {user.telegram_id}",
            callback_data=f"admin:u:{user.telegram_id}",
        )])
    rows.append([InlineKeyboardButton(text="🔎 Новый поиск", callback_data="admin:users:search")])
    rows.append([InlineKeyboardButton(text="⬅ Пользователи", callback_data="admin:users")])
    await state.clear()
    await render_input(
        message,
        f"🔎 Поиск пользователя\n\nНайдено: {len(users)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@advanced_users_router.callback_query(F.data == "admin:provision:all:ask")
async def admin_provision_all_ask(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="support")
    if not ok:
        return
    users = await db.list_users()
    await render_callback(call, 
        "🚀 Безопасное согласование доступа для всех пользователей\n\n"
        f"Пользователей: {len(users)}\n"
        "Для каждого пользователя будет рассчитан целевой набор по профилю пользователя → Тариф → Группа серверов. "
        "Будут только добавлены отсутствующие Inbounds на доступных нодах; лишние Inbounds не удаляются.\n\n"
        "Пользователи без тарифа/группы сохраняют режим совместимости «все управляемые Inbounds».",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Запустить безопасное согласование", callback_data="admin:provision:all:run")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:users")],
        ]),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data == "admin:provision:all:run")
async def admin_provision_all_run(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="support")
    if not ok:
        return
    users = await db.list_users()
    if not users:
        await call.answer("Нет пользователей.", show_alert=True)
        return
    await call.answer("Запускаю согласование…")
    run_id = await db.start_job_run(
        name="provision.reconcile_all", trigger="admin",
        actor_id=call.from_user.id if call.from_user else 0,
    )
    started = time.monotonic()
    try:
        summary = await provisioner.provision_many([u.telegram_id for u in users], strict=False)
        duration_ms = int((time.monotonic() - started) * 1000)
        failed = summary.get("failed") or {}
        status = "success" if not failed else "partial"
        await db.finish_job_run(
            run_id, status=status, duration_ms=duration_ms,
            details=f"ok={summary.get('ok')}; failed={len(failed)}; attached={summary.get('attached')}",
        )
        await audit_from_call(
            db, call, "users.provision_all", target_type="users", target_id=str(len(users)),
            details=f"ok={summary.get('ok')}; failed={len(failed)}; attached={summary.get('attached')}",
            success=not bool(failed),
        )
        lines = [
            "✅ Согласование завершено." if not failed else "⚠️ Согласование завершено частично.",
            "",
            f"Пользователей: {len(users)}",
            f"Успешно: {summary.get('ok')}",
            f"Добавлено связей Inbounds: {summary.get('attached')}",
            f"Ошибок: {len(failed)}",
            f"Время: {duration_ms / 1000:.1f}s",
        ]
        if failed:
            lines += ["", "Первые ошибки:"]
            for tg_id, err in list(failed.items())[:8]:
                lines.append(f"• TG {tg_id}: {err[:140]}")
        await render_callback(call, "\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅ Пользователи", callback_data="admin:users")]]))
    except Exception as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        await db.finish_job_run(run_id, status="failed", duration_ms=duration_ms, details=f"{type(exc).__name__}: {exc}")
        await audit_from_call(db, call, "users.provision_all", target_type="users", details=f"error={type(exc).__name__}: {exc}", success=False)
        await render_callback(call, f"🔴 Задание согласования завершилось ошибкой: {type(exc).__name__}: {exc}", reply_markup=users_back())


@advanced_users_router.callback_query(F.data == "admin:syncall:ask")
@advanced_users_router.callback_query(F.data == "admin:syncall:run")
async def admin_sync_all_legacy_redirect(call: CallbackQuery):
    if not await guard(call):
        return
    await render_callback(
        call,
        "ℹ️ «Синхронизировать всех» больше не используется.\n\n"
        "Автоматическое управление доступом выполняется через policy-based "
        "безопасное согласование.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Согласовать всех", callback_data="admin:provision:all:ask")],
            [InlineKeyboardButton(text="⬅ Пользователи", callback_data="admin:users")],
        ]),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data == "admin:stats")
async def admin_stats(call: CallbackQuery):
    if not await guard(call):
        return
    users = await db.list_users()
    now_ms = int(time.time() * 1000)
    active = sum(1 for u in users if not u.expiry_time or u.expiry_time > now_ms)
    soon = sum(1 for u in users if u.expiry_time and now_ms < u.expiry_time <= now_ms + 3*86400*1000)
    await render_callback(call, 
        f"📊 Локальная БД\n\nВсего: {len(users)}\n"
        f"Не истекли: {active}\nИстекают за 3 дня: {soon}",
        reply_markup=users_back()
    )
    await call.answer()


# ---------------------------------------------------------------------
# Legacy user-admin callbacks
# ---------------------------------------------------------------------


@advanced_users_router.callback_query(F.data.startswith("adminuser:"))
async def admin_user(call: CallbackQuery, state: FSMContext):
    """Compatibility route for buttons in messages sent before v4.20.4."""
    ok, role = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    await state.clear()
    tg_id = int(call.data.split(":", 1)[1])
    text, kb = await render_user(tg_id, role)
    await render_callback(call, text, reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("adminsub:"))
async def admin_sub(call: CallbackQuery):
    if not await guard(call):
        return
    tg_id = int(call.data.split(":", 1)[1])
    rec = await db.get(tg_id)
    if rec:
        await render_callback(call, f"🔗 {await _display_label(rec)}\n{sub_url(rec.sub_id)}", reply_markup=back_user(tg_id))
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("adminsublist:"))
async def admin_sub_from_list(call: CallbackQuery):
    if not await guard(call):
        return
    tg_id = int(call.data.split(":", 1)[1])
    rec = await db.get(tg_id)
    if rec:
        await render_callback(
            call,
            f"🔗 {user_label(rec, await db.get_user_profile(rec.telegram_id))}\n{sub_url(rec.sub_id)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅ Подписки", callback_data="admin:subscriptions")
            ]]),
        )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("adminsync:"))
async def admin_sync_inbounds(call: CallbackQuery):
    if not await guard(call):
        return
    tg_id = int(call.data.split(":", 1)[1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    await render_callback(
        call,
        "ℹ️ Это действие устарело.\n\n"
        "Автоматическая синхронизация доступа теперь выполняется "
        "через policy-based «Согласование».",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Открыть согласование", callback_data=f"admin:u:prov:{tg_id}")],
            [InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")],
        ]),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("adminextend:"))
async def admin_extend(call: CallbackQuery):
    if not await guard(call):
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
            db,
            call,
            "user.extend",
            target_type="user",
            target_id=rec.email,
            details=f"+30 days; expiry={new_expiry}",
        )
        await render_callback(
            call,
            f"✅ {await _display_label(rec)} продлён до {fmt_date(new_expiry)}",
            reply_markup=back_user(tg_id),
        )
    except XUIError as exc:
        await audit_from_call(
            db,
            call,
            "user.extend",
            target_type="user",
            target_id=rec.email,
            details=f"3x-ui error: {exc}",
            success=False,
        )
        await render_callback(call, f"Ошибка 3x-ui: {exc}", reply_markup=back_user(tg_id))
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admindisable:"))
async def admin_disable(call: CallbackQuery):
    if not await guard(call):
        return
    tg_id = int(call.data.split(":", 1)[1])
    rec = await db.get(tg_id)
    try:
        await xui.update_client(rec.email, enable=False)
        await audit_from_call(
            db,
            call,
            "user.disable",
            target_type="user",
            target_id=rec.email,
        )
        await render_callback(call, f"⛔ {await _display_label(rec)} отключён.", reply_markup=back_user(tg_id))
    except (XUIError, AttributeError) as exc:
        await audit_from_call(
            db,
            call,
            "user.disable",
            target_type="user",
            target_id=rec.email if rec else str(tg_id),
            details=str(exc),
            success=False,
        )
        await render_callback(call, f"Ошибка: {exc}", reply_markup=back_user(tg_id))
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("adminenable:"))
async def admin_enable(call: CallbackQuery):
    if not await guard(call):
        return
    tg_id = int(call.data.split(":", 1)[1])
    rec = await db.get(tg_id)
    try:
        await xui.update_client(rec.email, enable=True)
        await audit_from_call(
            db,
            call,
            "user.enable",
            target_type="user",
            target_id=rec.email,
        )
        await render_callback(call, f"✅ {await _display_label(rec)} включён.", reply_markup=back_user(tg_id))
    except (XUIError, AttributeError) as exc:
        await audit_from_call(
            db,
            call,
            "user.enable",
            target_type="user",
            target_id=rec.email if rec else str(tg_id),
            details=str(exc),
            success=False,
        )
        await render_callback(call, f"Ошибка: {exc}", reply_markup=back_user(tg_id))
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admindelask:"))
async def admin_del_ask(call: CallbackQuery):
    if not await guard(call):
        return
    tg_id = int(call.data.split(":", 1)[1])
    rec = await db.get(tg_id)
    if rec:
        await render_callback(
            call,
            f"Удалить {await _display_label(rec)} из 3x-ui и локальной БД?\n\n"
            "Клиент и его профиль будут удалены; платёжная история сохранится.",
            reply_markup=confirm_delete_keyboard(tg_id),
        )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admindel:"))
async def admin_del(call: CallbackQuery):
    if not await guard(call):
        return
    tg_id = int(call.data.split(":", 1)[1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Не найден.", show_alert=True)
        return
    try:
        display_label = await _display_label(rec)
        await xui.delete_client(rec.email)
        await db.delete(tg_id)
        await audit_from_call(
            db,
            call,
            "user.delete",
            target_type="user",
            target_id=rec.email,
        )
        await render_callback(call, f"🗑 {display_label} удалён.", reply_markup=users_back())
    except XUIError as exc:
        await audit_from_call(
            db,
            call,
            "user.delete",
            target_type="user",
            target_id=rec.email,
            details=f"3x-ui error: {exc}",
            success=False,
        )
        await render_callback(
            call,
            f"Ошибка 3x-ui, локальная запись сохранена: {exc}",
            reply_markup=back_user(tg_id),
        )
    await call.answer()


# ---------------------------------------------------------------------
# Bulk user actions
# ---------------------------------------------------------------------


async def _bulk_render(state: FSMContext) -> tuple[str, InlineKeyboardMarkup]:
    users = await db.list_users()
    data = await state.get_data()
    selected = {int(x) for x in data.get("selected", [])}
    page = max(0, int(data.get("page", 0)))
    page_size = 12
    pages = max(1, (len(users) + page_size - 1) // page_size)
    page = min(page, pages - 1)
    await state.update_data(page=page)
    visible = users[page * page_size:(page + 1) * page_size]
    rows = []
    for u in visible:
        profile = await db.get_user_profile(u.telegram_id)
        rows.append([InlineKeyboardButton(
            text=f"{'✅' if u.telegram_id in selected else '⬜'} {user_label(u, profile)}",
            callback_data=f"admin:bulk:toggle:{u.telegram_id}",
        )])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅", callback_data="admin:bulk:prev"))
    nav.append(InlineKeyboardButton(text=f"📄 {page + 1}/{pages}", callback_data="admin:bulk:noop"))
    if page + 1 < pages:
        nav.append(InlineKeyboardButton(text="➡", callback_data="admin:bulk:next"))
    rows.append(nav)
    rows.append([
        InlineKeyboardButton(text="☑️ Выбрать всех", callback_data="admin:bulk:all"),
        InlineKeyboardButton(text="🧹 Очистить", callback_data="admin:bulk:clear"),
    ])
    rows.append([InlineKeyboardButton(
        text=f"⚙️ Действия ({len(selected)})", callback_data="admin:bulk:actions"
    )])
    rows.append([InlineKeyboardButton(text="⬅ Пользователи", callback_data="admin:bulk:close")])
    return (
        "☑️ Массовые действия с пользователями\n\n"
        f"Выбрано: {len(selected)} из {len(users)}\n"
        "Отметь пользователей и открой «Действия».",
        InlineKeyboardMarkup(inline_keyboard=rows),
    )


@advanced_users_router.callback_query(F.data == "admin:users:bulk")
async def bulk_start(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    await state.clear()
    await state.set_state(BulkUserStates.selecting)
    await state.update_data(selected=[], page=0)
    text, kb = await _bulk_render(state)
    await render_callback(call, text, reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(BulkUserStates.selecting, F.data.startswith("admin:bulk:toggle:"))
async def bulk_toggle(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    data = await state.get_data()
    selected = {int(x) for x in data.get("selected", [])}
    if tg_id in selected:
        selected.remove(tg_id)
    else:
        selected.add(tg_id)
    await state.update_data(selected=sorted(selected))
    text, kb = await _bulk_render(state)
    await render_callback(call, text, reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(BulkUserStates.selecting, F.data.in_({"admin:bulk:prev", "admin:bulk:next"}))
async def bulk_page(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    data = await state.get_data()
    page = int(data.get("page", 0)) + (-1 if call.data.endswith("prev") else 1)
    await state.update_data(page=max(0, page))
    text, kb = await _bulk_render(state)
    await render_callback(call, text, reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(BulkUserStates.selecting, F.data == "admin:bulk:all")
async def bulk_all(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    users = await db.list_users()
    await state.update_data(selected=[u.telegram_id for u in users])
    text, kb = await _bulk_render(state)
    await render_callback(call, text, reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(BulkUserStates.selecting, F.data == "admin:bulk:clear")
async def bulk_clear(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    await state.update_data(selected=[])
    text, kb = await _bulk_render(state)
    await render_callback(call, text, reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(BulkUserStates.selecting, F.data == "admin:bulk:noop")
async def bulk_noop(call: CallbackQuery):
    await call.answer()


@advanced_users_router.callback_query(BulkUserStates.selecting, F.data == "admin:bulk:actions")
async def bulk_actions(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    selected = (await state.get_data()).get("selected", [])
    if not selected:
        await call.answer("Сначала выбери пользователей.", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ +30 дней", callback_data="admin:bulk:run:extend30")],
        [
            InlineKeyboardButton(text="✅ Включить", callback_data="admin:bulk:run:enable"),
            InlineKeyboardButton(text="⛔ Отключить", callback_data="admin:bulk:run:disable"),
        ],
        [InlineKeyboardButton(text="🔄 Сбросить трафик", callback_data="admin:bulk:run:reset")],
        [InlineKeyboardButton(text="🚀 Согласовать", callback_data="admin:bulk:run:reconcile")],
        [InlineKeyboardButton(text="⬅ К выбору", callback_data="admin:bulk:back")],
    ])
    await render_callback(call, f"⚙️ Массовые действия\n\nВыбрано: {len(selected)}", reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(BulkUserStates.selecting, F.data == "admin:bulk:back")
async def bulk_back(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    text, kb = await _bulk_render(state)
    await render_callback(call, text, reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(BulkUserStates.selecting, F.data == "admin:bulk:close")
async def bulk_close(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    await state.clear()
    await render_callback(call, "Выбор для массовых действий закрыт.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Пользователи", callback_data="admin:users")]
    ]))
    await call.answer()


@advanced_users_router.callback_query(BulkUserStates.selecting, F.data.startswith("admin:bulk:run:"))
async def bulk_run(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    action = call.data.rsplit(":", 1)[-1]
    data = await state.get_data()
    ids = [int(x) for x in data.get("selected", [])]
    records: list[UserRecord] = []
    for tg_id in ids:
        rec = await db.get(tg_id)
        if rec:
            records.append(rec)
    emails = [r.email for r in records]
    if not emails:
        await call.answer("Нет выбранных пользователей.", show_alert=True)
        return
    try:
        details = ""
        if action == "extend30":
            result = await xui.bulk_adjust_clients(emails, add_days=30)
            for rec in records:
                try:
                    obj = await xui.get_client(rec.email)
                    client = obj.get("client", obj)
                    await db.update_expiry(rec.telegram_id, int(client.get("expiryTime") or rec.expiry_time))
                except XUIError:
                    pass
            details = str(result.get("obj") or {})[:1000]
            message = "✅ +30 дней выполнено."
        elif action == "enable":
            result = await xui.bulk_enable_clients(emails)
            details = str(result.get("obj") or {})[:1000]
            message = "✅ Пользователи включены."
        elif action == "disable":
            result = await xui.bulk_disable_clients(emails)
            details = str(result.get("obj") or {})[:1000]
            message = "✅ Пользователи отключены."
        elif action == "reset":
            result = await xui.bulk_reset_traffic(emails)
            details = str(result.get("obj") or {})[:1000]
            message = "✅ Сброс трафика выполнен."
        elif action == "reconcile":
            summary = await provisioner.provision_many(
                [rec.telegram_id for rec in records],
                strict=False,
            )
            failed = summary.get("failed") or {}
            details = (
                f"ok={summary.get('ok')}; failed={len(failed)}; "
                f"attached={summary.get('attached')}"
            )
            message = (
                "✅ Безопасное согласование выполнено."
                if not failed else
                "⚠️ Безопасное согласование выполнено частично."
            )
        elif action == "sync":
            await render_callback(
                call,
                "ℹ️ Массовая «Синхронизация Inbounds» устарела.\n\n"
                "Используй policy-based «Согласование».",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅ К действиям", callback_data="admin:bulk:actions")],
                    [InlineKeyboardButton(text="⬅ Пользователи", callback_data="admin:bulk:close")],
                ]),
            )
            await call.answer()
            return
        else:
            await call.answer("Неизвестное действие.", show_alert=True)
            return
        await audit_from_call(
            db, call, f"users.bulk.{action}", target_type="users", target_id=str(len(emails)),
            details=f"users={len(records)}; {details}",
        )
        await render_callback(call, f"{message}\nПользователей: {len(emails)}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅ К выбору", callback_data="admin:bulk:back")],
            [InlineKeyboardButton(text="⬅ Пользователи", callback_data="admin:bulk:close")],
        ]))
    except Exception as exc:
        await audit_from_call(
            db, call, f"users.bulk.{action}", target_type="users", target_id=str(len(emails)),
            details=f"error={exc}", success=False,
        )
        await render_callback(call, f"Ошибка 3x-ui: {exc}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅ К выбору", callback_data="admin:bulk:back")],
            [InlineKeyboardButton(text="⬅ Пользователи", callback_data="admin:bulk:close")],
        ]))
    await call.answer()
