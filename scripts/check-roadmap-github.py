#!/usr/bin/env python3
"""Read-only reconciliation of every directly referenced Roadmap Issue and published Release.

Network/API failure is UNKNOWN (exit 2), never PASS. No production assertions.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.github.com"
ISSUE_URL = re.compile(
    r"https://github\.com/cLIcHE-QA/3xui-telegram-bot/issues/(\d+)(?:\b|/)", re.I
)
RELEASE_TAG = re.compile(r"\bv\d+\.\d+\.\d+(?:-rc\.\d+)?\b")
class Unknown(RuntimeError):
    pass
class Drift(RuntimeError):
    pass


def fetch(repo: str, suffix: str, token: str = ""):
    request = urllib.request.Request(f"{API}/repos/{repo}{suffix}", headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "roadmap-readonly-reconciliation",
        **({"Authorization": f"Bearer {token}"} if token else {}),
    })
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
            ValueError) as exc:
        raise Unknown(f"GitHub API unavailable/unreadable: {type(exc).__name__}") from exc


def expectations(roadmap: str) -> tuple[set[int], dict[int, str]]:
    """Discover all linked Issues, classify explicit active/completed Roadmap paragraphs."""
    referenced = {int(x) for x in ISSUE_URL.findall(roadmap)}
    if not referenced:
        raise Drift("Roadmap contains no directly linked Issues")
    section = roadmap.split("## Реестр открытых задач и будущие релизы", 1)
    if len(section) != 2:
        raise Drift("cannot identify canonical backlog section")
    section = section[1].split("\n## Завершённые этапы", 1)[0]
    states: dict[int, str] = {}
    for para in re.split(r"\n\s*\n", section):
        content = para.strip()
        if content.startswith(("**⬜ Запланировано", "**⬜ Отложенный")):
            expected = "open"
        elif content.startswith(("**Закрытый", "**✅ Завершено")):
            expected = "closed"
        else:
            continue
        for match in ISSUE_URL.finditer(content):
            number = int(match.group(1))
            if number in states and states[number] != expected:
                raise Drift(f"Issue #{number} has contradictory Roadmap contexts")
            states[number] = expected
    if not states:
        raise Drift("no explicit open/closed issue classifications found")
    return referenced, states


def declared_published(roadmap: str) -> str:
    if "**Published:**" not in roadmap:
        raise Drift("missing explicit Published field")
    after = roadmap.split("**Published:**", 1)[1]
    marker = RELEASE_TAG.search(after[:600])
    if not marker:
        raise Drift("Published field does not contain valid vX.Y.Z[-rc.N] tag")
    return marker.group()


def validate(roadmap: str, actual: dict[int, str], latest_published: str) -> None:
    referenced, expected = expectations(roadmap)
    declared = declared_published(roadmap)
    if declared != latest_published:
        raise Drift(f"latest Published release {latest_published} != Roadmap {declared}")
    missing = referenced.difference(actual)
    if missing:
        raise Drift(f"unverified linked Issue IDs: {sorted(missing)}")
    for number, state in actual.items():
        if number in referenced and state not in ("open", "closed"):
            raise Drift(f"unknown Issue state #{number}: {state}")
    for number, state in expected.items():
        if actual[number] != state:
            raise Drift(f"Roadmap Issue #{number} expected {state}, GitHub {actual[number]}")
    # The checker confirms all directly linked Issues are fetchable, but unclassified
    # Issue references are observations, not invented status assertions.


def audit(repo: str, root: Path = ROOT, token: str = ""):
    roadmap = (root / "docs/ROADMAP.md").read_text(encoding="utf-8")
    referenced, expected = expectations(roadmap)
    actual = {}
    for number in sorted(referenced):
        obj = fetch(repo, f"/issues/{number}", token)
        if "pull_request" in obj:
            raise Drift(f"#{number} is a PR, not an Issue")
        actual[number] = obj.get("state", "unknown")
    releases = fetch(repo, "/releases?per_page=30", token)
    published = [r for r in releases if not r.get("draft") and r.get("published_at")]
    if not published:
        raise Unknown("no published Releases returned")
    tag = max(published, key=lambda r: r["published_at"])["tag_name"]
    validate(roadmap, actual, tag)
    # Every OPEN Issue must exist exactly once in the structured canonical register.
    spec = __import__("importlib.util").util.spec_from_file_location(
        "roadmap_governance", root / "scripts/check-roadmap-governance.py")
    module = __import__("importlib.util").util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = module.roadmap_rows(root)
    open_ids = set()
    page = 1
    while True:
        batch = fetch(repo, f"/issues?state=open&per_page=100&page={page}", token)
        if not isinstance(batch,list):
            raise Unknown("GitHub open Issues pagination response invalid")
        open_ids.update(int(x["number"]) for x in batch if "pull_request" not in x)
        if len(batch) < 100:
            break
        page += 1
        if page > 30:
            raise Unknown("open Issues pagination exceeded safe limit")
    extra = set(rows) - open_ids
    missing = open_ids - set(rows)
    if missing or extra:
        raise Drift(f"active Issue register mismatch: missing={sorted(missing)}, stale={sorted(extra)}")
    for number, row in rows.items():
        if actual.get(number) != "open":
            raise Drift(f"active Roadmap row #{number} is not an open GitHub Issue")
    return tag, actual, expected, len(open_ids)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()
    try:
        tag, issues, classified, active_count = audit(
            args.repository, token=os.getenv("GITHUB_TOKEN", ""))
    except Unknown as exc:
        print(f"Roadmap GitHub reconciliation: UNKNOWN/PENDING — {exc}", file=sys.stderr)
        return 2
    except (Drift, KeyError, TypeError, OSError) as exc:
        print(f"Roadmap GitHub reconciliation: FAIL — {exc}", file=sys.stderr)
        return 1
    print(f"Roadmap GitHub reconciliation: PASS — published={tag}, "
          f"referenced_issues={len(issues)}, status_assertions={len(classified)}, "
          f"active_issues={active_count}; "
          "no production assertion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
