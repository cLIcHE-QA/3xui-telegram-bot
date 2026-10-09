from __future__ import annotations

import runpy
import unittest
from pathlib import Path


MODULE = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts" / "check-release-scope.py"))
eligible_commits = MODULE["eligible_commits"]
release_notes = MODULE["release_notes"]
missing_prs = MODULE["missing_prs"]


class ReleaseScopeTests(unittest.TestCase):
    def test_commit_type_scope(self):
        log = "\n".join([
            "a" * 40 + " feat: change",
            "b" * 40 + " docs: guide",
            "c" * 40 + " fix: defect",
            "d" * 40 + " security: hardening",
        ])
        self.assertEqual(eligible_commits(log), ["a" * 40, "c" * 40, "d" * 40])

    def test_release_section_only(self):
        md = "## Не выпущено\n- PR #900\n## v5.0.0-rc.8 — new\n- PR #361\n## v5.0.0-rc.7 — old\n- PR #12\n"
        self.assertIn("PR #361", release_notes(md, "5.0.0-rc.8"))
        self.assertNotIn("PR #12", release_notes(md, "5.0.0-rc.8"))
        self.assertEqual(release_notes(md, "5.0.0-rc.9"), "")

    def test_missing_pr_blocks(self):
        self.assertEqual(missing_prs([361, 362], "PR #361", ""), [362])

    def test_reasoned_exclusion_allowed(self):
        body = "Release scope exclusion: PR #362 — no release-facing effect"
        self.assertEqual(missing_prs([361, 362], "PR #361", body), [])

    def test_empty_exclusion_rejected(self):
        self.assertEqual(missing_prs([362], "", "Release scope exclusion: PR #362 — "), [362])

    def test_pr_number_prefix_collision(self):
        self.assertEqual(missing_prs([36], "PR #361", ""), [36])

    def test_duplicate_pr_association(self):
        self.assertEqual(missing_prs([361, 361], "PR #361", ""), [])


if __name__ == "__main__":
    unittest.main()
