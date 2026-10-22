"""#827: Happ Android с непрозрачным 20-значным окончанием User-Agent."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from customer_provider_xui import XuiCustomerProvider
from device_presentation import recognized_vpn_app


VALID = "Happ/4.7.1/Android/17912108360521999608"


class HappLongAndroidUaTests(unittest.TestCase):
    def test_exact_observation_and_backward_compatibility(self):
        for ua, name in (
            (VALID, "Happ"),
            ("happ/4.7.1/android/17912108360521999608", "Happ"),
            ("Happ/4.7.1/Android/" + "1" * 20, "Happ"),
            ("Happ/1.2", "Happ"),
            ("Happ/iOS/1.2.3", "Happ"),
            ("Throne/Android/2.0.3", "Throne"),
            ("V2Box 10.1.9/iOS 26.5.1", "V2Box"),
        ):
            with self.subTest(ua=ua):
                self.assertEqual(recognized_vpn_app(ua), name)

    def test_no_broader_long_numeric_suffix(self):
        rejected = (
            "OtherVPN/4.7.1/Android/" + "1" * 20,
            "Happ/4.7.1/iOS/" + "1" * 20,
            "Happ/4.7.1/Android/" + "1" * 19,
            "Happ/4.7.1/Android/" + "1" * 21,
            "Happ/4.7.1/Android/" + "1" * 20 + "/extra",
            VALID + "?token=private", VALID + ";bearer=secret",
            VALID + " https://example.invalid", VALID + "/123",
            VALID + "\nspoof", VALID + "\tspoof", VALID + "🔐",
            "<b>Happ</b>/4.7.1/Android/" + "1" * 20,
            "Happ/4.7.1/Android/" + "1" * 19 + "X",
            "Happ/4.7.1/Android/" + "1" * 19 + " ",
            "Happ/4.7.1/Android/" + "1" * 20 + "x" * 800,
            None, 5,
        )
        for ua in rejected:
            with self.subTest(ua=str(ua)[:45]):
                self.assertEqual(recognized_vpn_app(ua), "")


class HappClientDevicePresentationTests(unittest.IsolatedAsyncioTestCase):
    async def test_client_detail_and_admin_parser_consistency_without_leaking_ua(self):
        import client_access
        provider = XuiCustomerProvider(SimpleNamespace(
            client_hwids=AsyncMock(return_value=[{
                "id": 17, "deviceModel": "Pixel 6",
                "deviceOs": "Android", "osVersion": "17",
                "userAgent": VALID, "fingerprint": "opaque-fingerprint",
                "lastSeen": 1792665780000,
            }]),
            get_client=AsyncMock(return_value={"client": {
                "email": "example.invalid", "limitHwid": 5,
            }}),
        ))
        inventory = await provider.devices("example.invalid")
        device = inventory.devices[0]
        self.assertEqual((device.title, device.os_name, device.os_version, device.device_id, device.app_name),
                         ("Pixel 6", "Android", "17", 17, "Happ"))
        label, buttons = client_access._device_list_view(inventory, 0)
        self.assertNotIn(VALID, label + str(buttons))
        self.assertNotIn("Happ", label + str(buttons))
        service = SimpleNamespace(devices=AsyncMock(return_value=inventory))
        call = SimpleNamespace(from_user=SimpleNamespace(id=7), answer=AsyncMock())
        with patch.object(client_access, "_service", return_value=service), \
             patch.object(client_access, "render_callback", new=AsyncMock()) as render:
            await client_access._render_device_detail(call, 17, 0)
        detail = render.await_args.args[1]
        self.assertIn("Pixel 6", detail)
        self.assertIn("⚙️ ОС: Android 17", detail)
        self.assertIn("🛡️ VPN-клиент: Happ", detail)
        for secret in (VALID, "17912108360521999608", "opaque-fingerprint", "User-Agent:", "Fingerprint:"):
            self.assertNotIn(secret, detail + label + str(buttons))
        self.assertEqual(recognized_vpn_app(VALID), "Happ")


if __name__ == "__main__":
    unittest.main()
