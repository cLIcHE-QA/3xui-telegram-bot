# 3x-ui Telegram bot v3

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
