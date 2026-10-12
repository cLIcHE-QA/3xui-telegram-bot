#!/usr/bin/env python3
"""#510: one-shot SHA-leased deletion of exactly 96 revalidated merged historical refs.

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
BASE = "6692005c1781221bf49512516e7fe81b81496bf2"
MANIFEST_BASE = "b1fbd95b6f3c1b0dba35029f63533ba3f76360b1"
MANIFEST = Path("docs/audits/branch-cleanup-verified-96-candidates-2026-10-12.json")
WORKFLOW = ".github/workflows/retire-verified-100-510.yml"
SELF = "scripts/retire-verified-100-510.py"
EXPECTED = {
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
    "docs/future-issues-closure-sync-20261012": ("56746ee597c86901677e1663a24270e8436701fe", 509),
    "docs/branch-lifecycle-audit-20261012": ("78d5f29727f4b4967311cf09cf17ff80f76858d4", 511),
    "docs/branch-retention-policy-20261012": ("e4de8b36c4dcdd0c2327eb417d8b774591198a95", 513),
    "docs/branch-dry-run-inventory-20261012": ("9a7dc1eca791e1e95594b330751869cb90de0798", 514),
    "audit/a011-production-acceptance": ("094dfc224f4ab819dde4754b400d7ef55e582b7b", 281),
    "audit/a012-production-acceptance": ("7c9e1e23625d42c56904fa45bf62590ea46a152d", 282),
    "audit/pre-public-cross-cutting": ("2db20516499d06b878481d0e8baa9310562824bb", 283),
    "audit/clean-room-acceptance": ("c8174517e963d09bdc66b27b95f856f34f68c43d", 284),
    "audit/final-v4-pass": ("eb8d4bf99ec4fd608596a9991fd2fe1b99be128d", 285),
    "audit/v5-launch-gate": ("ffc8e0122d3a42064a379a525c50a37f888f2b09", 308),
    "test/living-docs-release-scope-gates": ("6001b9aa33a4e33d7725786a9c0944dd7392b6d3", 373),
    "test/352-isolated-job-alert-lifecycle": ("c830916d603da8ddcf7818c927c67b0cb2b583af", 450),
    "test/352-qa-telegram-delivery": ("9fea79e08b16c522fe2dfb802a819bafacb863bb", 452),
    "ci/supply-chain-main-gate": ("7ffe500487d5df0ac0c893cf1d3b065c4099ba1c", 274),
    "legal/apache-2-license": ("f8e48f7a59ef450765a36f512580f2650ead335b", 275),
    "refactor/admin-navigation": ("7ba98fea89c2368eedee1f58faf4c1a3cb5dc8a4", 80),
    "refactor/node-ui": ("889a8bf7c6399c7b58fbe8d9c2f9257b01022426", 81),
    "refactor/node-onboarding": ("1692ed8c9aacff57dce4dba5638e09c1b2dff7ea", 82),
    "refactor/node-presentation": ("0747d0c45f76db6f0a214d3625329db239db0209", 83),
    "refactor/node-admin-router": ("4b0f5db853c5f0a0643f700804e10f2170e01e24", 84),
    "refactor/system-admin-router": ("f19f7d116b908bada2652930452c9afd3c2036b7", 85),
    "refactor/backup-admin-router": ("6e2fbf744fe41a5246dd6c5b72a39e7255aac92e", 86),
    "refactor/legacy-user-admin": ("83c670286063f8acf85bb966a8537bd61dc8dfa3", 87),
    "refactor/admin-users-router": ("6e35373a46fa6759e196d02ae9d5a1cb87f0858d", 88),
    "refactor/client-access-router": ("c05257f9d8f08e99ffda745cecfabbe0e3f740fa", 89),
    "refactor/admin-shell-router": ("70c8052fbd3dd2b42480bd0e3a9c3abadb720efa", 90),
    "refactor/app-runtime": ("66927838b2faef5432eb6ccb2a9c269490efefcb", 91),
    "fix/readiness-callback-routing": ("87f3ea394cedbd534d7e334c0e0a0d815a1abf1e", 22),
    "fix/host-control-startup-recovery": ("16bc72fe07d66a672bcc656ea8f452da08e50bc3", 35),
    "fix/recovery-alert-copy": ("27b4dfd7021d452f1f759360d84011f62c1d58d4", 77),
    "fix/roadmap-gate-v4191-2": ("292dc4ff440cb03609d31e76c376135a73fbd9a8", 78),
    "fix/admin-setup-release-version": ("d342721a8153b5f3da7f8d869759c1d77bcdb328", 79),
    "fix/ui-russian-operations": ("9a1b77abf4f2b431b6b2748f3537c6f133ef234f", 94),
    "fix/ui-russian-control": ("c34b298b8fb4bb7726440077aff4cfc48924447c", 95),
    "fix/ui-russian-updates": ("dcf9f9c00dcb8549908fe91e4e725753a946dbe2", 96),
    "fix/ui-russian-domain-followup": ("120ce436bf9c11efa50e4d0176976dd7a4a47d12", 99),
    "fix/ui-russian-final-audit": ("97537cc1c2555b46af61a7c38d15b3a8dc5b13e7", 102),
    "fix/ui-emoji-audit": ("8f2ab26951b1eb3df45f42eedc1419ced18008be", 103),
    "fix/admin-navigation-audit": ("1955646c72b9284c7bcbcf9b97e9b06343804827", 104),
    "fix/public-readiness-copy": ("d19ce4f7271b5f63badb804edd079abd85b9ff75", 105),
    "fix/v4.20.1-release-notes-sigpipe": ("2c1d86e19c481012db1aa90d97395b8a09945df5", 107),
    "fix/admin-navigation-parent-flows": ("0b4e9444aebfd6f24c28b0fa6db09dab46b5257a", 109),
    "fix/v4.20.2-production-smoke": ("086ee56eda3973376bb9ac14d759b9ebaccc654f", 111),
    "fix/v4.20.5-ui-consistency": ("f7bfd3e79f510f8cc11780e5d113974efe07158f", 117),
    "fix/v4.20.6-health-summary": ("0aa3b58a5fdf4165bc8d9f2b21b243cd5e8ccc31", 121),
    "fix/v4.20.7-inbounds-terminology-clean": ("adf4bfa66e59fff820d8b09c30ee393f40f5368e", 125),
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
    if git("hash-object", str(MANIFEST)).stdout.strip() != "285df619eed3e3ed1facd78f969856d9484bf04c":
        stop("immutable original 50-ref manifest blob mismatch")
    if m.get("issue") != 510 or m.get("baseline_main_sha") != BASE:
        stop("manifest issue/original SHA mismatch")
    if m.get("action") != "PREPARE_ONLY_NO_DELETION" or m.get("selected_count") != 96:
        stop("manifest schema/count is not the approved preflight snapshot")
    refs = m.get("candidates")
    if not isinstance(refs, list) or len(refs) != 96 or len(EXPECTED) != 96:
        stop("expected exactly 96 historical ref candidates")
    if any(not isinstance(x, dict) or set(x) != {
        "branch", "tip_sha", "merged_pr", "squash_sha", "classification"} for x in refs):
        stop("candidate fields modified")
    if {x["branch"]: (x["tip_sha"], x["merged_pr"]) for x in refs} != EXPECTED:
        stop("hardcoded exact SHA/PR allowlist differs from immutable manifest")
    # Hard fail if any of the four original unsafe candidates enters the new scope.
    forbidden = {"fix/stable-bot-docker-network", "fix/admin-ui-navigation-consistency",
                 "fix/v4.9.3-node-detail-counters", "fix/release-tag-probe"}
    if any(n in EXPECTED for n in forbidden):
        stop("unsafe original 4 reintroduced")
    for row in refs:
        if row["classification"] != "DELETE_CANDIDATE_REQUIRES_FRESH_PREFLIGHT":
            stop("unexpected candidate classification")
        if not re.fullmatch(r"[0-9a-f]{40}", row["squash_sha"]):
            stop("invalid source squash SHA")
    for name, (sha, pr) in EXPECTED.items():
        if not re.fullmatch(r"(?:docs|audit|test|ci|legal|refactor|fix)/[a-zA-Z0-9_./-]+", name):
            stop("unsafe historical branch name")
        if not re.fullmatch(r"[0-9a-f]{40}", sha) or not isinstance(pr,int) or not 1 <= pr <= 537:
            stop("invalid exact tip SHA/PR")
    if any(n in EXPECTED for n in (
        "docs/russian-documentation", "docs/v4.10-host-control-contract", "main")):
        stop("known protected or mismatch exclusion in target list")
    if len({x["branch"] for x in refs}) != 96:
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
    live_open_prs = paged("pulls?state=open")
    if any((p.get("head") or {}).get("ref") == name or
           (p.get("base") or {}).get("ref") == name for p in live_open_prs):
        return "live open PR uses this branch"
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
    # Confirm no other still-live remote head contains the original PR tip.
    # This is a conservative check for graph-level dependencies beyond PR base refs.
    descendants = git("branch", "-r", "--contains", sha).stdout.splitlines()
    unexpected = [line.strip() for line in descendants
                  if line.strip() not in ("origin/" + name,)]
    if unexpected:
        return "tip is ancestor of other refs: " + ", ".join(unexpected[:4])
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
        stop("at least one of the 96 refs failed independent proof; deleted=0")
    print("PROOF SUMMARY eligible=96 retained=4_excluded", flush=True)
    if args.mode == "check":
        print("DRY-RUN PASS 96/96; deleted=0", flush=True)
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
    print("BATCH96 RESULT verified_deleted=" + str(verified) + "/96", flush=True)


if __name__ == "__main__":
    main()
