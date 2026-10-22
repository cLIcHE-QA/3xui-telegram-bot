"""Негативные регрессии: текущие статусы living docs против Roadmap."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "documentation_semantics_current", ROOT / "scripts/check-documentation-semantics.py"
)
semantics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(semantics)


class CurrentReleaseClaimsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = (
            "docs/ROADMAP.md", "docs/ADMIN_SETUP.md",
            "docs/SQLITE_MIGRATIONS.md", "CHANGELOG.md",
            "docs/roadmap/issue-closure-decisions.json",
        )
        for path in self.paths:
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text((ROOT / path).read_text(encoding="utf-8"), encoding="utf-8")

    def change(self, path, old, new):
        f = self.root / path
        source = f.read_text(encoding="utf-8")
        self.assertIn(old, source)
        f.write_text(source.replace(old, new, 1), encoding="utf-8")

    def test_current_docs_match_canonical_roadmap(self):
        self.assertEqual(semantics.current_release_claims_ok(self.root), [])

    def test_admin_stale_deployment_rejected(self):
        self.change("docs/ADMIN_SETUP.md", "Guide ориентирован на release ",
                    "Deployed/Accepted PENDING. Guide ориентирован на release ")
        self.assertTrue(any("ADMIN_SETUP" in x for x in
                            semantics.current_release_claims_ok(self.root)))

    def test_schema_stale_deployment_rejected(self):
        self.change("docs/SQLITE_MIGRATIONS.md", "Новых миграций в релизе нет:",
                    "Deployed/Accepted UNKNOWN/PENDING. Новых миграций в релизе нет:")
        self.assertTrue(any("SQLITE_MIGRATIONS" in x for x in
                            semantics.current_release_claims_ok(self.root)))

    def test_current_changelog_stale_acceptance_rejected(self):
        self.change("CHANGELOG.md", "Текущий checkpoint 2026-10-22",
                    "Deployed/Accepted PENDING. Текущий checkpoint 2026-10-22")
        self.assertTrue(any("CHANGELOG" in x for x in
                            semantics.current_release_claims_ok(self.root)))

    def test_completed_issue_cannot_be_open_in_admin(self):
        self.change("docs/ADMIN_SETUP.md", "Принятые оператором 23/23",
                    "#827 OPEN; Принятые оператором 23/23")
        self.assertTrue(any("#827" in x for x in
                            semantics.current_release_claims_ok(self.root)))

    def test_historical_publication_pending_is_not_current(self):
        self.change("CHANGELOG.md", "**Исторические publication checkpoints",
                    "**Исторические publication checkpoints")
        f = self.root / "CHANGELOG.md"
        s = f.read_text(encoding="utf-8")
        s = s.replace("**Исторические publication checkpoints",
                      "**Исторические publication checkpoints: Deployed/Accepted PENDING, #827 OPEN", 1)
        f.write_text(s, encoding="utf-8")
        self.assertEqual(semantics.current_release_claims_ok(self.root), [])


if __name__ == "__main__":
    unittest.main()
