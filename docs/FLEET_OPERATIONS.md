# Fleet Operations v4.13

Этот документ фиксирует scope и safety contract массовых операций по direct nodes.

## Цели

v4.13 добавляет четыре связанные возможности:

1. `🩺 Fleet Health` — read-only сводка по direct nodes.
2. `🛠 Fleet Maintenance` — controlled массовый вход/выход из maintenance.
3. `🚀 Controlled Rollout` — последовательное обновление 3x-ui или Xray.
4. `🧾 Fleet Jobs` — история fleet jobs и результатов.

Fleet layer оркестрирует существующие single-node механизмы. Он не создаёт второй update engine и не обходит backup, audit, no-retry, stable identity или post-condition проверки.

## Fleet Health

Health собирается только для direct nodes и показывает:

- состояние node из Master;
- enabled / maintenance;
- доступность Direct Panel API;
- тип Direct Admin binding: `node_id`, `legacy_name` или missing;
- состояние Host Control Agent;
- тип Host Control binding;
- итоговое состояние `healthy`, `maintenance`, `degraded` или `offline`.

`healthy` требует одновременно:

- node enabled;
- Master видит node online;
- Direct Panel API отвечает;
- Host Control сообщает `running`;
- Direct Admin и Host Control привязаны через stable `node_id`.

Fleet Health не выполняет mutation и доступен роли Read-only и выше.

## Fleet Maintenance

Оператор явно выбирает direct nodes и целевое состояние:

- `Enter maintenance`;
- `Exit maintenance`.

Перед mutation показывается review.

Batch выполняется строго последовательно. Уже достигнутое состояние считается `skipped`.

Если mutation подтверждена read-back проверкой, выполняется следующая node. Если результат state-changing запроса невозможно подтвердить, batch получает `unknown`, останавливается, а оставшиеся nodes отмечаются `not touched`.

Mutation автоматически не повторяется.

За один batch разрешено не более 20 nodes.

## Controlled Rollout

Поддерживаются:

- latest stable 3x-ui;
- конкретная Xray version, общая для всех выбранных nodes.

### Eligibility

До создания rollout plan каждая node должна:

- быть direct, не transitive;
- быть enabled и online;
- иметь доступный Direct Panel API;
- иметь доступный Host Control в состоянии `running`;
- иметь stable Direct Admin binding через `node_id`;
- иметь stable Host Control binding через тот же `node_id`.

Node с `legacy_name`, missing binding, offline/degraded state или недоступным direct API не участвует в rollout.

### Existing update engine

Для каждой node fleet rollout вызывает существующий `UpdateService`:

1. обычный update preflight;
2. fresh verified backup;
3. только затем intentional maintenance;
4. повторная direct-health проверка;
5. execute уже подготовленного operation;
6. существующая verification update engine;
7. exit maintenance только после подтверждённого success.

Обычный single-node update по-прежнему запрещён для disabled/offline node.

Fleet path может выполнить только уже prepared operation после intentional maintenance. Это узкое исключение не отменяет проверку fingerprint, версии, backup checksum, роли администратора или no-retry semantics.

### Canary

Первая node в выбранном порядке является canary.

После её успешного результата rollout переходит в `canary_passed` и требует отдельного подтверждения `Продолжить остальные`.

Canary failure/unknown немедленно останавливает plan; остальные nodes не затрагиваются.

### Stop-on-failure

Оставшиеся nodes обрабатываются строго по одной.

При первом результате `failed` или `unknown`:

- новые update mutation больше не отправляются;
- оставшиеся nodes получают `not_touched`;
- проблемная node остаётся в maintenance для ручной проверки;
- automatic retry отсутствует.

`unknown` не превращается в success без отдельной ручной проверки существующего single-node operation.

## Restart / crash safety

Rollout plan хранится рядом с bot DB в private journal `fleet/rollout-<id>.json` с mode 0600.

При старте бота plan в `canary_running` или `running` переводится в `interrupted`.

Ни update, ни maintenance mutation после рестарта автоматически не продолжаются и не повторяются.

Незавершённый `fleet.maintenance` job помечается `unknown` без replay.

## Roles

- Fleet Home / Health / Jobs: Read-only+.
- Fleet Maintenance: Admin+.
- Controlled Rollout: Admin+.
- Mass stop service / stop Xray в v4.13 отсутствуют намеренно.

Destructive `Stop service` и `Stop Xray` остаются только per-node Owner operations через `🧩 3x-ui Control`.

## Audit / Jobs

Fleet batch создаёт parent job:

- `fleet.maintenance`;
- `fleet.rollout`.

Controlled rollout дополнительно использует уже существующие per-node jobs `panel.update` / `xray.install`.

Audit фиксирует start/completion fleet operation и per-node rollout outcome без credentials.

## UI

~~~text
Infrastructure
└─ 🌐 Fleet Operations
   ├─ 🩺 Fleet Health
   ├─ 🛠 Enter maintenance
   ├─ ▶ Exit maintenance
   ├─ 🚀 Controlled rollout
   └─ 🧾 Fleet Jobs
~~~

## Не входит в v4.13

- mass `Stop service`;
- mass `Stop Xray`;
- parallel rollout;
- automatic rollback;
- automatic retry state-changing requests;
- automatic continuation after bot restart;
- mutation transitive nodes;
- rollout legacy-name privileged bindings.
