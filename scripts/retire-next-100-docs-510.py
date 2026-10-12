#!/usr/bin/env python3
"""#510: one-shot SHA-leased cleanup of 100 new merged docs PR-head refs.

Retention is the default on uncertain proof. Read-only retries tolerate API lag;
failed/unknown mutations never cause a second ref-write attempt.
No production operations.
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
BASE = "8d0599db573be7f8237f506217676a9397b02543"
MANIFEST = Path("docs/audits/branch-cleanup-next-100-docs-manifest-2026-10-12.json")
WORKFLOW = ".github/workflows/retire-next-100-docs-510.yml"
SELF = "scripts/retire-next-100-docs-510.py"
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
    "docs/agent-acceptance-issue-checkpoints": ("7160af4b0c3e07010efe6b9b08e563375af1e924", 421),
    "docs/plan-3xui-hosts-rc9": ("54b39deb5a40f44756b5391444f138d989b04d0a", 423),
    "docs/sync-hosts-422-main": ("92dbca1f187c434334315254c6f0a1abfb72fea6", 425),
    "docs/rc9-readiness-checkpoint": ("31426447345c7b9fdd5f14fe6de73a9644b8f13f", 426),
    "docs/read-only-baseline-20261011": ("276df0af3e9f51414246e65501a874112e61fe4b", 427),
    "docs/sync-3xui-contract-governance-428": ("bc069b7e66155458bf24e23251570ef5b0e9d2c0", 429),
    "docs/rc9-release-prep-checkpoint": ("8051360de8adf22738566776d5221fd8faf30f9f", 431),
    "docs/rc9-published-checkpoint": ("ae8651475b391c3f213e5e660fc00b61ba6bdb7b", 432),
    "docs/rc10-refunds-plan": ("2189bb276a85bd9f875f9177a2b5e326baf17f4c", 435),
    "docs/rc10-legal-support-psp-plan": ("cfe78357c4553d11238fe4c4a41779d0092aaad0", 438),
    "docs/platega-payment-link-contract": ("53e3a842678daf401442123caba5af76f4b33f82", 439),
    "docs/rc9-operator-deploy-checkpoint": ("041f9258fb8d0e9cd4f8bf79f8281213671a1c63", 440),
    "docs/rc9-hosts-visibility-checkpoint": ("a6121fdee882e67741b2614130a375d7614ee391", 441),
    "docs/rc9-netherlands-mapping-checkpoint": ("74ae09f683146ceac233d87df7170538b2fc22a6", 442),
    "docs/rc9-host-sources-acceptance": ("bb00c44fc310d8fdaa8829acbfd40a3a484f9db0", 443),
    "docs/rc9-422-closure-sync": ("941a1ce88f4d73fb3c23ab62472267fcb07ce305", 444),
    "docs/rc9-342-portal-off-callback-checkpoint": ("a6f10f501548b8a94d29b2415e320f8a86ec4884", 445),
    "docs/rc9-342-portal-restored-checkpoint": ("4528680e8fdf0ccbe5487510567277df171b2923", 446),
    "docs/rc9-342-readonly-acceptance": ("a2f4913644cd9676ac60699ff3516bda7e18eec7", 447),
    "docs/rc9-342-closed-status": ("110878302e73df79166a37e4cbc09256a65637e8", 448),
    "docs/rc9-352-readonly-preflight": ("4330f75a8ab1f634ef3da974711c912e971e7329", 449),
    "docs/rc9-352-isolated-smoke-result": ("7164e424138d8a579eced577fc31fa39628d07b6", 451),
    "docs/352-qa-runner-merged-sync": ("4a920c75c2999aa8473942965ff8f53cffb9f50e", 453),
    "docs/qa352-preview-pass-20261011": ("f1cedc4815f4477ee80fc0c815c4a2463a6967dc", 455),
    "docs/qa352-enroll-blocked-20261011": ("e97fbab1db03392993792ad60988b5fe63bf1db0", 456),
    "docs/qa352-getme-urlerror-20261011": ("64d4ff09e9e0d5dd895fc1f579a641b03b759a37", 457),
    "docs/qa352-ssl-verification-blocked-20261011": ("66e6efc893b1534de6cfb924dfb77c165d726129", 458),
    "docs/qa352-python-ca-paths-20261011": ("c23a8d2a9aab713cc0ac27029022e2968f676b50", 459),
    "docs/qa352-mac-ca-install-pass-20261011": ("7fbf945e7e835e9ed2636dece02d179243862713", 460),
    "docs/qa352-tls-post-ca-pass-20261011": ("079c37efe7d97651e69b1c5641275108e850cecc", 461),
    "docs/qa352-qa-private-enroll-pass-20261011": ("d36f8a19fa618ba661c559eb4a4bfc5e27b58c78", 462),
    "docs/qa352-first-telegram-delivery-evidence-20261011": ("02dae43803bbe2c51f600fa767bfc073e6ca3699", 463),
    "docs/qa352-telegram-synthetic-visual-4of4-20261011": ("982c2013e54c0a1f84b803a768a959dbd198a84a", 464),
    "docs/qa352-transport-confirmed-4of4-20261011": ("1e0e128dc59fa325a95c4d477c5b597011e35510", 465),
    "docs/qa352-risk-accepted-closure-20261011": ("3879d103409e9e4d7f81b2e02c9c5317d2c4df6c", 467),
    "docs/qa352-closed-followup-open-20261011": ("7d5e34fce161a98c31ac3eaf11182ae637894010", 468),
    "docs/rc9-acceptance-gates-waivers-index-20261011": ("8fab01793ac9e2d84a608424bc82001148c5aa6f", 469),
    "docs/rc11-client-portal-backlog-20261011": ("0f5ddefc215d6804ede5749fc2ad9fe2281d57e6", 474),
    "docs/future-tracks-issues-no-milestone-20261011": ("8eb289a57f20b1485ec838c24aff586b8a86e383", 480),
    "docs/rc9-scale-risk-code-review-20261011": ("e9c1bb6e6424bba67e2284d6810d8c98d8d899ff", 481),
    "docs/scale-issue-482-roadmap-20261011": ("4de4190329a4a7ea6c8bda0ede983cee0b1c64aa", 483),
    "docs/issue-first-tracking-rule-20261011": ("01647ad78e9f7b43682063f6d7c5f2232c76dca8", 485),
    "docs/issue-484-closure-20261011": ("bac07edb6f294043cc16acc191d458464b11f7f1", 486),
    "docs/node-sync-issue-487-20261012": ("d3d5d4eb3a127384193f00960a5e62b3c92a6b32", 488),
    "docs/aeza-warp-socks-vless-guide-20261012": ("d2e52bf7f1a0c34433294c71b02e62523c74a5c7", 490),
    "docs/sub-tls-nginx-readonly-checkpoint-20261012": ("00bed306aaf4c35019d9ea2125494ccef07fa848", 492),
    "docs/sub-tls-nginx-issue491-closure-sync": ("218eeb42d498aef79f10f7d47253b07f7cbbbb7a", 493),
    "docs/warp-issue489-closure-sync-20261012": ("accafeaea8b1ab2a0b9256d6fc05528ebf4996c2", 494),
    "docs/github-baseline-checkpoint-20261012-0130": ("68f25520ee6732f3248332bcac1267528c1d298f", 495),
    "docs/roadmap-future-issue-audit-20261012": ("79587fa9a8976be79f3d4da2071ca1354f0d89c3", 508),
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
        stop("manifest cannot be parsed")
    if set(m) != {"issue", "baseline_main_sha", "source_inventory_blob_sha", "created_at", "scope", "refs", "hard_exclusions"}:
        stop("manifest field set mismatch")
    if m["issue"] != 510 or m["baseline_main_sha"] != BASE or m["source_inventory_blob_sha"] != "1a56c8f346db88ee23e78e5b8e64d9f8e71bbf26":
        stop("manifest issue/baseline/inventory provenance mismatch")
    if m["hard_exclusions"] != ["docs/russian-documentation", "docs/v4.10-host-control-contract"]:
        stop("known prior blob mismatches not excluded")
    refs = m["refs"]
    if not isinstance(refs, list) or len(refs) != 100 or len(EXPECTED) != 100:
        stop("expected exactly 100 immutable candidates")
    if any(not isinstance(x, dict) or set(x) != {"name", "sha", "pr_number"} for x in refs):
        stop("invalid manifest row shape")
    if {x["name"]: (x["sha"], x["pr_number"]) for x in refs} != EXPECTED:
        stop("hardcoded immutable name/SHA/PR list disagrees with manifest")
    if len({x["name"] for x in refs}) != 100:
        stop("duplicate branch names")
    for name, (sha, pr) in EXPECTED.items():
        if not re.fullmatch(r"docs/[A-Za-z0-9_.\\-/]+", name):
            stop("unsafe historical branch name")
        if not re.fullmatch(r"[0-9a-f]{40}", sha) or not isinstance(pr, int) or not 1 <= pr <= 600:
            stop("invalid expected SHA or original merged PR")


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
    # Only repeat GitHub REST/ls-remote READS after one successful write.
    # GitHub's branch REST view can briefly lag a successful Git receive-pack.
    for delay in (0, 2, 3, 5, 8, 13):
        if delay:
            time.sleep(delay)
        remote = current_remote_sha(name)
        api_branch = request("branches/" + urllib.parse.quote(name, safe="/"), missing_ok=True)
        if remote is None and api_branch is None:
            return
        if remote is not None and remote != old_sha:
            stop("ref moved or was recreated after delete " + name)
        if api_branch is not None and api_branch.get("commit", {}).get("sha") != old_sha:
            stop("GitHub branch API sees unexpected head SHA " + name)
        print("READ-BACK PENDING", name, "only read-only wait; never replay delete", flush=True)
    stop("post-delete read-back inconclusive: " + name + "; stop; no write retries")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("check", "execute"))
    args = parser.parse_args()
    read_manifest()
    if args.mode == "execute":
        execute_gate()
    prs = all_prs()
    deps = local_dependency_hits()
    eligible: list[tuple[str, str, int]] = []
    skipped: list[tuple[str, str]] = []
    for name, (sha, pr_num) in EXPECTED.items():
        reason = classify(name, sha, pr_num, prs, deps)
        if reason == "PASS":
            eligible.append((name, sha, pr_num))
            print("PROOF PASS", name, sha, "PR#" + str(pr_num), flush=True)
        else:
            skipped.append((name, reason))
            print("RETAIN", name, "|", reason, flush=True)
    print("PROOF SUMMARY", "eligible=" + str(len(eligible)), "retained=" + str(len(skipped)), flush=True)
    if len(eligible) < 40:
        stop("fewer than 40 independently proven safe candidates; deleted=0")
    if args.mode == "check":
        print("DRY-RUN PASS; deleted=0; retained=" + str(len(skipped)), flush=True)
        return

    verified = 0
    retained_on_execution = 0
    for name, sha, pr_num in eligible:
        if request("branches/main")["commit"]["sha"] != git("rev-parse", "HEAD").stdout.strip():
            stop("main changed after checks; stop subsequent ref writes")
        reason = classify(name, sha, pr_num, prs, deps)
        if reason != "PASS":
            retained_on_execution += 1
            print("RETAIN AT EXECUTION", name, "|", reason, flush=True)
            continue
        # Exactly ONE server-side expected-SHA-lease DELETE write per branch.
        pushed = git(
            "push", "--porcelain", "--force-with-lease=refs/heads/" + name + ":" + sha,
            "origin", ":refs/heads/" + name, check=False
        )
        if pushed.returncode != 0:
            stop("SHA-lease deletion failed or unknown: " + name + "; do not replay")
        read_back_deleted_without_replay(name, sha)
        verified += 1
        print("DELETED / VERIFIED", name, sha, "PR#" + str(pr_num), flush=True)
    print("BATCH100 RESULT verified_deleted=" + str(verified), "initial_retained=" + str(len(skipped)),
          "retained_on_execution=" + str(retained_on_execution), flush=True)
    if not verified:
        stop("no refs deleted; scoped batch blocked, not PASS")


if __name__ == "__main__":
    main()
