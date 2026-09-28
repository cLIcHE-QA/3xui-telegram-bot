"""Historical release contract for v4.23.1."""
from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class V4231ReleaseTests(unittest.TestCase):
    def test_historical_changelog_keeps_v4231_contract(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(
            changelog.count("## v4.23.1 — Cheburcheck hotfix и navigation regression"),
            1,
        )
        section = changelog.split(
            "## v4.23.1 — Cheburcheck hotfix и navigation regression",
            1,
        )[1].split("\n## ", 1)[0]
        self.assertIn("bounded response-body limit до 1 MiB", section)
        self.assertIn("ASN response", section)
        self.assertIn("v4.23.1", section)

    def test_v4231_acceptance_remains_documented(self):
        deploy = (ROOT / "docs" / "CHEBURCHECK_DEPLOY.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        self.assertIn("Принятый production результат v4.23.1", deploy)
        self.assertIn("ff6638442cbe9c2adc9aa76d74c2cfb4b647aaf6", deploy)
        self.assertIn("✅ Выполнено в `v4.23.1`", roadmap)


if __name__ == "__main__":
    unittest.main()
