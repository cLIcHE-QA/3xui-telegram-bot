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
