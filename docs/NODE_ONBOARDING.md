# Node onboarding v4.11

v4.11 добавляет рекомендуемый путь подключения direct node без передачи privileged tokens через Telegram.

Цель: после подготовки нового VPS получить три независимых и явно проверяемых связи:

1. Master 3x-ui → node sync;
2. bot → direct 3x-ui admin API для backup / Panel / Xray;
3. bot → restricted Host Control Agent для `x-ui.service`.

Все privileged targets привязываются к стабильному `node.id`. Display name остаётся только подписью и fallback для старых конфигураций.

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
NODE_ONBOARD_NAME=Finland
NODE_ONBOARD_PANEL_URL=https://panel.example.com
NODE_ONBOARD_SYNC_TOKEN=<node-sync-secret>
NODE_ONBOARD_VERIFY_TLS=true
~~~

~~~bash
chmod 600 /root/3xui-node-fi.env
cd /opt/3xui-bot/3xui-telegram-bot

python3 scripts/onboard-node.py /root/3xui-node-fi.env --env .env
~~~

Без `--apply` helper выполняет только preflight через штатный 3x-ui nodes API и ничего не меняет.

После успешного preflight:

~~~bash
python3 scripts/onboard-node.py /root/3xui-node-fi.env --env .env --apply
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

Node-sync token, сохранённый Master 3x-ui, намеренно не читается обратно. Для backup, Panel/Xray actions, restore и Versions & Updates нужен отдельный admin-scope token.

Создай на Master mode-0600 файл:

~~~env
NODE_ADMIN_ALIAS=FI
NODE_ADMIN_NODE_ID=2
NODE_ADMIN_NODE_NAME=Finland
NODE_ADMIN_PANEL_URL=https://panel.example.com
NODE_ADMIN_API_TOKEN=<dedicated-admin-secret>
NODE_ADMIN_VERIFY_TLS=true
~~~

Проверка без изменений:

~~~bash
python3 scripts/import-node-admin-target.py   /root/3xui-node-admin-fi.env   --env .env   --check-only
~~~

Импорт:

~~~bash
python3 scripts/import-node-admin-target.py   /root/3xui-node-admin-fi.env   --env .env
~~~

Helper добавляет/обновляет `NODE_BACKUP_FI_*`, включая:

~~~env
NODE_BACKUP_FI_NODE_ID=2
~~~

и делает mode-0600 backup предыдущего `.env`.

## 4. Импортируй Host Control enrollment с тем же NODE_ID

Скопируй enrollment с remote VPS на Master защищённым каналом. Не используй `cat`, issue, PR или Telegram для token.

Проверка:

~~~bash
python3 scripts/import-host-control-enrollment.py   /root/3xui-host-control-fi.env   --env .env   --node-id 2   --check-only
~~~

Импорт и единственный recreate bot:

~~~bash
python3 scripts/import-host-control-enrollment.py   /root/3xui-host-control-fi.env   --env .env   --node-id 2   --recreate-bot
~~~

Итоговая Host Control binding содержит:

~~~env
HOST_CONTROL_FI_NODE_ID=2
~~~

## 5. Проверь Telegram Readiness

Открой:

`Infrastructure → Nodes → <node> → 🧭 Readiness`

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

После этого открой `🧩 3x-ui Control` и выполни обычный smoke-test.

## 6. Rename

При наличии `NODE_BACKUP_*_NODE_ID` и `HOST_CONTROL_*_NODE_ID` переименование node в 3x-ui не ломает privileged bindings.

Name-only target остаётся совместимым fallback для старых deployments, но Readiness показывает `legacy_name` и предлагает миграцию на `NODE_ID`.

## 7. Что остаётся разделённым намеренно

Node-sync token, direct-admin token и Host Control token — разные privilege domains. v4.11 не объединяет и не переиспользует эти секреты.

Telegram не хранит и не показывает их. Рекомендуемый onboarding выполняет secret-bearing шаги только локально на Master/target VPS.

## 8. После onboarding

После успешной проверки mode-0600 enrollment files можно удалить с Master. Bot `.env` и его защищённые backup-копии продолжают содержать необходимые credentials и должны храниться как secrets.
