from __future__ import annotations

import hashlib
import json
import time

from db import CommerceOrderRecord, CommercePaymentRecord, Database, EntitlementRecord, PaymentWebhookEventRecord
from provisioning import ProvisioningEngine, ProvisioningUnknown


ORDER_TRANSITIONS = {
    "created": {"awaiting_payment", "cancelled", "expired"},
    "awaiting_payment": {"paid", "cancelled", "expired"},
    "paid": set(), "cancelled": set(), "expired": set(),
}
PAYMENT_TRANSITIONS = {
    "created": {"pending", "confirmed", "failed", "unknown"},
    "pending": {"confirmed", "failed", "unknown"},
    "unknown": {"confirmed", "failed"},
    "confirmed": {"refunded"},
    "failed": set(), "refunded": set(),
}
ENTITLEMENT_TRANSITIONS = {
    "pending": {"provisioning", "failed"},
    "provisioning": {"active", "failed"},
    "active": {"suspended", "expired"},
    "suspended": {"active", "expired"},
    "expired": set(),
    "failed": {"provisioning"},
}


class CommerceError(RuntimeError):
    pass


class CommerceStateError(CommerceError):
    pass


class CommerceIntegrityError(CommerceError):
    pass


def validate_transition(current: str, target: str, allowed: dict[str, set[str]], *, kind: str) -> None:
    if current == target:
        return
    if target not in allowed.get(current, set()):
        raise CommerceStateError(f"Invalid {kind} transition: {current!r} -> {target!r}.")


def payload_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def safe_event_metadata(value: dict[str, object] | None) -> str:
    if not value:
        return "{}"
    allowed = {key: value[key] for key in ("reason", "method", "test_mode") if key in value}
    return json.dumps(allowed, ensure_ascii=True, separators=(",", ":"))[:2000]


class CommerceService:
    """Persistent v5 commerce primitives; provider adapters authenticate webhooks."""

    def __init__(self, db: Database):
        self.db = db

    async def create_order(self, *, telegram_id: int, plan_id: int, amount_minor: int,
                           currency: str, promo_code_id: int | None = None) -> CommerceOrderRecord:
        order_id = await self.db.create_commerce_order(
            telegram_id=telegram_id, plan_id=plan_id, promo_code_id=promo_code_id,
            amount_minor=amount_minor, currency=currency,
        )
        order = await self.db.get_commerce_order(order_id)
        if order is None:
            raise CommerceIntegrityError("Created order cannot be read back.")
        return order

    async def create_payment(self, *, order_id: int, provider: str,
                             provider_payment_id: str) -> CommercePaymentRecord:
        order = await self.db.get_commerce_order(order_id)
        if order is None:
            raise CommerceIntegrityError("Order does not exist.")
        payment_id = await self.db.create_commerce_payment(
            order_id=order.id, provider=provider, provider_payment_id=provider_payment_id,
            amount_minor=order.amount_minor, currency=order.currency,
        )
        payment = await self.db.get_commerce_payment(payment_id)
        if payment is None:
            raise CommerceIntegrityError("Created payment cannot be read back.")
        return payment

    async def ensure_entitlement(self, order: CommerceOrderRecord) -> tuple[EntitlementRecord, bool]:
        return await self.db.ensure_entitlement_for_order(
            telegram_id=order.telegram_id, order_id=order.id, plan_id=order.plan_id,
        )

    async def record_event(self, *, provider: str, provider_event_id: str, event_type: str,
                           signature_valid: bool, raw_payload: bytes,
                           metadata: dict[str, object] | None = None
                           ) -> tuple[PaymentWebhookEventRecord, bool]:
        event_id, created = await self.db.record_payment_webhook_event(
            provider=provider, provider_event_id=provider_event_id, event_type=event_type,
            signature_valid=signature_valid, payload_sha256=payload_sha256(raw_payload),
            metadata_json=safe_event_metadata(metadata),
        )
        event = await self.db.get_payment_webhook_event(event_id)
        if event is None:
            raise CommerceIntegrityError("Webhook event cannot be read back.")
        return event, created

    async def reconcile_confirmed_payment_event(
        self, event_id: int,
    ) -> tuple[
        PaymentWebhookEventRecord,
        CommercePaymentRecord | None,
        CommerceOrderRecord | None,
        EntitlementRecord | None,
        bool,
    ]:
        event = await self.db.get_payment_webhook_event(event_id)
        if event is None:
            raise CommerceIntegrityError("Webhook event does not exist.")
        if not event.signature_valid:
            raise CommerceIntegrityError("Unauthenticated webhook event cannot be reconciled.")
        if event.event_type != "payment.confirmed":
            raise CommerceIntegrityError("Only payment.confirmed events are reconcilable.")
        if not event.provider_payment_id:
            raise CommerceIntegrityError("Webhook event has no persisted provider payment reference.")
        if event.processing_status == "applied":
            return await self.db.apply_confirmed_payment_event(
                provider=event.provider,
                provider_event_id=event.provider_event_id,
                event_type=event.event_type,
                signature_valid=True,
                payload_sha256=event.payload_sha256,
                metadata_json=event.metadata_json,
                provider_payment_id=event.provider_payment_id,
            )
        if not (
            event.processing_status == "failed"
            and event.result_code == "payment_not_found"
        ):
            raise CommerceStateError(
                f"Webhook event #{event.id} is not in a recoverable state."
            )
        return await self.db.apply_confirmed_payment_event(
            provider=event.provider,
            provider_event_id=event.provider_event_id,
            event_type=event.event_type,
            signature_valid=True,
            payload_sha256=event.payload_sha256,
            metadata_json=event.metadata_json,
            provider_payment_id=event.provider_payment_id,
        )

    async def reconcile_recoverable_payment_events(
        self, *, limit: int = 100,
    ) -> dict[str, int]:
        events = await self.db.list_recoverable_payment_webhook_events(limit=limit)
        applied = 0
        still_missing = 0
        failed = 0
        for event in events:
            try:
                result = await self.reconcile_confirmed_payment_event(event.id)
            except Exception:
                failed += 1
                continue
            if result[0].processing_status == "applied":
                applied += 1
            else:
                still_missing += 1
        return {
            "checked": len(events),
            "applied": applied,
            "still_missing": still_missing,
            "failed": failed,
        }

    async def apply_confirmed_payment_event(
        self, *, provider: str, provider_event_id: str, provider_payment_id: str,
        raw_payload: bytes, signature_valid: bool,
        metadata: dict[str, object] | None = None,
        fail_after_payment_update: bool = False,
    ) -> tuple[
        PaymentWebhookEventRecord,
        CommercePaymentRecord | None,
        CommerceOrderRecord | None,
        EntitlementRecord | None,
        bool,
    ]:
        return await self.db.apply_confirmed_payment_event(
            provider=provider,
            provider_event_id=provider_event_id,
            event_type="payment.confirmed",
            signature_valid=signature_valid,
            payload_sha256=payload_sha256(raw_payload),
            metadata_json=safe_event_metadata(metadata),
            provider_payment_id=provider_payment_id,
            fail_after_payment_update=fail_after_payment_update,
        )



class EntitlementProvisioningService:
    """Bridge paid commerce entitlements into the existing safe provisioning engine."""

    def __init__(self, db: Database, provisioner: ProvisioningEngine):
        self.db = db
        self.provisioner = provisioner

    async def reconcile(self, entitlement_id: int) -> EntitlementRecord:
        entitlement = await self.db.get_entitlement(entitlement_id)
        if entitlement is None:
            raise CommerceIntegrityError("Entitlement does not exist.")
        if entitlement.status == "active":
            return entitlement
        validate_transition(
            entitlement.status, "provisioning",
            ENTITLEMENT_TRANSITIONS, kind="entitlement",
        )
        entitlement = await self.db.transition_entitlement(
            entitlement.id,
            expected_statuses={"pending", "failed"},
            target_status="provisioning",
        )
        try:
            plan = await self.db.get_plan(entitlement.plan_id)
            if plan is None or not plan.active:
                raise CommerceIntegrityError("Entitlement plan does not exist or is inactive.")
            user = await self.db.get(entitlement.telegram_id)
            if user is None:
                raise CommerceIntegrityError(
                    "Customer must have a persistent subscription identity before provisioning."
                )
            await self.db.set_user_plan(entitlement.telegram_id, plan.id)
            result = await self.provisioner.sync_user(
                entitlement.telegram_id,
                strict=False,
                apply_plan_limits=True,
            )
            if result.remaining_missing_ids:
                raise CommerceIntegrityError(
                    "Provisioning finished with desired inbounds still missing."
                )
        except ProvisioningUnknown:
            # Keep the durable state as provisioning: remote outcome is uncertain.
            # A later reconcile must read back through ProvisioningEngine rather
            # than treating the mutation as a definite failure.
            raise
        except Exception:
            await self.db.transition_entitlement(
                entitlement.id,
                expected_statuses={"provisioning"},
                target_status="failed",
            )
            raise

        starts_at = entitlement.starts_at or int(time.time())
        expires_at = 0
        if plan.duration_days:
            expires_at = starts_at + max(0, int(plan.duration_days)) * 86400
        return await self.db.transition_entitlement(
            entitlement.id,
            expected_statuses={"provisioning"},
            target_status="active",
            starts_at=starts_at,
            expires_at=expires_at,
        )
