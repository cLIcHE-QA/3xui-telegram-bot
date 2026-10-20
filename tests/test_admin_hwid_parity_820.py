"""#820: admin list shares safe HWID presentation without importing live runtime."""
from __future__ import annotations

import unittest
from pathlib import Path

from device_presentation import device_emoji, display_os

ROOT = Path(__file__).resolve().parents[1]


class AdminHwidParityTests(unittest.TestCase):
    def test_shared_os_and_icon_fixtures(self):
        cases = (
            ("macOS (Designed for iPad)", "iPad Pro (12.9-inch) (3rd generation)", "26.7", "💻", "macOS (Designed for iPad) 26.7"),
            ("iPadOS", "iPad Pro", "18", "📱", "iPadOS 18"),
            ("Windows", "Desktop", "11", "🖥️", "Windows 11"),
            ("", "Unknown", "", "🔹", "ОС неизвестна"),
        )
        for os_name, model, version, emoji, platform in cases:
            with self.subTest(model=model, os=os_name):
                self.assertEqual(device_emoji(os_name, model), emoji)
                self.assertEqual(display_os(os_name, version), platform)

    def test_admin_list_uses_same_read_only_presentation(self):
        src = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        list_view = src.split("async def _user_devices_view", 1)[1].split("async def _find_user_device", 1)[0]
        self.assertIn("from device_presentation import device_emoji, display_os", src)
        self.assertIn("icon = device_emoji(os_name, title)", list_view)
        self.assertIn("platform = display_os(os_name, os_version)", list_view)
        self.assertIn('f"{index}. {icon} {title} · {platform} · {last_seen}"', list_view)
        self.assertIn('text=f"{icon} {index}. {title}"[:60]', list_view)
        self.assertNotIn("Fingerprint:", list_view)
        self.assertIn('callback_data=f"admin:u:device:{tg_id}:{device_id}"', list_view)
        self.assertIn('callback_data=f"admin:u:connections:{tg_id}"', list_view)
        self.assertIn("devices[:30]", list_view)

    def test_admin_detail_contract_remains_untouched(self):
        src = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        detail = src.split("async def user_device_detail(", 1)[1].split('F.data.regexp(r"^admin:u:devdelask:', 1)[0]
        self.assertIn('f"User-Agent: {user_agent}\\n"', detail)
        self.assertIn('f"Fingerprint: {fingerprint}\\n"', detail)
        self.assertIn('text="🗑 Удалить устройство"', detail)
        self.assertIn('text="⬅ Устройства"', detail)


if __name__ == "__main__":
    unittest.main()
