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
