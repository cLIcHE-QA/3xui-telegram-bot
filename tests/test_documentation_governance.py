from __future__ import annotations
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

sem=load("semantic_docs","scripts/check-documentation-semantics.py")
gh=load("roadmap_gh","scripts/check-roadmap-github.py")

class DocumentationGovernanceTests(unittest.TestCase):
    def test_current_valid_and_original_archive_untouched(self):
        self.assertEqual(sem.current_ok(ROOT),[])
        self.assertEqual(sem.check(ROOT,[]),[])
        self.assertTrue((ROOT/"docs/audits/roadmap-history/source-client-portal-ux.md").is_file())
    def test_new_audit_requires_all_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"docs/audits").mkdir(parents=True)
            p="docs/audits/2026-10-13-new-test.md"
            (root/p).write_text("PASS",encoding="utf-8")
            errors=sem.audit_ok(root,p)
            self.assertIn(f"{p}: missing schema marker",errors)
            self.assertGreater(len(errors),10)
    def test_links_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"docs").mkdir()
            (root/"docs/test.md").write_text("[broken](missing.md)",encoding="utf-8")
            self.assertTrue(sem.links_ok(root,"docs/test.md"))
            (root/"docs/missing.md").write_text("ok",encoding="utf-8")
            self.assertEqual(sem.links_ok(root,"docs/test.md"),[])
    def test_gates_detect_duplicates(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"docs").mkdir()
            text=(ROOT/"docs/ROADMAP.md").read_text(encoding="utf-8")
            text+="\n| G-09 | duplicate | PENDING |\n"
            (root/"docs/ROADMAP.md").write_text(text,encoding="utf-8")
            self.assertIn("missing/duplicate gate G-09",sem.current_ok(root))
    def test_remote_issue_and_release_drift(self):
        text=(ROOT/"docs/ROADMAP.md").read_text(encoding="utf-8")
        states={593:"closed",433:"open",466:"open",596:"open"}
        gh.validate(text,states,"v5.0.0-rc.9")
        with self.assertRaises(gh.Drift):gh.validate(text,{433:"closed"},"v5.0.0-rc.9")
        with self.assertRaises(gh.Drift):gh.validate(text,states,"v9.9.9")
