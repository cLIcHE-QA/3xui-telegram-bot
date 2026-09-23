from __future__ import annotations

import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from host_control_agent import (
    AgentConfig,
    AgentHTTPServer,
    HostControlAgent,
    OperationJournal,
    ServiceState,
)


class FakeController:
    def __init__(self):
        self.state = "running"
        self.actions: list[str] = []

    def status(self) -> ServiceState:
        active = "active" if self.state == "running" else "inactive"
        return ServiceState(self.state, active, self.state)

    def run_action(self, action: str):
        import subprocess
        self.actions.append(action)
        self.state = "stopped" if action == "stop" else "running"
        return subprocess.CompletedProcess([], 0, "", ""), 1

    def wait_for(self, expected: str) -> ServiceState:
        return self.status()


class HostControlHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.token = "t" * 48
        self.controller = FakeController()
        config = AgentConfig(
            host_id="fi",
            listen_host="127.0.0.1",
            listen_port=0,
            token=self.token,
            db_path=root / "agent.sqlite3",
            operation_timeout=2.0,
        )
        agent = HostControlAgent(
            config,
            journal=OperationJournal(config.db_path),
            controller=self.controller,
        )
        self.server = AgentHTTPServer(("127.0.0.1", 0), agent)
        self.port = int(self.server.server_address[1])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._close_server)

    def _close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method: str, path: str, *, body=None, auth=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        headers = {"Accept": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {self.token}"
        payload = None
        if body is not None:
            payload = json.dumps(body)
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=payload, headers=headers)
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        data = json.loads(raw.decode("utf-8"))
        return response.status, response.getheaders(), data, raw

    def test_status_requires_authentication(self):
        status, _, data, raw = self.request("GET", "/v1/status", auth=False)
        self.assertEqual(status, 401)
        self.assertEqual(data, {"error": "unauthorized"})
        self.assertNotIn(self.token.encode(), raw)

    def test_status_returns_only_normalized_service_identity(self):
        status, headers, data, raw = self.request("GET", "/v1/status")
        self.assertEqual(status, 200)
        self.assertEqual(data["schema"], 1)
        self.assertEqual(data["host_id"], "fi")
        self.assertEqual(data["service"], "x-ui.service")
        self.assertEqual(data["state"], "running")
        self.assertEqual(dict(headers).get("Cache-Control"), "no-store")
        self.assertNotIn(self.token.encode(), raw)

    def test_query_string_is_rejected(self):
        status, _, data, _ = self.request("GET", "/v1/status?command=whoami")
        self.assertEqual(status, 400)
        self.assertEqual(data["error"], "invalid_request_target")

    def test_unknown_shell_exec_file_routes_do_not_exist(self):
        for path in ["/v1/shell", "/v1/exec", "/v1/command", "/v1/files", "/v1/docker"]:
            with self.subTest(path=path):
                status, _, data, _ = self.request("GET", path)
                self.assertEqual(status, 404)
                self.assertEqual(data["error"], "not_found")

    def test_mutation_schema_rejects_extra_command_fields_before_dispatch(self):
        body = {
            "operation_id": "a" * 32,
            "action": "restart",
            "command": "id",
        }
        status, _, data, _ = self.request("POST", "/v1/actions", body=body)
        self.assertEqual(status, 400)
        self.assertEqual(data["error"], "invalid_request")
        self.assertEqual(self.controller.actions, [])

    def test_invalid_action_never_reaches_controller(self):
        body = {"operation_id": "b" * 32, "action": "shell"}
        status, _, data, _ = self.request("POST", "/v1/actions", body=body)
        self.assertEqual(status, 400)
        self.assertEqual(data["error"], "invalid_action")
        self.assertEqual(self.controller.actions, [])

    def test_allowed_action_dispatches_once(self):
        op_id = "c" * 32
        body = {"operation_id": op_id, "action": "restart"}
        status, _, data, _ = self.request("POST", "/v1/actions", body=body)
        self.assertEqual(status, 200)
        self.assertEqual(data["result"], "success")
        self.assertEqual(self.controller.actions, ["restart"])

        status, _, replay, _ = self.request("POST", "/v1/actions", body=body)
        self.assertEqual(status, 200)
        self.assertTrue(replay["replayed"])
        self.assertEqual(self.controller.actions, ["restart"])

    def test_unsupported_http_methods_are_rejected(self):
        for method in ["PUT", "PATCH", "DELETE"]:
            with self.subTest(method=method):
                status, _, data, _ = self.request(method, "/v1/actions")
                self.assertEqual(status, 405)
                self.assertEqual(data["error"], "method_not_allowed")

    def test_operation_lookup_requires_exact_hex_id(self):
        status, _, data, _ = self.request("GET", "/v1/operations/../../etc/passwd")
        self.assertEqual(status, 400)
        self.assertEqual(data["error"], "invalid_operation_id")


if __name__ == "__main__":
    unittest.main()
