from __future__ import annotations

from pathlib import Path
import unittest

from admin_privileges import required_role_for_callback
from version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class V4251StabilizationTests(unittest.TestCase):
    def test_current_release_version(self):
        self.assertEqual(APP_VERSION, "4.26.0")

    def test_subscription_show_url_returns_to_subscription_parent(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        handler = source.split(
            '@advanced_users_router.callback_query(F.data.startswith("adminsub:"))',
            1,
        )[1].split(
            '@advanced_users_router.callback_query(F.data.startswith("adminsublist:"))',
            1,
        )[0]
        self.assertIn("reply_markup=back_subscription(tg_id)", handler)
        self.assertNotIn("reply_markup=back_user(tg_id)", handler)

    def test_user_scoped_payments_do_not_link_to_global_ledger(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        view = source.split("async def _user_payments_view", 1)[1].split(
            '@advanced_users_router.callback_query(F.data.regexp(r"^admin:u:payments:',
            1,
        )[0]
        self.assertNotIn('callback_data="admin:payments"', view)
        self.assertIn('callback_data=f"admin:u:{tg_id}"', view)

    def test_main_user_card_has_no_extend_shortcut(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        card = source.split("async def render_user", 1)[1].split(
            "async def _user_plan_view", 1
        )[0]
        self.assertNotIn('text="⏳ Продлить"', card)
        self.assertNotIn('callback_data=f"adminextend:{tg_id}"', card)
        expiry = source.split("async def _user_expiry_view", 1)[1].split(
            "async def _user_traffic_view", 1
        )[0]
        self.assertIn('text="➕ +30 дней"', expiry)
        self.assertIn('callback_data=f"adminextend:{tg_id}"', expiry)

    def test_hwid_limit_edit_route_requires_support(self):
        self.assertEqual(required_role_for_callback("admin:u:hwid:101"), "support")

    def test_hwid_limit_is_not_plan_managed(self):
        provisioning = (ROOT / "provisioning.py").read_text(encoding="utf-8")
        self.assertNotIn("limitHwid", provisioning)

    def test_administrator_list_separates_status_and_role(self):
        source = (ROOT / "business_admin.py").read_text(encoding="utf-8")
        view = source.split("async def administrators_list", 1)[1].split(
            '@business_router.callback_query(F.data == "admin:privileges")',
            1,
        )[0]
        for icon in ("👑", "🛡", "🧑‍💻", "👁"):
            self.assertIn(icon, source)
        self.assertIn('"🟢" if rec.enabled else "⛔"', view)
        self.assertIn("ROLE_ICONS.get(rec.role", view)
        self.assertIn(" · отключён", view)
        self.assertIn("Статус: 🟢 включён · ⛔ отключён", view)
        self.assertNotIn("'⚪'", view)

    def test_local_owner_keeps_explicit_source_marker(self):
        source = (ROOT / "business_admin.py").read_text(encoding="utf-8")
        self.assertIn(
            'f"🟢 👑 TG {tg_id} · Owner · локальная конфигурация"',
            source,
        )


if __name__ == "__main__":
    unittest.main()
