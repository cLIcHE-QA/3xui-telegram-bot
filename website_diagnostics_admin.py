from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from admin_auth import authorize_callback, authorize_message
from admin_ui import render_callback, render_input
from config import load_settings
from db import Database
from website_diagnostics import (
    WebsiteDiagnosticsError,
    cms_summary,
    dns_summary,
    format_url_list,
    http_summary,
    pagespeed_summary,
    qr_png,
    seo_summary,
    sitemap_urls,
    whois_summary,
)
from website_monitoring import SafeOutboundHttpClient, WebsiteMonitoringError
from website_monitoring_runtime import repository


settings = load_settings()
db = Database(settings.db_path)
client = SafeOutboundHttpClient()
website_diagnostics_router = Router(name="website_diagnostics")


class WebsiteDiagnosticsStates(StatesGroup):
    value = State()


_ACTION_LABELS = {
    "whois": "🌐 WHOIS / возраст",
    "dns": "🧭 DNS",
    "http": "🩺 HTTP",
    "redirects": "↪️ Redirect trace",
    "cms": "🧩 CMS",
    "seo": "🔍 Индексация / robots",
    "pagespeed": "⚡ PageSpeed",
    "sitemap": "🗺 Sitemap",
    "urllist": "🧹 Список URL",
    "qr": "🔳 QR",
}


def diagnostics_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌐 WHOIS / возраст", callback_data="admin:webdiag:whois"),
            InlineKeyboardButton(text="🧭 DNS", callback_data="admin:webdiag:dns"),
        ],
        [
            InlineKeyboardButton(text="🩺 HTTP", callback_data="admin:webdiag:http"),
            InlineKeyboardButton(text="↪️ Redirects", callback_data="admin:webdiag:redirects"),
        ],
        [
            InlineKeyboardButton(text="🧩 CMS", callback_data="admin:webdiag:cms"),
            InlineKeyboardButton(text="🔍 SEO", callback_data="admin:webdiag:seo"),
        ],
        [
            InlineKeyboardButton(text="⚡ PageSpeed", callback_data="admin:webdiag:pagespeed"),
            InlineKeyboardButton(text="🗺 Sitemap", callback_data="admin:webdiag:sitemap"),
        ],
        [
            InlineKeyboardButton(text="🧹 Список URL", callback_data="admin:webdiag:urllist"),
            InlineKeyboardButton(text="🔳 QR", callback_data="admin:webdiag:qr"),
        ],
        [InlineKeyboardButton(text="⬅ Мониторинг сайтов", callback_data="admin:webmon")],
    ])


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✖ Отмена", callback_data="admin:webdiag:cancel")
    ]])


def _result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 Другая диагностика", callback_data="admin:webdiag")],
        [InlineKeyboardButton(text="⬅ Мониторинг сайтов", callback_data="admin:webmon")],
    ])


def site_diagnostics_keyboard(monitor_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🌐 WHOIS / возраст",
                callback_data=f"admin:webdiag:site:{monitor_id}:whois",
            ),
            InlineKeyboardButton(
                text="🧭 DNS",
                callback_data=f"admin:webdiag:site:{monitor_id}:dns",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🩺 HTTP",
                callback_data=f"admin:webdiag:site:{monitor_id}:http",
            ),
            InlineKeyboardButton(
                text="↪️ Redirects",
                callback_data=f"admin:webdiag:site:{monitor_id}:redirects",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🧩 CMS",
                callback_data=f"admin:webdiag:site:{monitor_id}:cms",
            ),
            InlineKeyboardButton(
                text="🔍 SEO",
                callback_data=f"admin:webdiag:site:{monitor_id}:seo",
            ),
        ],
        [
            InlineKeyboardButton(
                text="⚡ PageSpeed",
                callback_data=f"admin:webdiag:site:{monitor_id}:pagespeed",
            ),
            InlineKeyboardButton(
                text="🗺 Sitemap",
                callback_data=f"admin:webdiag:site:{monitor_id}:sitemap",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔳 QR",
                callback_data=f"admin:webdiag:site:{monitor_id}:qr",
            ),
        ],
        [
            InlineKeyboardButton(
                text="⬅ Сайт",
                callback_data=f"admin:webmon:site:{monitor_id}",
            )
        ],
    ])


def _site_result_keyboard(monitor_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🩺 Другой инструмент",
                callback_data=f"admin:webdiag:site:{monitor_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="⬅ Сайт",
                callback_data=f"admin:webmon:site:{monitor_id}",
            )
        ],
    ])


def _prompt(action: str) -> str:
    title = _ACTION_LABELS.get(action, "🔎 Диагностика")
    if action in {"whois", "dns"}:
        body = "Отправь публичное доменное имя, например example.org."
    elif action == "urllist":
        body = "Отправь список URL, по одному на строку. Некорректные строки будут отброшены."
    elif action == "qr":
        body = "Отправь текст или URL длиной до 2048 символов."
    else:
        body = "Отправь публичный HTTP(S) URL или домен, например example.org."
    return f"{title}\n\n{body}"


def _compact_lines(values: list[str], *, limit: int = 3200) -> str:
    selected: list[str] = []
    used = 0
    for value in values:
        clean = str(value).replace("\x00", "")[:800]
        extra = len(clean) + 1
        if selected and used + extra > limit:
            selected.append("…")
            break
        selected.append(clean)
        used += extra
    return "\n".join(selected)


async def _run(action: str, value: str) -> tuple[str, bytes | None]:
    if action == "whois":
        result = await whois_summary(value, client)
        lines = [
            "🌐 WHOIS / возраст",
            "",
            f"Домен: {result.domain}",
            f"Регистратор: {result.registrar or '—'}",
            f"Создан: {result.created_at or '—'}",
            f"Истекает: {result.expires_at or '—'}",
            f"Возраст: {str(result.age_days) + ' дн' if result.age_days is not None else '—'}",
        ]
        if result.statuses:
            lines.append("Статусы: " + ", ".join(result.statuses[:8]))
        return "\n".join(lines), None

    if action == "dns":
        records = await dns_summary(value)
        lines = ["🧭 DNS", ""]
        if not records:
            lines.append("⚪ Записей не найдено.")
        else:
            for item in records:
                lines.append(f"{item.record_type}: {item.value}")
        return _compact_lines(lines), None

    if action in {"http", "redirects"}:
        result = await http_summary(value, client)
        if action == "http":
            return "\n".join([
                "🩺 HTTP",
                "",
                f"Статус: {result.status}",
                f"Ответ: {result.latency_ms} мс",
                f"Final URL: {result.final_url}",
                f"Content-Type: {result.content_type or '—'}",
                f"Server: {result.server or '—'}",
                f"Redirects: {len(result.redirects)}",
            ]), None
        lines = ["↪️ Redirect trace", "", f"Старт: {result.requested_url}"]
        for index, target in enumerate(result.redirects, start=1):
            lines.append(f"{index}. {target}")
        lines.append(f"Финал: {result.final_url} · HTTP {result.status}")
        return _compact_lines(lines), None

    if action == "cms":
        http, cms = await cms_summary(value, client)
        return "\n".join([
            "🧩 CMS",
            "",
            f"CMS: {cms}",
            f"HTTP: {http.status}",
            f"Final URL: {http.final_url}",
        ]), None

    if action == "seo":
        result = await seo_summary(value, client)
        blocked = result.root_disallowed or result.meta_noindex or result.header_noindex
        return "\n".join([
            "🔍 Индексация / robots",
            "",
            f"Итог: {'🟡 есть ограничение индексации' if blocked else '🟢 явный noindex не обнаружен'}",
            f"robots.txt: {'🟢 доступен' if result.robots_txt_available else '⚪ не найден/недоступен'}",
            f"Disallow /: {'🔴 да' if result.root_disallowed else '🟢 нет'}",
            f"meta robots noindex: {'🔴 да' if result.meta_noindex else '🟢 нет'}",
            f"X-Robots-Tag noindex: {'🔴 да' if result.header_noindex else '🟢 нет'}",
        ]), None

    if action == "pagespeed":
        result = await pagespeed_summary(
            value,
            client,
            api_key=settings.pagespeed_api_key,
        )
        if not result.enabled:
            return (
                "⚡ PageSpeed\n\n⚪ Не настроен. "
                "Добавь PAGESPEED_API_KEY локально на Master, если эта диагностика нужна.",
                None,
            )
        return "\n".join([
            "⚡ PageSpeed",
            "",
            f"Performance: {str(result.performance_score) + '/100' if result.performance_score is not None else '—'}",
            f"Field category: {result.category or '—'}",
        ]), None

    if action == "sitemap":
        values = await sitemap_urls(value, client)
        lines = ["🗺 Sitemap", "", f"URL найдено: {len(values)}"]
        lines.extend(values[:60])
        if len(values) > 60:
            lines.append(f"… ещё {len(values) - 60}")
        return _compact_lines(lines), None

    if action == "urllist":
        values = format_url_list(value)
        lines = ["🧹 Список URL", "", f"Корректных уникальных URL: {len(values)}"]
        lines.extend(values[:80])
        if len(values) > 80:
            lines.append(f"… ещё {len(values) - 80}")
        return _compact_lines(lines), None

    if action == "qr":
        data = qr_png(value)
        return "🔳 QR\n\nГотово. QR отправлен отдельным изображением.", data

    raise WebsiteDiagnosticsError("Неизвестная диагностика.", code="unknown_action")


@website_diagnostics_router.callback_query(
    F.data.regexp(r"^admin:webdiag:site:\d+$")
)
async def diagnostics_site_home(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call)
    if not ok:
        return
    monitor_id = int((call.data or "").rsplit(":", 1)[-1])
    if not await repository.is_watcher(monitor_id, call.from_user.id):
        await call.answer("Сайт не найден в твоих подписках.", show_alert=True)
        return
    item = await repository.get_monitor(monitor_id)
    if item is None:
        await call.answer("Сайт не найден.", show_alert=True)
        return
    await state.clear()
    await render_callback(
        call,
        f"🩺 Диагностика · {item.hostname}\n\n"
        "Выбери read-only проверку. Target берётся из карточки сайта "
        "и не хранится в callback data.",
        reply_markup=site_diagnostics_keyboard(item.id),
        disable_web_page_preview=True,
    )
    await call.answer()


@website_diagnostics_router.callback_query(
    F.data.regexp(
        r"^admin:webdiag:site:\d+:(whois|dns|http|redirects|cms|seo|pagespeed|sitemap|qr)$"
    )
)
async def diagnostics_site_run(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call)
    if not ok:
        return
    parts = (call.data or "").split(":")
    monitor_id = int(parts[3])
    action = parts[4]
    if not await repository.is_watcher(monitor_id, call.from_user.id):
        await call.answer("Сайт не найден в твоих подписках.", show_alert=True)
        return
    item = await repository.get_monitor(monitor_id)
    if item is None:
        await call.answer("Сайт не найден.", show_alert=True)
        return

    await state.clear()
    await call.answer("Проверяю…")
    try:
        text, image = await _run(action, item.canonical_url)
    except (WebsiteDiagnosticsError, WebsiteMonitoringError) as exc:
        await render_callback(
            call,
            f"{_ACTION_LABELS.get(action, '🩺 Диагностика')}\n\n🔴 {str(exc)}",
            reply_markup=_site_result_keyboard(item.id),
            disable_web_page_preview=True,
        )
        return
    except Exception:
        await render_callback(
            call,
            f"{_ACTION_LABELS.get(action, '🩺 Диагностика')}\n\n"
            "🔴 Диагностика временно недоступна.",
            reply_markup=_site_result_keyboard(item.id),
            disable_web_page_preview=True,
        )
        return

    if image is not None and call.message is not None:
        try:
            await call.bot.send_photo(
                call.message.chat.id,
                BufferedInputFile(image, filename="qr.png"),
                caption=f"🔳 QR · {item.hostname}",
            )
        except Exception:
            text = "🔳 QR\n\n🔴 Не удалось отправить изображение."

    await render_callback(
        call,
        text,
        reply_markup=_site_result_keyboard(item.id),
        disable_web_page_preview=True,
    )


@website_diagnostics_router.callback_query(F.data == "admin:webdiag")
async def diagnostics_home(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call)
    if not ok:
        return
    await state.clear()
    await render_callback(
        call,
        "🔎 Разовая диагностика\n\n"
        "Проверки не создают persistent monitor target. "
        "HTTP(S) обращения используют общий SSRF-safe outbound boundary.",
        reply_markup=diagnostics_keyboard(),
    )
    await call.answer()


@website_diagnostics_router.callback_query(
    F.data.regexp(r"^admin:webdiag:(whois|dns|http|redirects|cms|seo|pagespeed|sitemap|urllist|qr)$")
)
async def diagnostics_start(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call)
    if not ok:
        return
    action = (call.data or "").rsplit(":", 1)[-1]
    await state.clear()
    await state.set_state(WebsiteDiagnosticsStates.value)
    await state.update_data(webdiag_action=action)
    await render_callback(call, _prompt(action), reply_markup=_cancel_keyboard())
    await call.answer()


@website_diagnostics_router.callback_query(F.data == "admin:webdiag:cancel")
async def diagnostics_cancel(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call)
    if not ok:
        return
    await state.clear()
    await render_callback(
        call,
        "🔎 Разовая диагностика\n\nВыбери инструмент:",
        reply_markup=diagnostics_keyboard(),
    )
    await call.answer("Отменено")


@website_diagnostics_router.message(WebsiteDiagnosticsStates.value)
async def diagnostics_value(message: Message, state: FSMContext):
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
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅ Мониторинг сайтов", callback_data="admin:webmon")
            ]]),
        )
        return

    data = await state.get_data()
    action = str(data.get("webdiag_action") or "")
    value = message.text or ""
    try:
        text, image = await _run(action, value)
    except (WebsiteDiagnosticsError, WebsiteMonitoringError) as exc:
        await render_input(
            message,
            f"{_ACTION_LABELS.get(action, '🔎 Диагностика')}\n\n🔴 {str(exc)}",
            reply_markup=_cancel_keyboard(),
        )
        return
    except Exception:
        await render_input(
            message,
            f"{_ACTION_LABELS.get(action, '🔎 Диагностика')}\n\n🔴 Диагностика временно недоступна.",
            reply_markup=_cancel_keyboard(),
        )
        return

    await state.clear()
    if image is not None:
        try:
            await message.bot.send_photo(
                message.chat.id,
                BufferedInputFile(image, filename="qr.png"),
                caption="🔳 QR",
            )
        except Exception:
            text = "🔳 QR\n\n🔴 Не удалось отправить изображение."
    await render_input(
        message,
        text,
        reply_markup=_result_keyboard(),
        disable_web_page_preview=True,
    )
