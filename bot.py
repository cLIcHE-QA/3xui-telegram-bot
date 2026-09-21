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
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="🧪 Inbound'ы", callback_data="inbounds")],
    ])

def user_admin_keyboard(tg_id: int, enabled: bool = True) -> InlineKeyboardMarkup:
    state_btn = (
        InlineKeyboardButton(text="⛔ Отключить", callback_data=f"admindisable:{tg_id}")
        if enabled else
        InlineKeyboardButton(text="✅ Включить", callback_data=f"adminenable:{tg_id}")
    )
    return InlineKeyboardMarkup(inline_keyboard=[
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

async def guard_message(message: Message) -> bool:
    if not message.from_user or not is_allowed(message.from_user.id):
        await message.answer("Нет доступа.")
        return False
    return True

async def guard_admin_call(call: CallbackQuery) -> bool:
    if not call.from_user or not is_admin(call.from_user.id):
        await call.answer("Только для администратора.", show_alert=True)
        return False
    return True

def choose_inbounds(inbounds):
    chosen = []
    exact_ids = set(settings.inbound_ids)
    for i in inbounds:
        if not i.enable:
            continue
        if i.protocol in set(settings.ignored_protocols):
            continue
        if i.tag.lower() in set(settings.ignored_tags) or i.tag.lower().startswith("api"):
            continue
        if exact_ids and i.id not in exact_ids:
            continue
        if settings.allowed_ports and i.port not in set(settings.allowed_ports):
            continue
        if settings.allowed_protocols and i.protocol not in set(settings.allowed_protocols):
            continue
        chosen.append(i)
    return chosen

def sub_url(sub_id: str) -> str:
    return settings.subscription_url_template.format(sub_id=sub_id)

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
    await message.answer("3x-ui Telegram bot v3", reply_markup=user_menu())

@router.message(Command("admin"))
async def admin(message: Message):
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer("Команда доступна только администратору.")
        return
    await message.answer("⚙️ Админ-панель", reply_markup=admin_menu())

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
    rows.append([InlineKeyboardButton(text="⬅ Админка", callback_data="admin:home")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await call.message.answer(f"Пользователи в БД бота: {len(users)}", reply_markup=kb)
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

@router.callback_query(F.data == "admin:home")
async def admin_home(call: CallbackQuery):
    if not await guard_admin_call(call):
        return
    await call.message.answer("⚙️ Админ-панель", reply_markup=admin_menu())
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
        text = (
            f"👤 {rec.email}\n"
            f"Telegram ID: {rec.telegram_id}\n"
            f"Статус: {'✅ включён' if enabled else '⛔ отключён'}\n"
            f"Срок: {fmt_date(int(client.get('expiryTime') or rec.expiry_time))}\n"
            f"Лимит: {human_bytes(total) if total else 'без лимита'}\n"
            f"Использовано: {human_bytes(up + down)}\n"
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

        if not missing_ids:
            await call.message.answer(
                f"✅ {rec.email} уже подключён ко всем разрешённым inbound'ам.\n\n"
                f"Текущие ID: {', '.join(map(str, current_ids)) or 'нет'}"
            )
            await call.answer()
            return

        await xui.attach_client(rec.email, missing_ids)

        updated = await xui.get_client(rec.email)
        updated_ids = sorted({int(x) for x in (updated.get("inboundIds") or [])})

        by_id = {i.id: i for i in available}
        details = []
        for inbound_id in missing_ids:
            i = by_id.get(inbound_id)
            if i:
                details.append(f"• #{i.id} — {i.port}/{i.protocol} — {i.remark}")
            else:
                details.append(f"• #{inbound_id}")

        await call.message.answer(
            f"✅ Inbound'ы синхронизированы для {rec.email}.\n\n"
            "Добавлены:\n" + "\n".join(details) + "\n\n"
            f"Теперь привязан к ID: {', '.join(map(str, updated_ids))}"
        )
    except XUIError as e:
        await call.message.answer(
            "Не удалось синхронизировать inbound'ы.\n\n"
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
        await call.message.answer(f"✅ {rec.email} продлён до {fmt_date(new_expiry)}")
    except XUIError as e:
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
        await call.message.answer(f"⛔ {rec.email} отключён.")
    except (XUIError, AttributeError) as e:
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
        await call.message.answer(f"✅ {rec.email} включён.")
    except (XUIError, AttributeError) as e:
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
        await call.message.answer(f"🗑 {rec.email} удалён.")
    except XUIError as e:
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
        expiry = (now + settings.test_days * 86400) * 1000
        username = ""
        if getattr(message, "chat", None) and getattr(message.chat, "username", None):
            username = message.chat.username.strip().lower()
        email = f"tg_{username}" if username else f"tg_{tg_id}"
        sid = secrets.token_urlsafe(18)
        await xui.create_client(
            email=email, telegram_id=tg_id, sub_id=sid,
            inbound_ids=[i.id for i in chosen],
            total_bytes=settings.test_traffic_gb * 1024**3,
            expiry_time_ms=expiry, limit_ip=settings.test_ip_limit,
            comment="Created by Telegram bot v3"
        )
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

async def main():
    logging.basicConfig(level=logging.INFO)
    await db.init()
    bot = Bot(settings.bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
