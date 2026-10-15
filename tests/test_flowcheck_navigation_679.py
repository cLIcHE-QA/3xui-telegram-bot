"""Проверка origin-aware навигации Flow (#679), без production запросов."""
from pathlib import Path
import unittest
from admin_privileges import required_role_for_callback

ROOT = Path(__file__).resolve().parents[1]

class FlowCheckNavigationTests(unittest.TestCase):
    def test_callbacks_and_role(self):
        for callback in ("admin:u:flowcheck:123", "admin:u:flowcheck:cfg:123"):
            self.assertEqual(required_role_for_callback(callback), "read_only")
            self.assertLessEqual(len(callback.encode()), 64)
        biggest_id = 9_223_372_036_854_775_807
        contextual = f"admin:u:flowcheck:cfg:{biggest_id}"
        self.assertLessEqual(len(contextual.encode("utf-8")), 64)
        self.assertEqual(required_role_for_callback(contextual), "read_only")
        for callback in ("admin:u:flowcheck:cfg:abc", "admin:u:flowcheck:other:123", "admin:u:flowcheck:cfg:-2"):
            self.assertIsNone(required_role_for_callback(callback))

    def test_entrypoints_have_distinct_contexts(self):
        src = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        card = src.split("async def render_user(", 1)[1].split("async def ", 1)[0] if "async def render_user(" in src else src
        self.assertIn('callback_data=f"admin:u:flowcheck:{tg_id}"', card)
        settings = src.split("async def user_access_config", 1)[1].split("async def user_flow_sync_ask", 1)[0]
        self.assertIn('callback_data=f"admin:u:flowcheck:cfg:{tg_id}"', settings)

    def test_both_back_and_refresh_preserve_context_even_on_error(self):
        src = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        check = src.split("async def user_flow_check", 1)[1].split("async def user_advanced_card", 1)[0]
        for needle in (
            'from_access_config = (call.data or "").split(":")[3:4] == ["cfg"]',
            'f"admin:u:flowcheck:cfg:{tg_id}" if from_access_config else f"admin:u:flowcheck:{tg_id}"',
            'text="⬅ Параметры доступа" if from_access_config else "⬅ Пользователь"',
            'callback_data=f"admin:u:accesscfg:{tg_id}" if from_access_config else f"admin:u:{tg_id}"',
            'except (XUIError, ValueError, TypeError):',
            'reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)',
        ):
            self.assertIn(needle, check)

    def test_editor_result_keeps_access_config(self):
        src = (ROOT / "flow_edit_routes.py").read_text(encoding="utf-8")
        result = src.split("async def flow_edit_commit", 1)[1]
        self.assertIn('("🔎 Проверить Flow", f"admin:u:flowcheck:cfg:{tg_id}")', result)
        self.assertIn('("⬅ Параметры доступа", f"admin:u:accesscfg:{tg_id}")', result)

if __name__ == "__main__":
    unittest.main()
