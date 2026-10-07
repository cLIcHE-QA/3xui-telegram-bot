from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from commerce import CommerceService
from customer_service import CustomerPortalService
from db import Database, UserRecord


class _NoopCustomerProvider:
    async def traffic(self, email: str):
        raise AssertionError("not used")

    async def devices(self, email: str):
        raise AssertionError("not used")


class TelegramStarsCommerceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "bot.sqlite3"
        self.db = Database(str(self.path))
        await self.db.init()
        self.commerce = CommerceService(self.db)
        self.customer = CustomerPortalService(
            self.db,
            self.commerce,
            _NoopCustomerProvider(),
            subscription_url_template="https://sub.example/{sub_id}",
        )
        await self.db.put(
            UserRecord(
                telegram_id=7001,
                email="stars@example.invalid",
                sub_id="stars-sub",
                expiry_time=0,
                created_at=1,
            )
        )
        self.plan_id = await self.db.create_plan(
            name="Stars plan",
            duration_days=30,
            traffic_gb=100,
            ip_limit=2,
            price_minor=49900,
            currency="RUB",
            stars_price=250,
        )

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_stars_order_uses_xtr_and_enters_awaiting_payment(self):
        plan = await self.db.get_plan(self.plan_id)
        order, created = await self.customer.get_or_create_stars_order(
            telegram_id=7001,
            plan=plan,
        )
        self.assertTrue(created)
        self.assertEqual(order.currency, "XTR")
        self.assertEqual(order.amount_minor, 250)
        self.assertEqual(order.status, "awaiting_payment")

        same, created_again = await self.customer.get_or_create_stars_order(
            telegram_id=7001,
            plan=plan,
        )
        self.assertFalse(created_again)
        self.assertEqual(same.id, order.id)

    async def test_stars_order_does_not_reuse_legacy_fiat_quote(self):
        fiat_order, fiat_created = await self.commerce.get_or_create_order(
            telegram_id=7001,
            plan_id=self.plan_id,
            amount_minor=49900,
            currency="RUB",
        )
        self.assertTrue(fiat_created)

        plan = await self.db.get_plan(self.plan_id)
        stars_order, stars_created = await self.customer.get_or_create_stars_order(
            telegram_id=7001,
            plan=plan,
        )

        self.assertTrue(stars_created)
        self.assertNotEqual(stars_order.id, fiat_order.id)
        self.assertEqual(stars_order.currency, "XTR")
        self.assertEqual(stars_order.amount_minor, 250)

    async def test_stars_price_change_creates_new_quote(self):
        plan = await self.db.get_plan(self.plan_id)
        first, first_created = await self.customer.get_or_create_stars_order(
            telegram_id=7001,
            plan=plan,
        )
        self.assertTrue(first_created)
        self.assertEqual(first.amount_minor, 250)

        await self.db.set_plan_stars_price(self.plan_id, 300)
        updated_plan = await self.db.get_plan(self.plan_id)
        second, second_created = await self.customer.get_or_create_stars_order(
            telegram_id=7001,
            plan=updated_plan,
        )

        self.assertTrue(second_created)
        self.assertNotEqual(second.id, first.id)
        self.assertEqual(second.currency, "XTR")
        self.assertEqual(second.amount_minor, 300)

    async def test_confirm_stars_payment_is_atomic_and_idempotent(self):
        plan = await self.db.get_plan(self.plan_id)
        order, _ = await self.customer.get_or_create_stars_order(
            telegram_id=7001,
            plan=plan,
        )
        raw = b"stars:v1:test-charge"

        first = await self.customer.confirm_stars_payment(
            telegram_id=7001,
            order_id=order.id,
            charge_id="tg-charge-1",
            amount=250,
            raw_payload=raw,
        )
        second = await self.customer.confirm_stars_payment(
            telegram_id=7001,
            order_id=order.id,
            charge_id="tg-charge-1",
            amount=250,
            raw_payload=raw,
        )

        first_payment, first_order, first_entitlement, first_created = first
        second_payment, second_order, second_entitlement, second_created = second
        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_payment.id, second_payment.id)
        self.assertEqual(first_order.status, "paid")
        self.assertEqual(second_order.status, "paid")
        self.assertEqual(first_entitlement.id, second_entitlement.id)
        self.assertEqual(first_entitlement.status, "pending")

        with sqlite3.connect(self.path) as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM commerce_payments WHERE provider = 'telegram_stars'"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM entitlements WHERE order_id = ?",
                    (order.id,),
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM payment_webhook_events
                    WHERE provider = 'telegram_stars'
                      AND provider_event_id = 'tg-charge-1'
                      AND processing_status = 'applied'
                    """
                ).fetchone()[0],
                1,
            )

    async def test_stars_confirmation_rejects_wrong_owner_or_amount_without_mutation(self):
        plan = await self.db.get_plan(self.plan_id)
        order, _ = await self.customer.get_or_create_stars_order(
            telegram_id=7001,
            plan=plan,
        )

        with self.assertRaises(RuntimeError):
            await self.customer.confirm_stars_payment(
                telegram_id=9999,
                order_id=order.id,
                charge_id="tg-charge-owner",
                amount=250,
                raw_payload=b"owner",
            )
        with self.assertRaises(RuntimeError):
            await self.customer.confirm_stars_payment(
                telegram_id=7001,
                order_id=order.id,
                charge_id="tg-charge-amount",
                amount=251,
                raw_payload=b"amount",
            )

        with sqlite3.connect(self.path) as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM commerce_payments WHERE provider = 'telegram_stars'"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT status FROM commerce_orders WHERE id = ?",
                    (order.id,),
                ).fetchone()[0],
                "awaiting_payment",
            )

    async def test_stars_price_is_independent_from_fiat_price(self):
        plan = await self.db.get_plan(self.plan_id)
        self.assertEqual(plan.price_minor, 49900)
        self.assertEqual(plan.currency, "RUB")
        self.assertEqual(plan.stars_price, 250)

        await self.db.set_plan_stars_price(self.plan_id, 300)
        updated = await self.db.get_plan(self.plan_id)
        self.assertEqual(updated.price_minor, 49900)
        self.assertEqual(updated.currency, "RUB")
        self.assertEqual(updated.stars_price, 300)


class TelegramStarsUiContractTests(unittest.TestCase):
    def test_client_purchase_uses_native_stars_not_external_checkout_url(self):
        source = (Path(__file__).resolve().parents[1] / "client_access.py").read_text(
            encoding="utf-8"
        )
        for required in (
            'currency="XTR"',
            'provider_token=""',
            "LabeledPrice",
            "pre_checkout_query",
            "successful_payment",
            "telegram_payment_charge_id",
            'Command("paysupport")',
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)
        self.assertNotIn("checkout.payment.checkout_url", source)
        self.assertNotIn("CheckoutUnavailable", source)
        self.assertNotIn("CheckoutError", source)


if __name__ == "__main__":
    unittest.main()
