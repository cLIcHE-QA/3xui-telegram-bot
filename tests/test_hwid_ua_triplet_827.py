"""Регрессия #827: безопасный User-Agent формата Client/Platform/Version."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from customer_provider_xui import XuiCustomerProvider
from device_presentation import recognized_vpn_app
from client_access import _device_list_view


class UniversalPlatformUserAgentTests(unittest.TestCase):
    def test_any_safe_brand_with_platform_and_version(self):
        cases = (
            ("Throne/Android/2.0.3", "Throne"),
            ("Throne/android/v2.0.3", "Throne"),
            ("FutureVPN/iOS/1.2.3", "FutureVPN"),
            ("NewVPN/iPadOS/2.0", "NewVPN"),
            ("SecureClient/macOS/1.0.0-beta2", "SecureClient"),
            ("Client-Lab/Windows/7.1-rc1", "Client-Lab"),
            ("SomeVPN/Linux/1.2.3.4", "SomeVPN"),
            ("v2rayNG/Linux/1.9.46", "v2rayNG"),
            ("Happ/iOS/1.2.3", "Happ"),
            ("Incy/Android/2.3", "Incy"),
            ("VPN-Client.Pro/ANDROID/2.0.3", "VPN-Client.Pro"),
            ("CustomVPN/3.2", "CustomVPN"),
            ("V2Box 10.1.9/iOS 26.5.1", "V2Box"),
        )
        for ua, expected in cases:
            with self.subTest(ua=ua):
                self.assertEqual(recognized_vpn_app(ua), expected)

    def test_reject_technical_components_ambiguous_or_sensitive_ua(self):
        forbidden = (
            "Android/Android/2.0.3", "iOS/Android/2.0.3",
            "Windows/Linux/1.2.3", "Linux/iOS/1.0",
            "Dalvik/Android/2.1", "Mozilla/Android/5.0",
            "curl/Android/8.1", "okhttp/Android/4.0",
            "CFNetwork/iOS/2.0", "Throne/Androidish/2.0.3",
            "Throne/UnknownOS/2.0.3", "Throne/Android/",
            "Throne/Android/v", "Throne/Android/two",
            "Throne/Android/2.0.3/extra", "Throne/Android/2.0.3 token=secret",
            "Throne/Android/2.0.3?token=secret",
            "Throne/Android/2.0.3;bearer=secret",
            "Throne/Android/2.0.3 https://example.invalid/path",
            "Throne/Android/2.0.3\nInjected",
            "Throne/Android/2.0.3\tInjected",
            "Throne/Android/2.0.3🔒",
            "<b>Throne</b>/Android/2.0.3",
            "Throne 2.0.3/Android/2.0.3?access_token=x",
            "Throne/Android/2.0.3" + "x" * 800,
            "Android 2.0.3/iOS 1.0",
            None, 23,
        )
        for ua in forbidden:
            with self.subTest(ua=str(ua)[:45]):
                self.assertEqual(recognized_vpn_app(ua), "")


class UniversalPlatformProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_claimed_name_does_not_change_identity_or_list(self):
        provider = XuiCustomerProvider(SimpleNamespace(
            client_hwids=AsyncMock(return_value=[
                {
                    "id": 17, "deviceModel": "sdk_gphone16k_arm64",
                    "deviceOs": "Android", "osVersion": "17",
                    "fingerprint": "opaque-private-value",
                    "userAgent": "Throne/Android/2.0.3",
                },
                {
                    "id": 18, "deviceModel": "Pixel 9",
                    "deviceOs": "Android", "osVersion": "16",
                    "userAgent": "Throne/Android/2.0.3 token=private",
                },
            ]),
            get_client=AsyncMock(return_value={
                "client": {"email": "example.invalid", "limitHwid": 5}
            }),
        ))
        inventory = await provider.devices("example.invalid")
        self.assertEqual([device.device_id for device in inventory.devices], [17, 18])
        self.assertEqual([device.app_name for device in inventory.devices], ["Throne", ""])
        self.assertEqual(inventory.devices[0].title, "Устройство Android")
        self.assertEqual(inventory.devices[0].os_name, "Android")
        self.assertEqual(inventory.devices[0].os_version, "17")
        label, buttons = _device_list_view(inventory, 0)
        self.assertNotIn("Throne", label + str(buttons))
        self.assertNotIn("opaque-private-value", label + str(buttons))
        self.assertNotIn("Throne/Android/2.0.3", label + str(buttons))
        # Detail UI uses app_name, not the untrusted raw User-Agent.
        from pathlib import Path
        source = Path("client_access.py").read_text(encoding="utf-8")
        self.assertIn("VPN-клиент: {device.app_name or 'Не определён'}", source)


if __name__ == "__main__":
    unittest.main()
