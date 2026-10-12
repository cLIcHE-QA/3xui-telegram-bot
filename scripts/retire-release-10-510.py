#!/usr/bin/env python3
"""#510: one-shot SHA-leased deletion of exactly ten historical release refs, fail-closed."""
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
BASE = "42bb1cfcef94a6e99b1841c74f4481e4a8a869a4"
MANIFEST = Path("docs/audits/branch-cleanup-release-10-execution-2026-10-12.json")
WORKFLOW = ".github/workflows/retire-release-10-510.yml"
SELF = "scripts/retire-release-10-510.py"
EXPECTED = {
    "release/v4-23-0": ("ef39ed8bfc771dc5ea211b2f60b55179614f9c04", 155),
    "release/v4-23-1": ("b4acd456d163fccae43fb8e4c1f275e0af6008a7", 156),
    "release/v4.10.1": ("b1c1e1a00115421641dbb7f1aabc4637457554ea", 16),
    "release/v4.11.0": ("8707f1a67469da802860f2e513cdf1db6585a435", 18),
    "release/v4.11.1": ("8006c5bed107667f981ba668d85bb80ac8b5d326", 23),
    "release/v4.12.0": ("8ee5ab32db5db676ed59811ed0c5a0c4f756ee77", 25),
    "release/v4.13.0": ("afa770f443d60869e181092f82595e4117302a08", 27),
    "release/v4.13.1": ("a78e454a570a4c67df25012c8df936934d5b0b14", 30),
    "release/v4.13.2": ("1f77dc18a85801aa5024023485cc3f78718e4982", 38),
    "release/v4.14.0": ("d573cbaa61f85140c25b3ad29f630f5656fd3bee", 47),
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
    if git("hash-object", str(MANIFEST)).stdout.strip() != "0ea1e9622475de6bb8b6bc4e46cc80e704757ff0":
        stop("immutable manifest blob hash mismatch")
    if m.get("schema") != 1 or m.get("issue") != 510 or m.get("repository") != REPO:
        stop("manifest schema/repo/issue mismatch")
    if m.get("baseline_main_sha") != BASE or m.get("source_manifest_sha") != "d2727d82c3bda4eb5c3f3d996641309f99edb01f":
        stop("baseline and provenance mismatch")
    if m.get("action") != "PREPARE_ONLY_NO_DELETION" or m.get("selected_count") != 10:
        stop("manifest not prepared for ten-ref safety proof")
    refs = m.get("candidates")
    if not isinstance(refs, list) or len(refs) != 10 or len(EXPECTED) != 10:
        stop("expected ten refs")
    if any(not isinstance(x, dict) or set(x) != {"branch","tip_sha","merged_pr","original_pr_head_sha","squash_sha","classification"} for x in refs):
        stop("manifest candidate format mismatch")
    if {x["branch"]: (x["tip_sha"],x["merged_pr"]) for x in refs} != EXPECTED:
        stop("manifest exact allowlist mismatch")
    if len({x["branch"] for x in refs}) != 10:
        stop("duplicate branch name")
    for x in refs:
        if x["classification"] != "DELETE_CANDIDATE_REQUIRES_FRESH_PREFLIGHT" or x["original_pr_head_sha"] != x["tip_sha"]:
            stop("candidate classification or tip mismatch")
        if not re.fullmatch(r"[0-9a-f]{40}",x["squash_sha"]):
            stop("invalid squash sha")
    for name, (sha, pr) in EXPECTED.items():
        if not re.fullmatch(r"release/[A-Za-z0-9_.-]+",name) or ".." in name:
            stop("not an approved release work-branch name")
        if not re.fullmatch(r"[0-9a-f]{40}",sha) or not isinstance(pr,int) or not 1 <= pr <= 546:
            stop("invalid reference sha/PR number")

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
        stop("at least one of the 10 refs failed independent proof; deleted=0")
    print("PROOF SUMMARY eligible=10 retained=98_excluded", flush=True)
    if args.mode == "check":
        print("DRY-RUN PASS 10/10; deleted=0", flush=True)
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
    print("BATCH10 RESULT verified_deleted=" + str(verified) + "/10", flush=True)


if __name__ == "__main__":
    main()
