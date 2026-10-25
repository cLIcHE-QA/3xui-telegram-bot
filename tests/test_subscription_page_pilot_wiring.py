"""#887 D2c: сквозные synthetic aiogram Dispatcher + loopback HTTP + SQLite.

Ни один тест не вызывает Telegram Bot API, не использует действующие
credential/provider/SQLite и не запускает публичный HTTP или HTTPS listener.
"""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram import Bot
from aiogram.methods import AnswerCallbackQuery, EditMessageReplyMarkup, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, Update, User
from aiohttp import ClientSession
from aiohttp.test_utils import TestClient, TestServer

from subscription_page_pilot_wiring import build_isolated_pilot, start_loopback_api
from subscription_page_standalone import PENDING_COOKIE, SESSION_COOKIE, create_standalone_pilot

ORIGIN = "https://web.example.invalid"
HOST = "web.example.invalid"
OWNER = 100_001
FOREIGN = 100_002
BOT_ID = 900_001
NOW = 1_800_000_000
AUTH = "/api/subpage/v1/auth/standalone"
ME = "/api/subpage/v1/standalone/me"
BOT_TOKEN = "900001:" + "A" * 35  # synthetic, never usable for a live bot


def person(tg_id: int = OWNER) -> User:
    return User(id=tg_id, is_bot=False, first_name="Пилот")


def msg(tg_id: int = OWNER, *, text: str = "", message_id: int = 1,
        kind: str = "private", chat_id: int | None = None,
        forwarded: bool = False) -> Message:
    fields = dict(
        message_id=message_id, date=datetime.fromtimestamp(NOW, timezone.utc),
        chat=Chat(id=tg_id if chat_id is None else chat_id, type=kind),
        from_user=person(tg_id), text=text,
    )
    if forwarded:
        fields["forward_origin"] = {
            "type": "user", "date": NOW,
            "sender_user": person(FOREIGN).model_dump(),
        }
    return Message(**fields)


def callback(nonce: str, *, owner: int = OWNER, message_id: int = 777) -> Update:
    return Update(
        update_id=50,
        callback_query=CallbackQuery(
            id="callback-test", from_user=person(owner),
            chat_instance="synthetic-private",
            data=f"d2bs:yes:{nonce}",
            message=Message(
                message_id=message_id,
                date=datetime.fromtimestamp(NOW, timezone.utc),
                chat=Chat(id=OWNER, type="private"),
                from_user=User(id=BOT_ID, is_bot=True, first_name="Пилотный бот"),
                text="Подтвердить вход",
            ),
        ),
    )


class IsolatedPilotWiringTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "standalone-pilot.sqlite3")
        self.clock = float(NOW)
        self.service = SimpleNamespace(profile=AsyncMock(return_value=SimpleNamespace(
            exists=True, access_status="active", period_status="active",
            plan_name="Изолированный тариф", expiry_time=NOW * 1000,
            expiry_known=True, available_locations=2,
        )))
        self.flags = SimpleNamespace(
            snapshot=AsyncMock(return_value=SimpleNamespace(portal_enabled=True)),
        )
        self.kwargs = dict(
            https_origin=ORIGIN, sqlite_path=self.path,
            customer_service=self.service, feature_flags=self.flags,
            pilot_ids=frozenset({OWNER}), now=lambda: self.clock,
        )
        self.bundle = build_isolated_pilot(explicitly_enabled=True, **self.kwargs)
        self.web = TestClient(TestServer(self.bundle.app))
        await self.web.start_server()
        self.bot = Bot(token=BOT_TOKEN)
        self.outgoing: list[object] = []

    async def asyncTearDown(self) -> None:
        await self.web.close()
        await self.bot.session.close()
        self.tmp.cleanup()

    @staticmethod
    def headers(cookie: str | None = None) -> dict[str, str]:
        h = {"Host": HOST, "Origin": ORIGIN}
        if cookie:
            h["Cookie"] = cookie
        return h

    async def start_browser(self) -> tuple[str, str]:
        async with self.web.post(
            AUTH + "/start", json={}, headers=self.headers(),
        ) as response:
            self.assertEqual(response.status, 200)
            self.assertIn(PENDING_COOKIE, response.cookies)
            cookie = response.cookies[PENDING_COOKIE]
            self.assertTrue(cookie["secure"])
            self.assertTrue(cookie["httponly"])
            self.assertEqual(cookie["samesite"].lower(), "strict")
            return (await response.json())["challenge"], f"{PENDING_COOKIE}={cookie.value}"

    async def complete(self, code: str, binding: str) -> tuple[int, str | None]:
        async with self.web.post(
            AUTH + "/complete", json={"challenge": code},
            headers=self.headers(binding),
        ) as response:
            issued = response.cookies.get(SESSION_COOKIE)
            return response.status, (
                f"{SESSION_COOKIE}={issued.value}" if issued else None
            )

    async def bot_call(self, _bot: Bot, method, **kwargs):
        self.outgoing.append(method)
        if isinstance(method, SendMessage):
            return msg(BOT_ID, text=method.text, message_id=777, chat_id=OWNER)
        if isinstance(method, (AnswerCallbackQuery, EditMessageReplyMarkup)):
            return True
        raise AssertionError("Synthetic transport rejected unexpected Bot API call")

    async def feed(self, update: Update):
        # The class is patched only inside the call: no network request possible.
        with patch.object(Bot, "__call__", autospec=True, side_effect=self.bot_call):
            return await self.bundle.dispatcher.feed_update(self.bot, update)

    async def test_factory_is_default_off_and_never_binds_network(self):
        with self.assertRaises(ValueError):
            build_isolated_pilot(**self.kwargs)
        with self.assertRaises(ValueError):
            build_isolated_pilot(explicitly_enabled=1, **self.kwargs)
        with self.assertRaises(ValueError):
            build_isolated_pilot(
                explicitly_enabled=True,
                **(self.kwargs | {"sqlite_path": str(Path(self.tmp.name) / "bot.sqlite3")}),
            )
        with self.assertRaises(ValueError):
            build_isolated_pilot(
                explicitly_enabled=True, **(self.kwargs | {"https_origin": "http://localhost"}),
            )
        self.assertIs(self.bundle.approval.pilot, self.bundle.pilot)
        self.assertIsNotNone(self.bundle.pilot.ledger)
        self.assertEqual(len(self.bundle.dispatcher.sub_routers), 1)
        self.assertEqual(self.bundle.dispatcher.sub_routers[0].name, "d2b_standalone_approval")
        # Only explicit start_loopback_api opens a listener.
        with self.assertRaises(ValueError):
            await start_loopback_api(self.bundle)
        for host in ("0.0.0.0", "::1", "localhost", "web.example.invalid"):
            with self.subTest(host=host):
                with self.assertRaises(ValueError):
                    await start_loopback_api(self.bundle, explicitly_enabled=True, host=host)
        for port in (-1, 65536, True):
            with self.subTest(port=port):
                with self.assertRaises(ValueError):
                    await start_loopback_api(self.bundle, explicitly_enabled=True, port=port)

    async def test_real_dispatcher_private_approval_to_bound_http_session(self):
        code, binding = await self.start_browser()
        self.assertEqual((await self.complete(code, binding))[0], 202)
        await self.feed(Update(update_id=1, message=msg(text=f"/web_login {code}")))
        self.assertEqual(len(self.bundle.approval.prompts), 1)
        nonce = next(iter(self.bundle.approval.prompts))
        sent = [x for x in self.outgoing if isinstance(x, SendMessage)]
        self.assertEqual(len(sent), 1)
        self.assertIn(ORIGIN, sent[0].text)
        self.assertNotIn(code, sent[0].text)
        self.assertTrue(sent[0].reply_markup.inline_keyboard[0][0].callback_data.endswith(nonce))
        self.assertEqual((await self.complete(code, binding))[0], 202)

        # The callback is exercised through the actual aiogram dispatcher filters.
        await self.feed(callback(nonce))
        self.assertFalse(self.bundle.approval.prompts)
        self.assertEqual((await self.complete(code, "invalid-cookie"))[0], 401)
        status, session = await self.complete(code, binding)
        self.assertEqual(status, 200)
        self.assertTrue(session)
        self.assertEqual((await self.complete(code, binding))[0], 401)
        async with self.web.get(ME, headers=self.headers(session)) as response:
            self.assertEqual(response.status, 200)
            dto = (await response.json())["subscription"]
            self.assertEqual(dto["planName"], "Изолированный тариф")
            self.assertEqual(sorted(dto), sorted([
                "status", "periodStatus", "planName", "expiryTime", "availableLocations",
            ]))
        async with self.web.post(AUTH + "/logout", json={},
                                 headers=self.headers(session)) as response:
            self.assertEqual(response.status, 200)
        async with self.web.get(ME, headers=self.headers(session)) as response:
            self.assertEqual(response.status, 401)
        # No plaintext credentials in DB and no external Bot API calls.
        data = Path(self.path).read_bytes()
        self.assertNotIn(code.encode(), data)
        self.assertNotIn(binding.encode(), data)
        self.assertNotIn((session or "").encode(), data)
        self.assertTrue(any(isinstance(x, AnswerCallbackQuery) for x in self.outgoing))

    async def test_dispatcher_denies_group_forwarded_foreign_and_expired_requests(self):
        code, bind = await self.start_browser()
        await self.feed(Update(update_id=1, message=msg(OWNER, kind="supergroup",
                                                        chat_id=-1001, text=f"/web_login {code}")))
        await self.feed(Update(update_id=2, message=msg(FOREIGN, text=f"/web_login {code}")))
        await self.feed(Update(update_id=3, message=msg(OWNER, text=f"/web_login {code}",
                                                        forwarded=True)))
        self.assertFalse(self.bundle.approval.prompts)
        self.assertEqual((await self.complete(code, bind))[0], 202)
        self.clock += 181
        await self.feed(Update(update_id=4, message=msg(text=f"/web_login {code}")))
        self.assertFalse(self.bundle.approval.prompts)
        self.assertEqual((await self.complete(code, bind))[0], 401)

    async def test_dispatcher_different_actor_cannot_confirm_prompt(self):
        code, bind = await self.start_browser()
        await self.feed(Update(update_id=1, message=msg(text=f"/web_login {code}")))
        nonce = next(iter(self.bundle.approval.prompts))
        await self.feed(callback(nonce, owner=FOREIGN))
        self.assertIn(nonce, self.bundle.approval.prompts)
        self.assertEqual((await self.complete(code, bind))[0], 202)
        await self.feed(callback(nonce, message_id=33))
        self.assertIn(nonce, self.bundle.approval.prompts)
        self.assertEqual((await self.complete(code, bind))[0], 202)
        self.flags.snapshot.return_value = SimpleNamespace(portal_enabled=False)
        await self.feed(callback(nonce))
        self.assertEqual((await self.complete(code, bind))[0], 202)
        self.assertFalse(self.bundle.approval.prompts)
        self.flags.snapshot.return_value = SimpleNamespace(portal_enabled=True)

    async def test_local_listener_must_be_explicit_loopback_only_and_can_close(self):
        listener = await start_loopback_api(self.bundle, explicitly_enabled=True)
        self.assertGreater(listener.port, 0)
        url = f"http://127.0.0.1:{listener.port}"
        try:
            async with ClientSession(trust_env=False) as external:
                async with external.post(
                    url + AUTH + "/start", json={}, headers=self.headers(),
                ) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.headers.get("Cache-Control"), "no-store")
                    self.assertNotIn("sub_id", await response.text())
                async with external.post(
                    url + AUTH + "/start", json={}, headers={
                        "Host": "evil.example.invalid", "Origin": ORIGIN,
                    },
                ) as response:
                    self.assertEqual(response.status, 403)
                async with external.post(
                    url + AUTH + "/start", json={}, headers={
                        "Host": HOST, "Origin": "https://evil.example.invalid",
                    },
                ) as response:
                    self.assertEqual(response.status, 403)
        finally:
            await listener.close()
        self.assertFalse(listener.runner.sites)
