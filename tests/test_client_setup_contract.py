from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ClientSetupContractTests(unittest.TestCase):
    def test_pilot_only_and_acceptance_link(self):
        setup = (ROOT / "docs" / "CLIENT_SETUP.md").read_text(encoding="utf-8")
        self.assertIn("CONTROLLED PILOT ONLY / PUBLIC LAUNCH BLOCKED", setup)
        self.assertIn("BLOCKED до полного PASS", setup)
        self.assertIn("V5_PRODUCTION_ACCEPTANCE.md", setup)
        self.assertIn("CLIENT_PORTAL_ENABLED", setup)
        self.assertIn("CLIENT_PAYMENT_ACCEPTANCE_ENABLED", setup)
        self.assertIn("ALLOWED_TELEGRAM_IDS", setup)
        self.assertIn("rc.7", setup)
        self.assertIn("В `rc.7` этого интерфейса нет", setup)
        self.assertIn("unknown", setup)

    def test_living_docs_and_navigation(self):
        contract = json.loads((ROOT / "docs" / "live-docs.json").read_text(encoding="utf-8"))
        self.assertIn("docs/CLIENT_SETUP.md", contract["living_documents"])
        rule = next(r for r in contract["rules"] if r["id"] == "v5-client-acceptance")
        self.assertIn("docs/CLIENT_SETUP.md", rule["documents"])
        self.assertIn("docs/CLIENT_SETUP.md", (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn("CLIENT_SETUP.md", (ROOT / "docs" / "ADMIN_SETUP.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
