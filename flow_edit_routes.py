"""Support+ scoped Reality Flow editor. All writes go through Master."""
from __future__ import annotations
import asyncio
import secrets
import time
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from admin_auth import authorize_callback
from admin_ui import render_callback
from audit import audit_from_call
from flow_diagnostics import inspect_node_flow
from flow_edit import FLOW_CHOICES, FlowConfirmation, FlowEditRejected, discover_flow_targets, pop_confirmation, preflight_reason, read_target_outcome
from xui import XUIError, XUIMutationError

def node_label(node_id: int) -> str:
    return "🖥 Master" if node_id == 0 else f"🌐 Node #{node_id}"

def flow_label(value: str) -> str:
    return value or "none"

PAGE_SIZE = 8

def page_keyboard(items, page: int, *, route_prefix: str, back):
    """Render one bounded page, never silently omit navigation to later nodes."""
    pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    if not 0 <= page < pages:
        raise ValueError("Invalid page")
    result = list(items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE])
    if page > 0:
        result.append(("◀️ Назад", f"{route_prefix}:{page - 1}"))
    if page + 1 < pages:
        result.append(("▶️ Далее", f"{route_prefix}:{page + 1}"))
    result.append(back)
    return keyboard(*result)


def keyboard(*items):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=label, callback_data=route)] for label, route in items])

def register_flow_edit_handlers(router: Router, *, db, xui, settings) -> None:
    challenges: dict[int, FlowConfirmation] = {}

    async def auth(call):
        ok, _ = await authorize_callback(db, settings, call, minimum="support")
        return ok

    async def preflight(call, tg_id):
        rec = await db.get(tg_id)
        if rec is None:
            await call.answer("Пользователь не найден.", show_alert=True)
            return None
        try:
            snap = await discover_flow_targets(xui, rec.email, tg_id)
            return rec, snap
        except (FlowEditRejected, XUIError, asyncio.TimeoutError, TypeError, ValueError) as exc:
            await call.answer(f"Master/Inbounds не подтверждены ({preflight_reason(exc)}); изменений нет.", show_alert=True)
            return None

    @router.callback_query(F.data.regexp(r"^admin:u:flowedit:\d+(?::\d+)?$"))
    async def flow_edit_nodes(call: CallbackQuery):
        if not await auth(call):
            return
        parts = call.data.split(":")
        tg_id, page = int(parts[3]), int(parts[4]) if len(parts) == 5 else 0
        prepared = await preflight(call, tg_id)
        if prepared is None:
            return
        _, snap = prepared
        ids = sorted({t.node_id for t in snap.targets})
        rows = [(node_label(i), f"admin:u:flowib:{tg_id}:{i}") for i in ids]
        try:
            markup = page_keyboard(rows, page, route_prefix=f"admin:u:flowedit:{tg_id}", back=("✖ Отмена", f"admin:u:accesscfg:{tg_id}"))
        except ValueError:
            await call.answer("Страница недоступна.", show_alert=True)
            return
        await render_callback(call, "✏️ Изменить Flow · выберите ноду\n\nИзменения только после подтверждения." if ids else "✏️ Изменить Flow\n\nПодходящих Reality Inbounds нет.", reply_markup=markup)
        await call.answer()

    @router.callback_query(F.data.regexp(r"^admin:u:flowib:\d+:\d+(?::\d+)?$"))
    async def flow_edit_inbounds(call: CallbackQuery):
        if not await auth(call):
            return
        parts = call.data.split(":")
        tg_id, node_id = map(int, parts[3:5])
        page = int(parts[5]) if len(parts) == 6 else 0
        prepared = await preflight(call, tg_id)
        if prepared is None:
            return
        _, snap = prepared
        targets = [t for t in snap.targets if t.node_id == node_id]
        if not targets:
            await call.answer("Inbounds недоступны.", show_alert=True)
            return
        rows = [(f"Inbound #{t.inbound_id}", f"admin:u:flowval:{tg_id}:{node_id}:{t.inbound_id}") for t in targets]
        try:
            markup = page_keyboard(rows, page, route_prefix=f"admin:u:flowib:{tg_id}:{node_id}", back=("⬅ Ноды", f"admin:u:flowedit:{tg_id}"))
        except ValueError:
            await call.answer("Страница недоступна.", show_alert=True)
            return
        await render_callback(call, f"✏️ Изменить Flow · {node_label(node_id)}\n\nВыберите Inbound.", reply_markup=markup)
        await call.answer()

    @router.callback_query(F.data.regexp(r"^admin:u:flowval:\d+:\d+:\d+$"))
    async def flow_edit_values(call: CallbackQuery):
        if not await auth(call):
            return
        tg_id, node_id, iid = map(int, call.data.split(":")[3:])
        prepared = await preflight(call, tg_id)
        if prepared is None:
            return
        _, snap = prepared
        try:
            target = snap.select(node_id, iid)
        except FlowEditRejected:
            await call.answer("Inbound изменился.", show_alert=True)
            return
        rows = [(("✅ " if target.current_flow == flow else "▫️ ") + flow_label(flow), f"admin:u:flowset:{tg_id}:{node_id}:{iid}:{code}") for code, flow in FLOW_CHOICES.items()]
        rows.append(("⬅ Inbounds", f"admin:u:flowib:{tg_id}:{node_id}"))
        await render_callback(call, f"✏️ Flow · {node_label(node_id)} / Inbound #{iid}\n\nMaster: {flow_label(target.current_flow)}\nNode Panel: ⚪ не проверено\n\nВыберите значение:", reply_markup=keyboard(*rows))
        await call.answer()

    @router.callback_query(F.data.regexp(r"^admin:u:flowset:\d+:\d+:\d+:[nvu]$"))
    async def flow_edit_confirm(call: CallbackQuery):
        if not await auth(call):
            return
        tg_id, node_id, iid = map(int, call.data.split(":")[3:6])
        code = call.data.split(":")[6]
        prepared = await preflight(call, tg_id)
        if prepared is None:
            return
        _, snap = prepared
        try:
            target = snap.select(node_id, iid)
        except FlowEditRejected:
            await call.answer("Inbound изменился.", show_alert=True)
            return
        nonce = secrets.token_hex(8)
        challenges[call.from_user.id] = FlowConfirmation(call.from_user.id, tg_id, nonce, node_id, iid, target.inbound_tag, target.current_flow, FLOW_CHOICES[code], snap.fingerprint, time.monotonic())
        await render_callback(call, f"⚠️ Подтвердить Flow · {node_label(node_id)} / Inbound #{iid}\n\nСейчас: {flow_label(target.current_flow)}\nБудет: {flow_label(FLOW_CHOICES[code])}\n\nТолько выбранный Inbound через Master.", reply_markup=keyboard(("✅ Применить Flow", f"admin:u:flowcommit:{tg_id}:{nonce}"), ("✖ Отмена", f"admin:u:flowval:{tg_id}:{node_id}:{iid}")))
        await call.answer()

    @router.callback_query(F.data.regexp(r"^admin:u:flowcommit:\d+:[a-f0-9]{16}$"))
    async def flow_edit_commit(call: CallbackQuery):
        if not await auth(call):
            return
        tg_id, nonce = call.data.split(":")[3:]
        tg_id = int(tg_id)
        challenge = pop_confirmation(challenges, call.from_user.id, tg_id, nonce, now=time.monotonic())
        if challenge is None:
            await call.answer("Подтверждение устарело или использовано.", show_alert=True)
            return
        prepared = await preflight(call, tg_id)
        if prepared is None:
            return
        rec, snap = prepared
        try:
            target = snap.select(challenge.node_id, challenge.inbound_id)
        except FlowEditRejected:
            await call.answer("Inbound изменился.", show_alert=True)
            return
        if (target.inbound_tag != challenge.tag or target.current_flow != challenge.old_flow or snap.fingerprint != challenge.client_fingerprint):
            await call.answer("Данные Master изменились; подтверждение устарело.", show_alert=True)
            return
        certainty = "not_required"
        if target.current_flow != challenge.new_flow:
            try:
                await xui.update_client_inbound_flow(rec.email, challenge.inbound_id, challenge.new_flow, client=snap.client, wg_verified=snap.wg_verified)
                certainty = "response_success"
            except XUIMutationError as exc:
                certainty = "unknown" if exc.uncertain else "failed"
            except XUIError:
                certainty = "unknown"
        master_result, node_result = await read_target_outcome(xui, settings.node_backup_targets, rec.email, tg_id, challenge.node_id, challenge.inbound_id, challenge.new_flow, inspect=inspect_node_flow)
        result = "PASS" if master_result == "MATCH" and node_result in {"MATCH", "N/A"} and certainty in {"response_success", "not_required"} else "PENDING"
        if certainty == "failed":
            result = "FAIL"
        elif master_result == "MISMATCH" or node_result == "MISMATCH":
            result = "PARTIAL" if master_result == "MATCH" else "FAIL"
        await audit_from_call(db, call, "user.flow.scoped", target_type="user", target_id=tg_id, details=f"node_id={challenge.node_id}; inbound_id={challenge.inbound_id}; mutation={certainty}; no_retry=true; master={master_result}; node={node_result}; scope={result}", success=result == "PASS")
        visual = {"MATCH": "🟢 MATCH", "MISMATCH": "🔴 MISMATCH", "UNKNOWN": "⚪ UNKNOWN", "N/A": "— Master"}
        await render_callback(call, f"✏️ Flow · {node_label(challenge.node_id)} / Inbound #{challenge.inbound_id}\n\nЗапрошено: {flow_label(challenge.new_flow)}\nИзменение: {certainty}\nMaster inbound: {visual[master_result]}\nNode Panel: {visual[node_result]}\nИтог проверки: {result}\n\nNode Panel не аттестует Xray. При UNKNOWN/MISMATCH нет автоматического повтора.", reply_markup=keyboard(("🔎 Проверить Flow", f"admin:u:flowcheck:cfg:{tg_id}"), ("⬅ Параметры доступа", f"admin:u:accesscfg:{tg_id}")))
        await call.answer()
