from __future__ import annotations

import argparse
import json
from pathlib import Path


ALLOWED_FIELDS = (
    "RuleID",
    "Description",
    "File",
    "Commit",
    "StartLine",
    "EndLine",
    "Fingerprint",
)


def sanitize(source: Path, destination: Path) -> int:
    if not source.exists() or source.stat().st_size == 0:
        findings = []
    else:
        raw = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise SystemExit("unexpected gitleaks report format")
        findings = [
            {field: item.get(field) for field in ALLOWED_FIELDS if item.get(field) not in (None, "")}
            for item in raw
            if isinstance(item, dict)
        ]

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(findings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(findings)


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove secret-bearing fields from a Gitleaks JSON report.")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    count = sanitize(args.source, args.destination)
    print(f"gitleaks sanitized findings={count} report={args.destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
