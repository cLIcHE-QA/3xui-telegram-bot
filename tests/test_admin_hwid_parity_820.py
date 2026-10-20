"""#820: read-only parity and 8-item admin HWID pagination without runtime import."""
from __future__ import annotations

import unittest
from pathlib import Path

from admin_privileges import required_role_for_callback
from device_presentation import (
    ADMIN_DEVICE_PAGE_SIZE,
    admin_device_page_window,
    device_emoji,
    display_os,
)

ROOT = Path(__file__).resolve().parents[1]


class AdminHwidParityTests(unittest.TestCase):
    def test_shared_os_and_icon_fixtures(self):
        cases = (
            ("macOS (Designed for iPad)", "iPad Pro (12.9-inch) (3rd generation)", "26.7", "💻", "macOS (Designed for iPad) 26.7"),
            ("iPadOS", "iPad Pro", "18", "📱", "iPadOS 18"),
            ("Windows", "Desktop", "11", "🖥️", "Windows 11"),
            ("", "Unknown", "", "🔹", "ОС неизвестна"),
        )
        for os_name, model, version, emoji, platform in cases:
            with self.subTest(model=model, os=os_name):
                self.assertEqual(device_emoji(os_name, model), emoji)
                self.assertEqual(display_os(os_name, version), platform)

    def test_admin_page_boundaries_and_no_lost_devices(self):
        self.assertEqual(ADMIN_DEVICE_PAGE_SIZE, 8)
        for total, expected_pages in (
            (0, 1), (1, 1), (8, 1), (9, 2), (16, 2),
            (17, 3), (30, 4), (31, 4), (65, 9),
        ):
            with self.subTest(total=total):
                observed = []
                for requested in range(expected_pages):
                    page, pages, start = admin_device_page_window(total, requested)
                    self.assertEqual((page, pages, start), (requested, expected_pages, requested * 8))
                    indices = list(range(total))[start:start + ADMIN_DEVICE_PAGE_SIZE]
                    self.assertLessEqual(len(indices), 8)
                    observed.extend(indices)
                self.assertEqual(observed, list(range(total)))
                self.assertEqual(admin_device_page_window(total, -1)[0], 0)
                self.assertEqual(admin_device_page_window(total, 999)[0], expected_pages - 1)

    def test_admin_list_uses_same_read_only_presentation_and_pages(self):
        src = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        list_view = src.split("async def _user_devices_view", 1)[1].split("async def _find_user_device", 1)[0]
        self.assertIn("from device_presentation import ADMIN_DEVICE_PAGE_SIZE, admin_device_page_window", src)
        self.assertIn("page, pages, start = admin_device_page_window(len(devices), page)", list_view)
        self.assertIn("devices[start:start + ADMIN_DEVICE_PAGE_SIZE]", list_view)
        self.assertIn('lines.append(f"Страница {page + 1}/{pages}")', list_view)
        self.assertIn("icon = device_emoji(os_name, title)", list_view)
        self.assertIn("platform = display_os(os_name, os_version)", list_view)
        self.assertIn('f"{index}. {icon} {title} · {platform} · {last_seen}"', list_view)
        self.assertIn('text=f"{icon} {index}. {title}"[:60]', list_view)
        self.assertNotIn("Fingerprint:", list_view)
        self.assertNotIn("devices[:30]", list_view)
        self.assertNotIn("… ещё", list_view)
        self.assertIn('callback_data=f"admin:u:device:{tg_id}:{device_id}:{page}"', list_view)
        self.assertIn('callback_data=f"admin:u:devices:{tg_id}:{page - 1}"', list_view)
        self.assertIn('callback_data=f"admin:u:devices:{tg_id}:{page + 1}"', list_view)
        self.assertIn('callback_data=f"admin:u:connections:{tg_id}"', list_view)

    def test_legacy_and_page_aware_callbacks_keep_rbac_and_back(self):
        src = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        handler = src.split("async def user_devices(", 1)[1].split("async def user_device_detail(", 1)[0]
        self.assertIn('authorize_callback(db, settings, call, minimum="read_only")', handler)
        self.assertIn("_user_devices_view(tg_id, role, page)", handler)
        self.assertIn('await call.answer("Некорректная страница устройств.", show_alert=True)', handler)
        detail = src.split("async def user_device_detail(", 1)[1].split('F.data.regexp(r"^admin:u:devdelask:', 1)[0]
        self.assertIn("tg_id, device_id = int(parts[3]), int(parts[4])", detail)
        self.assertIn('back += f":{int(parts[5])}"', detail)
        self.assertEqual(detail.count("callback_data=back"), 2)
        for callback in (
            "admin:u:devices:101", "admin:u:devices:101:0",
            "admin:u:devices:101:1", "admin:u:devices:101:999",
            "admin:u:device:101:7", "admin:u:device:101:7:1",
        ):
            with self.subTest(callback=callback):
                self.assertEqual(required_role_for_callback(callback), "read_only")

    def test_admin_detail_contract_remains_untouched(self):
        src = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        detail = src.split("async def user_device_detail(", 1)[1].split('F.data.regexp(r"^admin:u:devdelask:', 1)[0]
        self.assertIn('f"User-Agent: {user_agent}\\n"', detail)
        self.assertIn('f"Fingerprint: {fingerprint}\\n"', detail)
        self.assertIn('text="🗑 Удалить устройство"', detail)
        self.assertIn('text="⬅ Устройства"', detail)

    def test_client_page_size_remains_five(self):
        src = (ROOT / "client_access.py").read_text(encoding="utf-8")
        self.assertIn("DEVICE_PAGE_SIZE = 5", src)
        self.assertIn("inventory.devices[start:start + DEVICE_PAGE_SIZE]", src)


if __name__ == "__main__":
    unittest.main()
