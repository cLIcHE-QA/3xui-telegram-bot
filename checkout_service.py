from __future__ import annotations

from dataclasses import dataclass

from checkout_provider import CheckoutProvider, CheckoutRequest, CheckoutResult
from commerce import CommerceService
from db import CommerceOrderRecord, CommercePaymentRecord


@dataclass(frozen=True)
class CheckoutSession:
    order: CommerceOrderRecord
    payment: CommercePaymentRecord
    created: bool


class CheckoutService:
    """Idempotent customer checkout orchestration without provider-specific UI logic."""

    def __init__(self, commerce: CommerceService, provider: CheckoutProvider):
        self.commerce = commerce
        self.provider = provider

    async def start(self, order: CommerceOrderRecord) -> CheckoutSession:
        idempotency_key = f"order:{int(order.id)}"
        existing = await self.commerce.find_checkout_payment(
            provider=self.provider.name,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            return CheckoutSession(order=order, payment=existing, created=False)

        result: CheckoutResult = await self.provider.create_checkout(
            CheckoutRequest(
                order_id=order.id,
                amount_minor=order.amount_minor,
                currency=order.currency,
                idempotency_key=idempotency_key,
            )
        )
        payment, created = await self.commerce.create_or_get_checkout_payment(
            order_id=order.id,
            provider=self.provider.name,
            provider_payment_id=result.provider_payment_id,
            checkout_url=result.checkout_url,
            idempotency_key=idempotency_key,
        )
        return CheckoutSession(order=order, payment=payment, created=created)
