import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import EditMessageText, SendMessage, SendInvoice
from aiogram.types import CallbackQuery, Chat, InlineKeyboardButton, InlineKeyboardMarkup, Message, MessageEntity, Sticker, User

from admin_privileges import required_role_for_callback
from admin_ui import get_panel_message, register_panel_message
from client_theme import (
    ClientThemeService, ClientThemeContext, ClientThemeRequests, SLOTS, SETTING_KEY,
    ThemeSnapshot, ThemeConflict, ThemeUnavailable, ThemeTransportUnavailable,
    decode_theme, encode_theme, emoji_id, decorate_markup, decorate_text, _CURRENT, _ThemeScope,
)
import client_theme_owner_ui as ui
from db import Database


IDENTIFIER = "1234567890123456789"  # Synthetic; never looked up on Telegram.


def message(actor=10, *, panel=False, text=None, **extra):
    return Message(message_id=77 if panel else 90, date=datetime.now(timezone.utc),
                   chat=Chat(id=actor, type="private"),
                   from_user=User(id=2000 if panel else actor, is_bot=panel, first_name="Fixture"), text=text, **extra)


def settings(enabled=True, bot_id=2000):
    return SimpleNamespace(admin_telegram_ids=(10,), client_custom_emoji_enabled=enabled,
                           client_custom_emoji_verified_bot_id=bot_id)


class ThemeCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "fixture.sqlite3")); await self.db.init()
        self.service = ClientThemeService(self.db, settings())

    async def asyncTearDown(self):
        self.tmp.cleanup()


class ThemeStoreTests(ThemeCase):
    async def test_default_off_and_bot_bound_operator_veto(self):
        self.assertFalse((await self.service.snapshot(2000)).enabled)
        await self.service.change(10, 0, "set", slot="portal.menu.profile", value=IDENTIFIER)
        await self.service.change(10, 1, "enable", bot_id=2000)
        self.assertTrue((await self.service.snapshot(2000)).enabled)
        self.assertFalse((await self.service.snapshot(2001)).enabled)
        self.assertFalse((await ClientThemeService(self.db, settings(False)).snapshot(2000)).enabled)
        with self.assertRaises(ThemeUnavailable):
            await ClientThemeService(self.db, settings(False)).change(10, 2, "enable", bot_id=2000)
        self.assertFalse(ClientThemeService(self.db, settings(True, True)).permitted(1))

    async def test_cas_concurrency_restart_and_atomic_audit(self):
        result = await asyncio.gather(
            self.service.change(10, 0, "set", slot="portal.menu.profile", value=IDENTIFIER),
            self.service.change(10, 0, "set", slot="portal.nav.back", value=IDENTIFIER), return_exceptions=True)
        self.assertEqual(sum(isinstance(x, ThemeConflict) for x in result), 1)
        fresh = ClientThemeService(Database(self.db.path), settings())
        snapshot = await fresh.read(); self.assertEqual(snapshot.revision, 1); self.assertEqual(len(snapshot.icons), 1)
        with sqlite3.connect(self.db.path) as conn:
            count, details = conn.execute("SELECT count(*), details FROM audit_log WHERE action='client.theme.change'").fetchone()
            self.assertEqual(count, 1); self.assertNotIn(IDENTIFIER, details)

    async def test_owner_role_rechecked_at_transaction_and_disabled_rejected(self):
        for role in ("read_only", "support", "admin"):
            await self.db.upsert_administrator(telegram_id=20, role=role)
            with self.assertRaises(ThemeUnavailable): await self.service.change(20, 0, "reset_all")
        await self.db.upsert_administrator(telegram_id=20, role="owner")
        await self.service.change(20, 0, "reset_all")
        await self.db.set_administrator_enabled(20, False)
        with self.assertRaises(ThemeUnavailable): await self.service.change(20, 1, "reset_all")

    async def test_reset_slot_and_all_preserve_other_runtime_settings(self):
        await self.db.set_runtime_setting("trial_days", "7")
        for revision, slot in enumerate(("portal.menu.profile", "portal.nav.back")):
            await self.service.change(10, revision, "set", slot=slot, value=IDENTIFIER)
        await self.service.change(10, 2, "reset", slot="portal.nav.back")
        self.assertEqual(len((await self.service.read()).icons), 1)
        await self.service.change(10, 3, "reset_all")
        self.assertEqual((await self.service.read()).icons, ())
        self.assertEqual(await self.db.get_runtime_setting("trial_days"), "7")

    async def test_corruption_denies_writes_and_render_falls_back(self):
        await self.db.set_runtime_setting(SETTING_KEY, '{"version":1,"version":1}')
        self.assertFalse((await self.service.snapshot(2000)).enabled)
        with self.assertRaises(ThemeUnavailable): await self.service.change(10, 0, "reset_all")
        self.assertEqual(await self.db.get_runtime_setting(SETTING_KEY), '{"version":1,"version":1}')

    async def test_audit_failure_rolls_back_setting_atomically(self):
        with sqlite3.connect(self.db.path) as conn:
            conn.execute("CREATE TRIGGER fixture_audit_failure BEFORE INSERT ON audit_log BEGIN SELECT RAISE(ABORT, 'fixture'); END")
        with self.assertRaises(ThemeUnavailable):
            await self.service.change(10, 0, "set", slot="portal.menu.profile", value=IDENTIFIER)
        self.assertEqual((await self.service.read()).revision, 0)


class ThemeRenderTests(unittest.TestCase):
    def setUp(self): self.theme = ThemeSnapshot(1, True, tuple(sorted((key, IDENTIFIER) for key in SLOTS)))

    def test_identifiers_strict_json_schema_and_no_arbitrary_markup(self):
        for value in (None, True, 12, "", "0", "01", "１２", "1\" onclick=", "18446744073709551616"):
            with self.subTest(value=value), self.assertRaises(ValueError): emoji_id(value)
        encoded = encode_theme(self.theme); self.assertEqual(decode_theme(encoded), self.theme)
        for bad in ({"version": 2}, {"version": 1, "revision": True, "enabled": True, "icons": {}},
                    {"version": 1, "revision": 0, "enabled": True, "icons": {"admin.home": IDENTIFIER}}):
            with self.assertRaises(ValueError): decode_theme(json.dumps(bad))

    def test_environment_is_off_by_default_and_activation_requires_bound_bot(self):
        from config import load_settings
        fixture = {"BOT_TOKEN": "2000:synthetic-test-token", "PANEL_URL": "https://panel.example.invalid",
                   "PANEL_API_TOKEN": "synthetic", "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/{sub_id}",
                   "ALLOWED_TELEGRAM_IDS": "10", "ADMIN_TELEGRAM_IDS": "10"}
        with patch.dict(os.environ, fixture, clear=True):
            self.assertFalse(load_settings().client_custom_emoji_enabled)
            os.environ["CLIENT_CUSTOM_EMOJI_ENABLED"] = "true"
            with self.assertRaises(RuntimeError): load_settings()
            os.environ["CLIENT_CUSTOM_EMOJI_VERIFIED_BOT_ID"] = "2000"
            self.assertEqual(load_settings().client_custom_emoji_verified_bot_id, 2000)
            os.environ["CLIENT_CUSTOM_EMOJI_VERIFIED_BOT_ID"] = "-1"
            with self.assertRaises(RuntimeError): load_settings()

    def test_button_callbacks_labels_payloads_and_statuses_are_unchanged(self):
        source = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="👤 Профиль", callback_data="client:profile"),
            InlineKeyboardButton(text="🟢 Включено", callback_data="client:status"),
            InlineKeyboardButton(text="⬅ Система", callback_data="admin:section:system"),
            InlineKeyboardButton(text="🗑 Да, удалить устройство", callback_data="client:device-delete:confirm:abc"),
        ]])
        result = decorate_markup(source, self.theme)
        self.assertEqual(result.inline_keyboard[0][0].icon_custom_emoji_id, IDENTIFIER)
        for before, after in zip(source.inline_keyboard[0], result.inline_keyboard[0]):
            self.assertEqual(before.text, after.text); self.assertEqual(before.callback_data, after.callback_data)
        for button in result.inline_keyboard[0][1:]: self.assertIsNone(button.icon_custom_emoji_id)
        self.assertIsNone(source.inline_keyboard[0][0].icon_custom_emoji_id)
        self.assertIs(decorate_markup(source, ThemeSnapshot()), source)

    def test_typed_entities_use_utf16_offsets_and_do_not_parse_user_html(self):
        text = "🌐 Моя подписка\n\n👨‍👩‍👧‍👦 <b>literal</b>\n🔗 Subscription URL:\nhttps://example.invalid/synthetic"
        entities = decorate_text(text, self.theme)
        self.assertEqual(len(entities), 2); self.assertEqual(entities[0].length, 2)
        start = len(text.split("🔗")[0].encode("utf-16-le")) // 2
        self.assertEqual(entities[1].offset, start); self.assertEqual(entities[1].length, 2)
        self.assertEqual(decorate_text("📱 Устройства · 12/20\n\n", self.theme)[0].custom_emoji_id, IDENTIFIER)
        self.assertEqual(decorate_text("📜 История · заказы\n\n", self.theme)[0].length, 2)
        self.assertEqual(decorate_text("🖥️ Fixture\n\n", self.theme, device_detail=True)[0].length, 3)
        self.assertEqual(decorate_text("❌ Нет доступа", self.theme), [])
        self.assertEqual(decorate_text("😀" * 4097, self.theme), [])
        self.assertEqual(decorate_text(chr(0xD800), self.theme), [])

    def test_every_semantic_slot_has_a_safe_unicode_binding(self):
        self.assertLessEqual(len(SLOTS), 32)
        for slot, spec in SLOTS.items():
            self.assertTrue(slot.startswith("portal.")); self.assertTrue(spec.label); self.assertTrue(spec.fallback)
            self.assertEqual(self.theme.icon(slot), IDENTIFIER)
        self.assertIsNone(self.theme.icon("admin.home"))

    def test_all_slots_have_reachable_button_or_text_bindings(self):
        from client_theme import _HEADINGS, _button_slot
        samples = {"connect": "📱 Подключить устройство", "link": "📋 Скопировать ссылку",
                   "qr": "🔳 QR подписки", "open": "🚀 Открыть в VPN-клиент", "import": "🔗 VPN-клиент · импорт",
                   "check": "🛠 Проверить подписку", "refresh": "🔄 Обновить"}
        covered = set()
        for key, spec in SLOTS.items():
            if key.startswith("portal.menu."):
                label = spec.fallback + " " + spec.label
            elif key.startswith("portal.action."):
                label = samples[key.rsplit(".", 1)[1]]
            elif key.startswith("portal.nav."):
                label = "⬅ Личный кабинет" if key.endswith("back") else "➡ Следующая"
            else: continue
            button = InlineKeyboardButton(text=label, callback_data="client:home")
            self.assertEqual(_button_slot(button), key)
            covered.add(key)
        for prefix, key in _HEADINGS:
            entities = decorate_text(prefix + "\n\nfixture", self.theme)
            self.assertEqual(entities[0].custom_emoji_id, IDENTIFIER); covered.add(key)
        self.assertTrue(decorate_text("fixture\n🔗 Subscription URL:\nhttps://example.invalid", self.theme))
        covered.add("portal.subscription.link")
        self.assertEqual(covered, set(SLOTS))

    def test_entity_input_requires_one_whole_telegram_entity(self):
        good = message(text="😀", entities=[MessageEntity(type="custom_emoji", offset=0, length=2, custom_emoji_id=IDENTIFIER)])
        self.assertEqual(ui.extract_emoji(good), IDENTIFIER)
        for bad in (message(text=IDENTIFIER), message(text="<tg-emoji>😀</tg-emoji>"),
                    good.model_copy(update={"text": "😀 secret"}),
                    good.model_copy(update={"entities": [MessageEntity(type="custom_emoji", offset=1, length=1, custom_emoji_id=IDENTIFIER)]})):
            with self.assertRaises((ValueError, UnicodeError)): ui.extract_emoji(bad)


class ThemeTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = Bot("2000:synthetic-test-token")
        self.service = ClientThemeService(SimpleNamespace(), settings())
        self.middleware = ClientThemeRequests(self.service)
        self.theme = ThemeSnapshot(1, True, (("portal.profile.heading", IDENTIFIER),))
        self.scope = _ThemeScope(10, self.theme)
        self.token = _CURRENT.set(self.scope)

    async def asyncTearDown(self):
        _CURRENT.reset(self.token); await self.bot.session.close()

    async def test_send_once_then_one_cosmetic_edit_and_no_resend_on_any_failure(self):
        for failure in (None, "400", "network"):
            self.service.blocked = False; calls = []
            async def invoke(bot, method):
                calls.append(method)
                if len(calls) == 1: return message(panel=True, text=method.text)
                if failure == "400": raise TelegramBadRequest(method=method, message="CUSTOM_EMOJI_INVALID")
                if failure: raise TelegramNetworkError(method=method, message="fixture")
                return message(panel=True, text=method.text)
            original = SendMessage(chat_id=10, text="👤 Профиль\n\nprivate fixture")
            result = await self.middleware(invoke, self.bot, original)
            self.assertEqual(len(calls), 2); self.assertIs(calls[0], original)
            self.assertIsInstance(calls[1], EditMessageText); self.assertEqual(calls[1].message_id, result.message_id)
            self.assertIsNone(original.entities); self.assertEqual(calls[1].entities[0].custom_emoji_id, IDENTIFIER)
            self.assertEqual(self.service.blocked, failure is not None)

    async def test_definite_400_gets_only_same_panel_unicode_edit(self):
        calls = []
        async def invoke(bot, method):
            calls.append(method)
            if len(calls) == 1: raise TelegramBadRequest(method=method, message="fixture 400")
            return message(panel=True)
        original = EditMessageText(chat_id=10, message_id=77, text="👤 Профиль\n\nfixture")
        await self.middleware(invoke, self.bot, original)
        self.assertEqual(len(calls), 2); self.assertIs(calls[1], original)
        self.assertTrue(all(isinstance(x, EditMessageText) for x in calls)); self.assertTrue(self.service.blocked)

    async def test_unknown_and_foreign_request_error_no_fallback_or_replay(self):
        for failure in ("network", "foreign400"):
            self.service.blocked = False; calls = []
            async def invoke(bot, method):
                calls.append(method)
                if failure == "foreign400": raise TelegramBadRequest(method=SendMessage(chat_id=99, text="fixture"), message="fixture")
                raise TelegramNetworkError(method=method, message="fixture")
            with self.assertRaises(ThemeTransportUnavailable):
                await self.middleware(invoke, self.bot, EditMessageText(chat_id=10, message_id=77, text="👤 Профиль\n\nfixture"))
            self.assertEqual(len(calls), 1)

    async def test_pinned_sdk_http_status_not_json_error_code_controls_fallback(self):
        for status, parameters, count in ((400, {}, 2), (500, {}, 1), (500, {"retry_after": 1}, 1)):
            self.service.blocked = False; calls = []
            async def invoke(bot, method):
                calls.append(method)
                if len(calls) > 1: return message(panel=True, text=method.text)
                content = json.dumps({"ok": False, "error_code": 400, "description": "fixture emoji error", "parameters": parameters})
                return self.bot.session.check_response(bot, method, status, content)
            operation = EditMessageText(chat_id=10, message_id=77, text="👤 Профиль\n\nfixture")
            if status == 400: await self.middleware(invoke, self.bot, operation)
            else:
                with self.assertRaises(ThemeTransportUnavailable): await self.middleware(invoke, self.bot, operation)
            self.assertEqual(len(calls), count)

    async def test_plain_fallback_failure_never_escapes_as_generic_bad_request(self):
        invoke = AsyncMock(side_effect=lambda bot, method: (_ for _ in ()).throw(TelegramBadRequest(method=method, message="fixture")))
        with self.assertRaises(ThemeTransportUnavailable):
            await self.middleware(invoke, self.bot, EditMessageText(chat_id=10, message_id=77, text="👤 Профиль\n\nfixture"))
        self.assertEqual(invoke.await_count, 2)

    async def test_other_chat_admin_scope_html_or_existing_entities_untouched(self):
        for token_value, method in ((ThemeSnapshot(), SendMessage(chat_id=10, text="👤 Профиль\n\n")),
                (_ThemeScope(10, self.theme), SendMessage(chat_id=20, text="👤 Профиль\n\n")),
                (_ThemeScope(10, self.theme), SendMessage(chat_id=10, text="👤 Профиль\n\n", parse_mode="HTML")),
                (_ThemeScope(10, self.theme), SendMessage(chat_id=10, text="👤 Профиль\n\n", entities=[MessageEntity(type="bold", offset=0, length=2)]))):
            token = _CURRENT.set(token_value); invoke = AsyncMock(return_value=message(panel=True))
            try: await self.middleware(invoke, self.bot, method)
            finally: _CURRENT.reset(token)
            self.assertEqual(invoke.await_count, 1); self.assertIs(invoke.call_args.args[1], method)

    async def test_unbound_or_wrong_receipt_never_edits(self):
        invoke = AsyncMock(return_value=message(actor=20, panel=True))
        await self.middleware(invoke, self.bot, SendMessage(chat_id=10, text="👤 Профиль\n\n"))
        self.assertEqual(invoke.await_count, 1); self.assertTrue(self.service.blocked)

    async def test_context_reset_on_handler_exception_and_group_not_activated(self):
        service = SimpleNamespace(snapshot=AsyncMock(return_value=self.theme))
        middleware = ClientThemeContext(service)
        event = CallbackQuery(id="f", chat_instance="f", data="client:profile",
                              from_user=User(id=10, is_bot=False, first_name="Fixture"), message=message(panel=True)).as_(self.bot)
        async def handler(event, data):
            self.assertEqual((_CURRENT.get().actor, _CURRENT.get().theme), (10, self.theme)); raise ValueError("fixture")
        with self.assertRaises(ValueError): await middleware(handler, event, {"bot": self.bot})
        self.assertIs(_CURRENT.get(), self.scope)
        group = message().model_copy(update={"chat": Chat(id=-100, type="group")}).as_(self.bot)
        before = service.snapshot.await_count
        await middleware(AsyncMock(), group, {"bot": self.bot})
        self.assertEqual(service.snapshot.await_count, before)

    async def test_delayed_child_task_cannot_keep_client_decoration_scope(self):
        proceed = asyncio.Event(); calls = []
        service = SimpleNamespace(snapshot=AsyncMock(return_value=self.theme))
        context = ClientThemeContext(service)
        event = message().as_(self.bot)
        async def invoke(bot, method): calls.append(method); return message(panel=True, text=method.text)
        async def delayed():
            await proceed.wait()
            await self.middleware(invoke, self.bot, EditMessageText(chat_id=10, message_id=77, text="👤 Профиль\n\nfixture"))
        async def handler(event, data): return asyncio.create_task(delayed())
        child = await context(handler, event, {"bot": self.bot})
        proceed.set(); await child
        self.assertEqual(len(calls), 1); self.assertIsNone(calls[0].entities)

    async def test_cancellation_opens_circuit_and_does_not_replay(self):
        invoke = AsyncMock(side_effect=asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):
            await self.middleware(invoke, self.bot, EditMessageText(chat_id=10, message_id=77, text="👤 Профиль\n\nfixture"))
        self.assertTrue(self.service.blocked); self.assertEqual(invoke.await_count, 1)

    async def test_real_dispatcher_session_isolates_client_and_admin(self):
        from aiogram import Dispatcher, F, Router
        from aiogram.client.session.base import BaseSession
        from aiogram.types import Update
        class Session(BaseSession):
            def __init__(self): super().__init__(); self.calls = []
            async def close(self): pass
            async def stream_content(self, *args, **kwargs):
                if False: yield b""
            async def make_request(self, bot, method, timeout=None):
                self.calls.append(method)
                if isinstance(method, EditMessageText): return message(panel=True, text=method.text)
                return True
        session = Session(); bot = Bot("2000:synthetic-test-token", session=session)
        session.middleware(ClientThemeRequests(self.service))
        self.service.snapshot = AsyncMock(return_value=self.theme)
        client, admin = Router(), Router()
        client.callback_query.middleware(ClientThemeContext(self.service))
        async def show(call):
            await call.message.edit_text("👤 Профиль\n\nfixture")
            await call.answer()
        client.callback_query.register(show, F.data == "client:profile")
        admin.callback_query.register(show, F.data == "admin:home")
        dp = Dispatcher(); dp.include_router(client); dp.include_router(admin)
        token = _CURRENT.set(ThemeSnapshot())
        try:
            for idx, data in enumerate(("client:profile", "admin:home")):
                call = CallbackQuery(id="f", chat_instance="f", data=data, from_user=User(id=10, is_bot=False, first_name="Fixture"), message=message(panel=True))
                await dp.feed_update(bot, Update(update_id=idx, callback_query=call))
        finally: _CURRENT.reset(token); await session.close()
        edits = [m for m in session.calls if isinstance(m, EditMessageText)]
        self.assertEqual(len(edits), 2)
        self.assertEqual(edits[0].entities[0].custom_emoji_id, IDENTIFIER)
        self.assertIsNone(edits[1].entities)


class ThemeOwnerUITests(ThemeCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = Bot("2000:synthetic-test-token"); self.now = 1000
        self.ui = ui.ClientThemeOwnerUI(self.service, clock=lambda: self.now)
        self.storage = MemoryStorage(); self.state = FSMContext(storage=self.storage, key=StorageKey(bot_id=2000, chat_id=10, user_id=10))
        self.panel = message(panel=True).as_(self.bot); register_panel_message(10, self.panel)
        async def render(event, text, **kwargs):
            self.panel = self.panel.model_copy(update={"text": text, "reply_markup": kwargs["reply_markup"]}).as_(self.bot)
            register_panel_message(10, self.panel); return self.panel
        self.patches = [patch.object(ui, "render_callback", side_effect=render), patch.object(ui, "render_input", side_effect=render),
                        patch.object(CallbackQuery, "answer", new=AsyncMock())]
        for item in self.patches: item.start()

    async def asyncTearDown(self):
        for item in reversed(self.patches): item.stop()
        await self.storage.close(); await self.bot.session.close(); await super().asyncTearDown()

    def call(self, data="admin:client-theme", actor=10, panel=None):
        return CallbackQuery(id="f", chat_instance="f", data=data, from_user=User(id=actor, is_bot=False, first_name="Fixture"),
                             message=panel or self.panel).as_(self.bot)

    async def click(self, label):
        self.now += 1
        data = next(b.callback_data for row in self.panel.reply_markup.inline_keyboard for b in row if b.text.startswith(label))
        await self.ui.callback(self.call(data), self.state)
        return data

    async def draft(self):
        await self.ui.callback(self.call(), self.state)
        await self.click("🗂"); await self.click("👤 Профиль"); await self.click("✏️")
        sticker = Sticker(file_id="fixture", file_unique_id="fixture", type="custom_emoji", width=100, height=100,
                          is_animated=False, is_video=False, custom_emoji_id=IDENTIFIER)
        with patch.object(Bot, "get_custom_emoji_stickers", new=AsyncMock(return_value=[sticker])):
            await self.ui.input(message(text="😀", entities=[MessageEntity(type="custom_emoji", offset=0, length=2,
                                                                          custom_emoji_id=IDENTIFIER)]).as_(self.bot), self.state)

    async def test_owner_draft_requires_confirm_and_nonce_replay_cannot_save_twice(self):
        await self.draft(); self.assertEqual((await self.service.read()).revision, 0)
        old_panel = self.panel; data = await self.click("✅")
        self.assertEqual(dict((await self.service.read()).icons)["portal.menu.profile"], IDENTIFIER)
        self.now += 1; await self.ui.callback(self.call(data, panel=old_panel), self.state)
        self.assertEqual((await self.service.read()).revision, 1)
        for row in self.panel.reply_markup.inline_keyboard:
            for button in row: self.assertIsNone(button.icon_custom_emoji_id)

    async def test_non_owner_forged_expired_and_changed_panel_denied(self):
        await self.ui.callback(self.call(actor=20), self.state)
        self.assertFalse(self.ui.actions)
        await self.draft(); old = self.panel
        token = next(b.callback_data for row in old.reply_markup.inline_keyboard for b in row if b.text.startswith("✅"))
        self.now += 91; await self.ui.callback(self.call(token, panel=old), self.state)
        self.assertEqual((await self.service.read()).revision, 0)
        self.now += 1; await self.ui.callback(self.call("admin:client-theme:aaaaaaaaaaaaaaaa"), self.state)
        self.assertEqual((await self.service.read()).revision, 0)

    async def test_cancel_clears_form_and_previous_admin_panel_rejects_input(self):
        await self.ui.callback(self.call(), self.state)
        await self.click("🗂"); await self.click("👤 Профиль"); await self.click("✏️")
        register_panel_message(10, self.panel.model_copy(update={"reply_markup": InlineKeyboardMarkup(inline_keyboard=[])}))
        lookup = AsyncMock()
        with patch.object(Bot, "get_custom_emoji_stickers", new=lookup):
            await self.ui.input(message(text=IDENTIFIER).as_(self.bot), self.state)
        lookup.assert_not_awaited(); self.assertIsNone(await self.state.get_state())

    async def test_default_off_cannot_activate_or_preview_via_forged_token(self):
        self.service.settings = settings(False)
        await self.ui.callback(self.call(), self.state)
        self.assertNotIn("🟢 Включить", str(self.panel.reply_markup))
        self.assertEqual(required_role_for_callback("admin:client-theme"), "owner")
        self.assertEqual(required_role_for_callback("admin:client-theme:0123456789abcdef"), "owner")
        self.assertIsNone(required_role_for_callback("admin:client-theme:raw-id"))

    async def test_metadata_failure_never_saves_or_retains_input(self):
        await self.ui.callback(self.call(), self.state)
        await self.click("🗂"); await self.click("👤 Профиль"); await self.click("✏️")
        lookup = AsyncMock(return_value=[])
        with patch.object(Bot, "get_custom_emoji_stickers", new=lookup):
            await self.ui.input(message(text="😀", entities=[MessageEntity(type="custom_emoji", offset=0, length=2,
                                                                          custom_emoji_id=IDENTIFIER)]).as_(self.bot), self.state)
        lookup.assert_awaited_once()
        self.assertEqual(await self.state.get_data(), {})
        self.assertEqual((await self.service.read()).revision, 0)

    async def test_cancel_during_metadata_lookup_cannot_resurrect_draft(self):
        await self.ui.callback(self.call(), self.state)
        await self.click("🗂"); await self.click("👤 Профиль"); await self.click("✏️")
        entered, finish = asyncio.Event(), asyncio.Event()
        async def lookup(bot, identifier):
            entered.set(); await finish.wait(); return identifier
        with patch.object(ui, "verify_emoji", side_effect=lookup):
            task = asyncio.create_task(self.ui.input(message(text="😀", entities=[MessageEntity(type="custom_emoji", offset=0, length=2,
                                                                                              custom_emoji_id=IDENTIFIER)]).as_(self.bot), self.state))
            await entered.wait(); await self.click("✖")
            cancelled_panel = self.panel.text
            finish.set(); await task
        self.assertEqual(self.panel.text, cancelled_panel)
        self.assertNotIn("Предпросмотр настройки", self.panel.text)
        self.assertEqual((await self.service.read()).revision, 0)
