from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from customer_service import CustomerPortalService, CustomerProviderUnavailable, CustomerTraffic

ROOT = Path(__file__).resolve().parents[1]


class ClientOnboardingDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_diagnostics_is_read_only_and_reports_entitlement(self):
        db = SimpleNamespace(
            get=AsyncMock(return_value=SimpleNamespace(email="u@example", expiry_time=0, sub_id="secret")),
            get_user_profile=AsyncMock(return_value=None),
            get_plan=AsyncMock(),
            get_latest_entitlement_for_user=AsyncMock(return_value=SimpleNamespace(status="active")),
        )
        provider = SimpleNamespace(
            traffic=AsyncMock(return_value=CustomerTraffic(up=1, down=2, total=10)),
            devices=AsyncMock(),
        )
        service = CustomerPortalService(
            db, SimpleNamespace(), provider,
            subscription_url_template="https://sub.example/compat/{sub_id}",
        )
        result = await service.diagnostics(42)
        self.assertTrue(result.account_exists)
        self.assertEqual(result.entitlement_status, "active")
        self.assertTrue(result.subscription_available)
        self.assertTrue(result.provider_reachable)
        self.assertFalse(hasattr(service, "reconcile"))

    async def test_diagnostics_degrades_when_provider_read_is_unavailable(self):
        db = SimpleNamespace(
            get=AsyncMock(return_value=SimpleNamespace(email="u@example", expiry_time=0, sub_id="secret")),
            get_user_profile=AsyncMock(return_value=None),
            get_plan=AsyncMock(),
            get_latest_entitlement_for_user=AsyncMock(return_value=None),
        )
        provider = SimpleNamespace(
            traffic=AsyncMock(side_effect=CustomerProviderUnavailable("down")),
            devices=AsyncMock(),
        )
        service = CustomerPortalService(
            db, SimpleNamespace(), provider,
            subscription_url_template="https://sub.example/compat/{sub_id}",
        )
        result = await service.diagnostics(42)
        self.assertEqual(result.entitlement_status, "legacy")
        self.assertFalse(result.provider_reachable)

    def test_client_ui_keeps_qr_local_private_and_diagnostics_non_mutating(self):
        source = (ROOT / "client_access.py").read_text(encoding="utf-8")
        self.assertIn("qr_png(url)", source)
        self.assertIn('chat.type != "private"', source)
        self.assertIn('callback_data="client:diagnostics"', source)
        self.assertNotIn("await _service().reconcile", source)
        self.assertNotIn("aiohttp", source)
        self.assertNotIn("httpx", source)


if __name__ == "__main__":
    unittest.main()
