from __future__ import annotations

import io
import json
import sqlite3
import tarfile
import tempfile
import unittest
from pathlib import Path

from restore_manager import RestoreManager, RestoreError


def make_sqlite_bytes(value: str) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "db.sqlite3"
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE state(value TEXT NOT NULL)")
            db.execute("INSERT INTO state(value) VALUES (?)", (value,))
            db.commit()
        return path.read_bytes()


def read_sqlite_value(path: Path) -> str:
    with sqlite3.connect(path) as db:
        row = db.execute("SELECT value FROM state").fetchone()
    return str(row[0])


def write_backup(path: Path, *, bot_db: bytes, member_name: str = "bot.sqlite3") -> None:
    manifest = json.dumps({"version": "4.16.0-test"}).encode()
    with tarfile.open(path, "w:gz") as tar:
        info = tarfile.TarInfo("manifest.json")
        info.size = len(manifest)
        tar.addfile(info, io.BytesIO(manifest))

        db_info = tarfile.TarInfo(member_name)
        db_info.size = len(bot_db)
        tar.addfile(db_info, io.BytesIO(bot_db))


class RestoreRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "data" / "bot.sqlite3"
        self.db_path.parent.mkdir(parents=True)
        self.db_path.write_bytes(make_sqlite_bytes("live"))
        self.backup_dir = self.root / "backups"
        self.backup_dir.mkdir()
        self.manager = RestoreManager(str(self.db_path), str(self.backup_dir))

    def tearDown(self):
        self.tmp.cleanup()

    def test_malformed_archive_and_unsafe_member_fail_closed(self):
        broken = self.backup_dir / "3xui-bot-backup-broken.tar.gz"
        broken.write_bytes(b"not a tar archive")
        inspected = self.manager.inspect_backup(broken, deep=True)
        self.assertFalse(inspected.valid)
        self.assertTrue(inspected.errors)

        traversal = self.backup_dir / "3xui-bot-backup-traversal.tar.gz"
        payload = make_sqlite_bytes("backup")
        write_backup(traversal, bot_db=payload, member_name="../bot.sqlite3")
        inspected = self.manager.inspect_backup(traversal, deep=True)
        self.assertFalse(inspected.valid)
        self.assertTrue(any("Небезопасный путь" in err for err in inspected.errors))

    def test_stage_requires_valid_bot_database_and_does_not_create_pending_marker_on_failure(self):
        invalid = self.backup_dir / "3xui-bot-backup-invalid.tar.gz"
        write_backup(invalid, bot_db=b"not sqlite")

        with self.assertRaises(RestoreError):
            self.manager.stage_bot_restore(invalid, actor_id=42)

        self.assertFalse(self.manager.pending_bot_restore())
        self.assertEqual(read_sqlite_value(self.db_path), "live")

    def test_stage_and_bootstrap_restore_are_atomic_and_keep_rescue_copy(self):
        backup = self.backup_dir / "3xui-bot-backup-good.tar.gz"
        write_backup(backup, bot_db=make_sqlite_bytes("restored"))

        marker = self.manager.stage_bot_restore(backup, actor_id=42)
        self.assertTrue(self.manager.pending_bot_restore())
        rescue = Path(marker["rescue_path"])
        self.assertTrue(rescue.is_file())
        self.assertEqual(read_sqlite_value(rescue), "live")
        self.assertEqual(read_sqlite_value(self.db_path), "live")

        result = self.manager.perform_pending_bot_restore()
        self.assertEqual(result["status"], "success")
        self.assertEqual(read_sqlite_value(self.db_path), "restored")
        self.assertFalse(self.manager.pending_bot_restore())
        self.assertFalse((self.manager.pending_root / "bot.sqlite3").exists())

        history = self.manager.recent_history(limit=10)
        statuses = [item.get("status") for item in history]
        self.assertIn("success", statuses)
        self.assertIn("scheduled", statuses)

    def test_tampered_staged_database_fails_without_replacing_live_database_or_replaying(self):
        backup = self.backup_dir / "3xui-bot-backup-good.tar.gz"
        write_backup(backup, bot_db=make_sqlite_bytes("restored"))
        self.manager.stage_bot_restore(backup, actor_id=7)

        staged = self.manager.pending_root / "bot.sqlite3"
        staged.write_bytes(make_sqlite_bytes("tampered"))

        result = self.manager.perform_pending_bot_restore()
        self.assertEqual(result["status"], "failed")
        self.assertIn("SHA-256 mismatch", result["error"])
        self.assertEqual(read_sqlite_value(self.db_path), "live")
        self.assertFalse(self.manager.pending_bot_restore())
        self.assertIsNone(self.manager.perform_pending_bot_restore())

        failed_markers = list(self.manager.pending_root.glob("failed-*.json"))
        self.assertEqual(len(failed_markers), 1)

    def test_consume_boot_result_is_one_shot(self):
        self.manager.restore_root.mkdir(parents=True, exist_ok=True)
        self.manager.result_path.write_text('{"status":"failed","error":"synthetic"}', encoding="utf-8")

        first = self.manager.consume_boot_result()
        second = self.manager.consume_boot_result()

        self.assertEqual(first["status"], "failed")
        self.assertIsNone(second)


if __name__ == "__main__":
    unittest.main()
