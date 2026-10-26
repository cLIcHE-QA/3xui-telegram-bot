"""#887 D3e synthetic HTTP Origin/CSRF/session and SQLite atomicity tests."""
from __future__ import annotations

import asyncio
import hashlib
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiohttp.test_utils import TestClient, TestServer

from subscription_page_customer import COOKIE as MINI_COOKIE, MiniAppSessions, VerifiedMiniAppIdentity
from subscription_page_standalone import SESSION_COOKIE as STANDALONE_COOKIE, StandalonePilot
from subscription_page_import_http import BASE, create_import_preflight_app
from subscription_page_import_sqlite import ImportSQLiteLedger, ISSUE_LIMIT

NOW = 1800000000.0
HOST = "web.example.invalid"
ORIGIN = "https://" + HOST
OWNER = 100001
OTHER = 100002


class ImportHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.private = Path(self.tmp.name) / "private"
        self.private.mkdir(mode=0o700)
        self.path = str(self.private / "import.sqlite3")
        self.ledger = ImportSQLiteLedger(self.path, https_origin=ORIGIN)
        self.clock = NOW
        self.flags = SimpleNamespace(snapshot=AsyncMock(
            return_value=SimpleNamespace(portal_enabled=True)))
        self.profile = SimpleNamespace(exists=True, access_status="active",
                                       period_status="active", sub_id="SECRET_SUB_ID",
                                       email="hidden@example.invalid")
        self.service = SimpleNamespace(profile=AsyncMock(return_value=self.profile))
        self.mini = MiniAppSessions(ttl=120)
        self.cookie = self.mini.issue(
            VerifiedMiniAppIdentity(OWNER, int(NOW), b"d3e-mini-owner"), NOW)
        self.other = self.mini.issue(
            VerifiedMiniAppIdentity(OTHER, int(NOW), b"d3e-mini-other"), NOW)
        self.standalone = StandalonePilot(
            https_origin=ORIGIN, customer_service=self.service,
            feature_flags=self.flags, pilot_ids=frozenset({OWNER, OTHER}),
            now=lambda: self.clock,
        )
        self.standalone_cookie = "S" * 43
        self.standalone.sessions[self.standalone._hash(self.standalone_cookie)] = (
            OWNER, NOW + 120)
        self.clients = []
        await self.new_client()

    async def new_client(self, *, enabled=True, ledger=None):
        app = create_import_preflight_app(
            https_origin=ORIGIN, ledger=ledger or self.ledger,
            mini_sessions=self.mini, standalone=self.standalone,
            customer_service=self.service, feature_flags=self.flags,
            pilot_ids=frozenset({OWNER}), enabled=enabled,
            now=lambda: self.clock, csrf_secret=b"S" * 32,
        )
        client = TestClient(TestServer(app))
        await client.start_server()
        self.clients.append(client)
        return client

    async def asyncTearDown(self):
        for client in self.clients:
            await client.close()
        self.tmp.cleanup()

    def headers(self, cookie=None, **extra):
        h = {"Host": HOST, "Origin": ORIGIN,
             "Cookie": f"{MINI_COOKIE}={self.cookie}" if cookie is None else cookie}
        h.update(extra)
        return h

    async def csrf(self, client=None, headers=None):
        async with (client or self.clients[0]).get(
            BASE + "/csrf", headers=headers or self.headers(),
        ) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            return (await response.json())["csrfToken"]

    async def issue(self, token, client=None, headers=None):
        h = headers or self.headers()
        h["X-CSRF-Token"] = token
        return await (client or self.clients[0]).post(
            BASE + "/issue", json={}, headers=h)

    async def consume(self, csrf, proof, client=None, headers=None):
        h = headers or self.headers()
        h["X-CSRF-Token"] = csrf
        return await (client or self.clients[0]).post(
            BASE + "/consume", json={"proof": proof}, headers=h)

    async def test_default_off_no_routes_without_explicit_enable(self):
        client = await self.new_client(enabled=False)
        async with client.get(BASE + "/csrf", headers=self.headers()) as response:
            self.assertEqual(response.status, 404)
            self.assertNotIn("SECRET_SUB_ID", await response.text())

    async def test_minimal_owner_bound_one_time_flow_no_secrets(self):
        token = await self.csrf()
        async with await self.issue(token) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            payload = await response.json()
            self.assertEqual(set(payload), {"proof", "expiresIn"})
            proof = payload["proof"]
            self.assertEqual(len(proof), 43)
        async with await self.consume(token, proof) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.json(), {"preflight": True})
            self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        async with await self.consume(token, proof) as response:
            self.assertEqual(response.status, 403)
        with sqlite3.connect(self.path) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM import_grants").fetchone()[0], 0)
        for value in (self.cookie, "SECRET_SUB_ID", "hidden@example.invalid"):
            self.assertNotIn(value.encode(), Path(self.path).read_bytes())

    async def test_unauthorized_and_multiple_sessions_rejected(self):
        for cookie in ("", f"{MINI_COOKIE}=forged", f"{MINI_COOKIE}={self.other}",
                       f"{MINI_COOKIE}={self.cookie}; {STANDALONE_COOKIE}={self.standalone_cookie}"):
            async with self.clients[0].get(
                BASE + "/csrf", headers=self.headers(cookie),
            ) as response:
                self.assertIn(response.status, (401, 403))

    async def test_standalone_session_works_without_browser_owner_id(self):
        headers = self.headers(f"{STANDALONE_COOKIE}={self.standalone_cookie}")
        token = await self.csrf(headers=headers)
        async with await self.issue(token, headers=headers) as response:
            self.assertEqual(response.status, 200)
            proof = (await response.json())["proof"]
        async with await self.consume(token, proof, headers=headers) as response:
            self.assertEqual(response.status, 200)

    async def test_host_origin_fetch_metadata_csrf_content_type_guards(self):
        token = await self.csrf()
        for headers in (
            self.headers(Origin="https://other.example.invalid"),
            self.headers(Host="other.example.invalid"),
            self.headers(**{"Sec-Fetch-Site": "cross-site"}),
            self.headers(**{"X-CSRF-Token": "bad"}),
        ):
            async with self.clients[0].post(BASE + "/issue", json={}, headers=headers) as r:
                self.assertEqual(r.status, 403)
                self.assertEqual(r.headers["Cache-Control"], "no-store")
        async with self.clients[0].post(
            BASE + "/issue", data="{}", headers=self.headers(**{"X-CSRF-Token": token}),
        ) as r:
            self.assertEqual(r.status, 415)
        async with self.clients[0].post(
            BASE + "/issue", json={"owner": OWNER},
            headers=self.headers(**{"X-CSRF-Token": token}),
        ) as r:
            self.assertEqual(r.status, 400)

    async def test_revocation_policy_veto_and_expiry(self):
        token = await self.csrf()
        async with await self.issue(token) as r:
            proof = (await r.json())["proof"]
        self.flags.snapshot.return_value = SimpleNamespace(portal_enabled=False)
        async with await self.consume(token, proof) as r:
            self.assertEqual(r.status, 403)
        self.flags.snapshot.return_value = SimpleNamespace(portal_enabled=True)
        async with await self.consume(token, proof) as r:
            self.assertEqual(r.status, 403)
        async with await self.issue(token) as r:
            proof = (await r.json())["proof"]
        self.mini.revoke(self.cookie)
        async with await self.consume(token, proof) as r:
            self.assertEqual(r.status, 401)

    async def test_cross_worker_sqlite_once_and_rate(self):
        second_ledger = ImportSQLiteLedger(self.path, https_origin=ORIGIN)
        second = await self.new_client(ledger=second_ledger)
        token = await self.csrf()
        async with await self.issue(token) as r:
            proof = (await r.json())["proof"]
        responses = await asyncio.gather(
            self.consume(token, proof),
            self.consume(token, proof, client=second),
        )
        try:
            self.assertEqual(sorted([r.status for r in responses]), [200, 403])
        finally:
            for r in responses:
                await r.release()
        for _ in range(ISSUE_LIMIT - 1):
            async with await self.issue(token) as r:
                self.assertEqual(r.status, 200)
        async with await self.issue(token) as r:
            self.assertEqual(r.status, 429)

    async def test_private_ledger_permissions_and_origin(self):
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)
        with self.assertRaises(ValueError):
            ImportSQLiteLedger(self.path, https_origin="https://evil.example.invalid")
        os.chmod(self.path, 0o644)
        try:
            token = await self.csrf()
            async with await self.issue(token) as r:
                self.assertEqual(r.status, 503)
        finally:
            os.chmod(self.path, 0o600)


if __name__ == "__main__":
    unittest.main()
