import asyncio
import logging
import secrets
import time
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from config import load_settings
from db import Database, UserRecord
from xui import XUIClient, XUIError

settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
router = Router()

def is_allowed(tg_id: int) -> bool:
    return tg_id in settings.allowed_telegram_ids

def menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Проверить inbound'ы", callback_data="inbounds")],
        [InlineKeyboardButton(text="Создать тестовый доступ", callback_data="create")],
        [InlineKeyboardButton(text="Моя подписка", callback_data="subscription")],
        [InlineKeyboardButton(text="Удалить тестового пользователя", callback_data="delete")],
    ])

async def guard_message(message: Message) -> bool:
    if not message.from_user or not is_allowed(message.from_user.id):
        await message.answer("Этот бот работает только для тестовых Telegram ID.")
        return False
    return True

async def guard_callback(call: CallbackQuery) -> bool:
    if not call.from_user or not is_allowed(call.from_user.id):
        await call.answer("Нет доступа к тестовому боту.", show_alert=True)
        return False
    return True

def choose_inbounds(inbounds):
    chosen = []
    exact_ids = set(settings.inbound_ids)
    allowed_ports = set(settings.allowed_ports)
    allowed_protocols = set(settings.allowed_protocols)
    ignored_tags = set(settings.ignored_tags)
    ignored_protocols = set(settings.ignored_protocols)

    for i in inbounds:
        tag_lower = i.tag.lower()

        if not i.enable:
            continue
        if i.protocol in ignored_protocols:
            continue
        if tag_lower in ignored_tags:
            continue
        if tag_lower.startswith("api"):
            continue

        if exact_ids and i.id not in exact_ids:
            continue
        if allowed_ports and i.port not in allowed_ports:
            continue
        if allowed_protocols and i.protocol not in allowed_protocols:
            continue

        chosen.append(i)

    return chosen

def sub_url(sub_id: str) -> str:
    return settings.subscription_url_template.format(sub_id=sub_id)

def format_inbound(i) -> str:
    return (
        f"• ID #{i.id} | {i.port} | {i.protocol}\n"
        f"  tag: {i.tag or '-'}\n"
        f"  name: {i.remark}"
    )

@router.message(CommandStart())
async def start(message: Message):
    if not await guard_message(message):
        return
    await message.answer(
        "Тестовый бот для одной 3x-ui ноды.\n\n"
        "Текущий фильтр рассчитан на порты 2053, 2083 и 443.",
        reply_markup=menu(),
    )

async def show_inbounds_to(message: Message):
    try:
        all_inbounds = await xui.inbound_options()
        chosen = choose_inbounds(all_inbounds)

        all_text = "\n\n".join(format_inbound(i) for i in all_inbounds) or "Нет inbound'ов."
        chosen_text = "\n\n".join(format_inbound(i) for i in chosen) or "Ничего не выбрано."

        await message.answer(
            "Все inbound'ы, которые видит API:\n\n"
            f"{all_text}\n\n"
            "--------------------\n"
            "Будут выданы новому клиенту:\n\n"
            f"{chosen_text}",
            reply_markup=menu(),
        )
    except XUIError as e:
        await message.answer(f"Ошибка 3x-ui API:\n{e}", reply_markup=menu())

@router.message(Command("inbounds"))
async def cmd_inbounds(message: Message):
    if await guard_message(message):
        await show_inbounds_to(message)

@router.callback_query(F.data == "inbounds")
async def cb_inbounds(call: CallbackQuery):
    if not await guard_callback(call):
        return
    await call.answer()
    await show_inbounds_to(call.message)

@router.message(Command("create"))
async def cmd_create(message: Message):
    if await guard_message(message):
        await create_user(message.from_user.id, message)

@router.callback_query(F.data == "create")
async def cb_create(call: CallbackQuery):
    if not await guard_callback(call):
        return
    await call.answer()
    await create_user(call.from_user.id, call.message)

async def create_user(tg_id: int, message: Message):
    existing = await db.get(tg_id)
    if existing:
        await message.answer(
            f"Пользователь уже создан.\n\n{sub_url(existing.sub_id)}",
            reply_markup=menu(),
        )
        return

    try:
        panel_matches = await xui.get_client_by_tg_id(tg_id)
        if panel_matches:
            item = panel_matches[0]
            client = item.get("client", item)
            email = client.get("email")
            sid = client.get("subId")
            expiry = int(client.get("expiryTime") or 0)
            if email and sid:
                await db.put(UserRecord(
                    telegram_id=tg_id,
                    email=email,
                    sub_id=sid,
                    expiry_time=expiry,
                    created_at=int(time.time()),
                ))
                await message.answer(
                    "Нашёл существующего клиента в 3x-ui и восстановил локальную запись.\n\n"
                    f"{sub_url(sid)}",
                    reply_markup=menu(),
                )
                return

        all_inbounds = await xui.inbound_options()
        chosen = choose_inbounds(all_inbounds)
        if not chosen:
            await message.answer(
                "После фильтрации не осталось ни одного inbound.\n"
                "Сначала выполни /inbounds и проверь ID/порты.",
                reply_markup=menu(),
            )
            return

        now = int(time.time())
        expiry_ms = (now + settings.test_days * 86400) * 1000
        email = f"tg_{tg_id}"
        sid = secrets.token_urlsafe(18)

        await xui.create_client(
            email=email,
            telegram_id=tg_id,
            sub_id=sid,
            inbound_ids=[i.id for i in chosen],
            total_bytes=settings.test_traffic_gb * 1024**3,
            expiry_time_ms=expiry_ms,
            limit_ip=settings.test_ip_limit,
            comment="Created by Telegram single-node test bot",
        )

        await db.put(UserRecord(
            telegram_id=tg_id,
            email=email,
            sub_id=sid,
            expiry_time=expiry_ms,
            created_at=now,
        ))

        inbound_lines = "\n".join(
            f"• #{i.id} {i.port}/{i.protocol} {i.tag}" for i in chosen
        )
        expiry_text = datetime.fromtimestamp(
            expiry_ms / 1000, tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M UTC")

        await message.answer(
            "Клиент создан ✅\n\n"
            f"Email: {email}\n"
            f"До: {expiry_text}\n"
            f"Трафик: {settings.test_traffic_gb} GB\n"
            f"IP limit: {settings.test_ip_limit}\n\n"
            f"Inbound'ы:\n{inbound_lines}\n\n"
            f"Subscription:\n{sub_url(sid)}",
            reply_markup=menu(),
        )
    except XUIError as e:
        await message.answer(f"Ошибка создания клиента:\n{e}", reply_markup=menu())

@router.message(Command("subscription"))
async def cmd_subscription(message: Message):
    if await guard_message(message):
        await show_subscription(message.from_user.id, message)

@router.callback_query(F.data == "subscription")
async def cb_subscription(call: CallbackQuery):
    if not await guard_callback(call):
        return
    await call.answer()
    await show_subscription(call.from_user.id, call.message)

async def show_subscription(tg_id: int, message: Message):
    rec = await db.get(tg_id)
    if not rec:
        await message.answer("Сначала создай тестовый доступ.", reply_markup=menu())
        return

    try:
        links = await xui.sub_links(rec.sub_id)
        detected = []
        for link in links:
            scheme = link.split(":", 1)[0] if ":" in link else "unknown"
            detected.append(scheme)
        detected = sorted(set(detected))
        details = ", ".join(detected) if detected else "нет protocol links"
    except XUIError as e:
        details = f"ошибка проверки: {e}"

    await message.answer(
        f"Subscription:\n{sub_url(rec.sub_id)}\n\n"
        f"Обнаруженные схемы: {details}",
        reply_markup=menu(),
    )

@router.message(Command("delete_test"))
async def cmd_delete(message: Message):
    if await guard_message(message):
        await delete_user(message.from_user.id, message)

@router.callback_query(F.data == "delete")
async def cb_delete(call: CallbackQuery):
    if not await guard_callback(call):
        return
    await call.answer()
    await delete_user(call.from_user.id, call.message)

async def delete_user(tg_id: int, message: Message):
    rec = await db.get(tg_id)
    if not rec:
        await message.answer("Тестового пользователя в БД бота нет.", reply_markup=menu())
        return
    try:
        await xui.delete_client(rec.email)
        await db.delete(tg_id)
        await message.answer("Тестовый клиент удалён.", reply_markup=menu())
    except XUIError as e:
        await message.answer(
            "3x-ui вернул ошибку, локальная запись сохранена:\n"
            f"{e}",
            reply_markup=menu(),
        )

async def main():
    logging.basicConfig(level=logging.INFO)
    await db.init()
    bot = Bot(settings.bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
