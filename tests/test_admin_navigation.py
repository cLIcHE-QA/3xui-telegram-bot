from __future__ import annotations

import unittest

import admin_navigation


def callback_values(markup) -> set[str]:
    return {
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    }


def labels_by_callback(markup) -> dict[str, str]:
    return {
        button.callback_data: button.text
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    }


class AdminNavigationTests(unittest.TestCase):
    def test_top_level_admin_callbacks_are_stable(self):
        self.assertEqual(
            callback_values(admin_navigation.admin_menu()),
            {
                "admin:dashboard",
                "admin:users",
                "admin:subscriptions",
                "admin:payments",
                "admin:plans",
                "admin:promo",
                "admin:section:infrastructure",
                "admin:section:monitoring",
                "admin:section:system",
            },
        )

    def test_core_navigation_labels_use_russian_vocabulary(self):
        top = labels_by_callback(admin_navigation.admin_menu())
        self.assertEqual(top["admin:dashboard"], "📊 Обзор")
        self.assertEqual(top["admin:users"], "👥 Пользователи")
        self.assertEqual(top["admin:subscriptions"], "🔗 Подписки")
        self.assertEqual(top["admin:payments"], "💳 Платежи")
        self.assertEqual(top["admin:plans"], "💎 Тарифы")
        self.assertEqual(top["admin:promo"], "🎟 Промокоды")
        self.assertEqual(top["admin:section:infrastructure"], "🌐 Инфраструктура")
        self.assertEqual(top["admin:section:monitoring"], "📈 Мониторинг")
        self.assertEqual(top["admin:section:system"], "⚙️ Система")

        system = labels_by_callback(admin_navigation.system_menu())
        self.assertEqual(system["admin:botupd"], "🤖 Обновления бота")
        self.assertEqual(system["admin:versions"], "🧩 Версии и обновления")
        self.assertEqual(system["admin:jobs"], "⚙️ Задания")
        self.assertEqual(system["admin:backups"], "💾 Резервные копии")
        self.assertEqual(system["admin:audit"], "🧾 Журнал аудита")
        self.assertEqual(system["admin:administrators"], "👮 Администраторы")
        self.assertEqual(system["admin:settings"], "🔧 Настройки")

    def test_section_navigation_callbacks_are_stable(self):
        self.assertIn("admin:versions", callback_values(admin_navigation.infrastructure_menu()))
        self.assertIn("admin:nodes", callback_values(admin_navigation.infrastructure_menu()))
        self.assertIn("admin:health", callback_values(admin_navigation.monitoring_menu()))
        self.assertIn("admin:botupd", callback_values(admin_navigation.system_menu()))
        self.assertIn("admin:backups", callback_values(admin_navigation.system_menu()))

    def test_user_action_callbacks_are_stable(self):
        enabled = callback_values(admin_navigation.user_admin_keyboard(123, enabled=True))
        disabled = callback_values(admin_navigation.user_admin_keyboard(123, enabled=False))
        self.assertIn("admindisable:123", enabled)
        self.assertIn("adminenable:123", disabled)
        self.assertIn("adminsync:123", enabled)
        self.assertIn("admindelask:123", enabled)


if __name__ == "__main__":
    unittest.main()
