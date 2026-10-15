from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from admin_privileges import required_role_for_callback
from flow_diagnostics import inspect_node_flow, _reality_inbound, _inbound_client_flow
from xui import XUIError


def ib(tag, node_id, flow, email="test@example.invalid", protocol="vless", stream=None):
    return {
        "id": 1, "tag": tag, "nodeId": node_id, "protocol": protocol,
        "streamSettings": stream or '{"network":"tcp","security":"reality"}',
        "settings": {"clients": [{"email": email, "flow": flow}]},
    }


class Rc11FlowDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.master = SimpleNamespace(inbound_get=AsyncMock())
        self.targets = (SimpleNamespace(node_id=7, panel_url="https://node.example.invalid",
                                        api_token="secret", verify_tls=True),)
        self.master.inbound_get.return_value = ib("tag-reality", 7, "xtls-rprx-vision")

    @staticmethod
    def node(flow, tag="tag-reality"):
        return SimpleNamespace(inbounds_list=AsyncMock(return_value=[ib(tag, None, flow)]))

    async def check_with(self, flow, target=True):
        node = self.node(flow)
        with patch("flow_diagnostics.XUIClient", return_value=node) as construct:
            got, omitted = await inspect_node_flow(self.master, self.targets if target else (), "test@example.invalid", [1])
        return got, omitted, construct, node

    async def test_matching_real_node_data(self):
        got, omitted, create, node = await self.check_with("xtls-rprx-vision")
        self.assertEqual([(x.node_id, x.state, x.master_flow, x.node_flow) for x in got],
                         [(7, "MATCH", "xtls-rprx-vision", "xtls-rprx-vision")])
        self.assertEqual(omitted, 0)
        create.assert_called_once_with("https://node.example.invalid", "secret", True)
        node.inbounds_list.assert_awaited_once()

    async def test_detects_actual_none_on_node(self):
        got, _, _, _ = await self.check_with("")
        self.assertEqual(got[0].state, "MISMATCH")
        self.assertEqual(got[0].node_flow, "")

    async def test_missing_direct_binding_unknown_never_queries_node(self):
        got, _, create, _ = await self.check_with("xtls-rprx-vision", target=False)
        self.assertEqual(got[0].state, "UNKNOWN")
        self.assertIn("node_id", got[0].reason)
        create.assert_not_called()

    async def test_non_flow_inbound_ignored(self):
        self.master.inbound_get.return_value = ib(
            "tag-ws", 7, "", stream='{"network":"ws","security":"tls"}')
        with patch("flow_diagnostics.XUIClient") as create:
            got, omitted = await inspect_node_flow(self.master, self.targets, "test@example.invalid", [1])
        self.assertEqual((got, omitted), ([], 0))
        create.assert_not_called()

    async def test_tag_mismatch_is_unknown_not_false_green(self):
        got, _, _, _ = await self.check_with("xtls-rprx-vision", target=True)
        node = self.node("xtls-rprx-vision", tag="different")
        with patch("flow_diagnostics.XUIClient", return_value=node):
            got, _ = await inspect_node_flow(self.master, self.targets, "test@example.invalid", [1])
        self.assertEqual(got[0].state, "UNKNOWN")

    async def test_direct_panel_unavailable_unknown(self):
        node = SimpleNamespace(inbounds_list=AsyncMock(side_effect=XUIError("offline")))
        with patch("flow_diagnostics.XUIClient", return_value=node):
            got, _ = await inspect_node_flow(self.master, self.targets, "test@example.invalid", [1])
        self.assertEqual(got[0].state, "UNKNOWN")
        self.assertIn("недоступен", got[0].reason)

    async def test_bad_settings_unknown(self):
        node = SimpleNamespace(inbounds_list=AsyncMock(return_value=[{
            "tag": "tag-reality", "settings": "{bad json"
        }]))
        with patch("flow_diagnostics.XUIClient", return_value=node):
            got, _ = await inspect_node_flow(self.master, self.targets, "test@example.invalid", [1])
        self.assertEqual(got[0].state, "UNKNOWN")

    async def test_master_reality_absence_is_unknown(self):
        self.master.inbound_get.return_value = ib("tag-reality", 7, "xtls-rprx-vision", email="other@example.invalid")
        with patch("flow_diagnostics.XUIClient") as node:
            got, _ = await inspect_node_flow(self.master, self.targets, "test@example.invalid", [1])
        self.assertEqual(got[0].state, "UNKNOWN")
        node.assert_not_called()

    def test_role_catalog(self):
        self.assertEqual(required_role_for_callback("admin:u:flowcheck:123"), "read_only")
        self.assertIsNone(required_role_for_callback("admin:u:flowcheck:abc"))


if __name__ == "__main__":
    unittest.main()
