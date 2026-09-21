import asyncio
import logging
import secrets
import time
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from config import load_settings
from db import Database, UserRecord
from xui import XUIClient, XUIError

settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(
    settings.panel_url,
    settings.panel_api_token,
    settings.verify_tls,
)

router = Router()

def allowed(tg_id: int) -> bool:
    return tg_id in settings.allowed_telegram_ids

def menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать тестовый доступ", callback_data="create")],
        [InlineKeyboardButton(text="Моя подписка", callback_data="subscription")],
        [InlineKeyboardButton(text="Проверить inbound'ы", callback_data="inbounds")],
        [InlineKeyboardButton(text="Удалить тестового пользователя", callback_data="delete")],
    ])

async def guard_message(message: Message) -> bool:
    if not message.from_user or not allowed(message.from_user.id):
        await message.answer("Этот бот сейчас работает только для тестовых Telegram ID.")
        return False
    return True

async def guard_callback(call: CallbackQuery) -> bool:
    if not call.from_user or not allowed(call.from_user.id):
        await call.answer("Нет доступа к тестовому боту.", show_alert=True)
        return False
    return True

def select_inbounds(all_inbounds):
    enabled = [
        i for i in all_inbounds
        if i.enable and i.protocol in settings.allowed_protocols
    ]
    if settings.inbound_ids:
        wanted = set(settings.inbound_ids)
        enabled = [i for i in enabled if i.id in wanted]
    return enabled

def sub_url(sub_id: str) -> str:
    return settings.subscription_url_template.format(sub_id=sub_id)

@router.message(CommandStart())
async def start(message: Message):
    if not await guard_message(message):
        return
    await message.answer(
        "Тестовый бот 3x-ui.\n\n"
        "Он создаёт одного клиента и привязывает его ко всем разрешённым "
        "включённым inbound'ам на этой панели.",
        reply_markup=menu(),
    )

@router.message(Command("inbounds"))
async def cmd_inbounds(message: Message):
    if not await guard_message(message):
        return
    await show_inbounds(message)

async def show_inbounds(target):
    try:
        inbounds = await xui.list_inbounds()
        chosen = select_inbounds(inbounds)
        if not chosen:
            text = "Не найдено ни одного подходящего включённого inbound."
        else:
            lines = [
                f"• #{i.id} — {i.remark} [{i.protocol}]"
                for i in chosen
            ]
            text = "Inbound'ы, куда будет добавлен клиент:\n\n" + "\n".join(lines)
    except XUIError as e:
        text = f"Ошибка 3x-ui API:\n{e}"

    if isinstance(target, CallbackQuery):
        await target.message.answer(text, reply_markup=menu())
        await target.answer()
    else:
        await target.answer(text, reply_markup=menu())

@router.callback_query(F.data == "inbounds")
async def cb_inbounds(call: CallbackQuery):
    if not await guard_callback(call):
        return
    await show_inbounds(call)

@router.message(Command("create"))
async def cmd_create(message: Message):
    if not await guard_message(message):
        return
    await create_for(message.from_user.id, message)

@router.callback_query(F.data == "create")
async def cb_create(call: CallbackQuery):
    if not await guard_callback(call):
        return
    await call.answer()
    await create_for(call.from_user.id, call.message)

async def create_for(tg_id: int, message: Message):
    existing = await db.get(tg_id)
    if existing:
        await message.answer(
            "Тестовый пользователь уже создан.\n\n"
            f"Подписка:\n{sub_url(existing.sub_id)}",
            reply_markup=menu(),
        )
        return

    try:
        # Recover an existing panel client if DB was deleted/recreated.
        panel_matches = await xui.get_client_by_tg_id(tg_id)
        if panel_matches:
            item = panel_matches[0]
            client = item.get("client", item)
            email = client.get("email")
            sid = client.get("subId")
            expiry = int(client.get("expiryTime") or 0)
            if email and sid:
                rec = UserRecord(
                    telegram_id=tg_id,
                    email=email,
                    sub_id=sid,
                    expiry_time=expiry,
                    created_at=int(time.time()),
                )
                await db.put(rec)
                await message.answer(
                    "Нашёл уже существующего клиента в 3x-ui и восстановил его в БД бота.\n\n"
                    f"Подписка:\n{sub_url(sid)}",
                    reply_markup=menu(),
                )
                return

        all_inbounds = await xui.list_inbounds()
        chosen = select_inbounds(all_inbounds)
        if not chosen:
            await message.answer(
                "Нет подходящих inbound'ов. Проверь INBOUND_IDS / ALLOWED_PROTOCOLS.",
                reply_markup=menu(),
            )
            return

        now = int(time.time())
        expiry_ms = (now + settings.test_days * 86400) * 1000
        total_bytes = settings.test_traffic_gb * 1024**3
        email = f"tg_{tg_id}"
        sid = secrets.token_urlsafe(18)

        await xui.create_client(
            email=email,
            telegram_id=tg_id,
            sub_id=sid,
            inbound_ids=[i.id for i in chosen],
            total_bytes=total_bytes,
            expiry_time_ms=expiry_ms,
            limit_ip=settings.test_ip_limit,
            comment="Created by Telegram test bot",
        )

        rec = UserRecord(
            telegram_id=tg_id,
            email=email,
            sub_id=sid,
            expiry_time=expiry_ms,
            created_at=now,
        )
        await db.put(rec)

        date_str = datetime.fromtimestamp(
            expiry_ms / 1000, tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M UTC")

        await message.answer(
            "Готово ✅\n\n"
            f"Клиент: {email}\n"
            f"Inbound'ов: {len(chosen)}\n"
            f"Трафик: {settings.test_traffic_gb} GB\n"
            f"Лимит IP: {settings.test_ip_limit}\n"
            f"До: {date_str}\n\n"
            f"Подписка:\n{sub_url(sid)}",
            reply_markup=menu(),
        )
    except XUIError as e:
        await message.answer(
            "3x-ui не смог создать клиента.\n\n"
            f"{e}",
            reply_markup=menu(),
        )

@router.message(Command("subscription"))
async def cmd_subscription(message: Message):
    if not await guard_message(message):
        return
    await subscription_for(message.from_user.id, message)

@router.callback_query(F.data == "subscription")
async def cb_subscription(call: CallbackQuery):
    if not await guard_callback(call):
        return
    await call.answer()
    await subscription_for(call.from_user.id, call.message)

async def subscription_for(tg_id: int, message: Message):
    rec = await db.get(tg_id)
    if not rec:
        await message.answer(
            "Пользователь ещё не создан. Нажми «Создать тестовый доступ».",
            reply_markup=menu(),
        )
        return

    try:
        links = await xui.sub_links(rec.sub_id)
        protocols = sorted({
            link.split(":", 1)[0]
            for link in links
            if ":" in link
        })
        suffix = (
            "\nПротоколы: " + ", ".join(protocols)
            if protocols else
            "\n3x-ui пока не вернул protocol links — проверь host/sub настройки."
        )
    except XUIError as e:
        suffix = f"\nНе удалось проверить protocol links: {e}"

    await message.answer(
        f"Твоя подписка:\n{sub_url(rec.sub_id)}{suffix}",
        reply_markup=menu(),
    )

@router.message(Command("delete_test"))
async def cmd_delete(message: Message):
    if not await guard_message(message):
        return
    await delete_for(message.from_user.id, message)

@router.callback_query(F.data == "delete")
async def cb_delete(call: CallbackQuery):
    if not await guard_callback(call):
        return
    await call.answer()
    await delete_for(call.from_user.id, call.message)

async def delete_for(tg_id: int, message: Message):
    rec = await db.get(tg_id)
    if not rec:
        await message.answer("В локальной БД тестового пользователя нет.", reply_markup=menu())
        return
    try:
        await xui.delete_client(rec.email)
        await db.delete(tg_id)
        await message.answer(
            "Тестовый клиент удалён из 3x-ui и из БД бота.",
            reply_markup=menu(),
        )
    except XUIError as e:
        await message.answer(
            "Не удаляю локальную запись, потому что 3x-ui вернул ошибку:\n"
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
