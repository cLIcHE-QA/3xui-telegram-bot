from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from customer_provider_xui import XuiCustomerProvider
from device_presentation import device_emoji, display_os
from client_access import _device_list_view


class HwidPresentation814Tests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_version_and_ui(self):
        provider = XuiCustomerProvider(SimpleNamespace(
            client_hwids=AsyncMock(return_value=[
                {"id": 7, "deviceModel": "Pixel 9", "deviceOs": "Android", "osVersion": "15"},
                {"id": 8, "deviceModel": "ThinkPad", "deviceOs": "Windows", "osVersion": "11"},
            ]),
            get_client=AsyncMock(return_value={"client": {"email": "example.invalid", "limitHwid": 5}}),
        ))
        result = await provider.devices("example.invalid")
        self.assertEqual([x.os_version for x in result.devices], ["15", "11"])
        label, buttons = _device_list_view(result, 0)
        self.assertIn("📱 Pixel 9 · Android 15", label)
        self.assertIn("💻 ThinkPad · Windows 11", label)
        self.assertIn("📱 Pixel 9", str(buttons))
        self.assertIn("💻 ThinkPad", str(buttons))

    async def test_untrusted_version_is_ignored(self):
        for raw in ("<b>15</b>", "a" * 60, "https://example.invalid/secret", "f" * 32, 17, None):
            with self.subTest(raw=raw):
                provider = XuiCustomerProvider(SimpleNamespace(
                    client_hwids=AsyncMock(return_value=[{"id": 1, "deviceOs": "Android", "osVersion": raw}]),
                    get_client=AsyncMock(return_value={"client": {"email": "example.invalid"}}),
                ))
                result = await provider.devices("example.invalid")
                self.assertEqual(result.devices[0].os_version, "")
                self.assertEqual(display_os(result.devices[0].os_name, result.devices[0].os_version), "Android")

    def test_version_not_guessed_and_not_duplicated(self):
        self.assertEqual(display_os("Android", ""), "Android")
        self.assertEqual(display_os("", "15"), "ОС неизвестна")
        self.assertEqual(display_os("macOS 14.5", "14.5"), "macOS 14.5")
        self.assertEqual(display_os("Windows", "11"), "Windows 11")

    def test_icons_no_guess_for_unknown(self):
        for os, model, expected in [
            ("android", "Pixel 9", "📱"), ("iOS", "iPhone", "📱"),
            ("iPadOS", "iPad", "📱"), ("Windows", "ThinkPad", "💻"),
            ("macOS", "MacBook Pro", "💻"), ("macOS", "iMac", "🖥️"),
            ("Linux", "Desktop", "🖥️"), ("Solaris", "Unknown", "🔹"),
            ("", "Unknown", "🔹"),
        ]:
            with self.subTest(os=os, model=model):
                self.assertEqual(device_emoji(os, model), expected)


if __name__ == "__main__":
    unittest.main()
