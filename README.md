# 3x-ui Telegram bot v4.4.0

Production-oriented Telegram admin panel for 3x-ui.

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
Payments, Promo Codes, Panels, Traffic, Online, Logs, Jobs, Audit Log,
Administrators and Settings. They do not perform mock or destructive operations.


## v3.9.0 — Plans + Server Groups + Hosts

This release adds three production admin catalog modules without changing the
existing provisioning/subscription/node/backup behavior. Dashboard also shows
active/total Plans, Server Group count, and enabled/total Hosts.

### Plans

`/admin -> Plans` now supports:

- create a plan;
- duration in days;
- traffic limit in GB (`0` = unlimited);
- IP/device limit (`0` = unlimited);
- price + 3-letter currency;
- optional Server Group assignment;
- enable/disable;
- delete.

Important: in v3.9 Plans are a control-plane catalog only. The existing `/create`
flow still uses `TEST_DAYS`, `TEST_TRAFFIC_GB` and `TEST_IP_LIMIT`. Wiring Plans
into provisioning is intentionally deferred so the already-working user flow is
not changed without explicit approval.

### Server Groups

`/admin -> Infrastructure -> Server Groups` supports:

- create/delete groups;
- optional description;
- add/remove the Master server;
- add/remove native 3x-ui nodes discovered from the Master panel;
- assign a group to a Plan.

Group membership is stored in the bot SQLite database. It does not yet rewrite
subscriptions or client inbound assignments automatically.

### Hosts

`/admin -> Infrastructure -> Hosts` is a central metadata registry for domains
and IPs. It supports roles such as Panel, Subscription, VPN endpoint and
Reality/SNI, enable/disable, delete, and discovery of the hosts already present
in the current `PANEL_URL`, public compatibility subscription URL and upstream
3x-ui subscription URL.

The Hosts registry does not edit DNS, nginx, certificates, or 3x-ui settings in
v3.9. That separation is intentional for safe production rollout.

### Database migration

No manual migration is required. On startup the bot creates the additional
SQLite tables (`plans`, `server_groups`, `server_group_members`, `hosts`) with
`CREATE TABLE IF NOT EXISTS`. Existing `users` rows remain unchanged.

### Upgrade from v3.8.0

No new environment variables are required.

```bash
cd /opt/3xui-bot/3xui-telegram-bot-v3.8.0
docker compose down
cp .env .env.backup
cp data/bot.sqlite3 data/bot.sqlite3.backup

cp /opt/3xui-bot/3xui-telegram-bot-v3.8.0/.env \
   /opt/3xui-bot/3xui-telegram-bot-v3.9.0/.env
mkdir -p /opt/3xui-bot/3xui-telegram-bot-v3.9.0/data
cp -a /opt/3xui-bot/3xui-telegram-bot-v3.8.0/data/. \
   /opt/3xui-bot/3xui-telegram-bot-v3.9.0/data/.

cd /opt/3xui-bot/3xui-telegram-bot-v3.9.0
docker compose up -d --build
```

The first startup performs only additive `CREATE TABLE IF NOT EXISTS` schema
initialization for the new catalog tables. The existing `users` table and all
current 3x-ui behavior are preserved.

## v4.0.0 — Monitoring, Jobs and Audit Log

v4.0 keeps the working v3.9 control-plane behavior unchanged and fills the
production Monitoring/System modules that were previously placeholders.

### Monitoring → Traffic

`/admin -> Monitoring -> Traffic` reads the current first-class client list from
3x-ui and aggregates its traffic records. The page shows:

- total upload/download and total transferred bytes;
- number of clients visible to 3x-ui and number linked to the bot SQLite DB;
- aggregate usage of finite quotas;
- top clients by cumulative traffic.

The counters are intentionally labelled **cumulative**. They are the current
3x-ui counters since the last traffic reset, not a fabricated "today" metric.

### Monitoring → Online

Uses the native 3x-ui clients monitoring endpoints. The page shows currently
online client emails deduplicated across the master and nodes, marks bot-known
users with their Telegram ID, and shows a short list of recent last-seen users.
No client source IP addresses are exposed in the Telegram UI.

### System → Jobs

The Jobs page is backed by the new `job_runs` SQLite table. v4.0 records real
backup executions rather than displaying synthetic jobs:

- `backup.daily` — scheduled automatic backup;
- `backup.manual` — backup launched by an administrator.

Each run stores trigger, status, start/end time, duration and a short result.
`Run backup now` is available from the Jobs page. A shared process lock prevents
two full backup archives from being built at the same time.

### System → Audit Log

The new `audit_log` SQLite table records administrative mutations without
storing API tokens or subscription secrets. v4.0 audits the main production
actions, including:

- per-user sync, +30 days, enable/disable and delete;
- global inbound sync;
- node add;
- backup create/download;
- plan create/toggle/group/delete;
- server group create/member changes/delete;
- host discover/create/toggle/delete.

The Audit Log is paginated and intentionally has no "clear" button.

### Dashboard

Dashboard now also includes the live Monitoring summary:

- cumulative traffic currently reported by 3x-ui;
- number of clients currently online.

If the monitoring API is temporarily unavailable, Dashboard reports that
section as a warning without breaking the rest of the admin panel.

### Database migration

No existing table is rewritten. `db.init()` adds only:

```text
audit_log
job_runs
```

Existing `users`, `plans`, `server_groups`, `server_group_members` and `hosts`
remain compatible with v3.9.0.

### Upgrade from v3.9.0

```bash
cd /opt/3xui-bot/3xui-telegram-bot-v3.9.0
docker compose down
cp .env .env.backup
cp data/bot.sqlite3 data/bot.sqlite3.backup

cp /opt/3xui-bot/3xui-telegram-bot-v3.9.0/.env \
   /opt/3xui-bot/3xui-telegram-bot-v4.0.0/.env

mkdir -p /opt/3xui-bot/3xui-telegram-bot-v4.0.0/data
cp -a /opt/3xui-bot/3xui-telegram-bot-v3.9.0/data/. \
   /opt/3xui-bot/3xui-telegram-bot-v4.0.0/data/.

cd /opt/3xui-bot/3xui-telegram-bot-v4.0.0
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 bot
```

Then check:

```text
/admin
 -> Dashboard
 -> Monitoring -> Traffic
 -> Monitoring -> Online
 -> System -> Jobs
 -> System -> Audit Log
```

No new `.env` variables are required for v4.0.0.



## v4.1.0 — Payments, Promo Codes, Administrators/Roles, Safe Settings

v4.1.0 is additive on top of v4.0.0. Existing user provisioning, 3x-ui
operations, subscriptions, compatibility proxy, Nodes, Backups, Monitoring,
Jobs and Audit Log are kept in place.

### Payments

`/admin -> Payments` now provides an internal production ledger:

- list recent payments and paid/pending/refunded totals;
- create a manual payment for an existing bot user;
- optionally link it to a Plan;
- amount + 3-letter currency;
- `pending`, `paid`, `refunded`, `cancelled` states;
- optional external/reference ID;
- paid totals grouped by currency;
- audit entries for creation and status changes.

This release intentionally does not pretend that an external payment provider is
connected. Provider integrations can later write into the same ledger without
rewriting payment history.

### Promo Codes

`/admin -> Promo Codes` supports:

- percentage or fixed-value discounts;
- optional Plan restriction;
- max-use limit (`0` = unlimited);
- optional UTC expiry date;
- enable/disable and delete;
- audit entries.

The catalog is ready for a future checkout flow. Promo codes are **not** applied
to the existing `/create` trial automatically in v4.1.0.

### Administrators and roles

`/admin -> System -> Administrators` adds database-backed administrators.
`ADMIN_TELEGRAM_IDS` remain immutable break-glass Owners and cannot be disabled
from Telegram.

Roles:

- `Owner` — full access, including administrator management;
- `Administrator` — production operations + safe runtime settings;
- `Support` — read access across the admin panel plus common user operations
  (extend, sync, enable/disable);
- `Read-only` — view-only administration/monitoring.

The existing environment administrator IDs keep full access after upgrade.

### Safe runtime Settings

`/admin -> System -> Settings` exposes only non-secret runtime settings:

- Trial days;
- Trial traffic in GB;
- Trial IP/device limit;
- default currency.

Trial settings apply to **new** `/create` operations immediately. Default currency
is used when a Plan, Payment or fixed-value Promo Code is entered without an
explicit currency.

Secrets such as `BOT_TOKEN`, `PANEL_API_TOKEN`, node API tokens, TLS policy,
backup bind mounts and other infrastructure settings remain outside the Telegram
UI. Backup schedule/retention and TLS verification are displayed read-only from
`.env`.

### Database migration

No existing table is rewritten. `db.init()` adds only:

```text
payments
promo_codes
administrators
runtime_settings
```

Existing data from v4.0.0 remains compatible.

### Upgrade from v4.0.0

No new `.env` variables are required.

```bash
cd /opt/3xui-bot/3xui-telegram-bot-v4.0.0
docker compose down
cp .env .env.backup
cp data/bot.sqlite3 data/bot.sqlite3.backup

cp /opt/3xui-bot/3xui-telegram-bot-v4.0.0/.env \
   /opt/3xui-bot/3xui-telegram-bot-v4.1.0/.env

mkdir -p /opt/3xui-bot/3xui-telegram-bot-v4.1.0/data
cp -a /opt/3xui-bot/3xui-telegram-bot-v4.0.0/data/. \
   /opt/3xui-bot/3xui-telegram-bot-v4.1.0/data/.

cd /opt/3xui-bot/3xui-telegram-bot-v4.1.0
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 bot
```

Then verify:

```text
/admin
 -> Payments
 -> Promo Codes
 -> System -> Administrators
 -> System -> Settings
```


## v4.2.0 — Advanced User Management

v4.2.0 is additive on top of v4.1.0. Existing provisioning, subscription
compatibility, Nodes, Plans, Server Groups, Payments, Monitoring, Backups,
Administrators/Roles and Settings are not replaced.

### Advanced user card

Open `/admin -> Users -> user -> Advanced management`.

The extended card shows live 3x-ui values together with control-plane metadata:

- enable state;
- expiry;
- traffic quota and used traffic;
- IP limit;
- attached inbound IDs;
- VLESS flow;
- assigned Plan;
- assigned Server Group;
- internal admin note.

### Direct edits

Support+ administrators can now change:

- expiry (`+30`, an absolute `YYYY-MM-DD` date, or `0` for unlimited);
- traffic quota in GB (`0` = unlimited);
- IP limit (`0` = unlimited);
- Plan assignment;
- Server Group assignment;
- internal note;
- individual managed inbound membership.

Detaching the last managed inbound is blocked to avoid accidentally leaving a
bot user with no usable service inbound.

Plan and Server Group assignment are stored as control-plane metadata in the new
`user_profiles` table. Assigning a Plan by itself does not silently rewrite a
live 3x-ui client. The explicit `Apply Plan to limits` action applies the Plan's
expiry duration, traffic quota and IP limit; when the Plan has a Server Group,
that group is stored on the user's control-plane profile as well.

### Traffic reset

`Reset traffic` uses the current first-class 3x-ui client bulk reset endpoint
with a single email. This resets the shared client traffic counters across its
attached inbounds and works with the same multi-node-aware client model used by
3x-ui.

### Subscription ID rotation

Owner/Administrator can rotate a user's `subId` from Telegram. The operation:

1. creates a new unique random subscription ID;
2. updates the first-class 3x-ui client;
3. updates the bot SQLite row;
4. writes an Audit Log entry;
5. returns the new compatibility subscription URL.

The old subscription URL stops refreshing after rotation. Existing already
imported proxy configs are not remotely deleted from user devices.

Protocol credentials (VLESS UUID, Hysteria auth, AmneziaWG keys) are deliberately
not rotated by this action; credential rotation is a separate protocol-aware
workflow and is not mixed with subscription-ID rotation.

### Bulk user actions

`/admin -> Users -> Bulk actions` provides a selector with pagination and:

- +30 days;
- enable;
- disable;
- reset traffic;
- synchronize managed inbounds + VLESS flow.

Bulk mutations use the first-class `/panel/api/clients/bulk*` endpoints where
available and create Audit Log entries. Bulk delete is intentionally omitted from
this screen to keep destructive actions explicit per user.

### Database migration

No existing table is rewritten. `db.init()` adds only:

```text
user_profiles
```

The existing `users` table remains the stable Telegram-ID / email / subId link.
Deleting a bot user now also deletes its optional `user_profiles` row.

### Upgrade from v4.1.0

No new `.env` variables are required.

```bash
cd /opt/3xui-bot/3xui-telegram-bot-v4.1.0
docker compose down
cp .env .env.backup
cp data/bot.sqlite3 data/bot.sqlite3.backup

cp /opt/3xui-bot/3xui-telegram-bot-v4.1.0/.env \
   /opt/3xui-bot/3xui-telegram-bot-v4.2.0/.env

mkdir -p /opt/3xui-bot/3xui-telegram-bot-v4.2.0/data
cp -a /opt/3xui-bot/3xui-telegram-bot-v4.1.0/data/. \
   /opt/3xui-bot/3xui-telegram-bot-v4.2.0/data/.

cd /opt/3xui-bot/3xui-telegram-bot-v4.2.0
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 bot
```

Then verify:

```text
/admin
 -> Users
 -> open a user
 -> Advanced management

/admin
 -> Users
 -> Bulk actions
```


## v4.3.0 — Advanced Inbound Management

v4.3.0 is additive on top of v4.2.0. Existing user provisioning, Plans,
Server Groups, subscription compatibility, backups, nodes, monitoring and user
management are intentionally left in place. The Infrastructure → Inbounds page
now opens first-class inbound cards instead of being only a status list.

### Inbound cards

Each managed inbound can now be opened from:

```text
/admin
→ Infrastructure
→ Inbounds
→ select inbound
```

The card shows server/node, enable state, protocol, port, listen address,
transport/security, client count and traffic counters. XHTTP cards also show
path/host/mode/padding. REALITY cards show SNI and the public client
fingerprint setting; private keys are never printed to Telegram.

Available actions:

```text
Clients
Edit
Enable / Disable
Sync users
Reset inbound traffic
Clone
Save as template
Delete inbound (confirmed)
```

### Safe editing

Telegram editing uses the documented full inbound replacement payload while
preserving the existing settings/streamSettings/sniffing objects. It exposes
only selected operational fields:

```text
remark
port
listen
XHTTP path
XHTTP host
XHTTP mode
XHTTP xPaddingBytes
REALITY serverNames / SNI
REALITY client fingerprint
```

The REALITY private key, AWG private material and other secret fields are not
shown or requested. They remain preserved in the full configuration sent back
to 3x-ui.

Enable/disable uses the dedicated `/panel/api/inbounds/setEnable/:id` endpoint
rather than serialising the whole inbound just to flip a switch.

### Clients and sync

`Clients` lists the clients currently attached to the inbound. Clients known to
the Telegram bot link back to their existing admin user card.

`Sync users` is an explicit confirmed bulk operation. It attaches every user
known to the local bot SQLite database to the selected inbound without changing
credentials or limits. Existing attachments are skipped by 3x-ui.

### Clone and multi-node deployment

Clone follows the current 3x-ui panel behaviour: the clone is created disabled,
with no clients, zero inbound counters, an empty listen address and the same
configuration as the source. The target can be Master or any online native
3x-ui node. The source port is reused when free on that target; otherwise the
bot asks for another port.

### Inbound Templates

A current inbound can be saved as a template. Templates are stored in
`bot.sqlite3` and intentionally contain the configuration needed to reproduce
the inbound, so treat the bot database/backup as secret material.

```text
Infrastructure
→ Inbounds
→ Templates
→ template
→ Deploy
→ Master / node
```

Deploy creates a disabled inbound with no clients. It uses the template port
when available on the target and asks for another port on conflict.

### Database migration

One additive table is created automatically:

```text
inbound_templates
```

No existing table is rebuilt or rewritten.

### Upgrade from v4.2.0

```bash
cd /opt/3xui-bot/3xui-telegram-bot-v4.2.0
docker compose down
cp .env .env.backup
cp data/bot.sqlite3 data/bot.sqlite3.backup

cp /opt/3xui-bot/3xui-telegram-bot-v4.2.0/.env \
   /opt/3xui-bot/3xui-telegram-bot-v4.3.0/.env
mkdir -p /opt/3xui-bot/3xui-telegram-bot-v4.3.0/data
cp -a /opt/3xui-bot/3xui-telegram-bot-v4.2.0/data/. \
   /opt/3xui-bot/3xui-telegram-bot-v4.3.0/data/.

cd /opt/3xui-bot/3xui-telegram-bot-v4.3.0
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 bot
```


## v4.4.0 — Advanced Nodes

v4.4.0 is additive on top of v4.3.0. Existing user, subscription, inbound,
monitoring, backup and business logic is kept intact. The native 3x-ui node
card now exposes operational controls suitable for day-to-day administration.

Open:

```text
/admin
→ Infrastructure
→ Nodes
→ select node
```

The node card now shows panel/Xray state, 3x-ui and Xray versions, endpoint,
TLS verification mode, inbound-sync mode, API latency, CPU/RAM, uptime,
network throughput, inbound/client counts, heartbeat state and per-node backup
availability.

### Node actions

```text
Test / probe
Inbounds
Per-node DB backup
Maintenance mode
Rename
Restart Xray
Update 3x-ui
Delete node
```

`Maintenance mode` uses the native node enable/disable switch on the master.
It does not shut down the VPS; it tells the master to stop actively managing the
node until it is enabled again.

`Inbounds` lists only master-known inbounds assigned to that node and links each
row to the existing Advanced Inbound Management card from v4.3.0.

### Per-node backup and Xray restart

3x-ui intentionally does not expose the node-sync API token back through the
master's node API. Therefore operations that must call the remote panel directly
use the already-supported dedicated admin token from `NODE_BACKUP_TARGETS`.

The same target is used for:

```text
per-node database download
remote Xray restart
```

If a target is not configured, the buttons explain the requirement rather than
falling back to an unsafe token source. Manual node snapshots are stored below
`BACKUP_DIR/nodes/<node>/` and the newest five are retained.

Example (same variables as earlier releases):

```env
NODE_BACKUP_TARGETS=FI
NODE_BACKUP_FI_NODE_NAME=Finland
NODE_BACKUP_FI_PANEL_URL=https://fi-panel.example.com/basepath
NODE_BACKUP_FI_API_TOKEN=replace_with_dedicated_admin_scope_token
NODE_BACKUP_FI_VERIFY_TLS=true
```

If a node with a configured backup target is renamed, update the corresponding
`NODE_BACKUP_*_NODE_NAME` value and restart/recreate the bot container so the
direct target follows the new name.

### Panel update

`Update 3x-ui` uses the native master endpoint for node panel updates and starts
the official stable-channel self-updater on the selected enabled/online node.
It is confirmation-gated because the remote panel restarts during the update.

### Safe deletion

The bot checks for node-assigned inbounds before presenting the final delete
confirmation. 3x-ui itself also refuses to delete a node while inbounds are still
attached. Removing a node from Master does not delete the remote VPS or uninstall
3x-ui on it.

### Database / environment changes

No bot SQLite migration and no new `.env` variables are required in v4.4.0.
All node mutations are recorded in the existing Audit Log.

### Upgrade from v4.3.0

```bash
cd /opt/3xui-bot/3xui-telegram-bot-v4.3.0
docker compose down
cp .env .env.backup
cp data/bot.sqlite3 data/bot.sqlite3.backup

cp /opt/3xui-bot/3xui-telegram-bot-v4.3.0/.env \
   /opt/3xui-bot/3xui-telegram-bot-v4.4.0/.env
mkdir -p /opt/3xui-bot/3xui-telegram-bot-v4.4.0/data
cp -a /opt/3xui-bot/3xui-telegram-bot-v4.3.0/data/. \
   /opt/3xui-bot/3xui-telegram-bot-v4.4.0/data/.

cd /opt/3xui-bot/3xui-telegram-bot-v4.4.0
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 bot
```
