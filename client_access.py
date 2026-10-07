from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from admin_ui import render_callback
from config import load_settings
from customer_service import CustomerPortalService, CustomerProviderUnavailable
from ui_time import format_timestamp
from version import APP_VERSION


settings = load_settings()
customer_service: CustomerPortalService | None = None

client_access_router = Router(name="client_access")

TERMS_VERSION = "v5-stars-2026-10-07"


def is_allowed(tg_id: int) -> bool:
    # v5 pilot boundary. Public signup remains closed until abuse/rate-limit
    # controls and the full checkout provider flow are ready.
    return (
        tg_id in settings.allowed_telegram_ids
        or tg_id in settings.admin_telegram_ids
    )


def configure_client_access(service: CustomerPortalService) -> None:
    global customer_service
    customer_service = service


def _service() -> CustomerPortalService:
    if customer_service is None:
        raise RuntimeError("Client Portal service is not configured")
    return customer_service


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


def stars_payload(*, order_id: int, telegram_id: int) -> str:
    return f"stars:v1:{int(order_id)}:{int(telegram_id)}"


def parse_stars_payload(value: str) -> tuple[int, int]:
    parts = str(value or "").split(":")
    if len(parts) != 4 or parts[:2] != ["stars", "v1"]:
        raise ValueError("invalid Stars invoice payload")
    order_id = int(parts[2])
    telegram_id = int(parts[3])
    if order_id <= 0 or telegram_id <= 0:
        raise ValueError("invalid Stars invoice identity")
    return order_id, telegram_id


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
    profile = await _service().profile(tg_id)
    if not profile.exists:
        return (
            f"Личный кабинет · v{APP_VERSION}\n\n"
            "Доступ пока не оформлен. Публичная регистрация ещё закрыта; "
            "обратитесь в поддержку для подключения."
        )
    return (
        f"Личный кабинет · v{APP_VERSION}\n\n"
        f"👤 {profile.display_name or profile.email}\n"
        f"💎 Тариф: {profile.plan_name or 'не назначен'}\n"
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
    profile = await _service().profile(call.from_user.id)
    if not profile.exists:
        text = "👤 Профиль\n\nДоступ пока не оформлен."
    else:
        expiry = format_timestamp(
            profile.expiry_time,
            milliseconds=True,
            empty="без срока",
        )
        text = (
            "👤 Профиль\n\n"
            f"Имя: {profile.display_name or '—'}\n"
            f"Аккаунт: {profile.email}\n"
            f"Тариф: {profile.plan_name or 'не назначен'}\n"
            f"Срок: {expiry}"
        )
    await render_callback(call, text, reply_markup=back_menu())
    await call.answer()


@client_access_router.message(Command("subscription"))
async def subscription_cmd(message: Message):
    if not await guard_message(message):
        return
    url = await _service().subscription_url(message.from_user.id)
    await message.answer(
        url or "Подписка пока не оформлена.",
        reply_markup=portal_menu(),
    )


@client_access_router.callback_query(F.data == "client:subscription")
async def subscription_cb(call: CallbackQuery):
    if not await guard_callback(call):
        return
    url = await _service().subscription_url(call.from_user.id)
    text = "🌐 Моя подписка\n\n" + (url or "Подписка пока не оформлена.")
    await render_callback(call, text, reply_markup=back_menu())
    await call.answer()


@client_access_router.callback_query(F.data == "client:traffic")
async def traffic_cb(call: CallbackQuery):
    if not await guard_callback(call):
        return
    try:
        traffic = await _service().traffic(call.from_user.id)
        if traffic is None:
            text = "📊 Трафик\n\nДоступ пока не оформлен."
        else:
            used = traffic.up + traffic.down
            text = (
                "📊 Трафик\n\n"
                f"Использовано: {human_bytes(used)}\n"
                f"Лимит: {human_bytes(traffic.total) if traffic.total else 'без лимита'}\n"
                f"Отправлено: {human_bytes(traffic.up)}\n"
                f"Получено: {human_bytes(traffic.down)}"
            )
    except CustomerProviderUnavailable:
        text = "📊 Трафик\n\n⚠️ Данные провайдера временно недоступны."
    await render_callback(call, text, reply_markup=back_menu())
    await call.answer()


@client_access_router.callback_query(F.data == "client:devices")
async def devices_cb(call: CallbackQuery):
    if not await guard_callback(call):
        return
    try:
        devices = await _service().devices(call.from_user.id)
        if devices is None:
            text = "📱 Устройства\n\nДоступ пока не оформлен."
        else:
            lines = ["📱 Устройства", ""]
            if not devices:
                lines.append("Зарегистрированных HWID-устройств нет.")
            else:
                for index, item in enumerate(devices, start=1):
                    last_seen = format_timestamp(
                        item.last_seen,
                        milliseconds=True,
                        empty="—",
                    )
                    lines.append(
                        f"{index}. {item.title[:60]} · {item.os_name or 'ОС неизвестна'}"
                    )
                    lines.append(f"   Последняя активность: {last_seen}")
            text = "\n".join(lines)
    except CustomerProviderUnavailable:
        text = "📱 Устройства\n\n⚠️ Данные провайдера временно недоступны."
    await render_callback(call, text, reply_markup=back_menu())
    await call.answer()


@client_access_router.callback_query(F.data == "client:buy")
async def buy_cb(call: CallbackQuery):
    if not await guard_callback(call):
        return
    profile = await _service().profile(call.from_user.id)
    if not profile.exists:
        await render_callback(
            call,
            "💳 Купить / продлить\n\n"
            "Сначала требуется создать клиентский аккаунт. "
            "Публичный onboarding пока не открыт.",
            reply_markup=back_menu(),
        )
        await call.answer()
        return

    plans = await _service().active_plans()
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
            text=(
                f"{plan.name} · ⭐ {plan.stars_price}"
                if int(plan.stars_price or 0) > 0
                else f"{plan.name} · Stars не настроены"
            ),
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
    profile = await _service().profile(call.from_user.id)
    if not profile.exists:
        await call.answer("Аккаунт не оформлен.", show_alert=True)
        return
    try:
        plan_id = int((call.data or "").rsplit(":", 1)[1])
    except (TypeError, ValueError):
        await call.answer("Некорректный тариф.", show_alert=True)
        return
    plan = await _service().active_plan(plan_id)
    if plan is None:
        await call.answer("Тариф недоступен.", show_alert=True)
        return

    if int(plan.stars_price or 0) <= 0:
        await render_callback(
            call,
            "💳 Заказ\n\n"
            "Цена этого тарифа в Telegram Stars ещё не настроена.",
            reply_markup=back_menu(),
        )
        await call.answer()
        return

    if not await _service().has_accepted_terms(call.from_user.id, TERMS_VERSION):
        await render_callback(
            call,
            "📄 Условия покупки\n\n"
            f"Тариф: {plan.name}\n"
            f"Сумма: ⭐ {plan.stars_price}\n\n"
            "Нажимая «Принимаю и оплатить», вы подтверждаете покупку цифровой "
            "VPN-подписки за Telegram Stars и соглашаетесь обратиться в поддержку "
            "по вопросам оплаты/возврата.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="✅ Принимаю и оплатить",
                    callback_data=f"client:terms:{plan.id}",
                )],
                [InlineKeyboardButton(text="⬅ Купить / продлить", callback_data="client:buy")],
            ]),
        )
        await call.answer()
        return

    order, created = await _service().get_or_create_stars_order(
        telegram_id=call.from_user.id,
        plan=plan,
    )
    payload = stars_payload(order_id=order.id, telegram_id=call.from_user.id)
    await call.bot.send_invoice(
        chat_id=call.from_user.id,
        title=plan.name[:32],
        description=(
            f"VPN-подписка: {plan.name}, срок {plan.duration_days} дней."
        )[:255],
        payload=payload,
        currency="XTR",
        prices=[
            LabeledPrice(
                label=plan.name[:32],
                amount=int(plan.stars_price),
            )
        ],
        provider_token="",
    )
    state = "создан" if created else "уже существует"
    await render_callback(
        call,
        "💳 Заказ\n\n"
        f"Тариф: {plan.name}\n"
        f"Сумма: ⭐ {plan.stars_price}\n"
        f"Заказ: #{order.id} · {state}\n\n"
        "Invoice Telegram Stars отправлен отдельным сообщением. "
        "Доступ изменится только после успешного платежа Telegram.",
        reply_markup=back_menu(),
    )
    await call.answer()



@client_access_router.callback_query(F.data.startswith("client:terms:"))
async def terms_accept_cb(call: CallbackQuery):
    if not await guard_callback(call):
        return
    try:
        plan_id = int((call.data or "").rsplit(":", 1)[1])
    except (TypeError, ValueError):
        await call.answer("Некорректный тариф.", show_alert=True)
        return
    plan = await _service().active_plan(plan_id)
    if plan is None or int(plan.stars_price or 0) <= 0:
        await call.answer("Тариф недоступен.", show_alert=True)
        return
    await _service().accept_terms(call.from_user.id, TERMS_VERSION)
    order, created = await _service().get_or_create_stars_order(
        telegram_id=call.from_user.id,
        plan=plan,
    )
    payload = stars_payload(order_id=order.id, telegram_id=call.from_user.id)
    await call.bot.send_invoice(
        chat_id=call.from_user.id,
        title=plan.name[:32],
        description=f"VPN-подписка: {plan.name}, срок {plan.duration_days} дней."[:255],
        payload=payload,
        currency="XTR",
        prices=[LabeledPrice(label=plan.name[:32], amount=int(plan.stars_price))],
        provider_token="",
    )
    state = "создан" if created else "уже существует"
    await render_callback(
        call,
        "💳 Заказ\n\n"
        f"Тариф: {plan.name}\n"
        f"Сумма: ⭐ {plan.stars_price}\n"
        f"Заказ: #{order.id} · {state}\n"
        f"Условия: приняты ({TERMS_VERSION})\n\n"
        "Invoice Telegram Stars отправлен отдельным сообщением. "
        "Доступ изменится только после успешного платежа Telegram.",
        reply_markup=back_menu(),
    )
    await call.answer()


@client_access_router.pre_checkout_query()
async def stars_pre_checkout(query: PreCheckoutQuery):
    if not is_allowed(query.from_user.id):
        await query.answer(
            ok=False,
            error_message="Покупка сейчас недоступна для этого аккаунта.",
        )
        return
    try:
        order_id, telegram_id = parse_stars_payload(query.invoice_payload)
    except (TypeError, ValueError):
        await query.answer(ok=False, error_message="Некорректный платёжный запрос.")
        return
    if telegram_id != query.from_user.id or query.currency != "XTR":
        await query.answer(ok=False, error_message="Платёж не прошёл проверку владельца.")
        return
    valid = await _service().validate_stars_precheckout(
        telegram_id=query.from_user.id,
        order_id=order_id,
        amount=query.total_amount,
    )
    if not valid:
        await query.answer(
            ok=False,
            error_message="Заказ изменился или больше недоступен. Создайте оплату заново.",
        )
        return
    await query.answer(ok=True)


@client_access_router.message(F.successful_payment)
async def stars_successful_payment(message: Message):
    if not message.from_user or not message.successful_payment:
        return
    payment = message.successful_payment
    if payment.currency != "XTR":
        return
    try:
        order_id, telegram_id = parse_stars_payload(payment.invoice_payload)
    except (TypeError, ValueError):
        await message.answer(
            "⚠️ Платёж получен, но invoice payload не распознан. Обратитесь в поддержку."
        )
        return
    if telegram_id != message.from_user.id:
        await message.answer(
            "⚠️ Платёж получен, но владелец заказа не совпадает. Обратитесь в поддержку."
        )
        return

    raw_payload = (
        f"{payment.invoice_payload}|{payment.currency}|{payment.total_amount}|"
        f"{payment.telegram_payment_charge_id}"
    ).encode("utf-8")
    try:
        _, order, entitlement, created = await _service().confirm_stars_payment(
            telegram_id=message.from_user.id,
            order_id=order_id,
            charge_id=payment.telegram_payment_charge_id,
            amount=payment.total_amount,
            raw_payload=raw_payload,
        )
    except Exception:
        await message.answer(
            "⚠️ Telegram подтвердил платёж, но локальная фиксация не завершилась. "
            "Не оплачивайте повторно и обратитесь в поддержку."
        )
        raise

    await message.answer(
        "✅ Оплата Telegram Stars подтверждена.\n\n"
        f"Заказ: #{order.id}\n"
        f"Entitlement: #{entitlement.id}\n"
        + (
            "Доступ поставлен в очередь на активацию."
            if created
            else "Платёж уже был учтён ранее; повторного продления не произошло."
        ),
        reply_markup=portal_menu(),
    )


@client_access_router.message(Command("paysupport"))
async def payment_support(message: Message):
    if not message.from_user:
        return
    await message.answer(
        "Поддержка по оплате Telegram Stars:\n"
        "отправьте администратору ваш Telegram ID и время платежа. "
        "Не публикуйте subscription URL или другие секреты доступа."
    )


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
