from __future__ import annotations

import unittest
from types import SimpleNamespace

import node_ui


def callback_values(markup) -> set[str]:
    return {
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    }


class NodeUiTests(unittest.TestCase):
    def test_node_status_icons(self):
        self.assertEqual(node_ui.node_status_icon(SimpleNamespace(enable=False, status="offline")), "⚪")
        self.assertEqual(node_ui.node_status_icon(SimpleNamespace(enable=True, status="online")), "🟢")
        self.assertEqual(node_ui.node_status_icon(SimpleNamespace(enable=True, status="offline")), "🔴")
        self.assertEqual(node_ui.node_status_icon(SimpleNamespace(enable=True, status="unknown")), "🟡")

    def test_xray_icons(self):
        self.assertEqual(node_ui.xray_icon(SimpleNamespace(xray_state="running")), "🟢")
        self.assertEqual(node_ui.xray_icon(SimpleNamespace(xray_state="failed")), "🔴")
        self.assertEqual(node_ui.xray_icon(SimpleNamespace(xray_state="unknown")), "🟡")

    def test_formatters_are_stable(self):
        self.assertEqual(node_ui.duration_text(0), "0ч 0м")
        self.assertEqual(node_ui.duration_text(90061), "1д 1ч 1м")
        self.assertEqual(node_ui.epoch_text(0), "никогда")
        self.assertEqual(node_ui.node_display_name("Finland"), "🇫🇮 Finland")
        self.assertEqual(node_ui.node_display_name("🇩🇪 Germany"), "🇩🇪 Germany")
        self.assertEqual(node_ui.node_display_name("Custom"), "Custom")

    def test_add_node_callbacks_are_stable(self):
        self.assertEqual(
            callback_values(node_ui.add_node_tls_keyboard()),
            {"admin:nodeadd:tls:verify", "admin:nodeadd:tls:skip", "admin:nodeadd:cancel"},
        )
        self.assertIn("admin:nodeadd:save", callback_values(node_ui.add_node_review_keyboard("verify")))
        self.assertIn("admin:nodeadd:test", callback_values(node_ui.add_node_retry_keyboard("verify")))

    def test_node_detail_callbacks_are_stable(self):
        self.assertIn("admin:hostctl:m", callback_values(node_ui.master_detail_keyboard()))
        node_callbacks = callback_values(node_ui.node_detail_keyboard(2))
        self.assertIn("admin:hostctl:n2", node_callbacks)
        self.assertIn("admin:ver:panel:n2", node_callbacks)
        self.assertIn("admin:ver:xray:n2:0", node_callbacks)
        self.assertIn("admin:node:2:readiness", node_callbacks)


if __name__ == "__main__":
    unittest.main()
