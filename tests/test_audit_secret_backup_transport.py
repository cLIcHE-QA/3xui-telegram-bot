from __future__ import annotations

import io
import stat
import tarfile
import tempfile
import unittest
from pathlib import Path

from restore_manager import RestoreManager


ROOT = Path(__file__).resolve().parents[1]


class SecretBackupTransportAuditTests(unittest.TestCase):
    def test_secret_backup_artifacts_are_not_sent_as_telegram_documents(self):
        for name in ("storage_admin.py", "advanced_nodes.py", "disaster_recovery.py"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("answer_document(", text, name)
            self.assertNotIn("FSInputFile", text, name)

        runtime = (ROOT / "app_runtime.py").read_text(encoding="utf-8")
        self.assertNotIn("send_document(", runtime)
        self.assertNotIn("FSInputFile", runtime)

    def test_legacy_backup_download_callbacks_fail_closed(self):
        navigation = (ROOT / "admin_navigation.py").read_text(encoding="utf-8")
        privileges = (ROOT / "admin_privileges.py").read_text(encoding="utf-8")
        storage = (ROOT / "storage_admin.py").read_text(encoding="utf-8")
        for callback in ("admin:backup:botdb", "admin:backup:full"):
            self.assertNotIn(callback, navigation)
            self.assertNotIn(callback, privileges)
            self.assertNotIn(callback, storage)

    def test_automatic_backup_delivery_option_is_removed(self):
        for path in (
            ROOT / ".env.example",
            ROOT / "config.py",
            ROOT / "app_runtime.py",
            ROOT / "storage_admin.py",
            ROOT / "docs" / "ADMIN_SETUP.md",
        ):
            self.assertNotIn("BACKUP_SEND_TO_ADMINS", path.read_text(encoding="utf-8"), str(path))

    def test_host_side_dr_exports_are_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backup_dir = root / "backups"
            backup = root / "3xui-bot-backup-20261005-000000.tar.gz"

            env_data = b"BOT_TOKEN=placeholder\n"
            nginx_data = b"server {}\n"
            with tarfile.open(backup, "w:gz") as archive:
                env_info = tarfile.TarInfo("bot.env")
                env_info.size = len(env_data)
                archive.addfile(env_info, io.BytesIO(env_data))

                nginx_dir = tarfile.TarInfo("nginx")
                nginx_dir.type = tarfile.DIRTYPE
                archive.addfile(nginx_dir)

                nginx_info = tarfile.TarInfo("nginx/nginx.conf")
                nginx_info.size = len(nginx_data)
                archive.addfile(nginx_info, io.BytesIO(nginx_data))

            manager = RestoreManager(str(root / "bot.sqlite3"), str(backup_dir))

            env_out = manager.export_member(backup, "bot.env", filename="bot.env")
            self.assertEqual(stat.S_IMODE(env_out.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(manager.export_root.stat().st_mode), 0o700)

            nginx_out = manager.export_nginx_bundle(backup)
            self.assertEqual(stat.S_IMODE(nginx_out.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(manager.export_root.stat().st_mode), 0o700)

    def test_security_contract_requires_host_side_transport(self):
        security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Telegram используется только как control UI", security)
        self.assertIn("не прикладываются к сообщениям", security)
        self.assertIn("secret-bearing файлы не прикладываются к Telegram", readme)


if __name__ == "__main__":
    unittest.main()
