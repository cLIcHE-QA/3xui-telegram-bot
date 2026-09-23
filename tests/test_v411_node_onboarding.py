from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import NodeBackupTarget, _load_host_control_targets, _load_node_backup_targets
from system_backup import SystemBackupService


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, filename: str):
    path = ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


host_import = load_script("v411_host_import", "import-host-control-enrollment.py")
node_import = load_script("v411_node_import", "import-node-admin-target.py")
onboard = load_script("v411_onboard", "onboard-node.py")


class StableNodeIdentityTests(unittest.TestCase):
    def test_node_backup_target_loads_optional_node_id(self):
        env = {
            "NODE_BACKUP_TARGETS": "FI",
            "NODE_BACKUP_FI_NODE_NAME": "Finland",
            "NODE_BACKUP_FI_NODE_ID": "2",
            "NODE_BACKUP_FI_PANEL_URL": "https://fi.example.invalid",
            "NODE_BACKUP_FI_API_TOKEN": "x" * 43,
            "NODE_BACKUP_FI_VERIFY_TLS": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            target = _load_node_backup_targets()[0]
        self.assertEqual(target.node_id, 2)

    def test_host_control_target_loads_optional_node_id(self):
        env = {
            "HOST_CONTROL_TARGETS": "FI",
            "HOST_CONTROL_FI_NAME": "Finland",
            "HOST_CONTROL_FI_NODE_ID": "2",
            "HOST_CONTROL_FI_HOST_ID": "fi",
            "HOST_CONTROL_FI_URL": "https://fi-host.example.invalid",
            "HOST_CONTROL_FI_TOKEN": "x" * 43,
            "HOST_CONTROL_FI_VERIFY_TLS": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            target = _load_host_control_targets()[0]
        self.assertEqual(target.node_id, 2)

    def test_duplicate_host_control_node_id_is_rejected(self):
        env = {
            "HOST_CONTROL_TARGETS": "FI,SE",
            "HOST_CONTROL_FI_NAME": "Finland",
            "HOST_CONTROL_FI_NODE_ID": "2",
            "HOST_CONTROL_FI_HOST_ID": "fi",
            "HOST_CONTROL_FI_URL": "https://fi-host.example.invalid",
            "HOST_CONTROL_FI_TOKEN": "f" * 43,
            "HOST_CONTROL_FI_VERIFY_TLS": "true",
            "HOST_CONTROL_SE_NAME": "Sweden",
            "HOST_CONTROL_SE_NODE_ID": "2",
            "HOST_CONTROL_SE_HOST_ID": "se",
            "HOST_CONTROL_SE_URL": "https://se-host.example.invalid",
            "HOST_CONTROL_SE_TOKEN": "s" * 43,
            "HOST_CONTROL_SE_VERIFY_TLS": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(RuntimeError):
                _load_host_control_targets()

    def test_node_id_binding_survives_display_name_change(self):
        target = NodeBackupTarget(
            key="FI",
            node_name="Finland",
            node_id=2,
            panel_url="https://fi.example.invalid",
            api_token="x" * 43,
            verify_tls=True,
        )
        service = SystemBackupService(None, (target,))
        self.assertIs(service.target_for("Renamed Finland", 2), target)

    def test_legacy_name_binding_remains_compatible(self):
        target = NodeBackupTarget(
            key="FI",
            node_name="Finland",
            node_id=None,
            panel_url="https://fi.example.invalid",
            api_token="x" * 43,
            verify_tls=True,
        )
        service = SystemBackupService(None, (target,))
        self.assertIs(service.target_for("finland", 2), target)


class OnboardingImporterTests(unittest.TestCase):
    def test_node_admin_importer_builds_stable_binding(self):
        alias, updates = node_import.enrollment_updates({
            "NODE_ADMIN_ALIAS": "FI",
            "NODE_ADMIN_NODE_ID": "2",
            "NODE_ADMIN_NODE_NAME": "Finland",
            "NODE_ADMIN_PANEL_URL": "https://fi.example.invalid/base",
            "NODE_ADMIN_API_TOKEN": "x" * 43,
            "NODE_ADMIN_VERIFY_TLS": "true",
        })
        self.assertEqual(alias, "FI")
        self.assertEqual(updates["NODE_BACKUP_FI_NODE_ID"], "2")

    def test_node_admin_importer_rejects_plain_http(self):
        with self.assertRaises(SystemExit):
            node_import.enrollment_updates({
                "NODE_ADMIN_ALIAS": "FI",
                "NODE_ADMIN_NODE_ID": "2",
                "NODE_ADMIN_NODE_NAME": "Finland",
                "NODE_ADMIN_PANEL_URL": "http://fi.example.invalid/base",
                "NODE_ADMIN_API_TOKEN": "x" * 43,
                "NODE_ADMIN_VERIFY_TLS": "true",
            })

    def test_host_importer_rejects_duplicate_node_id(self):
        env = {
            "HOST_CONTROL_TARGETS": "SE",
            "HOST_CONTROL_SE_NAME": "Sweden",
            "HOST_CONTROL_SE_NODE_ID": "2",
            "HOST_CONTROL_SE_HOST_ID": "se",
            "HOST_CONTROL_SE_URL": "https://se.example.invalid",
            "HOST_CONTROL_SE_TOKEN": "s" * 43,
            "HOST_CONTROL_SE_VERIFY_TLS": "true",
        }
        alias, updates = host_import.enrollment_to_updates({
            "HOST_CONTROL_ALIAS": "FI",
            "HOST_CONTROL_NAME": "Finland",
            "HOST_CONTROL_HOST_ID": "fi",
            "HOST_CONTROL_URL": "https://fi.example.invalid",
            "HOST_CONTROL_VERIFY_TLS": "true",
            "HOST_CONTROL_TOKEN": "f" * 43,
        })
        updates["HOST_CONTROL_FI_NODE_ID"] = "2"
        with self.assertRaises(SystemExit):
            host_import.validate_combined(env, alias, updates)

    def test_local_onboarding_requires_https(self):
        with self.assertRaises(SystemExit):
            onboard.parse_node_url("http://fi.example.invalid/base")

    def test_local_onboarding_normalizes_browser_panel_url(self):
        parsed = onboard.parse_node_url("https://fi.example.invalid:2053/base/panel/")
        self.assertEqual(parsed["scheme"], "https")
        self.assertEqual(parsed["address"], "fi.example.invalid")
        self.assertEqual(parsed["port"], 2053)
        self.assertEqual(parsed["basePath"], "/base/")

    def test_local_onboarding_requires_private_secret_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "node.env"
            path.write_text("secret\n", encoding="utf-8")
            path.chmod(0o644)
            with self.assertRaises(SystemExit):
                onboard.require_private_file(path)
            path.chmod(0o600)
            onboard.require_private_file(path)

    def test_readiness_button_is_present_on_node_card(self):
        source = (ROOT / "bot.py").read_text(encoding="utf-8")
        self.assertIn('text="🧭 Readiness"', source)
        self.assertIn('admin:node:{node_id}:readiness', source)
        self.assertIn("Stable identity", source)


if __name__ == "__main__":
    unittest.main()
