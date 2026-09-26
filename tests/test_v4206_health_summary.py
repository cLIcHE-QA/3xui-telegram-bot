"""Regression coverage for the v4.20.6 health-summary patch."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

import system_admin
from version import APP_VERSION


class V4206HealthSummaryTests(unittest.TestCase):
    def test_release_version_is_4206(self):
        self.assertEqual(APP_VERSION, "4.20.6")

    def test_direct_node_health_summary_is_explicit(self):
        node = SimpleNamespace(
            id=1,
            name="Finland",
            enable=True,
            status="online",
            xray_state="running",
            xray_version="26.9.9",
            cpu_pct=8.0,
            mem_pct=27.0,
            uptime_secs=3600,
            inbound_count=3,
            client_count=24,
            online_count=7,
            latency_ms=42,
        )
        lines = system_admin._node_health_lines(node)
        self.assertEqual(lines[0], "🇫🇮 Finland · 🟢 В сети")
        self.assertIn("🟢 Панель: в сети", lines)
        self.assertIn("🟢 Xray: работает 26.9.9", lines)
        self.assertIn("🧮 CPU: 8.0%", lines)
        self.assertIn("🧠 RAM: 27.0%", lines)
        self.assertIn("🌐 Inbound'ы: 3", lines)
        self.assertIn("📶 Задержка API: 42 ms", lines)

    def test_unknown_xray_is_not_rendered_as_failure(self):
        node = SimpleNamespace(
            id=1,
            name="Finland",
            enable=True,
            status="online",
            xray_state="unknown",
            xray_version="",
            cpu_pct=0.0,
            mem_pct=0.0,
            uptime_secs=0,
            inbound_count=0,
            client_count=0,
            online_count=0,
            latency_ms=0,
        )
        lines = system_admin._node_health_lines(node)
        self.assertIn("🟡 Xray: неизвестно", lines)


if __name__ == "__main__":
    unittest.main()
