#!/usr/bin/env python3
"""#510: one-shot SHA-leased deletion of exactly 94 independently proven historical refs.

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
BASE = "ae669ba8bff3b7bf93250bd0efddfb8f89c2f053"
MANIFEST_BASE = "ae669ba8bff3b7bf93250bd0efddfb8f89c2f053"
MANIFEST = Path("docs/audits/branch-cleanup-verified-94-candidates-2026-10-12.json")
WORKFLOW = ".github/workflows/retire-verified-94-510.yml"
SELF = "scripts/retire-verified-94-510.py"
EXPECTED = {
    "chore/host-control-rollout": ("b2c8d5776d6b85192b8860c33b1a71d896534d9a", 15),
    "chore/living-docs-contract": ("06b4d1e9e62cefa47f77a946ecf4dc80125cf391", 289),
    "chore/pr-checklist-gate": ("5836ffe504dc710a2cfa63a3266975ba35c1de1e", 371),
    "chore/release-automation": ("2b7ad82f47d608cce712f68880ae9d33d8a4db0e", 19),
    "chore/vps-recovery-kit": ("16b1666997a7839c24ffcb5b436b92bd1fc2b643", 14),
    "chore/3xui-living-contract-sync": ("99f781f44af4fdba43a92fb362eccddecf771413", 428),
    "docs/branch-audit-closure-readback-20261012": ("ca4c922e1980c24c6f7e08c48829694213980b7e", 512),
    "feat/master-node-hosts-readonly-422": ("42ccdd740b8a062def3242d1c04574ab72a9d548", 424),
    "feat/v5-checkout-provider-boundary": ("2b5fbd817d2fa107b36d11578016f030fb2aa548", 302),
    "feat/v5-client-onboarding-diagnostics": ("9839396320f37559a1848d144709ce62562f0148", 306),
    "feat/v5-client-portal-shell": ("42b64d2b6d6a5a3f5d9ffd34c4ab28a5acdf7ec7", 296),
    "feat/v5-commerce-foundation": ("9cc2d7cd14c9dfa296bb39834ddf23789a0422e1", 290),
    "feat/v5-customer-service-boundary": ("beb89ecb73513df39691a40f4a3abc968e044d6b", 301),
    "feat/v5-entitlement-fulfillment-worker": ("3d89e083fcaa6b663dc224c75716daeee8ce1ce3", 295),
    "feat/v5-entitlement-provisioning": ("39f374cea8eccdb46f692cad64a55e0fc97aa58d", 292),
    "feat/v5-launch-readiness": ("4e7bb23fe848ad51a82256d3e43a9411e53355bd", 307),
    "feat/v5-payment-entitlement-transaction": ("0831384e76bba14a9905ac80ed7050e46252aea9", 291),
    "feat/v5-payment-event-reconciliation": ("d08fdc87f27ad7028af2255adb2ddd656938e139", 294),
    "feat/v5-payment-webhook-gateway": ("cb731d04c4c57de56bf9b714c47780a1ff54f0de", 293),
    "feat/v5-release-candidate-path": ("c2a76a0132e8bb59ecc7e572475d533ee2c18d8d", 310),
    "feat/v5-stars-production-hardening": ("840c848ef516b2b3b1124770cd646e4ec33f1afb", 305),
    "feat/v5-telegram-stars": ("1eee32586d3ee14bd493037bd3be7f0c6a01c581", 304),
    "feature/admin-username-display-355": ("7d7874aa278d8ab9d99dab4bdfcdbf7e2a78f5b8", 364),
    "feature/attention-center": ("5044031d53279d992faf5719b53ad9b5e7063047", 224),
    "feature/cheburcheck-discovery-v4-23": ("b9da160fb1e8b0283568d65f41553fd8d8f72c7b", 154),
    "feature/cheburcheck-v4-23-2": ("d5df86801329aae29b1a4acd64e2bb96e5aac978", 158),
    "feature/cheburcheck-v4-23": ("517bdddfc31f8b5807d40b3e8c6b8e2e789cf45e", 153),
    "feature/client-portal-stars-switches-342": ("ff0d699ccb80b1fbab5197619976f1f9fc20b444", 368),
    "feature/dashboard-attention": ("5ebcd4c82451fc957a76ba90aff2f619c9e85e04", 221),
    "feature/direct-node-onboarding-wrapper": ("371bb91735207c87f39c49a5005540dfd8f352af", 24),
    "feature/extended-node-backup-clean": ("1b6afc96ecf75cb7310f8d2f7ccfabbd75f3c434", 45),
    "feature/fleet-operations": ("413abf186e093e7ac42f230c2ca4e0e9b82135cf", 26),
    "feature/job-update-unknown-ack-353": ("2552168cbdbc9599eb30da96ed76faec07f387d6", 362),
    "feature/node-drain": ("f3d105bc03fdaf13fe65f46a6cd943d40af3990e", 209),
    "feature/owner-client-session-reset-345": ("680fa7789a12e8c4f42bcf15874f3bd8bbb954df", 416),
    "feature/rbac-privileges": ("44ef8973aeff4238060349a93d984065b785c7f3", 42),
    "feature/telegram-command-catalog-356": ("bf50ffad077a75b066bab1df55ccc2e0cfd8fe7d", 365),
    "feature/user-audience-groups": ("c1b1c44c536f78f8b28517beff0656d152cb496f", 147),
    "feature/user-display-name": ("bf1556cc77e91c3873857008cb56eeae102d1877", 136),
    "feature/v4-24-monitoring-foundation": ("33785ccd9cdb315c92764c3f485bcff36fe4e0ac", 165),
    "feature/v4-24-monitoring-lifecycle": ("3ed7f054f52de2821fd429ce844978d8570d8c45", 168),
    "feature/v4-24-monitoring-ui-runtime": ("8b967aa2eb9435624f4a6aa4affd01e0af737591", 166),
    "feature/v4-24-web-diagnostics": ("089a7a4535463c4f5ba12f7fb9ad29e62cd5b9e2", 167),
    "feature/v4-25-user-bulk-completion": ("6936549fcb25d96056ce8e2c92f525727fdf8ab2", 182),
    "feature/v4-25-user-card-navigation": ("e7d3add006b0124c36a739acf3b71431cccc34fd", 177),
    "feature/v4-25-user-connections": ("7f4a2373954cffcc0c8d42b18203e33a9f26348e", 178),
    "feature/v4-25-user-create": ("3a6a41ef543bc2ae3591e73f09e4151f83838009", 180),
    "feature/v4-25-user-management-foundation": ("23ff19b013ba6339ae510120bdd3969065bad8d3", 176),
    "feature/v4-25-user-payments-activity": ("a2e82cc77ed9d801e3e7207d150b3adc09879be7", 179),
    "feature/v4-25-user-safety-subscription": ("3ff1de440f2fdf4246f60627086de6e9ee126ea3", 181),
    "feature/v4.11.0-node-onboarding": ("dd2744f309346875a0a6468e646d11801d56fc68", 17),
    "feature/v4.16-regression-hardening": ("14dd01729d59e6bf0190574d1254e29be1662fc0", 60),
    "feature/v4.17-openapi-contract-gate": ("a6dc3d1c2f7377d332fcb1fe015b11788d18c9a2", 64),
    "feature/v4.18-offsite-backup": ("45386133476507f20337aa8800366c13d7ec3b7b", 68),
    "feature/v4.19-safe-bot-self-update": ("fa0c21fd8f3c699f05b03216181cf61c8582bba5", 73),
    "feature/versioned-sqlite-migrations": ("20608d01a745a5a0d8a29ac8bab6deaa8a3dc906", 55),
    "fix/attention-navigation-role-heading-354": ("7bb726a31f32403e9fc1c710e62d2271b9733acb", 363),
    "fix/backup-master-fail-closed": ("dda781907b7319ad492865c39bb6438534eeb4af", 350),
    "fix/client-portal-callback-effective-flag": ("c8d1d3ac8df6a89012df42766168937fbbe9fdcc", 420),
    "fix/container-least-privilege-rollout": ("b51b5995af681d217086adae8a50dce92badcb36", 269),
    "fix/container-source-permissions": ("d460f78c708ff3498d034d0da92c930b34761b10", 279),
    "fix/history-secret-audit-fetch": ("c60baf0d975347bf854f9e3c6021663662ac503d", 265),
    "fix/inbound-input-validation": ("186b958cf6d8af7d6f37c794f19405046ae18483", 200),
    "fix/job-alert-repeat-context": ("cfc18797972226e9e0cb227e3e7664aef3543bcf", 361),
    "fix/master-backup-api-wal-acl": ("b1c4df9fa7f83ca5e3e64e52e37070b11e65b44f", 351),
    "fix/node-drain-cancel-navigation": ("a26233176467f23ed537d3e803c4db454389637c", 213),
    "fix/permission-aware-navigation": ("ec36268fa8affdd5e1a845e6930d27326abafacd", 228),
    "fix/qa352-direct-preview-import": ("5305583d4b995949755da4ebc7c05c94862ebead", 454),
    "fix/safari-subscription-assets-nginx": ("048fe4f3f67ebe4cd9d428d1c4d491acdf2f3e50", 300),
    "fix/stars-invoice-use-bot-display-name": ("31baa5427b8a7e0b7cd0e2a1070991b98916bba0", 347),
    "fix/stars-paid-invoice-cleanup-320": ("b525328d2de39b6a3c41b3a44b63c99bf0b99da8", 417),
    "fix/subscription-browser-blank-page": ("76ea0c926adf9805c89d03180baba9f5c6226dd5", 297),
    "fix/subscription-runtime-base-path": ("922af000227da4573ce7367a331d8c3bc40d0248", 298),
    "fix/trial-zero-limits-343": ("5608105300913eefa4fd5c671f99ddd148bc69a0", 367),
    "fix/v4-25-access-navigation-contract": ("b6fbd241054019c5ca9eb62fe253f19bcc4aac46", 183),
    "fix/v4-25-final-ui-contract": ("5c1d115007be49eaef30f6dec8ca5d68c2f44d08", 184),
    "fix/v4.20.8-inbound-capitalization": ("8d57c95c81d61d5c6be08300d50eb7744f2d9070", 128),
    "fix/v4.20.9-post-acceptance-ui-cleanup": ("6de9c6cf2ce1d5fed917c05a00cda560819ab46c", 131),
    "fix/v4.20.10-inbound-keyboard-density": ("b06832e9dfbf63e3f928f77abc13fa506c3fd409", 133),
    "fix/v4.21.1-display-time-consistency": ("faa1ff287dc4013b0c3de58970dee2220a0e87da", 140),
    "fix/v4.21.2-dr-logs": ("8613d075d078b6fd9159290d9314050db89e0b1b", 143),
    "fix/v4.25.8-navigation-owner-safety": ("f5fdb1284286396cb2a7023444da96d9d492473f", 205),
    "fix/v5-expired-customer-status": ("2d5b3fe24f9c6a2e2ffbc706e0ccfd43e1edd268", 312),
    "fix/v5-rc3-provider-access-status": ("41dacac830e26df181bbf7c4280a7611ca50d44e", 325),
    "fix/v5-rc3-quota-ui": ("bb3a326fa9ad908f59751bcdf2887fde6ccfc411", 318),
    "fix/v5-stars-refund-handler-import": ("f3b7f75fa375299f81e25c60174d9e273a72d13a", 329),
    "fix/v5-stars-refund-terminal-and-admin-totals": ("29596f9cdfcba0dfd8eccb275c5e0bcf8cd26f67", 335),
    "fix/v4250-acceptance-readonly-extend": ("4eeca5a076241ddafdb313f57dfc37c15a0b4246", 188),
    "fix/v4251-stabilization": ("837be548cad132b56669ce3ff06c995a1be5fec2", 189),
    "fix/v4252-subscription-compat": ("a78065522e402c0c848b4d500cc12690c09b7849", 191),
    "fix/v4253-incy-desktop-ua": ("453c146d438e2fc32c10b0dd7a10bf589f03d809", 193),
    "fix/v4254-streisand-plain-subscription": ("3a7c87c00c91f400d4ef4c90aa35c48a3fcb9c86", 195),
    "fix/v4255-streisand-force-raw": ("770607de34140d47a4d02b14d02bef5d5a2d9647", 196),
    "fix/v4256-revert-streisand-workarounds": ("03f3ff4d625c147ec5d4c96f3167516b3e1e82f6", 197),
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
        stop("94-ref manifest unreadable")
    if git("hash-object", str(MANIFEST)).stdout.strip() != "0ca0669bcd68461d67d78b431f32d1c01322929a":
        stop("immutable 94-ref manifest blob SHA mismatch")
    if m.get("schema") != 1 or m.get("issue") != 510 or m.get("repository") != REPO:
        stop("manifest schema/repo/issue mismatch")
    if m.get("baseline_main_sha") != BASE or m.get("parent_manifest_blob_sha") != "3b9cb914e288b79223951196e192142ddce6c436":
        stop("main/parent manifest SHA mismatch")
    if m.get("original_100_ref_preflight_run") != 38246026296 or m.get("original_preflight_status") != "FAIL":
        stop("historical preflight provenance mismatch")
    if m.get("action") != "PREPARE_ONLY_NO_DELETION" or m.get("selected_count") != 94 or m.get("original_pass_count") != 94:
        stop("manifest action/count mismatch")
    refs = m.get("candidates")
    if not isinstance(refs, list) or len(refs) != 94 or len(EXPECTED) != 94:
        stop("expected exactly 94 immutable refs")
    if any(not isinstance(x, dict) or set(x) != {"branch", "tip_sha", "merged_pr", "original_pr_head_sha", "squash_sha", "classification"} for x in refs):
        stop("candidate fields modified")
    if {x["branch"]: (x["tip_sha"], x["merged_pr"]) for x in refs} != EXPECTED:
        stop("manifest does not match exact SHA/PR allowlist")
    forbidden = {
        "chore/git-conventions",
        "chore/publish-v4.10.0",
        "chore/release-deploy-helper",
        "feature/v4.9.2-system-version-fingerprint",
        "feature/v4.10-host-control",
        "feature/versions-updates",
        "docs/russian-documentation",
        "docs/v4.10-host-control-contract",
        "fix/stable-bot-docker-network",
        "fix/admin-ui-navigation-consistency",
        "fix/v4.9.3-node-detail-counters",
        "fix/release-tag-probe",
        "main",
    }
    excluded = m.get("exclusions")
    expected_exclusions = ["chore/git-conventions","chore/publish-v4.10.0","chore/release-deploy-helper","feature/v4.9.2-system-version-fingerprint","feature/v4.10-host-control","feature/versions-updates"]
    if not isinstance(excluded, list) or len(excluded) != 6 or {x.get("branch") for x in excluded if isinstance(x, dict)} != set(expected_exclusions):
        stop("six historical RETAIN refs missing")
    if any(n in EXPECTED for n in forbidden):
        stop("known RETAIN/protected ref in allowlist")
    for row in refs:
        if row["classification"] != "DELETE_CANDIDATE_REQUIRES_FRESH_PREFLIGHT":
            stop("unexpected candidate classification")
        if row["original_pr_head_sha"] != row["tip_sha"]:
            stop("original PR head SHA mismatch")
        if not re.fullmatch(r"[0-9a-f]{40}", row["squash_sha"]):
            stop("invalid original squash SHA")
    for name, (sha, pr) in EXPECTED.items():
        if not re.fullmatch(r"(?:chore|docs|feat|feature|fix|hotfix|security)/[a-zA-Z0-9_./-]+", name):
            stop("invalid historical branch name")
        if ".." in name or name.endswith("/"):
            stop("unsafe branch name")
        if not re.fullmatch(r"[0-9a-f]{40}", sha) or not isinstance(pr,int) or not 1 <= pr <= 542:
            stop("invalid tip SHA/PR")
    if len({x["branch"] for x in refs}) != 94:
        stop("duplicate branch names")


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
        stop("at least one of the 94 refs failed independent proof; deleted=0")
    print("PROOF SUMMARY eligible=94 retained=6_excluded", flush=True)
    if args.mode == "check":
        print("DRY-RUN PASS 94/94; deleted=0", flush=True)
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
    print("BATCH94 RESULT verified_deleted=" + str(verified) + "/94", flush=True)


if __name__ == "__main__":
    main()
