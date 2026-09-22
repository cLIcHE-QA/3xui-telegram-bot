# 3x-ui Telegram bot v3.8.0

Adds a Telegram admin panel to the single-node test bot.

## Admin commands

`/admin`

Features:
- list local bot users;
- open a user card;
- show subscription;
- show expiry and traffic (when returned by 3x-ui);
- extend expiry by 30 days;
- enable / disable;
- delete from 3x-ui and local SQLite.

## Upgrade from v2 without losing users

1. Stop old project:
   `docker compose down`
2. Back up DB:
   `cp data/bot.sqlite3 data/bot.sqlite3.backup`
3. Copy v3 files over the project directory, but keep your `.env` and `data/`.
4. Add to `.env`:
   `ADMIN_TELEGRAM_IDS=YOUR_TELEGRAM_ID`
5. Start:
   `docker compose up -d --build`
6. Open Telegram and send `/admin`.

The v3 SQLite schema is compatible with v2.

## Important

The 3x-ui client update API replaces the client row rather than patching it.
This bot first fetches the complete client object, preserves the common fields,
then changes only expiry or enable state.

## Username-based 3x-ui client names

New users are named:

- `tg_<telegram_username>` when the Telegram user has a username;
- `tg_<telegram_id>` as a fallback when no username is set.

The local database still uses the numeric Telegram ID as the stable identifier.


## v3.3: global inbound sync

The `/admin` menu now has `🔄 Синхронизировать всех`.

After confirmation, the bot reads the allowed inbound set from `.env` and calls
`POST /panel/api/clients/bulkAttach` for every user stored in the bot SQLite DB.
Existing client/inbound pairs are skipped by 3x-ui; missing pairs are attached.

This is useful after adding a new inbound or protocol such as AmneziaWG.
The global action affects only users present in the bot's local SQLite database.

## v3.4: INCY-compatible AmneziaWG subscription proxy

3x-ui currently emits AmneziaWG raw links as `vpn://<base64url-conf>`. INCY mobile
expects `amneziawg://` or `awg://` for line-based mixed subscriptions.

v3.4 starts a small HTTP compatibility proxy inside the bot container:

- internal route: `GET /compat/{sub_id}`
- health check: `GET /healthz`
- fetches the original 3x-ui raw subscription from `SUBSCRIPTION_URL_TEMPLATE`
- accepts both base64-wrapped and plain upstream subscriptions
- converts only `vpn://...` to `amneziawg://...`
- preserves VLESS/Hysteria/etc. lines unchanged
- preserves the upstream base64/plain wrapping style
- forwards useful subscription headers such as `Subscription-Userinfo`
- validates that `{sub_id}` exists in the bot's local SQLite database

Configuration:

```env
# Source / upstream: keep the existing 3x-ui raw subscription URL here.
SUBSCRIPTION_URL_TEMPLATE=https://sub.example.com:2096/sub/{sub_id}

# URL the bot gives to users.
COMPAT_SUBSCRIPTION_URL_TEMPLATE=https://sub.example.com/compat/{sub_id}

SUBSCRIPTION_PROXY_HOST=0.0.0.0
SUBSCRIPTION_PROXY_PORT=8080
```

Docker publishes the proxy only on host loopback:

```text
127.0.0.1:18080 -> container:8080
```

Example nginx location on the VPS hosting `sub.example.com`:

```nginx
location /compat/ {
    proxy_pass http://127.0.0.1:18080;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

Reload nginx, then test locally first:

```bash
curl -fsS http://127.0.0.1:18080/healthz
```

For a known bot user, test the compatibility endpoint:

```bash
curl -fsS http://127.0.0.1:18080/compat/YOUR_SUB_ID | base64 -d
```

If the original 3x-ui subscription has `subEncrypt=false`, omit `| base64 -d`.
The expected line set is approximately:

```text
vless://...
vless://...
hysteria2://...
amneziawg://...
```

Important: the old subscription URL already stored in a VPN client does not
magically change. Add the new `/compat/{sub_id}` URL once, or replace the old
subscription in the client. Future refreshes then use the compatibility proxy.

## v3.5 — default 3x-ui page + INCY-compatible AmneziaWG

The same public URL now has two modes:

- Browser (`Accept: text/html`, `?html=1`, or `?view=html`) -> the **default 3x-ui subscription page**.
- VPN app -> raw subscription, preserving the upstream Base64 wrapping while converting only `vpn://` AmneziaWG links to `amneziawg://`.

The default 3x-ui page is fetched from the original subscription server rather than recreated. Its Vite `/assets/...` references are routed through `/compat/assets/...`, so the existing nginx `location ^~ /compat/` continues to work without another public location.

The proxy also passes through `?format=info`, which the current 3x-ui subscription page uses for live status/traffic updates.

Recommended settings remain:

```env
SUBSCRIPTION_URL_TEMPLATE=https://panel.example.com:2096/sub/{sub_id}
COMPAT_SUBSCRIPTION_URL_TEMPLATE=https://sub.example.com/compat/{sub_id}
SUBSCRIPTION_PROXY_HOST=0.0.0.0
SUBSCRIPTION_PROXY_PORT=8080
```

Quick checks:

```bash
# Browser-mode HTML
curl -fsS -H 'Accept: text/html' 'https://sub.example.com/compat/SUB_ID' | head

# Raw VPN subscription
curl -fsS 'https://sub.example.com/compat/SUB_ID' | base64 -d
```


## v3.5.1 fix: built-in 3x-ui page assets

3x-ui serves its built-in subscription SPA assets below the configured subscription path,
for example `/clichegamesub/assets/...`. v3.5 incorrectly fetched `/assets/...`, which could
produce a white page while the HTML itself loaded. v3.5.1 derives the asset prefix directly
from `SUBSCRIPTION_URL_TEMPLATE` and proxies it through `/compat/assets/...`.

For nginx, keep `proxy_buffering off;`. With current 3x-ui large Vite bundles it is also safe
to add `proxy_max_temp_file_size 0;` inside the `/compat/` location.


## v3.5.2 — preserve native 3x-ui AmneziaWG page rendering

HTML mode now leaves 3x-ui `vpn://` AmneziaWG links untouched. This preserves
the built-in AmneziaWG card, remark, QR/copy actions and the separate
AmneziaWG config row on the default subscription page.

Raw subscription mode is unchanged: `vpn://` is still converted to
`amneziawg://` for INCY compatibility. Thus the same `/compat/{sub_id}` URL
serves the native 3x-ui page in a browser and the adapted subscription to VPN
clients.


## v3.5.3 — VLESS XTLS flow synchronization

Adds `VLESS_FLOW` (default `xtls-rprx-vision`). New clients are created with this
flow and then normalized through the current 3x-ui `POST /panel/api/clients/bulkAdjust`
endpoint. The same endpoint is also called by both the per-user and global inbound
synchronization buttons, so existing bot users can be fixed without deletion/recreation.

Add to `.env`:

```env
VLESS_FLOW=xtls-rprx-vision
```

Set `VLESS_FLOW=` to leave existing flow values untouched. Current 3x-ui applies the
flow only where the inbound supports the requested XTLS flow.

After upgrading, use either:

- `/admin` -> user -> `Синхронизировать inbound'ы` for one user; or
- `/admin` -> `Синхронизировать всех` for every user in the bot SQLite database.

The admin user card also shows the client's current stored flow.


## v3.5.4: Shadowrocket XHTTP Reality compatibility

The compatibility subscription endpoint now detects Shadowrocket from its
`User-Agent`. For Shadowrocket only, it removes the `fp` query parameter from
`vless://` links where both `type=xhttp` and `security=reality` are present.

Other behavior is unchanged:

- browser requests still receive the default 3x-ui subscription page;
- INCY and other clients keep the original XHTTP fingerprint;
- VLESS TCP Reality links keep their fingerprint;
- AmneziaWG raw links are still converted from `vpn://` to `amneziawg://`.

No nginx changes and no new `.env` variables are required.

## v3.5.5: server health + bounded Docker logs

The `/admin` menu now includes `🩺 Состояние сервера`. It checks:

- the 3x-ui API through the configured panel route;
- the local subscription compatibility proxy;
- the public subscription `/healthz` route through nginx/TLS;
- managed inbound enable/disable state reported by 3x-ui;
- disk usage, RAM usage, uptime, and local bot-user count.

Inbound status is intentionally reported from the 3x-ui API. UDP/TCP socket probing is
not used because a successful TCP connect does not validate REALITY/XHTTP and UDP
services cannot be reliably health-checked with a generic connect probe.

Docker json-file logs are also capped in `docker-compose.yml`:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

The limit applies after the container is recreated with the new Compose configuration.

## v3.6.0: admin backups

`/admin` now includes `💾 Резервные копии` with:

- create a full backup immediately;
- download a fresh consistent `bot.sqlite3` snapshot;
- download the latest full `.tar.gz` backup;
- automatic daily backups with retention.

The full archive can contain:

- `bot.sqlite3` — consistent SQLite backup of the bot database;
- `x-ui.db` — consistent SQLite backup of 3x-ui;
- `bot.env` — the current bot `.env` file;
- `docker-compose.yml`;
- `nginx/` — the mounted nginx configuration directory;
- `manifest.json` and restore notes.

**The full archive contains secrets. Treat it like a password/credential file.**
Only Telegram IDs listed in `ADMIN_TELEGRAM_IDS` can use the backup buttons.

Default backup settings:

```env
BACKUP_ENABLED=true
BACKUP_DIR=/app/data/backups
BACKUP_KEEP=14
BACKUP_HOUR_UTC=2
BACKUP_SEND_TO_ADMINS=false
```

Automatic full backups are created daily at `BACKUP_HOUR_UTC`. The latest
`BACKUP_KEEP` full archives are retained. Manual SQLite download snapshots keep
only the latest three files.

For this deployment, Compose mounts the standard 3x-ui database directory and
the custom nginx configuration directory read-only:

```env
BACKUP_XUI_DIR_HOST_PATH=/etc/x-ui
BACKUP_NGINX_CONF_HOST_PATH=/opt/mtproxyl-nginx/conf
```

If nginx lives elsewhere, set `BACKUP_NGINX_CONF_HOST_PATH` in `.env` before
starting v3.6.0. 3x-ui uses `/etc/x-ui/x-ui.db` by default.

Optional off-server copy via Telegram:

```env
BACKUP_SEND_TO_ADMINS=true
```

When enabled, each automatic full backup is sent to every admin chat. This is
disabled by default because the archive contains secrets.

v3.6.0 also adds `.dockerignore`, so `.env`, databases and the `data/` directory
are no longer copied into the Docker image during `docker compose build`.

## v3.7.0: native 3x-ui multi-node foundation

v3.7.0 integrates the bot with the **native 3x-ui Nodes API** on the master panel.
The bot does not keep a second copy of the node registry and does not need the
node-sync tokens which the master stores internally.

New admin UI:

- `🌍 Ноды` lists every node registered in the master 3x-ui panel;
- `🔄 Проверить все` asks the master to probe all direct nodes;
- each direct node has a detail page with panel status, Xray state/version,
  API latency, CPU, RAM, uptime, inbound count and client counts;
- `🩺 Состояние системы` now shows Master + all nodes in one report;
- master CPU/RAM/disk/uptime are read from `/panel/api/server/status`, rather
  than inferred from the bot container.

### First Finland node

Register the Finland server in the master 3x-ui panel under **Nodes**. A simple
name such as `Finland` is recommended because the bot uses the same name.
Once the node is registered, `/admin -> 🌍 Ноды` discovers it automatically;
no bot `.env` changes are required for monitoring.

3x-ui supports token, certificate pinning and mTLS trust modes for native nodes.
Prefer verified HTTPS (or mTLS) rather than `skip` once the initial connection is
working.

### Backing up node databases

The master Nodes API deliberately does not return the node API token. Therefore
node health works automatically, while **database backup is configured
separately** for every node which should be included in the bot's full archive.
The bot downloads a consistent backup through the node's official
`GET /panel/api/server/getDb` endpoint. This supports both SQLite panels and
PostgreSQL panels (the returned file may be `.db` or `.dump`).

For the Finland node, add to the existing `.env` when ready:

```env
NODE_BACKUP_TARGETS=FI
NODE_BACKUP_FI_NODE_NAME=Finland
NODE_BACKUP_FI_PANEL_URL=https://fi-panel.example.com/basepath
NODE_BACKUP_FI_API_TOKEN=replace_with_dedicated_admin_scope_token
NODE_BACKUP_FI_VERIFY_TLS=true
```

`NODE_BACKUP_FI_NODE_NAME` must match the node name shown by the master 3x-ui
panel. For backup, use a **dedicated admin-scope API token on the Finland node**;
a restricted node-sync/monitor token may not be allowed to download the DB.
Never commit this token.

When configured, the existing `💾 Создать сейчас` and daily automatic backup
append files such as:

```text
nodes/
  Finland/
    x-ui.db        # or a PostgreSQL .dump returned by the node
    node.json      # non-secret source metadata
```

A failed node backup does not discard the master backup. The archive is still
created and the failed node is listed in the `missing` section and manifest.


### v3.7.1: Master card in Nodes

`/admin -> 🌍 Ноды` now always shows the master server as the first clickable row.
By default it is rendered as `🇳🇱 Master · 🟢 Online`; the label can be changed with `MASTER_NAME` and `MASTER_FLAG`.
The Master card opens a compact health view with 3x-ui/Xray, CPU/RAM/disk/uptime, subscription proxy, managed inbounds, bot users and latest backup.
Server totals and online counts include Master.


## v3.7.2 — Add nodes from Telegram

`/admin → 🌍 Ноды → ➕ Добавить ноду` opens a four-step wizard:

1. node name;
2. full 3x-ui panel URL (scheme/host/port/base path are parsed automatically);
3. node API token (the bot attempts to delete the Telegram message immediately after reading it);
4. TLS verification mode (`verify` recommended, `skip` only when needed).

Before saving, the bot calls the master 3x-ui `/panel/api/nodes/test` endpoint and shows panel/Xray health and latency. The final save uses `/panel/api/nodes/add`; credentials remain stored by the master 3x-ui, not in the bot SQLite database.

When no remote nodes exist, the hint is intentionally neutral: use the **➕ Добавить ноду** button to connect a server.

## v3.8.0 — Production Admin UI foundation

The existing v3.7.2 behavior is frozen: node management, backups, health checks,
subscriptions, user operations and compatibility-proxy logic are not rewritten.
v3.8.0 adds a stable navigation layer on top of those callbacks.

Top-level `/admin` navigation:

- `Dashboard`
- `Users`
- `Subscriptions`
- `Payments`
- `Plans`
- `Promo Codes`
- `Infrastructure`
- `Monitoring`
- `System`

Implemented in this foundation release:

- Dashboard summary for users, expiring users, master/node availability,
  managed inbound state and latest backup;
- Users keeps the existing user cards, bulk inbound sync and user statistics;
- Subscriptions lists local bot subscriptions without exposing their URL until
  the administrator opens a specific record;
- Infrastructure contains the existing Nodes UI and a managed Inbounds view;
- Monitoring contains the existing System Health implementation;
- System contains the existing Backups implementation.

Reserved modules are visible but explicitly marked as not implemented yet:
Payments, Plans, Promo Codes, Panels, Hosts, Server Groups, Traffic, Online,
Logs, Jobs, Audit Log, Administrators and Settings. They do not perform mock
or destructive operations.
