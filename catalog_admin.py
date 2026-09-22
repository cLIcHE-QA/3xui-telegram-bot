from __future__ import annotations

import ipaddress
import re
import sqlite3
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlsplit

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import load_settings
from db import Database, HostRecord, PlanRecord, ServerGroupRecord
from xui import XUIClient, XUIError


settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
catalog_router = Router(name="catalog_admin")


class AddPlanStates(StatesGroup):
    name = State()
    duration = State()
    traffic = State()
    ip_limit = State()
    price = State()
    group = State()
    review = State()


class AddServerGroupStates(StatesGroup):
    name = State()
    description = State()


class AddHostStates(StatesGroup):
    label = State()
    hostname = State()
    role = State()


HOST_ROLE_LABELS = {
    "panel": "🖥 Panel",
    "subscription": "🔗 Subscription",
    "subscription-upstream": "🔐 Subscription upstream",
    "vpn": "🌐 VPN endpoint",
    "reality": "🪞 Reality/SNI",
    "other": "📌 Other",
}


def is_admin(tg_id: int) -> bool:
    return tg_id in settings.admin_telegram_ids


async def guard_call(call: CallbackQuery) -> bool:
    if not call.from_user or not is_admin(call.from_user.id):
        await call.answer("Недостаточно прав.", show_alert=True)
        return False
    return True


async def guard_message(message: Message, state: FSMContext) -> bool:
    if not message.from_user or not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("Недостаточно прав.")
        return False
    return True


def dashboard_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Dashboard", callback_data="admin:home")],
    ])


def infrastructure_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Infrastructure", callback_data="admin:section:infrastructure")],
    ])


def cancel_keyboard(callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data=callback)],
    ])


def _money(plan: PlanRecord) -> str:
    value = Decimal(plan.price_minor) / Decimal(100)
    if value == value.to_integral():
        amount = str(int(value))
    else:
        amount = f"{value:.2f}"
    return f"{amount} {plan.currency}"


def _parse_price(raw: str) -> tuple[int, str]:
    text = raw.strip().upper().replace(",", ".")
    parts = text.split()
    if not parts:
        raise ValueError("empty")
    currency = "RUB" if len(parts) == 1 else parts[1]
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("currency")
    try:
        value = Decimal(parts[0])
    except InvalidOperation as exc:
        raise ValueError("amount") from exc
    if value < 0 or value > Decimal("100000000"):
        raise ValueError("range")
    minor = int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return minor, currency


def _normalize_hostname(raw: str) -> str:
    text = raw.strip()
    if not text or any(ch.isspace() for ch in text):
        raise ValueError("hostname")
    parsed = urlsplit(text if "://" in text else f"//{text}")
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise ValueError("hostname")
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    if len(host) > 253 or not re.fullmatch(r"[a-z0-9.-]+", host):
        raise ValueError("hostname")
    labels = host.split(".")
    if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-") for label in labels):
        raise ValueError("hostname")
    return host


async def _group_name(group_id: int | None) -> str:
    if not group_id:
        return "не назначена"
    group = await db.get_server_group(group_id)
    return group.name if group else f"#{group_id} (удалена)"


# ---------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------


@catalog_router.callback_query(F.data == "admin:plans")
async def plans_list(call: CallbackQuery):
    if not await guard_call(call):
        return
    plans = await db.list_plans()
    rows: list[list[InlineKeyboardButton]] = []
    for plan in plans[:40]:
        icon = "🟢" if plan.active else "⚪"
        rows.append([InlineKeyboardButton(
            text=f"{icon} {plan.name} · {_money(plan)}",
            callback_data=f"admin:plan:{plan.id}",
        )])
    rows += [
        [InlineKeyboardButton(text="➕ Добавить тариф", callback_data="admin:planadd:start")],
        [InlineKeyboardButton(text="⬅ Dashboard", callback_data="admin:home")],
    ]
    active = sum(1 for p in plans if p.active)
    await call.message.answer(
        "💎 Plans\n\n"
        f"Тарифов: {len(plans)} · активных: {active}\n\n"
        "В v3.9 тарифы — production-каталог. Они пока не меняют текущую "
        "логику /create автоматически; подключение provisioning сделаем отдельно по согласованию.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@catalog_router.callback_query(F.data.regexp(r"^admin:plan:\d+$"))
async def plan_detail(call: CallbackQuery):
    if not await guard_call(call):
        return
    try:
        plan_id = int(call.data.rsplit(":", 1)[-1])
    except Exception:
        await call.answer("Некорректный тариф.", show_alert=True)
        return
    plan = await db.get_plan(plan_id)
    if not plan:
        await call.answer("Тариф не найден.", show_alert=True)
        return
    group_name = await _group_name(plan.server_group_id)
    traffic = "без лимита" if plan.traffic_gb == 0 else f"{plan.traffic_gb} GB"
    ip_limit = "без лимита" if plan.ip_limit == 0 else str(plan.ip_limit)
    status = "🟢 active" if plan.active else "⚪ disabled"
    text = (
        f"💎 {plan.name}\n\n"
        f"Статус: {status}\n"
        f"Срок: {plan.duration_days} дней\n"
        f"Трафик: {traffic}\n"
        f"IP limit: {ip_limit}\n"
        f"Цена: {_money(plan)}\n"
        f"Server Group: {group_name}\n\n"
        "Каталог не влияет на уже работающий provisioning до отдельного включения."
    )
    toggle_text = "⛔ Отключить" if plan.active else "✅ Включить"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗂 Выбрать Server Group", callback_data=f"admin:plan:groups:{plan.id}")],
        [InlineKeyboardButton(text=toggle_text, callback_data=f"admin:plan:toggle:{plan.id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:plan:deleteask:{plan.id}")],
        [InlineKeyboardButton(text="⬅ Plans", callback_data="admin:plans")],
    ])
    await call.message.answer(text, reply_markup=kb)
    await call.answer()


@catalog_router.callback_query(F.data == "admin:planadd:start")
async def plan_add_start(call: CallbackQuery, state: FSMContext):
    if not await guard_call(call):
        return
    await state.clear()
    await state.set_state(AddPlanStates.name)
    await call.message.answer(
        "💎 Новый тариф · 1/5\n\nНазвание тарифа:",
        reply_markup=cancel_keyboard("admin:planadd:cancel"),
    )
    await call.answer()


@catalog_router.message(AddPlanStates.name)
async def plan_add_name(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    name = (message.text or "").strip()
    if not 1 <= len(name) <= 64:
        await message.answer("Название должно быть от 1 до 64 символов.")
        return
    await state.update_data(name=name)
    await state.set_state(AddPlanStates.duration)
    await message.answer("💎 Новый тариф · 2/5\n\nСрок действия в днях, например 30:")


@catalog_router.message(AddPlanStates.duration)
async def plan_add_duration(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    try:
        value = int((message.text or "").strip())
        if not 1 <= value <= 3650:
            raise ValueError
    except ValueError:
        await message.answer("Введите целое число от 1 до 3650.")
        return
    await state.update_data(duration_days=value)
    await state.set_state(AddPlanStates.traffic)
    await message.answer("💎 Новый тариф · 3/5\n\nЛимит трафика в GB. 0 = без лимита:")


@catalog_router.message(AddPlanStates.traffic)
async def plan_add_traffic(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    try:
        value = int((message.text or "").strip())
        if not 0 <= value <= 1_000_000:
            raise ValueError
    except ValueError:
        await message.answer("Введите целое число от 0 до 1000000.")
        return
    await state.update_data(traffic_gb=value)
    await state.set_state(AddPlanStates.ip_limit)
    await message.answer("💎 Новый тариф · 4/5\n\nЛимит IP/устройств. 0 = без лимита:")


@catalog_router.message(AddPlanStates.ip_limit)
async def plan_add_ip_limit(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    try:
        value = int((message.text or "").strip())
        if not 0 <= value <= 1000:
            raise ValueError
    except ValueError:
        await message.answer("Введите целое число от 0 до 1000.")
        return
    await state.update_data(ip_limit=value)
    await state.set_state(AddPlanStates.price)
    await message.answer(
        "💎 Новый тариф · 5/5\n\nЦена, например:\n499\n499.90 RUB\n5 EUR\n\n0 = бесплатно."
    )


@catalog_router.message(AddPlanStates.price)
async def plan_add_price(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    try:
        price_minor, currency = _parse_price(message.text or "")
    except ValueError:
        await message.answer("Не понял цену. Пример: 499 RUB, 4.99 EUR или 0.")
        return
    await state.update_data(price_minor=price_minor, currency=currency)
    await state.set_state(AddPlanStates.group)
    groups = await db.list_server_groups()
    rows = [[InlineKeyboardButton(text="Без группы", callback_data="admin:planadd:group:none")]]
    for group in groups[:30]:
        rows.append([InlineKeyboardButton(
            text=f"🗂 {group.name}",
            callback_data=f"admin:planadd:group:{group.id}",
        )])
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="admin:planadd:cancel")])
    await message.answer(
        "Выбери Server Group для тарифа.\n"
        "Можно оставить без группы и назначить позже.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@catalog_router.callback_query(AddPlanStates.group, F.data.startswith("admin:planadd:group:"))
async def plan_add_group(call: CallbackQuery, state: FSMContext):
    if not await guard_call(call):
        return
    raw = call.data.rsplit(":", 1)[-1]
    group_id = None if raw == "none" else int(raw)
    if group_id is not None and not await db.get_server_group(group_id):
        await call.answer("Группа уже не существует.", show_alert=True)
        return
    await state.update_data(server_group_id=group_id)
    data = await state.get_data()
    await state.set_state(AddPlanStates.review)
    price_value = Decimal(int(data["price_minor"])) / Decimal(100)
    price_text = str(int(price_value)) if price_value == price_value.to_integral() else f"{price_value:.2f}"
    group_name = await _group_name(group_id)
    traffic = "без лимита" if int(data["traffic_gb"]) == 0 else f"{data['traffic_gb']} GB"
    ips = "без лимита" if int(data["ip_limit"]) == 0 else str(data["ip_limit"])
    await call.message.answer(
        "💎 Проверь тариф\n\n"
        f"Название: {data['name']}\n"
        f"Срок: {data['duration_days']} дней\n"
        f"Трафик: {traffic}\n"
        f"IP limit: {ips}\n"
        f"Цена: {price_text} {data['currency']}\n"
        f"Server Group: {group_name}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Создать", callback_data="admin:planadd:save")],
            [InlineKeyboardButton(text="Отмена", callback_data="admin:planadd:cancel")],
        ]),
    )
    await call.answer()


@catalog_router.callback_query(AddPlanStates.review, F.data == "admin:planadd:save")
async def plan_add_save(call: CallbackQuery, state: FSMContext):
    if not await guard_call(call):
        return
    data = await state.get_data()
    try:
        plan_id = await db.create_plan(
            name=str(data["name"]),
            duration_days=int(data["duration_days"]),
            traffic_gb=int(data["traffic_gb"]),
            ip_limit=int(data["ip_limit"]),
            price_minor=int(data["price_minor"]),
            currency=str(data["currency"]),
            server_group_id=data.get("server_group_id"),
        )
    except sqlite3.IntegrityError:
        await call.message.answer("Тариф с таким названием уже существует.", reply_markup=dashboard_back())
        await state.clear()
        await call.answer()
        return
    await state.clear()
    await call.message.answer(
        f"✅ Тариф создан: #{plan_id} · {data['name']}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Открыть тариф", callback_data=f"admin:plan:{plan_id}")],
            [InlineKeyboardButton(text="⬅ Plans", callback_data="admin:plans")],
        ]),
    )
    await call.answer()


@catalog_router.callback_query(F.data == "admin:planadd:cancel")
async def plan_add_cancel(call: CallbackQuery, state: FSMContext):
    if not await guard_call(call):
        return
    await state.clear()
    await call.message.answer("Создание тарифа отменено.", reply_markup=dashboard_back())
    await call.answer()


@catalog_router.callback_query(F.data.startswith("admin:plan:toggle:"))
async def plan_toggle(call: CallbackQuery):
    if not await guard_call(call):
        return
    plan_id = int(call.data.rsplit(":", 1)[-1])
    plan = await db.get_plan(plan_id)
    if not plan:
        await call.answer("Тариф не найден.", show_alert=True)
        return
    await db.set_plan_active(plan_id, not bool(plan.active))
    await call.message.answer(
        "✅ Статус тарифа обновлён.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Открыть тариф", callback_data=f"admin:plan:{plan_id}")],
            [InlineKeyboardButton(text="⬅ Plans", callback_data="admin:plans")],
        ]),
    )
    await call.answer()


@catalog_router.callback_query(F.data.startswith("admin:plan:groups:"))
async def plan_group_select(call: CallbackQuery):
    if not await guard_call(call):
        return
    plan_id = int(call.data.rsplit(":", 1)[-1])
    if not await db.get_plan(plan_id):
        await call.answer("Тариф не найден.", show_alert=True)
        return
    groups = await db.list_server_groups()
    rows = [[InlineKeyboardButton(
        text="Без группы",
        callback_data=f"admin:plan:setgroup:{plan_id}:none",
    )]]
    for group in groups[:30]:
        rows.append([InlineKeyboardButton(
            text=f"🗂 {group.name}",
            callback_data=f"admin:plan:setgroup:{plan_id}:{group.id}",
        )])
    rows.append([InlineKeyboardButton(text="⬅ Тариф", callback_data=f"admin:plan:{plan_id}")])
    await call.message.answer(
        "Выбери Server Group для тарифа:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@catalog_router.callback_query(F.data.startswith("admin:plan:setgroup:"))
async def plan_set_group(call: CallbackQuery):
    if not await guard_call(call):
        return
    parts = call.data.split(":")
    plan_id = int(parts[-2])
    raw = parts[-1]
    group_id = None if raw == "none" else int(raw)
    if group_id is not None and not await db.get_server_group(group_id):
        await call.answer("Группа не найдена.", show_alert=True)
        return
    await db.set_plan_group(plan_id, group_id)
    await call.answer("Server Group сохранена.")
    # Reuse detail rendering through a fresh synthetic callback is undesirable;
    # return a compact success card instead.
    await call.message.answer(
        f"✅ Server Group: {await _group_name(group_id)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅ Тариф", callback_data=f"admin:plan:{plan_id}")],
        ]),
    )


@catalog_router.callback_query(F.data.startswith("admin:plan:deleteask:"))
async def plan_delete_ask(call: CallbackQuery):
    if not await guard_call(call):
        return
    plan_id = int(call.data.rsplit(":", 1)[-1])
    plan = await db.get_plan(plan_id)
    if not plan:
        await call.answer("Тариф не найден.", show_alert=True)
        return
    await call.message.answer(
        f"Удалить тариф «{plan.name}»?\n\nПользователи и 3x-ui не изменятся.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ Да, удалить", callback_data=f"admin:plan:delete:{plan_id}")],
            [InlineKeyboardButton(text="Отмена", callback_data=f"admin:plan:{plan_id}")],
        ]),
    )
    await call.answer()


@catalog_router.callback_query(F.data.startswith("admin:plan:delete:"))
async def plan_delete(call: CallbackQuery):
    if not await guard_call(call):
        return
    plan_id = int(call.data.rsplit(":", 1)[-1])
    await db.delete_plan(plan_id)
    await call.message.answer("✅ Тариф удалён из каталога.", reply_markup=dashboard_back())
    await call.answer()


# ---------------------------------------------------------------------
# Server Groups
# ---------------------------------------------------------------------


@catalog_router.callback_query(F.data == "admin:servergroups")
async def server_groups_list(call: CallbackQuery):
    if not await guard_call(call):
        return
    groups = await db.list_server_groups()
    rows: list[list[InlineKeyboardButton]] = []
    for group in groups[:40]:
        members = await db.list_server_group_members(group.id)
        rows.append([InlineKeyboardButton(
            text=f"🗂 {group.name} · {len(members)} servers",
            callback_data=f"admin:servergroup:{group.id}",
        )])
    rows += [
        [InlineKeyboardButton(text="➕ Добавить группу", callback_data="admin:servergroupadd:start")],
        [InlineKeyboardButton(text="⬅ Infrastructure", callback_data="admin:section:infrastructure")],
    ]
    await call.message.answer(
        "🗂 Server Groups\n\n"
        f"Групп: {len(groups)}\n\n"
        "Группа объединяет Master и/или ноды. В v3.9 это control-plane каталог; "
        "применение групп при выдаче подписки включим отдельно по согласованию.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@catalog_router.callback_query(F.data == "admin:servergroupadd:start")
async def server_group_add_start(call: CallbackQuery, state: FSMContext):
    if not await guard_call(call):
        return
    await state.clear()
    await state.set_state(AddServerGroupStates.name)
    await call.message.answer(
        "🗂 Новая Server Group · 1/2\n\nНазвание, например Europe или Premium:",
        reply_markup=cancel_keyboard("admin:servergroupadd:cancel"),
    )
    await call.answer()


@catalog_router.message(AddServerGroupStates.name)
async def server_group_add_name(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    name = (message.text or "").strip()
    if not 1 <= len(name) <= 64:
        await message.answer("Название должно быть от 1 до 64 символов.")
        return
    await state.update_data(name=name)
    await state.set_state(AddServerGroupStates.description)
    await message.answer("🗂 Новая Server Group · 2/2\n\nОписание или «-», если не нужно:")


@catalog_router.message(AddServerGroupStates.description)
async def server_group_add_description(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    data = await state.get_data()
    description = (message.text or "").strip()
    if description == "-":
        description = ""
    if len(description) > 300:
        await message.answer("Описание слишком длинное. Максимум 300 символов.")
        return
    try:
        group_id = await db.create_server_group(name=str(data["name"]), description=description)
    except sqlite3.IntegrityError:
        await message.answer("Группа с таким названием уже существует.", reply_markup=infrastructure_back())
        await state.clear()
        return
    await state.clear()
    await message.answer(
        f"✅ Server Group создана: #{group_id} · {data['name']}\n\nТеперь выбери серверы в карточке группы.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Открыть группу", callback_data=f"admin:servergroup:{group_id}")],
            [InlineKeyboardButton(text="⬅ Server Groups", callback_data="admin:servergroups")],
        ]),
    )


@catalog_router.callback_query(F.data == "admin:servergroupadd:cancel")
async def server_group_add_cancel(call: CallbackQuery, state: FSMContext):
    if not await guard_call(call):
        return
    await state.clear()
    await call.message.answer("Создание Server Group отменено.", reply_markup=infrastructure_back())
    await call.answer()


async def _server_group_card(group: ServerGroupRecord) -> tuple[str, InlineKeyboardMarkup]:
    members = await db.list_server_group_members(group.id)
    nodes_error = ""
    try:
        nodes = await xui.nodes_list()
    except XUIError as exc:
        nodes = []
        nodes_error = str(exc)[:160]

    selected = []
    if "master" in members:
        selected.append(f"{settings.master_flag} {settings.master_name}")
    node_by_key = {f"node_{n.id}": n for n in nodes}
    for key in sorted(members):
        if key == "master":
            continue
        node = node_by_key.get(key)
        selected.append(node.name if node else f"{key} (not discovered)")

    lines = [
        f"🗂 {group.name}",
        "",
        group.description or "Без описания",
        "",
        f"Серверов в группе: {len(members)}",
    ]
    if selected:
        lines += ["", "Members:"] + [f"• {name}" for name in selected]
    if nodes_error:
        lines += ["", f"⚠️ Nodes API: {nodes_error}"]
    lines += ["", "Изменение состава группы пока не меняет существующие подписки автоматически."]

    rows: list[list[InlineKeyboardButton]] = [[InlineKeyboardButton(
        text=f"{'✅' if 'master' in members else '⬜'} {settings.master_flag} {settings.master_name}",
        callback_data=f"admin:servergroup:toggle:{group.id}:master",
    )]]
    live_keys = set()
    for node in nodes[:30]:
        key = f"node_{node.id}"
        live_keys.add(key)
        icon = "✅" if key in members else "⬜"
        rows.append([InlineKeyboardButton(
            text=f"{icon} {node.name}",
            callback_data=f"admin:servergroup:toggle:{group.id}:{key}",
        )])
    for stale_key in sorted(members - {"master"} - live_keys):
        rows.append([InlineKeyboardButton(
            text=f"⚠️ {stale_key} · убрать",
            callback_data=f"admin:servergroup:toggle:{group.id}:{stale_key}",
        )])
    rows += [
        [InlineKeyboardButton(text="🗑 Удалить группу", callback_data=f"admin:servergroup:deleteask:{group.id}")],
        [InlineKeyboardButton(text="⬅ Server Groups", callback_data="admin:servergroups")],
    ]
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


@catalog_router.callback_query(F.data.regexp(r"^admin:servergroup:\d+$"))
async def server_group_detail(call: CallbackQuery):
    if not await guard_call(call):
        return
    group_id = int(call.data.rsplit(":", 1)[-1])
    group = await db.get_server_group(group_id)
    if not group:
        await call.answer("Группа не найдена.", show_alert=True)
        return
    text, kb = await _server_group_card(group)
    await call.message.answer(text, reply_markup=kb)
    await call.answer()


@catalog_router.callback_query(F.data.startswith("admin:servergroup:toggle:"))
async def server_group_toggle(call: CallbackQuery):
    if not await guard_call(call):
        return
    parts = call.data.split(":")
    group_id = int(parts[-2])
    member_key = parts[-1]
    group = await db.get_server_group(group_id)
    if not group:
        await call.answer("Группа не найдена.", show_alert=True)
        return
    members = await db.list_server_group_members(group_id)
    await db.set_server_group_member(group_id, member_key, member_key not in members)
    await call.answer("Состав группы обновлён.")
    text, kb = await _server_group_card(group)
    await call.message.answer(text, reply_markup=kb)


@catalog_router.callback_query(F.data.startswith("admin:servergroup:deleteask:"))
async def server_group_delete_ask(call: CallbackQuery):
    if not await guard_call(call):
        return
    group_id = int(call.data.rsplit(":", 1)[-1])
    group = await db.get_server_group(group_id)
    if not group:
        await call.answer("Группа не найдена.", show_alert=True)
        return
    await call.message.answer(
        f"Удалить Server Group «{group.name}»?\n\n"
        "У тарифов эта группа будет снята. 3x-ui и пользователи не изменятся.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ Да, удалить", callback_data=f"admin:servergroup:delete:{group_id}")],
            [InlineKeyboardButton(text="Отмена", callback_data=f"admin:servergroup:{group_id}")],
        ]),
    )
    await call.answer()


@catalog_router.callback_query(F.data.startswith("admin:servergroup:delete:"))
async def server_group_delete(call: CallbackQuery):
    if not await guard_call(call):
        return
    group_id = int(call.data.rsplit(":", 1)[-1])
    await db.delete_server_group(group_id)
    await call.message.answer("✅ Server Group удалена.", reply_markup=infrastructure_back())
    await call.answer()


# ---------------------------------------------------------------------
# Hosts
# ---------------------------------------------------------------------


@catalog_router.callback_query(F.data == "admin:hosts")
async def hosts_list(call: CallbackQuery):
    if not await guard_call(call):
        return
    hosts = await db.list_hosts()
    rows: list[list[InlineKeyboardButton]] = []
    for host in hosts[:50]:
        icon = "🟢" if host.enabled else "⚪"
        role = HOST_ROLE_LABELS.get(host.role, host.role)
        rows.append([InlineKeyboardButton(
            text=f"{icon} {host.hostname} · {role}",
            callback_data=f"admin:host:{host.id}",
        )])
    rows += [
        [InlineKeyboardButton(text="➕ Добавить host", callback_data="admin:hostadd:start")],
        [InlineKeyboardButton(text="🔎 Найти текущие hosts", callback_data="admin:hosts:discover")],
        [InlineKeyboardButton(text="⬅ Infrastructure", callback_data="admin:section:infrastructure")],
    ]
    enabled = sum(1 for h in hosts if h.enabled)
    await call.message.answer(
        "🌐 Hosts\n\n"
        f"Записей: {len(hosts)} · активных: {enabled}\n\n"
        "Это централизованный реестр доменов/IP и их ролей. v3.9 не меняет DNS, nginx "
        "или 3x-ui автоматически.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@catalog_router.callback_query(F.data == "admin:hosts:discover")
async def hosts_discover(call: CallbackQuery):
    if not await guard_call(call):
        return
    candidates = [
        (f"{settings.master_name} panel", settings.panel_url, "panel"),
        ("Public subscription", settings.compat_subscription_url_template, "subscription"),
        ("3x-ui subscription upstream", settings.subscription_url_template, "subscription-upstream"),
    ]
    added: list[str] = []
    for label, raw, role in candidates:
        if not raw:
            continue
        try:
            host = _normalize_hostname(raw)
        except ValueError:
            continue
        await db.upsert_host(label=label, hostname=host, role=role)
        added.append(f"{host} · {HOST_ROLE_LABELS.get(role, role)}")
    text = "✅ Текущие hosts синхронизированы с реестром."
    if added:
        text += "\n\n" + "\n".join(f"• {x}" for x in added)
    else:
        text += "\n\nПодходящих hosts в текущей конфигурации не найдено."
    await call.message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅ Hosts", callback_data="admin:hosts")],
        ]),
    )
    await call.answer()


@catalog_router.callback_query(F.data == "admin:hostadd:start")
async def host_add_start(call: CallbackQuery, state: FSMContext):
    if not await guard_call(call):
        return
    await state.clear()
    await state.set_state(AddHostStates.label)
    await call.message.answer(
        "🌐 Новый host · 1/3\n\nНазвание, например Public Subscription или NL VPN:",
        reply_markup=cancel_keyboard("admin:hostadd:cancel"),
    )
    await call.answer()


@catalog_router.message(AddHostStates.label)
async def host_add_label(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    label = (message.text or "").strip()
    if not 1 <= len(label) <= 80:
        await message.answer("Название должно быть от 1 до 80 символов.")
        return
    await state.update_data(label=label)
    await state.set_state(AddHostStates.hostname)
    await message.answer(
        "🌐 Новый host · 2/3\n\nHostname, IP или URL. Например:\nsub.example.com\nhttps://panel.example.com/basepath"
    )


@catalog_router.message(AddHostStates.hostname)
async def host_add_hostname(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    try:
        hostname = _normalize_hostname(message.text or "")
    except ValueError:
        await message.answer("Некорректный hostname/IP/URL.")
        return
    await state.update_data(hostname=hostname)
    await state.set_state(AddHostStates.role)
    rows = []
    for key in ("panel", "subscription", "vpn", "reality", "other"):
        rows.append([InlineKeyboardButton(
            text=HOST_ROLE_LABELS[key],
            callback_data=f"admin:hostadd:role:{key}",
        )])
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="admin:hostadd:cancel")])
    await message.answer(
        "🌐 Новый host · 3/3\n\nВыбери роль:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@catalog_router.callback_query(AddHostStates.role, F.data.startswith("admin:hostadd:role:"))
async def host_add_role(call: CallbackQuery, state: FSMContext):
    if not await guard_call(call):
        return
    role = call.data.rsplit(":", 1)[-1]
    if role not in HOST_ROLE_LABELS:
        await call.answer("Неизвестная роль.", show_alert=True)
        return
    data = await state.get_data()
    try:
        host_id = await db.create_host(label=str(data["label"]), hostname=str(data["hostname"]), role=role)
    except sqlite3.IntegrityError:
        await call.message.answer(
            "Такой hostname с этой ролью уже есть в реестре.",
            reply_markup=infrastructure_back(),
        )
        await state.clear()
        await call.answer()
        return
    await state.clear()
    await call.message.answer(
        f"✅ Host добавлен: {data['hostname']} · {HOST_ROLE_LABELS[role]}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Открыть host", callback_data=f"admin:host:{host_id}")],
            [InlineKeyboardButton(text="⬅ Hosts", callback_data="admin:hosts")],
        ]),
    )
    await call.answer()


@catalog_router.callback_query(F.data == "admin:hostadd:cancel")
async def host_add_cancel(call: CallbackQuery, state: FSMContext):
    if not await guard_call(call):
        return
    await state.clear()
    await call.message.answer("Добавление host отменено.", reply_markup=infrastructure_back())
    await call.answer()


@catalog_router.callback_query(F.data.regexp(r"^admin:host:\d+$"))
async def host_detail(call: CallbackQuery):
    if not await guard_call(call):
        return
    host_id = int(call.data.rsplit(":", 1)[-1])
    host = await db.get_host(host_id)
    if not host:
        await call.answer("Host не найден.", show_alert=True)
        return
    role = HOST_ROLE_LABELS.get(host.role, host.role)
    text = (
        f"🌐 {host.label}\n\n"
        f"Host: {host.hostname}\n"
        f"Role: {role}\n"
        f"Status: {'🟢 enabled' if host.enabled else '⚪ disabled'}\n\n"
        "Эта запись — metadata registry. Изменения здесь не переписывают DNS/nginx/3x-ui."
    )
    toggle = "⛔ Отключить" if host.enabled else "✅ Включить"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle, callback_data=f"admin:host:toggle:{host.id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:host:deleteask:{host.id}")],
        [InlineKeyboardButton(text="⬅ Hosts", callback_data="admin:hosts")],
    ])
    await call.message.answer(text, reply_markup=kb)
    await call.answer()


@catalog_router.callback_query(F.data.startswith("admin:host:toggle:"))
async def host_toggle(call: CallbackQuery):
    if not await guard_call(call):
        return
    host_id = int(call.data.rsplit(":", 1)[-1])
    host = await db.get_host(host_id)
    if not host:
        await call.answer("Host не найден.", show_alert=True)
        return
    await db.set_host_enabled(host_id, not bool(host.enabled))
    await call.answer("Статус host обновлён.")
    await call.message.answer(
        "✅ Статус обновлён.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Открыть host", callback_data=f"admin:host:{host_id}")],
            [InlineKeyboardButton(text="⬅ Hosts", callback_data="admin:hosts")],
        ]),
    )


@catalog_router.callback_query(F.data.startswith("admin:host:deleteask:"))
async def host_delete_ask(call: CallbackQuery):
    if not await guard_call(call):
        return
    host_id = int(call.data.rsplit(":", 1)[-1])
    host = await db.get_host(host_id)
    if not host:
        await call.answer("Host не найден.", show_alert=True)
        return
    await call.message.answer(
        f"Удалить из реестра {host.hostname} ({HOST_ROLE_LABELS.get(host.role, host.role)})?\n\n"
        "DNS/nginx/3x-ui изменены не будут.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ Да, удалить", callback_data=f"admin:host:delete:{host_id}")],
            [InlineKeyboardButton(text="Отмена", callback_data=f"admin:host:{host_id}")],
        ]),
    )
    await call.answer()


@catalog_router.callback_query(F.data.startswith("admin:host:delete:"))
async def host_delete(call: CallbackQuery):
    if not await guard_call(call):
        return
    host_id = int(call.data.rsplit(":", 1)[-1])
    await db.delete_host(host_id)
    await call.message.answer("✅ Host удалён из реестра.", reply_markup=infrastructure_back())
    await call.answer()
