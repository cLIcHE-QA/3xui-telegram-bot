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
        dashboard = callback_values(admin_navigation.dashboard_menu())
        infrastructure = callback_values(admin_navigation.infrastructure_menu())
        system = callback_values(admin_navigation.system_menu())
        self.assertEqual(dashboard, {"admin:dashboard", "admin:home"})
        self.assertNotIn("admin:versions", infrastructure)
        self.assertIn("admin:nodes", infrastructure)
        self.assertIn("admin:health", callback_values(admin_navigation.monitoring_menu()))
        self.assertIn("admin:versions", system)
        self.assertIn("admin:botupd", system)
        self.assertIn("admin:backups", system)

    def test_root_back_labels_match_admin_home(self):
        for menu in (
            admin_navigation.dashboard_menu(),
            admin_navigation.infrastructure_menu(),
            admin_navigation.monitoring_menu(),
            admin_navigation.system_menu(),
        ):
            labels = labels_by_callback(menu)
            self.assertEqual(labels["admin:home"], "⬅ Панель администратора")

        dashboard = labels_by_callback(admin_navigation.dashboard_menu())
        self.assertEqual(dashboard["admin:dashboard"], "🔄 Обновить")

    def test_global_sync_cancel_returns_to_users(self):
        labels = labels_by_callback(admin_navigation.confirm_sync_all_keyboard())
        self.assertEqual(labels["admin:syncall:run"], "✅ Синхронизировать всех")
        self.assertEqual(labels["admin:users"], "✖ Отмена")

    def test_operator_renderers_keep_explicit_navigation(self):
        root = Path(__file__).resolve().parents[1]
        files = (
            "admin_shell.py",
            "advanced_users.py",
            "user_groups_admin.py",
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

    def test_parent_flows_for_nested_operational_screens(self):
        root = Path(__file__).resolve().parents[1]

        bot_updates = (root / "bot_updates.py").read_text(encoding="utf-8")
        self.assertIn('def _bot_updates_back(*, refresh: bool = False)', bot_updates)
        self.assertIn('("⬅ Обновления бота", "admin:botupd")', bot_updates)
        self.assertIn('def _system_back()', bot_updates)
        self.assertIn('@bot_updates_router.callback_query(F.data == "admin:botupd:history")', bot_updates)
        history = bot_updates.split(
            '@bot_updates_router.callback_query(F.data == "admin:botupd:history")',
            1,
        )[1]
        self.assertIn('reply_markup=_bot_updates_back()', history)

        logs = (root / "logs_alerts.py").read_text(encoding="utf-8")
        self.assertIn(
            'callback_data=f"admin:logs:node:{node_id}" if node_id is not None else "admin:logs"',
            logs,
        )

        host_control = (root / "host_control_ui.py").read_text(encoding="utf-8")
        self.assertIn('def _parent_back_from_key(key: str)', host_control)
        self.assertIn('def _control_cancel(key: str)', host_control)
        self.assertIn('reply_markup=_control_cancel(key)', host_control)
        self.assertIn('reply_markup=_parent_back_from_key(key)', host_control)

        restore = (root / "disaster_recovery.py").read_text(encoding="utf-8")
        self.assertIn('def _restore_cancel(backup_id: str)', restore)
        self.assertIn('reply_markup=_restore_cancel(bid)', restore)

        versions = (root / "versions_updates.py").read_text(encoding="utf-8")
        self.assertIn(
            '@versions_router.callback_query(F.data.regexp(r"^admin:ver:op:[0-9a-f]{16}$"))',
            versions,
        )
        self.assertIn('f"admin:ver:op:{op.nonce}"', versions)
        self.assertIn('f"admin:ver:op:{nonce}"', versions)

    def test_production_smoke_parent_and_ui_contracts(self):
        root = Path(__file__).resolve().parents[1]

        restore = (root / "disaster_recovery.py").read_text(encoding="utf-8")
        self.assertIn(
            'InlineKeyboardButton(text="⬅ Аварийное восстановление", callback_data="admin:restore")',
            restore,
        )
        self.assertNotIn('def _backup_back()', restore)

        shell = (root / "admin_shell.py").read_text(encoding="utf-8")
        self.assertIn('callback_data=f"adminsublist:{u.telegram_id}"', shell)
        self.assertNotIn("Этот раздел уже доступен в v3.9.", shell)

        users = (root / "advanced_users.py").read_text(encoding="utf-8")
        self.assertIn('F.data.startswith("adminsublist:")', users)
        self.assertIn(
            'InlineKeyboardButton(text="⬅ Подписки", callback_data="admin:subscriptions")',
            users,
        )

        catalog = (root / "catalog_admin.py").read_text(encoding="utf-8")
        self.assertIn("from node_ui import node_display_name", catalog)
        self.assertIn("node_display_name(node.name)", catalog)
        self.assertNotIn("согласовании доступа v4.5", catalog)
        self.assertNotIn("v3.9 не меняет DNS", catalog)

        inbound = (root / "inbound_admin.py").read_text(encoding="utf-8")
        self.assertIn("🔄 Синхронизировать клиентов", inbound)
        self.assertNotIn("🔄 Синхронизировать пользователей", inbound)

        business = (root / "business_admin.py").read_text(encoding="utf-8")
        self.assertIn('f"🖥 Master-сервер: {settings.master_name}', business)
        self.assertNotIn('f"🖥 Master: {settings.master_flag} {settings.master_name}', business)

        health = (root / "system_admin.py").read_text(encoding="utf-8")
        self.assertIn(
            'InlineKeyboardButton(text="⬅ Мониторинг", callback_data="admin:section:monitoring")',
            health,
        )
        self.assertIn(
            'InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:health")',
            health,
        )
        self.assertNotIn("reply_markup=monitoring_menu()", health)

    def test_legacy_user_action_handlers_remain_compatible(self):
        root = Path(__file__).resolve().parents[1]
        users = (root / "advanced_users.py").read_text(encoding="utf-8")
        for prefix in (
            "adminuser:",
            "adminsync:",
            "adminextend:",
            "admindisable:",
            "adminenable:",
            "admindelask:",
        ):
            self.assertIn(f'F.data.startswith("{prefix}")', users)
        self.assertNotIn("def user_admin_keyboard(", (root / "admin_navigation.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
