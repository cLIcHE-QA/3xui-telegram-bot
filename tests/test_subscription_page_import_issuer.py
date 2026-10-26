"""#887 D3f: offline, default-off owner-bound subscription URL release tests."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiohttp.test_utils import TestClient, TestServer

from subscription_page_customer import COOKIE as MINI_COOKIE, MiniAppSessions, VerifiedMiniAppIdentity
from subscription_page_standalone import SESSION_COOKIE as STANDALONE_COOKIE, StandalonePilot
from subscription_page_import_http import BASE, create_import_preflight_app
from subscription_page_import_issuer import (
    ReviewedImportClient, owner_bound_subscription_url, reviewed_import_keys,
    validate_subscription_url,
)
from subscription_page_import_sqlite import ImportSQLiteLedger

NOW = 1800000000.
OWNER = 100001
OTHER = 100002
ORIGIN = "https://web.example.invalid"
URL_ORIGIN = "https://subscription.example.invalid"
BEARER = URL_ORIGIN + "/sub/SECRET_SUB_ID?token=SYNTHETIC"
REVIEWED = (ReviewedImportClient("ios", "synthetic-client", "1.0.0", "#887", True, True),)


class D3fIssuerTests(unittest.IsolatedAsyncioTestCase):
    async def test_https_origin_credential_and_control_validation(self):
        self.assertEqual(validate_subscription_url(BEARER, expected_origin=URL_ORIGIN), BEARER)
        for url in (None, "", "http://subscription.example.invalid/sub/id",
                    "https://evil.example.invalid/sub/id",
                    "https://subscription.example.invalid.evil.invalid/sub/id",
                    "https://subscription.example.invalid:443/sub/id",
                    "https://user:pass@subscription.example.invalid/sub/id",
                    URL_ORIGIN + "/sub/id#fragment", URL_ORIGIN + "/",
                    URL_ORIGIN + "/sub/id\\bad", URL_ORIGIN + "/sub/id\r\nX: injected",
                    URL_ORIGIN + "/sub/id%0d%0aX:injected",
                    URL_ORIGIN + "/sub/id%5cfoo", URL_ORIGIN + "/sub/id%00",
                    URL_ORIGIN + "/sub/{id}", " " + BEARER, BEARER + " "):
            with self.subTest(url=url):
                self.assertIsNone(validate_subscription_url(url, expected_origin=URL_ORIGIN))
        self.assertIsNone(validate_subscription_url(BEARER, expected_origin="http://subscription.example.invalid"))
        self.assertIsNone(validate_subscription_url(BEARER, expected_origin="https://evil.example.invalid"))

    async def test_review_registry_fails_closed(self):
        self.assertEqual(reviewed_import_keys(()), frozenset())
        self.assertEqual(reviewed_import_keys(REVIEWED), frozenset({("ios", "synthetic-client", "1.0.0")}))
        for records in (
            REVIEWED + REVIEWED,
            (ReviewedImportClient("ios", "synthetic-client", "1.0.0", "", True, True),),
            (ReviewedImportClient("ios", "synthetic-client", "1.0.0", "#887", False, False),),
            (ReviewedImportClient("ios", "../bad", "1.0.0", "#887", True, False),),
            (ReviewedImportClient("ios", "synthetic-client", "1.0.0", "#887", "yes", True),),
        ):
            with self.subTest(records=records), self.assertRaises(ValueError):
                reviewed_import_keys(records)

    async def test_owner_scoped_service_must_be_active(self):
        profile = SimpleNamespace(exists=True, access_status="active",
            period_status="active", sub_id="SECRET_SUB_ID")
        service = SimpleNamespace(subscription_card=AsyncMock(
            return_value=SimpleNamespace(profile=profile, url=BEARER)))
        self.assertEqual(await owner_bound_subscription_url(
            customer_service=service, authenticated_owner=OWNER,
            expected_origin=URL_ORIGIN), BEARER)
        service.subscription_card.assert_awaited_with(OWNER)
        for field, value in (("exists", False), ("access_status", "disabled"),
                             ("access_status", "unknown"), ("period_status", "expired"),
                             ("sub_id", "../fake")):
            prior = getattr(profile, field)
            setattr(profile, field, value)
            self.assertIsNone(await owner_bound_subscription_url(
                customer_service=service, authenticated_owner=OWNER,
                expected_origin=URL_ORIGIN))
            setattr(profile, field, prior)
        self.assertIsNone(await owner_bound_subscription_url(
            customer_service=service, authenticated_owner=OTHER,
            expected_origin="https://wrong.invalid"))
        service.subscription_card.side_effect = RuntimeError("SENSITIVE-provider-error")
        self.assertIsNone(await owner_bound_subscription_url(
            customer_service=service, authenticated_owner=OWNER,
            expected_origin=URL_ORIGIN))


class D3fHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        private = Path(self.tmp.name) / "private"
        private.mkdir(mode=0o700)
        self.path = str(private / "import.sqlite3")
        self.ledger = ImportSQLiteLedger(self.path, https_origin=ORIGIN)
        self.clock = NOW
        self.flags = SimpleNamespace(snapshot=AsyncMock(
            return_value=SimpleNamespace(portal_enabled=True)))
        self.profile = SimpleNamespace(exists=True, access_status="active",
            period_status="active", sub_id="SECRET_SUB_ID")
        self.service = SimpleNamespace(
            profile=AsyncMock(return_value=self.profile),
            subscription_card=AsyncMock(return_value=SimpleNamespace(
                profile=self.profile, url=BEARER)))
        self.mini = MiniAppSessions(ttl=120)
        self.mini_cookie = self.mini.issue(
            VerifiedMiniAppIdentity(OWNER, int(NOW), b"d3f-owner"), NOW)
        self.mini_other = self.mini.issue(
            VerifiedMiniAppIdentity(OTHER, int(NOW), b"d3f-other"), NOW)
        self.standalone = StandalonePilot(
            https_origin=ORIGIN, customer_service=self.service,
            feature_flags=self.flags, pilot_ids=frozenset({OWNER, OTHER}),
            now=lambda: self.clock)
        self.standalone_cookie = "S" * 43
        self.standalone.sessions[self.standalone._hash(self.standalone_cookie)] = (
            OWNER, NOW + 120)
        self.clients = []
        self.client = await self.make_client()

    async def make_client(self, **kw):
        options = dict(
            https_origin=ORIGIN, ledger=self.ledger, mini_sessions=self.mini,
            standalone=self.standalone, customer_service=self.service,
            feature_flags=self.flags, pilot_ids=frozenset({OWNER}),
            enabled=True, now=lambda: self.clock, csrf_secret=b"x" * 32,
            delivery_enabled=True, subscription_origin=URL_ORIGIN,
            reviewed_clients=REVIEWED)
        options.update(kw)
        client = TestClient(TestServer(create_import_preflight_app(**options)))
        await client.start_server()
        self.clients.append(client)
        return client

    async def asyncTearDown(self):
        for c in self.clients:
            await c.close()
        self.tmp.cleanup()

    def headers(self, raw_cookie=None):
        return {"Host": "web.example.invalid", "Origin": ORIGIN,
                "Cookie": raw_cookie or f"{MINI_COOKIE}={self.mini_cookie}"}

    async def csrf(self, client=None, raw_cookie=None):
        async with (client or self.client).get(
            BASE + "/csrf", headers=self.headers(raw_cookie)) as r:
            self.assertEqual(r.status, 200)
            return (await r.json())["csrfToken"]

    async def proof(self, csrf, client=None, raw_cookie=None):
        headers = self.headers(raw_cookie)
        headers["X-CSRF-Token"] = csrf
        async with (client or self.client).post(
            BASE + "/issue", json={}, headers=headers) as r:
            self.assertEqual(r.status, 200)
            return (await r.json())["proof"]

    async def deliver(self, token, proof, *, client=None, raw_cookie=None,
                      platform="ios", client_id="synthetic-client",
                      version="1.0.0", extra=None):
        headers = self.headers(raw_cookie)
        headers["X-CSRF-Token"] = token
        if extra:
            headers.update(extra)
        return await (client or self.client).post(BASE + "/deliver",
            json={"proof": proof, "platform": platform,
                  "clientId": client_id, "clientVersion": version},
            headers=headers)

    async def test_default_off_and_empty_allowlist(self):
        for opts in ({"delivery_enabled": False},
                     {"delivery_enabled": False, "reviewed_clients": ()}):
            other = await self.make_client(**opts)
            token = await self.csrf(other)
            proof = await self.proof(token, other)
            async with await self.deliver(token, proof, client=other) as r:
                self.assertEqual(r.status, 404)
                self.assertNotIn("SECRET_SUB_ID", await r.text())
        with self.assertRaises(ValueError):
            create_import_preflight_app(
                https_origin=ORIGIN, ledger=self.ledger, mini_sessions=self.mini,
                standalone=self.standalone, customer_service=self.service,
                feature_flags=self.flags, pilot_ids=frozenset({OWNER}),
                enabled=True, now=lambda: self.clock, csrf_secret=b"x" * 32,
                delivery_enabled=True, subscription_origin=URL_ORIGIN, reviewed_clients=())

    async def test_one_shot_owner_url_no_cache_and_no_replay(self):
        token = await self.csrf()
        proof = await self.proof(token)
        async with await self.deliver(token, proof) as r:
            self.assertEqual(r.status, 200)
            self.assertEqual(await r.json(), {"subscriptionUrl": BEARER})
            self.assertEqual(r.headers["Cache-Control"], "no-store")
            self.assertEqual(r.headers["Pragma"], "no-cache")
            self.assertEqual(r.headers["Referrer-Policy"], "no-referrer")
        self.service.subscription_card.assert_awaited_with(OWNER)
        async with await self.deliver(token, proof) as r:
            self.assertEqual(r.status, 403)
            self.assertNotIn(BEARER, await r.text())

    async def test_unreviewed_client_or_version_burns_proof(self):
        token = await self.csrf()
        for opts in (dict(platform="android"), dict(client_id="other"),
                     dict(version="2.0.0")):
            proof = await self.proof(token)
            async with await self.deliver(token, proof, **opts) as r:
                self.assertEqual(r.status, 403)
                self.assertNotIn(BEARER, await r.text())
            async with await self.deliver(token, proof) as r:
                self.assertEqual(r.status, 403)
        self.service.subscription_card.assert_not_awaited()

    async def test_other_session_and_csrf_idor(self):
        token = await self.csrf()
        proof = await self.proof(token)
        async with await self.deliver(token, proof,
             raw_cookie=f"{MINI_COOKIE}={self.mini_other}") as r:
            self.assertEqual(r.status, 403)
        async with await self.deliver(token, proof, extra={"X-CSRF-Token": "wrong"}) as r:
            self.assertEqual(r.status, 403)
        async with await self.deliver(token, proof, extra={"Origin": "https://evil.invalid"}) as r:
            self.assertEqual(r.status, 403)
        async with await self.deliver(token, proof) as r:
            self.assertEqual(r.status, 200)
        self.service.subscription_card.assert_awaited_with(OWNER)

    async def test_owner_revocation_and_provider_error_burn(self):
        token = await self.csrf()
        proof = await self.proof(token)
        self.flags.snapshot.return_value = SimpleNamespace(portal_enabled=False)
        async with await self.deliver(token, proof) as r:
            self.assertEqual(r.status, 403)
            self.assertNotIn(BEARER, await r.text())
        self.flags.snapshot.return_value = SimpleNamespace(portal_enabled=True)
        async with await self.deliver(token, proof) as r:
            self.assertEqual(r.status, 403)
        proof = await self.proof(token)
        self.service.subscription_card.side_effect = RuntimeError("SENSITIVE-private-upstream")
        async with await self.deliver(token, proof) as r:
            self.assertEqual(r.status, 403)
            self.assertNotIn("SENSITIVE", await r.text())
        self.service.subscription_card.side_effect = None

    async def test_revoke_during_async_card_is_denied(self):
        token = await self.csrf()
        proof = await self.proof(token)
        async def revoke(owner):
            self.mini.revoke(self.mini_cookie)
            return SimpleNamespace(profile=self.profile, url=BEARER)
        self.service.subscription_card = AsyncMock(side_effect=revoke)
        async with await self.deliver(token, proof) as r:
            self.assertIn(r.status, (401, 403))
            self.assertNotIn(BEARER, await r.text())

    async def test_concurrent_delivery_consumes_once_across_clients(self):
        second = await self.make_client(ledger=ImportSQLiteLedger(
            self.path, https_origin=ORIGIN))
        token = await self.csrf()
        proof = await self.proof(token)
        responses = await asyncio.gather(
            self.deliver(token, proof), self.deliver(token, proof, client=second))
        try:
            self.assertEqual(sorted(r.status for r in responses), [200, 403])
        finally:
            for r in responses:
                r.release()

    async def test_standalone_owner_session_supported(self):
        cookie = f"{STANDALONE_COOKIE}={self.standalone_cookie}"
        token = await self.csrf(raw_cookie=cookie)
        proof = await self.proof(token, raw_cookie=cookie)
        async with await self.deliver(token, proof, raw_cookie=cookie) as r:
            self.assertEqual(r.status, 200)


if __name__ == "__main__":
    unittest.main()
