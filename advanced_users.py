from __future__ import annotations

import secrets
import time
import unicodedata

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_ui import render_callback, render_input
from admin_auth import authorize_callback, authorize_message
from admin_navigation import confirm_delete_keyboard, confirm_sync_all_keyboard
from inbound_policy import is_managed_inbound as inbound_is_managed
from audit import audit_from_call, audit_from_message
from config import load_settings
from db import Database, UserRecord
from ui_time import end_of_day_timestamp, format_timestamp
from user_ui import display_name_from_profile, user_label
from xui import XUIClient, XUIError
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


async def render_user(tg_id: int) -> tuple[str, InlineKeyboardMarkup]:
    rec = await db.get(tg_id)
    if not rec:
        return "Пользователь не найден.", InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅ Пользователи", callback_data="admin:users")]
        ])

    plan_name, group_name, note, display_name = await _profile_labels(tg_id)
    provisioning_line = "🚀 Согласование: недоступно"
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
            f"🗂 Группа серверов: {group_name}",
            provisioning_line,
            f"⏳ Срок: {fmt_date(expiry)}",
            f"📦 Лимит трафика: {human_bytes(total) if total else 'без лимита'}",
            f"📊 Использовано: {human_bytes(up + down)}",
            f"📱 Лимит IP: {limit_ip if limit_ip else 'без лимита'}",
            f"📡 Inbounds: {', '.join(map(str, inbound_ids)) if inbound_ids else 'нет'}",
            f"🔀 Flow: {flow}",
        ]
        if note:
            lines += ["", f"📝 Заметка: {note}"]
    except XUIError as exc:
        enabled = True
        lines = [
            f"👤 {display_name or rec.email}",
            *([f"Email: {rec.email}"] if display_name else []),
            f"Telegram ID: {rec.telegram_id}",
            "",
            f"💎 Тариф: {plan_name}",
            f"🗂 Группа серверов: {group_name}",
            provisioning_line,
            "",
            f"⚠️ 3x-ui: {exc}",
        ]
        if note:
            lines += ["", f"📝 Заметка: {note}"]

    state_button = (
        InlineKeyboardButton(text="⛔ Отключить", callback_data=f"admindisable:{tg_id}")
        if enabled else
        InlineKeyboardButton(text="✅ Включить", callback_data=f"adminenable:{tg_id}")
    )
    rows = [
        [
            InlineKeyboardButton(text="⏳ Срок", callback_data=f"admin:u:expiry:{tg_id}"),
            InlineKeyboardButton(text="📦 Трафик", callback_data=f"admin:u:traffic:{tg_id}"),
        ],
        [
            InlineKeyboardButton(text="📱 Лимит IP", callback_data=f"admin:u:ip:{tg_id}"),
            InlineKeyboardButton(text="📡 Inbounds", callback_data=f"admin:u:inbounds:{tg_id}"),
        ],
        [
            InlineKeyboardButton(text="💎 Тариф", callback_data=f"admin:u:plan:{tg_id}"),
            InlineKeyboardButton(text="🗂 Группа серверов", callback_data=f"admin:u:group:{tg_id}"),
        ],
        [InlineKeyboardButton(text="▶ Применить тариф к лимитам", callback_data=f"admin:u:planapplyask:{tg_id}")],
        [InlineKeyboardButton(text="🚀 Согласование", callback_data=f"admin:u:prov:{tg_id}")],
        [InlineKeyboardButton(text="🚀 Тариф + согласование", callback_data=f"admin:u:planprovask:{tg_id}")],
        [
            InlineKeyboardButton(text="🔄 Сбросить трафик", callback_data=f"admin:u:resetask:{tg_id}"),
            InlineKeyboardButton(text="📝 Заметка", callback_data=f"admin:u:note:{tg_id}"),
        ],
        [InlineKeyboardButton(text="✏️ Имя", callback_data=f"admin:u:name:{tg_id}")],
        [InlineKeyboardButton(text="👥 Группы пользователей", callback_data=f"admin:u:audgroups:{tg_id}")],
        [InlineKeyboardButton(text="🔄 Синхронизировать Inbounds", callback_data=f"adminsync:{tg_id}")],
        [
            InlineKeyboardButton(text="➕ +30 дней", callback_data=f"adminextend:{tg_id}"),
            state_button,
        ],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admindelask:{tg_id}")],
        [InlineKeyboardButton(text="🔐 Сменить ID подписки", callback_data=f"admin:u:subrotateask:{tg_id}")],
        [InlineKeyboardButton(text="🔗 Открыть подписку", callback_data=f"adminsub:{tg_id}")],
        [InlineKeyboardButton(text="⬅ Пользователи", callback_data="admin:users")],
    ]
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


@advanced_users_router.callback_query(F.data.regexp(r"^admin:u:\d+$"))
async def user_advanced_card(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="read_only"):
        return
    await state.clear()
    tg_id = int(call.data.rsplit(":", 1)[-1])
    text, kb = await render_user(tg_id)
    await render_callback(call, text, reply_markup=kb)
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

    rows.append([InlineKeyboardButton(text="🔎 Поиск", callback_data="admin:users:search")])
    if role in {"support", "admin", "owner"}:
        rows.append([
            InlineKeyboardButton(text="☑️ Массовые действия", callback_data="admin:users:bulk"),
            InlineKeyboardButton(text="🚀 Согласовать всех", callback_data="admin:provision:all:ask"),
        ])
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
    if not await guard(call, minimum="read_only"):
        return
    await state.clear()
    tg_id = int(call.data.split(":", 1)[1])
    text, kb = await render_user(tg_id)
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
