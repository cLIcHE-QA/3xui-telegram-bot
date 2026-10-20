from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from customer_provider_xui import XuiCustomerProvider
from device_presentation import device_emoji, display_os, recognized_vpn_app
from client_access import _device_list_view


class HwidPresentation814Tests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_version_and_ui(self):
        provider = XuiCustomerProvider(SimpleNamespace(
            client_hwids=AsyncMock(return_value=[
                {"id": 7, "deviceModel": "Pixel 9", "deviceOs": "Android", "osVersion": "15", "userAgent": "Happ/1.0"},
                {"id": 8, "deviceModel": "ThinkPad", "deviceOs": "Windows", "osVersion": "11", "userAgent": "Incy/1.2"},
            ]),
            get_client=AsyncMock(return_value={"client": {"email": "example.invalid", "limitHwid": 5}}),
        ))
        result = await provider.devices("example.invalid")
        self.assertEqual([x.os_version for x in result.devices], ["15", "11"])
        self.assertEqual([x.app_name for x in result.devices], ["Happ", "Incy"])
        label, buttons = _device_list_view(result, 0)
        self.assertIn("📱 Pixel 9 · Android 15", label)
        self.assertIn("💻 ThinkPad · Windows 11", label)
        self.assertIn("📱 Pixel 9", str(buttons))
        self.assertIn("💻 ThinkPad", str(buttons))
        self.assertNotIn("Happ", label)
        self.assertNotIn("Incy", str(buttons))

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

    async def test_untrusted_user_agent_is_hidden(self):
        for raw in ("", None, 42, "<b>Happ</b>", "Happ/1.0 secret", "Other/1.0 Happ/3", "NotIncy", "Happily", "Incy/1.0; OS", "Happ/" + "1" * 150, "Happ\\n1", "Happ\\u200b", "Shadowrocketly/3445", "Shadowrocket/1 <secret>"):
            with self.subTest(raw=raw):
                provider = XuiCustomerProvider(SimpleNamespace(
                    client_hwids=AsyncMock(return_value=[{"id": 1, "deviceModel": "Pixel", "deviceOs": "Android", "userAgent": raw}]),
                    get_client=AsyncMock(return_value={"client": {"email": "example.invalid"}}),
                ))
                inventory = await provider.devices("example.invalid")
                self.assertEqual(inventory.devices[0].app_name, "")
                label, buttons = _device_list_view(inventory, 0)
                self.assertNotIn("Приложение:", label)
                self.assertNotIn("Happ/", str(buttons))

    def test_allowlisted_user_agents(self):
        for raw, expected in [("Happ", "Happ"), ("hApp/1.0", "Happ"), ("INCY/1.2", "Incy"), ("Incy", "Incy")]:
            with self.subTest(raw=raw):
                self.assertEqual(recognized_vpn_app(raw), expected)

    def test_real_world_user_agents(self):
        cases = (
            ("Shadowrocket/3445 CFNetwork/3860.600.12 Darwin/25.5.0 iPhone18,1", "Shadowrocket"),
            ("INCY/2.6.4/macos CFNetwork/3860.700.1 Darwin/25.6.0", "Incy"),
            ("Happ/6.1.0/ios/2610091516618", "Happ"),
            ("UnknownVPN/2.3", ""),
            ("Happ/6.1.0/ios/2610091516618 <token>", ""),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(recognized_vpn_app(raw), expected)

    def test_macos_on_ipad_form_factor_is_mac(self):
        self.assertEqual(device_emoji("macOS (Designed for iPad)", "iPad Pro (12.9-inch) (3rd generation)"), "💻")
        self.assertEqual(device_emoji("iPadOS", "iPad Pro"), "📱")
        self.assertEqual(device_emoji("macOS", "iMac"), "🖥️")

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
