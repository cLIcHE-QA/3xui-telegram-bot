from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PUBLIC_SURFACES = (
    ".env.example",
    "README.md",
    "config.py",
    "node_admin.py",
    "advanced_users.py",
    "catalog_admin.py",
    "business_admin.py",
    "scripts/setup-host-control-endpoint.sh",
    "docs/ADMIN_SETUP.md",
    "docs/HOST_CONTROL_AGENT.md",
    "docs/HOST_CONTROL_DEPLOY.md",
    "docs/HOST_CONTROL_ROLLOUT.md",
    "docs/NODE_ONBOARDING.md",
    "docs/OFFSITE_BACKUP.md",
    "docs/VERSIONS_UPDATES.md",
    "docs/GIT_WORKFLOW.md",
)

DEPLOYMENT_SPECIFIC_MARKERS = (
    "Finland",
    "HOST_CONTROL_FI_",
    "NODE_BACKUP_FI_",
    "NODE_ONBOARD_NAME=Finland",
    "NODE_ADMIN_NODE_NAME=Finland",
    "3xui-node-fi.env",
    "3xui-node-admin-fi.env",
    "3xui-host-control-fi.env",
    "panel-fi.example.com",
    "host-control-fi.example.com",
    "HOST_CONTROL_TARGETS=MASTER,FI",
    "MASTER_FLAG=🇳🇱",
)

STALE_UI_PATHS = (
    "→ Infrastructure",
    "→ Nodes",
    "→ Readiness",
    "→ System",
    "→ Backups",
    "`Infrastructure → Nodes",
    "`System → Jobs",
    "`/admin → Backups",
    "`⬅ System`",
)


class PublicReadinessTests(unittest.TestCase):
    def _source(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_current_public_surfaces_do_not_use_private_deployment_examples(self):
        failures = []
        for path in PUBLIC_SURFACES:
            source = self._source(path)
            for marker in DEPLOYMENT_SPECIFIC_MARKERS:
                if marker in source:
                    failures.append(f"{path}: {marker}")
        self.assertEqual(failures, [])

    def test_current_runbooks_use_current_russian_admin_paths(self):
        failures = []
        for path in PUBLIC_SURFACES:
            source = self._source(path)
            for marker in STALE_UI_PATHS:
                if marker in source:
                    failures.append(f"{path}: {marker}")
        self.assertEqual(failures, [])

    def test_neutral_examples_are_part_of_the_public_contract(self):
        env = self._source(".env.example")
        self.assertIn("MASTER_FLAG=🖥", env)
        self.assertIn("# HOST_CONTROL_TARGETS=MASTER,NODE1", env)
        self.assertIn("# HOST_CONTROL_NODE1_NAME=Edge-1", env)
        self.assertIn("# NODE_BACKUP_TARGETS=NODE1", env)
        self.assertIn("# NODE_BACKUP_NODE1_NODE_NAME=Edge-1", env)

        node_admin = self._source("node_admin.py")
        self.assertIn('"Например: Edge-1"', node_admin)

        catalog = self._source("catalog_admin.py")
        self.assertIn("Название, например Основная или Резервная", catalog)
        self.assertIn("Название, например Публичная подписка или VPN-шлюз", catalog)

    def test_destructive_confirmations_state_their_scope(self):
        users = self._source("advanced_users.py")
        self.assertIn(
            "Клиент и его профиль будут удалены; платёжная история сохранится.",
            users,
        )

        business = self._source("business_admin.py")
        self.assertIn(
            "Административный доступ через эту запись будет удалён; "
            "пользовательские данные и 3x-ui не изменятся.",
            business,
        )

    def test_readme_describes_current_admin_hierarchy(self):
        readme = self._source("README.md")
        self.assertIn(
            "Обзор / Пользователи / Подписки / Платежи / Тарифы / Промокоды / "
            "Инфраструктура / Мониторинг / Система",
            readme,
        )
        self.assertIn(
            "Инфраструктура: Ноды / Inbound'ы / Хосты / Операции с нодами / Группы серверов",
            readme,
        )
        self.assertIn(
            "Система: Обновления бота / Версии и обновления / Задания / Резервные копии / "
            "Журнал аудита / Администраторы / Настройки",
            readme,
        )


if __name__ == "__main__":
    unittest.main()
