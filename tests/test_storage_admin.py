from __future__ import annotations

import unittest
from unittest.mock import patch

import storage_admin


class StorageAdminTests(unittest.TestCase):
    def test_human_bytes(self):
        self.assertEqual(storage_admin.human_bytes(0), "0 B")
        self.assertEqual(storage_admin.human_bytes(1024), "1.0 KB")
        self.assertEqual(storage_admin.human_bytes(1024**2), "1.0 MB")

    def test_status_text_handles_empty_state(self):
        with patch.object(
            storage_admin.backup_manager,
            "list_backups",
            return_value=[],
        ), patch.object(
            storage_admin.system_backup,
            "configured_node_names",
            return_value=[],
        ):
            text = storage_admin.backup_status_text()
        self.assertIn("Последняя: ещё не создана", text)
        self.assertIn("Backup нод: не настроен", text)


if __name__ == "__main__":
    unittest.main()
