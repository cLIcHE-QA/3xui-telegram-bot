#!/usr/bin/env python3
"""Fail release-prep CI if significant merged PRs lack release notes."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
SUBJECT = re.compile(r"^(feat|fix|security): ")
VERSION = re.compile(r'^APP_VERSION\s*=\s*"([^"]+)"', re.MULTILINE)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip()


def eligible_commits(log: str) -> list[str]:
    found = []
    for line in log.splitlines():
        sha, delim, subject = line.partition(" ")
        if delim and re.fullmatch("[0-9a-f]{40}", sha) and SUBJECT.match(subject):
            found.append(sha)
    return found


def release_notes(markdown: str, version: str) -> str:
    sections = list(re.finditer(r"^##\s+(.+)$", markdown, re.MULTILINE))
    for i, section in enumerate(sections):
        label = section.group(1)
        if label == f"v{version}" or label.startswith(f"v{version} "):
            end = sections[i + 1].start() if i + 1 < len(sections) else len(markdown)
            return markdown[section.end():end]
    return ""


def missing_prs(numbers: list[int], notes: str, body: str) -> list[int]:
    missing = []
    for number in sorted(set(numbers)):
        noted = re.search(rf"(?<!\d)(?:PR\s*)?#\s*{number}(?!\d)", notes)
        excluded = re.search(
            rf"(?im)^Release scope exclusion:\s*PR\s*#{number}\s*[—-]\s*\S.+$",
            body,
        )
        if not noted and not excluded:
            missing.append(number)
    return missing


def associated_prs(commit_sha: str, repo: str, token: str) -> list[int]:
    url = f"https://api.github.com/repos/{repo}/commits/{commit_sha}/pulls?per_page=100"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "release-scope-gate",
    }
    with urlopen(Request(url, headers=headers), timeout=15) as reply:
        return [int(pr["number"]) for pr in json.load(reply) if pr.get("merged_at")]


def main() -> int:
    if not os.getenv("RELEASE_SCOPE_PR_TITLE", "").startswith("release: "):
        print("Release scope: N/A (not a release-prep PR).")
        return 0
    base = os.environ["RELEASE_SCOPE_BASE_SHA"]
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    version_source = (ROOT / "version.py").read_text(encoding="utf-8")
    match = VERSION.search(version_source)
    if not match:
        print("Release scope: missing APP_VERSION", file=sys.stderr)
        return 1
    tags = git("tag", "--merged", base, "--sort=-version:refname").splitlines()
    previous = next(
        (t for t in tags if re.fullmatch(r"v\d+\.\d+\.\d+(?:-rc\.\d+)?", t)),
        "",
    )
    if not previous:
        print("Release scope: previous release tag missing", file=sys.stderr)
        return 1
    shas = eligible_commits(
        git("log", "--first-parent", "--format=%H %s", f"{previous}..{base}")
    )
    numbers = set()
    try:
        for sha in shas:
            prs = associated_prs(sha, repo, token)
            if not prs:
                raise ValueError(f"Missing PR association for {sha}")
            numbers.update(prs)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        print(f"Release scope: GitHub API lookup failed: {exc}", file=sys.stderr)
        return 1
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    notes = release_notes(changelog, match.group(1))
    if not notes:
        print(f"Release scope: missing v{match.group(1)} section", file=sys.stderr)
        return 1
    missing = missing_prs(sorted(numbers), notes, os.getenv("RELEASE_SCOPE_PR_BODY", ""))
    if missing:
        print(f"Release scope: missing PRs: {missing}", file=sys.stderr)
        return 1
    print(f"Release scope: PASS, {len(numbers)} PRs covered since {previous}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
