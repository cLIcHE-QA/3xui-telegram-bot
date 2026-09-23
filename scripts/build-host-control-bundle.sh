#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'USAGE'
Usage:
  ./scripts/build-host-control-bundle.sh /secure/path/3xui-host-control-bundle.tar.gz

Builds a secret-free Host Control deployment bundle for a remote VPS.
The bundle contains only the agent, installers and systemd/sudoers assets.
A sibling .sha256 file is written for transfer verification.
USAGE
}

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

case "${1:-}" in
    --help|-h) usage; exit 0 ;;
esac

[[ "$#" -eq 1 ]] || { usage >&2; exit 2; }
OUT="$1"
[[ "$OUT" = /* ]] || die "output path must be absolute"

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

need=(
    version.py
    host_control_agent.py
    scripts/install-host-control-agent.sh
    scripts/setup-host-control-endpoint.sh
    scripts/refresh-host-control-tls.sh
    deploy/host-control/3xui-host-control.service
    deploy/host-control/3xui-host-control.sudoers
)
for path in "${need[@]}"; do
    [[ -f "$path" ]] || die "missing bundle input: $path"
done

mkdir -p "$(dirname -- "$OUT")"
tmp="$(mktemp "${OUT}.XXXXXX")"
trap 'rm -f "$tmp"' EXIT HUP INT TERM

tar -czf "$tmp" -- "${need[@]}"
chmod 0600 "$tmp"
mv "$tmp" "$OUT"
trap - EXIT HUP INT TERM

OUT_DIR="$(dirname -- "$OUT")"
OUT_NAME="$(basename -- "$OUT")"
if command -v sha256sum >/dev/null 2>&1; then
    (cd "$OUT_DIR" && sha256sum "$OUT_NAME" > "$OUT_NAME.sha256")
    chmod 0600 "$OUT.sha256"
elif command -v shasum >/dev/null 2>&1; then
    (cd "$OUT_DIR" && shasum -a 256 "$OUT_NAME" > "$OUT_NAME.sha256")
    chmod 0600 "$OUT.sha256"
else
    die "bundle created, but sha256sum/shasum is unavailable"
fi

printf 'Host Control bundle created: %s\n' "$OUT"
printf 'Checksum file: %s.sha256\n' "$OUT"
printf 'Bundle contains no enrollment token or runtime secret.\n'
