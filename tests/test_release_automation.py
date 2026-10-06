from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render-release-notes.py"
SPEC = importlib.util.spec_from_file_location("release_notes", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
release_notes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_notes)


class ReleaseNotesTests(unittest.TestCase):
    def test_canonical_release_title_and_body(self):
        changelog = """# Журнал изменений

## v4.11.0 — Node readiness и безопасный onboarding
- Первый пункт.
- Второй пункт.

## v4.10.1 — Старый релиз
- Старый пункт.
"""
        commit = "a" * 40
        title, body = release_notes.render_release_notes(changelog, "4.11.0", commit)

        self.assertEqual(title, "v4.11.0 — Node readiness и безопасный onboarding")
        self.assertTrue(body.startswith("## v4.11.0 — Node readiness и безопасный onboarding\n\n"))
        self.assertIn("- Первый пункт.\n- Второй пункт.", body)
        self.assertIn("Коммит релиза: " + commit, body)
        self.assertIn("./scripts/deploy-release.sh v4.11.0", body)
        self.assertIn("./scripts/deploy-release.sh --status", body)
        self.assertIn("не выполняет production deployment автоматически", body)

    def test_missing_release_section_is_rejected(self):
        with self.assertRaises(SystemExit):
            release_notes.render_release_notes(
                "## v4.10.1 — Старый релиз\n- Пункт.\n",
                "4.11.0",
                "b" * 40,
            )

    def test_duplicate_release_section_is_rejected(self):
        changelog = """## v4.11.0 — One
- A.

## v4.11.0 — Two
- B.
"""
        with self.assertRaises(SystemExit):
            release_notes.render_release_notes(changelog, "4.11.0", "c" * 40)

    def test_release_section_requires_bullets(self):
        with self.assertRaises(SystemExit):
            release_notes.render_release_notes(
                "## v4.11.0 — Empty style\nТекст без bullets.\n",
                "4.11.0",
                "d" * 40,
            )

    def test_actual_v411_changelog_renders_canonical_style(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        title, body = release_notes.render_release_notes(
            changelog,
            "4.11.0",
            "e" * 40,
        )
        self.assertEqual(title, "v4.11.0 — Node readiness и безопасный onboarding")
        self.assertGreaterEqual(sum(1 for line in body.splitlines() if line.startswith("- ")), 5)

    def test_release_workflow_is_fail_closed(self):
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read\n  pull-requests: read", workflow)
        self.assertIn("workflow_run.head_branch == 'main'", workflow)
        self.assertIn("workflow_run.conclusion == 'success'", workflow)
        self.assertIn("Verify tested main commit came from merged PR", workflow)
        self.assertIn("Verify release commit came from release-prep PR", workflow)
        self.assertIn("Release provenance:", workflow)
        self.assertIn("permissions:\n      contents: write", workflow)
        self.assertIn("needs: prepare", workflow)
        self.assertIn("Refusing to move it.", workflow)
        self.assertIn('if existing="$(gh api', workflow)
        self.assertNotIn("git/ref/tags/$tag\" --jq '.object.sha' 2>/dev/null || true", workflow)
        self.assertNotIn("--force", workflow)
        self.assertIn("scripts/render-release-notes.py", workflow)

    def test_release_contract_forbids_manual_publication(self):
        doc = (ROOT / "docs" / "RELEASES.md").read_text(encoding="utf-8")
        self.assertIn("tag и GitHub Release вручную не создаются", doc)
        self.assertIn("Release не должен иметь пустой `name` или пустой `body`", doc)
        self.assertIn("CHANGELOG.md", doc)


if __name__ == "__main__":
    unittest.main()
