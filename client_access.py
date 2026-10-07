from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_ui import render_callback
from commerce import CommerceService
from config import load_settings
from db import Database
from ui_time import format_timestamp
from version import APP_VERSION
from xui import XUIClient, XUIError


settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
commerce = CommerceService(db)

client_access_router = Router(name="client_access")


def is_allowed(tg_id: int) -> bool:
    # v5 pilot boundary. Public signup remains closed until abuse/rate-limit
    # controls and the full checkout provider flow are ready.
    return (
        tg_id in settings.allowed_telegram_ids
        or tg_id in settings.admin_telegram_ids
    )


def sub_url(sub_id: str) -> str:
    template = (
        settings.compat_subscription_url_template
        or settings.subscription_url_template
    )
    return template.format(sub_id=sub_id)


def human_bytes(value: int) -> str:
    n = float(max(0, int(value or 0)))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{int(n)} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def money_text(amount_minor: int, currency: str) -> str:
    amount = max(0, int(amount_minor))
    whole, minor = divmod(amount, 100)
    value = f"{whole}" if minor == 0 else f"{whole}.{minor:02d}"
    return f"{value} {(currency or '').upper()}".strip()


def portal_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👤 Профиль", callback_data="client:profile"),
            InlineKeyboardButton(text="🌐 Моя подписка", callback_data="client:subscription"),
        ],
        [
            InlineKeyboardButton(text="💳 Купить / продлить", callback_data="client:buy"),
            InlineKeyboardButton(text="📊 Трафик", callback_data="client:traffic"),
        ],
        [
            InlineKeyboardButton(text="📱 Устройства", callback_data="client:devices"),
            InlineKeyboardButton(text="🆘 Помощь", callback_data="client:help"),
        ],
    ])


def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅ Личный кабинет", callback_data="client:home")
    ]])


async def guard_message(message: Message) -> bool:
    if not message.from_user or not is_allowed(message.from_user.id):
        await message.answer("Нет доступа.")
        return False
    return True


async def guard_callback(call: CallbackQuery) -> bool:
    if not call.from_user or not is_allowed(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return False
    return True


async def portal_text(tg_id: int) -> str:
    rec = await db.get(tg_id)
    if rec is None:
        return (
            f"Личный кабинет · v{APP_VERSION}\n\n"
            "Доступ пока не оформлен. Публичная регистрация ещё закрыта; "
            "обратитесь в поддержку для подключения."
        )
    profile = await db.get_user_profile(tg_id)
    plan = await db.get_plan(profile.plan_id) if profile and profile.plan_id else None
    return (
        f"Личный кабинет · v{APP_VERSION}\n\n"
        f"👤 {getattr(profile, 'display_name', '') or rec.email}\n"
        f"💎 Тариф: {plan.name if plan else 'не назначен'}\n"
        f"🌐 Подписка: активна"
    )


async def render_home(call: CallbackQuery) -> None:
    await render_callback(
        call,
        await portal_text(call.from_user.id),
        reply_markup=portal_menu(),
    )


@client_access_router.message(CommandStart())
async def start(message: Message):
    if not await guard_message(message):
        return
    await message.answer(
        await portal_text(message.from_user.id),
        reply_markup=portal_menu(),
    )


@client_access_router.callback_query(F.data == "client:home")
async def home_cb(call: CallbackQuery):
    if not await guard_callback(call):
        return
    await render_home(call)
    await call.answer()


@client_access_router.callback_query(F.data == "client:profile")
async def profile_cb(call: CallbackQuery):
    if not await guard_callback(call):
        return
    rec = await db.get(call.from_user.id)
    if rec is None:
        text = "👤 Профиль\n\nДоступ пока не оформлен."
    else:
        profile = await db.get_user_profile(call.from_user.id)
        plan = await db.get_plan(profile.plan_id) if profile and profile.plan_id else None
        expiry = format_timestamp(
            int(rec.expiry_time or 0),
            milliseconds=True,
            empty="без срока",
        )
        text = (
            "👤 Профиль\n\n"
            f"Имя: {getattr(profile, 'display_name', '') or '—'}\n"
            f"Аккаунт: {rec.email}\n"
            f"Тариф: {plan.name if plan else 'не назначен'}\n"
            f"Срок: {expiry}"
        )
    await render_callback(call, text, reply_markup=back_menu())
    await call.answer()


@client_access_router.message(Command("subscription"))
async def subscription_cmd(message: Message):
    if not await guard_message(message):
        return
    rec = await db.get(message.from_user.id)
    await message.answer(
        sub_url(rec.sub_id) if rec else "Подписка пока не оформлена.",
        reply_markup=portal_menu(),
    )


@client_access_router.callback_query(F.data == "client:subscription")
async def subscription_cb(call: CallbackQuery):
    if not await guard_callback(call):
        return
    rec = await db.get(call.from_user.id)
    text = (
        "🌐 Моя подписка\n\n"
        + (sub_url(rec.sub_id) if rec else "Подписка пока не оформлена.")
    )
    await render_callback(call, text, reply_markup=back_menu())
    await call.answer()


@client_access_router.callback_query(F.data == "client:traffic")
async def traffic_cb(call: CallbackQuery):
    if not await guard_callback(call):
        return
    rec = await db.get(call.from_user.id)
    if rec is None:
        text = "📊 Трафик\n\nДоступ пока не оформлен."
    else:
        try:
            obj = await xui.get_client(rec.email)
            client = obj.get("client", obj)
            traffic = await xui.traffic(rec.email)
            up = int(traffic.get("up") or traffic.get("uplink") or 0)
            down = int(traffic.get("down") or traffic.get("downlink") or 0)
            total = int(client.get("totalGB") or 0)
            used = up + down
            text = (
                "📊 Трафик\n\n"
                f"Использовано: {human_bytes(used)}\n"
                f"Лимит: {human_bytes(total) if total else 'без лимита'}\n"
                f"Отправлено: {human_bytes(up)}\n"
                f"Получено: {human_bytes(down)}"
            )
        except XUIError:
            text = "📊 Трафик\n\n⚠️ Данные 3x-ui временно недоступны."
    await render_callback(call, text, reply_markup=back_menu())
    await call.answer()


@client_access_router.callback_query(F.data == "client:devices")
async def devices_cb(call: CallbackQuery):
    if not await guard_callback(call):
        return
    rec = await db.get(call.from_user.id)
    if rec is None:
        text = "📱 Устройства\n\nДоступ пока не оформлен."
    else:
        try:
            devices = await xui.client_hwids(rec.email)
            lines = ["📱 Устройства", ""]
            if not devices:
                lines.append("Зарегистрированных HWID-устройств нет.")
            else:
                for index, item in enumerate(devices[:20], start=1):
                    model = str(item.get("deviceModel") or "").strip()
                    os_name = str(item.get("deviceOs") or "").strip()
                    title = model or os_name or f"Устройство #{index}"
                    last_seen = format_timestamp(
                        int(item.get("lastSeen") or 0),
                        milliseconds=True,
                        empty="—",
                    )
                    lines.append(f"{index}. {title[:60]} · {os_name or 'ОС неизвестна'}")
                    lines.append(f"   Последняя активность: {last_seen}")
            text = "\n".join(lines)
        except XUIError:
            text = "📱 Устройства\n\n⚠️ Данные 3x-ui временно недоступны."
    await render_callback(call, text, reply_markup=back_menu())
    await call.answer()


@client_access_router.callback_query(F.data == "client:buy")
async def buy_cb(call: CallbackQuery):
    if not await guard_callback(call):
        return
    rec = await db.get(call.from_user.id)
    if rec is None:
        await render_callback(
            call,
            "💳 Купить / продлить\n\n"
            "Сначала требуется создать клиентский аккаунт. "
            "Публичный onboarding пока не открыт.",
            reply_markup=back_menu(),
        )
        await call.answer()
        return

    plans = [plan for plan in await db.list_plans() if plan.active]
    if not plans:
        await render_callback(
            call,
            "💳 Купить / продлить\n\nСейчас нет доступных тарифов.",
            reply_markup=back_menu(),
        )
        await call.answer()
        return

    rows = [
        [InlineKeyboardButton(
            text=f"{plan.name} · {money_text(plan.price_minor, plan.currency)}",
            callback_data=f"client:plan:{plan.id}",
        )]
        for plan in plans[:20]
    ]
    rows.append([InlineKeyboardButton(text="⬅ Личный кабинет", callback_data="client:home")])
    await render_callback(
        call,
        "💳 Купить / продлить\n\nВыберите тариф:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@client_access_router.callback_query(F.data.startswith("client:plan:"))
async def plan_cb(call: CallbackQuery):
    if not await guard_callback(call):
        return
    rec = await db.get(call.from_user.id)
    if rec is None:
        await call.answer("Аккаунт не оформлен.", show_alert=True)
        return
    try:
        plan_id = int((call.data or "").rsplit(":", 1)[1])
    except (TypeError, ValueError):
        await call.answer("Некорректный тариф.", show_alert=True)
        return
    plan = await db.get_plan(plan_id)
    if plan is None or not plan.active:
        await call.answer("Тариф недоступен.", show_alert=True)
        return

    order, created = await commerce.get_or_create_order(
        telegram_id=call.from_user.id,
        plan_id=plan.id,
        amount_minor=plan.price_minor,
        currency=plan.currency,
    )
    state = "создан" if created else "уже существует"
    await render_callback(
        call,
        "💳 Заказ\n\n"
        f"Тариф: {plan.name}\n"
        f"Сумма: {money_text(order.amount_minor, order.currency)}\n"
        f"Заказ: #{order.id} · {state}\n\n"
        "Оплата пока не подключена. Заказ сохранён, но доступ не изменится "
        "до подтверждённого события платёжного провайдера.",
        reply_markup=back_menu(),
    )
    await call.answer()


@client_access_router.callback_query(F.data == "client:help")
async def help_cb(call: CallbackQuery):
    if not await guard_callback(call):
        return
    await render_callback(
        call,
        "🆘 Помощь\n\n"
        "Если подписка не открывается или подключение перестало работать, "
        "передайте администратору Telegram ID и краткое описание проблемы.\n\n"
        "Не отправляйте публично ссылку подписки: она является секретом доступа.",
        reply_markup=back_menu(),
    )
    await call.answer()


# Old v4 test buttons can still exist in message history. They are deliberately
# non-mutating now and only redirect users to the v5 portal.
@client_access_router.callback_query(F.data.in_({"create", "inbounds", "subscription"}))
async def legacy_client_callback(call: CallbackQuery):
    if not await guard_callback(call):
        return
    await render_home(call)
    await call.answer("Старый тестовый экран заменён личным кабинетом.")


@client_access_router.message(Command("create", "inbounds"))
async def legacy_client_command(message: Message):
    if not await guard_message(message):
        return
    await message.answer(
        "Старый тестовый сценарий отключён. Используйте личный кабинет:",
        reply_markup=portal_menu(),
    )
