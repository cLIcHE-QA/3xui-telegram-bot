"""Release-prep contract for v4.23.2."""
from __future__ import annotations

from pathlib import Path
import unittest

from version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class V4232ReleaseTests(unittest.TestCase):
    def test_release_version_is_4232(self):
        self.assertEqual(APP_VERSION, "4.23.2")

    def test_current_docs_reference_release_4232(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        admin_setup = (ROOT / "docs" / "ADMIN_SETUP.md").read_text(encoding="utf-8")
        sqlite_doc = (ROOT / "docs" / "SQLITE_MIGRATIONS.md").read_text(encoding="utf-8")
        self.assertTrue(readme.startswith("# Telegram-бот для 3x-ui v4.23.2"))
        self.assertIn("Guide ориентирован на release v4.23.2.", admin_setup)
        self.assertIn("git checkout --detach v4.23.2", admin_setup)
        self.assertIn("Bot version: 4.23.2", admin_setup)
        self.assertIn("Для `v4.23.2` текущая bot schema version — **3**", sqlite_doc)

    def test_release_notes_cover_compact_cheburcheck_scope(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        integration = (ROOT / "docs" / "CHEBURCHECK.md").read_text(encoding="utf-8")
        self.assertEqual(
            changelog.count("## v4.23.2 — Компактный результат Cheburcheck"),
            1,
        )
        section = changelog.split(
            "## v4.23.2 — Компактный результат Cheburcheck",
            1,
        )[1].split("\n## ", 1)[0]
        for needle in (
            "/api/v1/probe/{id}",
            "256 KiB",
            "context",
            "SQLite schema остаётся v3",
        ):
            self.assertIn(needle, section)
        self.assertIn("`v4.23.2` опубликован и развернут", roadmap)
        self.assertIn("hotfix `v4.23.3`", roadmap)
        self.assertIn("🌍 Регионы: 11 ответов · 🟢 8 · 🔴 2 · 🟡 1", integration)


if __name__ == "__main__":
    unittest.main()
