from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V5LaunchAuditContractTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_customer_ui_cannot_import_admin_or_storage_backends(self):
        source = self.read("client_access.py")
        for forbidden in (
            "from db import", "Database(", "from xui import", "XUIClient",
            "from commerce import", "CommerceService(", "admin:",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_stars_identity_and_quote_are_revalidated_server_side(self):
        ui = self.read("client_access.py")
        service = self.read("customer_service.py")
        db = self.read("db.py")
        self.assertIn("telegram_id != query.from_user.id", ui)
        self.assertIn('query.currency != "XTR"', ui)
        self.assertIn("validate_stars_precheckout", ui)
        self.assertIn("int(order.telegram_id) == int(telegram_id)", service)
        self.assertIn('str(order.currency) == "XTR"', service)
        self.assertIn("int(order.amount_minor) == int(amount)", service)
        self.assertIn("confirm_telegram_stars_payment", db)

    def test_payment_journal_and_identity_are_idempotent(self):
        migrations = self.read("db_migrations.py")
        commerce = self.read("db.py")
        self.assertIn("idx_commerce_payments_provider_identity", migrations)
        self.assertIn("idx_payment_webhook_provider_event", migrations)
        self.assertIn("INSERT OR IGNORE INTO payment_webhook_events", commerce)

    def test_subscription_secret_and_qr_controls_remain_present(self):
        ui = self.read("client_access.py")
        self.assertIn('chat.type != "private"', ui)
        self.assertIn("qr_png(url)", ui)
        self.assertIn("секрет", ui.lower())
        self.assertNotIn("api.qrserver", ui)

    def test_launch_has_abuse_and_rollback_controls(self):
        ui = self.read("client_access.py")
        config = self.read("config.py")
        self.assertIn("client_rate_limiter.allow", ui)
        self.assertIn("CLIENT_PORTAL_ENABLED", config)
        self.assertIn("CLIENT_PAYMENT_ACCEPTANCE_ENABLED", config)

    def test_customer_diagnostics_do_not_trigger_mutation_recovery(self):
        ui = self.read("client_access.py")
        start = ui.index("async def diagnostics_cb")
        end = ui.index("async def pay_support_cb", start)
        block = ui[start:end]
        self.assertNotIn("reconcile(", block)
        self.assertNotIn("provision", block.lower())


if __name__ == "__main__":
    unittest.main()
