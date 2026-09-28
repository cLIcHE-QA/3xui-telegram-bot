"""Release-prep contract for v4.23.3."""
from __future__ import annotations

from pathlib import Path
import unittest

from version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class V4233ReleaseTests(unittest.TestCase):
    def test_release_version_is_4233(self):
        self.assertEqual(APP_VERSION, "4.23.3")

    def test_current_docs_reference_release_4233(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        admin_setup = (ROOT / "docs" / "ADMIN_SETUP.md").read_text(encoding="utf-8")
        sqlite_doc = (ROOT / "docs" / "SQLITE_MIGRATIONS.md").read_text(encoding="utf-8")
        self.assertTrue(readme.startswith("# Telegram-бот для 3x-ui v4.23.3"))
        self.assertIn("Guide ориентирован на release v4.23.3.", admin_setup)
        self.assertIn("git checkout --detach v4.23.3", admin_setup)
        self.assertIn("Bot version: 4.23.3", admin_setup)
        self.assertIn("Для `v4.23.3` текущая bot schema version — **3**", sqlite_doc)

    def test_release_notes_cover_hotfix_scope(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        deploy = (ROOT / "docs" / "CHEBURCHECK_DEPLOY.md").read_text(encoding="utf-8")
        self.assertEqual(
            changelog.count("## v4.23.3 — Hotfix compact result Cheburcheck"),
            1,
        )
        section = changelog.split(
            "## v4.23.3 — Hotfix compact result Cheburcheck",
            1,
        )[1].split("\n## ", 1)[0]
        for needle in (
            "🟢 не найден",
            "geo.asn",
            "started.online_probes",
            "нет активных региональных сканеров",
            "SQLite schema остаётся v3",
        ):
            self.assertIn(needle, section)
        self.assertIn("🟡 Реализовано в `main`; release `v4.23.3` ещё не опубликован.", roadmap)
        self.assertIn("v4.23.3 не требует rebuild Cheburcheck runtime", deploy)


if __name__ == "__main__":
    unittest.main()
