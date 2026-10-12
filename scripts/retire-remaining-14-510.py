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
    "docs/russian-documentation": ("40101eec1125b9b1f7077751b42d9f1403195b92", 2),
    "docs/v4.10-host-control-contract": ("e760bd9047066c4118d7b54558d8e85a042de772", 11),
    "docs/v5-client-portal-roadmap": ("64e4b6395c776fa84bdf33711f93264f27db1811", 28),
    "docs/v4-admin-finalization-scope": ("9d469bb02b32823d7076cf4f7a5ca316eab377a4", 31),
    "docs/v4-safe-self-update": ("26ebd02b7c54d18c341018f08d8dd79e222e06ce", 32),
    "docs/v4-finalization-audit": ("247626b9a598602b64bc7a57e0fd1e50ef37ca6a", 33),
    "docs/roadmap-competitive-benchmark": ("968ba1bac552c4583aef89dbce7d89b444c26e1f", 34),
    "docs/roadmap-status-tracking": ("4f4369ca4038e699760ba776f6c6e1b0d951f43c", 36),
    "docs/roadmap-status-contract": ("b93404168cfe35177aafa63572bdb1e09d95a399", 37),
    "docs/roadmap-v4-13-2-status": ("15f453e116fa6e0ea38c1fdadbfdc1ed1115e10b", 39),
    "docs/post-release-verification": ("3f67f1e3903322619524d18a51c1842feaf28c30", 40),
    "docs/targeted-release-smoke": ("4d6301d054a952c86c5f3ee16990000e2b04577d", 41),
    "docs/rbac-main-status": ("dddf8007adddf67288c1f53f92b8ea277bb495cd", 43),
    "docs/extended-node-backup-main-status": ("cd7fe3ecb369b5c061ba9cf69e5d38cc0f126288", 46),
    "docs/close-v4.14-roadmap": ("1784e539e2e8b1e79b2fea7f09a00abc97189c74", 50),
    "docs/quick-start-v4.14.1": ("1f3a5c11b5b44fbeb23907a7f33da011e66c4f8a", 51),
    "docs/admin-setup-guide": ("ba5bff77ff01e3871cd0558c365dd2b007864d2b", 54),
    "docs/sqlite-migrations-status": ("3d7586d3cf2c918c8d5e883a5bfa8c594b1eda43", 56),
    "docs/sqlite-migrations-complete": ("c4699f082834d1fdc6b37a0a096042f99e4ce444", 58),
    "docs/telegram-text-emoji-audit": ("01cb1f9d63093427c845cea962ae61bd2a2cc19f", 59),
    "docs/v416-regression-status": ("78c7a23e0f502d6977c91598ad453b1e085f224d", 61),
    "docs/v416-regression-accepted": ("3db78fe96e2bc9f1ecd6e7142039e5879f398875", 63),
    "docs/v417-openapi-status": ("e9eae8f2dbff286f2a99699483d4fa4d3279e8bf", 65),
    "docs/v417-production-acceptance": ("999685557a380eb5bc7c26f8670439975bd0f3af", 67),
    "docs/v418-offsite-status": ("9afb6f46c646f60dc13816aaea8d6a9a8283279c", 69),
    "docs/v418-deferred-acceptance": ("8489f2e98e6d760e4bf67e87e539ba54eabba6d4", 71),
    "docs/client-portal-gate-statuses": ("db818b0ee20819d9995ed8c0376a5643b49489c6", 72),
    "docs/v419-self-update-status": ("cae66ab47da171fc988e3b8cec9cc8cc86d5c5f3", 74),
    "docs/readme-current-state": ("bb37d9c7f17e0ca48b6f4df0a510fdb6a4e17f24", 92),
    "docs/ui-russian-core": ("3a3928aef13a34b018d0e07cb381c2750a8114b1", 93),
    "docs/ui-localization-roadmap-status": ("2f25d804de5011976646dcc3cd0909447656ebaa", 100),
    "docs/cleanup-roadmap-statuses": ("2c91abcece68a8b03801fa1be99c3cac5d979f48", 101),
    "docs/v4.20.1-freeze-prep-acceptance": ("bb4e39c5c3e6d648019de2401419e8b05f63cf37", 108),
    "docs/v4.20.5-ui-follow-up": ("01e5e63b5d37ccd1f2e6537ca1f7c794a65b9615", 114),
    "docs/pre-v5-feature-roadmap-and-final-audit": ("3ca415c7a75c30531c559a678bd5016d02cf9e79", 115),
    "docs/agents-guidance": ("16f68c919f9a5453d3ebf6d2b6c36357776de71a", 116),
    "docs/v4.20.5-published-status": ("ea9c6f5398336e5434248025087c3b828cce2c94", 119),
    "docs/v4.20.5-production-acceptance": ("0f6a050646aaf9df06bb4adf8e2103868c642905", 120),
    "docs/v4.20.6-acceptance-v4.20.7-plan": ("7ef77eac9e1e95add2b1d8ab0b60e915bfea9e15", 123),
    "docs/v4.20.7-production-acceptance": ("3bfd1475c7356a2a88e2c5a7d3292c6f2a10a606", 127),
    "docs/v4.20.8-production-acceptance": ("8f4a2175272148a5689d025a978fe32f03e51178", 130),
    "docs/v4.20.10-production-acceptance": ("68a8eed587a131147bf21fd816d62b8c4db1b88e", 135),
    "docs/v4.21.0-published-status": ("7f9f01169d5af679e5025a4934b002da11fb2266", 138),
    "docs/v4.21.0-production-acceptance": ("02cd6213bfeb091dcb64fe339daa5fdc846a5318", 139),
    "docs/v4.21.1-published-status": ("576fcb1a3d49dcf8af392bc768d3fa5da3d34238", 142),
    "docs/v4.21.2-production-acceptance": ("b4ec3add52eb7ec3f5f99e315280ab275426fa60", 145),
    "docs/v4-25-user-management-roadmap": ("bea9773892cb8afce4051f174ff1f5886d8c4e1b", 146),
    "docs/v4-22-implemented": ("b2b1d3d5bb4ff4389723557d5eeb412754ceb2d0", 148),
    "docs/v4-22-published": ("67d759dfe8dd01d80d2d90a0479aaaafaed2e1f0", 150),
    "docs/v4-22-production-accepted": ("96313d018cb41125b3e927db9149f7dbc96b41ad", 151),
    "docs/v4-26-node-drain": ("971c1a4cb4febf12571eca82b7de195f92c68a01", 152),
    "docs/v4-23-1-acceptance": ("8bc27be8c5c348071c12fa82105a5e5bc78efe0d", 157),
    "docs/cheburcheck-probe-fleet-roadmap": ("f3c60d53aae235319b56d727f07914e950568e9f", 162),
    "docs/close-v4-23-3": ("2c61c44a55773156d0c7c93bab31f0b26459f9ee", 163),
    "docs/v4-24-0-release-contract": ("8f0b7a62662d1f42ee4f5c2148fff597588ce519", 164),
    "docs/v4-24-1-whois-msk": ("98b71b134e879cd00e5150671c7e95993534c8f8", 170),
    "docs/v4-24-1-production-acceptance": ("29ae304cbbba2327a18af484550f6cd10b7361cc", 173),
    "docs/close-v4-24-line": ("0a3e140f98281bedc625b325f346ee85652497b9", 174),
    "docs/sync-production-acceptance-v4-21-v4-24": ("9575cc3d1da8c98ad58b3a50962c79dc4b9d72cb", 175),
    "docs/v4-25-implementation-complete": ("bdeaa52a7d187863d0e6a44a56654ab63f56ea9e", 185),
    "docs/v4-25-published-status": ("088fbf3740f5abe0d68c1f6fce2a177c2c554986", 187),
    "docs/v4251-production-acceptance": ("40b5638a14c93040de4a667c1e37f442c0a45f22", 190),
    "docs/shadowrocket-send-hwid": ("fe4cbd9f537957751b853b636c7387c29471e4f9", 192),
    "docs/close-v425-production-line": ("827f9686638b9e193da08da743cd3a7703b742fb", 198),
    "docs/roadmap-v4.25.8": ("79be864b791c1e252e1d84918a56a55e25cac019", 203),
    "docs/close-v4.25-line": ("f6d1f60b70f052c919f68b1c09706664e3e1c8da", 207),
    "docs/v4-26-1-node-drain-navigation": ("38b61d559d5f46c8e828de5306ebfed9558c0cfc", 212),
    "docs/v4-26-1-production-acceptance": ("2f646e5e1f7fea5326f954b903fb9e7a9655a381", 215),
    "docs/attention-releases-v4-26-2-v4-26-3": ("c7ac8d22b331e7434f8ffc0041ede200996dc6c3", 218),
    "docs/data-plane-addressing-firewall": ("a9e575faacfcb7350ff7b0f5d1cd92c4d29453f7", 220),
    "docs/v4.26.2-acceptance": ("4187fa6305ea71912bcfd325477d2e6d217d76cd", 223),
    "docs/v4.26.4-navigation-fix": ("92160142d4daa273012799aec4437e3d9ee498c9", 227),
    "docs/v4.26.4-acceptance": ("16ce4b2c5e4fba704d9a90e6369c298db9261111", 230),
    "docs/fix-v4-closure-order": ("92ff8f1c3da4e4a26fedc7a2bf1795b42c96f556", 231),
    "docs/remnawave-roadmap": ("54f84f17e09817adc7c22c3909c15f662742ec2a", 232),
    "docs/final-v4-feature-freeze": ("dfa5bc16a7601fcd31d550b3ae4955b7a716eb98", 233),
    "docs/final-v4-audit-baseline": ("dc445039a632278150000603c7ae7bc24cb1bccc", 247),
    "docs/recovery-drill-record": ("7bc6de5fc9069119fd7d9b3fa32f1b61a882d5f0", 251),
    "docs/github-communication-language": ("ee447092fb1ec89e063944e4781fdcb22b10a755", 254),
    "docs/russian-v4-audit": ("886c6cc4dcf0914a795717047b6d2c4652e336dc", 257),
    "docs/full-backup-retrieval": ("b2956028c9a9f8c2d5839e23e913c6b17ce75b3d", 259),
    "docs/github-status-health-gate": ("203a4115692eec4524302db1fb469a2cb0aa9b33", 262),
    "docs/close-a010-history-secret-audit": ("719108f62d89b2d5bda38cce3bed73c049e7b0bb", 267),
    "docs/sync-a011-a012-audit-status": ("5fe48886123fed36617705a328329560f1a15826", 271),
    "docs/close-a008-a009": ("955fa87b7260a2b7c245a0483da486e68733e121", 276),
    "docs/accept-a007-risk": ("0eabe4c43bd695340a888b75ca4f09f3e4b0270f", 277),
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
