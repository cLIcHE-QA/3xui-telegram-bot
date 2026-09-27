"""Historical release contract for v4.22.0."""
from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class V4220ReleaseTests(unittest.TestCase):
    def test_changelog_preserves_v4220_release_section(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(
            changelog.count("## v4.22.0 — Группы пользователей"),
            1,
        )
        self.assertIn("user_audience_groups_v4_22_0", changelog)
        self.assertIn("downgrade", changelog)


if __name__ == "__main__":
    unittest.main()
