"""#887 D3i — только изолированный synthetic staging, без bearer/VPS."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiohttp.test_utils import TestClient, TestServer

from subscription_page_import_http import BASE
from subscription_page_import_staging import (
    build_isolated_import_staging, start_isolated_import_loopback,
)
from subscription_page_pilot_wiring import build_isolated_pilot
from subscription_page_staging import _SyntheticCustomer, _SyntheticFlags
from subscription_page_standalone import SESSION_COOKIE

ORIGIN = "https://staging.example.invalid"
HOST = "staging.example.invalid"
OWNER = 100001
NOW = 1800000000.0


class D3iStagingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.private = Path(self.temp.name) / "private"
        self.private.mkdir(mode=0o700)
        self.clock = lambda: NOW
        self.service = _SyntheticCustomer(frozenset({OWNER}))
        self.flags = _SyntheticFlags()
        self.pilot = build_isolated_pilot(
            explicitly_enabled=True,
            https_origin=ORIGIN,
            sqlite_path=str(self.private / "standalone-pilot.sqlite3"),
            customer_service=self.service,
            feature_flags=self.flags,
            pilot_ids=frozenset({OWNER}),
            now=self.clock,
        )
        self.import_path = str(self.private / "import-staging.sqlite3")
        self.clients = []

    async def asyncTearDown(self):
        for client in self.clients:
            await client.close()
        self.temp.cleanup()

    def build(self, **overrides):
        params = dict(
            explicitly_enabled=True, pilot_bundle=self.pilot,
            import_sqlite_path=self.import_path, csrf_secret=b"A" * 32,
            preflight_enabled=False, now=self.clock,
        )
        params.update(overrides)
        return build_isolated_import_staging(**params)

    async def client(self, **opts):
        staging = self.build(**opts)
        client = TestClient(TestServer(staging.app))
        await client.start_server()
        self.clients.append(client)
        return client

    def mint_synthetic_session(self) -> str:
        """Синтетический session ledger; НЕ Telegram approval/evidence."""
        cookie = "C" * 43
        challenge, binding = b"a" * 32, b"b" * 32
        assert self.pilot.pilot.ledger is not None
        ledger = self.pilot.pilot.ledger
        self.assertTrue(ledger.begin(
            challenge, binding, current=NOW, expires=NOW + 90,
            old_binding=None, old_session_hash=None))
        self.assertTrue(ledger.approve(challenge, OWNER, current=NOW))
        self.assertTrue(ledger.exchange(
            challenge, binding, OWNER,
            hashlib.sha256(cookie.encode("ascii")).digest(),
            current=NOW, session_ttl=120))
        self.assertEqual(self.pilot.pilot.session_owner_from_cookie(cookie, NOW), OWNER)
        return cookie

    def headers(self, cookie: str, *, origin: str | None = ORIGIN, **extra):
        result = {"Host": HOST, "Cookie": f"{SESSION_COOKIE}={cookie}"}
        if origin is not None:
            result["Origin"] = origin
        result.update(extra)
        return result

    async def test_construction_default_off_and_unsafe_inputs_never_create_ledger(self):
        with self.assertRaises(ValueError):
            self.build(explicitly_enabled=False)
        self.assertFalse(Path(self.import_path).exists())
        for invalid in (
            {"preflight_enabled": 1},
            {"csrf_secret": b"short"},
            {"import_sqlite_path": str(self.private / "standalone-pilot.sqlite3")},
            {"import_sqlite_path": str(self.private / "other.sqlite3")},
            {"import_sqlite_path": "/tmp/import-staging.sqlite3"},
            {"now": lambda: NOW},
        ):
            with self.subTest(invalid=list(invalid)):
                with self.assertRaises(ValueError):
                    self.build(**invalid)
            self.assertFalse(Path(self.import_path).exists())

    async def test_requires_unmodified_single_host_synthetic_owner_service(self):
        self.pilot.pilot.service = SimpleNamespace(profile=AsyncMock())
        with self.assertRaises(ValueError):
            self.build()
        self.pilot.pilot.service = self.service
        self.pilot.pilot.flags = SimpleNamespace(snapshot=AsyncMock())
        with self.assertRaises(ValueError):
            self.build()
        self.pilot.pilot.flags = self.flags
        self.pilot.pilot.pilot_ids = frozenset({OWNER + 1})
        with self.assertRaises(ValueError):
            self.build()
        self.assertFalse(Path(self.import_path).exists())

    async def test_import_routes_do_not_return_bearer_default_off(self):
        cookie = self.mint_synthetic_session()
        client = await self.client()
        async with client.get(BASE + "/csrf", headers=self.headers(cookie, origin=None)) as response:
            self.assertEqual(response.status, 404)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        async with client.post(BASE + "/deliver", json={}, headers=self.headers(cookie)) as response:
            self.assertEqual(response.status, 404)
            self.assertNotIn("subscriptionUrl", await response.text())
        # Independent source-only factory never reads 3x-ui URLs.
        self.assertFalse(hasattr(self.service, "subscription_card"))

    async def test_opt_in_preflight_still_denies_unknown_synthetic_entitlement(self):
        cookie = self.mint_synthetic_session()
        client = await self.client(preflight_enabled=True)
        async with client.get(BASE + "/csrf", headers=self.headers(cookie, origin=None)) as response:
            self.assertEqual(response.status, 403)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
        async with client.post(BASE + "/deliver", json={}, headers=self.headers(cookie)) as response:
            self.assertEqual(response.status, 404)

    async def test_synthetic_server_session_browser_csrf_and_atomic_preflight_only(self):
        # Offline fixture-only positive path: no real provider subscription.
        self.service.profile = AsyncMock(return_value=SimpleNamespace(
            exists=True, access_status="active", period_status="active"))
        cookie = self.mint_synthetic_session()
        client = await self.client(preflight_enabled=True)
        async with client.get(BASE + "/csrf",
                              headers=self.headers(cookie, origin=None,
                                                   **{"Sec-Fetch-Site": "same-origin"})) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            csrf = (await response.json())["csrfToken"]
            self.assertEqual(len(csrf), 64)
        for origin in ("https://evil.example.invalid", "null"):
            async with client.get(BASE + "/csrf",
                                  headers=self.headers(cookie, origin=origin)) as response:
                self.assertEqual(response.status, 403)
        async with client.get(
            BASE + "/csrf", headers=self.headers(
                cookie, origin=None, **{"Sec-Fetch-Site": "cross-site"},
            ),
        ) as response:
            self.assertEqual(response.status, 403)

        for origin, token, expected in (
            (None, csrf, 403), (ORIGIN, "bad", 403),
            ("https://evil.example.invalid", csrf, 403),
            (ORIGIN, csrf, 200),
        ):
            async with client.post(
                BASE + "/issue", json={},
                headers={**self.headers(cookie, origin=origin), "X-CSRF-Token": token},
            ) as response:
                self.assertEqual(response.status, expected)
                if expected == 200:
                    proof = (await response.json())["proof"]
        async with client.post(
            BASE + "/consume", json={"proof": proof},
            headers={**self.headers(cookie), "X-CSRF-Token": csrf},
        ) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.json(), {"preflight": True})
        async with client.post(
            BASE + "/consume", json={"proof": proof},
            headers={**self.headers(cookie), "X-CSRF-Token": csrf},
        ) as response:
            self.assertEqual(response.status, 403)
        async with client.post(BASE + "/deliver", json={}, headers=self.headers(cookie)) as response:
            self.assertEqual(response.status, 404)
            self.assertNotIn("subscriptionUrl", await response.text())
        for secret in (cookie, "subscriptionUrl", "PRIVATE_TOKEN"):
            self.assertNotIn(secret.encode(), Path(self.import_path).read_bytes())

    async def test_invalid_identity_and_staging_loopback_guard(self):
        self.service.profile = AsyncMock(return_value=SimpleNamespace(
            exists=True, access_status="active", period_status="active"))
        client = await self.client(preflight_enabled=True)
        for cookie in ("bogus", "C" * 43):
            async with client.get(BASE + "/csrf",
                                  headers=self.headers(cookie, origin=None)) as response:
                self.assertEqual(response.status, 401)
        staging = self.build(preflight_enabled=True)
        for params in (
            {}, {"explicitly_enabled": True, "host": "0.0.0.0"},
            {"explicitly_enabled": True, "port": -1},
            {"explicitly_enabled": True, "port": True},
        ):
            with self.assertRaises(ValueError):
                await start_isolated_import_loopback(staging, **params)
        listener = await start_isolated_import_loopback(
            staging, explicitly_enabled=True, host="127.0.0.1", port=0)
        try:
            self.assertGreater(listener.port, 0)
        finally:
            await listener.close()

    async def test_source_only_ingress_exact_routes_csp_and_deliver_deny(self):
        source = Path(__file__).resolve().parents[1]
        new = (source / "deploy/subpage-staging/nginx-d3i-import-staging.conf.example"
               ).read_text(encoding="utf-8")
        old = (source / "deploy/subpage-staging/nginx-d2d-staging.conf.example"
               ).read_text(encoding="utf-8")
        for suffix in ("/csrf", "/issue", "/consume", "/deliver"):
            location = "location = " + BASE + suffix + " {"
            self.assertIn(location, new)
            self.assertNotIn(location, old)
        self.assertIn("img-src 'self' data: blob:;", new)
        self.assertNotIn("img-src 'self' data: blob:;", old)
        self.assertIn('access_log off;', new)
        self.assertIn('if ($ssl_server_name != "staging.example.invalid")', new)
        self.assertIn('proxy_set_header Authorization "";', new)
        self.assertIn("proxy_pass http://127.0.0.1:8828;", new)
        forbidden = new.split("location = " + BASE + "/deliver {", 1)[1].split("}", 1)[0]
        self.assertIn("return 404;", forbidden)
        self.assertNotIn("proxy_pass", forbidden)
        self.assertIn("location / {\n        return 404;", new)


if __name__ == "__main__":
    unittest.main()
