"""#887 D1b — отдельный чистый процесс для synthetic offline disaster recovery.

Не является испытанием реального VPS. В subprocess не передаётся исходный
каталог или первичный Fernet key; не пишутся plaintext dumps/secrets.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cryptography.fernet import Fernet

from subscription_page_admin import AdminAccount, EncryptedDrafts, password_verifier
from subscription_page_admin_recovery import OfflineD1bRecovery
from subscription_page_admin_vault import EncryptedAdminRoster
from test_subscription_page_admin_recovery import fixture


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "tests" / "d1b_recovery_worker.py"
PASSWORD = "synthetic-disaster-password"
MFA = base64.b32encode(b"synthetic-disaster-owner-enrollment").decode("ascii")
SECOND_MFA = base64.b32encode(b"synthetic-disaster-editor-enrollment").decode("ascii")


class IsolatedDisasterRecoveryDrillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "synthetic-source"
        self.source.mkdir(mode=0o700)
        self.primary = Fernet.generate_key()
        self.backup = Fernet.generate_key()
        self.new_primary = Fernet.generate_key()
        roster = EncryptedAdminRoster(self.source / "private-accounts.enc",
                                      self.primary)
        roster.initialize([
            AdminAccount("owner1", password_verifier(PASSWORD), "owner", MFA),
            AdminAccount("editor1", password_verifier("synthetic-editor-password"),
                         "editor", SECOND_MFA),
        ])
        draft = EncryptedDrafts(self.source / "drafts.sqlite3", self.primary)
        self.assertEqual(draft.save("owner1", 0, fixture())["revision"], 1)
        self.assertEqual(draft.propose("owner1", 1)["state"],
                         "pending_manual_review")
        draft.issue_session("owner1", 17000000,
                            "synthetic-disaster-cookie-hash",
                            "synthetic-disaster-csrf", 120,
                            account_binding="f" * 64)
        self.archive = self.root / "sealed-disaster.fernet"
        OfflineD1bRecovery(self.source, self.primary).backup(
            self.archive, self.backup)
        # Destroy ONLY ephemeral synthetic fixture files: the child process
        # cannot read or discover a surviving copy of the original roster/DB.
        # The old key stays solely in this parent test process.
        shutil.rmtree(self.source)
        self.assertFalse(self.source.exists())
        self.target = self.root / "recovered-from-backup"

    def _worker(self, *, backup_key: bytes | None = None,
                target: Path | None = None) -> subprocess.CompletedProcess[str]:
        keys = {"backup_key": (backup_key or self.backup).decode("ascii"),
                "new_key": self.new_primary.decode("ascii")}
        return subprocess.run(
            [sys.executable, "-I", str(WORKER), str(self.archive),
             str(target or self.target)],
            cwd=self.root,
            input=json.dumps(keys), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=40, check=False,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                 "LANG": "C.UTF-8"},
        )

    def test_fresh_process_recovers_and_smokes_https_policy(self):
        result = self._worker()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout),
                         {"status": "PASS", "drafts": 1,
                          "sessions_revoked": 1, "roster_revision": 1,
                          "https_origin_contract": "PASS"})
        for sensitive in (
            self.backup.decode(), self.new_primary.decode(),
            self.primary.decode(), PASSWORD, MFA, SECOND_MFA,
            "synthetic-disaster-cookie-hash", str(self.root),
        ):
            self.assertNotIn(sensitive, result.stdout + result.stderr)
        self.assertFalse(self.source.exists())
        with sqlite3.connect(self.target / "drafts.sqlite3") as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM admin_sessions").fetchone()[0], 1)
        # Why session count changed: successful fresh HTTPS synthetic login
        # created exactly one new session after recovering revoked zero.
        # The old cookie-hash must not have been restored.
        with sqlite3.connect(self.target / "drafts.sqlite3") as db:
            self.assertEqual(db.execute(
                "SELECT count(*) FROM admin_sessions WHERE token_hash=?",
                ("synthetic-disaster-cookie-hash",)).fetchone()[0], 0)

    def test_wrong_backup_key_never_creates_destination(self):
        result = self._worker(backup_key=Fernet.generate_key())
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr.strip(), "ISOLATED_DRILL_FAIL")
        self.assertFalse(self.target.exists())

    def test_corrupt_backup_never_creates_destination(self):
        self.archive.write_bytes(b"synthetic-tampered-archive")
        result = self._worker()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr.strip(), "ISOLATED_DRILL_FAIL")
        self.assertFalse(self.target.exists())

    def test_no_overwrite_or_silent_second_recovery(self):
        self.assertEqual(self._worker().returncode, 0)
        current = (self.target / "private-accounts.enc").read_bytes()
        retried = self._worker()
        self.assertEqual(retried.returncode, 2)
        self.assertEqual(retried.stderr.strip(), "ISOLATED_DRILL_FAIL")
        self.assertEqual((self.target / "private-accounts.enc").read_bytes(), current)


if __name__ == "__main__":
    unittest.main()
