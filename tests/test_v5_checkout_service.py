from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from checkout_provider import CheckoutRequest, CheckoutResult, CheckoutUnavailable
from checkout_service import CheckoutService
from commerce import CommerceService
from db import Database


class _FakeProvider:
    name = "generic_hmac"

    def __init__(self):
        self.calls: list[CheckoutRequest] = []
        self.fail = False

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutResult:
        self.calls.append(request)
        if self.fail:
            raise CheckoutUnavailable("uncertain")
        return CheckoutResult(
            provider_payment_id=f"pay-{request.order_id}",
            checkout_url=f"https://pay.example/checkout/{request.order_id}",
        )


class CheckoutServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "bot.sqlite3"
        self.db = Database(str(self.path))
        await self.db.init()
        self.commerce = CommerceService(self.db)
        self.provider = _FakeProvider()
        self.checkout = CheckoutService(self.commerce, self.provider)

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_repeated_checkout_reuses_durable_payment_without_provider_recall(self):
        order = await self.commerce.create_order(
            telegram_id=5001,
            plan_id=91,
            amount_minor=12900,
            currency="RUB",
        )

        first = await self.checkout.start(order)
        second = await self.checkout.start(order)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.payment.id, second.payment.id)
        self.assertEqual(first.payment.idempotency_key, f"order:{order.id}")
        self.assertEqual(
            first.payment.checkout_url,
            f"https://pay.example/checkout/{order.id}",
        )
        self.assertEqual(len(self.provider.calls), 1)
        self.assertEqual(
            (await self.db.get_commerce_order(order.id)).status,
            "awaiting_payment",
        )

    async def test_uncertain_provider_outcome_does_not_create_local_payment(self):
        order = await self.commerce.create_order(
            telegram_id=5002,
            plan_id=92,
            amount_minor=9900,
            currency="EUR",
        )
        self.provider.fail = True

        with self.assertRaises(CheckoutUnavailable):
            await self.checkout.start(order)

        self.assertEqual(len(self.provider.calls), 1)
        self.assertEqual(
            self.provider.calls[0].idempotency_key,
            f"order:{order.id}",
        )
        self.assertIsNone(
            await self.commerce.find_checkout_payment(
                provider="generic_hmac",
                idempotency_key=f"order:{order.id}",
            )
        )
        self.assertEqual(
            (await self.db.get_commerce_order(order.id)).status,
            "created",
        )

    async def test_same_idempotency_key_cannot_bind_different_order(self):
        first = await self.commerce.create_order(
            telegram_id=5003,
            plan_id=93,
            amount_minor=1000,
            currency="USD",
        )
        second = await self.commerce.create_order(
            telegram_id=5004,
            plan_id=94,
            amount_minor=1000,
            currency="USD",
        )
        await self.commerce.create_or_get_checkout_payment(
            order_id=first.id,
            provider="generic_hmac",
            provider_payment_id="pay-first",
            checkout_url="https://pay.example/first",
            idempotency_key="stable-key",
        )
        with self.assertRaises(RuntimeError):
            await self.commerce.create_or_get_checkout_payment(
                order_id=second.id,
                provider="generic_hmac",
                provider_payment_id="pay-second",
                checkout_url="https://pay.example/second",
                idempotency_key="stable-key",
            )


if __name__ == "__main__":
    unittest.main()
