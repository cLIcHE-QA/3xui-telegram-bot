from __future__ import annotations

import os
import subprocess
import tempfile
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


    def test_bind_parses_admin_and_host_control_enrollment_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            node = root / "node.env"
            admin = root / "admin.env"
            host = root / "host.env"
            env_file = root / ".env"
            for path in (node, admin, host, env_file):
                path.write_text("placeholder=1\n", encoding="utf-8")

            log = root / "calls.log"
            fake_python = root / "python3"
            fake_python.write_text(
                "#!/usr/bin/env bash\n"
                "set -eu\n"
                "if [[ \"$1\" == *\"scripts/onboard-node.py\" ]]; then\n"
                "  printf '%s\\n' 'Node already registered. NODE_ID=7'\n"
                "  exit 0\n"
                "fi\n"
                "printf '%s\\n' \"$*\" >> \"$CALL_LOG\"\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)

            proc_env = os.environ.copy()
            proc_env["PATH"] = f"{root}:{proc_env['PATH']}"
            proc_env["CALL_LOG"] = str(log)
            result = subprocess.run(
                [
                    "bash",
                    str(WRAPPER),
                    "bind",
                    "--node-enrollment",
                    str(node),
                    "--admin-enrollment",
                    str(admin),
                    "--host-control-enrollment",
                    str(host),
                    "--env",
                    str(env_file),
                ],
                cwd=ROOT,
                env=proc_env,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            calls = log.read_text(encoding="utf-8")
            self.assertIn(
                f"scripts/import-node-admin-target.py {admin} --env {env_file} --node-id 7 --check-only",
                calls,
            )
            self.assertIn(
                f"scripts/import-host-control-enrollment.py {host} --env {env_file} --node-id 7 --check-only",
                calls,
            )

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
