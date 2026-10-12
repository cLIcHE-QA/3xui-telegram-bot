#!/usr/bin/env python3
"""#510: one-shot SHA-leased deletion of exactly fifty revalidated merged docs refs.

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
BASE = "635453d7694cd73192b363106f7c745f999b4e96"
MANIFEST = Path("docs/audits/branch-cleanup-next-50-dry-run-2026-10-12.json")
WORKFLOW = ".github/workflows/retire-verified-50-510.yml"
SELF = "scripts/retire-verified-50-510.py"
EXPECTED = {
    "docs/v5-rc5-reconciliation-and-rc6-status": ("fa0ef4abf09003540fa8581eaed1585972f19136", 340),
    "docs/v5-admin-settings-review": ("2de080e12ef1ef44994cde58a7763a0a73d5b752", 344),
    "docs/v5-rc6-ownership-canary": ("7210caf46e13ac3b31a7029c8af145ab8f37bbb6", 346),
    "docs/v5-rc6-post-canary-fix-backlog": ("eab829444ae030a009e923ce4794c7d6383fc387", 358),
    "docs/rc7-backup-acceptance-evidence": ("17c933336fc28d17e06d5119d5649c343372d804", 360),
    "docs/cloudflare-warp-runbook-357": ("7a18cd74da982dc48834fe9cf32d8dc722978e2b", 366),
    "docs/roadmap-release-acceptance-l10n-audit": ("8976fe856d9ef4083d4f72c1c51402a6112b01f9", 369),
    "docs/roadmap-acceptance-ledger": ("fb4b10986433580b34fdfeb174aa93deddd5807b", 370),
    "docs/reconcile-current-living-docs": ("f7ddeeaf793bd1b5314ec3092279d450f0fe8435", 372),
    "docs/security-v5-rc-limited-support": ("a0a4243214c3fe9de4cf0e58a1c382602e3170f8", 374),
    "docs/client-portal-controlled-pilot-setup": ("3b1d562f62621ada3eb592b9f350fc74acaaaefb", 375),
    "docs/v5-trial-expiry-20261010": ("eab797147576d62a31da2125c63e0529c936fb52", 376),
    "docs/docker-hub-status-diagnostics": ("4125816c46b2b8c49cb4e741eec58771d3d05e87", 377),
    "docs/v5-order3-provider-reconciliation-20261010": ("eac3521727abe304806397238812165d902af365", 379),
    "docs/v5-paid-customer-ui-20261010": ("600a838c105062fd43766fea5a70b9ff174f9604", 380),
    "docs/v5-isolated-ownership-smoke-20261010": ("cc6807dc0a51dadd821b65c1f470e6edf0b2f152", 381),
    "docs/v5-tempdb-handler-ownership-20261010": ("00b491a1810573a8437e2d5538d37f10f901e7ec", 382),
    "docs/v5-offline-callback-rbac-smoke-20261010": ("c6b5d906068988086167f28f281dbdc56073fa72", 383),
    "docs/v5-dispatcher-offline-smoke-20261010": ("d0f1e21386cb6d6b51fd11a0950393a7e60d1e08", 384),
    "docs/v5-quota-reset-no-replay-offline-20261010": ("b22472cee81a17586edd0ea445582e82027370b0", 385),
    "docs/v5-commerce-offline-regression-20261010": ("d0a7a5bc6ae2c1dfda05ba4236ca680582ad2303", 386),
    "docs/v5-stars-isolated-regression-20261010": ("0b6259cba53c3a8ae7f92cc111cb6f91ac52b8cd", 387),
    "docs/v5-stars-kill-switch-offline-20261010": ("6297f525b281f01aea5db610b8acfdd0c808c34d", 388),
    "docs/v5-provider-outage-recovery-20261010": ("04a9e4264ffb228c29870c32e96db7393365c9ff", 389),
    "docs/v5-scheduled-backup-job-pass-20261010": ("d0651ba60ea0aa366db3ae4c73310cded0ebfb77", 390),
    "docs/v5-scheduled-archive-deep-check-20261010": ("deacc86ef4b85be0a6b49aad33fcf4039c8cc5f1", 391),
    "docs/v5-offsite-97-independent-linkage-20261010": ("20a356f80312cd52dd58db1fff85d74acdefbbc9", 392),
    "docs/v5-isolated-restore-preflight-20261010": ("f762c0016e4a24d5af440d4bfed265ff5a348df5", 393),
    "docs/v5-recovery-97-archive-linkage-20261010": ("040be4c835e9da32a8a8e906f871398b5d544673", 394),
    "docs/v5-rc7-recovery-component-startup-20261010": ("cdb76a200939f101bf8d9d7c13254c11263c1f1d", 395),
    "docs/recovery-drill-artifact-cleanup-20261010": ("6766cf68bc9790b4b3f93b6c477090226ecd1db4", 396),
    "docs/v5-rc7-isolated-container-process-pass-20261010": ("9fad528f68acf1a35cfdfc195645e3f3d689b9cf", 397),
    "docs/v5-master-xui-isolation-preflight-20261010": ("24b9f674a1139e74cadf67a39823c821f546865f", 398),
    "docs/correct-rc7-dr-host-identity-20261010": ("f3f53db4a175d71e2b10d45ee453261f322d4232", 399),
    "docs/record-master-cleanup-and-dr-waiver-20261010": ("b4da705df678f84ee76318ad934f6d7df8e26e49", 400),
    "docs/roadmap-current-rc7-acceptance-20261010": ("9c97d1e365b218f6bef5918d5147af8bbe904df4", 401),
    "docs/record-real-telegram-ab-canary-20261010": ("f51c24e8e75aa7eb4448b4c964e7c4d97be44f8c", 402),
    "docs/v5-rc7-smoke-current-main-20261010": ("e1b639f58b152b4513003f68f445ce47a4e827a6", 404),
    "docs/close-334-stars-summary-20261010": ("bc5a17e71f29bb2961a061e320547534deb6c6ad", 405),
    "docs/close-333-refunded-stars-20261010": ("fd3b8453b30f244f40156c1565e917c46993110f", 406),
    "docs/stars-invoice-ui-rc7-20261010": ("bfd5262208744eb21ef6e538039ad76315279c7f", 407),
    "docs/accept-backup-fixes-348-349-20261010": ("ea3921f6896e91c836dd004c744ace358a8978ba", 408),
    "docs/stars-sqlite-ledger-reconciliation-20261010": ("93bb065a12c438a031a33e82b6d8c8928d3eeb86", 409),
    "docs/v5-client-subscription-refresh-smoke-20261010": ("299ef84c95634af0aeda4af62389f94e257622c9", 410),
    "docs/v5-nonpilot-telegram-auth-denial-20261010": ("d270e74f818c973988de3ad40f88bf82ce0b547a", 411),
    "docs/v5-nonpilot-subscription-command-denied-20261010": ("afb07907cc17080ff0a8397d70dfd998a7f9b2e8", 412),
    "docs/v5-telegram-burst-transport-waiver-20261010": ("09191322e02e3ce173c704406312c6c577970aa8", 413),
    "docs/v5-a002-refund-unknown-and-quota-success-recovery-20261011": ("4c3a450606132571ddd2b07e0c67d9e421aa3c4e", 414),
    "docs/v5-a002-cross-process-recovery-20261011": ("180fa527546f75aad2f0ebd38deabca3a94544e2", 415),
    "docs/rc8-production-smoke-evidence": ("d0dc7df9540ab9d3ee61a70be08903c1881ccb42", 419),
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
    if git("hash-object", str(MANIFEST)).stdout.strip() != "3022d911be6a4d9c90dad04a2a0b869d0836f275":
        stop("immutable original 50-ref manifest blob mismatch")
    if m.get("issue") != 510 or m.get("baseline_main_sha") != "9fff3180a87a95d965aa155950079f910a49349e":
        stop("manifest issue/original SHA mismatch")
    if m.get("action") != "PREPARE_ONLY_NO_DELETION" or m.get("candidate_count") != 50:
        stop("manifest schema/count is not the approved preflight snapshot")
    refs = m.get("candidates")
    if not isinstance(refs, list) or len(refs) != 50 or len(EXPECTED) != 50:
        stop("expected exactly 50 historical ref candidates")
    if any(not isinstance(x, dict) or set(x) != {
        "branch", "tip_sha", "merged_pr", "squash_sha", "classification"} for x in refs):
        stop("candidate fields modified")
    if {x["branch"]: (x["tip_sha"], x["merged_pr"]) for x in refs} != EXPECTED:
        stop("hardcoded exact SHA/PR allowlist differs from immutable manifest")
    for row in refs:
        if row["classification"] != "DELETE_CANDIDATE_REQUIRES_FRESH_PREFLIGHT":
            stop("unexpected candidate classification")
        if not re.fullmatch(r"[0-9a-f]{40}", row["squash_sha"]):
            stop("invalid source squash SHA")
    for name, (sha, pr) in EXPECTED.items():
        if not re.fullmatch(r"docs/[a-zA-Z0-9_.\\-/]+", name):
            stop("unsafe historical branch name")
        if not re.fullmatch(r"[0-9a-f]{40}", sha) or not isinstance(pr,int) or not 1 <= pr <= 534:
            stop("invalid exact tip SHA/PR")
    if any(n in EXPECTED for n in (
        "docs/russian-documentation", "docs/v4.10-host-control-contract", "main")):
        stop("known protected or mismatch exclusion in target list")
    if len({x["branch"] for x in refs}) != 50:
        stop("duplicate branch name")


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
        stop("at least one of the 50 refs failed independent proof; deleted=0")
    print("PROOF SUMMARY eligible=50 retained=0", flush=True)
    if args.mode == "check":
        print("DRY-RUN PASS 50/50; deleted=0", flush=True)
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
    print("BATCH50 RESULT verified_deleted=" + str(verified) + "/50", flush=True)


if __name__ == "__main__":
    main()
