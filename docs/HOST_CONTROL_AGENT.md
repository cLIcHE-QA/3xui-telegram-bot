# v4.10.0 — контракт Host Control Agent

Статус: **зафиксированный контракт для реализации v4.10.0**.

Цель v4.10.0 — добавить в Telegram-бот безопасное управление **самим host-level сервисом 3x-ui**:

- получить состояние x-ui.service;
- запустить 3x-ui;
- остановить 3x-ui;
- перезапустить 3x-ui.

Это отдельный механизм от существующего 🔄 Restart Xray, который вызывает API 3x-ui и перезапускает только Xray Core.

Дополнительно v4.10.0 сохраняет штатный soft restart процесса панели:

~~~text
POST /panel/api/setting/restartPanel
~~~

Он оформляется как отдельное действие **♻️ Restart Panel process** и не заменяет host-level `restart x-ui.service`.

Итого control plane намеренно разделён:

- Xray Core → штатный API 3x-ui;
- Panel process soft restart → штатный `restartPanel` API;
- x-ui.service status/start/stop/restart → Host Control Agent.

`restartPanel` не является fallback для Host Control Agent, а Host Control Agent не является автоматическим fallback для `restartPanel`: оператор всегда явно выбирает нужную семантику.

---

## 1. Архитектура

~~~text
Telegram bot
    |
    | authenticated HTTP(S)
    v
Host Control Agent
    |
    | exact allowlisted systemctl commands
    v
systemd: x-ui.service
~~~

Host Control Agent запускается как отдельный systemd service и **не зависит от x-ui.service**.

Это обязательное требование: после stop x-ui.service агент должен остаться доступен, чтобы выполнить последующий start.

Агент не является SSH gateway, remote shell или general-purpose process manager.

---

## 2. Границы ответственности

### Агент МОЖЕТ

- читать состояние только x-ui.service;
- выполнять только start, stop и restart;
- возвращать результат и текущее состояние;
- хранить минимальный журнал host-control операций для idempotency/recovery;
- отдавать read-only snapshot nginx configuration только из одного заранее заданного локального каталога;
- писать безопасный audit trail в journald.

### Агент НЕ МОЖЕТ

- выполнять произвольные shell-команды;
- принимать имя systemd unit из HTTP-запроса;
- управлять другими сервисами;
- выполнять sudo sh, bash -c, eval или shell=True;
- принимать путь к executable из запроса;
- принимать filesystem path, имя файла или source directory из HTTP-запроса;
- предоставлять directory listing, arbitrary file read/write или general-purpose file API;
- читать или изменять 3x-ui DB;
- обновлять 3x-ui/Xray;
- менять firewall;
- управлять Docker;
- использовать Telegram credentials;
- переиспользовать PANEL_API_TOKEN или NODE_BACKUP_*_API_TOKEN.

Host-control credentials всегда отдельные.

---

## 3. Модель развёртывания

На каждом физическом сервере, которым нужно управлять, устанавливается отдельный агент:

~~~text
Master host
  x-ui.service
  3xui-host-control.service

Edge-1 host
  x-ui.service
  3xui-host-control.service
~~~

Рекомендуемая схема:

- agent слушает только loopback или отдельный management interface;
- TLS завершается reverse proxy;
- remote endpoint ограничен firewall/source allowlist;
- Edge-1 принимает host-control трафик только от Master VPS;
- endpoint не должен быть открыт всему Internet без source restriction.

Для локального Master допустим отдельный private host route из Docker-сети, если он не публикуется наружу и защищён firewall.

---

## 4. Локальные права агента

Агент работает от отдельного непривилегированного пользователя, например 3xui-hostctl.

Сервис **не запускается от root**.

Для state-changing операций используется sudo -n с точным allowlist.

Принцип sudoers:

~~~text
/usr/bin/systemctl start x-ui.service
/usr/bin/systemctl stop x-ui.service
/usr/bin/systemctl restart x-ui.service
~~~

Запрещены wildcard-команды вида:

~~~text
/usr/bin/systemctl *
~~~

Чтение состояния через systemctl show/is-active x-ui.service выполняется без elevated privileges, если это разрешено системой.

Имя unit задаётся локальной конфигурацией агента и **никогда не приходит из API request**.

---

## 5. Аутентификация

Все /v1/* endpoints требуют:

~~~http
Authorization: Bearer <dedicated-host-control-token>
~~~

Требования:

- отдельный token для каждого host;
- минимум 32 случайных байта энтропии;
- token не передаётся в URL/query string;
- token не пишется в логи;
- сравнение token выполняется constant-time;
- файлы с token имеют права не шире 0600;
- token Edge-1 не совпадает с token Master;
- host-control token не совпадает с node/API/backup token.

При неверном или отсутствующем token:

~~~http
401 Unauthorized
~~~

Ответ не должен раскрывать, какой именно credential был неверным.

---

## 6. Transport security

### Remote nodes

Для Edge-1 и последующих remote nodes:

- только https://;
- TLS verification включён;
- валидный hostname/certificate;
- source allowlist на стороне firewall/reverse proxy;
- VERIFY_TLS=false для remote host-control запрещён.

### Master/local host

Допустимы два варианта:

1. HTTPS через локальный/restricted reverse proxy — предпочтительно.
2. HTTP по выделенному private Docker/host management route — только если маршрут не доступен извне и ограничен firewall.

Plain HTTP через публичную сеть запрещён.

---

## 7. Идентичность host

У каждого агента есть постоянный локальный ID, например:

~~~text
master
edge-1
~~~

Он задаётся при установке и возвращается каждым API response.

Bot target содержит ожидаемый HOST_ID.

Если agent возвращает другой host_id, бот считает target неверным и запрещает mutation.

Это защищает от ошибки DNS/route/configuration, когда credential случайно ведёт не на тот сервер.

---

## 8. API v1

Базовый prefix:

~~~text
/v1
~~~

JSON UTF-8.

Максимальный request body для mutation — 4 KiB.

Неиспользуемые HTTP methods отклоняются.

### 8.1 GET /v1/status

Возвращает текущее состояние x-ui.service.

Пример:

~~~json
{
  "schema": 1,
  "host_id": "edge-1",
  "service": "x-ui.service",
  "state": "running",
  "active_state": "active",
  "sub_state": "running",
  "agent_version": "0.2.0",
  "timestamp": "2026-09-23T17:30:00Z"
}
~~~

Нормализованные state:

- running;
- stopped;
- failed;
- transitioning;
- unknown.

Маппинг:

- ActiveState=active → running;
- ActiveState=inactive → stopped;
- ActiveState=failed → failed;
- activating/deactivating/reloading → transitioning;
- остальное → unknown.

GET является safe/idempotent и может повторяться клиентом.

### 8.2 POST /v1/actions

Body:

~~~json
{
  "operation_id": "2f31b7a8d6bf4e4f8f9ef0c4d4c635de",
  "action": "restart"
}
~~~

operation_id:

- генерируется bot перед отправкой mutation;
- 32 lowercase hex symbols;
- уникален для одной logical operation;
- сохраняется bot audit/job до выполнения POST.

action принимает только:

~~~text
start
stop
restart
~~~

Любое другое значение:

~~~http
400 Bad Request
~~~

Пример успешного ответа:

~~~json
{
  "schema": 1,
  "host_id": "edge-1",
  "operation_id": "2f31b7a8d6bf4e4f8f9ef0c4d4c635de",
  "action": "restart",
  "result": "success",
  "changed": true,
  "before": "running",
  "after": "running",
  "duration_ms": 1834,
  "replayed": false
}
~~~

Нормализованный result:

- success;
- failed;
- uncertain.

### 8.3 GET /v1/operations/{operation_id}

Возвращает сохранённое состояние операции.

Пример:

~~~json
{
  "schema": 1,
  "host_id": "edge-1",
  "operation_id": "2f31b7a8d6bf4e4f8f9ef0c4d4c635de",
  "action": "restart",
  "result": "success",
  "before": "running",
  "after": "running",
  "duration_ms": 1834,
  "created_at": "2026-09-23T17:30:00Z",
  "finished_at": "2026-09-23T17:30:02Z"
}
~~~

Неизвестная операция:

~~~http
404 Not Found
~~~

Этот endpoint нужен для recovery после потерянного ответа на POST.

### 8.4 GET /v1/snapshots/nginx

Read-only endpoint для Extended direct-node backup. Он возвращает gzip tar только из локального source, настроенного на самом target VPS через `HOST_CONTROL_AGENT_NGINX_SOURCE`.

HTTP request **не принимает** path, filename, glob, command, argv или другой selector. Query string также запрещён. Поэтому Master/Telegram не может попросить agent прочитать `/etc/passwd`, произвольный каталог или другой host file.

Архив содержит:

~~~text
<nginx files...>
_snapshot.json
~~~

`_snapshot.json` фиксирует:

- `schema` и stable `host_id`;
- timestamp;
- список файлов;
- размер и SHA-256 каждого файла;
- пропущенные/недоступные элементы;
- `complete=true|false`.

Agent обходит только настроенный source, не следует в symlink-directory и не читает symlink, ведущий за пределы source. Special/device entries не попадают в snapshot. Число файлов и суммарный размер ограничены.

Если source не настроен:

~~~http
404 Not Found
~~~

с безопасным code `nginx_snapshot_unconfigured`.

Если часть конфигурации нельзя безопасно прочитать, snapshot может быть выдан как `complete=false`. Bot обязан отразить его как degraded/missing component, а не считать полным node backup.

Этот endpoint не является file browser и не расширяет mutation allowlist: `POST /v1/actions` по-прежнему принимает только `start|stop|restart`.

---

## 9. Idempotency и lost-response recovery

Агент хранит operation journal локально, например в SQLite:

~~~text
/var/lib/3xui-host-control/agent.sqlite3
~~~

Минимально сохраняются:

- operation_id;
- action;
- before;
- after;
- result;
- timestamps;
- duration;
- безопасный error code.

Перед запуском systemctl операция записывается как started.

После завершения обновляется в success, failed или uncertain.

Если тот же operation_id приходит повторно с тем же action:

- команда повторно **не выполняется**;
- возвращается сохранённый результат;
- replayed=true.

Если тот же operation_id приходит с другим action:

~~~http
409 Conflict
~~~

Bot **никогда автоматически не повторяет POST mutation после timeout/network error**.

Вместо этого он делает:

~~~text
POST lost/timeout
  ↓
GET /v1/operations/{operation_id}
  ↓
found → use recorded result
not found → uncertain, no automatic mutation retry
~~~

---

## 10. Concurrency

На одном agent одновременно выполняется не более одной state-changing операции.

При второй конкурентной mutation:

~~~http
409 Conflict
~~~

с безопасным error code:

~~~json
{
  "error": "operation_in_progress"
}
~~~

GET status/operation остаются доступны во время mutation.

---

## 11. Action semantics

### start

Если уже running:

- result=success;
- changed=false;
- повторный systemctl start не требуется.

Если stopped/failed:

- выполнить exact systemctl start x-ui.service;
- дождаться post-condition running.

### stop

Если уже stopped:

- result=success;
- changed=false.

Иначе:

- выполнить exact systemctl stop x-ui.service;
- дождаться post-condition stopped.

### restart

- выполнить exact systemctl restart x-ui.service;
- дождаться post-condition running.

Для restart состояние running → running само по себе не является доказательством выполнения; authoritative result берётся из operation journal.

### Restart Panel process

Это отдельная native 3x-ui операция, не action Host Control Agent:

~~~http
POST /panel/api/setting/restartPanel
~~~

Правила:

- доступна только для Master или direct node с admin-scope direct API token;
- transitive node не поддерживается;
- POST отправляется ровно один раз;
- если 3x-ui явно отклонил запрос, результат failed;
- если HTTP response потерян, POST **не повторяется**;
- после обычного accepted response bot ждёт grace period и подтверждает возврат Panel API;
- после lost response success допускается только если bot наблюдал Panel API down → up;
- если post-condition доказать нельзя, результат uncertain;
- automatic fallback на Host Control Agent запрещён.

### Xray Core

Native endpoints:

~~~http
POST /panel/api/server/stopXrayService
POST /panel/api/server/restartXrayService
~~~

`restartXrayService` используется и как Restart, и как Start после ручного Stop. Stop Xray — Owner-only; Restart / Start Xray — Admin+.

---

## 12. Timeouts и post-condition

Agent использует ограниченные timeout:

- command timeout;
- post-condition timeout.

Рекомендуемый стартовый предел для v4.10.0: 20 секунд на operation.

Если команда завершилась ошибкой:

- result=failed;
- возвращается безопасный error_code;
- stderr не пересылается пользователю целиком.

Если результат нельзя доказать:

- result=uncertain;
- mutation автоматически не повторяется.

После успешного host-control action bot дополнительно проверяет:

~~~text
agent /v1/status
~~~

Для start/restart после этого проверяется 3x-ui Panel API.

Успех Telegram UI показывается только после подтверждённого expected state.

---

## 13. HTTP status contract

- 200 — status read или завершённая/cached operation;
- 400 — invalid request/action/operation_id;
- 401 — authentication failed;
- 404 — operation not found или локальный nginx snapshot source не настроен;
- 409 — concurrent operation или operation_id conflict;
- 413 — nginx snapshot превышает ограничение размера/числа файлов;
- 500 — internal agent error;
- 503 — systemctl/post-condition failed;
- 504 — timeout / uncertain execution.

При 503/504 JSON body всё равно содержит operation_id и нормализованный result.

---

## 14. Bot configuration

Предварительный env contract:

~~~env
HOST_CONTROL_TARGETS=MASTER,NODE1

HOST_CONTROL_MASTER_NAME=Master
HOST_CONTROL_MASTER_HOST_ID=master
HOST_CONTROL_MASTER_URL=https://host-control-master.example.com
HOST_CONTROL_MASTER_TOKEN=replace_with_dedicated_token
HOST_CONTROL_MASTER_VERIFY_TLS=true

HOST_CONTROL_NODE1_NAME=Edge-1
HOST_CONTROL_NODE1_HOST_ID=edge-1
HOST_CONTROL_NODE1_URL=https://host-control-node1.example.com
HOST_CONTROL_NODE1_TOKEN=replace_with_dedicated_token
HOST_CONTROL_NODE1_VERIFY_TLS=true
~~~

Tokens не выводятся в Telegram, logs, audit details или diagnostics.

Target lookup выполняется по configured alias/name и expected HOST_ID.

Host-control config не переиспользует NODE_BACKUP_TARGETS: это отдельный privilege domain.

---

## 15. Agent configuration

Предварительный local config:

~~~env
HOST_CONTROL_AGENT_ID=edge-1
HOST_CONTROL_AGENT_LISTEN=127.0.0.1:18181
HOST_CONTROL_AGENT_TOKEN_FILE=/etc/3xui-host-control/token
HOST_CONTROL_AGENT_SERVICE=x-ui.service
HOST_CONTROL_AGENT_DB=/var/lib/3xui-host-control/agent.sqlite3
HOST_CONTROL_AGENT_OPERATION_TIMEOUT=20
~~~

Опциональный fixed source для nginx snapshot хранится отдельно, чтобы обычная повторная установка agent не перезаписывала локальный выбор:

~~~env
# /etc/3xui-host-control/nginx-snapshot.env
HOST_CONTROL_AGENT_NGINX_SOURCE=/etc/nginx
~~~

Systemd unit читает этот файл через optional `EnvironmentFile=-...`. `HOST_CONTROL_AGENT_SERVICE` и `HOST_CONTROL_AGENT_NGINX_SOURCE` читаются только локально при startup.

`HOST_CONTROL_AGENT_NGINX_SOURCE` необязателен. Он должен быть абсолютным существующим каталогом, не filesystem root и не symlink. Файл `nginx-snapshot.env` создаёт оператор локально на target VPS; он не входит в bot enrollment и не управляется через Telegram.

HTTP request не может изменить service name или nginx source.

### 15.1 Deployment boundary

Репозиторий содержит:

~~~text
host_control_agent.py
deploy/host-control/3xui-host-control.service
deploy/host-control/3xui-host-control.sudoers
scripts/install-host-control-agent.sh
~~~

Installer запускается локально на конкретном VPS от root и:

- создаёт системного пользователя `3xui-hostctl` без login shell;
- устанавливает agent как root-owned executable;
- генерирует отдельный random token локально, сохраняет его с mode `0600` и **не печатает**;
- валидирует sudoers через `visudo -cf`;
- устанавливает exact sudoers allowlist только для start/stop/restart `x-ui.service`;
- запускает agent на `127.0.0.1:18181`;
- устанавливает unit с optional `/etc/3xui-host-control/nginx-snapshot.env`, но сам не выбирает и не передаёт nginx filesystem path;
- **не меняет firewall, SSH, Docker или reverse proxy**.

Agent никогда не слушает публичный или private-LAN interface напрямую.

Для remote node (Edge-1) внешний доступ строится только так:

~~~text
Master bot
   |
   | HTTPS + Bearer token
   v
restricted reverse proxy on Edge-1
   |
   | loopback
   v
127.0.0.1:18181 Host Control Agent
~~~

Reverse proxy должен:

- использовать валидный TLS certificate;
- принимать host-control запросы только от management source (для Edge-1 — Master VPS);
- не публиковать backend port 18181;
- не логировать Authorization header;
- проксировать только `/v1/` к loopback agent.

Для Master допустим restricted private Docker-host route или аналогичный локальный reverse proxy. Plain HTTP разрешён bot config только для alias `MASTER` на private/local адресе; любой remote target, включая private-address node, требует verified HTTPS.

---

## 16. Telegram permissions

Минимальные роли:

| Operation | Minimum role |
| --- | --- |
| Status | Read-only |
| Start service | Admin |
| Restart service | Admin |
| Restart Panel process | Admin |
| Restart / Start Xray | Admin |
| Stop Xray | Owner |
| Stop service | Owner |

Transitive nodes — read-only, host-control mutations запрещены.

### Restart service confirmation

~~~text
⚠️ Перезапустить 3x-ui service на Edge-1?

Панель и API будут кратковременно недоступны.
VPN-сессии могут быть затронуты.

[🔄 Да, restart service]
[✖ Отмена]
~~~

### Restart Panel process confirmation

~~~text
⚠️ Выполнить штатный Restart Panel process на Edge-1?

Будет отправлен ровно один POST /panel/api/setting/restartPanel.
Panel API кратковременно станет недоступен.

[♻️ Да, restart panel]
[✖ Отмена]
~~~

### Stop service confirmation

Stop service — Owner-only и требует усиленного подтверждения.

План v4.10.0: одноразовый confirmation nonce + явная фраза с именем target, например:

~~~text
STOP Edge-1
~~~

Nonce имеет короткий TTL и используется один раз.

После stop интерфейс должен сохранять кнопку ▶ Start, потому что host-control agent продолжает работать независимо от 3x-ui.

---

## 17. Telegram UI

На Master/direct node появляется отдельный экран:

~~~text
🧩 3x-ui · Edge-1

🟢 Service: running
🟢 Panel API: online

[▶ Start service]
[🔄 Restart service]
[⏹ Stop service]

[♻️ Restart Panel process]

[🔄 Restart / Start Xray]
[⏹ Stop Xray]

[⬅ Нода]
~~~

Кнопка Stop Xray отображается только Owner; destructive Stop service также Owner-only.

UI не должен объединять или путать:

- Xray Core restart;
- штатный Panel process restart через `/panel/api/setting/restartPanel`;
- x-ui.service restart через Host Control Agent.

---

## 18. Bot audit/job contract

Используются существующие audit и job_runs.

Action names:

~~~text
host_control.start
host_control.stop
host_control.restart
panel.restart
xray.stop
xray.restart
~~~

Target:

~~~text
target_type=host_control
target_id=<configured target display name>
~~~

Audit/job details могут содержать:

- operation_id;
- action;
- before;
- after;
- result;
- duration_ms;
- normalized error code.

Запрещено сохранять:

- Authorization header;
- token;
- полный agent URL с embedded credentials;
- raw sudo/systemctl stderr, если в нём потенциально есть sensitive host data.

uncertain считается неуспешным/неподтверждённым исходом и явно показывается администратору.

---

## 19. Agent logging

Agent пишет в journald:

- timestamp;
- host_id;
- operation_id;
- action;
- result;
- before/after;
- duration;
- source address, если доступен;
- normalized error code.

Token и Authorization header никогда не логируются.

---

## 20. Threat model

### Unauthorized Telegram user

Защита: существующая role model + Owner-only Stop.

### Stolen 3x-ui API/node token

Защита: host-control использует отдельный credential domain.

### Arbitrary command injection и выход на VPS

Критическое требование v4.10.0: Telegram bot и Host Control Agent **не предоставляют способ получить shell или произвольный доступ к VPS**.

Защита:

- отсутствуют SSH endpoints и SSH execution;
- отсутствуют shell/exec/run endpoints;
- отсутствуют параметры command, argv, executable, path, service/unit name;
- subprocess запускается только со статическим списком аргументов и `shell=False`;
- executable фиксирован локально;
- unit фиксирован локально как `x-ui.service`;
- action — строгий enum `start|stop|restart`;
- agent user непривилегированный;
- sudoers содержит только точные команды для `x-ui.service`, без wildcard;
- Telegram input никогда не интерполируется в командную строку;
- нет файлового API, upload/download, чтения env, произвольных host logs или произвольных путей;
- нет Docker/firewall/reboot/package-management возможностей.

Любая будущая функция, которая нарушает этот список, требует отдельного threat-model review и не входит в v4.10.0.

### Replay/double restart

Защита: persistent operation_id journal + no mutation retry.

### Concurrent mutations

Защита: single-operation lock + 409.

### Network MITM

Защита: HTTPS/TLS verify для remote node.

### Wrong host / DNS misroute

Защита: expected host_id verification.

### Accidental Stop

Защита: Owner-only + explicit typed confirmation + audit.

### x-ui stopped

Защита: agent independent from x-ui service.

### Agent host compromise

Не считается решаемым на уровне данного API: root/admin compromise физического host означает полный контроль над x-ui.

### Telegram bot host compromise

Bot host содержит host-control tokens. Поэтому blast radius ограничивается:

- отдельным token на host;
- source firewall allowlist;
- отсутствием arbitrary commands;
- разрешением управления только x-ui.service.

---

## 21. Fail-closed requirements

Mutation запрещается, если:

- agent сообщает systemd state `unknown` или `transitioning`;
- target отсутствует в HOST_CONTROL_TARGETS;
- token отсутствует;
- URL/transport не соответствует policy;
- host_id не совпадает;
- target transitive;
- роль Telegram ниже требуемой;
- confirmation истёк;
- другая operation выполняется;
- agent response нарушает schema;
- result не может быть достоверно подтверждён.

В этих случаях бот не пытается fallback через SSH или другой канал.

---

## 22. Acceptance criteria v4.10.0

Релиз считается готовым, если тестами и production smoke test подтверждено:

1. Status работает для Master и Edge-1.
2. Start уже running target не делает лишний restart.
3. Stop уже stopped target безопасно idempotent.
4. Restart выполняется ровно один раз.
5. Повтор одного operation_id не выполняет command второй раз.
6. Потеря POST response восстанавливается через operation lookup.
7. Неизвестный operation остаётся uncertain, POST не повторяется.
8. Concurrent mutation блокируется.
9. При `unknown/transitioning` systemd state mutation блокируется до POST/systemctl.
10. Произвольный action отклоняется.
11. Произвольный systemd unit передать невозможно.
12. Неверный token даёт 401 без утечки деталей.
13. Wrong host_id блокирует mutation.
14. Stop service и Stop Xray доступны только Owner.
15. Restart/Start service, Restart Panel process и Restart/Start Xray доступны Admin/Owner.
16. Read-only может смотреть status, но не выполнять mutation.
17. Agent остаётся доступен после stop x-ui.service.
18. После host-level start/restart проверяется и systemd state, и 3x-ui Panel API.
19. `Restart Panel process` вызывает только `POST /panel/api/setting/restartPanel` и не выполняет systemctl.
20. Потеря ответа `restartPanel` не вызывает автоматический повтор POST; итог подтверждается возвратом Panel API либо остаётся uncertain.
21. `Restart Panel process` доступен для Master и direct nodes с admin-scope API token и запрещён для transitive nodes.
22. Ни один Telegram callback/message не может задавать command, executable, argv, path или systemd unit.
23. Агент не содержит SSH/shell/exec/file/Docker/firewall/reboot/package-management API.
24. Sudoers использует только точные allowlisted команды для `x-ui.service`, без wildcard.
25. Audit/job records не содержат secrets.
26. Edge-1 remote transport работает с TLS verification.
27. Существующие Backup, Xray restart, provisioning, subscription и Версии и обновления не регрессируют.

---

## 23. Что намеренно не входит в v4.10.0

- arbitrary service management;
- SSH execution;
- Docker management;
- reboot/shutdown host;
- package updates;
- firewall management;
- 3x-ui/Xray update orchestration;
- fleet-wide bulk actions;
- automatic retry state-changing requests;
- automatic rollback;
- node onboarding/readiness wizard.

Fleet-wide операции остаются целью v4.12.0.

Для v4.11.0 отдельно зафиксирована цель **Node readiness / onboarding**:
- preflight готовности Panel API, direct admin и Host Control Agent;
- упрощённое добавление/замена direct nodes;
- уход от ручной привязки privileged targets к display name в пользу стабильной identity там, где это можно сделать без ослабления security boundary;
- onboarding-flow, который помогает подготовить локальную конфигурацию и проверяет её, но не принимает и не хранит host/admin secrets через Telegram;
- существующие `NODE_BACKUP_*` и `HOST_CONTROL_*` остаются поддерживаемым fail-safe способом конфигурации.
