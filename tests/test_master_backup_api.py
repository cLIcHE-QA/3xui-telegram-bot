from __future__ import annotations

import sqlite3
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from backup_manager import BackupManager
from restore_manager import RestoreManager
from system_backup import SystemBackupService


def sqlite_bytes(path: Path) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE state(value TEXT)")
        db.execute("INSERT INTO state VALUES ('ok')")
    return path.read_bytes()


class MasterApiBackupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.manager = BackupManager(str(root / "bot.sqlite3"), str(root / "backups"))
        sqlite_bytes(self.manager.db_path)
        self.manager.sources_root = root / "unreadable-master-files"
        self.master = root / "mock-master.db"
        self.valid = sqlite_bytes(self.master)

    async def test_master_api_full_backup_independent_of_filesystem(self):
        client = AsyncMock()
        client.download_database.return_value = (self.valid, "x-ui.db")
        service = SystemBackupService(self.manager, (), master_client=client)
        result = await service.create_full_backup()
        client.download_database.assert_awaited_once()
        self.assertIn("x-ui.db", result.included)
        with tarfile.open(result.info.path, "r:gz") as archive:
            self.assertEqual(archive.extractfile("x-ui.db").read(), self.valid)
        inspection = RestoreManager(str(self.manager.db_path), str(self.manager.backup_dir)).inspect_backup(
            result.info.path, deep=True,
        )
        self.assertTrue(inspection.xui_db_ok)
        self.assertTrue(inspection.valid, inspection.errors)

    async def test_master_api_rejects_bad_payload_without_archive(self):
        client = AsyncMock()
        client.download_database.return_value = (b"<html>login</html>", "x-ui.db")
        service = SystemBackupService(self.manager, (), master_client=client)
        with self.assertRaisesRegex(RuntimeError, "non-SQLite"):
            await service.create_full_backup()
        self.assertEqual(list(self.manager.backup_dir.glob("3xui-bot-backup-*")), [])

    async def test_master_api_rejects_bad_sqlite_header_only(self):
        client = AsyncMock()
        client.download_database.return_value = (b"SQLite format 3\x00" + b"0" * 128, "x-ui.db")
        service = SystemBackupService(self.manager, (), master_client=client)
        with self.assertRaisesRegex(RuntimeError, "invalid Master API SQLite"):
            await service.create_full_backup()

    async def test_failed_master_api_cannot_fallback_to_host_files(self):
        master_path = self.manager.sources_root / "x-ui" / "x-ui.db"
        sqlite_bytes(master_path)
        client = AsyncMock()
        client.download_database.side_effect = RuntimeError("panel refused")
        service = SystemBackupService(self.manager, (), master_client=client)
        with self.assertRaisesRegex(RuntimeError, "panel refused"):
            await service.create_full_backup()
        self.assertEqual(list(self.manager.backup_dir.glob("3xui-bot-backup-*")), [])


if __name__ == "__main__":
    unittest.main()
