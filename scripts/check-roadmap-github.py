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
RELEASE_TAG = re.compile(r"\bv\d+\.\d+\.\d+(?:-rc\.\d+(?:\.\d+)?)?\b")
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
    section = roadmap.split("## Активный Issue-реестр (machine-checked)", 1)
    if len(section) != 2:
        raise Drift("cannot identify canonical active Issue register")
    section = section[1].split("\n## ", 1)[0]
    states: dict[int, str] = {}
    for line in section.splitlines():
        match = re.match(r"^\|\s*\[#(\d+)\]\(https://github\.com/cLIcHE-QA/3xui-telegram-bot/issues/\1\)\s*\|", line)
        if not match:
            continue
        number = int(match.group(1))
        if number in states:
            raise Drift(f"duplicate active Issue #{number}")
        states[number] = "open"
    if not states:
        raise Drift("empty or missing canonical active Issue register")
    return referenced, states


# PRs указаны только в каноническом активном реестре; исторические
# ссылки в сводке не дают оснований менять lifecycle state.
PR_LINK = re.compile(r"https://github\.com/cLIcHE-QA/3xui-telegram-bot/pull/(\d+)")
PLANNED = "⬜ Запланировано"
IMPLEMENTED = "🟡 Реализовано в main"


def code_file(path: str) -> bool:
    """Docs-only, audit и test-only PR не подтверждают runtime implementation."""
    if path.startswith(("docs/", "tests/", ".github/")) or path in (
        "README.md", "CHANGELOG.md", "SECURITY.md", "AGENTS.md",
    ):
        return False
    return not path.endswith((".md", ".rst", ".txt"))


def implementation_drift(rows: dict[int, dict[str, str]], repo: str,
                         fetcher=None) -> None:
    """Read-only GitHub PR evidence: merged runtime implementation vs Roadmap.

    Не объявляет Published/Deployed/Accepted и не закрывает Issues.
    Github failures propagate as UNKNOWN, missing/contradictory evidence as FAIL.
    """
    fetcher = fetcher or fetch
    cache: dict[int, bool] = {}
    for number, row in rows.items():
        if row["status"] not in (PLANNED, IMPLEMENTED):
            continue
        refs = [int(x) for x in PR_LINK.findall(row["pr"])]
        if not refs:
            if row["status"] == IMPLEMENTED:
                raise Drift(f"Roadmap Issue #{number} implemented without implementation PR")
            continue
        implemented = False
        for pr_number in sorted(set(refs)):
            if pr_number not in cache:
                pr = fetcher(repo, f"/pulls/{pr_number}")
                if not isinstance(pr, dict):
                    raise Unknown(f"invalid PR #{pr_number} payload")
                if pr.get("merged"):
                    if (pr.get("base", {}).get("ref") != "main"
                            or not pr.get("merge_commit_sha")):
                        raise Drift(f"PR #{pr_number} merged without main/merge SHA evidence")
                    files = fetcher(repo, f"/pulls/{pr_number}/files?per_page=100")
                    if not isinstance(files, list):
                        raise Unknown(f"invalid PR #{pr_number} files payload")
                    if len(files) == 100:
                        raise Unknown(f"PR #{pr_number} files require pagination")
                    cache[pr_number] = any(
                        code_file(str(f.get("filename", ""))) for f in files
                        if isinstance(f, dict)
                    )
                else:
                    cache[pr_number] = False
            implemented |= cache[pr_number]
        if row["status"] == PLANNED and implemented:
            raise Drift(f"Roadmap Issue #{number} is planned, but runtime PR is MERGED in main")
        if row["status"] == IMPLEMENTED and not implemented:
            raise Drift(f"Roadmap Issue #{number} claims implemented without merged runtime PR")


def closure_decisions_ok(rows: dict[int, dict[str, str]], actual: dict[int, str],
                         manifest: dict) -> None:
    """Новые acceptance decisions fail-closed; не определяет PASS за оператора."""
    if manifest.get("schema") != 1 or not isinstance(manifest.get("decisions"), list):
        raise Drift("invalid closure decisions manifest")
    seen: set[int] = set()
    for item in manifest["decisions"]:
        if not isinstance(item, dict):
            raise Drift("invalid closure decision entry")
        number = item.get("issue")
        decision = item.get("decision")
        if not isinstance(number, int) or number <= 0 or number in seen:
            raise Drift("duplicate or invalid closure decision")
        seen.add(number)
        if decision not in ("completed", "keep_open"):
            raise Drift(f"Issue #{number}: missing/invalid closure decision")
        if not all(isinstance(item.get(key), str) and item[key].strip()
                   for key in ("accepted", "evidence", "date", "comment")):
            raise Drift(f"Issue #{number}: missing closure evidence")
        if number not in actual:
            raise Drift(f"Issue #{number}: closure state not fetched")
        if decision == "completed":
            if actual[number] != "closed" or number in rows:
                raise Drift(f"Issue #{number}: accepted/completed but GitHub/active register not closed")
        elif actual[number] != "open" or number not in rows:
            raise Drift(f"Issue #{number}: keep_open decision mismatches GitHub/active register")


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
    implementation_drift(rows, repo)
    decisions_path = root / "docs/roadmap/issue-closure-decisions.json"
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    for item in decisions["decisions"]:
        number = item["issue"]
        if number not in actual:
            payload = fetch(repo, f"/issues/{number}", token)
            if "pull_request" in payload:
                raise Drift(f"#{number} is a PR, not an Issue")
            actual[number] = payload.get("state", "unknown")
    closure_decisions_ok(rows, actual, decisions)
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
