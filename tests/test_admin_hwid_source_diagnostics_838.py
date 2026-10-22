"""Административная диагностика исходных моделей/ОС без утечек (#838)."""
import unittest
from pathlib import Path
from device_model_resolver import admin_original_hwid_labels, display_device_model
from device_presentation import display_os

ROOT = Path(__file__).resolve().parents[1]


class AdminRawLabelsTest(unittest.TestCase):
    def test_windows_and_linux_originals(self):
        pairs = (
            ("DESKTOP-5RIKK8G_x86_64", "Windows 10_10.0.19045",
             "Устройство Windows", "DESKTOP-5RIKK8G_x86_64", "Windows 10_10.0.19045"),
            ("Windows 10 amd64", "Windows 10 10.0",
             "Устройство Windows", "Windows 10 amd64", "Windows 10 10.0"),
            ("Unknown device", "Ubuntu 24.04",
             "Устройство Linux", "Unknown device", "Ubuntu 24.04"),
            ("ThinkPad T14", "Debian 13", "ThinkPad T14", "", "Debian 13"),
            ("iPhone18,1", "iOS 26.5.1", "iPhone 17 Pro", "iPhone18,1", "iOS 26.5.1"),
        )
        for source_model, source_os, expected_display, original_model, original_os in pairs:
            with self.subTest(source_model=source_model):
                label = display_device_model(source_model, source_os)
                self.assertEqual(label, expected_display)
                self.assertEqual(
                    admin_original_hwid_labels(source_model, source_os, label),
                    (original_model, original_os)
                )

    def test_os_version_append_does_not_trigger_raw(self):
        self.assertEqual(display_os("Windows", "11"), "Windows 11")
        self.assertEqual(admin_original_hwid_labels("ThinkPad", "Windows", "ThinkPad"), ("", "Windows"))
        self.assertEqual(admin_original_hwid_labels("Dell", "Ubuntu 24.04", "Dell"), ("", "Ubuntu 24.04"))

    def test_never_expose_untrusted_markup_and_secrets(self):
        dangerous = (
            "<b>DESKTOP</b>", "Model\nINJECTED", "OS\rINJECTED",
            "token=secret", "https://malicious.invalid",
            "a" * 140, "x" * 48, "a_b" * 22,
            "WINDOWS;command", "Модель [скрытая](https://invalid.example)",
        )
        for raw in dangerous:
            with self.subTest(raw=raw[:25]):
                self.assertEqual(admin_original_hwid_labels(raw, raw, "Устройство Windows"), ("", ""))

    def test_admin_only_read_only_integration(self):
        admin = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        customer = (ROOT / "customer_provider_xui.py").read_text(encoding="utf-8")
        detail = admin.split("async def user_device_detail(", 1)[1].split('F.data.regexp(r"^admin:u:devdelask:', 1)[0]
        self.assertIn("admin_original_hwid_labels(", detail)
        self.assertIn("Исходная модель: {original_model}", detail)
        self.assertIn("Исходная ОС: {original_os}", detail)
        self.assertIn('f"🧾 Исходная ОС: {original_os}\\n"', detail)
        self.assertIn('f"{model_icon} Модель: {model}\\n"', detail)
        self.assertNotIn("Исходная модель:", customer)
        self.assertNotIn("Исходная ОС:", customer)
        self.assertIn('callback_data=f"admin:u:devdelask:{tg_id}:{device_id}"', detail)


if __name__ == "__main__":
    unittest.main()
