#!/usr/bin/env bash
set -Eeuo pipefail

PROXY_SERVICE=3xui-host-control-proxy.service
PROXY_USER=3xui-hostproxy
PROXY_CONFIG=/etc/3xui-host-control/proxy-nginx.conf
PROXY_UNIT=/etc/systemd/system/3xui-host-control-proxy.service
PROXY_STATE=/var/lib/3xui-host-control-proxy
TLS_DIR=/etc/3xui-host-control/tls
TLS_SOURCE_STATE=/etc/3xui-host-control/tls-source.env
TLS_REFRESH_BIN=/usr/local/libexec/3xui-host-control-refresh-tls
TLS_REFRESH_SERVICE=/etc/systemd/system/3xui-host-control-tls-refresh.service
TLS_REFRESH_TIMER=/etc/systemd/system/3xui-host-control-tls-refresh.timer
UFW_STATE=/etc/3xui-host-control/ufw-managed.env

usage() {
    cat <<'USAGE'
Usage:
  sudo scripts/setup-host-control-endpoint.sh master \
    --alias MASTER --host-id master --name Master \
    --bridge-ip 172.19.0.1 --docker-subnet 172.19.0.0/16 \
    [--nginx-source /etc/nginx] [--proxy-port 18182] [--apply-ufw]

  sudo scripts/setup-host-control-endpoint.sh remote \
    --alias FI --host-id fi --name Finland \
    --listen-ip 203.0.113.10 --source-ip 198.51.100.20 \
    --public-host host-control-fi.example.com \
    --cert /path/fullchain.pem --key /path/privkey.pem \
    [--nginx-source /etc/nginx] [--proxy-port 18443] [--apply-ufw]

Creates a separate restricted nginx process. Existing nginx/MTProxy configs are not edited.
A mode-0600 enrollment file is written; it contains the dedicated token.
The token is never printed.
USAGE
}

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
need_root() { [[ "$(id -u)" -eq 0 ]] || die "run as root"; }
need_cmd() { command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"; }
need_value() { [[ "$#" -ge 2 ]] || die "missing value for $1"; }

valid_alias() { [[ "$1" =~ ^[A-Z0-9][A-Z0-9_]{0,31}$ ]]; }
valid_host_id() { [[ "$1" =~ ^[a-z0-9][a-z0-9_-]{0,31}$ ]]; }
valid_port() { [[ "$1" =~ ^[0-9]+$ ]] && (( "$1" >= 1024 && "$1" <= 65535 )); }

valid_ipv4() {
    python3 - "$1" <<'PY' >/dev/null
import ipaddress, sys
ipaddress.IPv4Address(sys.argv[1])
PY
}

valid_private_ipv4() {
    python3 - "$1" <<'PY' >/dev/null
import ipaddress, sys
ip = ipaddress.IPv4Address(sys.argv[1])
if not (ip.is_private or ip.is_loopback or ip.is_link_local):
    raise SystemExit(1)
PY
}

valid_network4() {
    python3 - "$1" <<'PY' >/dev/null
import ipaddress, sys
ipaddress.IPv4Network(sys.argv[1], strict=False)
PY
}

repo_root() {
    local d
    d="$(cd -- "$(dirname -- "$0")" && pwd)"
    cd "$d/.." && pwd
}

find_nginx() {
    local x
    for x in /opt/mtproxyl-nginx/sbin/nginx /usr/sbin/nginx; do
        [[ -x "$x" ]] && { printf '%s\n' "$x"; return 0; }
    done
    x="$(command -v nginx 2>/dev/null || true)"
    [[ -n "$x" && -x "$x" ]] || return 1
    printf '%s\n' "$x"
}

MODE=""
[[ "$#" -gt 0 ]] && MODE="$1"
if [[ "$MODE" == "--help" || "$MODE" == "-h" ]]; then usage; exit 0; fi
[[ -n "$MODE" ]] || { usage >&2; exit 2; }
shift
[[ "$MODE" == "master" || "$MODE" == "remote" ]] || die "mode must be master or remote"

ALIAS=""
HOST_ID=""
NAME=""
BRIDGE_IP=""
DOCKER_SUBNET=""
LISTEN_IP=""
SOURCE_IP=""
PUBLIC_HOST=""
CERT_PATH=""
KEY_PATH=""
PROXY_PORT=""
APPLY_UFW=0
ENROLLMENT_FILE=""
NGINX_SOURCE=""

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --alias) need_value "$@"; ALIAS="$2"; shift 2 ;;
        --host-id) need_value "$@"; HOST_ID="$2"; shift 2 ;;
        --name) need_value "$@"; NAME="$2"; shift 2 ;;
        --bridge-ip) need_value "$@"; BRIDGE_IP="$2"; shift 2 ;;
        --docker-subnet) need_value "$@"; DOCKER_SUBNET="$2"; shift 2 ;;
        --listen-ip) need_value "$@"; LISTEN_IP="$2"; shift 2 ;;
        --source-ip) need_value "$@"; SOURCE_IP="$2"; shift 2 ;;
        --public-host) need_value "$@"; PUBLIC_HOST="$2"; shift 2 ;;
        --cert) need_value "$@"; CERT_PATH="$2"; shift 2 ;;
        --key) need_value "$@"; KEY_PATH="$2"; shift 2 ;;
        --proxy-port) need_value "$@"; PROXY_PORT="$2"; shift 2 ;;
        --enrollment-file) need_value "$@"; ENROLLMENT_FILE="$2"; shift 2 ;;
        --nginx-source) need_value "$@"; NGINX_SOURCE="$2"; shift 2 ;;
        --apply-ufw) APPLY_UFW=1; shift ;;
        --help|-h) usage; exit 0 ;;
        *) die "unknown argument: $1" ;;
    esac
done

need_root
need_cmd python3
need_cmd systemctl
need_cmd install
need_cmd ss
[[ -x /usr/sbin/useradd ]] || die "required executable not found: /usr/sbin/useradd"

valid_alias "$ALIAS" || die "invalid --alias"
valid_host_id "$HOST_ID" || die "invalid --host-id"
[[ -n "$NAME" && "$NAME" != *$'\n'* && "$NAME" != *$'\r'* ]] || die "invalid --name"

ROOT="$(repo_root)"
INSTALL_AGENT="$ROOT/scripts/install-host-control-agent.sh"
[[ -x "$INSTALL_AGENT" ]] || die "missing executable $INSTALL_AGENT"
NGINX_BIN="$(find_nginx)" || die "nginx executable not found"
[[ "$NGINX_BIN" = /* ]] || die "nginx path must be absolute"

if [[ -z "$ENROLLMENT_FILE" ]]; then
    alias_lower="$(printf '%s' "$ALIAS" | tr 'A-Z' 'a-z')"
    ENROLLMENT_FILE="/root/3xui-host-control-$alias_lower.env"
fi
[[ "$ENROLLMENT_FILE" = /* ]] || die "--enrollment-file must be absolute"

if [[ "$MODE" == "master" ]]; then
    [[ -n "$PROXY_PORT" ]] || PROXY_PORT=18182
    valid_port "$PROXY_PORT" || die "invalid --proxy-port"
    valid_ipv4 "$BRIDGE_IP" || die "invalid --bridge-ip"
    valid_private_ipv4 "$BRIDGE_IP" || die "--bridge-ip must be private/local"
    valid_network4 "$DOCKER_SUBNET" || die "invalid --docker-subnet"
else
    [[ -n "$PROXY_PORT" ]] || PROXY_PORT=18443
    valid_port "$PROXY_PORT" || die "invalid --proxy-port"
    valid_ipv4 "$LISTEN_IP" || die "invalid --listen-ip"
    valid_ipv4 "$SOURCE_IP" || die "invalid --source-ip"
    [[ "$LISTEN_IP" != "0.0.0.0" ]] || die "wildcard listen is forbidden"
    [[ -n "$PUBLIC_HOST" && "$PUBLIC_HOST" =~ ^[A-Za-z0-9.-]+$ ]] || die "invalid --public-host"
    [[ "$CERT_PATH" = /* ]] || die "--cert must be an absolute path"
    [[ "$KEY_PATH" = /* ]] || die "--key must be an absolute path"
    [[ -f "$CERT_PATH" ]] || die "TLS certificate not found"
    [[ -f "$KEY_PATH" ]] || die "TLS private key not found"
    need_cmd openssl
    openssl x509 -in "$CERT_PATH" -noout -checkhost "$PUBLIC_HOST" >/dev/null 2>&1 \
        || die "TLS certificate does not match --public-host"
fi

printf 'Installing restricted Host Control Agent for %s...\n' "$HOST_ID"
if [[ -n "$NGINX_SOURCE" ]]; then
    "$INSTALL_AGENT" "$HOST_ID" --nginx-source "$NGINX_SOURCE"
else
    "$INSTALL_AGENT" "$HOST_ID"
fi
systemctl is-active --quiet 3xui-host-control.service || die "agent is not active"

if ! id "$PROXY_USER" >/dev/null 2>&1; then
    /usr/sbin/useradd --system --home-dir /nonexistent --shell /usr/sbin/nologin "$PROXY_USER"
fi

install -d -o root -g root -m 0755 /etc/3xui-host-control
install -d -o 3xui-hostctl -g 3xui-hostctl -m 0700 /var/lib/3xui-host-control
install -d -o "$PROXY_USER" -g "$PROXY_USER" -m 0700 "$PROXY_STATE"

if [[ "$MODE" == "remote" ]]; then
    REFRESH_SOURCE="$ROOT/scripts/refresh-host-control-tls.sh"
    [[ -f "$REFRESH_SOURCE" ]] || die "missing TLS refresh helper: $REFRESH_SOURCE"
    install -d -o root -g root -m 0755 /usr/local/libexec
    install -o root -g root -m 0755 "$REFRESH_SOURCE" "$TLS_REFRESH_BIN"

    install -d -o root -g "$PROXY_USER" -m 0750 "$TLS_DIR"
    install -o root -g "$PROXY_USER" -m 0640 "$CERT_PATH" "$TLS_DIR/fullchain.pem"
    install -o root -g "$PROXY_USER" -m 0640 "$KEY_PATH" "$TLS_DIR/privkey.pem"

    STMP="$(mktemp /etc/3xui-host-control/tls-source.env.XXXXXX)"
    trap 'rm -f "$STMP"' EXIT HUP INT TERM
    {
        printf 'CERT_PATH=%s\n' "$CERT_PATH"
        printf 'KEY_PATH=%s\n' "$KEY_PATH"
        printf 'PUBLIC_HOST=%s\n' "$PUBLIC_HOST"
    } > "$STMP"
    chmod 0600 "$STMP"
    chown root:root "$STMP"
    mv "$STMP" "$TLS_SOURCE_STATE"
    trap - EXIT HUP INT TERM

    cat > "$TLS_REFRESH_SERVICE" <<UNIT
[Unit]
Description=Refresh TLS material for 3x-ui Host Control proxy
After=local-fs.target

[Service]
Type=oneshot
ExecStart=$TLS_REFRESH_BIN
UNIT
    chmod 0644 "$TLS_REFRESH_SERVICE"

    cat > "$TLS_REFRESH_TIMER" <<'UNIT'
[Unit]
Description=Daily TLS refresh for 3x-ui Host Control proxy

[Timer]
OnCalendar=daily
Persistent=true
RandomizedDelaySec=1h

[Install]
WantedBy=timers.target
UNIT
    chmod 0644 "$TLS_REFRESH_TIMER"
fi

TMP="$(mktemp /etc/3xui-host-control/proxy-nginx.conf.XXXXXX)"
trap 'rm -f "$TMP"' EXIT HUP INT TERM

cat > "$TMP" <<'NGINX'
worker_processes 1;
pid /var/lib/3xui-host-control-proxy/nginx.pid;
error_log stderr warn;

events {
    worker_connections 128;
}

http {
    access_log off;
    server_tokens off;
    client_max_body_size 8k;
    proxy_connect_timeout 2s;
    proxy_send_timeout 25s;
    proxy_read_timeout 25s;
NGINX

if [[ "$MODE" == "master" ]]; then
    cat >> "$TMP" <<NGINX
    server {
        listen $BRIDGE_IP:$PROXY_PORT;
        server_name _;
        allow $DOCKER_SUBNET;
        deny all;
NGINX
else
    cat >> "$TMP" <<NGINX
    server {
        listen $LISTEN_IP:$PROXY_PORT ssl;
        server_name $PUBLIC_HOST;
        ssl_certificate $TLS_DIR/fullchain.pem;
        ssl_certificate_key $TLS_DIR/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_session_tickets off;
        allow $SOURCE_IP;
        deny all;
NGINX
fi

cat >> "$TMP" <<'NGINX'
        location ^~ /v1/ {
            proxy_pass http://127.0.0.1:18181;
            proxy_http_version 1.1;
            proxy_redirect off;
            proxy_set_header Authorization $http_authorization;
            proxy_set_header Host localhost;
            proxy_request_buffering off;
            proxy_buffering off;
        }

        location / {
            return 404;
        }
    }
}
NGINX

chown root:root "$TMP"
chmod 0644 "$TMP"
mv "$TMP" "$PROXY_CONFIG"
trap - EXIT HUP INT TERM

cat > "$PROXY_UNIT" <<UNIT
[Unit]
Description=Restricted reverse proxy for 3x-ui Host Control Agent
After=network-online.target 3xui-host-control.service
Requires=3xui-host-control.service

[Service]
Type=simple
User=$PROXY_USER
Group=$PROXY_USER
ExecStartPre=$NGINX_BIN -e stderr -t -c $PROXY_CONFIG
ExecStart=$NGINX_BIN -e stderr -c $PROXY_CONFIG -g "daemon off;"
ExecReload=/bin/kill -HUP \$MAINPID
KillSignal=SIGQUIT
TimeoutStopSec=10
Restart=on-failure
RestartSec=2
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
CapabilityBoundingSet=
AmbientCapabilities=
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
ReadWritePaths=$PROXY_STATE
ReadOnlyPaths=/etc/3xui-host-control
UMask=0077

[Install]
WantedBy=multi-user.target
UNIT
chmod 0644 "$PROXY_UNIT"

sudo -u "$PROXY_USER" "$NGINX_BIN" -e stderr -t -c "$PROXY_CONFIG"

systemctl daemon-reload
systemctl enable --now "$PROXY_SERVICE"
systemctl is-active --quiet "$PROXY_SERVICE" || die "proxy service is not active"

if [[ "$MODE" == "remote" ]]; then
    systemctl enable --now 3xui-host-control-tls-refresh.timer
    systemctl is-enabled --quiet 3xui-host-control-tls-refresh.timer \
        || die "TLS refresh timer is not enabled"
fi

if [[ "$APPLY_UFW" == 1 ]]; then
    need_cmd ufw
    if ufw status | grep -q '^Status: active'; then
        if [[ "$MODE" == "master" ]]; then
            UFW_SOURCE="$DOCKER_SUBNET"
            UFW_DEST="$BRIDGE_IP"
            UFW_COMMENT='3xui host-control master proxy'
        else
            UFW_SOURCE="$SOURCE_IP"
            UFW_DEST="$LISTEN_IP"
            UFW_COMMENT='3xui host-control remote proxy'
        fi

        if [[ -f "$UFW_STATE" ]]; then
            OLD_MODE="$(sed -n 's/^MODE=//p' "$UFW_STATE" | head -n 1)"
            OLD_SOURCE="$(sed -n 's/^SOURCE=//p' "$UFW_STATE" | head -n 1)"
            OLD_DEST="$(sed -n 's/^DEST=//p' "$UFW_STATE" | head -n 1)"
            OLD_PORT="$(sed -n 's/^PORT=//p' "$UFW_STATE" | head -n 1)"
            if [[ -n "$OLD_SOURCE" && -n "$OLD_DEST" && -n "$OLD_PORT" ]] \
                && [[ "$OLD_MODE|$OLD_SOURCE|$OLD_DEST|$OLD_PORT" != "$MODE|$UFW_SOURCE|$UFW_DEST|$PROXY_PORT" ]]; then
                ufw --force delete allow from "$OLD_SOURCE" to "$OLD_DEST" port "$OLD_PORT" proto tcp >/dev/null 2>&1 || true
            fi
        fi

        ufw allow from "$UFW_SOURCE" to "$UFW_DEST" port "$PROXY_PORT" proto tcp \
            comment "$UFW_COMMENT"

        UTMP="$(mktemp /etc/3xui-host-control/ufw-managed.env.XXXXXX)"
        trap 'rm -f "$UTMP"' EXIT HUP INT TERM
        {
            printf 'MODE=%s\n' "$MODE"
            printf 'SOURCE=%s\n' "$UFW_SOURCE"
            printf 'DEST=%s\n' "$UFW_DEST"
            printf 'PORT=%s\n' "$PROXY_PORT"
        } > "$UTMP"
        chmod 0600 "$UTMP"
        chown root:root "$UTMP"
        mv "$UTMP" "$UFW_STATE"
        trap - EXIT HUP INT TERM
    else
        printf 'UFW is inactive; no rule added.\n'
    fi
fi

TOKEN_FILE=/etc/3xui-host-control/token
[[ -s "$TOKEN_FILE" ]] || die "agent token file missing"

if [[ "$MODE" == "master" ]]; then
    TARGET_URL="http://$BRIDGE_IP:$PROXY_PORT"
else
    if [[ "$PROXY_PORT" == 443 ]]; then
        TARGET_URL="https://$PUBLIC_HOST"
    else
        TARGET_URL="https://$PUBLIC_HOST:$PROXY_PORT"
    fi
fi

ETMP="$(mktemp "$ENROLLMENT_FILE.XXXXXX")"
trap 'rm -f "$ETMP"' EXIT HUP INT TERM
{
    printf 'HOST_CONTROL_ALIAS=%s\n' "$ALIAS"
    printf 'HOST_CONTROL_NAME=%s\n' "$NAME"
    printf 'HOST_CONTROL_HOST_ID=%s\n' "$HOST_ID"
    printf 'HOST_CONTROL_URL=%s\n' "$TARGET_URL"
    printf 'HOST_CONTROL_VERIFY_TLS=true\n'
    printf 'HOST_CONTROL_TOKEN='
    cat "$TOKEN_FILE"
    printf '\n'
} > "$ETMP"
chmod 0600 "$ETMP"
chown root:root "$ETMP"
mv "$ETMP" "$ENROLLMENT_FILE"
trap - EXIT HUP INT TERM

if [[ "$MODE" == "master" ]]; then
    EXPECTED="$BRIDGE_IP:$PROXY_PORT"
else
    EXPECTED="$LISTEN_IP:$PROXY_PORT"
fi

ss -ltn | grep -Fq "$EXPECTED" || die "expected listener not found: $EXPECTED"
if ss -ltn | grep -Eq "0\.0\.0\.0:$PROXY_PORT([^0-9]|$)"; then
    die "unsafe wildcard listener detected"
fi

printf 'Host-control endpoint installed successfully.\n'
printf 'Mode: %s\n' "$MODE"
printf 'Host ID: %s\n' "$HOST_ID"
printf 'Target URL: %s\n' "$TARGET_URL"
printf 'Enrollment file: %s (0600, contains secret token)\n' "$ENROLLMENT_FILE"
if [[ "$MODE" == "remote" ]]; then
    printf 'TLS refresh timer: 3xui-host-control-tls-refresh.timer\n'
fi
printf 'Token was NOT printed.\n'
