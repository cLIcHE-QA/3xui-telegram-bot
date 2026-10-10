"""Invoice cleanup is cosmetic; successful Stars payments remain durable (#320)."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import client_access
from commerce import CommerceService
from db import Database, UserRecord


class StarsPaidInvoiceCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "bot.sqlite3"
        self.db = Database(str(self.path))
        await self.db.init()
        self.commerce = CommerceService(self.db)
        self.plan_id = await self.db.create_plan(
            name="Test Stars", duration_days=30, traffic_gb=5,
            ip_limit=1, price_minor=100, currency="RUB", stars_price=1,
        )
        await self.db.put(UserRecord(
            telegram_id=7001, email="test@example.invalid",
            sub_id="test-sub", expiry_time=0, created_at=1,
        ))
        self.order = await self.commerce.create_order(
            telegram_id=7001, plan_id=self.plan_id,
            amount_minor=1, currency="XTR",
        )

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def confirm(self):
        return await self.commerce.confirm_telegram_stars_payment(
            order_id=self.order.id, telegram_id=7001,
            charge_id="fake-charge", amount=1, raw_payload=b"fake-payload",
        )

    def message(self):
        return SimpleNamespace(
            from_user=SimpleNamespace(id=7001),
            successful_payment=SimpleNamespace(
                currency="XTR", invoice_payload=f"stars:v1:{self.order.id}:7001",
                total_amount=1, telegram_payment_charge_id="fake-charge",
            ),
            bot=SimpleNamespace(delete_message=AsyncMock()),
            answer=AsyncMock(),
        )

    async def invoke(self, message):
        service = SimpleNamespace(db=self.db, confirm_stars_payment=AsyncMock(
            side_effect=lambda **kwargs: self.commerce.confirm_telegram_stars_payment(
                **kwargs
            )
        ))
        with patch.object(client_access, "_service", return_value=service):
            await client_access.stars_successful_payment(message)

    async def test_paid_invoice_deleted_once_and_duplicate_no_replay(self):
        await self.db.record_stars_invoice_message(
            order_id=self.order.id, chat_id=7001, message_id=200,
        )
        await self.db.record_stars_invoice_message(
            order_id=self.order.id, chat_id=7001, message_id=201,
        )
        message = self.message()
        await self.invoke(message)
        self.assertEqual(message.bot.delete_message.await_count, 2)
        await self.invoke(message)
        self.assertEqual(message.bot.delete_message.await_count, 2)
        self.assertEqual((await self.db.get_commerce_order(self.order.id)).status, "paid")
        with sqlite3.connect(self.path) as conn:
            statuses = conn.execute(
                "SELECT cleanup_status FROM stars_invoice_messages ORDER BY message_id"
            ).fetchall()
            entitlements = conn.execute(
                "SELECT count(*) FROM entitlements WHERE order_id = ?",
                (self.order.id,),
            ).fetchone()[0]
        self.assertEqual(statuses, [("success",), ("success",)])
        self.assertEqual(entitlements, 1)

    async def test_uncertain_delete_never_replays_and_payment_stays_confirmed(self):
        await self.db.record_stars_invoice_message(
            order_id=self.order.id, chat_id=7001, message_id=300,
        )
        message = self.message()
        message.bot.delete_message.side_effect = OSError("connection lost")
        await self.invoke(message)
        await self.invoke(message)
        message.bot.delete_message.assert_awaited_once()
        with sqlite3.connect(self.path) as conn:
            status = conn.execute(
                "SELECT cleanup_status FROM stars_invoice_messages WHERE order_id = ?",
                (self.order.id,),
            ).fetchone()[0]
            payments = conn.execute(
                "SELECT status FROM commerce_payments WHERE order_id = ?",
                (self.order.id,),
            ).fetchall()
        self.assertEqual(status, "unknown")
        self.assertEqual(payments, [("confirmed",)])

    async def test_claim_before_payment_is_noop_and_foreign_invoice_not_stored(self):
        await self.db.record_stars_invoice_message(
            order_id=self.order.id, chat_id=7001, message_id=400,
        )
        await self.db.record_stars_invoice_message(
            order_id=self.order.id, chat_id=9000, message_id=500,
        )
        self.assertEqual(
            await self.db.claim_stars_invoice_cleanup(
                order_id=self.order.id, chat_id=7001,
            ), [],
        )
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM stars_invoice_messages"
            ).fetchone()[0], 1)
        await self.confirm()
        self.assertEqual(
            await self.db.claim_stars_invoice_cleanup(
                order_id=self.order.id, chat_id=7001,
            ), [400],
        )
        self.assertEqual(
            await self.db.claim_stars_invoice_cleanup(
                order_id=self.order.id, chat_id=7001,
            ), [],
        )

    async def test_cleanup_persists_across_database_reopen(self):
        await self.db.record_stars_invoice_message(
            order_id=self.order.id, chat_id=7001, message_id=600,
        )
        await self.confirm()
        self.assertEqual(await self.db.claim_stars_invoice_cleanup(
            order_id=self.order.id, chat_id=7001,
        ), [600])
        reopened = Database(str(self.path))
        self.assertEqual(await reopened.claim_stars_invoice_cleanup(
            order_id=self.order.id, chat_id=7001,
        ), [])


if __name__ == "__main__":
    unittest.main()
