#!/bin/sh
set -eu

usage() {
    echo "Usage: sudo scripts/install-host-control-agent.sh <host-id>" >&2
    exit 2
}

[ "$#" -eq 1 ] || usage
HOST_ID="$1"

printf '%s' "$HOST_ID" | grep -Eq '^[a-z0-9][a-z0-9_-]{0,31}$' || {
    echo "Invalid host-id." >&2
    exit 2
}

[ "$(id -u)" -eq 0 ] || {
    echo "Run this installer as root." >&2
    exit 2
}

for bin in /usr/bin/python3 /usr/bin/systemctl /usr/bin/sudo /usr/sbin/visudo; do
    [ -x "$bin" ] || {
        echo "Required executable missing: $bin" >&2
        exit 2
    }
done

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
AGENT_SOURCE="$REPO_ROOT/host_control_agent.py"
UNIT_SOURCE="$REPO_ROOT/deploy/host-control/3xui-host-control.service"
SUDOERS_SOURCE="$REPO_ROOT/deploy/host-control/3xui-host-control.sudoers"

[ -f "$AGENT_SOURCE" ] || { echo "Missing $AGENT_SOURCE" >&2; exit 2; }
[ -f "$UNIT_SOURCE" ] || { echo "Missing $UNIT_SOURCE" >&2; exit 2; }
[ -f "$SUDOERS_SOURCE" ] || { echo "Missing $SUDOERS_SOURCE" >&2; exit 2; }

if ! id 3xui-hostctl >/dev/null 2>&1; then
    /usr/sbin/useradd --system --home-dir /nonexistent --shell /usr/sbin/nologin 3xui-hostctl
fi

install -d -o root -g root -m 0755 /opt/3xui-host-control
install -d -o root -g root -m 0755 /etc/3xui-host-control
install -d -o 3xui-hostctl -g 3xui-hostctl -m 0700 /var/lib/3xui-host-control
install -o root -g root -m 0755 "$AGENT_SOURCE" /opt/3xui-host-control/host_control_agent.py

TOKEN_FILE=/etc/3xui-host-control/token
if [ ! -f "$TOKEN_FILE" ]; then
    TMP_TOKEN=$(mktemp /etc/3xui-host-control/token.XXXXXX)
    trap 'rm -f "$TMP_TOKEN"' EXIT HUP INT TERM
    /usr/bin/python3 - <<'PY' > "$TMP_TOKEN"
import secrets
print(secrets.token_urlsafe(48))
PY
    chown 3xui-hostctl:3xui-hostctl "$TMP_TOKEN"
    chmod 0600 "$TMP_TOKEN"
    mv "$TMP_TOKEN" "$TOKEN_FILE"
    trap - EXIT HUP INT TERM
else
    chown 3xui-hostctl:3xui-hostctl "$TOKEN_FILE"
    chmod 0600 "$TOKEN_FILE"
fi

cat > /etc/3xui-host-control/agent.env <<EOF
HOST_CONTROL_AGENT_ID=$HOST_ID
HOST_CONTROL_AGENT_LISTEN=127.0.0.1:18181
HOST_CONTROL_AGENT_TOKEN_FILE=/etc/3xui-host-control/token
HOST_CONTROL_AGENT_SERVICE=x-ui.service
HOST_CONTROL_AGENT_DB=/var/lib/3xui-host-control/agent.sqlite3
HOST_CONTROL_AGENT_OPERATION_TIMEOUT=20
EOF
chown root:root /etc/3xui-host-control/agent.env
chmod 0644 /etc/3xui-host-control/agent.env

SUDOERS_TMP=$(mktemp /etc/sudoers.d/3xui-host-control.XXXXXX)
trap 'rm -f "$SUDOERS_TMP"' EXIT HUP INT TERM
cat "$SUDOERS_SOURCE" > "$SUDOERS_TMP"
chmod 0440 "$SUDOERS_TMP"
/usr/sbin/visudo -cf "$SUDOERS_TMP" >/dev/null
mv "$SUDOERS_TMP" /etc/sudoers.d/3xui-host-control
trap - EXIT HUP INT TERM
chown root:root /etc/sudoers.d/3xui-host-control
chmod 0440 /etc/sudoers.d/3xui-host-control

install -o root -g root -m 0644 "$UNIT_SOURCE" /etc/systemd/system/3xui-host-control.service
/usr/bin/systemctl daemon-reload
/usr/bin/systemctl enable 3xui-host-control.service
/usr/bin/systemctl restart 3xui-host-control.service
/usr/bin/systemctl is-active --quiet 3xui-host-control.service || {
    echo "Host-control agent did not become active." >&2
    exit 1
}

echo "3x-ui host-control agent installed for host-id=$HOST_ID"
echo "Listener is loopback-only: 127.0.0.1:18181"
echo "Token is stored in /etc/3xui-host-control/token and was NOT printed."
echo "Configure a restricted reverse proxy/firewall before adding a remote HOST_CONTROL_* target."