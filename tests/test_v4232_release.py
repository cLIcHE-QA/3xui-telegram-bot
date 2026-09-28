"""Historical release contract for v4.23.2."""
from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class V4232ReleaseTests(unittest.TestCase):
    def test_historical_changelog_keeps_v4232_contract(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
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

    def test_v4232_production_finding_remains_documented(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        self.assertIn("`v4.23.2` опубликован и развернут", roadmap)
        self.assertIn("production smoke выявил incomplete compact enrichment", roadmap)
        self.assertIn("hotfix `v4.23.3`", roadmap)


if __name__ == "__main__":
    unittest.main()
