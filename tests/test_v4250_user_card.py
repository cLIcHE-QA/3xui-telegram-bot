from __future__ import annotations

from pathlib import Path
import unittest

from admin_privileges import required_role_for_callback


ROOT = Path(__file__).resolve().parents[1]


class V4250UserCardNavigationTests(unittest.TestCase):
    def test_card_uses_canonical_sections(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        for label, callback in (
            ("💎 Тариф", "admin:u:planview:"),
            ("📅 Срок", "admin:u:expiryview:"),
            ("📊 Трафик", "admin:u:trafficview:"),
            ("🌐 Доступ", "admin:u:access:"),
            ("🔗 Подписка", "admin:u:subview:"),
            ("✏️ Профиль", "admin:u:profile:"),
            ("⚙️ Ещё действия", "admin:u:more:"),
        ):
            self.assertIn(f'text="{label}"', source)
            self.assertIn(f'callback_data=f"{callback}{{tg_id}}"', source)

    def test_new_sections_are_read_only_routes(self):
        for callback in (
            "admin:u:planview:101",
            "admin:u:expiryview:101",
            "admin:u:trafficview:101",
            "admin:u:access:101",
            "admin:u:accesscfg:101",
            "admin:u:subview:101",
            "admin:u:profile:101",
            "admin:u:more:101",
        ):
            with self.subTest(callback=callback):
                self.assertEqual(required_role_for_callback(callback), "read_only")

    def test_section_mutations_are_role_aware(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        self.assertIn("def _role_can_support", source)
        self.assertIn("def _role_can_admin", source)
        self.assertIn('if _role_can_support(role):', source)
        self.assertIn('if _role_can_admin(role):', source)
        self.assertIn('callback_data=f"admin:u:subrotateask:{tg_id}"', source)
        self.assertIn('callback_data=f"admindelask:{tg_id}"', source)

    def test_access_section_is_parent_for_access_views(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        self.assertIn(
            'InlineKeyboardButton(text="⬅ Доступ", callback_data=f"admin:u:access:{tg_id}")',
            source,
        )
        self.assertIn('callback_data=f"admin:u:prov:{tg_id}"', source)
        self.assertIn('callback_data=f"admin:u:inbounds:{tg_id}"', source)

    def test_legacy_user_route_renders_same_role_aware_card(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        legacy = source.split(
            '@advanced_users_router.callback_query(F.data.startswith("adminuser:"))',
            1,
        )[1].split(
            '@advanced_users_router.callback_query(F.data.startswith("adminsub:"))',
            1,
        )[0]
        self.assertIn("authorize_callback", legacy)
        self.assertIn("text, kb = await render_user(tg_id, role)", legacy)


if __name__ == "__main__":
    unittest.main()
