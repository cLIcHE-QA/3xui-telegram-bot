"""Historical release contract for v4.23.0."""
from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class V4230ReleaseTests(unittest.TestCase):
    def test_historical_changelog_keeps_v4230_contract(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(
            changelog.count("## v4.23.0 — Проверка блокировок Cheburcheck"),
            1,
        )
        section = changelog.split(
            "## v4.23.0 — Проверка блокировок Cheburcheck",
            1,
        )[1].split("\n## ", 1)[0]
        self.assertIn(
            "LowderPlay/cheburcheck@0bbd2be8ca4b8f9ded1407597654314fc2a900c6",
            section,
        )
        self.assertIn("лимит response body 256 KiB", section)
        self.assertIn("CHEBURCHECK_URL", section)


if __name__ == "__main__":
    unittest.main()
