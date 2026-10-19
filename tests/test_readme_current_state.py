"""Проверки текущей карты README: исторические snapshots живут вне актуального вступления."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def readme_contract_errors(readme: str, decisions: dict) -> list[str]:
    errors = []
    if "## Roadmap: текущие статусы и архив" not in readme:
        return ["README: нет раздела Roadmap"]
    intro, rest = readme.split("## Roadmap: текущие статусы и архив", 1)
    tariff = rest.split("## Тарифная модель #705", 1)
    if len(tariff) != 2:
        return ["README: отсутствует раздел тарифной модели #705"]
    tariff_text = tariff[1].split("\n## ", 1)[0]
    if len(re.findall(r"(?m)^\\*\\*Published:\\*\\*", intro)) != 1:
        errors.append("README: требуется единый текущий Published")
    if not all(f"**{s}:**" in intro for s in ("Published", "Deployed", "Accepted")):
        errors.append("README: независимые Published/Deployed/Accepted обязательны")
    if re.search(r"(?mi)^\\*\\*(?:Опубликованный|Исходный план|Исторический implementation|Acceptance checkpoint|Published \`v)", intro):
        errors.append("README: историческая release-хронология во вступлении")
    if re.search(r"(?i)(?:ещ[её] не Published|при[её]мка ожидается|targeted acceptance #705.{0,15}PENDING)", intro):
        errors.append("README: устаревший статус во вступлении")
    decisions_by_issue = {entry["issue"]: entry["decision"] for entry in decisions["decisions"]}
    if decisions_by_issue.get(705) == "completed":
        if "CLOSED/completed" not in tariff_text or "operator-reported scoped acceptance" not in tariff_text:
            errors.append("README: #705 должен отражать completed и provenance")
        if re.search(r"(?i)(?:при[её]мка ожидается|#705/B5.{0,30}BLOCKED|#705.{0,40}PENDING)", tariff_text):
            errors.append("README: #705 имеет устаревший acceptance")
    for text in ("G-11", "PARTIAL/NO-GO", "public rollout", "BLOCKED"):
        if text not in intro:
            errors.append("README: не отражены границы общего v5 acceptance: " + text)
    for link in ("docs/ROADMAP.md", "CHANGELOG.md", "docs/RELEASES.md",
                 "docs/ADMIN_SETUP.md", "docs/SQLITE_MIGRATIONS.md", "docs/UI_STYLE.md"):
        if link not in readme:
            errors.append("README: отсутствует каноническая ссылка " + link)
    return errors


class ReadmeCurrentStateTests(unittest.TestCase):
    def setUp(self):
        self.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.decisions = json.loads((ROOT / "docs/roadmap/issue-closure-decisions.json").read_text(encoding="utf-8"))

    def test_current_readme(self):
        self.assertEqual(readme_contract_errors(self.readme, self.decisions), [])

    def test_stale_acceptance_detected(self):
        mutated = self.readme.replace("CLOSED/completed", "приёмка ожидается", 1)
        self.assertTrue(readme_contract_errors(mutated, self.decisions))

    def test_stale_release_history_detected(self):
        mutated = self.readme.replace("## Roadmap:", "**Опубликованный rc.16:** targeted acceptance #705 — PENDING.\n\n## Roadmap:", 1)
        self.assertTrue(any("хронология" in e or "устаревший" in e for e in readme_contract_errors(mutated, self.decisions)))

    def test_missing_current_status_detected(self):
        mutated = self.readme.replace("**Deployed:**", "**Deploy:**", 1)
        self.assertTrue(any("Deployed" in e for e in readme_contract_errors(mutated, self.decisions)))


if __name__ == "__main__":
    unittest.main()
