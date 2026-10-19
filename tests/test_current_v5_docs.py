"""Living-docs current v5 acceptance and formatting regressions, independent of RC number."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY = re.compile(r"https://github[.]com/cLIcHE-QA/3xui-telegram-bot/blob/[a-f0-9]{40}/docs/V5_PRODUCTION_ACCEPTANCE[.]md")

def errors(acceptance, contract):
    result = []
    marker = "## 0. Зафиксировать baseline"
    if acceptance.count(marker) != 1:
        return ["missing or duplicate baseline"]
    front = acceptance.split(marker, 1)[0]
    current = front.split("## Исторические operator-reported checkpoints", 1)[0]
    if "## Исторические operator-reported checkpoints" not in front:
        result.append("missing separated history section")
    if "Roadmap](ROADMAP.md)" not in current or "PARTIAL/NO-GO" not in current or "BLOCKED" not in current:
        result.append("missing live source and rollout gate")
    if not HISTORY.search(front):
        result.append("missing immutable historical evidence")
    if re.search(r"(?im)\b(?:rc[.]\d+(?:[.]\d+)?\s+(?:deployed|published)|#\d+\s+OPEN)\b", current):
        result.append("historical checkpoint in live status")
    for section in ("## 1. V5-A-001", "## 2. V5-A-002", "## 3. V5-A-003", "## 5. Rollback test", "## 6. Финальная reconciliation"):
        if section not in acceptance:
            result.append("missing acceptance procedure "+section)
    if "\\n\\n" in contract:
        result.append("escaped paragraph breaks in contract")
    if "Для #659 read-only сопоставление Node inbound tagsДля #659" in contract:
        result.append("duplicated text in contract")
    if "v3.10.2" not in contract or "fail-closed" not in contract:
        result.append("3x-ui compatibility boundary missing")
    return result

class CurrentV5DocsTests(unittest.TestCase):
    def setUp(self):
        self.acceptance=(ROOT/"docs/V5_PRODUCTION_ACCEPTANCE.md").read_text(encoding="utf-8")
        self.contract=(ROOT/"docs/3XUI_OPENAPI_CONTRACT.md").read_text(encoding="utf-8")
    def test_current_docs(self):
        self.assertEqual(errors(self.acceptance,self.contract),[])
    def test_historical_status_in_current_header_rejected(self):
        marker="## Исторические operator-reported checkpoints"
        self.assertEqual(self.acceptance.count(marker),1)
        corrupted=self.acceptance.replace(marker,"#705 OPEN\nrc.16.2 deployed\n\n"+marker,1)
        self.assertTrue(errors(corrupted,self.contract))
    def test_missing_source_and_rollout_gate_rejected(self):
        for text in ("Roadmap](ROADMAP.md)","PARTIAL/NO-GO"):
            with self.subTest(text=text):
                self.assertIn(text,self.acceptance)
                self.assertTrue(errors(self.acceptance.replace(text,"INVALID",1),self.contract))
    def test_malformed_3xui_paragraphs_rejected(self):
        for bad in ("\\n\\n","Для #659 read-only сопоставление Node inbound tagsДля #659"):
            with self.subTest(bad=bad):
                self.assertTrue(errors(self.acceptance,self.contract+"\n"+bad))
    def test_missing_acceptance_section_rejected(self):
        self.assertTrue(errors(self.acceptance.replace("## 1. V5-A-001","## removed",1),self.contract))

if __name__=="__main__":
    unittest.main()
