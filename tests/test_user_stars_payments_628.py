"""#628: owner-isolated read-only Stars ledger in user admin payments."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from db import Database


class UserStarsPaymentsDbTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "bot.sqlite3"))
        await self.db.init()

        self.first = await self.db.create_commerce_order(
            telegram_id=101, plan_id=1, amount_minor=12, currency="XTR"
        )
        self.second = await self.db.create_commerce_order(
            telegram_id=202, plan_id=1, amount_minor=19, currency="XTR"
        )
        self.paid, _ = await self.db.create_or_get_checkout_payment(
            order_id=self.first, provider="telegram_stars",
            provider_payment_id="synthetic-stars-1", amount_minor=12,
            currency="XTR", checkout_url="", idempotency_key="test-628-1",
        )
        self.other, _ = await self.db.create_or_get_checkout_payment(
            order_id=self.second, provider="telegram_stars",
            provider_payment_id="synthetic-stars-2", amount_minor=19,
            currency="XTR", checkout_url="", idempotency_key="test-628-2",
        )
        self.refund_order = await self.db.create_commerce_order(
            telegram_id=101, plan_id=1, amount_minor=8, currency="XTR"
        )
        self.refunded, _ = await self.db.create_or_get_checkout_payment(
            order_id=self.refund_order, provider="telegram_stars",
            provider_payment_id="synthetic-stars-3", amount_minor=8,
            currency="XTR", checkout_url="", idempotency_key="test-628-3",
        )
        with sqlite3.connect(self.db.path) as conn:
            conn.execute("UPDATE commerce_payments SET status='confirmed' WHERE id=?", (self.paid.id,))
            conn.execute("UPDATE commerce_payments SET status='unknown' WHERE id=?", (self.other.id,))
            conn.execute("UPDATE commerce_payments SET status='refunded' WHERE id=?", (self.refunded.id,))
            conn.execute(
                "INSERT INTO stars_refund_operations ("
                "operation_id, payment_id, telegram_id, provider_payment_id, status,"
                "requested_by, created_at, updated_at, error"
                ") VALUES ('synthetic-refund', ?, 101, 'synthetic-stars-3',"
                "'success', 1, 100, 101, '')",
                (self.refunded.id,),
            )
        self.legacy_id = await self.db.create_payment(
            telegram_id=101, plan_id=None, amount_minor=1250,
            currency="RUB", status="paid",
        )

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_owner_isolation_statuses_and_refund_journal(self):
        rows = await self.db.list_user_stars_payments(101)
        self.assertEqual(len(rows), 2)
        self.assertEqual({r["status"] for r in rows}, {"confirmed", "refunded"})
        self.assertEqual(await self.db.count_user_stars_payments(101), 2)
        self.assertEqual(await self.db.count_user_stars_payments(202), 1)
        self.assertEqual(await self.db.count_user_payments(101), 1)
        self.assertEqual((await self.db.get_user_stars_payment(101, self.refunded.id))["refund_status"], "success")
        self.assertIsNone(await self.db.get_user_stars_payment(101, self.other.id))
        self.assertIsNone(await self.db.get_user_stars_payment(202, self.paid.id))
        self.assertIsNone(await self.db.get_user_stars_payment(101, 987654321))
        summary = await self.db.user_stars_payment_summary(101)
        self.assertEqual(summary["counts"]["confirmed"], 1)
        self.assertEqual(summary["counts"]["refunded"], 1)
        self.assertEqual(summary["confirmed_xtr"], 12)
        self.assertEqual(summary["refunded_xtr"], 8)
        self.assertEqual(await self.db.paid_user_totals_by_currency(101), {"RUB": 1250})
        # The numeric id is namespaced by ledger, never used as cross-ledger identity.
        self.assertTrue(await self.db.get_user_payment(101, self.legacy_id))

    async def test_bounded_pagination_empty_and_unknown_status(self):
        first_page = await self.db.list_user_stars_payments(101, limit=1, offset=0)
        next_page = await self.db.list_user_stars_payments(101, limit=1, offset=1)
        self.assertEqual(len(first_page), 1)
        self.assertEqual(len(next_page), 1)
        self.assertNotEqual(first_page[0]["id"], next_page[0]["id"])
        self.assertEqual(await self.db.list_user_stars_payments(101, offset=20), [])
        self.assertEqual(await self.db.count_user_stars_payments(404), 0)
        self.assertEqual(await self.db.list_user_stars_payments(404), [])
        self.assertEqual((await self.db.list_user_stars_payments(202))[0]["status"], "unknown")


class UserStarsPaymentsUiTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_only_tabs_callback_and_owner_rejection(self):
        import advanced_users as ui

        fake_db = SimpleNamespace(
            get=AsyncMock(return_value=SimpleNamespace(telegram_id=101)),
            count_user_stars_payments=AsyncMock(return_value=2),
            count_user_payments=AsyncMock(return_value=0),
            user_stars_payment_summary=AsyncMock(return_value={
                "counts": {"confirmed": 1, "refunded": 1},
                "confirmed_xtr": 12, "refunded_xtr": 8,
            }),
            list_user_stars_payments=AsyncMock(return_value=[
                dict(id=1, order_id=5, amount_minor=12, currency="XTR",
                     status="confirmed", refund_status=None, created_at=100, confirmed_at=100),
                dict(id=2, order_id=6, amount_minor=8, currency="XTR",
                     status="refunded", refund_status="success", created_at=101, confirmed_at=100),
            ]),
            get_user_stars_payment=AsyncMock(return_value=None),
        )
        with patch.object(ui, "db", fake_db), patch.object(
            ui, "_display_label", new=AsyncMock(return_value="Synthetic customer")
        ):
            text, keyboard = await ui._user_payments_view(101)
            self.assertIn("⭐ Telegram Stars", text)
            self.assertIn("📒 Ручные платежи", text)
            self.assertIn("Возвращено: 1", text)
            self.assertIn("refund: success", text)
            buttons = [button for row in keyboard.inline_keyboard for button in row]
            self.assertTrue(any(b.callback_data == "admin:u:starpayment:101:1:0" for b in buttons))
            self.assertTrue(any(b.callback_data == "admin:u:payments:101:manual:0" for b in buttons))
            fake_db.count_user_payments.assert_awaited_once_with(101)

            call = SimpleNamespace(
                data="admin:u:starpayment:101:987:0",
                answer=AsyncMock(),
            )
            with patch.object(ui, "guard", new=AsyncMock(return_value=True)), patch.object(
                ui, "render_callback", new=AsyncMock()
            ) as render:
                await ui.user_stars_payment_detail(call)
            call.answer.assert_awaited_once_with(
                "Stars-платёж не найден для этого пользователя.", show_alert=True
            )
            render.assert_not_awaited()
            fake_db.get_user_stars_payment.assert_awaited_once_with(101, 987)

    def test_no_mutation_and_ledger_boundaries_in_user_handlers(self):
        source = (Path(__file__).resolve().parents[1] / "advanced_users.py").read_text(encoding="utf-8")
        segment = source.split("async def _user_payments_view(", 1)[1].split(
            "async def _user_activity_view(", 1
        )[0]
        self.assertNotIn("run_stars_refund", segment)
        self.assertNotIn("set_payment_status", segment)
        self.assertNotIn("admin:starsrefund:ask", segment)
        self.assertIn('minimum="read_only"', segment)
        self.assertIn("get_user_stars_payment(tg_id, payment_id)", segment)


if __name__ == "__main__":
    unittest.main()
