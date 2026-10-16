"""Presentation-only Flow regression tests for #691."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from pathlib import Path

from flow_ui_view import (
    _views, clean_label, node_label, inbound_label, load_node_names,
    store_flow_view, last_flow_view, FLOW_VIEW_CAP,
)

ROOT = Path(__file__).resolve().parents[1]


class FlowUiViewsTests(unittest.TestCase):
    def setUp(self):
        _views.clear()

    def test_shared_vs_scoped_flow_in_source(self):
        source = (ROOT / "advanced_users.py").read_text()
        self.assertIn('Общий Flow клиента (не Flow конкретного Inbound)', source)
        self.assertIn('Общий Flow клиента (не Flow Inbound)', source)
        self.assertNotIn('f"🖥 Flow Master: {flow}"', source)

    def test_read_back_only_historical_then_expired(self):
        self.assertIn("не проверено", last_flow_view(42, now=100))
        store_flow_view(42, "#1: MATCH / #2: MISMATCH", now=100)
        self.assertIn("последняя проверка, не live", last_flow_view(42, now=101))
        self.assertIn("MISMATCH", last_flow_view(42, now=101))
        self.assertIn("не проверено", last_flow_view(42, now=281))

    def test_user_isolation_and_bounded_entries(self):
        store_flow_view(42, "#1: MATCH", now=10)
        self.assertIn("не проверено", last_flow_view(43, now=10))
        for i in range(1000, 1300):
            store_flow_view(i, "UNKNOWN", now=10)
        self.assertLessEqual(len(_views), FLOW_VIEW_CAP)
        self.assertIn("не проверено", last_flow_view(42, now=10))

    def test_labels_use_only_display_data_with_stable_ids(self):
        self.assertEqual(node_label(7, {7: "Finland"}), "🌐 Finland (#7)")
        self.assertEqual(node_label(7, {7: "  "}), "🌐 Node #7")
        self.assertEqual(node_label(8, {7: "Finland"}), "🌐 Node #8")
        self.assertEqual(inbound_label(5, "VLESS Reality"), "VLESS Reality (#5)")
        self.assertEqual(inbound_label(5, ""), "Inbound #5")
        self.assertEqual(node_label(0, {0: "Other"}), "🖥 Master")
        self.assertNotIn("\n", clean_label("a\nb", "missing"))
        self.assertNotIn("\u202e", clean_label("a\u202eb", "missing"))

    def test_editor_uses_stable_id_not_label_as_callback(self):
        source = (ROOT / "flow_edit_routes.py").read_text()
        self.assertIn('f"admin:u:flowib:{tg_id}:{i}"', source)
        self.assertIn('f"admin:u:flowval:{tg_id}:{node_id}:{t.inbound_id}"', source)
        self.assertIn('inbound_label(iid, target.remark)', source)
        self.assertNotIn("update_client_inbound_flow(rec.email, challenge.inbound_id, challenge.new_flow, client=snap.client, wg_verified=snap.wg_verified, remark=", source)


class NodeNamesTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_only_name_lookup(self):
        obj = SimpleNamespace(nodes_list=AsyncMock(return_value=[
            SimpleNamespace(id=7, name="Finland"),
            SimpleNamespace(id=8, name="Netherlands"),
            SimpleNamespace(id=8, name="Duplicate"),
        ]))
        names = await load_node_names(obj)
        self.assertEqual(names, {7: "Finland", 8: "Netherlands"})
        obj.nodes_list.assert_awaited_once()

    async def test_missing_master_names_not_authoritative(self):
        obj = SimpleNamespace(nodes_list=AsyncMock(side_effect=RuntimeError("unavailable")))
        self.assertEqual(await load_node_names(obj), {})


if __name__ == "__main__":
    unittest.main()
