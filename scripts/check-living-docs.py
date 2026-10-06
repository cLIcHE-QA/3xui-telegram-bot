#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "docs" / "live-docs.json"


def load_contract(path: Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != 1:
        raise ValueError(f"Unsupported living-docs schema: {data.get('schema')!r}")
    return data


def path_matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(path, pattern)


def matching_paths(paths: Iterable[str], patterns: Iterable[str]) -> list[str]:
    return sorted(
        {
            path
            for path in paths
            for pattern in patterns
            if path_matches(path, pattern)
        }
    )


def evaluate_contract(
    contract: dict[str, Any],
    changed_files: Iterable[str],
    pr_body: str = "",
) -> list[dict[str, Any]]:
    changed = set(changed_files)
    violations: list[dict[str, Any]] = []

    for rule in contract.get("rules", []):
        rule_id = str(rule["id"])
        triggers = [str(item) for item in rule.get("triggers", [])]
        documents = [str(item) for item in rule.get("documents", [])]
        trigger_hits = matching_paths(changed, triggers)
        if not trigger_hits:
            continue

        changed_docs = sorted(changed.intersection(documents))
        mode = str(rule.get("mode", "review"))

        if mode == "require_all":
            missing = sorted(set(documents) - changed)
            if missing:
                violations.append(
                    {
                        "id": rule_id,
                        "mode": mode,
                        "triggers": trigger_hits,
                        "documents": documents,
                        "missing": missing,
                        "waiver": "",
                    }
                )
            continue

        if mode == "review":
            waiver = str(rule.get("waiver", "")).strip()
            if changed_docs or (waiver and waiver in pr_body):
                continue
            violations.append(
                {
                    "id": rule_id,
                    "mode": mode,
                    "triggers": trigger_hits,
                    "documents": documents,
                    "missing": documents,
                    "waiver": waiver,
                }
            )
            continue

        raise ValueError(f"Unknown living-docs rule mode {mode!r} for {rule_id}")

    return violations


def git_changed_files(base_sha: str, head_sha: str) -> list[str]:
    command = [
        "git",
        "diff",
        "--name-only",
        "--diff-filter=ACMRD",
        f"{base_sha}...{head_sha}",
        "--",
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "git diff failed for living-docs check: "
            + result.stderr.strip()
        )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail closed when a PR changes a contract trigger without reviewing its living docs."
    )
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--pr-body", default="")
    parser.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_CONTRACT,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        contract = load_contract(args.contract)
        changed = git_changed_files(args.base_sha, args.head_sha)
        violations = evaluate_contract(contract, changed, args.pr_body)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"Living Docs checker error: {exc}", file=sys.stderr)
        return 2

    print(f"Living Docs: {len(changed)} changed file(s) inspected.")
    if not violations:
        print("Living Docs: PASS")
        return 0

    print("Living Docs: FAIL", file=sys.stderr)
    for item in violations:
        print(
            f"::error title=Living Docs {item['id']}::"
            f"Triggers: {', '.join(item['triggers'])}. "
            f"Review/update: {', '.join(item['documents'])}.",
            file=sys.stderr,
        )
        if item["mode"] == "require_all":
            print(
                f"  missing required docs: {', '.join(item['missing'])}",
                file=sys.stderr,
            )
        elif item["waiver"]:
            print(
                f"  or add exact PR-body waiver after review: {item['waiver']}",
                file=sys.stderr,
            )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
