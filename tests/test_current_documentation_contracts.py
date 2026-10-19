"""Проверки living docs: нормативный контракт и исторический provenance."""
from __future__ import annotations
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = {
    "docs/CLIENT_SETUP.md": ("CONTROLLED PILOT ONLY / PUBLIC LAUNCH BLOCKED", "CLIENT_PAYMENT_ACCEPTANCE_ENABLED", "portal=false", "unknown", "## Действия при проблеме / rollback"),
    "docs/UI_STYLE.md": ("## Навигация", "admin:users", "admin:home", "🟡", "unknown", "## Граница private chat для Admin Control Plane"),
    "docs/SQLITE_MIGRATIONS.md": ("db_migrations.py", "MIGRATIONS", "requires_backup", "PRAGMA quick_check", "DatabaseSchemaTooNewError", "## Rollback"),
}
SNAPSHOT = re.compile(r"https://github[.]com/cLIcHE-QA/3xui-telegram-bot/blob/[0-9a-f]{40}/docs/[A-Z_]+[.]md")


def living_contract_errors(path: str, source: str) -> list[str]:
    errors = []
    if not source.startswith("# ") or "нормативн" not in source.split("\n## ", 1)[0].lower():
        errors.append("missing normative first section")
    if not all(item in source for item in DOCUMENTS[path]):
        errors.append("critical contract lost")
    if "## Историческ" not in source or not SNAPSHOT.search(source):
        errors.append("historical provenance missing")
    if re.search(r"(?m)^## (?:Operator-reported rc[.]|Published rc[.]|Release-prep)", source):
        errors.append("unscoped historical release checkpoint")
    return errors


class CurrentDocumentationContractsTests(unittest.TestCase):
    def test_all_current_documents(self):
        for path in DOCUMENTS:
            with self.subTest(path=path):
                s = (ROOT / path).read_text(encoding="utf-8")
                self.assertEqual(living_contract_errors(path, s), [])

    def test_negative_missing_provenance_and_contract(self):
        for path, critical in DOCUMENTS.items():
            source = (ROOT / path).read_text(encoding="utf-8")
            with self.subTest(path=path):
                mutated = source.replace(critical[0], "", 1)
                self.assertNotEqual(mutated, source)
                self.assertIn("critical contract lost", living_contract_errors(path, mutated))
                mutated = SNAPSHOT.sub("no-longer-immutable", source, count=1)
                self.assertNotEqual(mutated, source)
                self.assertIn("historical provenance missing", living_contract_errors(path, mutated))

    def test_historical_checkpoint_cannot_be_reintroduced(self):
        for path in DOCUMENTS:
            source = (ROOT / path).read_text(encoding="utf-8")
            mutated = source + "\n## Release-prep v0.0.0 — устаревший checkpoint\n"
            self.assertIn("unscoped historical release checkpoint", living_contract_errors(path, mutated))


if __name__ == "__main__":
    unittest.main()
