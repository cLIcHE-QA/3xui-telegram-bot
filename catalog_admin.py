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
from provisioning import ProvisioningEngine, is_managed_inbound, inbound_member_key
from audit import audit_from_call, audit_from_message
from admin_ui import render_callback, render_input
from admin_auth import authorize_callback, authorize_message
from node_ui import node_display_name


settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
catalog_router = Router(name="catalog_admin")
provisioner = ProvisioningEngine(db, xui, settings)


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
    "panel": "🖥 Панель",
    "subscription": "🔗 Подписка",
    "subscription-upstream": "🔐 Источник подписки",
    "vpn": "🌐 VPN endpoint",
    "reality": "🪞 Reality/SNI",
    "other": "📌 Другое",
}

INBOUND_MODE_LABELS = {
    "all_managed": "все управляемые",
    "selected": "выбранные",
}


def inbound_mode_text(value: str) -> str:
    return INBOUND_MODE_LABELS.get(value, value)


async def guard_call(call: CallbackQuery) -> bool:
    ok, _ = await authorize_callback(db, settings, call)
    return ok


async def guard_message(message: Message, state: FSMContext) -> bool:
    if not message.from_user:
        await state.clear()
        return False
    ok, _ = await authorize_message(db, settings, message.from_user.id, minimum="admin")
    if not ok:
        await state.clear()
        await render_input(message, "Недостаточно прав.")
        return False
    return True


def dashboard_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Панель администратора", callback_data="admin:home")],
    ])


def infrastructure_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Инфраструктура", callback_data="admin:section:infrastructure")],
    ])


def plans_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Тарифы", callback_data="admin:plans")],
    ])


def server_groups_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Группы серверов", callback_data="admin:servergroups")],
    ])


def hosts_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Хосты", callback_data="admin:hosts")],
    ])


def cancel_keyboard(callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✖ Отмена", callback_data=callback)],
    ])


def _money(plan: PlanRecord) -> str:
    value = Decimal(plan.price_minor) / Decimal(100)
    if value == value.to_integral():
        amount = str(int(value))
    else:
        amount = f"{value:.2f}"
    return f"{amount} {plan.currency}"


def _parse_price(raw: str, default_currency: str = "RUB") -> tuple[int, str]:
    text = raw.strip().upper().replace(",", ".")
    parts = text.split()
    if not parts:
        raise ValueError("empty")
    currency = default_currency.upper() if len(parts) == 1 else parts[1]
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
    raw_default = await db.get_runtime_setting("default_plan_id", "")
    try:
        default_plan_id = int(raw_default or 0)
    except (TypeError, ValueError):
        default_plan_id = 0
    rows: list[list[InlineKeyboardButton]] = []
    for plan in plans[:40]:
        icon = "🟢" if plan.active else "⚪"
        default_icon = "⭐ " if plan.id == default_plan_id else ""
        rows.append([InlineKeyboardButton(
            text=f"{default_icon}{icon} {plan.name} · {_money(plan)}",
            callback_data=f"admin:plan:{plan.id}",
        )])
    rows += [
        [InlineKeyboardButton(text="➕ Добавить тариф", callback_data="admin:planadd:start")],
        [InlineKeyboardButton(text="⬅ Панель администратора", callback_data="admin:home")],
    ]
    active = sum(1 for p in plans if p.active)
    await render_callback(call, 
        "💎 Тарифы\n\n"
        f"Тарифов: {len(plans)} · активных: {active}\n\n"
        "Тарифы участвуют в согласовании доступа. ⭐ отмечает тариф по умолчанию для новых пользователей. "
        "Тариф задаёт лимиты, а группа серверов — серверы и inbound-политику.",
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
    status = "🟢 активен" if plan.active else "⚪ отключён"
    raw_default = await db.get_runtime_setting("default_plan_id", "")
    try:
        is_default = int(raw_default or 0) == plan.id
    except (TypeError, ValueError):
        is_default = False
    try:
        policy = await provisioner.policy_for_plan(plan)
        target_text = f"{len(policy.desired_inbound_ids)} целевых / {len(policy.actionable_inbound_ids)} доступно"
        policy_warn = f"\n⚠️ {'; '.join(policy.warnings[:2])}" if policy.warnings else ""
    except Exception as exc:
        target_text = "ошибка расчёта"
        policy_warn = f"\n⚠️ {type(exc).__name__}: {str(exc)[:160]}"
    text = (
        f"💎 {plan.name}\n\n"
        f"Статус: {status}\n"
        f"По умолчанию для новых пользователей: {'⭐ да' if is_default else 'нет'}\n"
        f"Срок: {plan.duration_days} дней\n"
        f"Трафик: {traffic}\n"
        f"Лимит IP: {ip_limit}\n"
        f"Цена: {_money(plan)}\n"
        f"Группа серверов: {group_name}\n"
        f"Цели согласования: {target_text}"
        f"{policy_warn}"
    )
    toggle_text = "⛔ Отключить" if plan.active else "✅ Включить"
    default_text = "⭐ Убрать тариф по умолчанию" if is_default else "⭐ Сделать тарифом по умолчанию для новых пользователей"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗂 Выбрать группу серверов", callback_data=f"admin:plan:groups:{plan.id}")],
        [InlineKeyboardButton(text="🚀 Предпросмотр согласования", callback_data=f"admin:plan:preview:{plan.id}")],
        [InlineKeyboardButton(text=default_text, callback_data=f"admin:plan:default:{plan.id}")],
        [InlineKeyboardButton(text=toggle_text, callback_data=f"admin:plan:toggle:{plan.id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:plan:deleteask:{plan.id}")],
        [InlineKeyboardButton(text="⬅ Тарифы", callback_data="admin:plans")],
    ])
    await render_callback(call, text, reply_markup=kb)
    await call.answer()


@catalog_router.callback_query(F.data == "admin:planadd:start")
async def plan_add_start(call: CallbackQuery, state: FSMContext):
    if not await guard_call(call):
        return
    await state.clear()
    await state.set_state(AddPlanStates.name)
    await render_callback(call, 
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
        await render_input(message, "Название должно быть от 1 до 64 символов.", reply_markup=cancel_keyboard("admin:planadd:cancel"))
        return
    await state.update_data(name=name)
    await state.set_state(AddPlanStates.duration)
    await render_input(message, "💎 Новый тариф · 2/5\n\nСрок действия в днях, например 30:", reply_markup=cancel_keyboard("admin:planadd:cancel"))


@catalog_router.message(AddPlanStates.duration)
async def plan_add_duration(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    try:
        value = int((message.text or "").strip())
        if not 1 <= value <= 3650:
            raise ValueError
    except ValueError:
        await render_input(message, "Введите целое число от 1 до 3650.", reply_markup=cancel_keyboard("admin:planadd:cancel"))
        return
    await state.update_data(duration_days=value)
    await state.set_state(AddPlanStates.traffic)
    await render_input(message, "💎 Новый тариф · 3/5\n\nЛимит трафика в GB. 0 = без лимита:", reply_markup=cancel_keyboard("admin:planadd:cancel"))


@catalog_router.message(AddPlanStates.traffic)
async def plan_add_traffic(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    try:
        value = int((message.text or "").strip())
        if not 0 <= value <= 1_000_000:
            raise ValueError
    except ValueError:
        await render_input(message, "Введите целое число от 0 до 1000000.", reply_markup=cancel_keyboard("admin:planadd:cancel"))
        return
    await state.update_data(traffic_gb=value)
    await state.set_state(AddPlanStates.ip_limit)
    await render_input(message, "💎 Новый тариф · 4/5\n\nЛимит IP/устройств. 0 = без лимита:", reply_markup=cancel_keyboard("admin:planadd:cancel"))


@catalog_router.message(AddPlanStates.ip_limit)
async def plan_add_ip_limit(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    try:
        value = int((message.text or "").strip())
        if not 0 <= value <= 1000:
            raise ValueError
    except ValueError:
        await render_input(message, "Введите целое число от 0 до 1000.", reply_markup=cancel_keyboard("admin:planadd:cancel"))
        return
    await state.update_data(ip_limit=value)
    await state.set_state(AddPlanStates.price)
    await render_input(message, 
        "💎 Новый тариф · 5/5\n\nЦена, например:\n499\n499.90 RUB\n5 EUR\n\n0 = бесплатно.",
        reply_markup=cancel_keyboard("admin:planadd:cancel"),
    )


@catalog_router.message(AddPlanStates.price)
async def plan_add_price(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    try:
        default_currency = str(await db.get_runtime_setting("default_currency", "RUB") or "RUB").upper()
        price_minor, currency = _parse_price(message.text or "", default_currency)
    except ValueError:
        await render_input(message, "Не понял цену. Пример: 499 RUB, 4.99 EUR или 0.", reply_markup=cancel_keyboard("admin:planadd:cancel"))
        return
    await state.update_data(price_minor=price_minor, currency=currency)
    await state.set_state(AddPlanStates.group)
    groups = await db.list_server_groups()
    rows = [[InlineKeyboardButton(text="🚫 Без группы", callback_data="admin:planadd:group:none")]]
    for group in groups[:30]:
        rows.append([InlineKeyboardButton(
            text=f"🗂 {group.name}",
            callback_data=f"admin:planadd:group:{group.id}",
        )])
    rows.append([InlineKeyboardButton(text="✖ Отмена", callback_data="admin:planadd:cancel")])
    await render_input(message, 
        "Выбери группу серверов для тарифа.\n"
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
    await render_callback(call, 
        "💎 Проверь тариф\n\n"
        f"Название: {data['name']}\n"
        f"Срок: {data['duration_days']} дней\n"
        f"Трафик: {traffic}\n"
        f"Лимит IP: {ips}\n"
        f"Цена: {price_text} {data['currency']}\n"
        f"Группа серверов: {group_name}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Создать", callback_data="admin:planadd:save")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:planadd:cancel")],
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
        await render_callback(call, "Тариф с таким названием уже существует.", reply_markup=plans_back())
        await state.clear()
        await call.answer()
        return
    await audit_from_call(
        db, call, "plan.create", target_type="plan", target_id=str(plan_id),
        details=f"name={data['name']}; duration={data['duration_days']}; traffic_gb={data['traffic_gb']}",
    )
    await state.clear()
    await render_callback(call, 
        f"✅ Тариф создан: #{plan_id} · {data['name']}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Открыть тариф", callback_data=f"admin:plan:{plan_id}")],
            [InlineKeyboardButton(text="⬅ Тарифы", callback_data="admin:plans")],
        ]),
    )
    await call.answer()


@catalog_router.callback_query(F.data == "admin:planadd:cancel")
async def plan_add_cancel(call: CallbackQuery, state: FSMContext):
    if not await guard_call(call):
        return
    await state.clear()
    await render_callback(call, "Создание тарифа отменено.", reply_markup=plans_back())
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
    new_active = not bool(plan.active)
    await db.set_plan_active(plan_id, new_active)
    await audit_from_call(
        db, call, "plan.toggle", target_type="plan", target_id=str(plan_id),
        details=f"active={new_active}",
    )
    await render_callback(call, 
        "✅ Статус тарифа обновлён.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Открыть тариф", callback_data=f"admin:plan:{plan_id}")],
            [InlineKeyboardButton(text="⬅ Тарифы", callback_data="admin:plans")],
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
        text="🚫 Без группы",
        callback_data=f"admin:plan:setgroup:{plan_id}:none",
    )]]
    for group in groups[:30]:
        rows.append([InlineKeyboardButton(
            text=f"🗂 {group.name}",
            callback_data=f"admin:plan:setgroup:{plan_id}:{group.id}",
        )])
    rows.append([InlineKeyboardButton(text="⬅ Тариф", callback_data=f"admin:plan:{plan_id}")])
    await render_callback(call, 
        "Выбери группу серверов для тарифа:",
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
    await audit_from_call(
        db, call, "plan.set_group", target_type="plan", target_id=str(plan_id),
        details=f"server_group_id={group_id}",
    )
    await call.answer("Группа серверов сохранена.")
    # Reuse detail rendering through a fresh synthetic callback is undesirable;
    # return a compact success card instead.
    await render_callback(call, 
        f"✅ Группа серверов: {await _group_name(group_id)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅ Тариф", callback_data=f"admin:plan:{plan_id}")],
        ]),
    )


@catalog_router.callback_query(F.data.startswith("admin:plan:default:"))
async def plan_set_default(call: CallbackQuery):
    if not await guard_call(call):
        return
    plan_id = int(call.data.rsplit(":", 1)[-1])
    plan = await db.get_plan(plan_id)
    if not plan:
        await call.answer("Тариф не найден.", show_alert=True)
        return
    raw = await db.get_runtime_setting("default_plan_id", "")
    try:
        current = int(raw or 0)
    except (TypeError, ValueError):
        current = 0
    if current == plan_id:
        await db.delete_runtime_setting("default_plan_id")
        await audit_from_call(db, call, "plan.default", target_type="plan", target_id=str(plan_id), details="enabled=False")
        await call.answer("Тариф по умолчанию для новых пользователей снят.")
    else:
        if not plan.active:
            await call.answer("Сначала включи тариф.", show_alert=True)
            return
        try:
            policy = await provisioner.policy_for_plan(plan)
        except Exception as exc:
            await call.answer(f"Ошибка согласования: {str(exc)[:120]}", show_alert=True)
            return
        if plan.server_group_id and not policy.desired_inbound_ids:
            await call.answer("У группы серверов нет inbound'ов для согласования.", show_alert=True)
            return
        await db.set_runtime_setting("default_plan_id", str(plan_id), updated_by=call.from_user.id if call.from_user else 0)
        await audit_from_call(db, call, "plan.default", target_type="plan", target_id=str(plan_id), details="enabled=True")
        await call.answer("⭐ Тариф по умолчанию для новых пользователей установлен.")
    await render_callback(call, "Статус тарифа по умолчанию обновлён.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅ Тариф", callback_data=f"admin:plan:{plan_id}")]]))


@catalog_router.callback_query(F.data.startswith("admin:plan:preview:"))
async def plan_preview(call: CallbackQuery):
    if not await guard_call(call):
        return
    plan_id = int(call.data.rsplit(":", 1)[-1])
    plan = await db.get_plan(plan_id)
    if not plan:
        await call.answer("Тариф не найден.", show_alert=True)
        return
    try:
        policy = await provisioner.policy_for_plan(plan)
        lines = [
            f"🚀 Предпросмотр согласования · {plan.name}",
            "",
            f"Группа серверов: {policy.group.name if policy.group else 'режим совместимости «все управляемые»'}",
            f"Режим: {inbound_mode_text(policy.inbound_mode)}",
            f"Целевых inbound'ов: {len(policy.desired_inbound_ids)}",
            f"Доступно сейчас: {len(policy.actionable_inbound_ids)}",
        ]
        if policy.unavailable_members:
            lines.append(f"Недоступны: {', '.join(policy.unavailable_members)}")
        if policy.desired_inbound_ids:
            lines += ["", "Цели:"]
            for iid in policy.desired_inbound_ids[:30]:
                ib = policy.inbounds.get(iid)
                if ib:
                    server = settings.master_name if ib.node_id is None else policy.nodes.get(ib.node_id).name if policy.nodes.get(ib.node_id) else f"Нода #{ib.node_id}"
                    marker = "✅" if iid in policy.actionable_inbound_ids else "⏸"
                    lines.append(f"{marker} #{iid} · {server} · {ib.port}/{ib.protocol} · {ib.remark}")
        if policy.warnings:
            lines += ["", "Предупреждения:"] + [f"⚠️ {w}" for w in policy.warnings]
        await render_callback(call, "\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅ Тариф", callback_data=f"admin:plan:{plan_id}")]]))
    except Exception as exc:
        await render_callback(call, f"🔴 Предпросмотр согласования: {type(exc).__name__}: {exc}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅ Тариф", callback_data=f"admin:plan:{plan_id}")]]))
    await call.answer()


@catalog_router.callback_query(F.data.startswith("admin:plan:deleteask:"))
async def plan_delete_ask(call: CallbackQuery):
    if not await guard_call(call):
        return
    plan_id = int(call.data.rsplit(":", 1)[-1])
    plan = await db.get_plan(plan_id)
    if not plan:
        await call.answer("Тариф не найден.", show_alert=True)
        return
    await render_callback(call, 
        f"Удалить тариф «{plan.name}»?\n\nПользователи и 3x-ui не изменятся.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ Да, удалить", callback_data=f"admin:plan:delete:{plan_id}")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:plan:{plan_id}")],
        ]),
    )
    await call.answer()


@catalog_router.callback_query(F.data.startswith("admin:plan:delete:"))
async def plan_delete(call: CallbackQuery):
    if not await guard_call(call):
        return
    plan_id = int(call.data.rsplit(":", 1)[-1])
    plan = await db.get_plan(plan_id)
    raw_default = await db.get_runtime_setting("default_plan_id", "")
    if str(raw_default or "") == str(plan_id):
        await db.delete_runtime_setting("default_plan_id")
    await db.delete_plan(plan_id)
    await audit_from_call(
        db, call, "plan.delete", target_type="plan", target_id=str(plan_id),
        details=f"name={plan.name if plan else ''}",
    )
    await render_callback(call, "✅ Тариф удалён из каталога.", reply_markup=plans_back())
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
            text=f"🗂 {group.name} · серверов: {len(members)}",
            callback_data=f"admin:servergroup:{group.id}",
        )])
    rows += [
        [InlineKeyboardButton(text="➕ Добавить группу", callback_data="admin:servergroupadd:start")],
        [InlineKeyboardButton(text="⬅ Инфраструктура", callback_data="admin:section:infrastructure")],
    ]
    await render_callback(call, 
        "🗂 Группы серверов\n\n"
        f"Групп: {len(groups)}\n\n"
        "Группа объединяет Master и/или ноды и задаёт область согласования. "
        "Для каждой группы можно использовать все управляемые inbound'ы или выбрать конкретные.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@catalog_router.callback_query(F.data == "admin:servergroupadd:start")
async def server_group_add_start(call: CallbackQuery, state: FSMContext):
    if not await guard_call(call):
        return
    await state.clear()
    await state.set_state(AddServerGroupStates.name)
    await render_callback(call, 
        "🗂 Новая группа серверов · 1/2\n\nНазвание, например Основная или Резервная:",
        reply_markup=cancel_keyboard("admin:servergroupadd:cancel"),
    )
    await call.answer()


@catalog_router.message(AddServerGroupStates.name)
async def server_group_add_name(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    name = (message.text or "").strip()
    if not 1 <= len(name) <= 64:
        await render_input(message, "Название должно быть от 1 до 64 символов.", reply_markup=cancel_keyboard("admin:servergroupadd:cancel"))
        return
    await state.update_data(name=name)
    await state.set_state(AddServerGroupStates.description)
    await render_input(message, "🗂 Новая группа серверов · 2/2\n\nОписание или «-», если не нужно:", reply_markup=cancel_keyboard("admin:servergroupadd:cancel"))


@catalog_router.message(AddServerGroupStates.description)
async def server_group_add_description(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    data = await state.get_data()
    description = (message.text or "").strip()
    if description == "-":
        description = ""
    if len(description) > 300:
        await render_input(message, "Описание слишком длинное. Максимум 300 символов.", reply_markup=cancel_keyboard("admin:servergroupadd:cancel"))
        return
    try:
        group_id = await db.create_server_group(name=str(data["name"]), description=description)
    except sqlite3.IntegrityError:
        await render_input(message, "Группа с таким названием уже существует.", reply_markup=server_groups_back())
        await state.clear()
        return
    await audit_from_message(
        db, message, "server_group.create", target_type="server_group", target_id=str(group_id),
        details=f"name={data['name']}",
    )
    await state.clear()
    await render_input(message, 
        f"✅ Группа серверов создана: #{group_id} · {data['name']}\n\nТеперь выбери серверы в карточке группы.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Открыть группу", callback_data=f"admin:servergroup:{group_id}")],
            [InlineKeyboardButton(text="⬅ Группы серверов", callback_data="admin:servergroups")],
        ]),
    )


@catalog_router.callback_query(F.data == "admin:servergroupadd:cancel")
async def server_group_add_cancel(call: CallbackQuery, state: FSMContext):
    if not await guard_call(call):
        return
    await state.clear()
    await render_callback(call, "Создание группы серверов отменено.", reply_markup=server_groups_back())
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
        selected.append(node_display_name(node.name) if node else f"{key} (не обнаружена)")

    lines = [
        f"🗂 {group.name}",
        "",
        group.description or "Без описания",
        "",
        f"Серверов в группе: {len(members)}",
    ]
    if selected:
        lines += ["", "Участники:"] + [f"• {name}" for name in selected]
    if nodes_error:
        lines += ["", f"⚠️ API нод: {nodes_error}"]
    mode = await db.get_server_group_inbound_mode(group.id)
    selected_inbounds = await db.list_server_group_inbounds(group.id)
    lines += [
        "",
        f"Политика inbound'ов: {inbound_mode_text(mode)}" + (f" ({len(selected_inbounds)})" if mode == "selected" else ""),
        "Изменения применяются к пользователям через безопасное/строгое согласование; автоматически существующих клиентов не перестраиваем.",
    ]

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
            text=f"{icon} {node_display_name(node.name)}",
            callback_data=f"admin:servergroup:toggle:{group.id}:{key}",
        )])
    for stale_key in sorted(members - {"master"} - live_keys):
        rows.append([InlineKeyboardButton(
            text=f"⚠️ {stale_key} · убрать",
            callback_data=f"admin:servergroup:toggle:{group.id}:{stale_key}",
        )])
    rows += [
        [InlineKeyboardButton(text="📡 Inbound'ы согласования", callback_data=f"admin:servergroup:inbounds:{group.id}")],
        [InlineKeyboardButton(text="🗑 Удалить группу", callback_data=f"admin:servergroup:deleteask:{group.id}")],
        [InlineKeyboardButton(text="⬅ Группы серверов", callback_data="admin:servergroups")],
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
    await render_callback(call, text, reply_markup=kb)
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
    enabled = member_key not in members
    await db.set_server_group_member(group_id, member_key, enabled)
    await audit_from_call(
        db, call, "server_group.member", target_type="server_group", target_id=str(group_id),
        details=f"member={member_key}; enabled={enabled}",
    )
    await call.answer("Состав группы обновлён.")
    text, kb = await _server_group_card(group)
    await render_callback(call, text, reply_markup=kb)


@catalog_router.callback_query(F.data.startswith("admin:servergroup:inbounds:"))
async def server_group_inbounds(call: CallbackQuery):
    if not await guard_call(call):
        return
    group_id = int(call.data.rsplit(":", 1)[-1])
    group = await db.get_server_group(group_id)
    if not group:
        await call.answer("Группа не найдена.", show_alert=True)
        return
    members = await db.list_server_group_members(group_id)
    mode = await db.get_server_group_inbound_mode(group_id)
    selected = await db.list_server_group_inbounds(group_id)
    try:
        options = [i for i in await xui.inbound_options() if i.enable and is_managed_inbound(settings, i) and inbound_member_key(i) in members]
    except XUIError as exc:
        await render_callback(call, f"Ошибка 3x-ui: {exc}", reply_markup=infrastructure_back())
        await call.answer()
        return
    try:
        nodes = {n.id: n for n in await xui.nodes_list()}
    except XUIError:
        nodes = {}
    rows: list[list[InlineKeyboardButton]] = []
    if mode == "all_managed":
        rows.append([InlineKeyboardButton(text="✅ Режим: все управляемые", callback_data=f"admin:servergroup:inboundmode:{group_id}:selected")])
    else:
        rows.append([InlineKeyboardButton(text="🎯 Режим: выбранные", callback_data=f"admin:servergroup:inboundmode:{group_id}:all_managed")])
        for ib in options[:50]:
            server = settings.master_name if ib.node_id is None else nodes.get(ib.node_id).name if nodes.get(ib.node_id) else f"Нода #{ib.node_id}"
            rows.append([InlineKeyboardButton(
                text=f"{'✅' if ib.id in selected else '⬜'} #{ib.id} · {server} · {ib.port}/{ib.protocol}",
                callback_data=f"admin:servergroup:ibtoggle:{group_id}:{ib.id}",
            )])
    rows.append([InlineKeyboardButton(text="⬅ Группа серверов", callback_data=f"admin:servergroup:{group_id}")])
    text = (
        f"📡 Inbound'ы согласования · {group.name}\n\n"
        f"Режим: {inbound_mode_text(mode)}\n"
        f"Серверов-участников: {len(members)}\n"
        f"Доступных управляемых inbound'ов: {len(options)}\n\n"
        "Режим «все управляемые» автоматически включает все разрешённые управляемые inbound'ы на серверах группы. "
        "Режим «выбранные» позволяет зафиксировать конкретный набор."
    )
    await render_callback(call, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@catalog_router.callback_query(F.data.startswith("admin:servergroup:inboundmode:"))
async def server_group_inbound_mode(call: CallbackQuery):
    if not await guard_call(call):
        return
    parts = call.data.split(":")
    group_id = int(parts[-2])
    mode = parts[-1]
    if mode not in {"all_managed", "selected"}:
        await call.answer("Некорректный режим.", show_alert=True)
        return
    if mode == "selected":
        members = await db.list_server_group_members(group_id)
        try:
            options = [i for i in await xui.inbound_options() if i.enable and is_managed_inbound(settings, i) and inbound_member_key(i) in members]
        except XUIError as exc:
            await call.answer(f"3x-ui: {str(exc)[:120]}", show_alert=True)
            return
        await db.replace_server_group_inbounds(group_id, {i.id for i in options})
    await db.set_server_group_inbound_mode(group_id, mode)
    await audit_from_call(db, call, "server_group.inbound_mode", target_type="server_group", target_id=str(group_id), details=f"mode={mode}")
    await call.answer("Политика inbound'ов обновлена.")
    await render_callback(call, "Открой inbound'ы согласования ещё раз для настройки.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📡 Inbound'ы согласования", callback_data=f"admin:servergroup:inbounds:{group_id}")]]))


@catalog_router.callback_query(F.data.startswith("admin:servergroup:ibtoggle:"))
async def server_group_inbound_toggle(call: CallbackQuery):
    if not await guard_call(call):
        return
    parts = call.data.split(":")
    group_id, inbound_id = int(parts[-2]), int(parts[-1])
    if await db.get_server_group_inbound_mode(group_id) != "selected":
        await call.answer("Сначала включи режим «выбранные».", show_alert=True)
        return
    members = await db.list_server_group_members(group_id)
    try:
        valid = {
            i.id for i in await xui.inbound_options()
            if i.enable and is_managed_inbound(settings, i) and inbound_member_key(i) in members
        }
    except XUIError as exc:
        await call.answer(f"3x-ui: {str(exc)[:120]}", show_alert=True)
        return
    if inbound_id not in valid:
        await call.answer("Inbound не входит в управляемую область этой группы серверов.", show_alert=True)
        return
    selected = await db.list_server_group_inbounds(group_id)
    enabled = inbound_id not in selected
    await db.set_server_group_inbound(group_id, inbound_id, enabled)
    await audit_from_call(db, call, "server_group.inbound", target_type="server_group", target_id=str(group_id), details=f"inbound_id={inbound_id}; enabled={enabled}")
    await call.answer("Политика inbound'ов обновлена.")
    await render_callback(call, "Изменение сохранено.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📡 Продолжить", callback_data=f"admin:servergroup:inbounds:{group_id}")]]))


@catalog_router.callback_query(F.data.startswith("admin:servergroup:deleteask:"))
async def server_group_delete_ask(call: CallbackQuery):
    if not await guard_call(call):
        return
    group_id = int(call.data.rsplit(":", 1)[-1])
    group = await db.get_server_group(group_id)
    if not group:
        await call.answer("Группа не найдена.", show_alert=True)
        return
    await render_callback(call, 
        f"Удалить группу серверов «{group.name}»?\n\n"
        "У тарифов и профилей пользователей эта группа будет снята. Текущие привязки 3x-ui не изменятся до согласования.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ Да, удалить", callback_data=f"admin:servergroup:delete:{group_id}")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:servergroup:{group_id}")],
        ]),
    )
    await call.answer()


@catalog_router.callback_query(F.data.startswith("admin:servergroup:delete:"))
async def server_group_delete(call: CallbackQuery):
    if not await guard_call(call):
        return
    group_id = int(call.data.rsplit(":", 1)[-1])
    group = await db.get_server_group(group_id)
    await db.delete_server_group(group_id)
    await audit_from_call(
        db, call, "server_group.delete", target_type="server_group", target_id=str(group_id),
        details=f"name={group.name if group else ''}",
    )
    await render_callback(call, "✅ Группа серверов удалена.", reply_markup=server_groups_back())
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
        [InlineKeyboardButton(text="➕ Добавить хост", callback_data="admin:hostadd:start")],
        [InlineKeyboardButton(text="🔎 Найти текущие хосты", callback_data="admin:hosts:discover")],
        [InlineKeyboardButton(text="⬅ Инфраструктура", callback_data="admin:section:infrastructure")],
    ]
    enabled = sum(1 for h in hosts if h.enabled)
    await render_callback(call, 
        "🌐 Хосты\n\n"
        f"Записей: {len(hosts)} · активных: {enabled}\n\n"
        "Это централизованный реестр доменов/IP и их ролей. Изменения здесь не меняют DNS, nginx "
        "или 3x-ui автоматически.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@catalog_router.callback_query(F.data == "admin:hosts:discover")
async def hosts_discover(call: CallbackQuery):
    if not await guard_call(call):
        return
    candidates = [
        (f"{settings.master_name} панель", settings.panel_url, "panel"),
        ("Публичная подписка", settings.compat_subscription_url_template, "subscription"),
        ("Источник подписки 3x-ui", settings.subscription_url_template, "subscription-upstream"),
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
    await audit_from_call(
        db, call, "host.discover", target_type="hosts", target_id=str(len(added)),
        details="; ".join(added),
    )
    text = "✅ Текущие хосты синхронизированы с реестром."
    if added:
        text += "\n\n" + "\n".join(f"• {x}" for x in added)
    else:
        text += "\n\nПодходящих хостов в текущей конфигурации не найдено."
    await render_callback(call, 
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅ Хосты", callback_data="admin:hosts")],
        ]),
    )
    await call.answer()


@catalog_router.callback_query(F.data == "admin:hostadd:start")
async def host_add_start(call: CallbackQuery, state: FSMContext):
    if not await guard_call(call):
        return
    await state.clear()
    await state.set_state(AddHostStates.label)
    await render_callback(call, 
        "🌐 Новый хост · 1/3\n\nНазвание, например Публичная подписка или VPN-шлюз:",
        reply_markup=cancel_keyboard("admin:hostadd:cancel"),
    )
    await call.answer()


@catalog_router.message(AddHostStates.label)
async def host_add_label(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    label = (message.text or "").strip()
    if not 1 <= len(label) <= 80:
        await render_input(message, "Название должно быть от 1 до 80 символов.", reply_markup=cancel_keyboard("admin:hostadd:cancel"))
        return
    await state.update_data(label=label)
    await state.set_state(AddHostStates.hostname)
    await render_input(message, 
        "🌐 Новый хост · 2/3\n\nИмя хоста, IP или URL. Например:\nsub.example.com\nhttps://panel.example.com/basepath",
        reply_markup=cancel_keyboard("admin:hostadd:cancel"),
    )


@catalog_router.message(AddHostStates.hostname)
async def host_add_hostname(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    try:
        hostname = _normalize_hostname(message.text or "")
    except ValueError:
        await render_input(message, "Некорректное имя хоста/IP/URL.", reply_markup=cancel_keyboard("admin:hostadd:cancel"))
        return
    await state.update_data(hostname=hostname)
    await state.set_state(AddHostStates.role)
    rows = []
    for key in ("panel", "subscription", "vpn", "reality", "other"):
        rows.append([InlineKeyboardButton(
            text=HOST_ROLE_LABELS[key],
            callback_data=f"admin:hostadd:role:{key}",
        )])
    rows.append([InlineKeyboardButton(text="✖ Отмена", callback_data="admin:hostadd:cancel")])
    await render_input(message, 
        "🌐 Новый хост · 3/3\n\nВыбери роль:",
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
        await render_callback(call, 
            "Такой hostname с этой ролью уже есть в реестре.",
            reply_markup=hosts_back(),
        )
        await state.clear()
        await call.answer()
        return
    await audit_from_call(
        db, call, "host.create", target_type="host", target_id=str(host_id),
        details=f"hostname={data['hostname']}; role={role}",
    )
    await state.clear()
    await render_callback(call, 
        f"✅ Хост добавлен: {data['hostname']} · {HOST_ROLE_LABELS[role]}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Открыть хост", callback_data=f"admin:host:{host_id}")],
            [InlineKeyboardButton(text="⬅ Хосты", callback_data="admin:hosts")],
        ]),
    )
    await call.answer()


@catalog_router.callback_query(F.data == "admin:hostadd:cancel")
async def host_add_cancel(call: CallbackQuery, state: FSMContext):
    if not await guard_call(call):
        return
    await state.clear()
    await render_callback(call, "Добавление хоста отменено.", reply_markup=hosts_back())
    await call.answer()


@catalog_router.callback_query(F.data.regexp(r"^admin:host:\d+$"))
async def host_detail(call: CallbackQuery):
    if not await guard_call(call):
        return
    host_id = int(call.data.rsplit(":", 1)[-1])
    host = await db.get_host(host_id)
    if not host:
        await call.answer("Хост не найден.", show_alert=True)
        return
    role = HOST_ROLE_LABELS.get(host.role, host.role)
    text = (
        f"🌐 {host.label}\n\n"
        f"Хост: {host.hostname}\n"
        f"Роль: {role}\n"
        f"Статус: {'🟢 включён' if host.enabled else '⚪ отключён'}\n\n"
        "Эта запись — реестр метаданных. Изменения здесь не переписывают DNS/nginx/3x-ui."
    )
    toggle = "⛔ Отключить" if host.enabled else "✅ Включить"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle, callback_data=f"admin:host:toggle:{host.id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:host:deleteask:{host.id}")],
        [InlineKeyboardButton(text="⬅ Хосты", callback_data="admin:hosts")],
    ])
    await render_callback(call, text, reply_markup=kb)
    await call.answer()


@catalog_router.callback_query(F.data.startswith("admin:host:toggle:"))
async def host_toggle(call: CallbackQuery):
    if not await guard_call(call):
        return
    host_id = int(call.data.rsplit(":", 1)[-1])
    host = await db.get_host(host_id)
    if not host:
        await call.answer("Хост не найден.", show_alert=True)
        return
    new_enabled = not bool(host.enabled)
    await db.set_host_enabled(host_id, new_enabled)
    await audit_from_call(
        db, call, "host.toggle", target_type="host", target_id=str(host_id),
        details=f"hostname={host.hostname}; enabled={new_enabled}",
    )
    await call.answer("Статус хоста обновлён.")
    await render_callback(call, 
        "✅ Статус обновлён.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Открыть хост", callback_data=f"admin:host:{host_id}")],
            [InlineKeyboardButton(text="⬅ Хосты", callback_data="admin:hosts")],
        ]),
    )


@catalog_router.callback_query(F.data.startswith("admin:host:deleteask:"))
async def host_delete_ask(call: CallbackQuery):
    if not await guard_call(call):
        return
    host_id = int(call.data.rsplit(":", 1)[-1])
    host = await db.get_host(host_id)
    if not host:
        await call.answer("Хост не найден.", show_alert=True)
        return
    await render_callback(call, 
        f"Удалить из реестра {host.hostname} ({HOST_ROLE_LABELS.get(host.role, host.role)})?\n\n"
        "DNS/nginx/3x-ui изменены не будут.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ Да, удалить", callback_data=f"admin:host:delete:{host_id}")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:host:{host_id}")],
        ]),
    )
    await call.answer()


@catalog_router.callback_query(F.data.startswith("admin:host:delete:"))
async def host_delete(call: CallbackQuery):
    if not await guard_call(call):
        return
    host_id = int(call.data.rsplit(":", 1)[-1])
    host = await db.get_host(host_id)
    await db.delete_host(host_id)
    await audit_from_call(
        db, call, "host.delete", target_type="host", target_id=str(host_id),
        details=f"hostname={host.hostname if host else ''}",
    )
    await render_callback(call, "✅ Хост удалён из реестра.", reply_markup=hosts_back())
    await call.answer()
