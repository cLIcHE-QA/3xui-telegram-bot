#!/usr/bin/env bash
set -Eeuo pipefail

GITLEAKS_VERSION="8.30.1"
GITLEAKS_SHA256="551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"
GITLEAKS_URL="https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz"

ROOT="$(git rev-parse --show-toplevel)"
OUTPUT_DIR="${1:-${TMPDIR:-/tmp}/3xui-history-secret-audit}"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

mkdir -p "$OUTPUT_DIR"

archive="$WORK_DIR/gitleaks.tar.gz"
curl -fsSL "$GITLEAKS_URL" -o "$archive"
printf '%s  %s\n' "$GITLEAKS_SHA256" "$archive" | sha256sum -c -
tar -xzf "$archive" -C "$WORK_DIR" gitleaks
"$WORK_DIR/gitleaks" version

raw="$WORK_DIR/gitleaks-raw.json"
safe="$OUTPUT_DIR/gitleaks-safe.json"

set +e
(
  cd "$ROOT"
  "$WORK_DIR/gitleaks" git \
    --no-banner \
    --no-color \
    --redact=100 \
    --report-format json \
    --report-path "$raw" \
    .
)
gitleaks_rc=$?
set -e

if [[ "$gitleaks_rc" -gt 1 ]]; then
  echo "gitleaks failed with rc=$gitleaks_rc" >&2
  exit "$gitleaks_rc"
fi

python3 "$ROOT/scripts/sanitize-gitleaks-report.py" "$raw" "$safe"
python3 "$ROOT/scripts/scan-git-history-sensitive.py" --report "$OUTPUT_DIR/history-metadata.json"

python3 - "$safe" "$OUTPUT_DIR/history-metadata.json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

gitleaks = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
metadata = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))

print(f"history secret audit summary: gitleaks={len(gitleaks)} metadata_candidates={metadata['finding_count']}")
if gitleaks:
    print("gitleaks findings (secret values removed):")
    for item in gitleaks:
        print(
            f"- rule={item.get('RuleID','?')} file={item.get('File','?')} "
            f"commit={item.get('Commit','?')} line={item.get('StartLine','?')} "
            f"fingerprint={item.get('Fingerprint','?')}"
        )
if metadata["findings"]:
    print("sensitive metadata candidates (values fingerprinted, never printed):")
    for item in metadata["findings"]:
        print(
            f"- detector={item.get('detector','?')} path={item.get('path','?')} "
            f"commit={item.get('commit','?')} fingerprint={item.get('fingerprint','?')}"
        )
PY

echo "audit output: $OUTPUT_DIR"
