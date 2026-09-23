from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import aiohttp

from host_control import (
    HostControlClient,
    HostControlError,
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


if __name__ == "__main__":
    unittest.main()
