from __future__ import annotations

import re
import sqlite3
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_ui import render_callback, render_input
from admin_auth import ROLE_LABELS, authorize_callback, authorize_message, get_admin_role
from admin_privileges import PRIVILEGES
from audit import audit_from_call, audit_from_message
from config import load_settings
from db import AdministratorRecord, Database, PaymentRecord, PromoCodeRecord
from ui_time import backup_schedule_text, end_of_day_timestamp, format_timestamp
from user_ui import user_label

settings = load_settings()
db = Database(settings.db_path)
business_router = Router(name="business_admin")

PAYMENT_STATUSES = {
    "pending": "🟡 Ожидает",
    "paid": "🟢 Оплачен",
    "refunded": "↩️ Возвращён",
    "cancelled": "⚪ Отменён",
}

PROMO_TYPES = {
    "percent": "Процент",
    "fixed": "Фиксированная сумма",
}


PROMO_STATE_LABELS = {
    "disabled": "отключён",
    "expired": "истёк",
    "limit reached": "лимит использований исчерпан",
    "active": "активен",
}


def promo_state_text(value: str) -> str:
    return PROMO_STATE_LABELS.get(value, value)

SAFE_SETTING_SPECS = {
    "trial_days": ("🗓 Дней пробного доступа", 1, 3650, "int"),
    "trial_traffic_gb": ("📦 Трафик пробного доступа, GB", 0, 100000, "int"),
    "trial_ip_limit": ("📱 Лимит IP пробного доступа", 0, 1000, "int"),
    "default_currency": ("💱 Валюта по умолчанию", None, None, "currency"),
}


class AddPaymentStates(StatesGroup):
    telegram_id = State()
    plan = State()
    amount = State()
    status = State()
    reference = State()
    review = State()


class AddPromoStates(StatesGroup):
    code = State()
    discount_type = State()
    value = State()
    plan = State()
    max_uses = State()
    expires = State()
    review = State()


class AddAdministratorStates(StatesGroup):
    telegram_id = State()
    role = State()


class EditSettingStates(StatesGroup):
    value = State()


async def guard(call: CallbackQuery, *, minimum: str | None = None) -> bool:
    ok, _ = await authorize_callback(db, settings, call, minimum=minimum)
    return ok


async def guard_message(message: Message, state: FSMContext, *, minimum: str = "admin") -> bool:
    if not message.from_user:
        await state.clear()
        return False
    ok, _ = await authorize_message(db, settings, message.from_user.id, minimum=minimum)
    if not ok:
        await state.clear()
        await render_input(message, "Недостаточно прав.")
        return False
    return True


def dashboard_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Панель администратора", callback_data="admin:home")],
    ])


def system_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Система", callback_data="admin:section:system")],
    ])


def cancel(callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✖ Отмена", callback_data=callback)],
    ])


def money(amount_minor: int, currency: str) -> str:
    value = Decimal(int(amount_minor)) / Decimal(100)
    if value == value.to_integral():
        text = str(int(value))
    else:
        text = f"{value:.2f}"
    return f"{text} {currency.upper()}"


async def default_currency() -> str:
    value = await db.get_runtime_setting("default_currency", "RUB")
    value = (value or "RUB").strip().upper()
    return value if re.fullmatch(r"[A-Z]{3}", value) else "RUB"


def parse_money(raw: str, fallback_currency: str) -> tuple[int, str]:
    text = (raw or "").strip().upper().replace(",", ".")
    parts = text.split()
    if not parts:
        raise ValueError("empty")
    currency = fallback_currency if len(parts) == 1 else parts[1]
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("currency")
    try:
        amount = Decimal(parts[0])
    except InvalidOperation as exc:
        raise ValueError("amount") from exc
    if amount < 0 or amount > Decimal("100000000"):
        raise ValueError("range")
    minor = int((amount * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return minor, currency


def utc_text(ts: int) -> str:
    return format_timestamp(ts)


# ---------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------


@business_router.callback_query(F.data == "admin:payments")
async def payments_list(call: CallbackQuery):
    if not await guard(call):
        return
    payments = await db.list_payments(limit=30)
    summary = await db.payment_summary()
    totals = await db.paid_totals_by_currency()
    rows: list[list[InlineKeyboardButton]] = []
    for item in payments:
        icon = PAYMENT_STATUSES.get(item.status, item.status).split()[0]
        user = await db.get(item.telegram_id)
        profile = await db.get_user_profile(item.telegram_id) if user else None
        label = user_label(user, profile) if user else f"TG {item.telegram_id}"
        rows.append([InlineKeyboardButton(
            text=f"{icon} #{item.id} · {label} · {money(item.amount_minor, item.currency)}",
            callback_data=f"admin:payment:{item.id}",
        )])
    rows += [
        [InlineKeyboardButton(text="➕ Добавить платёж", callback_data="admin:paymentadd:start")],
        [InlineKeyboardButton(text="⬅ Панель администратора", callback_data="admin:home")],
    ]
    paid_text = ", ".join(f"{money(v, c)}" for c, v in sorted(totals.items())) or "—"
    await render_callback(call, 
        "💳 Платежи\n\n"
        f"Всего: {await db.count_payments()}\n"
        f"🟢 Оплачено: {summary.get('paid', 0)}\n"
        f"🟡 Ожидают: {summary.get('pending', 0)}\n"
        f"↩️ Возвращено: {summary.get('refunded', 0)}\n"
        f"Выручка по оплаченным: {paid_text}\n\n"
        "Пока это внутренний журнал платежей. Интеграция с платёжным провайдером "
        "будет подключаться поверх него без изменения истории.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@business_router.callback_query(F.data.regexp(r"^admin:payment:\d+$"))
async def payment_detail(call: CallbackQuery):
    if not await guard(call):
        return
    payment_id = int(call.data.rsplit(":", 1)[-1])
    item = await db.get_payment(payment_id)
    if not item:
        await call.answer("Платёж не найден.", show_alert=True)
        return
    user = await db.get(item.telegram_id)
    profile = await db.get_user_profile(item.telegram_id) if user else None
    plan = await db.get_plan(item.plan_id) if item.plan_id else None
    lines = [
        f"💳 Платёж #{item.id}", "",
        f"Пользователь: {user_label(user, profile) if user else 'не найден'} · TG {item.telegram_id}",
        f"Тариф: {plan.name if plan else 'не привязан'}",
        f"Сумма: {money(item.amount_minor, item.currency)}",
        f"Статус: {PAYMENT_STATUSES.get(item.status, item.status)}",
        f"Провайдер: {item.provider}",
        f"Внешний ID: {item.external_id or '—'}",
        f"Создан: {utc_text(item.created_at)}",
        f"Оплачен: {utc_text(item.paid_at)}",
    ]
    if item.note:
        lines.append(f"Заметка: {item.note}")
    rows = [
        [
            InlineKeyboardButton(text="🟢 Оплачен", callback_data=f"admin:payment:status:{item.id}:paid"),
            InlineKeyboardButton(text="🟡 Ожидает", callback_data=f"admin:payment:status:{item.id}:pending"),
        ],
        [
            InlineKeyboardButton(text="↩️ Возвращён", callback_data=f"admin:payment:status:{item.id}:refunded"),
            InlineKeyboardButton(text="⚪ Отменён", callback_data=f"admin:payment:status:{item.id}:cancelled"),
        ],
        [InlineKeyboardButton(text="⬅ Платежи", callback_data="admin:payments")],
    ]
    await render_callback(call, "\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@business_router.callback_query(F.data.startswith("admin:payment:status:"))
async def payment_status(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    parts = call.data.split(":")
    payment_id = int(parts[-2])
    status = parts[-1]
    if status not in PAYMENT_STATUSES:
        await call.answer("Некорректный статус.", show_alert=True)
        return
    item = await db.get_payment(payment_id)
    if not item:
        await call.answer("Платёж не найден.", show_alert=True)
        return
    await db.set_payment_status(payment_id, status)
    await audit_from_call(
        db, call, "payment.status", target_type="payment", target_id=payment_id,
        details=f"{item.status}->{status}",
    )
    await call.answer("Статус обновлён")
    await render_callback(call, 
        f"✅ Платёж #{payment_id}: {PAYMENT_STATUSES[status]}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Открыть платёж", callback_data=f"admin:payment:{payment_id}")],
            [InlineKeyboardButton(text="⬅ Платежи", callback_data="admin:payments")],
        ]),
    )


@business_router.callback_query(F.data == "admin:paymentadd:start")
async def payment_add_start(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="admin"):
        return
    await state.clear()
    await state.set_state(AddPaymentStates.telegram_id)
    await render_callback(call, 
        "➕ Новый платёж\n\nШаг 1/5. Отправь Telegram ID существующего пользователя.",
        reply_markup=cancel("admin:paymentadd:cancel"),
    )
    await call.answer()


@business_router.message(AddPaymentStates.telegram_id)
async def payment_add_user(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    try:
        tg_id = int((message.text or "").strip())
    except ValueError:
        await render_input(message, "Нужен числовой Telegram ID.", reply_markup=cancel("admin:paymentadd:cancel"))
        return
    user = await db.get(tg_id)
    if not user:
        await render_input(message, "Пользователь с таким Telegram ID не найден в БД бота.", reply_markup=cancel("admin:paymentadd:cancel"))
        return
    profile = await db.get_user_profile(tg_id)
    await state.update_data(
        telegram_id=tg_id,
        email=user.email,
        user_label=user_label(user, profile),
    )
    plans = await db.list_plans()
    rows = [[InlineKeyboardButton(text="🚫 Без тарифа", callback_data="admin:paymentadd:plan:0")]]
    for plan in plans[:30]:
        rows.append([InlineKeyboardButton(
            text=f"{'🟢' if plan.active else '⚪'} {plan.name}",
            callback_data=f"admin:paymentadd:plan:{plan.id}",
        )])
    rows.append([InlineKeyboardButton(text="✖ Отмена", callback_data="admin:paymentadd:cancel")])
    await state.set_state(AddPaymentStates.plan)
    await render_input(message, "Шаг 2/5. Выбери тариф для привязки платежа.", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@business_router.callback_query(AddPaymentStates.plan, F.data.startswith("admin:paymentadd:plan:"))
async def payment_add_plan(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="admin"):
        return
    plan_id = int(call.data.rsplit(":", 1)[-1])
    await state.update_data(plan_id=plan_id or None)
    await state.set_state(AddPaymentStates.amount)
    currency = await default_currency()
    await render_callback(call, 
        "Шаг 3/5. Отправь сумму.\n\n"
        f"Например: 299 или 4.99 USD\nВалюта по умолчанию: {currency}",
        reply_markup=cancel("admin:paymentadd:cancel"),
    )
    await call.answer()


@business_router.message(AddPaymentStates.amount)
async def payment_add_amount(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    try:
        amount_minor, currency = parse_money(message.text or "", await default_currency())
    except ValueError:
        await render_input(message, "Не понял сумму. Пример: 299 RUB или 4.99 USD", reply_markup=cancel("admin:paymentadd:cancel"))
        return
    await state.update_data(amount_minor=amount_minor, currency=currency)
    await state.set_state(AddPaymentStates.status)
    await render_input(message, 
        "Шаг 4/5. Начальный статус платежа?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🟢 Оплачен", callback_data="admin:paymentadd:status:paid"),
                InlineKeyboardButton(text="🟡 Ожидает", callback_data="admin:paymentadd:status:pending"),
            ],
            [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:paymentadd:cancel")],
        ]),
    )


@business_router.callback_query(AddPaymentStates.status, F.data.startswith("admin:paymentadd:status:"))
async def payment_add_status(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="admin"):
        return
    status = call.data.rsplit(":", 1)[-1]
    if status not in {"paid", "pending"}:
        await call.answer("Некорректный статус", show_alert=True)
        return
    await state.update_data(status=status)
    await state.set_state(AddPaymentStates.reference)
    await render_callback(call, 
        "Шаг 5/5. Отправь reference/ID платежа или `-`, если его нет.",
        reply_markup=cancel("admin:paymentadd:cancel"),
    )
    await call.answer()


@business_router.message(AddPaymentStates.reference)
async def payment_add_reference(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    ref = (message.text or "").strip()
    if ref == "-":
        ref = ""
    if len(ref) > 160:
        await render_input(message, "Внешний ID слишком длинный (максимум 160 символов).", reply_markup=cancel("admin:paymentadd:cancel"))
        return
    await state.update_data(external_id=ref)
    data = await state.get_data()
    plan = await db.get_plan(data.get("plan_id")) if data.get("plan_id") else None
    await state.set_state(AddPaymentStates.review)
    await render_input(message, 
        "Проверь платёж:\n\n"
        f"Пользователь: {data.get('user_label') or data['email']} · TG {data['telegram_id']}\n"
        f"Тариф: {plan.name if plan else 'не привязан'}\n"
        f"Сумма: {money(data['amount_minor'], data['currency'])}\n"
        f"Статус: {PAYMENT_STATUSES[data['status']]}\n"
        f"Внешний ID: {ref or '—'}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Сохранить", callback_data="admin:paymentadd:save")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:paymentadd:cancel")],
        ]),
    )


@business_router.callback_query(AddPaymentStates.review, F.data == "admin:paymentadd:save")
async def payment_add_save(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="admin"):
        return
    data = await state.get_data()
    payment_id = await db.create_payment(
        telegram_id=int(data["telegram_id"]), plan_id=data.get("plan_id"),
        amount_minor=int(data["amount_minor"]), currency=str(data["currency"]),
        status=str(data["status"]), external_id=str(data.get("external_id") or ""),
        created_by=call.from_user.id,
    )
    await audit_from_call(
        db, call, "payment.create", target_type="payment", target_id=payment_id,
        details=f"tg={data['telegram_id']}; amount={data['amount_minor']} {data['currency']}; status={data['status']}",
    )
    await state.clear()
    await call.answer("Платёж сохранён")
    await render_callback(call, 
        f"✅ Платёж #{payment_id} создан.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Открыть", callback_data=f"admin:payment:{payment_id}")],
            [InlineKeyboardButton(text="⬅ Платежи", callback_data="admin:payments")],
        ]),
    )


@business_router.callback_query(F.data == "admin:paymentadd:cancel")
async def payment_add_cancel(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="admin"):
        return
    await state.clear()
    await payments_list(call)


# ---------------------------------------------------------------------
# Promo codes
# ---------------------------------------------------------------------


def promo_value_text(item: PromoCodeRecord) -> str:
    if item.discount_type == "percent":
        return f"{item.value}%"
    return money(item.value, item.currency)


def promo_state(item: PromoCodeRecord) -> tuple[str, str]:
    now = int(time.time())
    if not item.active:
        return "⚪", "disabled"
    if item.expires_at and item.expires_at < now:
        return "🔴", "expired"
    if item.max_uses and item.uses_count >= item.max_uses:
        return "🔴", "limit reached"
    return "🟢", "active"


@business_router.callback_query(F.data == "admin:promo")
async def promo_list(call: CallbackQuery):
    if not await guard(call):
        return
    promos = await db.list_promo_codes()
    rows = []
    active = 0
    for item in promos[:40]:
        icon, state = promo_state(item)
        active += 1 if state == "active" else 0
        rows.append([InlineKeyboardButton(
            text=f"{icon} {item.code} · {promo_value_text(item)}",
            callback_data=f"admin:promo:{item.id}",
        )])
    rows += [
        [InlineKeyboardButton(text="➕ Добавить промокод", callback_data="admin:promoadd:start")],
        [InlineKeyboardButton(text="⬅ Панель администратора", callback_data="admin:home")],
    ]
    await render_callback(call, 
        "🎟 Промокоды\n\n"
        f"Промокодов: {len(promos)} · активных: {active}\n\n"
        "Каталог готов для будущей оплаты. Пока промокоды не применяются автоматически при создании доступа.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@business_router.callback_query(F.data.regexp(r"^admin:promo:\d+$"))
async def promo_detail(call: CallbackQuery):
    if not await guard(call):
        return
    promo_id = int(call.data.rsplit(":", 1)[-1])
    item = await db.get_promo_code(promo_id)
    if not item:
        await call.answer("Промокод не найден.", show_alert=True)
        return
    icon, state = promo_state(item)
    plan = await db.get_plan(item.plan_id) if item.plan_id else None
    uses = f"{item.uses_count}/{item.max_uses}" if item.max_uses else f"{item.uses_count}/∞"
    toggle = "⛔ Отключить" if item.active else "✅ Включить"
    await render_callback(call, 
        f"🎟 {item.code}\n\n"
        f"Статус: {icon} {promo_state_text(state)}\n"
        f"Скидка: {promo_value_text(item)}\n"
        f"Тариф: {plan.name if plan else 'все тарифы'}\n"
        f"Использовано: {uses}\n"
        f"Действует до: {utc_text(item.expires_at) if item.expires_at else 'без срока'}\n"
        f"Создан: {utc_text(item.created_at)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=toggle, callback_data=f"admin:promo:toggle:{item.id}")],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:promo:deleteask:{item.id}")],
            [InlineKeyboardButton(text="⬅ Промокоды", callback_data="admin:promo")],
        ]),
    )
    await call.answer()


@business_router.callback_query(F.data == "admin:promoadd:start")
async def promo_add_start(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="admin"):
        return
    await state.clear()
    await state.set_state(AddPromoStates.code)
    await render_callback(call, 
        "➕ Новый промокод\n\nШаг 1/6. Отправь код, например: WELCOME20",
        reply_markup=cancel("admin:promoadd:cancel"),
    )
    await call.answer()


@business_router.message(AddPromoStates.code)
async def promo_add_code(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    code = (message.text or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9_-]{3,32}", code):
        await render_input(message, "Код: 3–32 символа, A-Z, 0-9, `_` или `-`.", reply_markup=cancel("admin:promoadd:cancel"))
        return
    await state.update_data(code=code)
    await state.set_state(AddPromoStates.discount_type)
    await render_input(message, 
        "Шаг 2/6. Тип скидки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Процент", callback_data="admin:promoadd:type:percent"),
                InlineKeyboardButton(text="💵 Сумма", callback_data="admin:promoadd:type:fixed"),
            ],
            [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:promoadd:cancel")],
        ]),
    )


@business_router.callback_query(AddPromoStates.discount_type, F.data.startswith("admin:promoadd:type:"))
async def promo_add_type(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="admin"):
        return
    kind = call.data.rsplit(":", 1)[-1]
    if kind not in PROMO_TYPES:
        await call.answer("Некорректный тип", show_alert=True)
        return
    await state.update_data(discount_type=kind)
    await state.set_state(AddPromoStates.value)
    currency = await default_currency()
    prompt = "Шаг 3/6. Процент скидки от 1 до 100." if kind == "percent" else (
        f"Шаг 3/6. Сумма скидки, например 100 или 4.99 USD. По умолчанию {currency}."
    )
    await render_callback(call, prompt, reply_markup=cancel("admin:promoadd:cancel"))
    await call.answer()


@business_router.message(AddPromoStates.value)
async def promo_add_value(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    data = await state.get_data()
    if data.get("discount_type") == "percent":
        try:
            value = int((message.text or "").strip())
        except ValueError:
            value = 0
        if not 1 <= value <= 100:
            await render_input(message, "Процент должен быть от 1 до 100.", reply_markup=cancel("admin:promoadd:cancel"))
            return
        await state.update_data(value=value, currency=await default_currency())
    else:
        try:
            value, currency = parse_money(message.text or "", await default_currency())
        except ValueError:
            await render_input(message, "Не понял сумму. Пример: 100 RUB или 4.99 USD", reply_markup=cancel("admin:promoadd:cancel"))
            return
        if value <= 0:
            await render_input(message, "Скидка должна быть больше нуля.", reply_markup=cancel("admin:promoadd:cancel"))
            return
        await state.update_data(value=value, currency=currency)
    plans = await db.list_plans()
    rows = [[InlineKeyboardButton(text="🌐 Все тарифы", callback_data="admin:promoadd:plan:0")]]
    for plan in plans[:30]:
        rows.append([InlineKeyboardButton(text=f"💎 {plan.name}", callback_data=f"admin:promoadd:plan:{plan.id}")])
    rows.append([InlineKeyboardButton(text="✖ Отмена", callback_data="admin:promoadd:cancel")])
    await state.set_state(AddPromoStates.plan)
    await render_input(message, "Шаг 4/6. Ограничить промокод конкретным тарифом?", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@business_router.callback_query(AddPromoStates.plan, F.data.startswith("admin:promoadd:plan:"))
async def promo_add_plan(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="admin"):
        return
    plan_id = int(call.data.rsplit(":", 1)[-1])
    await state.update_data(plan_id=plan_id or None)
    await state.set_state(AddPromoStates.max_uses)
    await render_callback(call, 
        "Шаг 5/6. Максимальное количество использований. `0` = без ограничения.",
        reply_markup=cancel("admin:promoadd:cancel"),
    )
    await call.answer()


@business_router.message(AddPromoStates.max_uses)
async def promo_add_max_uses(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    try:
        max_uses = int((message.text or "").strip())
    except ValueError:
        max_uses = -1
    if max_uses < 0 or max_uses > 10_000_000:
        await render_input(message, "Нужно целое число от 0 до 10000000.", reply_markup=cancel("admin:promoadd:cancel"))
        return
    await state.update_data(max_uses=max_uses)
    await state.set_state(AddPromoStates.expires)
    await render_input(message, 
        "Шаг 6/6. Срок действия: `0` = без срока или дата `YYYY-MM-DD` (MSK).",
        reply_markup=cancel("admin:promoadd:cancel"),
    )


@business_router.message(AddPromoStates.expires)
async def promo_add_expires(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    raw = (message.text or "").strip()
    if raw == "0":
        expires_at = 0
    else:
        try:
            expires_at = end_of_day_timestamp(raw)
        except ValueError:
            await render_input(message, "Формат даты: YYYY-MM-DD или 0.", reply_markup=cancel("admin:promoadd:cancel"))
            return
        if expires_at <= int(time.time()):
            await render_input(message, "Дата должна быть в будущем.", reply_markup=cancel("admin:promoadd:cancel"))
            return
    await state.update_data(expires_at=expires_at)
    data = await state.get_data()
    plan = await db.get_plan(data.get("plan_id")) if data.get("plan_id") else None
    display_value = f"{data['value']}%" if data["discount_type"] == "percent" else money(data["value"], data["currency"])
    await state.set_state(AddPromoStates.review)
    await render_input(message, 
        "Проверь промокод:\n\n"
        f"Код: {data['code']}\n"
        f"Скидка: {display_value}\n"
        f"Тариф: {plan.name if plan else 'все тарифы'}\n"
        f"Максимум использований: {data['max_uses'] or '∞'}\n"
        f"Действует до: {utc_text(expires_at) if expires_at else 'без срока'}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Сохранить", callback_data="admin:promoadd:save")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:promoadd:cancel")],
        ]),
    )


@business_router.callback_query(AddPromoStates.review, F.data == "admin:promoadd:save")
async def promo_add_save(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="admin"):
        return
    data = await state.get_data()
    try:
        promo_id = await db.create_promo_code(
            code=data["code"], discount_type=data["discount_type"], value=int(data["value"]),
            currency=data["currency"], plan_id=data.get("plan_id"),
            max_uses=int(data["max_uses"]), expires_at=int(data["expires_at"]),
        )
    except sqlite3.IntegrityError:
        await call.answer("Промокод с таким кодом уже существует.", show_alert=True)
        return
    await audit_from_call(
        db, call, "promo.create", target_type="promo", target_id=promo_id,
        details=f"code={data['code']}; type={data['discount_type']}; value={data['value']}",
    )
    await state.clear()
    await call.answer("Промокод создан")
    await render_callback(call, 
        f"✅ Промокод {data['code']} создан.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Открыть", callback_data=f"admin:promo:{promo_id}")],
            [InlineKeyboardButton(text="⬅ Промокоды", callback_data="admin:promo")],
        ]),
    )


@business_router.callback_query(F.data == "admin:promoadd:cancel")
async def promo_add_cancel(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="admin"):
        return
    await state.clear()
    await promo_list(call)


@business_router.callback_query(F.data.startswith("admin:promo:toggle:"))
async def promo_toggle(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    promo_id = int(call.data.rsplit(":", 1)[-1])
    item = await db.get_promo_code(promo_id)
    if not item:
        await call.answer("Промокод не найден.", show_alert=True)
        return
    new_state = not bool(item.active)
    await db.set_promo_active(promo_id, new_state)
    await audit_from_call(
        db, call, "promo.toggle", target_type="promo", target_id=promo_id,
        details=f"active={int(new_state)}",
    )
    await call.answer("Статус изменён")
    await render_callback(call, 
        f"✅ {item.code}: {'включён' if new_state else 'отключён'}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Открыть промокод", callback_data=f"admin:promo:{promo_id}")],
            [InlineKeyboardButton(text="⬅ Промокоды", callback_data="admin:promo")],
        ]),
    )


@business_router.callback_query(F.data.startswith("admin:promo:deleteask:"))
async def promo_delete_ask(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    promo_id = int(call.data.rsplit(":", 1)[-1])
    await render_callback(call, 
        "Удалить промокод? История платежей не затрагивается.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ Да, удалить", callback_data=f"admin:promo:delete:{promo_id}")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:promo:{promo_id}")],
        ]),
    )
    await call.answer()


@business_router.callback_query(F.data.startswith("admin:promo:delete:"))
async def promo_delete(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    promo_id = int(call.data.rsplit(":", 1)[-1])
    item = await db.get_promo_code(promo_id)
    if not item:
        await call.answer("Промокод не найден.", show_alert=True)
        return
    await db.delete_promo_code(promo_id)
    await audit_from_call(db, call, "promo.delete", target_type="promo", target_id=promo_id, details=f"code={item.code}")
    await promo_list(call)


# ---------------------------------------------------------------------
# Administrators / roles
# ---------------------------------------------------------------------


def role_button(role: str) -> str:
    return {
        "owner": "👑 Owner",
        "admin": "🛡 Administrator",
        "support": "🧑‍💻 Support",
        "read_only": "👁 Read-only",
    }.get(role, role)


@business_router.callback_query(F.data == "admin:administrators")
async def administrators_list(call: CallbackQuery):
    if not await guard(call, minimum="owner"):
        return
    db_admins = {a.telegram_id: a for a in await db.list_administrators()}
    all_ids = sorted(set(settings.admin_telegram_ids) | set(db_admins))
    rows = []
    for tg_id in all_ids:
        if tg_id in settings.admin_telegram_ids:
            text = f"👑 TG {tg_id} · Owner · локальная конфигурация"
        else:
            rec = db_admins[tg_id]
            text = f"{'🟢' if rec.enabled else '⚪'} TG {tg_id} · {ROLE_LABELS.get(rec.role, rec.role)}"
        rows.append([InlineKeyboardButton(text=text, callback_data=f"admin:administrator:{tg_id}")])
    rows += [
        [InlineKeyboardButton(text="➕ Добавить администратора", callback_data="admin:administratoradd:start")],
        [InlineKeyboardButton(text="🔐 Роли и права", callback_data="admin:privileges")],
        [InlineKeyboardButton(text="⬅ Система", callback_data="admin:section:system")],
    ]
    await render_callback(call, 
        "👮 Администраторы\n\n"
        "Owner из локальной конфигурации — аварийный владелец; его нельзя отключить из Telegram.\n\n"
        "Роли:\n"
        "👑 Owner — полный доступ и управление администраторами\n"
        "🛡 Administrator — все рабочие операции и безопасные настройки\n"
        "🧑‍💻 Support — просмотр админки + операции с пользователями\n"
        "👁 Read-only — просмотр без изменений",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@business_router.callback_query(F.data == "admin:privileges")
async def roles_privileges(call: CallbackQuery):
    if not await guard(call, minimum="owner"):
        return
    role_order = ("read_only", "support", "admin", "owner")
    role_icons = {
        "read_only": "👁",
        "support": "🧑‍💻",
        "admin": "🛡",
        "owner": "👑",
    }
    lines = [
        "🔐 Роли и права",
        "",
        "Четыре роли фиксированы. Каждое право задаёт минимально допустимую роль.",
        "Более высокая роль наследует права нижестоящих ролей.",
        "Технические идентификаторы прав остаются внутренней частью RBAC.",
    ]
    for role in role_order:
        lines += ["", f"{role_icons[role]} {ROLE_LABELS[role]}"]
        for item in PRIVILEGES:
            if item.minimum_role == role:
                lines.append(f"• {item.label}")
    await render_callback(
        call,
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅ Администраторы", callback_data="admin:administrators")],
        ]),
    )
    await call.answer()


@business_router.callback_query(F.data.regexp(r"^admin:administrator:\d+$"))
async def administrator_detail(call: CallbackQuery):
    if not await guard(call, minimum="owner"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    if tg_id in settings.admin_telegram_ids:
        await render_callback(call, 
            f"👑 TG {tg_id}\n\nРоль: Owner\nИсточник: локальная конфигурация\nСтатус: 🟢 включён\n\n"
            "Этот владелец защищён от изменения через Telegram.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅ Администраторы", callback_data="admin:administrators")],
            ]),
        )
        await call.answer()
        return
    rec = await db.get_administrator(tg_id)
    if not rec:
        await call.answer("Администратор не найден.", show_alert=True)
        return
    rows = [
        [
            InlineKeyboardButton(text="👑 Owner", callback_data=f"admin:administrator:role:{tg_id}:owner"),
            InlineKeyboardButton(text="🛡 Administrator", callback_data=f"admin:administrator:role:{tg_id}:admin"),
        ],
        [
            InlineKeyboardButton(text="🧑‍💻 Support", callback_data=f"admin:administrator:role:{tg_id}:support"),
            InlineKeyboardButton(text="👁 Read-only", callback_data=f"admin:administrator:role:{tg_id}:read_only"),
        ],
        [InlineKeyboardButton(
            text="⛔ Отключить" if rec.enabled else "✅ Включить",
            callback_data=f"admin:administrator:toggle:{tg_id}",
        )],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:administrator:deleteask:{tg_id}")],
        [InlineKeyboardButton(text="⬅ Администраторы", callback_data="admin:administrators")],
    ]
    await render_callback(call, 
        f"👮 TG {tg_id}\n\n"
        f"Роль: {role_button(rec.role)}\n"
        f"Статус: {'🟢 включён' if rec.enabled else '⚪ отключён'}\n"
        f"Добавил: {f'TG {rec.added_by}' if rec.added_by else 'система'}\n"
        f"Создан: {utc_text(rec.created_at)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@business_router.callback_query(F.data == "admin:administratoradd:start")
async def administrator_add_start(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="owner"):
        return
    await state.clear()
    await state.set_state(AddAdministratorStates.telegram_id)
    await render_callback(call, 
        "➕ Новый администратор\n\nОтправь Telegram ID.",
        reply_markup=cancel("admin:administratoradd:cancel"),
    )
    await call.answer()


@business_router.message(AddAdministratorStates.telegram_id)
async def administrator_add_id(message: Message, state: FSMContext):
    if not await guard_message(message, state, minimum="owner"):
        return
    try:
        tg_id = int((message.text or "").strip())
    except ValueError:
        await render_input(message, "Нужен числовой Telegram ID.", reply_markup=cancel("admin:administratoradd:cancel"))
        return
    if tg_id <= 0:
        await render_input(message, "Telegram ID должен быть положительным.", reply_markup=cancel("admin:administratoradd:cancel"))
        return
    if tg_id in settings.admin_telegram_ids:
        await render_input(message, "Этот Telegram ID уже является аварийным Owner из локальной конфигурации.", reply_markup=cancel("admin:administratoradd:cancel"))
        return
    await state.update_data(telegram_id=tg_id)
    await state.set_state(AddAdministratorStates.role)
    await render_input(message, 
        "Выбери роль:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👑 Owner", callback_data="admin:administratoradd:role:owner"),
                InlineKeyboardButton(text="🛡 Administrator", callback_data="admin:administratoradd:role:admin"),
            ],
            [
                InlineKeyboardButton(text="🧑‍💻 Support", callback_data="admin:administratoradd:role:support"),
                InlineKeyboardButton(text="👁 Read-only", callback_data="admin:administratoradd:role:read_only"),
            ],
            [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:administratoradd:cancel")],
        ]),
    )


@business_router.callback_query(AddAdministratorStates.role, F.data.startswith("admin:administratoradd:role:"))
async def administrator_add_role(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="owner"):
        return
    role = call.data.rsplit(":", 1)[-1]
    if role not in ROLE_LABELS:
        await call.answer("Некорректная роль", show_alert=True)
        return
    data = await state.get_data()
    tg_id = int(data["telegram_id"])
    await db.upsert_administrator(
        telegram_id=tg_id, role=role, enabled=True, added_by=call.from_user.id,
    )
    await audit_from_call(
        db, call, "administrator.upsert", target_type="administrator", target_id=tg_id,
        details=f"role={role}; enabled=1",
    )
    await state.clear()
    await call.answer("Администратор сохранён")
    await render_callback(call, 
        f"✅ TG {tg_id} · {ROLE_LABELS[role]}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Открыть", callback_data=f"admin:administrator:{tg_id}")],
            [InlineKeyboardButton(text="⬅ Администраторы", callback_data="admin:administrators")],
        ]),
    )


@business_router.callback_query(F.data == "admin:administratoradd:cancel")
async def administrator_add_cancel(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="owner"):
        return
    await state.clear()
    await administrators_list(call)


@business_router.callback_query(F.data.startswith("admin:administrator:role:"))
async def administrator_role(call: CallbackQuery):
    if not await guard(call, minimum="owner"):
        return
    parts = call.data.split(":")
    tg_id = int(parts[-2])
    role = parts[-1]
    if role not in ROLE_LABELS or tg_id in settings.admin_telegram_ids:
        await call.answer("Изменение запрещено.", show_alert=True)
        return
    rec = await db.get_administrator(tg_id)
    if not rec:
        await call.answer("Администратор не найден.", show_alert=True)
        return
    await db.upsert_administrator(telegram_id=tg_id, role=role, enabled=bool(rec.enabled), added_by=rec.added_by)
    await audit_from_call(db, call, "administrator.role", target_type="administrator", target_id=tg_id, details=f"{rec.role}->{role}")
    await call.answer("Роль обновлена")
    await render_callback(call, 
        f"✅ TG {tg_id}: {ROLE_LABELS[role]}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Открыть", callback_data=f"admin:administrator:{tg_id}")],
            [InlineKeyboardButton(text="⬅ Администраторы", callback_data="admin:administrators")],
        ]),
    )


@business_router.callback_query(F.data.startswith("admin:administrator:toggle:"))
async def administrator_toggle(call: CallbackQuery):
    if not await guard(call, minimum="owner"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    if tg_id in settings.admin_telegram_ids:
        await call.answer("Аварийного Owner из локальной конфигурации нельзя отключить.", show_alert=True)
        return
    rec = await db.get_administrator(tg_id)
    if not rec:
        await call.answer("Администратор не найден.", show_alert=True)
        return
    new_enabled = not bool(rec.enabled)
    await db.set_administrator_enabled(tg_id, new_enabled)
    await audit_from_call(db, call, "administrator.toggle", target_type="administrator", target_id=tg_id, details=f"enabled={int(new_enabled)}")
    await call.answer("Статус изменён")
    await render_callback(call, 
        f"✅ TG {tg_id}: {'включён' if new_enabled else 'отключён'}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Открыть", callback_data=f"admin:administrator:{tg_id}")],
            [InlineKeyboardButton(text="⬅ Администраторы", callback_data="admin:administrators")],
        ]),
    )


@business_router.callback_query(F.data.startswith("admin:administrator:deleteask:"))
async def administrator_delete_ask(call: CallbackQuery):
    if not await guard(call, minimum="owner"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    if tg_id in settings.admin_telegram_ids:
        await call.answer("Аварийного Owner из локальной конфигурации нельзя удалить.", show_alert=True)
        return
    await render_callback(call, 
        f"Удалить администратора TG {tg_id}?\n\n"
        "Административный доступ через эту запись будет удалён; пользовательские данные и 3x-ui не изменятся.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ Да, удалить", callback_data=f"admin:administrator:delete:{tg_id}")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:administrator:{tg_id}")],
        ]),
    )
    await call.answer()


@business_router.callback_query(F.data.startswith("admin:administrator:delete:"))
async def administrator_delete(call: CallbackQuery):
    if not await guard(call, minimum="owner"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    if tg_id in settings.admin_telegram_ids:
        await call.answer("Аварийного Owner из локальной конфигурации нельзя удалить.", show_alert=True)
        return
    await db.delete_administrator(tg_id)
    await audit_from_call(db, call, "administrator.delete", target_type="administrator", target_id=tg_id)
    await administrators_list(call)


# ---------------------------------------------------------------------
# Safe runtime settings
# ---------------------------------------------------------------------


async def effective_setting(key: str) -> str:
    defaults = {
        "trial_days": str(settings.test_days),
        "trial_traffic_gb": str(settings.test_traffic_gb),
        "trial_ip_limit": str(settings.test_ip_limit),
        "default_currency": "RUB",
    }
    return str(await db.get_runtime_setting(key, defaults[key]) or defaults[key])


@business_router.callback_query(F.data == "admin:settings")
async def settings_view(call: CallbackQuery):
    if not await guard(call):
        return
    values = {key: await effective_setting(key) for key in SAFE_SETTING_SPECS}
    rows = [
        [InlineKeyboardButton(text=f"🗓 Дней пробного доступа · {values['trial_days']}", callback_data="admin:settings:edit:trial_days")],
        [InlineKeyboardButton(text=f"📦 Трафик пробного доступа · {values['trial_traffic_gb']} GB", callback_data="admin:settings:edit:trial_traffic_gb")],
        [InlineKeyboardButton(text=f"📱 Лимит IP пробного доступа · {values['trial_ip_limit']}", callback_data="admin:settings:edit:trial_ip_limit")],
        [InlineKeyboardButton(text=f"💱 Валюта по умолчанию · {values['default_currency']}", callback_data="admin:settings:edit:default_currency")],
        [InlineKeyboardButton(text="⬅ Система", callback_data="admin:section:system")],
    ]
    await render_callback(call, 
        "🔧 Настройки\n\n"
        "Безопасные настройки — применяются без изменения локальной конфигурации:\n"
        f"🗓 Дней пробного доступа: {values['trial_days']}\n"
        f"📦 Трафик пробного доступа: {values['trial_traffic_gb']} GB\n"
        f"📱 Лимит IP пробного доступа: {values['trial_ip_limit']}\n"
        f"💱 Валюта по умолчанию: {values['default_currency']}\n\n"
        "Окружение (только чтение):\n"
        f"💾 Резервные копии: {'включены' if settings.backup_enabled else 'выключены'}, {backup_schedule_text(settings.backup_hour_utc)}, хранить {settings.backup_keep}\n"
        f"🔐 Проверка TLS: {'включена' if settings.verify_tls else 'выключена'}\n"
        f"🖥 Master-сервер: {settings.master_name}\n\n"
        "BOT_TOKEN, PANEL_API_TOKEN и другие секреты через Telegram не редактируются.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@business_router.callback_query(F.data.startswith("admin:settings:edit:"))
async def settings_edit(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="admin"):
        return
    key = call.data.rsplit(":", 1)[-1]
    spec = SAFE_SETTING_SPECS.get(key)
    if not spec:
        await call.answer("Неизвестная настройка.", show_alert=True)
        return
    await state.clear()
    await state.update_data(setting_key=key)
    await state.set_state(EditSettingStates.value)
    current = await effective_setting(key)
    hint = "трёхбуквенный ISO-код, например RUB или USD" if spec[3] == "currency" else f"целое число {spec[1]}..{spec[2]}"
    await render_callback(call, 
        f"{spec[0]}\n\nТекущее значение: {current}\nОтправь новое значение ({hint}).",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩ Сбросить к значению локальной конфигурации", callback_data=f"admin:settings:reset:{key}")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:settings:cancel")],
        ]),
    )
    await call.answer()


@business_router.message(EditSettingStates.value)
async def settings_value(message: Message, state: FSMContext):
    if not await guard_message(message, state, minimum="admin"):
        return
    data = await state.get_data()
    key = str(data.get("setting_key") or "")
    spec = SAFE_SETTING_SPECS.get(key)
    if not spec:
        await state.clear()
        await render_input(message, "Настройка не найдена.", reply_markup=system_back())
        return
    raw = (message.text or "").strip().upper() if spec[3] == "currency" else (message.text or "").strip()
    if spec[3] == "currency":
        if not re.fullmatch(r"[A-Z]{3}", raw):
            await render_input(message, "Нужен трёхбуквенный код валюты, например RUB или USD.", reply_markup=cancel("admin:settings:cancel"))
            return
        value = raw
    else:
        try:
            parsed = int(raw)
        except ValueError:
            await render_input(message, "Нужно целое число.", reply_markup=cancel("admin:settings:cancel"))
            return
        if parsed < spec[1] or parsed > spec[2]:
            await render_input(message, f"Допустимый диапазон: {spec[1]}..{spec[2]}.", reply_markup=cancel("admin:settings:cancel"))
            return
        value = str(parsed)
    old = await effective_setting(key)
    await db.set_runtime_setting(key, value, updated_by=message.from_user.id)
    await audit_from_message(db, message, "settings.set", target_type="setting", target_id=key, details=f"{old}->{value}")
    await state.clear()
    await render_input(message, 
        f"✅ {spec[0]}: {value}\nИзменение применяется к новым операциям сразу.",
        reply_markup=system_back(),
    )


@business_router.callback_query(F.data.startswith("admin:settings:reset:"))
async def settings_reset(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="admin"):
        return
    key = call.data.rsplit(":", 1)[-1]
    if key not in SAFE_SETTING_SPECS:
        await call.answer("Неизвестная настройка.", show_alert=True)
        return
    old = await effective_setting(key)
    await db.delete_runtime_setting(key)
    new = await effective_setting(key)
    await audit_from_call(db, call, "settings.reset", target_type="setting", target_id=key, details=f"{old}->{new}")
    await state.clear()
    await settings_view(call)


@business_router.callback_query(F.data == "admin:settings:cancel")
async def settings_cancel(call: CallbackQuery, state: FSMContext):
    if not await guard(call):
        return
    await state.clear()
    await settings_view(call)
