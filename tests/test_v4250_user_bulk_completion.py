from __future__ import annotations

from pathlib import Path
import unittest

from admin_privileges import required_role_for_callback


ROOT = Path(__file__).resolve().parents[1]


class V4250UserBulkCompletionTests(unittest.TestCase):
    def test_bulk_completion_callbacks_require_support(self):
        callbacks = (
            "admin:bulk:plan",
            "admin:bulk:plan:7",
            "admin:bulk:runplan:7",
            "admin:bulk:group",
            "admin:bulk:group:4",
            "admin:bulk:rungroup:4",
            "admin:bulk:expiry",
            "admin:bulk:traffic",
            "admin:bulk:runexpiry",
            "admin:bulk:runtraffic",
            "admin:bulk:input-cancel",
            "admin:bulk:ask:extend30",
            "admin:bulk:ask:enable",
            "admin:bulk:ask:disable",
            "admin:bulk:ask:reset",
            "admin:bulk:ask:reconcile",
        )
        for callback in callbacks:
            with self.subTest(callback=callback):
                self.assertEqual(required_role_for_callback(callback), "support")

    def test_bulk_actions_cover_roadmap_and_confirm_simple_mutations(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        actions = source.split("async def bulk_actions", 1)[1].split(
            "async def bulk_ask", 1
        )[0]
        for label in (
            "💎 Назначить тариф",
            "🗂 Назначить группу",
            "➕ +30 дней",
            "📅 Установить срок",
            "📦 Лимит трафика",
            "🚀 Согласовать",
            "✅ Включить",
            "⛔ Отключить",
            "♻️ Сбросить трафик",
        ):
            self.assertIn(label, actions)
        self.assertIn('callback_data="admin:bulk:ask:enable"', actions)
        self.assertIn('callback_data="admin:bulk:ask:disable"', actions)
        self.assertIn('callback_data="admin:bulk:ask:reset"', actions)
        self.assertIn('callback_data="admin:bulk:ask:reconcile"', actions)
        self.assertNotIn("strict", actions.lower())

    def test_bulk_ask_is_non_mutating_and_shows_selected_count(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        ask = source.split("async def bulk_ask", 1)[1].split(
            "async def bulk_plan_menu", 1
        )[0]
        self.assertIn("Пользователей: {len(records)}", ask)
        self.assertNotIn("bulk_enable_clients(", ask)
        self.assertNotIn("bulk_disable_clients(", ask)
        self.assertNotIn("bulk_reset_traffic(", ask)
        self.assertNotIn("provision_many(", ask)

    def test_plan_and_group_bulk_assignment_do_not_hide_remote_provisioning(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        plan = source.split("async def bulk_run_plan", 1)[1].split(
            "async def bulk_run_group", 1
        )[0]
        self.assertIn("db.set_user_plan", plan)
        self.assertNotIn("xui.", plan)
        self.assertNotIn("provisioner.", plan)

        group = source.split("async def bulk_run_group", 1)[1].split(
            "async def bulk_run_expiry", 1
        )[0]
        self.assertIn("db.set_user_server_group", group)
        self.assertNotIn("xui.", group)
        self.assertNotIn("provisioner.", group)

    def test_custom_expiry_and_traffic_use_preview_before_run(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        expiry_input = source.split("async def bulk_expiry_input", 1)[1].split(
            "async def bulk_traffic_start", 1
        )[0]
        self.assertIn('_bulk_confirmation_keyboard("admin:bulk:runexpiry")', expiry_input)
        self.assertIn("end_of_day_timestamp", expiry_input)

        traffic_input = source.split("async def bulk_traffic_input", 1)[1].split(
            "async def bulk_input_cancel", 1
        )[0]
        self.assertIn('_bulk_confirmation_keyboard("admin:bulk:runtraffic")', traffic_input)
        self.assertIn("100000", traffic_input)

    def test_bulk_result_audit_does_not_store_email_list(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        result = source.split("async def _bulk_result", 1)[1].split(
            "async def bulk_run_plan", 1
        )[0]
        self.assertIn('target_id=str(ok + len(failed))', result)
        self.assertIn('details=details', result)
        self.assertNotIn("email", result.lower())


if __name__ == "__main__":
    unittest.main()
