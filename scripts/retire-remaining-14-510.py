#!/usr/bin/env python3
"""#510: one-shot SHA-leased deletion of exactly fourteen revalidated merged docs refs.

Never retry a DELETE operation. Bounded read-only post-delete checks tolerate GitHub REST lag.
No bot/production operations; unexpected state halts all subsequent deletions.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = "cLIcHE-QA/3xui-telegram-bot"
BASE = "57ac6f228cd59418a6f50534ca2754ee6010cd2e"
MANIFEST = Path("docs/audits/branch-cleanup-remaining-14-manifest-2026-10-12.json")
WORKFLOW = ".github/workflows/retire-remaining-14-510.yml"
SELF = "scripts/retire-remaining-14-510.py"
EXPECTED = {
    "docs/post-public-roadmap": ("99a2ba7f1648c1364311bff71632454eb0c11967", 286),
    "docs/live-docs-post-public-sync": ("f66d97549d8a53b37124b9de19e2dbc800750439", 287),
    "docs/close-post-public-governance": ("506f05085c2846f9a62063afdf2a5dc32b918f74", 288),
    "docs/v5-roadmap-after-checkout": ("ff7159520dba4ac402d5b60a25c0f422e6b3d8e2", 303),
    "docs/v5-production-acceptance": ("beac2ee46a83074ca9e91c35dde0392d32815159", 309),
    "docs/v5-rc2-acceptance-progress": ("fdac282b541c426563b1bf8d5a04df696889b58d", 315),
    "docs/v5-stars-orders-admin-roadmap": ("75150b60329b8d870b046e32281849f3deb0561f", 316),
    "docs/v5-stars-paid-invoice-ux": ("ec41ac6cab399a81a182a0828c78112091b17c83", 321),
    "docs/v5-rc3-v5-a-007-pass": ("e9bf880b7de2c67ea78202454bd8e1a616a6567f", 322),
    "docs/v5-customer-device-self-service": ("987562015f1c328a34ef4fde550b55a41e790df8", 323),
    "docs/v5-rc4-v5-a-008-targeted-pass": ("f27c651a67032a9143779a29ddb2e59138211964", 327),
    "docs/v5-rc5-production-smoke-evidence": ("2416de3d59e2123df152752c4e638a51f5991aba", 331),
    "docs/v5-rc5-refund-targeted-pass": ("aaaa51bc049c3b99dce296a6d9665963319b37cf", 332),
    "docs/future-external-psp-sbp-checkout-v2": ("0763ebd29ba4b0641753fde367397a6d7805b163", 338),
}


def stop(reason: str) -> None:
    raise SystemExit("STOP/PENDING #510: " + reason)


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    p = subprocess.run(("git", *args), capture_output=True, text=True, check=False)
    if check and p.returncode != 0:
        stop("git " + args[0] + " exit " + str(p.returncode))
    return p


def request(path: str, *, missing_ok: bool = False):
    token = os.environ.get("GH_TOKEN")
    if not token:
        stop("missing ephemeral GitHub Actions token")
    q = urllib.request.Request(
        "https://api.github.com/repos/" + REPO + "/" + path,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(q, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        if missing_ok and e.code == 404:
            return None
        stop("REST " + path.split("?")[0] + " HTTP " + str(e.code))
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        stop("REST error " + type(e).__name__)


def paged(path: str) -> list[dict]:
    results: list[dict] = []
    for page in range(1, 30):
        sep = "&" if "?" in path else "?"
        items = request(path + sep + "per_page=100&page=" + str(page))
        if not isinstance(items, list):
            stop("invalid REST pagination shape " + path)
        results.extend(items)
        if len(items) < 100:
            return results
    stop("pagination bound exceeded " + path)


def read_manifest() -> None:
    try:
        m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stop("manifest unreadable")
    required = {
        "issue", "baseline_main_sha", "source_manifest_sha",
        "prior_partial_audit_sha", "created_at", "scope",
        "observed_live_branch_count", "refs",
        "previously_eligible_now_absent", "permanent_blob_mismatch_exclusions"
    }
    if set(m) != required or m["issue"] != 510 or m["baseline_main_sha"] != BASE:
        stop("manifest schema/issue/baseline mismatch")
    if m["source_manifest_sha"] != "32f06e699549410da88f4d8a754ad246d043cf0e":
        stop("prior immutable manifest SHA mismatch")
    if m["prior_partial_audit_sha"] != "ccd0611d08db4434bf485e2c550ffdddf0e05fe0":
        stop("prior 100-ref partial audit SHA mismatch")
    refs = m["refs"]
    if not isinstance(refs, list) or len(refs) != 14 or len(EXPECTED) != 14:
        stop("expected exactly 14 deletion candidates")
    if any(not isinstance(r, dict) or set(r) != {"name", "sha", "pr_number"} for r in refs):
        stop("unexpected manifest item shape")
    if {r["name"]: (r["sha"], r["pr_number"]) for r in refs} != EXPECTED:
        stop("immutable hardcoded manifest differ")
    for name, (sha, pr) in EXPECTED.items():
        if not re.fullmatch(r"docs/[a-zA-Z0-9_.\-/]+", name):
            stop("unsafe ref name")
        if not re.fullmatch(r"[0-9a-f]{40}", sha) or not isinstance(pr, int) or not 1 <= pr <= 400:
            stop("invalid immutable SHA/PR mapping")
    absent = m["previously_eligible_now_absent"]
    excluded = m["permanent_blob_mismatch_exclusions"]
    if not isinstance(absent, list) or len(absent) != 50:
        stop("must account for exactly 50 preexisting missing refs")
    if not isinstance(excluded, list) or len(excluded) != 2:
        stop("must account for exactly 2 blob mismatches")
    if {x.get("name") for x in excluded} != {
        "docs/russian-documentation", "docs/v4.10-host-control-contract"
    }:
        stop("permanent exclusions changed")
    allnames = [r["name"] for r in refs] + [r["name"] for r in absent] + [r["name"] for r in excluded]
    if len(allnames) != 66 or len(set(allnames)) != 66:
        stop("duplicate/overlapping names between 14, 50 and 2")
    if any(x.get("name") in EXPECTED for x in absent + excluded):
        stop("unexpected target present in exclusions")


def local_dependency_hits() -> set[str]:
    """Scan tracked source once, excluding historical audit/explicit evidence."""
    excluded = {str(MANIFEST), WORKFLOW, SELF, "docs/ROADMAP.md"}
    refs: set[str] = set()
    for path in git("ls-files", "-z").stdout.split("\0"):
        if not path or path in excluded or path.startswith("docs/audits/"):
            continue
        p = Path(path)
        if not p.is_file():
            continue
        try:
            body = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            stop("tracked source unreadable " + path)
        for name in EXPECTED:
            if name in body:
                refs.add(name)
    return refs


def current_remote_sha(name: str) -> str | None:
    p = git("ls-remote", "--heads", "origin", "refs/heads/" + name)
    lines = [line for line in p.stdout.splitlines() if line.strip()]
    if not lines:
        return None
    if len(lines) != 1:
        stop("ambiguous remote refs " + name)
    sha, tab, ref = lines[0].partition("\t")
    if not tab or ref != "refs/heads/" + name or not re.fullmatch(r"[0-9a-f]{40}", sha):
        stop("remote ref mismatch " + name)
    return sha


def matching_blobs(pr_num: int, merge_sha: str) -> bool:
    pr_files = paged("pulls/" + str(pr_num) + "/files")
    commit_pages = []
    parents = None
    for page in range(1, 30):
        body = request("commits/" + merge_sha + "?per_page=100&page=" + str(page))
        if parents is None:
            parents = body.get("parents", [])
        files = body.get("files", [])
        if not isinstance(files, list):
            stop("invalid commit files")
        commit_pages.extend(files)
        if len(files) < 100:
            break
    else:
        stop("commit file pagination exceeds bound")
    if not isinstance(parents, list) or len(parents) != 1 or not pr_files or not commit_pages:
        return False

    def normalized(rows: list[dict]) -> dict[str, tuple[str, str | None]] | None:
        data: dict[str, tuple[str, str | None]] = {}
        for row in rows:
            file = row.get("filename")
            status = row.get("status")
            blob = row.get("sha")
            if not isinstance(file, str) or not status or file in data:
                return None
            if blob is not None and not re.fullmatch(r"[0-9a-f]{40}", blob):
                return None
            data[file] = (status, blob)
        return data

    first, second = normalized(pr_files), normalized(commit_pages)
    return first is not None and second is not None and first == second


def all_prs() -> list[dict]:
    return paged("pulls?state=all")


def classify(name: str, sha: str, pr_num: int, prs: list[dict], deps: set[str]) -> str:
    if name in deps:
        return "tracked source contains branch-name dependency"
    info = request("branches/" + urllib.parse.quote(name, safe="/"), missing_ok=True)
    if info is None:
        return "branch no longer exists"
    if info.get("protected") is not False or info.get("commit", {}).get("sha") != sha:
        return "protected or exact head SHA drift"
    if current_remote_sha(name) != sha:
        return "remote ref SHA drift"
    matched = [p for p in prs if (p.get("head") or {}).get("ref") == name]
    if len(matched) != 1 or matched[0].get("number") != pr_num:
        return "not exactly one original PR head association"
    if any((p.get("base") or {}).get("ref") == name for p in prs):
        return "a PR uses this branch as base"
    pr = matched[0]
    head, base = pr.get("head") or {}, pr.get("base") or {}
    merge_sha = pr.get("merge_commit_sha")
    if pr.get("state") != "closed" or not pr.get("merged_at") or base.get("ref") != "main":
        return "original PR is not merged into main"
    if head.get("sha") != sha or not isinstance(merge_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", merge_sha):
        return "original PR head or squash SHA mismatch"
    if git("merge-base", "--is-ancestor", merge_sha, "HEAD", check=False).returncode != 0:
        return "squash merge not an ancestor of verified main"
    if not matching_blobs(pr_num, merge_sha):
        return "PR final file/status/blob SHA differ from squash merge"
    return "PASS"


def execute_gate() -> None:
    if os.environ.get("GITHUB_REPOSITORY", "").casefold() != REPO.casefold():
        stop("repository mismatch")
    if os.environ.get("GITHUB_EVENT_NAME") != "workflow_run":
        stop("not an approved workflow_run event")
    if os.environ.get("GITHUB_WORKFLOW_RUN_CONCLUSION") != "success":
        stop("required main Python checks are not successful")
    if os.environ.get("GITHUB_WORKFLOW_RUN_EVENT") != "push":
        stop("not post-merge main push")
    if git("rev-parse", "HEAD^").stdout.strip() != BASE:
        stop("unexpected first-parent main baseline")
    head = git("rev-parse", "HEAD").stdout.strip()
    if os.environ.get("GITHUB_WORKFLOW_RUN_SHA") != head:
        stop("CI provenance and checkout SHA mismatch")
    if request("branches/main")["commit"]["sha"] != head:
        stop("main changed since CI; no ref deletion")


def read_back_deleted_without_replay(name: str, old_sha: str) -> None:
    # GitHub branch API may lag the successful, SHA-leased Git ref update.
    # Retry *only read-only requests*, never git push.
    for delay in (0, 2, 3, 5, 8, 10, 12):
        if delay:
            time.sleep(delay)
        from_git = current_remote_sha(name)
        from_api = request("branches/" + urllib.parse.quote(name, safe="/"), missing_ok=True)
        if from_git is None and from_api is None:
            return
        if from_git is not None and from_git != old_sha:
            stop("branch ref recreated/moved after deletion: " + name)
        if from_api is not None and from_api.get("commit", {}).get("sha") != old_sha:
            stop("branch API points at unexpected SHA after deletion: " + name)
        print("READ-BACK PENDING", name, "API stale or Git ref still visible; read-only wait", flush=True)
    stop("unable to confirm post-delete absence for " + name + "; no retry of ref write")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("check", "execute"))
    args = parser.parse_args()
    read_manifest()
    if args.mode == "execute":
        execute_gate()
    prs = all_prs()
    deps = local_dependency_hits()
    errors: list[tuple[str, str]] = []
    for name, (sha, pr_num) in EXPECTED.items():
        reason = classify(name, sha, pr_num, prs, deps)
        if reason != "PASS":
            errors.append((name, reason))
            print("RETAIN / FAILED PROOF", name, reason, flush=True)
        else:
            print("PROOF PASS", name, sha, "PR#" + str(pr_num), flush=True)
    if errors:
        stop("at least one of the 14 refs failed independent proof; deleted=0")
    print("PROOF SUMMARY eligible=14 retained=0", flush=True)
    if args.mode == "check":
        print("DRY-RUN PASS 14/14; deleted=0", flush=True)
        return

    verified = 0
    for name, (sha, pr_num) in EXPECTED.items():
        if request("branches/main")["commit"]["sha"] != git("rev-parse", "HEAD").stdout.strip():
            stop("main changed during deletion; no subsequent writes")
        if classify(name, sha, pr_num, prs, deps) != "PASS":
            stop("candidate changed during deletion: " + name)
        # Exactly ONE SHA-leased ref-delete attempt for this branch.
        pushed = git(
            "push", "--porcelain", "--force-with-lease=refs/heads/" + name + ":" + sha,
            "origin", ":refs/heads/" + name, check=False
        )
        if pushed.returncode:
            stop("SHA-lease deletion rejected or outcome unknown: " + name + "; do not replay")
        read_back_deleted_without_replay(name, sha)
        verified += 1
        print("DELETED / VERIFIED", name, sha, "PR#" + str(pr_num), flush=True)
    print("BATCH14 RESULT verified_deleted=" + str(verified) + "/14", flush=True)


if __name__ == "__main__":
    main()
