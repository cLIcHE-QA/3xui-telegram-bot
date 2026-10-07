from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from commerce import EntitlementProvisioningService
from customer_service import CustomerPortalService


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
        )
        service = CustomerPortalService(
            db,
            SimpleNamespace(),
            SimpleNamespace(),
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
                )
                service = CustomerPortalService(
                    db,
                    SimpleNamespace(),
                    SimpleNamespace(),
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
        provider = SimpleNamespace(traffic=AsyncMock(return_value=SimpleNamespace()))
        service = CustomerPortalService(
            db, SimpleNamespace(), provider,
            subscription_url_template="https://sub.example/{sub_id}",
        )
        diagnostics = await service.diagnostics(1)
        self.assertEqual(diagnostics.entitlement_status, "expired")

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
