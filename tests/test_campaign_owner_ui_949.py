import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
import uuid

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Chat, InlineKeyboardButton, InlineKeyboardMarkup, Message, User

import campaign_owner_ui as ui
from admin_privileges import required_role_for_callback
from admin_ui import get_panel_message, register_panel_message
from campaign_store import CampaignOutcomeUnknown
from db import Database, UserRecord
from service_campaign_delivery import CampaignDelivery, CampaignWorker
from campaign_telegram import CampaignAwareSession, CampaignBotTransport, CampaignPrivateObserver


class FixturePolicy:
    allowed = True
    async def allow_category(self, category): return self.allowed
    async def allow_recipient(self, category, actor): return self.allowed


class CampaignOwnerSource949Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "fixture.sqlite3"
        self.db = Database(str(self.path)); await self.db.init()
        await self.db.put(UserRecord(1001, "fixture@example.invalid", "synthetic-sub", 0, 1))
        self.now = 1704067200
        self.settings = SimpleNamespace(admin_telegram_ids=(10, 20))
        self.policy = FixturePolicy()
        self.api = CampaignDelivery(self.db, authorize_owner=AsyncMock(side_effect=lambda actor: actor in {10, 20}),
                                    policy=self.policy, enabled=True, clock=lambda: self.now)
        self.controller = ui.CampaignOwnerUI(self.api, self.db, self.settings, enabled=True)
        self.storage = MemoryStorage()
        self.state = FSMContext(storage=self.storage, key=StorageKey(bot_id=2000, chat_id=10, user_id=10))
        self.panels = {}; self.rendered = []
        for actor in (10, 20, 30):
            self.panels[actor] = self.message(actor, panel=True)
            register_panel_message(actor, self.panels[actor])
        async def render(event, text, **kwargs):
            actor = event.from_user.id
            panel = event.message if isinstance(event, CallbackQuery) else get_panel_message(event.chat.id, actor)
            panel = panel.model_copy(update={"text": text, "reply_markup": kwargs["reply_markup"]})
            self.panels[actor] = panel
            register_panel_message(actor, panel)
            self.rendered.append((text, kwargs))
            return panel
        self.patches = [patch.object(ui, "render_callback", side_effect=render),
                        patch.object(ui, "render_input", side_effect=render),
                        patch.object(CallbackQuery, "answer", new=AsyncMock())]
        for item in self.patches: item.start()

    async def asyncTearDown(self):
        for item in reversed(self.patches): item.stop()
        await self.storage.close(); self.tmp.cleanup()

    def message(self, actor=10, *, panel=False, text=None, chat_id=None, kind="private", **extra):
        return Message(message_id=77 if panel else 90, date=datetime.now(timezone.utc),
                       chat=Chat(id=actor if chat_id is None else chat_id, type=kind),
                       from_user=User(id=2000 if panel else actor, is_bot=panel, first_name="Fixture"),
                       text=text, **extra)

    def call(self, data="admin:campaigns", *, actor=10, panel=None):
        return CallbackQuery(id="fixture", chat_instance="fixture", data=data,
                             from_user=User(id=actor, is_bot=False, first_name="Fixture"),
                             message=panel if panel is not None else self.panels[actor])

    def button(self, label, *, actor=10):
        for row in self.panels[actor].reply_markup.inline_keyboard:
            for button in row:
                if button.text.startswith(label): return button.callback_data
        raise AssertionError("Button absent: " + label)

    async def click(self, label, **options):
        await self.controller.callback(self.call(self.button(label), **options), self.state)

    async def text(self, text):
        await self.controller.input(self.message(text=text), self.state)

    def rows(self, sql):
        with sqlite3.connect(self.path) as conn: return conn.execute(sql).fetchall()

    async def review(self, *, body="Плановое обслуживание", include="-", exclude="-"):
        await self.controller.callback(self.call(), self.state)
        await self.click("➕ Новый")
        await self.click("Техническое")
        for value in ("Сервисное сообщение", body, include, exclude): await self.text(value)

    async def draft(self):
        await self.review(); await self.click("✅ Сохранить")
        return (await self.api.list_drafts(10)).items[0]

    async def schedule_review(self):
        await self.draft()
        await self.api.observe_private_update(actor_id=1001, chat_id=1001, chat_type="private", is_bot=False)
        await self.click("🕒 Планирование")
        await self.text("2024-02-01T09:00 UTC")

    async def test_source_factory_is_off_and_cannot_supply_policy_from_boolean(self):
        controller = ui.create_campaign_owner_ui(self.db, self.settings, clock=lambda: self.now)
        self.assertFalse(controller.enabled); self.assertFalse(controller.api._ready())
        await controller.callback(self.call(), self.state)
        self.assertIn("выключен", self.rendered[-1][0])
        with self.assertRaises(AssertionError): self.button("➕ Новый")
        self.controller = ui.create_campaign_owner_ui(self.db, self.settings, enabled=True, clock=lambda: self.now)
        await self.draft(); await self.click("🕒 Планирование")
        self.assertEqual(self.rows("SELECT count(*) FROM service_campaign_jobs"), [(0,)])
        self.assertEqual(self.rows("SELECT count(*) FROM service_campaign_revisions"), [(0,)])
        self.assertFalse(self.controller.api._ready())

    async def test_create_preview_estimate_and_back_have_no_delivery(self):
        draft = await self.draft()
        self.assertEqual((await self.api.get_draft(10, draft.id)).body, "Плановое обслуживание")
        self.assertIn("Локальный предпросмотр", self.rendered[-1][0])
        await self.click("👥 Оценить")
        self.assertIn("Разрешено доставить: 0", self.rendered[-1][0])
        await self.click("⬅ Черновик"); await self.click("⬅ Черновики")
        self.assertIn("Черновики · 1", self.rendered[-1][0])
        self.assertEqual(self.rows("SELECT count(*) FROM service_campaign_attempts"), [(0,)])
        self.assertTrue(all(options["parse_mode"] is None for _, options in self.rendered))

    async def test_new_form_cancel_returns_to_actual_home_parent(self):
        await self.controller.callback(self.call(), self.state); await self.click("➕ Новый")
        await self.click("✖ Отмена")
        self.assertIn("📣 Сервисные сообщения", self.rendered[-1][0])
        self.assertIsNone(await self.state.get_state())
        self.assertEqual((await self.api.list_drafts(10)).total, 0)

    async def test_replayed_save_and_forged_callback_cannot_duplicate_or_send(self):
        await self.review(); data = self.button("✅ Сохранить"); panel = self.panels[10]
        await asyncio.gather(*[self.controller.callback(self.call(data, panel=panel), self.state) for _ in range(2)])
        self.assertEqual((await self.api.list_drafts(10)).total, 1)
        await self.controller.callback(self.call("admin:campaigns:" + "0" * 16), self.state)
        self.assertEqual(self.rows("SELECT count(*) FROM service_campaign_jobs"), [(0,)])
        self.assertIsNone(required_role_for_callback("admin:campaigns:send:1001"))

    async def test_group_wrong_actor_and_human_panel_are_rejected_before_data_reads(self):
        with patch.object(self.api, "list_drafts", new=AsyncMock()) as read:
            for panel in (self.message(panel=True, kind="group", chat_id=-100),
                          self.message(panel=True, chat_id=20), self.message(panel=False)):
                await self.controller.callback(self.call(panel=panel), self.state)
            read.assert_not_awaited()
        self.assertEqual(self.rendered, [])

    async def test_nonowner_current_role_cannot_use_ui_or_fsm(self):
        with patch.object(self.db, "get_administrator", return_value=SimpleNamespace(enabled=True, role="read_only")):
            await self.controller.callback(self.call(actor=30), self.state)
            self.assertEqual(self.rendered, [])
        await self.review(); data = self.button("✅ Сохранить")
        self.settings.admin_telegram_ids = (20,)
        await self.controller.callback(self.call(data), self.state)
        self.assertEqual((await self.api.list_drafts(10)).total, 0)

    async def test_confirmation_is_bound_to_owner_chat_message_and_visible_keyboard(self):
        await self.review(); data = self.button("✅ Сохранить"); panel = self.panels[10]
        for event in (self.call(data, actor=20), self.call(data, panel=panel.model_copy(update={"message_id": 78})),
                      self.call(data, panel=panel.model_copy(update={"reply_markup": None}))):
            await self.controller.callback(event, self.state)
        self.assertEqual((await self.api.list_drafts(10)).total, 0)

    async def test_expired_or_clock_regressed_tokens_never_mutate(self):
        for offset in (91, -1):
            self.now = 1704067200
            await self.review(); data = self.button("✅ Сохранить")
            self.now += offset
            await self.controller.callback(self.call(data), self.state)
        self.assertEqual((await self.api.list_drafts(10)).total, 0)

    async def test_stale_edit_preserves_concurrent_revision(self):
        draft = await self.draft(); await self.click("✏ Изменить"); await self.click("Техническое")
        for value in ("Новая тема", "Новый текст", "-", "-"): await self.text(value)
        await self.api.edit_draft(10, draft.id, expected_revision=1, category="technical", subject="Другой редактор", body="Сохранённый текст")
        await self.click("✅ Сохранить")
        current = await self.api.get_draft(10, draft.id)
        self.assertEqual((current.revision, current.subject), (2, "Другой редактор"))
        self.assertIn("изменился", self.rendered[-1][0])

    async def test_edit_success_keeps_identity_and_increments_revision_only(self):
        draft = await self.draft(); await self.click("✏ Изменить"); await self.click("О тарифе")
        for value in ("Новый тариф", "Условия сервиса изменились", "-", "-"): await self.text(value)
        await self.click("✅ Сохранить")
        current = await self.api.get_draft(10, draft.id)
        self.assertEqual((current.id, current.revision, current.category, current.subject),
                         (draft.id, 2, "tariff", "Новый тариф"))
        self.assertEqual((await self.api.list_drafts(10)).total, 1)

    async def test_editor_off_revokes_previously_visible_save(self):
        await self.review(); data = self.button("✅ Сохранить")
        self.controller.enabled = False
        await self.controller.callback(self.call(data), self.state)
        self.assertEqual((await self.api.list_drafts(10)).total, 0)

    async def test_authorization_failure_is_closed_and_does_not_expose_details(self):
        with patch.object(ui, "authorize_callback", side_effect=OSError("private-auth-detail")):
            await self.controller.callback(self.call(), self.state)
        self.assertEqual(self.rendered, [])
        with patch.object(ui, "authorize_message", side_effect=OSError("private-auth-detail")):
            await self.controller.input(self.message(text="fixture"), self.state)
        self.assertEqual(self.rendered, [])

    async def test_unknown_save_is_redacted_and_replay_is_not_retried(self):
        await self.review(); data = self.button("✅ Сохранить"); panel = self.panels[10]
        with patch.object(self.api, "create_draft", side_effect=CampaignOutcomeUnknown("private-database")) as create:
            await self.controller.callback(self.call(data), self.state)
            self.assertIn("Исход не подтверждён", self.rendered[-1][0])
            self.assertNotIn("private-database", self.rendered[-1][0])
            await self.controller.callback(self.call(data, panel=panel), self.state)
            create.assert_awaited_once()

    async def test_forged_expired_or_other_section_fsm_cannot_create_draft(self):
        await self.review(); form = (await self.state.get_data())["campaign"]
        form["actor"] = 20; await self.state.update_data(campaign=form)
        await self.text("Другая тема")
        self.assertEqual((await self.api.list_drafts(10)).total, 0)
        await self.controller.callback(self.call(), self.state); await self.click("➕ Новый"); await self.click("Техническое")
        panel = self.panels[10].model_copy(update={"reply_markup": InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅ Система", callback_data="admin:section:system")]])})
        register_panel_message(10, panel)
        await self.text("Не ввод кампании")
        self.assertIsNone(await self.state.get_state())
        self.assertEqual((await self.api.list_drafts(10)).total, 0)

    async def test_groups_markup_links_media_and_large_inputs_fail_closed(self):
        for invalid in ("1,2,0", "1," * 60, "1,2,@unknown", "https://example.invalid"):
            await self.review(include=invalid)
            self.assertEqual((await self.api.list_drafts(10)).total, 0)
        await self.review(body="<b>markup</b>")
        self.assertEqual((await self.api.list_drafts(10)).total, 0)

    async def test_long_emoji_preview_is_explicitly_truncated_without_parse_mode(self):
        await self.review(body="🟢" * 3000)
        self.assertIn("показан фрагмент", self.rendered[-1][0])
        for text, options in self.rendered:
            self.assertLessEqual(len(text.encode("utf-16-le")) // 2, 3800)
            self.assertIsNone(options["parse_mode"])
        await self.click("✅ Сохранить"); await self.click("🕒 Планирование")
        self.assertEqual(self.rows("SELECT count(*) FROM service_campaign_jobs"), [(0,)])
        self.assertEqual(self.rows("SELECT count(*) FROM service_campaign_revisions"), [(0,)])

    async def test_capacity_and_expired_form_keep_fixed_exit_without_mutation(self):
        with patch.object(ui, "MAX_TOKENS", 0):
            await self.controller.callback(self.call(), self.state)
        self.assertEqual(self.panels[10].reply_markup.inline_keyboard[0][0].callback_data, "admin:section:system")
        await self.controller.callback(self.call(), self.state); await self.click("➕ Новый"); await self.click("Техническое")
        self.now += ui.FORM_TTL + 1; await self.text("Просроченная тема")
        self.assertIsNone(await self.state.get_state())
        self.assertEqual((await self.api.list_drafts(10)).total, 0)

    async def test_media_input_and_unknown_group_cannot_be_saved(self):
        await self.controller.callback(self.call(), self.state); await self.click("➕ Новый"); await self.click("Техническое")
        await self.controller.input(self.message(text=None), self.state)
        self.assertEqual((await self.api.list_drafts(10)).total, 0)
        await self.review(include="9999"); await self.click("✅ Сохранить")
        self.assertEqual((await self.api.list_drafts(10)).total, 0)

    async def test_schedule_confirmation_has_one_snapshot_and_no_transport_attempts(self):
        await self.schedule_review(); data = self.button("✅ Подтвердить планирование"); panel = self.panels[10]
        self.assertIn("MSK", self.rendered[-1][0])
        await asyncio.gather(*[self.controller.callback(self.call(data, panel=panel), self.state) for _ in range(2)])
        self.assertEqual(self.rows("SELECT state FROM service_campaign_jobs"), [("scheduled",)])
        self.assertEqual(self.rows("SELECT count(*) FROM service_campaign_recipients"), [(1,)])
        self.assertEqual(self.rows("SELECT count(*) FROM service_campaign_attempts"), [(0,)])

    async def test_category_revoked_after_review_blocks_before_snapshot(self):
        await self.schedule_review(); self.policy.allowed = False
        await self.click("✅ Подтвердить планирование")
        self.assertEqual(self.rows("SELECT count(*) FROM service_campaign_jobs"), [(0,)])
        self.assertEqual(self.rows("SELECT count(*) FROM service_campaign_revisions"), [(0,)])

    async def test_stale_schedule_and_invalid_dst_never_create_jobs(self):
        await self.schedule_review()
        draft = (await self.api.list_drafts(10)).items[0]
        await self.api.edit_draft(10, draft.id, expected_revision=1, category="technical", subject="Новое", body="Изменено")
        await self.click("✅ Подтвердить планирование")
        self.assertEqual(self.rows("SELECT count(*) FROM service_campaign_jobs"), [(0,)])
        await self.controller.callback(self.call(), self.state); await self.click("📄 Черновики"); await self.click("📄 #")
        await self.click("🕒 Планирование"); await self.text("2024-03-10T02:30 America/New_York")
        self.assertEqual(self.rows("SELECT count(*) FROM service_campaign_jobs"), [(0,)])

    async def test_draft_list_is_bounded_and_keeps_parent(self):
        for index in range(10):
            await self.api.create_draft(10, category="service", subject=f"Сообщение {index}", body="Текст")
        await self.controller.callback(self.call(), self.state); await self.click("📄 Черновики")
        rows = self.panels[10].reply_markup.inline_keyboard
        self.assertEqual(sum(button.text.startswith("📄 #") for row in rows for button in row), 8)
        await self.click("➡ Следующие")
        self.assertEqual(sum(button.text.startswith("📄 #") for row in self.panels[10].reply_markup.inline_keyboard for button in row), 2)
        await self.click("⬅ Предыдущие"); await self.click("⬅ Сервисные сообщения")
        self.assertIn("📣 Сервисные сообщения", self.rendered[-1][0])

    async def test_cancel_is_two_step_and_remains_available_when_editor_is_off(self):
        await self.schedule_review(); await self.click("✅ Подтвердить планирование")
        self.controller.enabled = False
        await self.click("⛔ Отменить кампанию")
        self.assertEqual(self.rows("SELECT state FROM service_campaign_jobs"), [("scheduled",)])
        await self.click("✖ Отмена")
        self.assertEqual(self.rows("SELECT state FROM service_campaign_jobs"), [("scheduled",)])
        await self.click("⛔ Отменить кампанию"); await self.click("⛔ Отменить кампанию")
        self.assertEqual(self.rows("SELECT state FROM service_campaign_jobs"), [("cancelled",)])

    async def test_isolated_queue_to_existing_bot_receipt_finishes_durable_intent(self):
        await self.schedule_review(); await self.click("✅ Подтвердить планирование")
        self.now = 1706778000
        response = self.message(actor=1001, panel=True).model_copy(update={"message_id": 8})
        bot = AsyncMock(return_value=response); bot.id = 2000
        transport = CampaignBotTransport(bot, authorize_envelope=AsyncMock(return_value=True))
        worker = CampaignWorker(self.api, transport=transport)
        await worker.tick()
        self.assertEqual(self.rows("SELECT state FROM service_campaign_attempts"), [("sent",)])
        self.assertEqual(self.rows("SELECT state FROM service_campaign_jobs"), [("completed",)])
        await worker.tick(); bot.assert_awaited_once()
        self.assertEqual(bot.await_args.args[0].chat_id, 1001)

    async def test_isolated_http500_with_retry_after_is_unknown_and_never_replayed(self):
        import json
        await self.schedule_review(); await self.click("✅ Подтвердить планирование")
        self.now = 1706778000
        session = CampaignAwareSession()
        async def rejected(method, **kwargs):
            return session.check_response(None, method, 500, json.dumps({"ok": False, "error_code": 500,
                "description": "private-upstream", "parameters": {"retry_after": 2}}))
        bot = AsyncMock(side_effect=rejected); bot.id = 2000
        try:
            worker = CampaignWorker(self.api, transport=CampaignBotTransport(bot, authorize_envelope=AsyncMock(return_value=True)))
            await worker.tick(); await worker.tick()
            self.assertEqual(self.rows("SELECT state FROM service_campaign_attempts"), [("unknown",)])
            self.assertEqual(self.rows("SELECT state FROM service_campaign_jobs"), [("paused",)])
            restarted = CampaignWorker(self.api, transport=CampaignBotTransport(bot, authorize_envelope=AsyncMock(return_value=True)))
            await restarted.tick(); bot.assert_awaited_once()
        finally:
            await session.close()

    async def test_isolated_verified_http429_obeys_durable_retry_and_receipt(self):
        import json
        await self.schedule_review(); await self.click("✅ Подтвердить планирование")
        self.now = 1706778000
        session = CampaignAwareSession(); calls = 0
        async def receive(method, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return session.check_response(None, method, 429, json.dumps({"ok": False, "error_code": 429,
                    "description": "fixture", "parameters": {"retry_after": 2}}))
            return self.message(actor=1001, panel=True)
        bot = AsyncMock(side_effect=receive); bot.id = 2000
        try:
            worker = CampaignWorker(self.api, transport=CampaignBotTransport(bot, authorize_envelope=AsyncMock(return_value=True)))
            await worker.tick()
            self.assertEqual(self.rows("SELECT state FROM service_campaign_attempts"), [("rate_limited",)])
            await worker.tick(); self.assertEqual(bot.await_count, 1)
            self.now += 3; await worker.tick()
            self.assertEqual(self.rows("SELECT state FROM service_campaign_attempts ORDER BY id"), [("rate_limited",), ("sent",)])
            self.assertEqual(bot.await_count, 2)
        finally:
            await session.close()

    async def test_isolated_blocked_receipt_is_terminal_and_observation_never_unblocks(self):
        import json
        await self.schedule_review(); await self.click("✅ Подтвердить планирование")
        self.now = 1706778000
        session = CampaignAwareSession()
        async def rejected(method, **kwargs):
            return session.check_response(None, method, 403, json.dumps({"ok": False, "error_code": 403,
                "description": "Forbidden: bot was blocked by the user"}))
        bot = AsyncMock(side_effect=rejected); bot.id = 2000
        try:
            worker = CampaignWorker(self.api, transport=CampaignBotTransport(bot, authorize_envelope=AsyncMock(return_value=True)))
            await worker.tick()
            self.assertEqual(self.rows("SELECT state FROM service_campaign_recipients"), [("unavailable",)])
            blocked = self.rows("SELECT blocked_at FROM service_campaign_contacts")[0][0]
            self.assertGreater(blocked, 0)
            observer = CampaignPrivateObserver(self.api, enabled=True, authorize_update=AsyncMock(return_value=True))
            self.assertTrue(await observer.observe(self.message(actor=1001)))
            self.assertEqual(self.rows("SELECT blocked_at FROM service_campaign_contacts"), [(blocked,)])
            await worker.tick(); bot.assert_awaited_once()
        finally:
            await session.close()

    async def test_no_global_menu_registration_or_new_slash_handler(self):
        import ast
        from telegram_commands import COMMANDS
        root = Path(__file__).resolve().parents[1]
        for name in ("app_runtime.py", "bot.py", "client_access.py", "admin_navigation.py"):
            tree = ast.parse((root / name).read_text())
            self.assertFalse(any(isinstance(node, ast.ImportFrom) and node.module == "campaign_owner_ui" for node in ast.walk(tree)))
        self.assertEqual(required_role_for_callback("admin:campaigns"), "owner")
        self.assertEqual(required_role_for_callback("admin:campaigns:" + "a" * 16), "owner")
        self.assertFalse(any(item.source == "campaign_owner_ui.py" for item in COMMANDS))
        self.assertNotIn("campaigns", {item.name for item in COMMANDS})

    async def test_isolated_dispatcher_routes_callback_and_fsm_without_network(self):
        from aiogram import Bot, Dispatcher
        from aiogram.client.session.base import BaseSession
        from aiogram.types import Update
        class NoNetwork(BaseSession):
            calls = 0
            async def close(self): pass
            async def make_request(self, bot, method, timeout=None):
                self.calls += 1
                raise AssertionError("No Telegram request is allowed")
            async def stream_content(self, *args, **kwargs):
                raise AssertionError("No Telegram download is allowed")
                yield b""
        session = NoNetwork()
        bot = Bot("2000:synthetic-tests", session=session)
        dispatcher = Dispatcher(storage=self.storage)
        dispatcher.include_router(self.controller.router)
        try:
            await dispatcher.feed_update(bot, Update(update_id=1, callback_query=self.call()))
            await dispatcher.feed_update(bot, Update(update_id=2, callback_query=self.call(self.button("➕ Новый"))))
            await dispatcher.feed_update(bot, Update(update_id=3, callback_query=self.call(self.button("Техническое"))))
            self.assertEqual(await self.state.get_state(), ui.CampaignInput.value.state)
            await dispatcher.feed_update(bot, Update(update_id=4, message=self.message(text="Тема из FSM")))
            self.assertIn("Введите текст", self.rendered[-1][0])
            self.assertEqual(session.calls, 0)
            self.assertEqual((await self.api.list_drafts(10)).total, 0)
        finally:
            await session.close()
