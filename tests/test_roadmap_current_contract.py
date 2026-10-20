"""Универсальные текущие/исторические границы Roadmap, без pinned Issue/RC."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = "## Актуальная сводка проекта"
NEXT = "## Статусы дорожной карты"
PLANS = "## Будущие release-кандидаты"
REGISTRY = "## Реестр открытых задач и будущие релизы"
VERSION = re.compile(r"v(\d+)\.(\d+)\.(\d+)-rc\.(\d+)(?:\.(\d+))?")


def roadmap_current_errors(document: str) -> list[str]:
    errors: list[str] = []
    if document.count(SUMMARY) != 1 or document.count(NEXT) != 1:
        return ["current roadmap sections must be unique"]
    current = document.split(SUMMARY, 1)[1].split(NEXT, 1)[0]
    if len(current) > 4500:
        errors.append("current summary exceeds bounded 4500-character budget")
    if current.count("**Published:**") != 1 or current.count("**Deployed:**") != 1 or current.count("**Accepted:**") != 1:
        errors.append("Published/Deployed/Accepted must be unique in current summary")
    if re.search(r"(?im)^\*\*(?:Published checkpoint|Release-prep checkpoint|Implementation checkpoint|Исторический|Acceptance checkpoint|План v)", current):
        errors.append("historical release checkpoint placed in current summary")
    if re.search(r"\b\d+\s+OPEN Issues\b", current):
        errors.append("ephemeral OPEN issue count placed in current summary")
    if "PARTIAL/NO-GO" not in current or "public rollout BLOCKED" not in current:
        errors.append("full acceptance/public rollout boundary absent")
    if "blob/" not in current or "docs/ROADMAP.md" not in current:
        errors.append("immutable historical source provenance absent")
    if document.count(PLANS) != 1 or document.count(REGISTRY) != 1:
        return errors + ["future release candidate section missing or duplicate"]
    future = document.split(PLANS, 1)[1].split(REGISTRY, 1)[0]
    published_line = next((line for line in current.splitlines() if line.startswith("**Published:**")), "")
    match = VERSION.search(published_line)
    if not match:
        errors.append("published release version missing")
        return errors
    baseline = tuple(int(n or 0) for n in match.groups())
    candidates = []
    for line in future.splitlines():
        if not line.startswith("| **v"):
            continue
        marker = VERSION.search(line)
        if not marker:
            errors.append("invalid planned release candidate version")
            continue
        candidate = tuple(int(n or 0) for n in marker.groups())
        candidates.append(candidate)
        if candidate <= baseline:
            errors.append("planned release candidate is already published or older")
    if not candidates:
        errors.append("future release plan must have candidates")
    if len(candidates) != len(set(candidates)):
        errors.append("duplicate future release candidate")
    return errors


class RoadmapCurrentContractTests(unittest.TestCase):
    def setUp(self):
        self.roadmap = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")

    def test_live_roadmap(self):
        self.assertEqual(roadmap_current_errors(self.roadmap), [])

    def test_stale_history_and_open_count_rejected(self):
        for payload in (
            "**Release-prep checkpoint 2026-10-18:** rc old is not Published.\n\n",
            "**39 OPEN Issues** before release.\n\n",
        ):
            with self.subTest(payload=payload):
                mutated = self.roadmap.replace(NEXT, payload + NEXT, 1)
                self.assertNotEqual(mutated, self.roadmap)
                self.assertTrue(roadmap_current_errors(mutated))

    def test_previous_release_cannot_be_future_candidate(self):
        current = self.roadmap.split(SUMMARY, 1)[1].split(NEXT, 1)[0]
        published = VERSION.search(current.split("**Published:**", 1)[1]).group()
        anchor = "| Целевой RC | Задачи | Зависимости перед включением |"
        self.assertEqual(self.roadmap.count(anchor), 1)
        mutated = self.roadmap.replace(anchor, anchor + "\n| **" + published + "** | fixture | stale |", 1)
        self.assertTrue(any("already published" in x for x in roadmap_current_errors(mutated)))

    def test_missing_provenance_and_duplicate_fields_rejected(self):
        mutated = self.roadmap.replace("blob/", "historical/")
        self.assertTrue(any("provenance" in e for e in roadmap_current_errors(mutated)))
        mutated = self.roadmap.replace("**Deployed:**", "**Deployed:** UNKNOWN **Deployed:**", 1)
        self.assertTrue(any("unique" in e for e in roadmap_current_errors(mutated)))


if __name__ == "__main__":
    unittest.main()
