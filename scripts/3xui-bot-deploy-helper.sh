#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT="/opt/3xui-bot/3xui-telegram-bot"
DEPLOY_SCRIPT="$REPO_ROOT/scripts/deploy-release.sh"
EXPECTED_REPOSITORY="cLIcHE-QA/3xui-telegram-bot"
SSH_KEY="/etc/3xui-deploy-agent/deploy-key"
PROJECT="3xui-telegram-bot"
SERVICE="bot"
HEALTH_URL="http://127.0.0.1:18080/healthz"
BACKUP_ROOT="/opt/3xui-bot/deploy-backups"
LOCK_FILE="/tmp/${PROJECT}.deploy-release.lock"
RELEASE_RE='^v[0-9]+\.[0-9]+\.[0-9]+$'

die() {
    printf 'ERROR_CODE=%s\n' "$1"
    exit "${2:-1}"
}

need_file() {
    [[ -f "$1" ]] || die "missing_required_file"
}

cd "$REPO_ROOT" 2>/dev/null || die "repo_unavailable"
need_file "$DEPLOY_SCRIPT"
need_file "$SSH_KEY"

export HOME="/root"
export DEPLOY_REPO_ROOT="$REPO_ROOT"
export DEPLOY_PROJECT="$PROJECT"
export DEPLOY_SERVICE="$SERVICE"
export DEPLOY_HEALTH_URL="$HEALTH_URL"
export DEPLOY_BACKUP_ROOT="$BACKUP_ROOT"
export DEPLOY_SSH_KEY="$SSH_KEY"
export DEPLOY_EXPECTED_REPOSITORY="$EXPECTED_REPOSITORY"
export DEPLOY_LOCK_FILE="$LOCK_FILE"
unset DEPLOY_ALLOW_DOWNGRADE

validate_origin() {
    local origin
    origin="$(git remote get-url origin 2>/dev/null || true)"
    case "$origin" in
        "git@github.com:${EXPECTED_REPOSITORY}.git"|        "ssh://git@github.com/${EXPECTED_REPOSITORY}.git"|        "https://github.com/${EXPECTED_REPOSITORY}.git"|        "https://github.com/${EXPECTED_REPOSITORY}") ;;
        *) die "unexpected_origin" ;;
    esac
}

fetch_metadata() {
    validate_origin
    GIT_SSH_COMMAND="ssh -i $SSH_KEY -o IdentitiesOnly=yes"         git fetch origin main --tags --prune >/dev/null 2>&1 || die "git_fetch_failed"
}

current_release() {
    git describe --tags --exact-match HEAD 2>/dev/null || printf 'untagged'
}

version_from_tag() {
    git show "$1:version.py" 2>/dev/null         | sed -nE 's/^APP_VERSION[[:space:]]*=[[:space:]]*"([^"]+)"/\1/p'         | head -n 1
}

validate_release() {
    local release="$1"
    [[ "$release" =~ $RELEASE_RE ]] || die "invalid_release"
    fetch_metadata

    local tag_sha target_version
    tag_sha="$(git rev-parse -q --verify "refs/tags/${release}^{commit}" 2>/dev/null || true)"
    [[ -n "$tag_sha" ]] || die "release_not_found"
    git merge-base --is-ancestor "$tag_sha" origin/main || die "release_not_in_main"
    target_version="$(version_from_tag "$release")"
    [[ -n "$target_version" && "v$target_version" == "$release" ]] || die "release_version_mismatch"

    printf 'TARGET_RELEASE=%s\n' "$release"
    printf 'TARGET_SHA=%s\n' "$tag_sha"
    printf 'TARGET_VERSION=%s\n' "$target_version"
}

status_cmd() {
    local output rc=0
    set +e
    output="$("$DEPLOY_SCRIPT" --status 2>&1)"
    rc=$?
    set -e

    local tag sha version health db tcp
    tag="$(printf '%s\n' "$output" | sed -n 's/^Git tag: //p' | tail -n1)"
    sha="$(printf '%s\n' "$output" | sed -n 's/^Git SHA: //p' | tail -n1)"
    version="$(printf '%s\n' "$output" | sed -n 's/^Bot version: //p' | tail -n1)"
    health="$(printf '%s\n' "$output" | sed -n 's/^Health: //p' | tail -n1)"
    db="$(printf '%s\n' "$output" | sed -n 's/^DB: //p' | tail -n1)"
    tcp="$(printf '%s\n' "$output" | sed -n 's/^3x-ui connectivity: //p' | tail -n1)"

    printf 'CURRENT_RELEASE=%s\n' "${tag:-unknown}"
    printf 'CURRENT_SHA=%s\n' "${sha:-unknown}"
    printf 'BOT_VERSION=%s\n' "${version:-unknown}"
    printf 'HEALTH=%s\n' "${health:-failed}"
    printf 'DB=%s\n' "${db:-failed}"
    printf 'CONNECTIVITY=%s\n' "${tcp:-failed}"

    if [[ "$rc" -eq 0 && "$health" == ok && "$db" == ok && "$tcp" == ok ]]; then
        printf 'STATUS_OK=1\n'
        return 0
    fi
    printf 'STATUS_OK=0\n'
    return 1
}

latest_cmd() {
    fetch_metadata
    local release
    release="$(
        git tag --merged origin/main --list 'v[0-9]*.[0-9]*.[0-9]*'           | while IFS= read -r tag; do
                [[ "$tag" =~ $RELEASE_RE ]] || continue
                version="$(version_from_tag "$tag")"
                [[ "v$version" == "$tag" ]] || continue
                printf '%s\n' "$tag"
            done           | sort -V           | tail -n1
    )"
    [[ -n "$release" ]] || die "no_published_release"
    printf 'LATEST_RELEASE=%s\n' "$release"
}

preflight_cmd() {
    local release="$1"
    validate_release "$release"

    [[ -d .git ]] || die "repo_unavailable"
    [[ -f .env ]] || die "env_missing"
    [[ -f docker-compose.yml ]] || die "compose_missing"
    git diff --quiet || die "working_tree_dirty"
    git diff --cached --quiet || die "index_dirty"

    local cid current target downgrade=0
    cid="$(docker compose --project-name "$PROJECT" --env-file .env -f docker-compose.yml ps -q "$SERVICE" 2>/dev/null || true)"
    [[ -n "$cid" ]] || die "container_not_running"
    [[ "$(docker inspect "$cid" --format '{{.State.Running}}' 2>/dev/null || true)" == true ]] || die "container_not_running"

    local tmp="/tmp/3xui-deploy-preflight-status.$$"
    if status_cmd >"$tmp"; then
        cat "$tmp"
        rm -f "$tmp"
    else
        rm -f "$tmp"
        die "current_status_failed"
    fi

    current="$(current_release)"
    target="$release"
    if [[ "$current" =~ $RELEASE_RE && "$current" != "$target" ]]; then
        if [[ "$(printf '%s\n%s\n' "$current" "$target" | sort -V | tail -n1)" != "$target" ]]; then
            downgrade=1
        fi
    fi
    printf 'DOWNGRADE=%s\n' "$downgrade"
    printf 'PREFLIGHT_OK=1\n'
}

notes_cmd() {
    local release="$1"
    validate_release "$release" >/dev/null
    local title="/tmp/3xui-deploy-title.$$"
    local body="/tmp/3xui-deploy-body.$$"
    python3 scripts/render-release-notes.py         --version "${release#v}"         --commit "$(git rev-parse "refs/tags/${release}^{commit}")"         --title-out "$title"         --body-out "$body" >/dev/null 2>&1 || die "release_notes_failed"
    cat "$title"
    printf '\n'
    cat "$body"
    rm -f "$title" "$body"
}

deploy_cmd() {
    local release="$1"
    local allow="${2:-}"
    [[ -z "$allow" || "$allow" == "--allow-downgrade" ]] || die "invalid_argument"
    validate_release "$release" >/dev/null

    if [[ "$allow" == "--allow-downgrade" ]]; then
        export DEPLOY_ALLOW_DOWNGRADE=1
    fi

    printf 'Creating deployment backup...\n'

    local output rc=0
    set +e
    output="$("$DEPLOY_SCRIPT" "$release" 2>&1)"
    rc=$?
    set -e
    printf '%s\n' "$output"

    if [[ "$rc" -ne 0 ]]; then
        exit "$rc"
    fi
    printf 'DEPLOY_OK\n'
}

case "${1:-}" in
    status)
        [[ "$#" -eq 1 ]] || die "invalid_argument"
        status_cmd
        ;;
    latest)
        [[ "$#" -eq 1 ]] || die "invalid_argument"
        latest_cmd
        ;;
    preflight)
        [[ "$#" -eq 2 ]] || die "invalid_argument"
        preflight_cmd "$2"
        ;;
    notes)
        [[ "$#" -eq 2 ]] || die "invalid_argument"
        notes_cmd "$2"
        ;;
    deploy)
        [[ "$#" -eq 2 || "$#" -eq 3 ]] || die "invalid_argument"
        deploy_cmd "$2" "${3:-}"
        ;;
    *)
        die "invalid_command" 2
        ;;
esac
