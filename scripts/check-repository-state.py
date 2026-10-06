#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "docs" / "live-docs.json"
API_ROOT = "https://api.github.com"


class AuditError(RuntimeError):
    pass


def load_contract(path: Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != 1:
        raise AuditError(f"Unsupported living-docs schema: {data.get('schema')!r}")
    return data


def request_json(url: str, token: str = "") -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "3xui-telegram-bot-repository-state-audit",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if token and exc.code == 403:
            return request_json(url, token="")
        body = exc.read().decode("utf-8", errors="replace")
        raise AuditError(f"GitHub API {exc.code} for {url}: {body[:500]}") from exc
    except urllib.error.URLError as exc:
        raise AuditError(f"GitHub API request failed for {url}: {exc}") from exc


def api(repo: str, suffix: str, token: str = "") -> Any:
    return request_json(f"{API_ROOT}/repos/{repo}{suffix}", token=token)


def get_ruleset(repo: str, expected: dict[str, Any], token: str) -> dict[str, Any]:
    rulesets = api(repo, "/rulesets", token)
    matches = [
        item for item in rulesets
        if item.get("name") == expected["name"]
        and item.get("target") == expected["target"]
    ]
    if len(matches) != 1:
        raise AuditError(
            f"Expected exactly one ruleset {expected['name']!r}/"
            f"{expected['target']!r}, got {len(matches)}."
        )
    ruleset_id = matches[0]["id"]
    return api(repo, f"/rulesets/{ruleset_id}", token)


def verify_ruleset(ruleset: dict[str, Any], expected: dict[str, Any]) -> None:
    name = expected["name"]
    if ruleset.get("enforcement") != expected["enforcement"]:
        raise AuditError(
            f"{name}: enforcement={ruleset.get('enforcement')!r}, "
            f"expected {expected['enforcement']!r}"
        )

    includes = set(
        ruleset.get("conditions", {}).get("ref_name", {}).get("include", [])
    )
    required_includes = set(expected.get("include", []))
    if not required_includes.issubset(includes):
        raise AuditError(
            f"{name}: include={sorted(includes)!r}, "
            f"missing {sorted(required_includes - includes)!r}"
        )

    rules = {str(item.get("type")): item for item in ruleset.get("rules", [])}
    required_rules = set(expected.get("required_rules", []))
    missing_rules = required_rules - set(rules)
    if missing_rules:
        raise AuditError(f"{name}: missing rules {sorted(missing_rules)!r}")

    forbidden_rules = set(expected.get("forbidden_rules", []))
    present_forbidden = forbidden_rules.intersection(rules)
    if present_forbidden:
        raise AuditError(
            f"{name}: forbidden rules present {sorted(present_forbidden)!r}"
        )

    if expected.get("no_bypass"):
        if ruleset.get("bypass_actors", []):
            raise AuditError(f"{name}: bypass actors are configured")
        bypass = ruleset.get("current_user_can_bypass")
        if bypass not in (None, "never"):
            raise AuditError(f"{name}: current_user_can_bypass={bypass!r}")

    pull = rules.get("pull_request")
    if pull and expected.get("allowed_merge_methods"):
        actual = set(pull.get("parameters", {}).get("allowed_merge_methods", []))
        wanted = set(expected["allowed_merge_methods"])
        if actual != wanted:
            raise AuditError(
                f"{name}: allowed_merge_methods={sorted(actual)!r}, "
                f"expected {sorted(wanted)!r}"
            )

    checks = rules.get("required_status_checks")
    if checks:
        params = checks.get("parameters", {})
        actual = {
            str(item.get("context"))
            for item in params.get("required_status_checks", [])
        }
        wanted = set(expected.get("required_status_checks", []))
        if not wanted.issubset(actual):
            raise AuditError(
                f"{name}: required checks={sorted(actual)!r}, "
                f"missing {sorted(wanted - actual)!r}"
            )
        if expected.get("strict_status_checks") and not params.get(
            "strict_required_status_checks_policy"
        ):
            raise AuditError(f"{name}: strict status checks policy is disabled")


def app_version_from_text(text: str) -> str:
    match = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"\s*$', text, re.MULTILINE)
    if not match:
        raise AuditError("APP_VERSION not found in version.py")
    return match.group(1)


def resolve_tag_commit(repo: str, tag_name: str, token: str) -> str:
    encoded = urllib.parse.quote(tag_name, safe="")
    ref = api(repo, f"/git/ref/tags/{encoded}", token)
    obj = ref["object"]
    for _ in range(4):
        if obj.get("type") == "commit":
            return str(obj["sha"])
        if obj.get("type") != "tag":
            raise AuditError(f"Unexpected Git tag object type: {obj.get('type')!r}")
        tag_obj = api(repo, f"/git/tags/{obj['sha']}", token)
        obj = tag_obj["object"]
    raise AuditError("Annotated tag nesting is unexpectedly deep")


def tagged_version(repo: str, tag_name: str, token: str) -> str:
    query = urllib.parse.urlencode({"ref": tag_name})
    payload = api(repo, f"/contents/version.py?{query}", token)
    if payload.get("encoding") != "base64":
        raise AuditError("version.py content encoding is not base64")
    text = base64.b64decode(payload["content"]).decode("utf-8")
    return app_version_from_text(text)


def verify_release(repo: str, default_branch: str, token: str) -> None:
    latest = api(repo, "/releases/latest", token)
    tag_name = str(latest.get("tag_name", ""))
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag_name):
        raise AuditError(f"Latest release has unexpected tag {tag_name!r}")

    local_version = app_version_from_text(
        (ROOT / "version.py").read_text(encoding="utf-8")
    )
    expected_tag = f"v{local_version}"
    if tag_name != expected_tag:
        raise AuditError(
            f"Latest release tag={tag_name!r}, expected {expected_tag!r}"
        )

    remote_version = tagged_version(repo, tag_name, token)
    if remote_version != local_version:
        raise AuditError(
            f"{tag_name}: APP_VERSION={remote_version!r}, "
            f"expected {local_version!r}"
        )

    tag_sha = resolve_tag_commit(repo, tag_name, token)
    compare = api(
        repo,
        f"/compare/{tag_sha}...{urllib.parse.quote(default_branch, safe='')}",
        token,
    )
    if compare.get("status") not in {"ahead", "identical"}:
        raise AuditError(
            f"{tag_name} commit {tag_sha} is not an ancestor of {default_branch}; "
            f"compare status={compare.get('status')!r}"
        )
    print(f"release: {tag_name} -> {tag_sha} ({compare.get('status')})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only audit of public GitHub repository settings kept outside Git."
    )
    parser.add_argument("--repository", required=True)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get("GITHUB_TOKEN", "")
    try:
        contract = load_contract(args.contract)
        expected = contract["repository_state"]
        metadata = api(args.repository, "", token)

        if metadata.get("visibility") != expected["visibility"]:
            raise AuditError(
                f"visibility={metadata.get('visibility')!r}, "
                f"expected {expected['visibility']!r}"
            )
        default_branch = str(metadata["default_branch"])
        print(f"repository: visibility={metadata.get('visibility')} default={default_branch}")

        branch_ruleset = get_ruleset(
            args.repository, expected["branch_ruleset"], token
        )
        verify_ruleset(branch_ruleset, expected["branch_ruleset"])
        print(f"ruleset: {branch_ruleset['name']} PASS")

        tag_ruleset = get_ruleset(args.repository, expected["tag_ruleset"], token)
        verify_ruleset(tag_ruleset, expected["tag_ruleset"])
        print(f"ruleset: {tag_ruleset['name']} PASS")

        verify_release(args.repository, default_branch, token)
    except (AuditError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Repository state audit: FAIL: {exc}", file=sys.stderr)
        return 1

    print("Repository state audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
