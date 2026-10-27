import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
import uuid

from aiogram.exceptions import (
    TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter, TelegramServerError,
)
from aiogram.methods import SendMessage
from aiogram.types import Chat, Message, User

from campaign_telegram import (
    CampaignAwareSession, CampaignBotTransport, CampaignPrivateObserver,
    _CampaignSendMessage, _VerifiedCampaign429,
)
from db import Database, UserRecord
from service_campaign_delivery import CampaignEnvelope
from service_campaigns import CampaignDenied, CampaignInvalid, ServiceCampaigns


def message(actor=1001, *, chat_id=None, kind="private", is_bot=False, **kwargs):
    return Message(message_id=7, date=datetime.now(timezone.utc),
                   chat=Chat(id=actor if chat_id is None else chat_id, type=kind),
                   from_user=User(id=actor, is_bot=is_bot, first_name="Fixture"), **kwargs)


def envelope(**changes):
    fields = dict(chat_id=1001, subject="Сервисное сообщение", body="Плановое обслуживание",
                  operation_id=str(uuid.uuid4()))
    fields.update(changes)
    return CampaignEnvelope(**fields)


class FakeBot(AsyncMock):
    id = 2000


def receipt(*args, **kwargs):
    return message(*args, **kwargs).model_copy(update={
        "from_user": User(id=2000, is_bot=True, first_name="Fixture bot")})


class CampaignTelegramTransport949Tests(unittest.IsolatedAsyncioTestCase):
    async def test_default_missing_or_nontrue_admission_never_calls_bot(self):
        bot = FakeBot()
        for admission in (None, AsyncMock(return_value=False), AsyncMock(return_value="owner"),
                          AsyncMock(side_effect=RuntimeError("private-policy-details"))):
            with self.assertRaises(CampaignDenied) as error:
                await CampaignBotTransport(bot, authorize_envelope=admission).send(envelope())
            self.assertNotIn("private-policy", str(error.exception))
        bot.assert_not_awaited()

    async def test_existing_bot_one_shot_has_no_paid_markup_links_or_alternate_target(self):
        bot = FakeBot(return_value=receipt())
        value = envelope()
        result = await CampaignBotTransport(bot, authorize_envelope=AsyncMock(return_value=True)).send(value)
        self.assertEqual((result.kind, result.chat_id, result.message_id), ("confirmed", 1001, 7))
        bot.assert_awaited_once()
        method = bot.await_args.args[0]
        self.assertIsInstance(method, _CampaignSendMessage)
        self.assertEqual(method.chat_id, value.chat_id)
        self.assertEqual(method.text, value.subject + "\n\n" + value.body)
        self.assertIsNone(method.parse_mode)
        self.assertIsNone(method.entities)
        self.assertTrue(method.link_preview_options.is_disabled)
        self.assertFalse(method.allow_paid_broadcast)
        self.assertTrue(method.protect_content)
        for field in ("reply_markup", "reply_parameters", "business_connection_id", "message_thread_id",
                      "direct_messages_topic_id", "receiver_user_id", "callback_query_id"):
            self.assertIsNone(getattr(method, field))
        self.assertEqual(bot.await_args.kwargs, {"request_timeout": 8})

    async def test_invalid_envelopes_fail_before_admission_and_transport(self):
        bot, admission = FakeBot(), AsyncMock(return_value=True)
        for changes in ({"chat_id": True}, {"chat_id": -1}, {"chat_id": "1001"},
                        {"operation_id": str(uuid.uuid1())}, {"operation_id": "bad"},
                        {"body": "https://example.invalid"}, {"subject": "<b>Text</b>"},
                        {"parse_mode": "HTML"}, {"link_preview": True},
                        {"body": "🟢" * 3000}):
            with self.subTest(changes=list(changes)), self.assertRaises(CampaignInvalid):
                await CampaignBotTransport(bot, authorize_envelope=admission).send(envelope(**changes))
        bot.assert_not_awaited(); admission.assert_not_awaited()

    async def test_confirmed_403_and_exact_400_chat_missing_are_terminal_unavailable(self):
        method = SendMessage(chat_id=1001, text="fixture")
        errors = [TelegramForbiddenError(method=method, message="private-forbidden"),
                  TelegramBadRequest(method=method, message="Bad Request: chat not found")]
        for error in errors:
            async def rejected(actual_method, **kwargs):
                raise type(error)(method=actual_method, message=error.message)
            bot = FakeBot(side_effect=rejected)
            result = await CampaignBotTransport(bot, authorize_envelope=AsyncMock(return_value=True)).send(envelope())
            self.assertEqual(result.kind, "unavailable")
            self.assertNotIn("private-forbidden", repr(result))
            bot.assert_awaited_once()

    async def test_unproven_retry_after_5xx_and_network_are_unknown_and_stop_adapter(self):
        method = SendMessage(chat_id=1001, text="fixture")
        errors = [TelegramRetryAfter(method=method, message="retry", retry_after=2),
                  TelegramServerError(method=method, message="private-server"),
                  TelegramBadRequest(method=method, message="private-validation"),
                  TimeoutError("private-timeout"), OSError("private-network")]
        for error in errors:
            bot = FakeBot(side_effect=error)
            adapter = CampaignBotTransport(bot, authorize_envelope=AsyncMock(return_value=True))
            result = await adapter.send(envelope())
            self.assertEqual(result.kind, "unknown")
            self.assertNotIn("private", repr(result))
            with self.assertRaises(CampaignDenied):
                await adapter.send(envelope())
            bot.assert_awaited_once()

    async def test_only_verified_http429_can_be_safe_rate_limited(self):
        session = CampaignAwareSession()
        method = _CampaignSendMessage(chat_id=1001, text="fixture")
        raw = json.dumps({"ok": False, "error_code": 429, "description": "private-detail",
                          "parameters": {"retry_after": 17}})
        try:
            with self.assertRaises(_VerifiedCampaign429) as error:
                session.check_response(None, method, 429, raw)
            async def rejected(actual_method, **kwargs):
                return session.check_response(None, actual_method, 429, raw)
            bot = FakeBot(side_effect=rejected)
            result = await CampaignBotTransport(bot, authorize_envelope=AsyncMock(return_value=True)).send(envelope())
            self.assertEqual((result.kind, result.retry_after), ("rate_limited", 17))
            self.assertNotIn("private-detail", str(error.exception))
        finally:
            await session.close()

    async def test_rejection_for_a_different_method_never_authorizes_retry_or_unavailable(self):
        other = _CampaignSendMessage(chat_id=1002, text="fixture")
        for error in (_VerifiedCampaign429(method=other, message="fixture", retry_after=2),
                      TelegramForbiddenError(method=other, message="Forbidden: bot was blocked by the user")):
            bot = FakeBot(side_effect=error)
            result = await CampaignBotTransport(bot, authorize_envelope=AsyncMock(return_value=True)).send(envelope())
            self.assertEqual(result.kind, "unknown")

    async def test_retry_after_on_other_status_or_noncampaign_method_is_not_verified(self):
        session = CampaignAwareSession()
        raw = json.dumps({"ok": False, "error_code": 500, "description": "fixture",
                          "parameters": {"retry_after": 2}})
        try:
            for code in (200, 403, 500, 503):
                with self.assertRaises(TelegramRetryAfter) as error:
                    session.check_response(None, _CampaignSendMessage(chat_id=1001, text="fixture"), code, raw)
                self.assertNotIsInstance(error.exception, _VerifiedCampaign429)
            with self.assertRaises(TelegramRetryAfter) as error:
                session.check_response(None, SendMessage(chat_id=1001, text="fixture"), 429,
                                       raw.replace('"error_code": 500', '"error_code": 429'))
            self.assertNotIsInstance(error.exception, _VerifiedCampaign429)
        finally:
            await session.close()

    async def test_invalid_rate_limit_json_is_never_a_verified_rejection(self):
        session = CampaignAwareSession()
        try:
            for changes in ({"retry_after": True}, {"retry_after": 0}, {"retry_after": 3601},
                            {"retry_after": "2"}):
                raw = json.dumps({"ok": False, "error_code": 429, "description": "fixture",
                                  "parameters": changes})
                try:
                    session.check_response(None, _CampaignSendMessage(chat_id=1001, text="fixture"), 429, raw)
                except Exception as error:
                    self.assertNotIsInstance(error, _VerifiedCampaign429)
        finally:
            await session.close()

    async def test_wrong_or_invalid_receipt_never_confirms(self):
        for reply in (receipt(chat_id=1002), receipt(kind="group", chat_id=-100), object(),
                      message(), receipt().model_copy(update={"from_user": User(id=3000, is_bot=True, first_name="Other")}),
                      receipt().model_copy(update={"message_id": True})):
            adapter = CampaignBotTransport(FakeBot(return_value=reply), authorize_envelope=AsyncMock(return_value=True))
            self.assertEqual((await adapter.send(envelope())).kind, "unknown")
            with self.assertRaises(CampaignDenied):
                await adapter.send(envelope())

    async def test_noncooperative_timeout_is_bounded_unknown_and_late_reply_never_replays(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def stubborn(*args, **kwargs):
            entered.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                await release.wait()
            return receipt()
        bot = FakeBot(side_effect=stubborn)
        adapter = CampaignBotTransport(bot, authorize_envelope=AsyncMock(return_value=True))
        with patch("campaign_telegram.REQUEST_TIMEOUT", 0.01):
            result = await asyncio.wait_for(adapter.send(envelope()), 0.5)
        self.assertTrue(entered.is_set())
        self.assertEqual(result.kind, "unknown")
        with self.assertRaises(CampaignDenied):
            await adapter.send(envelope())
        release.set(); await asyncio.sleep(0); await asyncio.sleep(0)
        self.assertEqual(result.kind, "unknown"); bot.assert_awaited_once()

    async def test_concurrent_transport_calls_never_fan_out(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def pending(*args, **kwargs):
            entered.set(); await release.wait(); return receipt()
        bot = FakeBot(side_effect=pending)
        adapter = CampaignBotTransport(bot, authorize_envelope=AsyncMock(return_value=True))
        first = asyncio.create_task(adapter.send(envelope()))
        await entered.wait()
        with self.assertRaises(CampaignDenied):
            await adapter.send(envelope())
        release.set(); self.assertEqual((await first).kind, "confirmed"); bot.assert_awaited_once()

    async def test_cancellation_never_turns_uncertain_send_into_safe_failure(self):
        entered = asyncio.Event()
        async def pending(*args, **kwargs):
            entered.set(); await asyncio.Event().wait()
        bot = FakeBot(side_effect=pending)
        adapter = CampaignBotTransport(bot, authorize_envelope=AsyncMock(return_value=True))
        task = asyncio.create_task(adapter.send(envelope()))
        await entered.wait(); task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        with self.assertRaises(CampaignDenied):
            await adapter.send(envelope())
        bot.assert_awaited_once()


class CampaignPrivateObserver949Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "fixture.sqlite3"
        self.db = Database(str(self.path)); await self.db.init()
        await self.db.put(UserRecord(1001, "fixture@example.invalid", "synthetic-sub", 0, 1))
        self.api = ServiceCampaigns(self.db, clock=lambda: 1000)

    async def asyncTearDown(self):
        self.tmp.cleanup()

    def contacts(self):
        with sqlite3.connect(self.path) as conn:
            return conn.execute("SELECT telegram_id,first_seen_at,last_seen_at,source,blocked_at FROM service_campaign_contacts").fetchall()

    async def test_defaults_and_missing_or_nontrue_admission_do_not_collect(self):
        for enabled, admit in ((False, AsyncMock(return_value=True)), ("true", AsyncMock(return_value=True)),
                               (True, None), (True, AsyncMock(return_value="allowed"))):
            self.assertFalse(await CampaignPrivateObserver(self.api, enabled=enabled, authorize_update=admit).observe(message()))
        self.assertEqual(self.contacts(), [])

    async def test_only_existing_allowed_private_human_produces_minimal_proof(self):
        observer = CampaignPrivateObserver(self.api, enabled=True, authorize_update=AsyncMock(return_value=True))
        self.assertTrue(await observer.observe(message(text="not persisted")))
        self.assertEqual(self.contacts(), [(1001, 1000, 1000, "private_update", 0)])
        self.assertFalse(await observer.observe(message(actor=2002)))
        self.assertEqual(len(self.contacts()), 1)

    async def test_group_wrong_identity_bot_forward_and_sender_chat_are_rejected(self):
        service, admission = AsyncMock(), AsyncMock(return_value=True)
        observer = CampaignPrivateObserver(service, enabled=True, authorize_update=admission)
        wrong = [object(), message(chat_id=1002), message(chat_id=-100, kind="group"),
                 message(is_bot=True), message(sender_chat=Chat(id=-100, type="channel")),
                 message(via_bot=User(id=2000, is_bot=True, first_name="Fixture")),
                 message(forward_origin={"type": "hidden_user", "date": 1, "sender_user_name": "Fixture"})]
        for event in wrong:
            self.assertFalse(await observer.observe(event))
        admission.assert_not_awaited(); service.observe_private_update.assert_not_awaited()

    async def test_admission_and_store_errors_are_redacted_without_client_failure(self):
        observer = CampaignPrivateObserver(self.api, enabled=True,
                                           authorize_update=AsyncMock(side_effect=OSError("private-policy")))
        self.assertFalse(await observer.observe(message()))
        with patch.object(self.api, "observe_private_update", side_effect=OSError("private-database")):
            observer = CampaignPrivateObserver(self.api, enabled=True, authorize_update=AsyncMock(return_value=True))
            self.assertFalse(await observer.observe(message()))
        self.assertEqual(self.contacts(), [])

    async def test_noncooperative_admission_cannot_block_or_accumulate_tasks(self):
        release = asyncio.Event()
        async def stubborn(value):
            try:
                await release.wait()
            except asyncio.CancelledError:
                await release.wait()
            return True
        admission = AsyncMock(side_effect=stubborn)
        observer = CampaignPrivateObserver(self.api, enabled=True, authorize_update=admission)
        with patch("campaign_telegram.ADMISSION_TIMEOUT", 0.01):
            self.assertFalse(await asyncio.wait_for(observer.observe(message()), 0.5))
        for _ in range(20):
            self.assertFalse(await observer.observe(message()))
        admission.assert_awaited_once(); self.assertEqual(self.contacts(), [])
        release.set(); await asyncio.sleep(0); await asyncio.sleep(0)

    async def test_no_runtime_import_or_registration_was_added(self):
        import ast
        root = Path(__file__).resolve().parents[1]
        for filename in ("app_runtime.py", "bot.py", "client_access.py"):
            tree = ast.parse((root / filename).read_text())
            self.assertFalse(any(isinstance(node, ast.ImportFrom) and node.module == "campaign_telegram"
                                 for node in ast.walk(tree)))
