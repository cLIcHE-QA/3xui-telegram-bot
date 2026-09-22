from __future__ import annotations

import secrets
import time
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_auth import authorize_callback, authorize_message
from audit import audit_from_call, audit_from_message
from config import load_settings
from db import Database, UserRecord
from xui import XUIClient, XUIError
from provisioning import ProvisioningEngine

settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
advanced_users_router = Router(name="advanced_users")
provisioner = ProvisioningEngine(db, xui, settings)


class EditUserStates(StatesGroup):
    expiry = State()
    traffic = State()
    ip_limit = State()
    note = State()


class BulkUserStates(StatesGroup):
    selecting = State()


async def guard(call: CallbackQuery, *, minimum: str | None = None) -> bool:
    ok, _ = await authorize_callback(db, settings, call, minimum=minimum)
    return ok


async def guard_message(message: Message, state: FSMContext, *, minimum: str = "support") -> bool:
    if not message.from_user:
        await state.clear()
        return False
    ok, _ = await authorize_message(db, settings, message.from_user.id, minimum=minimum)
    if not ok:
        await state.clear()
        await message.answer("Недостаточно прав.")
        return False
    return True


def human_bytes(value: int) -> str:
    n = float(int(value or 0))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"


def fmt_date(ms: int) -> str:
    if not ms:
        return "без срока"
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except (OSError, ValueError, OverflowError):
        return str(ms)


def sub_url(sub_id: str) -> str:
    template = settings.compat_subscription_url_template or settings.subscription_url_template
    return template.format(sub_id=sub_id)


def is_managed_inbound(i) -> bool:
    exact_ids = set(settings.inbound_ids)
    if i.protocol in set(settings.ignored_protocols):
        return False
    if i.tag.lower() in set(settings.ignored_tags) or i.tag.lower().startswith("api"):
        return False
    if exact_ids and i.id not in exact_ids:
        return False
    if settings.allowed_ports and i.port not in set(settings.allowed_ports):
        return False
    if settings.allowed_protocols and i.protocol not in set(settings.allowed_protocols):
        return False
    return True


def choose_inbounds(inbounds):
    return [i for i in inbounds if i.enable and is_managed_inbound(i)]


def back_user(tg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")],
    ])


def cancel_edit(tg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:u:{tg_id}")],
    ])


async def _profile_labels(tg_id: int) -> tuple[str, str, str]:
    profile = await db.get_user_profile(tg_id)
    plan_name = "не назначен"
    group_name = "не назначена"
    note = ""
    if profile:
        if profile.plan_id:
            plan = await db.get_plan(profile.plan_id)
            plan_name = plan.name if plan else f"#{profile.plan_id} (удалён)"
        if profile.server_group_id:
            group = await db.get_server_group(profile.server_group_id)
            group_name = group.name if group else f"#{profile.server_group_id} (удалена)"
        note = profile.note or ""
    return plan_name, group_name, note


async def render_user(tg_id: int) -> tuple[str, InlineKeyboardMarkup]:
    rec = await db.get(tg_id)
    if not rec:
        return "Пользователь не найден.", InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅ Users", callback_data="admin:users")]
        ])

    plan_name, group_name, note = await _profile_labels(tg_id)
    provisioning_line = "🚀 Provisioning: unavailable"
    try:
        policy = await provisioner.policy_for_user(tg_id)
        pobj = await xui.get_client(rec.email)
        pcurrent = {int(x) for x in (pobj.get("inboundIds") or [])}
        pdesired = set(policy.desired_inbound_ids)
        pmissing = len(pdesired - pcurrent)
        pextra = len((pcurrent & set(policy.managed_inbound_ids)) - pdesired)
        provisioning_line = f"🚀 Provisioning: desired {len(pdesired)} · missing {pmissing} · extra {pextra}"
    except Exception as exc:
        provisioning_line = f"🚀 Provisioning: ⚠️ {type(exc).__name__}"
    try:
        obj = await xui.get_client(rec.email)
        client = obj.get("client", obj)
        traffic = await xui.traffic(rec.email)
        up = int(traffic.get("up") or traffic.get("uplink") or 0)
        down = int(traffic.get("down") or traffic.get("downlink") or 0)
        total = int(client.get("totalGB") or 0)
        expiry = int(client.get("expiryTime") or rec.expiry_time or 0)
        limit_ip = int(client.get("limitIp") or 0)
        inbound_ids = sorted({int(x) for x in (obj.get("inboundIds") or [])})
        enabled = bool(client.get("enable", True))
        flow = str(client.get("flow") or "none")
        lines = [
            f"👤 {rec.email}",
            f"Telegram ID: {rec.telegram_id}",
            f"Статус: {'🟢 Enabled' if enabled else '⛔ Disabled'}",
            "",
            f"💎 Plan: {plan_name}",
            f"🗂 Server Group: {group_name}",
            provisioning_line,
            f"⏳ Expiry: {fmt_date(expiry)}",
            f"📦 Traffic limit: {human_bytes(total) if total else 'unlimited'}",
            f"📊 Used: {human_bytes(up + down)}",
            f"📱 IP limit: {limit_ip if limit_ip else 'unlimited'}",
            f"📡 Inbounds: {', '.join(map(str, inbound_ids)) if inbound_ids else 'нет'}",
            f"🔀 Flow: {flow}",
        ]
        if note:
            lines += ["", f"📝 Note: {note}"]
    except XUIError as exc:
        enabled = True
        lines = [
            f"👤 {rec.email}",
            f"Telegram ID: {rec.telegram_id}",
            "",
            f"💎 Plan: {plan_name}",
            f"🗂 Server Group: {group_name}",
            provisioning_line,
            "",
            f"⚠️ 3x-ui: {exc}",
        ]
        if note:
            lines += ["", f"📝 Note: {note}"]

    rows = [
        [
            InlineKeyboardButton(text="⏳ Expiry", callback_data=f"admin:u:expiry:{tg_id}"),
            InlineKeyboardButton(text="📦 Traffic", callback_data=f"admin:u:traffic:{tg_id}"),
        ],
        [
            InlineKeyboardButton(text="📱 IP limit", callback_data=f"admin:u:ip:{tg_id}"),
            InlineKeyboardButton(text="📡 Inbounds", callback_data=f"admin:u:inbounds:{tg_id}"),
        ],
        [
            InlineKeyboardButton(text="💎 Plan", callback_data=f"admin:u:plan:{tg_id}"),
            InlineKeyboardButton(text="🗂 Server Group", callback_data=f"admin:u:group:{tg_id}"),
        ],
        [InlineKeyboardButton(text="▶ Применить Plan к лимитам", callback_data=f"admin:u:planapplyask:{tg_id}")],
        [InlineKeyboardButton(text="🚀 Provisioning", callback_data=f"admin:u:prov:{tg_id}")],
        [InlineKeyboardButton(text="🚀 Plan + Provision", callback_data=f"admin:u:planprovask:{tg_id}")],
        [
            InlineKeyboardButton(text="🔄 Reset traffic", callback_data=f"admin:u:resetask:{tg_id}"),
            InlineKeyboardButton(text="📝 Note", callback_data=f"admin:u:note:{tg_id}"),
        ],
        [InlineKeyboardButton(text="🔐 Rotate subscription ID", callback_data=f"admin:u:subrotateask:{tg_id}")],
        [InlineKeyboardButton(text="🔗 Открыть подписку", callback_data=f"adminsub:{tg_id}")],
        [InlineKeyboardButton(text="⬅ Users", callback_data="admin:users")],
    ]
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


@advanced_users_router.callback_query(F.data.regexp(r"^admin:u:\d+$"))
async def user_advanced_card(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="read_only"):
        return
    await state.clear()
    tg_id = int(call.data.rsplit(":", 1)[-1])
    text, kb = await render_user(tg_id)
    await call.message.answer(text, reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:expiry:"))
async def user_expiry_start(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    if not await db.get(tg_id):
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    await state.clear()
    await state.update_data(tg_id=tg_id)
    await state.set_state(EditUserStates.expiry)
    await call.message.answer(
        "⏳ Изменение срока\n\n"
        "Введи:\n"
        "• +30 — добавить 30 дней к текущему сроку\n"
        "• 2026-12-31 — установить дату 23:59 UTC\n"
        "• 0 — без срока",
        reply_markup=cancel_edit(tg_id),
    )
    await call.answer()


@advanced_users_router.message(EditUserStates.expiry)
async def user_expiry_save(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    data = await state.get_data()
    tg_id = int(data["tg_id"])
    rec = await db.get(tg_id)
    if not rec:
        await state.clear()
        await message.answer("Пользователь не найден.")
        return
    raw = (message.text or "").strip()
    try:
        obj = await xui.get_client(rec.email)
        client = obj.get("client", obj)
        current = int(client.get("expiryTime") or rec.expiry_time or 0)
        now_ms = int(time.time() * 1000)
        if raw == "0":
            new_expiry = 0
        elif raw.startswith("+"):
            days = int(raw[1:])
            if not 1 <= days <= 3650:
                raise ValueError
            base = max(current, now_ms)
            new_expiry = base + days * 86400 * 1000
        else:
            dt = datetime.strptime(raw, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
            new_expiry = int(dt.timestamp() * 1000)
        await xui.update_client(rec.email, expiryTime=new_expiry)
        await db.update_expiry(tg_id, new_expiry)
        await audit_from_message(
            db, message, "user.expiry.set", target_type="user", target_id=rec.email,
            details=f"old={current}; new={new_expiry}",
        )
        await state.clear()
        await message.answer(f"✅ Expiry: {fmt_date(new_expiry)}", reply_markup=back_user(tg_id))
    except (ValueError, XUIError) as exc:
        if isinstance(exc, XUIError):
            await message.answer(f"Ошибка 3x-ui: {exc}", reply_markup=cancel_edit(tg_id))
        else:
            await message.answer("Формат: +30, YYYY-MM-DD или 0.")


@advanced_users_router.callback_query(F.data.startswith("admin:u:traffic:"))
async def user_traffic_start(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    await state.clear()
    await state.update_data(tg_id=tg_id)
    await state.set_state(EditUserStates.traffic)
    await call.message.answer(
        "📦 Новый traffic limit в GB.\n0 = unlimited.\nНапример: 100",
        reply_markup=cancel_edit(tg_id),
    )
    await call.answer()


@advanced_users_router.message(EditUserStates.traffic)
async def user_traffic_save(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    data = await state.get_data()
    tg_id = int(data["tg_id"])
    rec = await db.get(tg_id)
    try:
        gb = int((message.text or "").strip())
        if not 0 <= gb <= 1_000_000:
            raise ValueError
        if not rec:
            raise XUIError("Пользователь не найден")
        await xui.update_client(rec.email, totalGB=gb * 1024**3)
        await audit_from_message(
            db, message, "user.traffic_limit.set", target_type="user", target_id=rec.email,
            details=f"traffic_gb={gb}",
        )
        await state.clear()
        await message.answer(
            f"✅ Traffic limit: {gb} GB" if gb else "✅ Traffic limit: unlimited",
            reply_markup=back_user(tg_id),
        )
    except ValueError:
        await message.answer("Введи целое число GB от 0 до 1000000.")
    except XUIError as exc:
        await message.answer(f"Ошибка 3x-ui: {exc}", reply_markup=cancel_edit(tg_id))


@advanced_users_router.callback_query(F.data.startswith("admin:u:ip:"))
async def user_ip_start(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    await state.clear()
    await state.update_data(tg_id=tg_id)
    await state.set_state(EditUserStates.ip_limit)
    await call.message.answer(
        "📱 Новый IP limit.\n0 = unlimited.\nНапример: 2",
        reply_markup=cancel_edit(tg_id),
    )
    await call.answer()


@advanced_users_router.message(EditUserStates.ip_limit)
async def user_ip_save(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    data = await state.get_data()
    tg_id = int(data["tg_id"])
    rec = await db.get(tg_id)
    try:
        limit = int((message.text or "").strip())
        if not 0 <= limit <= 1000:
            raise ValueError
        if not rec:
            raise XUIError("Пользователь не найден")
        await xui.update_client(rec.email, limitIp=limit)
        await audit_from_message(
            db, message, "user.ip_limit.set", target_type="user", target_id=rec.email,
            details=f"limitIp={limit}",
        )
        await state.clear()
        await message.answer(
            f"✅ IP limit: {limit}" if limit else "✅ IP limit: unlimited",
            reply_markup=back_user(tg_id),
        )
    except ValueError:
        await message.answer("Введи целое число от 0 до 1000.")
    except XUIError as exc:
        await message.answer(f"Ошибка 3x-ui: {exc}", reply_markup=cancel_edit(tg_id))


@advanced_users_router.callback_query(F.data.startswith("admin:u:note:"))
async def user_note_start(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    await state.clear()
    await state.update_data(tg_id=tg_id)
    await state.set_state(EditUserStates.note)
    await call.message.answer(
        "📝 Введи внутреннюю заметку (до 500 символов).\n«-» очищает заметку.",
        reply_markup=cancel_edit(tg_id),
    )
    await call.answer()


@advanced_users_router.message(EditUserStates.note)
async def user_note_save(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    data = await state.get_data()
    tg_id = int(data["tg_id"])
    rec = await db.get(tg_id)
    note = (message.text or "").strip()
    if note == "-":
        note = ""
    if len(note) > 500:
        await message.answer("Максимум 500 символов.")
        return
    await db.set_user_note(tg_id, note)
    await audit_from_message(
        db, message, "user.note.set", target_type="user", target_id=rec.email if rec else str(tg_id),
        details=f"length={len(note)}",
    )
    await state.clear()
    await message.answer("✅ Заметка сохранена.", reply_markup=back_user(tg_id))


@advanced_users_router.callback_query(F.data.startswith("admin:u:plan:"))
async def user_plan_menu(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    plans = await db.list_plans()
    profile = await db.get_user_profile(tg_id)
    current = profile.plan_id if profile else None
    rows = [[InlineKeyboardButton(
        text=f"{'✅' if current is None else '⬜'} Без тарифа",
        callback_data=f"admin:u:planset:{tg_id}:0",
    )]]
    for plan in plans[:30]:
        icon = "✅" if current == plan.id else ("🟢" if plan.active else "⚪")
        rows.append([InlineKeyboardButton(
            text=f"{icon} {plan.name}", callback_data=f"admin:u:planset:{tg_id}:{plan.id}"
        )])
    rows.append([InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")])
    await call.message.answer(
        "💎 Plan\n\nНазначение здесь — метаданные control-plane. Лимиты 3x-ui не меняются автоматически.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:planset:"))
async def user_plan_set(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    parts = call.data.split(":")
    tg_id, plan_id = int(parts[-2]), int(parts[-1])
    rec = await db.get(tg_id)
    if plan_id and not await db.get_plan(plan_id):
        await call.answer("Тариф не найден.", show_alert=True)
        return
    await db.set_user_plan(tg_id, plan_id or None)
    plan = await db.get_plan(plan_id) if plan_id else None
    await audit_from_call(
        db, call, "user.plan.set", target_type="user", target_id=rec.email if rec else str(tg_id),
        details=f"plan_id={plan_id or None}; name={plan.name if plan else ''}",
    )
    await call.message.answer(
        f"✅ Plan: {plan.name if plan else 'не назначен'}", reply_markup=back_user(tg_id)
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:planapplyask:"))
async def user_plan_apply_ask(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    profile = await db.get_user_profile(tg_id)
    plan = await db.get_plan(profile.plan_id) if profile and profile.plan_id else None
    if not rec or not plan:
        await call.answer("Сначала назначь пользователю Plan.", show_alert=True)
        return
    await call.message.answer(
        f"Применить Plan «{plan.name}» к {rec.email}?\n\n"
        f"Expiry станет: сейчас + {plan.duration_days} дней\n"
        f"Traffic: {plan.traffic_gb} GB{' (unlimited)' if plan.traffic_gb == 0 else ''}\n"
        f"IP limit: {plan.ip_limit if plan.ip_limit else 'unlimited'}\n\n"
        "Накопленный traffic не сбрасывается. Server Group сохраняется отдельно.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Применить", callback_data=f"admin:u:planapplyrun:{tg_id}")],
            [InlineKeyboardButton(text="Отмена", callback_data=f"admin:u:{tg_id}")],
        ]),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:planapplyrun:"))
async def user_plan_apply_run(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    profile = await db.get_user_profile(tg_id)
    plan = await db.get_plan(profile.plan_id) if profile and profile.plan_id else None
    if not rec or not plan:
        await call.answer("Plan не найден.", show_alert=True)
        return
    expiry = int((time.time() + max(0, plan.duration_days) * 86400) * 1000) if plan.duration_days else 0
    try:
        await xui.update_client(
            rec.email,
            expiryTime=expiry,
            totalGB=max(0, plan.traffic_gb) * 1024**3,
            limitIp=max(0, plan.ip_limit),
        )
        await db.update_expiry(tg_id, expiry)
        if plan.server_group_id:
            await db.set_user_server_group(tg_id, plan.server_group_id)
        await audit_from_call(
            db, call, "user.plan.apply", target_type="user", target_id=rec.email,
            details=(
                f"plan_id={plan.id}; expiry={expiry}; traffic_gb={plan.traffic_gb}; "
                f"limit_ip={plan.ip_limit}; server_group_id={plan.server_group_id}"
            ),
        )
        await call.message.answer(
            f"✅ Plan «{plan.name}» применён к лимитам 3x-ui.", reply_markup=back_user(tg_id)
        )
    except XUIError as exc:
        await audit_from_call(
            db, call, "user.plan.apply", target_type="user", target_id=rec.email,
            details=f"error={exc}", success=False,
        )
        await call.message.answer(f"Ошибка 3x-ui: {exc}", reply_markup=back_user(tg_id))
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:group:"))
async def user_group_menu(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    groups = await db.list_server_groups()
    profile = await db.get_user_profile(tg_id)
    current = profile.server_group_id if profile else None
    rows = [[InlineKeyboardButton(
        text=f"{'✅' if current is None else '⬜'} Без группы",
        callback_data=f"admin:u:groupset:{tg_id}:0",
    )]]
    for group in groups[:30]:
        rows.append([InlineKeyboardButton(
            text=f"{'✅' if current == group.id else '⬜'} {group.name}",
            callback_data=f"admin:u:groupset:{tg_id}:{group.id}",
        )])
    rows.append([InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")])
    await call.message.answer(
        "🗂 Server Group\n\nГруппа определяет desired provisioning scope. Само назначение не меняет 3x-ui мгновенно — используй 🚀 Provisioning / reconcile.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:groupset:"))
async def user_group_set(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    parts = call.data.split(":")
    tg_id, group_id = int(parts[-2]), int(parts[-1])
    rec = await db.get(tg_id)
    if group_id and not await db.get_server_group(group_id):
        await call.answer("Группа не найдена.", show_alert=True)
        return
    await db.set_user_server_group(tg_id, group_id or None)
    group = await db.get_server_group(group_id) if group_id else None
    await audit_from_call(
        db, call, "user.server_group.set", target_type="user", target_id=rec.email if rec else str(tg_id),
        details=f"server_group_id={group_id or None}; name={group.name if group else ''}",
    )
    await call.message.answer(
        f"✅ Server Group: {group.name if group else 'не назначена'}", reply_markup=back_user(tg_id)
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:prov:"))
async def user_provisioning_card(call: CallbackQuery):
    if not await guard(call, minimum="read_only"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    try:
        policy = await provisioner.policy_for_user(tg_id)
        obj = await xui.get_client(rec.email)
        current = {int(x) for x in (obj.get("inboundIds") or [])}
        desired = set(policy.desired_inbound_ids)
        managed = set(policy.managed_inbound_ids)
        missing = sorted(desired - current)
        actionable_missing = sorted(set(policy.actionable_inbound_ids) - current)
        extra = sorted((current & managed) - desired)
        lines = [
            f"🚀 Provisioning · {rec.email}",
            "",
            f"Source: {policy.source}",
            f"Plan: {policy.plan.name if policy.plan else 'не назначен'}",
            f"Server Group: {policy.group.name if policy.group else 'legacy all-managed'}",
            f"Inbound mode: {policy.inbound_mode}",
            "",
            f"Desired: {len(desired)} · {', '.join(map(str, sorted(desired))) if desired else 'нет'}",
            f"Current: {len(current)} · {', '.join(map(str, sorted(current))) if current else 'нет'}",
            f"Missing: {len(missing)} · actionable now: {len(actionable_missing)}",
            f"Extra managed: {len(extra)}",
        ]
        if policy.unavailable_members:
            lines.append(f"Unavailable nodes: {', '.join(policy.unavailable_members)}")
        if policy.warnings:
            lines += ["", "Warnings:"] + [f"⚠️ {w}" for w in policy.warnings]
        rows = [
            [InlineKeyboardButton(text="✅ Safe reconcile", callback_data=f"admin:u:provrun:{tg_id}:safe")],
            [InlineKeyboardButton(text="⚠️ Strict reconcile", callback_data=f"admin:u:provstrictask:{tg_id}")],
            [InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")],
        ]
        await call.message.answer("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception as exc:
        await call.message.answer(f"🔴 Provisioning: {type(exc).__name__}: {exc}", reply_markup=back_user(tg_id))
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:provstrictask:"))
async def user_provisioning_strict_ask(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    await call.message.answer(
        "⚠️ Strict reconcile не только добавит missing inbound'ы, но и отключит управляемые inbound'ы, которых нет в desired policy.\n\nПродолжить?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ Да, strict reconcile", callback_data=f"admin:u:provrun:{tg_id}:strict")],
            [InlineKeyboardButton(text="Отмена", callback_data=f"admin:u:prov:{tg_id}")],
        ]),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.regexp(r"^admin:u:provrun:\d+:(safe|strict)$"))
async def user_provisioning_run(call: CallbackQuery):
    mode = call.data.rsplit(":", 1)[-1]
    minimum = "admin" if mode == "strict" else "support"
    if not await guard(call, minimum=minimum):
        return
    parts = call.data.split(":")
    tg_id = int(parts[-2])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    try:
        result = await provisioner.sync_user(tg_id, strict=(mode == "strict"), apply_plan_limits=False)
        await audit_from_call(
            db, call, f"user.provision.{mode}", target_type="user", target_id=rec.email,
            details=f"attached={result.attached_ids}; detached={result.detached_ids}; remaining={result.remaining_missing_ids}; extra={result.extra_ids}",
        )
        lines = [
            f"✅ {mode.capitalize()} reconcile завершён.",
            f"Attached: {result.attached_ids or 'нет'}",
            f"Detached: {result.detached_ids or 'нет'}",
            f"Still missing: {result.remaining_missing_ids or 'нет'}",
            f"Extra managed: {result.extra_ids or 'нет'}",
        ]
        if result.policy.unavailable_members:
            lines.append(f"⏸ Недоступные ноды: {', '.join(result.policy.unavailable_members)}")
        await call.message.answer("\n".join(lines), reply_markup=back_user(tg_id))
    except Exception as exc:
        await audit_from_call(db, call, f"user.provision.{mode}", target_type="user", target_id=rec.email, details=f"error={type(exc).__name__}: {exc}", success=False)
        await call.message.answer(f"🔴 Provisioning error: {type(exc).__name__}: {exc}", reply_markup=back_user(tg_id))
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:planprovask:"))
async def user_plan_provision_ask(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    profile = await db.get_user_profile(tg_id)
    plan = await db.get_plan(profile.plan_id) if profile and profile.plan_id else None
    if not plan:
        await call.answer("Сначала назначь Plan.", show_alert=True)
        return
    await call.message.answer(
        f"Применить Plan «{plan.name}» к лимитам и выполнить safe provisioning?\n\n"
        "Это обновит expiry/traffic/IP limit, назначит Server Group тарифа и добавит missing inbound'ы. Extra inbound'ы не удаляются.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Plan + Provision", callback_data=f"admin:u:planprovrun:{tg_id}")],
            [InlineKeyboardButton(text="Отмена", callback_data=f"admin:u:{tg_id}")],
        ]),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:planprovrun:"))
async def user_plan_provision_run(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    try:
        result = await provisioner.sync_user(tg_id, strict=False, apply_plan_limits=True)
        await audit_from_call(
            db, call, "user.plan.provision", target_type="user", target_id=rec.email,
            details=f"plan={result.policy.plan.id if result.policy.plan else None}; attached={result.attached_ids}; remaining={result.remaining_missing_ids}",
        )
        await call.message.answer(
            f"✅ Plan + Provision завершён.\nAttached: {result.attached_ids or 'нет'}\nStill missing: {result.remaining_missing_ids or 'нет'}",
            reply_markup=back_user(tg_id),
        )
    except Exception as exc:
        await audit_from_call(db, call, "user.plan.provision", target_type="user", target_id=rec.email, details=f"error={type(exc).__name__}: {exc}", success=False)
        await call.message.answer(f"🔴 Plan + Provision: {type(exc).__name__}: {exc}", reply_markup=back_user(tg_id))
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:inbounds:"))
async def user_inbounds(call: CallbackQuery):
    if not await guard(call, minimum="read_only"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    try:
        all_inbounds = choose_inbounds(await xui.inbound_options())
        obj = await xui.get_client(rec.email)
        current = {int(x) for x in (obj.get("inboundIds") or [])}
        rows = []
        for inbound in all_inbounds[:40]:
            rows.append([InlineKeyboardButton(
                text=f"{'✅' if inbound.id in current else '⬜'} #{inbound.id} · {inbound.port}/{inbound.protocol} · {inbound.remark}",
                callback_data=f"admin:u:ibtoggle:{tg_id}:{inbound.id}",
            )])
        rows.append([InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")])
        await call.message.answer(
            f"📡 Inbounds · {rec.email}\n\nНажатие подключает/отключает пользователя от конкретного inbound.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )
    except XUIError as exc:
        await call.message.answer(f"Ошибка 3x-ui: {exc}", reply_markup=back_user(tg_id))
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:ibtoggle:"))
async def user_inbound_toggle(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    parts = call.data.split(":")
    tg_id, inbound_id = int(parts[-2]), int(parts[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    try:
        obj = await xui.get_client(rec.email)
        current = {int(x) for x in (obj.get("inboundIds") or [])}
        allowed = {i.id for i in choose_inbounds(await xui.inbound_options())}
        if inbound_id in current:
            managed_current = current & allowed
            if inbound_id in managed_current and len(managed_current) <= 1:
                await call.answer("Нельзя отключить последний управляемый inbound.", show_alert=True)
                return
            await xui.detach_client(rec.email, [inbound_id])
            action = "detach"
        else:
            if inbound_id not in allowed:
                await call.answer("Inbound не разрешён настройками бота.", show_alert=True)
                return
            await xui.attach_client(rec.email, [inbound_id])
            if settings.vless_flow:
                await xui.bulk_adjust_clients([rec.email], flow=settings.vless_flow)
            action = "attach"
        await audit_from_call(
            db, call, f"user.inbound.{action}", target_type="user", target_id=rec.email,
            details=f"inbound_id={inbound_id}",
        )
        await call.answer("Обновлено.")
        # Re-render the list as a new message so Telegram callback state stays simple.
        all_inbounds = choose_inbounds(await xui.inbound_options())
        updated = await xui.get_client(rec.email)
        now_ids = {int(x) for x in (updated.get("inboundIds") or [])}
        rows = [[InlineKeyboardButton(
            text=f"{'✅' if i.id in now_ids else '⬜'} #{i.id} · {i.port}/{i.protocol} · {i.remark}",
            callback_data=f"admin:u:ibtoggle:{tg_id}:{i.id}",
        )] for i in all_inbounds[:40]]
        rows.append([InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{tg_id}")])
        await call.message.answer("📡 Inbounds обновлены.", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except XUIError as exc:
        await audit_from_call(
            db, call, "user.inbound.toggle", target_type="user", target_id=rec.email,
            details=f"inbound_id={inbound_id}; error={exc}", success=False,
        )
        await call.message.answer(f"Ошибка 3x-ui: {exc}", reply_markup=back_user(tg_id))


@advanced_users_router.callback_query(F.data.startswith("admin:u:resetask:"))
async def user_reset_ask(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    await call.message.answer(
        f"Сбросить накопленный трафик {rec.email} до 0?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Сбросить трафик", callback_data=f"admin:u:resetrun:{tg_id}")],
            [InlineKeyboardButton(text="Отмена", callback_data=f"admin:u:{tg_id}")],
        ]),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:resetrun:"))
async def user_reset_run(call: CallbackQuery):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    try:
        result = await xui.bulk_reset_traffic([rec.email])
        affected = int((result.get("obj") or {}).get("affected") or 0)
        await audit_from_call(
            db, call, "user.traffic.reset", target_type="user", target_id=rec.email,
            details=f"affected={affected}",
        )
        await call.message.answer(f"✅ Трафик сброшен. affected={affected}", reply_markup=back_user(tg_id))
    except XUIError as exc:
        await audit_from_call(
            db, call, "user.traffic.reset", target_type="user", target_id=rec.email,
            details=f"error={exc}", success=False,
        )
        await call.message.answer(f"Ошибка 3x-ui: {exc}", reply_markup=back_user(tg_id))
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:subrotateask:"))
async def user_sub_rotate_ask(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    await call.message.answer(
        "🔐 Rotate subscription ID\n\n"
        "Старый URL подписки перестанет работать. Уже импортированные конфиги в клиентах не удалятся, "
        "но обновлять их по старому URL будет нельзя.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ Сгенерировать новый subId", callback_data=f"admin:u:subrotaterun:{tg_id}")],
            [InlineKeyboardButton(text="Отмена", callback_data=f"admin:u:{tg_id}")],
        ]),
    )
    await call.answer()


@advanced_users_router.callback_query(F.data.startswith("admin:u:subrotaterun:"))
async def user_sub_rotate_run(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    rec = await db.get(tg_id)
    if not rec:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    new_sid = ""
    for _ in range(5):
        candidate = secrets.token_urlsafe(18)
        if not await db.get_by_sub_id(candidate):
            new_sid = candidate
            break
    if not new_sid:
        await call.answer("Не удалось сгенерировать уникальный subId.", show_alert=True)
        return
    try:
        await xui.update_client(rec.email, subId=new_sid)
        await db.update_sub_id(tg_id, new_sid)
        await audit_from_call(
            db, call, "user.subscription.rotate", target_type="user", target_id=rec.email,
            details="subId rotated",
        )
        await call.message.answer(
            f"✅ Новый URL подписки для {rec.email}:\n{sub_url(new_sid)}",
            reply_markup=back_user(tg_id),
        )
    except XUIError as exc:
        await audit_from_call(
            db, call, "user.subscription.rotate", target_type="user", target_id=rec.email,
            details=f"error={exc}", success=False,
        )
        await call.message.answer(f"Ошибка 3x-ui: {exc}", reply_markup=back_user(tg_id))
    await call.answer()


# ---------------------------------------------------------------------
# Bulk user actions
# ---------------------------------------------------------------------


async def _bulk_render(state: FSMContext) -> tuple[str, InlineKeyboardMarkup]:
    users = await db.list_users()
    data = await state.get_data()
    selected = {int(x) for x in data.get("selected", [])}
    page = max(0, int(data.get("page", 0)))
    page_size = 12
    pages = max(1, (len(users) + page_size - 1) // page_size)
    page = min(page, pages - 1)
    await state.update_data(page=page)
    visible = users[page * page_size:(page + 1) * page_size]
    rows = []
    for u in visible:
        rows.append([InlineKeyboardButton(
            text=f"{'✅' if u.telegram_id in selected else '⬜'} {u.email}",
            callback_data=f"admin:bulk:toggle:{u.telegram_id}",
        )])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅", callback_data="admin:bulk:prev"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="admin:bulk:noop"))
    if page + 1 < pages:
        nav.append(InlineKeyboardButton(text="➡", callback_data="admin:bulk:next"))
    rows.append(nav)
    rows.append([
        InlineKeyboardButton(text="☑️ Выбрать всех", callback_data="admin:bulk:all"),
        InlineKeyboardButton(text="🧹 Очистить", callback_data="admin:bulk:clear"),
    ])
    rows.append([InlineKeyboardButton(
        text=f"⚙️ Действия ({len(selected)})", callback_data="admin:bulk:actions"
    )])
    rows.append([InlineKeyboardButton(text="⬅ Users", callback_data="admin:bulk:close")])
    return (
        "☑️ Bulk user actions\n\n"
        f"Выбрано: {len(selected)} из {len(users)}\n"
        "Отметь пользователей и открой «Действия».",
        InlineKeyboardMarkup(inline_keyboard=rows),
    )


@advanced_users_router.callback_query(F.data == "admin:users:bulk")
async def bulk_start(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    await state.clear()
    await state.set_state(BulkUserStates.selecting)
    await state.update_data(selected=[], page=0)
    text, kb = await _bulk_render(state)
    await call.message.answer(text, reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(BulkUserStates.selecting, F.data.startswith("admin:bulk:toggle:"))
async def bulk_toggle(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    tg_id = int(call.data.rsplit(":", 1)[-1])
    data = await state.get_data()
    selected = {int(x) for x in data.get("selected", [])}
    if tg_id in selected:
        selected.remove(tg_id)
    else:
        selected.add(tg_id)
    await state.update_data(selected=sorted(selected))
    text, kb = await _bulk_render(state)
    await call.message.answer(text, reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(BulkUserStates.selecting, F.data.in_({"admin:bulk:prev", "admin:bulk:next"}))
async def bulk_page(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    data = await state.get_data()
    page = int(data.get("page", 0)) + (-1 if call.data.endswith("prev") else 1)
    await state.update_data(page=max(0, page))
    text, kb = await _bulk_render(state)
    await call.message.answer(text, reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(BulkUserStates.selecting, F.data == "admin:bulk:all")
async def bulk_all(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    users = await db.list_users()
    await state.update_data(selected=[u.telegram_id for u in users])
    text, kb = await _bulk_render(state)
    await call.message.answer(text, reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(BulkUserStates.selecting, F.data == "admin:bulk:clear")
async def bulk_clear(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    await state.update_data(selected=[])
    text, kb = await _bulk_render(state)
    await call.message.answer(text, reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(BulkUserStates.selecting, F.data == "admin:bulk:noop")
async def bulk_noop(call: CallbackQuery):
    await call.answer()


@advanced_users_router.callback_query(BulkUserStates.selecting, F.data == "admin:bulk:actions")
async def bulk_actions(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    selected = (await state.get_data()).get("selected", [])
    if not selected:
        await call.answer("Сначала выбери пользователей.", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ +30 дней", callback_data="admin:bulk:run:extend30")],
        [
            InlineKeyboardButton(text="✅ Enable", callback_data="admin:bulk:run:enable"),
            InlineKeyboardButton(text="⛔ Disable", callback_data="admin:bulk:run:disable"),
        ],
        [InlineKeyboardButton(text="🔄 Reset traffic", callback_data="admin:bulk:run:reset")],
        [InlineKeyboardButton(text="📡 Sync inbounds", callback_data="admin:bulk:run:sync")],
        [InlineKeyboardButton(text="⬅ К выбору", callback_data="admin:bulk:back")],
    ])
    await call.message.answer(f"⚙️ Bulk actions\n\nВыбрано: {len(selected)}", reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(BulkUserStates.selecting, F.data == "admin:bulk:back")
async def bulk_back(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    text, kb = await _bulk_render(state)
    await call.message.answer(text, reply_markup=kb)
    await call.answer()


@advanced_users_router.callback_query(BulkUserStates.selecting, F.data == "admin:bulk:close")
async def bulk_close(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    await state.clear()
    await call.message.answer("Bulk selection закрыт.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Users", callback_data="admin:users")]
    ]))
    await call.answer()


@advanced_users_router.callback_query(BulkUserStates.selecting, F.data.startswith("admin:bulk:run:"))
async def bulk_run(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="support"):
        return
    action = call.data.rsplit(":", 1)[-1]
    data = await state.get_data()
    ids = [int(x) for x in data.get("selected", [])]
    records: list[UserRecord] = []
    for tg_id in ids:
        rec = await db.get(tg_id)
        if rec:
            records.append(rec)
    emails = [r.email for r in records]
    if not emails:
        await call.answer("Нет выбранных пользователей.", show_alert=True)
        return
    try:
        details = ""
        if action == "extend30":
            result = await xui.bulk_adjust_clients(emails, add_days=30)
            for rec in records:
                try:
                    obj = await xui.get_client(rec.email)
                    client = obj.get("client", obj)
                    await db.update_expiry(rec.telegram_id, int(client.get("expiryTime") or rec.expiry_time))
                except XUIError:
                    pass
            details = str(result.get("obj") or {})[:1000]
            message = "✅ +30 дней выполнено."
        elif action == "enable":
            result = await xui.bulk_enable_clients(emails)
            details = str(result.get("obj") or {})[:1000]
            message = "✅ Enable выполнен."
        elif action == "disable":
            result = await xui.bulk_disable_clients(emails)
            details = str(result.get("obj") or {})[:1000]
            message = "✅ Disable выполнен."
        elif action == "reset":
            result = await xui.bulk_reset_traffic(emails)
            details = str(result.get("obj") or {})[:1000]
            message = "✅ Traffic reset выполнен."
        elif action == "sync":
            inbounds = choose_inbounds(await xui.inbound_options())
            ids_to_attach = sorted({i.id for i in inbounds})
            result = await xui.bulk_attach_clients(emails, ids_to_attach)
            if settings.vless_flow:
                await xui.bulk_adjust_clients(emails, flow=settings.vless_flow)
            details = f"inbounds={ids_to_attach}; result={str(result.get('obj') or {})[:700]}"
            message = "✅ Inbound sync выполнен."
        else:
            await call.answer("Неизвестное действие.", show_alert=True)
            return
        await audit_from_call(
            db, call, f"users.bulk.{action}", target_type="users", target_id=str(len(emails)),
            details=f"emails={','.join(emails[:20])}; {details}",
        )
        await call.message.answer(f"{message}\nПользователей: {len(emails)}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅ К выбору", callback_data="admin:bulk:back")],
            [InlineKeyboardButton(text="⬅ Users", callback_data="admin:bulk:close")],
        ]))
    except XUIError as exc:
        await audit_from_call(
            db, call, f"users.bulk.{action}", target_type="users", target_id=str(len(emails)),
            details=f"error={exc}", success=False,
        )
        await call.message.answer(f"Ошибка 3x-ui: {exc}")
    await call.answer()
