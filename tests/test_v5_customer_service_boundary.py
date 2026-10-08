from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from customer_service import (
    CustomerDevice,
    CustomerProviderAccess,
    CustomerPortalService,
    CustomerTraffic,
)


ROOT = Path(__file__).resolve().parents[1]


class CustomerServiceBoundaryTests(unittest.IsolatedAsyncioTestCase):
    def test_client_portal_has_no_direct_provider_or_storage_dependency(self):
        source = (ROOT / "client_access.py").read_text(encoding="utf-8")
        for forbidden in (
            "from xui import",
            "XUIClient",
            "XUIError",
            "from db import",
            "Database(",
            "from commerce import",
            "CommerceService(",
            "await xui.",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        self.assertIn("CustomerPortalService", source)
        self.assertIn("configure_client_access", source)

    def test_customer_domain_contract_is_provider_neutral(self):
        service = (ROOT / "customer_service.py").read_text(encoding="utf-8")
        adapter = (ROOT / "customer_provider_xui.py").read_text(encoding="utf-8")
        runtime = (ROOT / "app_runtime.py").read_text(encoding="utf-8")

        self.assertIn("class CustomerAccessProvider(Protocol)", service)
        self.assertNotIn("from xui import", service)
        self.assertNotIn("XUIClient", service)
        self.assertIn("class XuiCustomerProvider", adapter)
        self.assertIn("from xui import XUIClient, XUIError", adapter)
        self.assertIn("XuiCustomerProvider(commerce_xui)", runtime)
        self.assertIn("configure_client_access(customer_portal_service)", runtime)

    async def test_service_resolves_profile_subscription_and_provider_reads(self):
        db = SimpleNamespace(
            get=AsyncMock(return_value=SimpleNamespace(
                email="tg-42@example.invalid",
                expiry_time=1234567890000,
                sub_id="secret-sub-id",
            )),
            get_user_profile=AsyncMock(return_value=SimpleNamespace(
                display_name="Test User",
                plan_id=7,
            )),
            get_plan=AsyncMock(return_value=SimpleNamespace(
                id=7,
                name="Pilot",
                active=True,
                price_minor=500,
                currency="EUR",
            )),
            list_plans=AsyncMock(return_value=[]),
            get_latest_entitlement_for_user=AsyncMock(return_value=None),
        )
        commerce = SimpleNamespace(get_or_create_order=AsyncMock())
        provider = SimpleNamespace(
            access=AsyncMock(return_value=CustomerProviderAccess(enabled=True, expiry_time=1234567890000)),
            traffic=AsyncMock(return_value=CustomerTraffic(up=10, down=20, total=100)),
            devices=AsyncMock(return_value=[
                CustomerDevice(title="Phone", os_name="iOS", last_seen=123),
            ]),
        )
        service = CustomerPortalService(
            db,
            commerce,
            provider,
            subscription_url_template="https://sub.example/compat/{sub_id}",
        )

        profile = await service.profile(42)
        self.assertTrue(profile.exists)
        self.assertEqual(profile.email, "tg-42@example.invalid")
        self.assertEqual(profile.display_name, "Test User")
        self.assertEqual(profile.plan_name, "Pilot")
        self.assertEqual(profile.access_status, "expired")
        provider.access.assert_awaited_once_with("tg-42@example.invalid")
        self.assertEqual(
            await service.subscription_url(42),
            "https://sub.example/compat/secret-sub-id",
        )

        traffic = await service.traffic(42)
        self.assertEqual((traffic.up, traffic.down, traffic.total), (10, 20, 100))
        provider.traffic.assert_awaited_once_with("tg-42@example.invalid")

        devices = await service.devices(42)
        self.assertEqual(devices[0].title, "Phone")
        provider.devices.assert_awaited_once_with("tg-42@example.invalid")

    async def test_missing_customer_does_not_call_provider(self):
        db = SimpleNamespace(
            get=AsyncMock(return_value=None),
            get_user_profile=AsyncMock(),
            get_plan=AsyncMock(),
            list_plans=AsyncMock(return_value=[]),
            get_latest_entitlement_for_user=AsyncMock(return_value=None),
        )
        provider = SimpleNamespace(
            access=AsyncMock(),
            traffic=AsyncMock(),
            devices=AsyncMock(),
        )
        service = CustomerPortalService(
            db,
            SimpleNamespace(get_or_create_order=AsyncMock()),
            provider,
            subscription_url_template="https://sub.example/compat/{sub_id}",
        )

        self.assertFalse((await service.profile(99)).exists)
        self.assertIsNone(await service.subscription_url(99))
        self.assertIsNone(await service.traffic(99))
        self.assertIsNone(await service.devices(99))
        provider.access.assert_not_awaited()
        provider.traffic.assert_not_awaited()
        provider.devices.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
