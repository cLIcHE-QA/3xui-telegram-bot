from __future__ import annotations

from pathlib import Path
import unittest

from client_rate_limit import SlidingWindowRateLimiter

ROOT = Path(__file__).resolve().parents[1]


class ClientLaunchReadinessTests(unittest.TestCase):
    def test_rate_limiter_is_per_user_and_sliding(self):
        limiter = SlidingWindowRateLimiter(limit=2, window_seconds=10)
        self.assertTrue(limiter.allow(1, now=0))
        self.assertTrue(limiter.allow(1, now=1))
        self.assertFalse(limiter.allow(1, now=2))
        self.assertTrue(limiter.allow(2, now=2))
        self.assertTrue(limiter.allow(1, now=11))

    def test_customer_ui_has_independent_portal_and_payment_switches(self):
        source = (ROOT / "client_access.py").read_text(encoding="utf-8")
        self.assertIn("settings.client_portal_enabled", source)
        self.assertIn("settings.client_payment_acceptance_enabled", source)
        self.assertIn("client_rate_limiter.allow", source)

    def test_payment_kill_switch_does_not_drop_successful_payment_handler(self):
        source = (ROOT / "client_access.py").read_text(encoding="utf-8")
        start = source.index("async def stars_successful_payment")
        end = source.index("async def payment_support", start)
        handler = source[start:end]
        self.assertNotIn("payment_acceptance_enabled()", handler)
        self.assertIn("confirm_stars_payment", handler)

    def test_env_example_documents_emergency_controls(self):
        env = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn("CLIENT_PORTAL_ENABLED=true", env)
        self.assertIn("CLIENT_PAYMENT_ACCEPTANCE_ENABLED=true", env)
        self.assertIn("CLIENT_RATE_LIMIT_COUNT=30", env)
        self.assertIn("CLIENT_RATE_LIMIT_WINDOW_SECONDS=60", env)


if __name__ == "__main__":
    unittest.main()
