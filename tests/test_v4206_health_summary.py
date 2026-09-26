"""Regression coverage for the v4.20.6 health-summary release."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class V4206HealthSummaryTests(unittest.TestCase):
    def test_health_summary_release_contract_is_present(self):
        system = source("system_admin.py")
        node_ui = source("node_ui.py")

        for needle in (
            "node_list_status(node)",
            "_panel_status_line(node)",
            "xray_state_icon(node.xray_state)",
            "xray_state_text(node.xray_state)",
            "node.xray_version",
            "🧮 CPU:",
            "🧠 RAM:",
            "⏱ Время работы:",
            "🌐 Inbounds:",
            "👥 Клиентов:",
            "📶 Задержка API:",
        ):
            self.assertIn(needle, system)

        self.assertIn('return "🛠 Панель: обслуживание"', system)
        self.assertIn('def xray_state_icon(state: str)', node_ui)
        self.assertIn('return "🟡"', node_ui)

    def test_health_summary_does_not_add_direct_node_fetches(self):
        system = source("system_admin.py")
        helper = system.split("def _node_health_lines", 1)[1].split(
            "async def _guard",
            1,
        )[0]
        self.assertNotIn("await ", helper)
        self.assertNotIn("xui.", helper)


if __name__ == "__main__":
    unittest.main()
