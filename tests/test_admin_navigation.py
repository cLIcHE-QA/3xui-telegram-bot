from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

import admin_navigation
from admin_privileges import required_role_for_callback


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
        self.assertIn("admin:cheburcheck", callback_values(admin_navigation.monitoring_menu()))
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
            "cheburcheck_admin.py",
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

    def test_repo_wide_static_admin_navigation_contract(self):
        root = Path(__file__).resolve().parents[1]
        canonical_back_labels = {
            "admin:home": "⬅ Панель администратора",
            "admin:section:infrastructure": "⬅ Инфраструктура",
            "admin:section:monitoring": "⬅ Мониторинг",
            "admin:section:system": "⬅ Система",
            "admin:users": "⬅ Пользователи",
            "admin:subscriptions": "⬅ Подписки",
            "admin:usergroups": "⬅ Группы пользователей",
            "admin:nodes": "⬅ Ноды",
            "admin:infra:inbounds": "⬅ Inbounds",
            "admin:inboundtemplates": "⬅ Шаблоны",
            "admin:plans": "⬅ Тарифы",
            "admin:servergroups": "⬅ Группы серверов",
            "admin:hosts": "⬅ Хосты",
            "admin:fleet": "⬅ Операции с нодами",
            "admin:versions": "⬅ Версии и обновления",
            "admin:botupd": "⬅ Обновления бота",
            "admin:jobs": "⬅ Задания",
            "admin:backups": "⬅ Резервные копии",
            "admin:restore": "⬅ Аварийное восстановление",
            "admin:logs": "⬅ Журналы",
            "admin:logs:nodes": "⬅ Журналы нод",
            "admin:alerts": "⬅ Оповещения",
            "admin:payments": "⬅ Платежи",
            "admin:promo": "⬅ Промокоды",
            "admin:administrators": "⬅ Администраторы",
        }

        static_buttons: list[tuple[str, str, str]] = []
        for path in sorted(root.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                func_name = (
                    func.id if isinstance(func, ast.Name)
                    else func.attr if isinstance(func, ast.Attribute)
                    else ""
                )
                if func_name != "InlineKeyboardButton":
                    continue
                values = {}
                for keyword in node.keywords:
                    if (
                        keyword.arg in {"text", "callback_data"}
                        and isinstance(keyword.value, ast.Constant)
                        and isinstance(keyword.value.value, str)
                    ):
                        values[keyword.arg] = keyword.value.value
                text = values.get("text")
                callback = values.get("callback_data")
                if text and callback and callback.startswith("admin:"):
                    static_buttons.append((path.name, text, callback))

        missing_privilege = [
            f"{path}:{callback}"
            for path, _text, callback in static_buttons
            if required_role_for_callback(callback) is None
        ]
        self.assertEqual(missing_privilege, [])

        exact_routes: set[str] = set()
        prefix_routes: set[str] = set()
        regex_routes: list[re.Pattern[str]] = []
        membership_routes: set[str] = set()
        route_errors: list[str] = []

        def static_string(node: ast.AST, constants: dict[str, str]) -> str | None:
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                return node.value
            if not isinstance(node, ast.JoinedStr):
                return None
            parts: list[str] = []
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    parts.append(value.value)
                    continue
                if (
                    isinstance(value, ast.FormattedValue)
                    and isinstance(value.value, ast.Name)
                    and value.value.id in constants
                ):
                    parts.append(constants[value.value.id])
                    continue
                return None
            return "".join(parts)

        for path in sorted(root.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=path.name)
            constants: dict[str, str] = {}
            for statement in tree.body:
                if (
                    isinstance(statement, (ast.Assign, ast.AnnAssign))
                    and isinstance(statement.value, ast.Constant)
                    and isinstance(statement.value.value, str)
                ):
                    targets = (
                        statement.targets
                        if isinstance(statement, ast.Assign)
                        else [statement.target]
                    )
                    for target in targets:
                        if isinstance(target, ast.Name):
                            constants[target.id] = statement.value.value

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func

                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "startswith"
                    and isinstance(func.value, ast.Attribute)
                    and func.value.attr == "data"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    prefix_routes.add(node.args[0].value)
                    continue

                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "regexp"
                    and isinstance(func.value, ast.Attribute)
                    and func.value.attr == "data"
                    and node.args
                ):
                    pattern = static_string(node.args[0], constants)
                    if pattern is not None:
                        try:
                            regex_routes.append(re.compile(pattern))
                        except re.error as exc:
                            route_errors.append(f"{path.name}:{node.lineno}:{exc}")
                    continue

                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "in_"
                    and isinstance(func.value, ast.Attribute)
                    and func.value.attr == "data"
                    and node.args
                    and isinstance(node.args[0], (ast.Set, ast.Tuple, ast.List))
                ):
                    for item in node.args[0].elts:
                        if isinstance(item, ast.Constant) and isinstance(item.value, str):
                            membership_routes.add(item.value)

                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "callback_query"
                ):
                    for arg in node.args:
                        if not isinstance(arg, ast.Compare) or len(arg.ops) != 1:
                            continue
                        if not isinstance(arg.ops[0], ast.Eq) or len(arg.comparators) != 1:
                            continue
                        left = arg.left
                        right = arg.comparators[0]
                        if (
                            isinstance(left, ast.Attribute)
                            and left.attr == "data"
                            and isinstance(right, ast.Constant)
                            and isinstance(right.value, str)
                        ):
                            exact_routes.add(right.value)

        self.assertEqual(route_errors, [])

        def has_route(callback: str) -> bool:
            return (
                callback in exact_routes
                or callback in membership_routes
                or any(callback.startswith(prefix) for prefix in prefix_routes)
                or any(pattern.fullmatch(callback) for pattern in regex_routes)
            )

        dead_static_buttons = [
            f"{path}:{text}->{callback}"
            for path, text, callback in static_buttons
            if not has_route(callback)
        ]
        self.assertEqual(dead_static_buttons, [])

        wrong_back_labels = [
            f"{path}:{text}->{callback}"
            for path, text, callback in static_buttons
            if text.startswith("⬅ ")
            and callback in canonical_back_labels
            and text != canonical_back_labels[callback]
        ]
        self.assertEqual(wrong_back_labels, [])

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
