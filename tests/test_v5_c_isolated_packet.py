"""C1-C4 deterministic no-network acceptance tests for synthetic pilot identities.

Run on a clean isolated GitHub checkout, never on a production VPS.
Do not load a production .env, DB, subscription, Telegram, or 3x-ui API.
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from client_rate_limit import SlidingWindowRateLimiter
from commerce import CommerceService, EntitlementProvisioningService
from db import Database, UserRecord
from provisioning import ProvisioningEngine, ProvisioningUnknown
from xui import InboundOption, XUIMutationError

FAKE_ENV = {
    "BOT_TOKEN": "123456789:synthetic-offline-only",
    "PANEL_URL": "https://panel.example.invalid",
    "PANEL_API_TOKEN": "synthetic-offline-token",
    "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/{sub_id}",
    "ALLOWED_TELEGRAM_IDS": "1001,1002",
    "ADMIN_TELEGRAM_IDS": "9001",
}


def portal_module():
    with patch.dict(os.environ, FAKE_ENV):
        import client_access
    return client_access


class C1DurableUnknownTests(unittest.IsolatedAsyncioTestCase):
    async def test_quota_unknown_survives_service_reinit_without_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_file = Path(tmp) / "synthetic.sqlite3"
            db = Database(str(db_file))
            await db.init()
            commerce = CommerceService(db)
            plan_id = await db.create_plan(
                name="Offline finite", duration_days=30, traffic_gb=1,
                ip_limit=1, price_minor=100, currency="RUB",
            )
            await db.put(UserRecord(
                telegram_id=1001, email="a@example.invalid",
                sub_id="synthetic-sub-a", expiry_time=0, created_at=1,
            ))
            order = await commerce.create_order(
                telegram_id=1001, plan_id=plan_id,
                amount_minor=100, currency="RUB",
            )
            payment = await commerce.create_payment(
                order_id=order.id, provider="test",
                provider_payment_id="synthetic-payment-1",
            )
            _, _, _, entitlement, _ = await commerce.apply_confirmed_payment_event(
                provider="test", provider_event_id="synthetic-event-1",
                provider_payment_id=payment.provider_payment_id,
                raw_payload=b"offline-test", signature_valid=True,
            )

            class LostReplyProvider:
                def __init__(self):
                    self.sync_calls = 0
                    self.reset_calls = 0

                async def sync_user(self, *args, **kwargs):
                    self.sync_calls += 1
                    return SimpleNamespace(remaining_missing_ids=[])

                async def reset_user_traffic(self, _telegram_id):
                    self.reset_calls += 1
                    raise XUIMutationError(
                        "synthetic lost reply", code="network_error", uncertain=True,
                    )

            fake = LostReplyProvider()
            with self.assertRaisesRegex(ProvisioningUnknown, "mutation_not_retried=true"):
                await EntitlementProvisioningService(db, fake).reconcile(entitlement.id)
            self.assertEqual((fake.sync_calls, fake.reset_calls), (1, 1))
            original = await db.get_entitlement(entitlement.id)
            self.assertEqual(
                (original.status, original.quota_reset_status),
                ("provisioning", "unknown"),
            )

            # New service and SQLite connection simulate restart, no docker.
            db_reopened = Database(str(db_file))
            await db_reopened.init()
            summary = await EntitlementProvisioningService(
                db_reopened, fake
            ).reconcile_pending()
            self.assertGreaterEqual(summary.get("unknown", 0), 1)
            self.assertEqual(summary.get("active", 0), 0)
            self.assertEqual((fake.sync_calls, fake.reset_calls), (1, 1))
            persisted = await db_reopened.get_entitlement(entitlement.id)
            self.assertEqual(
                (persisted.status, persisted.quota_reset_status),
                ("provisioning", "unknown"),
            )
            self.assertEqual(
                (await db_reopened.get_commerce_payment(payment.id)).status,
                "confirmed",
            )
            with sqlite3.connect(db_file) as conn:
                self.assertEqual(conn.execute(
                    "SELECT COUNT(*) FROM entitlements WHERE order_id=?",
                    (order.id,),
                ).fetchone()[0], 1)
                self.assertEqual(conn.execute(
                    "SELECT expiry_time FROM users WHERE telegram_id=1001"
                ).fetchone()[0], 0)


class C2ForgedOwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def test_forged_callbacks_use_auth_identity_not_foreign_target(self):
        portal = portal_module()
        service = SimpleNamespace(
            profile=AsyncMock(return_value=SimpleNamespace(exists=False)),
            subscription_url=AsyncMock(
                return_value="https://sub.example.invalid/only-a"
            ),
            traffic=AsyncMock(return_value=SimpleNamespace(
                up=1, down=2, total=10,
            )),
            devices=AsyncMock(return_value=[]),
        )
        flags = SimpleNamespace(snapshot=AsyncMock(
            return_value=SimpleNamespace(portal_enabled=True)
        ))
        bot = SimpleNamespace(send_photo=AsyncMock())
        call = SimpleNamespace(
            from_user=SimpleNamespace(id=1001), data="client:profile",
            answer=AsyncMock(), bot=bot,
            message=SimpleNamespace(chat=SimpleNamespace(id=1001, type="private")),
        )
        with patch.object(portal, "feature_flags", flags), patch.object(
            portal, "is_allowed", side_effect=lambda uid: uid in (1001, 1002)
        ), patch.object(
            portal, "client_rate_limiter",
            SlidingWindowRateLimiter(limit=30, window_seconds=60),
        ), patch.object(portal, "_service", return_value=service), patch.object(
            portal, "render_callback", new_callable=AsyncMock
        ), patch.object(portal, "qr_png", return_value=b"fake-png") as qr:
            # Direct handler calls are stricter than router's data filters.
            for handler, forged_data in (
                (portal.profile_cb, "client:profile:1002"),
                (portal.subscription_cb, "client:subscription:1002"),
                (portal.traffic_cb, "client:traffic:1002"),
                (portal.devices_cb, "client:devices:1002"),
            ):
                call.data = forged_data
                await handler(call)
            call.data = "client:onboard:qr"
            await portal.onboarding_platform_cb(call)
            qr.assert_called_once_with("https://sub.example.invalid/only-a")
            bot.send_photo.assert_awaited_once()
        for operation in (
            service.profile, service.subscription_url, service.traffic, service.devices
        ):
            operation.assert_awaited()
            self.assertTrue(all(
                entry.args[0] == 1001 for entry in operation.await_args_list
            ))

    async def test_foreign_payment_payload_fails_before_order_lookup(self):
        portal = portal_module()
        service = SimpleNamespace(validate_stars_precheckout=AsyncMock())
        query = SimpleNamespace(
            from_user=SimpleNamespace(id=1001),
            invoice_payload=portal.stars_payload(
                order_id=55, telegram_id=1002,
            ),
            currency="XTR", total_amount=100, answer=AsyncMock(),
        )
        with patch.object(
            portal, "payment_acceptance_enabled",
            new=AsyncMock(return_value=True),
        ), patch.object(portal, "is_allowed", return_value=True), patch.object(
            portal, "_service", return_value=service
        ):
            await portal.stars_pre_checkout(query)
        query.answer.assert_awaited_once_with(
            ok=False, error_message="Платёж не прошёл проверку владельца."
        )
        service.validate_stars_precheckout.assert_not_awaited()

    async def test_forged_owner_admin_callback_fails_closed(self):
        import admin_auth
        db = SimpleNamespace(get_administrator=AsyncMock(return_value=None))
        settings = SimpleNamespace(admin_telegram_ids=(9001,))
        call = SimpleNamespace(
            from_user=SimpleNamespace(id=1001, username="fake"),
            data="admin:botupd", answer=AsyncMock(),
        )
        with patch.object(admin_auth, "is_private_admin_event", return_value=True):
            self.assertEqual(
                await admin_auth.authorize_callback(db, settings, call),
                (False, None),
            )
            call.answer.assert_awaited_once()
            db.get_administrator = AsyncMock(return_value=SimpleNamespace(
                enabled=1, role="read_only",
            ))
            call.answer.reset_mock()
            self.assertEqual(
                await admin_auth.authorize_callback(db, settings, call),
                (False, "read_only"),
            )
            call.answer.assert_awaited_once()


class C3BoundedConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_rate_limits_remain_per_customer(self):
        portal = portal_module()
        limiter = SlidingWindowRateLimiter(limit=30, window_seconds=60)
        flags = SimpleNamespace(snapshot=AsyncMock(
            return_value=SimpleNamespace(portal_enabled=True)
        ))
        def fake_call(uid):
            return SimpleNamespace(
                from_user=SimpleNamespace(id=uid), answer=AsyncMock(),
            )
        first = [fake_call(1001) for _ in range(40)]
        second = fake_call(1002)
        with patch.object(portal, "feature_flags", flags), patch.object(
            portal, "is_allowed", return_value=True
        ), patch.object(portal, "client_rate_limiter", limiter):
            results = await asyncio.gather(*(
                portal.guard_callback(c) for c in [*first, second]
            ))
        self.assertEqual(sum(results[:40]), 30)
        self.assertTrue(results[40])
        self.assertEqual(len(limiter._events[1001]), 30)
        self.assertEqual(len(limiter._events[1002]), 1)
        self.assertEqual(sum(c.answer.await_count for c in first), 10)
        second.answer.assert_not_awaited()

    async def test_oversized_plan_callback_never_creates_order(self):
        portal = portal_module()
        service = SimpleNamespace(
            profile=AsyncMock(return_value=SimpleNamespace(exists=True)),
            active_plan=AsyncMock(return_value=None),
            get_or_create_stars_order=AsyncMock(),
        )
        call = SimpleNamespace(
            from_user=SimpleNamespace(id=1001),
            data="client:plan:" + "9" * 5000, answer=AsyncMock(),
        )
        with patch.object(
            portal, "guard_callback", new=AsyncMock(return_value=True)
        ), patch.object(
            portal, "payment_acceptance_enabled",
            new=AsyncMock(return_value=True),
        ), patch.object(portal, "_service", return_value=service):
            await portal.plan_cb(call)
        call.answer.assert_awaited()
        service.get_or_create_stars_order.assert_not_awaited()


class C4NodeOfflineReturnTests(unittest.IsolatedAsyncioTestCase):
    async def test_mock_node_offline_online_reconcile_once(self):
        # Reuse existing fake objects, not existing TestCase (no duplicate tests).
        import test_v416_provisioning as fixture
        db = fixture.FakeProvisioningDB()
        db.groups[7] = SimpleNamespace(
            id=7, name="MockGroup", description="", created_at=0,
        )
        db.profiles[1] = SimpleNamespace(
            telegram_id=1, plan_id=None, server_group_id=7,
        )
        db.members[7] = {"master", "node_2"}
        node = SimpleNamespace(
            id=2, enable=True, status="offline", transitive=False,
        )
        fake = fixture.FakeProvisioningXUI(
            [
                InboundOption(
                    id=10, remark="master", tag="master",
                    protocol="vless", port=10010, enable=True, node_id=None,
                ),
                InboundOption(
                    id=20, remark="node", tag="node",
                    protocol="vless", port=10020, enable=True, node_id=2,
                ),
            ],
            nodes=[node], client_ids={"one@example.test": set()},
        )
        engine = ProvisioningEngine(db, fake, fixture.settings())
        offline = await engine.sync_user(1, strict=False)
        self.assertEqual(offline.policy.desired_inbound_ids, [10, 20])
        self.assertEqual(offline.policy.actionable_inbound_ids, [10])
        self.assertEqual(offline.policy.unavailable_members, ["node_2"])
        self.assertEqual(offline.remaining_missing_ids, [20])
        self.assertEqual(fake.attach_calls, [("one@example.test", [10])])
        node.status = "online"
        recovered = await engine.sync_user(1, strict=False)
        self.assertEqual(recovered.remaining_missing_ids, [])
        self.assertEqual(fake.attach_calls, [
            ("one@example.test", [10]),
            ("one@example.test", [20]),
        ])
        await engine.sync_user(1, strict=False)
        self.assertEqual(len(fake.attach_calls), 2)
        self.assertEqual(fake.client_ids["one@example.test"], {10, 20})
        self.assertEqual(fake.detach_calls, [])
