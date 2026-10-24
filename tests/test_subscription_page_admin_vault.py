"""D1b #887 offline-only encrypted admin roster and MFA recovery tests.

Synthetic account credentials only. No real enrollment material or network.
"""
from __future__ import annotations

import base64
import os
import sqlite3
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer
from cryptography.fernet import Fernet

from subscription_page_admin import (
    COOKIE, AdminAccount, _totp_at, _totp_key, password_verifier,
    create_editor_app,
)
from subscription_page_admin_vault import EncryptedAdminRoster


OWNER_SEED = base64.b32encode(b"synthetic-owner-enrollment-seed00").decode("ascii")
EDITOR_SEED = base64.b32encode(b"synthetic-editor-enrollment-seed0").decode("ascii")
PASSWORD = "synthetic-owner-password-test"


def accounts() -> list[AdminAccount]:
    return [
        AdminAccount("owner1", password_verifier(PASSWORD), "owner", OWNER_SEED),
        AdminAccount("editor1", password_verifier(PASSWORD), "editor", EDITOR_SEED),
    ]


class AdminRosterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.key = Fernet.generate_key()
        self.path = self.directory / "private-accounts.enc"
        self.roster = EncryptedAdminRoster(self.path, self.key)
        self.initial = accounts()

    def init(self):
        self.assertEqual(self.roster.initialize(self.initial), 1)

    def test_initialize_encrypts_full_roster_and_rejects_overwrite(self):
        self.init()
        raw = self.path.read_bytes()
        self.assertNotIn(self.initial[0].password_hash.encode(), raw)
        self.assertNotIn(OWNER_SEED.encode(), raw)
        self.assertNotIn(EDITOR_SEED.encode(), raw)
        self.assertNotIn(PASSWORD.encode(), raw)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.path.with_name(self.path.name + ".lock").stat().st_mode & 0o777, 0o600)
        version, loaded = self.roster.snapshot()
        self.assertEqual((version, loaded), (1, self.initial))
        with self.assertRaises(FileExistsError):
            self.roster.initialize(self.initial)
        self.assertEqual(self.roster.snapshot(), (1, self.initial))

    def test_rotate_password_is_revision_guarded_and_preserves_other_accounts(self):
        self.init()
        rotated_to = "synthetic-rotated-password-2026"
        self.assertEqual(self.roster.rotate_password("owner1", rotated_to, 1), 2)
        version, updated = self.roster.snapshot()
        self.assertEqual(version, 2)
        self.assertNotEqual(updated[0].password_hash, self.initial[0].password_hash)
        self.assertEqual(updated[0].totp_secret_b32, OWNER_SEED)
        self.assertEqual(updated[1], self.initial[1])
        self.assertNotIn(rotated_to.encode(), self.path.read_bytes())
        with self.assertRaises(ValueError):
            self.roster.rotate_password("owner1", "retry-stale-password", 1)
        with self.assertRaises(ValueError):
            self.roster.rotate_password("missing", "synthetic-new-password", 2)
        self.assertEqual(self.roster.snapshot()[0], 2)
        self.assertEqual(list(self.directory.glob(".*.tmp")), [])

    def test_parallel_writers_cannot_reuse_revision(self):
        self.init()
        def rotate(name: str, new: str):
            try:
                return self.roster.rotate_password(name, new, 1)
            except ValueError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(rotate, "owner1", "synthetic-first-rotated"),
                pool.submit(rotate, "editor1", "synthetic-second-rotated"),
            ]
            results = [f.result() for f in futures]
        self.assertEqual(results.count(2), 1)
        self.assertEqual(results.count(None), 1)
        self.assertEqual(self.roster.snapshot()[0], 2)

    def test_mfa_recovery_requires_proof_and_never_exposes_seed_in_repr(self):
        self.init()
        pending = self.roster.prepare_mfa_recovery("owner1")
        self.assertEqual((pending.username, pending.expected_revision), ("owner1", 1))
        self.assertNotEqual(pending.secret_b32, OWNER_SEED)
        self.assertNotIn(pending.secret_b32, repr(pending))
        self.assertNotIn(pending.secret_b32.encode(), self.path.read_bytes())
        with self.assertRaises(ValueError):
            self.roster.confirm_mfa_recovery(pending, "invalid")
        self.assertEqual(self.roster.snapshot()[0], 1)
        valid_code = _totp_at(_totp_key(pending.secret_b32), int(time.time() // 30))
        self.assertEqual(self.roster.confirm_mfa_recovery(pending, valid_code), 2)
        revision, new_accounts = self.roster.snapshot()
        self.assertEqual(revision, 2)
        self.assertEqual(new_accounts[0].totp_secret_b32, pending.secret_b32)
        self.assertEqual(new_accounts[0].password_hash, self.initial[0].password_hash)
        self.assertEqual(new_accounts[1], self.initial[1])
        self.assertNotIn(pending.secret_b32.encode(), self.path.read_bytes())
        with self.assertRaises(ValueError):
            self.roster.confirm_mfa_recovery(pending, valid_code)
        self.assertEqual(self.roster.snapshot()[0], 2)

    def test_mfa_recovery_can_rotate_password_together_atomically(self):
        self.init()
        pending = self.roster.prepare_mfa_recovery("owner1")
        new_password = "synthetic-password-and-MFA-rotation"
        proof = _totp_at(_totp_key(pending.secret_b32), int(time.time() // 30))
        self.assertEqual(self.roster.confirm_mfa_recovery(
            pending, proof, new_password=new_password), 2)
        current = self.roster.load_accounts()
        self.assertNotEqual(current[0].password_hash, self.initial[0].password_hash)
        self.assertEqual(current[0].totp_secret_b32, pending.secret_b32)
        self.assertNotIn(new_password.encode(), self.path.read_bytes())

    def test_missing_owner_duplicate_seed_and_bad_metadata_refused(self):
        with self.assertRaises(ValueError):
            self.roster.initialize([AdminAccount(
                "editor1", self.initial[1].password_hash, "editor", EDITOR_SEED)])
        with self.assertRaises(ValueError):
            self.roster.initialize([self.initial[0], AdminAccount(
                "editor1", self.initial[1].password_hash, "editor", OWNER_SEED)])
        with self.assertRaises(ValueError):
            self.roster.initialize([self.initial[0], self.initial[0]])
        self.assertFalse(self.path.exists())
        self.init()

    def test_refuses_world_readable_file_and_symlink(self):
        self.init()
        os.chmod(self.path, 0o644)
        with self.assertRaises(ValueError):
            self.roster.snapshot()
        os.chmod(self.path, 0o600)
        relocated = self.directory / "plain-link.enc"
        relocated.symlink_to(self.path)
        other = EncryptedAdminRoster(relocated, self.key)
        with self.assertRaises((ValueError, OSError)):
            other.snapshot()

    def test_refuses_wrong_key_and_corrupted_ciphertext(self):
        self.init()
        with self.assertRaises(ValueError):
            EncryptedAdminRoster(self.path, Fernet.generate_key()).snapshot()
        self.path.write_bytes(b"not-Fernet-data")
        with self.assertRaises(ValueError):
            self.roster.snapshot()


class AdminRosterHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.key = Fernet.generate_key()
        self.path = Path(self.tmp.name) / "admin-accounts.enc"
        self.roster = EncryptedAdminRoster(self.path, self.key)
        self.roster.initialize(accounts())
        self.db = Path(self.tmp.name) / "drafts.sqlite3"
        self.app = create_editor_app(
            accounts_loader=self.roster.load_accounts, db_path=self.db,
            encryption_key=self.key, https_origin="https://admin.example.test")
        self.client = TestClient(TestServer(self.app))
        await self.client.start_server()
        self.api = "/admin/subpage/api"
        self.origin = {"Host": "admin.example.test", "Origin": "https://admin.example.test"}

    async def asyncTearDown(self):
        await self.client.close()

    async def login(self, password: str = PASSWORD, otp: str | None = None):
        return await self.client.post(
            self.api + "/session", headers=self.origin,
            json={"username": "owner1", "password": password,
                  "otp": otp or _totp_at(_totp_key(OWNER_SEED), int(time.time() // 30))})

    async def test_dynamic_roster_rotation_invalidates_live_cookie_without_restart(self):
        logged = await self.login()
        self.assertEqual(logged.status, 200)
        headers = {**self.origin, "Cookie": f"{COOKIE}={logged.cookies[COOKIE].value}"}
        self.assertEqual((await self.client.get(self.api + "/session", headers=headers)).status, 200)
        self.assertEqual(self.roster.rotate_password(
            "owner1", "synthetic-rotated-password-2026", 1), 2)
        self.assertEqual((await self.client.get(self.api + "/session", headers=headers)).status, 401)
        old_password = await self.login()
        self.assertEqual(old_password.status, 401)
        with sqlite3.connect(self.db) as con:
            count = con.execute("SELECT COUNT(*) FROM admin_sessions").fetchone()[0]
            self.assertEqual(count, 0)

    async def test_dynamic_roster_mfa_recovery_invalidates_live_cookie(self):
        logged = await self.login()
        self.assertEqual(logged.status, 200)
        headers = {**self.origin, "Cookie": f"{COOKIE}={logged.cookies[COOKIE].value}"}
        pending = self.roster.prepare_mfa_recovery("owner1")
        proof = _totp_at(_totp_key(pending.secret_b32), int(time.time() // 30))
        self.roster.confirm_mfa_recovery(pending, proof)
        denied = await self.client.get(self.api + "/draft", headers=headers)
        self.assertEqual(denied.status, 401)
        obsolete_code = await self.login()
        self.assertEqual(obsolete_code.status, 401)

    async def test_loader_absent_or_unreadable_denies_requests_without_static_fallback(self):
        logged = await self.login()
        self.assertEqual(logged.status, 200)
        headers = {**self.origin, "Cookie": f"{COOKIE}={logged.cookies[COOKIE].value}"}
        self.path.write_bytes(b"synthetic-invalid-roster")
        self.assertEqual((await self.client.get(self.api + "/session", headers=headers)).status, 503)
        self.assertEqual((await self.login()).status, 503)

    def test_requires_exactly_one_account_source(self):
        with self.assertRaises(ValueError):
            create_editor_app(
                accounts_loader=self.roster.load_accounts, accounts=accounts(),
                db_path=self.db, encryption_key=self.key,
                https_origin="https://admin.example.test")
        with self.assertRaises(ValueError):
            create_editor_app(
                db_path=self.db, encryption_key=self.key,
                https_origin="https://admin.example.test")


if __name__ == "__main__":
    unittest.main()
