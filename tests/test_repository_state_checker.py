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


    def test_latest_published_includes_rc_and_filters_drafts(self):
        from unittest.mock import patch
        fixtures = [
            {"tag_name": "v4.26.9", "published_at": "2026-10-08T00:00:00Z", "draft": False},
            {"tag_name": "v5.0.0-rc.9", "published_at": "2026-10-11T11:24:04Z", "draft": False},
            {"tag_name": "v5.0.0-rc.10", "published_at": None, "draft": True},
        ]
        with patch.object(module, "api", side_effect=lambda _r, _s, _t: fixtures):
            self.assertEqual(module.latest_published_release("o/r", "")["tag_name"], "v5.0.0-rc.9")

    def test_latest_published_fail_closed_missing_ambiguous_and_invalid(self):
        from unittest.mock import patch
        good = {"tag_name": "v5.0.0-rc.9", "published_at": "2026-10-11T11:24:04Z", "draft": False}
        fixtures = ([], [good, dict(good, tag_name="v5.0.0-rc.8")],
                    [dict(good, published_at=None)],
                    [dict(good, tag_name=None)])
        for items in fixtures:
            with self.subTest(items=items), patch.object(module, "api", return_value=items):
                with self.assertRaises(module.AuditError):
                    module.latest_published_release("o/r", "")

    def test_verify_release_checks_rc_tag_version_and_ancestry(self):
        from unittest.mock import patch
        import base64
        latest = {"tag_name": "v5.0.0-rc.9", "published_at": "2026-10-11T11:24:04Z", "draft": False}
        contents = base64.b64encode(b'APP_VERSION = "5.0.0-rc.9"\n').decode()
        def api_mock(_repo, path, _token):
            if path.startswith("/releases?"):
                return [latest]
            if path.startswith("/contents/version.py?"):
                return {"encoding": "base64", "content": contents}
            if path.startswith("/git/ref/tags/"):
                return {"object": {"type": "commit", "sha": "abc123"}}
            if path.startswith("/compare/"):
                return {"status": "ahead"}
            raise AssertionError(path)
        with patch.object(module, "api", side_effect=api_mock), patch.object(
            module.Path, "read_text", return_value='APP_VERSION = "5.0.0-rc.9"\n'
        ):
            module.verify_release("o/r", "main", "")
            latest["tag_name"] = "v5.0.0-rc.8"
            with self.assertRaises(module.AuditError):
                module.verify_release("o/r", "main", "")
            latest["tag_name"] = "v5.0.0-rc.9"
            contents = base64.b64encode(b'APP_VERSION = "5.0.0-rc.8"\n').decode()
            with self.assertRaises(module.AuditError):
                module.verify_release("o/r", "main", "")
            contents = base64.b64encode(b'APP_VERSION = "5.0.0-rc.9"\n').decode()
            def divergent(_repo, path, _token):
                value = api_mock(_repo, path, _token)
                if path.startswith("/compare/"):
                    return {"status": "diverged"}
                return value
            with patch.object(module, "api", side_effect=divergent):
                with self.assertRaises(module.AuditError):
                    module.verify_release("o/r", "main", "")

    def test_stable_release_accepted_when_latest(self):
        from unittest.mock import patch
        stable = {"tag_name": "v4.26.9", "published_at": "2026-10-11T11:24:04Z", "draft": False}
        with patch.object(module, "api", return_value=[stable]):
            self.assertEqual(module.latest_published_release("o/r", "")["tag_name"], "v4.26.9")


if __name__ == "__main__":
    unittest.main()
