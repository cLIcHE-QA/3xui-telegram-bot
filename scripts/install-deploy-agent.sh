#!/bin/sh
set -eu

[ "$(id -u)" -eq 0 ] || {
    echo "Run this installer as root." >&2
    exit 2
}

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
AGENT_SOURCE="$REPO_ROOT/deploy_agent.py"
HELPER_SOURCE="$REPO_ROOT/scripts/3xui-bot-deploy-helper.sh"
UNIT_SOURCE="$REPO_ROOT/deploy/deploy-agent/3xui-deploy-agent.service"
SUDOERS_SOURCE="$REPO_ROOT/deploy/deploy-agent/3xui-deploy-agent.sudoers"

for path in "$AGENT_SOURCE" "$HELPER_SOURCE" "$UNIT_SOURCE" "$SUDOERS_SOURCE"; do
    [ -f "$path" ] || { echo "Missing $path" >&2; exit 2; }
done

for bin in /usr/bin/python3 /usr/bin/systemctl /usr/bin/sudo /usr/sbin/visudo; do
    [ -x "$bin" ] || { echo "Required executable missing: $bin" >&2; exit 2; }
done

if ! id 3xui-deploy >/dev/null 2>&1; then
    /usr/sbin/useradd --system --home-dir /nonexistent --shell /usr/sbin/nologin 3xui-deploy
fi

install -d -o root -g root -m 0755 /opt/3xui-deploy-agent
install -d -o root -g root -m 0755 /etc/3xui-deploy-agent
install -d -o 3xui-deploy -g 3xui-deploy -m 0700 /var/lib/3xui-deploy-agent
install -d -o root -g root -m 0755 /usr/local/libexec

install -o root -g root -m 0755 "$AGENT_SOURCE" /opt/3xui-deploy-agent/deploy_agent.py
install -o root -g root -m 0755 "$HELPER_SOURCE" /usr/local/libexec/3xui-bot-deploy

TOKEN_FILE=/etc/3xui-deploy-agent/token
if [ ! -f "$TOKEN_FILE" ]; then
    TMP_TOKEN=$(mktemp /etc/3xui-deploy-agent/token.XXXXXX)
    trap 'rm -f "$TMP_TOKEN"' EXIT HUP INT TERM
    /usr/bin/python3 - <<'PY' > "$TMP_TOKEN"
import secrets
print(secrets.token_urlsafe(48))
PY
    chown 3xui-deploy:3xui-deploy "$TMP_TOKEN"
    chmod 0600 "$TMP_TOKEN"
    mv "$TMP_TOKEN" "$TOKEN_FILE"
    trap - EXIT HUP INT TERM
else
    chown 3xui-deploy:3xui-deploy "$TOKEN_FILE"
    chmod 0600 "$TOKEN_FILE"
fi

cat > /etc/3xui-deploy-agent/agent.env <<'EOF'
DEPLOY_AGENT_LISTEN=172.19.0.1:18184
DEPLOY_AGENT_TOKEN_FILE=/etc/3xui-deploy-agent/token
DEPLOY_AGENT_DB=/var/lib/3xui-deploy-agent/agent.sqlite3
EOF
chown root:root /etc/3xui-deploy-agent/agent.env
chmod 0644 /etc/3xui-deploy-agent/agent.env

SUDOERS_TMP=$(mktemp /etc/sudoers.d/3xui-deploy-agent.XXXXXX)
trap 'rm -f "$SUDOERS_TMP"' EXIT HUP INT TERM
cat "$SUDOERS_SOURCE" > "$SUDOERS_TMP"
chmod 0440 "$SUDOERS_TMP"
/usr/sbin/visudo -cf "$SUDOERS_TMP" >/dev/null
mv "$SUDOERS_TMP" /etc/sudoers.d/3xui-deploy-agent
trap - EXIT HUP INT TERM
chown root:root /etc/sudoers.d/3xui-deploy-agent
chmod 0440 /etc/sudoers.d/3xui-deploy-agent

install -o root -g root -m 0644 "$UNIT_SOURCE" /etc/systemd/system/3xui-deploy-agent.service
/usr/bin/systemctl daemon-reload
/usr/bin/systemctl enable 3xui-deploy-agent.service
/usr/bin/systemctl restart 3xui-deploy-agent.service
/usr/bin/systemctl is-active --quiet 3xui-deploy-agent.service || {
    echo "Deploy Agent did not become active." >&2
    exit 1
}

echo "3x-ui bot Deploy Agent installed."
echo "Listener: 172.19.0.1:18184 (Docker-host private route only)."
echo "Token stored in /etc/3xui-deploy-agent/token and was NOT printed."
echo "Next: copy the token locally into DEPLOY_AGENT_TOKEN in the bot .env without sending it through chat."
