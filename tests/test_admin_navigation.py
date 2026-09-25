from __future__ import annotations

import ast
import unittest
from pathlib import Path

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
        infrastructure = callback_values(admin_navigation.infrastructure_menu())
        system = callback_values(admin_navigation.system_menu())
        self.assertNotIn("admin:versions", infrastructure)
        self.assertIn("admin:nodes", infrastructure)
        self.assertIn("admin:health", callback_values(admin_navigation.monitoring_menu()))
        self.assertIn("admin:versions", system)
        self.assertIn("admin:botupd", system)
        self.assertIn("admin:backups", system)

    def test_root_back_labels_match_admin_home(self):
        for menu in (
            admin_navigation.infrastructure_menu(),
            admin_navigation.monitoring_menu(),
            admin_navigation.system_menu(),
        ):
            labels = labels_by_callback(menu)
            self.assertEqual(labels["admin:home"], "⬅ Панель администратора")

    def test_global_sync_cancel_returns_to_users(self):
        labels = labels_by_callback(admin_navigation.confirm_sync_all_keyboard())
        self.assertEqual(labels["admin:syncall:run"], "✅ Синхронизировать всех")
        self.assertEqual(labels["admin:users"], "✖ Отмена")

    def test_operator_renderers_keep_explicit_navigation(self):
        root = Path(__file__).resolve().parents[1]
        files = (
            "admin_shell.py",
            "advanced_users.py",
            "catalog_admin.py",
            "business_admin.py",
            "node_admin.py",
            "advanced_nodes.py",
            "inbound_admin.py",
            "admin_observability.py",
            "logs_alerts.py",
            "storage_admin.py",
            "system_admin.py",
        )
        missing = []
        for name in files:
            tree = ast.parse((root / name).read_text(encoding="utf-8"), filename=name)
            functions = (
                node for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
            for function in functions:
                # Authorization guards clear FSM state before rendering denial.
                # They are terminal by design and are the only allowed exception.
                if function.name == "guard_message":
                    continue
                for node in ast.walk(function):
                    if not isinstance(node, ast.Call):
                        continue
                    func = node.func
                    func_name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
                    if func_name not in {"render_callback", "render_input"}:
                        continue
                    if not any(keyword.arg == "reply_markup" for keyword in node.keywords):
                        missing.append(f"{name}:{node.lineno}:{func_name}")
        self.assertEqual(missing, [])

    def test_user_action_callbacks_are_stable(self):
        enabled = callback_values(admin_navigation.user_admin_keyboard(123, enabled=True))
        disabled = callback_values(admin_navigation.user_admin_keyboard(123, enabled=False))
        self.assertIn("admindisable:123", enabled)
        self.assertIn("adminenable:123", disabled)
        self.assertIn("adminsync:123", enabled)
        self.assertIn("admindelask:123", enabled)


if __name__ == "__main__":
    unittest.main()
