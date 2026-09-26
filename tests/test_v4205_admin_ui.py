"""Regression coverage for the v4.20.5 Admin UI consistency patch."""
from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from node_ui import nodes_menu
ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def labels_by_callback(markup) -> dict[str, str]:
    return {
        button.callback_data: button.text
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    }


class V4205AdminUiTests(unittest.TestCase):
    def test_fleet_health_uses_shared_node_display_name(self):
        fleet = source("fleet_operations.py")
        health = fleet.split(
            '@fleet_router.callback_query(F.data == "admin:fleet:health")',
            1,
        )[1].split(
            "async def _selection_data",
            1,
        )[0]
        self.assertIn(
            "node_display_name(str(item['name']))",
            health,
        )
        self.assertNotIn(
            "{item['name']} · {_health_state_text",
            health,
        )

    def test_nodes_menu_uses_symmetric_status_grammar(self):
        cases = (
            (True, "online", "🇫🇮 Finland · 🟢 В сети"),
            (True, "offline", "🇫🇮 Finland · 🔴 Не в сети"),
            (True, "unknown", "🇫🇮 Finland · 🟡 Неизвестно"),
            (False, "offline", "🇫🇮 Finland · 🛠 Обслуживание"),
        )
        for enabled, status, expected in cases:
            with self.subTest(enabled=enabled, status=status):
                node = SimpleNamespace(
                    id=1,
                    name="Finland",
                    enable=enabled,
                    status=status,
                    transitive=False,
                )
                labels = labels_by_callback(
                    nodes_menu(
                        [node],
                        master_online=True,
                        master_flag="🖥",
                        master_name="Master",
                    )
                )
                self.assertEqual(
                    labels["admin:master"],
                    "🖥 Master · 🟢 В сети",
                )
                self.assertEqual(labels["admin:node:1"], expected)

    def test_dashboard_is_child_screen_with_local_navigation(self):
        shell = source("admin_shell.py")
        dashboard = shell.split(
            '@admin_shell_router.callback_query(F.data == "admin:dashboard")',
            1,
        )[1].split(
            '@admin_shell_router.callback_query(F.data == "admin:subscriptions")',
            1,
        )[0]
        self.assertIn("reply_markup=dashboard_menu()", dashboard)
        self.assertNotIn("reply_markup=admin_menu()", dashboard)

        home = shell.split(
            '@admin_shell_router.callback_query(F.data == "admin:home")',
            1,
        )[1]
        self.assertIn("reply_markup=admin_menu()", home)


if __name__ == "__main__":
    unittest.main()
