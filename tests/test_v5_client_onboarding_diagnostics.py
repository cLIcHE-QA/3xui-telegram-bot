from pathlib import Path
from types import SimpleNamespace
import time
import unittest
from unittest.mock import AsyncMock, patch

from customer_service import CustomerPortalService, CustomerProviderUnavailable, CustomerTraffic, CustomerProviderAccess, CustomerDiagnostics
from customer_provider_xui import XuiCustomerProvider

ROOT = Path(__file__).resolve().parents[1]


class ClientOnboardingDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_diagnostics_is_read_only_and_reports_entitlement(self):
        db = SimpleNamespace(
            get=AsyncMock(return_value=SimpleNamespace(email="u@example", expiry_time=0, sub_id="secret")),
            get_user_profile=AsyncMock(return_value=None),
            get_plan=AsyncMock(),
            get_latest_entitlement_for_user=AsyncMock(return_value=SimpleNamespace(status="active", expires_at=0)),
        )
        provider = SimpleNamespace(
            access=AsyncMock(return_value=CustomerProviderAccess(enabled=True, expiry_time=0)),
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
        self.assertEqual(result.expiry_comparison, "match")
        self.assertEqual(result.vpn_access_status, "active")
        self.assertFalse(hasattr(service, "reconcile"))

    async def test_diagnostics_degrades_when_provider_read_is_unavailable(self):
        db = SimpleNamespace(
            get=AsyncMock(return_value=SimpleNamespace(email="u@example", expiry_time=0, sub_id="secret")),
            get_user_profile=AsyncMock(return_value=None),
            get_plan=AsyncMock(),
            get_latest_entitlement_for_user=AsyncMock(return_value=None),
        )
        provider = SimpleNamespace(
            access=AsyncMock(side_effect=CustomerProviderUnavailable("down")),
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
        self.assertEqual(result.expiry_comparison, "insufficient_data")
        self.assertEqual(result.vpn_access_status, "unknown")

    async def test_expiry_comparison_uses_available_evidence_only(self):
        now_ms = int(time.time()) * 1000
        future_ms = now_ms + 3_600_000
        expired_ms = now_ms - 3_600_000
        defaults = dict(
            local_expiry=future_ms, ent_status="active",
            ent_expiry=future_ms // 1000, provider_expiry=future_ms,
            provider_known=True, provider_fails=False, provider_enabled=True,
        )
        cases = [
            ("all_three_match", {}, "match", "active"),
            ("tolerance_at_two_seconds", {"provider_expiry": future_ms + 2000}, "match", "active"),
            ("drift_over_two_seconds", {"provider_expiry": future_ms + 2001}, "mismatch", "unknown"),
            ("provider_unavailable", {"provider_fails": True}, "insufficient_data", "unknown"),
            ("known_mismatch_without_provider", {
                "provider_fails": True, "ent_expiry": future_ms // 1000 + 10,
            }, "mismatch", "unknown"),
            ("missing_provider_expiry", {"provider_known": False}, "insufficient_data", "unknown"),
            ("missing_local_expiry", {"local_expiry": None}, "insufficient_data", "active"),
            ("missing_entitlement_expiry", {"ent_expiry": None}, "insufficient_data", "active"),
            ("legacy_without_entitlement", {"ent_status": None}, "match", "active"),
            ("expired_trial", {
                "ent_status": None, "local_expiry": expired_ms, "provider_expiry": expired_ms,
            }, "match", "expired"),
            ("pending_no_entitlement_expiry", {
                "ent_status": "pending", "ent_expiry": None,
            }, "insufficient_data", "provisioning"),
            ("expired_paid_entitlement", {
                "ent_status": "expired", "local_expiry": expired_ms,
                "ent_expiry": expired_ms // 1000, "provider_expiry": expired_ms,
            }, "match", "expired"),
            ("explicit_unlimited", {
                "local_expiry": 0, "ent_expiry": 0, "provider_expiry": 0,
            }, "match", "active"),
            ("finite_vs_unlimited", {"provider_expiry": 0}, "mismatch", "unknown"),
            ("disabled_provider", {"provider_enabled": False}, "match", "disabled"),
        ]
        for name, changes, expected, expected_access in cases:
            with self.subTest(case=name):
                values = {**defaults, **changes}
                entitlement = (
                    SimpleNamespace(status=values["ent_status"], expires_at=values["ent_expiry"])
                    if values["ent_status"] is not None else None
                )
                db = SimpleNamespace(
                    get=AsyncMock(return_value=SimpleNamespace(
                        email="synthetic@example.invalid", expiry_time=values["local_expiry"],
                        sub_id="synthetic-sub",
                    )),
                    get_user_profile=AsyncMock(return_value=None),
                    get_latest_entitlement_for_user=AsyncMock(return_value=entitlement),
                )
                provider_read = (
                    AsyncMock(side_effect=CustomerProviderUnavailable("offline"))
                    if values["provider_fails"]
                    else AsyncMock(return_value=CustomerProviderAccess(
                        enabled=values["provider_enabled"],
                        expiry_time=values["provider_expiry"],
                        expiry_available=values["provider_known"],
                    ))
                )
                service = CustomerPortalService(
                    db, SimpleNamespace(), SimpleNamespace(access=provider_read),
                    subscription_url_template="https://sub.example/compat/{sub_id}",
                )
                result = await service.diagnostics(42)
                self.assertEqual(result.expiry_comparison, expected)
                self.assertEqual(result.vpn_access_status, expected_access)
                self.assertEqual(result.expiry_drift, expected == "mismatch")
                self.assertEqual("не совпадают" in result.note, expected == "mismatch")
                db.get.assert_awaited_once_with(42)
                db.get_latest_entitlement_for_user.assert_awaited_once_with(42)
                provider_read.assert_awaited_once_with("synthetic@example.invalid")

    async def test_xui_adapter_keeps_omitted_expiry_distinct_from_unlimited(self):
        for client, expected_known in [
            ({"enable": True}, False),
            ({"enable": True, "expiryTime": None}, False),
            ({"enable": True, "expiryTime": ""}, False),
            ({"enable": True, "expiryTime": 0}, True),
        ]:
            with self.subTest(client=client):
                xui = SimpleNamespace(get_client=AsyncMock(return_value={"client": client}))
                result = await XuiCustomerProvider(xui).access("synthetic@example.invalid")
                self.assertEqual(result.expiry_available, expected_known)

    async def test_ui_displays_three_distinct_expiry_states_without_mutations(self):
        import client_access

        for state, label in [
            ("match", "✅ Сроки совпадают"),
            ("insufficient_data", "⚪ Недостаточно данных для сравнения"),
            ("mismatch", "⚠️ Сроки не совпадают"),
        ]:
            with self.subTest(state=state):
                result = CustomerDiagnostics(
                    account_exists=True, entitlement_status="active",
                    provider_reachable=True, vpn_access_status="active",
                    expiry_comparison=state,
                )
                call = SimpleNamespace(from_user=SimpleNamespace(id=42), answer=AsyncMock())
                diagnostics = AsyncMock(return_value=result)
                with patch.object(
                    client_access, "guard_callback", new=AsyncMock(return_value=True)
                ), patch.object(
                    client_access, "_service",
                    return_value=SimpleNamespace(diagnostics=diagnostics),
                ), patch.object(
                    client_access, "render_callback", new=AsyncMock()
                ) as rendered:
                    await client_access.diagnostics_cb(call)
                self.assertIn("Сроки: " + label, rendered.await_args.args[1])
                diagnostics.assert_awaited_once_with(42)
                call.answer.assert_awaited_once()
                buttons = rendered.await_args.kwargs["reply_markup"].inline_keyboard
                self.assertEqual(buttons[0][0].callback_data, "client:diagnostics")
                self.assertEqual(buttons[1][0].callback_data, "client:help")

    def test_client_ui_keeps_qr_local_private_and_diagnostics_non_mutating(self):
        source = (ROOT / "client_access.py").read_text(encoding="utf-8")
        self.assertIn("qr_png(url)", source)
        self.assertIn('chat.type != "private"', source)
        self.assertIn('callback_data="client:diagnostics"', source)
        self.assertNotIn("await _service().reconcile", source)
        self.assertNotIn("aiohttp", source)
        self.assertNotIn("httpx", source)
        for label in ("✅ Сроки совпадают", "⚪ Недостаточно данных для сравнения", "⚠️ Сроки не совпадают"):
            self.assertIn(label, source)
        self.assertNotIn("согласованы / нет данных", source)


if __name__ == "__main__":
    unittest.main()
