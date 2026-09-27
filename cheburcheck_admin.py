from __future__ import annotations

from dataclasses import dataclass
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
        "admin:cheburcheck:master",
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
            f"admin:cheburcheck:node:{node.id}",
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
            f"admin:cheburcheck:host:{host.id}",
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
                callback_data="admin:cheburcheck:start",
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text="⬅ Мониторинг",
            callback_data="admin:section:monitoring",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✖ Отмена",
            callback_data="admin:cheburcheck:cancel",
        )
    ]])


def _result_keyboard(
    *,
    back_callback: str = "admin:cheburcheck",
    back_text: str = "⬅ Проверка блокировок",
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="🔎 Проверить ещё",
                callback_data="admin:cheburcheck:start",
            )
        ],
        [InlineKeyboardButton(text=back_text, callback_data=back_callback)],
    ]
    if back_callback != "admin:section:monitoring":
        rows.append([
            InlineKeyboardButton(
                text="📈 Мониторинг",
                callback_data="admin:section:monitoring",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _error_keyboard(
    retry_callback: str,
    *,
    back_callback: str,
    back_text: str,
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🔄 Повторить", callback_data=retry_callback)],
        [InlineKeyboardButton(text=back_text, callback_data=back_callback)],
    ]
    if back_callback != "admin:section:monitoring":
        rows.append([
            InlineKeyboardButton(
                text="📈 Мониторинг",
                callback_data="admin:section:monitoring",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


def _bounded(values: tuple[str, ...], *, limit: int = 5) -> str:
    if not values:
        return "—"
    shown = list(values[:limit])
    if len(values) > limit:
        shown.append(f"… ещё {len(values) - limit}")
    return ", ".join(shown)


def result_text(result: CheburcheckResult) -> str:
    verdict = "🔴 обнаружена блокировка" if result.blocked else "🟢 блокировка не обнаружена"
    lines = [
        "🔎 Проверка блокировок",
        "",
        f"Цель: {result.target}",
        f"Тип: {result.target_type or '—'}",
        f"Результат: {verdict}",
    ]
    if result.rkn_domain:
        lines.append(f"Домен из реестра: {result.rkn_domain}")
    if result.subnet_size:
        lines.append(f"Размер подсети: {result.subnet_size}")
    lines.extend([
        "",
        f"IP: {_bounded(result.ips)}",
        f"Reverse DNS: {_bounded(result.reverse_lookup)}",
        f"Заблокированные подсети: {_bounded(result.blocked_subnets)}",
    ])
    geo_parts = [part for part in (result.organisation, result.asn, result.location) if part]
    if geo_parts:
        lines.append(f"Сеть: {' · '.join(geo_parts)}")
    complaints = sum(item.count for item in result.complaints)
    if complaints:
        lines.append(f"Жалобы за 14 дней: {complaints}")
    lines.extend([
        "",
        "Источник: Cheburcheck.",
        "Результат отражает данные сервиса на момент запроса и не является гарантией фактической доступности у каждого провайдера.",
    ])
    return "\n".join(lines)


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
    back_callback: str,
    back_text: str,
) -> None:
    if not client.enabled:
        text, keyboard = await _home_view()
        await render_callback(call, text, reply_markup=keyboard)
        await call.answer("Cheburcheck не настроен", show_alert=True)
        return
    if not _consume_cooldown(call.from_user.id):
        await call.answer("Слишком частые запросы. Повтори через пару секунд.", show_alert=True)
        return
    try:
        result = await client.check(target)
    except CheburcheckError as exc:
        await render_callback(
            call,
            f"🔎 Проверка блокировок\n\n⚠️ {exc}",
            reply_markup=_error_keyboard(
                call.data or "admin:cheburcheck",
                back_callback=back_callback,
                back_text=back_text,
            ),
        )
        await call.answer()
        return

    await render_callback(
        call,
        result_text(result),
        reply_markup=_result_keyboard(
            back_callback=back_callback,
            back_text=back_text,
        ),
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


@cheburcheck_router.callback_query(F.data == "admin:cheburcheck:start")
async def cheburcheck_start(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    if not client.enabled:
        text, keyboard = await _home_view()
        await call.answer("Cheburcheck не настроен", show_alert=True)
        await render_callback(call, text, reply_markup=keyboard)
        return
    await state.clear()
    await state.set_state(CheburcheckStates.target)
    await render_callback(
        call,
        "🔎 Проверка блокировок\n\n"
        "Введи домен, публичный IP-адрес, подсеть или ASN.\n\n"
        "Примеры:\n"
        "example.org\n"
        "1.1.1.1\n"
        "1.1.1.0/24\n"
        "AS13335",
        reply_markup=_cancel_keyboard(),
    )
    await call.answer()


@cheburcheck_router.callback_query(F.data == "admin:cheburcheck:cancel")
async def cheburcheck_cancel(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    await state.clear()
    text, keyboard = await _home_view()
    await render_callback(call, text, reply_markup=keyboard)
    await call.answer("Отменено")


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
        back_callback="admin:master",
        back_text="⬅ Master",
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
        back_callback=f"admin:node:{node_id}",
        back_text="⬅ Нода",
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
        back_callback="admin:cheburcheck",
        back_text="⬅ Проверка блокировок",
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

    if not _consume_cooldown(message.from_user.id):
        await render_input(
            message,
            "🔎 Проверка блокировок\n\n⚠️ Слишком частые запросы. Повтори через пару секунд.",
            reply_markup=_cancel_keyboard(),
        )
        return

    raw = (message.text or "").strip()
    try:
        result = await client.check(raw)
    except CheburcheckError as exc:
        await render_input(
            message,
            f"🔎 Проверка блокировок\n\n⚠️ {exc}\n\nПопробуй другую цель.",
            reply_markup=_cancel_keyboard(),
        )
        return

    await state.clear()
    await render_input(
        message,
        result_text(result),
        reply_markup=_result_keyboard(),
    )
