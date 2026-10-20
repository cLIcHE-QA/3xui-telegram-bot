"""Отдельные fallback-названия Windows/Linux (#833)."""
import unittest

from device_model_resolver import display_device_model


class DesktopModelTests(unittest.TestCase):
    def test_windows_cases(self):
        for model, os_name, expected in (
            ("DESKTOP-5RIKK8G_x86_64", "Windows 10_10.0.19045", "Устройство Windows"),
            ("Windows 10 amd64", "Windows 10 10.0", "Устройство Windows"),
            ("Unknown device", "Windows 11", "Устройство Windows"),
            ("x86_64", "Windows 11", "Устройство Windows"),
            ("ThinkPad T14", "Windows 11", "ThinkPad T14"),
            ("ASUS ROG Zephyrus G14", "Windows 10", "ASUS ROG Zephyrus G14"),
            ("DESKTOP-5RIKK8G_x86_64", "Android 14", "DESKTOP-5RIKK8G_x86_64"),
            ("DESKTOP-5RIKK8G_x86_64", "Solaris 11", "DESKTOP-5RIKK8G_x86_64"),
        ):
            with self.subTest(model=model, os=os_name):
                self.assertEqual(display_device_model(model, os_name), expected)

    def test_linux_cases(self):
        for model, os_name, expected in (
            ("Unknown device", "Ubuntu 24.04", "Устройство Linux"),
            ("x86_64", "Debian 13", "Устройство Linux"),
            ("Ubuntu 24.04", "Ubuntu 24.04", "Устройство Linux"),
            ("Linux x86_64", "Linux", "Устройство Linux"),
            ("Dell XPS 13", "Debian 13", "Dell XPS 13"),
            ("ThinkPad T14", "Ubuntu 24.04", "ThinkPad T14"),
            ("Unknown device", "Arch Linux", "Устройство Linux"),
            ("Unknown device", "Android 15", "Устройство Android"),
            ("Unknown device", "Ubuntuish 24.04", "Unknown device"),
            ("Unknown device", "MyDebian 13", "Unknown device"),
        ):
            with self.subTest(model=model, os=os_name):
                self.assertEqual(display_device_model(model, os_name), expected)


if __name__ == "__main__":
    unittest.main()
