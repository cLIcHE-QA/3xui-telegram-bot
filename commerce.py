from __future__ import annotations

import hashlib
import json

from db import CommerceOrderRecord, CommercePaymentRecord, Database, EntitlementRecord, PaymentWebhookEventRecord


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
