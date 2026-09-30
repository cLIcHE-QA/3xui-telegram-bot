"""Release contracts through v4.26.1 Node Drain Cancel navigation."""
from __future__ import annotations

from pathlib import Path
import unittest

from version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class V4261ReleaseTests(unittest.TestCase):
    def test_release_version_is_4261(self):
        self.assertEqual(APP_VERSION, "4.26.1")

    def test_current_docs_reference_release_4261(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        admin_setup = (ROOT / "docs" / "ADMIN_SETUP.md").read_text(encoding="utf-8")
        sqlite_doc = (ROOT / "docs" / "SQLITE_MIGRATIONS.md").read_text(encoding="utf-8")

        self.assertTrue(readme.startswith("# Telegram-бот для 3x-ui v4.26.1"))
        self.assertIn("Guide ориентирован на release v4.26.1.", admin_setup)
        self.assertIn("git checkout --detach v4.26.1", admin_setup)
        self.assertIn("Bot version: 4.26.1", admin_setup)
        self.assertIn(
            "Для `v4.24.0`, `v4.24.1`, `v4.25.0`, `v4.25.1`, `v4.25.2`, `v4.25.3`, `v4.25.4`, `v4.25.5`, `v4.25.6`, `v4.25.7`, `v4.25.8`, `v4.26.0` и `v4.26.1` текущая bot schema version — **5**",
            sqlite_doc,
        )

    def test_release_notes_cover_v4261_scope(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(changelog.count("## v4.26.1 — Node Drain Cancel navigation"), 1)
        section = changelog.split("## v4.26.1 — Node Drain Cancel navigation", 1)[1].split("\n## ", 1)[0]
        for needle in (
            "✖ Отмена",
            "read-only preflight",
            "review → cancelled",
            "no-mutation contract",
            "Stale `run`",
            "SQLite schema остаётся v5",
            "OpenAPI contract остаётся v3.8.5",
            "finding #211",
        ):
            self.assertIn(needle, section)

    def test_release_notes_cover_v4260_scope(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(changelog.count("## v4.26.0 — Node Drain"), 1)
        section = changelog.split("## v4.26.0 — Node Drain", 1)[1].split("\n## ", 1)[0]
        for needle in (
            "graceful Node Drain",
            "attach-before-detach",
            "last-working-Inbound guard",
            "XUIMutationError",
            "draining",
            "drained",
            "fleet.drain",
            "без reverse replay",
            "SQLite schema остаётся v5",
        ):
            self.assertIn(needle, section)

    def test_release_notes_cover_v4258_scope(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(changelog.count("## v4.25.8 — navigation and Owner self-role safety"), 1)
        section = changelog.split("## v4.25.8 — navigation and Owner self-role safety", 1)[1].split("\n## ", 1)[0]
        for needle in (
            "Clone Inbound",
            "DB-backed Owner",
            "FSM state",
            "nonce",
            "ADMIN_TELEGRAM_IDS",
            "SQLite schema v5",
            "OpenAPI contract v3.8.5",
        ):
            self.assertIn(needle, section)

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

    def test_roadmap_closes_full_v425_line_after_v4258_acceptance(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        self.assertIn("##### v4.25.4 — Streisand plain subscription compatibility", roadmap)
        self.assertIn("##### v4.25.5 — Streisand plain mode precedence", roadmap)
        self.assertIn("##### v4.25.6 — Streisand incompatibility / forward revert", roadmap)
        self.assertIn("test 50 — version/health: **PASS**", roadmap)
        self.assertIn("test 55 — Streisand: **EXPECTED LIMITATION**", roadmap)
        self.assertIn("test 56 — final bot/DB/3x-ui health: **PASS**", roadmap)
        self.assertIn("hwid_not_supported", roadmap)
        self.assertIn("не передаёт совместимый `X-HWID`", roadmap)
        self.assertIn("`v4.25.0–v4.25.8` полностью проверены и operationally закрыты", roadmap)
        self.assertIn("graceful Node Drain / вывод direct-ноды", roadmap)
        self.assertIn("issue #202 закрыт как `completed`", roadmap)
        self.assertIn("issue #204 закрыт как `completed`", roadmap)

    def test_v425_line_is_closed_without_claiming_streisand_support(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        for patch_version in range(8):
            heading = f"##### v4.25.{patch_version} — "
            with self.subTest(release=heading):
                self.assertEqual(roadmap.count(heading), 1)
                section = roadmap.split(heading, 1)[1].split("\n##### ", 1)[0]
                self.assertIn("**Статус: ✅", section)
                if patch_version in (4, 5):
                    self.assertIn("исторический diagnostic release", section)
                    self.assertIn("`v4.25.6`", section)
                    self.assertIn("не список полученных PASS", section)
        self.assertEqual(roadmap.count("##### v4.25.8 — "), 2)
        for heading in (
            "##### v4.25.8 — Inbound clone navigation hotfix",
            "##### v4.25.8 — Owner self-role safety",
        ):
            section = roadmap.split(heading, 1)[1].split("\n##### ", 1)[0]
            self.assertIn("**Статус: ✅ Выполнено в `v4.25.8`", section)
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

    def test_v4258_production_acceptance_is_recorded(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        for needle in (
            "tag/GitHub Release `v4.25.8`",
            "768fc0e4b9a0c0d2e35508febf272709896c3e7f",
            "587 tests OK",
            "targeted production tests navigation hotfix и Owner self-demotion safety — **PASS**",
            "final bot/DB/3x-ui health — **PASS**",
            "issues #202 и #204",
        ):
            self.assertIn(needle, roadmap)

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Линия `v4.25.x` (`v4.25.0–v4.25.8`) полностью опубликована", readme)

    def test_v4260_is_deployed_but_production_acceptance_is_partial(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        heading = "##### v4.26.0 — Node Drain / graceful traffic evacuation"
        section = roadmap.split(heading, 1)[1].split("\n##### ", 1)[0]
        for needle in (
            "`v4.26.0` опубликован и развёрнут",
            "production acceptance частичный",
            "полный mutation smoke ещё не закрыт",
            "issue #208",
            "implementation PR #209",
            "e46c58870ea31b3a0532bd69b9b2dc01ba9bfa4a",
            "release-prep PR #210",
            "cd39048a2da00443523e7b33b400f4c8b5dcd608",
            "finding #211",
            "полный mutation smoke",
        ):
            self.assertIn(needle, section)

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Текущий runtime-релиз `v4.26.1` сохраняет graceful Node Drain", readme)
        self.assertIn("полный Node Drain mutation smoke", readme)

    def test_v4261_fix_is_merged_but_not_production_verified(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        heading = "##### v4.26.1 — Node Drain Cancel navigation"
        section = roadmap.split(heading, 1)[1].split("\n##### ", 1)[0]
        for needle in (
            "🟡 Реализовано в `main`",
            "release `v4.26.1` ещё не опубликован",
            "issue #211 остаётся открыт",
            "fix PR #213",
            "218f2e9fda914b05121051dd0dd00a94ba99dc6b",
            "no-mutation Cancel",
            "stale/cancelled `run`",
            "targeted Cancel smoke",
        ):
            self.assertIn(needle, section)

    def test_admin_setup_keeps_pinned_3xui_contract(self):
        admin_setup = (ROOT / "docs" / "ADMIN_SETUP.md").read_text(encoding="utf-8")
        self.assertIn(
            "Для bot release `v4.26.1` машинно проверяемый native API contract pinned к 3x-ui `v3.8.5`",
            admin_setup,
        )


if __name__ == "__main__":
    unittest.main()
