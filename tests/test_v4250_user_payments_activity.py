from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from admin_privileges import required_role_for_callback
from db import Database


ROOT = Path(__file__).resolve().parents[1]


class V4250UserPaymentsActivityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "bot.sqlite3"))
        await self.db.init()

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_user_payment_queries_are_scoped_by_telegram_id(self):
        first = await self.db.create_payment(
            telegram_id=101, plan_id=None, amount_minor=1500, currency="RUB",
            status="paid", provider="manual",
        )
        await self.db.create_payment(
            telegram_id=202, plan_id=None, amount_minor=9900, currency="USD",
            status="paid", provider="manual",
        )
        await self.db.create_payment(
            telegram_id=101, plan_id=None, amount_minor=500, currency="RUB",
            status="pending", provider="manual",
        )
        items = await self.db.list_user_payments(101, limit=20)
        self.assertEqual({item.telegram_id for item in items}, {101})
        self.assertEqual(await self.db.count_user_payments(101), 2)
        self.assertEqual(await self.db.count_user_payments_by_status(101, "paid"), 1)
        self.assertEqual(await self.db.get_user_payment(101, first), items[-1])
        self.assertIsNone(await self.db.get_user_payment(202, first))
        self.assertEqual(await self.db.paid_user_totals_by_currency(101), {"RUB": 1500})

    async def test_user_audit_queries_match_only_technical_identity(self):
        await self.db.add_audit(
            actor_id=1, action="user.plan.set", target_type="user",
            target_id="tg_101", details="plan=2",
        )
        await self.db.add_audit(
            actor_id=1, action="user.expiry.set", target_type="user",
            target_id="101", details="expiry=1",
        )
        await self.db.add_audit(
            actor_id=1, action="user.plan.set", target_type="user",
            target_id="tg_202", details="plan=3",
        )
        rows = await self.db.list_user_audit(101, "tg_101", limit=20)
        self.assertEqual(len(rows), 2)
        self.assertEqual(await self.db.count_user_audit(101, "tg_101"), 2)
        self.assertTrue(all(item.target_id in {"tg_101", "101"} for item in rows))

    def test_user_payment_and_activity_callbacks_have_separate_privileges(self):
        self.assertEqual(required_role_for_callback("admin:u:payments:101"), "read_only")
        self.assertEqual(required_role_for_callback("admin:u:payments:101:8"), "read_only")
        self.assertEqual(required_role_for_callback("admin:u:payment:101:7"), "read_only")
        self.assertEqual(required_role_for_callback("admin:u:activity:101"), "read_only")
        self.assertEqual(required_role_for_callback("admin:u:activity:101:10"), "read_only")

    def test_user_card_exposes_payments_and_activity_without_financial_mutations(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        self.assertIn('text="💳 Платежи"', source)
        self.assertIn('callback_data=f"admin:u:payments:{tg_id}"', source)
        self.assertIn('text="🧾 Активность"', source)
        self.assertIn('callback_data=f"admin:u:activity:{tg_id}"', source)
        payment_view = source.split("async def _user_payments_view", 1)[1].split(
            "@advanced_users_router.callback_query(F.data.regexp(r\"^admin:u:payment:", 1
        )[0]
        self.assertNotIn("create_payment(", payment_view)
        self.assertNotIn("set_payment_status(", payment_view)

    def test_sensitive_audit_details_are_redacted(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        self.assertIn(
            'SENSITIVE_AUDIT_ACTIONS = {"user.subscription.rotate", "user.device.delete"}',
            source,
        )
        self.assertIn(
            'return "Подробности скрыты для защиты credentials/device identity."',
            source,
        )


if __name__ == "__main__":
    unittest.main()
