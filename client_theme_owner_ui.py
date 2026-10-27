"""Owner-only theme drafts. Admin panels themselves always use Unicode."""
from __future__ import annotations

import math
import secrets
import time
from dataclasses import dataclass

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, Sticker

from admin_auth import get_admin_role
from admin_ui import get_panel_message, render_callback, render_input
from client_theme import (
    SLOTS, ThemeSnapshot, ThemeUnavailable, ThemeConflict, _CURRENT, _HEADINGS, _ThemeScope, emoji_id,
)


class ThemeInput(StatesGroup):
    value = State()


@dataclass(frozen=True)
class _Action:
    actor: int
    chat: int
    message: int
    expires: float
    action: str
    args: tuple


def extract_emoji(message):
    text, entities = message.text, message.entities or []
    if not isinstance(text, str) or len(text) > 128 or len(entities) != 1:
        raise ValueError("Send one custom emoji entity")
    entity = entities[0]
    if entity.type != "custom_emoji" or entity.offset < 0 or entity.length <= 0:
        raise ValueError("Send one custom emoji entity")
    raw = text.encode("utf-16-le")
    first, last = 2 * entity.offset, 2 * (entity.offset + entity.length)
    if last > len(raw) or text.strip() != raw[first:last].decode("utf-16-le"):
        raise ValueError("Custom emoji must be the whole message")
    return emoji_id(entity.custom_emoji_id)


async def verify_emoji(bot, identifier):
    # Metadata existence is not bot eligibility. No files/downloads/other bot.
    result = await bot.get_custom_emoji_stickers(custom_emoji_ids=[emoji_id(identifier)], request_timeout=3)
    if (not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], Sticker)
            or result[0].type != "custom_emoji" or result[0].custom_emoji_id != identifier):
        raise ValueError("Custom emoji was not verified")
    return identifier


class ClientThemeOwnerUI:
    def __init__(self, service, *, clock=time.monotonic):
        self.service, self.clock = service, clock
        self.router = Router(name="client_theme_owner")
        self.router.callback_query.register(self.callback, F.data.regexp(r"^admin:client-theme(?::[a-f0-9]{16})?$"))
        self.router.message.register(self.input, ThemeInput.value)
        self.actions, self.views = {}, {}
        self.last_action, self.last_preview = {}, {}
        self.inputs, self.lookup_busy = {}, set()

    def _now(self):
        now = self.clock()
        if not isinstance(now, (int, float)) or not math.isfinite(now) or now < 0:
            raise ThemeUnavailable("UI clock unavailable")
        return now

    async def _owner(self, event):
        user = event.from_user
        message = event.message if isinstance(event, CallbackQuery) else event
        if (not user or user.is_bot or user.id <= 0 or not isinstance(message, Message)
                or message.chat.type != "private" or message.chat.id != user.id
                or message.sender_chat or message.via_bot):
            raise ThemeUnavailable("Private Owner context required")
        if isinstance(event, CallbackQuery):
            if not message.from_user or not message.from_user.is_bot or message.from_user.id != event.bot.id:
                raise ThemeUnavailable("Bot panel required")
        if await get_admin_role(self.service.db, self.service.settings, user.id) != "owner":
            raise ThemeUnavailable("Owner required")
        return user.id, message

    def _clear(self, actor, chat):
        now = self._now()
        self.actions = {k: v for k, v in self.actions.items()
                        if now < v.expires and (v.actor, v.chat) != (actor, chat)}
        self.views = {k: v for k, v in self.views.items() if now < v[1] and k != (actor, chat)}
        self.inputs = {k: v for k, v in self.inputs.items() if k in self.views}

    async def _render(self, event, text, buttons=()):
        actor, incoming = await self._owner(event)
        panel = incoming if isinstance(event, CallbackQuery) else get_panel_message(incoming.chat.id, actor)
        if not isinstance(panel, Message):
            raise ThemeUnavailable("Panel unavailable")
        self._clear(actor, panel.chat.id)
        if len(self.actions) + len(buttons) > 256 or len(self.views) >= 256:
            raise ThemeUnavailable("UI capacity reached")
        now, rows = self._now(), []
        for label, action, args in buttons:
            token = secrets.token_hex(8)
            self.actions[token] = _Action(actor, panel.chat.id, panel.message_id,
                                          now + (90 if action == "save" else 300), action, tuple(args))
            rows.append([InlineKeyboardButton(text=label, callback_data="admin:client-theme:" + token)])
        rows.append([InlineKeyboardButton(text="⬅ Клиентский портал", callback_data="admin:settings:client")])
        markup = InlineKeyboardMarkup(inline_keyboard=rows)
        visible = frozenset(button.callback_data for row in rows for button in row if button.callback_data != "admin:settings:client")
        self.views[(actor, panel.chat.id)] = (panel.message_id, now + 300, visible)
        render = render_callback if isinstance(event, CallbackQuery) else render_input
        await render(event, text, reply_markup=markup, parse_mode=None,
                     link_preview_options={"is_disabled": True})

    def _visible(self, panel):
        return {b.callback_data for row in (panel.reply_markup.inline_keyboard if panel.reply_markup else []) for b in row}

    def _take(self, call, actor, panel):
        token = (call.data or "").removeprefix("admin:client-theme:")
        item = self.actions.get(token)
        if (not item or self._now() >= item.expires or call.data not in self._visible(panel)
                or (item.actor, item.chat, item.message) != (actor, panel.chat.id, panel.message_id)):
            raise ThemeUnavailable("Expired theme action")
        self._clear(actor, panel.chat.id)  # One-shot, before any mutation await.
        return item.action, item.args

    async def _home(self, event):
        snapshot = await self.service.read()
        can_enable = self.service.permitted(event.bot.id)
        text = ("🎨 Оформление клиентского портала\n\n"
                f"Слотов настроено: {len(snapshot.icons)} / {len(SLOTS)}\n"
                f"Тема: {'включена' if snapshot.enabled else 'выключена'}\n"
                f"Локальный допуск: {'подтверждён оператором для этого бота' if can_enable else 'запрещён или временно отключён'}\n"
                "Настройка не меняет доступ, подписки или платежи. Админка сохраняет обычные значки.\n"
                "Данные emoji не подтверждают Telegram eligibility. До отдельного допуска действует Unicode.")
        buttons = [("🗂 Слоты", "list", (0,)), ("↩ Сбросить всю тему", "ask", ("reset_all", None, None, snapshot.revision))]
        if snapshot.enabled or can_enable:
            action = "disable" if snapshot.enabled else "enable"
            buttons.append(("⚪ Выключить" if snapshot.enabled else "🟢 Включить", "ask", (action, None, None, snapshot.revision)))
        await self._render(event, text, buttons)

    async def _list(self, event, page):
        keys = list(SLOTS)
        page = min(max(0, page), (len(keys) - 1) // 8)
        buttons = [(SLOTS[key].fallback + " " + SLOTS[key].label, "slot", (key,)) for key in keys[page * 8:page * 8 + 8]]
        if page: buttons.append(("⬅ Предыдущая", "list", (page - 1,)))
        if (page + 1) * 8 < len(keys): buttons.append(("➡ Следующая", "list", (page + 1,)))
        buttons.append(("⬅ Оформление", "home", ()))
        await self._render(event, f"🗂 Клиентские значки · страница {page + 1}", buttons)

    async def _slot(self, event, slot):
        snapshot = await self.service.read()
        await self._render(event, f"{SLOTS[slot].fallback} {SLOTS[slot].label}\n\n{slot}\n"
                           f"Custom emoji ID: {dict(snapshot.icons).get(slot, 'не задан')}\n"
                           "Русский текст, Unicode fallback и маршруты заданы кодом; произвольный HTML не принимается.",
                           [("✏️ Изменить", "input", (slot, snapshot.revision)),
                            ("↩ Сбросить слот", "ask", ("reset", slot, None, snapshot.revision)),
                            ("⬅ Слоты", "list", (list(SLOTS).index(slot) // 8,))])

    async def _ask(self, event, action, slot, value, revision):
        current = await self.service.read()
        if current.revision != revision:
            raise ThemeConflict("Stale theme")
        buttons = [("✅ Подтвердить", "save", (action, slot, value, revision))]
        if action == "set": buttons.append(("👁 Клиентское превью", "preview", (slot, value, revision)))
        buttons.append(("✖ Отмена", "slot" if slot else "home", (slot,) if slot else ()))
        await self._render(event, "🎨 Предпросмотр настройки\n\n"
                           + (f"{SLOTS[slot].fallback} {SLOTS[slot].label}\n{slot}\nEmoji ID: {value or 'стандартный'}\n" if slot else "Вся клиентская тема\n")
                           + f"Действие: {dict(set='сохранить значок', reset='сбросить слот', reset_all='сбросить и выключить', enable='включить', disable='выключить')[action]}\n"
                           "Это только черновик до подтверждения. Custom preview требует локального допуска; иначе обычный Unicode.", buttons)

    async def _preview(self, call, actor, slot, value, revision):
        now = self._now()
        self.last_preview = {k: v for k, v in self.last_preview.items() if now - v < 600}
        if now - self.last_preview.get(actor, -600) < 10 or len(self.last_preview) >= 256:
            raise ThemeUnavailable("Preview rate limit")
        self.last_preview[actor] = now
        snapshot = await self.service.read()
        if snapshot.revision != revision:
            raise ThemeConflict("Stale preview")
        icons = dict(snapshot.icons); icons[slot] = value
        theme = ThemeSnapshot(revision, self.service.permitted(call.bot.id), tuple(icons.items()))
        heading = next((prefix for prefix, key in _HEADINGS if key == slot), "👤 Профиль")
        samples = {"portal.action.connect": "📱 Подключить устройство", "portal.action.link": "📋 Скопировать ссылку",
                   "portal.action.qr": "🔳 QR подписки", "portal.action.open": "🚀 Открыть в VPN-клиент",
                   "portal.action.import": "🔗 VPN-клиент · импорт", "portal.action.check": "🛠 Проверить подписку",
                   "portal.action.refresh": "🔄 Обновить", "portal.nav.back": "⬅ Личный кабинет", "portal.nav.next": "➡ Следующая"}
        label = samples.get(slot, SLOTS[slot].fallback + " " + SLOTS[slot].label)
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data="client:home")],
            [InlineKeyboardButton(text="⬅ Настройки оформления", callback_data="admin:client-theme")]])
        scope = _ThemeScope(actor, theme)
        token = _CURRENT.set(scope)
        try:
            await call.bot.send_message(actor, heading + "\n\nПример клиентского экрана. Данные вымышлены.\n🔗 Subscription URL:\nссылка не используется",
                                        reply_markup=markup, parse_mode=None, link_preview_options={"is_disabled": True})
        finally:
            scope.active = False
            _CURRENT.reset(token)
        await self._ask(call, "set", slot, value, revision)

    async def _failure(self, event, state, error):
        await state.clear()
        text = ("Настройка уже изменилась. Откройте актуальную версию." if isinstance(error, ThemeConflict)
                else "Действие недоступно или исход не подтверждён. Обновите раздел; автоматического повтора нет.")
        try:
            await self._render(event, text, [("⬅ Оформление", "home", ())])
        except Exception:
            if isinstance(event, CallbackQuery):
                await event.answer("Нет доступа или раздел временно недоступен.", show_alert=True)

    async def callback(self, call: CallbackQuery, state: FSMContext):
        try:
            actor, panel = await self._owner(call)
            now = self._now()
            self.last_action = {k: v for k, v in self.last_action.items() if now - v < 600}
            if now - self.last_action.get(actor, -600) < 0.5 or len(self.last_action) >= 256:
                await call.answer("Слишком часто. Повторите позже.", show_alert=True)
                return
            self.last_action[actor] = now
            if call.data == "admin:client-theme":
                await state.clear(); await self._home(call)
            else:
                action, args = self._take(call, actor, panel)
                await state.clear()
                if action == "home": await self._home(call)
                elif action == "list": await self._list(call, *args)
                elif action == "slot": await self._slot(call, *args)
                elif action == "ask": await self._ask(call, *args)
                elif action == "preview": await self._preview(call, actor, *args)
                elif action == "input":
                    slot, revision = args
                    await self._render(call, "Отправьте или перешлите ровно один custom emoji.\n"
                                       "Обычный значок, числовой ID, URL, HTML и дополнительные данные не принимаются.",
                                       [("✖ Отмена", "slot", (slot,))])
                    await state.set_state(ThemeInput.value)
                    await state.set_data({"theme_slot": slot, "theme_revision": revision})
                elif action == "save":
                    operation, slot, value, revision = args
                    await self.service.change(actor, revision, operation, slot=slot, value=value, bot_id=call.bot.id)
                    if slot:
                        await self._slot(call, slot)
                    else:
                        await self._home(call)
                else: raise ThemeUnavailable("Unknown theme action")
            await call.answer()
        except Exception as error:
            await self._failure(call, state, error)

    async def input(self, message: Message, state: FSMContext):
        binding = None
        try:
            actor, _ = await self._owner(message)
            panel = get_panel_message(message.chat.id, actor)
            view = self.views.get((actor, message.chat.id))
            if (not view or not isinstance(panel, Message) or panel.message_id != view[0]
                    or self._now() >= view[1] or not view[2].intersection(self._visible(panel))):
                raise ThemeUnavailable("Expired form")
            data = await state.get_data()
            slot, revision = data.get("theme_slot"), data.get("theme_revision")
            if slot not in SLOTS or type(revision) is not int:
                raise ThemeUnavailable("Invalid form")
            key = (actor, message.chat.id)
            if self.views.get(key) != view or actor in self.lookup_busy or len(self.lookup_busy) >= 8:
                raise ThemeUnavailable("Input already consumed or lookup busy")
            binding = secrets.token_hex(8)
            self.inputs[key] = binding
            self.lookup_busy.add(actor)
            try:
                await state.clear()  # Input consumed before API lookup; no raw body persisted.
                identifier = await verify_emoji(message.bot, extract_emoji(message))
            finally:
                self.lookup_busy.discard(actor)
            # A cancel/new panel while metadata was in flight revokes the draft.
            if self.inputs.get(key) != binding or self.views.get(key) != view:
                return
            panel = get_panel_message(message.chat.id, actor)
            if not isinstance(panel, Message) or not view[2].intersection(self._visible(panel)):
                self.inputs.pop(key, None)
                return
            await self._ask(message, "set", slot, identifier, revision)
        except Exception as error:
            if binding is not None and self.inputs.get((actor, message.chat.id)) != binding:
                return
            await self._failure(message, state, error)
