from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from admin_ui import render_callback
from config import load_settings
from client_flags import ClientFeatureFlags
from client_rate_limit import SlidingWindowRateLimiter
from customer_service import CustomerPortalService, CustomerProviderUnavailable
from ui_time import format_timestamp
from website_diagnostics import qr_png
from version import APP_VERSION
from stars_invoice_ui import stars_invoice_title


settings = load_settings()
customer_service: CustomerPortalService | None = None
feature_flags: ClientFeatureFlags | None = None

client_access_router = Router(name="client_access")

TERMS_VERSION = "v5-stars-2026-10-07"
client_rate_limiter = SlidingWindowRateLimiter(
    limit=settings.client_rate_limit_count,
    window_seconds=settings.client_rate_limit_window_seconds,
)


def is_allowed(tg_id: int) -> bool:
    # settings.client_portal_enabled is an immutable environment veto.
    # Pilot/public access policy stays explicit; the launch flag is an
    # independent rollback switch.
    return (
        tg_id in settings.allowed_telegram_ids
        or tg_id in settings.admin_telegram_ids
    )


async def payment_acceptance_enabled() -> bool:
    # settings.client_payment_acceptance_enabled remains the immutable environment veto.
    return bool(feature_flags and (await feature_flags.snapshot()).stars_enabled)


def configure_client_access(service: CustomerPortalService) -> None:
    global customer_service
    customer_service = service


def configure_client_feature_flags(flags: ClientFeatureFlags) -> None:
    global feature_flags
    feature_flags = flags


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
    if not (feature_flags and (await feature_flags.snapshot()).portal_enabled):
        await message.answer("Личный кабинет временно отключён.")
        return False
    if not message.from_user or not is_allowed(message.from_user.id):
        await message.answer("Нет доступа.")
        return False
    if not client_rate_limiter.allow(message.from_user.id):
        await message.answer("Слишком много запросов. Попробуйте немного позже.")
        return False
    return True


async def guard_callback(call: CallbackQuery) -> bool:
    if not settings.client_portal_enabled:
        await call.answer("Личный кабинет временно отключён.", show_alert=True)
        return False
    if not call.from_user or not is_allowed(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return False
    if not client_rate_limiter.allow(call.from_user.id):
        await call.answer("Слишком много запросов. Попробуйте немного позже.", show_alert=True)
        return False
    return True


def customer_period_label(status: str) -> str:
    return {
        "active": "🟢 оплачен",
        "legacy": "ℹ️ оформлен",
        "pending": "🟡 ожидает оплаты/активации",
        "provisioning": "🟡 активируется",
        "suspended": "⛔ приостановлен",
        "expired": "⌛ истёк",
        "failed": "❌ ошибка активации",
    }.get(status, "⚪ статус неизвестен")


def customer_access_label(status: str) -> str:
    return {
        "active": "🟢 доступен",
        "disabled": "⛔ отключён",
        "expired": "⌛ истёк",
        "suspended": "⛔ приостановлен",
        "provisioning": "🟡 активация",
        "unknown": "⚪ статус неизвестен",
    }.get(status, "⚪ статус неизвестен")


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
        f"💳 Период: {customer_period_label(profile.period_status)}\n"
        f"🌐 VPN-доступ: {customer_access_label(profile.access_status)}"
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


@client_access_router.message(Command("paysupport"))
async def pay_support(message: Message):
    if not await guard_message(message):
        return
    await message.answer(
        "💳 Поддержка по оплате\n\n"
        "Если платёж Telegram Stars прошёл, но доступ не появился, либо нужен возврат, "
        "отправьте в поддержку Telegram ID и примерное время покупки. "
        "Не пересылайте токены, subscription URL или другие секреты.\n\n"
        "Возврат Stars выполняется оператором через журнал платежей и не повторяется "
        "автоматически при неизвестном исходе.",
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
            f"Период: {customer_period_label(profile.period_status)}\n"
            f"VPN-доступ: {customer_access_label(profile.access_status)}\n"
            f"Срок: {expiry}" + (
                "\n⚠️ Сроки доступа различаются; обратитесь в поддержку."
                if profile.expiry_drift else ""
            )
        )
    await render_callback(call, text, reply_markup=back_menu())
    await call.answer()


@client_access_router.message(Command("subscription"))
async def subscription_cmd(message: Message):
    if not await guard_message(message):
        return
    url = await _service().subscription_url(message.from_user.id)
    await message.answer(
        "🌐 Моя подписка\n\n" + (url or "Подписка пока не оформлена."),
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
    if not await payment_acceptance_enabled():
        await render_callback(
            call,
            "💳 Купить / продлить\n\nПриём новых платежей временно отключён.",
            reply_markup=back_menu(),
        )
        await call.answer()
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
                f"💎 {plan.name} · ⭐ {plan.stars_price}"
                if int(plan.stars_price or 0) > 0
                else f"💎 {plan.name} · Stars не настроены"
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
    if not await payment_acceptance_enabled():
        await call.answer("Приём новых платежей временно отключён.", show_alert=True)
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
    if not await payment_acceptance_enabled():
        await call.answer("Приём новых платежей временно отключён.", show_alert=True)
        return
    await call.bot.send_invoice(
        chat_id=call.from_user.id,
        title=await stars_invoice_title(call.bot),
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
    if not await payment_acceptance_enabled():
        await call.answer("Приём новых платежей временно отключён.", show_alert=True)
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
    if not await payment_acceptance_enabled():
        await call.answer("Приём новых платежей временно отключён.", show_alert=True)
        return
    await call.bot.send_invoice(
        chat_id=call.from_user.id,
        title=await stars_invoice_title(call.bot),
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
    if not await payment_acceptance_enabled():
        await query.answer(
            ok=False,
            error_message="Приём новых платежей временно отключён.",
        )
        return
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
    # Recheck after order validation: a switch may change during DB I/O.
    if not await payment_acceptance_enabled():
        await query.answer(ok=False, error_message="Приём новых платежей временно отключён.")
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


def onboarding_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🍎 iOS", callback_data="client:onboard:ios"),
            InlineKeyboardButton(text="🤖 Android", callback_data="client:onboard:android"),
        ],
        [
            InlineKeyboardButton(text="🪟 Windows", callback_data="client:onboard:windows"),
            InlineKeyboardButton(text="🍎 macOS", callback_data="client:onboard:macos"),
        ],
        [InlineKeyboardButton(text="🐧 Linux", callback_data="client:onboard:linux")],
        [InlineKeyboardButton(text="🔳 QR подписки", callback_data="client:onboard:qr")],
        [InlineKeyboardButton(text="⬅ Помощь", callback_data="client:help")],
    ])


_PLATFORM_GUIDES = {
    "ios": ("iOS", "Откройте поддерживаемый VPN-клиент → импорт подписки по URL → вставьте ссылку из «Моя подписка»."),
    "android": ("Android", "Откройте поддерживаемый VPN-клиент → добавьте подписку по URL → вставьте ссылку из «Моя подписка»."),
    "windows": ("Windows", "В поддерживаемом VPN-клиенте выберите импорт подписки по URL и используйте ссылку из «Моя подписка»."),
    "macos": ("macOS", "В поддерживаемом VPN-клиенте импортируйте подписку по URL из раздела «Моя подписка»."),
    "linux": ("Linux", "Импортируйте subscription URL в совместимый клиент. Не передавайте ссылку через shell history или публичные логи."),
}


@client_access_router.callback_query(F.data == "client:help")
async def help_cb(call: CallbackQuery):
    if not await guard_callback(call):
        return
    await render_callback(
        call,
        "🆘 Помощь\n\n"
        "Выберите сценарий. Диагностика только читает состояние и не запускает "
        "provisioning/reconcile автоматически.\n\n"
        "Не отправляйте публично ссылку подписки: она является секретом доступа.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 Как подключиться", callback_data="client:onboard")],
            [InlineKeyboardButton(text="🛠 Проверить подписку", callback_data="client:diagnostics")],
            [InlineKeyboardButton(text="💳 Поддержка по оплате", callback_data="client:paysupport")],
            [InlineKeyboardButton(text="⬅ Личный кабинет", callback_data="client:home")],
        ]),
    )
    await call.answer()


@client_access_router.callback_query(F.data == "client:onboard")
async def onboarding_cb(call: CallbackQuery):
    if not await guard_callback(call):
        return
    await render_callback(
        call,
        "📱 Как подключиться\n\n"
        "Выберите платформу. Subscription URL является секретом доступа: "
        "не публикуйте его и не пересылайте посторонним.",
        reply_markup=onboarding_menu(),
    )
    await call.answer()


@client_access_router.callback_query(F.data.startswith("client:onboard:"))
async def onboarding_platform_cb(call: CallbackQuery):
    if not await guard_callback(call):
        return
    platform = (call.data or "").rsplit(":", 1)[-1]
    if platform == "qr":
        url = await _service().subscription_url(call.from_user.id)
        if not url:
            await call.answer("Подписка пока не оформлена.", show_alert=True)
            return
        if not call.message or call.message.chat.type != "private":
            await call.answer("QR доступен только в личном чате.", show_alert=True)
            return
        image = qr_png(url)
        await call.bot.send_photo(
            call.message.chat.id,
            BufferedInputFile(image, filename="subscription-qr.png"),
            caption=(
                "🔳 QR подписки\n\n"
                "Сканируйте только на своём устройстве. QR содержит секретную "
                "subscription URL; не публикуйте изображение."
            ),
        )
        await call.answer()
        return
    guide = _PLATFORM_GUIDES.get(platform)
    if guide is None:
        await call.answer("Неизвестная платформа.", show_alert=True)
        return
    name, instructions = guide
    await render_callback(
        call,
        f"📱 Подключение · {name}\n\n{instructions}\n\n"
        "Автоматический deep-link пока не используется: формат импорта должен "
        "быть стабилен и безопасен для конкретного клиента.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Моя подписка", callback_data="client:subscription")],
            [InlineKeyboardButton(text="⬅ Платформы", callback_data="client:onboard")],
        ]),
    )
    await call.answer()


@client_access_router.callback_query(F.data == "client:diagnostics")
async def diagnostics_cb(call: CallbackQuery):
    if not await guard_callback(call):
        return
    result = await _service().diagnostics(call.from_user.id)
    if not result.account_exists:
        text = "🛠 Проверить подписку\n\n❌ Клиентский аккаунт ещё не оформлен."
    else:
        entitlement_labels = {
            "active": "🟢 активен",
            "pending": "🟡 ожидает активации",
            "provisioning": "🟡 выполняется активация",
            "suspended": "⛔ приостановлен",
            "expired": "⌛ истёк",
            "failed": "❌ ошибка активации",
            "legacy": "ℹ️ legacy-доступ",
        }
        provider = (
            "🟢 доступен" if result.provider_reachable is True
            else "⚠️ временно недоступен" if result.provider_reachable is False
            else "—"
        )
        text = (
            "🛠 Проверить подписку\n\n"
            f"Аккаунт: 🟢 найден\n"
            f"Entitlement: {entitlement_labels.get(result.entitlement_status, result.entitlement_status)}\n"
            f"Subscription URL: {'🟢 сформирована' if result.subscription_available else '❌ отсутствует'}\n"
            f"Provider read: {provider}\n"
            f"VPN-доступ: {customer_access_label(result.vpn_access_status)}\n"
            f"Сроки: {'⚠️ расхождение' if result.expiry_drift else 'согласованы / нет данных'}\n"
        )
        if result.note:
            text += f"\nℹ️ {result.note}"
        if result.entitlement_status in {"pending", "provisioning"}:
            text += "\n\nАктивация ещё не завершена. Диагностика не повторяет provisioning mutation."
        elif result.entitlement_status == "failed":
            text += "\n\nАктивация завершилась ошибкой. Обратитесь в поддержку; автоматический retry отсюда не запускается."
    await render_callback(
        call,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Проверить снова", callback_data="client:diagnostics")],
            [InlineKeyboardButton(text="⬅ Помощь", callback_data="client:help")],
        ]),
    )
    await call.answer()


@client_access_router.callback_query(F.data == "client:paysupport")
async def pay_support_cb(call: CallbackQuery):
    if not await guard_callback(call):
        return
    await render_callback(
        call,
        "💳 Поддержка по оплате\n\n"
        "Если Stars списались, но доступ не появился, используйте /paysupport. "
        "Не оплачивайте повторно при неизвестном исходе и не отправляйте subscription URL.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛠 Проверить подписку", callback_data="client:diagnostics")],
            [InlineKeyboardButton(text="⬅ Помощь", callback_data="client:help")],
        ]),
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
