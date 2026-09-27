from __future__ import annotations

import time

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_auth import authorize_callback, authorize_message
from admin_ui import render_callback, render_input
from cheburcheck import CheburcheckClient, CheburcheckError, CheburcheckResult
from config import load_settings
from db import Database


settings = load_settings()
db = Database(settings.db_path)
client = CheburcheckClient(
    settings.cheburcheck_url,
    verify_tls=settings.cheburcheck_verify_tls,
)
cheburcheck_router = Router(name="cheburcheck_admin")
_MIN_REQUEST_INTERVAL_SECONDS = 2.0
_last_request_at: dict[int, float] = {}


class CheburcheckStates(StatesGroup):
    target = State()


def _home_keyboard() -> InlineKeyboardMarkup:
    rows = []
    if client.enabled:
        rows.append([
            InlineKeyboardButton(
                text="🔎 Проверить цель",
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


def _result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔎 Проверить ещё",
                callback_data="admin:cheburcheck:start",
            )
        ],
        [
            InlineKeyboardButton(
                text="⬅ Мониторинг",
                callback_data="admin:section:monitoring",
            )
        ],
    ])


def _home_text() -> str:
    status = "🟢 настроен" if client.enabled else "⚪ не настроен"
    detail = (
        "Сервис включён. Доступность проверяется при каждом запросе."
        if client.enabled else
        "Укажи CHEBURCHECK_URL в локальной конфигурации, чтобы включить диагностику."
    )
    return (
        "🔎 Проверка блокировок\n\n"
        "Read-only диагностика домена, публичного IP, подсети или ASN через Cheburcheck.\n"
        "Функция не меняет VPN-конфигурацию и не выполняет provisioning.\n\n"
        f"Сервис: {status}\n"
        f"{detail}"
    )


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


@cheburcheck_router.callback_query(F.data == "admin:cheburcheck")
async def cheburcheck_home(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    await state.clear()
    await render_callback(call, _home_text(), reply_markup=_home_keyboard())
    await call.answer()


@cheburcheck_router.callback_query(F.data == "admin:cheburcheck:start")
async def cheburcheck_start(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="read_only")
    if not ok:
        return
    if not client.enabled:
        await call.answer("Cheburcheck не настроен", show_alert=True)
        await render_callback(call, _home_text(), reply_markup=_home_keyboard())
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
    await render_callback(call, _home_text(), reply_markup=_home_keyboard())
    await call.answer("Отменено")


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
        await render_input(
            message,
            "Недостаточно прав.",
            reply_markup=_home_keyboard(),
        )
        return

    actor_id = int(message.from_user.id)
    now = time.monotonic()
    previous = _last_request_at.get(actor_id, 0.0)
    if now - previous < _MIN_REQUEST_INTERVAL_SECONDS:
        await render_input(
            message,
            "🔎 Проверка блокировок\n\n⚠️ Слишком частые запросы. Повтори через пару секунд.",
            reply_markup=_cancel_keyboard(),
        )
        return
    _last_request_at[actor_id] = now

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
