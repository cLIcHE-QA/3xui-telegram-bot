"""Regression coverage for v4.21.1 display/time consistency."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest

from ui_time import MSK, backup_schedule_text, end_of_day_timestamp, format_timestamp
from user_ui import user_label


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class V4211DisplayTimeConsistencyTests(unittest.TestCase):
    def test_user_label_prefers_display_name_but_keeps_email(self):
        user = SimpleNamespace(email="machine@example.test")
        profile = SimpleNamespace(display_name="Alice")
        self.assertEqual(user_label(user, profile), "Alice · machine@example.test")
        self.assertEqual(user_label(user, None), "machine@example.test")

    def test_operator_time_is_msk(self):
        ts = int(datetime(2026, 1, 1, 0, 0, tzinfo=MSK).timestamp())
        self.assertEqual(format_timestamp(ts), "2026-01-01 00:00 MSK")
        self.assertEqual(backup_schedule_text(2), "05:00 MSK (02:00 UTC)")

    def test_date_only_input_means_end_of_day_msk(self):
        ts = end_of_day_timestamp("2026-12-31")
        dt = datetime.fromtimestamp(ts, tz=MSK)
        self.assertEqual((dt.year, dt.month, dt.day), (2026, 12, 31))
        self.assertEqual((dt.hour, dt.minute, dt.second), (23, 59, 59))

    def test_display_name_is_used_on_neighboring_admin_surfaces(self):
        shell = source("admin_shell.py")
        users = source("advanced_users.py")
        inbound = source("inbound_admin.py")
        observability = source("admin_observability.py")
        business = source("business_admin.py")

        self.assertIn('text=f"🔗 {user_label(u, profile)}"', shell)
        self.assertIn('f"🔗 {await _display_label(rec)}', users)
        self.assertIn('text=f"👤 {label}"', inbound)
        self.assertIn('label = user_label(rec, profile) if rec else email', observability)
        self.assertIn('label = user_label(user, profile) if user else f"TG {item.telegram_id}"', business)

    def test_operator_date_inputs_are_msk_but_backup_setting_remains_utc(self):
        users = source("advanced_users.py")
        business = source("business_admin.py")
        runtime = source("app_runtime.py")
        config = source("config.py")

        self.assertIn("23:59 MSK", users)
        self.assertIn("YYYY-MM-DD` (MSK)", business)
        self.assertIn("end_of_day_timestamp(raw)", users)
        self.assertIn("end_of_day_timestamp(raw)", business)
        self.assertIn("settings.backup_hour_utc", runtime)
        self.assertIn('os.getenv("BACKUP_HOUR_UTC", "2")', config)


if __name__ == "__main__":
    unittest.main()
