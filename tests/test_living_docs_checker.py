from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-living-docs.py"

spec = importlib.util.spec_from_file_location("check_living_docs", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LivingDocsCheckerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = {
            "schema": 1,
            "rules": [
                {
                    "id": "release-version",
                    "mode": "require_all",
                    "triggers": ["version.py"],
                    "documents": ["README.md", "CHANGELOG.md"],
                },
                {
                    "id": "operator-setup",
                    "mode": "review",
                    "triggers": ["Dockerfile", "deploy/**"],
                    "documents": ["docs/ADMIN_SETUP.md"],
                    "waiver": "Admin Setup: изменений не требуется",
                },
            ],
        }

    def test_require_all_reports_each_missing_document(self):
        violations = module.evaluate_contract(
            self.contract,
            ["version.py", "README.md"],
            "",
        )
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["id"], "release-version")
        self.assertEqual(violations[0]["missing"], ["CHANGELOG.md"])

    def test_require_all_passes_when_all_documents_change(self):
        violations = module.evaluate_contract(
            self.contract,
            ["version.py", "README.md", "CHANGELOG.md"],
            "",
        )
        self.assertEqual(violations, [])

    def test_review_rule_passes_when_document_changes(self):
        violations = module.evaluate_contract(
            self.contract,
            ["Dockerfile", "docs/ADMIN_SETUP.md"],
            "",
        )
        self.assertEqual(violations, [])

    def test_review_rule_passes_with_exact_waiver(self):
        violations = module.evaluate_contract(
            self.contract,
            ["deploy/agent.service"],
            "Проверено. Admin Setup: изменений не требуется",
        )
        self.assertEqual(violations, [])

    def test_review_rule_fails_without_doc_or_waiver(self):
        violations = module.evaluate_contract(
            self.contract,
            ["deploy/agent.service"],
            "",
        )
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["id"], "operator-setup")
        self.assertEqual(
            violations[0]["waiver"],
            "Admin Setup: изменений не требуется",
        )

    def test_unrelated_change_does_not_trigger_contract(self):
        violations = module.evaluate_contract(
            self.contract,
            ["client_portal.py"],
            "",
        )
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
