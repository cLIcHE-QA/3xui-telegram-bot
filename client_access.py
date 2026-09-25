from __future__ import annotations

import secrets
import time

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_ui import render_callback
from config import load_settings
from db import Database, UserRecord
from inbound_policy import is_managed_inbound
from provisioning import ProvisioningEngine
from version import APP_VERSION
from xui import XUIClient, XUIError


settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
provisioner = ProvisioningEngine(db, xui, settings)

client_access_router = Router(name="client_access")


def is_allowed(tg_id: int) -> bool:
    return (
        tg_id in settings.allowed_telegram_ids
        or tg_id in settings.admin_telegram_ids
    )


def user_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Проверить inbound'ы", callback_data="inbounds")],
        [InlineKeyboardButton(text="🧪 Создать тестовый доступ", callback_data="create")],
        [InlineKeyboardButton(text="🔗 Моя подписка", callback_data="subscription")],
    ])


async def guard_message(message: Message) -> bool:
    if not message.from_user or not is_allowed(message.from_user.id):
        await message.answer("Нет доступа.")
        return False
    return True


def choose_inbounds(inbounds):
    return [
        inbound
        for inbound in inbounds
        if inbound.enable and is_managed_inbound(settings, inbound)
    ]


def sub_url(sub_id: str) -> str:
    template = (
        settings.compat_subscription_url_template
        or settings.subscription_url_template
    )
    return template.format(sub_id=sub_id)


@client_access_router.message(CommandStart())
async def start(message: Message):
    if not await guard_message(message):
        return
    await message.answer(
        f"3x-ui Telegram bot v{APP_VERSION}",
        reply_markup=user_menu(),
    )


@client_access_router.message(Command("inbounds"))
async def inbounds_cmd(message: Message):
    if not await guard_message(message):
        return
    await show_inbounds(message)


@client_access_router.callback_query(F.data == "inbounds")
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
            f"• ID #{i.id} | {i.port} | {i.protocol}\n"
            f"  tag: {i.tag}\n"
            f"  name: {i.remark}"
            for i in chosen
        ]
        await message.answer(
            "Будут выданы:\n\n" + ("\n\n".join(lines) or "Ничего")
        )
    except XUIError as exc:
        await message.answer(f"Ошибка 3x-ui: {exc}")


@client_access_router.message(Command("create"))
async def create_cmd(message: Message):
    if not await guard_message(message):
        return
    await create_user(message.from_user.id, message)


@client_access_router.callback_query(F.data == "create")
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
                    tg_id,
                    client["email"],
                    client["subId"],
                    int(client.get("expiryTime") or 0),
                    int(time.time()),
                )
                await db.put(rec)
                await message.answer(f"Восстановлен:\n{sub_url(rec.sub_id)}")
                return

        default_plan, policy = await provisioner.new_user_plan()
        now = int(time.time())
        provisioning_note = ""

        if default_plan and policy:
            inbound_ids = list(policy.actionable_inbound_ids)
            if not inbound_ids:
                await message.answer(
                    "Тариф по умолчанию для согласования настроен, но сейчас нет доступных "
                    "целевых inbound'ов. Попроси администратора проверить "
                    "Тариф → Группа серверов → Ноды/Inbound'ы."
                )
                return
            duration_days = max(0, default_plan.duration_days)
            traffic_gb = max(0, default_plan.traffic_gb)
            ip_limit = max(0, default_plan.ip_limit)
            expiry = (
                (now + duration_days * 86400) * 1000
                if duration_days
                else 0
            )
            provisioning_note = f"Тариф: {default_plan.name}"
        else:
            chosen = choose_inbounds(await xui.inbound_options())
            if not chosen:
                await message.answer("Нет подходящих inbound'ов.")
                return
            inbound_ids = [i.id for i in chosen]
            try:
                duration_days = int(
                    await db.get_runtime_setting(
                        "trial_days",
                        str(settings.test_days),
                    )
                    or settings.test_days
                )
                traffic_gb = int(
                    await db.get_runtime_setting(
                        "trial_traffic_gb",
                        str(settings.test_traffic_gb),
                    )
                    or settings.test_traffic_gb
                )
                ip_limit = int(
                    await db.get_runtime_setting(
                        "trial_ip_limit",
                        str(settings.test_ip_limit),
                    )
                    or settings.test_ip_limit
                )
            except (TypeError, ValueError):
                duration_days = settings.test_days
                traffic_gb = settings.test_traffic_gb
                ip_limit = settings.test_ip_limit
            expiry = (now + duration_days * 86400) * 1000
            provisioning_note = "Политика совместимости пробного доступа"

        username = ""
        if (
            getattr(message, "chat", None)
            and getattr(message.chat, "username", None)
        ):
            username = message.chat.username.strip().lower()
        email = f"tg_{username}" if username else f"tg_{tg_id}"
        sid = secrets.token_urlsafe(18)

        await xui.create_client(
            email=email,
            telegram_id=tg_id,
            sub_id=sid,
            inbound_ids=inbound_ids,
            total_bytes=traffic_gb * 1024**3,
            expiry_time_ms=expiry,
            limit_ip=ip_limit,
            comment=(
                f"Создано Telegram-ботом v{APP_VERSION} · "
                f"{provisioning_note}"
            ),
            flow=settings.vless_flow,
        )
        if settings.vless_flow:
            await xui.bulk_adjust_clients(
                [email],
                flow=settings.vless_flow,
            )

        await db.put(UserRecord(tg_id, email, sid, expiry, now))

        if default_plan and policy:
            await db.upsert_user_profile(
                tg_id,
                plan_id=default_plan.id,
                server_group_id=default_plan.server_group_id,
                note="",
                preserve_unspecified=False,
            )

        lines = ["✅ Создан", "", sub_url(sid)]
        if default_plan and policy:
            lines += [
                "",
                f"💎 Тариф: {default_plan.name}",
                f"📡 Inbound'ы: {', '.join(map(str, inbound_ids))}",
            ]
            if policy.unavailable_members:
                lines.append(
                    "⏸ Часть нод недоступна; администратор сможет "
                    "выполнить согласование позже."
                )
        await message.answer("\n".join(lines))
    except XUIError as exc:
        await message.answer(f"Ошибка 3x-ui: {exc}")


@client_access_router.message(Command("subscription"))
async def sub_cmd(message: Message):
    if not await guard_message(message):
        return
    rec = await db.get(message.from_user.id)
    if rec:
        await message.answer(sub_url(rec.sub_id))
    else:
        await message.answer("Сначала /create")


@client_access_router.callback_query(F.data == "subscription")
async def sub_cb(call: CallbackQuery):
    if not call.from_user or not is_allowed(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return
    rec = await db.get(call.from_user.id)
    await render_callback(
        call,
        sub_url(rec.sub_id) if rec else "Сначала создай доступ.",
    )
    await call.answer()
