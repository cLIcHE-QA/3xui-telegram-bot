from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

import aiohttp


class CheckoutError(RuntimeError):
    pass


class CheckoutUnavailable(CheckoutError):
    pass


@dataclass(frozen=True)
class CheckoutRequest:
    order_id: int
    amount_minor: int
    currency: str
    idempotency_key: str


@dataclass(frozen=True)
class CheckoutResult:
    provider_payment_id: str
    checkout_url: str


class CheckoutProvider(Protocol):
    name: str

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutResult: ...


def _validate_checkout_url(url: str) -> str:
    value = str(url or "").strip()
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise CheckoutError("checkout_url must be an absolute HTTPS URL without credentials/fragment")
    return value


class GenericHmacCheckoutProvider:
    """Provider-neutral HTTPS checkout bridge with deterministic idempotency."""

    name = "generic_hmac"

    def __init__(self, endpoint: str, secret: str):
        self.endpoint = _validate_checkout_url(endpoint)
        self.secret = secret

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutResult:
        payload = json.dumps(
            {
                "order_id": int(request.order_id),
                "amount_minor": int(request.amount_minor),
                "currency": str(request.currency).upper(),
                "idempotency_key": request.idempotency_key,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        signature = hmac.new(
            self.secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        timeout = aiohttp.ClientTimeout(total=15)
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": request.idempotency_key,
            "X-Payment-Signature": f"sha256={signature}",
        }
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.endpoint,
                    data=payload,
                    headers=headers,
                    allow_redirects=False,
                ) as response:
                    body = await response.read()
                    if response.status >= 500:
                        raise CheckoutUnavailable(
                            "checkout provider outcome is uncertain; retry only with same idempotency key"
                        )
                    if response.status >= 400:
                        raise CheckoutError(f"checkout provider rejected request: HTTP {response.status}")
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise CheckoutUnavailable(
                "checkout provider outcome is uncertain; retry only with same idempotency key"
            ) from exc

        if len(body) > 64 * 1024:
            raise CheckoutError("checkout provider response is too large")
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CheckoutError("checkout provider returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise CheckoutError("checkout provider response must be an object")

        payment_id = str(data.get("payment_id") or "").strip()
        if not payment_id or len(payment_id) > 160:
            raise CheckoutError("checkout provider returned invalid payment_id")
        checkout_url = _validate_checkout_url(str(data.get("checkout_url") or ""))
        return CheckoutResult(
            provider_payment_id=payment_id,
            checkout_url=checkout_url,
        )
