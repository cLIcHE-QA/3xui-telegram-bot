import sqlite3
import tempfile
import unittest
from pathlib import Path

from commerce import (
    ENTITLEMENT_TRANSITIONS,
    ORDER_TRANSITIONS,
    PAYMENT_TRANSITIONS,
    CommerceService,
    EntitlementProvisioningService,
    CommerceStateError,
    payload_sha256,
    validate_transition,
)
from db import Database, UserRecord
from db_migrations import CURRENT_SCHEMA_VERSION, current_schema_version
from provisioning import ProvisioningResult, ProvisioningUnknown


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

    async def test_confirmed_event_atomically_pays_order_and_creates_one_entitlement(self):
        order = await self.service.create_order(
            telegram_id=1002, plan_id=8, amount_minor=59900, currency="RUB",
        )
        payment = await self.service.create_payment(
            order_id=order.id, provider="test", provider_payment_id="pay-confirm-1",
        )
        waiting = await self.db.get_commerce_order(order.id)
        self.assertEqual(waiting.status, "awaiting_payment")

        event, confirmed, paid, entitlement, created = (
            await self.service.apply_confirmed_payment_event(
                provider="test", provider_event_id="evt-confirm-1",
                provider_payment_id="pay-confirm-1",
                raw_payload=b'{"status":"confirmed"}', signature_valid=True,
            )
        )
        self.assertTrue(created)
        self.assertEqual(event.processing_status, "applied")
        self.assertEqual(confirmed.id, payment.id)
        self.assertEqual(confirmed.status, "confirmed")
        self.assertEqual(paid.status, "paid")
        self.assertEqual(entitlement.order_id, order.id)
        self.assertEqual(entitlement.status, "pending")

        duplicate = await self.service.apply_confirmed_payment_event(
            provider="test", provider_event_id="evt-confirm-1",
            provider_payment_id="pay-confirm-1",
            raw_payload=b'{"status":"confirmed"}', signature_valid=True,
        )
        self.assertFalse(duplicate[4])
        self.assertEqual(duplicate[3].id, entitlement.id)
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM entitlements WHERE order_id = ?",
                    (order.id,),
                ).fetchone()[0],
                1,
            )

    async def test_invalid_signature_is_journaled_but_never_changes_financial_state(self):
        order = await self.service.create_order(
            telegram_id=1003, plan_id=9, amount_minor=69900, currency="RUB",
        )
        payment = await self.service.create_payment(
            order_id=order.id, provider="test", provider_payment_id="pay-invalid-signature",
        )
        event, changed_payment, changed_order, entitlement, _ = (
            await self.service.apply_confirmed_payment_event(
                provider="test", provider_event_id="evt-invalid-signature",
                provider_payment_id="pay-invalid-signature",
                raw_payload=b"invalid", signature_valid=False,
            )
        )
        self.assertEqual(event.processing_status, "ignored")
        self.assertEqual(event.result_code, "invalid_signature")
        self.assertIsNone(changed_payment)
        self.assertIsNone(changed_order)
        self.assertIsNone(entitlement)
        self.assertEqual((await self.db.get_commerce_payment(payment.id)).status, "created")
        self.assertEqual((await self.db.get_commerce_order(order.id)).status, "awaiting_payment")

    async def test_transaction_rolls_back_crash_between_payment_and_entitlement(self):
        order = await self.service.create_order(
            telegram_id=1004, plan_id=10, amount_minor=79900, currency="RUB",
        )
        payment = await self.service.create_payment(
            order_id=order.id, provider="test", provider_payment_id="pay-crash",
        )
        with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
            await self.service.apply_confirmed_payment_event(
                provider="test", provider_event_id="evt-crash",
                provider_payment_id="pay-crash", raw_payload=b"confirmed",
                signature_valid=True, fail_after_payment_update=True,
            )

        self.assertEqual((await self.db.get_commerce_payment(payment.id)).status, "created")
        self.assertEqual((await self.db.get_commerce_order(order.id)).status, "awaiting_payment")
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM payment_webhook_events WHERE provider_event_id = 'evt-crash'"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM entitlements WHERE order_id = ?",
                    (order.id,),
                ).fetchone()[0],
                0,
            )

        restarted = CommerceService(Database(str(self.path)))
        event, confirmed, paid, entitlement, created = (
            await restarted.apply_confirmed_payment_event(
                provider="test", provider_event_id="evt-crash",
                provider_payment_id="pay-crash", raw_payload=b"confirmed",
                signature_valid=True,
            )
        )
        self.assertTrue(created)
        self.assertEqual(event.processing_status, "applied")
        self.assertEqual(confirmed.status, "confirmed")
        self.assertEqual(paid.status, "paid")
        self.assertIsNotNone(entitlement)

    async def test_duplicate_event_id_with_different_payload_fails_closed(self):
        order = await self.service.create_order(
            telegram_id=1005, plan_id=11, amount_minor=89900, currency="RUB",
        )
        await self.service.create_payment(
            order_id=order.id, provider="test", provider_payment_id="pay-reuse",
        )
        await self.service.apply_confirmed_payment_event(
            provider="test", provider_event_id="evt-reuse",
            provider_payment_id="pay-reuse", raw_payload=b"first",
            signature_valid=True,
        )
        with self.assertRaisesRegex(RuntimeError, "reused with different content"):
            await self.service.apply_confirmed_payment_event(
                provider="test", provider_event_id="evt-reuse",
                provider_payment_id="pay-reuse", raw_payload=b"second",
                signature_valid=True,
            )

    async def test_entitlement_reconcile_activates_through_existing_provisioner(self):
        plan_id = await self.db.create_plan(
            name="Commerce plan", duration_days=30, traffic_gb=100,
            ip_limit=2, price_minor=9900, currency="RUB",
        )
        await self.db.put(UserRecord(
            telegram_id=2001, email="tg_2001", sub_id="stable-sub",
            expiry_time=0, created_at=1,
        ))
        order = await self.service.create_order(
            telegram_id=2001, plan_id=plan_id, amount_minor=9900, currency="RUB",
        )
        payment = await self.service.create_payment(
            order_id=order.id, provider="test", provider_payment_id="pay-provision",
        )
        _, _, _, entitlement, _ = await self.service.apply_confirmed_payment_event(
            provider="test", provider_event_id="evt-provision",
            provider_payment_id=payment.provider_payment_id,
            raw_payload=b"confirmed", signature_valid=True,
        )

        class StubProvisioner:
            def __init__(self):
                self.calls = 0
            async def sync_user(self, telegram_id, *, strict=False, apply_plan_limits=False):
                self.calls += 1
                self.telegram_id = telegram_id
                self.strict = strict
                self.apply_plan_limits = apply_plan_limits
                return ProvisioningResult(
                    policy=None, current_ids=[1], attached_ids=[1], detached_ids=[],
                    remaining_missing_ids=[], extra_ids=[], limits_applied=True,
                )

        stub = StubProvisioner()
        bridge = EntitlementProvisioningService(self.db, stub)
        active = await bridge.reconcile(entitlement.id)
        self.assertEqual(active.status, "active")
        self.assertGreater(active.starts_at, 0)
        self.assertGreater(active.expires_at, active.starts_at)
        self.assertEqual(stub.calls, 1)
        self.assertTrue(stub.apply_plan_limits)

        again = await bridge.reconcile(entitlement.id)
        self.assertEqual(again.id, active.id)
        self.assertEqual(stub.calls, 1)

    async def test_entitlement_provisioning_failure_does_not_rollback_payment(self):
        plan_id = await self.db.create_plan(
            name="Failure plan", duration_days=30, traffic_gb=10,
            ip_limit=1, price_minor=4900, currency="RUB",
        )
        await self.db.put(UserRecord(
            telegram_id=2002, email="tg_2002", sub_id="stable-sub-2",
            expiry_time=0, created_at=1,
        ))
        order = await self.service.create_order(
            telegram_id=2002, plan_id=plan_id, amount_minor=4900, currency="RUB",
        )
        payment = await self.service.create_payment(
            order_id=order.id, provider="test", provider_payment_id="pay-fail",
        )
        _, _, _, entitlement, _ = await self.service.apply_confirmed_payment_event(
            provider="test", provider_event_id="evt-fail",
            provider_payment_id=payment.provider_payment_id,
            raw_payload=b"confirmed", signature_valid=True,
        )

        class FailingProvisioner:
            async def sync_user(self, *args, **kwargs):
                raise RuntimeError("remote rejected")

        bridge = EntitlementProvisioningService(self.db, FailingProvisioner())
        with self.assertRaisesRegex(RuntimeError, "remote rejected"):
            await bridge.reconcile(entitlement.id)
        self.assertEqual((await self.db.get_entitlement(entitlement.id)).status, "failed")
        self.assertEqual((await self.db.get_commerce_payment(payment.id)).status, "confirmed")
        self.assertEqual((await self.db.get_commerce_order(order.id)).status, "paid")

    async def test_unknown_provisioning_outcome_stays_provisioning_for_readback_recovery(self):
        plan_id = await self.db.create_plan(
            name="Unknown plan", duration_days=30, traffic_gb=10,
            ip_limit=1, price_minor=5900, currency="RUB",
        )
        await self.db.put(UserRecord(
            telegram_id=2003, email="tg_2003", sub_id="stable-sub-3",
            expiry_time=0, created_at=1,
        ))
        order = await self.service.create_order(
            telegram_id=2003, plan_id=plan_id, amount_minor=5900, currency="RUB",
        )
        payment = await self.service.create_payment(
            order_id=order.id, provider="test", provider_payment_id="pay-unknown",
        )
        _, _, _, entitlement, _ = await self.service.apply_confirmed_payment_event(
            provider="test", provider_event_id="evt-unknown",
            provider_payment_id=payment.provider_payment_id,
            raw_payload=b"confirmed", signature_valid=True,
        )

        class UnknownProvisioner:
            async def sync_user(self, *args, **kwargs):
                raise ProvisioningUnknown("attach: outcome=unknown")

        bridge = EntitlementProvisioningService(self.db, UnknownProvisioner())
        with self.assertRaises(ProvisioningUnknown):
            await bridge.reconcile(entitlement.id)
        self.assertEqual(
            (await self.db.get_entitlement(entitlement.id)).status,
            "provisioning",
        )
        self.assertEqual((await self.db.get_commerce_payment(payment.id)).status, "confirmed")

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
