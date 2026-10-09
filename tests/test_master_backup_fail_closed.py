from __future__ import annotations

import sqlite3
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backup_manager import BackupManager


def database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE demo(id INTEGER PRIMARY KEY)")


class MasterBackupFailClosedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.manager = BackupManager(str(root / "bot.sqlite3"), str(root / "backups"))
        self.manager.sources_root = root / "sources"
        database(self.manager.db_path)

    def archives(self):
        return list(self.manager.backup_dir.glob("3xui-bot-backup-*.tar.gz"))

    def test_missing_master_db_blocks_full_backup(self):
        with self.assertRaisesRegex(RuntimeError, "required Master x-ui.db"):
            self.manager.create_full_backup()
        self.assertEqual(self.archives(), [])

    def test_unreadable_master_db_cleans_partial_snapshot_and_archive(self):
        master = self.manager.sources_root / "x-ui" / "x-ui.db"
        database(master)
        real = BackupManager._sqlite_backup

        def fail_master(src, dst):
            if src == master:
                dst.write_bytes(b"")
                raise sqlite3.OperationalError("unable to open database file")
            return real(src, dst)

        with patch.object(BackupManager, "_sqlite_backup", side_effect=fail_master):
            with self.assertRaisesRegex(RuntimeError, "snapshot failed"):
                self.manager.create_full_backup()
        self.assertEqual(self.archives(), [])

    def test_corrupt_master_db_blocks_full_backup(self):
        master = self.manager.sources_root / "x-ui" / "x-ui.db"
        master.parent.mkdir(parents=True)
        master.write_bytes(b"invalid")
        with self.assertRaisesRegex(RuntimeError, "snapshot failed"):
            self.manager.create_full_backup()
        self.assertEqual(self.archives(), [])

    def test_valid_master_is_included(self):
        master = self.manager.sources_root / "x-ui" / "x-ui.db"
        database(master)
        result = self.manager.create_full_backup()
        with tarfile.open(result.info.path, "r:gz") as archive:
            self.assertGreater(archive.getmember("x-ui.db").size, 0)
        self.assertIn("x-ui.db", result.included)
        self.assertFalse(any(name.startswith("x-ui.db") for name in result.missing))


if __name__ == "__main__":
    unittest.main()
