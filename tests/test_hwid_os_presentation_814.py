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
        self.assertEqual(recognized_vpn_app("Unknown/2.4"), "Unknown")
        # The detail field renders a stable unknown label, not raw upstream metadata.
        source = __import__("pathlib").Path("client_access.py").read_text(encoding="utf-8")
        self.assertIn("VPN-клиент: {device.app_name or 'Не определён'}", source)
        back = source.split("def _device_back_menu", 1)[1].split("async def _guard_device_callback", 1)[0]
        self.assertNotIn("client:home", back)
        label, buttons = _device_list_view(result, 0)
        self.assertIn("📱 Pixel 9 · Android 15", label)
        self.assertIn("💻 ThinkPad · Windows 11", label)
        self.assertIn("📱 Pixel 9", str(buttons))
        self.assertIn("💻 ThinkPad", str(buttons))
        self.assertNotIn("Happ", label)
        self.assertNotIn("Incy", str(buttons))

    async def test_split_windows_os_is_shared_with_client_inventory(self):
        provider = XuiCustomerProvider(SimpleNamespace(
            client_hwids=AsyncMock(return_value=[{
                "id": 7, "deviceModel": "DESKTOP-TEST1234_x86_64",
                "deviceOs": "Windows", "osVersion": "10_10.0.19045",
                "userAgent": "Happ/4.5.4/Windows/2610141139502",
            }]),
            get_client=AsyncMock(return_value={"client": {
                "email": "example.invalid", "limitHwid": 5,
            }}),
        ))
        inventory = await provider.devices("example.invalid")
        label, buttons = _device_list_view(inventory, 0)
        self.assertIn("🖥️ Устройство Windows · Windows 10 (сборка 19045)", label)
        self.assertNotIn("DESKTOP-TEST1234", label + str(buttons))
        self.assertEqual(inventory.devices[0].os_name, "Windows")
        self.assertEqual(inventory.devices[0].os_version, "10_10.0.19045")
        self.assertEqual(display_os(inventory.devices[0].os_name,
                                    inventory.devices[0].os_version),
                         "Windows 10 (сборка 19045)")

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
        for raw in ("", None, 42, "<b>Happ</b>", "Happ/1.0 secret", "Other/1.0 Happ/3", "Incy/1.0; OS", "Happ/" + "1" * 150, "Happ\\n1", "Happ\\u200b", "Shadowrocket/1 <secret>"):
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
            ("UnknownVPN/2.3", "UnknownVPN"),
            ("Happ/6.1.0/ios/2610091516618 <token>", ""),
            ("V2Box 10.1.9/iOS 26.5.1", "V2Box"),
            ("v2rayNG/1.9.46", "v2rayNG"),
            ("sing-box/1.12.0", "sing-box"),
            ("Sing Box 2.3/android", "Sing Box"),
            ("VPN-Client.Pro 12.5/windows", "VPN-Client.Pro"),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(recognized_vpn_app(raw), expected)

    def test_universal_user_agent_security(self):
        safe = (
            ("CustomVPN/3.2", "CustomVPN"),
            ("NotIncy/1.0", "NotIncy"),
            ("V2Box/10.1.9", "V2Box"),
            ("V2Box 10.1.9/iOS 26.5.1", "V2Box"),
            ("Brand2-Pro.Only 3.14/linux", "Brand2-Pro.Only"),
            ("Happ", "Happ"),
            ("Shadowrocket/3445 CFNetwork/3860.600.12 Darwin/25.5.0 iPhone18,1", "Shadowrocket"),
        )
        for user_agent, expected in safe:
            with self.subTest(user_agent=user_agent):
                self.assertEqual(recognized_vpn_app(user_agent), expected)

        forbidden = (
            "", None, 5, "A/1.0", "Not A Name!/1.2",
            "V2Box 10.1.9/iOS 26.5.1 bearer=secret",
            "Custom/1.0 token=secret", "Mozilla/5.0 (compatible; bot)",
            "Custom/1.0/extra/private", "Custom/1.0?sub_id=token",
            "<b>Happ</b>/1.0", "Happ&Co/1.0", "Happ\\nX/1.0",
            "Happ\\u200b/1.0", "Happ/1.2 secret",
            "Happ/1.0" + "9" * 260, "V2Box 10.1.9/iOS 26.5.1/extra",
            "Name " + "X" * 50 + "/1.0", "Some Very Very Long Named Application Here Here/1.0",
            "Other/1.0 Happ/3", "NotIncy/1.0/secret",
            "Name\\r/1.0", "Name/1.0;TOKEN=secret",
            "Name/https://example.invalid/abc", "Name/1.0 <secret>",
        )
        for user_agent in forbidden:
            with self.subTest(user_agent=user_agent):
                self.assertEqual(recognized_vpn_app(user_agent), "")

    async def test_unknown_app_provider_only_changes_display_name(self):
        provider = XuiCustomerProvider(SimpleNamespace(
            client_hwids=AsyncMock(return_value=[
                {"id": 7, "deviceModel": "Pixel 9", "deviceOs": "Android",
                 "userAgent": "V2Box 10.1.9/iOS 26.5.1"},
                {"id": 8, "deviceModel": "Pixel 8", "deviceOs": "Android",
                 "userAgent": "Happ/1.0 secret"},
            ]),
            get_client=AsyncMock(return_value={"client": {"email": "example.invalid", "limitHwid": 5}}),
        ))
        inventory = await provider.devices("example.invalid")
        self.assertEqual([device.app_name for device in inventory.devices], ["V2Box", ""])
        self.assertEqual([device.device_id for device in inventory.devices], [7, 8])
        label, buttons = _device_list_view(inventory, 0)
        self.assertNotIn("V2Box", label + str(buttons))
        self.assertNotIn("Happ/1.0", label + str(buttons))

    def test_macos_on_ipad_form_factor_is_mac(self):
        self.assertEqual(device_emoji("macOS (Designed for iPad)", "iPad Pro (12.9-inch) (3rd generation)"), "💻")
        self.assertEqual(device_emoji("iPadOS", "iPad Pro"), "📱")
        self.assertEqual(device_emoji("macOS", "iMac"), "🖥️")
        self.assertEqual(device_emoji("Windows 10_10.0.19045", "Устройство Windows", "DESKTOP-5RIKK8G_x86_64"), "🖥️")
        self.assertEqual(device_emoji("Windows", "Устройство Windows", "Windows 10 amd64"), "💻")
        self.assertEqual(device_emoji("Windows", "Устройство Windows", "DESKTOP-aabb1234_x86_64<script>"), "💻")
        self.assertEqual(display_os("Windows 10_10.0.19045", "26.5"), "Windows 10 (сборка 19045)")

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
