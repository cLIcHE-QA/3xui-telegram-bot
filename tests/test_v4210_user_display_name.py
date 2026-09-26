"""Regression coverage for the v4.21.0 user display-name feature."""
from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from admin_privileges import required_role_for_callback
from db import Database, UserRecord
from version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def load_advanced_users():
    env = {
        "BOT_TOKEN": "123456789:offline-v421-token",
        "PANEL_URL": "https://panel.example.invalid/base",
        "PANEL_API_TOKEN": "offline-v421-token",
        "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/sub/{sub_id}",
        "COMPAT_SUBSCRIPTION_URL_TEMPLATE": "https://public.example.invalid/compat/{sub_id}",
        "ALLOWED_TELEGRAM_IDS": "1",
        "ADMIN_TELEGRAM_IDS": "1",
        "DB_PATH": "/tmp/v421-user-display-name.sqlite3",
    }
    with patch.dict(os.environ, env, clear=False):
        return importlib.import_module("advanced_users")


class V4210UserDisplayNameTests(unittest.IsolatedAsyncioTestCase):
    def test_release_version_is_4210(self):
        self.assertEqual(APP_VERSION, "4.21.0")

    def test_display_name_callback_requires_support(self):
        self.assertEqual(required_role_for_callback("admin:u:name:101"), "support")

    def test_display_name_normalization_and_validation(self):
        module = load_advanced_users()
        self.assertEqual(module.normalize_display_name("  Alice   Example  "), "Alice Example")
        self.assertEqual(module.normalize_display_name("-"), "")
        for invalid in ("", "   ", "Alice\nExample", "Alice\tExample", "A" * 65):
            with self.subTest(invalid=repr(invalid)):
                with self.assertRaises(ValueError):
                    module.normalize_display_name(invalid)

    async def test_display_name_is_profile_only_and_preserves_machine_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = Database(str(Path(tmp) / "bot.sqlite3"))
            await database.init()
            original = UserRecord(
                telegram_id=101,
                email="user101@example.test",
                sub_id="stable-sub-id",
                expiry_time=123456,
                created_at=789,
            )
            await database.put(original)
            await database.upsert_user_profile(
                101,
                plan_id=None,
                server_group_id=None,
                note="internal note",
            )

            await database.set_user_display_name(101, "Alice Example")

            rec = await database.get(101)
            profile = await database.get_user_profile(101)
            self.assertEqual(rec, original)
            self.assertEqual(profile.display_name, "Alice Example")
            self.assertEqual(profile.note, "internal note")

            await database.set_user_display_name(101, "")
            rec_after_clear = await database.get(101)
            profile_after_clear = await database.get_user_profile(101)
            self.assertEqual(rec_after_clear, original)
            self.assertEqual(profile_after_clear.display_name, "")

    def test_ui_uses_display_name_only_as_presentation(self):
        users = source("advanced_users.py")
        self.assertIn('f"👤 {display_name or rec.email}"', users)
        self.assertIn('*([f"Email: {rec.email}"] if display_name else [])', users)
        self.assertIn('label = user_label(u, profile)', users)
        self.assertIn('callback_data=f"admin:u:{u.telegram_id}"', users)
        self.assertIn('target_id=rec.email', users)
        self.assertIn('"user.display_name.set"', users)

        handler = users.split("async def user_display_name_save", 1)[1].split(
            '@advanced_users_router.callback_query(F.data.startswith("admin:u:note:"))',
            1,
        )[0]
        self.assertNotIn("xui.", handler)
        self.assertNotIn("update_sub_id", handler)
        self.assertNotIn("update_expiry", handler)


if __name__ == "__main__":
    unittest.main()
