from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aiohttp import web

from commerce import CommerceService
from config import load_settings
from db import Database
from payment_webhook import (
    MAX_PAYMENT_WEBHOOK_BYTES,
    PaymentWebhookError,
    PaymentWebhookGateway,
    normalize_payment_event,
    read_bounded_body,
    verify_hmac_sha256,
)


class _FakeContent:
    def __init__(self, body: bytes):
        self.body = body

    async def iter_chunked(self, size: int):
        for offset in range(0, len(self.body), max(1, size)):
            yield self.body[offset:offset + size]


class _FakeRequest:
    def __init__(
        self,
        body: bytes,
        *,
        provider: str = "generic_hmac",
        signature: str = "",
        content_length: int | None = None,
    ):
        self.match_info = {"provider": provider}
        self.headers = {"X-Payment-Signature": signature}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)
        self.content = _FakeContent(body)


def _signature(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


class PaymentWebhookConfigTests(unittest.TestCase):
    def base_env(self) -> dict[str, str]:
        return {
            "BOT_TOKEN": "123456789:offline-test-token",
            "PANEL_URL": "https://panel.example.invalid/base",
            "PANEL_API_TOKEN": "offline-panel-token",
            "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/{sub_id}",
            "ALLOWED_TELEGRAM_IDS": "1",
            "ADMIN_TELEGRAM_IDS": "1",
            "NODE_BACKUP_TARGETS": "",
            "HOST_CONTROL_TARGETS": "",
        }

    def test_webhook_is_disabled_by_default(self):
        with patch.dict(os.environ, self.base_env(), clear=True):
            settings = load_settings()
        self.assertFalse(settings.payment_webhook_enabled)
        self.assertEqual(settings.payment_webhook_provider, "generic_hmac")
        self.assertEqual(settings.payment_webhook_secret, "")

    def test_enabled_webhook_requires_independent_strong_secret(self):
        env = self.base_env()
        env.update({
            "PAYMENT_WEBHOOK_ENABLED": "true",
            "PAYMENT_WEBHOOK_SECRET": "short",
        })
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(RuntimeError, "at least 32 bytes"):
                load_settings()

    def test_enabled_webhook_accepts_bounded_provider_name_and_secret(self):
        env = self.base_env()
        env.update({
            "PAYMENT_WEBHOOK_ENABLED": "true",
            "PAYMENT_WEBHOOK_PROVIDER": "generic_hmac",
            "PAYMENT_WEBHOOK_SECRET": "w" * 48,
        })
        with patch.dict(os.environ, env, clear=True):
            settings = load_settings()
        self.assertTrue(settings.payment_webhook_enabled)
        self.assertEqual(settings.payment_webhook_provider, "generic_hmac")
        self.assertEqual(settings.payment_webhook_secret, "w" * 48)


class PaymentWebhookGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "bot.sqlite3"
        self.db = Database(str(self.path))
        await self.db.init()
        self.service = CommerceService(self.db)
        self.secret = "s" * 48
        self.gateway = PaymentWebhookGateway(
            self.service,
            enabled=True,
            provider="generic_hmac",
            secret=self.secret,
        )

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def _payment(self, suffix: str):
        order = await self.service.create_order(
            telegram_id=3001,
            plan_id=77,
            amount_minor=12900,
            currency="RUB",
        )
        payment = await self.service.create_payment(
            order_id=order.id,
            provider="generic_hmac",
            provider_payment_id=f"pay-{suffix}",
        )
        return order, payment

    def test_hmac_verification_supports_plain_and_prefixed_hex(self):
        body = b'{"hello":"world"}'
        signature = _signature(self.secret, body)
        self.assertTrue(verify_hmac_sha256(self.secret, body, signature))
        self.assertTrue(
            verify_hmac_sha256(self.secret, body, f"sha256={signature}")
        )
        self.assertFalse(verify_hmac_sha256(self.secret, body, "00" * 32))

    def test_normalization_is_strict_and_keeps_only_safe_metadata(self):
        event = normalize_payment_event(json.dumps({
            "event_id": "evt-1",
            "type": "PAYMENT.CONFIRMED",
            "payment_id": "pay-1",
            "metadata": {
                "method": "card",
                "test_mode": True,
                "secret": "must-not-pass",
            },
        }).encode())
        self.assertEqual(event.event_type, "payment.confirmed")
        self.assertEqual(event.metadata, {"method": "card", "test_mode": True})
        with self.assertRaises(PaymentWebhookError):
            normalize_payment_event(b'{"event_id":""}')

    async def test_valid_confirmed_webhook_applies_and_duplicate_is_idempotent(self):
        order, payment = await self._payment("ok")
        body = json.dumps({
            "event_id": "evt-ok",
            "type": "payment.confirmed",
            "payment_id": payment.provider_payment_id,
            "metadata": {"method": "card"},
        }, separators=(",", ":")).encode()
        request = _FakeRequest(body, signature=_signature(self.secret, body))
        response = await self.gateway.handle(request)
        payload = json.loads(response.text)
        self.assertEqual(response.status, 200)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["duplicate"])
        self.assertEqual((await self.db.get_commerce_payment(payment.id)).status, "confirmed")
        self.assertEqual((await self.db.get_commerce_order(order.id)).status, "paid")

        duplicate = await self.gateway.handle(
            _FakeRequest(body, signature=_signature(self.secret, body))
        )
        duplicate_payload = json.loads(duplicate.text)
        self.assertTrue(duplicate_payload["duplicate"])
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM entitlements WHERE order_id = ?",
                    (order.id,),
                ).fetchone()[0],
                1,
            )

    async def test_invalid_signature_is_journaled_without_finance_mutation(self):
        order, payment = await self._payment("bad-signature")
        body = json.dumps({
            "event_id": "evt-bad-signature",
            "type": "payment.confirmed",
            "payment_id": payment.provider_payment_id,
        }, separators=(",", ":")).encode()
        with self.assertRaises(web.HTTPUnauthorized):
            await self.gateway.handle(
                _FakeRequest(body, signature="00" * 32)
            )

        self.assertEqual((await self.db.get_commerce_payment(payment.id)).status, "created")
        self.assertEqual((await self.db.get_commerce_order(order.id)).status, "awaiting_payment")
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                """
                SELECT processing_status, result_code, signature_valid
                FROM payment_webhook_events WHERE provider_event_id = ?
                """,
                ("evt-bad-signature",),
            ).fetchone()
        self.assertEqual(row, ("ignored", "invalid_signature", 0))

    async def test_invalid_delivery_cannot_poison_later_valid_event_identity(self):
        order, payment = await self._payment("poison")
        body = json.dumps({
            "event_id": "evt-poison",
            "type": "payment.confirmed",
            "payment_id": payment.provider_payment_id,
        }, separators=(",", ":")).encode()

        with self.assertRaises(web.HTTPUnauthorized):
            await self.gateway.handle(
                _FakeRequest(body, signature="00" * 32)
            )

        response = await self.gateway.handle(
            _FakeRequest(body, signature=_signature(self.secret, body))
        )
        payload = json.loads(response.text)
        self.assertEqual(response.status, 200)
        self.assertFalse(payload["duplicate"])
        self.assertEqual((await self.db.get_commerce_payment(payment.id)).status, "confirmed")
        self.assertEqual((await self.db.get_commerce_order(order.id)).status, "paid")
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                """
                SELECT signature_valid, processing_status, result_code
                FROM payment_webhook_events WHERE provider_event_id = ?
                """,
                ("evt-poison",),
            ).fetchone()
        self.assertEqual(row, (1, "applied", "confirmed"))

    async def test_same_event_id_cannot_be_rebound_to_different_payment_reference(self):
        _, payment = await self._payment("bind-a")
        body = json.dumps({
            "event_id": "evt-bind",
            "type": "payment.confirmed",
            "payment_id": payment.provider_payment_id,
        }, separators=(",", ":")).encode()
        await self.gateway.handle(
            _FakeRequest(body, signature=_signature(self.secret, body))
        )

        other_body = json.dumps({
            "event_id": "evt-bind",
            "type": "payment.confirmed",
            "payment_id": "pay-bind-b",
        }, separators=(",", ":")).encode()
        with self.assertRaisesRegex(
            RuntimeError,
            "different (content|payment reference)",
        ):
            await self.gateway.handle(
                _FakeRequest(
                    other_body,
                    signature=_signature(self.secret, other_body),
                )
            )

    async def test_unsupported_signed_event_is_journaled_and_ignored(self):
        body = json.dumps({
            "event_id": "evt-refund",
            "type": "payment.refunded",
            "payment_id": "pay-refund",
            "metadata": {"reason": "provider_notice"},
        }, separators=(",", ":")).encode()
        with self.assertRaises(web.HTTPUnprocessableEntity):
            await self.gateway.handle(
                _FakeRequest(body, signature=_signature(self.secret, body))
            )
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                """
                SELECT event_type, processing_status, result_code, signature_valid
                FROM payment_webhook_events WHERE provider_event_id = ?
                """,
                ("evt-refund",),
            ).fetchone()
        self.assertEqual(
            row,
            ("payment.refunded", "ignored", "unsupported_event_type", 1),
        )

    async def test_body_size_limit_rejects_before_processing(self):
        request = _FakeRequest(
            b"{}",
            content_length=MAX_PAYMENT_WEBHOOK_BYTES + 1,
        )
        with self.assertRaises(web.HTTPRequestEntityTooLarge):
            await read_bounded_body(request)


if __name__ == "__main__":
    unittest.main()
