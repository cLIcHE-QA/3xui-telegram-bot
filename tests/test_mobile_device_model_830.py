"""Админка и Client Portal: безопасная модель HWID (#830)."""
from __future__ import annotations

import unittest
from pathlib import Path

from device_model_resolver import _android, _apple, display_device_model

ROOT = Path(__file__).resolve().parents[1]


class MobileModelResolverTests(unittest.TestCase):
    def test_four_real_cases(self):
        cases = (
            ("Unknown device", "iOS 26.5.1", "", "Устройство iOS"),
            ("iPhone18,1", "iOS 26.5.1", "", "iPhone 17 Pro"),
            ("iPhone", "iOS 26.5.1",
             "Shadowrocket/3445 CFNetwork/3860.600.12 Darwin/25.5.0 iPhone18,1",
             "iPhone 17 Pro"),
            ("iPad", "macOS 26.7", "", "Mac (модель не определена)"),
        )
        for model, os_name, ua, expected in cases:
            with self.subTest(model=model):
                self.assertEqual(display_device_model(model, os_name, ua), expected)

    def test_safe_fallback_and_platform_boundaries(self):
        cases = (
            ("Unknown device", "Android 15", "", "Устройство Android"),
            ("iPad", "iPadOS 18.0", "", "iPad (модель не определена)"),
            ("iPhone", "iOS 26.5", "", "iPhone (модель не определена)"),
            ("iPhone18,1", "Android", "", "iPhone18,1"),
            ("iPad", "Windows 11", "", "iPad"),
            ("", "", "", "Устройство"),
            ("Pixel 9", "Android 15", "", "Pixel 9"),
            ("Galaxy S24 Ultra", "Android 15", "", "Galaxy S24 Ultra"),
            ("Mac mini", "macOS 26.7", "", "Mac mini"),
            ("iPhone18,99", "iOS", "", "iPhone (модель не определена)"),
            ("iPad", "macOS (Designed for iPad) 26.7", "", "Mac (модель не определена)"),
        )
        for model, os_name, ua, expected in cases:
            with self.subTest(model=model, os=os_name):
                self.assertEqual(display_device_model(model, os_name, ua), expected)

    def test_conflict_and_untrusted_user_agent(self):
        real = "Shadowrocket/3445 CFNetwork/3860.600.12 Darwin/25.5.0 iPhone18,1"
        other = "Shadowrocket/3445 CFNetwork/3860.600.12 Darwin/25.5.0 iPhone18,2"
        self.assertEqual(display_device_model("iPhone18,1", "iOS", other),
                         "iPhone (модель не определена)")
        self.assertEqual(display_device_model("iPhone 17 Pro", "iOS", other),
                         "iPhone 17 Pro")
        self.assertEqual(display_device_model("iPhone", "Android", real), "iPhone")
        for payload in (
            "Unknown/1.0 CFNetwork/3 Darwin/25 iPhone18,1",
            "Shadowrocket/1.0 token=secret CFNetwork/3 Darwin/25 iPhone18,1",
            "Shadowrocket/1.0 CFNetwork/3 Darwin/25 iPhone18,1 https://evil",
            "Shadowrocket/1.0 CFNetwork/3 Darwin/25 iPhone18,1\\nBAD",
            "Shadowrocket/1.0 CFNetwork/3 Darwin/25 iPhone18,1" + "x" * 300,
        ):
            with self.subTest(payload=payload[:40]):
                self.assertEqual(display_device_model("iPhone", "iOS", payload),
                                 "iPhone (модель не определена)")

    def test_catalogs_load_and_ambiguity_is_not_guessed(self):
        self.assertEqual(_apple()["iPhone18,1"], "iPhone 17 Pro")
        self.assertGreater(len(_android()), 100)
        # Уникальное коммерческое название разрешено; неоднозначный код остаётся raw.
        self.assertEqual(display_device_model("Pixel 9", "Android"), "Pixel 9")

    def test_both_ui_surfaces_use_one_resolver_without_identity_changes(self):
        customer = (ROOT / "customer_provider_xui.py").read_text(encoding="utf-8")
        admin = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        self.assertIn('title=display_device_model(item.get("deviceModel"), os_name, item.get("userAgent"))', customer)
        self.assertIn('return display_device_model(', admin)
        self.assertIn('model = _device_title(item)', admin)
        self.assertIn('_verified_device_id(item.get("id"))', customer)
        self.assertIn('device_id = int(item.get("id") or 0)', admin)
        self.assertIn('callback_data=f"admin:u:device:{tg_id}:{device_id}:{page}"', admin)


if __name__ == "__main__":
    unittest.main()
