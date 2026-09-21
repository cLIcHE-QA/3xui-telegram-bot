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


## v3.2: synchronize allowed inbounds

The admin user card now has a `Синхронизировать inbound'ы` button. It compares the
client's current `inboundIds` with the inbound set allowed by `.env`, and attaches
only missing IDs using `POST /panel/api/clients/{email}/attach`.

For AmneziaWG, make sure its port/protocol and, if used, exact inbound ID are in `.env`:

```env
ALLOWED_PORTS=2053,2083,443,51820
ALLOWED_PROTOCOLS=vless,hysteria,amneziawg
INBOUND_IDS=1,2,3,4
```

Use the actual IDs shown by `/inbounds`.
