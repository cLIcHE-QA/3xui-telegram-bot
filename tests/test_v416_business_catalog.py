from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from db import Database, PromoCodeRecord, UserRecord


def _load_business_admin(db_path: str):
    env = {
        "BOT_TOKEN": "123456789:offline-v416-token",
        "PANEL_URL": "https://panel.example.invalid/base",
        "PANEL_API_TOKEN": "offline-v416-token",
        "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/sub/{sub_id}",
        "ALLOWED_TELEGRAM_IDS": "1",
        "ADMIN_TELEGRAM_IDS": "1",
        "DB_PATH": db_path,
    }
    with patch.dict(os.environ, env, clear=False):
        return importlib.import_module("business_admin")


class BusinessCatalogRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "bot.sqlite3"
        self.db = Database(str(self.db_path))
        await self.db.init()
        await self.db.put(
            UserRecord(
                telegram_id=101,
                email="user101@example.test",
                sub_id="sub-101",
                expiry_time=0,
                created_at=int(time.time()),
            )
        )

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_payment_status_transition_sets_paid_at_once_and_totals_follow_current_status(self):
        payment_id = await self.db.create_payment(
            telegram_id=101,
            plan_id=None,
            amount_minor=1299,
            currency="rub",
            status="pending",
            external_id="invoice-1",
            created_by=1,
        )
        pending = await self.db.get_payment(payment_id)
        self.assertIsNotNone(pending)
        self.assertEqual(pending.status, "pending")
        self.assertEqual(pending.paid_at, 0)

        await self.db.set_payment_status(payment_id, "paid")
        paid = await self.db.get_payment(payment_id)
        self.assertEqual(paid.status, "paid")
        self.assertGreater(paid.paid_at, 0)
        first_paid_at = paid.paid_at
        self.assertEqual(await self.db.paid_totals_by_currency(), {"RUB": 1299})

        await self.db.set_payment_status(payment_id, "refunded")
        refunded = await self.db.get_payment(payment_id)
        self.assertEqual(refunded.status, "refunded")
        self.assertEqual(refunded.paid_at, first_paid_at)
        self.assertEqual(await self.db.paid_totals_by_currency(), {})

        await self.db.set_payment_status(payment_id, "paid")
        paid_again = await self.db.get_payment(payment_id)
        self.assertEqual(paid_again.paid_at, first_paid_at)
        self.assertEqual(await self.db.paid_totals_by_currency(), {"RUB": 1299})

    async def test_payment_handler_rejects_unknown_status_before_db_mutation(self):
        module = _load_business_admin(str(self.db_path))
        call = SimpleNamespace(
            data="admin:payment:status:999:forged",
            answer=AsyncMock(),
        )
        db_mock = SimpleNamespace(
            get_payment=AsyncMock(),
            set_payment_status=AsyncMock(),
        )
        with (
            patch.object(module, "guard", new=AsyncMock(return_value=True)),
            patch.object(module, "db", db_mock),
        ):
            await module.payment_status(call)

        db_mock.get_payment.assert_not_awaited()
        db_mock.set_payment_status.assert_not_awaited()
        call.answer.assert_awaited_once_with("Некорректный статус.", show_alert=True)

    async def test_money_parser_and_promo_state_boundaries(self):
        module = _load_business_admin(str(self.db_path))

        self.assertEqual(module.parse_money("4,99", "EUR"), (499, "EUR"))
        self.assertEqual(module.parse_money("4.995 usd", "RUB"), (500, "USD"))
        self.assertEqual(module.parse_money("0", "RUB"), (0, "RUB"))
        for invalid in ("", "-1 RUB", "1 US", "not-money"):
            with self.subTest(raw=invalid):
                with self.assertRaises(ValueError):
                    module.parse_money(invalid, "RUB")

        now = int(time.time())
        base = dict(
            id=1,
            code="WELCOME",
            discount_type="percent",
            value=20,
            currency="RUB",
            plan_id=None,
            max_uses=0,
            uses_count=0,
            expires_at=0,
            active=1,
            created_at=now,
        )
        active = PromoCodeRecord(**base)
        disabled = PromoCodeRecord(**{**base, "active": 0})
        expired = PromoCodeRecord(**{**base, "expires_at": now - 1})
        exhausted = PromoCodeRecord(**{**base, "max_uses": 2, "uses_count": 2})

        self.assertEqual(module.promo_state(active), ("🟢", "active"))
        self.assertEqual(module.promo_state(disabled), ("⚪", "disabled"))
        self.assertEqual(module.promo_state(expired), ("🔴", "expired"))
        self.assertEqual(module.promo_state(exhausted), ("🔴", "limit reached"))

    async def test_promo_codes_are_case_insensitively_unique_and_toggle_is_persistent(self):
        promo_id = await self.db.create_promo_code(
            code="welcome20",
            discount_type="percent",
            value=20,
            currency="rub",
            max_uses=10,
        )
        promo = await self.db.get_promo_code(promo_id)
        self.assertEqual(promo.code, "WELCOME20")
        self.assertEqual(promo.active, 1)

        with self.assertRaises(sqlite3.IntegrityError):
            await self.db.create_promo_code(
                code="WELCOME20",
                discount_type="percent",
                value=10,
            )

        await self.db.set_promo_active(promo_id, False)
        self.assertEqual((await self.db.get_promo_code(promo_id)).active, 0)
        await self.db.set_promo_active(promo_id, True)
        self.assertEqual((await self.db.get_promo_code(promo_id)).active, 1)

    async def test_catalog_delete_cleans_plan_and_user_profile_relations(self):
        group_id = await self.db.create_server_group(name="Europe", description="primary")
        await self.db.set_server_group_member(group_id, "master", True)
        await self.db.set_server_group_member(group_id, "node_2", True)
        await self.db.set_server_group_inbound_mode(group_id, "selected")
        await self.db.replace_server_group_inbounds(group_id, [10, 11, 11])

        plan_id = await self.db.create_plan(
            name="Premium",
            duration_days=30,
            traffic_gb=100,
            ip_limit=2,
            price_minor=999,
            currency="rub",
            server_group_id=group_id,
        )
        await self.db.upsert_user_profile(
            101,
            plan_id=plan_id,
            server_group_id=group_id,
            note="keep",
            preserve_unspecified=False,
        )

        self.assertEqual(await self.db.list_server_group_members(group_id), {"master", "node_2"})
        self.assertEqual(await self.db.list_server_group_inbounds(group_id), {10, 11})
        self.assertEqual(await self.db.get_server_group_inbound_mode(group_id), "selected")

        await self.db.delete_server_group(group_id)

        self.assertIsNone(await self.db.get_server_group(group_id))
        self.assertIsNone((await self.db.get_plan(plan_id)).server_group_id)
        profile = await self.db.get_user_profile(101)
        self.assertEqual(profile.plan_id, plan_id)
        self.assertIsNone(profile.server_group_id)
        self.assertEqual(profile.note, "keep")
        self.assertEqual(await self.db.list_server_group_members(group_id), set())
        self.assertEqual(await self.db.list_server_group_inbounds(group_id), set())
        self.assertEqual(await self.db.get_server_group_inbound_mode(group_id), "all_managed")

        await self.db.delete_plan(plan_id)
        self.assertIsNone(await self.db.get_plan(plan_id))
        self.assertIsNone((await self.db.get_user_profile(101)).plan_id)

    async def test_catalog_rejects_invalid_mode_and_duplicate_casefolded_names(self):
        group_id = await self.db.create_server_group(name="Nordic")
        with self.assertRaises(sqlite3.IntegrityError):
            await self.db.create_server_group(name="nordic")
        with self.assertRaises(ValueError):
            await self.db.set_server_group_inbound_mode(group_id, "unsafe")

        await self.db.replace_server_group_inbounds(group_id, [7, 7, 8])
        self.assertEqual(await self.db.list_server_group_inbounds(group_id), {7, 8})

        await self.db.create_plan(
            name="Standard",
            duration_days=30,
            traffic_gb=50,
            ip_limit=2,
            price_minor=500,
            currency="rub",
        )
        with self.assertRaises(sqlite3.IntegrityError):
            await self.db.create_plan(
                name="standard",
                duration_days=7,
                traffic_gb=5,
                ip_limit=1,
                price_minor=100,
                currency="rub",
            )

    async def test_user_delete_removes_profile_but_preserves_payment_ledger(self):
        plan_id = await self.db.create_plan(
            name="History",
            duration_days=30,
            traffic_gb=10,
            ip_limit=1,
            price_minor=100,
            currency="RUB",
        )
        await self.db.upsert_user_profile(
            101,
            plan_id=plan_id,
            server_group_id=None,
            note="profile",
            preserve_unspecified=False,
        )
        payment_id = await self.db.create_payment(
            telegram_id=101,
            plan_id=plan_id,
            amount_minor=100,
            currency="RUB",
            status="paid",
        )

        await self.db.delete(101)

        self.assertIsNone(await self.db.get(101))
        self.assertIsNone(await self.db.get_user_profile(101))
        payment = await self.db.get_payment(payment_id)
        self.assertIsNotNone(payment)
        self.assertEqual(payment.telegram_id, 101)
        self.assertEqual(payment.amount_minor, 100)


if __name__ == "__main__":
    unittest.main()
