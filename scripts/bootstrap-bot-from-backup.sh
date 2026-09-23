#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT="${RECOVERY_PROJECT:-3xui-telegram-bot}"
SERVICE="${RECOVERY_SERVICE:-bot}"
HEALTH_URL="${RECOVERY_HEALTH_URL:-http://127.0.0.1:18080/healthz}"
SSH_KEY="${RECOVERY_SSH_KEY:-$HOME/.ssh/3xui_bot_deploy}"
EXPECTED_REPOSITORY="${RECOVERY_EXPECTED_REPOSITORY:-cLIcHE-QA/3xui-telegram-bot}"
RESCUE_ROOT="${RECOVERY_RESCUE_ROOT:-/opt/3xui-bot/recovery-rescue}"
ALLOW_VERSION_MISMATCH="${RECOVERY_ALLOW_VERSION_MISMATCH:-0}"

usage() {
    cat <<'USAGE'
Usage:
  ./scripts/bootstrap-bot-from-backup.sh vX.Y.Z /secure/path/3xui-bot-backup-YYYYMMDD-HHMMSS.tar.gz

Scope:
  Restores only the Telegram bot .env and bot.sqlite3 on a prepared VPS.
  It does NOT install/restore 3x-ui, Xray, MTProxy/nginx, firewall, Docker, TLS,
  DNS, SSH keys, or remote nodes.

Safety:
  - refuses to overwrite a running bot container;
  - validates archive paths and SQLite before writing;
  - checks release tag + APP_VERSION + origin;
  - requires backup manifest version to match the requested release by default;
  - creates a rescue copy of existing .env/data;
  - disables HOST_CONTROL_TARGETS and NODE_BACKUP_TARGETS until privileged targets are re-validated;
  - never prints secrets.

Break glass:
  RECOVERY_ALLOW_VERSION_MISMATCH=1 allows an intentional backup/release version mismatch.
USAGE
}

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

resolve_root() {
    local source="${BASH_SOURCE[0]:-}"
    if [[ -n "$source" && -f "$source" ]]; then
        local script_dir
        script_dir="$(cd -- "$(dirname -- "$source")" && pwd)"
        if [[ -d "$script_dir/../.git" ]]; then
            (cd "$script_dir/.." && pwd)
            return
        fi
    fi
    pwd
}

case "${1:-}" in
    --help|-h)
        usage
        exit 0
        ;;
esac

[[ "$#" -eq 2 ]] || { usage >&2; exit 2; }
RELEASE="$1"
ARCHIVE="$2"

[[ "$RELEASE" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "release must look like v4.10.0"
[[ -f "$ARCHIVE" ]] || die "backup archive not found: $ARCHIVE"

need_cmd git
need_cmd docker
need_cmd python3
need_cmd curl
need_cmd flock

ROOT="$(resolve_root)"
cd "$ROOT"

[[ -d .git ]] || die "$ROOT is not a Git working tree"
[[ -f docker-compose.yml ]] || die "$ROOT/docker-compose.yml not found"
[[ -f "$SSH_KEY" ]] || die "deploy key not found: $SSH_KEY"

origin="$(git remote get-url origin)"
case "$origin" in
    "git@github.com:$EXPECTED_REPOSITORY.git"|    "ssh://git@github.com/$EXPECTED_REPOSITORY.git"|    "https://github.com/$EXPECTED_REPOSITORY.git"|    "https://github.com/$EXPECTED_REPOSITORY") ;;
    *) die "unexpected origin: $origin" ;;
esac

git diff --quiet || die "tracked working tree has local changes"
git diff --cached --quiet || die "index has local changes"

exec 9>"/tmp/$PROJECT.recovery.lock"
flock -n 9 || die "another recovery is already running"

running_cid="$(docker compose --project-name "$PROJECT" -f docker-compose.yml ps -q "$SERVICE" 2>/dev/null || true)"
if [[ -n "$running_cid" ]] && [[ "$(docker inspect "$running_cid" --format '{{.State.Running}}' 2>/dev/null || true)" == true ]]; then
    die "bot container is running; this bootstrap intentionally refuses in-place restore"
fi

printf 'Fetching release metadata...\n'
GIT_SSH_COMMAND="ssh -i $SSH_KEY -o IdentitiesOnly=yes"     git fetch origin main --tags --prune

tag_sha="$(git rev-parse -q --verify "refs/tags/$RELEASE^{commit}")" || die "release tag not found: $RELEASE"
git merge-base --is-ancestor "$tag_sha" origin/main || die "$RELEASE is not contained in origin/main"

target_version="$(git show "$RELEASE:version.py" | sed -nE 's/^APP_VERSION[[:space:]]*=[[:space:]]*"([^"]+)"/\1/p' | head -n 1)"
[[ -n "$target_version" ]] || die "APP_VERSION not found in $RELEASE"
[[ "v$target_version" == "$RELEASE" ]] || die "$RELEASE does not match APP_VERSION=$target_version"

stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT HUP INT TERM

python3 - "$ARCHIVE" "$stage" "$target_version" "$ALLOW_VERSION_MISMATCH" <<'PY'
from __future__ import annotations
import json
import sqlite3
import sys
import tarfile
from pathlib import Path

archive = Path(sys.argv[1])
stage = Path(sys.argv[2])
target_version = sys.argv[3].strip()
allow_version_mismatch = sys.argv[4].strip() == "1"
max_members = 5000
max_member = 512 * 1024 * 1024
max_total = 2 * 1024 * 1024 * 1024

with tarfile.open(archive, "r:gz") as tar:
    members = tar.getmembers()
    if len(members) > max_members:
        raise SystemExit("backup has too many members")
    total = 0
    by_name = {}
    for member in members:
        normalized = member.name.replace("\\", "/")
        parts = Path(normalized).parts
        if not normalized or normalized.startswith(("/", "\\")) or any(p in {"", ".", ".."} for p in parts):
            raise SystemExit(f"unsafe backup path: {member.name!r}")
        if member.issym() or member.islnk() or member.isdev() or member.isfifo():
            raise SystemExit(f"unsupported backup member: {member.name!r}")
        if member.isfile():
            if member.size < 0 or member.size > max_member:
                raise SystemExit(f"oversized backup member: {member.name!r}")
            total += member.size
            if total > max_total:
                raise SystemExit("backup exceeds safe unpacked size")
        by_name[member.name] = member

    required = ("bot.env", "bot.sqlite3")
    for name in required:
        member = by_name.get(name)
        if member is None or not member.isfile():
            raise SystemExit(f"required backup member missing: {name}")
        src = tar.extractfile(member)
        if src is None:
            raise SystemExit(f"cannot read backup member: {name}")
        data = src.read(max_member + 1)
        if len(data) > max_member:
            raise SystemExit(f"backup member too large: {name}")
        (stage / name).write_bytes(data)

    manifest = {}
    member = by_name.get("manifest.json")
    if member is not None and member.isfile():
        src = tar.extractfile(member)
        if src is not None:
            try:
                manifest = json.loads(src.read(1024 * 1024).decode("utf-8"))
            except Exception:
                manifest = {}

backup_version = ""
if isinstance(manifest, dict):
    backup_version = str(manifest.get("version") or "").strip()

if not backup_version:
    if not allow_version_mismatch:
        raise SystemExit(
            "backup manifest version is missing; "
            "set RECOVERY_ALLOW_VERSION_MISMATCH=1 only for an intentional break-glass restore"
        )
    print("WARNING: backup manifest version is missing; mismatch override is enabled")
elif backup_version != target_version:
    if not allow_version_mismatch:
        raise SystemExit(
            f"backup app version {backup_version!r} does not match target release {target_version!r}"
        )
    print(
        "WARNING: backup app version "
        f"{backup_version} does not match target release {target_version}; mismatch override is enabled"
    )

db = stage / "bot.sqlite3"
if not db.read_bytes().startswith(b"SQLite format 3\x00"):
    raise SystemExit("bot.sqlite3 is not SQLite3")
uri = f"file:{db.resolve()}?mode=ro"
with sqlite3.connect(uri, uri=True, timeout=10) as conn:
    rows = conn.execute("PRAGMA quick_check").fetchall()
values = [str(row[0]) for row in rows]
if not values or any(v.lower() != "ok" for v in values):
    raise SystemExit("bot.sqlite3 quick_check failed: " + "; ".join(values[:10]))

print("Backup preflight: OK")
print("Backup app version:", backup_version or "unknown")
PY

# Restored privileged routes/tokens belong to the old deployment. Keep per-target
# values in the file for operator review, but disable the active target lists
# until Host Control and direct node admin connectivity are re-validated.
python3 - "$stage/bot.env" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
lines = path.read_text(encoding="utf-8").splitlines()
disabled = {"HOST_CONTROL_TARGETS", "NODE_BACKUP_TARGETS"}
out = []
seen = set()
for line in lines:
    if line.lstrip().startswith("#") or "=" not in line:
        out.append(line)
        continue
    key = line.split("=", 1)[0].strip()
    if key in disabled:
        out.append(f"{key}=")
        seen.add(key)
    else:
        out.append(line)
for key in sorted(disabled - seen):
    out.append(f"{key}=")
path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY

stamp="$(date -u +%Y%m%d-%H%M%S)"
rescue="$RESCUE_ROOT/pre-bootstrap-$stamp"
mkdir -p "$rescue"
chmod 700 "$rescue"

if [[ -f .env ]]; then
    cp -a .env "$rescue/.env"
    chmod 600 "$rescue/.env"
fi
if [[ -f data/bot.sqlite3 ]]; then
    cp -a data/bot.sqlite3 "$rescue/bot.sqlite3"
    chmod 600 "$rescue/bot.sqlite3"
fi

git checkout --detach "$RELEASE"
[[ "$(git rev-parse HEAD)" == "$tag_sha" ]] || die "checkout did not land on release commit"

install -m 0600 "$stage/bot.env" .env
mkdir -p data
chmod 700 data
install -m 0600 "$stage/bot.sqlite3" data/bot.sqlite3

docker compose     --project-name "$PROJECT"     --env-file .env     -f docker-compose.yml     config --quiet

docker compose     --project-name "$PROJECT"     --env-file .env     -f docker-compose.yml     build "$SERVICE"

docker compose     --project-name "$PROJECT"     --env-file .env     -f docker-compose.yml     up -d --no-deps --no-build "$SERVICE"

ok=0
for _ in $(seq 1 30); do
    if curl -fsS "$HEALTH_URL" 2>/dev/null | grep -qx 'ok'; then
        ok=1
        break
    fi
    sleep 1
done

if [[ "$ok" != 1 ]]; then
    docker compose         --project-name "$PROJECT"         --env-file .env         -f docker-compose.yml         logs --tail=100 "$SERVICE" >&2 || true
    die "recovered bot failed health check; rescue copy: $rescue"
fi

cid="$(docker compose --project-name "$PROJECT" --env-file .env -f docker-compose.yml ps -q "$SERVICE")"
docker exec -i "$cid" python - <<'PY'
import sqlite3
db = sqlite3.connect("/app/data/bot.sqlite3")
try:
    result = db.execute("PRAGMA quick_check").fetchone()[0]
finally:
    db.close()
print("DB=" + result)
if result != "ok":
    raise SystemExit(1)
PY

current_version="$(docker exec "$cid" python -c 'from version import APP_VERSION; print(APP_VERSION)')"
[[ "$current_version" == "$target_version" ]] \
    || die "recovered container APP_VERSION=$current_version, expected $target_version; rescue copy: $rescue"

./scripts/deploy-release.sh --status \
    || die "recovered deployment failed status checks; rescue copy: $rescue"

printf 'Recovery bootstrap complete.\n'
printf 'Release: %s\n' "$RELEASE"
printf 'APP_VERSION: %s\n' "$current_version"
printf 'Rescue copy: %s\n' "$rescue"
printf 'HOST_CONTROL_TARGETS and NODE_BACKUP_TARGETS were disabled intentionally.\n'
printf 'Re-enroll Host Control and re-validate direct node admin targets before enabling them.\n'
