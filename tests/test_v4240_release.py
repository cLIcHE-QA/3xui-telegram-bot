"""Release-prep contract for v4.24.1."""
from __future__ import annotations

from pathlib import Path
import unittest

from version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class V4241ReleaseTests(unittest.TestCase):
    def test_release_version_is_4241(self):
        self.assertEqual(APP_VERSION, "4.24.1")

    def test_current_docs_reference_release_4241(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        admin_setup = (ROOT / "docs" / "ADMIN_SETUP.md").read_text(encoding="utf-8")
        sqlite_doc = (ROOT / "docs" / "SQLITE_MIGRATIONS.md").read_text(encoding="utf-8")

        self.assertTrue(readme.startswith("# Telegram-бот для 3x-ui v4.24.1"))
        self.assertIn("Guide ориентирован на release v4.24.1.", admin_setup)
        self.assertIn("git checkout --detach v4.24.1", admin_setup)
        self.assertIn("Bot version: 4.24.1", admin_setup)
        self.assertIn(
            "Для `v4.24.0` и `v4.24.1` текущая bot schema version — **5**",
            sqlite_doc,
        )

    def test_release_notes_cover_v4241_hotfix_scope(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(
            changelog.count("## v4.24.1 — Hotfix web diagnostics и IPv6"),
            1,
        )
        section = changelog.split(
            "## v4.24.1 — Hotfix web diagnostics и IPv6",
            1,
        )[1].split("\n## ", 1)[0]

        for needle in (
            "DD.MM.YYYY HH:MM MSK",
            "Reverse DNS",
            "blocked subnets",
            "public IPv6 literals",
            "PAGESPEED_API_KEY",
            "SQLite schema",
        ):
            self.assertIn(needle, section)

    def test_release_is_published_but_v4241_production_acceptance_is_separate(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        self.assertIn(
            "🟠 Опубликовано в `v4.24.1`; GitHub release/CI закрыты, production acceptance ещё не подтверждён в репозитории.",
            roadmap,
        )
        self.assertIn(
            "operational closure остаётся открытым до подтверждённого production smoke",
            roadmap,
        )

    def test_packbot_attribution_is_pinned(self):
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## PackBot", notices)
        self.assertIn(
            "Reviewed revision: `3c4a5bb29626f8b3e28056bd52cd94fdce9f3c1a`",
            notices,
        )
        self.assertIn("License: MIT", notices)
        self.assertIn(
            "PackBot](https://github.com/vladpak1/packbot)",
            readme,
        )

    def test_pagespeed_remains_optional(self):
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
        admin_setup = (ROOT / "docs" / "ADMIN_SETUP.md").read_text(encoding="utf-8")
        self.assertIn("PAGESPEED_API_KEY=", env_example)
        self.assertIn("Optional PageSpeed diagnostics", admin_setup)
        self.assertIn("PAGESPEED_API_KEY=", admin_setup)


if __name__ == "__main__":
    unittest.main()
