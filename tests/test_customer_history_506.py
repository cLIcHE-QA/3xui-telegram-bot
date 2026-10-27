"""#506: owner-scoped, read-only Stars history; no live payments or Telegram."""
import importlib
from datetime import date
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import aiosqlite

from client_history_ui import history_route, history_list_view, history_detail_view, history_help_view
from commerce import CommerceService
from customer_service import CustomerPortalService
from db import Database, UserRecord


class CustomerHistory506Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "history.sqlite3"))
        await self.db.init()
        for actor in (1001, 1002):
            await self.db.put(UserRecord(actor, f"owner-{actor}@example.invalid", f"private-sub-{actor}", 0, 1))
        self.plan = await self.db.create_plan(
            name="Тест Stars", duration_days=30, traffic_gb=1, ip_limit=1,
            price_minor=100, currency="RUB", stars_price=5,
        )
        self.provider = AsyncMock()
        self.commerce = CommerceService(self.db)
        self.service = CustomerPortalService(
            self.db, self.commerce, self.provider,
            subscription_url_template="https://sub.example.invalid/{sub_id}", checkout=AsyncMock(),
        )
        env = {
            "BOT_TOKEN": "123456789:offline-tests", "PANEL_URL": "https://panel.example.invalid/base",
            "PANEL_API_TOKEN": "offline-token", "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/{sub_id}",
            "ALLOWED_TELEGRAM_IDS": "1", "ADMIN_TELEGRAM_IDS": "1", "DB_PATH": self.db.path,
        }
        with patch.dict(os.environ, env, clear=False):
            self.ui = importlib.import_module("client_access")

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def order(self, actor=1001, currency="XTR"):
        return await self.db.create_commerce_order(
            telegram_id=actor, plan_id=self.plan, amount_minor=5, currency=currency,
        )

    async def payment(self, order, status="confirmed", provider="telegram_stars", currency="XTR"):
        async with aiosqlite.connect(self.db.path) as conn:
            cur = await conn.execute(
                """INSERT INTO commerce_payments (
                    order_id,provider,provider_payment_id,amount_minor,currency,status,
                    created_at,updated_at,confirmed_at,checkout_url,idempotency_key
                ) VALUES (?,?,?,5,?,?,100,100,100,?,?)""",
                (order, provider, f"private-charge-{order}-{status}", currency, status,
                 "https://checkout.example.invalid/private", f"private-key-{order}-{status}"),
            )
            await conn.commit()
            return cur.lastrowid

    async def invoke(self, data, actor=1001, chat_type="private", chat_id=None, allowed=True):
        call = SimpleNamespace(
            data=data, from_user=SimpleNamespace(id=actor), answer=AsyncMock(),
            message=SimpleNamespace(chat=SimpleNamespace(type=chat_type, id=actor if chat_id is None else chat_id)),
        )
        render = AsyncMock()
        with patch.object(self.ui, "guard_callback", new=AsyncMock(return_value=allowed)), \
                patch.object(self.ui, "customer_service", self.service), \
                patch.object(self.ui, "render_callback", new=render):
            await self.ui.history_cb(call)
        if render.await_count == 0:
            return None, [], call
        args, kwargs = render.await_args
        buttons = [b for row in kwargs["reply_markup"].inline_keyboard for b in row]
        return args[1], buttons, call

    async def test_ownership_applies_to_both_lists_and_every_detail(self):
        own, foreign = await self.order(), await self.order(1002)
        own_pay, foreign_pay = await self.payment(own), await self.payment(foreign)
        for kind, valid, invalid in (("orders", own, foreign), ("payments", own_pay, foreign_pay)):
            page = await self.service.history_page(1001, kind=kind)
            self.assertEqual([row["id"] for row in page["items"]], [valid])
            self.assertIsNone(await self.service.history_detail(1001, kind=kind, entry_id=invalid))
            text, buttons, _ = await self.invoke(f"client:history:{'order' if kind == 'orders' else 'payment'}:{invalid}:0:{kind}")
            self.assertIn("недоступна", text)
            self.assertIn(f"client:history:{kind}:0", [b.callback_data for b in buttons])

    async def test_bounded_stable_pages_clamp_stale_and_huge_offsets(self):
        ids = [await self.order() for _ in range(19)]
        # All timestamps tie, so stable local ID is the required tie breaker.
        async with aiosqlite.connect(self.db.path) as conn:
            await conn.execute("UPDATE commerce_orders SET created_at=100")
            await conn.commit()
        first = await self.service.history_page(1001)
        second = await self.service.history_page(1001, page=1)
        last = await self.service.history_page(1001, page=10**30)
        self.assertEqual(first["total"], 19)
        self.assertEqual([r["id"] for r in first["items"]], ids[::-1][:8])
        self.assertEqual([r["id"] for r in second["items"]], ids[::-1][8:16])
        self.assertEqual(last["page"], 2)
        self.assertEqual(len(last["items"]), 3)
        text, menu = history_list_view(second)
        callbacks = [b.callback_data for row in menu.inline_keyboard for b in row]
        self.assertIn("client:history:orders:0", callbacks)
        self.assertIn("client:history:orders:2", callbacks)
        self.assertIn("Всего: 19", text)
        await self.db.delete(1001)
        self.assertIsNone(await self.service.history_page(1001, page=2))

    async def test_paid_intent_without_payment_does_not_claim_charge_or_activation(self):
        order = await self.order()
        async with aiosqlite.connect(self.db.path) as conn:
            await conn.execute("UPDATE commerce_orders SET status='paid' WHERE id=?", (order,))
            await conn.commit()
        text, _, _ = await self.invoke(f"client:history:order:{order}:0:orders")
        self.assertIn("Статус заказа: Оплачен", text)
        self.assertIn("списание не подтверждено", text)
        self.assertIn("Период доступа в журнале: Записи нет", text)
        self.assertIn("/paysupport", text)

    async def test_all_payment_attempts_remain_visible_and_latest_order_projection(self):
        order = await self.order()
        failed = await self.payment(order, "failed")
        unknown = await self.payment(order, "unknown")
        page = await self.service.history_page(1001, kind="payments")
        self.assertEqual([p["id"] for p in page["items"]], [unknown, failed])
        entry = await self.service.history_detail(1001, kind="orders", entry_id=order)
        self.assertEqual(entry["payment_id"], unknown)
        text, _, _ = await self.invoke(f"client:history:order:{order}:1:orders")
        self.assertIn("Исход неизвестен", text)
        self.assertIn("не оплачивайте повторно", text)

    async def test_xtr_native_only_no_rub_manual_or_foreign_provider_mix(self):
        order = await self.order()
        rub = await self.order(currency="RUB")
        native = await self.payment(order)
        await self.payment(rub)
        await self.payment(order, "pending", "future_psp")
        await self.payment(order, "failed", currency="RUB")
        self.assertEqual((await self.service.history_page(1001))["total"], 1)
        page = await self.service.history_page(1001, kind="payments")
        self.assertEqual([p["id"] for p in page["items"]], [native])
        self.assertIsNone(await self.service.history_detail(1001, kind="orders", entry_id=rub))

    async def test_refund_unknown_kept_separate_from_payment_and_access(self):
        order = await self.order()
        payment = await self.payment(order)
        async with aiosqlite.connect(self.db.path) as conn:
            await conn.execute(
                """INSERT INTO stars_refund_operations
                (operation_id,payment_id,telegram_id,provider_payment_id,status,requested_by,created_at,updated_at,error)
                VALUES ('private-op',?,1001,'private-charge','unknown',77,100,100,'private-error')""", (payment,),
            )
            await conn.commit()
        text, _, _ = await self.invoke(f"client:history:payment:{payment}:0:payments")
        self.assertIn("Платёж: #", text)
        self.assertIn("Подтверждён", text)
        self.assertIn("Операция возврата: Исход неизвестен", text)
        self.assertIn("Период доступа в журнале: Записи нет", text)
        async with aiosqlite.connect(self.db.path) as conn:
            await conn.execute("UPDATE commerce_payments SET status='refunded' WHERE id=?", (payment,))
            await conn.commit()
        text, _, _ = await self.invoke(f"client:history:payment:{payment}:0:payments")
        self.assertIn("Возвращён", text)

    async def test_misowned_related_rows_and_sensitive_columns_never_escape(self):
        order = await self.order()
        payment = await self.payment(order)
        async with aiosqlite.connect(self.db.path) as conn:
            await conn.execute(
                """INSERT INTO entitlements(telegram_id,order_id,plan_id,status,starts_at,expires_at,created_at,updated_at)
                VALUES (1002,?,?,'active',100,999999,100,100)""", (order, self.plan),
            )
            await conn.execute(
                """INSERT INTO stars_refund_operations
                (operation_id,payment_id,telegram_id,provider_payment_id,status,requested_by,created_at,updated_at)
                VALUES ('private-op',?,1002,'private-charge','success',77,100,100)""", (payment,),
            )
            await conn.execute("UPDATE plans SET name='https://example.invalid/private-sub'")
            await conn.commit()
        for kind, entry_id, action in (("orders", order, "order"), ("payments", payment, "payment")):
            entry = await self.service.history_detail(1001, kind=kind, entry_id=entry_id)
            self.assertIsNone(entry["entitlement_status"])
            self.assertIsNone(entry["refund_status"])
            text, menu = history_detail_view(entry, action, kind, 0)
            public = text + str(menu.model_dump()) + str({k: v for k, v in entry.items() if k != "plan_name"})
            for secret in ("private-charge", "private-key", "checkout_url", "provider_payment_id", "private-sub", "1002"):
                self.assertNotIn(secret, public)
            self.assertIn("Тариф (текущий каталог): недоступен", text)

    async def test_deleted_account_retains_journal_but_cannot_read_it(self):
        order = await self.order()
        payment = await self.payment(order)
        await self.db.delete(1001)
        self.assertIsNotNone(await self.db.get_commerce_order(order))
        for kind, identity in (("orders", order), ("payments", payment)):
            self.assertIsNone(await self.service.history_page(1001, kind=kind))
            self.assertIsNone(await self.service.history_detail(1001, kind=kind, entry_id=identity))
        text, _, _ = await self.invoke("client:history")
        self.assertIn("Аккаунт недоступен", text)

    async def test_duplicate_confirmed_event_does_not_duplicate_history(self):
        order = await self.order()
        await self.commerce.mark_order_awaiting_payment(order)
        args = dict(order_id=order, telegram_id=1001, charge_id="offline-charge", amount=5, raw_payload=b"offline")
        await self.commerce.confirm_telegram_stars_payment(**args)
        await self.commerce.confirm_telegram_stars_payment(**args)
        self.assertEqual((await self.service.history_page(1001))["total"], 1)
        self.assertEqual((await self.service.history_page(1001, kind="payments"))["total"], 1)

    async def test_private_owner_and_portal_guard_precede_all_history_reads(self):
        with patch.object(self.service, "history_page", new=AsyncMock()) as read:
            for kind, chat_id, allowed in (("group", 1001, True), ("private", 1002, True), ("private", 1001, False)):
                text, _, _ = await self.invoke("client:history", chat_type=kind, chat_id=chat_id, allowed=allowed)
                self.assertIsNone(text)
            read.assert_not_awaited()

    async def test_callbacks_fail_closed_and_back_preserves_source_page(self):
        for data in ("client:history:orders:-1", "client:history:payments:9999999999", "client:history:order:0:0:orders",
                     "client:history:order:1:0:admin", "client:history:orders:0:1002", "client:history:refund:1"):
            self.assertIsNone(history_route(data))
            text, _, _ = await self.invoke(data)
            self.assertIsNone(text)
        order = await self.order()
        text, buttons, _ = await self.invoke(f"client:history:order:{order}:2:payments")
        self.assertIn("client:history:payments:2", [b.callback_data for b in buttons])

    async def test_all_navigation_is_read_only_and_terms_publication_fails_closed(self):
        order = await self.order()
        payment = await self.payment(order)
        before = Path(self.db.path).read_bytes()
        with patch.object(self.commerce, "get_or_create_order", new=AsyncMock(side_effect=AssertionError)), \
                patch.object(self.service, "accept_terms", new=AsyncMock(side_effect=AssertionError)):
            for data in ("client:history", "client:history:payments:0",
                         f"client:history:payment:{payment}:0:payments",
                         "client:history:support:orders:0", "client:history:terms:orders:0"):
                text, buttons, _ = await self.invoke(data)
                self.assertIsNotNone(text)
                for button in buttons:
                    self.assertFalse(button.callback_data and any(word in button.callback_data for word in ("refund", "checkout", "cancel", "client:terms:")))
        self.assertEqual(Path(self.db.path).read_bytes(), before)
        self.assertEqual(self.provider.mock_calls, [])
        self.assertEqual(self.service.checkout.mock_calls, [])
        with patch("client_history_ui.get_published_terms", return_value=None):
            text, menu = history_help_view("terms", "payments", 1)
        self.assertIn("не опубликована", text)
        self.assertFalse(any(b.url for row in menu.inline_keyboard for b in row))

    async def test_missing_database_is_not_created_by_history(self):
        db = Database(str(Path(self.tmp.name) / "absent.sqlite3"))
        with self.assertRaises(aiosqlite.OperationalError):
            await db.customer_history_page(1001)
        self.assertFalse(Path(db.path).exists())

    async def test_database_read_failure_is_safe_and_has_a_parent(self):
        with patch.object(self.db, "customer_history_page", new=AsyncMock(side_effect=aiosqlite.OperationalError("private-path"))):
            text, buttons, _ = await self.invoke("client:history")
        self.assertIn("временно недоступен", text)
        self.assertNotIn("private-path", text)
        self.assertIn("client:home", [b.callback_data for b in buttons])

    async def test_own_access_state_and_published_terms_are_read_only(self):
        order = await self.order()
        async with aiosqlite.connect(self.db.path) as conn:
            await conn.execute(
                """INSERT INTO entitlements(telegram_id,order_id,plan_id,status,starts_at,expires_at,created_at,updated_at)
                VALUES (1001,?,?,'active',100,999999,100,100)""", (order, self.plan),
            )
            await conn.commit()
        text, _, _ = await self.invoke(f"client:history:order:{order}:0:orders")
        self.assertIn("Период доступа в журнале: Активен", text)
        self.assertIn("MSK", text)
        publication = SimpleNamespace(revision="v1.0", effective_at=date(2026, 1, 1),
                                      url="https://terms.example.invalid/legal")
        with patch("client_history_ui.get_published_terms", return_value=publication):
            text, menu = history_help_view("terms", "orders", 2)
        self.assertIn("v1.0", text)
        self.assertIn(publication.url, [b.url for row in menu.inline_keyboard for b in row])

    async def test_empty_history_and_inaccessible_message_do_not_dead_end(self):
        text, buttons, _ = await self.invoke("client:history")
        self.assertIn("Записей пока нет", text)
        self.assertIn("client:profile", [b.callback_data for b in buttons])
        call = SimpleNamespace(data="client:history", from_user=SimpleNamespace(id=1001), answer=AsyncMock(), message=None)
        with patch.object(self.ui, "guard_callback", new=AsyncMock(return_value=True)), \
                patch.object(self.service, "history_page", new=AsyncMock()) as read:
            await self.ui.history_cb(call)
        read.assert_not_awaited()
        call.answer.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
