# Host Control Rollout

Этот runbook описывает воспроизводимое развёртывание Host Control Agent для Master и direct nodes.

Цель: сделать rollout повторяемым без ручного редактирования существующих MTProxy/nginx-конфигов и не давать Telegram-боту доступ к VPS за пределами allowlist для `x-ui.service`.

Для remote node репозиторий клонировать не обязательно: из release checkout на Master можно собрать secret-free deployment bundle, передать его на VPS и выполнить installer локально. Enrollment возвращается на Master отдельным mode-0600 файлом и импортируется helper'ом без вывода token в терминал.

## 1. Быстрый путь — Master

Предпосылки:

- bot уже работает в Docker;
- Docker subnet известна;
- на VPS установлен nginx (поддерживается системный nginx или `/opt/mtproxyl-nginx/sbin/nginx`);
- `x-ui.service` существует;
- скрипт запускается из checkout релиза.

Пример:

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

Скрипт:

- устанавливает/обновляет loopback-only agent;
- не редактирует существующий nginx/MTProxy config;
- создаёт отдельный `3xui-host-control-proxy.service`;
- слушает только указанный Docker bridge IP;
- разрешает source только из Docker subnet;
- при `--apply-ufw` добавляет одно узкое UFW rule;
- создаёт enrollment file mode `0600`;
- не печатает token.

По умолчанию enrollment file:

~~~text
/root/3xui-host-control-master.env
~~~

Он содержит secret token и не должен попадать в Git/chat/logs.

## 2. Быстрый путь — remote/direct node

Для remote node используется отдельный HTTPS listener на management port. Existing public nginx/MTProxy server block не редактируется.

Сначала на Master из checkout нужного release собери bundle:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
bash scripts/build-host-control-bundle.sh /root/3xui-host-control-bundle.tar.gz
~~~

Передай на remote VPS сам архив и `.sha256` через защищённый канал. На remote:

~~~bash
mkdir -p /root/3xui-host-control-install
cd /root/3xui-host-control-install
sha256sum -c /root/3xui-host-control-bundle.tar.gz.sha256
tar -xzf /root/3xui-host-control-bundle.tar.gz
~~~

Bundle не содержит runtime secrets, token или TLS private key. Token создаётся только локально на target VPS.

Предпосылки:

- DNS `host-control-node.example.com` уже указывает на remote VPS;
- есть валидный TLS certificate/key для этого hostname;
- известен public source IP Master;
- management port свободен;
- UFW/провайдерский firewall позволяет source-IP → management-port.

Пример на remote VPS после распаковки bundle:

~~~bash
cd /root/3xui-host-control-install

sudo scripts/setup-host-control-endpoint.sh remote \
  --alias NODE1 \
  --host-id edge-1 \
  --name Edge-1 \
  --listen-ip 203.0.113.10 \
  --source-ip 198.51.100.20 \
  --public-host host-control-node1.example.com \
  --cert /etc/letsencrypt/live/host-control-node1.example.com/fullchain.pem \
  --key /etc/letsencrypt/live/host-control-node1.example.com/privkey.pem \
  --proxy-port 18443 \
  --apply-ufw
~~~

Remote endpoint:

~~~text
https://host-control-node1.example.com:18443
~~~

Он принимает соединения только с `--source-ip`.

Для Extended direct-node backup фиксированный каталог nginx configuration задаётся **только локально на target VPS** в отдельном файле, который installer не создаёт и не перезаписывает:

~~~env
# /etc/3xui-host-control/nginx-snapshot.env
HOST_CONTROL_AGENT_NGINX_SOURCE=/etc/nginx
~~~

Выбери фактический каталог конфигурации конкретной ноды, например `/etc/nginx` или deployment-specific `/opt/.../conf`. Каталог должен существовать, быть абсолютным, не быть filesystem root/symlink и быть читаемым непривилегированным пользователем `3xui-hostctl`.

Безопасная локальная настройка после установки/обновления agent:

~~~bash
sudo install -o root -g root -m 0644 /dev/null /etc/3xui-host-control/nginx-snapshot.env
sudoedit /etc/3xui-host-control/nginx-snapshot.env
sudo systemctl restart 3xui-host-control.service
~~~

Запиши в файл ровно одну локальную переменную `HOST_CONTROL_AGENT_NGINX_SOURCE=<absolute-dir>`. Systemd unit читает его как optional EnvironmentFile. Поэтому обычный повторный installer run обновляет agent/unit, но не выбирает и не перезаписывает source path.

Это значение:

- **не входит** в enrollment file и bot `.env`;
- не может быть изменено Telegram/Master HTTP request;
- не превращает endpoint в file browser: agent отдаёт только `GET /v1/snapshots/nginx` без path/query selector.

Если source не настроен или часть файлов недоступна, `x-ui.db` всё равно может быть сохранён, но node snapshot и соответствующий Full Backup явно помечаются как degraded/missing nginx component.

Installer сохраняет source paths сертификата/key в root-only state и включает `3xui-host-control-tls-refresh.timer`. Таймер ежедневно проверяет hostname и соответствие cert/key; если исходный сертификат обновился, копии для restricted proxy заменяются и отдельный proxy reload'ится. Existing nginx/MTProxy при этом не трогается.

Повторный запуск installer с `--apply-ufw` сохраняет managed firewall state. Если management source/destination/port изменились, прежнее exact UFW allow-rule удаляется перед добавлением нового.

## 3. Что installer никогда не делает

Скрипт не:

- редактирует существующий MTProxy nginx config;
- меняет x-ui config;
- запускает SSH commands из Telegram;
- принимает arbitrary filesystem path из Telegram/Master;
- публикует directory listing или general-purpose file read/write API;
- добавляет wildcard firewall rules;
- слушает agent на `0.0.0.0`;
- использует `sudo ALL`;
- добавляет Docker/systemd socket в bot container;
- печатает host-control token;
- отключает firewall;
- меняет DNS;
- получает/выпускает TLS certificate;
- удаляет чужие контейнеры/сервисы.

## 4. Проверка endpoint

Локально на target VPS:

~~~bash
systemctl is-active 3xui-host-control.service
systemctl is-active 3xui-host-control-proxy.service

ss -ltn | grep -E ':(18181|18182|18443)\b'
~~~

Agent должен слушать:

~~~text
127.0.0.1:18181
~~~

Master proxy — только private Docker bridge address.

Remote proxy — только конкретный public management IP, не wildcard.

Если настроен `HOST_CONTROL_AGENT_NGINX_SOURCE`, после restart agent проверь его журнал и активность. Сам snapshot через management endpoint проверяется после enrollment штатным bot flow. Не вставляй Bearer token в shell command/history только ради ручной проверки.

## 5. Проверка без token

Master из bot container:

~~~bash
python - <<'PY'
import urllib.error
import urllib.request

try:
    urllib.request.urlopen("http://172.19.0.1:18182/v1/status", timeout=5)
except urllib.error.HTTPError as exc:
    print("HTTP", exc.code)
PY
~~~

Ожидается `HTTP 401`.

Remote с Master:

~~~bash
curl -sS -o /dev/null -w '%{http_code}\n' \
  https://host-control-node1.example.com:18443/v1/status
~~~

Ожидается `401`.

## 6. Enrollment в bot .env

Enrollment file имеет вид:

~~~text
HOST_CONTROL_ALIAS=NODE1
HOST_CONTROL_NAME=Edge-1
HOST_CONTROL_HOST_ID=edge-1
HOST_CONTROL_URL=https://host-control-node1.example.com:18443
HOST_CONTROL_VERIFY_TLS=true
HOST_CONTROL_TOKEN=<secret>
~~~

Перенос enrollment на Master делается только защищённым каналом. Не копируй token через issue/PR/chat и не выводи enrollment через `cat`.

После передачи файла на Master сначала выполни preflight:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot

python3 scripts/import-host-control-enrollment.py   /root/3xui-host-control-node1.env   --env .env   --check-only
~~~

Затем импортируй и пересоздай только bot container:

~~~bash
python3 scripts/import-host-control-enrollment.py   /root/3xui-host-control-node1.env   --env .env   --recreate-bot
~~~

Helper:

- не печатает token;
- проверяет alias/host_id/name/URL/transport policy;
- блокирует повторное использование host_id/name/token между активными targets;
- добавляет alias в `HOST_CONTROL_TARGETS` идемпотентно;
- в v4.11 через `--node-id` закрепляет direct node за стабильным 3x-ui `node.id`;
- сохраняет mode-0600 backup предыдущего `.env`;
- проверяет Compose до recreate;
- пересоздаёт только service `bot`;
- ждёт `/healthz = ok`.

После успешной проверки enrollment-файл на Master можно удалить.

Для alias `NODE1` итоговые ключи bot env:

~~~text
HOST_CONTROL_TARGETS=MASTER,NODE1
HOST_CONTROL_NODE1_NAME=Edge-1
HOST_CONTROL_NODE1_HOST_ID=edge-1
HOST_CONTROL_NODE1_URL=https://host-control-node1.example.com:18443
HOST_CONTROL_NODE1_TOKEN=<secret>
HOST_CONTROL_NODE1_VERIFY_TLS=true
~~~

## 7. Production deploy bot

Если одновременно устанавливается новая версия самого Telegram-бота, production по-прежнему разворачивается только по опубликованному tag:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
./scripts/deploy-release.sh vX.Y.Z
./scripts/deploy-release.sh --status
~~~

Если release уже установлен и меняется только enrollment новой ноды, достаточно `import-host-control-enrollment.py --recreate-bot`: он пересоздаёт только текущий bot container с новым `.env`.

## 8. Smoke-test

Для release, который меняет Extended direct-node backup, targeted smoke выполняется без service mutation:

1. открыть direct node и создать `Node snapshot`;
2. проверить, что архив содержит `nodes/<node>/x-ui.db`, `nginx/`, `node.json`, `manifest.json`;
3. проверить `manifest.json`: stable `node_id/host_id`, component status и checksums;
4. создать обычный Full Backup и подтвердить тот же node snapshot внутри него;
5. если nginx source намеренно не настроен, ожидаемый результат — `degraded`, а не ложный complete;
6. завершить обычным bot/DB/3x-ui health/status-check.

Для Host Control mutations отдельный smoke-порядок остаётся:

1. Status;
2. Start service при уже running состоянии;
3. Restart Panel process;
4. Restart service;
5. Restart / Start Xray;
6. Audit / Jobs;
7. только затем destructive Stop tests.

## 9. Rollback endpoint

Host-control можно отключить независимо от bot release:

~~~bash
sudo systemctl disable --now 3xui-host-control-tls-refresh.timer 2>/dev/null || true
sudo systemctl disable --now 3xui-host-control-proxy.service
sudo systemctl disable --now 3xui-host-control.service
~~~

Удалить alias из `HOST_CONTROL_TARGETS` и пересоздать только bot container.

Не удаляй token/journal до завершения incident review.

## 10. Новый VPS

Для восстановления самого бота используй `docs/VPS_RECOVERY.md` и `scripts/bootstrap-bot-from-backup.sh`.

Host Control Agent на новом VPS всегда enroll заново: старый host token не должен автоматически переезжать на новый сервер.

Для полноценного `🧩 Управление 3x-ui` remote node также нужен проверенный direct admin target в `NODE_BACKUP_TARGETS`: Panel/Xray actions и post-condition после Start/Restart используют штатный 3x-ui API. v4.10.x оставляет этот credential отдельным fail-safe конфигом; объединённый onboarding/readiness flow относится к v4.11.0.
