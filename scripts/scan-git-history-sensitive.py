from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from secret_audit_common import fingerprint, scan_sensitive_metadata, sensitive_path_reason


SCANNER_VERSION = "1"


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.stdout


def _add(findings: list[dict[str, str]], seen: set[tuple[str, ...]], finding: dict[str, str]) -> None:
    key = (
        finding.get("detector", ""),
        finding.get("commit", ""),
        finding.get("path", ""),
        finding.get("fingerprint", ""),
    )
    if key in seen:
        return
    seen.add(key)
    findings.append(finding)


def scan_history() -> dict:
    head = _git("rev-parse", "HEAD").strip()
    refs = [line for line in _git("for-each-ref", "--format=%(refname)").splitlines() if line]
    findings: list[dict[str, str]] = []
    seen: set[tuple[str, ...]] = set()

    for line in _git("rev-list", "--objects", "--all").splitlines():
        parts = line.split(" ", 1)
        if len(parts) != 2:
            continue
        object_id, path = parts
        reason = sensitive_path_reason(path)
        if reason:
            _add(
                findings,
                seen,
                {
                    "detector": reason,
                    "commit": "",
                    "path": path,
                    "fingerprint": fingerprint(object_id + "\0" + path),
                },
            )

    log = _git(
        "log",
        "--all",
        "--format=@@COMMIT:%H",
        "--patch",
        "--no-ext-diff",
        "--unified=0",
        "--no-color",
        "--full-history",
    )
    commit = ""
    path = ""
    for line in log.splitlines():
        if line.startswith("@@COMMIT:"):
            commit = line.removeprefix("@@COMMIT:").strip()
            path = ""
            continue
        if line.startswith("+++ b/"):
            path = line[6:]
            continue
        if line.startswith("--- a/") or line.startswith("@@"):
            continue
        if not line.startswith(("+", "-")):
            continue
        payload = line[1:]
        for detector, fp in scan_sensitive_metadata(payload):
            _add(
                findings,
                seen,
                {
                    "detector": detector,
                    "commit": commit,
                    "path": path,
                    "fingerprint": fp,
                },
            )

    return {
        "schema": 1,
        "scanner": "repository-sensitive-history",
        "scanner_version": SCANNER_VERSION,
        "head": head,
        "ref_count": len(refs),
        "finding_count": len(findings),
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan reachable Git history for sensitive metadata without printing values.")
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    report = scan_history()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"history metadata scan: head={report['head']} refs={report['ref_count']} "
        f"findings={report['finding_count']} report={args.report}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
