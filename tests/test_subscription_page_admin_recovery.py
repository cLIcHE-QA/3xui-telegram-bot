"""#887 D1b offline sealed backup / recovery / Fernet staging regressions.

Synthetic data only; tests MUST NOT contain operator credentials or keys.
"""
from __future__ import annotations

import base64
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet

from subscription_page_admin import AdminAccount, EncryptedDrafts, password_verifier
from subscription_page_admin_vault import EncryptedAdminRoster
from subscription_page_admin_recovery import OfflineD1bRecovery


CODES = ("en", "ru", "zh", "fa", "fr")
OWNER_SEED = base64.b32encode(b"synthetic-owner-recovery-seed-2026").decode("ascii")
EDITOR_SEED = base64.b32encode(b"synthetic-editor-recovery-seed-2026").decode("ascii")


def fixture() -> dict:
    # An actual schema-valid but wholly synthetic config, not an operator JSON.
    loc = lambda v: {code: v + "-" + code for code in CODES}
    return {
        "locales": list(CODES), "version": "1",
        "uiConfig": {"subscriptionInfoBlockType": "expanded",
                     "installationGuidesBlockType": "cards"},
        "platforms": {
            "ios": {"displayName": loc("iOS"), "svgIconKey": "AppleIcon",
                    "apps": [{"name": "Synthetic", "featured": True,
                              "svgIconKey": "Demo", "blocks": [{
                                  "title": loc("Install"),
                                  "description": loc("Synthetic only"),
                                  "svgIconKey": "Plus",
                                  "svgIconColor": "#18a5f9", "buttons": [{
                                      "link": "https://example.invalid/demo",
                                      "type": "external",
                                      "text": loc("Download"),
                                      "svgIconKey": "ExternalLink"}]}]}]}
        },
        "svgLibrary": {"Demo": '<svg xmlns="http://www.w3.org/2000/svg"/>'},
        "baseSettings": {"metaTitle": "SYNTHETIC", "metaDescription": "Offline",
                         "hideGetLinkButton": False, "showConnectionKeys": False},
        "baseTranslations": {"getLink": loc("Get")},
        "brandingSettings": {"title": "Synthetic VPN",
                             "logoUrl": "", "supportUrl": ""},
    }


class OfflineBackupAndRotationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "private-source"
        self.source.mkdir(mode=0o700)
        self.key = Fernet.generate_key()
        self.backup_key = Fernet.generate_key()
        self.new_key = Fernet.generate_key()
        self.roster_path = self.source / "private-accounts.enc"
        self.db_path = self.source / "drafts.sqlite3"
        self.accounts = [
            AdminAccount("owner1", password_verifier("synthetic-owner-password"),
                         "owner", OWNER_SEED),
            AdminAccount("editor1", password_verifier("synthetic-editor-password"),
                         "editor", EDITOR_SEED),
        ]
        self.roster = EncryptedAdminRoster(self.roster_path, self.key)
        self.roster.initialize(self.accounts)
        self.store = EncryptedDrafts(self.db_path, self.key)
        self.document = fixture()
        self.assertEqual(self.store.save("owner1", 0, self.document)["revision"], 1)
        self.assertEqual(self.store.propose("owner1", 1)["state"], "pending_manual_review")
        self.store.issue_session(
            "owner1", 17000000, "synthetic-cookie-digest", "synthetic-csrf", 120,
            account_binding="f" * 64)
        self.recovery = OfflineD1bRecovery(self.source, self.key)
        self.sealed = self.root / "synthetic-backup.fernet"

    def _session_count(self, path: Path) -> int:
        with sqlite3.connect(path) as conn:
            return conn.execute("SELECT COUNT(*) FROM admin_sessions").fetchone()[0]

    def test_complete_encrypted_backup_restore_roundtrip(self):
        original_roster = self.roster_path.read_bytes()
        original_db = self.db_path.read_bytes()
        self.assertEqual(self.recovery.backup(self.sealed, self.backup_key), 1)
        ciphertext = self.sealed.read_bytes()
        self.assertEqual(self.sealed.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(self.accounts[0].password_hash.encode(), ciphertext)
        self.assertNotIn(OWNER_SEED.encode(), ciphertext)
        self.assertNotIn(b"synthetic-cookie-digest", ciphertext)
        self.assertNotIn(b"SYNTHETIC", ciphertext)
        destination = self.root / "restored"
        receipt = self.recovery.restore(self.sealed, self.backup_key, destination)
        self.assertEqual((receipt.revision, receipt.drafts, receipt.revoked_sessions),
                         (1, 1, 1))
        self.assertEqual(destination.stat().st_mode & 0o777, 0o700)
        restored_roster = EncryptedAdminRoster(
            destination / "private-accounts.enc", self.key)
        self.assertEqual(restored_roster.snapshot(), (1, self.accounts))
        restored_db = EncryptedDrafts(destination / "drafts.sqlite3", self.key)
        self.assertEqual(restored_db.current(), (1, self.document))
        with sqlite3.connect(destination / "drafts.sqlite3") as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM draft_proposals").fetchone()[0], 1)
            self.assertEqual(db.execute(
                "SELECT last_step FROM admin_totp_replay WHERE username='owner1'"
            ).fetchone()[0], 17000000)
        self.assertEqual(self._session_count(destination / "drafts.sqlite3"), 0)
        self.assertEqual(self._session_count(self.db_path), 1)
        self.assertEqual(self.roster_path.read_bytes(), original_roster)
        self.assertEqual(self.db_path.read_bytes(), original_db)

    def test_stage_key_rotation_preserves_data_revokes_cookies_and_keeps_source(self):
        self.recovery.backup(self.sealed, self.backup_key)
        old_roster = self.roster_path.read_bytes()
        old_db = self.db_path.read_bytes()
        destination = self.root / "rotation-stage"
        receipt = self.recovery.stage_rotation(destination, self.new_key)
        self.assertEqual((receipt.revision, receipt.drafts, receipt.revoked_sessions),
                         (1, 1, 1))
        self.assertEqual(EncryptedAdminRoster(
            destination / "private-accounts.enc", self.new_key).snapshot(),
            (1, self.accounts))
        migrated = EncryptedDrafts(destination / "drafts.sqlite3", self.new_key)
        self.assertEqual(migrated.current(), (1, self.document))
        self.assertEqual(self._session_count(destination / "drafts.sqlite3"), 0)
        with sqlite3.connect(destination / "drafts.sqlite3") as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM draft_proposals").fetchone()[0], 1)
            self.assertEqual(db.execute(
                "SELECT last_step FROM admin_totp_replay WHERE username='owner1'"
            ).fetchone()[0], 17000000)
        with self.assertRaises(ValueError):
            EncryptedAdminRoster(destination / "private-accounts.enc", self.key).snapshot()
        self.assertEqual(self.roster_path.read_bytes(), old_roster)
        self.assertEqual(self.db_path.read_bytes(), old_db)
        self.assertEqual(self.store.current(), (1, self.document))
        # Old backup and old key still restore to a separate verified location.
        restored = self.root / "emergency-restore"
        self.recovery.restore(self.sealed, self.backup_key, restored)
        self.assertEqual(EncryptedDrafts(
            restored / "drafts.sqlite3", self.key).current(), (1, self.document))

    def test_sealed_backup_cannot_overwrite_and_requires_distinct_key(self):
        with self.assertRaises(ValueError):
            self.recovery.backup(self.sealed, self.key)
        self.assertFalse(self.sealed.exists())
        self.recovery.backup(self.sealed, self.backup_key)
        original = self.sealed.read_bytes()
        with self.assertRaises(FileExistsError):
            self.recovery.backup(self.sealed, self.backup_key)
        self.assertEqual(self.sealed.read_bytes(), original)
        self.assertFalse(list(self.root.glob("*.stage")))

    def test_wrong_backup_key_and_tampering_fail_closed(self):
        self.recovery.backup(self.sealed, self.backup_key)
        with self.assertRaises(ValueError):
            self.recovery.restore(self.sealed, Fernet.generate_key(),
                                  self.root / "wrong-key")
        self.assertFalse((self.root / "wrong-key").exists())
        self.sealed.write_bytes(b"invalid-sealed-backup")
        with self.assertRaises(ValueError):
            self.recovery.restore(self.sealed, self.backup_key,
                                  self.root / "tampered")
        self.assertFalse((self.root / "tampered").exists())

    def test_invalid_source_draft_or_wrong_key_blocks_backup_and_rotation(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute("UPDATE draft_revisions SET content=? WHERE revision=1",
                       (b"invalid-plaintext-not-fernet",))
        with self.assertRaises(ValueError):
            self.recovery.backup(self.sealed, self.backup_key)
        self.assertFalse(self.sealed.exists())
        with self.assertRaises(ValueError):
            self.recovery.stage_rotation(self.root / "corrupt", self.new_key)
        self.assertFalse((self.root / "corrupt").exists())
        wrong = OfflineD1bRecovery(self.source, Fernet.generate_key())
        with self.assertRaises(ValueError):
            wrong.stage_rotation(self.root / "bad-key", self.new_key)
        self.assertFalse((self.root / "bad-key").exists())

    def test_existing_restore_or_rotation_target_is_never_overwritten(self):
        self.recovery.backup(self.sealed, self.backup_key)
        existing = self.root / "exists"
        existing.mkdir(mode=0o700)
        sentinel = existing / "marker"
        sentinel.write_text("original")
        with self.assertRaises(FileExistsError):
            self.recovery.restore(self.sealed, self.backup_key, existing)
        with self.assertRaises(FileExistsError):
            self.recovery.stage_rotation(existing, self.new_key)
        self.assertEqual(sentinel.read_text(), "original")

    def test_wrong_rotation_key_and_source_filename_rejected(self):
        with self.assertRaises(ValueError):
            self.recovery.stage_rotation(self.root / "same-key", self.key)
        self.assertFalse((self.root / "same-key").exists())
        with self.assertRaises(ValueError):
            OfflineD1bRecovery(self.source, self.key, db_name="../other.sqlite3")
        with self.assertRaises(ValueError):
            OfflineD1bRecovery(self.source, self.key, roster_name="drafts.sqlite3")

    def test_backup_not_published_when_post_write_verification_fails(self):
        # No partial/corrupt backup must be advertised as successful.
        with patch("subscription_page_admin_recovery._decode_database",
                   side_effect=ValueError("synthetic verification failure")):
            with self.assertRaises(ValueError):
                self.recovery.backup(self.sealed, self.backup_key)
        self.assertFalse(self.sealed.exists())
        self.assertFalse(list(self.root.glob("*.stage")))

    def test_recovery_refuses_unsafe_parent_and_source_files(self):
        public = self.root / "public"
        public.mkdir(mode=0o755)
        with self.assertRaises(ValueError):
            self.recovery.backup(public / "sealed.bin", self.backup_key)
        self.assertFalse((public / "sealed.bin").exists())
        self.recovery.backup(self.sealed, self.backup_key)
        with self.assertRaises(ValueError):
            self.recovery.restore(self.sealed, self.backup_key, public / "restored")
        self.assertFalse((public / "restored").exists())
        link = self.source / "db-link.sqlite3"
        link.symlink_to(self.db_path)
        with self.assertRaises(ValueError):
            OfflineD1bRecovery(self.source, self.key, db_name="db-link.sqlite3").backup(
                self.root / "backup-of-link", self.backup_key)

    def test_disaster_recovery_without_original_fernet_key_or_source(self):
        # The operator knows only the independently held backup key and has
        # generated a fresh replacement key. No original key is passed in.
        self.recovery.backup(self.sealed, self.backup_key)
        destination = self.root / "lost-key-recovery"
        result = OfflineD1bRecovery.recover_lost_key(
            self.sealed, self.backup_key, destination, self.new_key)
        self.assertEqual((result.revision, result.drafts, result.revoked_sessions),
                         (1, 1, 1))
        self.assertEqual(EncryptedAdminRoster(
            destination / "private-accounts.enc", self.new_key).snapshot(),
            (1, self.accounts))
        self.assertEqual(EncryptedDrafts(
            destination / "drafts.sqlite3", self.new_key).current(),
            (1, self.document))
        self.assertEqual(self._session_count(destination / "drafts.sqlite3"), 0)
        with sqlite3.connect(destination / "drafts.sqlite3") as db:
            self.assertEqual(db.execute(
                "SELECT last_step FROM admin_totp_replay WHERE username='owner1'"
            ).fetchone()[0], 17000000)
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM draft_proposals").fetchone()[0], 1)
        # Original source and sealed backup remain available for rollback.
        self.assertEqual(self.store.current(), (1, self.document))
        self.assertFalse((self.root / "replacement-primary-key").exists())

    def test_recovery_wrong_backup_key_and_reused_primary_key_rejected(self):
        self.recovery.backup(self.sealed, self.backup_key)
        with self.assertRaises(ValueError):
            OfflineD1bRecovery.recover_lost_key(
                self.sealed, Fernet.generate_key(), self.root / "unauthorized",
                self.new_key)
        with self.assertRaises(ValueError):
            OfflineD1bRecovery.recover_lost_key(
                self.sealed, self.backup_key, self.root / "reused",
                self.key)
        self.assertFalse((self.root / "unauthorized").exists())
        self.assertFalse((self.root / "reused").exists())

    def test_key_escrow_is_inside_sealed_payload_not_exposed_on_disk(self):
        self.recovery.backup(self.sealed, self.backup_key)
        sealed = self.sealed.read_bytes()
        self.assertNotIn(self.key, sealed)
        self.assertNotIn(self.backup_key, sealed)
        contents = json.loads(Fernet(self.backup_key).decrypt(sealed))
        self.assertEqual(contents["fernet_key"], self.key.decode("ascii"))
        # Old non-escrow schema cannot falsely advertise full key recovery.
        del contents["fernet_key"]
        broken = self.root / "legacy-without-escrow.bin"
        broken.write_bytes(Fernet(self.backup_key).encrypt(
            json.dumps(contents).encode("utf-8")))
        os.chmod(broken, 0o600)
        with self.assertRaises(ValueError):
            OfflineD1bRecovery.recover_lost_key(
                broken, self.backup_key, self.root / "invalid-schema",
                self.new_key)
        self.assertFalse((self.root / "invalid-schema").exists())

    def test_backup_rotation_with_no_live_sessions(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute("DELETE FROM admin_sessions")
        self.recovery.backup(self.sealed, self.backup_key)
        rotated = self.recovery.stage_rotation(self.root / "rotated-empty", self.new_key)
        self.assertEqual(rotated.revoked_sessions, 0)
        self.assertEqual(rotated.drafts, 1)


if __name__ == "__main__":
    unittest.main()
