"""#887 D2b: isolated, synthetic private-bot standalone ownership exchange tests."""
from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from customer_service import CustomerProfile
from subscription_page_customer import COOKIE as MINI_APP_COOKIE
from subscription_page_standalone import (
    BASE, CHALLENGE_TTL, CHALLENGE_PATTERN, MAX_PENDING, MAX_SESSIONS,
    PENDING_COOKIE, SESSION_COOKIE, StandalonePilot, create_standalone_pilot,
)

NOW = 1_800_000_000
USER = 100_001
OTHER = 100_002
HOST = "web.example.invalid"
ORIGIN = "https://" + HOST


def profile(*, exists=True) -> CustomerProfile:
    return CustomerProfile(
        exists=exists, email="private@example.invalid", sub_id="SECRET_SUB_ID",
        display_name="Secret Name", access_status="active", period_status="active",
        plan_name="Тестовый тариф", expiry_time=NOW * 1000 + 86400000,
        expiry_known=True, available_locations=2,
    )


class StandalonePilotTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = float(NOW)
        self.flags = SimpleNamespace(
            snapshot=AsyncMock(return_value=SimpleNamespace(portal_enabled=True))
        )
        self.service = SimpleNamespace(profile=AsyncMock(return_value=profile()))
        self.pilot = create_standalone_pilot(
            https_origin=ORIGIN, customer_service=self.service,
            feature_flags=self.flags, pilot_ids=frozenset({USER}),
            now=lambda: self.clock,
        )
        self.client = TestClient(TestServer(self.pilot.app))
        await self.client.start_server()
        self.headers = {"Host": HOST, "Origin": ORIGIN}

    async def asyncTearDown(self):
        await self.client.close()

    def head(self, cookie: str | None = None, **overrides) -> dict[str, str]:
        h = dict(self.headers)
        if cookie:
            h["Cookie"] = cookie
        h.update(overrides)
        return h

    async def start(self, cookie=None):
        async with self.client.post(
            BASE + "/start", json={}, headers=self.head(cookie),
        ) as response:
            self.assertEqual(response.status, 200)
            data = await response.json()
            self.assertEqual(data["expiresIn"], CHALLENGE_TTL)
            self.assertRegex(data["challenge"], CHALLENGE_PATTERN)
            self.assertNotIn("user_id", data)
            self.assertNotIn(SESSION_COOKIE, response.cookies)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
            self.assertEqual(response.headers["X-Frame-Options"], "DENY")
            pending = response.cookies[PENDING_COOKIE]
            self.assertEqual(pending["path"], "/")
            self.assertEqual(pending["samesite"], "Strict")
            self.assertTrue(pending["secure"])
            self.assertTrue(pending["httponly"])
            return data["challenge"], f"{PENDING_COOKIE}={pending.value}"

    async def complete(self, challenge, *, cookie: str | None = None):
        return await self.client.post(
            BASE + "/complete", json={"challenge": challenge},
            headers=self.head(cookie),
        )

    async def approval(self, challenge, actor=USER, chat=None, confirmed=True):
        return await self.pilot.approve_from_private_telegram(
            challenge, actor_id=actor, chat_id=actor if chat is None else chat,
            explicitly_confirmed=confirmed,
        )

    async def authenticated(self):
        challenge, bind = await self.start()
        self.assertTrue(await self.approval(challenge))
        async with await self.complete(challenge, cookie=bind) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(
                await response.json(), {"state": "authenticated", "mode": "standalone"},
            )
            self.assertNotIn(PENDING_COOKIE, response.cookies.get(SESSION_COOKIE, {}))
            cookie = response.cookies[SESSION_COOKIE]
            self.assertTrue(cookie["secure"])
            self.assertTrue(cookie["httponly"])
            self.assertEqual(cookie["samesite"], "Strict")
            self.assertEqual(cookie["path"], "/")
            self.assertEqual(int(cookie["max-age"]), 600)
            self.assertIn(PENDING_COOKIE, response.cookies)
            # Session and browser binding digests, never plaintext credentials.
            self.assertEqual(len(self.pilot.sessions), 1)
            self.assertEqual(len(next(iter(self.pilot.sessions))), 32)
            self.assertNotIn(cookie.value.encode(), self.pilot.sessions)
            return f"{SESSION_COOKIE}={cookie.value}", challenge, bind

    async def test_exchange_requires_explicit_private_owner_action(self):
        code, binding = await self.start()
        async with await self.complete(code, cookie=binding) as response:
            self.assertEqual(response.status, 202)
            self.assertEqual(await response.json(), {"state": "pending"})
            self.assertNotIn(SESSION_COOKIE, response.cookies)
        for actor, chat, confirmed in (
            (USER, USER, False), (USER, USER + 1, True),
            (OTHER, OTHER, True), (True, USER, True),
            (USER, USER, 1), (-1, -1, True),
        ):
            with self.subTest(actor=actor, chat=chat, confirmed=confirmed):
                self.assertFalse(await self.approval(
                    code, actor=actor, chat=chat, confirmed=confirmed,
                ))
        self.assertTrue(await self.approval(code))
        self.assertFalse(await self.approval(code))  # No repeated approval.
        async with await self.complete(code, cookie=binding) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual((await response.json())["mode"], "standalone")
            self.assertIn(SESSION_COOKIE, response.cookies)
        async with await self.complete(code, cookie=binding) as response:
            self.assertEqual(response.status, 401)  # One-time exchange.

    async def test_approved_challenge_is_tied_to_original_httponly_browser(self):
        code, original_binding = await self.start()
        other_code, other_binding = await self.start()
        self.assertNotEqual(code, other_code)
        self.assertNotEqual(original_binding, other_binding)
        self.assertTrue(await self.approval(code))
        for bad_cookie in (None, other_binding, f"{PENDING_COOKIE}=forged",
                           f"{MINI_APP_COOKIE}=not-the-standalone-cookie"):
            async with await self.complete(code, cookie=bad_cookie) as r:
                self.assertEqual(r.status, 401)
        async with await self.complete(code, cookie=original_binding) as r:
            self.assertEqual(r.status, 200)
        async with await self.complete(other_code, cookie=other_binding) as r:
            self.assertEqual(r.status, 202)

    async def test_profile_is_private_safe_and_owner_derived(self):
        cookie, code, binding = await self.authenticated()
        self.service.profile.reset_mock()
        async with self.client.get(
            "/api/subpage/v1/standalone/me",
            headers={"Host": HOST, "Cookie": cookie, "X-Telegram-User-Id": str(OTHER)},
        ) as response:
            self.assertEqual(response.status, 200)
            body = await response.text()
            data = json.loads(body)
            self.assertEqual(data["subscription"]["planName"], "Тестовый тариф")
            self.assertEqual(data["subscription"]["status"], "active")
            for secret in ("private@example.invalid", "SECRET_SUB_ID", "Secret Name", "url", "email", "admin"):
                self.assertNotIn(secret, body)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
        # Shared DTO comes from the same policy as Mini App.
        self.assertEqual(self.service.profile.await_args_list[-1].args, (USER,))
        async with self.client.get(
            "/api/subpage/v1/standalone/me?telegram_id=100002",
            headers={"Host": HOST, "Cookie": cookie},
        ) as response:
            self.assertEqual(response.status, 400)
        async with self.client.get(
            "/api/subpage/v1/standalone/me",
            headers={"Host": HOST, "Cookie": f"{MINI_APP_COOKIE}=FAKE"},
        ) as response:
            self.assertEqual(response.status, 401)
        # No public approval/admin URL: trusted bot hook is Python-only.
        async with self.client.post(
            BASE + "/approve", json={"challenge": code, "telegram_id": USER},
            headers=self.headers,
        ) as response:
            self.assertEqual(response.status, 404)

    async def test_feature_revoke_and_expiry_fail_closed(self):
        cookie, code, binding = await self.authenticated()
        self.flags.snapshot.return_value = SimpleNamespace(portal_enabled=False)
        async with self.client.get(
            "/api/subpage/v1/standalone/me", headers={"Host": HOST, "Cookie": cookie},
        ) as r:
            self.assertEqual(r.status, 403)
        self.flags.snapshot.return_value = SimpleNamespace(portal_enabled=True)
        async with self.client.get(
            "/api/subpage/v1/standalone/me", headers={"Host": HOST, "Cookie": cookie},
        ) as r:
            self.assertEqual(r.status, 401)
        # Owner approval never authorizes a disabled feature.
        code2, binding2 = await self.start()
        self.flags.snapshot.side_effect = RuntimeError("private feature failure")
        self.assertFalse(await self.approval(code2))
        self.flags.snapshot.side_effect = None
        self.clock += 181
        self.assertFalse(await self.approval(code2))
        async with await self.complete(code2, cookie=binding2) as r:
            self.assertEqual(r.status, 401)
        self.clock += 1
        code3, binding3 = await self.start()
        self.assertTrue(await self.approval(code3))
        async with await self.complete(code3, cookie=binding3) as r:
            self.assertEqual(r.status, 200)
            session = f"{SESSION_COOKIE}={r.cookies[SESSION_COOKIE].value}"
        self.clock += 600
        async with self.client.get(
            "/api/subpage/v1/standalone/me", headers={"Host": HOST, "Cookie": session},
        ) as r:
            self.assertEqual(r.status, 401)

    async def test_cancel_and_logout_are_confirmed_and_one_way(self):
        code, binding = await self.start()
        async with self.client.post(
            BASE + "/cancel", json={"challenge": code},
            headers=self.head(binding),
        ) as r:
            self.assertEqual(r.status, 200)
            self.assertEqual((await r.json())["state"], "cancelled")
        self.assertFalse(await self.approval(code))
        async with await self.complete(code, cookie=binding) as r:
            self.assertEqual(r.status, 401)
        cookie, _, _ = await self.authenticated()
        async with self.client.post(
            BASE + "/logout", json={}, headers=self.head(cookie),
        ) as r:
            self.assertEqual(r.status, 200)
            self.assertEqual(await r.json(), {"authenticated": False})
            self.assertIn(SESSION_COOKIE, r.cookies)
            self.assertIn(PENDING_COOKIE, r.cookies)
        async with self.client.get(
            "/api/subpage/v1/standalone/me", headers={"Host": HOST, "Cookie": cookie},
        ) as r:
            self.assertEqual(r.status, 401)

    async def test_same_browser_restart_revokes_old_pending(self):
        code, bind = await self.start()
        code2, bind2 = await self.start(cookie=bind)
        self.assertNotEqual(code, code2)
        self.assertFalse(await self.approval(code))
        async with await self.complete(code, cookie=bind) as r:
            self.assertEqual(r.status, 401)
        self.assertTrue(await self.approval(code2))
        async with await self.complete(code2, cookie=bind2) as r:
            self.assertEqual(r.status, 200)

    async def test_login_does_not_require_subscription_bearer(self):
        for forbidden in (
            {"sub_id": "SECRET_SUB_ID"},
            {"subscriptionUrl": "https://secret.example.invalid/compat/key"},
            {"telegram_id": USER},
            {"initDataUnsafe": {"user": {"id": USER}}},
            {"challenge": "TOKEN"},
        ):
            async with self.client.post(
                BASE + "/start", json=forbidden, headers=self.headers,
            ) as r:
                self.assertEqual(r.status, 400)
        async with self.client.post(
            BASE + "/start", data="{}", headers=self.headers,
        ) as r:
            self.assertEqual(r.status, 415)
        async with self.client.post(
            BASE + "/start?sub_id=SECRET_SUB_ID", json={}, headers=self.headers,
        ) as r:
            self.assertEqual(r.status, 400)
        async with self.client.post(
            BASE + "/start", json={}, headers={"Host": HOST, "Origin": "https://evil.invalid"},
        ) as r:
            self.assertEqual(r.status, 403)
        async with self.client.post(
            BASE + "/start", json={}, headers={"Host": "evil.invalid", "Origin": ORIGIN},
        ) as r:
            self.assertEqual(r.status, 403)
        code, bind = await self.start()
        async with self.client.post(
            BASE + "/complete", json={"challenge": code},
            headers=self.head(bind, Origin="https://evil.invalid"),
        ) as r:
            self.assertEqual(r.status, 403)
        async with self.client.post(
            BASE + "/cancel", json={"challenge": ["invalid"]},
            headers=self.head(bind),
        ) as r:
            self.assertEqual(r.status, 401)
        async with self.client.get(
            "/api/subpage/v1/standalone/me", headers={"Host": "evil.invalid"},
        ) as r:
            self.assertEqual(r.status, 403)

    async def test_owner_verification_and_provider_outage(self):
        code, bind = await self.start()
        self.service.profile.return_value = profile(exists=False)
        self.assertFalse(await self.approval(code))
        self.service.profile.return_value = profile()
        self.service.profile.side_effect = RuntimeError("provider secret error")
        self.assertFalse(await self.approval(code))
        self.service.profile.side_effect = None
        self.assertTrue(await self.approval(code))
        self.service.profile.side_effect = RuntimeError("provider secret error")
        async with await self.complete(code, cookie=bind) as r:
            self.assertEqual(r.status, 403)
            self.assertNotIn("provider secret", await r.text())

    async def test_no_public_admin_routes_and_bounded_capacity(self):
        async with self.client.get("/compat/SECRET", headers={"Host": HOST}) as r:
            self.assertEqual(r.status, 404)
        async with self.client.get("/admin", headers={"Host": HOST}) as r:
            self.assertEqual(r.status, 404)
        with patch("subscription_page_standalone.MAX_PENDING", 1):
            await self.start()
            async with self.client.post(BASE + "/start", json={}, headers=self.headers) as r:
                self.assertEqual(r.status, 503)

    async def test_rate_capacity_and_fail_closed_invalid_config(self):
        for _ in range(10):
            async with self.client.post(BASE + "/start", json={}, headers=self.headers) as r:
                self.assertEqual(r.status, 200)
        async with self.client.post(BASE + "/start", json={}, headers=self.headers) as r:
            self.assertEqual(r.status, 429)
        self.clock += 61
        async with self.client.post(BASE + "/start", json={}, headers=self.headers) as r:
            self.assertEqual(r.status, 200)
        for bad in ("http://bad.invalid", "https://user:password@web.example.invalid",
                    "https://web.example.invalid/path", "https://web.example.invalid?x=1"):
            with self.subTest(origin=bad), self.assertRaises(ValueError):
                create_standalone_pilot(
                    https_origin=bad, customer_service=self.service,
                    feature_flags=self.flags, pilot_ids=frozenset({USER}),
                )
        for ids in (frozenset(), frozenset({True}), frozenset({"100001"})):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                create_standalone_pilot(
                    https_origin=ORIGIN, customer_service=self.service,
                    feature_flags=self.flags, pilot_ids=ids,
                )

    async def test_throttle_ignores_untrusted_proxy_headers(self):
        async with self.client.post(
            BASE + "/start", json={},
            headers=self.head(**{"X-Forwarded-For": "203.0.113.3"}),
        ) as r:
            self.assertEqual(r.status, 200)
        self.assertEqual(len(self.pilot.sources), 1)
        async with self.client.post(
            BASE + "/start", json={},
            headers=self.head(**{"X-Forwarded-For": "203.0.113.5"}),
        ) as r:
            self.assertEqual(r.status, 200)
        self.assertEqual(len(self.pilot.sources), 1)


if __name__ == "__main__":
    unittest.main()
