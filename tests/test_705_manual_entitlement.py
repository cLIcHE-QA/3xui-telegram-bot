"""#705: offline end-to-end ручной grant → ProvisioningEngine → fake 3x-ui.

Тестовый provider не подключается к реальным панелям или Telegram.
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from commerce import CommerceIntegrityError, EntitlementProvisioningService
from db import Database, UserRecord
from manual_entitlements import ManualEntitlementService, ManualEntitlementUnknown
from provisioning import ProvisioningEngine
from xui import InboundOption, XUIMutationError


class FakeXUI:
    def __init__(self):
        self.attachments = set()
        self.limits = {"expiryTime": 1_900_000_000_000, "totalGB": 1024, "limitIp": 3}
        self.update_calls = 0
        self.attach_calls = 0
        self.omit_expiry = False
        self.uncertain_update = False

    async def inbound_options(self):
        return [InboundOption(id=11, remark="test", tag="test", protocol="vless",
                              port=443, enable=True, node_id=None)]

    async def nodes_list(self):
        return []

    async def get_client(self, email):
        fields = dict(self.limits)
        if self.omit_expiry:
            fields.pop("expiryTime", None)
        return {"client": {"email": email, **fields}, "inboundIds": sorted(self.attachments)}

    async def attach_client(self, email, ids):
        self.attach_calls += 1
        self.attachments.update(ids)

    async def update_client(self, email, **kwargs):
        self.update_calls += 1
        self.limits.update(kwargs)
        if self.uncertain_update:
            raise XUIMutationError("lost ACK", code="lost_response", uncertain=True)

    async def bulk_adjust_clients(self, emails, **kwargs):
        raise AssertionError("flow must not change in manual grant")


def settings():
    return SimpleNamespace(
        inbound_ids=(), ignored_protocols=(), ignored_tags=(),
        allowed_ports=(), allowed_protocols=(), vless_flow="",
    )


class ManualEntitlementTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "bot.sqlite3")
        self.db = Database(self.path)
        await self.db.init()
        await self.db.put(UserRecord(
            telegram_id=101, email="manual@example.invalid", sub_id="private-sub",
            expiry_time=1_900_000_000_000, created_at=1,
        ))
        self.finite = await self.db.create_plan(
            name="finite", duration_days=30, traffic_gb=1, ip_limit=2,
            price_minor=20000, currency="RUB", stars_price=50,
        )
        await self.db.set_user_plan(101, self.finite)
        self.manual = await self.db.create_plan(
            name="for family", duration_days=0, traffic_gb=0, ip_limit=0,
            price_minor=0, currency="RUB", stars_price=0,
            rub_price_enabled=False, visibility="admin_only",
        )
        self.xui = FakeXUI()
        self.engine = ProvisioningEngine(self.db, self.xui, settings())
        self.svc = ManualEntitlementService(self.db, self.engine)

    async def asyncTearDown(self):
        self.temp.cleanup()

    async def _grant(self):
        return await self.svc.grant(telegram_id=101, plan_id=self.manual, actor_id=1)

    async def test_grant_updates_provider_then_readback_once_without_payments(self):
        record, created = await self._grant()
        self.assertTrue(created)
        self.assertEqual((record.status, record.result_code, record.expires_at if hasattr(record, "expires_at") else 0),
                         ("active", "provider_readback_match", 0))
        self.assertGreater(record.confirmed_at, 0)
        self.assertEqual((self.xui.update_calls, self.xui.attach_calls), (1, 1))
        self.assertEqual(self.xui.limits, {"expiryTime": 0, "totalGB": 0, "limitIp": 0})
        self.assertEqual((await self.db.get(101)).expiry_time, 0)
        self.assertEqual((await self.db.get_user_profile(101)).plan_id, self.manual)
        self.assertEqual(record.previous_plan_id, self.finite)
        with sqlite3.connect(self.path) as conn:
            for table in ("commerce_orders", "commerce_payments", "entitlements", "payments"):
                self.assertEqual(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)

    async def test_repeat_after_restart_is_idempotent_and_does_not_replay_provider(self):
        first, _ = await self._grant()
        restarted = Database(self.path)
        await restarted.init()
        fresh_engine = ProvisioningEngine(restarted, self.xui, settings())
        again, created = await ManualEntitlementService(restarted, fresh_engine).grant(
            telegram_id=101, plan_id=self.manual, actor_id=1,
        )
        self.assertFalse(created)
        self.assertEqual(again.id, first.id)
        self.assertEqual((self.xui.update_calls, self.xui.attach_calls), (1, 1))
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM manual_entitlements").fetchone()[0], 1)

    async def test_missing_expiry_readback_becomes_unknown_and_blocks_retry(self):
        self.xui.omit_expiry = True
        with self.assertRaises(ManualEntitlementUnknown):
            await self._grant()
        rec = await self.db.get_live_manual_entitlement(101)
        self.assertEqual(rec.status, "unknown")
        self.assertEqual((await self.db.get(101)).expiry_time, 1_900_000_000_000)
        before = self.xui.update_calls
        restarted = Database(self.path)
        await restarted.init()
        with self.assertRaises(ValueError):
            await ManualEntitlementService(
                restarted, ProvisioningEngine(restarted, self.xui, settings()),
            ).grant(telegram_id=101, plan_id=self.manual, actor_id=1)
        self.assertEqual(self.xui.update_calls, before)

    async def test_uncertain_provider_ack_is_resolved_by_readback_without_replay(self):
        self.xui.uncertain_update = True
        result, created = await self._grant()
        self.assertTrue(created)
        self.assertEqual(result.status, "active")
        self.assertEqual(self.xui.update_calls, 1)

    async def test_existing_checkout_blocks_new_manual_grant(self):
        await self.db.create_commerce_order(
            telegram_id=101, plan_id=self.finite, amount_minor=50, currency="XTR",
        )
        with self.assertRaisesRegex(ValueError, "pending commerce"):
            await self._grant()
        self.assertIsNone(await self.db.get_live_manual_entitlement(101))
        self.assertEqual(self.xui.update_calls, 0)

    async def test_indefinite_direct_edit_rejected_and_finite_unchanged(self):
        with self.assertRaises(ValueError):
            await self.db.update_plan_catalog(self.manual, price_minor=100)
        with self.assertRaises(ValueError):
            await self.db.update_plan_catalog(self.manual, visibility="all")
        with self.assertRaises(ValueError):
            await self.db.set_plan_stars_price(self.manual, 3)
        unchanged = await self.db.get_plan(self.manual)
        self.assertEqual((unchanged.duration_days, unchanged.price_minor,
                          unchanged.stars_price, unchanged.visibility), (0, 0, 0, "admin_only"))
        finite = await self.db.get_plan(self.finite)
        self.assertEqual((finite.duration_days, finite.stars_price), (30, 50))

    async def test_live_manual_grant_hides_new_paid_purchases(self):
        from commerce import CommerceService
        from customer_service import CustomerPortalService
        await self._grant()
        portal = CustomerPortalService(
            self.db, CommerceService(self.db), provider=None,
            subscription_url_template="https://sub.example.invalid/{sub_id}",
        )
        self.assertEqual(await portal.active_plans(101), [])
        with self.assertRaises(ValueError):
            await portal.get_or_create_stars_order(
                telegram_id=101, plan=await self.db.get_plan(self.finite),
            )

    async def test_invalid_target_is_rejected_before_remote_mutation(self):
        with self.assertRaises(ValueError):
            await self.svc.grant(telegram_id=101, plan_id=self.finite, actor_id=1)
        with self.assertRaises(ValueError):
            await self.svc.grant(telegram_id=999, plan_id=self.manual, actor_id=1)
        with self.assertRaises(ValueError):
            await self.svc.grant(telegram_id=101, plan_id=self.manual, actor_id=0)
        self.assertEqual(self.xui.update_calls, 0)

    async def test_live_grant_blocks_ordinary_plan_change_and_paid_renewal(self):
        record, _ = await self._grant()
        with self.assertRaises(ValueError):
            await self.db.set_user_plan(101, self.finite)
        self.assertEqual((await self.db.get_live_manual_entitlement(101)).id, record.id)
        # Paid renewal bridge must not overwrite unlimited expiry with an old order.
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT INTO entitlements(telegram_id,order_id,plan_id,status,created_at,updated_at)"
                " VALUES (101,999,?,'pending',1,1)", (self.finite,),
            )
            eid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()
        with self.assertRaises(CommerceIntegrityError):
            await EntitlementProvisioningService(self.db, self.engine).reconcile(eid)
        self.assertEqual((await self.db.get(101)).expiry_time, 0)


if __name__ == "__main__":
    unittest.main()
