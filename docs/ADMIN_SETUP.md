# Admin Setup: установка и настройка Admin Control Plane

Этот runbook описывает полное развёртывание и operational-настройку административного контура 3x-ui Telegram Bot с чистых VPS: Master, одна или несколько direct nodes, Host Control Agent и Extended direct-node backup с nginx snapshot.

Scope документа — только **Admin Control Plane**. Client Portal v5 уже реализован для ограниченного pilot allowlist, но полный production acceptance ещё не завершён; этот runbook не является инструкцией по публичному запуску клиентского интерфейса или приёму новых реальных платежей. Условия контролируемой приёмки описаны в [v5 Production Acceptance](V5_PRODUCTION_ACCEPTANCE.md). Пилотная настройка client-facing функции описана в [CLIENT_SETUP.md](CLIENT_SETUP.md) и **не** разрешает общедоступный rollout; административный deployment flow здесь не смешивается с клиентским.

## Как поддерживать это руководство

`docs/ADMIN_SETUP.md` — канонический runbook установки и настройки Admin Control Plane. Если новая функция или изменение требует от оператора дополнительных действий, это руководство обновляется одновременно с соответствующим PR.

Сюда обязательно попадают новые или изменённые `.env`-параметры, системные пакеты, Docker/network/firewall настройки, DNS/TLS, systemd services/timers, Host Control, credentials/enrollment, backup/restore, migrations и любые новые обязательные preflight/post-deploy шаги. Если ручная настройка для функции не требуется, отдельный раздел добавлять не нужно.

Руководство описывает актуальный безопасный путь установки с нуля; исторические изменения и release history остаются в `CHANGELOG.md`.

Целевой результат:

~~~text
Master VPS
├─ 3x-ui (native systemd: x-ui.service)
├─ Telegram bot (Docker Compose)
├─ Host Control Agent + restricted local proxy
├─ Safe Bot Self-Update Deploy Agent (v4.19+, host systemd)
└─ Full Backup
   ├─ bot.sqlite3
   ├─ Master x-ui.db
   ├─ Master nginx/
   └─ nodes/<node>/
      ├─ x-ui.db
      ├─ nginx/
      ├─ node.json
      └─ manifest.json

Direct Node VPS
├─ 3x-ui (native systemd: x-ui.service)
├─ Host Control Agent on 127.0.0.1:18181
├─ restricted HTTPS management proxy
└─ local HOST_CONTROL_AGENT_NGINX_SOURCE
~~~

Guide ориентирован на release v5.0.0-rc.8. До его официальной публикации и отдельного controlled deployment production остаётся на v5.0.0-rc.7. RC объединяет прежний Full Backup fix #348/#349, Owner-only сброс клиентского ограничителя #345, косметическую очистку оплаченных Stars invoice #320 и SQLite schema v13. Перед развёртыванием обязателен проверенный backup и preflight миграции v11→v13; простой downgrade к rc.7 после обновления DB запрещён. После controlled deployment сначала проверь точный tag/SHA, Health/SQLite/3x-ui, затем manual Full Backup, off-site download/decrypt/deep validation и следующий scheduled backup/off-site cycle; прошлый `rc.6` backup нельзя считать PASS. Не изменяй права DB/WAL/SHM, не запускай реальные payments/refunds ради проверки backup. Public launch и stable release остаются заблокированы до общего v5 acceptance. Все privileged connections используют отдельные credentials и stable node_id binding.

> Начиная с `v4.14.2` guided wrapper `scripts/onboard-direct-node.sh bind` исправлен и является рекомендуемым путём для регистрации node и обоих privileged bindings. Underlying helpers остаются доступным manual fallback.

## 0. Что понадобится

Для каждого VPS:

- Ubuntu 22.04/24.04 или Debian 12+;
- root/sudo;
- публичный IPv4;
- DNS имя для 3x-ui panel;
- verified TLS certificate;
- native 3x-ui installation, создающая x-ui.service;
- UFW или эквивалентный provider firewall.

Для Master дополнительно:

- Telegram Bot token;
- numeric Telegram ID как минимум одного Owner;
- read-only доступ к **публичному** GitHub repository; для host-side Deploy Agent — отдельный read-only SSH deploy key и проверенный `known_hosts`;
- Docker Engine + Docker Compose plugin;
- Git;
- Python 3 + venv для локальных onboarding helpers.

Для каждой direct node понадобятся три независимых privilege domain:

1. node-sync token: Master 3x-ui → node;
2. dedicated admin-scope token: bot → direct 3x-ui API;
3. Host Control token: создаётся автоматически Host Control Agent installer.

Не переиспользуй один token в нескольких domains.

> **Cloudflare WARP — не prerequisite.** Установка, настройка DNS/egress, full/split tunnel и risk/rollback описаны отдельно в [опциональном WARP runbook](WARP_SETUP.md). Не подключай WARP на production Master/direct node в процессе обычного Admin Setup: хостовый VPN способен нарушить SSH, 3x-ui, Host Control, Docker и клиентский data plane. Требуются отдельные change approval и out-of-band console.

## 1. Сначала подготовь 3x-ui на всех VPS

Этот repository не устанавливает и не обновляет сам 3x-ui при первоначальной установке.

Используй актуальную upstream документацию:

- https://github.com/MHSanaei/3x-ui/wiki/Installation
- https://github.com/MHSanaei/3x-ui

Для Host Control нужен именно systemd service x-ui.service. После установки на каждом VPS:

~~~bash
systemctl is-enabled x-ui.service
systemctl is-active x-ui.service
~~~

Ожидается enabled и active.

Настрой для каждой панели:

- HTTPS;
- валидный certificate;
- уникальный panel hostname/base path;
- API credentials/tokens;
- subscription URL;
- нужные Inbounds.

Для каждого client-facing Inbound отдельно проверь data-plane address и host firewall. В текущей production policy panel URL / `Node.address` остаётся control-plane hostname, а client dial endpoint задаётся явным public IP через `shareAddrStrategy=custom`; SNI/Reality names при этом не переписываются. Полный addressing/firewall contract и post-onboarding smoke: [Data-plane addressing and inbound firewall](DATA_PLANE_ADDRESSING.md).

Client-side routing profiles Happ/Incy настраиваются отдельно от server-side Xray/data-plane. Общий operator contract, native-vs-compat boundary и acceptance: [Subscription client routing](SUBSCRIPTION_ROUTING.md).

Не переходи к bot onboarding, пока Master и node panel URL не открываются с verified TLS.

Для bot release `v5.0.0-rc.8` машинно проверяемый native API contract pinned к 3x-ui `v3.9.0`. Более новая версия панели не принимается автоматически как совместимая: перед плановым upgrade сначала обновляется и проходит review OpenAPI contract из `docs/3XUI_OPENAPI_CONTRACT.md`.

## 2. Базовая подготовка Master VPS

Установи системные пакеты:

~~~bash
sudo apt update
sudo apt install -y git curl ca-certificates python3 python3-venv openssl acl
~~~

Docker Engine и Compose plugin устанавливай по официальной инструкции:

https://docs.docker.com/engine/install/

Проверка:

~~~bash
docker version
docker compose version
systemctl is-active docker
~~~

## 3. Получи release бота

Репозиторий **публичный**: его можно клонировать по HTTPS без GitHub credentials. Для контролируемого host-side Deploy Agent всё равно требуется отдельный read-only SSH deploy key и проверенный `known_hosts` согласно [Safe Bot Self-Update](BOT_SELF_UPDATE.md); публичность исходников не отменяет защиту privileged операций. Не записывай GitHub token в repository или `.env`.

~~~bash
sudo mkdir -p /opt/3xui-bot
sudo chown "$(id -u):$(id -g)" /opt/3xui-bot
cd /opt/3xui-bot

git clone https://github.com/cLIcHE-QA/3xui-telegram-bot.git
cd 3xui-telegram-bot

git fetch --tags --prune
git checkout --detach v5.0.0-rc.8
~~~

Проверка release:

~~~bash
python3 - <<'PY'
from version import APP_VERSION
print(APP_VERSION)
PY
~~~

Ожидается:

~~~text
5.0.0-rc.8
~~~

## 4. Создай local admin venv

Bot работает в Docker, но onboarding helper onboard-node.py использует Python dependencies repository и запускается на Master host. На чистом VPS создай отдельный venv:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
python3 -m venv .venv-admin
.venv-admin/bin/python -m pip install --upgrade pip
.venv-admin/bin/python -m pip install -r requirements.txt
~~~

В дальнейшем команды вида:

~~~text
.venv-admin/bin/python scripts/...
~~~

запускаются из repository root.

## 5. Настрой .env бота

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
cp .env.example .env
chmod 600 .env
sudoedit .env
~~~

Минимально проверь следующие значения:

~~~env
BOT_TOKEN=<telegram-bot-token>

PANEL_URL=https://master-panel.example.com/basepath
PANEL_API_TOKEN=<master-dedicated-admin-api-token>
VERIFY_TLS=true

SUBSCRIPTION_URL_TEMPLATE=https://subscription.example.com/sub/{sub_id}
COMPAT_SUBSCRIPTION_URL_TEMPLATE=

# v5 payment webhook ingress remains disabled until a provider secret and
# verified-HTTPS reverse-proxy route are prepared.
PAYMENT_WEBHOOK_ENABLED=false
PAYMENT_WEBHOOK_PROVIDER=generic_hmac
PAYMENT_WEBHOOK_SECRET=

# Optional customer checkout creation; keep disabled until the verified HTTPS
# payment backend is prepared.
PAYMENT_CHECKOUT_ENABLED=false
PAYMENT_CHECKOUT_PROVIDER=generic_hmac
PAYMENT_CHECKOUT_ENDPOINT=
PAYMENT_CHECKOUT_SECRET=

ALLOWED_TELEGRAM_IDS=<your-telegram-id>
ADMIN_TELEGRAM_IDS=<your-telegram-id>

BACKUP_ENABLED=true
BACKUP_DIR=/app/data/backups
BACKUP_KEEP=14
BACKUP_HOUR_UTC=2

# Optional, disabled until a physically/logically separate S3-compatible target
# and a separately stored recovery encryption key are prepared.
OFFSITE_BACKUP_ENABLED=false
OFFSITE_BACKUP_BUCKET=
OFFSITE_BACKUP_PREFIX=3xui-bot
OFFSITE_BACKUP_REGION=us-east-1
OFFSITE_BACKUP_ENDPOINT_URL=
OFFSITE_BACKUP_ACCESS_KEY_ID=
OFFSITE_BACKUP_SECRET_ACCESS_KEY=
OFFSITE_BACKUP_KEEP=14
OFFSITE_BACKUP_ENCRYPTION_KEY_B64=

# Optional until the v4.19+ host-side Deploy Agent is installed.
DEPLOY_AGENT_URL=
DEPLOY_AGENT_TOKEN=

# Optional read-only blocking diagnostics. Leave empty until Cheburcheck is deployed.
CHEBURCHECK_URL=
CHEBURCHECK_VERIFY_TLS=true

# Optional Google PageSpeed Insights for v4.24+ web diagnostics.
# Leave empty to keep only PageSpeed disabled; other diagnostics still work.
PAGESPEED_API_KEY=

MASTER_NAME=Master
MASTER_FLAG=🖥

BOT_DOCKER_SUBNET=172.19.0.0/16

HOST_CONTROL_TARGETS=
NODE_BACKUP_TARGETS=
~~~

ADMIN_TELEGRAM_IDS — break-glass Owners. Не добавляй туда случайных пользователей.


### Subscription compatibility proxy: отдельные limits для browser assets

Если публичный `COMPAT_SUBSCRIPTION_URL_TEMPLATE` включён через nginx, не применяй customer-профиль `5r/s + burst=10 + conn=4` к `/compat/assets/`. 3x-ui subscription SPA использует Vite `modulepreload`; Safari/WebKit может одновременно запросить десятки JS/CSS resources. При общем строгом `location /compat/` nginx начинает отвечать `503` части bundles, и Safari остаётся на белой странице, даже если Chrome/Firefox работают.

В `http {}` используй отдельные bounded zones для assets:

~~~nginx
limit_req_zone $binary_remote_addr zone=sub_compat_rate:10m rate=5r/s;
limit_conn_zone $binary_remote_addr zone=sub_compat_conn:10m;

limit_req_zone $binary_remote_addr zone=sub_compat_assets_rate:10m rate=40r/s;
limit_conn_zone $binary_remote_addr zone=sub_compat_assets_conn:10m;
~~~

В public `server {}` более специфичный `location ^~ /compat/assets/` должен идти отдельно от `location ^~ /compat/` и использовать `sub_compat_assets_rate burst=80` + `sub_compat_assets_conn 32`. Customer subscription route сохраняет прежние `sub_compat_rate burst=10` + `sub_compat_conn 4`. Для обоих routes оставляй `access_log off`, `proxy_buffering off`, `proxy_request_buffering off`, `proxy_max_temp_file_size 0` и существующие timeout/header settings.

Это не снимает общий application bound: `subscription_proxy.py` по-прежнему ограничивает upstream до 32 concurrent fetch и 8 MiB на response. После изменения обязательно:

~~~bash
sudo nginx -t
sudo systemctl reload nginx
~~~

Targeted smoke: открыть subscription page в приватном окне Safari/WebKit и убедиться, что `/compat/assets/*.js|css` не получают HTTP 503.

### Optional v5 checkout provider

Customer checkout отключён по умолчанию. При включении `PAYMENT_CHECKOUT_ENABLED=true` требуется fixed verified HTTPS `PAYMENT_CHECKOUT_ENDPOINT` без credentials/query/fragment и отдельный `PAYMENT_CHECKOUT_SECRET` минимум 32 bytes.

Bot отправляет bounded JSON с локальными `order_id`, `amount_minor`, `currency` и deterministic `idempotency_key=order:<id>`; request подписывается HMAC-SHA256 и содержит тот же `Idempotency-Key` header. Endpoint должен вернуть provider identity `payment_id` и HTTPS `checkout_url`.

Timeout/network/HTTP 5xx считаются uncertain outcome. Bot не генерирует новый idempotency key и не создаёт второй локальный payment при retry. Доступ пользователя меняется только после отдельно аутентифицированного `payment.confirmed` webhook; сам checkout response entitlement не создаёт.

### Optional v5 payment webhook ingress

Первый provider-facing contract v5 использует тот же HTTP listener, что и compatibility subscription proxy, но отдельный route:

~~~text
POST /webhooks/payments/{provider}
~~~

До настройки payment provider держи `PAYMENT_WEBHOOK_ENABLED=false`. При включении route должен публиковаться наружу только через verified HTTPS reverse proxy. `PAYMENT_WEBHOOK_SECRET` — отдельный secret минимум 32 bytes; его нельзя переиспользовать как Telegram token, 3x-ui API token, deploy/host-control token или любой другой credential.

Текущий provider-neutral adapter `generic_hmac` принимает bounded JSON body (до 64 KiB) с `event_id`, `type`, `payment_id` и optional `metadata`. Подпись передаётся в `X-Payment-Signature` как raw hex SHA-256 или `sha256=<hex>` и вычисляется HMAC-SHA256 по exact raw request body. В finance lifecycle применяется только `payment.confirmed`; unsupported event types journaled/ignored и не меняют payment/order/entitlement. Invalid signature также journaled как auth failure и никогда не меняет финансовое состояние.

HTTP access log для встроенного listener отключён, поэтому bearer-like subscription IDs и webhook paths не должны попадать в aiohttp access log. Raw payment payload не сохраняется в DB: commerce journal хранит только SHA-256 и bounded safe metadata.

### Optional Cheburcheck diagnostics

В линии `v4.23.x` доступен read-only экран `/admin → Мониторинг → Проверка блокировок`; `v4.23.1` исправил acceptance-дефект ASN response limit; `v4.23.2` добавил compact result и context-preserving navigation; `v4.23.3` исправляет production findings этого compact result: explicit CDN negative state, bounded ASN enrichment для domain/IP и честный regional probe status. Экран не нужен для core startup, provisioning или 3x-ui control plane.

Предпочтительный production path — pinned self-hosted Cheburcheck service во внутренней сети. После его отдельного deployment укажи fixed endpoint:

~~~env
CHEBURCHECK_URL=http://cheburcheck:8000
CHEBURCHECK_VERIFY_TLS=true
~~~

Для remote endpoint используй verified HTTPS. HTTPS с `CHEBURCHECK_VERIFY_TLS=false` запрещён; plain HTTP допустим только для private/local address или внутреннего service name.

Если `CHEBURCHECK_URL` пуст, функция остаётся выключенной, а бот работает без деградации остальных возможностей. Канонический integration/security/acceptance contract: [Cheburcheck integration](CHEBURCHECK.md). Воспроизводимая VPS-настройка отдельного pinned backend + PostgreSQL 18, internal-only networking, health checks и rollback зафиксирована в [Cheburcheck deployment](CHEBURCHECK_DEPLOY.md).

### Optional PageSpeed diagnostics

`/admin → Мониторинг → Мониторинг сайтов → Разовая диагностика → PageSpeed` использует Google PageSpeed Insights только когда локально задан API key. По умолчанию интеграция остаётся выключенной:

~~~env
PAGESPEED_API_KEY=
~~~

Включай её только если оператору нужен внешний performance score для публичных страниц. Uptime/incident monitoring, DNS/WHOIS/HTTP/redirect/CMS/SEO/Sitemap/URL-list/QR от PageSpeed не зависят.

Для будущего включения:

1. в отдельном Google Cloud project включи **PageSpeed Insights API**;
2. создай отдельный API key только для этой интеграции;
3. ограничь key по API до PageSpeed Insights API; если у Master стабильный public egress IP, дополнительно используй server/IP application restriction;
4. локально на Master добавь key в mode-0600 `.env`:

~~~env
PAGESPEED_API_KEY=<google-pagespeed-api-key>
~~~

5. пересоздай только bot container, чтобы новое environment попало в runtime:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
docker compose \
  --project-name 3xui-telegram-bot \
  --env-file .env \
  -f docker-compose.yml \
  up -d --force-recreate bot
~~~

6. проверь базовый runtime status:

~~~bash
./scripts/deploy-release.sh --status
~~~

7. в Telegram открой monitored site → `🩺 Диагностика` → `⚡ PageSpeed`. При успешной конфигурации карточка показывает bounded `Performance: N/100` и, когда provider её возвращает, `Field category`.

Ключ не вводится через Telegram, не сохраняется в SQLite/audit и не показывается в UI. Target URL перед обращением к PageSpeed проходит тот же public HTTP(S) validation boundary, но сам публичный URL передаётся внешнему Google API; не запускай эту диагностику для URL с чувствительными query-параметрами/токенами.

Чтобы снова выключить интеграцию, оставь `PAGESPEED_API_KEY=`, пересоздай bot container тем же Compose command и повтори `--status`. Пустая переменная является штатным состоянием: PageSpeed отображается как `не настроен`, остальные diagnostics продолжают работать.

### Master backup paths

Укажи реальные host paths до Master 3x-ui SQLite directory и nginx configuration:

~~~env
BACKUP_XUI_DIR_HOST_PATH=/etc/x-ui
BACKUP_NGINX_CONF_HOST_PATH=/opt/mtproxyl-nginx/conf
NGINX_LOG_HOST_PATH=/var/log/nginx
~~~

Если используется system nginx, nginx path может быть:

~~~env
BACKUP_NGINX_CONF_HOST_PATH=/etc/nginx
~~~

До первого запуска проверь path:

~~~bash
test -d /etc/x-ui
test -d /opt/mtproxyl-nginx/conf
~~~

Не оставляй заведомо несуществующий nginx path: Docker bind mount может создать пустой directory и скрыть ошибку настройки.

### Сбой Master backup после обновления 3x-ui (WAL/ACL)

На `v5.0.0-rc.6` после обновления панели `3x-ui v3.8.5 → v3.9.0` наблюдался `backup.daily=success`, но `backup.offsite=failed` / `x-ui.db: not SQLite3`. В архиве `x-ui.db` был пустым. База на Master работала; ошибка происходила из-за файловых ACL на `x-ui.db`, `x-ui.db-wal`, `x-ui.db-shm`: `user:10001:r--` при `mask::---` означает `#effective:---`. Это не является доказательством повреждения 3x-ui DB.

**Диагностика без изменения production:**

```bash
sudo getfacl -cp /etc/x-ui/x-ui.db /etc/x-ui/x-ui.db-wal /etc/x-ui/x-ui.db-shm
sudo stat -c '%a %u:%g %s %n' /etc/x-ui/x-ui.db /etc/x-ui/x-ui.db-wal /etc/x-ui/x-ui.db-shm
```

На legacy runtime, читающем SQLite через readonly bind mount, временно можно исправить **только существующие** ACL-маски, если назначенные ACL `user:10001:r--` уже присутствуют:

```bash
sudo setfacl -m 'm::r--' /etc/x-ui/x-ui.db /etc/x-ui/x-ui.db-wal /etc/x-ui/x-ui.db-shm
```

Проверить чтение из контейнера read-only URI, не изменяя БД:

```bash
docker compose exec -T bot python - <<'PY'
import sqlite3
with sqlite3.connect(
    "file:/app/backup_sources/x-ui/x-ui.db?mode=ro", uri=True, timeout=10
) as db:
    print("journal_mode:", db.execute("PRAGMA journal_mode").fetchone()[0])
    print("quick_check:", db.execute("PRAGMA quick_check").fetchone()[0])
PY
```

Ожидается `wal` и `ok`. Изменение ACL временное: 3x-ui может вновь применить `chmod 0600` на DB/WAL/SHM при обновлении или перезапуске. Не использовать `chmod 777`, `immutable=1` для работающей базы, удаление WAL/SHM или запись в sqlite mount. В production runtime после fix #349 Master Full Backup получает согласованный SQLite export через штатный `GET /panel/api/server/getDb` с существующим `PANEL_API_TOKEN`; filesystem ACL для DB больше не является основным backup path. API failure **не** вызывает filesystem fallback и не считается успешным backup.

После внедрения нового immutable релиза подтвердить отдельно: manual Full Backup deep validation, `backup.daily` scheduled success и `backup.offsite` encrypted upload → download → decrypt → deep validation. Не считать прошлый rc.6 scheduled backup PASS задним числом.

### Least-privilege filesystem preparation

Bot image запускается как dedicated UID/GID `10001:10001`, root filesystem container-а read-only, Linux capabilities полностью dropped, а `no-new-privileges` включён. Writable runtime paths ограничены `/app/data` и tmpfs `/tmp`.

До первого запуска и после переноса существующего installation на этот security baseline подготовь host permissions:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
sudo bash scripts/prepare-bot-container-permissions.sh
~~~

Helper:

- переводит `./data` под ownership `10001:10001` и private modes;
- даёт runtime UID только read/traverse ACL к `.env`, 3x-ui backup source, nginx config и nginx logs;
- не делает source mounts writable;
- fail-closed, если source directory отсутствует или host не имеет `setfacl`.

После helper проверь, что sensitive host files не стали world-readable:

~~~bash
stat -c '%a %u:%g %n' .env
getfacl -cp .env | sed -n '1,12p'
~~~

`.env` остаётся host-owned и mode-0600; доступ container UID предоставляется отдельным ACL entry. Для backup/log source trees helper также ставит default ACL на directories, чтобы новые SQLite WAL/SHM, rotated nginx logs и новые config files наследовали read access для runtime UID. ACL нужен, потому что non-root container больше не обходит host Unix permissions как UID 0.

При изменении `BACKUP_XUI_DIR_HOST_PATH`, `BACKUP_NGINX_CONF_HOST_PATH` или `NGINX_LOG_HOST_PATH` повторно запусти permission helper до recreate bot container. Root-owned Safe Bot Self-Update вызывает helper автоматически после checkout target release и до recreate. Ручной non-root deployment fail-closed просит выполнить helper через `sudo` заранее.

## 6. Firewall Master для panel access из bot container

Если PANEL_URL ведёт на публичный адрес панели на том же Master VPS, firewall должен пропускать panel port из BOT_DOCKER_SUBNET.

Пример для panel port 2096:

~~~bash
sudo ufw allow from 172.19.0.0/16 to any port 2096 proto tcp comment '3xui bot docker network'
~~~

Подставь фактический panel port. Если BOT_DOCKER_SUBNET меняется, firewall rule меняется вместе с ним.

## 7. Первый запуск bot

Сначала validate Compose:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
docker compose --env-file .env -f docker-compose.yml config --quiet
~~~

Запуск:

~~~bash
docker compose --env-file .env -f docker-compose.yml up -d --build
~~~

Проверь runtime least privilege:

~~~bash
cid="$(docker compose --env-file .env -f docker-compose.yml ps -q bot)"
docker inspect --format '{{.Config.User}}' "$cid"
docker exec "$cid" sh -c 'id; grep -E "^(CapEff|NoNewPrivs):" /proc/self/status'
~~~

Ожидается:

- image user: `10001:10001`;
- effective capabilities: `0000000000000000`;
- `NoNewPrivs: 1`.

Root filesystem должен быть read-only; writable остаются только `/app/data` и bounded tmpfs `/tmp`.

Проверки:

~~~bash
curl -fsS http://127.0.0.1:18080/healthz
~~~

Ожидается:

~~~text
ok
~~~

Затем:

~~~bash
./scripts/deploy-release.sh --status
~~~

Проверь:

- Container: running;
- RestartCount=0;
- Bot version: соответствует установленному release;
- Health: ok;
- DB: ok;
- 3x-ui connectivity: ok.

В Telegram открой /admin. Пользователь из ADMIN_TELEGRAM_IDS должен получить Owner access.

## 8. Host Control для Master

Host Control Agent не даёт bot container shell/Docker/systemd access. Он умеет только фиксированные операции для x-ui.service и отдельные read-only endpoints.

При BOT_DOCKER_SUBNET=172.19.0.0/16 стандартный bridge address:

~~~text
172.19.0.1
~~~

Установка:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot

sudo scripts/setup-host-control-endpoint.sh master \
  --alias MASTER \
  --host-id master \
  --name Master \
  --bridge-ip 172.19.0.1 \
  --docker-subnet 172.19.0.0/16 \
  --proxy-port 18182 \
  --apply-ufw
~~~

Installer создаёт:

~~~text
/root/3xui-host-control-master.env
~~~

Это secret-bearing enrollment. Не выводи его через cat и не вставляй в chat/issues.

Preflight:

~~~bash
.venv-admin/bin/python scripts/import-host-control-enrollment.py \
  /root/3xui-host-control-master.env \
  --env .env \
  --check-only
~~~

Импорт и recreate только bot:

~~~bash
.venv-admin/bin/python scripts/import-host-control-enrollment.py \
  /root/3xui-host-control-master.env \
  --env .env \
  --recreate-bot
~~~

Проверка host services:

~~~bash
systemctl is-active 3xui-host-control.service
systemctl is-active 3xui-host-control-proxy.service
ss -ltn | grep -E ':(18181|18182)\b'
~~~

Agent должен слушать только 127.0.0.1:18181, а Master proxy — только private bridge address.

После успешной проверки enrollment file можно удалить:

~~~bash
sudo rm -f /root/3xui-host-control-master.env
~~~

## 8A. Safe Bot Self-Update Deploy Agent на Master

Начиная с v4.19 bot может обновлять сам себя только через отдельный restricted Deploy Agent. Первый v4.19 release по-прежнему устанавливается вручную через `scripts/deploy-release.sh`; затем host-side agent подключается отдельно.

Deploy Agent не является расширением Host Control Agent. Это отдельный privilege domain:

- отдельный system user `3xui-deploy`;
- отдельный bearer token;
- отдельный persistent journal;
- отдельная root-owned helper boundary;
- отдельная root-only копия read-only Git deploy key и SSH known_hosts;
- только published tag `vX.Y.Z`;
- никаких shell/argv/path/env полей из Telegram.

После ручного deploy v4.19:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
sudo ./scripts/install-deploy-agent.sh
~~~

Проверка:

~~~bash
systemctl is-enabled 3xui-deploy-agent.service
systemctl is-active 3xui-deploy-agent.service
~~~

Если UFW блокирует INPUT на Master, добавь fixed allow только из `BOT_DOCKER_SUBNET` к bridge listener:

~~~bash
sudo ufw allow from 172.19.0.0/16 to 172.19.0.1 port 18184 proto tcp comment '3xui bot deploy agent'
~~~

Port 18184 не публикуется в Internet.

Token хранится в `/etc/3xui-deploy-agent/token` и не печатается installer-ом. Его нужно перенести в production `.env` локально, не через Telegram/chat:

~~~env
DEPLOY_AGENT_URL=http://172.19.0.1:18184
DEPLOY_AGENT_TOKEN=<dedicated-agent-token>
~~~

После изменения `.env` validate Compose и recreate только bot service. Затем `/admin → Система → Обновления бота` должен показывать текущий production release и latest published release.

Полный security/recovery/install contract: [Safe Bot Self-Update](BOT_SELF_UPDATE.md).

## 9. Подготовь direct node

Ниже пример для одной ноды:

~~~text
Alias: NODE1
Name: Edge-1
Host ID: edge-1
Node panel: https://panel-node1.example.com/basepath
Host Control URL: https://host-control-node1.example.com:18443
Master public IP: MASTER_PUBLIC_IP
Node public IP: NODE_PUBLIC_IP
SSH port: SSH_PORT
~~~

Для следующей node повтори flow с уникальными Alias, Name, Host ID и credentials.

На node заранее должны быть:

- active x-ui.service;
- verified HTTPS panel;
- node-sync token;
- отдельный admin-scope token;
- DNS hostname;
- certificate/key, соответствующие Host Control public hostname.

## 10. Собери Host Control bundle на Master

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot

bash scripts/build-host-control-bundle.sh \
  /root/3xui-host-control-bundle-v5.0.0-rc.8.tar.gz
~~~

Передай только secret-free bundle и checksum:

~~~bash
scp -P SSH_PORT \
  /root/3xui-host-control-bundle-v5.0.0-rc.8.tar.gz \
  /root/3xui-host-control-bundle-v5.0.0-rc.8.tar.gz.sha256 \
  root@NODE_PUBLIC_IP:/root/
~~~

## 11. Установи Host Control endpoint на node

На node проверь checksum:

~~~bash
cd /root
sha256sum -c 3xui-host-control-bundle-v5.0.0-rc.8.tar.gz.sha256
~~~

Распакуй:

~~~bash
rm -rf /root/3xui-host-control-install
mkdir -p /root/3xui-host-control-install

tar -xzf /root/3xui-host-control-bundle-v5.0.0-rc.8.tar.gz \
  -C /root/3xui-host-control-install
~~~

Установка restricted remote endpoint:

~~~bash
cd /root/3xui-host-control-install

sudo scripts/setup-host-control-endpoint.sh remote \
  --alias NODE1 \
  --host-id edge-1 \
  --name Edge-1 \
  --listen-ip NODE_PUBLIC_IP \
  --source-ip MASTER_PUBLIC_IP \
  --public-host host-control-node1.example.com \
  --cert /etc/letsencrypt/live/host-control-node1.example.com/fullchain.pem \
  --key /etc/letsencrypt/live/host-control-node1.example.com/privkey.pem \
  --proxy-port 18443 \
  --apply-ufw
~~~

Если certificate хранится в другом месте, передай реальные absolute paths.

Результат:

- agent: 127.0.0.1:18181;
- restricted HTTPS proxy: NODE_PUBLIC_IP:18443;
- firewall source: только MASTER_PUBLIC_IP;
- TLS refresh timer enabled;
- enrollment: /root/3xui-host-control-node1.env.

Проверка:

~~~bash
systemctl is-active 3xui-host-control.service
systemctl is-active 3xui-host-control-proxy.service
systemctl is-enabled 3xui-host-control-tls-refresh.timer
ss -ltn | grep -E ':(18181|18443)\b'
~~~

Не должно быть listener 0.0.0.0:18443.

## 12. Настрой nginx snapshot source на node

Extended direct-node backup не принимает path от Telegram/Master. Source directory задаётся только локально на node.

Сначала определи реальный config directory. Типовые варианты:

~~~text
/etc/nginx
/opt/mtproxyl-nginx/conf
~~~

Проверь выбранный path:

~~~bash
SOURCE=/opt/mtproxyl-nginx/conf
test -d "$SOURCE"
test ! -L "$SOURCE"
test "$SOURCE" != "/"
sudo -u 3xui-hostctl find "$SOURCE" -type f -readable -printf '.' | wc -c
~~~

Последняя команда должна вернуть ненулевое количество readable files.

Создай local source env:

~~~bash
sudo install -d -o root -g root -m 0755 /etc/3xui-host-control
sudo install -o root -g root -m 0644 /dev/null \
  /etc/3xui-host-control/nginx-snapshot.env
sudoedit /etc/3xui-host-control/nginx-snapshot.env
~~~

В файле должна быть одна строка:

~~~env
HOST_CONTROL_AGENT_NGINX_SOURCE=/opt/mtproxyl-nginx/conf
~~~

Restart только agent:

~~~bash
sudo systemctl restart 3xui-host-control.service
systemctl is-active 3xui-host-control.service
~~~

Installer v4.14.2 при будущих upgrades не перезаписывает nginx-snapshot.env и сам restart'ит agent после обновления runtime files.

## 13. Передай Host Control enrollment на Master

С Master забери secret-bearing enrollment по SSH:

~~~bash
scp -P SSH_PORT \
  root@NODE_PUBLIC_IP:/root/3xui-host-control-node1.env \
  /root/3xui-host-control-node1.env

chmod 600 /root/3xui-host-control-node1.env
~~~

Не используй cat, Telegram, issue или PR для передачи содержимого этого файла.

Пока не импортируй его без stable node_id.

## 14. Подготовь три enrollment-файла на Master

Создай три mode-0600 файла:

1. node-sync enrollment: `/root/3xui-node-node1.env`;
2. direct-admin enrollment: `/root/3xui-node-admin-node1.env`;
3. Host Control enrollment: `/root/3xui-host-control-node1.env`, уже скопированный с node.

Node-sync:

~~~env
NODE_ONBOARD_NAME=Edge-1
NODE_ONBOARD_PANEL_URL=https://panel-node1.example.com/basepath
NODE_ONBOARD_SYNC_TOKEN=<node-sync-secret>
NODE_ONBOARD_VERIFY_TLS=true
~~~

Direct-admin:

~~~env
NODE_ADMIN_ALIAS=NODE1
NODE_ADMIN_NODE_NAME=Edge-1
NODE_ADMIN_PANEL_URL=https://panel-node1.example.com/basepath
NODE_ADMIN_API_TOKEN=<dedicated-admin-secret>
NODE_ADMIN_VERIFY_TLS=true
~~~

Для direct-admin файла `NODE_ADMIN_NODE_ID` можно не указывать: wrapper получает stable ID после регистрации и передаёт его importer через `--node-id`.

Проверь права:

~~~bash
chmod 600   /root/3xui-node-node1.env   /root/3xui-node-admin-node1.env   /root/3xui-host-control-node1.env
~~~

## 15. Guided bind: сначала preflight

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot

bash scripts/onboard-direct-node.sh bind   --node-enrollment /root/3xui-node-node1.env   --admin-enrollment /root/3xui-node-admin-node1.env   --host-control-enrollment /root/3xui-host-control-node1.env   --env .env
~~~

Для новой node этот запуск выполняет node preflight без mutation. Если exact node уже существует, wrapper также получает её stable `NODE_ID` и preflight-проверяет оба privileged enrollment.

## 16. Guided bind: применить

После успешного preflight:

~~~bash
bash scripts/onboard-direct-node.sh bind   --node-enrollment /root/3xui-node-node1.env   --admin-enrollment /root/3xui-node-admin-node1.env   --host-control-enrollment /root/3xui-host-control-node1.env   --env .env   --apply
~~~

Wrapper:

1. повторяет node preflight и регистрирует либо безопасно переиспользует exact name + endpoint;
2. получает stable `NODE_ID`;
3. проверяет direct-admin и Host Control enrollment с тем же ID;
4. импортирует direct-admin binding;
5. импортирует Host Control binding;
6. пересоздаёт только service `bot` один раз;
7. не печатает raw tokens.

Ожидаемый безопасный итог:

~~~text
READY candidate: NODE_ID=<number>
~~~

Если mutation не получила подтверждённый success, wrapper не должен автоматически повторять её. Сначала проверь Nodes на Master.

### Manual fallback

Если guided wrapper недоступен, используй underlying helpers из [Node Onboarding](NODE_ONBOARDING.md): `onboard-node.py`, `import-node-admin-target.py`, `import-host-control-enrollment.py`.

## 14a. Manual fallback: создай node-sync enrollment на Master

~~~bash
sudo install -o root -g root -m 0600 /dev/null /root/3xui-node-node1.env
sudoedit /root/3xui-node-node1.env
~~~

Содержимое:

~~~env
NODE_ONBOARD_NAME=Edge-1
NODE_ONBOARD_PANEL_URL=https://panel-node1.example.com/basepath
NODE_ONBOARD_SYNC_TOKEN=<node-sync-secret>
NODE_ONBOARD_VERIFY_TLS=true
~~~

Preflight без mutation:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot

.venv-admin/bin/python scripts/onboard-node.py \
  /root/3xui-node-node1.env \
  --env .env
~~~

Ожидается Node preflight OK.

Регистрация:

~~~bash
.venv-admin/bin/python scripts/onboard-node.py \
  /root/3xui-node-node1.env \
  --env .env \
  --apply
~~~

Запомни безопасный результат:

~~~text
NODE_ID=<number>
~~~

Если helper не подтвердил success, mutation автоматически не повторяй. Сначала проверь Nodes на Master.

## 15a. Manual fallback: создай direct-admin enrollment

Этот token отдельный от node-sync token.

~~~bash
sudo install -o root -g root -m 0600 /dev/null /root/3xui-node-admin-node1.env
sudoedit /root/3xui-node-admin-node1.env
~~~

Содержимое:

~~~env
NODE_ADMIN_ALIAS=NODE1
NODE_ADMIN_NODE_NAME=Edge-1
NODE_ADMIN_PANEL_URL=https://panel-node1.example.com/basepath
NODE_ADMIN_API_TOKEN=<dedicated-admin-secret>
NODE_ADMIN_VERIFY_TLS=true
~~~

NODE_ADMIN_NODE_ID можно не записывать в file: передай подтверждённый ID через --node-id.

Допустим node получил ID 2.

Preflight:

~~~bash
.venv-admin/bin/python scripts/import-node-admin-target.py \
  /root/3xui-node-admin-node1.env \
  --env .env \
  --node-id 2 \
  --check-only
~~~

Импорт:

~~~bash
.venv-admin/bin/python scripts/import-node-admin-target.py \
  /root/3xui-node-admin-node1.env \
  --env .env \
  --node-id 2
~~~

Bot пока можно не recreate: Host Control binding добавим следующим шагом и сделаем один recreate.

## 16a. Manual fallback: импортируй Host Control binding с тем же node_id

Preflight:

~~~bash
.venv-admin/bin/python scripts/import-host-control-enrollment.py \
  /root/3xui-host-control-node1.env \
  --env .env \
  --node-id 2 \
  --check-only
~~~

Импорт + recreate только bot:

~~~bash
.venv-admin/bin/python scripts/import-host-control-enrollment.py \
  /root/3xui-host-control-node1.env \
  --env .env \
  --node-id 2 \
  --recreate-bot
~~~

Итоговый .env должен логически содержать:

~~~env
NODE_BACKUP_TARGETS=NODE1
NODE_BACKUP_NODE1_NODE_NAME=Edge-1
NODE_BACKUP_NODE1_NODE_ID=2
NODE_BACKUP_NODE1_PANEL_URL=https://panel-node1.example.com/basepath
NODE_BACKUP_NODE1_VERIFY_TLS=true

HOST_CONTROL_TARGETS=MASTER,NODE1
HOST_CONTROL_NODE1_NAME=Edge-1
HOST_CONTROL_NODE1_NODE_ID=2
HOST_CONTROL_NODE1_HOST_ID=edge-1
HOST_CONTROL_NODE1_URL=https://host-control-node1.example.com:18443
HOST_CONTROL_NODE1_VERIFY_TLS=true
~~~

Token values намеренно не проверяй через grep/cat с выводом в shared terminal/log.

## 17. Readiness direct node

В Telegram:

~~~text
/admin
→ Инфраструктура
→ Ноды
→ Edge-1
→ 🧭 Готовность
~~~

Желаемый результат:

~~~text
Direct node: yes
Direct Panel API: online
binding: node_id

Host Control: running
binding: node_id

Runtime readiness: ready
Stable identity: node_id
~~~

Если binding показывает legacy_name, не считай onboarding законченным.

## 18. Проверка Host Control без destructive actions

Сначала только read-only/benign checks:

1. открой node;
2. открой 🧩 Управление 3x-ui;
3. проверь Status;
4. убедись, что Agent отвечает running;
5. destructive Stop service / Stop Xray на этапе первоначального onboarding не нужны.

На node локально:

~~~bash
systemctl show 3xui-host-control.service \
  -p ActiveState -p MainPID -p ExecMainStartTimestamp --no-pager
~~~

## 19. Проверка Extended direct-node backup

В Telegram на direct node создай Node snapshot.

Ожидаемая структура:

~~~text
nodes/Edge-1/
├─ x-ui.db
├─ nginx/
├─ node.json
└─ manifest.json
~~~

Snapshot считается успешно настроенным только если:

- complete=true;
- missing пуст;
- database status=ok;
- nginx status=ok;
- node_id совпадает с Master;
- host_id совпадает с Host Control target;
- manifest содержит SHA-256 файлов.

Если nginx source не настроен/нечитаем, backup должен быть degraded. Не принимай degraded как законченный onboarding.

## 20. Проверка Full Backup

Открой:

~~~text
/admin
→ Система
→ Резервные копии
→ Создать сейчас
~~~

Full Backup должен включать тот же:

~~~text
nodes/Edge-1/
~~~

и не иметь missing для этой node.

Master nginx в Full Backup берётся через BACKUP_NGINX_CONF_HOST_PATH. Direct node nginx — через Host Control snapshot endpoint. Это два разных механизма.

Full Backup, `bot.sqlite3`, direct-node snapshot, `bot.env` и nginx recovery bundle через Telegram **не отправляются**. Telegram UI только создаёт backup/host-side export. Забирай secret-bearing artifacts с Master по защищённому host-side каналу либо используй encrypted off-site recovery flow. DR exports, подготовленные из UI, находятся в `data/restore/exports/` и должны оставаться mode `0600` внутри private directory.

### Как получить созданный Full Backup

При стандартной конфигурации `BACKUP_DIR=/app/data/backups`, а Compose монтирует host directory `./data` в `/app/data`. Поэтому при каноническом checkout на Master локальные Full Backup находятся в:

~~~text
/opt/3xui-bot/3xui-telegram-bot/data/backups/
~~~

После `/admin → Система → Резервные копии → Создать сейчас` проверь созданные archives на Master:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
ls -lh data/backups/3xui-bot-backup-*.tar.gz

LATEST="$(ls -1t data/backups/3xui-bot-backup-*.tar.gz 2>/dev/null | head -1)"
test -n "$LATEST"
printf 'Latest Full Backup: %s\n' "$LATEST"
stat "$LATEST"
~~~

Canonical имя имеет формат `3xui-bot-backup-YYYYMMDD-HHMMSS.tar.gz`.

Для переноса archive на доверенную operator workstation используй уже настроенный защищённый SSH/SFTP канал к Master. Не публикуй archive через Telegram, email, issue/PR attachments или публичный HTTP endpoint.

Если локальная копия на Master недоступна и настроен encrypted off-site backup, используй host-side recovery flow из [Encrypted off-site Full Backup](OFFSITE_BACKUP.md). Он получает latest canonical object из configured prefix, проверяет integrity и сохраняет verified archive с mode `0600`.

## 21. Финальный health check Master

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
./scripts/deploy-release.sh --status
~~~

Критерии:

~~~text
Git tag: v5.0.0-rc.8
Container: running
RestartCount=0
Bot version: 5.0.0-rc.8
Health: ok
DB: ok
3x-ui connectivity: ok
~~~

## 22. Удали временные enrollment files после проверки

После успешных Readiness + backup smoke секреты уже находятся в защищённых runtime locations/.env.

На Master можно удалить:

~~~bash
sudo rm -f \
  /root/3xui-node-node1.env \
  /root/3xui-node-admin-node1.env \
  /root/3xui-host-control-node1.env
~~~

На node после подтверждённого импорта можно удалить enrollment copy:

~~~bash
sudo rm -f /root/3xui-host-control-node1.env
~~~

Не удаляй:

~~~text
/etc/3xui-host-control/token
/etc/3xui-host-control/nginx-snapshot.env
/etc/3xui-host-control/tls-source.env
~~~

## 23. Добавление следующих nodes

Для каждой новой node повтори шаги 9–22.

Обязательно уникальны:

- Alias: NODE1, DE, NL, ...
- Host ID: edge-1, de, nl, ...
- 3x-ui node_id;
- node-sync token;
- direct-admin token;
- Host Control token;
- panel hostname/name.

Management port 18443 можно использовать одинаковый на разных public IP.

HOST_CONTROL_AGENT_NGINX_SOURCE может различаться между nodes.

## 24. Обновления после первоначальной установки

### Bot

Runtime release deploy:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
./scripts/deploy-release.sh vX.Y.Z
./scripts/deploy-release.sh --status
~~~

### SQLite migrations

При startup bot DB проходит versioned migration engine до начала Telegram polling.

Нормальный upgrade выполняется тем же release helper:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
./scripts/deploy-release.sh vX.Y.Z
./scripts/deploy-release.sh --status
~~~

Перед заменой release helper уже сохраняет консистентный pre-release `bot.sqlite3`. Дополнительно каждая migration, помеченная `requires_backup=True`, до изменения DB создаёт проверенную recovery copy в persistent каталоге `data/migration-backups/`.

Если migration journal содержит `running`/`failed`, schema version новее текущего кода или schema validation не проходит, bot блокирует startup. Не удаляй `schema_migrations` и не меняй status вручную, чтобы принудительно продолжить запуск: сначала сохрани DB, проверь recovery copy/Full Backup и устрани причину.

Проверка journal из repository root:

~~~bash
docker compose exec -T bot python - <<'PY'
import sqlite3
db = sqlite3.connect('/app/data/bot.sqlite3')
try:
    for row in db.execute(
        "SELECT version, name, status, backup_path, error "
        "FROM schema_migrations ORDER BY version"
    ):
        print(row)
finally:
    db.close()
PY
~~~

Для штатного состояния все строки должны иметь `status=success`. Полный developer/recovery contract описан в [Versioned SQLite migrations](SQLITE_MIGRATIONS.md).

`v5.0.0-rc.3` впервые опубликовал bot schema **v11** (`entitlement_quota_cycle_v5_0_0`). Migration не вызывает 3x-ui и не сбрасывает traffic автоматически: существующие entitlement rows получают безопасный marker `legacy`, новые paid entitlements используют durable quota-reset journal. После deployment проверь наличие успешной строки v11 и обычный `DB: ok`. Если после применения v11 потребуется откат приложения на `rc.2`/schema v10, одного checkout старого tag недостаточно: восстанови совместимую pre-release/pre-migration bot DB по recovery contract.

### Host Control Agent на direct nodes

При release, который меняет Host Control Agent:

1. собрать новый secret-free bundle на Master;
2. передать bundle + sha256 на node;
3. проверить checksum;
4. повторно запустить setup-host-control-endpoint.sh remote с теми же identity/network параметрами;
5. убедиться, что service restart произошёл;
6. nginx-snapshot.env должен сохраниться;
7. выполнить targeted snapshot smoke.

Host Control token при обычном reinstall сохраняется и не печатается.

## 25. Security invariants

После установки должны оставаться истинными все условия:

- bot container не имеет Docker socket;
- bot не имеет SSH/general shell API;
- Host Control Agent слушает только 127.0.0.1:18181;
- remote proxy не слушает wildcard 0.0.0.0;
- remote Host Control доступен только с Master public IP;
- remote Host Control использует verified HTTPS;
- Telegram/Master не передаёт filesystem path для nginx snapshot;
- nginx source задаётся только локально на node;
- Host Control mutations ограничены fixed allowlist;
- node-sync/direct-admin/Host-Control tokens не переиспользуются;
- privileged direct-node targets привязаны stable node_id;
- secrets не попадают в Git/chat/issues/logs;
- Full Backup, bot/node DB snapshots и DR exports не передаются как Telegram documents;
- Full Backup рассматривается как secret-bearing archive.

## 26. Типичные ошибки

### Bot не видит Master 3x-ui

Проверь PANEL_URL, base path, PANEL_API_TOKEN, verified TLS и firewall rule из BOT_DOCKER_SUBNET.

### Readiness: Direct Panel API offline

Проверь NODE_BACKUP_*_PANEL_URL, dedicated admin token и TLS. Не подменяй его node-sync token.

### Readiness: Host Control offline

Проверь:

~~~bash
systemctl is-active 3xui-host-control.service
systemctl is-active 3xui-host-control-proxy.service
ss -ltn | grep 18443
~~~

Также проверь DNS/certificate и allow-rule только с Master IP.

### Node snapshot degraded: nginx missing

На node проверь:

~~~bash
cat /etc/3xui-host-control/nginx-snapshot.env
~~~

Эта команда безопасна только если file содержит исключительно source path и никаких secrets, как требует этот runbook.

Затем проверь directory/readability от 3xui-hostctl и restart agent.

### После переименования node backup/Host Control пропал

Правильный v4.14.2 onboarding должен использовать NODE_BACKUP_*_NODE_ID и HOST_CONTROL_*_NODE_ID. Name-only binding — legacy fallback, не финальное состояние.

### Host Control Agent обновлён, но старый process остался

Это был defect v4.14.0. В v4.14.2 installer явно выполняет restart 3xui-host-control.service. Проверяй MainPID/ExecMainStartTimestamp до и после upgrade.

### nginx snapshot даёт checksum mismatch через HTTPS proxy

Это был defect v4.14.0 multi-chunk client read. В v4.14.2 response читается до EOF с прежним hard size limit.

## 27. Definition of Done новой node

Нода считается полностью введённой в эксплуатацию только когда:

- node зарегистрирована в Master;
- stable node_id известен;
- Direct Panel API online с node_id binding;
- Host Control running с тем же node_id binding;
- runtime readiness ready;
- Host Control remote endpoint ограничен Master IP;
- nginx source настроен локально;
- standalone Node snapshot complete;
- Full Backup включает complete nodes/<node>/;
- final Master health/status green.

Связанные подробные runbooks:

- docs/NODE_ONBOARDING.md
- docs/HOST_CONTROL_ROLLOUT.md
- docs/HOST_CONTROL_AGENT.md
- docs/VPS_RECOVERY.md
- docs/GIT_WORKFLOW.md


## Shadowrocket: обязательный Send HWID при активном device limit

### Owner-only локальный сброс клиентской сессии (#345)

В личном чате откройте `/admin → Пользователи → карточка пользователя → ⚙️ Ещё действия`. Для Owner кнопка `🔄 Сбросить клиентскую сессию` показывается **только при наличии активного in-memory окна ограничителя запросов у выбранного пользователя**. Подтвердите выбранный Telegram ID на отдельном экране. Сброс выполняется внутри **работающего** процесса бота и касается только лимитера этого клиента; отдельный `docker compose exec python` не изменит нужный limiter. У Client Portal нет пользовательского FSM для очистки. Административные диалоги, настройки VPN/3x-ui, SQLite, покупки, подписки и allowlist не меняются. Повторное или устаревшее подтверждение отклоняется, результат фиксируется в аудите. Сброс **не снимает ограничения доставки и flood control Telegram**. Production smoke выполнять только на согласованном pilot после нового release; не слать Telegram burst.

Для пользователя с `HWID limit > 0` в Shadowrocket включите `Send HWID` / «Отправлять HWID», затем обновите подписку. Если все device slots заняты, удалите ненужное устройство или увеличьте per-user `HWID limit`; proxy не генерирует synthetic HWID и не обходит лимит.


## Streisand и HWID

Streisand не передаёт совместимый `X-HWID` для raw subscription requests. Если для пользователя включён `HWID limit > 0`, upstream 3x-ui отклоняет такой subscription request как `hwid_not_supported`.

Не используйте synthetic/fallback HWID и не отключайте enforcement на compat proxy. Для HWID-защищённой подписки используйте клиент, который передаёт поддерживаемый HWID header. Импорт отдельных VLESS links в Streisand возможен отдельно, но не является HWID-protected subscription flow.


## v5 Client Portal launch controls

Перед canary проверьте customer-only emergency controls:

- `CLIENT_PORTAL_ENABLED=true|false` — выключает customer UI, не затрагивая `/admin`;
- `CLIENT_PAYMENT_ACCEPTANCE_ENABLED=true|false` — запрещает новые Stars invoice/pre-checkout, но уже подтверждённый Telegram payment продолжает фиксироваться локально;
- `CLIENT_RATE_LIMIT_COUNT` / `CLIENT_RATE_LIMIT_WINDOW_SECONDS` — per-user sliding-window guard customer commands/callbacks.

Для emergency rollback сначала выключайте payment acceptance, затем при необходимости Client Portal. Не удаляйте подтверждённые orders/payments/entitlements и не исправляйте их прямой правкой БД.

## Client Portal / Stars runtime switches (#342; после следующего релиза)

В новом коде `/admin → Система → Настройки → 👤 Клиентский портал` Owner может ограничить доступ к клиентскому порталу и **новым** Telegram Stars платежам без редактирования `.env` и пересоздания контейнера. На опубликованном/развёрнутом `v5.0.0-rc.7` интерфейс ещё отсутствует; пользоваться им до отдельного выпуска/controlled rollout нельзя. `.env CLIENT_PORTAL_ENABLED=false` или `CLIENT_PAYMENT_ACCEPTANCE_ENABLED=false` всегда сильнее DB override `true`; отключённый портал также запрещает оплату. Наличие DB override без внешнего разрешения не включает pilot-доступ. Для emergency break-glass остаются локальные `.env` flags с контролируемым redeploy по release-процедуре, а не Telegram-host shell. Read-only состояние при ошибке DB = unknown/disabled. Toggle не отзывает 3x-ui клиентов, не переписывает entitlement, не останавливает обработку уже пришедшего successful_payment. Перед production acceptance отдельно проверить рестарт, audit, старые invoices/precheckout, приватные права и read-only payment reconciliation без реальной повторной оплаты/refund.
