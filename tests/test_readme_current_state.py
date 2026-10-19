"""Status claims in current README are a projection of the canonical Issue register.

The table is an explicit, bounded current-state surface; historical prose and
audits are not parsed as active status assertions.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECTION = "## Текущие Issue-статусы (сверяются с Roadmap и GitHub)"
LINK = re.compile(
    r"^\| \[#(\d+)\]\(https://github\.com/cLIcHE-QA/3xui-telegram-bot/issues/\1\)"
    r" \| \`([a-z_]+)\` \| .+ \|$"
)
ACTIVE = re.compile(
    r"^\| \[#(\d+)\]\(https://github\.com/cLIcHE-QA/3xui-telegram-bot/issues/\1\) \|"
)


def status_errors(readme: str, roadmap: str, manifest: dict) -> list[str]:
    errors: list[str] = []
    if readme.count(SECTION) != 1:
        return ["README: missing or duplicate current Issue status section"]
    section = readme.split(SECTION, 1)[1].split("\n## ", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("| [#")]
    active_block = roadmap.split("## Активный Issue-реестр (machine-checked)", 1)
    if len(active_block) != 2:
        return ["Roadmap: missing active Issue register"]
    active_block = active_block[1].split("\n## ", 1)[0]
    open_ids = {int(x.group(1)) for line in active_block.splitlines()
                if (x := ACTIVE.match(line))}
    decisions = {}
    for item in manifest.get("decisions", []):
        number = item.get("issue")
        if number in decisions:
            errors.append(f"Issue #{number}: duplicate closure decision")
        decisions[number] = item.get("decision")
    seen = set()
    for line in rows:
        match = LINK.fullmatch(line)
        if not match:
            errors.append("README: unparseable or ambiguous current Issue status row")
            continue
        number, stated = int(match.group(1)), match.group(2)
        if number in seen:
            errors.append(f"Issue #{number}: duplicate current status assertion")
        seen.add(number)
        if stated not in {"open", "completed"}:
            errors.append(f"Issue #{number}: unsupported current status {stated}")
        if number in open_ids:
            if stated != "open":
                errors.append(f"Issue #{number}: README claims {stated}, Roadmap is open")
            if decisions.get(number) == "completed":
                errors.append(f"Issue #{number}: completed decision contradicts open Roadmap")
        else:
            if stated != "completed":
                errors.append(f"Issue #{number}: README claims {stated}, not in open Roadmap")
            if decisions.get(number) != "completed":
                errors.append(f"Issue #{number}: missing completed closure decision")
    if not rows:
        errors.append("README: current Issue status table is empty")
    if not all(f"**{s}:**" in readme.split(SECTION, 1)[0]
               for s in ("Published", "Deployed", "Accepted")):
        errors.append("README: Published/Deployed/Accepted must be distinct")
    if "PARTIAL/NO-GO" not in readme.split(SECTION, 1)[0]:
        errors.append("README: full v5 acceptance boundary lost")
    return errors


class ReadmeCurrentStateTests(unittest.TestCase):
    def setUp(self):
        self.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.roadmap = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
        self.decisions = json.loads(
            (ROOT / "docs/roadmap/issue-closure-decisions.json").read_text(encoding="utf-8")
        )

    def check(self, readme=None, roadmap=None, decisions=None):
        return status_errors(
            self.readme if readme is None else readme,
            self.roadmap if roadmap is None else roadmap,
            self.decisions if decisions is None else decisions,
        )

    def test_current_document(self):
        self.assertEqual(self.check(), [])

    def test_all_declared_rows_are_checked_not_just_one_issue(self):
        rows = LINK.findall(self.readme.split(SECTION, 1)[1].split("\n## ", 1)[0])
        self.assertGreaterEqual(len(rows), 3)
        for number, status in rows:
            opposite = "completed" if status == "open" else "open"
            modified = self.readme.replace(
                f"/issues/{number}) | \`{status}\` |",
                f"/issues/{number}) | \`{opposite}\` |", 1,
            )
            with self.subTest(issue=number):
                self.assertTrue(any(f"Issue #{number}" in e for e in self.check(readme=modified)))

    def test_missing_closure_decision_fails_closed(self):
        closed = next(int(n) for n, s in LINK.findall(self.readme) if s == "completed")
        changed = dict(self.decisions)
        changed["decisions"] = [x for x in self.decisions["decisions"] if x["issue"] != closed]
        self.assertIn(f"Issue #{closed}: missing completed closure decision",
                      self.check(decisions=changed))

    def test_unknown_and_duplicate_rows_fail(self):
        row = next(line for line in self.readme.splitlines() if LINK.fullmatch(line))
        unknown = row.replace("| \`completed\` |", "| \`unknown\` |").replace(
            "| \`open\` |", "| \`unknown\` |"
        )
        self.assertTrue(self.check(readme=self.readme.replace(row, unknown, 1)))
        self.assertTrue(any("duplicate" in e for e in
                            self.check(readme=self.readme.replace(row, row + "\n" + row))))

    def test_historical_prose_not_parsed_as_current_status(self):
        historical = "\n## Историческая запись\n\n2026-10-10: #705 OPEN / PENDING.\n"
        self.assertEqual(self.check(readme=self.readme + historical), [])

    def test_missing_current_fields_and_section_fail(self):
        self.assertTrue(self.check(readme=self.readme.replace("**Deployed:**", "**Deploy:**", 1)))
        self.assertTrue(self.check(readme=self.readme.replace(SECTION, "## Предыдущие статусы", 1)))


if __name__ == "__main__":
    unittest.main()
