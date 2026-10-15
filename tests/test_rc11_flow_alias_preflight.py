"""Regression: safe node-scoped aliases and non-sensitive preflight diagnostics."""
from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from flow_diagnostics import _node_tag_matches, inspect_node_flow
from flow_edit import FlowEditRejected, preflight_reason


def inbound(tag, flow="xtls-rprx-vision", *, node_id=1):
    return {
        "id": 42, "nodeId": node_id, "tag": tag, "protocol": "vless",
        "streamSettings": '{"security":"reality","network":"tcp"}',
        "settings": {"clients": [{"email": "qa@example.invalid", "flow": flow}]},
    }


class NodeTagAliasTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.master = SimpleNamespace(inbound_get=AsyncMock(return_value=inbound("n1-vless", node_id=1)))
        self.targets = (SimpleNamespace(
            node_id=1, panel_url="https://node.example.invalid",
            api_token="fixture-token", verify_tls=True,
        ),)

    async def check(self, node_rows, *, master_tag="n1-vless"):
        self.master.inbound_get.return_value = inbound(master_tag, node_id=1)
        node = SimpleNamespace(inbounds_list=AsyncMock(return_value=node_rows))
        with patch("flow_diagnostics.XUIClient", return_value=node):
            result, omitted = await inspect_node_flow(
                self.master, self.targets, "qa@example.invalid", [42]
            )
        self.assertEqual(omitted, 0)
        node.inbounds_list.assert_awaited_once()
        return result[0]

    async def test_bare_node_prefixed_master_matches(self):
        got = await self.check([inbound("vless")])
        self.assertEqual((got.state, got.node_flow), ("MATCH", "xtls-rprx-vision"))

    async def test_prefixed_node_bare_master_matches(self):
        got = await self.check([inbound("n1-vless")], master_tag="vless")
        self.assertEqual(got.state, "MATCH")

    async def test_exact_tag_preserved(self):
        got = await self.check([inbound("n1-vless")])
        self.assertEqual(got.state, "MATCH")

    async def test_alias_detects_real_mismatch(self):
        got = await self.check([inbound("vless", "")])
        self.assertEqual((got.state, got.node_flow), ("MISMATCH", ""))

    async def test_two_tag_forms_are_ambiguous(self):
        got = await self.check([inbound("vless"), inbound("n1-vless")])
        self.assertEqual((got.state, got.node_flow), ("UNKNOWN", None))

    async def test_wrong_node_prefix_not_matched(self):
        got = await self.check([inbound("n2-vless")])
        self.assertEqual(got.state, "UNKNOWN")

    async def test_unrelated_tag_remains_unknown(self):
        got = await self.check([inbound("other")])
        self.assertEqual(got.state, "UNKNOWN")

    async def test_duplicate_aliases_unknown(self):
        got = await self.check([inbound("vless"), inbound("vless")])
        self.assertEqual(got.state, "UNKNOWN")

    async def test_missing_client_unknown(self):
        got = await self.check([inbound("vless", "") | {"settings": {"clients": []}}])
        self.assertEqual(got.state, "UNKNOWN")

    async def test_non_reality_not_queried(self):
        data = inbound("n1-vless")
        data["streamSettings"] = '{"security":"tls","network":"ws"}'
        self.master.inbound_get.return_value = data
        with patch("flow_diagnostics.XUIClient") as node:
            got, omitted = await inspect_node_flow(self.master, self.targets, "qa@example.invalid", [42])
        self.assertEqual((got, omitted), ([], 0))
        node.assert_not_called()

    def test_node_identity_not_fuzzy(self):
        self.assertEqual(_node_tag_matches([inbound("vless")], 2, "n1-vless"), [])
        self.assertEqual(_node_tag_matches([inbound("vless")], 0, "n1-vless"), [])
        self.assertEqual(_node_tag_matches([inbound("vless")], 1, ""), [])


class PreflightCodeTests(unittest.TestCase):
    def test_categories_are_fixed_and_safe(self):
        self.assertEqual(preflight_reason(FlowEditRejected("Неоднозначный tag")), "INBOUND_TAG")
        self.assertEqual(preflight_reason(FlowEditRejected("Неполный общий record")), "CLIENT_RECORD")
        self.assertEqual(preflight_reason(FlowEditRejected("Привязка клиента отсутствует или неоднозначна")), "INBOUND_CLIENT")
        self.assertEqual(preflight_reason(FlowEditRejected("Inbound origin ноды не определён")), "NODE_IDENTITY")
        self.assertEqual(preflight_reason(asyncio.TimeoutError()), "UPSTREAM_TIMEOUT")

    def test_unknown_upstream_error_never_leaks_details(self):
        secret = "secret-fixture-do-not-show"
        self.assertEqual(preflight_reason(ValueError(secret)), "MASTER_API_UNAVAILABLE")
        self.assertEqual(preflight_reason(FlowEditRejected(secret)), "MASTER_VALIDATION")
        self.assertNotIn(secret, preflight_reason(RuntimeError(secret)))


if __name__ == "__main__":
    unittest.main()
