"""#887 D2b: атомарный shared ledger между независимыми web/bot процессами."""
from __future__ import annotations

import asyncio
import hashlib
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiohttp.test_utils import TestClient, TestServer

from subscription_page_standalone import (
    PENDING_COOKIE, SESSION_COOKIE, create_standalone_pilot,
)
from subscription_page_standalone_sqlite import StandaloneSQLiteLedger
from subscription_page_telegram_approval import StandaloneTelegramApproval

NOW = 1_800_000_000
OWNER = 100_001
FOREIGN = 100_002
ORIGIN = "https://web.example.invalid"
HOST = "web.example.invalid"
BASE = "/api/subpage/v1/auth/standalone"
ME = "/api/subpage/v1/standalone/me"


class SharedLedgerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "standalone.sqlite3")
        self.clock = float(NOW)
        self.flags = SimpleNamespace(
            snapshot=AsyncMock(return_value=SimpleNamespace(portal_enabled=True))
        )
        self.service = SimpleNamespace(
            profile=AsyncMock(return_value=SimpleNamespace(
                exists=True, access_status="active", period_status="active",
                plan_name="Пилот", expiry_time=NOW * 1000,
                expiry_known=True, available_locations=2,
            ))
        )
        self.pilots = [
            create_standalone_pilot(
                https_origin=ORIGIN, pilot_ids=frozenset({OWNER}),
                customer_service=self.service, feature_flags=self.flags,
                now=lambda: self.clock, sqlite_path=self.path,
            ) for _ in range(3)
        ]
        self.clients = [TestClient(TestServer(pilot.app)) for pilot in self.pilots]
        for c in self.clients:
            await c.start_server()

    async def asyncTearDown(self):
        for c in self.clients:
            await c.close()
        self.temp.cleanup()

    @staticmethod
    def headers(cookie=None):
        headers = {"Host": HOST, "Origin": ORIGIN}
        if cookie is not None:
            headers["Cookie"] = cookie
        return headers

    async def begin(self, client=0):
        async with self.clients[client].post(
            BASE + "/start", json={}, headers=self.headers()
        ) as r:
            self.assertEqual(r.status, 200)
            code = (await r.json())["challenge"]
            cookie = f"{PENDING_COOKIE}={r.cookies[PENDING_COOKIE].value}"
            return code, cookie

    async def complete(self, worker, code, binding):
        async with self.clients[worker].post(
            BASE + "/complete", json={"challenge": code},
            headers=self.headers(binding),
        ) as r:
            cookie = r.cookies.get(SESSION_COOKIE)
            return r.status, (
                f"{SESSION_COOKIE}={cookie.value}" if cookie is not None else None
            )

    async def test_cross_worker_approval_and_one_time_exchange(self):
        code, bind = await self.begin(0)
        self.assertTrue(self.pilots[1].challenge_pending(code, self.clock))
        self.assertTrue(await self.pilots[1].approve_from_private_telegram(
            code, actor_id=OWNER, chat_id=OWNER, explicitly_confirmed=True,
        ))
        self.assertFalse(await self.pilots[0].approve_from_private_telegram(
            code, actor_id=OWNER, chat_id=OWNER, explicitly_confirmed=True,
        ))
        # Two distinct aiohttp workers race to consume the same approval.
        results = await asyncio.gather(
            self.complete(0, code, bind),
            self.complete(2, code, bind),
        )
        self.assertEqual(sorted(status for status, _ in results), [200, 401])
        session = next(cookie for status, cookie in results if status == 200)
        for worker in (0, 1, 2):
            async with self.clients[worker].get(ME, headers=self.headers(session)) as r:
                self.assertEqual(r.status, 200)
                self.assertEqual((await r.json())["subscription"]["planName"], "Пилот")
        # Stored only hashes, never public challenges or cookie values.
        with sqlite3.connect(self.path) as con:
            pending = con.execute(
                "SELECT challenge_hash,binding_hash FROM standalone_pending"
            ).fetchall()
            sessions = con.execute(
                "SELECT session_hash,owner FROM standalone_sessions"
            ).fetchall()
            self.assertEqual(pending, [])
            self.assertEqual(len(sessions), 1)
            self.assertEqual(len(sessions[0][0]), 32)
            self.assertEqual(sessions[0][1], OWNER)
            self.assertNotEqual(sessions[0][0], session.encode("utf8"))

    async def test_cross_worker_bot_adapter_private_confirm(self):
        code, bind = await self.begin(0)
        adapter = StandaloneTelegramApproval(self.pilots[1])
        message = SimpleNamespace(
            text="/web_login " + code,
            chat=SimpleNamespace(id=OWNER, type="private"),
            from_user=SimpleNamespace(id=OWNER, is_bot=False),
            sender_chat=None, forward_origin=None,
            answer=AsyncMock(return_value=SimpleNamespace(message_id=777)),
        )
        await adapter.handle_message(message)
        self.assertEqual(len(adapter.prompts), 1)
        nonce = next(iter(adapter.prompts))
        cb = SimpleNamespace(
            data="d2bs:yes:" + nonce,
            from_user=SimpleNamespace(id=OWNER, is_bot=False),
            message=SimpleNamespace(
                chat=SimpleNamespace(id=OWNER, type="private"),
                message_id=777,
                edit_reply_markup=AsyncMock(),
            ),
            answer=AsyncMock(),
        )
        await adapter.handle_callback(cb)
        self.assertIn("Вход подтверждён", cb.answer.await_args.args[0])
        status, session = await self.complete(2, code, bind)
        self.assertEqual(status, 200)
        self.assertTrue(session)

    async def test_browser_isolation_and_global_cancel_logout(self):
        code, bind = await self.begin(0)
        other_code, other_bind = await self.begin(2)
        self.assertFalse(await self.pilots[1].approve_from_private_telegram(
            code, actor_id=FOREIGN, chat_id=FOREIGN, explicitly_confirmed=True,
        ))
        self.assertTrue(await self.pilots[2].approve_from_private_telegram(
            code, actor_id=OWNER, chat_id=OWNER, explicitly_confirmed=True,
        ))
        self.assertEqual((await self.complete(2, code, other_bind))[0], 401)
        self.assertEqual((await self.complete(0, other_code, bind))[0], 401)
        self.assertEqual((await self.complete(0, code, bind))[0], 200)
        c, browser = await self.begin(1)
        async with self.clients[0].post(
            BASE + "/cancel", json={"challenge": c},
            headers=self.headers(browser),
        ) as r:
            self.assertEqual(r.status, 200)
        self.assertFalse(self.pilots[1].challenge_pending(c, self.clock))
        self.assertEqual((await self.complete(1, c, browser))[0], 401)
        # New auth cookie is invalid on all workers after one worker logout.
        code, bind = await self.begin(0)
        await self.pilots[2].approve_from_private_telegram(
            code, actor_id=OWNER, chat_id=OWNER, explicitly_confirmed=True,
        )
        status, session = await self.complete(1, code, bind)
        self.assertEqual(status, 200)
        async with self.clients[2].post(
            BASE + "/logout", json={}, headers=self.headers(session)
        ) as r:
            self.assertEqual(r.status, 200)
        async with self.clients[0].get(ME, headers=self.headers(session)) as r:
            self.assertEqual(r.status, 401)

    async def test_expiry_revocation_and_worker_restart(self):
        code, bind = await self.begin(0)
        self.clock += 181
        self.assertFalse(self.pilots[2].challenge_pending(code, self.clock))
        self.assertFalse(await self.pilots[1].approve_from_private_telegram(
            code, actor_id=OWNER, chat_id=OWNER, explicitly_confirmed=True,
        ))
        self.assertEqual((await self.complete(0, code, bind))[0], 401)
        new_code, new_bind = await self.begin(0)
        self.assertTrue(await self.pilots[1].approve_from_private_telegram(
            new_code, actor_id=OWNER, chat_id=OWNER, explicitly_confirmed=True,
        ))
        status, session = await self.complete(1, new_code, new_bind)
        self.assertEqual(status, 200)
        # New instance simulates a restart: same private ledger, no copied dict.
        restored = create_standalone_pilot(
            https_origin=ORIGIN, pilot_ids=frozenset({OWNER}),
            customer_service=self.service, feature_flags=self.flags,
            now=lambda: self.clock, sqlite_path=self.path,
        )
        c = TestClient(TestServer(restored.app))
        await c.start_server()
        try:
            async with c.get(ME, headers=self.headers(session)) as r:
                self.assertEqual(r.status, 200)
        finally:
            await c.close()
        self.flags.snapshot.return_value = SimpleNamespace(portal_enabled=False)
        async with self.clients[2].get(ME, headers=self.headers(session)) as r:
            self.assertEqual(r.status, 403)
        self.flags.snapshot.return_value = SimpleNamespace(portal_enabled=True)
        async with self.clients[0].get(ME, headers=self.headers(session)) as r:
            self.assertEqual(r.status, 401)

    async def test_file_integrity_and_private_permissions_fail_closed(self):
        mode = os.stat(self.path).st_mode & 0o777
        self.assertEqual(mode, 0o600)
        with sqlite3.connect(self.path) as con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertEqual(con.execute("PRAGMA quick_check").fetchone()[0], "ok")
        os.chmod(self.path, 0o644)
        try:
            async with self.clients[0].post(
                BASE + "/start", json={}, headers=self.headers()
            ) as r:
                self.assertEqual(r.status, 503)
        finally:
            os.chmod(self.path, 0o600)
        with tempfile.TemporaryDirectory() as invalid:
            unsafe = Path(invalid) / "unsafe.sqlite3"
            unsafe.symlink_to(self.path)
            with self.assertRaises(ValueError):
                StandaloneSQLiteLedger(unsafe)
        self.clock += 1
        async with self.clients[0].post(
            BASE + "/start", json={}, headers=self.headers()
        ) as r:
            self.assertEqual(r.status, 200)

    async def test_new_isolated_python_process_sees_pending_and_cancel(self):
        code, binding = await self.begin(0)
        worker = Path(__file__).with_name("d2b_ledger_readback_worker.py")
        command = [
            sys.executable, "-I", str(worker), self.path,
            hashlib.sha256(code.encode()).hexdigest(), str(self.clock),
        ]
        pending = subprocess.run(
            command, capture_output=True, text=True, timeout=12, check=True,
        )
        self.assertEqual(pending.stdout.strip(), "PENDING")
        self.assertEqual(pending.stderr, "")
        async with self.clients[2].post(
            BASE + "/cancel", json={"challenge": code},
            headers=self.headers(binding),
        ) as r:
            self.assertEqual(r.status, 200)
        revoked = subprocess.run(
            command, capture_output=True, text=True, timeout=12, check=True,
        )
        self.assertEqual(revoked.stdout.strip(), "ABSENT")
        self.assertEqual(revoked.stderr, "")

    async def test_global_pending_capacity_atomic_and_no_raw_credentials(self):
        from subscription_page_standalone_sqlite import MAX_PENDING
        from unittest.mock import patch
        with patch("subscription_page_standalone_sqlite.MAX_PENDING", 1):
            code, bind = await self.begin(0)
            async with self.clients[2].post(
                BASE + "/start", json={}, headers=self.headers()
            ) as r:
                self.assertEqual(r.status, 503)
            self.assertTrue(self.pilots[1].challenge_pending(code, self.clock))
        with open(self.path, "rb") as con:
            on_disk = con.read()
        self.assertNotIn(code.encode(), on_disk)
        self.assertNotIn(bind.encode(), on_disk)
        self.assertNotIn(b"private@example.invalid", on_disk)


if __name__ == "__main__":
    unittest.main()
