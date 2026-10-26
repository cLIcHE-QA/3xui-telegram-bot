"""#887 D3g: separate owner-bound Copy/QR permissions and QR privacy tests."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiohttp.test_utils import TestClient, TestServer

from subscription_page_customer import COOKIE as MINI_COOKIE, MiniAppSessions, VerifiedMiniAppIdentity
from subscription_page_standalone import StandalonePilot
from subscription_page_import_http import BASE, create_import_preflight_app
from subscription_page_import_issuer import ReviewedImportClient, reviewed_import_methods
from subscription_page_import_sqlite import ImportSQLiteLedger

NOW = 1800000000.0
ORIGIN = "https://web.example.invalid"
URL_ORIGIN = "https://subscription.example.invalid"
BEARER = URL_ORIGIN + "/sub/PRIVATE_TOKEN"
OWNER = 100001

COPY_ONLY = ReviewedImportClient("ios","copy-client","1.0.0","#887",True,False)
QR_ONLY = ReviewedImportClient("ios","qr-client","1.0.0","#887",False,True)


class D3gCopyQrTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        parent = Path(self.tmp.name) / "private"
        parent.mkdir(mode=0o700)
        self.ledger = ImportSQLiteLedger(str(parent / "import.sqlite3"), https_origin=ORIGIN)
        self.profile = SimpleNamespace(exists=True, access_status="active",
            period_status="active", sub_id="PRIVATE_TOKEN")
        self.service = SimpleNamespace(
            profile=AsyncMock(return_value=self.profile),
            subscription_card=AsyncMock(return_value=SimpleNamespace(
                profile=self.profile,url=BEARER)))
        self.flags = SimpleNamespace(snapshot=AsyncMock(
            return_value=SimpleNamespace(portal_enabled=True)))
        self.mini = MiniAppSessions(ttl=120)
        self.cookie = self.mini.issue(
            VerifiedMiniAppIdentity(OWNER, int(NOW), b"d3g-fixture"), NOW)
        self.standalone = StandalonePilot(
            https_origin=ORIGIN, customer_service=self.service,
            feature_flags=self.flags, pilot_ids=frozenset({OWNER}),
            now=lambda: NOW)
        self.clients = []
        self.client = await self.new_client()

    async def new_client(self, **overrides):
        opts = dict(https_origin=ORIGIN, ledger=self.ledger,
            mini_sessions=self.mini, standalone=self.standalone,
            customer_service=self.service, feature_flags=self.flags,
            pilot_ids=frozenset({OWNER}), enabled=True, now=lambda: NOW,
            csrf_secret=b"x"*32, delivery_enabled=True,
            subscription_origin=URL_ORIGIN, reviewed_clients=(COPY_ONLY,QR_ONLY))
        opts.update(overrides)
        client = TestClient(TestServer(create_import_preflight_app(**opts)))
        await client.start_server()
        self.clients.append(client)
        return client

    async def asyncTearDown(self):
        for c in self.clients:
            await c.close()
        self.tmp.cleanup()

    def headers(self):
        return {"Host":"web.example.invalid","Origin":ORIGIN,
                "Cookie":f"{MINI_COOKIE}={self.cookie}"}

    async def csrf_and_proof(self):
        async with self.client.get(BASE+"/csrf", headers=self.headers()) as r:
            self.assertEqual(r.status,200)
            csrf = (await r.json())["csrfToken"]
        headers = {**self.headers(),"X-CSRF-Token":csrf}
        async with self.client.post(BASE+"/issue",json={},headers=headers) as r:
            self.assertEqual(r.status,200)
            proof = (await r.json())["proof"]
        return csrf,proof

    async def deliver(self,csrf,proof,*,client_id,method,client=None):
        return await (client or self.client).post(BASE+"/deliver",json={
            "proof":proof,"platform":"ios","clientId":client_id,
            "clientVersion":"1.0.0","method":method},
            headers={**self.headers(),"X-CSRF-Token":csrf})

    async def test_copy_only_rejects_qr_and_burns_proof(self):
        csrf,proof=await self.csrf_and_proof()
        async with await self.deliver(csrf,proof,client_id="copy-client",method="qr") as r:
            self.assertEqual(r.status,403)
            self.assertNotIn("PRIVATE_TOKEN",await r.text())
        async with await self.deliver(csrf,proof,client_id="copy-client",method="copy") as r:
            self.assertEqual(r.status,403)
        self.service.subscription_card.assert_not_awaited()
        csrf,proof=await self.csrf_and_proof()
        async with await self.deliver(csrf,proof,client_id="copy-client",method="copy") as r:
            self.assertEqual(r.status,200)
            self.assertEqual(await r.json(),{"subscriptionUrl":BEARER})
            self.assertEqual(r.headers["Cache-Control"],"no-store")

    async def test_qr_only_rejects_copy_and_returns_private_png(self):
        csrf,proof=await self.csrf_and_proof()
        async with await self.deliver(csrf,proof,client_id="qr-client",method="copy") as r:
            self.assertEqual(r.status,403)
        csrf,proof=await self.csrf_and_proof()
        async with await self.deliver(csrf,proof,client_id="qr-client",method="qr") as r:
            self.assertEqual(r.status,200)
            self.assertEqual(r.headers["Content-Type"],"image/png")
            self.assertEqual(r.headers["Cache-Control"],"no-store")
            self.assertEqual(r.headers["Referrer-Policy"],"no-referrer")
            payload=await r.read()
            self.assertTrue(payload.startswith(b"\\x89PNG\\r\\n\\x1a\\n"))
            self.assertNotIn(BEARER.encode(),payload)
            self.assertNotIn("PRIVATE_TOKEN",str(r.headers))
        async with await self.deliver(csrf,proof,client_id="qr-client",method="qr") as r:
            self.assertEqual(r.status,403)

    async def test_method_mandatory_and_invalid_requests_fail_closed(self):
        csrf,proof=await self.csrf_and_proof()
        for method in ("download","handoff","",None,123):
            async with await self.deliver(csrf,proof,client_id="copy-client",method=method) as r:
                self.assertEqual(r.status,400)
                self.assertNotIn(BEARER,await r.text())
        headers={**self.headers(),"X-CSRF-Token":csrf}
        async with self.client.post(BASE+"/deliver",json={
            "proof":proof,"platform":"ios","clientId":"copy-client",
            "clientVersion":"1.0.0"},headers=headers) as r:
            self.assertEqual(r.status,400)
        # Missing/invalid method must not consume the valid proof.
        async with await self.deliver(csrf,proof,client_id="copy-client",method="copy") as r:
            self.assertEqual(r.status,200)

    async def test_qr_cross_process_atomic_and_owner_veto(self):
        second=await self.new_client(ledger=ImportSQLiteLedger(
            str(self.ledger.path),https_origin=ORIGIN))
        csrf,proof=await self.csrf_and_proof()
        responses=await asyncio.gather(
            self.deliver(csrf,proof,client_id="qr-client",method="qr"),
            self.deliver(csrf,proof,client_id="qr-client",method="qr",client=second))
        try:
            self.assertEqual(sorted(r.status for r in responses),[200,403])
            for r in responses:
                self.assertEqual(r.headers["Cache-Control"],"no-store")
        finally:
            for r in responses:r.release()
        csrf,proof=await self.csrf_and_proof()
        self.profile.period_status="expired"
        async with await self.deliver(csrf,proof,client_id="qr-client",method="qr") as r:
            self.assertEqual(r.status,403)
            self.assertNotIn(BEARER,await r.text())

    async def test_reviewed_permissions_require_traceable_and_non_duplicate_evidence(self):
        self.assertEqual(reviewed_import_methods(()),{})
        self.assertEqual(reviewed_import_methods((COPY_ONLY,QR_ONLY)),{
            ("ios","copy-client","1.0.0"):(True,False),
            ("ios","qr-client","1.0.0"):(False,True)})
        for bad in ((COPY_ONLY,COPY_ONLY),
                (ReviewedImportClient("ios","copy-client","1.0.0","invalid",True,False),),
                (ReviewedImportClient("ios","copy-client","1.0.0","#887",False,False),)):
            with self.assertRaises(ValueError):
                reviewed_import_methods(bad)


if __name__=="__main__":
    unittest.main()
