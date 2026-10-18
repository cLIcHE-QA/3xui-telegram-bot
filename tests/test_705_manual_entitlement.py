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

    async def test_empty_inbounds_rejected_before_grant(self):
        async def empty_inbounds():
            return []
        self.xui.inbound_options = empty_inbounds
        with self.assertRaisesRegex(ValueError, "нет доступных Inbounds"):
            await self._grant()
        self.assertIsNone(await self.db.get_live_manual_entitlement(101))
        self.assertEqual((await self.db.get_user_profile(101)).plan_id, self.finite)
        self.assertEqual(self.xui.update_calls, 0)

    async def test_finite_assignment_verifies_remote_before_local_commit(self):
        result = await self.engine.assign_finite_plan(101, self.finite)
        self.assertTrue(result.limits_applied)
        self.assertEqual((await self.db.get_user_profile(101)).plan_id, self.finite)
        self.assertEqual(self.xui.update_calls, 1)
        self.assertGreater((await self.db.get(101)).expiry_time, 0)

    async def test_finite_assignment_failure_preserves_local_plan_and_expiry(self):
        second = await self.db.create_plan(
            name="another finite", duration_days=90, traffic_gb=5, ip_limit=1,
            price_minor=54000, currency="RUB", stars_price=80,
        )
        self.xui.omit_expiry = True
        with self.assertRaises(Exception):
            await self.engine.assign_finite_plan(101, second)
        self.assertEqual((await self.db.get_user_profile(101)).plan_id, self.finite)
        self.assertEqual((await self.db.get(101)).expiry_time, 1_900_000_000_000)
        self.assertEqual(self.xui.update_calls, 1)

    async def test_finite_assignment_rejects_empty_policy_before_mutation(self):
        async def no_inbounds():
            return []
        self.xui.inbound_options = no_inbounds
        with self.assertRaises(ValueError):
            await self.engine.assign_finite_plan(101, self.finite)
        self.assertEqual(self.xui.update_calls, 0)

    async def test_bulk_manual_plan_callback_does_not_reach_mutations(self):
        source = (Path(__file__).resolve().parents[1] / "advanced_users.py").read_text()
        bulk = source.split("async def bulk_run_plan(", 1)[1].split(
            "async def bulk_run_group(", 1
        )[0]
        self.assertIn("plan.duration_days == 0", bulk)

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

    def test_indefinite_wizard_skips_payment_and_enforces_limits_early(self):
        source = (Path(__file__).resolve().parents[1] / "catalog_admin.py").read_text(encoding="utf-8")
        duration = source.split("async def plan_add_duration(", 1)[1].split(
            "async def plan_add_traffic(", 1
        )[0]
        self.assertIn('if value == 0:', duration)
        self.assertIn('stars_price=0, visibility="admin_only"', duration)
        self.assertIn('traffic_gb=0, price_minor=0, currency="RUB"', duration)
        hwid = source.split("async def plan_add_hwid_limit(", 1)[1].split(
            "async def plan_add_price(", 1
        )[0]
        self.assertIn('if int(data["duration_days"]) == 0:', hwid)
        self.assertIn("await _plan_add_group_keyboard()", hwid)
        self.assertIn("admin:planadd:backip", source)
        self.assertIn("int(data[\"hwid_limit\"])", source)
        self.assertIn("int(data[\"ip_limit\"])", source)

    async def test_bounded_indefinite_grant_readback_and_switch(self):
        bounded = await self.db.create_plan(
            name="indefinite-limits", duration_days=0, traffic_gb=0, ip_limit=2,
            hwid_limit=5, price_minor=0, rub_price_enabled=False,
            currency="RUB", stars_price=0, visibility="admin_only",
        )
        record, created = await self.svc.grant(telegram_id=101, plan_id=bounded, actor_id=1)
        self.assertTrue(created)
        self.assertEqual(record.status, "active")
        self.assertEqual(
            {key: self.xui.limits[key] for key in ("expiryTime", "totalGB", "limitIp", "limitHwid")},
            {"expiryTime": 0, "totalGB": 0, "limitIp": 2, "limitHwid": 5},
        )
        self.assertEqual((await self.svc.review(telegram_id=101, actor_id=1)).status, "active")
        switched = await self.svc.switch_to_finite(
            telegram_id=101, plan_id=self.finite, actor_id=1,
        )
        self.assertEqual(switched.status, "superseded")
        self.assertEqual(self.xui.update_calls, 2)

    async def test_bounded_indefinite_mismatch_is_unknown_no_replay(self):
        bounded = await self.db.create_plan(
            name="mismatch-limits", duration_days=0, traffic_gb=0, ip_limit=2,
            hwid_limit=5, price_minor=0, rub_price_enabled=False,
            currency="RUB", stars_price=0, visibility="admin_only",
        )
        previous_update = self.xui.update_client

        async def mismatched_update(email, **kwargs):
            await previous_update(email, **kwargs)
            self.xui.limits["limitHwid"] = 0

        self.xui.update_client = mismatched_update
        with self.assertRaises(ManualEntitlementUnknown):
            await self.svc.grant(telegram_id=101, plan_id=bounded, actor_id=1)
        self.assertEqual((await self.db.get_live_manual_entitlement(101)).status, "unknown")
        before = self.xui.update_calls
        with self.assertRaises(ValueError):
            await self.svc.grant(telegram_id=101, plan_id=bounded, actor_id=1)
        self.assertEqual(self.xui.update_calls, before)

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

    async def test_read_only_review_recovers_unknown_after_restart(self):
        self.xui.omit_expiry = True
        with self.assertRaises(ManualEntitlementUnknown):
            await self._grant()
        self.assertEqual((await self.db.get_live_manual_entitlement(101)).status, "unknown")
        before = self.xui.update_calls
        self.xui.omit_expiry = False
        restarted = Database(self.path)
        await restarted.init()
        svc = ManualEntitlementService(
            restarted, ProvisioningEngine(restarted, self.xui, settings()),
        )
        result = await svc.review(telegram_id=101, actor_id=2)
        self.assertEqual((result.status, result.result_code),
                         ("active", "operator_readback_match"))
        self.assertEqual(self.xui.update_calls, before)
        self.assertEqual((await restarted.get(101)).expiry_time, 0)

    async def test_unresolved_grant_blocks_background_sync_after_restart(self):
        from provisioning import ProvisioningUnknown
        self.xui.omit_expiry = True
        with self.assertRaises(ManualEntitlementUnknown):
            await self._grant()
        before = self.xui.update_calls
        with self.assertRaises(ProvisioningUnknown):
            await self.engine.sync_user(101, apply_plan_limits=True)
        self.assertEqual(self.xui.update_calls, before)
        with self.assertRaises(ManualEntitlementUnknown):
            await self.svc.review(telegram_id=101, actor_id=1)

    def test_manual_callbacks_need_admin_rbac(self):
        from admin_privileges import required_role_for_callback
        self.assertEqual(required_role_for_callback(
            "admin:u:manualrun:0123456789abcdef"), "admin")
        self.assertEqual(required_role_for_callback(
            "admin:u:manualcheck:101"), "admin")
        self.assertIsNone(required_role_for_callback(
            "admin:u:manualrun:forged"))

    async def test_uncertain_provider_ack_is_resolved_by_readback_without_replay(self):
        self.xui.uncertain_update = True
        result, created = await self._grant()
        self.assertTrue(created)
        self.assertEqual(result.status, "active")
        self.assertEqual(self.xui.update_calls, 1)

    async def test_active_manual_switch_to_finite_is_verified_and_atomic(self):
        active, _ = await self._grant()
        result = await self.svc.switch_to_finite(
            telegram_id=101, plan_id=self.finite, actor_id=1,
        )
        self.assertEqual(result.status, "superseded")
        self.assertEqual((await self.db.get_user_profile(101)).plan_id, self.finite)
        self.assertGreater((await self.db.get(101)).expiry_time, 0)
        self.assertIsNone(await self.db.get_live_manual_entitlement(101))
        self.assertEqual(self.xui.update_calls, 2)
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute(
                "SELECT status FROM manual_entitlements WHERE id=?", (active.id,)
            ).fetchone()[0], "superseded")

    async def test_switch_unknown_keeps_journal_and_read_only_recovery(self):
        await self._grant()
        self.xui.omit_expiry = True
        with self.assertRaises(ManualEntitlementUnknown):
            await self.svc.switch_to_finite(
                telegram_id=101, plan_id=self.finite, actor_id=1,
            )
        record = await self.db.get_live_manual_entitlement(101)
        self.assertEqual(record.status, "active")
        self.xui.omit_expiry = False
        self.xui.uncertain_update = True
        self.xui.limits = {"expiryTime": 0, "totalGB": 0, "limitIp": 0}
        switched = await self.svc.switch_to_finite(
            telegram_id=101, plan_id=self.finite, actor_id=1,
        )
        self.assertEqual(switched.status, "superseded")

    async def test_switch_after_unknown_remote_readback_never_replays(self):
        await self._grant()
        self.xui.uncertain_update = True
        self.xui.omit_expiry = True
        with self.assertRaises(ManualEntitlementUnknown):
            await self.svc.switch_to_finite(
                telegram_id=101, plan_id=self.finite, actor_id=1,
            )
        self.assertEqual((await self.db.get_live_manual_entitlement(101)).status, "active")

    def test_switch_callback_requires_admin(self):
        from admin_privileges import required_role_for_callback
        self.assertEqual(required_role_for_callback(
            "admin:u:manualswitch:0123456789abcdef"), "admin")
        self.assertIsNone(required_role_for_callback(
            "admin:u:manualswitch:forged"))

    async def _manual_switch_fixture(self):
        group = await self.db.create_server_group(name="manual switch test")
        await self.db.set_server_group_member(group, "master", True)
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE plans SET server_group_id=? WHERE id=?", (group, self.manual))
            conn.commit()
        await self.db.set_user_server_group(101, group)
        target = await self.db.create_plan(
            name="new lifetime", duration_days=0, traffic_gb=0,
            ip_limit=2, hwid_limit=5, price_minor=0, currency="RUB",
            stars_price=0, rub_price_enabled=False, visibility="admin_only",
            server_group_id=group,
        )
        old, _ = await self._grant()
        return old, target

    async def test_manual_to_manual_success_preserves_journal_and_no_payments(self):
        old, target = await self._manual_switch_fixture()
        result = await self.svc.switch_to_manual(
            telegram_id=101, plan_id=target, actor_id=12,
        )
        self.assertEqual((result.status, result.plan_id, result.previous_plan_id),
                         ("active", target, self.manual))
        self.assertEqual((await self.db.get_user_profile(101)).plan_id, target)
        self.assertEqual((await self.db.get(101)).expiry_time, 0)
        self.assertEqual((self.xui.update_calls, self.xui.attach_calls), (2, 1))
        self.assertEqual(self.xui.limits["limitIp"], 2)
        self.assertEqual(self.xui.limits["limitHwid"], 5)
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                "SELECT status, plan_id FROM manual_entitlements ORDER BY id"
            ).fetchall()
            self.assertEqual(rows, [("superseded", self.manual), ("active", target)])
            for table in ("commerce_orders", "commerce_payments", "entitlements", "payments"):
                self.assertEqual(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)

    async def test_manual_to_manual_rejects_bad_target_and_pending_order_before_mutation(self):
        old, target = await self._manual_switch_fixture()
        initial_calls = self.xui.update_calls
        with self.assertRaises(ValueError):
            await self.svc.switch_to_manual(telegram_id=101, plan_id=old.plan_id, actor_id=12)
        with self.assertRaises(ValueError):
            await self.svc.switch_to_manual(telegram_id=101, plan_id=self.finite, actor_id=12)
        other_group = await self.db.create_server_group(name="other group")
        cross = await self.db.create_plan(
            name="cross", duration_days=0, traffic_gb=0, ip_limit=0,
            price_minor=0, currency="RUB", stars_price=0,
            rub_price_enabled=False, visibility="admin_only",
            server_group_id=other_group,
        )
        with self.assertRaises(ValueError):
            await self.svc.switch_to_manual(telegram_id=101, plan_id=cross, actor_id=12)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT INTO commerce_orders(telegram_id,plan_id,amount_minor,currency,status,created_at,updated_at,paid_at) "
                "VALUES(101,?,50,'XTR','awaiting_payment',1,1,0)", (self.finite,)
            )
            conn.commit()
        with self.assertRaises(ValueError):
            await self.svc.switch_to_manual(telegram_id=101, plan_id=target, actor_id=12)
        self.assertEqual(self.xui.update_calls, initial_calls)
        self.assertEqual((await self.db.get_live_manual_entitlement(101)).status, "active")

    async def test_manual_to_manual_unknown_no_replay_and_recovery_after_restart(self):
        old, target = await self._manual_switch_fixture()
        # Первоначальный read-only preflight проходит; поле expiry теряется
        # только ПОСЛЕ единственной provider mutation.
        original_update = self.xui.update_client
        async def lose_readback(email, **kwargs):
            await original_update(email, **kwargs)
            self.xui.omit_expiry = True
        self.xui.update_client = lose_readback
        with self.assertRaises(ManualEntitlementUnknown):
            await self.svc.switch_to_manual(telegram_id=101, plan_id=target, actor_id=12)
        current = await self.db.get_live_manual_entitlement(101)
        self.assertEqual(current.status, "unknown")
        calls = self.xui.update_calls
        with self.assertRaises(ValueError):
            await self.svc.switch_to_manual(telegram_id=101, plan_id=target, actor_id=12)
        self.assertEqual(self.xui.update_calls, calls)
        self.xui.omit_expiry = False
        restarted = Database(self.path)
        await restarted.init()
        service = ManualEntitlementService(
            restarted, ProvisioningEngine(restarted, self.xui, settings()),
        )
        recovered = await service.review(telegram_id=101, actor_id=13)
        self.assertEqual((recovered.status, recovered.plan_id), ("active", target))
        self.assertEqual(self.xui.update_calls, calls)
        self.assertEqual((await restarted.get_user_profile(101)).plan_id, target)

    async def test_manual_to_manual_readback_mismatch_blocks_recovery(self):
        old, target = await self._manual_switch_fixture()
        previous = self.xui.update_client
        async def mismatch(email, **kwargs):
            await previous(email, **kwargs)
            self.xui.limits["limitIp"] = 77
        self.xui.update_client = mismatch
        with self.assertRaises(ManualEntitlementUnknown):
            await self.svc.switch_to_manual(telegram_id=101, plan_id=target, actor_id=12)
        calls = self.xui.update_calls
        with self.assertRaises(ManualEntitlementUnknown):
            await self.svc.review(telegram_id=101, actor_id=12)
        self.assertEqual(self.xui.update_calls, calls)
        self.assertEqual((await self.db.get_user_profile(101)).plan_id, self.manual)

    def test_manual_replace_callback_is_admin_only(self):
        from admin_privileges import required_role_for_callback
        self.assertEqual(required_role_for_callback(
            "admin:u:manualreplace:0123456789abcdef"), "admin")
        self.assertIsNone(required_role_for_callback("admin:u:manualreplace:forged"))
        source = (Path(__file__).resolve().parents[1] / "advanced_users.py").read_text()
        self.assertIn("await guard(call, minimum=\"admin\")", source.split(
            "async def manual_plan_replace_run(", 1)[1].split(
            "@advanced_users_router.callback_query", 1)[0])
        self.assertIn("callback_data=f\"admin:u:manualreplace:{nonce}\"", source)

    def test_bounded_manual_plan_ui_preflight_accepts_independent_limits(self):
        source = (Path(__file__).resolve().parents[1] / "advanced_users.py").read_text(encoding="utf-8")
        handler = source.split("async def user_plan_set(", 1)[1].split(
            "async def user_plan_assign_run(", 1
        )[0]
        self.assertNotIn("or plan.traffic_gb or plan.ip_limit", handler)
        self.assertIn("0 <= plan.ip_limit <= 1000", handler)
        self.assertIn("0 <= plan.hwid_limit <= 1000", handler)
        self.assertIn("manual_grant_commerce_block_reason(tg_id)", handler)
        self.assertLess(handler.index("manual_grant_commerce_block_reason(tg_id)"),
                        handler.index("_manual_grant_challenges[int(call.from_user.id)]"))
        run = source.split("async def manual_plan_grant_run(", 1)[1].split(
            "async def manual_plan_switch_run(", 1
        )[0]
        self.assertIn("except ValueError as exc:", run)
        self.assertIn("except ManualEntitlementUnknown as exc:", run)
        self.assertIn("mutation_not_started=true", run)

    async def test_commerce_preflight_is_read_only_and_atomic_fence_remains(self):
        self.assertIsNone(await self.db.manual_grant_commerce_block_reason(101))
        order_id = await self.db.create_commerce_order(
            telegram_id=101, plan_id=self.finite, amount_minor=50, currency="XTR",
        )
        before = await self.db.get_user_profile(101)
        reason = await self.db.manual_grant_commerce_block_reason(101)
        self.assertIn("Незавершённый заказ", reason)
        self.assertEqual((await self.db.get_user_profile(101)).plan_id, before.plan_id)
        self.assertIsNone(await self.db.get_live_manual_entitlement(101))
        with self.assertRaisesRegex(ValueError, "pending commerce"):
            await self._grant()
        self.assertEqual(self.xui.update_calls, 0)
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE commerce_orders SET status='cancelled' WHERE id=?", (order_id,))
            conn.commit()
        self.assertIsNone(await self.db.manual_grant_commerce_block_reason(101))

    async def test_pending_entitlement_preflight_blocks_even_without_open_order(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT INTO entitlements(telegram_id,order_id,plan_id,status,created_at,updated_at)"
                " VALUES (101,888,?,'provisioning',1,1)", (self.finite,),
            )
            conn.commit()
        reason = await self.db.manual_grant_commerce_block_reason(101)
        self.assertIn("entitlement", reason)
        with self.assertRaisesRegex(ValueError, "pending commerce"):
            await self._grant()
        self.assertEqual(self.xui.update_calls, 0)
        self.assertIsNone(await self.db.get_live_manual_entitlement(101))

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

    async def test_client_purchase_block_reason_matches_manual_status(self):
        from commerce import CommerceService
        from customer_service import CustomerPortalService

        portal = CustomerPortalService(
            self.db, CommerceService(self.db), provider=None,
            subscription_url_template="https://sub.example.invalid/{sub_id}",
        )
        self.assertIsNone(await portal.manual_purchase_block_reason(101))
        await self._grant()
        reason = await portal.manual_purchase_block_reason(101)
        self.assertIn("действует подписка, назначенная администратором", reason)
        self.assertEqual(await portal.active_plans(101), [])
        with self.assertRaises(ValueError):
            await portal.get_or_create_stars_order(
                telegram_id=101, plan=await self.db.get_plan(self.finite),
            )
        self.assertIsNone(await self.db.get_live_manual_entitlement(999))
        self.assertIsNone(await portal.manual_purchase_block_reason(999))

    async def test_client_purchase_block_reason_unknown_grant_hides_checkout(self):
        from commerce import CommerceService
        from customer_service import CustomerPortalService
        self.xui.omit_expiry = True
        with self.assertRaises(ManualEntitlementUnknown):
            await self._grant()
        portal = CustomerPortalService(
            self.db, CommerceService(self.db), provider=None,
            subscription_url_template="https://sub.example.invalid/{sub_id}",
        )
        reason = await portal.manual_purchase_block_reason(101)
        self.assertIn("идёт проверка", reason)
        self.assertEqual(await portal.active_plans(101), [])
        self.assertEqual(self.xui.update_calls, 1)

    async def test_client_purchase_block_reason_fail_closed_when_db_unavailable(self):
        from commerce import CommerceService
        from customer_service import CustomerPortalService
        from unittest.mock import AsyncMock
        portal = CustomerPortalService(
            self.db, CommerceService(self.db), provider=None,
            subscription_url_template="https://sub.example.invalid/{sub_id}",
        )
        portal.db.get_live_manual_entitlement = AsyncMock(side_effect=RuntimeError("storage unavailable"))
        reason = await portal.manual_purchase_block_reason(101)
        self.assertIn("Проверить право покупки сейчас не удалось", reason)

    def test_client_buy_renders_manual_grant_reason_before_empty_catalog(self):
        source = (Path(__file__).resolve().parents[1] / "client_access.py").read_text(encoding="utf-8")
        buy = source.split("async def buy_cb(", 1)[1].split("async def plan_cb(", 1)[0]
        self.assertLess(buy.index("manual_purchase_block_reason"), buy.index("active_plans("))
        self.assertIn("reply_markup=back_menu()", buy)

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
        with self.assertRaises(ValueError):
            await self.db.delete_plan(self.manual)
        with self.assertRaises(ValueError):
            await self.db.create_or_get_open_commerce_order(
                telegram_id=101, plan_id=self.finite, amount_minor=50, currency="XTR",
            )
        self.assertIsNotNone(await self.db.get_plan(self.manual))
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
