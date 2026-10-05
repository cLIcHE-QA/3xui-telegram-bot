from __future__ import annotations

import json
import secrets
import sqlite3
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_ui import render_callback, render_input
from admin_auth import authorize_callback, authorize_message
from audit import audit_from_call, audit_from_message
from config import load_settings
from db import Database
from user_ui import user_label
from node_ui import node_display_name
from xui import XUIClient, XUIError, XUIMutationError

settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
inbound_admin_router = Router(name="inbound_admin")

# Keep this list in sync with 3x-ui's UTLS_FINGERPRINT values.
REALITY_FINGERPRINTS = (
    "chrome",
    "firefox",
    "safari",
    "ios",
    "android",
    "edge",
    "360",
    "qq",
    "random",
    "randomized",
    "randomizednoalpn",
    "unsafe",
)


class InboundEditStates(StatesGroup):
    value = State()
    clone_port = State()
    template_name = State()
    template_port = State()


async def guard(call: CallbackQuery, *, minimum: str = "read_only") -> bool:
    ok, _ = await authorize_callback(db, settings, call, minimum=minimum)
    return ok


async def guard_message(message: Message, state: FSMContext, *, minimum: str = "admin") -> bool:
    if not message.from_user:
        await state.clear()
        return False
    ok, _ = await authorize_message(db, settings, message.from_user.id, minimum=minimum)
    if not ok:
        await state.clear()
        await render_input(message, "Недостаточно прав.")
        return False
    return True


def inbound_cancel_keyboard(iid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:inbound:{iid}")
    ]])


def inbound_back_keyboard(iid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅ Inbound", callback_data=f"admin:inbound:{iid}")
    ]])


def template_cancel_keyboard(tid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:inboundtemplate:{tid}")
    ]])


def template_back_keyboard(tid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅ Шаблон", callback_data=f"admin:inboundtemplate:{tid}")
    ]])


def _json_obj(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return json.loads(json.dumps(value))
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _settings(inbound: dict[str, Any]) -> dict[str, Any]:
    return _json_obj(inbound.get("settings"))


def _stream(inbound: dict[str, Any]) -> dict[str, Any]:
    return _json_obj(inbound.get("streamSettings"))


def _sniffing(inbound: dict[str, Any]) -> dict[str, Any]:
    return _json_obj(inbound.get("sniffing"))


def _node_key(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _node_label(node_id: int, nodes: list[Any]) -> str:
    if not node_id:
        return f"{settings.master_flag} {settings.master_name}"
    for n in nodes:
        if int(n.id) == int(node_id):
            return node_display_name(n.name)
    return f"Node #{node_id}"


def _human_bytes(value: int) -> str:
    n = float(max(0, int(value or 0)))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"


def _update_payload(inbound: dict[str, Any]) -> dict[str, Any]:
    """Build the documented full replacement payload without read-only fields."""
    payload: dict[str, Any] = {
        "enable": bool(inbound.get("enable", True)),
        "remark": str(inbound.get("remark") or ""),
        "listen": str(inbound.get("listen") or ""),
        "port": int(inbound.get("port") or 0),
        "protocol": str(inbound.get("protocol") or ""),
        "expiryTime": int(inbound.get("expiryTime") or 0),
        "total": int(inbound.get("total") or 0),
        "settings": _settings(inbound),
        "streamSettings": _stream(inbound),
        "sniffing": _sniffing(inbound),
    }
    for key in ("shareAddrStrategy", "shareAddr"):
        if key in inbound:
            payload[key] = inbound.get(key)
    return payload


def _template_payload(inbound: dict[str, Any]) -> dict[str, Any]:
    """Store a staged clone payload: disabled and without clients."""
    payload = _update_payload(inbound)
    st = _json_obj(payload.get("settings"))
    st["clients"] = []
    payload["settings"] = st
    payload["enable"] = False
    payload["total"] = 0
    payload["expiryTime"] = 0
    payload["listen"] = ""
    return payload


def _clone_payload(inbound: dict[str, Any], *, port: int, node_id: int | None) -> dict[str, Any]:
    payload = _template_payload(inbound)
    payload["remark"] = f"{str(inbound.get('remark') or 'Inbound')} (clone)"
    payload["port"] = int(port)
    if node_id is not None:
        payload["nodeId"] = int(node_id)
    return payload


def _deploy_payload(template_payload: dict[str, Any], *, port: int, node_id: int | None) -> dict[str, Any]:
    payload = json.loads(json.dumps(template_payload))
    payload["port"] = int(port)
    payload["enable"] = False
    payload["listen"] = ""
    st = _json_obj(payload.get("settings"))
    st["clients"] = []
    payload["settings"] = st
    payload.pop("nodeId", None)
    if node_id is not None:
        payload["nodeId"] = int(node_id)
    return payload


async def _port_free(target_node_id: int, port: int, *, exclude_inbound_id: int = 0) -> bool:
    for ib in await xui.inbounds_list(slim=True):
        try:
            ib_id = int(ib.get("id") or 0)
            ib_port = int(ib.get("port") or 0)
        except (TypeError, ValueError):
            continue
        if exclude_inbound_id and ib_id == exclude_inbound_id:
            continue
        if _node_key(ib.get("nodeId")) == int(target_node_id) and ib_port == int(port):
            return False
    return True


async def _inbound_update_with_readback(
    inbound_id: int,
    payload: dict[str, Any],
) -> tuple[bool, str]:
    try:
        await xui.inbound_update(inbound_id, payload)
        return True, "direct"
    except XUIMutationError as exc:
        if not exc.uncertain:
            raise
        try:
            readback = await xui.inbound_get(inbound_id)
        except XUIError as read_exc:
            return False, (
                f"code={exc.code}; mutation_not_retried=true; "
                f"readback=unavailable:{type(read_exc).__name__}"
            )
        if _update_payload(readback) != payload:
            return False, f"code={exc.code}; mutation_not_retried=true; readback=mismatch"
        return True, "readback=match; uncertain_resolved=success"


async def _inbound_add_with_readback(payload: dict[str, Any]) -> tuple[bool, str]:
    try:
        await xui.inbound_add(payload)
        return True, "direct"
    except XUIMutationError as exc:
        if not exc.uncertain:
            raise
        try:
            inbounds = await xui.inbounds_list(slim=True)
        except XUIError as read_exc:
            return False, (
                f"code={exc.code}; mutation_not_retried=true; "
                f"readback=unavailable:{type(read_exc).__name__}"
            )
        expected_node = _node_key(payload.get("nodeId"))
        expected_port = int(payload.get("port") or 0)
        candidates = [
            item for item in inbounds
            if isinstance(item, dict)
            and _node_key(item.get("nodeId")) == expected_node
            and int(item.get("port") or 0) == expected_port
        ]
        if len(candidates) != 1:
            return False, (
                f"code={exc.code}; mutation_not_retried=true; "
                f"readback={'ambiguous' if len(candidates) > 1 else 'absent'}"
            )
        candidate = candidates[0]
        expected_protocol = str(payload.get("protocol") or "")
        expected_remark = str(payload.get("remark") or "")
        if (
            str(candidate.get("protocol") or "") != expected_protocol
            or str(candidate.get("remark") or "") != expected_remark
            or bool(candidate.get("enable", True)) != bool(payload.get("enable", True))
        ):
            return False, f"code={exc.code}; mutation_not_retried=true; readback=mismatch"
        return True, "readback=unique_match; uncertain_resolved=success"


def _visible(inbound: dict[str, Any]) -> bool:
    protocol = str(inbound.get("protocol") or "").lower()
    tag = str(inbound.get("tag") or "").lower()
    if protocol in set(settings.ignored_protocols):
        return False
    if tag in set(settings.ignored_tags) or tag.startswith("api"):
        return False
    return True


def _managed(inbound: dict[str, Any]) -> bool:
    protocol = str(inbound.get("protocol") or "").lower()
    tag = str(inbound.get("tag") or "").lower()
    try:
        iid = int(inbound.get("id") or 0)
        port = int(inbound.get("port") or 0)
    except (TypeError, ValueError):
        return False
    if protocol in set(settings.ignored_protocols):
        return False
    if tag in set(settings.ignored_tags) or tag.startswith("api"):
        return False
    if settings.inbound_ids and iid not in set(settings.inbound_ids):
        return False
    if settings.allowed_ports and port not in set(settings.allowed_ports):
        return False
    if settings.allowed_protocols and protocol not in set(settings.allowed_protocols):
        return False
    return True


async def inbound_list_view() -> tuple[str, InlineKeyboardMarkup]:
    inbounds = [x for x in await xui.inbounds_list(slim=True) if _visible(x)]
    try:
        nodes = await xui.nodes_list()
    except XUIError:
        nodes = []
    rows: list[list[InlineKeyboardButton]] = []
    lines = ["📡 Inbounds", "", f"Видимых: {len(inbounds)}", "✅ = участвует в согласовании · ⚙️ = только администрирование"]
    for ib in sorted(inbounds, key=lambda x: (_node_key(x.get("nodeId")), int(x.get("port") or 0), int(x.get("id") or 0))):
        iid = int(ib.get("id") or 0)
        icon = "🟢" if bool(ib.get("enable", True)) else "🔴"
        node = _node_label(_node_key(ib.get("nodeId")), nodes)
        name = str(ib.get("remark") or ib.get("tag") or f"Inbound {iid}")
        scope = "✅" if _managed(ib) else "⚙️"
        rows.append([InlineKeyboardButton(
            text=f"{icon} {scope} {node} · {name} · {ib.get('port')}/{ib.get('protocol')}",
            callback_data=f"admin:inbound:{iid}",
        )])
    rows += [
        [InlineKeyboardButton(text="🧩 Шаблоны", callback_data="admin:inboundtemplates")],
        [InlineKeyboardButton(text="⬅ Инфраструктура", callback_data="admin:section:infrastructure")],
    ]
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


async def _inbound_card(inbound_id: int) -> tuple[str, InlineKeyboardMarkup]:
    ib = await xui.inbound_get(inbound_id)
    st = _settings(ib)
    stream = _stream(ib)
    clients = st.get("clients") if isinstance(st.get("clients"), list) else []
    xhttp = _json_obj(stream.get("xhttpSettings"))
    reality = _json_obj(stream.get("realitySettings"))
    reality_client = _json_obj(reality.get("settings"))
    try:
        nodes = await xui.nodes_list()
    except XUIError:
        nodes = []
    node_id = _node_key(ib.get("nodeId"))
    network = str(stream.get("network") or "-")
    security = str(stream.get("security") or "none")
    lines = [
        f"📡 {ib.get('remark') or ib.get('tag') or f'Inbound {inbound_id}'}",
        "",
        f"ID: #{inbound_id}",
        f"Сервер: {_node_label(node_id, nodes)}",
        f"Статус: {'🟢 включён' if ib.get('enable', True) else '🔴 отключён'}",
        f"Протокол: {ib.get('protocol') or '-'}",
        f"Порт: {ib.get('port') or 0}",
        f"Listen: {ib.get('listen') or '*'}",
        f"Транспорт: {network}",
        f"Безопасность: {security}",
        f"Согласование: {'✅ управляется' if _managed(ib) else '⚠️ не управляется текущей административной политикой'}",
        f"Клиентов: {len(clients)}",
        f"Трафик: ↑ {_human_bytes(int(ib.get('up') or 0))} · ↓ {_human_bytes(int(ib.get('down') or 0))}",
    ]
    if network == "xhttp":
        lines += [
            f"XHTTP path: {xhttp.get('path') or '/'}",
            f"XHTTP host: {xhttp.get('host') or '-'}",
            f"XHTTP mode: {xhttp.get('mode') or 'auto'}",
            f"XHTTP padding: {xhttp.get('xPaddingBytes') or '-'}",
        ]
    if security == "reality":
        server_names = reality.get("serverNames") or []
        if not isinstance(server_names, list):
            server_names = []
        lines += [
            f"Reality SNI: {', '.join(map(str, server_names)) or '-'}",
            f"Reality fingerprint: {reality_client.get('fingerprint') or reality.get('fingerprint') or '-'}",
        ]

    toggle_text = "⛔ Отключить" if ib.get("enable", True) else "✅ Включить"
    rows = [
        [
            InlineKeyboardButton(text="👥 Клиенты", callback_data=f"admin:inbound:clients:{inbound_id}"),
            InlineKeyboardButton(text="✏️ Изменить", callback_data=f"admin:inbound:edit:{inbound_id}"),
        ],
        [
            InlineKeyboardButton(text="🔄 Синхронизировать клиентов", callback_data=f"admin:inbound:syncask:{inbound_id}"),
            InlineKeyboardButton(text="♻️ Сбросить трафик", callback_data=f"admin:inbound:resetask:{inbound_id}"),
        ],
        [
            InlineKeyboardButton(text="📋 Клонировать", callback_data=f"admin:inbound:clone:{inbound_id}"),
            InlineKeyboardButton(text="🧩 Сохранить шаблон", callback_data=f"admin:inbound:template:{inbound_id}"),
        ],
        [
            InlineKeyboardButton(text=toggle_text, callback_data=f"admin:inbound:toggle:{inbound_id}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:inbound:deleteask:{inbound_id}"),
        ],
        [InlineKeyboardButton(text="⬅ Inbounds", callback_data="admin:infra:inbounds")],
    ]
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


@inbound_admin_router.callback_query(F.data.regexp(r"^admin:inbound:\d+$"))
async def inbound_detail(call: CallbackQuery, state: FSMContext):
    if not await guard(call):
        return
    await state.clear()
    inbound_id = int(call.data.rsplit(":", 1)[-1])
    try:
        text, kb = await _inbound_card(inbound_id)
        await render_callback(call, text, reply_markup=kb)
        await call.answer()
    except XUIError as exc:
        await call.answer(f"3x-ui: {str(exc)[:160]}", show_alert=True)


@inbound_admin_router.callback_query(F.data.startswith("admin:inbound:clients:"))
async def inbound_clients(call: CallbackQuery):
    if not await guard(call):
        return
    inbound_id = int(call.data.rsplit(":", 1)[-1])
    try:
        ib = await xui.inbound_get(inbound_id)
    except XUIError as exc:
        await call.answer(f"3x-ui: {str(exc)[:160]}", show_alert=True)
        return
    clients = _settings(ib).get("clients") or []
    if not isinstance(clients, list):
        clients = []
    lines = [f"👥 Клиенты · #{inbound_id}", "", f"Всего: {len(clients)}"]
    rows: list[list[InlineKeyboardButton]] = []
    for client in clients[:50]:
        if not isinstance(client, dict):
            continue
        email = str(client.get("email") or "-")
        enabled = bool(client.get("enable", True))
        rec = await db.get_by_email(email) if email != "-" else None
        profile = await db.get_user_profile(rec.telegram_id) if rec else None
        label = user_label(rec, profile) if rec else email
        lines.append(f"{'🟢' if enabled else '⛔'} {label}")
        if rec:
            rows.append([InlineKeyboardButton(
                text=f"👤 {label}", callback_data=f"adminuser:{rec.telegram_id}"
            )])
    if len(clients) > 50:
        lines += ["", f"… ещё {len(clients) - 50}"]
    rows.append([InlineKeyboardButton(text="⬅ Inbound", callback_data=f"admin:inbound:{inbound_id}")])
    await render_callback(call, "\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


def _edit_menu(ib: dict[str, Any]) -> InlineKeyboardMarkup:
    iid = int(ib.get("id") or 0)
    stream = _stream(ib)
    network = str(stream.get("network") or "")
    security = str(stream.get("security") or "")
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text="✏️ Название", callback_data=f"admin:inbound:editfield:{iid}:remark"),
            InlineKeyboardButton(text="🔌 Порт", callback_data=f"admin:inbound:editfield:{iid}:port"),
        ],
        [InlineKeyboardButton(text="👂 Listen", callback_data=f"admin:inbound:editfield:{iid}:listen")],
    ]
    if network == "xhttp":
        rows += [
            [
                InlineKeyboardButton(text="🌐 XHTTP path", callback_data=f"admin:inbound:editfield:{iid}:path"),
                InlineKeyboardButton(text="🏷️ XHTTP host", callback_data=f"admin:inbound:editfield:{iid}:host"),
            ],
            [
                InlineKeyboardButton(text="⚙️ XHTTP mode", callback_data=f"admin:inbound:editmode:{iid}"),
                InlineKeyboardButton(text="📐 XHTTP padding", callback_data=f"admin:inbound:editfield:{iid}:padding"),
            ],
        ]
    if security == "reality":
        rows += [
            [
                InlineKeyboardButton(text="🎯 Reality SNI", callback_data=f"admin:inbound:editfield:{iid}:sni"),
                InlineKeyboardButton(text="🪪 Fingerprint", callback_data=f"admin:inbound:editfp:{iid}"),
            ]
        ]
    rows.append([InlineKeyboardButton(text="⬅ Inbound", callback_data=f"admin:inbound:{iid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@inbound_admin_router.callback_query(F.data.startswith("admin:inbound:edit:"))
async def inbound_edit_menu(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    iid = int(call.data.rsplit(":", 1)[-1])
    try:
        ib = await xui.inbound_get(iid)
    except XUIError as exc:
        await call.answer(f"3x-ui: {str(exc)[:160]}", show_alert=True)
        return
    await render_callback(call, 
        "✏️ Изменение Inbound\n\n"
        "Из Telegram доступны только поля, которые можно обновить без показа приватных ключей. "
        "Полный settings/streamSettings сохраняется при каждом изменении.",
        reply_markup=_edit_menu(ib),
    )
    await call.answer()


_FIELD_PROMPTS = {
    "remark": "Новое название Inbound:",
    "port": "Новый port (1-65535):",
    "listen": "Listen address. Отправь - для пустого значения (все интерфейсы):",
    "path": "Новый XHTTP path, например / или /api:",
    "host": "Новый XHTTP host. Отправь - чтобы очистить:",
    "padding": "XHTTP xPaddingBytes, например 100-1000. Отправь - чтобы очистить:",
    "sni": "Reality SNI/serverNames через запятую, например www.oracle.com:",
}


@inbound_admin_router.callback_query(F.data.startswith("admin:inbound:editfield:"))
async def inbound_edit_start(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="admin"):
        return
    parts = call.data.split(":")
    iid = int(parts[-2])
    field = parts[-1]
    if field not in _FIELD_PROMPTS:
        await call.answer("Поле не поддерживается.", show_alert=True)
        return
    await state.clear()
    await state.set_state(InboundEditStates.value)
    await state.update_data(inbound_id=iid, field=field)
    await render_callback(call, 
        f"✏️ Inbound #{iid}\n\n{_FIELD_PROMPTS[field]}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:inbound:{iid}")
        ]]),
    )
    await call.answer()


def _reality_fingerprint(ib: dict[str, Any]) -> str:
    stream = _stream(ib)
    reality = _json_obj(stream.get("realitySettings"))
    client_half = _json_obj(reality.get("settings"))
    return str(client_half.get("fingerprint") or reality.get("fingerprint") or "")


def _set_reality_fingerprint(ib: dict[str, Any], fingerprint: str) -> str:
    if fingerprint not in REALITY_FINGERPRINTS:
        raise ValueError("unsupported Reality fingerprint")

    stream = _stream(ib)
    if str(stream.get("security") or "") != "reality":
        raise ValueError("inbound does not use Reality")

    reality = _json_obj(stream.get("realitySettings"))
    client_half = _json_obj(reality.get("settings"))
    old = str(client_half.get("fingerprint") or reality.get("fingerprint") or "")

    client_half["fingerprint"] = fingerprint
    reality["settings"] = client_half
    stream["realitySettings"] = reality
    ib["streamSettings"] = stream
    return old


def _fingerprint_menu(iid: int, current: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for offset in range(0, len(REALITY_FINGERPRINTS), 2):
        row = []
        for fingerprint in REALITY_FINGERPRINTS[offset:offset + 2]:
            marker = "✅" if fingerprint == current else "🪪"
            row.append(InlineKeyboardButton(
                text=f"{marker} {fingerprint}",
                callback_data=f"admin:inbound:setfp:{iid}:{fingerprint}",
            ))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅ Изменить", callback_data=f"admin:inbound:edit:{iid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@inbound_admin_router.callback_query(F.data.startswith("admin:inbound:editfp:"))
async def inbound_edit_fingerprint(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    iid = int(call.data.rsplit(":", 1)[-1])
    try:
        ib = await xui.inbound_get(iid)
        stream = _stream(ib)
        if str(stream.get("security") or "") != "reality":
            await call.answer("Этот Inbound не использует Reality.", show_alert=True)
            return
        current = _reality_fingerprint(ib)
        await render_callback(
            call,
            "🪪 Reality fingerprint\n\n"
            f"Текущее значение: {current or '-'}\n\n"
            "Выбери значение из списка 3x-ui:",
            reply_markup=_fingerprint_menu(iid, current),
        )
        await call.answer()
    except XUIError as exc:
        await call.answer(f"3x-ui: {str(exc)[:160]}", show_alert=True)


@inbound_admin_router.callback_query(F.data.startswith("admin:inbound:setfp:"))
async def inbound_set_fingerprint(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    parts = call.data.split(":")
    iid = int(parts[-2])
    fingerprint = parts[-1]
    if fingerprint not in REALITY_FINGERPRINTS:
        await call.answer("Некорректный fingerprint.", show_alert=True)
        return
    try:
        ib = await xui.inbound_get(iid)
        try:
            old = _set_reality_fingerprint(ib, fingerprint)
        except ValueError:
            await call.answer("Этот Inbound не использует Reality.", show_alert=True)
            return
        confirmed, evidence = await _inbound_update_with_readback(iid, _update_payload(ib))
        if not confirmed:
            await audit_from_call(
                db,
                call,
                "inbound.update.unknown",
                target_type="inbound",
                target_id=str(iid),
                details=f"field=reality.fingerprint; {evidence}",
                success=False,
            )
            await call.answer(
                "Итог изменения fingerprint неизвестен; mutation не повторялась.",
                show_alert=True,
            )
            return
        await audit_from_call(
            db,
            call,
            "inbound.update",
            target_type="inbound",
            target_id=str(iid),
            details=(
                f"field=reality.fingerprint; old={old[:120]}; "
                f"new={fingerprint}; {evidence}"
            ),
        )
        await call.answer("Сохранено.")
        text, kb = await _inbound_card(iid)
        await render_callback(call, text, reply_markup=kb)
    except XUIError as exc:
        await call.answer(f"3x-ui: {str(exc)[:160]}", show_alert=True)


@inbound_admin_router.callback_query(F.data.startswith("admin:inbound:editmode:"))
async def inbound_edit_mode(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    iid = int(call.data.rsplit(":", 1)[-1])
    rows = [[InlineKeyboardButton(text=f"⚙️ {mode}", callback_data=f"admin:inbound:setmode:{iid}:{mode}")]
            for mode in ("auto", "packet-up", "stream-up", "stream-one")]
    rows.append([InlineKeyboardButton(text="⬅ Изменить", callback_data=f"admin:inbound:edit:{iid}")])
    await render_callback(call, "Режим XHTTP:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


async def _apply_mode(call: CallbackQuery, iid: int, mode: str) -> bool:
    ib = await xui.inbound_get(iid)
    stream = _stream(ib)
    xhttp = _json_obj(stream.get("xhttpSettings"))
    xhttp["mode"] = mode
    stream["xhttpSettings"] = xhttp
    ib["streamSettings"] = stream
    confirmed, evidence = await _inbound_update_with_readback(iid, _update_payload(ib))
    if not confirmed:
        await audit_from_call(
            db,
            call,
            "inbound.update.unknown",
            target_type="inbound",
            target_id=str(iid),
            details=f"field=xhttp.mode; value={mode}; {evidence}",
            success=False,
        )
        return False
    await audit_from_call(
        db, call, "inbound.update", target_type="inbound", target_id=str(iid),
        details=f"field=xhttp.mode; value={mode}; {evidence}",
    )
    return True


@inbound_admin_router.callback_query(F.data.startswith("admin:inbound:setmode:"))
async def inbound_set_mode(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    parts = call.data.split(":")
    iid = int(parts[-2])
    mode = parts[-1]
    if mode not in {"auto", "packet-up", "stream-up", "stream-one"}:
        await call.answer("Некорректный режим.", show_alert=True)
        return
    try:
        confirmed = await _apply_mode(call, iid, mode)
        if not confirmed:
            await call.answer(
                "Итог изменения режима неизвестен; mutation не повторялась.",
                show_alert=True,
            )
            return
        await call.answer("Сохранено.")
        text, kb = await _inbound_card(iid)
        await render_callback(call, text, reply_markup=kb)
    except XUIError as exc:
        await call.answer(f"3x-ui: {str(exc)[:160]}", show_alert=True)


@inbound_admin_router.message(InboundEditStates.value)
async def inbound_edit_save(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    data = await state.get_data()
    iid = int(data.get("inbound_id") or 0)
    field = str(data.get("field") or "")
    raw = (message.text or "").strip()
    try:
        ib = await xui.inbound_get(iid)
        old_display = ""
        new_display = raw
        if field == "remark":
            if not 1 <= len(raw) <= 128:
                await render_input(message, "Название должно быть от 1 до 128 символов.", reply_markup=inbound_cancel_keyboard(iid))
                return
            old_display = str(ib.get("remark") or "")
            ib["remark"] = raw
        elif field == "port":
            try:
                port = int(raw)
            except ValueError:
                await render_input(message, "Нужен числовой порт.", reply_markup=inbound_cancel_keyboard(iid))
                return
            if not 1 <= port <= 65535:
                await render_input(message, "Порт должен быть 1-65535.", reply_markup=inbound_cancel_keyboard(iid))
                return
            if not await _port_free(_node_key(ib.get("nodeId")), port, exclude_inbound_id=iid):
                await render_input(message, "Этот port уже занят на данном сервере.", reply_markup=inbound_cancel_keyboard(iid))
                return
            old_display = str(ib.get("port") or 0)
            ib["port"] = port
            new_display = str(port)
        elif field == "listen":
            old_display = str(ib.get("listen") or "")
            ib["listen"] = "" if raw == "-" else raw
            new_display = str(ib["listen"] or "*")
        elif field in {"path", "host", "padding"}:
            stream = _stream(ib)
            if str(stream.get("network") or "") != "xhttp":
                await render_input(message, "Этот Inbound не использует XHTTP.", reply_markup=inbound_back_keyboard(iid))
                await state.clear()
                return
            xhttp = _json_obj(stream.get("xhttpSettings"))
            key = {"path": "path", "host": "host", "padding": "xPaddingBytes"}[field]
            old_display = str(xhttp.get(key) or "")
            value = "" if raw == "-" else raw
            if field == "path" and value and not value.startswith("/"):
                await render_input(message, "XHTTP path должен начинаться с /.", reply_markup=inbound_cancel_keyboard(iid))
                return
            xhttp[key] = value
            stream["xhttpSettings"] = xhttp
            ib["streamSettings"] = stream
            new_display = value or "-"
        elif field == "sni":
            stream = _stream(ib)
            if str(stream.get("security") or "") != "reality":
                await render_input(message, "Этот Inbound не использует Reality.", reply_markup=inbound_back_keyboard(iid))
                await state.clear()
                return
            values = [x.strip() for x in raw.split(",") if x.strip()]
            if not values:
                await render_input(message, "Укажи хотя бы один SNI.", reply_markup=inbound_cancel_keyboard(iid))
                return
            reality = _json_obj(stream.get("realitySettings"))
            old_display = ",".join(map(str, reality.get("serverNames") or []))
            reality["serverNames"] = values
            client_half = _json_obj(reality.get("settings"))
            client_half["serverName"] = values[0]
            reality["settings"] = client_half
            stream["realitySettings"] = reality
            ib["streamSettings"] = stream
            new_display = ",".join(values)
        else:
            await render_input(message, "Поле не поддерживается.", reply_markup=inbound_back_keyboard(iid))
            await state.clear()
            return
        confirmed, evidence = await _inbound_update_with_readback(iid, _update_payload(ib))
        if not confirmed:
            await state.clear()
            await audit_from_message(
                db, message, "inbound.update.unknown", target_type="inbound", target_id=str(iid),
                details=f"field={field}; {evidence}", success=False,
            )
            await render_input(
                message,
                "🟡 Итог изменения Inbound неизвестен. Mutation не повторялась; "
                "обнови карточку перед повтором.",
                reply_markup=inbound_back_keyboard(iid),
            )
            return
        await audit_from_message(
            db, message, "inbound.update", target_type="inbound", target_id=str(iid),
            details=(
                f"field={field}; old={old_display[:120]}; "
                f"new={new_display[:120]}; {evidence}"
            ),
        )
        await state.clear()
        text, kb = await _inbound_card(iid)
        await render_input(message, "✅ Inbound обновлён.\n\n" + text, reply_markup=kb)
    except XUIError as exc:
        await state.clear()
        await audit_from_message(
            db, message, "inbound.update", target_type="inbound", target_id=str(iid),
            details=f"field={field}; error={str(exc)[:300]}", success=False,
        )
        await render_input(message, f"Ошибка 3x-ui: {exc}", reply_markup=inbound_back_keyboard(iid))


@inbound_admin_router.callback_query(F.data.startswith("admin:inbound:toggle:"))
async def inbound_toggle(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    iid = int(call.data.rsplit(":", 1)[-1])
    try:
        ib = await xui.inbound_get(iid)
        enabled = not bool(ib.get("enable", True))
        await xui.inbound_set_enable(iid, enabled)
        await audit_from_call(
            db, call, "inbound.enable" if enabled else "inbound.disable",
            target_type="inbound", target_id=str(iid),
        )
        await call.answer("Включён" if enabled else "Отключён")
        text, kb = await _inbound_card(iid)
        await render_callback(call, text, reply_markup=kb)
    except XUIMutationError as exc:
        action = "inbound.enable" if enabled else "inbound.disable"
        if not exc.uncertain:
            await audit_from_call(
                db, call, action, target_type="inbound", target_id=str(iid),
                details=f"code={exc.code}; certainty=failed", success=False,
            )
            await call.answer(f"3x-ui: {str(exc)[:160]}", show_alert=True)
            return
        try:
            readback = await xui.inbound_get(iid)
        except XUIError as read_exc:
            await audit_from_call(
                db, call, f"{action}.unknown", target_type="inbound", target_id=str(iid),
                details=(
                    f"code={exc.code}; mutation_not_retried=true; "
                    f"readback=unavailable:{type(read_exc).__name__}"
                ),
                success=False,
            )
            await call.answer("Итог изменения неизвестен", show_alert=True)
            return
        if bool(readback.get("enable", True)) != enabled:
            await audit_from_call(
                db, call, f"{action}.unknown", target_type="inbound", target_id=str(iid),
                details=f"code={exc.code}; mutation_not_retried=true; readback=mismatch",
                success=False,
            )
            await call.answer("Итог изменения неизвестен", show_alert=True)
            return
        await audit_from_call(
            db, call, action, target_type="inbound", target_id=str(iid),
            details="readback=match; uncertain_resolved=success",
        )
        await call.answer("Включён" if enabled else "Отключён")
        text, kb = await _inbound_card(iid)
        await render_callback(call, text, reply_markup=kb)
    except XUIError as exc:
        await call.answer(f"3x-ui: {str(exc)[:160]}", show_alert=True)


@inbound_admin_router.callback_query(F.data.startswith("admin:inbound:syncask:"))
async def inbound_sync_ask(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    iid = int(call.data.rsplit(":", 1)[-1])
    users = await db.list_users()
    await render_callback(call, 
        f"🔄 Синхронизация пользователей → Inbound #{iid}\n\n"
        f"Все {len(users)} пользователей из локальной БД будут привязаны к этому Inbound, "
        "если они ещё не привязаны. Лимиты и credentials не меняются.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Выполнить", callback_data=f"admin:inbound:syncrun:{iid}")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:inbound:{iid}")],
        ]),
    )
    await call.answer()


@inbound_admin_router.callback_query(F.data.startswith("admin:inbound:syncrun:"))
async def inbound_sync_run(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    iid = int(call.data.rsplit(":", 1)[-1])
    users = await db.list_users()
    emails = [u.email for u in users]
    try:
        result = await xui.bulk_attach_clients(emails, [iid])
        obj = result.get("obj") if isinstance(result, dict) else {}
        await audit_from_call(
            db, call, "inbound.sync_users", target_type="inbound", target_id=str(iid),
            details=f"users={len(emails)}; result={str(obj)[:800]}",
        )
        await render_callback(
            call,
            f"✅ Синхронизация завершена для Inbound #{iid}.\nПользователей обработано: {len(emails)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅ Inbound", callback_data=f"admin:inbound:{iid}")
            ]]),
        )
        await call.answer()
    except XUIMutationError as exc:
        if not exc.uncertain:
            await audit_from_call(
                db, call, "inbound.sync_users", target_type="inbound", target_id=str(iid),
                details=f"code={exc.code}; certainty=failed", success=False,
            )
            await call.answer(f"3x-ui: {str(exc)[:160]}", show_alert=True)
            return
        readback = "match"
        try:
            for email in emails:
                obj = await xui.get_client(email)
                ids = {int(x) for x in (obj.get("inboundIds") or [])}
                if iid not in ids:
                    readback = "mismatch"
                    break
        except XUIError as read_exc:
            readback = f"unavailable:{type(read_exc).__name__}"
        if readback == "match":
            await audit_from_call(
                db, call, "inbound.sync_users", target_type="inbound", target_id=str(iid),
                details=(
                    f"users={len(emails)}; readback=match; "
                    "uncertain_resolved=success"
                ),
            )
            await render_callback(
                call,
                f"✅ Синхронизация подтверждена read-back для Inbound #{iid}.\n"
                f"Пользователей: {len(emails)}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="⬅ Inbound", callback_data=f"admin:inbound:{iid}")
                ]]),
            )
            await call.answer()
            return
        await audit_from_call(
            db, call, "inbound.sync_users.unknown", target_type="inbound", target_id=str(iid),
            details=(
                f"users={len(emails)}; code={exc.code}; "
                f"mutation_not_retried=true; readback={readback}"
            ),
            success=False,
        )
        await call.answer("Итог синхронизации неизвестен; mutation не повторялась.", show_alert=True)
    except XUIError as exc:
        await audit_from_call(
            db, call, "inbound.sync_users", target_type="inbound", target_id=str(iid),
            details=f"error={type(exc).__name__}", success=False,
        )
        await call.answer(f"3x-ui: {str(exc)[:160]}", show_alert=True)


@inbound_admin_router.callback_query(F.data.startswith("admin:inbound:resetask:"))
async def inbound_reset_ask(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    iid = int(call.data.rsplit(":", 1)[-1])
    await render_callback(call, 
        f"♻️ Обнулить общий трафик Inbound #{iid}?\n\nСчётчики отдельных клиентов не изменяются.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ Сбросить", callback_data=f"admin:inbound:resetrun:{iid}")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:inbound:{iid}")],
        ]),
    )
    await call.answer()


@inbound_admin_router.callback_query(F.data.startswith("admin:inbound:resetrun:"))
async def inbound_reset_run(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    iid = int(call.data.rsplit(":", 1)[-1])
    try:
        await xui.inbound_reset_traffic(iid)
        await audit_from_call(
            db, call, "inbound.reset_traffic", target_type="inbound", target_id=str(iid)
        )
        await call.answer("Трафик обнулён.")
        text, kb = await _inbound_card(iid)
        await render_callback(call, text, reply_markup=kb)
    except XUIMutationError as exc:
        if not exc.uncertain:
            await audit_from_call(
                db, call, "inbound.reset_traffic", target_type="inbound", target_id=str(iid),
                details=f"code={exc.code}; certainty=failed", success=False,
            )
            await call.answer(f"3x-ui: {str(exc)[:160]}", show_alert=True)
            return
        await audit_from_call(
            db, call, "inbound.reset_traffic.unknown", target_type="inbound", target_id=str(iid),
            details=f"code={exc.code}; mutation_not_retried=true; readback=not_provable",
            success=False,
        )
        await call.answer(
            "Итог сброса трафика неизвестен; mutation не повторялась.",
            show_alert=True,
        )
    except XUIError as exc:
        await call.answer(f"3x-ui: {str(exc)[:160]}", show_alert=True)


@inbound_admin_router.callback_query(F.data.startswith("admin:inbound:clone:"))
async def inbound_clone_start(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    iid = int(call.data.rsplit(":", 1)[-1])
    await render_callback(call, 
        "📋 Клонирование Inbound\n\nВыбери сервер. Клон создаётся отключённым и без клиентов.",
        reply_markup=await _target_keyboard(
            "admin:inbound:clonetarget", iid, cancel_callback=f"admin:inbound:{iid}"
        ),
    )
    await call.answer()


async def _create_clone(call: CallbackQuery, iid: int, target_node: int, port: int) -> None:
    ib = await xui.inbound_get(iid)
    payload = _clone_payload(ib, port=port, node_id=(target_node or None))
    await xui.inbound_add(payload)
    await audit_from_call(
        db, call, "inbound.clone", target_type="inbound", target_id=str(iid),
        details=f"target_node={target_node}; port={port}",
    )


@inbound_admin_router.callback_query(F.data.startswith("admin:inbound:clonetarget:"))
async def inbound_clone_target(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="admin"):
        return
    parts = call.data.split(":")
    iid = int(parts[-2])
    target_node = int(parts[-1])
    try:
        ib = await xui.inbound_get(iid)
        source_port = int(ib.get("port") or 0)
        if await _port_free(target_node, source_port):
            await _create_clone(call, iid, target_node, source_port)
            await call.answer("Клон создан отключённым.")
            text, kb = await inbound_list_view()
            await render_callback(call, text, reply_markup=kb)
            return
        await state.clear()
        await state.set_state(InboundEditStates.clone_port)
        await state.update_data(clone_inbound_id=iid, clone_target_node=target_node)
        await render_callback(call, 
            f"На выбранном сервере порт {source_port} уже занят.\n\nВведи другой порт (1-65535):",
            reply_markup=inbound_cancel_keyboard(iid),
        )
        await call.answer()
    except XUIError as exc:
        await call.answer(f"3x-ui: {str(exc)[:160]}", show_alert=True)


@inbound_admin_router.message(InboundEditStates.clone_port)
async def inbound_clone_port(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    data = await state.get_data()
    iid = int(data.get("clone_inbound_id") or 0)
    target_node = int(data.get("clone_target_node") or 0)
    try:
        port = int((message.text or "").strip())
    except ValueError:
        await render_input(message, "Нужен числовой порт.", reply_markup=inbound_cancel_keyboard(iid))
        return
    if not 1 <= port <= 65535:
        await render_input(message, "Порт должен быть 1-65535.", reply_markup=inbound_cancel_keyboard(iid))
        return
    if not await _port_free(target_node, port):
        await render_input(message, "Этот порт уже занят на выбранном сервере.", reply_markup=inbound_cancel_keyboard(iid))
        return
    try:
        # This path has no CallbackQuery for audit, so record the mutation directly.
        ib = await xui.inbound_get(iid)
        await xui.inbound_add(_clone_payload(ib, port=port, node_id=(target_node or None)))
        await audit_from_message(
            db, message, "inbound.clone", target_type="inbound", target_id=str(iid),
            details=f"target_node={target_node}; port={port}",
        )
        await state.clear()
        await render_input(message, 
            "✅ Клон создан отключённым.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="📡 Inbounds", callback_data="admin:infra:inbounds")
            ]]),
        )
    except XUIError as exc:
        await state.clear()
        await render_input(message, f"Ошибка 3x-ui: {exc}", reply_markup=inbound_back_keyboard(iid))


@inbound_admin_router.callback_query(F.data.startswith("admin:inbound:template:"))
async def inbound_template_start(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="admin"):
        return
    iid = int(call.data.rsplit(":", 1)[-1])
    try:
        ib = await xui.inbound_get(iid)
    except XUIError as exc:
        await call.answer(f"3x-ui: {str(exc)[:160]}", show_alert=True)
        return
    await state.clear()
    await state.set_state(InboundEditStates.template_name)
    await state.update_data(template_source_id=iid)
    await render_callback(call, 
        f"🧩 Сохранение шаблона из #{iid}\n\n"
        f"Источник: {ib.get('remark') or '-'}\n"
        "Введи имя шаблона. В шаблон попадёт конфигурация Inbound без клиентов.",
        reply_markup=inbound_cancel_keyboard(iid),
    )
    await call.answer()


@inbound_admin_router.message(InboundEditStates.template_name)
async def inbound_template_save(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    data = await state.get_data()
    iid = int(data.get("template_source_id") or 0)
    name = (message.text or "").strip()
    if not 1 <= len(name) <= 64:
        await render_input(message, "Имя должно быть от 1 до 64 символов.", reply_markup=inbound_cancel_keyboard(iid))
        return
    try:
        ib = await xui.inbound_get(iid)
        payload = _template_payload(ib)
        template_id = await db.create_inbound_template(
            name=name,
            source_inbound_id=iid,
            protocol=str(ib.get("protocol") or ""),
            payload_json=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        )
        await audit_from_message(
            db, message, "inbound_template.create", target_type="inbound_template",
            target_id=str(template_id), details=f"name={name}; source_inbound={iid}",
        )
        await state.clear()
        await render_input(message, 
            f"✅ Шаблон создан: {name}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🧩 Шаблоны", callback_data="admin:inboundtemplates")
            ]]),
        )
    except sqlite3.IntegrityError:
        await render_input(message, "Шаблон с таким именем уже существует.", reply_markup=inbound_cancel_keyboard(iid))
    except XUIError as exc:
        await state.clear()
        await render_input(message, f"Ошибка 3x-ui: {exc}", reply_markup=inbound_back_keyboard(iid))


@inbound_admin_router.callback_query(F.data == "admin:inboundtemplates")
async def inbound_templates(call: CallbackQuery, state: FSMContext):
    if not await guard(call):
        return
    await state.clear()
    templates = await db.list_inbound_templates()
    rows = [[InlineKeyboardButton(
        text=f"🧩 {t.name} · {t.protocol}", callback_data=f"admin:inboundtemplate:{t.id}"
    )] for t in templates[:50]]
    rows.append([InlineKeyboardButton(text="⬅ Inbounds", callback_data="admin:infra:inbounds")])
    text = "🧩 Шаблоны Inbounds\n\n" + (f"Шаблонов: {len(templates)}" if templates else "Шаблонов пока нет.")
    await render_callback(call, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@inbound_admin_router.callback_query(F.data.regexp(r"^admin:inboundtemplate:\d+$"))
async def inbound_template_card(call: CallbackQuery, state: FSMContext):
    if not await guard(call):
        return
    await state.clear()
    tid = int(call.data.rsplit(":", 1)[-1])
    t = await db.get_inbound_template(tid)
    if not t:
        await call.answer("Шаблон не найден.", show_alert=True)
        return
    try:
        payload = json.loads(t.payload_json)
    except json.JSONDecodeError:
        payload = {}
    stream = _json_obj(payload.get("streamSettings"))
    text = (
        f"🧩 {t.name}\n\n"
        f"ID: #{t.id}\n"
        f"Протокол: {t.protocol}\n"
        f"Порт: {payload.get('port') or 0}\n"
        f"Транспорт: {stream.get('network') or '-'}\n"
        f"Безопасность: {stream.get('security') or 'none'}\n"
        f"Исходный Inbound: #{t.source_inbound_id}\n\n"
        "Развёртывание создаёт отключённый Inbound без клиентов."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Развернуть", callback_data=f"admin:inboundtemplate:deploy:{tid}")],
        [InlineKeyboardButton(text="🗑 Удалить шаблон", callback_data=f"admin:inboundtemplate:deleteask:{tid}")],
        [InlineKeyboardButton(text="⬅ Шаблоны", callback_data="admin:inboundtemplates")],
    ])
    await render_callback(call, text, reply_markup=kb)
    await call.answer()


@inbound_admin_router.callback_query(F.data.startswith("admin:inboundtemplate:deploy:"))
async def template_deploy_start(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    tid = int(call.data.rsplit(":", 1)[-1])
    if not await db.get_inbound_template(tid):
        await call.answer("Шаблон не найден.", show_alert=True)
        return
    await render_callback(call, 
        "🚀 Развёртывание шаблона\n\nВыбери сервер. Новый Inbound будет отключён и без клиентов.",
        reply_markup=await _target_keyboard(
            "admin:inboundtemplate:target", tid, cancel_callback=f"admin:inboundtemplate:{tid}"
        ),
    )
    await call.answer()


async def _deploy_template(tid: int, target_node: int, port: int) -> None:
    t = await db.get_inbound_template(tid)
    if not t:
        raise ValueError("Шаблон не найден")
    payload = json.loads(t.payload_json)
    if not isinstance(payload, dict):
        raise ValueError("Некорректные данные шаблона")
    await xui.inbound_add(_deploy_payload(payload, port=port, node_id=(target_node or None)))


@inbound_admin_router.callback_query(F.data.startswith("admin:inboundtemplate:target:"))
async def template_deploy_target(call: CallbackQuery, state: FSMContext):
    if not await guard(call, minimum="admin"):
        return
    parts = call.data.split(":")
    tid = int(parts[-2])
    target_node = int(parts[-1])
    t = await db.get_inbound_template(tid)
    if not t:
        await call.answer("Шаблон не найден.", show_alert=True)
        return
    try:
        payload = json.loads(t.payload_json)
        port = int(payload.get("port") or 0)
    except (json.JSONDecodeError, TypeError, ValueError):
        await call.answer("Шаблон повреждён.", show_alert=True)
        return
    try:
        if port and await _port_free(target_node, port):
            await _deploy_template(tid, target_node, port)
            await audit_from_call(
                db, call, "inbound_template.deploy", target_type="inbound_template",
                target_id=str(tid), details=f"target_node={target_node}; port={port}",
            )
            await call.answer("Развёртывание завершено. Inbound отключён.")
            text, kb = await inbound_list_view()
            await render_callback(call, text, reply_markup=kb)
            return
        await state.clear()
        await state.set_state(InboundEditStates.template_port)
        await state.update_data(template_id=tid, template_target_node=target_node)
        await render_callback(call, 
            f"Порт {port} уже занят на выбранном сервере.\n\nВведи другой порт (1-65535):",
            reply_markup=template_cancel_keyboard(tid),
        )
        await call.answer()
    except XUIError as exc:
        await call.answer(f"3x-ui: {str(exc)[:160]}", show_alert=True)


@inbound_admin_router.message(InboundEditStates.template_port)
async def template_deploy_port(message: Message, state: FSMContext):
    if not await guard_message(message, state):
        return
    data = await state.get_data()
    tid = int(data.get("template_id") or 0)
    target_node = int(data.get("template_target_node") or 0)
    try:
        port = int((message.text or "").strip())
    except ValueError:
        await render_input(message, "Нужен числовой порт.", reply_markup=template_cancel_keyboard(tid))
        return
    if not 1 <= port <= 65535:
        await render_input(message, "Порт должен быть 1-65535.", reply_markup=template_cancel_keyboard(tid))
        return
    if not await _port_free(target_node, port):
        await render_input(message, "Этот порт уже занят на выбранном сервере.", reply_markup=template_cancel_keyboard(tid))
        return
    try:
        await _deploy_template(tid, target_node, port)
        await audit_from_message(
            db, message, "inbound_template.deploy", target_type="inbound_template",
            target_id=str(tid), details=f"target_node={target_node}; port={port}",
        )
        await state.clear()
        await render_input(message, 
            "✅ Развёртывание завершено. Новый Inbound отключён.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="📡 Inbounds", callback_data="admin:infra:inbounds")
            ]]),
        )
    except (XUIError, ValueError) as exc:
        await state.clear()
        await render_input(message, f"Ошибка развёртывания: {exc}", reply_markup=template_back_keyboard(tid))


@inbound_admin_router.callback_query(F.data.startswith("admin:inboundtemplate:deleteask:"))
async def template_delete_ask(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    tid = int(call.data.rsplit(":", 1)[-1])
    t = await db.get_inbound_template(tid)
    if not t:
        await call.answer("Шаблон не найден.", show_alert=True)
        return
    await render_callback(call, 
        f"Удалить шаблон «{t.name}»?\n\nРазвёрнутые Inbounds не изменятся.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ Удалить", callback_data=f"admin:inboundtemplate:delete:{tid}")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:inboundtemplate:{tid}")],
        ]),
    )
    await call.answer()


@inbound_admin_router.callback_query(F.data.regexp(r"^admin:inboundtemplate:delete:\d+$"))
async def template_delete(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    tid = int(call.data.rsplit(":", 1)[-1])
    t = await db.get_inbound_template(tid)
    await db.delete_inbound_template(tid)
    await audit_from_call(
        db, call, "inbound_template.delete", target_type="inbound_template", target_id=str(tid),
        details=f"name={t.name if t else ''}",
    )
    await call.answer("Шаблон удалён.")
    templates = await db.list_inbound_templates()
    rows = [[InlineKeyboardButton(text=f"🧩 {x.name}", callback_data=f"admin:inboundtemplate:{x.id}")]
            for x in templates[:50]]
    rows.append([InlineKeyboardButton(text="⬅ Inbounds", callback_data="admin:infra:inbounds")])
    await render_callback(call, 
        "🧩 Шаблоны Inbounds\n\n" + (f"Шаблонов: {len(templates)}" if templates else "Шаблонов пока нет."),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@inbound_admin_router.callback_query(F.data.startswith("admin:inbound:deleteask:"))
async def inbound_delete_ask(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    iid = int(call.data.rsplit(":", 1)[-1])
    try:
        ib = await xui.inbound_get(iid)
    except XUIError as exc:
        await call.answer(f"3x-ui: {str(exc)[:160]}", show_alert=True)
        return
    clients = _settings(ib).get("clients") or []
    await render_callback(call, 
        f"🗑 Удалить Inbound #{iid} «{ib.get('remark') or '-'}»?\n\n"
        f"Клиентов внутри: {len(clients) if isinstance(clients, list) else 0}.\n"
        "Удаление Inbound необратимо. 3x-ui также удалит связанные строки трафика/статистики; "
        "перед удалением проверь клиентские привязки.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ Да, удалить Inbound", callback_data=f"admin:inbound:delete:{iid}")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:inbound:{iid}")],
        ]),
    )
    await call.answer()


@inbound_admin_router.callback_query(F.data.regexp(r"^admin:inbound:delete:\d+$"))
async def inbound_delete(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    iid = int(call.data.rsplit(":", 1)[-1])
    try:
        ib = await xui.inbound_get(iid)
        await xui.inbound_delete(iid)
        await audit_from_call(
            db, call, "inbound.delete", target_type="inbound", target_id=str(iid),
            details=f"remark={str(ib.get('remark') or '')[:120]}; port={ib.get('port')}; protocol={ib.get('protocol')}",
        )
        await call.answer("Inbound удалён.")
        text, kb = await inbound_list_view()
        await render_callback(call, text, reply_markup=kb)
    except XUIMutationError as exc:
        if exc.uncertain:
            try:
                inbounds = await xui.inbounds_list(slim=True)
            except XUIError as read_exc:
                await audit_from_call(
                    db, call, "inbound.delete.unknown", target_type="inbound", target_id=str(iid),
                    details=(
                        f"code={exc.code}; mutation_not_retried=true; "
                        f"readback=unavailable:{type(read_exc).__name__}"
                    ),
                    success=False,
                )
                await call.answer("Итог удаления неизвестен", show_alert=True)
                await render_callback(
                    call,
                    "🟡 Ответ 3x-ui потерян, а read-back недоступен. Mutation не повторялась. "
                    "Проверь список Inbounds после восстановления связи перед новым удалением.",
                    reply_markup=inbound_back_keyboard(iid),
                )
                return
            if all(int(item.get("id") or 0) != iid for item in inbounds if isinstance(item, dict)):
                await audit_from_call(
                    db, call, "inbound.delete", target_type="inbound", target_id=str(iid),
                    details="readback=absent; uncertain_resolved=success",
                )
                await call.answer("Inbound удалён.")
                text, kb = await inbound_list_view()
                await render_callback(call, text, reply_markup=kb)
                return
            await audit_from_call(
                db, call, "inbound.delete.unknown", target_type="inbound", target_id=str(iid),
                details=f"code={exc.code}; mutation_not_retried=true; readback=present",
                success=False,
            )
            await call.answer("Итог удаления неизвестен", show_alert=True)
            await render_callback(
                call,
                "🟡 Ответ 3x-ui потерян. Mutation не повторялась; Inbound всё ещё виден при read-back. "
                "Обнови карточку и проверь состояние перед новым удалением.",
                reply_markup=inbound_back_keyboard(iid),
            )
            return
        raise
    except XUIError as exc:
        await audit_from_call(
            db, call, "inbound.delete", target_type="inbound", target_id=str(iid),
            details=str(exc)[:500], success=False,
        )
        await call.answer(f"3x-ui: {str(exc)[:160]}", show_alert=True)