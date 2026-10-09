"""Regression coverage for #354: explicit context, role labels and safe navigation."""
from __future__ import annotations

import unittest
from pathlib import Path

from admin_navigation import (
    admin_root_heading, attention_menu, backup_menu, dashboard_menu,
    monitoring_menu, system_menu,
)
from admin_privileges import required_role_for_callback
from admin_ui import filter_keyboard_for_role
from fleet_operations import _fleet_home_keyboard
from logs_alerts import _alerts_keyboard

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = {
    "infrastructure": ("admin:attention:health", "admin:health"),
    "jobs": ("admin:attention:jobs", "admin:jobs"),
    "alerts": ("admin:attention:alerts", "admin:alerts"),
    "backups": ("admin:attention:backups", "admin:backups"),
    "operations": ("admin:attention:fleet", "admin:fleet"),
}
ROLES = {
    "owner": "👑 Owner",
    "admin": "🛡 Administrator",
    "support": "🧑‍💻 Support",
    "read_only": "👁 Read-only",
}


def labels(markup):
    return {
        button.callback_data: button.text
        for row in markup.inline_keyboard for button in row if button.callback_data
    }


class ContextNavigationTests(unittest.TestCase):
    def test_root_heading_for_all_roles_and_unknown_role_fails_closed(self):
        for role, label in ROLES.items():
            with self.subTest(role=role):
                self.assertEqual(admin_root_heading(role), f"⚙️ Панель администратора · {label}")
                home = (ROOT / "admin_shell.py").read_text(encoding="utf-8")
                self.assertIn("await message.answer(admin_root_heading(role)", home)
                self.assertIn("await render_callback(call, admin_root_heading(role)", home)
        with self.assertRaises(ValueError):
            admin_root_heading("superuser")

    def test_attention_active_entries_use_specific_read_only_routes(self):
        for role in ROLES:
            with self.subTest(role=role):
                displayed = labels(attention_menu(set(CONTEXT), role))
                for domain, (callback, original) in CONTEXT.items():
                    self.assertIn(callback, displayed)
                    self.assertNotIn(original, displayed)
                    self.assertEqual(required_role_for_callback(callback), "read_only")
                self.assertEqual(displayed["admin:attention"], "🔄 Обновить")
                self.assertEqual(displayed["admin:dashboard"], "⬅ Обзор")

    def test_calm_attention_preserves_only_refresh_and_back(self):
        for role in ROLES:
            self.assertEqual(set(labels(attention_menu(set(), role))),
                             {"admin:attention", "admin:dashboard"})

    def test_context_back_and_refresh_for_all_five_domains(self):
        for role in ROLES:
            with self.subTest(role=role):
                backup = labels(backup_menu(role, from_attention=True))
                self.assertEqual(backup["admin:attention:backups"], "🔄 Обновить")
                self.assertEqual(backup["admin:attention"], "⬅ Требует внимания")
                self.assertNotIn("admin:section:system", backup)
                self.assertEqual(labels(backup_menu(role))["admin:section:system"], "⬅ Система")

                fleet = labels(_fleet_home_keyboard(role, from_attention=True))
                self.assertEqual(fleet["admin:attention:fleet"], "🔄 Обновить")
                self.assertEqual(fleet["admin:attention"], "⬅ Требует внимания")
                self.assertNotIn("admin:section:infrastructure", fleet)
                self.assertIn("admin:section:infrastructure", labels(_fleet_home_keyboard(role)))

                alert_rules = []
                alert = labels(filter_keyboard_for_role(
                    _alerts_keyboard(alert_rules, from_attention=True), role
                ))
                self.assertEqual(alert["admin:attention:alerts"], "🔄 Обновить")
                self.assertEqual(alert["admin:attention"], "⬅ Требует внимания")
                self.assertNotIn("admin:section:monitoring", alert)
                self.assertEqual(
                    labels(filter_keyboard_for_role(_alerts_keyboard(alert_rules), role))
                    ["admin:section:monitoring"], "⬅ Мониторинг"
                )
                self.assertEqual(required_role_for_callback("admin:attention:jobs"), "read_only")
                self.assertEqual(required_role_for_callback("admin:attention:health"), "read_only")

    def test_read_only_does_not_gain_mutation_permissions(self):
        for role in ("read_only", "support"):
            with self.subTest(role=role):
                self.assertNotIn("admin:backup:create", labels(backup_menu(role, from_attention=True)))
                self.assertNotIn("admin:fleet:rollout", labels(_fleet_home_keyboard(role, from_attention=True)))
        for callback in ("admin:jobs:backup", "admin:alerts:toggle:job_failed", "admin:backup:create"):
            self.assertEqual(required_role_for_callback(callback), "admin")
        for value in ("admin:attention:jobs:run", "admin:attention:alerts:toggle:job_failed",
                      "admin:attention:backups:create", "admin:attention:unknown"):
            self.assertIsNone(required_role_for_callback(value))

    def test_back_and_refresh_routes_are_durable_not_session_dependent(self):
        sources = {
            "admin_observability.py": [
                'F.data == "admin:attention:jobs"',
                'refresh = "admin:attention:jobs" if from_attention',
                'parent = "admin:attention" if from_attention',
            ],
            "logs_alerts.py": [
                'F.data == "admin:attention:alerts"',
                'refresh = "admin:attention:alerts" if from_attention',
            ],
            "storage_admin.py": ['F.data == "admin:attention:backups"'],
            "system_admin.py": [
                'F.data == "admin:attention:health"',
                'refresh = "admin:attention:health" if from_attention',
            ],
            "fleet_operations.py": ['F.data == "admin:attention:fleet"'],
        }
        for path, needles in sources.items():
            source = (ROOT / path).read_text(encoding="utf-8")
            for needle in needles:
                with self.subTest(path=path, needle=needle):
                    self.assertIn(needle, source)
        # There is no stateful breadcrumb setter, and old callback identities keep working.
        self.assertEqual(labels(system_menu())["admin:jobs"], "⚙️ Задания")
        self.assertIn("admin:alerts", labels(monitoring_menu()))
        self.assertIn("admin:attention", labels(dashboard_menu()))
        self.assertIsNone(required_role_for_callback("admin:attention:jobs:stale"))


if __name__ == "__main__":
    unittest.main()
