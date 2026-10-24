"""#887 D2a: synthetic Telegram Mini App HMAC, customer sessions and IDOR tests."""
from __future__ import annotations

import hashlib
import hmac
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import urlencode

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from customer_service import CustomerProfile
from subscription_page_customer import (
    AUTH_MAX_AGE, COOKIE, MAX_INIT_DATA_BYTES, InvalidMiniAppAuth,
    MiniAppSessions, VerifiedMiniAppIdentity, create_customer_mini_app,
    verify_telegram_init_data,
)

NOW = 1_800_000_000
TOKEN = "123456789:FAKE_TEST_TOKEN_ONLY_NOT_A_REAL_SECRET"
HOST = "web.example.invalid"
ORIGIN = "https://" + HOST
ROOT = "/api/subpage/v1"
USER1 = 100_001
USER2 = 100_002


def signed_init(user_id: int = USER1, *, date: int = NOW, fields: dict | None = None) -> str:
    values = {
        "auth_date": str(date),
        "user": json.dumps({"id": user_id, "first_name": "Тест"}, ensure_ascii=False, separators=(",", ":")),
    }
    if fields:
        values.update(fields)
    joined = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    key = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(key, joined.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


class TelegramInitDataTests(unittest.TestCase):
    def test_valid_user_is_derived_only_from_signed_json(self):
        signed = signed_init(fields={"query_id": "AA-X", "chat_type": "private"})
        identity = verify_telegram_init_data(signed, TOKEN, now=NOW)
        self.assertEqual(identity.telegram_id, USER1)
        self.assertEqual(identity.auth_date, NOW)
        self.assertEqual(len(identity.proof), 32)
        self.assertNotIn(TOKEN.encode(), identity.proof)

    def test_signature_field_is_not_silently_dropped_from_bot_hmac(self):
        raw = signed_init(fields={"signature": "synthetic_signature"})
        self.assertEqual(verify_telegram_init_data(raw, TOKEN, now=NOW).telegram_id, USER1)
        # Third-party signing and bot-token signing are distinct algorithms.
        self.assertRaises(InvalidMiniAppAuth, verify_telegram_init_data,
                          raw.replace("synthetic_signature", "tampered"), TOKEN, now=NOW)

    def test_rejects_unsigned_or_tampered_payloads(self):
        good = signed_init()
        cases = [
            good.replace("100001", "100002"),
            good.replace("auth_date=", "auth_date=1"),
            good + "&hash=" + "0" * 64,
            good + "&user=%7B%22id%22%3A100002%7D",
            good.replace("hash=", "proof="),
            good.replace("hash=", "hash=" + "0"),
            good + "&unknown=%GG",
            "", "user=%7B%7D", "hash=00",
            "auth_date&user=1",
            "x=" * 4000,
        ]
        for payload in cases:
            with self.subTest(payload=payload[:32]):
                with self.assertRaises(InvalidMiniAppAuth):
                    verify_telegram_init_data(payload, TOKEN, now=NOW)

    def test_expiry_future_and_exact_boundaries(self):
        self.assertEqual(verify_telegram_init_data(
            signed_init(date=NOW - AUTH_MAX_AGE), TOKEN, now=NOW,
        ).telegram_id, USER1)
        self.assertEqual(verify_telegram_init_data(
            signed_init(date=NOW + 30), TOKEN, now=NOW,
        ).telegram_id, USER1)
        for date in (NOW - AUTH_MAX_AGE - 1, NOW + 31, 0):
            with self.subTest(date=date), self.assertRaises(InvalidMiniAppAuth):
                verify_telegram_init_data(signed_init(date=date), TOKEN, now=NOW)

    def test_rejects_invalid_signed_id_and_json(self):
        for user in ('{"id":true}', '{"id":-1}', '{"id":4503599627370496}',
                     '{"id":"100001"}', '{"is_bot":true,"id":100001}',
                     '{"first_name":"User"}', '[100001]', '{"id":'):
            with self.subTest(user=user), self.assertRaises(InvalidMiniAppAuth):
                verify_telegram_init_data(signed_init(fields={"user": user}), TOKEN, now=NOW)

    def test_boundaries_reject_invalid_configuration(self):
        for bad in ("", "short", None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                verify_telegram_init_data(signed_init(), bad, now=NOW)
        for age in (0, -1, AUTH_MAX_AGE + 1, 1.5):
            with self.subTest(age=age), self.assertRaises(ValueError):
                verify_telegram_init_data(signed_init(), TOKEN, now=NOW, max_age=age)
        oversized = signed_init(fields={"start_param": "a" * MAX_INIT_DATA_BYTES})
        with self.assertRaises(InvalidMiniAppAuth):
            verify_telegram_init_data(oversized, TOKEN, now=NOW)


class CustomerSessionsTests(unittest.TestCase):
    def test_consumed_once_bound_expiry_and_revocation(self):
        store = MiniAppSessions(ttl=60)
        identity = VerifiedMiniAppIdentity(USER1, NOW, b"test-proof")
        first = store.issue(identity, NOW)
        self.assertEqual(store.user(first, NOW + 59), USER1)
        with self.assertRaises(InvalidMiniAppAuth):
            store.issue(identity, NOW + 1)
        self.assertIsNone(store.user(first, NOW + 60))
        second = store.issue(VerifiedMiniAppIdentity(USER2, NOW, b"other"), NOW + 60)
        self.assertEqual(store.user(second, NOW + 61), USER2)
        store.revoke(second)
        self.assertIsNone(store.user(second, NOW + 62))

    def test_capacity_fails_closed(self):
        store = MiniAppSessions()
        with patch("subscription_page_customer.MAX_SESSIONS", 1):
            store.issue(VerifiedMiniAppIdentity(USER1, NOW, b"one"), NOW)
            with self.assertRaises(web.HTTPServiceUnavailable):
                store.issue(VerifiedMiniAppIdentity(USER2, NOW, b"two"), NOW)


class CustomerMiniAppApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = NOW
        self.allowed = frozenset({USER1})
        self.flags = SimpleNamespace(
            snapshot=AsyncMock(return_value=SimpleNamespace(portal_enabled=True)))
        self.service = SimpleNamespace(
            profile=AsyncMock(return_value=CustomerProfile(
                exists=True, email="private@example.invalid", sub_id="SECRET_SUB_ID",
                plan_name="Тестовый тариф", expiry_time=NOW * 1000 + 86400000,
                expiry_known=True, access_status="active", period_status="active",
                available_locations=2,
            ))
        )
        self.app = create_customer_mini_app(
            bot_token=TOKEN, https_origin=ORIGIN, customer_service=self.service,
            feature_flags=self.flags, pilot_ids=self.allowed,
            now=lambda: self.clock, session_ttl=120,
        )
        self.client = TestClient(TestServer(self.app))
        await self.client.start_server()
        self.headers = {"Host": HOST, "Origin": ORIGIN}

    async def asyncTearDown(self):
        await self.client.close()

    async def login(self, init_data=None, headers=None):
        return await self.client.post(
            ROOT + "/auth/telegram",
            json={"initData": signed_init() if init_data is None else init_data},
            headers=self.headers if headers is None else headers,
        )

    async def cookie(self):
        async with await self.login() as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.json(), {"authenticated": True, "mode": "telegram"})
            self.assertIn(COOKIE, response.cookies)
            cookie = response.cookies[COOKIE]
            self.assertTrue(cookie["secure"])
            self.assertTrue(cookie["httponly"])
            self.assertEqual(cookie["samesite"], "Strict")
            return f"{COOKIE}={cookie.value}"

    async def test_authorized_profile_uses_only_cookie_owner_and_safe_dto(self):
        cookie = await self.cookie()
        async with self.client.get(
            ROOT + "/me", headers={"Host": HOST, "Cookie": cookie},
        ) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
            body = await response.text()
            self.assertNotIn("SECRET_SUB_ID", body)
            self.assertNotIn("private@example.invalid", body)
            self.assertNotIn("subscriptionUrl", body)
            data = json.loads(body)
            self.assertEqual(data["subscription"]["status"], "active")
            self.assertEqual(data["subscription"]["availableLocations"], 2)
            self.assertEqual(data["subscription"]["planName"], "Тестовый тариф")
            self.service.profile.assert_awaited_once_with(USER1)
        async with self.client.get(
            ROOT + "/me?telegram_id=100002", headers={"Host": HOST, "Cookie": cookie},
        ) as response:
            self.assertEqual(response.status, 400)
        self.service.profile.assert_awaited_once_with(USER1)

    async def test_forgery_replay_cross_user_and_missing_session(self):
        async with await self.login(signed_init(USER2)) as response:
            self.assertEqual(response.status, 403)
            self.assertNotIn(COOKIE, response.cookies)
        raw = signed_init().replace("100001", "100002")
        async with await self.login(raw) as response:
            self.assertEqual(response.status, 401)
            self.assertNotIn("100002", await response.text())
        async with self.client.get(ROOT + "/me", headers={"Host": HOST}) as response:
            self.assertEqual(response.status, 401)
        await self.cookie()
        async with await self.login() as response:
            self.assertEqual(response.status, 401)
        self.service.profile.assert_not_awaited()

    async def test_host_origin_content_type_and_mutation_csrf(self):
        async with await self.login(headers={"Host": HOST, "Origin": "https://evil.example.invalid"}) as r:
            self.assertEqual(r.status, 403)
        async with await self.login(headers={"Host": "evil.example.invalid", "Origin": ORIGIN}) as r:
            self.assertEqual(r.status, 403)
        async with self.client.post(
            ROOT + "/auth/telegram", data="initData=123", headers=self.headers,
        ) as r:
            self.assertEqual(r.status, 415)
        async with self.client.post(
            ROOT + "/auth/telegram?telegram_id=100002",
            json={"initData": signed_init()}, headers=self.headers,
        ) as r:
            self.assertEqual(r.status, 400)
        cookie = await self.cookie()
        async with self.client.post(
            ROOT + "/logout",
            headers={"Host": HOST, "Cookie": cookie, "Origin": "https://evil.example.invalid"},
        ) as r:
            self.assertEqual(r.status, 403)
        async with self.client.post(
            ROOT + "/logout", headers={**self.headers, "Cookie": cookie},
        ) as r:
            self.assertEqual(r.status, 200)
        async with self.client.get(ROOT + "/me", headers={"Host": HOST, "Cookie": cookie}) as r:
            self.assertEqual(r.status, 401)

    async def test_revocation_expiry_unknown_profile_and_provider_outage(self):
        cookie = await self.cookie()
        self.flags.snapshot.return_value = SimpleNamespace(portal_enabled=False)
        async with self.client.get(ROOT + "/me", headers={"Host": HOST, "Cookie": cookie}) as r:
            self.assertEqual(r.status, 403)
        self.flags.snapshot.return_value = SimpleNamespace(portal_enabled=True)
        async with self.client.get(ROOT + "/me", headers={"Host": HOST, "Cookie": cookie}) as r:
            self.assertEqual(r.status, 401)
        self.clock += 1
        cookie2 = None
        async with await self.login(signed_init(date=NOW + 1)) as r:
            self.assertEqual(r.status, 200)
            cookie2 = f"{COOKIE}={r.cookies[COOKIE].value}"
        self.service.profile.return_value = CustomerProfile(exists=False)
        async with self.client.get(ROOT + "/me", headers={"Host": HOST, "Cookie": cookie2}) as r:
            self.assertEqual(r.status, 403)
        self.service.profile.side_effect = RuntimeError("provider private error")
        async with self.client.get(ROOT + "/me", headers={"Host": HOST, "Cookie": cookie2}) as r:
            self.assertEqual(r.status, 503)
            self.assertNotIn("provider private error", await r.text())
        self.clock += 121
        async with self.client.get(ROOT + "/me", headers={"Host": HOST, "Cookie": cookie2}) as r:
            self.assertEqual(r.status, 401)

    async def test_backpressure_and_default_off_isolation(self):
        for _ in range(12):
            async with await self.login("forged") as r:
                self.assertEqual(r.status, 401)
        async with await self.login("forged") as r:
            self.assertEqual(r.status, 429)
        async with self.client.get("/compat/test", headers={"Host": HOST}) as r:
            self.assertEqual(r.status, 404)
        async with self.client.get("/api/subpage/v1/admin", headers={"Host": HOST}) as r:
            self.assertEqual(r.status, 404)

    async def test_configuration_fails_closed(self):
        with self.assertRaises(ValueError):
            create_customer_mini_app(
                bot_token=TOKEN, https_origin="http://bad.example.invalid",
                customer_service=self.service, feature_flags=self.flags,
                pilot_ids=self.allowed,
            )
        with self.assertRaises(ValueError):
            create_customer_mini_app(
                bot_token=TOKEN, https_origin=ORIGIN,
                customer_service=self.service, feature_flags=self.flags,
                pilot_ids=frozenset(),
            )


if __name__ == "__main__":
    unittest.main()
