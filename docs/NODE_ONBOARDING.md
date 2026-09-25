# Node onboarding v4.11

v4.11 добавляет рекомендуемый путь подключения direct node без передачи privileged tokens через Telegram.

Цель: после подготовки нового VPS получить три независимых и явно проверяемых связи:

1. Master 3x-ui → node sync;
2. bot → direct 3x-ui admin API для backup / Panel / Xray;
3. bot → restricted Host Control Agent для `x-ui.service`.

Все privileged targets привязываются к стабильному `node.id`. Display name остаётся только подписью и fallback для старых конфигураций.

## Быстрый guided flow

Для обычного добавления новой direct node используй wrapper `scripts/onboard-direct-node.sh`. Он не заменяет security helpers, а вызывает их в правильном порядке и не принимает/не печатает raw tokens.

На Master подготовь secret-free Host Control bundle и, при необходимости, сразу скопируй его на новую VPS:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot

bash scripts/onboard-direct-node.sh prepare \
  --alias DE \
  --host-id de \
  --name Germany \
  --listen-ip 203.0.113.10 \
  --source-ip 198.51.100.20 \
  --public-host panel-de.example.com \
  --copy-to root@203.0.113.10 \
  --ssh-port 22
~~~

`prepare` передаёт только bundle и checksum. Скрипт выводит exact remote command для установки Host Control endpoint с verified TLS, restricted source IP, managed UFW rule и ежедневным TLS refresh timer. Enrollment-файл с Host Control token создаётся только на remote VPS и возвращается на Master отдельно через защищённый канал.

После remote setup подготовь на Master три mode-0600 файла:

- node-sync enrollment для `onboard-node.py`;
- direct-admin enrollment для `import-node-admin-target.py`;
- Host Control enrollment, полученный с remote VPS.

Для direct-admin файла при использовании wrapper `NODE_ADMIN_NODE_ID` можно не указывать: wrapper получает стабильный ID после регистрации node и передаёт его через `--node-id`.

Сначала выполни read-only/preflight запуск:

~~~bash
bash scripts/onboard-direct-node.sh bind \
  --node-enrollment /root/3xui-node-de.env \
  --admin-enrollment /root/3xui-node-admin-de.env \
  --host-control-enrollment /root/3xui-host-control-de.env
~~~

Для новой node preflight ничего не меняет. После проверки запусти тот же flow с explicit mutation:

~~~bash
bash scripts/onboard-direct-node.sh bind \
  --node-enrollment /root/3xui-node-de.env \
  --admin-enrollment /root/3xui-node-admin-de.env \
  --host-control-enrollment /root/3xui-host-control-de.env \
  --apply
~~~

Wrapper:

1. повторяет node preflight и регистрирует либо безопасно переиспользует exact name + endpoint;
2. получает `NODE_ID`;
3. preflight-проверяет direct-admin и Host Control enrollment с одним и тем же ID;
4. импортирует direct-admin binding без recreate;
5. импортирует Host Control binding и пересоздаёт только service `bot` один раз;
6. оставляет финальную проверку `🧭 Readiness` оператору.

Wrapper не выполняет `docker compose down`, не запускает generic remote shell/SSH commands, не выводит enrollment contents и не объединяет node-sync/direct-admin/Host Control secrets.

## 1. Подготовь remote Host Control endpoint

На новой VPS используй release bundle и `scripts/setup-host-control-endpoint.sh remote` из [Host Control Rollout](HOST_CONTROL_ROLLOUT.md).

Результат:

- agent слушает только `127.0.0.1:18181`;
- restricted proxy слушает отдельный HTTPS management port;
- source-IP ограничен Master;
- enrollment file имеет mode `0600` и содержит Host Control token.

Пока не импортируй enrollment в bot `.env`: сначала зарегистрируй node в Master и получи `NODE_ID`.

## 2. Зарегистрируй node в Master без Telegram

На Master создай mode-0600 файл, например:

~~~env
NODE_ONBOARD_NAME=Edge-1
NODE_ONBOARD_PANEL_URL=https://panel.example.com
NODE_ONBOARD_SYNC_TOKEN=<node-sync-secret>
NODE_ONBOARD_VERIFY_TLS=true
~~~

~~~bash
chmod 600 /root/3xui-node-node1.env
cd /opt/3xui-bot/3xui-telegram-bot

python3 scripts/onboard-node.py /root/3xui-node-node1.env --env .env
~~~

Без `--apply` helper выполняет только preflight через штатный 3x-ui nodes API и ничего не меняет.

После успешного preflight:

~~~bash
python3 scripts/onboard-node.py /root/3xui-node-node1.env --env .env --apply
~~~

Helper:

- требует mode-0600 для enrollment и bot `.env`;
- принимает только verified HTTPS node endpoint;
- не печатает sync token;
- сначала выполняет `nodes/test`;
- не повторяет mutation автоматически;
- при повторном запуске распознаёт уже зарегистрированную ноду по name + endpoint;
- печатает только безопасный результат вида `NODE_ID=2`.

Запомни полученный `NODE_ID`.

## 3. Импортируй direct admin credential

Node-sync token, сохранённый Master 3x-ui, намеренно не читается обратно. Для backup, Panel/Xray actions, restore и Версии и обновления нужен отдельный admin-scope token.

Создай на Master mode-0600 файл:

~~~env
NODE_ADMIN_ALIAS=NODE1
NODE_ADMIN_NODE_ID=2
NODE_ADMIN_NODE_NAME=Edge-1
NODE_ADMIN_PANEL_URL=https://panel.example.com
NODE_ADMIN_API_TOKEN=<dedicated-admin-secret>
NODE_ADMIN_VERIFY_TLS=true
~~~

Проверка без изменений:

~~~bash
python3 scripts/import-node-admin-target.py   /root/3xui-node-admin-node1.env   --env .env   --check-only
~~~

Импорт:

~~~bash
python3 scripts/import-node-admin-target.py   /root/3xui-node-admin-node1.env   --env .env
~~~

Helper добавляет/обновляет `NODE_BACKUP_NODE1_*`, включая:

~~~env
NODE_BACKUP_NODE1_NODE_ID=2
~~~

и делает mode-0600 backup предыдущего `.env`.

## 4. Импортируй Host Control enrollment с тем же NODE_ID

Скопируй enrollment с remote VPS на Master защищённым каналом. Не используй `cat`, issue, PR или Telegram для token.

Проверка:

~~~bash
python3 scripts/import-host-control-enrollment.py   /root/3xui-host-control-node1.env   --env .env   --node-id 2   --check-only
~~~

Импорт и единственный recreate bot:

~~~bash
python3 scripts/import-host-control-enrollment.py   /root/3xui-host-control-node1.env   --env .env   --node-id 2   --recreate-bot
~~~

Итоговая Host Control binding содержит:

~~~env
HOST_CONTROL_NODE1_NODE_ID=2
~~~

## 5. Проверь Telegram Readiness

Открой:

`Инфраструктура → Ноды → <node> → 🧭 Готовность`

Экран проверяет без mutation:

- node существует в Master и не является transitive;
- Master видит состояние node;
- direct Panel API доступен;
- Host Control Agent доступен;
- оба privileged targets связаны через `node_id`, а не только display name.

Желаемый итог:

~~~text
Direct node: yes
Direct Panel API: online
  binding: node_id
Host Control: running
  binding: node_id
Runtime readiness: ready
Stable identity: node_id
~~~

После этого открой `🧩 Управление 3x-ui` и выполни обычный smoke-test.

## 6. Rename

При наличии `NODE_BACKUP_*_NODE_ID` и `HOST_CONTROL_*_NODE_ID` переименование node в 3x-ui не ломает privileged bindings.

Name-only target остаётся совместимым fallback для старых deployments, но Readiness показывает `legacy_name` и предлагает миграцию на `NODE_ID`.

## 7. Что остаётся разделённым намеренно

Node-sync token, direct-admin token и Host Control token — разные privilege domains. v4.11 не объединяет и не переиспользует эти секреты.

Telegram не хранит и не показывает их. Рекомендуемый onboarding выполняет secret-bearing шаги только локально на Master/target VPS.

## 8. После onboarding

После успешной проверки mode-0600 enrollment files можно удалить с Master. Bot `.env` и его защищённые backup-копии продолжают содержать необходимые credentials и должны храниться как secrets.
