"""v4.20.4 production-smoke regressions for Admin UI consolidation."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class V4204AdminUiTests(unittest.TestCase):
    def test_release_version_is_4204(self):
        self.assertEqual(APP_VERSION, "4.20.4")

    def test_users_list_uses_canonical_card_and_legacy_route_is_compatible(self):
        users = source("advanced_users.py")
        self.assertIn(
            'callback_data=f"admin:u:{u.telegram_id}"',
            users,
        )
        self.assertIn(
            '@advanced_users_router.callback_query(F.data.startswith("adminuser:"))',
            users,
        )
        legacy = users.split(
            '@advanced_users_router.callback_query(F.data.startswith("adminuser:"))',
            1,
        )[1].split(
            '@advanced_users_router.callback_query(F.data.startswith("adminsub:"))',
            1,
        )[0]
        self.assertIn("text, kb = await render_user(tg_id)", legacy)
        self.assertIn("await render_callback(call, text, reply_markup=kb)", legacy)
        self.assertNotIn("user_admin_keyboard", users)

    def test_audit_detail_is_read_only_and_preserves_full_details(self):
        observability = source("admin_observability.py")
        database = source("db.py")
        privileges = source("admin_privileges.py")

        self.assertIn("async def audit_detail(call: CallbackQuery)", observability)
        self.assertIn("item = await db.get_audit(audit_id)", observability)
        self.assertIn("Подробности:", observability)
        self.assertIn("async def get_audit(self, audit_id: int)", database)
        self.assertIn(r'r"^admin:audit:item:\d+:\d+$"', privileges)
        self.assertIn('"bot.update.started": "обновление бота: запущено"', observability)
        self.assertIn(
            '"bot.update.recovered": "обновление бота: итог восстановлен"',
            observability,
        )

    def test_operator_facing_admin_copy_hides_implementation_details(self):
        shell = source("admin_shell.py")
        catalog = source("catalog_admin.py")
        business = source("business_admin.py")
        users = source("advanced_users.py")
        system = source("system_admin.py")
        inbounds = source("inbound_admin.py")
        restore = source("disaster_recovery.py")

        for text in (shell, catalog, business):
            self.assertNotIn("/create", text)

        for text in (catalog, business, users, system, inbounds, restore):
            self.assertNotIn(".env", text)

        self.assertIn("По умолчанию для новых пользователей", shell)
        self.assertIn("тариф по умолчанию для новых пользователей", catalog)
        self.assertIn(
            "Пока промокоды не применяются автоматически при создании доступа.",
            business,
        )
        self.assertIn("локальной конфигурации", business)
        self.assertIn("текущей административной политикой", inbounds)
        self.assertIn("административной политики", users)

    def test_roles_screen_uses_human_labels_not_permission_ids(self):
        business = source("business_admin.py")
        privileges = source("admin_privileges.py")

        role_view = business.split(
            '@business_router.callback_query(F.data == "admin:privileges")',
            1,
        )[1].split(
            '@business_router.callback_query(F.data.regexp(r"^admin:administrator:\\d+$"))',
            1,
        )[0]
        self.assertIn('lines.append(f"• {item.label}")', role_view)
        self.assertNotIn("item.permission_id", role_view)

        self.assertIn('"users.support"', privileges)
        self.assertIn('"host_control.destructive"', privileges)
        self.assertIn('"bot_updates.manage"', privileges)

    def test_direct_node_operator_ui_uses_shared_formatter(self):
        modules = (
            "advanced_nodes.py",
            "logs_alerts.py",
            "disaster_recovery.py",
            "fleet_operations.py",
            "system_admin.py",
            "inbound_admin.py",
            "storage_admin.py",
            "versions_updates.py",
            "host_control_ui.py",
        )
        for path in modules:
            self.assertIn(
                "node_display_name",
                source(path),
                msg=f"{path} must use the shared direct-node display formatter",
            )

        residuals = {
            "advanced_nodes.py": 'f"📡 Inbound\'ы · {node.name}"',
            "logs_alerts.py": 'text=f"{icon} {node.name}"',
            "disaster_recovery.py": 'text=f"🌍 Восстановить ноду: {node.name}"',
            "fleet_operations.py": 'return f"{icon} {node.name} · ID {node.id}"',
            "system_admin.py": 'f"{icon} {node.name} · {xicon} Xray · "',
            "inbound_admin.py": 'text=f"🌍 {node.name}"',
            "versions_updates.py": 'f"🌍 {node.name}: 📦 3x-ui',
            "host_control_ui.py": 'f"🧩 Управление 3x-ui · {target.name}"',
        }
        for path, stale in residuals.items():
            self.assertNotIn(stale, source(path), msg=f"stale node label in {path}")

    def test_versions_overview_is_symmetric_and_state_lives_on_detail(self):
        versions = source("versions_updates.py")
        home = versions.split(
            '@versions_router.callback_query(F.data == "admin:versions")',
            1,
        )[1].split(
            '@versions_router.callback_query(F.data.regexp(rf"^admin:ver:target:({KEY})$"))',
            1,
        )[0]
        detail = versions.split(
            '@versions_router.callback_query(F.data.regexp(rf"^admin:ver:target:({KEY})$"))',
            1,
        )[1]

        self.assertIn("_server_label", home)
        self.assertIn("📦 3x-ui", home)
        self.assertIn("⚡ Xray", home)
        self.assertNotIn("xray_state_text(master.xray_state)", home)
        self.assertIn("xray_state_text(snapshot.xray_state)", detail)

    def test_direct_node_display_contract_is_documented(self):
        ui_style = source("docs/UI_STYLE.md")
        roadmap = source("docs/ROADMAP.md")

        self.assertIn("## Отображение Master и direct nodes", ui_style)
        self.assertIn("`node_display_name()`", ui_style)
        self.assertIn("стабильная техническая идентичность direct node — `node_id`", ui_style)
        self.assertIn('`if node.name == "Finland"`', ui_style)

        self.assertIn("#### Географические metadata direct nodes", roadmap)
        self.assertIn("`country_code`", roadmap)
        self.assertIn("ISO 3166-1 alpha-2", roadmap)
        self.assertIn(
            "Не является блокером `v4.20.4` или обязательным условием перехода к `v5.0.0`",
            roadmap,
        )

    def test_runtime_has_no_finland_specific_business_logic(self):
        offenders: list[str] = []
        for path in ROOT.glob("*.py"):
            if path.name == "node_ui.py":
                continue
            text = path.read_text(encoding="utf-8")
            if re.search(r"(?i)finland", text):
                offenders.append(path.name)
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
