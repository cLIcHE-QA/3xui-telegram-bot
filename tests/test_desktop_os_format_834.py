"""Отдельное безопасное форматирование версий ОС (#834)."""
import unittest

from device_presentation import display_os


class DesktopOsTests(unittest.TestCase):
    def test_known_windows_versions(self):
        pairs = (
            ("Windows 10_10.0.19045", "", "Windows 10 (сборка 19045)"),
            ("Windows 10 10.0", "", "Windows 10"),
            ("Windows 11 10.0.26100", "", "Windows 11 (сборка 26100)"),
            ("Windows 10", "10.0.19045", "Windows 10 (сборка 19045)"),
            ("Windows 11", "10.0.26100", "Windows 11 (сборка 26100)"),
            ("Windows 10_10.0.19045", "10.0.19045", "Windows 10 (сборка 19045)"),
        )
        for os_name, version, expected in pairs:
            with self.subTest(os=os_name, version=version):
                self.assertEqual(display_os(os_name, version), expected)
                self.assertEqual(display_os(expected), expected)

    def test_no_guess_on_conflict_or_unrecognized_os(self):
        pairs = (
            ("Windows", "10.0", "Windows 10.0"),
            ("Windows 10_10.0.19045", "10.0.26100", "Windows 10_10.0.19045 10.0.26100"),
            ("Windows 11", "garbage", "Windows 11 garbage"),
            ("Ubuntu 24.04", "", "Ubuntu 24.04"),
            ("Debian 13", "", "Debian 13"),
            ("Fedora 41", "", "Fedora 41"),
            ("iOS 26.5.1", "26.5.1", "iOS 26.5.1"),
            ("Android 15", "15", "Android 15"),
            ("macOS (Designed for iPad)", "26.7", "macOS (Designed for iPad) 26.7"),
            ("", "10.0", "ОС неизвестна"),
        )
        for os_name, version, expected in pairs:
            with self.subTest(os=os_name, version=version):
                self.assertEqual(display_os(os_name, version), expected)

if __name__ == "__main__":
    unittest.main()
