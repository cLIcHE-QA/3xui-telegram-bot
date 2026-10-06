# A-011 / A-012 production acceptance — 2026-10-06

Статус: **PENDING production smoke**.

Этот документ фиксирует уже выполненную implementation/CI часть и оставляет отдельным gate фактическую проверку на production Master VPS.

## A-011 / #244 — least-privilege bot container

Merged implementation:

- PR #268 → `a9ab0c02b019bbaa086d72bd02749543bca9e796`
- rollout fix PR #269 → `d3f0611060292e0609a10128e1351bcfdbabe18f`
- required CI:
  - PR #268 Python checks run `37474609300` — PASS
  - PR #269 Python checks run `37483324260` — PASS

Expected runtime contract:

- UID/GID `10001:10001`
- `CapEff=0000000000000000`
- `NoNewPrivs=1`
- root filesystem read-only
- `/app/data` writable
- `/tmp` writable bounded tmpfs
- backup/config/log mounts readable and read-only
- no Docker socket
- no restart loop

Production commands:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
sudo apt-get install -y acl
sudo bash scripts/prepare-bot-container-permissions.sh

docker compose --env-file .env -f docker-compose.yml config --quiet
docker compose --env-file .env -f docker-compose.yml up -d --build --force-recreate bot

cid="$(docker compose --env-file .env -f docker-compose.yml ps -q bot)"
docker inspect --format '{{.Config.User}}' "$cid"
docker exec "$cid" sh -c 'id; grep -E "^(CapEff|NoNewPrivs):" /proc/self/status'
./scripts/deploy-release.sh --status
~~~

Required acceptance evidence:

- health = ok
- SQLite quick_check = ok
- upstream 3x-ui connectivity = ok
- RestartCount remains 0 after observation window
- Full Backup succeeds
- recovery preflight succeeds without destructive restore
- representative client subscription refresh succeeds
- representative Owner/Admin flow succeeds
- backup/log read-only sources remain readable after a new log file / SQLite WAL/SHM appears

Do not close #244 until these checks are recorded.

## A-012 / #245 — subscription proxy resource bounds

Merged implementation:

- PR #270 → `8485346f0fbe99732a7e4b3d69f9ca28f96ac1af`
- PR #270 Python checks run `37488293491` — PASS

Application bounds:

- global upstream concurrency = 32
- upstream slot wait = 1 second, then HTTP 503 + `Retry-After: 1`
- max upstream response body = 8 MiB
- response body read is chunk-bounded

Canonical public nginx policy:

- per-client `limit_conn = 4`
- `limit_req = 5r/s`
- burst = 10
- `proxy_read_timeout = 25s`
- `/compat/` access log stays disabled because URI contains bearer-like `sub_id`

Required production/load acceptance:

1. Apply the documented nginx `limit_req_zone` / `limit_conn_zone` directives and validate with `nginx -t`.
2. Normal real subscription refresh through `/compat/{sub_id}` returns expected content.
3. Burst/parallel requests from one controlled source hit front-door bounds without crashing/restarting the bot.
4. Saturation returns bounded 503/429-class behavior; no unbounded queue growth.
5. Oversized upstream response is rejected rather than buffered beyond 8 MiB.
6. Health endpoint remains responsive during/after the load test.
7. Final `./scripts/deploy-release.sh --status` is healthy and RestartCount does not increase unexpectedly.

Do not put a real `sub_id` into terminal history copied to issues/chat. Use a controlled test subscription and redact credentials in evidence.

## Closure

A-011 and A-012 move to Closed only after the production evidence above is captured in this document/issue comments.
