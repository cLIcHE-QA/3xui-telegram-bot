from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import threading
import unittest
import contextlib
import io
from unittest.mock import patch

from host_control_agent import (
    ALLOWED_ACTIONS,
    SERVICE,
    SUDO,
    SYSTEMCTL,
    AgentConfig,
    AgentConfigError,
    AgentRequestHandler,
    HostControlAgent,
    OperationJournal,
    ServiceController,
    ServiceState,
)


class FakeController:
    def __init__(self, state: str = "running"):
        self.state = state
        self.actions: list[str] = []
        self.fail_returncode = 0
        self.timeout = False
        self.after_override: str | None = None

    def status(self) -> ServiceState:
        active = {
            "running": "active",
            "stopped": "inactive",
            "failed": "failed",
            "transitioning": "activating",
        }.get(self.state, "unknown")
        return ServiceState(self.state, active, self.state)

    def run_action(self, action: str):
        self.actions.append(action)
        if self.timeout:
            raise subprocess.TimeoutExpired(cmd=[SYSTEMCTL], timeout=1)
        if self.fail_returncode:
            return subprocess.CompletedProcess([], self.fail_returncode, "", "failure"), 10
        if self.after_override is not None:
            self.state = self.after_override
        elif action == "stop":
            self.state = "stopped"
        else:
            self.state = "running"
        return subprocess.CompletedProcess([], 0, "", ""), 10

    def wait_for(self, expected: str) -> ServiceState:
        return self.status()


class HostControlAgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = AgentConfig(
            host_id="fi",
            listen_host="127.0.0.1",
            listen_port=18181,
            token="x" * 43,
            db_path=self.root / "agent.sqlite3",
            operation_timeout=5.0,
        )
        self.controller = FakeController()
        self.agent = HostControlAgent(
            self.config,
            journal=OperationJournal(self.config.db_path),
            controller=self.controller,
        )

    def test_closed_action_enum(self):
        self.assertEqual(ALLOWED_ACTIONS, frozenset({"start", "stop", "restart"}))
        for value in ["shell", "exec", "bash", "reboot", "docker", "x-ui.service", "../stop"]:
            status, body = self.agent.execute("a" * 32, value)
            self.assertEqual(status, 400)
            self.assertEqual(body["error"], "invalid_action")
        self.assertEqual(self.controller.actions, [])

    def test_invalid_operation_id_does_not_dispatch(self):
        status, _ = self.agent.execute("../bad", "restart")
        self.assertEqual(status, 400)
        self.assertEqual(self.controller.actions, [])

    def test_start_already_running_is_idempotent_without_systemctl(self):
        status, body = self.agent.execute("1" * 32, "start")
        self.assertEqual(status, 200)
        self.assertEqual(body["result"], "success")
        self.assertFalse(body["changed"])
        self.assertEqual(self.controller.actions, [])

    def test_stop_already_stopped_is_idempotent_without_systemctl(self):
        self.controller.state = "stopped"
        status, body = self.agent.execute("2" * 32, "stop")
        self.assertEqual(status, 200)
        self.assertEqual(body["result"], "success")
        self.assertFalse(body["changed"])
        self.assertEqual(self.controller.actions, [])

    def test_restart_dispatches_once_and_replay_is_cached(self):
        op_id = "3" * 32
        status, body = self.agent.execute(op_id, "restart")
        self.assertEqual(status, 200)
        self.assertEqual(body["result"], "success")
        self.assertEqual(self.controller.actions, ["restart"])

        status, replay = self.agent.execute(op_id, "restart")
        self.assertEqual(status, 200)
        self.assertTrue(replay["replayed"])
        self.assertEqual(self.controller.actions, ["restart"])

    def test_operation_id_cannot_change_action(self):
        op_id = "4" * 32
        self.agent.execute(op_id, "restart")
        status, body = self.agent.execute(op_id, "stop")
        self.assertEqual(status, 409)
        self.assertEqual(body["error"], "operation_id_conflict")
        self.assertEqual(self.controller.actions, ["restart"])

    def test_timeout_becomes_uncertain_and_never_replays(self):
        op_id = "5" * 32
        self.controller.timeout = True
        status, body = self.agent.execute(op_id, "restart")
        self.assertEqual(status, 504)
        self.assertEqual(body["result"], "uncertain")
        self.assertEqual(self.controller.actions, ["restart"])

        self.controller.timeout = False
        status, replay = self.agent.execute(op_id, "restart")
        self.assertEqual(status, 200)
        self.assertEqual(replay["result"], "uncertain")
        self.assertTrue(replay["replayed"])
        self.assertEqual(self.controller.actions, ["restart"])

    def test_failed_systemctl_is_not_retried(self):
        op_id = "6" * 32
        self.controller.fail_returncode = 1
        status, body = self.agent.execute(op_id, "restart")
        self.assertEqual(status, 503)
        self.assertEqual(body["result"], "failed")
        self.assertEqual(body["error_code"], "systemctl_failed")
        self.agent.execute(op_id, "restart")
        self.assertEqual(self.controller.actions, ["restart"])

    def test_postcondition_failure_is_uncertain(self):
        op_id = "7" * 32
        self.controller.after_override = "transitioning"
        status, body = self.agent.execute(op_id, "restart")
        self.assertEqual(status, 504)
        self.assertEqual(body["result"], "uncertain")
        self.assertEqual(body["error_code"], "postcondition_timeout")

    def test_journal_contains_no_token_or_command(self):
        self.agent.execute("8" * 32, "restart")
        data = self.config.db_path.read_bytes()
        self.assertNotIn(self.config.token.encode(), data)
        self.assertNotIn(b"Authorization", data)
        self.assertNotIn(b"/usr/bin/sudo", data)

    def test_operation_log_contains_only_normalized_metadata(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.agent.execute("0" * 32, "restart")
        logged = out.getvalue()
        self.assertIn('"event":"host_control_operation"', logged)
        self.assertIn('"action":"restart"', logged)
        self.assertNotIn(self.config.token, logged)
        self.assertNotIn("Authorization", logged)
        self.assertNotIn("/usr/bin/sudo", logged)
        self.assertNotIn("systemctl restart", logged)

    def test_interrupted_started_operation_recovers_as_uncertain(self):
        journal = self.agent.journal
        journal.begin("9" * 32, "restart", "running")
        # Re-open simulates agent process restart.
        reopened = OperationJournal(self.config.db_path)
        record = reopened.get("9" * 32)
        self.assertIsNotNone(record)
        self.assertEqual(record.result, "uncertain")
        self.assertEqual(record.error_code, "agent_interrupted")

    def test_concurrent_mutation_is_rejected(self):
        acquired = self.agent._mutation_lock.acquire(blocking=False)
        self.assertTrue(acquired)
        try:
            status, body = self.agent.execute("a" * 32, "restart")
        finally:
            self.agent._mutation_lock.release()
        self.assertEqual(status, 409)
        self.assertEqual(body["error"], "operation_in_progress")
        self.assertEqual(self.controller.actions, [])


class ServiceControllerSecurityTests(unittest.TestCase):
    def test_exact_status_argv_and_shell_false(self):
        calls = []

        def runner(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(
                argv, 0, "ActiveState=active\nSubState=running\n", ""
            )

        state = ServiceController(timeout=5, runner=runner).status()
        self.assertEqual(state.state, "running")
        argv, kwargs = calls[0]
        self.assertEqual(
            argv,
            [
                SYSTEMCTL,
                "show",
                SERVICE,
                "--property=ActiveState",
                "--property=SubState",
                "--no-pager",
            ],
        )
        self.assertIs(kwargs["shell"], False)

    def test_exact_mutation_argv_and_shell_false(self):
        calls = []

        def runner(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0, "", "")

        controller = ServiceController(timeout=5, runner=runner, monotonic=lambda: 1.0)
        controller.run_action("restart")
        argv, kwargs = calls[0]
        self.assertEqual(argv, [SUDO, "-n", SYSTEMCTL, "restart", SERVICE])
        self.assertIs(kwargs["shell"], False)

    def test_invalid_action_never_reaches_runner(self):
        called = False

        def runner(*args, **kwargs):
            nonlocal called
            called = True
            raise AssertionError("runner must not be called")

        with self.assertRaises(Exception):
            ServiceController(timeout=5, runner=runner).run_action("reboot")
        self.assertFalse(called)


class AgentConfigSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.token_file = self.root / "token"
        self.token_file.write_text("t" * 43, encoding="utf-8")
        os.chmod(self.token_file, 0o600)
        self.base_env = {
            "HOST_CONTROL_AGENT_ID": "fi",
            "HOST_CONTROL_AGENT_LISTEN": "127.0.0.1:18181",
            "HOST_CONTROL_AGENT_TOKEN_FILE": str(self.token_file),
            "HOST_CONTROL_AGENT_DB": str(self.root / "agent.sqlite3"),
            "HOST_CONTROL_AGENT_OPERATION_TIMEOUT": "20",
        }

    def load(self, **changes):
        env = self.base_env | {k: str(v) for k, v in changes.items()}
        with patch.dict(os.environ, env, clear=True):
            return AgentConfig.from_env()

    def test_loopback_only(self):
        self.assertEqual(self.load().listen_host, "127.0.0.1")
        for address in ["0.0.0.0:18181", "192.0.2.10:18181", "10.0.0.2:18181"]:
            with self.subTest(address=address), self.assertRaises(AgentConfigError):
                self.load(HOST_CONTROL_AGENT_LISTEN=address)

    def test_service_cannot_be_changed(self):
        with self.assertRaises(AgentConfigError):
            self.load(HOST_CONTROL_AGENT_SERVICE="docker.service")

    def test_token_file_permissions_are_fail_closed(self):
        os.chmod(self.token_file, 0o640)
        with self.assertRaises(AgentConfigError):
            self.load()

    def test_token_symlink_is_rejected(self):
        real = self.root / "real-token"
        real.write_text("r" * 43, encoding="utf-8")
        os.chmod(real, 0o600)
        self.token_file.unlink()
        self.token_file.symlink_to(real)
        with self.assertRaises(AgentConfigError):
            self.load()

    def test_short_token_is_rejected(self):
        self.token_file.write_text("short", encoding="utf-8")
        os.chmod(self.token_file, 0o600)
        with self.assertRaises(AgentConfigError):
            self.load()


class RequestTargetSecurityTests(unittest.TestCase):
    def test_query_string_is_rejected(self):
        handler = object.__new__(AgentRequestHandler)
        handler.path = "/v1/status?command=whoami"
        self.assertIsNone(handler._path())

    def test_plain_known_path_is_accepted(self):
        handler = object.__new__(AgentRequestHandler)
        handler.path = "/v1/status"
        self.assertEqual(handler._path(), "/v1/status")


class SourceSecurityTests(unittest.TestCase):
    def test_agent_has_no_shell_true_or_ssh_execution(self):
        source = Path("host_control_agent.py").read_text(encoding="utf-8")
        self.assertNotIn("shell=True", source)
        self.assertNotIn("paramiko", source)
        self.assertNotIn("subprocess.Popen", source)
        self.assertNotIn("os.system(", source)
        self.assertNotIn("exec(", source)
        self.assertNotIn("eval(", source)

    def test_managed_service_is_hard_coded(self):
        self.assertEqual(SERVICE, "x-ui.service")


if __name__ == "__main__":
    unittest.main()
