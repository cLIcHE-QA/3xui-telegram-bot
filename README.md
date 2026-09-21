# 3x-ui Telegram bot v2 — single-node test

This build is pre-tuned for the current node layout:

- 2053/tcp — VLESS
- 2083/tcp — VLESS
- 443/udp — Hysteria
- service `api/tunnel` inbound is ignored

## First test

```bash
cp .env.example .env
nano .env
docker compose up -d --build
docker compose logs -f bot
```

Then in Telegram:

```text
/inbounds
```

The bot prints:

- numeric 3x-ui inbound ID
- port
- protocol
- tag
- remark

At the bottom it prints the exact subset that will be assigned to the new client.

Once you confirm the IDs, pin them in `.env`:

```env
INBOUND_IDS=1,2,3
```

Then rebuild/restart:

```bash
docker compose up -d --build
```

Create a client:

```text
/create
```

Check subscription:

```text
/subscription
```

Delete test client:

```text
/delete_test
```

## Filtering

The initial filter is:

```env
ALLOWED_PORTS=2053,2083,443
ALLOWED_PROTOCOLS=vless,hysteria
IGNORED_TAGS=api
IGNORED_PROTOCOLS=tunnel
```

`INBOUND_IDS` has the highest precision. After the first `/inbounds` test it is recommended to set exact IDs.

## API behavior

The bot first tries:

```text
GET /panel/api/inbounds/options
```

and falls back to:

```text
GET /panel/api/inbounds/list
```

if the installed 3x-ui build does not expose the lightweight endpoint.
