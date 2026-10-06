from __future__ import annotations

from pathlib import Path
import unittest

from admin_privileges import required_role_for_callback


ROOT = Path(__file__).resolve().parents[1]


class V4250UserSafetySubscriptionTests(unittest.TestCase):
    def test_user_card_uses_canonical_sections_without_extend_shortcut(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        card = source.split("async def render_user", 1)[1].split(
            "async def _user_plan_view", 1
        )[0]
        self.assertNotIn('text="⏳ Продлить"', card)
        self.assertNotIn('callback_data=f"adminextend:{tg_id}"', card)
        for label in (
            "💎 Тариф", "📅 Срок", "📊 Трафик", "🌐 Доступ",
            "📱 Подключения", "🔗 Подписка", "💳 Платежи",
            "🧾 Активность", "✏️ Профиль", "⚙️ Ещё действия",
        ):
            self.assertIn(f'text="{label}"', card)

    def test_subscription_has_open_show_and_local_qr(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        view = source.split("async def _user_subscription_view", 1)[1].split(
            "async def _user_profile_view", 1
        )[0]
        self.assertIn('text="🌐 Открыть ссылку"', view)
        self.assertIn('text="🔗 Показать URL"', view)
        self.assertIn('text="🔳 QR-код"', view)
        handler = source.split(
            '@advanced_users_router.callback_query(F.data.startswith("admin:u:subqr:"))',
            1,
        )[1].split(
            '@advanced_users_router.callback_query(F.data.startswith("admin:u:profile:"))',
            1,
        )[0]
        self.assertIn("qr_png(sub_url(rec.sub_id))", handler)
        self.assertIn("BufferedInputFile", handler)
        self.assertNotIn("aiohttp", handler)
        self.assertNotIn("httpx", handler)

    def test_subscription_qr_is_read_only(self):
        self.assertEqual(required_role_for_callback("admin:u:subqr:101"), "read_only")

    def test_vless_flow_sync_is_support_and_does_not_attach_or_detach(self):
        self.assertEqual(required_role_for_callback("admin:u:flowask:101"), "support")
        self.assertEqual(required_role_for_callback("admin:u:flowrun:101"), "support")
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        run = source.split(
            '@advanced_users_router.callback_query(F.data.startswith("admin:u:flowrun:"))',
            1,
        )[1].split(
            '@advanced_users_router.callback_query(F.data.startswith("admin:u:expiry:"))',
            1,
        )[0]
        self.assertIn("bulk_adjust_clients([rec.email], flow=settings.vless_flow)", run)
        self.assertNotIn("attach_client(", run)
        self.assertNotIn("detach_client(", run)
        self.assertIn("inbound_mutation=false", run)

    def test_disable_enable_are_confirmation_first(self):
        self.assertEqual(required_role_for_callback("admindisable:101"), "support")
        self.assertEqual(required_role_for_callback("admindisablerun:101"), "support")
        self.assertEqual(required_role_for_callback("adminenable:101"), "support")
        self.assertEqual(required_role_for_callback("adminenablerun:101"), "support")
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")

        disable_ask = source.split(
            '@advanced_users_router.callback_query(F.data.startswith("admindisable:"))',
            1,
        )[1].split(
            '@advanced_users_router.callback_query(F.data.startswith("admindisablerun:"))',
            1,
        )[0]
        self.assertNotIn("update_client(", disable_ask)
        self.assertIn('callback_data=f"admindisablerun:{tg_id}"', disable_ask)

        disable_run = source.split(
            '@advanced_users_router.callback_query(F.data.startswith("admindisablerun:"))',
            1,
        )[1].split(
            '@advanced_users_router.callback_query(F.data.startswith("adminenable:"))',
            1,
        )[0]
        self.assertEqual(disable_run.count("_update_client_with_readback("), 1)

        enable_ask = source.split(
            '@advanced_users_router.callback_query(F.data.startswith("adminenable:"))',
            1,
        )[1].split(
            '@advanced_users_router.callback_query(F.data.startswith("adminenablerun:"))',
            1,
        )[0]
        self.assertNotIn("update_client(", enable_ask)
        self.assertIn('callback_data=f"adminenablerun:{tg_id}"', enable_ask)

        enable_run = source.split(
            '@advanced_users_router.callback_query(F.data.startswith("adminenablerun:"))',
            1,
        )[1].split(
            '@advanced_users_router.callback_query(F.data.startswith("admindelask:"))',
            1,
        )[0]
        self.assertEqual(enable_run.count("_update_client_with_readback("), 1)


if __name__ == "__main__":
    unittest.main()
