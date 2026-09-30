from __future__ import annotations

from pathlib import Path
import unittest

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import admin_navigation
from admin_ui import filter_keyboard_for_role


ROOT = Path(__file__).resolve().parents[1]


def callbacks(markup: InlineKeyboardMarkup) -> set[str]:
    return {
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    }


class PermissionAwareNavigationTests(unittest.TestCase):
    def test_filter_uses_callback_catalog_role_matrix(self):
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="View", callback_data="admin:jobs"),
                InlineKeyboardButton(text="Admin", callback_data="admin:jobs:backup"),
                InlineKeyboardButton(text="Owner", callback_data="admin:restore"),
            ],
            [InlineKeyboardButton(text="Unknown", callback_data="admin:not-declared")],
        ])

        self.assertEqual(
            callbacks(filter_keyboard_for_role(markup, "read_only")),
            {"admin:jobs"},
        )
        self.assertEqual(
            callbacks(filter_keyboard_for_role(markup, "support")),
            {"admin:jobs"},
        )
        self.assertEqual(
            callbacks(filter_keyboard_for_role(markup, "admin")),
            {"admin:jobs", "admin:jobs:backup"},
        )
        self.assertEqual(
            callbacks(filter_keyboard_for_role(markup, "owner")),
            {"admin:jobs", "admin:jobs:backup", "admin:restore"},
        )

    def test_unknown_admin_callback_is_hidden_fail_closed(self):
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Unknown", callback_data="admin:future-action"),
        ]])
        filtered = filter_keyboard_for_role(markup, "owner")
        self.assertEqual(filtered.inline_keyboard, [])

    def test_non_admin_callback_and_url_buttons_are_preserved(self):
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Client", callback_data="client:open"),
            InlineKeyboardButton(text="Docs", url="https://example.com"),
        ]])
        filtered = filter_keyboard_for_role(markup, "read_only")
        self.assertEqual(len(filtered.inline_keyboard), 1)
        self.assertEqual(len(filtered.inline_keyboard[0]), 2)

    def test_backup_menu_hides_admin_and_owner_actions(self):
        self.assertEqual(
            callbacks(admin_navigation.backup_menu("read_only")),
            {"admin:section:system"},
        )
        self.assertEqual(
            callbacks(admin_navigation.backup_menu("admin")),
            {
                "admin:backup:create",
                "admin:backup:botdb",
                "admin:backup:full",
                "admin:section:system",
            },
        )
        self.assertIn("admin:restore", callbacks(admin_navigation.backup_menu("owner")))

    def test_system_menu_hides_owner_only_entries(self):
        read_only = callbacks(admin_navigation.system_menu("read_only"))
        self.assertNotIn("admin:botupd", read_only)
        self.assertNotIn("admin:administrators", read_only)
        self.assertIn("admin:versions", read_only)
        self.assertIn("admin:jobs", read_only)
        self.assertIn("admin:backups", read_only)
        self.assertIn("admin:settings", read_only)

        owner = callbacks(admin_navigation.system_menu("owner"))
        self.assertIn("admin:botupd", owner)
        self.assertIn("admin:administrators", owner)

    def test_attention_links_are_context_aware(self):
        empty = callbacks(admin_navigation.attention_menu(set(), "read_only"))
        self.assertEqual(empty, {"admin:attention", "admin:dashboard"})

        problem = callbacks(admin_navigation.attention_menu(
            {"jobs", "operations"},
            "read_only",
        ))
        self.assertEqual(
            problem,
            {"admin:jobs", "admin:fleet", "admin:attention", "admin:dashboard"},
        )

    def test_existing_attention_menu_default_contract_stays_available(self):
        full = callbacks(admin_navigation.attention_menu())
        for callback in (
            "admin:health",
            "admin:jobs",
            "admin:alerts",
            "admin:backups",
            "admin:fleet",
            "admin:attention",
            "admin:dashboard",
        ):
            self.assertIn(callback, full)

    def test_affected_destination_screens_apply_role_filtering(self):
        jobs = (ROOT / "admin_observability.py").read_text(encoding="utf-8")
        alerts = (ROOT / "logs_alerts.py").read_text(encoding="utf-8")
        storage = (ROOT / "storage_admin.py").read_text(encoding="utf-8")
        fleet = (ROOT / "fleet_operations.py").read_text(encoding="utf-8")

        jobs_block = jobs.split(
            '@observability_router.callback_query(F.data == "admin:jobs")',
            1,
        )[1].split(
            '@observability_router.callback_query(F.data == "admin:jobs:backup")',
            1,
        )[0]
        self.assertIn("filter_keyboard_for_role(kb, role)", jobs_block)

        self.assertIn("filter_keyboard_for_role(_alerts_keyboard(rules), role)", alerts)
        self.assertIn("await _backup_menu_for_call(call)", storage)
        self.assertIn("filter_keyboard_for_role(markup, role)", fleet)
        self.assertIn("await _fleet_home_keyboard_for_call(call)", fleet)

    def test_attention_handler_passes_actual_problem_categories(self):
        shell = (ROOT / "admin_shell.py").read_text(encoding="utf-8")
        handler = shell.split(
            '@admin_shell_router.callback_query(F.data == "admin:attention")',
            1,
        )[1].split(
            '@admin_shell_router.callback_query(F.data == "admin:subscriptions")',
            1,
        )[0]
        self.assertIn("{item.category for item in items}", handler)
        self.assertIn("attention_menu(", handler)


if __name__ == "__main__":
    unittest.main()
