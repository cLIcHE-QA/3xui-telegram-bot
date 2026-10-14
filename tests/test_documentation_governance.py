from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from version import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sem = load("semantic_docs", "scripts/check-documentation-semantics.py")
gh = load("roadmap_github", "scripts/check-roadmap-github.py")


class DocumentationGovernanceTests(unittest.TestCase):
    def test_current_valid_and_immutable_sources(self):
        self.assertEqual(sem.current_ok(ROOT), [])
        manifest = json.loads((ROOT / "docs/roadmap/archive-manifest.json").read_text(encoding="utf-8"))
        paths = [s["path"] for s in manifest["segments"]]
        self.assertFalse(any(p.startswith("docs/roadmap/concepts/") for p in paths))
        self.assertEqual(
            sum("source-" in p for p in paths), 3
        )

    def test_new_audit_requires_all_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs/audits").mkdir(parents=True)
            path = "docs/audits/2026-10-13-new-test.md"
            (root / path).write_text("PASS", encoding="utf-8")
            errors = sem.audit_ok(root, path)
            self.assertIn(f"{path}: audit-schema marker must appear exactly once", errors)
            self.assertGreater(len(errors), 10)

    def test_valid_new_audit_and_corruption(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs/audits").mkdir(parents=True)
            path = "docs/audits/2026-10-13-example.md"
            good = """# Результат

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-13 19:45 UTC+03:00
- **Окружение:** GitHub Actions
- **Цель:** verification
- **Версия и immutable tag/SHA:** v5.0.0-rc.9 `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`
- **Scope:** read-only GitHub
- **Фактический результат:** PASS — exact checked scope
- **Источник и evidence:** https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38432290724
- **Ограничения и остаточные риски:** Not production
- **Связанные Issues:** #597
- **Следующий шаг:** Документировать
- **Раздельные состояния:** merged=main; published=rc.9; deployed=operator-reported; accepted=NOT PASS
"""
            (root / path).write_text(good, encoding="utf-8")
            self.assertEqual(sem.audit_ok(root, path), [])
            broken = good.replace("**Фактический результат:** PASS", "**Фактический результат:** UNKNOWN")
            (root / path).write_text(broken, encoding="utf-8")
            self.assertIn(f"{path}: invalid audit result status", sem.audit_ok(root, path))
            broken = good.replace("**Источник и evidence:** https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38432290724",
                                  "**Источник и evidence:** без подтверждения")
            (root / path).write_text(broken, encoding="utf-8")
            self.assertIn(f"{path}: evidence must identify a source/link", sem.audit_ok(root, path))

    def test_local_markdown_paths_and_unicode_anchors(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs").mkdir()
            (root / "docs/target.md").write_text("# Пример раздела\n\n## Вторая секция\n", encoding="utf-8")
            (root / "docs/index.md").write_text(
                "[ok](target.md#пример-раздела) [ok2](target.md#вторая-секция)\n", encoding="utf-8")
            self.assertEqual(sem.links_ok(root, "docs/index.md"), [])
            (root / "docs/index.md").write_text("[broken](target.md#несуществующий)\n", encoding="utf-8")
            self.assertTrue(any("missing Markdown anchor" in x for x in sem.links_ok(root, "docs/index.md")))
            (root / "docs/index.md").write_text("[broken](missing.md)\n", encoding="utf-8")
            self.assertTrue(any("broken local link" in x for x in sem.links_ok(root, "docs/index.md")))
            (root / "docs/index.md").write_text("```md\n[example](missing.md)\n```\n", encoding="utf-8")
            self.assertEqual(sem.links_ok(root, "docs/index.md"), [])

    def test_completed_issue_summary_is_bounded(self):
        roadmap = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
        self.assertFalse(any("completed" in x for x in sem.current_ok(ROOT)))
        self.assertIn("**✅ Завершено в docs/CI scope:**", roadmap)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs").mkdir()
            path = root / "docs/ROADMAP.md"
            path.write_text(roadmap.replace("## Активный Issue-реестр",
                "**✅ Завершено в docs/CI scope:** дубликат\\n\\n## Активный Issue-реестр"),encoding="utf-8")
            self.assertTrue(any("at most one aggregate" in x for x in sem.current_ok(root)))
            path.write_text(roadmap.replace("## Активный Issue-реестр",
                "**✅ Документационное governance #999:** отдельный closure\\n\\n## Активный Issue-реестр"),encoding="utf-8")
            self.assertTrue(any("individual completed" in x for x in sem.current_ok(root)))
            path.write_text(roadmap.replace("**✅ Завершено в docs/CI scope:**",
                "**✅ Завершено в docs/CI scope:**" + "длинный текст " * 120),encoding="utf-8")
            self.assertTrue(any("exceeds 1200" in x for x in sem.current_ok(root)))

    def test_g11_stays_blocked_on_g09_after_d1_checkpoint(self):
        roadmap = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
        self.assertIn("**BLOCKED ON G-09**", roadmap)
        self.assertNotIn("**BLOCKED ON G-09 + D1**", roadmap)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs").mkdir()
            path = root / "docs/ROADMAP.md"
            path.write_text(roadmap.replace("**BLOCKED ON G-09**", "**PASS**"), encoding="utf-8")
            self.assertTrue(any("G-11 dependency" in x for x in sem.current_ok(root)))

    def test_all_acceptance_gates_are_unique(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs").mkdir()
            roadmap = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
            (root / "docs/ROADMAP.md").write_text(roadmap + "\n| G-01 | duplicated | PASS |\n", encoding="utf-8")
            self.assertTrue(any("duplicate acceptance gate G-01" in x for x in sem.current_ok(root)))

    def test_github_reconciliation_discovery_and_drift(self):
        text = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
        references, expectations = gh.expectations(text)
        self.assertGreater(len(references), 12)
        self.assertIn(433, expectations)
        self.assertEqual(expectations[433], "open")
        self.assertEqual(expectations[597], "closed")
        actual = {n: expectations.get(n, "open") for n in references}
        version = gh.declared_published(text)
        self.assertEqual(version, "v" + APP_VERSION)
        gh.validate(text, actual, version)
        with self.assertRaises(gh.Drift):
            gh.validate(text, {k: v for k, v in actual.items() if k != 433}, version)
        modified = dict(actual)
        modified[433] = "closed"
        with self.assertRaises(gh.Drift):
            gh.validate(text, modified, version)
        with self.assertRaises(gh.Drift):
            gh.validate(text, actual, "v9.9.9")

    def test_github_reconciliation_release_neutral(self):
        text = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
        future = text.replace("**Published:** immutable prerelease [`v" + APP_VERSION + "`]",
                              "**Published:** immutable prerelease [`v5.0.0-rc.42`]", 1)
        self.assertEqual(gh.declared_published(future), "v5.0.0-rc.42")

    def test_full_reconciliation_uses_second_page_and_filters_prs(self):
        from unittest.mock import patch
        import importlib.util
        spec=importlib.util.spec_from_file_location("governance_pagination",ROOT/"scripts/check-roadmap-governance.py")
        gov=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gov)
        open_ids=sorted(gov.roadmap_rows(ROOT))
        self.assertGreater(len(open_ids),1)
        page1=[{"number":n} for n in open_ids[:-1]]
        page1 += [{"number":900000+i,"pull_request":{}} for i in range(100-len(page1))]
        page2=[{"number":open_ids[-1]}]
        requested=[]
        def fake_fetch(repo,suffix,token=""):
            requested.append(suffix)
            if suffix.startswith("/issues/"):
                n=int(suffix.split("/")[-1])
                return {"state":gh.expectations((ROOT/"docs/ROADMAP.md").read_text(encoding="utf-8"))[1].get(n,"open")}
            if suffix.startswith("/releases?"):
                return [{"tag_name":"v"+APP_VERSION,"published_at":"2026-10-11T11:24:04Z","draft":False}]
            if suffix.endswith("page=1"):return page1
            if suffix.endswith("page=2"):return page2
            raise AssertionError("unexpected GitHub request "+suffix)
        with patch.object(gh,"fetch",side_effect=fake_fetch):
            tag,issues,classified,active_count=gh.audit("cLIcHE-QA/3xui-telegram-bot",ROOT)
        self.assertEqual(tag,"v"+APP_VERSION)
        self.assertEqual(active_count,len(open_ids))
        self.assertIn("/issues?state=open&per_page=100&page=2",requested)
