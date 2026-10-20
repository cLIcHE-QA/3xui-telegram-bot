"""Read-only admin/customer HWID visual parity; no mutations or navigation rewrites."""
from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from device_presentation import device_emoji, display_os
from advanced_users import _user_devices_view

ROOT = Path(__file__).resolve().parents[1]


class AdminHwidParityTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_list_matches_customer_icon_platform_date_without_fingerprint(self):
        rows = [
            {"id": 7, "deviceModel": "iPad Pro (12.9-inch) (3rd generation)", "deviceOs": "macOS (Designed for iPad)", "osVersion": "26.7", "fingerprint": "secret-fingerprint", "lastSeen": 1792534080000},
            {"id": 8, "deviceModel": "iPhone", "deviceOs": "iOS", "osVersion": "26", "lastSeen": 1792534080000},
            {"id": 9, "deviceModel": "Desktop", "deviceOs": "Windows", "osVersion": "11", "lastSeen": 1792534080000},
        ]
        rec = SimpleNamespace(email="user@example.invalid", telegram_id=123)
        with patch("advanced_users.db.get", new=AsyncMock(return_value=rec)), patch(
            "advanced_users.xui.client_hwids", new=AsyncMock(return_value=rows)
        ), patch("advanced_users._display_label", new=AsyncMock(return_value="pilot")):
            text, markup = await _user_devices_view(123, "read_only")
        self.assertIn("1. 💻 iPad Pro (12.9-inch) (3rd generation) · macOS (Designed for iPad) 26.7 ·", text)
        self.assertIn("2. 📱 iPhone · iOS 26 ·", text)
        self.assertIn("3. 🖥️ Desktop · Windows 11 ·", text)
        self.assertNotIn("Fingerprint:", text)
        self.assertNotIn("secret-fingerprint", text)
        self.assertEqual(markup.inline_keyboard[0][0].text.startswith("💻 1."), True)
        self.assertTrue(markup.inline_keyboard[1][0].text.startswith("📱 2."))
        self.assertTrue(markup.inline_keyboard[2][0].text.startswith("🖥️ 3."))
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "admin:u:device:123:7")
        self.assertEqual(markup.inline_keyboard[-1][0].callback_data, "admin:u:connections:123")

    def test_shared_presentation_source_and_admin_detail_untouched(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        self.assertIn("from device_presentation import device_emoji, display_os", source)
        self.assertIn("f\"{index}. {icon} {title} · {platform} · {last_seen}\"", source)
        self.assertEqual(device_emoji("macOS (Designed for iPad)", "iPad Pro"), "💻")
        self.assertEqual(display_os("macOS (Designed for iPad)", "26.7"), "macOS (Designed for iPad) 26.7")
        self.assertIn('f"User-Agent: {user_agent}\\n"', source)
        self.assertIn('f"Fingerprint: {fingerprint}\\n"', source)


if __name__ == "__main__":
    unittest.main()
