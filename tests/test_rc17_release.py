"""Регрессии release-prep rc.17: полнота заметных merged PR и границы публикации."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from version import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]


class Rc17ReleaseTests(unittest.TestCase):
    def test_release_scope_is_explicit_and_stays_canary(self):
        if APP_VERSION != "5.0.0-rc.17":
            self.skipTest("Версия rc.17 больше не готовится")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        heading = "## v5.0.0-rc.17 — "
        self.assertEqual(changelog.count(heading), 1)
        scope = changelog.split(heading, 1)[1].split("\n## ", 1)[0]
        for pr in ("#766", "#768", "#770", "#772", "#775", "#799", "#801"):
            with self.subTest(pr=pr):
                self.assertIn(pr, scope)
        self.assertIn("G-11", scope)
        self.assertIn("BLOCKED", scope)
        self.assertIn("не выполняет deployment", scope)
        legal = json.loads((ROOT / "docs/legal-publication.json").read_text(encoding="utf-8"))
        if legal["terms"]["publication_state"] == "unpublished":
            self.assertIn("§ 9", scope)
            self.assertIn("не опубликованы", scope.replace("**", ""))


if __name__ == "__main__":
    unittest.main()
