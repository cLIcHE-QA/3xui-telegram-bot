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
