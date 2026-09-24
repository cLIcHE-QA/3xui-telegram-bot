from __future__ import annotations

import asyncio
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import aiohttp

from deploy_agent import AgentConfig, DeployAgent, OperationJournal
from deploy_control import DeployControlClient, DeployControlError


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "deploy_agent.py"
CLIENT = ROOT / "deploy_control.py"
UI = ROOT / "bot_updates.py"
HELPER = ROOT / "scripts/3xui-bot-deploy-helper.sh"
INSTALLER = ROOT / "scripts/install-deploy-agent.sh"
UNIT = ROOT / "deploy/deploy-agent/3xui-deploy-agent.service"
SUDOERS = ROOT / "deploy/deploy-agent/3xui-deploy-agent.sudoers"
COMPOSE = ROOT / "docker-compose.yml"
BOT = ROOT / "bot.py"


class RecoveringAgent(DeployAgent):
    status_values: dict[str, str] = {}

    def _status_values(self) -> dict[str, str]:
        return dict(self.status_values)


class DeployAgentJournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "agent.sqlite3"
        self.config = AgentConfig(
            listen_host="127.0.0.1",
            listen_port=18184,
            token="x" * 48,
            db_path=self.db_path,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_operation_id_is_idempotent_but_cannot_change_target(self):
        agent = DeployAgent(self.config)
        agent._deploy_worker = lambda operation_id: None  # type: ignore[method-assign]

        status, first = agent.start_deploy(
            "a" * 32,
            "v4.19.0",
            False,
        )
        self.assertEqual(status, 202)
        self.assertEqual(first["operation_id"], "a" * 32)

        status, replay = agent.start_deploy(
            "a" * 32,
            "v4.19.0",
            False,
        )
        self.assertEqual(status, 200)
        self.assertTrue(replay["replayed"])

        status, conflict = agent.start_deploy(
            "a" * 32,
            "v4.20.0",
            False,
        )
        self.assertEqual(status, 409)
        self.assertEqual(conflict["error"], "operation_id_conflict")

    def test_agent_restart_never_replays_interrupted_mutation(self):
        journal = OperationJournal(self.db_path)
        journal.create("b" * 32, "v4.19.0", False)
        journal.update("b" * 32, state="deploying")

        RecoveringAgent.status_values = {
            "STATUS_OK": "1",
            "CURRENT_RELEASE": "v4.18.0",
            "CURRENT_SHA": "1" * 40,
            "HEALTH": "ok",
            "DB": "ok",
            "CONNECTIVITY": "ok",
        }
        agent = RecoveringAgent(self.config)
        record = agent.journal.get("b" * 32)
        self.assertIsNotNone(record)
        self.assertEqual(record.state, "unknown")
        self.assertEqual(
            record.error_code,
            "agent_interrupted_mutation_not_retried",
        )

    def test_agent_restart_can_prove_success_read_only(self):
        journal = OperationJournal(self.db_path)
        journal.create("c" * 32, "v4.19.0", False)
        journal.update("c" * 32, state="verifying")

        RecoveringAgent.status_values = {
            "STATUS_OK": "1",
            "CURRENT_RELEASE": "v4.19.0",
            "CURRENT_SHA": "2" * 40,
            "HEALTH": "ok",
            "DB": "ok",
            "CONNECTIVITY": "ok",
        }
        agent = RecoveringAgent(self.config)
        record = agent.journal.get("c" * 32)
        self.assertEqual(record.state, "success")
        self.assertEqual(record.current_release, "v4.19.0")


class DeployClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_lost_post_response_is_uncertain_and_never_retried(self):
        client = DeployControlClient(
            "http://172.19.0.1:18184",
            "t" * 48,
        )
        call = AsyncMock(side_effect=aiohttp.ClientConnectionError("lost"))
        with patch.object(client, "_http", call):
            with self.assertRaises(DeployControlError) as raised:
                await client.deploy("d" * 32, "v4.19.0")
        self.assertTrue(raised.exception.uncertain)
        self.assertEqual(call.await_count, 1)

    async def test_client_rejects_arbitrary_release_before_http(self):
        client = DeployControlClient(
            "http://172.19.0.1:18184",
            "t" * 48,
        )
        call = AsyncMock()
        with patch.object(client, "_http", call):
            with self.assertRaisesRegex(DeployControlError, "Invalid release"):
                await client.deploy("e" * 32, "main")
        call.assert_not_awaited()


class DeployAgentSecurityContractTests(unittest.TestCase):
    def test_host_scripts_are_executable(self):
        self.assertTrue(HELPER.stat().st_mode & stat.S_IXUSR)
        self.assertTrue(INSTALLER.stat().st_mode & stat.S_IXUSR)

    def test_agent_api_has_no_generic_exec_or_path_surface(self):
        text = AGENT.read_text(encoding="utf-8")
        for forbidden in [
            '"command"',
            '"argv"',
            '"executable"',
            '"script_path"',
            '"filesystem_path"',
            '"environment"',
            "shell=True",
            "os.system(",
            "/bin/sh",
            "/bin/bash",
        ]:
            self.assertNotIn(forbidden, text)
        self.assertIn('path != "/v1/deploy"', text)
        self.assertIn('"/v1/releases/latest"', text)
        self.assertIn('"/v1/history"', text)
        self.assertIn('"/v1/operations/"', text)
        self.assertIn('set(body) != {', text)

    def test_root_helper_is_closed_surface(self):
        text = HELPER.read_text(encoding="utf-8")
        for command in ["status)", "latest)", "preflight)", "notes)", "deploy)"]:
            self.assertIn(command, text)
        for forbidden in ["eval ", "bash -c", "sh -c", "source "$", "exec "$"]:
            self.assertNotIn(forbidden, text)
        self.assertIn("RELEASE_RE=", text)
        self.assertIn('EXPECTED_REPOSITORY="cLIcHE-QA/3xui-telegram-bot"', text)
        self.assertIn('REPO_ROOT="/opt/3xui-bot/3xui-telegram-bot"', text)
        self.assertIn('SSH_KEY="/etc/3xui-deploy-agent/deploy-key"', text)
        self.assertIn('SSH_KNOWN_HOSTS="/etc/3xui-deploy-agent/known_hosts"', text)

    def test_systemd_agent_is_unprivileged_and_scoped(self):
        text = UNIT.read_text(encoding="utf-8")
        self.assertIn("User=3xui-deploy", text)
        self.assertIn("Group=3xui-deploy", text)
        self.assertNotIn("User=root", text)
        self.assertIn("ProtectSystem=strict", text)
        self.assertIn("ProtectHome=true", text)
        self.assertIn("PrivateDevices=true", text)
        self.assertIn("/var/lib/3xui-deploy-agent", text)
        self.assertIn("/opt/3xui-bot/3xui-telegram-bot", text)
        self.assertNotIn("CapabilityBoundingSet=CAP_SYS_ADMIN", text)
        self.assertNotIn("AmbientCapabilities=", text)

    def test_sudoers_exposes_only_root_owned_helper(self):
        text = SUDOERS.read_text(encoding="utf-8")
        self.assertIn("/usr/local/libexec/3xui-bot-deploy", text)
        self.assertNotIn("docker ", text)
        self.assertNotIn("git ", text)
        self.assertNotIn("/bin/sh", text)
        self.assertNotIn("/bin/bash", text)
        self.assertNotIn("NOPASSWD: ALL", text)

    def test_installer_never_prints_secrets(self):
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("secrets.token_urlsafe", text)
        self.assertIn("chmod 0600", text)
        self.assertIn("was NOT printed", text)
        self.assertIn("/etc/3xui-deploy-agent/deploy-key", text)
        self.assertIn("/etc/3xui-deploy-agent/known_hosts", text)
        for forbidden in [
            'cat "$TOKEN_FILE"',
            "cat $TOKEN_FILE",
            'echo "$TOKEN"',
            "set -x",
        ]:
            self.assertNotIn(forbidden, text)

    def test_bot_container_still_has_no_docker_or_host_control_socket(self):
        text = COMPOSE.read_text(encoding="utf-8").lower()
        for forbidden in [
            "/var/run/docker.sock",
            "/run/docker.sock",
            "/run/systemd/private",
            "privileged: true",
            "network_mode: host",
            "pid: host",
            "cap_sys_admin",
        ]:
            self.assertNotIn(forbidden, text)

    def test_telegram_ui_does_not_execute_host_commands(self):
        text = UI.read_text(encoding="utf-8")
        for forbidden in [
            "subprocess",
            "os.system",
            "docker ",
            "git fetch",
            "/bin/sh",
            "/bin/bash",
        ]:
            self.assertNotIn(forbidden, text)

    def test_startup_recovery_does_not_block_health_endpoint(self):
        text = BOT.read_text(encoding="utf-8")
        main = text[text.index("async def main():"):]
        immediate = main.index("await reconcile_deploy_jobs(wait_seconds=0)")
        stale = main.index("await db.fail_stale_job_runs()")
        proxy = main.index("await proxy.start()")
        background = main.index("asyncio.create_task(_recover_deploy_after_health())")
        polling = main.index("await dp.start_polling(bot)")
        self.assertLess(immediate, stale)
        self.assertLess(stale, proxy)
        self.assertLess(proxy, background)
        self.assertLess(background, polling)
        self.assertNotIn("reconcile_deploy_jobs(wait_seconds=45)", main)


if __name__ == "__main__":
    unittest.main()
