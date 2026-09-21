# Telegram bot for 3x-ui — single-node test

Minimal test bot for one 3x-ui panel.

## What it does

- authenticates to 3x-ui with a Bearer API token;
- reads enabled inbounds from `/panel/api/inbounds/list`;
- creates one 3x-ui client and attaches it to all allowed inbounds;
- stores `Telegram ID -> email -> subId` in SQLite;
- returns your existing subscription-page URL;
- checks generated protocol links via `/panel/api/clients/subLinks/{subId}`;
- can remove the test user.

## 1. 3x-ui

Create an API token in **Settings -> Security -> API Token**.

For tests, use a dedicated token and revoke it after testing.

Make sure the subscription page is already enabled and you know its public URL format.

## 2. Telegram

Create a bot using BotFather and obtain `BOT_TOKEN`.

Find your numeric Telegram ID and add it to `ALLOWED_TELEGRAM_IDS`.

## 3. Configure

```bash
cp .env.example .env
nano .env
```

Important variables:

```env
BOT_TOKEN=...
PANEL_URL=https://panel.example.com
PANEL_API_TOKEN=...
SUBSCRIPTION_URL_TEMPLATE=https://sub.example.com/sub/{sub_id}
ALLOWED_TELEGRAM_IDS=123456789
```

If you want the test client to be added only to selected inbounds:

```env
INBOUND_IDS=1,3,7
```

If `INBOUND_IDS` is empty, the bot selects every enabled inbound whose protocol is in `ALLOWED_PROTOCOLS`.

## 4. Run with Docker

```bash
docker compose up -d --build
docker compose logs -f bot
```

Or without Docker:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

## Commands

- `/start` — menu
- `/inbounds` — show inbounds that will receive the client
- `/create` — create/recover the test client
- `/subscription` — show subscription URL and detected protocol links
- `/delete_test` — delete the test client

## Test order

1. Start bot.
2. Run `/inbounds` and verify the exact inbound list.
3. Run `/create`.
4. Open 3x-ui and verify that `tg_<telegram_id>` is attached to the expected inbounds.
5. Run `/subscription`.
6. Import the subscription URL into your client.
7. After testing, run `/delete_test`.

## Security

The 3x-ui API token is an administrative credential. Keep `.env` private.
The bot refuses all Telegram IDs that are not explicitly listed in
`ALLOWED_TELEGRAM_IDS`.
