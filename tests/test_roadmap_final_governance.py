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
        self.assertIn(433,rows)
        self.assertNotIn(605,rows)  # Closed docs-only issue removed after GitHub read-back
        self.assertGreaterEqual(len(rows),31)
        self.assertEqual(gov.concepts_ok(ROOT),[])
        self.assertEqual(gov.release_consistency(ROOT),[])
    def test_registry_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"docs").mkdir()
            t=(ROOT/"docs/ROADMAP.md").read_text(encoding="utf-8")
            old=next(line for line in t.splitlines() if line.startswith("| [#433]"))
            (root/"docs/ROADMAP.md").write_text(t.replace("\n## Завершённые этапы", "\n"+old+"\n## Завершённые этапы", 1),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"duplicate"):
                gov.roadmap_rows(root)
    def test_stage_must_not_claim_merged_without_pr(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"docs").mkdir()
            t=(ROOT/"docs/ROADMAP.md").read_text(encoding="utf-8")
            t=t.replace("| [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) | ⬜ Запланировано | — |",
                        "| [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) | 🟡 Реализовано в main | — |")
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
            text=text.replace("**Accepted:** общий v5 **NOT PASS**","**Accepted:** full acceptance PASS")
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
