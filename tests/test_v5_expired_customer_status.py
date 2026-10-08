from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from commerce import EntitlementProvisioningService
from customer_service import CustomerPortalService, CustomerProviderAccess, CustomerProviderUnavailable


ROOT = Path(__file__).resolve().parents[1]


class ExpiredCustomerStatusTests(unittest.IsolatedAsyncioTestCase):
    async def test_profile_marks_past_expiry_as_expired(self):
        db = SimpleNamespace(
            get=AsyncMock(return_value=SimpleNamespace(
                email="expired@example.invalid",
                expiry_time=int(time.time() * 1000) - 1000,
                sub_id="secret",
            )),
            get_user_profile=AsyncMock(return_value=SimpleNamespace(
                display_name="Expired", plan_id=None,
            )),
            get_latest_entitlement_for_user=AsyncMock(return_value=None),
        )
        service = CustomerPortalService(
            db,
            SimpleNamespace(),
            SimpleNamespace(access=AsyncMock(return_value=CustomerProviderAccess(enabled=True, expiry_time=int(time.time() * 1000) + 60_000))),
            subscription_url_template="https://sub.example/{sub_id}",
        )
        profile = await service.profile(1)
        self.assertTrue(profile.exists)
        self.assertEqual(profile.access_status, "expired")

    async def test_profile_marks_future_and_unlimited_expiry_active(self):
        for expiry in (0, int(time.time() * 1000) + 60_000):
            with self.subTest(expiry=expiry):
                db = SimpleNamespace(
                    get=AsyncMock(return_value=SimpleNamespace(
                        email="active@example.invalid",
                        expiry_time=expiry,
                        sub_id="secret",
                    )),
                    get_user_profile=AsyncMock(return_value=SimpleNamespace(
                        display_name="Active", plan_id=None,
                    )),
                    get_latest_entitlement_for_user=AsyncMock(return_value=None),
                )
                service = CustomerPortalService(
                    db,
                    SimpleNamespace(),
                    SimpleNamespace(access=AsyncMock(return_value=CustomerProviderAccess(enabled=True, expiry_time=expiry))),
                    subscription_url_template="https://sub.example/{sub_id}",
                )
                self.assertEqual((await service.profile(1)).access_status, "active")

    async def test_diagnostics_effectively_expires_stale_entitlement(self):
        now = int(time.time())
        db = SimpleNamespace(
            get=AsyncMock(return_value=SimpleNamespace(
                email="expired@example.invalid",
                expiry_time=(now - 1) * 1000,
                sub_id="secret",
            )),
            get_user_profile=AsyncMock(return_value=SimpleNamespace(
                display_name="Expired", plan_id=None,
            )),
            get_latest_entitlement_for_user=AsyncMock(return_value=SimpleNamespace(
                status="active", expires_at=now - 1,
            )),
        )
        provider = SimpleNamespace(access=AsyncMock(return_value=CustomerProviderAccess(enabled=True, expiry_time=(now - 1) * 1000)))
        service = CustomerPortalService(
            db, SimpleNamespace(), provider,
            subscription_url_template="https://sub.example/{sub_id}",
        )
        diagnostics = await service.diagnostics(1)
        self.assertEqual(diagnostics.entitlement_status, "expired")

    async def test_disabled_provider_overrides_paid_future_expiry(self):
        now = int(time.time() * 1000)
        db = SimpleNamespace(
            get=AsyncMock(return_value=SimpleNamespace(email="test@example.invalid", expiry_time=now + 300000, sub_id="secret")),
            get_user_profile=AsyncMock(return_value=SimpleNamespace(display_name="Test", plan_id=None)),
            get_latest_entitlement_for_user=AsyncMock(return_value=SimpleNamespace(status="active", expires_at=(now + 300000) // 1000)),
        )
        provider = SimpleNamespace(access=AsyncMock(return_value=CustomerProviderAccess(enabled=False, expiry_time=now + 300000)))
        svc = CustomerPortalService(db, SimpleNamespace(), provider, subscription_url_template="https://sub.example/{sub_id}")
        result = await svc.profile(1)
        self.assertEqual(result.access_status, "disabled")
        self.assertEqual(result.period_status, "active")
        self.assertFalse(result.expiry_drift)
        provider.access.assert_awaited_once_with("test@example.invalid")

    async def test_provider_unavailable_is_unknown_not_active(self):
        now = int(time.time() * 1000)
        db = SimpleNamespace(
            get=AsyncMock(return_value=SimpleNamespace(email="test@example.invalid", expiry_time=now + 300000, sub_id="secret")),
            get_user_profile=AsyncMock(return_value=None),
            get_latest_entitlement_for_user=AsyncMock(return_value=None),
        )
        provider = SimpleNamespace(access=AsyncMock(side_effect=CustomerProviderUnavailable("offline")))
        svc = CustomerPortalService(db, SimpleNamespace(), provider, subscription_url_template="https://sub.example/{sub_id}")
        result = await svc.profile(1)
        self.assertEqual(result.access_status, "unknown")
        self.assertEqual(result.provider_status, "unavailable")

    async def test_paid_period_drift_is_reported_without_mutations(self):
        now = int(time.time() * 1000)
        expiry = now + 300000
        db = SimpleNamespace(
            get=AsyncMock(return_value=SimpleNamespace(email="test@example.invalid", expiry_time=expiry + 3600000, sub_id="secret")),
            get_user_profile=AsyncMock(return_value=None),
            get_latest_entitlement_for_user=AsyncMock(return_value=SimpleNamespace(status="active", expires_at=expiry // 1000)),
        )
        provider = SimpleNamespace(access=AsyncMock(return_value=CustomerProviderAccess(enabled=True, expiry_time=expiry + 3600000)))
        svc = CustomerPortalService(db, SimpleNamespace(), provider, subscription_url_template="https://sub.example/{sub_id}")
        result = await svc.profile(1)
        self.assertTrue(result.expiry_drift)
        self.assertEqual(result.access_status, "unknown")
        diagnostics = await svc.diagnostics(1)
        self.assertTrue(diagnostics.expiry_drift)
        self.assertIn("не совпадают", diagnostics.note)
        db.get_latest_entitlement_for_user.assert_awaited()

    async def test_expire_due_is_local_transition_only(self):
        due = [
            SimpleNamespace(id=11, status="active"),
            SimpleNamespace(id=12, status="suspended"),
        ]
        db = SimpleNamespace(
            list_expired_active_entitlements=AsyncMock(return_value=due),
            transition_entitlement=AsyncMock(side_effect=due),
        )
        provisioner = SimpleNamespace(sync_user=AsyncMock())
        service = EntitlementProvisioningService(db, provisioner)

        self.assertEqual(await service.expire_due(limit=10), 2)
        self.assertEqual(db.transition_entitlement.await_count, 2)
        provisioner.sync_user.assert_not_awaited()

    def test_portal_does_not_hardcode_active_subscription(self):
        source = (ROOT / "client_access.py").read_text(encoding="utf-8")
        self.assertNotIn('f"🌐 Подписка: активна"', source)
        self.assertIn("profile.access_status", source)


if __name__ == "__main__":
    unittest.main()
