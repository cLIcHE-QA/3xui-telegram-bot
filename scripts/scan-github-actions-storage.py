from __future__ import annotations

import argparse
import concurrent.futures
import io
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from secret_audit_common import (
    fingerprint,
    scan_high_confidence,
    scan_sensitive_metadata,
    sensitive_path_reason,
)


SCANNER_VERSION = "1"
API_VERSION = "2022-11-28"
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 24 * 1024 * 1024
DEFAULT_WORKERS = 6

_SECRET_REF_RE = re.compile(r"\bsecrets\.([A-Za-z_][A-Za-z0-9_]*)")
_VAR_REF_RE = re.compile(r"\bvars\.([A-Za-z_][A-Za-z0-9_]*)")


class ApiError(RuntimeError):
    def __init__(self, status: int, path: str):
        super().__init__(f"GitHub API status={status} path={path}")
        self.status = status
        self.path = path


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "3xui-telegram-bot-actions-storage-audit",
    }


def _request_json(api_base: str, token: str, path: str) -> dict[str, Any]:
    req = urllib.request.Request(
        f"{api_base}{path}",
        headers=_headers(token),
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ApiError(exc.code, path) from exc


def _request_download(api_base: str, token: str, path: str) -> bytes:
    req = urllib.request.Request(
        f"{api_base}{path}",
        headers=_headers(token),
        method="GET",
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        response = opener.open(req, timeout=30)
    except urllib.error.HTTPError as exc:
        if exc.code not in {301, 302, 303, 307, 308}:
            raise ApiError(exc.code, path) from exc
        location = exc.headers.get("Location")
        if not location:
            raise ApiError(exc.code, path) from exc
        # Do not forward the GitHub token to the temporary blob-storage URL.
        unsigned = urllib.request.Request(
            location,
            headers={"User-Agent": "3xui-telegram-bot-actions-storage-audit"},
            method="GET",
        )
        with urllib.request.urlopen(unsigned, timeout=60) as redirected:
            data = redirected.read(MAX_ARCHIVE_BYTES + 1)
    else:
        with response:
            data = response.read(MAX_ARCHIVE_BYTES + 1)

    if len(data) > MAX_ARCHIVE_BYTES:
        raise RuntimeError(f"archive exceeds {MAX_ARCHIVE_BYTES} bytes")
    return data


def _paginate(
    api_base: str,
    token: str,
    path: str,
    key: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    separator = "&" if "?" in path else "?"
    while True:
        payload = _request_json(
            api_base,
            token,
            f"{path}{separator}per_page=100&page={page}",
        )
        batch = payload.get(key) or []
        if not isinstance(batch, list):
            raise RuntimeError(f"unexpected pagination payload for {path}")
        items.extend(item for item in batch if isinstance(item, dict))
        if len(batch) < 100:
            return items
        page += 1


def _scan_text(text: str, source: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for detector, fp in scan_high_confidence(text):
        findings.append(
            {
                "detector": detector,
                "fingerprint": fp,
                "source": source,
            }
        )
    for detector, fp in scan_sensitive_metadata(text):
        findings.append(
            {
                "detector": detector,
                "fingerprint": fp,
                "source": source,
            }
        )
    return findings


def _scan_zip(
    data: bytes,
    *,
    source_prefix: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    coverage_issues: list[dict[str, str]] = []

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return findings, [
            {
                "kind": "invalid-zip",
                "source": source_prefix,
            }
        ]

    with archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            member_source = f"{source_prefix}/{member.filename}"

            reason = sensitive_path_reason(member.filename)
            if reason:
                findings.append(
                    {
                        "detector": reason,
                        "fingerprint": fingerprint(member.filename),
                        "source": member_source,
                    }
                )

            if member.file_size > MAX_MEMBER_BYTES:
                coverage_issues.append(
                    {
                        "kind": "oversized-member",
                        "source": member_source,
                    }
                )
                continue

            try:
                raw = archive.read(member)
            except (RuntimeError, OSError, zipfile.BadZipFile):
                coverage_issues.append(
                    {
                        "kind": "unreadable-member",
                        "source": member_source,
                    }
                )
                continue

            text = raw.decode("utf-8", errors="replace")
            findings.extend(_scan_text(text, member_source))

    return findings, coverage_issues


def _historical_workflow_refs() -> dict[str, Any]:
    proc = subprocess.run(
        ["git", "log", "--all", "-p", "--", ".github/workflows"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    text = proc.stdout
    return {
        "secret_refs": sorted(set(_SECRET_REF_RE.findall(text))),
        "variable_refs": sorted(set(_VAR_REF_RE.findall(text))),
        "upload_artifact_mentions": text.count("upload-artifact"),
    }


def _current_workflow_refs(root: Path) -> dict[str, Any]:
    secrets: set[str] = set()
    variables: set[str] = set()
    upload_mentions = 0

    workflow_dir = root / ".github" / "workflows"
    for path in sorted(workflow_dir.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8", errors="replace")
        secrets.update(_SECRET_REF_RE.findall(text))
        variables.update(_VAR_REF_RE.findall(text))
        upload_mentions += text.count("upload-artifact")

    return {
        "secret_refs": sorted(secrets),
        "variable_refs": sorted(variables),
        "upload_artifact_mentions": upload_mentions,
    }


def _inventory_names(
    api_base: str,
    token: str,
    path: str,
    key: str,
) -> dict[str, Any]:
    try:
        items = _paginate(api_base, token, path, key)
    except ApiError as exc:
        return {
            "status": f"http-{exc.status}",
            "names": [],
        }
    names = sorted(
        str(item.get("name"))
        for item in items
        if item.get("name")
    )
    return {
        "status": "ok",
        "names": names,
    }


def _aggregate(findings: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}

    for finding in findings:
        key = (finding["detector"], finding["fingerprint"])
        record = grouped.setdefault(
            key,
            {
                "detector": finding["detector"],
                "fingerprint": finding["fingerprint"],
                "occurrences": 0,
                "sources": [],
            },
        )
        record["occurrences"] += 1
        if (
            len(record["sources"]) < 8
            and finding["source"] not in record["sources"]
        ):
            record["sources"].append(finding["source"])

    return sorted(
        grouped.values(),
        key=lambda item: (
            item["detector"],
            item["fingerprint"],
        ),
    )


def _scan_run_logs(
    api_base: str,
    token: str,
    repo: str,
    run: dict[str, Any],
) -> dict[str, Any]:
    run_id = int(run["id"])
    try:
        data = _request_download(
            api_base,
            token,
            f"/repos/{repo}/actions/runs/{run_id}/logs",
        )
    except ApiError as exc:
        if exc.status in {404, 410}:
            return {
                "run_id": run_id,
                "status": "not-retained",
                "findings": [],
                "coverage_issues": [],
            }
        return {
            "run_id": run_id,
            "status": f"http-{exc.status}",
            "findings": [],
            "coverage_issues": [
                {
                    "kind": f"http-{exc.status}",
                    "source": f"run:{run_id}",
                }
            ],
        }
    except Exception:
        return {
            "run_id": run_id,
            "status": "download-error",
            "findings": [],
            "coverage_issues": [
                {
                    "kind": "download-error",
                    "source": f"run:{run_id}",
                }
            ],
        }

    findings, coverage_issues = _scan_zip(
        data,
        source_prefix=f"run:{run_id}",
    )
    return {
        "run_id": run_id,
        "status": "scanned",
        "findings": findings,
        "coverage_issues": coverage_issues,
    }


def _scan_artifact(
    api_base: str,
    token: str,
    repo: str,
    artifact: dict[str, Any],
) -> dict[str, Any]:
    artifact_id = int(artifact["id"])
    try:
        data = _request_download(
            api_base,
            token,
            f"/repos/{repo}/actions/artifacts/{artifact_id}/zip",
        )
    except ApiError as exc:
        return {
            "artifact_id": artifact_id,
            "status": f"http-{exc.status}",
            "findings": [],
            "coverage_issues": [
                {
                    "kind": f"http-{exc.status}",
                    "source": f"artifact:{artifact_id}",
                }
            ],
        }
    except Exception:
        return {
            "artifact_id": artifact_id,
            "status": "download-error",
            "findings": [],
            "coverage_issues": [
                {
                    "kind": "download-error",
                    "source": f"artifact:{artifact_id}",
                }
            ],
        }

    findings, coverage_issues = _scan_zip(
        data,
        source_prefix=f"artifact:{artifact_id}",
    )
    return {
        "artifact_id": artifact_id,
        "status": "scanned",
        "findings": findings,
        "coverage_issues": coverage_issues,
    }


def scan(*, workers: int) -> dict[str, Any]:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    api_base = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")

    if not token:
        raise SystemExit("GITHUB_TOKEN is required")
    if "/" not in repo:
        raise SystemExit("GITHUB_REPOSITORY must be owner/name")

    root = Path(__file__).resolve().parents[1]
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    ).stdout.strip()

    runs = _paginate(
        api_base,
        token,
        f"/repos/{repo}/actions/runs?",
        "workflow_runs",
    )
    completed_runs = [
        run
        for run in runs
        if run.get("status") == "completed"
        and run.get("conclusion") != "skipped"
    ]

    artifacts = _paginate(
        api_base,
        token,
        f"/repos/{repo}/actions/artifacts?",
        "artifacts",
    )
    retained_artifacts = [
        artifact
        for artifact in artifacts
        if not artifact.get("expired")
    ]

    all_findings: list[dict[str, str]] = []
    coverage_issues: list[dict[str, str]] = []
    log_status_counts: dict[str, int] = defaultdict(int)
    artifact_status_counts: dict[str, int] = defaultdict(int)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(
                _scan_run_logs,
                api_base,
                token,
                repo,
                run,
            )
            for run in completed_runs
        ]
        for index, future in enumerate(
            concurrent.futures.as_completed(futures),
            start=1,
        ):
            result = future.result()
            log_status_counts[result["status"]] += 1
            all_findings.extend(result["findings"])
            coverage_issues.extend(result["coverage_issues"])
            if index % 100 == 0:
                print(
                    f"Actions log audit progress: "
                    f"{index}/{len(completed_runs)} runs"
                )

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(
                _scan_artifact,
                api_base,
                token,
                repo,
                artifact,
            )
            for artifact in retained_artifacts
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            artifact_status_counts[result["status"]] += 1
            all_findings.extend(result["findings"])
            coverage_issues.extend(result["coverage_issues"])

    secret_inventory = _inventory_names(
        api_base,
        token,
        f"/repos/{repo}/actions/secrets?",
        "secrets",
    )
    variable_inventory = _inventory_names(
        api_base,
        token,
        f"/repos/{repo}/actions/variables?",
        "variables",
    )

    aggregated = _aggregate(all_findings)

    report = {
        "schema": 1,
        "scanner": "github-actions-storage-secret-audit",
        "scanner_version": SCANNER_VERSION,
        "head": head,
        "repository": repo,
        "workflow_runs_total": len(runs),
        "completed_non_skipped_runs": len(completed_runs),
        "log_status_counts": dict(sorted(log_status_counts.items())),
        "artifacts_total": len(artifacts),
        "retained_artifacts": len(retained_artifacts),
        "artifact_status_counts": dict(sorted(artifact_status_counts.items())),
        "finding_count": len(aggregated),
        "findings": aggregated,
        "coverage_issue_count": len(coverage_issues),
        "coverage_issues": coverage_issues,
        "current_workflow_refs": _current_workflow_refs(root),
        "historical_workflow_refs": _historical_workflow_refs(),
        "repository_actions_secrets": secret_inventory,
        "repository_actions_variables": variable_inventory,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scan retained GitHub Actions run logs and artifacts without "
            "publishing raw secret values."
        )
    )
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
    )
    args = parser.parse_args()

    if args.workers < 1 or args.workers > 12:
        raise SystemExit("--workers must be between 1 and 12")

    report = scan(workers=args.workers)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "Actions storage audit summary: "
        f"head={report['head']} "
        f"runs={report['completed_non_skipped_runs']} "
        f"logs={report['log_status_counts']} "
        f"artifacts={report['retained_artifacts']} "
        f"artifact_status={report['artifact_status_counts']} "
        f"findings={report['finding_count']} "
        f"coverage_issues={report['coverage_issue_count']} "
        f"secret_inventory={report['repository_actions_secrets']['status']} "
        f"variable_inventory={report['repository_actions_variables']['status']} "
        f"report={args.report}"
    )

    for item in report["findings"]:
        print(
            "- "
            f"detector={item['detector']} "
            f"fingerprint={item['fingerprint']} "
            f"occurrences={item['occurrences']} "
            f"sources={','.join(item['sources'][:3])}"
        )

    if report["coverage_issue_count"]:
        print("Actions storage audit coverage is incomplete.")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
