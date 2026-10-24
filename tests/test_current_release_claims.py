"""Негативные регрессии: текущие статусы living docs против Roadmap."""
from __future__ import annotations

import importlib.util
import json
import re
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
        """Негативная мутация должна изменить ровно одну ожидаемую запись."""
        f = self.root / path
        source = f.read_text(encoding="utf-8")
        self.assertNotEqual(old, new, "no-op fixture mutation")
        self.assertEqual(source.count(old), 1, f"fixture changed: {path}")
        changed = source.replace(old, new, 1)
        self.assertNotEqual(changed, source)
        f.write_text(changed, encoding="utf-8")

    def published_tag(self):
        roadmap = (self.root / "docs/ROADMAP.md").read_text(encoding="utf-8")
        lines = [l for l in roadmap.splitlines() if l.startswith("**Published:** immutable ")]
        self.assertEqual(len(lines), 1)
        match = re.search(r"releases/tag/(v\d+\.\d+\.\d+(?:-rc\.\d+(?:\.\d+)?)?)", lines[0])
        self.assertIsNotNone(match)
        return match.group(1)

    def next_tag(self):
        tag = self.published_tag()
        replacement = re.sub(r"\d+$", lambda m: str(int(m.group()) + 1), tag)
        self.assertNotEqual(replacement, tag)
        return replacement

    def test_current_docs_match_canonical_roadmap(self):
        self.assertEqual(semantics.current_release_claims_ok(self.root), [])

    def test_admin_stale_deployment_rejected(self):
        self.change("docs/ADMIN_SETUP.md", "Guide ориентирован на release ",
                    "Deployed/Accepted PENDING. Guide ориентирован на release ")
        self.assertTrue(any("ADMIN_SETUP" in x for x in
                            semantics.current_release_claims_ok(self.root)))

    def test_schema_stale_deployment_rejected(self):
        self.change("docs/SQLITE_MIGRATIONS.md", "## Текущий контракт schema",
                    "## Текущий контракт schema\n\nDeployed/Accepted UNKNOWN/PENDING.")
        self.assertTrue(any("SQLITE_MIGRATIONS" in x for x in
                            semantics.current_release_claims_ok(self.root)))

    def test_current_changelog_stale_acceptance_rejected(self):
        self.change("CHANGELOG.md", "**Текущий checkpoint",
                    "**Текущий checkpoint Deployed/Accepted PENDING;")
        self.assertTrue(any("CHANGELOG" in x for x in
                            semantics.current_release_claims_ok(self.root)))

    def test_admin_outdated_published_tag_rejected(self):
        tag = self.published_tag()
        other = self.next_tag()
        self.change("docs/ADMIN_SETUP.md", f"Guide ориентирован на release {tag}",
                    f"Guide ориентирован на release {other}")
        self.assertTrue(any("ADMIN_SETUP" in x for x in
                            semantics.current_release_claims_ok(self.root)))

    def test_sqlite_outdated_published_tag_rejected(self):
        tag = self.published_tag()
        other = self.next_tag()
        self.change("docs/SQLITE_MIGRATIONS.md", f"для Published `{tag}`",
                    f"для Published `{other}`")
        self.assertTrue(any("SQLITE_MIGRATIONS" in x for x in
                            semantics.current_release_claims_ok(self.root)))

    def test_new_release_tag_is_derived_from_roadmap(self):
        """Новый Published RC не требует правки тестовых версий или дат."""
        tag = self.published_tag()
        other = self.next_tag()
        roadmap = (self.root / "docs/ROADMAP.md").read_text(encoding="utf-8")
        canonical = next(x for x in roadmap.splitlines()
                         if x.startswith("**Published:** immutable "))
        self.assertGreaterEqual(canonical.count(tag), 3)
        self.change("docs/ROADMAP.md", canonical,
                    canonical.replace(tag, other))
        self.change("docs/ADMIN_SETUP.md", f"Guide ориентирован на release {tag}",
                    f"Guide ориентирован на release {other}")
        self.change("docs/SQLITE_MIGRATIONS.md", f"для Published `{tag}`",
                    f"для Published `{other}`")
        self.change("CHANGELOG.md", f"GitHub Published `{tag}`",
                    f"GitHub Published `{other}`")
        self.assertEqual(semantics.current_release_claims_ok(self.root), [])
        # Новая публикация без нового deployment не отменяет доказанный scoped PASS:
        # общий "Deployed/Accepted PENDING" в текущем operator guide — ошибка.
        self.change("docs/ADMIN_SETUP.md", f"Guide ориентирован на release {other}",
                    f"Deployed/Accepted PENDING. Guide ориентирован на release {other}")
        self.assertIn("ADMIN_SETUP: противоречивый текущий Published/Deployed/Accepted",
                      semantics.current_release_claims_ok(self.root))

    def test_completed_issue_cannot_be_open_in_admin(self):
        decisions = json.loads((self.root / "docs/roadmap/issue-closure-decisions.json").read_text(encoding="utf-8"))
        issue = next(d["issue"] for d in decisions["decisions"] if d["decision"] == "completed")
        self.change("docs/ADMIN_SETUP.md", "**Текущий Published/Deployed/Accepted status:**",
                    f"**Текущий Published/Deployed/Accepted status:** #{issue} OPEN;")
        self.assertTrue(any(f"#{issue}" in x for x in
                            semantics.current_release_claims_ok(self.root)))

    def test_historical_publication_pending_is_not_current(self):
        f = self.root / "CHANGELOG.md"
        s = f.read_text(encoding="utf-8")
        decisions = json.loads((self.root / "docs/roadmap/issue-closure-decisions.json").read_text(encoding="utf-8"))
        issue = next(d["issue"] for d in decisions["decisions"] if d["decision"] == "completed")
        self.assertEqual(s.count("**Исторические publication checkpoints"), 1)
        s = s.replace("**Исторические publication checkpoints",
                      f"**Исторические publication checkpoints: Deployed/Accepted PENDING, #{issue} OPEN", 1)
        f.write_text(s, encoding="utf-8")
        self.assertEqual(semantics.current_release_claims_ok(self.root), [])


if __name__ == "__main__":
    unittest.main()
