from __future__ import annotations

import unittest
from pathlib import Path

from admin_navigation import confirm_delete_keyboard

ROOT = Path(__file__).resolve().parents[1]


class Rc11NavigationRegressionTests(unittest.TestCase):
    def test_delete_cancel_returns_to_more(self):
        keyboard = confirm_delete_keyboard(42)
        self.assertEqual(keyboard.inline_keyboard[1][0].callback_data, "admin:u:more:42")

    def test_bulk_close_and_input_cancel_navigation(self):
        s = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        close = s.split("async def bulk_close(", 1)[1].split("async def _bulk_result(", 1)[0]
        self.assertIn("await state.clear()", close)
        self.assertIn("_users_page_view(0, role)", close)
        self.assertNotIn("Выбор для массовых действий закрыт.", close)
        cancel = s.split("async def bulk_input_cancel(", 1)[1].split("async def bulk_back(", 1)[0]
        self.assertIn("_bulk_actions_keyboard()", cancel)
        self.assertIn('await state.set_state(BulkUserStates.selecting)', cancel)
        self.assertNotIn("_bulk_render(state)", cancel)

    def test_more_actions_cancel_routes(self):
        s = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        for function, next_function in (
            ("user_reset_ask", "user_reset_run"),
            ("user_provisioning_strict_ask", "user_provisioning_run"),
            ("user_sub_rotate_ask", "user_sub_rotate_run"),
        ):
            block = s.split(f"async def {function}(", 1)[1].split(f"async def {next_function}(", 1)[0]
            self.assertIn('callback_data=f"admin:u:more:{tg_id}"', block)

    def test_host_import_returns_to_sqlite(self):
        s = (ROOT / "catalog_admin.py").read_text(encoding="utf-8")
        block = s.split("async def hosts_discover(", 1)[1].split("async def ", 1)[0]
        self.assertIn('callback_data="admin:hosts:local"', block)

    def test_restore_history_keeps_backup_identity(self):
        s = (ROOT / "disaster_recovery.py").read_text(encoding="utf-8")
        detail = s.split("def _backup_actions(", 1)[1].split("async def restore_list(", 1)[0]
        self.assertIn('f"admin:restore:history:{bid}"', detail)
        history = s.split("async def restore_history(", 1)[1].split("async def send_boot_restore_notice(", 1)[0]
        self.assertIn("_backup_by_id(bid)", history)
        self.assertIn("_restore_back(bid) if bid else _restore_list_back()", history)


if __name__ == "__main__":
    unittest.main()
