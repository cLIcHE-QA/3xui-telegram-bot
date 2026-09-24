from __future__ import annotations

import os
from pathlib import Path
import re
import stat
import unittest


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "host_control_agent.py"
CLIENT = ROOT / "host_control.py"
UI = ROOT / "host_control_ui.py"
UNIT = ROOT / "deploy/host-control/3xui-host-control.service"
SUDOERS = ROOT / "deploy/host-control/3xui-host-control.sudoers"
INSTALLER = ROOT / "scripts/install-host-control-agent.sh"
ENDPOINT = ROOT / "scripts/setup-host-control-endpoint.sh"
TLS_REFRESH = ROOT / "scripts/refresh-host-control-tls.sh"
BUNDLE = ROOT / "scripts/build-host-control-bundle.sh"
COMPOSE = ROOT / "docker-compose.yml"


class HostControlDeploymentSecurityTests(unittest.TestCase):
    def test_installer_is_executable(self):
        mode = INSTALLER.stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR)


    def test_endpoint_rollout_keeps_agent_loopback_and_separate_proxy(self):
        text = ENDPOINT.read_text(encoding="utf-8")
        self.assertIn("127.0.0.1:18181", text)
        self.assertIn("3xui-host-control-proxy.service", text)
        self.assertIn("/etc/3xui-host-control/proxy-nginx.conf", text)
        self.assertNotIn("listen 0.0.0.0", text)
        self.assertNotIn("sudo ALL", text)

    def test_remote_tls_has_refresh_timer_and_validates_hostname(self):
        endpoint = ENDPOINT.read_text(encoding="utf-8")
        refresh = TLS_REFRESH.read_text(encoding="utf-8")
        self.assertIn("3xui-host-control-tls-refresh.timer", endpoint)
        self.assertIn("OnCalendar=daily", endpoint)
        self.assertIn("openssl x509", refresh)
        self.assertIn("-checkhost", refresh)
        self.assertIn("certificate/private key mismatch", refresh)
        self.assertIn('systemctl reload "$PROXY_SERVICE"', refresh)

    def test_rollout_tracks_managed_ufw_rule_for_reconfiguration(self):
        text = ENDPOINT.read_text(encoding="utf-8")
        self.assertIn("ufw-managed.env", text)
        self.assertIn("ufw --force delete allow from", text)
        self.assertIn("comment \"$UFW_COMMENT\"", text)

    def test_bundle_is_explicit_secret_free_allowlist(self):
        text = BUNDLE.read_text(encoding="utf-8")
        for required in [
            "host_control_agent.py",
            "scripts/install-host-control-agent.sh",
            "scripts/setup-host-control-endpoint.sh",
            "scripts/refresh-host-control-tls.sh",
            "deploy/host-control/3xui-host-control.service",
            "deploy/host-control/3xui-host-control.sudoers",
        ]:
            self.assertIn(required, text)
        for forbidden in [".env", "/etc/3xui-host-control/token", "x-ui.db", "bot.sqlite3", "privkey.pem"]:
            self.assertNotIn(forbidden, text.lower())

    def test_agent_systemd_service_runs_unprivileged_and_loopback_only(self):
        text = UNIT.read_text(encoding="utf-8")
        self.assertIn("User=3xui-hostctl", text)
        self.assertIn("Group=3xui-hostctl", text)
        self.assertNotIn("User=root", text)
        self.assertIn("ExecStart=/usr/bin/python3 /opt/3xui-host-control/host_control_agent.py", text)
        self.assertIn(
            "EnvironmentFile=-/etc/3xui-host-control/nginx-snapshot.env",
            text,
        )
        self.assertIn("ProtectSystem=strict", text)
        self.assertIn("ProtectHome=true", text)
        self.assertIn("PrivateDevices=true", text)
        self.assertIn("IPAddressDeny=any", text)
        self.assertIn("IPAddressAllow=localhost", text)
        self.assertNotIn("CapabilityBoundingSet=CAP_SYS_ADMIN", text)
        self.assertNotIn("AmbientCapabilities=", text)

    def test_sudoers_is_exact_allowlist_without_wildcards(self):
        text = SUDOERS.read_text(encoding="utf-8")
        commands = {
            "/usr/bin/systemctl start x-ui.service",
            "/usr/bin/systemctl stop x-ui.service",
            "/usr/bin/systemctl restart x-ui.service",
        }
        for command in commands:
            self.assertIn(command, text)
        self.assertEqual(text.count("/usr/bin/systemctl"), 3)
        self.assertNotRegex(text, r"systemctl\s+\*")
        self.assertNotRegex(text, r"x-ui\.service\s+\*")
        self.assertNotIn("ALL=(ALL) NOPASSWD: ALL", text)
        self.assertNotIn("NOPASSWD: ALL", text)
        self.assertNotIn("/bin/sh", text)
        self.assertNotIn("/bin/bash", text)

    def test_installer_does_not_print_or_embed_token(self):
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("secrets.token_urlsafe", text)
        self.assertIn("chmod 0600", text)
        self.assertIn("Token is stored", text)
        self.assertIn("was NOT printed", text)
        forbidden = [
            'cat "$TOKEN_FILE"',
            "cat $TOKEN_FILE",
            'echo "$TOKEN"',
            "echo $TOKEN",
            'printf "%s" "$TOKEN"',
            "set -x",
        ]
        for value in forbidden:
            self.assertNotIn(value, text)

    def test_installer_restarts_agent_after_updating_runtime_files(self):
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("/usr/bin/systemctl enable 3xui-host-control.service", text)
        self.assertIn("/usr/bin/systemctl restart 3xui-host-control.service", text)
        self.assertNotIn(
            "/usr/bin/systemctl enable --now 3xui-host-control.service",
            text,
        )

    def test_installer_does_not_modify_firewall_or_ssh(self):
        text = INSTALLER.read_text(encoding="utf-8").lower()
        for token in ["ufw ", "iptables", "nft ", "sshd", "authorized_keys", "ssh-key"]:
            self.assertNotIn(token, text)

    def test_agent_has_no_generic_host_escape_surface(self):
        text = AGENT.read_text(encoding="utf-8")
        forbidden = [
            "shell=True",
            "subprocess.Popen",
            "os.system(",
            "pty.",
            "paramiko",
            "fabric",
            "docker",
            "iptables",
            "nftables",
            "reboot",
            "shutdown",
        ]
        for value in forbidden:
            self.assertNotIn(value, text)

        routes = set(re.findall(r'"(/v1/[A-Za-z0-9_/{}/.-]+)"', text))
        self.assertTrue({"/v1/status", "/v1/actions"}.issubset(routes))
        for route in routes:
            self.assertNotRegex(route, r"(shell|exec|command|file|docker|firewall|ssh)")

    def test_bot_client_does_not_follow_redirects_with_bearer_token(self):
        text = CLIENT.read_text(encoding="utf-8")
        self.assertIn("allow_redirects=False", text)

    def test_bot_client_has_no_generic_command_surface(self):
        text = CLIENT.read_text(encoding="utf-8")
        for name in ["run_command", "execute_shell", "ssh", "read_file", "write_file"]:
            self.assertNotIn(f"def {name}", text)
            self.assertNotIn(f"async def {name}", text)

    def test_bot_container_has_no_host_escape_socket_or_privilege(self):
        text = COMPOSE.read_text(encoding="utf-8").lower()
        forbidden = [
            "/var/run/docker.sock",
            "/run/docker.sock",
            "/run/systemd/private",
            "privileged: true",
            "network_mode: host",
            "pid: host",
            "cap_sys_admin",
        ]
        for value in forbidden:
            self.assertNotIn(value, text)

    def test_telegram_ui_never_builds_os_commands(self):
        text = UI.read_text(encoding="utf-8")
        for value in [
            "subprocess",
            "os.system",
            "systemctl",
            "/bin/sh",
            "/bin/bash",
            "paramiko",
            "ssh ",
        ]:
            self.assertNotIn(value, text)
        self.assertNotRegex(text, r"(command|argv|executable|unit)\s*=")


if __name__ == "__main__":
    unittest.main()