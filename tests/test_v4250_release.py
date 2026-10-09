"""Release contracts through v4.26.9 subscription browser hotfix."""
from __future__ import annotations

from pathlib import Path
import unittest

from version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class V4269ReleaseTests(unittest.TestCase):
    def test_v4269_remains_historical_release_contract(self):
        self.assertNotEqual(APP_VERSION, "4.26.9")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        sqlite_doc = (ROOT / "docs" / "SQLITE_MIGRATIONS.md").read_text(encoding="utf-8")

        self.assertIn("## v4.26.9 — Subscription browser compatibility hotfix", changelog)
        self.assertIn(
            "Для `v4.24.0`, `v4.24.1`, `v4.25.0`, `v4.25.1`, `v4.25.2`, `v4.25.3`, `v4.25.4`, `v4.25.5`, `v4.25.6`, `v4.25.7`, `v4.25.8`, `v4.26.0`, `v4.26.1`, `v4.26.2`, `v4.26.3`, `v4.26.4`, `v4.26.5`, `v4.26.6`, `v4.26.7` и `v4.26.8` текущая bot schema version — **5**",
            sqlite_doc,
        )
        self.assertIn("Для `v4.26.9` текущая bot schema version — **7**.", sqlite_doc)

    def test_release_notes_cover_v4269_scope(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        heading = "## v4.26.9 — Subscription browser compatibility hotfix"
        self.assertEqual(changelog.count(heading), 1)
        section = changelog.split(heading, 1)[1].split("\n## ", 1)[0]
        for needle in (
            "window.X_UI_BASE_PATH",
            "/compat/",
            "X-Accel-Buffering: no",
            "browser regression tests",
            "Client Portal foundation",
            "публичный signup не открыт",
            "payment provider/checkout ещё не подключён",
            "SQLite schema version — **7**",
            "OpenAPI contract остаётся v3.8.5",
        ):
            self.assertIn(needle, section)

    def test_release_notes_cover_v4268_scope(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        heading = "## v4.26.8 — A-011 non-root startup hotfix"
        self.assertEqual(changelog.count(heading), 1)
        section = changelog.split(heading, 1)[1].split("\n## ", 1)[0]
        for needle in (
            "production blocker `v4.26.7`",
            "/app/restore_bootstrap.py",
            "u=rwX,go=rX",
            "10001:10001",
            "read-only rootfs",
            "mode `0600`",
            "A-011/#244",
            "A-012/#245",
            "SQLite schema остаётся v5",
            "OpenAPI contract остаётся v3.8.5",
        ):
            self.assertIn(needle, section)

    def test_release_notes_cover_v4267_scope(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        heading = "## v4.26.7 — Final v4 audit hardening: container, proxy и supply chain"
        self.assertEqual(changelog.count(heading), 1)
        section = changelog.split(heading, 1)[1].split("\n## ", 1)[0]
        for needle in (
            "A-011/#244",
            "10001:10001",
            "read-only root filesystem",
            "A-012/#245",
            "32 concurrent upstream fetch",
            "8 MiB",
            "requirements.lock",
            "Apache-2.0",
            "targeted smoke A-011/A-012",
            "SQLite schema остаётся v5",
            "OpenAPI contract остаётся v3.8.5",
        ):
            self.assertIn(needle, section)

    def test_release_notes_cover_v4266_scope(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(
            changelog.count(
                "## v4.26.6 — Final v4 audit remediation: admin boundary, redirects и file modes"
            ),
            1,
        )
        section = changelog.split(
            "## v4.26.6 — Final v4 audit remediation: admin boundary, redirects и file modes",
            1,
        )[1].split("\n## ", 1)[0]
        for needle in (
            "A-004/#237",
            "private Telegram chat",
            "A-005/#238",
            "cross-origin",
            "HTTPS downgrade",
            "A-006/#239",
            "0700/0600",
            "SQLite schema остаётся v5",
            "OpenAPI contract остаётся v3.8.5",
            "targeted production acceptance",
        ):
            self.assertIn(needle, section)

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

    def test_release_notes_cover_v4264_scope(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(changelog.count("## v4.26.4 — Permission-aware admin navigation"), 1)
        section = changelog.split("## v4.26.4 — Permission-aware admin navigation", 1)[1].split("\n## ", 1)[0]
        for needle in (
            "production finding #226",
            "RBAC callback catalog",
            "read_only",
            "owner-only",
            "Attention Center",
            "calm/empty state",
            "Canonical parent semantics",
        ):
            self.assertIn(needle, section)

    def test_release_notes_cover_v4263_scope(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(changelog.count("## v4.26.3 — Attention Center drill-down"), 1)
        section = changelog.split("## v4.26.3 — Attention Center drill-down", 1)[1].split("\n## ", 1)[0]
        for needle in (
            "⚠️ Требует внимания",
            "grouped detail",
            "stable technical identity",
            "5 items",
            "canonical read-only deep-links",
            "admin:attention",
            "Read-only+",
            "remote mutations нет",
        ):
            self.assertIn(needle, section)

    def test_release_notes_cover_v4262_scope(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(changelog.count("## v4.26.2 — Dashboard Attention summary"), 1)
        section = changelog.split("## v4.26.2 — Dashboard Attention summary", 1)[1].split("\n## ", 1)[0]
        for needle in (
            "⚠️ Требует внимания",
            "latest problematic background jobs",
            "offline/unknown direct-node states",
            "failed",
            "unknown",
            "interrupted",
            "Read-only+ boundary",
            "v4.26.3",
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

    def test_v4260_production_acceptance_is_recorded(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        heading = "##### v4.26.0 — Node Drain / graceful traffic evacuation"
        section = roadmap.split(heading, 1)[1].split("\n##### ", 1)[0]
        for needle in (
            "`v4.26.0` опубликован и развёрнут",
            "полный controlled state-changing production acceptance завершён 2026-10-01",
            "issue #208 закрыт как `completed`",
            "implementation PR #209",
            "e46c58870ea31b3a0532bd69b9b2dc01ba9bfa4a",
            "release-prep PR #210",
            "cd39048a2da00443523e7b33b400f4c8b5dcd608",
            "finding #211",
            "affected=1, movable=1, blockers=0",
            "`drained`",
            "remaining assignments=0",
            "reconnect через альтернативный Master прошёл успешно",
            "временные test user/plan/server group/Inbound/node bindings",
        ):
            self.assertIn(needle, section)

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Controlled Node Drain production acceptance #208 завершён 2026-10-01", readme)

    def test_final_v4_feature_freeze_is_recorded(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        for needle in (
            "off-site recovery drill завершён 2026-10-05",
            "`backup.offsite` завершился `success`",
            "`OFFSITE_RECOVERY_OK`",
            "`manifest.version=4.26.4`",
            "**final v4 feature freeze объявлен 2026-10-05**",
            "**Активный gate:** провести полный финальный repository/public-release audit",
            "Final v4 feature freeze действует с 2026-10-05",
        ):
            self.assertIn(needle, roadmap)
        self.assertNotIn("Единственный оставшийся обязательный pre-freeze gate", roadmap)

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Encrypted off-site backup/restore drill завершён 2026-10-05", readme)
        self.assertIn("**Final v4 feature freeze действует с 2026-10-05**", readme)
        self.assertIn("до закрытия repository/public-release audit", readme)
        self.assertNotIn("Единственный оставшийся обязательный pre-freeze gate", readme)

    def test_data_plane_hardening_219_is_closed(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        heading = "##### Data-plane address hardening — issue #219"
        section = roadmap.split(heading, 1)[1].split("\n##### ", 1)[0]
        for needle in (
            "issue #219 закрыт как `completed`",
            "`Node.address` остаётся только control-plane endpoint",
            "Отдельная node-level `data_plane_address`",
            "`shareAddrStrategy=custom`",
            "Automatic DNS→IP persistence",
            "Reality SNI/serverNames",
            "read-back подтвердил `custom`",
            "обновлённая subscription успешно переподключилась через test node",
        ):
            self.assertIn(needle, section)

    def test_v4261_production_acceptance_is_recorded(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        heading = "##### v4.26.1 — Node Drain Cancel navigation"
        section = roadmap.split(heading, 1)[1].split("\n##### ", 1)[0]
        for needle in (
            "✅ Выполнено в `v4.26.1`",
            "issue #211 закрыт как `completed`",
            "fix PR #213",
            "218f2e9fda914b05121051dd0dd00a94ba99dc6b",
            "release-prep PR #214",
            "c2fc8baee1c11a716babb4bfc72743dface686ed",
            "runtime version `4.26.1` подтверждён",
            "финальный health/status — **PASS**",
            "issue #208",
            "полный state-changing Node Drain mutation smoke",
        ):
            self.assertIn(needle, section)

    def test_v4262_production_acceptance_is_recorded(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        heading = "##### v4.26.2 — Dashboard Attention summary"
        section = roadmap.split(heading, 1)[1].split("\n##### ", 1)[0]
        for needle in (
            "✅ Выполнено в `v4.26.2`",
            "release-prep PR #222",
            "467d4f5609290622f0f839ce103fbf606f6f29b6",
            "targeted read-only smoke `/admin → Обзор` — **PASS**",
            "`RestartCount=0`",
            "Health/DB/3x-ui connectivity — ok",
            "issue #216 закрыт как `completed`",
        ):
            self.assertIn(needle, section)


    def test_v4264_production_acceptance_is_recorded(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        heading = "##### v4.26.4 — Permission-aware admin navigation fix"
        section = roadmap.split(heading, 1)[1].split("\n##### ", 1)[0]
        for needle in (
            "✅ Выполнено в `v4.26.4`",
            "release-prep PR #229",
            "e2b6834d549a6b3272702fc27570c8a8a3a99bfe",
            "targeted role smoke — **PASS**",
            "Attention Center `Refresh/Back`",
            "`RestartCount=0`",
            "Health/DB/3x-ui connectivity — ok",
            "bug #226 и feature acceptance #217 закрыты как `completed`",
        ):
            self.assertIn(needle, section)


    def test_admin_setup_keeps_pinned_3xui_contract(self):
        admin_setup = (ROOT / "docs" / "ADMIN_SETUP.md").read_text(encoding="utf-8")
        self.assertIn(
            "Для bot release `v5.0.0-rc.7` машинно проверяемый native API contract pinned к 3x-ui `v3.9.0`",
            admin_setup,
        )


if __name__ == "__main__":
    unittest.main()
