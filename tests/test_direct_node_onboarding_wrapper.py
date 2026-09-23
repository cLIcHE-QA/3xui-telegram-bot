from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "onboard-direct-node.sh"


class DirectNodeOnboardingWrapperTests(unittest.TestCase):
    def test_wrapper_shell_syntax_and_help(self):
        subprocess.run(["bash", "-n", str(WRAPPER)], check=True)
        result = subprocess.run(
            ["bash", str(WRAPPER), "--help"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("prepare", result.stdout)
        self.assertIn("bind", result.stdout)

    def test_wrapper_reuses_security_helpers_and_single_bot_recreate(self):
        text = WRAPPER.read_text(encoding="utf-8")
        self.assertIn("build-host-control-bundle.sh", text)
        self.assertIn("setup-host-control-endpoint.sh remote", text)
        self.assertIn("--apply-ufw", text)
        self.assertIn('import-node-admin-target.py "$admin_enrollment" --env "$env_path" --node-id "$node_id" --check-only', text)
        self.assertIn('import-host-control-enrollment.py "$host_control_enrollment" --env "$env_path" --node-id "$node_id" --check-only', text)
        self.assertIn('import-host-control-enrollment.py "$host_control_enrollment" --env "$env_path" --node-id "$node_id" --recreate-bot', text)
        self.assertNotIn('import-node-admin-target.py "$admin_enrollment" --env "$env_path" --node-id "$node_id" --recreate-bot', text)

    def test_wrapper_does_not_expose_secret_or_destructive_surfaces(self):
        text = WRAPPER.read_text(encoding="utf-8")
        for forbidden in [
            "set -x",
            "docker compose down",
            "docker system prune",
            'cat "$node_enrollment"',
            'cat "$admin_enrollment"',
            'cat "$host_control_enrollment"',
            "HOST_CONTROL_TOKEN",
            "NODE_ADMIN_API_TOKEN",
            "NODE_ONBOARD_SYNC_TOKEN",
        ]:
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
