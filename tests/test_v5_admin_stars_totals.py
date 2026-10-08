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
        call = SimpleNamespace(answer=AsyncMock())
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
