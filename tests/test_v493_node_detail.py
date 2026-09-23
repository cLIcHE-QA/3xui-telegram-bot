"""v4.9.3 regression tests for node detail derived counters."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from xui import XUIClient, XUIError


class V493NodeDetailTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = XUIClient(
            "https://panel.example.invalid/base",
            "offline-test-token",
            verify_tls=True,
        )

    async def test_node_get_enriched_prefers_list_derived_counters(self):
        list_payload = {
            "success": True,
            "obj": [{
                "id": 7,
                "name": "Finland",
                "address": "fi.example.invalid",
                "port": 443,
                "basePath": "/panel/",
                "scheme": "https",
                "enable": True,
                "status": "online",
                "cpuPct": 33,
                "memPct": 49,
                "uptimeSecs": 100,
                "latencyMs": 38,
                "inboundCount": 4,
                "clientCount": 12,
                "activeCount": 11,
                "onlineCount": 1,
                "depletedCount": 0,
                "disabledCount": 1,
                "panelVersion": "3.8.5",
                "xrayState": "running",
                "xrayVersion": "26.7.28",
                "lastHeartbeat": 1234567890,
                "lastError": "",
                "configDirty": False,
                "transitive": False,
                "hasApiToken": True,
                "tlsVerifyMode": "verify",
                "inboundSyncMode": "all",
                "outboundTag": "",
                "allowPrivateAddress": False,
                "netUp": 1000,
                "netDown": 2000,
            }],
        }

        async def fake_request(method, path, **kwargs):
            self.assertEqual((method, path), ("GET", "/panel/api/nodes/list"))
            return list_payload

        with patch.object(self.client, "_request", side_effect=fake_request) as request:
            node = await self.client.node_get_enriched(7)

        self.assertEqual(node.id, 7)
        self.assertEqual(node.inbound_count, 4)
        self.assertEqual(node.client_count, 12)
        self.assertEqual(node.active_count, 11)
        self.assertEqual(node.online_count, 1)
        self.assertEqual(request.await_count, 1)

    async def test_node_get_enriched_falls_back_when_list_has_no_node(self):
        with (
            patch.object(self.client, "nodes_list", new=AsyncMock(return_value=[])),
            patch.object(self.client, "node_get", new=AsyncMock()) as detail,
        ):
            detail.return_value = self.client._parse_node({
                "id": 7,
                "name": "Finland",
                "status": "online",
                "enable": True,
            })
            node = await self.client.node_get_enriched(7)

        self.assertEqual(node.id, 7)
        detail.assert_awaited_once_with(7)

    async def test_node_get_enriched_falls_back_when_list_api_fails(self):
        with (
            patch.object(self.client, "nodes_list", new=AsyncMock(side_effect=XUIError("list failed"))),
            patch.object(self.client, "node_get", new=AsyncMock()) as detail,
        ):
            detail.return_value = self.client._parse_node({
                "id": 7,
                "name": "Finland",
                "status": "online",
                "enable": True,
            })
            node = await self.client.node_get_enriched(7)

        self.assertEqual(node.name, "Finland")
        detail.assert_awaited_once_with(7)


if __name__ == "__main__":
    unittest.main()
