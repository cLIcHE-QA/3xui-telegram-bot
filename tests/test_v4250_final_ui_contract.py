from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class V4250FinalUiContractTests(unittest.TestCase):
    def test_plan_view_shows_plan_and_current_user_parameters(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        view = source.split("async def _user_plan_view", 1)[1].split(
            "async def _user_expiry_view", 1
        )[0]
        for text in (
            "Стоимость:",
            "Период:",
            "Параметры тарифа:",
            "Текущие параметры пользователя:",
            "🗂 Группа серверов:",
        ):
            self.assertIn(text, view)
        self.assertIn("money_text(plan.price_minor, plan.currency)", view)
        self.assertIn("xui.get_client(rec.email)", view)

    def test_subscription_masks_identity_and_presents_state(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        view = source.split("async def _user_subscription_view", 1)[1].split(
            "async def _user_profile_view", 1
        )[0]
        self.assertIn("masked_sub_id(rec.sub_id)", view)
        self.assertIn("Статус:", view)
        self.assertIn("🟢 активна", view)
        self.assertIn("⛔ отключена", view)
        self.assertIn("⌛ истекла", view)
        self.assertNotIn("ID: {rec.sub_id}", view)

    def test_empty_vless_flow_is_presented_as_not_configured(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        handler = source.split("async def user_access_config", 1)[1].split(
            "async def user_flow_sync_ask", 1
        )[0]
        self.assertIn('"не настроен" if not settings.vless_flow', handler)
        self.assertIn("if settings.vless_flow:", handler)

    def test_detail_back_helpers_match_canonical_parents(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        expected = (
            ('text="⬅ Тариф"', 'admin:u:planview:'),
            ('text="⬅ Срок"', 'admin:u:expiryview:'),
            ('text="⬅ Трафик"', 'admin:u:trafficview:'),
            ('text="⬅ Параметры доступа"', 'admin:u:accesscfg:'),
            ('text="⬅ Подписка"', 'admin:u:subview:'),
            ('text="⬅ Профиль"', 'admin:u:profile:'),
        )
        for label, callback in expected:
            with self.subTest(callback=callback):
                self.assertIn(label, source)
                self.assertIn(callback, source)

    def test_return_to_detail_screen_clears_fsm(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        renderer = source.split("async def _render_user_section", 1)[1].split(
            '@advanced_users_router.callback_query(F.data.startswith("admin:u:planview:"))',
            1,
        )[0]
        self.assertIn("state: FSMContext | None = None", renderer)
        self.assertIn("await state.clear()", renderer)
        for handler in (
            "user_plan_view",
            "user_expiry_view",
            "user_traffic_view",
            "user_access_view",
            "user_subscription_view",
            "user_profile_view",
        ):
            self.assertIn(f"async def {handler}(call: CallbackQuery, state: FSMContext)", source)

    def test_v425_dynamic_callbacks_fit_telegram_limit_for_64_bit_ids(self):
        max_id = 9_223_372_036_854_775_807
        callbacks = (
            f"admin:u:devdelask:{max_id}:{max_id}",
            f"admin:u:devdel:{max_id}:{max_id}",
            f"admin:u:device:{max_id}:{max_id}",
            f"admin:u:payment:{max_id}:{max_id}",
            f"admin:users:create:recover:{max_id}",
            f"admin:u:provrun:{max_id}:strict",
            f"admin:bulk:runplan:{max_id}",
            f"admin:bulk:rungroup:{max_id}",
        )
        for callback in callbacks:
            with self.subTest(callback=callback):
                self.assertLessEqual(len(callback.encode("utf-8")), 64)

    def test_delete_confirmation_shows_identity_and_irreversibility(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        block = source.split("async def admin_del_ask", 1)[1].split(
            "async def admin_del", 1
        )[0]
        self.assertIn("🗑 Удалить пользователя", block)
        self.assertIn("Email: {rec.email}", block)
        self.assertIn("Telegram ID: {rec.telegram_id}", block)
        self.assertIn("Это действие необратимо.", block)

    def test_plan_expiry_traffic_ip_and_subscription_results_keep_context(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        self.assertIn("reply_markup=back_plan(tg_id)", source)
        self.assertIn("reply_markup=back_expiry(tg_id)", source)
        self.assertIn("reply_markup=back_traffic(tg_id)", source)
        self.assertIn("reply_markup=back_access_config(tg_id)", source)
        self.assertIn("reply_markup=back_subscription(tg_id)", source)


if __name__ == "__main__":
    unittest.main()
