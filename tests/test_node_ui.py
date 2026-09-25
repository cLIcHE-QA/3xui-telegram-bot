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
        self.assertEqual(node_ui.node_status_text("online"), "в сети")
        self.assertEqual(node_ui.node_status_text("offline"), "не в сети")
        self.assertEqual(node_ui.xray_state_text("running"), "работает")
        self.assertEqual(node_ui.xray_state_text("stopped"), "остановлен")
        self.assertEqual(node_ui.tls_verify_mode_text("verify"), "проверять")
        self.assertEqual(node_ui.tls_verify_mode_text("skip"), "без проверки")
        self.assertEqual(node_ui.inbound_sync_mode_text("all"), "все inbound'ы")

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

    def test_node_action_labels_are_localized(self):
        master_labels = {
            button.callback_data: button.text
            for row in node_ui.master_detail_keyboard().inline_keyboard
            for button in row
            if button.callback_data
        }
        node_labels = {
            button.callback_data: button.text
            for row in node_ui.node_detail_keyboard(2).inline_keyboard
            for button in row
            if button.callback_data
        }
        self.assertEqual(master_labels["admin:hostctl:m"], "🧩 Управление 3x-ui")
        self.assertEqual(master_labels["admin:ver:panel:m"], "⬆️ Обновления 3x-ui")
        self.assertEqual(node_labels["admin:nodectl:2:maintenance"], "🛠 Включить обслуживание")
        self.assertEqual(node_labels["admin:node:2:readiness"], "🧭 Готовность")
        self.assertEqual(node_labels["admin:nodectl:2:deleteask"], "🗑 Удалить ноду")

    def test_node_detail_callbacks_are_stable(self):
        self.assertIn("admin:hostctl:m", callback_values(node_ui.master_detail_keyboard()))
        node_callbacks = callback_values(node_ui.node_detail_keyboard(2))
        self.assertIn("admin:hostctl:n2", node_callbacks)
        self.assertIn("admin:ver:panel:n2", node_callbacks)
        self.assertIn("admin:ver:xray:n2:0", node_callbacks)
        self.assertIn("admin:node:2:readiness", node_callbacks)


    def test_nodes_menu_uses_injected_master_identity(self):
        node = SimpleNamespace(
            enable=True,
            status="online",
            name="Finland",
            transitive=False,
            id=2,
        )
        markup = node_ui.nodes_menu(
            [node],
            True,
            master_flag="🇫🇮",
            master_name="Master",
        )
        self.assertEqual(markup.inline_keyboard[0][0].text, "🇫🇮 Master · 🟢 В сети")
        self.assertIn("admin:node:2", callback_values(markup))
        self.assertIn("admin:nodeadd:start", callback_values(markup))

    def test_node_detail_text_uses_injected_backup_state(self):
        node = SimpleNamespace(
            enable=True,
            status="online",
            xray_state="running",
            xray_version="25.9.5",
            scheme="https",
            address="fi.example.invalid",
            port=2053,
            base_path="/base/",
            name="Finland",
            panel_version="3.8.5",
            tls_verify_mode="verify",
            inbound_sync_mode="all",
            outbound_tag="",
            latency_ms=42,
            net_up=1024,
            net_down=2048,
            cpu_pct=12.5,
            mem_pct=34.5,
            uptime_secs=90061,
            inbound_count=3,
            client_count=4,
            active_count=3,
            online_count=2,
            last_heartbeat=0,
            config_dirty=False,
            last_error="",
            xray_error="",
            transitive=False,
        )
        configured = node_ui.node_detail_text(node, backup_configured=True)
        missing = node_ui.node_detail_text(node, backup_configured=False)
        self.assertIn("🌍 🇫🇮 Finland", configured)
        self.assertIn("🟢 Панель: в сети", configured)
        self.assertIn("🔗 Адрес: https://fi.example.invalid:2053/base/", configured)
        self.assertIn("🔐 Проверка TLS: проверять · синхронизация inbound'ов: все inbound'ы", configured)
        self.assertIn("📶 Задержка API: 42 ms", configured)
        self.assertIn("📊 Сеть: ↑ 1.0 KB/s · ↓ 2.0 KB/s", configured)
        self.assertIn("🕒 Последний сигнал: никогда", configured)
        self.assertIn("⏱ Время работы: 1д 1ч 1м", configured)
        self.assertIn("💾 Резервная копия БД: настроена", configured)
        self.assertIn("💾 Резервная копия БД: не настроена", missing)

if __name__ == "__main__":
    unittest.main()
