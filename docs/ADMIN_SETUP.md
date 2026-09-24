# Admin Setup: установка и настройка Admin Control Plane

Этот runbook описывает полное развёртывание и operational-настройку административного контура 3x-ui Telegram Bot с чистых VPS: Master, одна или несколько direct nodes, Host Control Agent и Extended direct-node backup с nginx snapshot.

Scope документа — только **Admin Control Plane**. Будущая client-facing часть проекта должна иметь отдельное руководство (например, `docs/CLIENT_SETUP.md`) и не смешиваться с административным deployment flow.

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

Guide ориентирован на release v4.14.2. Все privileged connections используют отдельные credentials и stable node_id binding.

> В `v4.14.2` guided wrapper `scripts/onboard-direct-node.sh bind` исправлен и является рекомендуемым путём для регистрации node и обоих privileged bindings. Underlying helpers остаются доступным manual fallback.

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
- authenticated read access к private GitHub repository;
- Docker Engine + Docker Compose plugin;
- Git;
- Python 3 + venv для локальных onboarding helpers.

Для каждой direct node понадобятся три независимых privilege domain:

1. node-sync token: Master 3x-ui → node;
2. dedicated admin-scope token: bot → direct 3x-ui API;
3. Host Control token: создаётся автоматически Host Control Agent installer.

Не переиспользуй один token в нескольких domains.

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
- нужные inbound'ы.

Не переходи к bot onboarding, пока Master и node panel URL не открываются с verified TLS.

## 2. Базовая подготовка Master VPS

Установи системные пакеты:

~~~bash
sudo apt update
sudo apt install -y git curl ca-certificates python3 python3-venv openssl
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

Настрой read access к private GitHub repository через отдельный deploy key/SSH key или другой разрешённый способ. Не записывай GitHub token в repository или .env.

~~~bash
sudo mkdir -p /opt/3xui-bot
sudo chown "$(id -u):$(id -g)" /opt/3xui-bot
cd /opt/3xui-bot

git clone git@github.com:cLIcHE-QA/3xui-telegram-bot.git
cd 3xui-telegram-bot

git fetch --tags --prune
git checkout --detach v4.14.2
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
4.14.2
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

ALLOWED_TELEGRAM_IDS=<your-telegram-id>
ADMIN_TELEGRAM_IDS=<your-telegram-id>

BACKUP_ENABLED=true
BACKUP_DIR=/app/data/backups
BACKUP_KEEP=14
BACKUP_HOUR_UTC=2
BACKUP_SEND_TO_ADMINS=false

MASTER_NAME=Master
MASTER_FLAG=🇳🇱

BOT_DOCKER_SUBNET=172.19.0.0/16

HOST_CONTROL_TARGETS=
NODE_BACKUP_TARGETS=
~~~

ADMIN_TELEGRAM_IDS — break-glass Owners. Не добавляй туда случайных пользователей.

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
- Bot version: 4.14.2;
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

## 9. Подготовь direct node

Ниже пример для одной ноды:

~~~text
Alias: FI
Name: Finland
Host ID: fi
Node panel: https://panel-fi.example.com/basepath
Host Control URL: https://panel-fi.example.com:18443
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
  /root/3xui-host-control-bundle-v4.14.2.tar.gz
~~~

Передай только secret-free bundle и checksum:

~~~bash
scp -P SSH_PORT \
  /root/3xui-host-control-bundle-v4.14.2.tar.gz \
  /root/3xui-host-control-bundle-v4.14.2.tar.gz.sha256 \
  root@NODE_PUBLIC_IP:/root/
~~~

## 11. Установи Host Control endpoint на node

На node проверь checksum:

~~~bash
cd /root
sha256sum -c 3xui-host-control-bundle-v4.14.2.tar.gz.sha256
~~~

Распакуй:

~~~bash
rm -rf /root/3xui-host-control-install
mkdir -p /root/3xui-host-control-install

tar -xzf /root/3xui-host-control-bundle-v4.14.2.tar.gz \
  -C /root/3xui-host-control-install
~~~

Установка restricted remote endpoint:

~~~bash
cd /root/3xui-host-control-install

sudo scripts/setup-host-control-endpoint.sh remote \
  --alias FI \
  --host-id fi \
  --name Finland \
  --listen-ip NODE_PUBLIC_IP \
  --source-ip MASTER_PUBLIC_IP \
  --public-host panel-fi.example.com \
  --cert /etc/letsencrypt/live/panel-fi.example.com/fullchain.pem \
  --key /etc/letsencrypt/live/panel-fi.example.com/privkey.pem \
  --proxy-port 18443 \
  --apply-ufw
~~~

Если certificate хранится в другом месте, передай реальные absolute paths.

Результат:

- agent: 127.0.0.1:18181;
- restricted HTTPS proxy: NODE_PUBLIC_IP:18443;
- firewall source: только MASTER_PUBLIC_IP;
- TLS refresh timer enabled;
- enrollment: /root/3xui-host-control-fi.env.

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
  root@NODE_PUBLIC_IP:/root/3xui-host-control-fi.env \
  /root/3xui-host-control-fi.env

chmod 600 /root/3xui-host-control-fi.env
~~~

Не используй cat, Telegram, issue или PR для передачи содержимого этого файла.

Пока не импортируй его без stable node_id.

## 14. Подготовь три enrollment-файла на Master

Создай три mode-0600 файла:

1. node-sync enrollment: `/root/3xui-node-fi.env`;
2. direct-admin enrollment: `/root/3xui-node-admin-fi.env`;
3. Host Control enrollment: `/root/3xui-host-control-fi.env`, уже скопированный с node.

Node-sync:

~~~env
NODE_ONBOARD_NAME=Finland
NODE_ONBOARD_PANEL_URL=https://panel-fi.example.com/basepath
NODE_ONBOARD_SYNC_TOKEN=<node-sync-secret>
NODE_ONBOARD_VERIFY_TLS=true
~~~

Direct-admin:

~~~env
NODE_ADMIN_ALIAS=FI
NODE_ADMIN_NODE_NAME=Finland
NODE_ADMIN_PANEL_URL=https://panel-fi.example.com/basepath
NODE_ADMIN_API_TOKEN=<dedicated-admin-secret>
NODE_ADMIN_VERIFY_TLS=true
~~~

Для direct-admin файла `NODE_ADMIN_NODE_ID` можно не указывать: wrapper получает stable ID после регистрации и передаёт его importer через `--node-id`.

Проверь права:

~~~bash
chmod 600   /root/3xui-node-fi.env   /root/3xui-node-admin-fi.env   /root/3xui-host-control-fi.env
~~~

## 15. Guided bind: сначала preflight

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot

bash scripts/onboard-direct-node.sh bind   --node-enrollment /root/3xui-node-fi.env   --admin-enrollment /root/3xui-node-admin-fi.env   --host-control-enrollment /root/3xui-host-control-fi.env   --env .env
~~~

Для новой node этот запуск выполняет node preflight без mutation. Если exact node уже существует, wrapper также получает её stable `NODE_ID` и preflight-проверяет оба privileged enrollment.

## 16. Guided bind: применить

После успешного preflight:

~~~bash
bash scripts/onboard-direct-node.sh bind   --node-enrollment /root/3xui-node-fi.env   --admin-enrollment /root/3xui-node-admin-fi.env   --host-control-enrollment /root/3xui-host-control-fi.env   --env .env   --apply
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
sudo install -o root -g root -m 0600 /dev/null /root/3xui-node-fi.env
sudoedit /root/3xui-node-fi.env
~~~

Содержимое:

~~~env
NODE_ONBOARD_NAME=Finland
NODE_ONBOARD_PANEL_URL=https://panel-fi.example.com/basepath
NODE_ONBOARD_SYNC_TOKEN=<node-sync-secret>
NODE_ONBOARD_VERIFY_TLS=true
~~~

Preflight без mutation:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot

.venv-admin/bin/python scripts/onboard-node.py \
  /root/3xui-node-fi.env \
  --env .env
~~~

Ожидается Node preflight OK.

Регистрация:

~~~bash
.venv-admin/bin/python scripts/onboard-node.py \
  /root/3xui-node-fi.env \
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
sudo install -o root -g root -m 0600 /dev/null /root/3xui-node-admin-fi.env
sudoedit /root/3xui-node-admin-fi.env
~~~

Содержимое:

~~~env
NODE_ADMIN_ALIAS=FI
NODE_ADMIN_NODE_NAME=Finland
NODE_ADMIN_PANEL_URL=https://panel-fi.example.com/basepath
NODE_ADMIN_API_TOKEN=<dedicated-admin-secret>
NODE_ADMIN_VERIFY_TLS=true
~~~

NODE_ADMIN_NODE_ID можно не записывать в file: передай подтверждённый ID через --node-id.

Допустим node получил ID 2.

Preflight:

~~~bash
.venv-admin/bin/python scripts/import-node-admin-target.py \
  /root/3xui-node-admin-fi.env \
  --env .env \
  --node-id 2 \
  --check-only
~~~

Импорт:

~~~bash
.venv-admin/bin/python scripts/import-node-admin-target.py \
  /root/3xui-node-admin-fi.env \
  --env .env \
  --node-id 2
~~~

Bot пока можно не recreate: Host Control binding добавим следующим шагом и сделаем один recreate.

## 16a. Manual fallback: импортируй Host Control binding с тем же node_id

Preflight:

~~~bash
.venv-admin/bin/python scripts/import-host-control-enrollment.py \
  /root/3xui-host-control-fi.env \
  --env .env \
  --node-id 2 \
  --check-only
~~~

Импорт + recreate только bot:

~~~bash
.venv-admin/bin/python scripts/import-host-control-enrollment.py \
  /root/3xui-host-control-fi.env \
  --env .env \
  --node-id 2 \
  --recreate-bot
~~~

Итоговый .env должен логически содержать:

~~~env
NODE_BACKUP_TARGETS=FI
NODE_BACKUP_FI_NODE_NAME=Finland
NODE_BACKUP_FI_NODE_ID=2
NODE_BACKUP_FI_PANEL_URL=https://panel-fi.example.com/basepath
NODE_BACKUP_FI_VERIFY_TLS=true

HOST_CONTROL_TARGETS=MASTER,FI
HOST_CONTROL_FI_NAME=Finland
HOST_CONTROL_FI_NODE_ID=2
HOST_CONTROL_FI_HOST_ID=fi
HOST_CONTROL_FI_URL=https://panel-fi.example.com:18443
HOST_CONTROL_FI_VERIFY_TLS=true
~~~

Token values намеренно не проверяй через grep/cat с выводом в shared terminal/log.

## 17. Readiness direct node

В Telegram:

~~~text
/admin
→ Infrastructure
→ Nodes
→ Finland
→ 🧭 Readiness
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
2. открой 🧩 3x-ui Control;
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
nodes/Finland/
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
→ System
→ Backups
→ Создать сейчас
~~~

Full Backup должен включать тот же:

~~~text
nodes/Finland/
~~~

и не иметь missing для этой node.

Master nginx в Full Backup берётся через BACKUP_NGINX_CONF_HOST_PATH. Direct node nginx — через Host Control snapshot endpoint. Это два разных механизма.

## 21. Финальный health check Master

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
./scripts/deploy-release.sh --status
~~~

Критерии:

~~~text
Git tag: v4.14.2
Container: running
RestartCount=0
Bot version: 4.14.2
Health: ok
DB: ok
3x-ui connectivity: ok
~~~

## 22. Удали временные enrollment files после проверки

После успешных Readiness + backup smoke секреты уже находятся в защищённых runtime locations/.env.

На Master можно удалить:

~~~bash
sudo rm -f \
  /root/3xui-node-fi.env \
  /root/3xui-node-admin-fi.env \
  /root/3xui-host-control-fi.env
~~~

На node после подтверждённого импорта можно удалить enrollment copy:

~~~bash
sudo rm -f /root/3xui-host-control-fi.env
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

- Alias: FI, DE, NL, ...
- Host ID: fi, de, nl, ...
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
