# A-011 / A-012 production acceptance — 2026-10-06

Статус: **A-011 PASS; A-012 PENDING production/load acceptance**.

A-011 production retest успешно завершён на опубликованном `v4.26.8`. A-012 остаётся отдельным gate и начинается только после успешного runtime acceptance A-011.

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

## Production attempt v4.26.7 — FAIL

Release under test:

- tag: `v4.26.7`;
- SHA: `70acd009a3d1546c96c0852544b99c5569541a88`.

Observed status immediately after deployment:

- Container: running/restarting;
- `RestartCount=10`;
- Bot version: `unknown`;
- Health: `failed`;
- DB: `failed`;
- Docker subnet: `172.19.0.0/16`;
- 3x-ui connectivity: `failed`.

Primary container log:

~~~text
python: can't open file '/app/restore_bootstrap.py': [Errno 13] Permission denied
~~~

Root cause: Docker `COPY . .` preserved restrictive source modes from the production checkout/build context, while the image switched runtime to UID/GID `10001:10001`. The application tree therefore remained root-owned but was not guaranteed readable/traversable by the non-root runtime.

Disposition:

- A-011 acceptance: **FAIL / remediation required**;
- A-012 production/load acceptance: **not started**, because the runtime startup gate failed first;
- no evidence of SQLite/3x-ui regression is inferred from downstream `failed` values because the process never reached bootstrap/runtime initialization;
- remediation must normalize application-tree ownership/modes inside the image independently of host checkout umask and add a restrictive-build-context regression smoke.

Remediation status:

- fix PR #279 merged as `6ebdd5e5bb67e741ce643de853c50c90889a45f3`;
- application tree remains root-owned but is normalized inside the image with `u=rwX,go=rX`;
- PR #279 `Python checks` run `37522004615` — PASS, including restrictive-`0600` container smoke;
- PR #279 `Supply-chain audit` run `37522004528` — PASS;
- post-merge `main` `Python checks` run `37522213218` — PASS;
- post-merge `main` `Supply-chain audit` run `37522213135` — PASS;
- production retest must use published hotfix `v4.26.8`; successful CI does not close A-011.

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

## Production retest v4.26.8 — PASS

Release under test:

- tag: `v4.26.8`;
- SHA: `e096bf436425ea037399e290a5a54f54c729b352`.

Recovery/deploy context:

- перед переключением сохранена отдельная SQLite-consistent rescue copy текущего production state;
- exact published tag/SHA проверен до checkout;
- Compose config validation — PASS;
- image пересобран из exact `v4.26.8`, после чего только bot container был force-recreated.

Runtime evidence:

- Container: `running`;
- `RestartCount=0` как сразу после recreate, так и после backup/preflight/client smoke;
- Bot version: `4.26.8`;
- Health: `ok`;
- DB: `ok`;
- Docker subnet: `172.19.0.0/16`;
- 3x-ui connectivity: `ok`;
- image/runtime user: `10001:10001`;
- runtime identity: `uid=10001(bot) gid=10001(bot)`;
- `ReadOnlyRootfs=true`;
- `CapDrop=["ALL"]`;
- `SecurityOpt=["no-new-privileges:true"]`;
- `CapEff=0000000000000000`;
- `NoNewPrivs=1`;
- only `/app/data` is a writable bind mount; bot env, x-ui, nginx config and nginx log sources are read-only;
- `/tmp` is bounded tmpfs: `rw,nosuid,nodev,noexec,size=64m,mode=1777`;
- Docker socket is absent inside the container.

Filesystem/ACL propagation evidence:

- host permission helper completed with runtime UID/GID `10001:10001`;
- controlled new `0600` x-ui WAL-like and nginx log probe files inherited ACLs;
- both new files were readable but not writable from the bot container;
- result: `ACL_INHERITANCE=ok`.

Backup/recovery evidence:

- manual Full Backup — PASS;
- included `bot.sqlite3`, Master `x-ui.db`, `bot.env`, `docker-compose.yml`, nginx snapshot and configured Finland node snapshot;
- encrypted off-site copy upload/verification — PASS;
- DR deep preflight on the new Full Backup — PASS;
- archive manifest version: `4.26.8`;
- `bot.sqlite3 quick_check` — PASS;
- `x-ui.db quick_check` — PASS;
- archived `PANEL_API_TOKEN` matched current runtime config;
- preflight explicitly completed without modifying data.

Representative flows:

- Owner/Admin path through `/admin → System → Backups` successfully created the Full Backup;
- Owner-only Disaster Recovery preflight successfully inspected the backup without restore;
- representative real client subscription refresh through the production compat path succeeded, returned the normal profile/list and produced no empty/error response.

Final status after all smoke operations:

~~~text
Git tag: v4.26.8
Git SHA: e096bf436425ea037399e290a5a54f54c729b352
Container: running
RestartCount=0
Bot version: 4.26.8
Health: ok
DB: ok
Docker subnet: 172.19.0.0/16
3x-ui connectivity: ok
~~~

Disposition:

- A-011 production/runtime acceptance: **PASS**;
- regression from `v4.26.7` is remediated and verified on production;
- #244 may close once this evidence change lands on `main`;
- A-012 production/load acceptance is now unblocked but remains **PENDING**.

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
