#!/usr/bin/env python3
"""One-shot, fail-closed historical Git ref retirement for Issue #510.

This tool only accepts the three immutable refs in the accompanying manifest.
A PR workflow runs --check without writes; --execute is confined to a single
post-merge main push and uses git push --force-with-lease for every deletion.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = "cLIcHE-QA/3xui-telegram-bot"
BASE = "8684135fa58dd20ceee7fb0725c51bdb31a60d52"
MANIFEST = Path("docs/audits/branch-cleanup-pilot-510-2026-10-12.json")
WORKFLOW = ".github/workflows/branch-cleanup-pilot-510.yml"
EXPECTED = {
    "chore/github-branch-gc-510": "37b1c700c846791b66a893843e1c68063ab92a6a",
    "docs/branch-policy-and-inventory-510-20261012": "37b1c700c846791b66a893843e1c68063ab92a6a",
    "docs/git-branch-lifecycle-policy-510": "37b1c700c846791b66a893843e1c68063ab92a6a",
}


def stop(reason: str) -> None:
    raise SystemExit("STOP/PENDING #510: " + reason)


def git(*args: str, must_succeed: bool = True) -> subprocess.CompletedProcess[str]:
    p = subprocess.run(("git", *args), capture_output=True, text=True, check=False)
    if must_succeed and p.returncode:
        stop("git " + args[0] + " failed (exit " + str(p.returncode) + ")")
    return p


def api(path: str, *, missing_ok: bool = False):
    token = os.environ.get("GH_TOKEN")
    if not token:
        stop("GitHub read token not available")
    request = urllib.request.Request(
        "https://api.github.com/repos/" + REPO + "/" + path,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.load(response)
    except urllib.error.HTTPError as err:
        if missing_ok and err.code == 404:
            return None
        stop("GitHub REST " + path.split("?")[0] + " HTTP " + str(err.code))
    except (urllib.error.URLError, TimeoutError, ValueError) as err:
        stop("GitHub read error: " + type(err).__name__)


def current_remote_sha(name: str) -> str | None:
    p = git("ls-remote", "--heads", "origin", "refs/heads/" + name)
    lines = [line for line in p.stdout.splitlines() if line.strip()]
    if not lines:
        return None
    if len(lines) != 1:
        stop("ambiguous remote branch ref for " + name)
    sha, _, ref = lines[0].partition("\t")
    if ref != "refs/heads/" + name or len(sha) != 40:
        stop("remote ref mismatch for " + name)
    return sha


def branch_info(name: str):
    return api("branches/" + urllib.parse.quote(name, safe="/"), missing_ok=True)


def check_legal_manifest() -> None:
    try:
        content = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        stop("manifest unreadable: " + type(err).__name__)
    if set(content) != {"issue", "baseline_main_sha", "refs", "scope", "created_at"}:
        stop("unexpected manifest fields")
    if content["issue"] != 510 or content["baseline_main_sha"] != BASE:
        stop("manifest issue/main baseline mismatch")
    refs = content["refs"]
    if not isinstance(refs, list) or len(refs) != len(EXPECTED):
        stop("manifest ref count mismatch")
    if any(not isinstance(r, dict) or set(r) != {"name", "sha"} for r in refs):
        stop("manifest entry shape mismatch")
    if {r["name"]: r["sha"] for r in refs} != EXPECTED:
        stop("manifest refs do not match hardcoded approved pilot")
    if any(r["name"] == "main" or r["name"].startswith("v") for r in refs):
        stop("protected/default/tag target forbidden")


def check_operational_references() -> None:
    excluded = {str(MANIFEST), str(WORKFLOW), "scripts/branch-cleanup-pilot-510.py", "docs/ROADMAP.md"}
    files = git("ls-files", "-z").stdout.split("\0")
    for raw in files:
        if not raw or raw in excluded or raw.startswith("docs/audits/"):
            continue
        path = Path(raw)
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            stop("could not inspect tracked dependency file " + raw)
        for branch_name in EXPECTED:
            if branch_name in text:
                stop("possible tracked dependency on " + branch_name + " in " + raw)


def check_branch(name: str, sha: str) -> None:
    if name not in EXPECTED or EXPECTED[name] != sha:
        stop("unapproved name/SHA")
    info = branch_info(name)
    if info is None:
        stop("target branch missing before deletion: " + name)
    if info.get("protected") is not False or info.get("commit", {}).get("sha") != sha:
        stop("GitHub protected or changed branch " + name)
    if current_remote_sha(name) != sha:
        stop("remote tip SHA changed: " + name)
    ancestry = git("merge-base", "--is-ancestor", sha, "HEAD", must_succeed=False)
    if ancestry.returncode != 0:
        stop("branch has commits not proven ancestral to verified main: " + name)
    owner = REPO.split("/", 1)[0]
    q_head = urllib.parse.urlencode({"state": "all", "per_page": 100, "head": owner + ":" + name})
    q_base = urllib.parse.urlencode({"state": "all", "per_page": 100, "base": name})
    if api("pulls?" + q_head) or api("pulls?" + q_base):
        stop("branch is referenced by a pull request: " + name)


def ensure_execute_gate() -> None:
    if os.environ.get("GITHUB_REPOSITORY", "").casefold() != REPO.casefold():
        stop("wrong repository")
    if os.environ.get("GITHUB_EVENT_NAME") != "push" or os.environ.get("GITHUB_REF") != "refs/heads/main":
        stop("not a protected main push")
    if os.environ.get("GITHUB_EVENT_BEFORE") != BASE:
        stop("not the unique approved one-shot push")
    if git("rev-parse", "HEAD^").stdout.strip() != BASE:
        stop("first-parent baseline does not match")
    head = git("rev-parse", "HEAD").stdout.strip()
    if api("branches/main")["commit"]["sha"] != head:
        stop("main moved during preflight")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("check", "execute"))
    args = p.parse_args()
    check_legal_manifest()
    check_operational_references()
    if args.mode == "execute":
        ensure_execute_gate()

    # Preflight ALL refs first, before touching even the first branch.
    for name, sha in EXPECTED.items():
        check_branch(name, sha)
        print("PREFLIGHT PASS", name, sha)
    if args.mode == "check":
        print("PILOT DRY-RUN PASS; no refs deleted")
        return

    for name, sha in EXPECTED.items():
        # Lease is enforced by git receive-pack, not a non-atomic REST DELETE.
        check_branch(name, sha)
        p = git(
            "push", "--porcelain",
            "--force-with-lease=refs/heads/" + name + ":" + sha,
            "origin", ":refs/heads/" + name, must_succeed=False
        )
        if p.returncode:
            stop("SHA-lease deletion rejected for " + name + ", exit " + str(p.returncode))
        if branch_info(name) is not None or current_remote_sha(name) is not None:
            stop("post-delete independent ref read-back not 404 for " + name)
        print("DELETED / VERIFIED", name, sha)

    print("PILOT DELETION: 3/3 confirmed, #510 still requires Roadmap/Issue checkpoint")


if __name__ == "__main__":
    main()
