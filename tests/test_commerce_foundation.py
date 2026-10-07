import sqlite3
import tempfile
import unittest
from pathlib import Path

from commerce import (
    ENTITLEMENT_TRANSITIONS,
    ORDER_TRANSITIONS,
    PAYMENT_TRANSITIONS,
    CommerceService,
    CommerceStateError,
    payload_sha256,
    validate_transition,
)
from db import Database
from db_migrations import CURRENT_SCHEMA_VERSION, current_schema_version


class CommerceFoundationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "bot.sqlite3"
        self.db = Database(str(self.path))
        await self.db.init()
        self.service = CommerceService(self.db)

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_schema_v6_contains_separate_commerce_tables(self):
        self.assertEqual(CURRENT_SCHEMA_VERSION, 6)
        self.assertEqual(await current_schema_version(str(self.path)), 6)
        with sqlite3.connect(self.path) as conn:
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
        self.assertTrue({
            "commerce_orders", "commerce_payments",
            "payment_webhook_events", "entitlements",
        }.issubset(tables))

    async def test_legacy_admin_payments_table_is_unchanged(self):
        with sqlite3.connect(self.path) as conn:
            columns = [row[1] for row in conn.execute(
                'PRAGMA table_info("payments")'
            ).fetchall()]
        self.assertEqual(columns, [
            "id", "telegram_id", "plan_id", "amount_minor", "currency", "status",
            "provider", "external_id", "note", "created_by", "created_at",
            "updated_at", "paid_at",
        ])

    async def test_order_payment_and_entitlement_use_persistent_identity(self):
        order = await self.service.create_order(
            telegram_id=1001, plan_id=7, amount_minor=49900, currency="rub",
        )
        self.assertEqual(order.status, "created")
        self.assertEqual(order.currency, "RUB")

        payment = await self.service.create_payment(
            order_id=order.id, provider="test", provider_payment_id="pay-1",
        )
        self.assertEqual(payment.order_id, order.id)
        self.assertEqual(payment.amount_minor, order.amount_minor)

        entitlement, created = await self.service.ensure_entitlement(order)
        self.assertTrue(created)
        again, created_again = await self.service.ensure_entitlement(order)
        self.assertFalse(created_again)
        self.assertEqual(again.id, entitlement.id)

    async def test_webhook_journal_is_idempotent_and_does_not_store_raw_payload(self):
        raw = b'{"card":"4111111111111111","secret":"never-store"}'
        first, created = await self.service.record_event(
            provider="test", provider_event_id="evt-1", event_type="payment.confirmed",
            signature_valid=True, raw_payload=raw,
            metadata={"reason": "ok", "secret": "drop-me"},
        )
        second, created_again = await self.service.record_event(
            provider="test", provider_event_id="evt-1", event_type="payment.confirmed",
            signature_valid=True, raw_payload=raw,
        )
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.id, second.id)
        self.assertEqual(first.payload_sha256, payload_sha256(raw))
        self.assertNotIn("411111", first.metadata_json)
        self.assertNotIn("drop-me", first.metadata_json)

    async def test_state_machine_rejects_unsafe_transitions(self):
        validate_transition("created", "awaiting_payment", ORDER_TRANSITIONS, kind="order")
        validate_transition("unknown", "confirmed", PAYMENT_TRANSITIONS, kind="payment")
        validate_transition("failed", "provisioning", ENTITLEMENT_TRANSITIONS, kind="entitlement")
        with self.assertRaises(CommerceStateError):
            validate_transition("paid", "created", ORDER_TRANSITIONS, kind="order")
        with self.assertRaises(CommerceStateError):
            validate_transition("confirmed", "pending", PAYMENT_TRANSITIONS, kind="payment")


if __name__ == "__main__":
    unittest.main()
