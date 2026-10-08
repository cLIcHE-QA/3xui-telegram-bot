from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class V5Rc2CanaryFindingsTests(unittest.TestCase):
    def test_client_home_separates_period_and_actual_vpn_access(self):
        source = (ROOT / "client_access.py").read_text(encoding="utf-8")
        self.assertIn('f"💳 Период: {customer_period_label(profile.period_status)}"', source)
        self.assertIn('f"🌐 VPN-доступ: {customer_access_label(profile.access_status)}"', source)
        self.assertIn('"disabled": "⛔ отключён"', source)
        self.assertIn('"unknown": "⚪ статус неизвестен"', source)

    def test_dynamic_stars_plan_buttons_have_leading_semantic_emoji(self):
        source = (ROOT / "client_access.py").read_text(encoding="utf-8")
        self.assertIn('f"💎 {plan.name} · ⭐ {plan.stars_price}"', source)
        self.assertIn('f"💎 {plan.name} · Stars не настроены"', source)

    def test_subscription_command_uses_canonical_heading(self):
        source = (ROOT / "client_access.py").read_text(encoding="utf-8")
        self.assertIn('"🌐 Моя подписка\\n\\n" + (url or "Подписка пока не оформлена.")', source)

    def test_payment_support_has_one_guarded_command_renderer(self):
        source = (ROOT / "client_access.py").read_text(encoding="utf-8")
        self.assertEqual(
            source.count('@client_access_router.message(Command("paysupport"))'),
            1,
        )
        self.assertIn('"💳 Поддержка по оплате\\n\\n"', source)
        self.assertIn("if not await guard_message(message):", source)


if __name__ == "__main__":
    unittest.main()
