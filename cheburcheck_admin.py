from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
import re
import time
from urllib.parse import urlsplit

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_auth import authorize_callback, authorize_message
from admin_ui import render_callback, render_input
from cheburcheck import (
    CheburcheckClient,
    CheburcheckError,
    CheburcheckResult,
    normalize_target,
)
from config import load_settings
from db import Database
from xui import XUIClient, XUIError


settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
client = CheburcheckClient(
    settings.cheburcheck_url,
    verify_tls=settings.cheburcheck_verify_tls,
)
cheburcheck_router = Router(name="cheburcheck_admin")
_MIN_REQUEST_INTERVAL_SECONDS = 2.0
_MAX_DISCOVERED_TARGETS = 20
_last_request_at: dict[int, float] = {}
_NON_PUBLIC_DOMAIN_SUFFIXES = (
    ".local",
    ".localhost",
    ".internal",
    ".lan",
    ".home",
    ".arpa",
)


@dataclass(frozen=True)
class DiscoveredTarget:
    label: str
    target: str
    callback_data: str


class CheburcheckStates(StatesGroup):
    target = State()


def _compact_label(value: str, *, limit: int = 28) -> str:
    text = " ".join((value or "").split()).strip() or "Ресурс"
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _stored_target(value: str) -> str | None:
    """Extract only a hostname/IP from trusted stored configuration.

    Stored URLs may contain a panel path or port. Those parts are intentionally
    discarded before the target reaches Cheburcheck.
    """
    raw = (value or "").strip()
    if not raw:
        return None

    candidates: list[str] = []
    if "://" in raw:
        try:
            parsed = urlsplit(raw)
        except ValueError:
            return None
        if parsed.hostname:
            candidates.append(parsed.hostname)
    else:
        candidates.append(raw)
        try:
            parsed = urlsplit("//" + raw)
        except ValueError:
            parsed = None
        if parsed is not None and parsed.hostname and parsed.hostname != raw:
            candidates.append(parsed.hostname)

    for candidate in candidates:
        try:
            target = normalize_target(candidate)
        except CheburcheckError:
            continue
        lowered = target.casefold()
        if lowered.endswith(_NON_PUBLIC_DOMAIN_SUFFIXES):
            continue
        if "/" in target or target.upper().startswith("AS"):
            continue
        return target
    return None


async def discover_targets() -> tuple[list[DiscoveredTarget], tuple[str, ...]]:
    """Return safe, de-duplicated stored targets without exposing credentials."""
    if not client.enabled:
        return [], ()

    targets: list[DiscoveredTarget] = []
    warnings: list[str] = []
    seen: set[str] = set()

    def add(label: str, value: str, callback_data: str) -> None:
        target = _stored_target(value)
        if not target or target.casefold() in seen:
            return
        seen.add(target.casefold())
        targets.append(
            DiscoveredTarget(
                label=_compact_label(label),
                target=target,
                callback_data=callback_data,
            )
        )

    add(
        f"🖥 {settings.master_name}",
        settings.panel_url,
        "admin:cheburcheck:target:master",
    )

    try:
        nodes = await xui.nodes_list()
    except XUIError:
        warnings.append("ноды")
        nodes = []
    for node in nodes:
        if len(targets) >= _MAX_DISCOVERED_TARGETS:
            break
        if node.id <= 0 or node.transitive:
            continue
        add(
            f"🌍 {node.name}",
            node.address,
            f"admin:cheburcheck:target:node:{node.id}",
        )

    try:
        hosts = await db.list_hosts()
    except Exception:
        warnings.append("хосты")
        hosts = []
    for host in hosts:
        if len(targets) >= _MAX_DISCOVERED_TARGETS:
            break
        if not host.enabled:
            continue
        add(
            f"🌐 {host.label or host.hostname}",
            host.hostname,
            f"admin:cheburcheck:target:host:{host.id}",
        )

    return targets[:_MAX_DISCOVERED_TARGETS], tuple(warnings)


def _home_keyboard(targets: list[DiscoveredTarget]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if client.enabled:
        for item in targets:
            target = item.target if len(item.target) <= 34 else item.target[:33] + "…"
            rows.append([
                InlineKeyboardButton(
                    text=f"{item.label} · {target}",
                    callback_data=item.callback_data,
                )
            ])
        rows.append([
            InlineKeyboardButton(
                text="✏️ Ввести вручную",
                callback_data="admin:cheburcheck:start:monitoring",
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text="⬅ Мониторинг",
            callback_data="admin:section:monitoring",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _context_token(value: str | None) -> str:
    token = (value or "").strip().lower()
    if token == "master":
        return "master"
    if token.startswith("node-") and token[5:].isdigit():
        return token
    return "monitoring"


def _context_back(context: str) -> tuple[str, str]:
    token = _context_token(context)
    if token == "master":
        return "admin:master", "⬅ Master"
    if token.startswith("node-"):
        return f"admin:node:{int(token[5:])}", "⬅ Нода"
    return "admin:cheburcheck", "⬅ Проверка блокировок"


def _cancel_keyboard(context: str) -> InlineKeyboardMarkup:
    token = _context_token(context)
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✖ Отмена",
            callback_data=f"admin:cheburcheck:cancel:{token}",
        )
    ]])


def _result_keyboard(context: str = "monitoring") -> InlineKeyboardMarkup:
    token = _context_token(context)
    back_callback, back_text = _context_back(token)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔎 Проверить ещё",
                callback_data=f"admin:cheburcheck:start:{token}",
            )
        ],
        [InlineKeyboardButton(text=back_text, callback_data=back_callback)],
    ])


def _error_keyboard(
    retry_callback: str,
    *,
    context: str,
) -> InlineKeyboardMarkup:
    back_callback, back_text = _context_back(context)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Повторить", callback_data=retry_callback)],
        [InlineKeyboardButton(text=back_text, callback_data=back_callback)],
    ])

def _home_text(
    targets: list[DiscoveredTarget],
    warnings: tuple[str, ...],
) -> str:
    status = "🟢 настроен" if client.enabled else "⚪ не настроен"
    detail = (
        "Сервис включён. Доступность проверяется при каждом запросе."
        if client.enabled else
        "Укажи CHEBURCHECK_URL в локальной конфигурации, чтобы включить диагностику."
    )
    lines = [
        "🔎 Проверка блокировок",
        "",
        "Read-only диагностика домена, публичного IP, подсети или ASN через Cheburcheck.",
        "Функция не меняет VPN-конфигурацию и не выполняет provisioning.",
        "",
        f"Сервис: {status}",
        detail,
    ]
    if client.enabled:
        lines += [
            "",
            (
                f"Обнаружено целей: {len(targets)}. "
                "Можно выбрать уже известный Master/Node/Host или ввести цель вручную."
                if targets else
                "Подходящие публичные Master/Node/Host цели не обнаружены. "
                "Можно ввести цель вручную."
            ),
            "Из сохранённых URL используются только hostname/IP; path и credentials не передаются.",
        ]
        if warnings:
            lines.append("⚠️ Не удалось прочитать часть источников: " + ", ".join(warnings) + ".")
    return "\n".join(lines)


async def _home_view() -> tuple[str, InlineKeyboardMarkup]:
    targets, warnings = await discover_targets()
    return _home_text(targets, warnings), _home_keyboard(targets)


def _network_word(count: int) -> str:
    value = abs(int(count))
    if value % 10 == 1 and value % 100 != 11:
        return "сеть"
    if value % 10 in {2, 3, 4} and value % 100 not in {12, 13, 14}:
        return "сети"
    return "сетей"


def _cdn_text(result: CheburcheckResult) -> str:
    if not result.cdn_providers:
        return "🟢 не найден"
    names = ", ".join(item.name for item in result.cdn_providers[:3])
    if len(result.cdn_providers) > 3:
        names += f", … ещё {len(result.cdn_providers) - 3}"
    networks = sum(item.network_count for item in result.cdn_providers)
    return f"{names} · {networks} {_network_word(networks)}"


def result_text(result: CheburcheckResult) -> str:
    verdict = "🔴 обнаружена блокировка" if result.blocked else "🟢 блокировка не обнаружена"
    network = " · ".join(
        part for part in (result.organisation, result.asn, result.location) if part
    ) or "—"

    if result.rkn_domain:
        rkn = "🔴 найден"
    elif result.blocked_subnets:
        rkn = f"🔴 {len(result.blocked_subnets)} подсетей"
    else:
        rkn = "🟢 не найден"

    whitelist = "—"
    if result.whitelist:
        whitelist = "🟡 найдено"
        if result.whitelist_last_ok:
            whitelist += f" · last ok {result.whitelist_last_ok}"

    asn_lists = "—"
    if result.asn_prefix_count:
        asn_lists = (
            f"{result.asn_blocked_prefix_count} / "
            f"{result.asn_prefix_count} подсетей в списках"
        )

    regions = "—"
    target = result.target.strip().upper()
    regional_supported = "/" not in target and re.fullmatch(r"AS[1-9][0-9]{0,9}", target) is None
    if result.probe_summary is not None:
        summary = result.probe_summary
        if summary.online_probes == 0:
            regions = "⚪ нет активных региональных сканеров"
        elif summary.response_count == 0:
            regions = f"🟡 нет ответов · {summary.online_probes} сканеров онлайн"
        else:
            regions = (
                f"{summary.response_count} ответов · "
                f"🟢 {summary.green} · 🔴 {summary.red} · 🟡 {summary.yellow}"
            )
    elif regional_supported:
        regions = "🟡 региональная проверка недоступна"

    return "\n".join([
        "🔎 Проверка блокировок",
        "",
        f"Цель: {result.target}",
        f"Результат: {verdict}",
        f"Сеть: {network}",
        "",
        "📋 Списки",
        f"РКН: {rkn}",
        f"CDN: {_cdn_text(result)}",
        f"Исключение CDN: {whitelist}",
        f"ASN: {asn_lists}",
        "",
        f"🌍 Регионы: {regions}",
        "",
        "Источник: Cheburcheck.",
    ])


async def _check_result(target: str) -> CheburcheckResult:
    result = await client.check(target)

    asn_task = client.asn_summary(result)
    probe_task = client.probe_summary(result)
    asn_summary, probe_summary = await asyncio.gather(
        asn_task,
        probe_task,
        return_exceptions=True,
    )

    updates = {}
    if not isinstance(asn_summary, Exception) and asn_summary is not None:
        blocked_count, prefix_count = asn_summary
        updates["asn_blocked_prefix_count"] = blocked_count
        updates["asn_prefix_count"] = prefix_count
    if not isinstance(probe_summary, Exception):
        updates["probe_summary"] = probe_summary
    return replace(result, **updates)

def _consume_cooldown(actor_id: int) -> bool:
    now = time.monotonic()
    previous = _last_request_at.get(int(actor_id), 0.0)
    if now - previous < _MIN_REQUEST_INTERVAL_SECONDS:
        return False
    _last_request_at[int(actor_id)] = now
    return True


async def _check_callback_target(
    call: CallbackQuery,
    target: str,
    *,
    context: str,
) -> None:
    if not client.enabled:
        if _context_token(context) == "monitoring":
            text, keyboard = await _home_view()
            await render_callback(call, text, reply_markup=keyboard)
        else:
            back_callback, back_text = _context_back(context)
            await render_callback(
                call,
                "🔎 Проверка блокировок\n\n⚪ Cheburcheck не настроен.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text=back_text, callback_data=back_callback)
                ]]),
            )
        await call.answer("Cheburcheck не настроен", show_alert=True)
        return
    if not _consume_cooldown(call.from_user.id):
        await call.answer("Слишком частые запросы. Повтори через пару секунд.", show_alert=True)
        return
    try:
        result = await _check_result(target)
    except CheburcheckError as exc:
        await render_callback(
            call,
            f"🔎 Проверка блокировок\n\n⚠️ {exc}",
            reply_markup=_error_keyboard(
                call.data or "admin:cheburcheck",
                context=context,
            ),
        )
        await call.answer()
        return

    await render_callback(
        call,
        result_text(result),
        reply_markup=_result_keyboard(context),
    )
    await call.answer()


@cheburcheck_router.callback_query(F.data == "admin:cheburcheck")
async def cheburcheck_home(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    await state.clear()
    text, keyboard = await _home_view()
    await render_callback(call, text, reply_markup=keyboard)
    await call.answer()


@cheburcheck_router.callback_query(
    F.data.regexp(r"^admin:cheburcheck:start(?::(monitoring|master|node-\d+))?$")
)
async def cheburcheck_start(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    context = _context_token((call.data or "").split(":")[-1] if ":" in (call.data or "") else None)
    if call.data == "admin:cheburcheck:start":
        context = "monitoring"
    if not client.enabled:
        if context == "monitoring":
            text, keyboard = await _home_view()
            await render_callback(call, text, reply_markup=keyboard)
        else:
            back_callback, back_text = _context_back(context)
            await render_callback(
                call,
                "🔎 Проверка блокировок\n\n⚪ Cheburcheck не настроен.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text=back_text, callback_data=back_callback)
                ]]),
            )
        await call.answer("Cheburcheck не настроен", show_alert=True)
        return
    await state.clear()
    await state.set_state(CheburcheckStates.target)
    await state.update_data(cheburcheck_context=context)
    await render_callback(
        call,
        "🔎 Проверка блокировок\n\n"
        "Введи домен, публичный IP-адрес, подсеть или ASN.\n\n"
        "Примеры:\n"
        "example.org\n"
        "1.1.1.1\n"
        "1.1.1.0/24\n"
        "AS13335",
        reply_markup=_cancel_keyboard(context),
    )
    await call.answer()


@cheburcheck_router.callback_query(
    F.data.regexp(r"^admin:cheburcheck:cancel(?::(monitoring|master|node-\d+))?$")
)
async def cheburcheck_cancel(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    context = _context_token((call.data or "").split(":")[-1] if ":" in (call.data or "") else None)
    if call.data == "admin:cheburcheck:cancel":
        context = "monitoring"
    await state.clear()
    if context == "monitoring":
        text, keyboard = await _home_view()
        await render_callback(call, text, reply_markup=keyboard)
    else:
        back_callback, back_text = _context_back(context)
        await render_callback(
            call,
            "🔎 Проверка блокировок\n\nПроверка отменена.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=back_text, callback_data=back_callback)
            ]]),
        )
    await call.answer("Отменено")


@cheburcheck_router.callback_query(F.data == "admin:cheburcheck:target:master")
async def cheburcheck_target_master(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    target = _stored_target(settings.panel_url)
    if not target:
        await call.answer("У Master нет подходящего публичного hostname/IP.", show_alert=True)
        return
    await _check_callback_target(call, target, context="monitoring")


@cheburcheck_router.callback_query(
    F.data.regexp(r"^admin:cheburcheck:target:node:\d+$")
)
async def cheburcheck_target_node(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    try:
        node_id = int((call.data or "").rsplit(":", 1)[-1])
        node = await xui.node_get_enriched(node_id)
    except (ValueError, XUIError):
        await call.answer("Не удалось прочитать ноду.", show_alert=True)
        return
    target = _stored_target(node.address)
    if not target:
        await call.answer("У ноды нет подходящего публичного hostname/IP.", show_alert=True)
        return
    await _check_callback_target(call, target, context="monitoring")


@cheburcheck_router.callback_query(
    F.data.regexp(r"^admin:cheburcheck:target:host:\d+$")
)
async def cheburcheck_target_host(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    try:
        host_id = int((call.data or "").rsplit(":", 1)[-1])
    except ValueError:
        await call.answer("Некорректный ID хоста.", show_alert=True)
        return
    host = await db.get_host(host_id)
    if host is None or not host.enabled:
        await call.answer("Хост не найден или отключён.", show_alert=True)
        return
    target = _stored_target(host.hostname)
    if not target:
        await call.answer("У хоста нет подходящего публичного hostname/IP.", show_alert=True)
        return
    await _check_callback_target(call, target, context="monitoring")


@cheburcheck_router.callback_query(F.data == "admin:cheburcheck:master")
async def cheburcheck_master(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    target = _stored_target(settings.panel_url)
    if not target:
        await call.answer("У Master нет подходящего публичного hostname/IP.", show_alert=True)
        return
    await _check_callback_target(
        call,
        target,
        context="master",
    )


@cheburcheck_router.callback_query(F.data.regexp(r"^admin:cheburcheck:node:\d+$"))
async def cheburcheck_node(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    try:
        node_id = int((call.data or "").rsplit(":", 1)[-1])
        node = await xui.node_get_enriched(node_id)
    except (ValueError, XUIError):
        await call.answer("Не удалось прочитать ноду.", show_alert=True)
        return
    target = _stored_target(node.address)
    if not target:
        await call.answer("У ноды нет подходящего публичного hostname/IP.", show_alert=True)
        return
    await _check_callback_target(
        call,
        target,
        context=f"node-{node_id}",
    )


@cheburcheck_router.callback_query(F.data.regexp(r"^admin:cheburcheck:host:\d+$"))
async def cheburcheck_host(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    try:
        host_id = int((call.data or "").rsplit(":", 1)[-1])
    except ValueError:
        await call.answer("Некорректный ID хоста.", show_alert=True)
        return
    host = await db.get_host(host_id)
    if host is None or not host.enabled:
        await call.answer("Хост не найден или отключён.", show_alert=True)
        return
    target = _stored_target(host.hostname)
    if not target:
        await call.answer("У хоста нет подходящего публичного hostname/IP.", show_alert=True)
        return
    await _check_callback_target(
        call,
        target,
        context="monitoring",
    )


@cheburcheck_router.message(CheburcheckStates.target)
async def cheburcheck_target(message: Message, state: FSMContext):
    if not message.from_user:
        return
    ok, _ = await authorize_message(
        db,
        settings,
        message.from_user.id,
        minimum="read_only",
    )
    if not ok:
        await state.clear()
        targets, _ = await discover_targets()
        await render_input(
            message,
            "Недостаточно прав.",
            reply_markup=_home_keyboard(targets),
        )
        return

    state_data = await state.get_data()
    context = _context_token(state_data.get("cheburcheck_context"))

    if not _consume_cooldown(message.from_user.id):
        await render_input(
            message,
            "🔎 Проверка блокировок\n\n⚠️ Слишком частые запросы. Повтори через пару секунд.",
            reply_markup=_cancel_keyboard(context),
        )
        return

    raw = (message.text or "").strip()
    try:
        result = await _check_result(raw)
    except CheburcheckError as exc:
        await render_input(
            message,
            f"🔎 Проверка блокировок\n\n⚠️ {exc}\n\nПопробуй другую цель.",
            reply_markup=_cancel_keyboard(context),
        )
        return

    await state.clear()
    await render_input(
        message,
        result_text(result),
        reply_markup=_result_keyboard(context),
    )
