#!/usr/bin/env python3
"""Second one-shot, fail-closed historical Git ref retirement for Issue #510.

This tool only accepts the three immutable refs in the accompanying manifest.
A PR workflow runs --check without writes; --execute is confined to a unique
post-merge main CI and uses git push --force-with-lease for every deletion.
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
BASE = "17ca2a1812941b72d57e2883ea45cf283e4b4099"
MANIFEST = Path("docs/audits/branch-cleanup-batch-20-2026-10-12.json")
WORKFLOW = ".github/workflows/branch-cleanup-batch-510.yml"
EXPECTED = {
    "chore/pre-v5-repo-hygiene": "6f61f092d67376093335094cd85980fe7f0342e9",
    "docs/a007-fully-remediated": "3514200d536562e8ee237a418b46c585ef6caf79",
    "docs/qa352-telegram-4of4-confirmed-20261011": "aee2df99e878ac705bb953818fe40b3040e9641a",
    "docs/qa352-tls-restored-20261011": "779fcc03009dfdadc6c77a11ef20616569b6f7c4",
    "docs/reschedule-v5-expiry-smoke-oct10": "0b44ac1c7dd4b53f69092ee8c5a38c7c0c4e504e",
    "docs/v4-audit-closure": "e4633406b0cfffe5f8805e816a21728274d650e0",
    "docs/v4-audit-completion-gates": "e4633406b0cfffe5f8805e816a21728274d650e0",
    "docs/v4-audit-finalization": "e4633406b0cfffe5f8805e816a21728274d650e0",
    "docs/v4-audit-findings": "e4633406b0cfffe5f8805e816a21728274d650e0",
    "docs/v4-audit-follow-up": "e4633406b0cfffe5f8805e816a21728274d650e0",
    "docs/v4-audit-followups": "e4633406b0cfffe5f8805e816a21728274d650e0",
    "docs/v4-safe-bot-self-update": "bccb74cb5b9bf6630775defa620dd1e1ba2ca4e2",
    "docs/v5-a002-two-offline-regressions-20261011": "d07ee9b762cddce68cd785a120592dd442d9ac93",
    "docs/v5-commerce-offline-suite-20261010": "04c951caa5f1b5e7cdd5247b07eeebc536b8af98",
    "docs/v5-scheduled-backup-deepcheck-20261010": "b4e7938b7d7c913661b29917ff88492c26d228f3",
    "docs/v5-stars-refund-unknown-no-retry-rc7-20261011": "d07ee9b762cddce68cd785a120592dd442d9ac93",
    "feature/v4.11.1-node-onboarding": "c3bccf7edfcf0db2ea7513f90483b72111b0b7b5",
    "fix/roadmap-gate-v4191": "b8df3aaa828360fca0385b47cd054f971b2dc829",
    "fix/v4.20.2-admin-navigation": "7f0f20e27b7394ea91780380b8fecbdb24750f1a",
    "security/private-admin-chat": "d4178af779e344f757ee4bed27cc43c675c32794",
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
    excluded = {str(MANIFEST), str(WORKFLOW), "scripts/branch-cleanup-batch-510.py", "docs/ROADMAP.md"}
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
    if os.environ.get("GITHUB_EVENT_NAME") != "workflow_run":
        stop("not a trusted successful post-main-CI event")
    if os.environ.get("GITHUB_WORKFLOW_RUN_CONCLUSION") != "success":
        stop("main required CI did not succeed")
    if os.environ.get("GITHUB_WORKFLOW_RUN_EVENT") != "push":
        stop("triggered by PR instead of verified main push")
    if git("rev-parse", "HEAD^").stdout.strip() != BASE:
        stop("first-parent baseline does not match unique approved batch")
    head = git("rev-parse", "HEAD").stdout.strip()
    if os.environ.get("GITHUB_WORKFLOW_RUN_SHA") != head:
        stop("checked-out commit differs from successful Python checks SHA")
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
        print("BATCH20 DRY-RUN PASS; no refs deleted")
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

    print("BATCH20 DELETION: 20/20 confirmed, #510 still requires Roadmap/Issue checkpoint")


if __name__ == "__main__":
    main()
