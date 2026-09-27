"""Release-prep contract for v4.23.1."""
from __future__ import annotations

from pathlib import Path
import unittest

from version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class V4231ReleaseTests(unittest.TestCase):
    def test_release_version_is_4231(self):
        self.assertEqual(APP_VERSION, "4.23.1")

    def test_current_docs_reference_release_4231(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        admin_setup = (ROOT / "docs" / "ADMIN_SETUP.md").read_text(encoding="utf-8")
        sqlite_doc = (ROOT / "docs" / "SQLITE_MIGRATIONS.md").read_text(encoding="utf-8")
        self.assertTrue(readme.startswith("# Telegram-бот для 3x-ui v4.23.1"))
        self.assertIn("Guide ориентирован на release v4.23.1.", admin_setup)
        self.assertIn("git checkout --detach v4.23.1", admin_setup)
        self.assertIn("Bot version: 4.23.1", admin_setup)
        self.assertIn("Для `v4.23.1` текущая bot schema version — **3**", sqlite_doc)

    def test_cheburcheck_hotfix_and_deployment_are_documented(self):
        client = (ROOT / "cheburcheck.py").read_text(encoding="utf-8")
        integration = (ROOT / "docs" / "CHEBURCHECK.md").read_text(encoding="utf-8")
        deploy = (ROOT / "docs" / "CHEBURCHECK_DEPLOY.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

        self.assertIn("MAX_RESPONSE_BYTES = 1024 * 1024", client)
        self.assertIn("response body 1 MiB", integration)
        self.assertIn("postgres:18.6-bookworm", deploy)
        self.assertIn("postgres-data:/var/lib/postgresql", deploy)
        self.assertIn("0bbd2be8ca4b8f9ded1407597654314fc2a900c6", deploy)
        self.assertIn("не входят", deploy)
        self.assertIn("Full Backup", deploy)
        self.assertIn("hotfix `v4.23.1`", roadmap)
        self.assertEqual(
            changelog.count("## v4.23.1 — Cheburcheck hotfix и navigation regression"),
            1,
        )


if __name__ == "__main__":
    unittest.main()
