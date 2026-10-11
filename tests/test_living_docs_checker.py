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

    def test_real_3xui_contract_requires_doc_without_waiver(self):
        contract = module.load_contract()
        for changed_file in (
            "contracts/3xui/contract.json",
            "contracts/3xui/v3.9.0/openapi.json",
        ):
            with self.subTest(path=changed_file):
                violations = module.evaluate_contract(
                    contract,
                    [changed_file],
                    "Living Docs: 3xui-client-api — изменений не требуется",
                )
                self.assertEqual([v["id"] for v in violations], ["3xui-openapi-contract"])
                self.assertEqual(violations[0]["missing"], ["docs/3XUI_OPENAPI_CONTRACT.md"])
                self.assertEqual(
                    module.evaluate_contract(
                        contract,
                        [changed_file, "docs/3XUI_OPENAPI_CONTRACT.md"],
                    ),
                    [],
                )

    def test_real_3xui_client_review_requires_doc_or_exact_waiver(self):
        contract = module.load_contract()
        for path in ("xui.py", "version_api.py"):
            with self.subTest(path=path):
                violations = module.evaluate_contract(contract, [path], "")
                self.assertEqual([v["id"] for v in violations], ["3xui-client-api"])
                self.assertEqual(
                    module.evaluate_contract(
                        contract, [path],
                        "Living Docs: 3xui-client-api — изменений не требуется",
                    ),
                    [],
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
