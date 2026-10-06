from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-repository-state.py"

spec = importlib.util.spec_from_file_location("check_repository_state", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RepositoryStateCheckerTests(unittest.TestCase):
    def test_app_version_parser(self):
        self.assertEqual(
            module.app_version_from_text('APP_VERSION = "5.0.0"\n'),
            "5.0.0",
        )
        with self.assertRaises(module.AuditError):
            module.app_version_from_text("VERSION = '5.0.0'\n")

    def test_branch_ruleset_fixture_passes(self):
        expected = {
            "name": "Protect main release path",
            "enforcement": "active",
            "include": ["~DEFAULT_BRANCH"],
            "required_rules": [
                "deletion",
                "non_fast_forward",
                "pull_request",
                "required_status_checks",
                "required_linear_history",
            ],
            "allowed_merge_methods": ["squash"],
            "required_status_checks": ["test", "title"],
            "strict_status_checks": True,
            "no_bypass": True,
        }
        ruleset = {
            "name": expected["name"],
            "enforcement": "active",
            "conditions": {
                "ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}
            },
            "bypass_actors": [],
            "current_user_can_bypass": "never",
            "rules": [
                {"type": "deletion"},
                {"type": "non_fast_forward"},
                {"type": "required_linear_history"},
                {
                    "type": "pull_request",
                    "parameters": {"allowed_merge_methods": ["squash"]},
                },
                {
                    "type": "required_status_checks",
                    "parameters": {
                        "strict_required_status_checks_policy": True,
                        "required_status_checks": [
                            {"context": "test"},
                            {"context": "title"},
                        ],
                    },
                },
            ],
        }
        module.verify_ruleset(ruleset, expected)

    def test_tag_ruleset_creation_must_remain_allowed(self):
        expected = {
            "name": "Protect release tags",
            "enforcement": "active",
            "include": ["refs/tags/v*"],
            "required_rules": ["deletion", "non_fast_forward", "update"],
            "forbidden_rules": ["creation"],
            "no_bypass": True,
        }
        ruleset = {
            "name": expected["name"],
            "enforcement": "active",
            "conditions": {
                "ref_name": {"include": ["refs/tags/v*"], "exclude": []}
            },
            "bypass_actors": [],
            "current_user_can_bypass": "never",
            "rules": [
                {"type": "deletion"},
                {"type": "non_fast_forward"},
                {"type": "update"},
                {"type": "creation"},
            ],
        }
        with self.assertRaises(module.AuditError):
            module.verify_ruleset(ruleset, expected)

    def test_ruleset_with_bypass_fails(self):
        expected = {
            "name": "Protect release tags",
            "enforcement": "active",
            "include": ["refs/tags/v*"],
            "required_rules": ["deletion", "non_fast_forward", "update"],
            "forbidden_rules": ["creation"],
            "no_bypass": True,
        }
        ruleset = {
            "name": expected["name"],
            "enforcement": "active",
            "conditions": {
                "ref_name": {"include": ["refs/tags/v*"], "exclude": []}
            },
            "bypass_actors": [{"actor_type": "RepositoryRole"}],
            "rules": [
                {"type": "deletion"},
                {"type": "non_fast_forward"},
                {"type": "update"},
            ],
        }
        with self.assertRaises(module.AuditError):
            module.verify_ruleset(ruleset, expected)


if __name__ == "__main__":
    unittest.main()
