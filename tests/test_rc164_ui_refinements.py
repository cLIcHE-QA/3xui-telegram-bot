"""#742–#745: offline-regression статусов, сортировки и контекстных переходов."""
import unittest
from pathlib import Path
from types import SimpleNamespace

from catalog_admin import sort_catalog_plans
from admin_privileges import required_role_for_callback
from node_ui import master_detail_keyboard, node_detail_keyboard


ROOT = Path(__file__).resolve().parents[1]


def plan(id, price, stars, *, enabled=True, currency="RUB"):
    return SimpleNamespace(id=id, price_minor=price, stars_price=stars,
                           rub_price_enabled=enabled, currency=currency)


class Rc164UiTests(unittest.TestCase):
    def test_independent_price_sort_and_missing_last(self):
        items = [plan(4, 0, 5, enabled=False), plan(1, 200, 0),
                 plan(3, 100, 10), plan(2, 100, 1)]
        self.assertEqual([x.id for x in sort_catalog_plans(items, "rub_asc")], [2,3,1,4])
        self.assertEqual([x.id for x in sort_catalog_plans(items, "rub_desc")], [1,2,3,4])
        self.assertEqual([x.id for x in sort_catalog_plans(items, "stars_asc")], [2,4,3,1])
        self.assertEqual([x.id for x in sort_catalog_plans(items, "stars_desc")], [3,4,2,1])
        self.assertEqual([x.id for x in sort_catalog_plans(items, "")], [4,1,3,2])

    def test_saved_sort_requires_admin(self):
        for mode in ("rub_asc", "rub_desc", "stars_asc", "stars_desc", "original"):
            self.assertEqual(required_role_for_callback("admin:plans:save:"+mode), "admin")
        source = (ROOT/"catalog_admin.py").read_text(encoding="utf-8")
        self.assertIn('set_runtime_setting("admin_plans_sort_mode", mode', source)
        self.assertIn('get_runtime_setting("admin_plans_sort_mode", "stars_desc")', source)

    def test_price_callbacks_are_read_only(self):
        for suffix in ("rub_asc", "rub_desc", "stars_asc", "stars_desc"):
            self.assertEqual(required_role_for_callback("admin:plans:"+suffix), "read_only")

    def test_direct_node_shortcuts_preserve_origin(self):
        master = [b.callback_data for row in master_detail_keyboard().inline_keyboard for b in row]
        node = [b.callback_data for row in node_detail_keyboard(17).inline_keyboard for b in row]
        for key, labels in (("m", master), ("n17", node)):
            self.assertIn(f"admin:ver:panel:{key}:i", labels)
            self.assertIn(f"admin:ver:xray:{key}:0:i", labels)
            self.assertEqual(required_role_for_callback(f"admin:ver:panel:{key}:i"), "read_only")
            self.assertEqual(required_role_for_callback(f"admin:ver:xray:{key}:0:i"), "read_only")

    def test_user_list_and_search_have_one_read_only_status_lookup(self):
        source = (ROOT/"advanced_users.py").read_text(encoding="utf-8")
        self.assertIn("async def _user_status_icons(", source)
        self.assertIn("clients = await xui.clients_list()", source)
        self.assertIn("statuses.get(user.email, '🟡')", source)
        self.assertIn("🟢 включён' if enabled else '⚪ отключён", source)

    def test_search_result_renders_3xui_status_not_person_icon(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        search = source.split("async def admin_users_search_message(", 1)[1].split(
            "@advanced_users_router.callback_query", 1
        )[0]
        self.assertIn("statuses = await _user_status_icons(users)", search)
        self.assertIn("statuses.get(user.email, '🟡')", search)
        self.assertNotIn('text=f"👤 {user_label(user, profile)}', search)
        self.assertIn("callback_data=f\"admin:u:{user.telegram_id}\"", search)

    def test_manual_user_filter_and_badges_preserve_status_and_navigation(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        db_source = (ROOT / "db.py").read_text(encoding="utf-8")
        self.assertIn('async def list_live_manual_users(', db_source)
        self.assertIn('async def manual_statuses_for_users(', db_source)
        self.assertIn("m.status IN ('active', 'in_flight', 'unknown')", db_source)
        self.assertIn('WHERE EXISTS (', db_source)
        self.assertIn('for start in range(0, len(ids), 400)', db_source)
        self.assertIn('if status == "active":', source)
        self.assertIn('return " ♾️"', source)
        self.assertIn('return " 🟡♾️"', source)
        self.assertNotIn('return " ♾"', source)
        self.assertNotIn('return " 🟡♾"', source)
        self.assertIn('manual_only: bool = False', source)
        self.assertIn('db.list_live_manual_users() if manual_only else db.list_users()', source)
        self.assertIn('_manual_list_badge(manual_statuses.get(user.telegram_id))', source)
        self.assertIn('statuses = await _user_status_icons(visible)', source)
        self.assertIn('statuses = await _user_status_icons(users)', source)
        self.assertIn('admin:users:manual:page:', source)
        self.assertIn('minimum="read_only"', source)
        self.assertIn('callback_data=f"admin:u:{user.telegram_id}"', source)

    def test_status_is_distinct_from_warning_actions(self):
        for path in ("inbound_admin.py", "business_admin.py", "advanced_users.py"):
            source = (ROOT/path).read_text(encoding="utf-8")
            self.assertIn("⚪", source)
        self.assertIn("⛔ Отключить", (ROOT/"inbound_admin.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
