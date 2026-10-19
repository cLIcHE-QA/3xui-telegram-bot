"""Проверяем, что текущий Roadmap не зафиксирован в тестах произвольным Issue ID."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT_TESTS = (
    "tests/test_roadmap_final_governance.py",
    "tests/test_living_docs.py",
)


def pinned_current_issue_errors(sources: dict[str, str]) -> list[str]:
    """Проверка узкого антипаттерна, не запрещающая исторические fixtures."""
    errors = []
    for path, source in sources.items():
        if path.endswith("test_roadmap_final_governance.py"):
            if re.search(r"assert(?:In|NotIn)\(\s*\d{2,}\s*,\s*rows\b", source):
                errors.append(f"{path}: текущий реестр привязан к Issue ID")
            if re.search(r"starts(?:with)?\(\s*[\"']\| \[#\d+", source):
                errors.append(f"{path}: выбор текущей строки привязан к Issue ID")
        if path.endswith("test_living_docs.py"):
            if re.search(r"assertIn\(\s*[\"']#\d+[\"']\s*,\s*roadmap\s*\)", source):
                errors.append(f"{path}: текущий Roadmap привязан к Issue ID")
    return errors


class DocumentationTestReuseTests(unittest.TestCase):
    def test_current_state_tests_avoid_pinned_issues(self):
        sources = {p: (ROOT / p).read_text(encoding="utf-8") for p in CURRENT_TESTS}
        self.assertEqual(pinned_current_issue_errors(sources), [])

    def test_detect_pinned_current_issue_assertion(self):
        source = "self.assertIn(499,rows)"
        self.assertTrue(pinned_current_issue_errors({
            "tests/test_roadmap_final_governance.py": source,
        }))

    def test_historical_fixture_numbers_are_allowed(self):
        source = 'fixture = {"issue": 499, "pr": 754, "version": "v5.0.0-rc.1"}'
        self.assertEqual(pinned_current_issue_errors({
            "tests/test_roadmap_final_governance.py": source,
        }), [])


if __name__ == "__main__":
    unittest.main()
