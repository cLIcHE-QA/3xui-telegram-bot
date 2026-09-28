from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_auth import authorize_callback, authorize_message
from admin_privileges import ROLE_RANK
from admin_ui import render_callback, render_input
from audit import audit_from_call, audit_from_message
from config import load_settings
from db import Database
from website_monitoring import (
    WebsiteMonitorRecord,
    WebsiteMonitoringError,
    validate_public_url_resolution,
)
from website_monitoring_runtime import (
    process_monitor_execution,
    repository,
    service,
)


settings = load_settings()
db = Database(settings.db_path)
website_monitoring_router = Router(name="website_monitoring")
MSK = timezone(timedelta(hours=3))


class WebsiteMonitoringStates(StatesGroup):
    add_url = State()


def _role_at_least(role: str | None, minimum: str) -> bool:
    return ROLE_RANK.get(role or "", 0) >= ROLE_RANK[minimum]


def _status_text(item: WebsiteMonitorRecord) -> str:
    if not item.enabled:
        return "⏸ приостановлен"
    return {
        "up": "🟢 доступен",
        "down": "🔴 недоступен",
        "suspect": "🟡 перепроверка",
        "unknown": "⚪ не проверен",
    }.get(item.state, "⚪ неизвестно")


def _relative_time(timestamp: int) -> str:
    value = int(timestamp or 0)
    if value <= 0:
        return "ещё не проверялся"
    delta = max(0, int(datetime.now(timezone.utc).timestamp()) - value)
    if delta < 60:
        return f"{delta} сек назад"
    if delta < 3600:
        return f"{delta // 60} мин назад"
    if delta < 86400:
        return f"{delta // 3600} ч назад"
    return f"{delta // 86400} дн назад"


def _home_keyboard(role: str | None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="📋 Сайты", callback_data="admin:webmon:list")],
    ]
    if _role_at_least(role, "support"):
        rows.append([
            InlineKeyboardButton(text="➕ Добавить сайт", callback_data="admin:webmon:add")
        ])
    rows.append([
        InlineKeyboardButton(text="⬅ Мониторинг", callback_data="admin:section:monitoring")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _list_keyboard(
    sites: list[WebsiteMonitorRecord],
    role: str | None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in sites[:30]:
        icon = {
            "up": "🟢",
            "down": "🔴",
            "suspect": "🟡",
            "unknown": "⚪",
        }.get(item.state, "⚪")
        if not item.enabled:
            icon = "⏸"
        label = item.hostname
        if len(label) > 42:
            label = label[:39] + "…"
        rows.append([
            InlineKeyboardButton(
                text=f"{icon} {label}",
                callback_data=f"admin:webmon:site:{item.id}",
            )
        ])
    if _role_at_least(role, "support"):
        rows.append([
            InlineKeyboardButton(text="➕ Добавить сайт", callback_data="admin:webmon:add")
        ])
    rows.append([
        InlineKeyboardButton(text="⬅ Мониторинг сайтов", callback_data="admin:webmon")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _site_keyboard(
    item: WebsiteMonitorRecord,
    *,
    role: str | None,
    notifications_enabled: bool,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if _role_at_least(role, "support"):
        rows.append([
            InlineKeyboardButton(
                text="🔄 Проверить сейчас",
                callback_data=f"admin:webmon:check:{item.id}",
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text="📜 История инцидентов",
            callback_data=f"admin:webmon:incidents:{item.id}",
        )
    ])
    if _role_at_least(role, "support"):
        rows.append([
            InlineKeyboardButton(
                text=("🔕 Выключить оповещения" if notifications_enabled else "🔔 Включить оповещения"),
                callback_data=f"admin:webmon:alerts:{item.id}",
            )
        ])
        rows.append([
            InlineKeyboardButton(
                text="🗑 Удалить / отписаться",
                callback_data=f"admin:webmon:removeask:{item.id}",
            )
        ])
    rows.append([
        InlineKeyboardButton(text="⬅ Сайты", callback_data="admin:webmon:list")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _add_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✖ Отмена", callback_data="admin:webmon:add:cancel")
    ]])


async def _owned_monitor(
    monitor_id: int,
    telegram_id: int,
) -> WebsiteMonitorRecord | None:
    if not await repository.is_watcher(monitor_id, telegram_id):
        return None
    return await repository.get_monitor(monitor_id)


async def _render_home(call: CallbackQuery, role: str | None) -> None:
    sites = await repository.list_for_watcher(call.from_user.id)
    counts = {"up": 0, "down": 0, "unknown": 0}
    for item in sites:
        if item.state == "up":
            counts["up"] += 1
        elif item.state == "down":
            counts["down"] += 1
        else:
            counts["unknown"] += 1
    text = (
        "🌐 Мониторинг сайтов\n\n"
        f"Сайтов: {len(sites)}\n"
        f"🟢 Доступны: {counts['up']}\n"
        f"🔴 Недоступны: {counts['down']}\n"
        f"⚪ Не проверены/перепроверка: {counts['unknown']}\n\n"
        "Периодические проверки используют безопасный outbound HTTP-контур "
        "и подтверждают подозрительный failure повторной проверкой."
    )
    await render_callback(call, text, reply_markup=_home_keyboard(role))


async def _render_site(
    call: CallbackQuery,
    item: WebsiteMonitorRecord,
    role: str | None,
) -> None:
    enabled = await repository.notifications_enabled(item.id, call.from_user.id)
    http = str(item.last_http_status) if item.last_http_status else "—"
    latency = f"{item.last_latency_ms} мс" if item.last_latency_ms else "—"
    error = item.last_error_kind or "—"
    text = (
        f"🌐 {item.hostname}\n\n"
        f"URL: {item.canonical_url}\n"
        f"Статус: {_status_text(item)}\n"
        f"HTTP: {http}\n"
        f"Ответ: {latency}\n"
        f"Последняя проверка: {_relative_time(item.last_check_at)}\n"
        f"Ошибка: {error}\n"
        f"Оповещения: {'🔔 включены' if enabled else '🔕 выключены'}"
    )
    await render_callback(
        call,
        text,
        reply_markup=_site_keyboard(
            item,
            role=role,
            notifications_enabled=enabled,
        ),
        disable_web_page_preview=True,
    )


@website_monitoring_router.callback_query(F.data == "admin:webmon")
async def website_monitoring_home(call: CallbackQuery, state: FSMContext):
    ok, role = await authorize_callback(db, settings, call)
    if not ok:
        return
    await state.clear()
    await _render_home(call, role)
    await call.answer()


@website_monitoring_router.callback_query(F.data == "admin:webmon:list")
async def website_monitoring_list(call: CallbackQuery, state: FSMContext):
    ok, role = await authorize_callback(db, settings, call)
    if not ok:
        return
    await state.clear()
    sites = await repository.list_for_watcher(call.from_user.id)
    text = "📋 Сайты\n\n"
    if sites:
        text += f"Подписок: {len(sites)}. Выбери сайт:"
    else:
        text += "Сайтов пока нет."
    await render_callback(call, text, reply_markup=_list_keyboard(sites, role))
    await call.answer()


@website_monitoring_router.callback_query(F.data == "admin:webmon:add")
async def website_monitoring_add(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call)
    if not ok:
        return
    await state.clear()
    await state.set_state(WebsiteMonitoringStates.add_url)
    await render_callback(
        call,
        "➕ Добавить сайт\n\n"
        "Отправь публичный домен или HTTP(S) URL.\n"
        "Private/local addresses, credentials в URL и нестандартные порты запрещены.\n\n"
        "Пример: example.org",
        reply_markup=_add_cancel(),
    )
    await call.answer()


@website_monitoring_router.callback_query(F.data == "admin:webmon:add:cancel")
async def website_monitoring_add_cancel(call: CallbackQuery, state: FSMContext):
    ok, role = await authorize_callback(db, settings, call)
    if not ok:
        return
    await state.clear()
    await _render_home(call, role)
    await call.answer("Отменено")


@website_monitoring_router.message(WebsiteMonitoringStates.add_url)
async def website_monitoring_add_url(message: Message, state: FSMContext):
    if not message.from_user:
        return
    ok, _ = await authorize_message(
        db,
        settings,
        message.from_user.id,
        minimum="support",
    )
    if not ok:
        await state.clear()
        await render_input(message, "Недостаточно прав.")
        return

    raw = (message.text or "").strip()
    try:
        canonical = await validate_public_url_resolution(raw)
        item = await repository.add_watcher(canonical, message.from_user.id)
    except WebsiteMonitoringError as exc:
        await render_input(
            message,
            f"➕ Добавить сайт\n\n🔴 {str(exc)}",
            reply_markup=_add_cancel(),
        )
        return
    except Exception:
        await render_input(
            message,
            "➕ Добавить сайт\n\n🔴 Не удалось подтвердить публичный DNS target.",
            reply_markup=_add_cancel(),
        )
        return

    await audit_from_message(
        db,
        message,
        "website_monitor.subscribe",
        target_type="website_monitor",
        target_id=item.id,
        details=f"host={item.hostname}",
    )
    await state.clear()

    try:
        execution = await service.check_monitor(item.id)
        await process_monitor_execution(message.bot, execution)
    except Exception:
        # The subscription is valid even when the first network check is
        # temporarily unavailable; scheduler will retry from persistent state.
        pass

    current = await repository.get_monitor(item.id)
    if current is None:
        await render_input(message, "Сайт добавлен, но карточка временно недоступна.")
        return

    enabled = await repository.notifications_enabled(current.id, message.from_user.id)
    text = (
        f"🌐 {current.hostname}\n\n"
        f"URL: {current.canonical_url}\n"
        f"Статус: {_status_text(current)}\n"
        f"HTTP: {current.last_http_status or '—'}\n"
        f"Ответ: {f'{current.last_latency_ms} мс' if current.last_latency_ms else '—'}\n"
        f"Последняя проверка: {_relative_time(current.last_check_at)}\n"
        f"Оповещения: {'🔔 включены' if enabled else '🔕 выключены'}"
    )
    await render_input(
        message,
        text,
        reply_markup=_site_keyboard(
            current,
            role="support",
            notifications_enabled=enabled,
        ),
        disable_web_page_preview=True,
    )


@website_monitoring_router.callback_query(F.data.regexp(r"^admin:webmon:site:\d+$"))
async def website_monitoring_site(call: CallbackQuery):
    ok, role = await authorize_callback(db, settings, call)
    if not ok:
        return
    monitor_id = int((call.data or "").rsplit(":", 1)[-1])
    item = await _owned_monitor(monitor_id, call.from_user.id)
    if item is None:
        await call.answer("Сайт не найден в твоих подписках.", show_alert=True)
        return
    await _render_site(call, item, role)
    await call.answer()


@website_monitoring_router.callback_query(F.data.regexp(r"^admin:webmon:check:\d+$"))
async def website_monitoring_check(call: CallbackQuery):
    ok, role = await authorize_callback(db, settings, call)
    if not ok:
        return
    monitor_id = int((call.data or "").rsplit(":", 1)[-1])
    item = await _owned_monitor(monitor_id, call.from_user.id)
    if item is None:
        await call.answer("Сайт не найден в твоих подписках.", show_alert=True)
        return

    await call.answer("Проверяю…")
    try:
        execution = await service.check_monitor(item.id)
        await process_monitor_execution(call.bot, execution)
    except WebsiteMonitoringError as exc:
        await call.answer(str(exc)[:180], show_alert=True)
        return
    except Exception:
        await call.answer("Проверка временно недоступна.", show_alert=True)
        return

    await audit_from_call(
        db,
        call,
        "website_monitor.check",
        target_type="website_monitor",
        target_id=item.id,
        details=f"state={execution.final_state}; error={execution.outcome.error_kind}",
        success=execution.outcome.kind != "checker_error",
    )
    current = await repository.get_monitor(item.id)
    if current:
        await _render_site(call, current, role)


@website_monitoring_router.callback_query(F.data.regexp(r"^admin:webmon:alerts:\d+$"))
async def website_monitoring_toggle_alerts(call: CallbackQuery):
    ok, role = await authorize_callback(db, settings, call)
    if not ok:
        return
    monitor_id = int((call.data or "").rsplit(":", 1)[-1])
    item = await _owned_monitor(monitor_id, call.from_user.id)
    if item is None:
        await call.answer("Сайт не найден в твоих подписках.", show_alert=True)
        return
    current = await repository.notifications_enabled(item.id, call.from_user.id)
    await repository.set_notifications_enabled(item.id, call.from_user.id, not current)
    await audit_from_call(
        db,
        call,
        "website_monitor.notifications",
        target_type="website_monitor",
        target_id=item.id,
        details=f"enabled={not current}",
    )
    await call.answer("Оповещения изменены")
    refreshed = await repository.get_monitor(item.id)
    if refreshed:
        await _render_site(call, refreshed, role)


@website_monitoring_router.callback_query(F.data.regexp(r"^admin:webmon:incidents:\d+$"))
async def website_monitoring_incidents(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call)
    if not ok:
        return
    monitor_id = int((call.data or "").rsplit(":", 1)[-1])
    item = await _owned_monitor(monitor_id, call.from_user.id)
    if item is None:
        await call.answer("Сайт не найден в твоих подписках.", show_alert=True)
        return
    incidents = await repository.list_incidents(item.id, limit=10)
    lines = [f"📜 Инциденты · {item.hostname}", ""]
    if not incidents:
        lines.append("Инцидентов ещё нет.")
    for incident in incidents:
        opened = datetime.fromtimestamp(incident.opened_at, MSK).strftime("%d.%m.%Y %H:%M")
        if incident.resolved_at:
            resolved = datetime.fromtimestamp(incident.resolved_at, MSK).strftime("%d.%m.%Y %H:%M")
            status = f"✅ {opened} → {resolved} MSK"
        else:
            status = f"🔴 открыт {opened} MSK"
        reason = incident.reason_kind or "unknown"
        if incident.last_http_status:
            reason += f" · HTTP {incident.last_http_status}"
        lines.append(f"{status}\nПричина: {reason}")
    await render_callback(
        call,
        "\n\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="⬅ Сайт",
                callback_data=f"admin:webmon:site:{item.id}",
            )
        ]]),
    )
    await call.answer()


@website_monitoring_router.callback_query(F.data.regexp(r"^admin:webmon:removeask:\d+$"))
async def website_monitoring_remove_ask(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call)
    if not ok:
        return
    monitor_id = int((call.data or "").rsplit(":", 1)[-1])
    item = await _owned_monitor(monitor_id, call.from_user.id)
    if item is None:
        await call.answer("Сайт не найден в твоих подписках.", show_alert=True)
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⚠️ Да, отписаться",
            callback_data=f"admin:webmon:remove:{item.id}",
        )],
        [InlineKeyboardButton(
            text="✖ Отмена",
            callback_data=f"admin:webmon:site:{item.id}",
        )],
    ])
    await render_callback(
        call,
        f"🗑 Удалить / отписаться\n\nСайт: {item.canonical_url}\n\n"
        "Будет удалена только твоя подписка. Если других watchers нет, "
        "orphan target и его локальная incident history будут очищены.",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )
    await call.answer()


@website_monitoring_router.callback_query(F.data.regexp(r"^admin:webmon:remove:\d+$"))
async def website_monitoring_remove(call: CallbackQuery):
    ok, role = await authorize_callback(db, settings, call)
    if not ok:
        return
    monitor_id = int((call.data or "").rsplit(":", 1)[-1])
    item = await _owned_monitor(monitor_id, call.from_user.id)
    if item is None:
        await call.answer("Сайт уже удалён из твоих подписок.", show_alert=True)
        return
    removed = await repository.remove_watcher(item.id, call.from_user.id)
    if removed:
        await audit_from_call(
            db,
            call,
            "website_monitor.unsubscribe",
            target_type="website_monitor",
            target_id=item.id,
            details=f"host={item.hostname}",
        )
    await call.answer("Подписка удалена")
    await _render_home(call, role)
