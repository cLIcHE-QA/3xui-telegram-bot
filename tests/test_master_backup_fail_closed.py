from __future__ import annotations

import sqlite3
import tarfile
import os
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

    def test_deep_validation_failure_is_not_published(self):
        master = self.manager.sources_root / "x-ui" / "x-ui.db"
        database(master)
        from restore_manager import RestoreManager, BackupInspection
        from dataclasses import replace

        original = RestoreManager.inspect_backup

        def fail_validation(manager, path, *, deep=False, **kwargs):
            inspection = original(manager, path, deep=deep, **kwargs)
            return replace(inspection, valid=False, errors=("synthetic invalid manifest",))

        with patch.object(RestoreManager, "inspect_backup", fail_validation):
            with self.assertRaisesRegex(RuntimeError, "deep validation"):
                self.manager.create_full_backup()
        self.assertEqual(self.archives(), [])
        self.assertEqual(list(self.manager.backup_dir.glob(".backup-pending-*")), [])

    def test_archive_creation_failure_cleans_temporary_file(self):
        master = self.manager.sources_root / "x-ui" / "x-ui.db"
        database(master)
        original = tarfile.TarFile.add

        def failed_add(tar, name, *args, **kwargs):
            raise OSError("synthetic tar failure")

        with patch.object(tarfile.TarFile, "add", failed_add):
            with self.assertRaisesRegex(OSError, "synthetic tar failure"):
                self.manager.create_full_backup()
        self.assertEqual(self.archives(), [])
        self.assertEqual(list(self.manager.backup_dir.glob(".backup-pending-*")), [])

    def test_archive_published_with_private_mode(self):
        master = self.manager.sources_root / "x-ui" / "x-ui.db"
        database(master)
        result = self.manager.create_full_backup()
        self.assertEqual(result.info.path.stat().st_mode & 0o777, 0o600)

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
