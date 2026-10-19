"""#470: только read-only Orders, Payment и Entitlement в Admin."""
from __future__ import annotations

import importlib
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import aiosqlite

from admin_privileges import required_role_for_callback
from db import Database


class StarsOrdersAdminTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "orders.sqlite3"))
        await self.db.init()
        self.plan_id = await self.db.create_plan(
            name="Тест XTR", duration_days=30, traffic_gb=1, ip_limit=1,
            price_minor=100, currency="RUB", stars_price=5,
        )
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
            self.module = importlib.import_module("business_admin")

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def invoke(self, handler, data, allowed=True):
        call = SimpleNamespace(data=data, answer=AsyncMock())
        view = AsyncMock()
        with (
            patch.object(self.module, "db", self.db),
            patch.object(self.module, "guard", new=AsyncMock(return_value=allowed)) as guard,
            patch.object(self.module, "render_callback", new=view),
        ):
            await handler(call)
        guard.assert_awaited_once_with(call)
        if not allowed:
            view.assert_not_awaited()
            call.answer.assert_not_awaited()
            return None, [], call
        if view.await_count == 0:
            return None, [], call
        args, kwargs = view.await_args
        buttons = [button for row in kwargs["reply_markup"].inline_keyboard for button in row]
        return args[1], buttons, call

    async def order(self):
        return await self.db.create_commerce_order(
            telegram_id=1001, plan_id=self.plan_id,
            amount_minor=5, currency="XTR",
        )

    async def test_empty_and_pending_without_payment(self):
        text, buttons, _ = await self.invoke(self.module.stars_orders_list, "admin:starsorders")
        self.assertIn("Заказы: 0", text)
        self.assertIn("admin:starspayments", [b.callback_data for b in buttons])
        order_id = await self.order()
        text, buttons, _ = await self.invoke(self.module.stars_orders_list, "admin:starsorders")
        self.assertIn("Заказы: 1", text)
        self.assertIn("нет платежа", [b.text for b in buttons][0])
        self.assertIn(f"admin:starsorder:{order_id}:0", [b.callback_data for b in buttons])
        detail, buttons, _ = await self.invoke(
            self.module.stars_order_detail, f"admin:starsorder:{order_id}:0",
        )
        self.assertIn("Статус заказа: created", detail)
        self.assertIn("Платёж ещё не подтверждён / не создан", detail)
        self.assertIn("Entitlement: Записи нет", detail)
        self.assertIn("Тест XTR", detail)
        self.assertNotIn("🔎 Открыть Stars-платёж", [b.text for b in buttons])
        self.assertIn("admin:starsorders:0", [b.callback_data for b in buttons])
        self.assertIn("не подтверждён", detail)

    async def test_paid_order_correlates_existing_payment_and_entitlement(self):
        order_id = await self.order()
        async with aiosqlite.connect(self.db.path) as conn:
            await conn.execute(
                "UPDATE commerce_orders SET status='paid', paid_at=12345 WHERE id=?",
                (order_id,),
            )
            cur = await conn.execute(
                """INSERT INTO commerce_payments (
                    order_id,provider,provider_payment_id,amount_minor,currency,
                    status,created_at,updated_at,confirmed_at
                ) VALUES (?, 'telegram_stars', 'secret-never-visible', 5,'XTR',
                          'confirmed',100,100,100)""",
                (order_id,),
            )
            payment_id = cur.lastrowid
            await conn.execute(
                """INSERT INTO entitlements (
                    telegram_id,order_id,plan_id,status,created_at,updated_at
                ) VALUES (1001,?,?,'active',100,100)""",
                (order_id, self.plan_id),
            )
            await conn.commit()
        detail, buttons, _ = await self.invoke(
            self.module.stars_order_detail, f"admin:starsorder:{order_id}:0",
        )
        self.assertIn("Статус заказа: paid", detail)
        self.assertIn(f"Платёж: #{payment_id} · confirmed", detail)
        self.assertIn("Entitlement: #", detail)
        self.assertIn("active", detail)
        self.assertNotIn("secret-never-visible", detail)
        self.assertNotIn("refund", detail.lower())
        self.assertEqual(
            [b.callback_data for b in buttons if b.text == "🔎 Открыть Stars-платёж"],
            [f"admin:starspayment:{payment_id}"],
        )

    async def test_pagination_out_of_range_and_stale_order(self):
        for _ in range(17):
            await self.order()
        first, buttons, _ = await self.invoke(self.module.stars_orders_list, "admin:starsorders")
        self.assertIn("Заказы: 17", first)
        self.assertEqual(len([b for b in buttons if b.callback_data and b.callback_data.startswith("admin:starsorder:")]), 8)
        self.assertIn("admin:starsorders:8", [b.callback_data for b in buttons])
        second, buttons, _ = await self.invoke(self.module.stars_orders_list, "admin:starsorders:8")
        self.assertIn("страница 2", second)
        self.assertIn("admin:starsorders:0", [b.callback_data for b in buttons])
        last, buttons, _ = await self.invoke(self.module.stars_orders_list, "admin:starsorders:99999")
        self.assertIn("страница 3", last)
        self.assertEqual(len([b for b in buttons if b.callback_data and b.callback_data.startswith("admin:starsorder:")]), 1)
        detail, buttons, call = await self.invoke(self.module.stars_order_detail, "admin:starsorder:999999:0")
        self.assertIsNone(detail)
        self.assertEqual(buttons, [])
        call.answer.assert_awaited_once_with(
            "Заказ Stars не найден или больше недоступен.", show_alert=True,
        )

    async def test_permissions_and_denied_request(self):
        for cb in ("admin:starsorders", "admin:starsorders:8", "admin:starsorder:7", "admin:starsorder:7:8"):
            self.assertEqual(required_role_for_callback(cb), "read_only")
        for cb in ("admin:starsorders:-1", "admin:starsorder:-1", "admin:starsorder:7:-1",
                   "admin:starsorder:1:8:1", "admin:starsorders:rerun:1"):
            self.assertIsNone(required_role_for_callback(cb))
        self.assertEqual(required_role_for_callback("admin:starsrefund:run:7"), "admin")
        await self.invoke(self.module.stars_orders_list, "admin:starsorders", allowed=False)
        await self.invoke(self.module.stars_order_detail, "admin:starsorder:8", allowed=False)
