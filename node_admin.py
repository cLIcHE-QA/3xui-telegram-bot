from __future__ import annotations

import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_auth import authorize_callback, authorize_message
from admin_navigation import admin_menu
from admin_ui import render_callback, render_input
from audit import audit_from_call
from backup_manager import BackupManager
from config import load_settings
from db import Database
from host_control import HostControlClient, HostControlError
from node_onboarding import AddNodeStates, node_mutation_payload, parse_node_url
from node_ui import (
    add_node_retry_keyboard,
    add_node_review_keyboard,
    add_node_tls_keyboard,
    node_detail_keyboard,
    node_detail_text as node_detail_text_view,
    node_display_name,
    node_status_icon,
    node_status_text,
    xray_state_text,
    nodes_menu as nodes_menu_view,
)
from system_backup import SystemBackupService
from xui import NodeInfo, XUIClient, XUIError


settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
backup_manager = BackupManager(settings.db_path, settings.backup_dir, settings.backup_keep)
system_backup = SystemBackupService(
    backup_manager,
    settings.node_backup_targets,
    settings.host_control_targets,
)

node_admin_router = Router(name="node_admin")


async def _guard_admin_call(call: CallbackQuery) -> bool:
    ok, _ = await authorize_callback(db, settings, call)
    return ok


def nodes_menu(nodes: list[NodeInfo], master_online: bool = True) -> InlineKeyboardMarkup:
    return nodes_menu_view(
        nodes,
        master_online,
        master_flag=settings.master_flag,
        master_name=settings.master_name,
    )


def node_detail_text(node: NodeInfo) -> str:
    return node_detail_text_view(
        node,
        backup_configured=system_backup.has_target_for(
            node.name,
            getattr(node, "id", None),
        ),
    )


def _binding_mode_text(mode: str) -> str:
    return {
        "node_id": "node_id",
        "legacy_name": "legacy name",
        "missing": "не настроена",
    }.get(mode, mode or "не настроена")


def _host_state_text(state: str) -> str:
    return {
        "running": "работает",
        "stopped": "остановлен",
        "transitioning": "переходное состояние",
        "unavailable": "недоступен",
        "not configured": "не настроен",
    }.get((state or "").lower(), state or "неизвестно")


def _host_control_target_for_node(node: NodeInfo):
    for target in settings.host_control_targets:
        if target.node_id == node.id:
            return target, "node_id"
    needle = node.name.strip().casefold()
    for target in settings.host_control_targets:
        if (
            target.key != "MASTER"
            and target.node_id is None
            and target.name.strip().casefold() == needle
        ):
            return target, "legacy_name"
    return None, "missing"


@node_admin_router.callback_query(F.data == "admin:nodes")
async def admin_nodes(call: CallbackQuery):
    if not await _guard_admin_call(call):
        return

    master_online = False
    master_error = None
    try:
        await xui.server_status()
        master_online = True
    except XUIError as exc:
        master_error = str(exc)

    nodes: list[NodeInfo] = []
    nodes_error = None
    try:
        nodes = await xui.nodes_list()
    except XUIError as exc:
        nodes_error = str(exc)

    online = (1 if master_online else 0) + sum(
        1 for node in nodes if node.enable and node.status == "online"
    )
    total = 1 + len(nodes)
    text = f"🌍 Ноды\n\nСерверов: {total} · в сети: {online}"
    if not nodes and not nodes_error:
        text += (
            "\n\nПока зарегистрированных нод нет. "
            "Используй «➕ Добавить ноду», чтобы подключить сервер."
        )
    if master_error:
        text += f"\n\n⚠️ Master: {master_error[:180]}"
    if nodes_error:
        text += f"\n⚠️ API нод: {nodes_error[:180]}"

    await render_callback(call, text, reply_markup=nodes_menu(nodes, master_online))
    await call.answer()


@node_admin_router.callback_query(F.data == "admin:nodeadd:start")
async def admin_node_add_start(call: CallbackQuery, state: FSMContext):
    if not await _guard_admin_call(call):
        return
    await state.clear()
    await state.set_state(AddNodeStates.name)
    await render_callback(
        call,
        "➕ Добавление ноды\n\n"
        "Шаг 1/4. Отправь имя ноды.\n"
        "Например: Finland",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:nodeadd:cancel")]
        ]),
    )
    await call.answer()


@node_admin_router.message(AddNodeStates.name)
async def admin_node_add_name(message: Message, state: FSMContext):
    if not message.from_user:
        return
    ok, _ = await authorize_message(
        db,
        settings,
        message.from_user.id,
        minimum="admin",
    )
    if not ok:
        await state.clear()
        await render_input(message, "Недостаточно прав.")
        return
    name = (message.text or "").strip()
    if not name or len(name) > 64:
        await render_input(message, "Имя должно содержать от 1 до 64 символов.")
        return
    await state.update_data(name=name)
    await state.set_state(AddNodeStates.url)
    await render_input(
        message,
        "Шаг 2/4. Отправь URL панели 3x-ui на ноде.\n\n"
        "Можно целиком, например:\n"
        "https://fi.example.com:2053/my-base/panel/\n\n"
        "Можно вставить URL прямо из браузера: завершающий /panel/ будет убран автоматически. "
        "Если схема не указана, будет использован https.",
    )


@node_admin_router.message(AddNodeStates.url)
async def admin_node_add_url(message: Message, state: FSMContext):
    if not message.from_user:
        return
    ok, _ = await authorize_message(
        db,
        settings,
        message.from_user.id,
        minimum="admin",
    )
    if not ok:
        await state.clear()
        await render_input(message, "Недостаточно прав.")
        return
    try:
        parsed = parse_node_url(message.text or "")
    except ValueError as exc:
        await render_input(message, f"Не удалось разобрать URL: {exc}\nПопробуй ещё раз.")
        return
    await state.update_data(**parsed)
    await state.set_state(AddNodeStates.token)
    await render_input(
        message,
        "Шаг 3/4. Отправь API token этой ноды.\n\n"
        "Токен 3x-ui является полным административным секретом. "
        "Сообщение с токеном бот попробует удалить сразу после получения.",
    )


@node_admin_router.message(AddNodeStates.token)
async def admin_node_add_token(message: Message, state: FSMContext):
    if not message.from_user:
        return
    ok, _ = await authorize_message(
        db,
        settings,
        message.from_user.id,
        minimum="admin",
    )
    if not ok:
        await state.clear()
        await render_input(message, "Недостаточно прав.")
        return
    token = (message.text or "").strip()
    if len(token) < 8:
        await render_input(
            message,
            "Токен выглядит слишком коротким. Отправь API token ноды ещё раз.",
        )
        return
    await state.update_data(apiToken=token)
    try:
        await message.delete()
    except Exception:
        pass
    await state.set_state(AddNodeStates.review)
    await render_input(
        message,
        "Шаг 4/4. Как проверять TLS-сертификат ноды?\n\n"
        "Рекомендуется «Проверять TLS». Режим без проверки нужен только для "
        "временного теста или собственного сертификата.",
        reply_markup=add_node_tls_keyboard(),
    )


async def _node_add_test_and_show(
    call: CallbackQuery,
    state: FSMContext,
    tls_mode: str | None = None,
):
    data = await state.get_data()
    if not data.get("apiToken"):
        await state.clear()
        await render_callback(
            call,
            "Сессия добавления ноды истекла. Начни добавление заново.",
            reply_markup=admin_menu(),
        )
        return
    if tls_mode:
        await state.update_data(tlsVerifyMode=tls_mode)
        data["tlsVerifyMode"] = tls_mode
    data.setdefault("tlsVerifyMode", "verify")
    payload = node_mutation_payload(data)
    try:
        result = await xui.node_test(payload)
    except XUIError as exc:
        mode = str(data.get("tlsVerifyMode") or "verify")
        await render_callback(
            call,
            "🔴 Проверка ноды не прошла.\n\n"
            f"{str(exc)[:500]}\n\n"
            "Проверь URL/API token. Если на ноде собственный TLS-сертификат, "
            "можно временно попробовать режим без проверки.",
            reply_markup=add_node_retry_keyboard(mode),
        )
        return

    mode = str(data.get("tlsVerifyMode") or "verify")
    status = str(result.get("status") or "unknown").lower()
    status_icon = "🟢" if status == "online" else "🟡"
    lines = [
        "🔍 Проверка ноды завершена",
        "",
        f"Имя: {node_display_name(str(data['name']))}",
        f"Адрес: {data['scheme']}://{data['address']}:{data['port']}{data['basePath']}",
        f"TLS: {mode}",
        f"{status_icon} Панель: {node_status_text(status)}",
    ]
    if result.get("panelVersion"):
        lines.append(f"3x-ui: {result['panelVersion']}")
    if result.get("xrayState"):
        lines.append(
            f"Xray: {xray_state_text(str(result['xrayState']))} {result.get('xrayVersion') or ''}".rstrip()
        )
    if result.get("latencyMs") is not None:
        lines.append(f"Задержка API: {int(result.get('latencyMs') or 0)} ms")
    if result.get("cpuPct") is not None:
        lines.append(f"🧮 CPU: {float(result.get('cpuPct') or 0):.1f}%")
    if result.get("memPct") is not None:
        lines.append(f"🧠 RAM: {float(result.get('memPct') or 0):.1f}%")
    if result.get("error"):
        lines.append(f"⚠️ {str(result['error'])[:240]}")
    if result.get("xrayError"):
        lines.append(f"⚠️ Xray: {str(result['xrayError'])[:240]}")
    lines += ["", "Если всё верно, нажми «✅ Добавить ноду». "]
    await render_callback(
        call,
        "\n".join(lines),
        reply_markup=add_node_review_keyboard(mode),
    )


@node_admin_router.callback_query(F.data.startswith("admin:nodeadd:tls:"))
async def admin_node_add_tls(call: CallbackQuery, state: FSMContext):
    if not await _guard_admin_call(call):
        return
    mode = call.data.rsplit(":", 1)[-1]
    if mode not in {"verify", "skip"}:
        await call.answer("Некорректный TLS-режим", show_alert=True)
        return
    await call.answer("Проверяю соединение…")
    await _node_add_test_and_show(call, state, mode)


@node_admin_router.callback_query(F.data == "admin:nodeadd:test")
async def admin_node_add_test(call: CallbackQuery, state: FSMContext):
    if not await _guard_admin_call(call):
        return
    await call.answer("Проверяю соединение…")
    await _node_add_test_and_show(call, state)


@node_admin_router.callback_query(F.data == "admin:nodeadd:save")
async def admin_node_add_save(call: CallbackQuery, state: FSMContext):
    if not await _guard_admin_call(call):
        return
    data = await state.get_data()
    if not data.get("apiToken"):
        await state.clear()
        await call.answer("Сессия добавления истекла", show_alert=True)
        return
    payload = node_mutation_payload(data)
    await call.answer("Добавляю ноду…")
    try:
        node = await xui.node_add(payload)
        try:
            probed = await xui.node_probe(node.id)
            if probed is not None:
                node = probed
        except XUIError:
            pass
    except XUIError as exc:
        await audit_from_call(
            db,
            call,
            "node.add",
            target_type="node",
            target_id=str(data.get("name") or ""),
            details=f"3x-ui error: {exc}",
            success=False,
        )
        await render_callback(
            call,
            "🔴 Не удалось добавить ноду.\n\n"
            f"Ошибка 3x-ui: {str(exc)[:500]}",
            reply_markup=add_node_review_keyboard(
                str(data.get("tlsVerifyMode") or "verify")
            ),
        )
        return

    await audit_from_call(
        db,
        call,
        "node.add",
        target_type="node",
        target_id=str(node.id),
        details=f"name={node.name}; status={node.status}",
    )
    await state.clear()
    await render_callback(
        call,
        f"✅ Нода {node_display_name(node.name)} добавлена.\n"
        f"Статус: {node_status_icon(node)} {node_status_text(node.status)}",
        reply_markup=node_detail_keyboard(node.id, node.enable),
    )


@node_admin_router.callback_query(F.data == "admin:nodeadd:cancel")
async def admin_node_add_cancel(call: CallbackQuery, state: FSMContext):
    if not await _guard_admin_call(call):
        return
    await state.clear()
    await call.answer("Добавление отменено")
    await render_callback(
        call,
        "Добавление ноды отменено.",
        reply_markup=admin_menu(),
    )


@node_admin_router.callback_query(F.data == "admin:nodes:noop")
async def admin_nodes_noop(call: CallbackQuery):
    if not await _guard_admin_call(call):
        return
    await call.answer("Транзитная нода отображается только для мониторинга.")


@node_admin_router.callback_query(F.data == "admin:nodes:refresh")
async def admin_nodes_refresh(call: CallbackQuery):
    if not await _guard_admin_call(call):
        return
    await call.answer("Проверяю серверы…")

    master_online = False
    try:
        await xui.server_status()
        master_online = True
    except XUIError:
        pass

    try:
        current = await xui.nodes_list()
        direct = [node for node in current if node.id > 0 and not node.transitive]
        if direct:
            await asyncio.gather(
                *(xui.node_probe(node.id) for node in direct),
                return_exceptions=True,
            )
        nodes = await xui.nodes_list()
        online = (1 if master_online else 0) + sum(
            1 for node in nodes if node.enable and node.status == "online"
        )
        await render_callback(
            call,
            f"🌍 Ноды обновлены\n\nСерверов: {1 + len(nodes)} · в сети: {online}",
            reply_markup=nodes_menu(nodes, master_online),
        )
    except XUIError as exc:
        await render_callback(
            call,
            "🌍 Ноды обновлены\n\n"
            f"{settings.master_flag} {settings.master_name}: "
            f"{'🟢 В сети' if master_online else '🔴 Не в сети'}\n"
            f"⚠️ API нод: {str(exc)[:180]}",
            reply_markup=nodes_menu([], master_online),
        )


@node_admin_router.callback_query(F.data.regexp(r"^admin:node:\d+$"))
async def admin_node_detail(call: CallbackQuery):
    if not await _guard_admin_call(call):
        return
    try:
        node_id = int(call.data.rsplit(":", 1)[1])
    except (TypeError, ValueError):
        await call.answer("Некорректный ID ноды", show_alert=True)
        return

    await call.answer("Проверяю ноду…")
    probe_error = None
    try:
        await xui.node_probe(node_id)
    except XUIError as exc:
        probe_error = str(exc)
    try:
        node = await xui.node_get_enriched(node_id)
    except XUIError as exc:
        await render_callback(
            call,
            f"🔴 Нода недоступна: {exc}",
            reply_markup=admin_menu(),
        )
        return

    text = node_detail_text(node)
    if probe_error and not node.last_error:
        text += f"\n⚠️ Проверка: {probe_error[:240]}"
    await render_callback(
        call,
        text,
        reply_markup=node_detail_keyboard(node_id, node.enable),
    )


@node_admin_router.callback_query(F.data.regexp(r"^admin:node:\d+:readiness$"))
async def admin_node_readiness(call: CallbackQuery):
    ok, _ = await authorize_callback(
        db,
        settings,
        call,
        minimum="read_only",
    )
    if not ok:
        return
    try:
        node_id = int((call.data or "").split(":")[2])
    except (TypeError, ValueError, IndexError):
        await call.answer("Некорректный ID ноды", show_alert=True)
        return

    await call.answer("Проверяю готовность…")
    try:
        node = await xui.node_get_enriched(node_id)
    except XUIError as exc:
        await render_callback(
            call,
            f"🧭 Готовность ноды\n\n🔴 Нода не найдена в Master: {str(exc)[:240]}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅ Ноды", callback_data="admin:nodes")
            ]]),
        )
        return

    direct_target = system_backup.target_for(node.name, node.id)
    direct_mode = (
        "node_id"
        if direct_target is not None and direct_target.node_id == node.id
        else "legacy_name"
        if direct_target is not None
        else "missing"
    )
    direct_ok = False
    direct_error = ""
    if direct_target is not None:
        try:
            await system_backup.direct_client_for(
                node.name,
                getattr(node, "id", None),
            ).server_status()
            direct_ok = True
        except Exception as exc:
            direct_error = type(exc).__name__

    host_target, host_mode = _host_control_target_for_node(node)
    host_ok = False
    host_state = "not configured"
    host_error = ""
    if host_target is not None:
        try:
            status = await HostControlClient(
                host_target.url,
                host_target.token,
                host_target.host_id,
                verify_tls=host_target.verify_tls,
            ).status()
            host_state = status.state
            host_ok = status.state in {"running", "stopped"}
        except HostControlError as exc:
            host_error = exc.code or "unavailable"
            host_state = "unavailable"

    lines = [
        f"🧭 Готовность ноды · {node_display_name(node.name)}",
        "",
        f"ID ноды: {node.id}",
        f"{'🟢' if not node.transitive else '🔴'} Прямая нода: "
        f"{'да' if not node.transitive else 'нет'}",
        f"{'🟢' if node.enable and node.status == 'online' else '🟡'} "
        f"Состояние в Master: {node_status_text(node.status)}",
        "",
        "Привязки привилегированных каналов",
        f"{'🟢' if direct_ok else '🔴'} Прямой API панели: "
        + (
            "в сети"
            if direct_ok
            else (
                "не настроен"
                if direct_target is None
                else f"недоступен ({direct_error})"
            )
        ),
        f"   привязка: {_binding_mode_text(direct_mode)}",
        f"{'🟢' if host_ok else '🔴'} Host Control: {_host_state_text(host_state)}"
        + (f" ({host_error})" if host_error else ""),
        f"   привязка: {_binding_mode_text(host_mode)}",
    ]

    stable = direct_mode == "node_id" and host_mode == "node_id"
    runtime_ready = not node.transitive and direct_ok and host_ok
    lines += [
        "",
        f"{'🟢' if runtime_ready else '🟡'} Готовность к операциям: "
        f"{'готово' if runtime_ready else 'неполно'}",
        f"{'🟢' if stable else '🟡'} Стабильная идентичность: "
        f"{'node_id' if stable else 'нужна миграция'}",
    ]

    hints: list[str] = []
    if direct_target is None:
        hints.append(
            "Direct Admin: импортируй локальный enrollment через "
            f"scripts/import-node-admin-target.py (NODE_ID={node.id})."
        )
    elif direct_mode != "node_id":
        hints.append(f"Direct Admin: добавь NODE_BACKUP_*_NODE_ID={node.id}.")
    if host_target is None:
        hints.append(
            f"Host Control: импортируй enrollment с --node-id {node.id}."
        )
    elif host_mode != "node_id":
        hints.append(f"Host Control: добавь HOST_CONTROL_*_NODE_ID={node.id}.")
    if hints:
        lines += ["", "Следующие шаги"] + [f"• {item}" for item in hints]

    await render_callback(
        call,
        "\n".join(lines)[:3900],
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Проверить снова",
                    callback_data=f"admin:node:{node.id}:readiness",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🧩 Управление 3x-ui",
                    callback_data=f"admin:hostctl:n{node.id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅ Нода",
                    callback_data=f"admin:node:{node.id}",
                )
            ],
        ]),
    )
