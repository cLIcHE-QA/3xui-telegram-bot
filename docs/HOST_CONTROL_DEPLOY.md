# v4.10.0 — безопасное развёртывание Host Control Agent

Этот документ описывает production-схему для Master и direct node (например Edge-1).

Цель: дать Telegram-боту только узкую capability для `x-ui.service` и не превращать бот в канал доступа к VPS.

## 1. Что устанавливается на каждом VPS

На Master и на каждой direct node устанавливаются:

~~~text
3xui-host-control.service
/opt/3xui-host-control/host_control_agent.py
/etc/3xui-host-control/token
/etc/3xui-host-control/agent.env
/etc/sudoers.d/3xui-host-control
/var/lib/3xui-host-control/agent.sqlite3
~~~

Agent:

- работает от отдельного пользователя `3xui-hostctl`;
- слушает только `127.0.0.1:18181`;
- не принимает SSH/shell/exec/file-команды;
- управляет только `x-ui.service`;
- не печатает bearer token.

Установка выполняется локально на соответствующем VPS:

~~~bash
sudo scripts/install-host-control-agent.sh master
~~~

Для Edge-1 используется собственный host id:

~~~bash
sudo scripts/install-host-control-agent.sh fi
~~~

Не копируй token Master на Edge-1 и наоборот.

## 2. Master: bot container → host agent

Bot работает в Docker, поэтому не может обратиться к host loopback напрямую.

Рекомендуемый вариант — локальный reverse proxy, который:

- слушает только Docker bridge address;
- принимает запросы только из bot Docker subnet;
- проксирует их на `127.0.0.1:18181`;
- не публикуется на public interface.

При стандартной подсети проекта `172.19.0.0/16` пример логики nginx:

~~~nginx
server {
    listen 172.19.0.1:18182;
    server_name _;

    allow 172.19.0.0/16;
    deny all;

    access_log off;

    location ^~ /v1/ {
        proxy_pass http://127.0.0.1:18181;
        proxy_http_version 1.1;
        proxy_redirect off;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header Host localhost;
    }

    location / {
        return 404;
    }
}
~~~

Если `BOT_DOCKER_SUBNET` отличается от `172.19.0.0/16`, адрес bridge и allowlist должны соответствовать фактической подсети.

Bot config:

~~~env
HOST_CONTROL_MASTER_NAME=Master
HOST_CONTROL_MASTER_HOST_ID=master
HOST_CONTROL_MASTER_URL=http://172.19.0.1:18182
HOST_CONTROL_MASTER_TOKEN=<dedicated Master host-control token>
HOST_CONTROL_MASTER_VERIFY_TLS=true
~~~

Plain HTTP разрешён конфигом только для alias `MASTER` и только на private/local address.

Не открывай `18181` или `18182` на public interface.

## 3. Пример direct node: Master VPS → remote agent

Для remote node agent по-прежнему остаётся loopback-only.

Наружу публикуется только HTTPS reverse proxy:

~~~text
Master VPS
   |
   | HTTPS + dedicated Bearer token
   v
Edge-1 reverse proxy :443
   |
   | loopback HTTP
   v
127.0.0.1:18181
~~~

Пример логики nginx:

~~~nginx
server {
    listen 443 ssl;
    server_name host-control-node1.example.com;

    # TLS certificate/key are configured locally and are not stored in this repo.

    allow <MASTER_PUBLIC_IP>;
    deny all;

    access_log off;

    location ^~ /v1/ {
        proxy_pass http://127.0.0.1:18181;
        proxy_http_version 1.1;
        proxy_redirect off;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header Host localhost;
    }

    location / {
        return 404;
    }
}
~~~

`<MASTER_PUBLIC_IP>` — обязательный placeholder: конфигурация не должна вводиться в production до замены на реальный management source.

Bot config:

~~~env
HOST_CONTROL_NODE1_NAME=Edge-1
HOST_CONTROL_NODE1_HOST_ID=edge-1
HOST_CONTROL_NODE1_URL=https://host-control-node1.example.com
HOST_CONTROL_NODE1_TOKEN=<dedicated Edge-1 host-control token>
HOST_CONTROL_NODE1_VERIFY_TLS=true
~~~

Remote host-control target по plain HTTP конфиг бота отклоняет.

## 4. Tokens

Host-control token:

- отдельный для каждого VPS;
- не совпадает с `PANEL_API_TOKEN`;
- не совпадает с `NODE_BACKUP_*_API_TOKEN`;
- не совпадает с Telegram bot token;
- не передаётся в URL;
- не добавляется в Git;
- не отправляется в Telegram;
- не должен попадать в reverse-proxy access logs.

Installer генерирует token локально и сохраняет:

~~~text
/etc/3xui-host-control/token
~~~

Файл должен оставаться mode `0600`.

При переносе значения в production `.env` делай это локально на VPS. Не вставляй token в issue/PR/chat/log output.

## 5. Firewall boundary

Agent port `18181` никогда не открывается через UFW/iptables/nftables.

Для Edge-1 public HTTPS endpoint разрешается только management source Master VPS.

Для Master отдельное public firewall rule не требуется: reverse proxy слушает только Docker bridge address.

Не отключай firewall ради диагностики host-control.

## 6. Production enable sequence

Рекомендуемый порядок:

1. Установить agent на Master.
2. Проверить `systemctl is-active 3xui-host-control.service`.
3. Настроить Master Docker-bridge reverse proxy.
4. Добавить только `HOST_CONTROL_MASTER_*` в bot `.env`.
5. Пересоздать только bot container.
6. Открыть `Master → 🧩 Управление 3x-ui` и проверить Status.
7. Выполнить безопасный `Запустить сервис` при уже running состоянии — agent должен вернуть `changed=false`.
8. Проверить `♻️ Restart Panel process`.
9. Проверить `🔄 Restart service`.
10. Только после успешного Master smoke test устанавливать agent на Edge-1.
11. Настроить Edge-1 HTTPS reverse proxy + source allowlist.
12. Добавить `HOST_CONTROL_NODE1_*` в bot `.env`.
13. Проверить Edge-1 Status / Restart Panel / Restart service.
14. `Остановить сервис` тестировать последним и только при готовом recovery path.

## 7. Перед первым Stop service

Перед первым production Stop должны быть подтверждены:

- Host Control Agent показывает `Service: running`;
- кнопка `▶ Start service` доступна Owner/Admin после остановки;
- direct Panel API target настроен для post-condition после Start;
- agent endpoint остаётся доступен независимо от x-ui;
- есть обычный VPS console/SSH recovery вне Telegram;
- есть свежий backup.

Telegram bot не является единственным recovery channel VPS.

## 8. Что нельзя делать

Не добавляй:

~~~text
systemctl *
sudo ALL
/run?command=...
/exec
/shell
SSH private key в bot container
Docker socket в bot container
/run/systemd/private в bot container
host filesystem mount в bot container
~~~

Не запускай Host Control Agent от root.

Не меняй listener agent с `127.0.0.1` на `0.0.0.0`.

Не делай fallback из Host Control Agent в SSH.

## 9. Проверка после установки

Через Telegram:

~~~text
/admin
→ Инфраструктура
→ Ноды
→ Master / Edge-1
→ 🧩 Управление 3x-ui
~~~

Ожидается:

~~~text
🟢 Service: running
🟢 Panel API: online
🟢 Xray Core: running
~~~

После mutation проверь `Мониторинг → Задания` и `Журнал аудита`: записи должны содержать только operation metadata и не содержать bearer token, Authorization header или shell command.

## 10. Rollback

Если host-control feature нужно отключить без отката всего bot release:

1. Удали соответствующий alias из `HOST_CONTROL_TARGETS` в bot `.env`.
2. Пересоздай только bot container.
3. После проверки можно остановить agent локально:
   `systemctl disable --now 3xui-host-control.service`.
4. Reverse proxy route host-control удаляется отдельно.
5. Не удаляй sudoers/token/journal до завершения расследования, если отключение связано с incident.

Отключение Host Control Agent не затрагивает существующие provisioning, subscriptions, backups и штатный 3x-ui API.
