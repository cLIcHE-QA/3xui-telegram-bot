#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
    cat <<'USAGE'
Usage:
  bash scripts/onboard-direct-node.sh prepare \
    --alias DE --host-id de --name Germany \
    --listen-ip 203.0.113.10 --source-ip 198.51.100.20 \
    --public-host panel-de.example.com \
    [--proxy-port 18443] [--bundle /root/3xui-host-control-bundle.tar.gz] \
    [--copy-to root@203.0.113.10] [--ssh-port 22]

  bash scripts/onboard-direct-node.sh bind \
    --node-enrollment /root/3xui-node-de.env \
    --admin-enrollment /root/3xui-node-admin-de.env \
    --host-control-enrollment /root/3xui-host-control-de.env \
    [--env .env] [--apply]

prepare:
  Builds the secret-free Host Control bundle and prints the exact remote install command.
  With --copy-to, copies only the bundle and checksum via scp; it never copies secrets.

bind:
  Without --apply, runs node preflight and, when NODE_ID is already known, importer preflights.
  With --apply, registers/reuses the node, captures NODE_ID, preflights both privileged bindings,
  imports direct-admin + Host Control with the same NODE_ID, and recreates only the bot service once.

Secret-bearing enrollment files are never printed by this wrapper.
USAGE
}

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
need_cmd() { command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"; }
need_file() { [[ -f "$1" ]] || die "file not found: $1"; }
valid_alias() { [[ "$1" =~ ^[A-Z0-9][A-Z0-9_]{0,31}$ ]]; }
valid_host_id() { [[ "$1" =~ ^[a-z0-9][a-z0-9_-]{0,31}$ ]]; }
valid_port() { [[ "$1" =~ ^[0-9]+$ ]] && (( "$1" >= 1024 && "$1" <= 65535 )); }

print_remote_command() {
    local alias="$1" host_id="$2" name="$3" listen_ip="$4" source_ip="$5"
    local public_host="$6" cert="$7" key="$8" proxy_port="$9"
    printf '  cd /root/3xui-host-control-install && '
    printf './scripts/setup-host-control-endpoint.sh remote'
    printf ' --alias %q' "$alias"
    printf ' --host-id %q' "$host_id"
    printf ' --name %q' "$name"
    printf ' --listen-ip %q' "$listen_ip"
    printf ' --source-ip %q' "$source_ip"
    printf ' --public-host %q' "$public_host"
    printf ' --cert %q' "$cert"
    printf ' --key %q' "$key"
    printf ' --proxy-port %q --apply-ufw\n' "$proxy_port"
}

prepare() {
    local alias="" host_id="" name="" listen_ip="" source_ip="" public_host=""
    local proxy_port=18443 bundle=/root/3xui-host-control-bundle.tar.gz
    local copy_to="" ssh_port=22 cert="" key=""

    while [[ "$#" -gt 0 ]]; do
        case "$1" in
            --alias) [[ "$#" -ge 2 ]] || die "missing value for --alias"; alias="${2^^}"; shift 2 ;;
            --host-id) [[ "$#" -ge 2 ]] || die "missing value for --host-id"; host_id="${2,,}"; shift 2 ;;
            --name) [[ "$#" -ge 2 ]] || die "missing value for --name"; name="$2"; shift 2 ;;
            --listen-ip) [[ "$#" -ge 2 ]] || die "missing value for --listen-ip"; listen_ip="$2"; shift 2 ;;
            --source-ip) [[ "$#" -ge 2 ]] || die "missing value for --source-ip"; source_ip="$2"; shift 2 ;;
            --public-host) [[ "$#" -ge 2 ]] || die "missing value for --public-host"; public_host="$2"; shift 2 ;;
            --cert) [[ "$#" -ge 2 ]] || die "missing value for --cert"; cert="$2"; shift 2 ;;
            --key) [[ "$#" -ge 2 ]] || die "missing value for --key"; key="$2"; shift 2 ;;
            --proxy-port) [[ "$#" -ge 2 ]] || die "missing value for --proxy-port"; proxy_port="$2"; shift 2 ;;
            --bundle) [[ "$#" -ge 2 ]] || die "missing value for --bundle"; bundle="$2"; shift 2 ;;
            --copy-to) [[ "$#" -ge 2 ]] || die "missing value for --copy-to"; copy_to="$2"; shift 2 ;;
            --ssh-port) [[ "$#" -ge 2 ]] || die "missing value for --ssh-port"; ssh_port="$2"; shift 2 ;;
            --help|-h) usage; exit 0 ;;
            *) die "unknown prepare argument: $1" ;;
        esac
    done

    [[ -n "$alias" && -n "$host_id" && -n "$name" && -n "$listen_ip" && -n "$source_ip" && -n "$public_host" ]] \
        || die "prepare requires --alias, --host-id, --name, --listen-ip, --source-ip and --public-host"
    valid_alias "$alias" || die "invalid --alias"
    valid_host_id "$host_id" || die "invalid --host-id"
    valid_port "$proxy_port" || die "invalid --proxy-port"
    [[ "$ssh_port" =~ ^[0-9]+$ ]] && (( ssh_port >= 1 && ssh_port <= 65535 )) || die "invalid --ssh-port"
    [[ "$bundle" = /* ]] || die "--bundle must be an absolute path"

    [[ -n "$cert" ]] || cert="/etc/letsencrypt/live/$public_host/fullchain.pem"
    [[ -n "$key" ]] || key="/etc/letsencrypt/live/$public_host/privkey.pem"

    need_cmd bash
    cd "$ROOT"
    bash scripts/build-host-control-bundle.sh "$bundle"

    if [[ -n "$copy_to" ]]; then
        need_cmd scp
        scp -P "$ssh_port" "$bundle" "$bundle.sha256" "$copy_to:/root/"
        printf 'Bundle copied to %s.\n' "$copy_to"
    fi

    printf '\nRemote VPS steps (run as root):\n'
    printf '  mkdir -p /root/3xui-host-control-install\n'
    printf '  cd /root && sha256sum -c %q && tar -xzf %q -C /root/3xui-host-control-install\n' "$(basename "$bundle").sha256" "$(basename "$bundle")"
    print_remote_command "$alias" "$host_id" "$name" "$listen_ip" "$source_ip" "$public_host" "$cert" "$key" "$proxy_port"
    printf '\nThen copy /root/3xui-host-control-%s.env back to Master through a protected channel.\n' "${alias,,}"
    printf 'Do not cat or paste that file: it contains the Host Control token.\n'
}

extract_node_id() {
    sed -nE 's/.*NODE_ID=([0-9]+).*/\1/p' | tail -n 1
}

bind() {
    local node_enrollment="" admin_enrollment="" host_control_enrollment=""
    local env_path=.env apply=0

    while [[ "$#" -gt 0 ]]; do
        case "$1" in
            --node-enrollment) [[ "$#" -ge 2 ]] || die "missing value for --node-enrollment"; node_enrollment="$2"; shift 2 ;;
            --admin-enrollment) [[ "$#" -ge 2 ]] || die "missing value for --admin-enrollment"; admin_enrolment="$2"; shift 2 ;;
            --host-control-enrollment) [[ "$#" -ge 2 ]] || die "missing value for --host-control-enrollment": host_control_enrolment="$2"; shift 2 ;;
            --env) [[ "$#" -ge 2 ]] || die "missing value for --env"; env_path="$2"; shift 2 ;;
            --apply) apply=1; shift ;;
            --help|-h) usage; exit 0 ;;
            *) die "unknown bind argument: $1" ;;
        esac
    done

    [[ -n "$node_enrollment" && -n "$admin_enrollment" && -n "$host_control_enrollment" ]] \
        || die "bind requires --node-enrollment, --admin-enrollment and --host-control-enrollment"
    for path in "$node_enrollment" "$admin_enrollment" "$host_control_enrollment" "$env_path"; do
        need_file "$path"
    done
    need_cmd python3

    cd "$ROOT"

    printf 'Node preflight...\n'
    local preflight node_id=""
    preflight="$(python3 scripts/onboard-node.py "$node_enrollment" --env "$env_path")"
    printf '%s\n' "$preflight"
    node_id="$(printf '%s\n' "$preflight" | extract_node_id)"

    if [[ "$apply" -ne 1 ]]; then
        if [[ -n "$node_id" ]]; then
            printf 'Existing NODE_ID=%s found; checking privileged enrollments...\n' "$node_id"
            python3 scripts/import-node-admin-target.py "$admin_enrollment" --env "$env_path" --node-id "$node_id" --check-only
            python3 scripts/import-host-control-enrollment.py "$host_control_enrollment" --env "$env_path" --node-id "$node_id" --check-only
        else
            printf 'Preflight only: no mutation performed. Re-run the same bind command with --apply after review.\n'
        fi
        return 0
    fi

    printf 'Registering or reusing node...\n'
    local applied
    applied="$(python3 scripts/onboard-node.py "$node_enrollment" --env "$env_path" --apply)"
    printf '%s\n' "$applied"
    node_id="$(printf '%s\n' "$applied" | extract_node_id)"
    [[ -n "$node_id" ]] || die "onboard-node.py did not return NODE_ID; no privileged bindings were changed"

    printf 'Privileged enrollment preflights for NODE_ID=%s...\n' "$node_id"
    python3 scripts/import-node-admin-target.py "$admin_enrollment" --env "$env_path" --node-id "$node_id" --check-only
    python3 scripts/import-host-control-enrollment.py "$host_control_enrollment" --env "$env_path" --node-id "$node_id" --check-only

    printf 'Importing direct-admin binding...\n'
    python3 scripts/import-node-admin-target.py "$admin_enrollment" --env "$env_path" --node-id "$node_id"

    printf 'Importing Host Control binding and recreating only bot...\n'
    python3 scripts/import-host-control-enrollment.py "$host_control_enrollment" --env "$env_path" --node-id "$node_id" --recreate-bot

    printf '\nREADY candidate: NODE_ID=%s.\n' "$node_id"
    printf 'Verify in Telegram: Infrastructure -> Nodes -> node -> Readiness.\n'
    printf 'Expected: Direct Panel API online/node_id, Host Control running/node_id, Runtime readiness ready, Stable identity node_id.\n'
}

case "${1:-}" in
    prepare) shift; prepare "$@" ;;
    bind) shift; bind "$@" ;;
    --help|-h) usage ;;
    "") usage >&2; exit 2 ;;
    *) die "first argument must be prepare or bind" ;;
esac
