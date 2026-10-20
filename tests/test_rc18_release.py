"""Проверки канонического release-prep v5.0.0-rc.18 без публикации/деплоя."""
from __future__ import annotations

from pathlib import Path
import re
import unittest

from version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class Rc18ReleaseTests(unittest.TestCase):
    def test_release_scope_and_pilot_gates(self):
        if APP_VERSION != "5.0.0-rc.18":
            self.skipTest("Это версия другого release candidate")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        sections = re.findall(r"^## v5\.0\.0-rc\.18 — .*", changelog, re.M)
        self.assertEqual(len(sections), 1)
        notes = changelog.split(sections[0], 1)[1].split("\n## ", 1)[0]
        for identifier in ("#808", "#810", "#471", "#472", "G-11",
                           "PARTIAL/NO-GO", "BLOCKED", "v15", "v3.10.2",
                           "unknown", "no-replay", "не выполняет deployment"):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, notes)
        self.assertIn("§ 9", notes)
        self.assertIn("не Published, не Deployed и не Accepted", notes)
        self.assertEqual(
            (ROOT / "version.py").read_text(encoding="utf-8").count(
                'APP_VERSION = "5.0.0-rc.18"'), 1,
        )
        roadmap = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
        self.assertIn("v5.0.0-rc.17", roadmap)
        self.assertIn("public rollout BLOCKED", roadmap)


if __name__ == "__main__":
    unittest.main()
