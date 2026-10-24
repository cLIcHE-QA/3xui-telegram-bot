"""#887 D2b: приватное Bot API подтверждение, только синтетические Update."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiohttp.test_utils import TestClient, TestServer

from subscription_page_telegram_approval import (
    MAX_PER_OWNER, MAX_PROMPTS, StandaloneTelegramApproval,
    build_standalone_telegram_router,
)
from subscription_page_standalone import PENDING_COOKIE, SESSION_COOKIE, create_standalone_pilot

NOW = 1_800_000_000
OWNER = 100_001
OTHER = 100_002
HOST = "web.example.invalid"
ORIGIN = "https://" + HOST
PREFIX = "/api/subpage/v1/auth/standalone"


def user(identifier=OWNER, *, bot=False):
    return SimpleNamespace(id=identifier, is_bot=bot)


def chat(identifier=OWNER, kind="private"):
    return SimpleNamespace(id=identifier, type=kind)


class TelegramApprovalTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = float(NOW)
        self.service = SimpleNamespace(
            profile=AsyncMock(return_value=SimpleNamespace(exists=True))
        )
        self.flags = SimpleNamespace(
            snapshot=AsyncMock(return_value=SimpleNamespace(portal_enabled=True))
        )
        self.pilot = create_standalone_pilot(
            https_origin=ORIGIN, customer_service=self.service,
            feature_flags=self.flags, pilot_ids=frozenset({OWNER}),
            now=lambda: self.clock,
        )
        self.client = TestClient(TestServer(self.pilot.app))
        await self.client.start_server()
        self.adapter = StandaloneTelegramApproval(self.pilot)

    async def asyncTearDown(self):
        await self.client.close()

    async def challenge(self):
        async with self.client.post(
            PREFIX + "/start", json={}, headers={"Host": HOST, "Origin": ORIGIN},
        ) as result:
            self.assertEqual(result.status, 200)
            code = (await result.json())["challenge"]
            cookie = f"{PENDING_COOKIE}={result.cookies[PENDING_COOKIE].value}"
            return code, cookie

    def incoming(self, *, text, actor=OWNER, chat_id=None, kind="private",
                 forwarded=False, sender_chat=None, bot=False, message_id=999):
        obj = SimpleNamespace(
            text=text, from_user=user(actor, bot=bot),
            chat=chat(actor if chat_id is None else chat_id, kind),
            sender_chat=sender_chat, forward_origin="forwarded" if forwarded else None,
            answer=AsyncMock(return_value=SimpleNamespace(message_id=message_id)),
        )
        return obj

    def callback(self, nonce, *, confirmed=True, actor=OWNER, chat_id=None,
                 kind="private", message_id=999, callback_message=True):
        msg = SimpleNamespace(
            chat=chat(actor if chat_id is None else chat_id, kind),
            message_id=message_id, edit_reply_markup=AsyncMock(),
        ) if callback_message else None
        return SimpleNamespace(
            data=f"d2bs:{'yes' if confirmed else 'no'}:{nonce}",
            from_user=user(actor), message=msg, answer=AsyncMock(),
        )

    async def prompt(self, code):
        message = self.incoming(text="/web_login " + code)
        await self.adapter.handle_message(message)
        self.assertEqual(message.answer.await_count, 1)
        self.assertEqual(len(self.adapter.prompts), 1)
        nonce = next(iter(self.adapter.prompts))
        args = message.answer.await_args
        self.assertIn("Подтвердить", args.args[0])
        self.assertIn("Только" if False else "ТОЛЬКО", args.args[0])
        self.assertIn(ORIGIN, args.args[0])
        self.assertNotIn(code, args.args[0])  # Only last 4, not full challenge.
        self.assertEqual(args.kwargs["reply_markup"].inline_keyboard[0][0].callback_data,
                         f"d2bs:yes:{nonce}")
        return nonce

    async def test_router_is_only_constructed_not_automatically_registered(self):
        router = build_standalone_telegram_router(self.pilot)
        self.assertEqual(router.name, "d2b_standalone_approval")
        self.assertEqual(len(router.message.handlers), 1)
        self.assertEqual(len(router.callback_query.handlers), 1)
        self.assertEqual(len(self.pilot.app.router.routes()), 5)
        self.assertNotIn("d2b", self.pilot.app.keys())

    async def test_private_bot_confirmation_is_required_to_issue_browser_session(self):
        code, binding = await self.challenge()
        nonce = await self.prompt(code)
        async with self.client.post(PREFIX + "/complete", json={"challenge": code},
                                    headers={"Host": HOST, "Origin": ORIGIN,
                                             "Cookie": binding}) as result:
            self.assertEqual(result.status, 202)
            self.assertNotIn(SESSION_COOKIE, result.cookies)
        cb = self.callback(nonce)
        await self.adapter.handle_callback(cb)
        cb.answer.assert_awaited_once()
        self.assertIn("Вход подтверждён", cb.answer.await_args.args[0])
        cb.message.edit_reply_markup.assert_awaited_once()
        self.assertNotIn(nonce, self.adapter.prompts)
        async with self.client.post(PREFIX + "/complete", json={"challenge": code},
                                    headers={"Host": HOST, "Origin": ORIGIN,
                                             "Cookie": binding}) as result:
            self.assertEqual(result.status, 200)
            self.assertIn(SESSION_COOKIE, result.cookies)
            self.assertNotIn(code, await result.text())
        await self.adapter.handle_callback(cb)
        self.assertTrue(cb.answer.await_args.kwargs.get("show_alert"))
        self.assertEqual(len(self.pilot.sessions), 1)

    async def test_private_decline_never_confirms_challenge(self):
        code, binding = await self.challenge()
        nonce = await self.prompt(code)
        cb = self.callback(nonce, confirmed=False)
        await self.adapter.handle_callback(cb)
        self.assertFalse(self.pilot.pending[code].approved_owner)
        async with self.client.post(PREFIX + "/complete", json={"challenge": code},
                                    headers={"Host": HOST, "Origin": ORIGIN,
                                             "Cookie": binding}) as r:
            self.assertEqual(r.status, 202)
        self.assertNotIn(nonce, self.adapter.prompts)

    async def test_no_group_forwarded_anonymous_or_foreign_private_command(self):
        code, _ = await self.challenge()
        cases = [
            dict(actor=OWNER, kind="group"),
            dict(actor=OWNER, chat_id=OTHER),
            dict(actor=OWNER, forwarded=True),
            dict(actor=OWNER, sender_chat=chat(OWNER)),
            dict(actor=OWNER, bot=True),
            dict(actor=True), dict(actor=0),
            dict(actor=OTHER),
        ]
        for params in cases:
            with self.subTest(params=params):
                message = self.incoming(text="/web_login " + code, **params)
                await self.adapter.handle_message(message)
                self.assertFalse(self.adapter.prompts)
                if params.get("actor") != OTHER:
                    message.answer.assert_not_awaited()
        self.assertIsNone(self.pilot.pending[code].approved_owner)

    async def test_malformed_content_cannot_mint_prompt(self):
        code, _ = await self.challenge()
        for text in (
            "", "/web_login", "/start " + code,
            "/web_login " + code + " any",
            "/web_login " + code + "\n",
            "/web_login " + code + "?id=100001",
            "/web_login@" + "other_bot " + code,
            "/web_login " + "x" * 200,
        ):
            with self.subTest(text=text[:22]):
                msg = self.incoming(text=text)
                await self.adapter.handle_message(msg)
                self.assertFalse(self.adapter.prompts)
        self.assertIsNone(self.pilot.pending[code].approved_owner)

    async def test_foreign_callback_or_foreign_message_cannot_approve(self):
        code, _ = await self.challenge()
        nonce = await self.prompt(code)
        for cb in [
            self.callback(nonce, actor=OTHER),
            self.callback(nonce, actor=OWNER, chat_id=OTHER),
            self.callback(nonce, kind="supergroup"),
            self.callback(nonce, message_id=10),
            self.callback(nonce, callback_message=False),
            self.callback(nonce, actor=True),
        ]:
            with self.subTest(callback=cb):
                await self.adapter.handle_callback(cb)
                self.assertIsNone(self.pilot.pending[code].approved_owner)
                self.assertIn(nonce, self.adapter.prompts)
        valid = self.callback(nonce)
        await self.adapter.handle_callback(valid)
        self.assertEqual(self.pilot.pending[code].approved_owner, OWNER)

    async def test_expiry_and_replaced_browser_request_are_rejected(self):
        code, binding = await self.challenge()
        nonce = await self.prompt(code)
        self.clock += 181
        cb = self.callback(nonce)
        await self.adapter.handle_callback(cb)
        self.assertTrue(cb.answer.await_args.kwargs.get("show_alert"))
        self.assertIsNone(self.pilot.pending.get(code))
        self.assertNotIn(nonce, self.adapter.prompts)
        code, binding = await self.challenge()
        nonce = await self.prompt(code)
        async with self.client.post(PREFIX + "/cancel", json={"challenge": code},
                                    headers={"Host": HOST, "Origin": ORIGIN,
                                             "Cookie": binding}) as response:
            self.assertEqual(response.status, 200)
        await self.adapter.handle_callback(self.callback(nonce))
        self.assertNotIn(code, self.pilot.pending)

    async def test_owner_feature_and_service_fail_closed(self):
        code, _ = await self.challenge()
        self.flags.snapshot.return_value = SimpleNamespace(portal_enabled=False)
        await self.adapter.handle_message(self.incoming(text="/web_login " + code))
        self.assertFalse(self.adapter.prompts)
        self.flags.snapshot.return_value = SimpleNamespace(portal_enabled=True)
        self.service.profile.side_effect = RuntimeError("private provider data")
        await self.adapter.handle_message(self.incoming(text="/web_login " + code))
        self.assertFalse(self.adapter.prompts)
        self.service.profile.side_effect = None
        nonce = await self.prompt(code)
        self.flags.snapshot.side_effect = RuntimeError("private flag data")
        c = self.callback(nonce)
        await self.adapter.handle_callback(c)
        self.assertTrue(c.answer.await_args.kwargs.get("show_alert"))
        self.assertIsNone(self.pilot.pending[code].approved_owner)

    async def test_send_failure_and_unbound_message_cannot_leave_approvable_prompt(self):
        code, _ = await self.challenge()
        outgoing = self.incoming(text="/web_login " + code)
        outgoing.answer.side_effect = RuntimeError("test transport unavailable")
        with self.assertRaisesRegex(RuntimeError, "test transport"):
            await self.adapter.handle_message(outgoing)
        self.assertFalse(self.adapter.prompts)
        outgoing = self.incoming(text="/web_login " + code, message_id=0)
        await self.adapter.handle_message(outgoing)
        self.assertFalse(self.adapter.prompts)

    async def test_bounded_prompts_and_no_duplicate_callback_races(self):
        code, _ = await self.challenge()
        nonce = await self.prompt(code)
        with patch("subscription_page_telegram_approval.MAX_PER_OWNER", 1):
            await self.adapter.handle_message(self.incoming(text="/web_login " + code))
            self.assertEqual(len(self.adapter.prompts), 1)
        with patch("subscription_page_telegram_approval.MAX_PROMPTS", 1):
            await self.adapter.handle_message(self.incoming(text="/web_login " + code))
            self.assertEqual(len(self.adapter.prompts), 1)
        cb = self.callback(nonce)
        await self.adapter.handle_callback(cb)
        await self.adapter.handle_callback(cb)
        self.assertEqual(self.pilot.pending[code].approved_owner, OWNER)
        self.assertFalse(self.adapter.prompts)


if __name__ == "__main__":
    unittest.main()
