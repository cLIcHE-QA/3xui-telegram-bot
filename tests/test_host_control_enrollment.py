from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "import-host-control-enrollment.py"
SPEC = importlib.util.spec_from_file_location("host_control_enrollment", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class HostControlEnrollmentTests(unittest.TestCase):
    def enrollment(self, **overrides):
        values = {
            "HOST_CONTROL_ALIAS": "FI",
            "HOST_CONTROL_NAME": "Finland",
            "HOST_CONTROL_HOST_ID": "fi",
            "HOST_CONTROL_URL": "https://fi.example.com:18443",
            "HOST_CONTROL_VERIFY_TLS": "true",
            "HOST_CONTROL_TOKEN": "x" * 43,
        }
        values.update(overrides)
        return values

    def test_remote_http_is_rejected(self):
        with self.assertRaises(SystemExit):
            mod.enrollment_to_updates(
                self.enrollment(HOST_CONTROL_URL="http://203.0.113.10:18443")
            )

    def test_master_private_http_is_allowed(self):
        alias, updates = mod.enrollment_to_updates(
            self.enrollment(
                HOST_CONTROL_ALIAS="MASTER",
                HOST_CONTROL_NAME="Master",
                HOST_CONTROL_HOST_ID="master",
                HOST_CONTROL_URL="http://172.19.0.1:18182",
            )
        )
        self.assertEqual(alias, "MASTER")
        self.assertEqual(updates["HOST_CONTROL_MASTER_URL"], "http://172.19.0.1:18182")

    def test_duplicate_token_is_rejected(self):
        env = {
            "HOST_CONTROL_TARGETS": "MASTER",
            "HOST_CONTROL_MASTER_NAME": "Master",
            "HOST_CONTROL_MASTER_HOST_ID": "master",
            "HOST_CONTROL_MASTER_URL": "http://172.19.0.1:18182",
            "HOST_CONTROL_MASTER_VERIFY_TLS": "true",
            "HOST_CONTROL_MASTER_TOKEN": "x" * 43,
        }
        alias, updates = mod.enrollment_to_updates(self.enrollment())
        with self.assertRaises(SystemExit):
            mod.validate_combined(env, alias, updates)

    def test_import_appends_alias_and_preserves_other_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_path = root / ".env"
            env_path.write_text(
                "BOT_TOKEN=secret\n"
                "HOST_CONTROL_TARGETS=MASTER\n"
                "HOST_CONTROL_MASTER_NAME=Master\n"
                "HOST_CONTROL_MASTER_HOST_ID=master\n"
                "HOST_CONTROL_MASTER_URL=http://172.19.0.1:18182\n"
                "HOST_CONTROL_MASTER_VERIFY_TLS=true\n"
                f"HOST_CONTROL_MASTER_TOKEN={'m' * 43}\n",
                encoding="utf-8",
            )
            env = mod.parse_simple_env(env_path)
            alias, target_updates = mod.enrollment_to_updates(self.enrollment())
            aliases = mod.validate_combined(env, alias, target_updates)
            updates = dict(target_updates)
            updates["HOST_CONTROL_TARGETS"] = ",".join(aliases)
            rendered = mod.render_env(env_path, updates)

            self.assertIn("BOT_TOKEN=secret\n", rendered)
            self.assertIn("HOST_CONTROL_TARGETS=MASTER,FI\n", rendered)
            self.assertIn("HOST_CONTROL_FI_NAME=Finland\n", rendered)
            self.assertIn("HOST_CONTROL_FI_TOKEN=" + ("x" * 43) + "\n", rendered)

    def test_replacing_same_alias_does_not_duplicate_targets(self):
        env = {
            "HOST_CONTROL_TARGETS": "MASTER,FI",
            "HOST_CONTROL_MASTER_NAME": "Master",
            "HOST_CONTROL_MASTER_HOST_ID": "master",
            "HOST_CONTROL_MASTER_URL": "http://172.19.0.1:18182",
            "HOST_CONTROL_MASTER_VERIFY_TLS": "true",
            "HOST_CONTROL_MASTER_TOKEN": "m" * 43,
            "HOST_CONTROL_FI_NAME": "Finland old",
            "HOST_CONTROL_FI_HOST_ID": "fi",
            "HOST_CONTROL_FI_URL": "https://old.example.com:18443",
            "HOST_CONTROL_FI_VERIFY_TLS": "true",
            "HOST_CONTROL_FI_TOKEN": "o" * 43,
        }
        alias, updates = mod.enrollment_to_updates(self.enrollment())
        aliases = mod.validate_combined(env, alias, updates)
        self.assertEqual(aliases, ["MASTER", "FI"])


if __name__ == "__main__":
    unittest.main()
