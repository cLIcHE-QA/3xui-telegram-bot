from __future__ import annotations

import unittest
from pathlib import Path

from admin_identity import (
    MAX_BUTTON_LENGTH, MAX_ENTRIES, TTL_SECONDS, administrator_label,
    bounded_admin_button, clear_hints, observe_admin_identity, observed_username,
)
from admin_privileges import required_role_for_callback


class AdministratorUsernamePresentationTests(unittest.TestCase):
    def setUp(self):
        clear_hints()

    def tearDown(self):
        clear_hints()

    def test_present_absent_changed_removed_and_expired(self):
        self.assertEqual(administrator_label(101, now=100), "TG 101")
        observe_admin_identity(101, "Alice_123", now=100)
        self.assertEqual(administrator_label(101, now=100), "@Alice_123")
        observe_admin_identity(101, "NewAlice_123", now=120)
        self.assertEqual(administrator_label(101, now=120), "@NewAlice_123")
        self.assertEqual(administrator_label(101, now=120 + TTL_SECONDS + 1), "TG 101")
        observe_admin_identity(101, "Alice_123", now=30000)
        observe_admin_identity(101, None, now=30001)
        self.assertEqual(administrator_label(101, now=30002), "TG 101")

    def test_duplicate_username_is_bound_to_distinct_numeric_ids(self):
        observe_admin_identity(101, "Shared_123", now=100)
        observe_admin_identity(202, "Shared_123", now=100)
        self.assertEqual(observed_username(101, now=101), "Shared_123")
        self.assertEqual(observed_username(202, now=101), "Shared_123")
        observe_admin_identity(101, None, now=102)
        self.assertEqual(administrator_label(101, now=103), "TG 101")
        self.assertEqual(administrator_label(202, now=103), "@Shared_123")
        for number in (101, 202):
            self.assertEqual(required_role_for_callback(f"admin:administrator:{number}"), "owner")

    def test_invalid_username_is_not_reused(self):
        observe_admin_identity(101, "Alice_123", now=100)
        for invalid in ("a", "a" * 33, "bad name", "https://example.org", "alice@site"):
            observe_admin_identity(101, invalid, now=101)
            self.assertEqual(administrator_label(101, now=102), "TG 101")
            observe_admin_identity(101, "Alice_123", now=103)

    def test_cache_capacity_and_bounded_button(self):
        for number in range(1, MAX_ENTRIES + 4):
            observe_admin_identity(number, "Person_123", now=100)
        self.assertEqual(administrator_label(1, now=101), "TG 1")
        self.assertEqual(administrator_label(MAX_ENTRIES + 3, now=101), "@Person_123")
        label = bounded_admin_button("🟢 👑 @Person_123 · Owner · локальная конфигурация")
        self.assertIn("локальная конфигурация", label)
        self.assertLessEqual(len(bounded_admin_button("a" * 250)), MAX_BUTTON_LENGTH)

    def test_admin_list_is_owner_scoped_and_identity_does_not_change_auth(self):
        self.assertEqual(required_role_for_callback("admin:administrators"), "owner")
        source = (Path(__file__).resolve().parents[1] / "business_admin.py").read_text(encoding="utf-8")
        self.assertIn('if not await guard(call, minimum="owner")', source)
        self.assertIn('callback_data=f"admin:administrator:{tg_id}"', source)
        self.assertIn("Telegram ID: {tg_id}", source)
        auth = (Path(__file__).resolve().parents[1] / "admin_auth.py").read_text(encoding="utf-8")
        self.assertIn("observe_admin_identity(call.from_user.id, call.from_user.username)", auth)
        self.assertNotIn("observed_username", auth)


if __name__ == "__main__":
    unittest.main()
