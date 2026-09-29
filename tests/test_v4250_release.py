"""Release contract for v4.25.7 Inbound input validation."""
from __future__ import annotations

from pathlib import Path
import unittest

from version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class V4257ReleaseTests(unittest.TestCase):
    def test_release_version_is_4257(self):
        self.assertEqual(APP_VERSION, "4.25.7")

    def test_current_docs_reference_release_4257(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        admin_setup = (ROOT / "docs" / "ADMIN_SETUP.md").read_text(encoding="utf-8")
        sqlite_doc = (ROOT / "docs" / "SQLITE_MIGRATIONS.md").read_text(encoding="utf-8")

        self.assertTrue(readme.startswith("# Telegram-бот для 3x-ui v4.25.7"))
        self.assertIn("Guide ориентирован на release v4.25.7.", admin_setup)
        self.assertIn("git checkout --detach v4.25.7", admin_setup)
        self.assertIn("Bot version: 4.25.7", admin_setup)
        self.assertIn(
            "Для `v4.24.0`, `v4.24.1`, `v4.25.0`, `v4.25.1`, `v4.25.2`, `v4.25.3`, `v4.25.4`, `v4.25.5`, `v4.25.6` и `v4.25.7` текущая bot schema version — **5**",
            sqlite_doc,
        )

    def test_release_notes_cover_v4257_scope(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(changelog.count("## v4.25.7 — Inbound input validation"), 1)
        section = changelog.split("## v4.25.7 — Inbound input validation", 1)[1].split("\n## ", 1)[0]
        for needle in (
            "UnboundLocalError",
            "FSM",
            "occupied port",
            "disabled/clientless",
            "SQLite schema v5",
            "OpenAPI contract v3.8.5",
        ):
            self.assertIn(needle, section)

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

    def test_roadmap_closes_previous_v425_releases_after_v4256_acceptance(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        self.assertIn("##### v4.25.4 — Streisand plain subscription compatibility", roadmap)
        self.assertIn("##### v4.25.5 — Streisand plain mode precedence", roadmap)
        self.assertIn("##### v4.25.6 — Streisand incompatibility / forward revert", roadmap)
        self.assertIn("test 50 — version/health: **PASS**", roadmap)
        self.assertIn("test 55 — Streisand: **EXPECTED LIMITATION**", roadmap)
        self.assertIn("test 56 — final bot/DB/3x-ui health: **PASS**", roadmap)
        self.assertIn("hwid_not_supported", roadmap)
        self.assertIn("не передаёт совместимый `X-HWID`", roadmap)
        self.assertIn("релизы `v4.25.0–v4.25.7` полностью проверены и закрыты", roadmap)
        self.assertIn("Следующий активный патч — `v4.25.8`", roadmap)
        self.assertIn("следующий feature release — `v4.26.0` Node Drain.", roadmap)

    def test_previous_v425_sections_are_closed_without_claiming_streisand_support(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        for patch_version in range(7):
            heading = f"##### v4.25.{patch_version} — "
            with self.subTest(release=heading):
                self.assertEqual(roadmap.count(heading), 1)
                section = roadmap.split(heading, 1)[1].split("\n##### ", 1)[0]
                self.assertIn("**Статус: ✅", section)
                if patch_version in (4, 5):
                    self.assertIn("исторический diagnostic release", section)
                    self.assertIn("`v4.25.6`", section)
                    self.assertIn("не список полученных PASS", section)
        self.assertNotIn("production acceptance ещё не закрыт", roadmap)
        self.assertIn("**N/A production exception**", roadmap)

    def test_v4257_validation_patch_is_closed_after_production_acceptance(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        heading = "##### v4.25.7 — Inbound input validation"
        self.assertEqual(roadmap.count(heading), 1)
        section = roadmap.split(heading, 1)[1].split("\n##### ", 1)[0]
        self.assertIn("**Статус: ✅ Выполнено в `v4.25.7`", section)
        for needle in (
            "issue #199",
            "closed/completed",
            "fix PR #200",
            "release PR #201",
            "2b24ce709ffe77d479c98e1604462deb4910c072",
            "053b9fecb85d009e5cfe9b323c1f4cf6d4e7d890",
            "tag `v4.25.7`",
            "production deployment выполнен",
            "финальный bot/DB/3x-ui health — **PASS**",
            "issue #202",
        ):
            self.assertIn(needle, section)

    def test_admin_setup_keeps_pinned_3xui_contract(self):
        admin_setup = (ROOT / "docs" / "ADMIN_SETUP.md").read_text(encoding="utf-8")
        self.assertIn(
            "Для bot release `v4.25.7` машинно проверяемый native API contract pinned к 3x-ui `v3.8.5`",
            admin_setup,
        )


if __name__ == "__main__":
    unittest.main()
