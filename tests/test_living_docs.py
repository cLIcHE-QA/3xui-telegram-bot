from __future__ import annotations

import json
import unittest
from pathlib import Path

from db_migrations import CURRENT_SCHEMA_VERSION
from version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class LivingDocsSemanticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(
            (ROOT / "docs" / "live-docs.json").read_text(encoding="utf-8")
        )

    def test_contract_has_unique_valid_rules_and_existing_documents(self):
        self.assertEqual(self.contract["schema"], 1)

        living_documents = self.contract["living_documents"]
        self.assertEqual(len(living_documents), len(set(living_documents)))
        for path in living_documents:
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file(), path)

        rule_ids = [rule["id"] for rule in self.contract["rules"]]
        self.assertEqual(len(rule_ids), len(set(rule_ids)))
        for rule in self.contract["rules"]:
            with self.subTest(rule=rule["id"]):
                self.assertIn(rule["mode"], {"require_all", "review"})
                self.assertTrue(rule["triggers"])
                self.assertTrue(rule["documents"])
                for path in rule["documents"]:
                    self.assertIn(path, living_documents)
                if rule["mode"] == "review":
                    self.assertTrue(rule.get("waiver"))

    def test_current_release_version_is_reflected_in_living_docs(self):
        version = APP_VERSION
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        admin_setup = (ROOT / "docs" / "ADMIN_SETUP.md").read_text(encoding="utf-8")

        self.assertTrue(readme.startswith(f"# Telegram-бот для 3x-ui v{version}"))
        self.assertIn(f"## v{version} ", changelog)
        self.assertIn(f"Guide ориентирован на release v{version}.", admin_setup)
        self.assertIn(f"git checkout --detach v{version}", admin_setup)

    def test_current_sqlite_schema_version_is_documented(self):
        migration_doc = (ROOT / "docs" / "SQLITE_MIGRATIONS.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            f"текущая bot schema version — **{CURRENT_SCHEMA_VERSION}**",
            migration_doc,
        )

    def test_public_security_reporting_is_current(self):
        security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn("Private Vulnerability Reporting is enabled", security)
        self.assertIn("Report a vulnerability", security)
        self.assertIn("public repository", security)

    def test_git_and_release_docs_record_current_rulesets(self):
        git_workflow = (ROOT / "docs" / "GIT_WORKFLOW.md").read_text(
            encoding="utf-8"
        )
        releases = (ROOT / "docs" / "RELEASES.md").read_text(encoding="utf-8")
        expected = self.contract["repository_state"]

        for document in (git_workflow, releases):
            self.assertIn(expected["branch_ruleset"]["name"], document)
            self.assertIn(expected["tag_ruleset"]["name"], document)

        self.assertIn("refs/tags/v*", git_workflow)
        self.assertIn("refs/tags/v*", releases)

    def test_roadmap_has_current_next_product_track(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        self.assertIn(
            "**Статус: ⬜ Следующий активный product track.",
            roadmap,
        )
        self.assertIn("### v5.0.0 — Client Portal", roadmap)
        self.assertIn("A-007 технически закрыт полностью", roadmap)

    def test_living_docs_are_linked_from_readme_and_agent_contract(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("docs/LIVING_DOCS.md", readme)
        self.assertIn("docs/LIVING_DOCS.md", agents)
        self.assertIn("scripts/check-living-docs.py", agents)

    def test_ci_and_scheduled_repository_state_audit_are_wired(self):
        tests_workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(
            encoding="utf-8"
        )
        state_workflow = (
            ROOT / ".github" / "workflows" / "repository-state-audit.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("scripts/check-living-docs.py", tests_workflow)
        self.assertIn("pull_request.head.sha", tests_workflow)
        self.assertIn("workflow_dispatch:", state_workflow)
        self.assertIn("schedule:", state_workflow)
        self.assertIn("scripts/check-repository-state.py", state_workflow)


if __name__ == "__main__":
    unittest.main()
