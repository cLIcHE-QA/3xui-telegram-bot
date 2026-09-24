from __future__ import annotations

import asyncio
import io
from pathlib import Path
import tarfile
import tempfile
import threading
import unittest
from unittest.mock import AsyncMock, patch

import aiohttp

from host_control import (
    HostControlClient,
    HostControlError,
)
from host_control_agent import (
    AgentConfig,
    AgentHTTPServer,
    HostControlAgent,
    OperationJournal,
    ServiceState,
)


def status_payload(**changes):
    data = {
        "schema": 1,
        "host_id": "fi",
        "service": "x-ui.service",
        "state": "running",
        "active_state": "active",
        "sub_state": "running",
        "agent_version": "0.1.0",
        "timestamp": "2026-09-23T18:00:00Z",
    }
    data.update(changes)
    return data


def operation_payload(op_id="a" * 32, action="restart", **changes):
    data = {
        "schema": 1,
        "host_id": "fi",
        "service": "x-ui.service",
        "operation_id": op_id,
        "action": action,
        "result": "success",
        "changed": True,
        "before": "running",
        "after": "running",
        "duration_ms": 100,
        "error_code": "",
        "created_at": "2026-09-23T18:00:00Z",
        "finished_at": "2026-09-23T18:00:01Z",
        "replayed": False,
    }
    data.update(changes)
    return data


class HostControlClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = HostControlClient(
            "https://host-control.example.invalid",
            "secret-token",
            "fi",
            verify_tls=True,
        )

    async def test_status_validates_host_identity(self):
        with patch.object(
            self.client, "_http", new=AsyncMock(return_value=(200, status_payload()))
        ):
            state = await self.client.status()
        self.assertEqual(state.host_id, "fi")
        self.assertEqual(state.state, "running")

        with patch.object(
            self.client,
            "_http",
            new=AsyncMock(return_value=(200, status_payload(host_id="master"))),
        ):
            with self.assertRaisesRegex(HostControlError, "identity"):
                await self.client.status()

    async def test_execute_does_not_retry_post_after_network_error(self):
        op_id = "b" * 32
        calls = []

        async def fake_http(method, path, *, body=None):
            calls.append((method, path, body))
            if path == "/v1/status":
                return 200, status_payload()
            if method == "POST":
                raise aiohttp.ClientConnectionError("lost response")
            return 404, {"error": "operation_not_found"}

        with patch.object(self.client, "_http", side_effect=fake_http):
            with self.assertRaises(HostControlError) as ctx:
                await self.client.execute("restart", op_id)

        self.assertTrue(ctx.exception.uncertain)
        self.assertEqual([x[0] for x in calls], ["GET", "POST", "GET"])
        self.assertEqual(sum(1 for x in calls if x[0] == "POST"), 1)

    async def test_execute_recovers_lost_response_from_read_only_lookup(self):
        op_id = "c" * 32
        calls = []

        async def fake_http(method, path, *, body=None):
            calls.append((method, path, body))
            if path == "/v1/status":
                return 200, status_payload()
            if method == "POST":
                raise asyncio.TimeoutError()
            return 200, operation_payload(op_id=op_id)

        with patch.object(self.client, "_http", side_effect=fake_http):
            result = await self.client.execute("restart", op_id)

        self.assertEqual(result.result, "success")
        self.assertEqual([x[0] for x in calls], ["GET", "POST", "GET"])

    async def test_504_operation_response_is_returned_as_uncertain_record(self):
        op_id = "d" * 32
        payload = operation_payload(
            op_id=op_id,
            result="uncertain",
            error_code="postcondition_timeout",
        )
        request = AsyncMock(side_effect=[
            (200, status_payload()),
            (504, payload),
        ])
        with patch.object(self.client, "_http", new=request):
            result = await self.client.execute("restart", op_id)
        self.assertEqual(result.result, "uncertain")
        self.assertEqual(result.error_code, "postcondition_timeout")

    async def test_invalid_action_is_rejected_before_network(self):
        request = AsyncMock()
        with patch.object(self.client, "_http", new=request):
            with self.assertRaises(HostControlError):
                await self.client.execute("shell", "e" * 32)
        request.assert_not_awaited()

    async def test_invalid_operation_id_is_rejected_before_network(self):
        request = AsyncMock()
        with patch.object(self.client, "_http", new=request):
            with self.assertRaises(HostControlError):
                await self.client.execute("restart", "../bad")
        request.assert_not_awaited()

    async def test_service_and_schema_mismatch_fail_closed(self):
        for payload in [
            status_payload(service="ssh.service"),
            status_payload(schema=2),
        ]:
            with self.subTest(payload=payload), patch.object(
                self.client, "_http", new=AsyncMock(return_value=(200, payload))
            ):
                with self.assertRaises(HostControlError):
                    await self.client.status()

    async def test_operation_action_mismatch_fails_closed(self):
        op_id = "f" * 32
        request = AsyncMock(side_effect=[
            (200, status_payload()),
            (200, operation_payload(op_id=op_id, action="stop")),
        ])
        with patch.object(self.client, "_http", new=request):
            with self.assertRaises(HostControlError) as ctx:
                await self.client.execute("restart", op_id)
        self.assertTrue(ctx.exception.uncertain)

    async def test_unstable_preflight_blocks_mutation_post(self):
        for state, code in [("unknown", "service_state_unknown"), ("transitioning", "service_transitioning")]:
            calls = []

            async def fake_http(method, path, *, body=None, _state=state):
                calls.append((method, path, body))
                return 200, status_payload(state=_state)

            with self.subTest(state=state), patch.object(self.client, "_http", side_effect=fake_http):
                with self.assertRaises(HostControlError) as ctx:
                    await self.client.execute("restart", "9" * 32)
                self.assertEqual(ctx.exception.code, code)
                self.assertEqual([x[0] for x in calls], ["GET"])

    async def test_wrong_host_preflight_blocks_mutation_post(self):
        op_id = "1" * 32
        calls = []

        async def fake_http(method, path, *, body=None):
            calls.append((method, path, body))
            return 200, status_payload(host_id="master")

        with patch.object(self.client, "_http", side_effect=fake_http):
            with self.assertRaises(HostControlError) as ctx:
                await self.client.execute("restart", op_id)

        self.assertEqual(ctx.exception.code, "host_id_mismatch")
        self.assertEqual([x[0] for x in calls], ["GET"])

    async def test_malformed_mutation_response_is_uncertain(self):
        op_id = "2" * 32
        request = AsyncMock(side_effect=[
            (200, status_payload()),
            (200, operation_payload(op_id=op_id, duration_ms="not-a-number")),
        ])
        with patch.object(self.client, "_http", new=request):
            with self.assertRaises(HostControlError) as ctx:
                await self.client.execute("restart", op_id)
        self.assertTrue(ctx.exception.uncertain)

    def test_client_exposes_no_generic_command_method(self):
        forbidden = {"shell", "exec", "run_command", "ssh", "read_file", "write_file"}
        self.assertTrue(forbidden.isdisjoint(set(dir(self.client))))



class SnapshotController:
    def status(self):
        return ServiceState("running", "active", "running")


class HostControlSnapshotClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        nginx = root / "nginx"
        nginx.mkdir()
        (nginx / "nginx.conf").write_text("events {}\n", encoding="utf-8")
        self.token = "z" * 48
        config = AgentConfig(
            host_id="fi",
            listen_host="127.0.0.1",
            listen_port=0,
            token=self.token,
            db_path=root / "agent.sqlite3",
            operation_timeout=2.0,
            nginx_source=nginx,
        )
        agent = HostControlAgent(
            config,
            journal=OperationJournal(config.db_path),
            controller=SnapshotController(),
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

    async def test_client_downloads_and_validates_fixed_nginx_snapshot(self):
        client = HostControlClient(
            f"http://127.0.0.1:{self.port}",
            self.token,
            "fi",
            verify_tls=False,
        )
        body = await client.download_nginx_snapshot()
        with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as archive:
            self.assertIn("nginx.conf", archive.getnames())
            self.assertIn("_snapshot.json", archive.getnames())

    async def test_client_reads_snapshot_until_eof_across_chunks(self):
        body = b"first-chunk" + b"second-chunk"
        digest = __import__("hashlib").sha256(body).hexdigest()

        class FakeStream:
            def __init__(self):
                self.chunks = [b"first-chunk", b"second-chunk", b""]

            async def read(self, _size=-1):
                return self.chunks.pop(0)

        class FakeResponse:
            status = 200
            content_length = len(body)
            headers = {
                "X-Host-Control-Schema": "1",
                "X-Host-Control-Host-Id": "fi",
                "X-Host-Control-Component": "nginx",
                "X-Content-SHA256": digest,
            }

            def __init__(self):
                self.content = FakeStream()

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class FakeSession:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            def get(self, *args, **kwargs):
                return FakeResponse()

        with patch("host_control.aiohttp.ClientSession", FakeSession):
            result = await self.client.download_nginx_snapshot()

        self.assertEqual(result, body)

    async def test_client_rejects_wrong_snapshot_host_identity(self):
        client = HostControlClient(
            f"http://127.0.0.1:{self.port}",
            self.token,
            "master",
            verify_tls=False,
        )
        with self.assertRaises(HostControlError) as ctx:
            await client.download_nginx_snapshot()
        self.assertEqual(ctx.exception.code, "host_id_mismatch")


if __name__ == "__main__":
    unittest.main()