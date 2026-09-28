"""Historical release contract for v4.23.3."""
from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class V4233ReleaseTests(unittest.TestCase):
    def test_historical_changelog_keeps_v4233_contract(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
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
            "SQLite schema остаётся v3",
        ):
            self.assertIn(needle, section)

    def test_v4233_acceptance_remains_documented(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        deploy = (ROOT / "docs" / "CHEBURCHECK_DEPLOY.md").read_text(encoding="utf-8")
        self.assertIn("✅ Закрыто. `v4.23.3` опубликован и принят", roadmap)
        self.assertIn("Probe fleet", roadmap)
        self.assertIn("v4.23.3 не требует rebuild Cheburcheck runtime", deploy)


if __name__ == "__main__":
    unittest.main()
