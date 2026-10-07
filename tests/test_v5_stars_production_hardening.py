import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from stars_refund import run_stars_refund
from commerce import CommerceService
from db import Database, UserRecord
from db_migrations import CURRENT_SCHEMA_VERSION


class StarsProductionHardeningTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "bot.sqlite3"))
        await self.db.init()
        self.service = CommerceService(self.db)
        await self.db.create_plan(
            name="Stars", duration_days=30, traffic_gb=100, ip_limit=5,
            price_minor=99900, currency="RUB", server_group_id=None,
        )
        plan = (await self.db.list_plans())[0]
        await self.db.set_plan_stars_price(plan.id, 250)
        self.plan = await self.db.get_plan(plan.id)
        await self.db.put(UserRecord(
            telegram_id=1001, email="u@example", sub_id="sub",
            expiry_time=0, created_at=1,
        ))

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def _confirmed_payment(self):
        order, _ = await self.service.get_or_create_order(
            telegram_id=1001, plan_id=self.plan.id,
            amount_minor=250, currency="XTR",
        )
        order = await self.service.mark_order_awaiting_payment(order.id)
        payment, _, _, _ = await self.service.confirm_telegram_stars_payment(
            order_id=order.id, telegram_id=1001, charge_id="charge-1",
            amount=250, raw_payload=b"paid",
        )
        return payment

    async def test_schema_v10_and_terms_acceptance_are_persistent(self):
        self.assertEqual(CURRENT_SCHEMA_VERSION, 10)
        self.assertFalse(await self.db.has_customer_accepted_terms(
            telegram_id=1001, terms_version="terms-v1",
        ))
        await self.db.accept_customer_terms(
            telegram_id=1001, terms_version="terms-v1",
        )
        self.assertTrue(await self.db.has_customer_accepted_terms(
            telegram_id=1001, terms_version="terms-v1",
        ))

    async def test_successful_refund_marks_payment_refunded(self):
        payment = await self._confirmed_payment()
        bot = AsyncMock()
        op = await run_stars_refund(self.db, bot, payment_id=payment.id, requested_by=77)
        self.assertEqual(op.status, "success")
        bot.refund_star_payment.assert_awaited_once_with(
            user_id=1001,
            telegram_payment_charge_id="charge-1",
        )
        updated = await self.db.get_commerce_payment(payment.id)
        self.assertEqual(updated.status, "refunded")

    async def test_unknown_refund_is_not_replayed(self):
        payment = await self._confirmed_payment()
        bot = AsyncMock()
        bot.refund_star_payment.side_effect = OSError("connection lost")
        first = await run_stars_refund(self.db, bot, payment_id=payment.id, requested_by=77)
        self.assertEqual(first.status, "unknown")
        second = await run_stars_refund(self.db, bot, payment_id=payment.id, requested_by=77)
        self.assertEqual(second.status, "unknown")
        self.assertEqual(bot.refund_star_payment.await_count, 1)
        updated = await self.db.get_commerce_payment(payment.id)
        self.assertEqual(updated.status, "confirmed")


if __name__ == "__main__":
    unittest.main()
