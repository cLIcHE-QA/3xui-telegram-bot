from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class V5Rc1CanaryFindingsTests(unittest.TestCase):
    def test_stars_admin_ledger_has_runtime_aiosqlite_dependency(self):
        source = (ROOT / "business_admin.py").read_text(encoding="utf-8")
        self.assertIn("import aiosqlite", source)
        self.assertIn('F.data == "admin:starspayments"', source)
        self.assertIn("async with aiosqlite.connect(db.path)", source)

    def test_expired_customer_status_is_not_hardcoded_active(self):
        source = (ROOT / "client_access.py").read_text(encoding="utf-8")
        self.assertIn("profile.access_status", source)
        self.assertNotIn('f"🌐 Подписка: активна"', source)

    def test_runtime_reconciles_due_entitlement_expiry_locally(self):
        runtime = (ROOT / "app_runtime.py").read_text(encoding="utf-8")
        commerce = (ROOT / "commerce.py").read_text(encoding="utf-8")
        self.assertIn("entitlement_provisioning_service.expire_due", runtime)
        self.assertIn("list_expired_active_entitlements", commerce)
        self.assertIn('target_status="expired"', commerce)


if __name__ == "__main__":
    unittest.main()
