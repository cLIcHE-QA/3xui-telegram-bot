#!/usr/bin/env bash
set -Eeuo pipefail

STATE_FILE="${HOST_CONTROL_TLS_STATE:-/etc/3xui-host-control/tls-source.env}"
TLS_DIR="${HOST_CONTROL_TLS_DIR:-/etc/3xui-host-control/tls}"
PROXY_SERVICE="${HOST_CONTROL_PROXY_SERVICE:-3xui-host-control-proxy.service}"

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
read_state() {
    local key="$1"
    sed -n "s/^$key=//p" "$STATE_FILE" | head -n 1
}

[[ "$(id -u)" -eq 0 ]] || die "run as root"
[[ -f "$STATE_FILE" ]] || die "TLS source state not found: $STATE_FILE"
command -v openssl >/dev/null 2>&1 || die "openssl not found"
command -v systemctl >/dev/null 2>&1 || die "systemctl not found"

CERT_PATH="$(read_state CERT_PATH)"
KEY_PATH="$(read_state KEY_PATH)"
PUBLIC_HOST="$(read_state PUBLIC_HOST)"

[[ "$CERT_PATH" = /* && -f "$CERT_PATH" ]] || die "certificate source missing"
[[ "$KEY_PATH" = /* && -f "$KEY_PATH" ]] || die "private-key source missing"
[[ -n "$PUBLIC_HOST" ]] || die "PUBLIC_HOST missing"

openssl x509 -in "$CERT_PATH" -noout -checkhost "$PUBLIC_HOST" >/dev/null 2>&1 \
    || die "certificate does not match $PUBLIC_HOST"

cert_pub="$(openssl x509 -in "$CERT_PATH" -pubkey -noout | openssl pkey -pubin -outform der 2>/dev/null | sha256sum | awk '{print $1}')"
key_pub="$(openssl pkey -in "$KEY_PATH" -pubout -outform der 2>/dev/null | sha256sum | awk '{print $1}')"
[[ -n "$cert_pub" && "$cert_pub" == "$key_pub" ]] || die "TLS certificate/private key mismatch"

changed=0
if [[ ! -f "$TLS_DIR/fullchain.pem" ]] || ! cmp -s "$CERT_PATH" "$TLS_DIR/fullchain.pem"; then
    changed=1
fi
if [[ ! -f "$TLS_DIR/privkey.pem" ]] || ! cmp -s "$KEY_PATH" "$TLS_DIR/privkey.pem"; then
    changed=1
fi

if [[ "$changed" == 0 ]]; then
    printf 'Host-control TLS is already current.\n'
    exit 0
fi

install -d -o root -g 3xui-hostproxy -m 0750 "$TLS_DIR"
install -o root -g 3xui-hostproxy -m 0640 "$CERT_PATH" "$TLS_DIR/fullchain.pem.new"
install -o root -g 3xui-hostproxy -m 0640 "$KEY_PATH" "$TLS_DIR/privkey.pem.new"

mv "$TLS_DIR/fullchain.pem.new" "$TLS_DIR/fullchain.pem"
mv "$TLS_DIR/privkey.pem.new" "$TLS_DIR/privkey.pem"

systemctl reload "$PROXY_SERVICE"
systemctl is-active --quiet "$PROXY_SERVICE" || die "proxy service is not active after TLS reload"
printf 'Host-control TLS refreshed and proxy reloaded.\n'
