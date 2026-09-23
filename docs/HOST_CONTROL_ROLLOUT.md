# Host Control Rollout

Этот runbook описывает воспроизводимое развёртывание Host Control Agent для Master и direct nodes.

Цель: свести ручной rollout к одному installer-скрипту, не редактировать существующие MTProxy/nginx-конфиги и не давать Telegram-боту доступ к VPS за пределами allowlist для `x-ui.service`.

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

Предпосылки:

- DNS `host-control-node.example.com` уже указывает на remote VPS;
- есть валидный TLS certificate/key для этого hostname;
- известен public source IP Master;
- management port свободен;
- UFW/провайдерский firewall позволяет source-IP → management-port.

Пример:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot

sudo scripts/setup-host-control-endpoint.sh remote \
  --alias FI \
  --host-id fi \
  --name Finland \
  --listen-ip 203.0.113.10 \
  --source-ip 198.51.100.20 \
  --public-host host-control-fi.example.com \
  --cert /etc/letsencrypt/live/host-control-fi.example.com/fullchain.pem \
  --key /etc/letsencrypt/live/host-control-fi.example.com/privkey.pem \
  --proxy-port 18443 \
  --apply-ufw
~~~

Remote endpoint:

~~~text
https://host-control-fi.example.com:18443
~~~

Он принимает соединения только с `--source-ip`.

## 3. Что installer никогда не делает

Скрипт не:

- редактирует существующий MTProxy nginx config;
- меняет x-ui config;
- запускает SSH commands из Telegram;
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
  https://host-control-fi.example.com:18443/v1/status
~~~

Ожидается `401`.

## 6. Enrollment в bot .env

Enrollment file имеет вид:

~~~text
HOST_CONTROL_ALIAS=FI
HOST_CONTROL_NAME=Finland
HOST_CONTROL_HOST_ID=fi
HOST_CONTROL_URL=https://host-control-fi.example.com:18443
HOST_CONTROL_VERIFY_TLS=true
HOST_CONTROL_TOKEN=<secret>
~~~

Перенос token в bot `.env` делается локально на Master. Не копируй token через issue/PR/chat.

Для alias `FI` итоговые ключи bot env:

~~~text
HOST_CONTROL_TARGETS=MASTER,FI
HOST_CONTROL_FI_NAME=Finland
HOST_CONTROL_FI_HOST_ID=fi
HOST_CONTROL_FI_URL=https://host-control-fi.example.com:18443
HOST_CONTROL_FI_TOKEN=<secret>
HOST_CONTROL_FI_VERIFY_TLS=true
~~~

## 7. Production deploy bot

После enrollment:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
./scripts/deploy-release.sh vX.Y.Z
./scripts/deploy-release.sh --status
~~~

## 8. Smoke-test

Порядок:

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
sudo systemctl disable --now 3xui-host-control-proxy.service
sudo systemctl disable --now 3xui-host-control.service
~~~

Удалить alias из `HOST_CONTROL_TARGETS` и пересоздать только bot container.

Не удаляй token/journal до завершения incident review.

## 10. Новый VPS

Для восстановления самого бота используй `docs/VPS_RECOVERY.md` и `scripts/bootstrap-bot-from-backup.sh`.

Host Control Agent на новом VPS всегда enroll заново: старый host token не должен автоматически переезжать на новый сервер.
