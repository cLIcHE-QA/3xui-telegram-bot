from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass

from aiohttp import web

from commerce import CommerceService


MAX_PAYMENT_WEBHOOK_BYTES = 64 * 1024
SIGNATURE_HEADER = "X-Payment-Signature"


class PaymentWebhookError(RuntimeError):
    pass


@dataclass(frozen=True)
class NormalizedPaymentEvent:
    event_id: str
    event_type: str
    payment_id: str
    metadata: dict[str, object]


def verify_hmac_sha256(secret: str, raw_payload: bytes, signature: str) -> bool:
    value = (signature or "").strip()
    if value.lower().startswith("sha256="):
        value = value.split("=", 1)[1].strip()
    if len(value) != 64:
        return False
    try:
        bytes.fromhex(value)
    except ValueError:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, value.lower())


def normalize_payment_event(raw_payload: bytes) -> NormalizedPaymentEvent:
    try:
        payload = json.loads(raw_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PaymentWebhookError("Webhook body must be valid UTF-8 JSON.") from exc
    if not isinstance(payload, dict):
        raise PaymentWebhookError("Webhook body must be a JSON object.")

    event_id = str(payload.get("event_id") or "").strip()
    event_type = str(payload.get("type") or "").strip().lower()
    payment_id = str(payload.get("payment_id") or "").strip()
    if not event_id or len(event_id) > 160:
        raise PaymentWebhookError("event_id is required and must be <= 160 characters.")
    if not event_type or len(event_type) > 64:
        raise PaymentWebhookError("type is required and must be <= 64 characters.")
    if not payment_id or len(payment_id) > 160:
        raise PaymentWebhookError("payment_id is required and must be <= 160 characters.")

    safe_metadata: dict[str, object] = {}
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        for key in ("reason", "method", "test_mode"):
            if key in metadata:
                safe_metadata[key] = metadata[key]

    return NormalizedPaymentEvent(
        event_id=event_id,
        event_type=event_type,
        payment_id=payment_id,
        metadata=safe_metadata,
    )


async def read_bounded_body(request: web.Request, *, max_bytes: int = MAX_PAYMENT_WEBHOOK_BYTES) -> bytes:
    raw_length = (request.headers.get("Content-Length") or "").strip()
    if raw_length:
        try:
            declared = int(raw_length)
        except ValueError as exc:
            raise web.HTTPBadRequest(text="invalid content length\n") from exc
        if declared < 0 or declared > max_bytes:
            raise web.HTTPRequestEntityTooLarge(max_size=max_bytes, actual_size=max(0, declared))

    chunks: list[bytes] = []
    total = 0
    async for chunk in request.content.iter_chunked(16 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise web.HTTPRequestEntityTooLarge(max_size=max_bytes, actual_size=total)
        chunks.append(chunk)
    return b"".join(chunks)


class PaymentWebhookGateway:
    """Authenticated provider ingress for normalized payment.confirmed events."""

    def __init__(
        self,
        service: CommerceService,
        *,
        enabled: bool,
        provider: str,
        secret: str,
    ):
        self.service = service
        self.enabled = bool(enabled)
        self.provider = str(provider).strip().lower()
        self.secret = str(secret)

    async def handle(self, request: web.Request) -> web.Response:
        if not self.enabled:
            raise web.HTTPNotFound()

        provider = (request.match_info.get("provider") or "").strip().lower()
        if provider != self.provider:
            raise web.HTTPNotFound()

        raw_payload = await read_bounded_body(request)
        try:
            event = normalize_payment_event(raw_payload)
        except PaymentWebhookError as exc:
            raise web.HTTPBadRequest(text=f"{exc}\n")

        signature_valid = verify_hmac_sha256(
            self.secret,
            raw_payload,
            request.headers.get(SIGNATURE_HEADER, ""),
        )

        if event.event_type != "payment.confirmed":
            journal, _ = await self.service.record_event(
                provider=self.provider,
                provider_event_id=event.event_id,
                event_type=event.event_type,
                signature_valid=signature_valid,
                raw_payload=raw_payload,
                metadata={**event.metadata, "reason": "unsupported_event_type"},
            )
            await self.service.db.finalize_payment_webhook_event(
                journal.id,
                processing_status="ignored",
                result_code=(
                    "unsupported_event_type" if signature_valid else "invalid_signature"
                ),
            )
            if not signature_valid:
                raise web.HTTPUnauthorized(text="invalid signature\n")
            raise web.HTTPUnprocessableEntity(text="unsupported event type\n")

        webhook, payment, order, entitlement, created = (
            await self.service.apply_confirmed_payment_event(
                provider=self.provider,
                provider_event_id=event.event_id,
                provider_payment_id=event.payment_id,
                raw_payload=raw_payload,
                signature_valid=signature_valid,
                metadata=event.metadata,
            )
        )

        if not signature_valid:
            raise web.HTTPUnauthorized(text="invalid signature\n")

        if webhook.processing_status == "failed":
            return web.json_response(
                {
                    "ok": False,
                    "event_id": event.event_id,
                    "status": webhook.processing_status,
                    "result": webhook.result_code,
                },
                status=409,
            )

        return web.json_response(
            {
                "ok": True,
                "event_id": event.event_id,
                "status": webhook.processing_status,
                "duplicate": not created,
                "payment_id": payment.id if payment else None,
                "order_id": order.id if order else None,
                "entitlement_id": entitlement.id if entitlement else None,
            }
        )
