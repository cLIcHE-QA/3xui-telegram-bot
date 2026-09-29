"""Stabilization release contract for v4.25.1."""
from __future__ import annotations

from pathlib import Path
import unittest

from version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class V4251ReleaseTests(unittest.TestCase):
    def test_release_version_is_4251(self):
        self.assertEqual(APP_VERSION, "4.25.1")

    def test_current_docs_reference_release_4251(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        admin_setup = (ROOT / "docs" / "ADMIN_SETUP.md").read_text(encoding="utf-8")
        sqlite_doc = (ROOT / "docs" / "SQLITE_MIGRATIONS.md").read_text(encoding="utf-8")

        self.assertTrue(readme.startswith("# Telegram-бот для 3x-ui v4.25.1"))
        self.assertIn("Guide ориентирован на release v4.25.1.", admin_setup)
        self.assertIn("git checkout --detach v4.25.1", admin_setup)
        self.assertIn("Bot version: 4.25.1", admin_setup)
        self.assertIn(
            "Для `v4.24.0`, `v4.24.1`, `v4.25.0` и `v4.25.1` текущая bot schema version — **5**",
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

    def test_roadmap_marks_v4251_accepted_and_v4252_required_before_v426(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        self.assertIn(
            "✅ Опубликовано в `v4.25.1` и принято в production.",
            roadmap,
        )
        self.assertIn(
            "##### v4.25.2 — Subscription client compatibility",
            roadmap,
        )
        self.assertIn(
            "обязательный compatibility hotfix перед переходом к `v4.26.0`",
            roadmap,
        )
        self.assertIn(
            "Линия `v4.25` считается полностью production-closed только после публикации и targeted production acceptance `v4.25.2`.",
            roadmap,
        )

    def test_admin_setup_keeps_pinned_3xui_contract(self):
        admin_setup = (ROOT / "docs" / "ADMIN_SETUP.md").read_text(encoding="utf-8")
        self.assertIn(
            "Для bot release `v4.25.1` машинно проверяемый native API contract pinned к 3x-ui `v3.8.5`",
            admin_setup,
        )


if __name__ == "__main__":
    unittest.main()
