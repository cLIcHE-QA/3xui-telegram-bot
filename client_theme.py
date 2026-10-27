"""Bounded Client Portal decoration; labels, routes and statuses stay authoritative."""
from __future__ import annotations

import asyncio
import contextvars
import json
import re
import time
from dataclasses import dataclass
from types import MappingProxyType

import aiosqlite
from aiogram import BaseMiddleware
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import EditMessageText, SendMessage
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, MessageEntity


SETTING_KEY = "client_theme:v1"
MAX_REVISION = 2_147_483_646
MAX_BYTES = 8192


@dataclass(frozen=True)
class ThemeSlot:
    label: str
    fallback: str


SLOTS = MappingProxyType({
    "portal.menu.profile": ThemeSlot("Профиль", "👤"),
    "portal.menu.subscription": ThemeSlot("Моя подписка", "🌐"),
    "portal.menu.buy": ThemeSlot("Купить / продлить", "💳"),
    "portal.menu.traffic": ThemeSlot("Трафик", "📊"),
    "portal.menu.devices": ThemeSlot("Устройства", "📱"),
    "portal.menu.help": ThemeSlot("Помощь", "🆘"),
    "portal.menu.history": ThemeSlot("История заказов и платежей", "📜"),
    "portal.action.connect": ThemeSlot("Подключение", "📱"),
    "portal.action.link": ThemeSlot("Копирование ссылки", "📋"),
    "portal.action.qr": ThemeSlot("QR", "🔳"),
    "portal.action.open": ThemeSlot("Открытие VPN-клиента", "🚀"),
    "portal.action.import": ThemeSlot("Импорт", "🔗"),
    "portal.action.check": ThemeSlot("Диагностика", "🛠"),
    "portal.action.refresh": ThemeSlot("Обновление", "🔄"),
    "portal.nav.back": ThemeSlot("Назад", "⬅"),
    "portal.nav.next": ThemeSlot("Следующая страница", "➡"),
    "portal.profile.heading": ThemeSlot("Заголовок профиля", "👤"),
    "portal.subscription.heading": ThemeSlot("Заголовок подписки", "🌐"),
    "portal.subscription.link": ThemeSlot("Маркер ссылки подписки", "🔗"),
    "portal.traffic.heading": ThemeSlot("Заголовок трафика", "📊"),
    "portal.devices.heading": ThemeSlot("Заголовок устройств", "📱"),
    "portal.device.details": ThemeSlot("Заголовок устройства", "📱"),
    "portal.connect.heading": ThemeSlot("Заголовок подключения", "📱"),
    "portal.help.heading": ThemeSlot("Заголовок помощи", "🆘"),
    "portal.history.heading": ThemeSlot("Заголовок истории", "📜"),
})


class ThemeUnavailable(RuntimeError):
    pass


class ThemeConflict(ThemeUnavailable):
    pass


class ThemeTransportUnavailable(RuntimeError):
    """A decorated request must never reach the generic edit-to-send fallback."""


def emoji_id(value):
    if (not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,19}", value)
            or int(value) > 2**64 - 1):
        raise ValueError("Invalid custom emoji identifier")
    return value


@dataclass(frozen=True)
class ThemeSnapshot:
    revision: int = 0
    enabled: bool = False
    icons: tuple[tuple[str, str], ...] = ()

    def icon(self, slot):
        return dict(self.icons).get(slot) if self.enabled and slot in SLOTS else None


def decode_theme(raw):
    if raw is None:
        return ThemeSnapshot()
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Invalid theme storage")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate theme field")
            result[key] = value
        return result
    obj = json.loads(raw, object_pairs_hook=unique)
    if (not isinstance(obj, dict) or set(obj) != {"version", "revision", "enabled", "icons"}
            or type(obj["version"]) is not int or obj["version"] != 1
            or type(obj["revision"]) is not int or not 0 <= obj["revision"] <= MAX_REVISION
            or type(obj["enabled"]) is not bool or not isinstance(obj["icons"], dict)
            or not set(obj["icons"]).issubset(SLOTS)):
        raise ValueError("Invalid theme storage")
    icons = tuple(sorted((key, emoji_id(value)) for key, value in obj["icons"].items()))
    return ThemeSnapshot(obj["revision"], obj["enabled"], icons)


def encode_theme(snapshot):
    return json.dumps({"version": 1, "revision": snapshot.revision,
                       "enabled": snapshot.enabled, "icons": dict(snapshot.icons)},
                      separators=(",", ":"), ensure_ascii=True)


class ClientThemeService:
    def __init__(self, db, settings):
        self.db, self.settings = db, settings
        self.blocked = False

    def permitted(self, bot_id):
        # An operator attestation bound to this bot, never inferred from RBAC/Premium.
        return (not self.blocked
                and getattr(self.settings, "client_custom_emoji_enabled", False) is True
                and type(bot_id) is int and bot_id > 0
                and type(getattr(self.settings, "client_custom_emoji_verified_bot_id", 0)) is int
                and getattr(self.settings, "client_custom_emoji_verified_bot_id", 0) == bot_id)

    async def read(self):
        try:
            return decode_theme(await self.db.get_runtime_setting(SETTING_KEY))
        except Exception:
            raise ThemeUnavailable("Theme storage unavailable") from None

    async def snapshot(self, bot_id):
        if not self.permitted(bot_id):
            return ThemeSnapshot()
        try:
            return await self.read()
        except ThemeUnavailable:
            return ThemeSnapshot()

    async def change(self, actor, revision, action, *, slot=None, value=None, bot_id=0):
        if type(actor) is not int or actor <= 0 or type(revision) is not int or not 0 <= revision < MAX_REVISION:
            raise ThemeUnavailable("Invalid theme actor/revision")
        if action not in {"set", "reset", "reset_all", "enable", "disable"}:
            raise ThemeUnavailable("Invalid theme action")
        if action in {"set", "reset"} and slot not in SLOTS:
            raise ThemeUnavailable("Invalid theme slot")
        if action == "set":
            value = emoji_id(value)
        if action == "enable" and not self.permitted(bot_id):
            raise ThemeUnavailable("Custom emoji activation not permitted")
        try:
            async with aiosqlite.connect(self.db.path, timeout=3) as conn:
                await conn.execute("BEGIN IMMEDIATE")
                if actor not in self.settings.admin_telegram_ids:
                    cur = await conn.execute("SELECT role, enabled FROM administrators WHERE telegram_id=?", (actor,))
                    role = await cur.fetchone()
                    if not role or role[0] != "owner" or role[1] != 1:
                        raise ThemeUnavailable("Owner required")
                cur = await conn.execute("SELECT value FROM runtime_settings WHERE key=?", (SETTING_KEY,))
                row = await cur.fetchone()
                current = decode_theme(row[0] if row else None)
                if current.revision != revision:
                    raise ThemeConflict("Stale theme revision")
                icons, enabled = dict(current.icons), current.enabled
                if action == "set": icons[slot] = value
                elif action == "reset": icons.pop(slot, None)
                elif action == "reset_all": icons, enabled = {}, False
                else: enabled = action == "enable"
                result = ThemeSnapshot(revision + 1, enabled, tuple(sorted(icons.items())))
                now = int(time.time())
                await conn.execute(
                    "INSERT INTO runtime_settings(key,value,updated_by,updated_at) VALUES(?,?,?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_by=excluded.updated_by,updated_at=excluded.updated_at",
                    (SETTING_KEY, encode_theme(result), actor, now))
                await conn.execute(
                    "INSERT INTO audit_log(actor_id,actor_username,action,target_type,target_id,details,success,created_at) "
                    "VALUES(?, '', 'client.theme.change','setting',?,?,1,?)",
                    (actor, SETTING_KEY, f"action={action};slot={slot or '-'};revision={revision + 1}", now))
                await conn.commit()
                return result
        except (ThemeConflict, ThemeUnavailable):
            raise
        except Exception:
            raise ThemeUnavailable("Theme write outcome unconfirmed; read state") from None


@dataclass
class _ThemeScope:
    actor: int
    theme: ThemeSnapshot
    device_detail: bool = False
    active: bool = True


_CURRENT = contextvars.ContextVar("client_theme", default=None)


def _button_slot(button):
    text, callback = button.text, button.callback_data or ""
    if callback and not callback.startswith("client:"):
        return None
    if callback.startswith(("client:device-delete:", "client:terms:")):
        return None  # Destructive/payment confirmations are never decoration slots.
    if text.startswith("⬅ "): return "portal.nav.back"
    if text.startswith("➡ "): return "portal.nav.next"
    exact = {"👤 Профиль": "profile", "🌐 Моя подписка": "subscription",
             "💳 Купить / продлить": "buy", "📊 Трафик": "traffic",
             "📱 Устройства": "devices", "🆘 Помощь": "help",
             "📜 История заказов и платежей": "history"}
    if text in exact and callback:
        return "portal.menu." + exact[text]
    for prefix, key in (("📱 Подключить", "connect"), ("📱 Как подключиться", "connect"),
                        ("📋 Скопировать", "link"), ("🔳 QR", "qr"),
                        ("🚀 Открыть в ", "open"), ("🔗 ", "import"),
                        ("🛠 Проверить", "check"), ("🔄 ", "refresh")):
        if text.startswith(prefix) and (callback or button.copy_text or button.url):
            return "portal.action." + key
    return None


def decorate_markup(markup, theme):
    if not isinstance(markup, InlineKeyboardMarkup) or not theme.enabled:
        return markup
    rows = []
    for row in markup.inline_keyboard:
        buttons = []
        for button in row:
            identifier = theme.icon(_button_slot(button))
            # Keep the entire canonical text, including its Unicode fallback.
            buttons.append(button.model_copy(update={"icon_custom_emoji_id": identifier}) if identifier else button)
        rows.append(buttons)
    return markup.model_copy(update={"inline_keyboard": rows})


_HEADINGS = (("👤 Профиль", "portal.profile.heading"), ("🌐 Моя подписка", "portal.subscription.heading"),
             ("📊 Трафик", "portal.traffic.heading"), ("📱 Устройства", "portal.devices.heading"),
             ("📱 Устройство", "portal.device.details"), ("📱 Как подключиться", "portal.connect.heading"),
             ("🆘 Помощь", "portal.help.heading"), ("📜 История", "portal.history.heading"))


def decorate_text(text, theme, *, device_detail=False):
    if not isinstance(text, str):
        return []
    try:
        units = len(text.encode("utf-16-le")) // 2
    except UnicodeError:
        return []
    if units > 4096:
        return []
    entities = []
    for prefix, slot in _HEADINGS:
        identifier = theme.icon(slot)
        if identifier and (text == prefix or text.startswith(prefix + "\n")
                           or (slot in {"portal.history.heading", "portal.devices.heading"}
                               and text.startswith(prefix + " · "))):
            entities.append(MessageEntity(type="custom_emoji", offset=0,
                                          length=len(SLOTS[slot].fallback.encode("utf-16-le")) // 2,
                                          custom_emoji_id=identifier))
            break
    if not entities and device_detail and theme.icon("portal.device.details"):
        match = re.match(r"^(📱|💻|🖥️?|🔹) ", text)
        if match:
            entities.append(MessageEntity(type="custom_emoji", offset=0,
                                          length=len(match.group(1).encode("utf-16-le")) // 2,
                                          custom_emoji_id=theme.icon("portal.device.details")))
    # Only the fixed server-side link marker, never URL text/entities from settings.
    marker = "\n🔗 Subscription URL:\n"
    pos = text.find(marker)
    identifier = theme.icon("portal.subscription.link")
    if pos >= 0 and identifier:
        offset = len(text[:pos + 1].encode("utf-16-le")) // 2
        entities.append(MessageEntity(type="custom_emoji", offset=offset, length=2, custom_emoji_id=identifier))
    return entities


def decorate_method(method, theme, bot, *, device_detail=False):
    if (not theme.enabled or not isinstance(method, (SendMessage, EditMessageText))
            or method.entities or bot.default.parse_mode is not None
            or (isinstance(method.parse_mode, str) and method.parse_mode)):
        return None
    entities = decorate_text(method.text, theme, device_detail=device_detail)
    markup = decorate_markup(method.reply_markup, theme)
    if not entities and markup == method.reply_markup:
        return None
    return method.model_copy(update={"entities": entities or None, "parse_mode": None, "reply_markup": markup})


class ClientThemeRequests(BaseRequestMiddleware):
    """One accepted message; cosmetic edits never replay the customer handler."""
    def __init__(self, service):
        self.service = service

    async def __call__(self, make_request, bot, method):
        context = _CURRENT.get()
        if not isinstance(context, _ThemeScope) or not context.active:
            return await make_request(bot, method)
        actor, theme = context.actor, context.theme
        if not self.service.permitted(bot.id) or getattr(method, "chat_id", None) != actor:
            return await make_request(bot, method)
        decorated = decorate_method(method, theme, bot, device_detail=context.device_detail)
        if decorated is None:
            return await make_request(bot, method)
        if isinstance(method, SendMessage):
            # Establish a Unicode message first. Even revoked eligibility cannot
            # lead to a second send of a private payload.
            result = await make_request(bot, method)
            if (not isinstance(result, Message) or result.chat.type != "private"
                    or result.chat.id != actor or result.message_id <= 0
                    or result.text != method.text
                    or not result.from_user or result.from_user.id != bot.id or not result.from_user.is_bot):
                self.service.blocked = True
                return result
            edit = EditMessageText(chat_id=actor, message_id=result.message_id,
                                   text=decorated.text, entities=decorated.entities, parse_mode=None,
                                   reply_markup=decorated.reply_markup, link_preview_options=method.link_preview_options)
            try:
                await make_request(bot, edit)
            except asyncio.CancelledError:
                self.service.blocked = True
                raise
            except Exception:
                # Initial receipt is proven. Cosmetic failure/unknown causes no
                # resend, retry, handler replay or raw payload/error logging.
                self.service.blocked = True
            return result
        try:
            return await make_request(bot, decorated)
        except asyncio.CancelledError:
            self.service.blocked = True
            raise
        except TelegramBadRequest as exc:
            self.service.blocked = True
            if type(exc) is TelegramBadRequest and exc.method is decorated:
                # Pinned SDK maps HTTP400 to this type: proven rejection. One
                # Unicode edit of the same message; never edit-to-new-send.
                try:
                    return await make_request(bot, method)
                except Exception:
                    pass
            raise ThemeTransportUnavailable("Client display unavailable") from None
        except Exception:
            self.service.blocked = True
            raise ThemeTransportUnavailable("Client display outcome unknown") from None


class ClientThemeContext(BaseMiddleware):
    def __init__(self, service):
        self.service = service

    async def __call__(self, handler, event, data):
        msg = event.message if isinstance(event, CallbackQuery) else event
        user = getattr(event, "from_user", None)
        if (not isinstance(msg, Message) or msg.chat.type != "private" or not user
                or user.is_bot or user.id <= 0 or user.id != msg.chat.id):
            return await handler(event, data)
        bot = data.get("bot") or event.bot
        if isinstance(event, CallbackQuery) and (
                not msg.from_user or not msg.from_user.is_bot or msg.from_user.id != bot.id):
            return await handler(event, data)
        theme = await self.service.snapshot(bot.id)
        detail = isinstance(event, CallbackQuery) and re.fullmatch(
            r"client:device:[1-9][0-9]{0,18}:(0|[1-9][0-9]{0,2})", event.data or "") is not None
        scope = _ThemeScope(user.id, theme, detail)
        token = _CURRENT.set(scope)
        try:
            return await handler(event, data)
        except ThemeTransportUnavailable:
            if isinstance(event, CallbackQuery):
                await event.answer("Оформление отключено. Повторите переход — будет обычный вид.", show_alert=True)
            return None
        finally:
            scope.active = False  # Revoke context inherited by delayed child tasks.
            _CURRENT.reset(token)
