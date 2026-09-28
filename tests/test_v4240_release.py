"""Historical release contract for v4.24.1."""
from __future__ import annotations

from pathlib import Path
import unittest



ROOT = Path(__file__).resolve().parents[1]


class V4241ReleaseTests(unittest.TestCase):
    def test_v4241_historical_release_notes_remain_present(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        self.assertIn("## v4.24.1 — Hotfix web diagnostics и IPv6", changelog)
        self.assertIn(
            "✅ Выполнено и принято в production в `v4.24.1`; acceptance линии `v4.24.x` закрыт.",
            roadmap,
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

    def test_v424x_production_acceptance_is_closed(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        self.assertIn(
            "✅ Выполнено и принято в production в `v4.24.1`; acceptance линии `v4.24.x` закрыт.",
            roadmap,
        )
        self.assertIn(
            "production smoke линии `v4.24.x` проведён и acceptance закрыт",
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
