"""Regression coverage for the v4.20.7 Inbound/Inbounds terminology cleanup."""
from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HYBRID = re.compile(r"(?i)inbound\'[А-Яа-яЁё]+")


class V4207InboundsTerminologyTests(unittest.TestCase):
    def test_current_operator_facing_sources_do_not_use_hybrid_inbound_forms(self):
        paths = sorted(ROOT.glob("*.py"))
        paths += [ROOT / "README.md"]
        paths += sorted((ROOT / "docs").glob("*.md"))

        offenders: list[str] = []
        for path in paths:
            if path.name == "CHANGELOG.md":
                continue
            text = path.read_text(encoding="utf-8")
            if HYBRID.search(text):
                offenders.append(str(path.relative_to(ROOT)))

        self.assertEqual(offenders, [])

    def test_canonical_terminology_is_documented(self):
        style = (ROOT / "docs" / "UI_STYLE.md").read_text(encoding="utf-8")
        self.assertIn("`Inbound` / `Inbounds`", style)
        self.assertIn("гибридные русифицированные склонения с апострофом", style)


if __name__ == "__main__":
    unittest.main()
