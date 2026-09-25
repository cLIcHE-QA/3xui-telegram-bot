from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GitConventionTests(unittest.TestCase):
    def test_git_workflow_defines_canonical_history_style(self):
        doc = (ROOT / "docs" / "GIT_WORKFLOW.md").read_text(encoding="utf-8")
        for needle in [
            "## Канонический стиль Git-истории",
            "<type>: <краткое описание>",
            "Squash and merge",
            "(#N)",
            "release: vX.Y.Z",
            "bug: <симптом>",
            "feature: <результат>",
            "task: <результат>",
        ]:
            self.assertIn(needle, doc)

    def test_readme_is_current_state_map_not_release_history(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for needle in [
            "## Текущий production path",
            "docs/ADMIN_SETUP.md",
            "docs/RELEASES.md",
            "docs/VPS_RECOVERY.md",
            "docs/OFFSITE_BACKUP.md",
            "## Subscription Compatibility Proxy",
            "COMPAT_SUBSCRIPTION_URL_TEMPLATE",
            "127.0.0.1:18080 -> container:8080",
            "CHANGELOG.md",
            "app_runtime.py",
            "client_access.py",
            "admin_shell.py",
        ]:
            self.assertIn(needle, readme)

        self.assertNotRegex(readme, r"(?m)^## v\d")
        self.assertNotRegex(readme, r"deploy-release\.sh v4\.\d")
        self.assertIn("./scripts/deploy-release.sh vX.Y.Z", readme)

    def test_pr_template_contains_required_sections(self):
        template = (ROOT / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
        for needle in [
            "## Что изменено",
            "## Зачем",
            "## Проверки",
            "## Совместимость и security",
            "## Rollout / rollback",
            "PR title соответствует",
            "CHANGELOG.md",
        ]:
            self.assertIn(needle, template)

    def test_issue_forms_exist_with_canonical_prefixes(self):
        cases = {
            "bug.yml": 'title: "bug: "',
            "feature.yml": 'title: "feature: "',
            "task.yml": 'title: "task: "',
        }
        base = ROOT / ".github" / "ISSUE_TEMPLATE"
        for filename, title in cases.items():
            text = (base / filename).read_text(encoding="utf-8")
            self.assertIn(title, text)
            self.assertIn("Acceptance criteria", text)

    def test_pr_title_workflow_checks_expected_types(self):
        workflow = (ROOT / ".github" / "workflows" / "pr-conventions.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request:", workflow)
        self.assertIn("PR_TITLE", workflow)
        self.assertIn("feat|fix|security|docs|test|chore|refactor", workflow)
        self.assertIn("^release:", workflow)
        self.assertNotIn("contents: write", workflow)


if __name__ == "__main__":
    unittest.main()
