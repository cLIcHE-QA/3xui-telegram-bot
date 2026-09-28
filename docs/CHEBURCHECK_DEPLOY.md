# Cheburcheck deployment

Этот runbook фиксирует production deployment optional read-only Cheburcheck service для Telegram Admin Control Plane.

Он дополняет [Cheburcheck integration](CHEBURCHECK.md): integration document описывает API/security/UI contract, а этот файл — host/runtime topology и воспроизводимую настройку VPS.

## Зафиксированный runtime

Для текущей v4.23.x integration используется:

- upstream: `LowderPlay/cheburcheck`;
- reviewed revision: `0bbd2be8ca4b8f9ded1407597654314fc2a900c6`;
- backend component: `website`;
- internal API: `http://cheburcheck:8000`;
- PostgreSQL: `postgres:18.6-bookworm`;
- bot и Cheburcheck соединяются только через internal Docker network;
- Cheburcheck и PostgreSQL не публикуют host ports.

Pinned upstream migration `website/migrations/20260528125659_optimizations.sql` использует `uuidv7()`. Поэтому accepted production topology использует PostgreSQL 18; PostgreSQL 16 для этой revision недостаточен.

PostgreSQL 18 official image хранит cluster data под `/var/lib/postgresql/<major>/docker`, поэтому persistent volume монтируется в `/var/lib/postgresql`, а не в legacy `/var/lib/postgresql/data`.

## Operational boundary

Cheburcheck — отдельный third-party runtime:

- бот не запускает и не обновляет его автоматически;
- Safe Bot Self-Update обновляет только bot release;
- `bot.sqlite3` и 3x-ui schema не зависят от PostgreSQL Cheburcheck;
- PostgreSQL/cache Cheburcheck **не входят** в Full Backup Telegram-бота;
- PostgreSQL password хранится только локально в `/opt/cheburcheck/runtime/.env`;
- внутренний Cheburcheck URL не показывается в Telegram UI.

Если сохранение query history Cheburcheck важно для оператора, PostgreSQL volume нужно резервировать отдельно. Для восстановления самой read-only проверки достаточно заново развернуть pinned runtime и дождаться загрузки blocking databases.

## 1. Найди Docker network бота

Сначала проверь actual network и subnet:

~~~bash
for n in $(docker network ls -q); do
  docker network inspect -f '{{.Name}} {{range .IPAM.Config}}{{.Subnet}}{{end}}' "$n"
done
~~~

Нужна сеть текущего bot Compose project с `BOT_DOCKER_SUBNET` из bot `.env`.

Канонический production example:

~~~text
3xui-telegram-bot_default 172.19.0.0/16
~~~

Если имя сети отличается, используй фактическое имя в compose ниже. Не создавай вторую сеть с тем же subnet.

## 2. Получи exact upstream revision

~~~bash
sudo install -d -m 0755 /opt/cheburcheck

sudo git clone --no-checkout \
  https://github.com/LowderPlay/cheburcheck.git \
  /opt/cheburcheck/upstream

sudo git -C /opt/cheburcheck/upstream checkout --detach \
  0bbd2be8ca4b8f9ded1407597654314fc2a900c6

sudo git -C /opt/cheburcheck/upstream status --short --branch
~~~

Ожидается detached clean checkout. Не переключай runtime на новый upstream commit без отдельного review его API, migrations, license и security boundary.

## 3. Создай закрытый runtime directory и secrets

~~~bash
sudo install -d -m 0700 /opt/cheburcheck/runtime
~~~

Создай runtime env, не печатая password:

~~~bash
sudo sh -c 'umask 077
pw="$(openssl rand -hex 32)"
cat > /opt/cheburcheck/runtime/.env <<EOF
POSTGRES_DB=cheburcheck
POSTGRES_USER=cheburcheck
POSTGRES_PASSWORD=$pw
DATABASE_URL=postgres://cheburcheck:$pw@postgres:5432/cheburcheck
DATABASE_MIN_CONNECTIONS=1
DATABASE_MAX_CONNECTIONS=10
API_RATE_LIMIT_RPM=30
EOF'
~~~

Файл должен оставаться mode 0600/root-owned. Не копируй PostgreSQL password в bot `.env`, Telegram, issue или PR.

## 4. Minimal internal-only Compose

Создай `/opt/cheburcheck/runtime/compose.yml`:

~~~yaml
services:
  postgres:
    image: postgres:18.6-bookworm
    restart: unless-stopped
    env_file:
      - .env
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql
    networks:
      - db
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U \"$${POSTGRES_USER}\" -d \"$${POSTGRES_DB}\""]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 10s

  cheburcheck:
    build:
      context: ../upstream
      dockerfile: website/Dockerfile
    restart: unless-stopped
    env_file:
      - .env
    environment:
      DATABASE_URL: ${DATABASE_URL}
      DATABASE_MIN_CONNECTIONS: ${DATABASE_MIN_CONNECTIONS}
      DATABASE_MAX_CONNECTIONS: ${DATABASE_MAX_CONNECTIONS}
      API_RATE_LIMIT_RPM: ${API_RATE_LIMIT_RPM}
      DATABASE_CACHE_DIR: /var/cache/cheburcheck/databases
      DATABASE_RETRY_INTERVAL_SECONDS: "300"
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - database-cache:/var/cache/cheburcheck/databases
    expose:
      - "8000"
    networks:
      - db
      - bot
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8000/api/v1/healthcheck"]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 60s

networks:
  db:
    internal: true
  bot:
    external: true
    name: 3xui-telegram-bot_default

volumes:
  postgres-data:
  database-cache:
~~~

Если actual bot network имеет другое имя, замени только `networks.bot.name`.

Security properties:

- нет секции `ports:`;
- PostgreSQL находится только в `db`;
- `db` помечена `internal: true`;
- backend находится в `db` и bot network;
- bot обращается к backend по service DNS `cheburcheck:8000`.

## 5. Validate и запусти stack

Сначала только syntax/config validation:

~~~bash
cd /opt/cheburcheck/runtime
sudo docker compose config -q
~~~

Затем PostgreSQL:

~~~bash
sudo docker compose up -d postgres
sudo docker compose ps postgres
~~~

Продолжай только при `healthy`.

Backend собирается из exact pinned checkout:

~~~bash
sudo docker compose up -d --build cheburcheck
sudo docker compose ps
~~~

Оба сервиса должны стать `healthy`.

Первый Rust build может занять значительное время и оставить несколько GiB Docker build cache. Runtime image и build cache — разные объекты; cache можно обслуживать отдельно после успешной проверки, не удаляя active images/volumes.

## 6. Проверь reachability именно из bot container

Пример read-only health probe:

~~~bash
BOT_CID="$(sudo docker ps \
  --filter label=com.docker.compose.project=3xui-telegram-bot \
  --filter label=com.docker.compose.service=bot \
  -q | head -n1)"

sudo docker exec "$BOT_CID" python -c \
  'import urllib.request; print(urllib.request.urlopen("http://cheburcheck:8000/api/v1/healthcheck", timeout=5).read().decode())'
~~~

Ожидается:

~~~text
OK
~~~

Если Compose project name бота отличается, получи container/network по Docker labels и используй фактические значения.

## 7. Подключи bot

Сначала backup bot `.env`:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
cp -a .env ".env.pre-cheburcheck-$(date +%Y%m%d-%H%M%S)"
~~~

Добавь:

~~~env
CHEBURCHECK_URL=http://cheburcheck:8000
CHEBURCHECK_VERIFY_TLS=true
~~~

Проверь только эти keys:

~~~bash
grep -n '^CHEBURCHECK_' .env
~~~

Пересоздай только bot service:

~~~bash
docker compose up -d --force-recreate bot
docker compose ps bot
~~~

Не требуется обновлять 3x-ui, Xray, Host Control Agent, Deploy Agent или bot SQLite schema.

## 8. Production acceptance

В Telegram:

1. `/admin → Мониторинг → Проверка блокировок`: service должен быть `🟢 настроен`;
2. убедись, что обнаруженные Master/direct Nodes/enabled Hosts показывают только hostname/IP;
3. проверь Master target;
4. проверь shortcut из карточки Master;
5. проверь shortcut из одной direct Node;
6. проверь manual public IP;
7. проверь ASN;
8. проверь validation URL/private IP;
9. проверь rate-limit presentation;
10. временно сделай endpoint недоступным и убедись, что ошибка локализована в Cheburcheck screen;
11. восстанови endpoint и повтори запрос;
12. повтори base `deploy-release.sh --status`.

Для линии v4.23.x bot static response body hard limit — 1 MiB. Он остаётся bounded вместе с concurrency/timeouts, но пропускает нормальные ASN responses, которые могут превышать 256 KiB.

### Принятый production результат v4.23.1

Acceptance выполнен на release `v4.23.1` / `ff6638442cbe9c2adc9aa76d74c2cfb4b647aaf6`:

- service configured, discovery показал Master/direct Nodes без URL path/credentials;
- Master и direct-node shortcuts вернули штатный результат и сохранили корректный parent navigation;
- manual public IPv4 и ASN `AS213459` прошли; ASN response около 382 KiB корректно помещается в новый 1 MiB hard limit и UI остаётся bounded;
- arbitrary URL и private IPv4 отклоняются локальной validation;
- при остановленном Cheburcheck backend UI показал graceful unavailable error, bot не деградировал; после запуска backend повторный ASN прошёл;
- `docker compose ps` показал Cheburcheck и PostgreSQL healthy;
- финальный bot status: exact v4.23.1 SHA, container running, `RestartCount=0`, Health/DB/3x-ui `ok`;
- targeted log scan не нашёл internal Cheburcheck URL, `CHEBURCHECK_URL`, `DATABASE_URL` или `POSTGRES_PASSWORD`;
- backend rate-limit не проверялся production flood'ом; per-admin 2-second guard проверяется regression-test'ом до upstream request.


## 9. Rollback / disable

Чтобы выключить integration без удаления external stack:

1. очисти `CHEBURCHECK_URL` в bot `.env`;
2. пересоздай только bot service;
3. проверь, что экран показывает `не настроен`, а core bot/3x-ui остаются healthy.

Остановка external stack:

~~~bash
cd /opt/cheburcheck/runtime
sudo docker compose stop cheburcheck postgres
~~~

Не удаляй `runtime_postgres-data` при обычном rollback. Удаление volume — отдельное destructive действие и допустимо только для осознанного clean reinstall/restore.

## 10. Update policy

Bot release и Cheburcheck upstream обновляются независимо.

- v4.23.2 не требует rebuild Cheburcheck runtime, если pinned service уже healthy;
- bot update выполняется обычным release deployment;
- upstream commit не меняется автоматически;
- смена PostgreSQL major/version или upstream revision требует отдельного review migrations и recovery plan;
- после изменения runtime повторяются network reachability, health и Telegram acceptance checks.
