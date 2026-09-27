"""Release-prep contract for v4.23.0."""
from __future__ import annotations

from pathlib import Path
import unittest

from version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class V4230ReleaseTests(unittest.TestCase):
    def test_release_version_is_4230(self):
        self.assertEqual(APP_VERSION, "4.23.0")

    def test_current_docs_reference_release_4230(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        admin_setup = (ROOT / "docs" / "ADMIN_SETUP.md").read_text(encoding="utf-8")
        sqlite_doc = (ROOT / "docs" / "SQLITE_MIGRATIONS.md").read_text(encoding="utf-8")
        self.assertTrue(readme.startswith("# Telegram-бот для 3x-ui v4.23.0"))
        self.assertIn("Guide ориентирован на release v4.23.0.", admin_setup)
        self.assertIn("git checkout --detach v4.23.0", admin_setup)
        self.assertIn("Bot version: 4.23.0", admin_setup)
        self.assertIn("Для `v4.23.0` текущая bot schema version — **3**", sqlite_doc)

    def test_changelog_has_single_release_section(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(
            changelog.count("## v4.23.0 — Проверка блокировок Cheburcheck"),
            1,
        )
        self.assertIn("LowderPlay/cheburcheck@0bbd2be8ca4b8f9ded1407597654314fc2a900c6", changelog)
        self.assertIn("Safe Bot Self-Update", changelog)
        self.assertIn("CHEBURCHECK_URL", changelog)


if __name__ == "__main__":
    unittest.main()
