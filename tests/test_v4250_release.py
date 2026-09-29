"""Release contract for v4.25.6 Streisand forward-revert."""
from __future__ import annotations

from pathlib import Path
import unittest

from version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class V4251ReleaseTests(unittest.TestCase):
    def test_release_version_is_4251(self):
        self.assertEqual(APP_VERSION, "4.25.6")

    def test_current_docs_reference_release_4251(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        admin_setup = (ROOT / "docs" / "ADMIN_SETUP.md").read_text(encoding="utf-8")
        sqlite_doc = (ROOT / "docs" / "SQLITE_MIGRATIONS.md").read_text(encoding="utf-8")

        self.assertTrue(readme.startswith("# Telegram-бот для 3x-ui v4.25.6"))
        self.assertIn("Guide ориентирован на release v4.25.6.", admin_setup)
        self.assertIn("git checkout --detach v4.25.6", admin_setup)
        self.assertIn("Bot version: 4.25.6", admin_setup)
        self.assertIn(
            "Для `v4.24.0`, `v4.24.1`, `v4.25.0`, `v4.25.1`, `v4.25.2`, `v4.25.3`, `v4.25.4`, `v4.25.5` и `v4.25.6` текущая bot schema version — **5**",
            sqlite_doc,
        )

    def test_release_notes_cover_v4250_scope(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(changelog.count("## v4.25.0 — User Management"), 1)
        section = changelog.split("## v4.25.0 — User Management", 1)[1].split("\n## ", 1)[0]

        for needle in (
            "bounded pagination",
            "📱 Подключения",
            "💳 Платежи",
            "🧾 Активность",
            "➕ Создать пользователя",
            "no-retry mutation boundary",
            "локальным `🔳 QR-код`",
            "VLESS Flow",
            "Bulk User Management",
            "callback-size",
        ):
            self.assertIn(needle, section)

    def test_roadmap_records_streisand_hwid_incompatibility_and_revert(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        self.assertIn("##### v4.25.4 — Streisand plain subscription compatibility", roadmap)
        self.assertIn("##### v4.25.5 — Streisand plain mode precedence", roadmap)
        self.assertIn("##### v4.25.6 — Streisand incompatibility / forward revert", roadmap)
        self.assertIn("hwid_not_supported", roadmap)
        self.assertIn("не передаёт совместимый `X-HWID`", roadmap)
        self.assertIn("вернуть runtime subscription proxy и его regression contract к `v4.25.3`", roadmap)

    def test_admin_setup_keeps_pinned_3xui_contract(self):
        admin_setup = (ROOT / "docs" / "ADMIN_SETUP.md").read_text(encoding="utf-8")
        self.assertIn(
            "Для bot release `v4.25.6` машинно проверяемый native API contract pinned к 3x-ui `v3.8.5`",
            admin_setup,
        )


if __name__ == "__main__":
    unittest.main()
