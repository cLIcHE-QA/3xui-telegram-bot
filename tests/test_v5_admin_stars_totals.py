"""Admin payment stats must show Stars commerce separately from manual payments."""
from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from commerce import CommerceService
from db import Database, UserRecord
from stars_refund import run_stars_refund


class AdminStarsTotalsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "bot.sqlite3"))
        await self.db.init()
        await self.db.put(UserRecord(
            telegram_id=1001, email="stars@example.invalid",
            sub_id="test-sub", expiry_time=0, created_at=1,
        ))
        env = {
            "BOT_TOKEN": "123456789:offline-tests",
            "PANEL_URL": "https://panel.example.invalid/base",
            "PANEL_API_TOKEN": "offline-token",
            "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/{sub_id}",
            "ALLOWED_TELEGRAM_IDS": "1",
            "ADMIN_TELEGRAM_IDS": "1",
            "DB_PATH": self.db.path,
        }
        with patch.dict(os.environ, env, clear=False):
            self.admin = importlib.import_module("business_admin")

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def _render(self):
        call = SimpleNamespace(data="admin:payments", answer=AsyncMock())
        renderer = AsyncMock()
        with (
            patch.object(self.admin, "db", self.db),
            patch.object(self.admin, "guard", new=AsyncMock(return_value=True)),
            patch.object(self.admin, "render_callback", new=renderer),
        ):
            await self.admin.payments_list(call)
        call.answer.assert_awaited_once()
        return renderer.await_args.args[1]

    async def test_empty_and_manual_totals_remain_separate(self):
        empty = await self._render()
        self.assertIn("Всего записей: 0", empty)
        self.assertIn("⭐ Telegram Stars", empty)
        self.assertIn("📒 Ручные платежи (учёт)", empty)

        await self.db.create_payment(
            telegram_id=1001, plan_id=None, amount_minor=1000,
            currency="RUB", status="paid",
        )
        mixed = await self._render()
        self.assertIn("Всего записей: 1", mixed)
        self.assertIn("Выручка по оплаченным: 10 RUB", mixed)
        self.assertIn("⭐ Telegram Stars\nВсего: 0", mixed)

    async def test_stars_global_pagination_boundaries_and_back(self):
        module = self.admin
        plan_id = await self.db.create_plan(name="pagination", duration_days=30, traffic_gb=1, ip_limit=1, price_minor=100, currency="RUB", stars_price=1)
        async with __import__("aiosqlite").connect(self.db.path) as conn:
            for i in range(17):
                cursor = await conn.execute(
                    "INSERT INTO commerce_orders(telegram_id,plan_id,amount_minor,currency,status,created_at,updated_at) "
                    "VALUES (1001,?,1,'XTR','created',?,?)",
                    (plan_id, 100 + i, 100 + i),
                )
                await conn.execute(
                    "INSERT INTO commerce_payments(order_id,provider,provider_payment_id,amount_minor,currency,status,created_at,updated_at) "
                    "VALUES (?,'telegram_stars',?,1,'XTR','created',?,?)",
                    (cursor.lastrowid, f'test-{i}', 100 + i, 100 + i),
                )
            await conn.commit()
        async def render(data):
            call = SimpleNamespace(data=data, answer=AsyncMock())
            cb = AsyncMock()
            with (patch.object(module, "db", self.db),
                  patch.object(module, "guard", new=AsyncMock(return_value=True)),
                  patch.object(module, "render_callback", new=cb)):
                await module.stars_payments_list(call)
            return cb.await_args
        first = await render("admin:starspayments")
        rows = [b for row in first.kwargs["reply_markup"].inline_keyboard for b in row]
        self.assertEqual(sum(b.callback_data.startswith("admin:starspayment:") for b in rows), 8)
        self.assertIn("admin:starspayments:8", [b.callback_data for b in rows])
        second = await render("admin:starspayments:8")
        btns = [b.callback_data for row in second.kwargs["reply_markup"].inline_keyboard for b in row]
        self.assertIn("admin:starspayments:0", btns)
        self.assertIn("admin:starspayments:16", btns)
        last = await render("admin:starspayments:9999")
        vals = [b.callback_data for row in last.kwargs["reply_markup"].inline_keyboard for b in row]
        self.assertEqual(sum(v.startswith("admin:starspayment:") for v in vals), 1)
        self.assertNotIn("admin:starspayments:24", vals)

    async def test_manual_ledger_has_eight_entries_and_bounded_back_navigation(self):
        for i in range(17):
            await self.db.create_payment(
                telegram_id=1001, plan_id=None, amount_minor=100 + i,
                currency="RUB", status="paid",
            )
        async def render(data):
            renderer = AsyncMock()
            call = SimpleNamespace(data=data, answer=AsyncMock())
            with (patch.object(self.admin, "db", self.db),
                  patch.object(self.admin, "guard", new=AsyncMock(return_value=True)),
                  patch.object(self.admin, "render_callback", new=renderer)):
                await self.admin.payments_list(call)
            return renderer.await_args.kwargs["reply_markup"]
        first = await render("admin:payments")
        callbacks = [b.callback_data for row in first.inline_keyboard for b in row]
        self.assertEqual(sum(v.startswith("admin:payment:") for v in callbacks), 8)
        self.assertIn("admin:payments:8", callbacks)
        second = await render("admin:payments:8")
        callbacks = [b.callback_data for row in second.inline_keyboard for b in row]
        self.assertIn("admin:payments:0", callbacks)
        self.assertIn("admin:payments:16", callbacks)
        self.assertTrue(any(v.endswith(":8") and v.startswith("admin:payment:") for v in callbacks))
        final = await render("admin:payments:99999")
        callbacks = [b.callback_data for row in final.inline_keyboard for b in row]
        self.assertEqual(sum(v.startswith("admin:payment:") for v in callbacks), 1)

    async def test_read_only_payment_paging_callbacks(self):
        from admin_privileges import required_role_for_callback
        for callback in ("admin:payments:8", "admin:payment:123:8", "admin:starspayments:8", "admin:starspayment:123:8"):
            self.assertEqual(required_role_for_callback(callback), "read_only")
        self.assertIsNone(required_role_for_callback("admin:starspayments:-1"))

    async def test_confirmed_and_refunded_stars_visible(self):
        commerce = CommerceService(self.db)
        plan_id = await self.db.create_plan(
            name="test", duration_days=30, traffic_gb=1, ip_limit=1,
            price_minor=1000, currency="RUB", stars_price=1,
        )
        for i in (1, 2):
            order = await commerce.create_order(
                telegram_id=1001, plan_id=plan_id,
                amount_minor=1, currency="XTR",
            )
            await self.db.mark_commerce_order_awaiting_payment(order.id)
            payment, _, _, _ = await commerce.confirm_telegram_stars_payment(
                order_id=order.id, telegram_id=1001,
                charge_id=f"charge-{i}", amount=1, raw_payload=f"paid-{i}".encode(),
            )
            if i == 1:
                await run_stars_refund(self.db, AsyncMock(), payment_id=payment.id, requested_by=77)

        rendered = await self._render()
        self.assertIn("Всего записей: 2", rendered)
        self.assertIn("🟢 Подтверждено: 1 · ⭐ 1", rendered)
        self.assertIn("↩️ Возвращено: 1 · ⭐ 1", rendered)
        self.assertIn("📒 Ручные платежи (учёт)", rendered)


if __name__ == "__main__":
    unittest.main()
