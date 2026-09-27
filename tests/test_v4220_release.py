"""Release-prep contract for v4.22.0."""
from __future__ import annotations

from pathlib import Path
import unittest

from version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class V4220ReleaseTests(unittest.TestCase):
    def test_release_version_is_4220(self):
        self.assertEqual(APP_VERSION, "4.22.0")

    def test_current_docs_reference_release_4220(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        admin_setup = (ROOT / "docs" / "ADMIN_SETUP.md").read_text(encoding="utf-8")
        self.assertTrue(readme.startswith("# Telegram-бот для 3x-ui v4.22.0"))
        self.assertIn("Guide ориентирован на release v4.22.0.", admin_setup)
        self.assertIn("git checkout --detach v4.22.0", admin_setup)
        self.assertIn("Bot version: 4.22.0", admin_setup)

    def test_changelog_has_single_release_section(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(
            changelog.count("## v4.22.0 — Группы пользователей"),
            1,
        )
        self.assertIn("user_audience_groups_v4_22_0", changelog)
        self.assertIn("downgrade", changelog)


if __name__ == "__main__":
    unittest.main()
