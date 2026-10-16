from __future__ import annotations
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("roadmap_gov", ROOT/"scripts/check-roadmap-governance.py")
gov=importlib.util.module_from_spec(spec)
spec.loader.exec_module(gov)

class RoadmapFinalGovernanceTests(unittest.TestCase):
    def test_current_register_and_release(self):
        rows=gov.roadmap_rows(ROOT)
        self.assertIn(499,rows)
        self.assertTrue(all(row["effort"] in gov.EFFORT for row in rows.values()))
        self.assertNotIn(605,rows)  # Closed docs-only issue removed after GitHub read-back
        self.assertGreaterEqual(len(rows),31)
        self.assertEqual(gov.concepts_ok(ROOT),[])
        self.assertEqual(gov.release_consistency(ROOT),[])
    def test_g09_pass_g11_pending_requires_completed_dependency(self):
        from importlib.util import module_from_spec, spec_from_file_location
        spec = spec_from_file_location(
            "roadmap_docs_semantics",
            ROOT / "scripts/check-documentation-semantics.py",
        )
        assert spec and spec.loader
        checker = module_from_spec(spec)
        spec.loader.exec_module(checker)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            content = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
            (root / "docs/ROADMAP.md").write_text(content, encoding="utf-8")
            self.assertEqual(checker.current_ok(root), [])
            # Regression: a pending/unobserved G-09 must never unblock G-11.
            stale = content.replace(
                "| PASS | Независимая VPS/data-plane attestation отсутствует;",
                "| PENDING | Независимая VPS/data-plane attestation отсутствует;",
                1,
            )
            (root / "docs/ROADMAP.md").write_text(stale, encoding="utf-8")
            self.assertTrue(
                any("G-11 must stay BLOCKED" in error
                    for error in checker.current_ok(root))
            )

    def test_registry_effort_required_and_enum(self):
        original=(ROOT/"docs/ROADMAP.md").read_text(encoding="utf-8")
        needle="| [#499](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/499)"
        row=next(x for x in original.splitlines() if x.startswith(needle))
        for replacement in (row.rsplit("|",2)[0]+"| |", row.rsplit("|",2)[0]+"| TBD |", row.rsplit("|",2)[0]+"| XXL |"):
            with self.subTest(replacement=replacement):
                with tempfile.TemporaryDirectory() as tmp:
                    root=Path(tmp); (root/"docs").mkdir()
                    (root/"docs/ROADMAP.md").write_text(original.replace(row,replacement),encoding="utf-8")
                    with self.assertRaisesRegex(ValueError,"effort|empty"):
                        gov.roadmap_rows(root)

    def test_registry_seven_columns_and_header(self):
        original=(ROOT/"docs/ROADMAP.md").read_text(encoding="utf-8")
        row=next(x for x in original.splitlines() if x.startswith("| [#499]"))
        for invalid in (original.replace(row,row.rsplit("|",2)[0]+"|",1), original.replace(" | Объём |"," |",1)):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); (root/"docs").mkdir()
                (root/"docs/ROADMAP.md").write_text(invalid,encoding="utf-8")
                with self.assertRaisesRegex(ValueError,"seven|header"):
                    gov.roadmap_rows(root)

    def test_registry_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"docs").mkdir()
            t=(ROOT/"docs/ROADMAP.md").read_text(encoding="utf-8")
            old=next(line for line in t.splitlines() if line.startswith("| [#499]"))
            (root/"docs/ROADMAP.md").write_text(t.replace("\n## Завершённые этапы", old+"\n## Завершённые этапы", 1),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"duplicate"):
                gov.roadmap_rows(root)
    def test_stage_must_not_claim_merged_without_pr(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"docs").mkdir()
            t=(ROOT/"docs/ROADMAP.md").read_text(encoding="utf-8")
            t=t.replace("| [#499](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/499) | ⬜ Запланировано | — |",
                        "| [#499](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/499) | 🟡 Реализовано в main | — |")
            (root/"docs/ROADMAP.md").write_text(t,encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"requires PR"):
                gov.roadmap_rows(root)
    def test_concept_transitions_refuse_skips(self):
        obj=json.loads((ROOT/"docs/roadmap/concept-registry.json").read_text(encoding="utf-8"))
        bad=json.loads(json.dumps(obj))
        bad["concepts"][0]["status"]="INCORPORATED"
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            path=root/"docs/roadmap/concept-registry.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(bad),encoding="utf-8")
            (root/"docs/roadmap/concepts").mkdir()
            for x in bad["concepts"]:
                (root/x["path"]).write_text("draft",encoding="utf-8")
            (root/"docs/roadmap/archive-manifest.json").write_text('{"segments":[]}',encoding="utf-8")
            errors=gov.concepts_ok(root,obj)
            self.assertTrue(any("invalid lifecycle transition" in e for e in errors))
            self.assertTrue(any("implementation" in e or "incorporation" in e for e in errors))
    def test_release_false_claim_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"docs").mkdir()
            (root/"CHANGELOG.md").write_text((ROOT/"CHANGELOG.md").read_text(encoding="utf-8"),encoding="utf-8")
            text=(ROOT/"docs/ROADMAP.md").read_text(encoding="utf-8")
            # Мутируем фактическую сводку, не закрепляя устаревающий текст.
            summary=text.split("## Актуальная сводка проекта",1)[1].split("\n## ",1)[0]
            accepted=summary.split("**Accepted:**",1)[1].split("\n",1)[0]
            self.assertIn("NOT PASS",accepted)
            text=text.replace("**Accepted:**"+accepted,"**Accepted:** full acceptance PASS",1)
            (root/"docs/ROADMAP.md").write_text(text,encoding="utf-8")
            self.assertTrue(gov.release_consistency(root))
    def test_concept_change_requires_registry_review(self):
        errors=gov.validate(ROOT,[("docs/roadmap/concepts/client-portal-ux.md","M")])
        self.assertTrue(any("same-PR lifecycle registry" in error for error in errors))

    def test_dated_audit_deletion_is_blocked(self):
        errors=gov.validate(ROOT,[("docs/audits/2026-10-13-roadmap-github-first-dispatch.md","D")])
        self.assertTrue(any("dated audit deletion forbidden" in x for x in errors))

    def test_changed_audit_invalid_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"docs/audits").mkdir(parents=True)
            file=root/"docs/audits/2026-10-13-new.md"
            file.write_text("PASS",encoding="utf-8")
            checker=gov.load_audit(ROOT)
            self.assertTrue(checker.audit_ok(root,"docs/audits/2026-10-13-new.md"))
