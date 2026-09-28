"""Release-prep contract for v4.24.0."""
from __future__ import annotations

from pathlib import Path
import unittest

from version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class V4240ReleaseTests(unittest.TestCase):
    def test_release_version_is_4240(self):
        self.assertEqual(APP_VERSION, "4.24.0")

    def test_current_docs_reference_release_4240(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        admin_setup = (ROOT / "docs" / "ADMIN_SETUP.md").read_text(encoding="utf-8")
        sqlite_doc = (ROOT / "docs" / "SQLITE_MIGRATIONS.md").read_text(encoding="utf-8")

        self.assertTrue(readme.startswith("# Telegram-бот для 3x-ui v4.24.0"))
        self.assertIn("Guide ориентирован на release v4.24.0.", admin_setup)
        self.assertIn("git checkout --detach v4.24.0", admin_setup)
        self.assertIn("Bot version: 4.24.0", admin_setup)
        self.assertIn(
            "Для `v4.24.0` текущая bot schema version — **5**",
            sqlite_doc,
        )

    def test_release_notes_cover_website_monitoring_scope(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(
            changelog.count("## v4.24.0 — Мониторинг сайтов и web diagnostics"),
            1,
        )
        section = changelog.split(
            "## v4.24.0 — Мониторинг сайтов и web diagnostics",
            1,
        )[1].split("\n## ", 1)[0]

        for needle in (
            "🌐 Мониторинг сайтов",
            "SSRF-safe",
            "PAGESPEED_API_KEY",
            "website_monitoring_v4_24_0",
            "website_watcher_lifecycle_v4_24_0",
            "3c4a5bb29626f8b3e28056bd52cd94fdce9f3c1a",
            "dnspython",
            "qrcode[pil]",
        ):
            self.assertIn(needle, section)

    def test_release_is_ready_for_production_acceptance_not_closed(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        self.assertIn(
            "🟡 Реализовано для `v4.24.0`; production acceptance ещё не закрыт.",
            roadmap,
        )
        self.assertIn(
            "Критерий окончательного закрытия остаётся production acceptance",
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
