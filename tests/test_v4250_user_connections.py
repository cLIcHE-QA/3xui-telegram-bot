from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest.mock import AsyncMock

from admin_privileges import required_role_for_callback
from xui import XUIClient


ROOT = Path(__file__).resolve().parents[1]


class V4250UserConnectionsTests(unittest.IsolatedAsyncioTestCase):
    def test_openapi_manifest_adds_reviewed_connections_endpoints(self):
        contract = json.loads(
            (ROOT / "contracts" / "3xui" / "contract.json").read_text(encoding="utf-8")
        )
        endpoints = {(item["method"], item["path"]) for item in contract["endpoints"]}
        self.assertIn(("POST", "/panel/api/clients/ips/{email}"), endpoints)
        self.assertIn(("POST", "/panel/api/clients/hwids/{email}"), endpoints)
        self.assertIn(("DELETE", "/panel/api/clients/hwids/{email}/{id}"), endpoints)

    async def test_xui_parses_bounded_connection_primitives(self):
        client = XUIClient("https://panel.example.invalid", "token")
        client._request = AsyncMock(side_effect=[
            {"success": True, "obj": ["203.0.113.10 (1735000000000)"]},
            {"success": True, "obj": [
                {"id": 7, "deviceModel": "Pixel 9", "fingerprint": "abc123"},
                "unexpected",
            ]},
        ])
        self.assertEqual(
            await client.client_ips("user@example.test"),
            ["203.0.113.10 (1735000000000)"],
        )
        self.assertEqual(
            await client.client_hwids("user@example.test"),
            [{"id": 7, "deviceModel": "Pixel 9", "fingerprint": "abc123"}],
        )

    async def test_hwid_delete_uses_single_no_retry_mutation_request(self):
        client = XUIClient("https://panel.example.invalid", "token")
        client._mutation_request = AsyncMock(return_value={"success": True})
        await client.delete_client_hwid("user@example.test", 7)
        client._mutation_request.assert_awaited_once_with(
            "/panel/api/clients/hwids/user%40example.test/7",
            method="DELETE",
        )

    def test_connections_routes_have_expected_rbac(self):
        for callback in (
            "admin:u:connections:101",
            "admin:u:devices:101",
            "admin:u:device:101:7",
            "admin:u:ips:101",
        ):
            with self.subTest(callback=callback):
                self.assertEqual(required_role_for_callback(callback), "read_only")
        self.assertEqual(required_role_for_callback("admin:u:devdelask:101:7"), "support")
        self.assertEqual(required_role_for_callback("admin:u:devdel:101:7"), "support")

    def test_device_delete_is_two_step_and_uncertain_outcome_is_not_replayed(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        ask = source.split(
            '@advanced_users_router.callback_query(F.data.regexp(r"^admin:u:devdelask:\\d+:\\d+$"))',
            1,
        )[1].split(
            '@advanced_users_router.callback_query(F.data.regexp(r"^admin:u:devdel:\\d+:\\d+$"))',
            1,
        )[0]
        self.assertNotIn("delete_client_hwid", ask)
        run = source.split(
            '@advanced_users_router.callback_query(F.data.regexp(r"^admin:u:devdel:\\d+:\\d+$"))',
            1,
        )[1].split(
            '@advanced_users_router.callback_query(F.data.startswith("admin:u:ips:"))',
            1,
        )[0]
        self.assertEqual(run.count("delete_client_hwid"), 1)
        self.assertIn("Запрос не повторялся", run)
        self.assertIn("exc.uncertain", run)

    def test_ip_view_does_not_create_device_identity_or_audit_ip_values(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        view = source.split(
            '@advanced_users_router.callback_query(F.data.startswith("admin:u:ips:"))',
            1,
        )[1].split(
            '@advanced_users_router.callback_query(F.data.regexp(r"^admin:u:\\d+$"))',
            1,
        )[0]
        self.assertIn("IP/session не считается физическим устройством", view)
        self.assertNotIn("audit_from_call", view)


if __name__ == "__main__":
    unittest.main()
