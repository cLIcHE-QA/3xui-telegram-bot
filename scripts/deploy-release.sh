#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT="${DEPLOY_PROJECT:-3xui-telegram-bot}"
SERVICE="${DEPLOY_SERVICE:-bot}"
HEALTH_URL="${DEPLOY_HEALTH_URL:-http://127.0.0.1:18080/healthz}"
BACKUP_ROOT="${DEPLOY_BACKUP_ROOT:-/opt/3xui-bot/deploy-backups}"
SSH_KEY="${DEPLOY_SSH_KEY:-$HOME/.ssh/3xui_bot_deploy}"
SSH_KNOWN_HOSTS="${DEPLOY_SSH_KNOWN_HOSTS:-$HOME/.ssh/known_hosts}"
EXPECTED_REPOSITORY="${DEPLOY_EXPECTED_REPOSITORY:-cLIcHE-QA/3xui-telegram-bot}"
DEFAULT_SUBNET="172.19.0.0/16"
LOCK_FILE="${DEPLOY_LOCK_FILE:-${BACKUP_ROOT}/.${PROJECT}.deploy-release.lock}"

usage() {
    cat <<'USAGE'
Usage:
  ./scripts/deploy-release.sh vX.Y.Z
  ./scripts/deploy-release.sh --status
  ./scripts/deploy-release.sh --help

Environment overrides:
  DEPLOY_REPO_ROOT             repository directory when the script is run outside the checkout
  DEPLOY_PROJECT               Docker Compose project name (default: 3xui-telegram-bot)
  DEPLOY_SERVICE               Compose service name (default: bot)
  DEPLOY_HEALTH_URL            local health endpoint (default: http://127.0.0.1:18080/healthz)
  DEPLOY_BACKUP_ROOT           deployment backup directory (default: /opt/3xui-bot/deploy-backups)
  DEPLOY_SSH_KEY               read-only GitHub deploy key (default: ~/.ssh/3xui_bot_deploy)
  DEPLOY_SSH_KNOWN_HOSTS        SSH known_hosts used for host-key verification
  DEPLOY_EXPECTED_REPOSITORY   expected origin repository (default: cLIcHE-QA/3xui-telegram-bot)
  DEPLOY_ALLOW_DOWNGRADE=1     allow deploying a lower semantic version intentionally

The script never runs docker compose down, docker system prune, 3x-ui updates, Xray updates,
or automatic database rollback.
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
    if [[ -n "${DEPLOY_REPO_ROOT:-}" ]]; then
        printf '%s\n' "$DEPLOY_REPO_ROOT"
        return
    fi

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

ROOT="$(resolve_root)"

compose() {
    docker compose \
        --project-name "$PROJECT" \
        --env-file "$ROOT/.env" \
        -f "$ROOT/docker-compose.yml" \
        "$@"
}

container_id() {
    compose ps -q "$SERVICE"
}

read_env_value() {
    local key="$1"
    local value
    value="$(sed -nE "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*(.*)$/\\1/p" "$ROOT/.env" | tail -n 1)"
    value="${value%$'\r'}"
    if [[ ${#value} -ge 2 ]]; then
        if [[ "${value:0:1}" == '"' && "${value: -1}" == '"' ]]; then
            value="${value:1:${#value}-2}"
        elif [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
            value="${value:1:${#value}-2}"
        fi
    fi
    printf '%s\n' "$value"
}

check_health() {
    curl -fsS "$HEALTH_URL" 2>/dev/null | grep -qx 'ok'
}

check_db() {
    local cid="$1"
    docker exec -i "$cid" python - <<'PY'
import sqlite3

db = sqlite3.connect('/app/data/bot.sqlite3')
try:
    result = db.execute('PRAGMA quick_check').fetchone()[0]
finally:
    db.close()

print('DB=' + result)
if result != 'ok':
    raise SystemExit(1)
PY
}

check_upstream_tcp() {
    local cid="$1"
    docker exec -i "$cid" python - <<'PY'
import os
import socket
from urllib.parse import urlsplit

url = urlsplit(os.environ['SUBSCRIPTION_URL_TEMPLATE'])
host = url.hostname
if not host:
    raise SystemExit('SUBSCRIPTION_URL_TEMPLATE has no hostname')
port = url.port or (443 if url.scheme == 'https' else 80)

with socket.create_connection((host, port), 5):
    pass

print('3XUI_TCP=ok')
PY
}

network_subnet() {
    local network="${PROJECT}_default"
    docker network inspect "$network" --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null
}

status() {
    cd "$ROOT"
    test -f .env || die "$ROOT/.env not found"
    test -f docker-compose.yml || die "$ROOT/docker-compose.yml not found"

    local cid sha tag app_version subnet health db_state tcp_state
    sha="$(git rev-parse HEAD 2>/dev/null || printf 'unknown')"
    tag="$(git describe --tags --exact-match HEAD 2>/dev/null || printf 'untagged')"
    cid="$(container_id 2>/dev/null || true)"

    printf 'Git tag: %s\n' "$tag"
    printf 'Git SHA: %s\n' "$sha"

    if [[ -z "$cid" ]]; then
        printf 'Container: not running\n'
        return 1
    fi

    printf 'Container: running\n'
    printf 'RestartCount=%s\n' "$(docker inspect "$cid" --format '{{.RestartCount}}')"

    app_version="$(docker exec "$cid" python -c 'from version import APP_VERSION; print(APP_VERSION)' 2>/dev/null || printf 'unknown')"
    printf 'Bot version: %s\n' "$app_version"

    if check_health; then health=ok; else health=failed; fi
    printf 'Health: %s\n' "$health"

    db_state="$(check_db "$cid" 2>/dev/null | tail -n 1 | cut -d= -f2- || printf 'failed')"
    printf 'DB: %s\n' "$db_state"

    subnet="$(network_subnet || true)"
    printf 'Docker subnet: %s\n' "${subnet:-unknown}"

    if check_upstream_tcp "$cid" >/dev/null 2>&1; then tcp_state=ok; else tcp_state=failed; fi
    printf '3x-ui connectivity: %s\n' "$tcp_state"

    [[ "$health" == ok && "$db_state" == ok && "$tcp_state" == ok ]]
}

validate_origin() {
    local origin
    origin="$(git remote get-url origin)"
    case "$origin" in
        "git@github.com:${EXPECTED_REPOSITORY}.git"|\
        "ssh://git@github.com/${EXPECTED_REPOSITORY}.git"|\
        "https://github.com/${EXPECTED_REPOSITORY}.git"|\
        "https://github.com/${EXPECTED_REPOSITORY}") ;;
        *) die "unexpected origin: $origin" ;;
    esac
}

version_from_tag() {
    local release="$1"
    git show "$release:version.py" \
        | sed -nE 's/^APP_VERSION[[:space:]]*=[[:space:]]*"([^"]+)"/\1/p' \
        | head -n 1
}

prepare_container_permissions() {
    local helper="$ROOT/scripts/prepare-bot-container-permissions.sh"

    # Old releases do not have the least-privilege helper.
    [[ -f "$helper" ]] || return 0

    if [[ "${EUID}" -ne 0 ]]; then
        die "target release requires least-privilege host permissions; run 'sudo bash scripts/prepare-bot-container-permissions.sh' before deployment or use the root-owned Deploy Agent"
    fi

    need_cmd setfacl
    printf 'Preparing least-privilege bot filesystem permissions...\n'
    (
        cd "$ROOT"
        ENV_FILE="$ROOT/.env" DATA_DIR="$ROOT/data" bash "$helper"
    )
}

backup_current_state() {
    local cid="$1"
    local release="$2"
    local stamp backup tmp

    stamp="$(date -u +%Y%m%d-%H%M%S)"
    backup="$BACKUP_ROOT/pre-${release}-${stamp}"
    tmp="/app/data/.deploy-release-backup.sqlite3"

    mkdir -p "$backup"
    chmod 700 "$backup"

    cp -a "$ROOT/.env" "$backup/.env"
    cp -a "$ROOT/docker-compose.yml" "$backup/docker-compose.yml"
    git rev-parse HEAD > "$backup/git-sha.txt"
    docker inspect "$cid" --format '{{.Image}}' > "$backup/docker-image-id.txt"
    docker inspect "$cid" --format '{{.Config.Image}}' > "$backup/docker-image-name.txt"

    docker exec -i "$cid" python - <<'PY'
import sqlite3
from pathlib import Path

src = '/app/data/bot.sqlite3'
dst = '/app/data/.deploy-release-backup.sqlite3'
Path(dst).unlink(missing_ok=True)

source = sqlite3.connect(src)
target = sqlite3.connect(dst)
try:
    source.backup(target)
finally:
    target.close()
    source.close()

check = sqlite3.connect(dst)
try:
    result = check.execute('PRAGMA quick_check').fetchone()[0]
finally:
    check.close()

if result != 'ok':
    raise SystemExit('SQLite backup quick_check failed: ' + result)
PY

    printf 'SQLITE_BACKUP=ok\n' >&2
    docker cp "$cid:$tmp" "$backup/bot.sqlite3"
    docker exec "$cid" rm -f "$tmp"
    chmod 600 "$backup/.env" "$backup/bot.sqlite3"

    printf '%s\n' "$backup"
}

main() {
    case "${1:-}" in
        --help|-h)
            usage
            return 0
            ;;
        --status)
            need_cmd git
            need_cmd docker
            need_cmd curl
            status
            return
            ;;
        '')
            usage >&2
            return 2
            ;;
    esac

    local release="$1"
    [[ "$release" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "release must look like v4.9.2"

    need_cmd git
    need_cmd docker
    need_cmd curl
    need_cmd flock

    cd "$ROOT"
    test -d .git || die "$ROOT is not a Git working tree"
    test -f .env || die "$ROOT/.env not found"
    test -f docker-compose.yml || die "$ROOT/docker-compose.yml not found"
    test -f "$SSH_KEY" || die "deploy key not found: $SSH_KEY"
    mkdir -p "$BACKUP_ROOT"

    exec 9>"$LOCK_FILE"
    flock -n 9 || die "another deployment is already running"

    validate_origin

    git diff --quiet || die "tracked working tree has local changes"
    git diff --cached --quiet || die "index has local changes"

    local current_cid current_tag current_sha current_version target_version tag_sha
    local expected_subnet actual_subnet backup new_cid

    current_cid="$(container_id)"
    [[ -n "$current_cid" ]] || die "current bot container is not running"
    [[ "$(docker inspect "$current_cid" --format '{{.State.Running}}')" == true ]] || die "current bot container is not running"

    current_sha="$(git rev-parse HEAD)"
    current_tag="$(git describe --tags --exact-match HEAD 2>/dev/null || true)"

    check_health || die "current bot health check failed"
    check_db "$current_cid"
    check_upstream_tcp "$current_cid"

    printf 'Fetching release metadata...\n'
    [[ -f "$SSH_KNOWN_HOSTS" ]] || die "SSH known_hosts not found: $SSH_KNOWN_HOSTS"
    GIT_SSH_COMMAND="ssh -i $SSH_KEY -o IdentitiesOnly=yes -o UserKnownHostsFile=$SSH_KNOWN_HOSTS" \
        git fetch origin main --tags --prune

    tag_sha="$(git rev-parse -q --verify "refs/tags/${release}^{commit}")" || die "release tag not found: $release"
    git merge-base --is-ancestor "$tag_sha" origin/main || die "$release is not contained in origin/main"

    target_version="$(version_from_tag "$release")"
    [[ -n "$target_version" ]] || die "APP_VERSION not found in $release"
    [[ "v$target_version" == "$release" ]] || die "$release does not match APP_VERSION=$target_version"

    if [[ "$current_tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ && "$current_tag" != "$release" ]]; then
        if [[ "$(printf '%s\n%s\n' "$current_tag" "$release" | sort -V | tail -n 1)" != "$release" ]]; then
            [[ "${DEPLOY_ALLOW_DOWNGRADE:-0}" == 1 ]] || die "downgrade $current_tag -> $release requires DEPLOY_ALLOW_DOWNGRADE=1"
        fi
    fi

    printf 'Current: %s (%s)\n' "${current_tag:-untagged}" "$current_sha"
    printf 'Target:  %s (%s)\n' "$release" "$tag_sha"

    backup="$(backup_current_state "$current_cid" "$release")"
    printf 'Backup: %s\n' "$backup"

    git checkout --detach "$release"
    [[ "$(git rev-parse HEAD)" == "$tag_sha" ]] || die "checkout did not land on release commit"

    compose config --quiet
    prepare_container_permissions

    expected_subnet="$(read_env_value BOT_DOCKER_SUBNET)"
    expected_subnet="${expected_subnet:-$DEFAULT_SUBNET}"
    actual_subnet="$(network_subnet || true)"
    if [[ -n "$actual_subnet" && "$actual_subnet" != "$expected_subnet" ]]; then
        die "existing Docker subnet is $actual_subnet, release expects $expected_subnet; network recreation requires a manual maintenance step"
    fi

    printf 'Building %s...\n' "$release"
    compose build "$SERVICE"

    printf 'Deploying %s...\n' "$release"
    compose up -d --no-deps --no-build --force-recreate "$SERVICE"

    printf 'Verifying %s...\n' "$release"
    new_cid="$(container_id)"
    [[ -n "$new_cid" ]] || die "new bot container was not created; backup: $backup"

    local ok=0
    for _ in $(seq 1 30); do
        if check_health; then
            ok=1
            break
        fi
        sleep 1
    done
    if [[ "$ok" != 1 ]]; then
        compose logs --tail=100 "$SERVICE" >&2 || true
        die "new release failed health check; no automatic rollback was attempted; backup: $backup"
    fi

    current_version="$(docker exec "$new_cid" python -c 'from version import APP_VERSION; print(APP_VERSION)')"
    [[ "$current_version" == "$target_version" ]] || die "container APP_VERSION=$current_version, expected $target_version; backup: $backup"

    check_db "$new_cid"
    check_upstream_tcp "$new_cid"

    actual_subnet="$(network_subnet || true)"
    [[ "$actual_subnet" == "$expected_subnet" ]] || die "Docker subnet=$actual_subnet, expected $expected_subnet; backup: $backup"

    printf '\nDEPLOY_OK\n'
    printf 'Production=%s\n' "$release"
    printf 'GitSHA=%s\n' "$tag_sha"
    printf 'APP_VERSION=%s\n' "$current_version"
    printf 'DockerSubnet=%s\n' "$actual_subnet"
    printf 'Backup=%s\n' "$backup"
    printf 'RestartCount=%s\n' "$(docker inspect "$new_cid" --format '{{.RestartCount}}')"
}

main "$@"
