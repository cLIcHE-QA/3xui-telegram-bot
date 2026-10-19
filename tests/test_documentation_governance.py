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
            (root / "docs/roadmap").mkdir(parents=True)
            (root / "docs/roadmap/issue-closure-decisions.json").write_text(json.dumps({"schema": 1, "decisions": [{"issue": 597, "decision": "completed"}]}), encoding="utf-8")
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
- **Решение по Issues:** #597: completed
- **Следующий шаг:** Документировать
- **Раздельные состояния:** merged=main; published=rc.9; deployed=operator-reported; accepted=NOT PASS
"""
            (root / path).write_text(good, encoding="utf-8")
            self.assertEqual(sem.audit_ok(root, path), [])
            broken = good.replace("- **Решение по Issues:** #597: completed\\n", "")
            (root / path).write_text(broken, encoding="utf-8")
            self.assertTrue(any("PASS audit requires explicit closure decision" in e for e in sem.audit_ok(root, path)))
            broken = good.replace("#597: completed", "#597: keep_open")
            (root / path).write_text(broken, encoding="utf-8")
            self.assertTrue(any("closure decisions missing/mismatched" in e for e in sem.audit_ok(root, path)))
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
        self.assertNotIn("**✅ Завершено в docs/CI scope:**", roadmap)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs").mkdir()
            path = root / "docs/ROADMAP.md"
            path.write_text(roadmap.replace("## Активный Issue-реестр",
                "**✅ Завершено в docs/CI scope:** дубликат\\n\\n## Активный Issue-реестр"),encoding="utf-8")
            self.assertEqual(sem.current_ok(root), [])  # One optional aggregate is bounded and permitted
            path.write_text(roadmap.replace("## Активный Issue-реестр",
                "**✅ Завершено a**\n**✅ Завершено b**\n\n## Активный Issue-реестр"), encoding="utf-8")
            self.assertTrue(any("at most one aggregate" in x for x in sem.current_ok(root)))
            path.write_text(roadmap.replace("## Активный Issue-реестр",
                "**✅ Документационное governance #999:** отдельный closure\\n\\n## Активный Issue-реестр"),encoding="utf-8")
            self.assertTrue(any("individual completed" in x for x in sem.current_ok(root)))
            path.write_text(roadmap.replace("## Активный Issue-реестр",
                "**✅ Завершено в docs/CI scope:**" + "длинный текст " * 120 + "\\n\\n## Активный Issue-реестр"),encoding="utf-8")
            self.assertTrue(any("exceeds 1200" in x for x in sem.current_ok(root)))

    def test_g11_unblocked_only_after_g09_checkpoint(self):
        roadmap = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
        self.assertIn("| G-09 |", roadmap)
        self.assertIn("| G-11 |", roadmap)
        self.assertIn("**G-11 / PARTIAL:**", roadmap)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs").mkdir()
            path = root / "docs/ROADMAP.md"
            path.write_text(
                roadmap.replace("| G-09 | Natural paid Stars entitlement:", "| G-09 | Natural paid Stars entitlement:")
                .replace("| PASS | Независимая VPS/data-plane attestation отсутствует;",
                         "| PENDING | Независимая VPS/data-plane attestation отсутствует;", 1),
                encoding="utf-8",
            )
            self.assertTrue(any("G-11 must stay BLOCKED" in x for x in sem.current_ok(root)))

    def test_canonical_gate_status_and_queue_lifecycle(self):
        roadmap = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
        self.assertEqual(sem.current_ok(ROOT), [])
        mutations = [
            ("| G-01 |", "| G-99 |", "acceptance gate set mismatch"),
            ("| PARTIAL | Независимая", "| CLOSED | Независимая", "invalid gate row or verdict"),
            ("| G-02 |", "| G-02 |", None),
            ("OPERATOR-WAIVED / NOT TESTED", "PASS", "waiver register mismatch"),
            ("1. **G-11 / PARTIAL:", "1. **D1 / PASS:", "queue row must have active gate"),
            ("1. **G-11 / PARTIAL:", "1. **G-11 / PASS:", "queue row must have active gate"),
            ("| Gate | Что проверено | Итог gate | Осталось / риск |",
             "| Gate | Checked | Status | Next |", "canonical four-column header"),
        ]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs").mkdir()
            path = root / "docs/ROADMAP.md"
            for old, new, expected in mutations:
                if expected is None:
                    continue
                self.assertIn(old, roadmap)
                path.write_text(roadmap.replace(old, new, 1), encoding="utf-8")
                errors = sem.current_ok(root)
                self.assertTrue(any(expected in x for x in errors), (old, errors))

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
        self.assertIn(499, expectations)
        self.assertEqual(expectations[499], "open")
        self.assertNotIn(597, expectations)  # Closed history is not a living Issue register
        actual = {n: expectations.get(n, "open") for n in references}
        version = gh.declared_published(text)
        # Release-prep APP_VERSION may advance before immutable prerelease publication.
        self.assertIn("v" + APP_VERSION, text)
        gh.validate(text, actual, version)
        with self.assertRaises(gh.Drift):
            gh.validate(text, {k: v for k, v in actual.items() if k != 499}, version)
        modified = dict(actual)
        modified[499] = "closed"
        with self.assertRaises(gh.Drift):
            gh.validate(text, modified, version)
        with self.assertRaises(gh.Drift):
            gh.validate(text, actual, "v9.9.9")

    def test_lifecycle_merged_runtime_pr_requires_implemented_status(self):
        rows = {
            752: {"status": gh.PLANNED,
                  "pr": "[PR #754](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/754)"},
        }
        calls = []
        def github(repo, suffix, token=""):
            calls.append(suffix)
            if suffix == "/pulls/754":
                return {"merged": True, "merge_commit_sha": "6a735dc67db4efd08849bcff8f56e5ff6fff4315",
                        "base": {"ref": "main"}}
            if suffix == "/pulls/754/files?per_page=100":
                return [{"filename": "db.py"}, {"filename": "manual_entitlements.py"},
                        {"filename": "docs/ROADMAP.md"}]
            raise AssertionError(suffix)
        with self.assertRaisesRegex(gh.Drift, r"Issue #752 is planned"):
            gh.implementation_drift(rows, "cLIcHE-QA/3xui-telegram-bot", github)
        rows[752]["status"] = gh.IMPLEMENTED
        gh.implementation_drift(rows, "cLIcHE-QA/3xui-telegram-bot", github)
        self.assertIn("/pulls/754/files?per_page=100", calls)

    def test_lifecycle_docs_only_and_unmerged_do_not_count_as_implementation(self):
        rows = {
            707: {"status": gh.PLANNED, "pr":
                  "[PR #708](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/708)"},
            752: {"status": gh.PLANNED, "pr":
                  "[PR #754](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/754)"},
        }
        def github(repo, suffix, token=""):
            if suffix == "/pulls/708":
                return {"merged": True, "merge_commit_sha": "a" * 40,
                        "base": {"ref": "main"}}
            if suffix == "/pulls/708/files?per_page=100":
                return [{"filename": "docs/ROADMAP.md"},
                        {"filename": "docs/LEGAL_PORTAL_PLACEMENT.md"}]
            if suffix == "/pulls/754":
                return {"merged": False, "merge_commit_sha": None, "base": {"ref": "main"}}
            raise AssertionError(suffix)
        gh.implementation_drift(rows, "cLIcHE-QA/3xui-telegram-bot", github)
        rows[707]["status"] = gh.IMPLEMENTED
        with self.assertRaisesRegex(gh.Drift, r"Issue #707 claims implemented"):
            gh.implementation_drift(rows, "cLIcHE-QA/3xui-telegram-bot", github)

    def test_lifecycle_implemented_without_merged_pr_or_link_is_rejected(self):
        rows = {752: {"status": gh.IMPLEMENTED,
                      "pr": "[PR #754](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/754)"}}
        def unmerged(repo, suffix, token=""):
            return {"merged": False, "base": {"ref": "main"}}
        with self.assertRaisesRegex(gh.Drift, "without merged runtime PR"):
            gh.implementation_drift(rows, "cLIcHE-QA/3xui-telegram-bot", unmerged)
        rows[752]["pr"] = "—"
        with self.assertRaisesRegex(gh.Drift, "without implementation PR"):
            gh.implementation_drift(rows, "cLIcHE-QA/3xui-telegram-bot", unmerged)

    def test_lifecycle_unknown_fails_closed(self):
        rows = {752: {"status": gh.IMPLEMENTED,
                      "pr": "https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/754"}}
        def unreachable(repo, suffix, token=""):
            raise gh.Unknown("GitHub unavailable")
        with self.assertRaises(gh.Unknown):
            gh.implementation_drift(rows, "cLIcHE-QA/3xui-telegram-bot", unreachable)

    def test_closure_decisions_prevent_accepted_open_and_stale_rows(self):
        rows = {730: {"status": gh.IMPLEMENTED, "pr": "PR"}, 760: {"status": gh.PLANNED, "pr": "—"}}
        sample = {"schema": 1, "decisions": [
            {"issue": 730, "decision": "completed",
             "accepted": "operator-reported", "evidence": "docs/audits/a.md",
             "date": "2026-10-19", "comment": "scoped closure"}
        ]}
        with self.assertRaisesRegex(gh.Drift, "accepted/completed"):
            gh.closure_decisions_ok(rows, {730: "open", 760: "open"}, sample)
        with self.assertRaisesRegex(gh.Drift, "accepted/completed"):
            gh.closure_decisions_ok(rows, {730: "closed", 760: "open"}, sample)
        rows.pop(730)
        gh.closure_decisions_ok(rows, {730: "closed", 760: "open"}, sample)
        sample["decisions"][0]["decision"] = "keep_open"
        with self.assertRaisesRegex(gh.Drift, "keep_open"):
            gh.closure_decisions_ok(rows, {730: "closed", 760: "open"}, sample)
        sample["decisions"][0]["decision"] = "completed"
        sample["decisions"].append(dict(sample["decisions"][0]))
        with self.assertRaisesRegex(gh.Drift, "duplicate"):
            gh.closure_decisions_ok(rows, {730: "closed", 760: "open"}, sample)
        sample["decisions"][1]["issue"] = 999
        with self.assertRaisesRegex(gh.Drift, "not fetched"):
            gh.closure_decisions_ok(rows, {730: "closed", 760: "open"}, sample)

    def test_github_reconciliation_release_neutral(self):
        text = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
        current = gh.declared_published(text)
        # Test version discovery independently of the surrounding canary wording.
        # Не зависим от оформления Markdown-ссылки вокруг опубликованного тега.
        prefix, marker, published = text.partition("**Published:**")
        self.assertTrue(marker)
        self.assertIn(current, published[:600])
        future = prefix + marker + published.replace(current, "v5.0.0-rc.42", 1)
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
                return [{"tag_name":gh.declared_published((ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")),"published_at":"2026-10-11T11:24:04Z","draft":False}]
            if suffix.endswith("page=1"):return page1
            if suffix.endswith("page=2"):return page2
            raise AssertionError("unexpected GitHub request "+suffix)
        with patch.object(gh,"fetch",side_effect=fake_fetch), \
             patch.object(gh,"implementation_drift"):
            tag,issues,classified,active_count=gh.audit("cLIcHE-QA/3xui-telegram-bot",ROOT)
        self.assertEqual(tag,gh.declared_published((ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")))
        self.assertEqual(active_count,len(open_ids))
        self.assertIn("/issues?state=open&per_page=100&page=2",requested)
