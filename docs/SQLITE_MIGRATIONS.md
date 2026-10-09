# Versioned SQLite migrations

Этот документ фиксирует migration contract для локальной bot database `bot.sqlite3`.

Механизм относится только к SQLite самого Telegram-бота. Базы 3x-ui на Master/direct nodes мигрируются самим 3x-ui и не управляются этим framework.

## Источник истины

Схема бота управляется каталогом `MIGRATIONS` в `db_migrations.py`.

Каждый шаг имеет:

- целочисленный `version`;
- стабильное `name`;
- функцию `apply`;
- флаг `requires_backup`.

Версии идут строго подряд, начиная с `1`. Пропуски, дубликаты и переименование уже опубликованной migration считаются ошибкой.

Текущая версия схемы определяется последним элементом каталога, а не версией приложения.

## Migration journal

В каждой bot DB создаётся служебная таблица `schema_migrations`.

Для каждого шага фиксируются:

- version/name;
- `running | success | failed`;
- требовалась ли recovery copy;
- путь к созданной recovery copy;
- время начала/завершения;
- диагностическая ошибка.

Journal является source of truth о применённых преобразованиях.

Legacy DB без `schema_migrations` не считается ошибкой: migration `v1 baseline_v4_14_2` идемпотентно доводит её до канонической схемы v4.14.2, проверяет ожидаемые таблицы/колонки/indexes и сохраняет существующие данные.

## Текущий каталог schema

Для `v4.24.0`, `v4.24.1`, `v4.25.0`, `v4.25.1`, `v4.25.2`, `v4.25.3`, `v4.25.4`, `v4.25.5`, `v4.25.6`, `v4.25.7`, `v4.25.8`, `v4.26.0`, `v4.26.1`, `v4.26.2`, `v4.26.3`, `v4.26.4`, `v4.26.5`, `v4.26.6`, `v4.26.7` и `v4.26.8` текущая bot schema version — **5**.

Для `v4.26.9` текущая bot schema version — **7**. Этот release впервые публикует additive Client Portal migrations v6/v7 поверх исторической v4 baseline.

Для `v5.0.0-rc.1` и `v5.0.0-rc.2` опубликованная bot schema version — **10**.

Для опубликованного `v5.0.0-rc.7` bot schema version — **11** (впервые опубликована в `rc.3`). В текущем коде ветки разработки схема **12**; до публикации следующего релиза схема v12 не считается развёрнутой. Полный каталог ветки:

1. `v1 baseline_v4_14_2` — исходная каноническая схема v4.14.2;
2. `v2 user_display_name_v4_21_0` — additive `display_name TEXT NOT NULL DEFAULT ''` в `user_profiles`;
3. `v3 user_audience_groups_v4_22_0` — additive таблицы `user_groups` / `user_group_members` и индекс `idx_user_group_members_user`;
4. `v4 website_monitoring_v4_24_0` — additive persistence foundation для website monitoring: canonical monitor targets, many-to-many admin watchers, incidents и idempotent notification journal;
5. `v5 website_watcher_lifecycle_v4_24_0` — additive `monitoring_enabled INTEGER NOT NULL DEFAULT 1` для watcher-scoped pause/resume без глобального выключения target.
6. `v6 client_portal_commerce_foundation_v5_0_0` — additive commerce foundation: отдельные `commerce_orders`, `commerce_payments`, immutable/minimally-mutable `payment_webhook_events` и `entitlements`. Существующая административная таблица `payments` не меняется и не становится источником истины для customer commerce.
7. `v7 payment_event_reconciliation_v5_0_0` — additive `provider_payment_id TEXT NOT NULL DEFAULT ''` в `payment_webhook_events` для безопасного restart/reconciliation уже аутентифицированных provider events без хранения raw payload.
8. `v8 checkout_reference_v5_0_0` — additive `checkout_url` + `idempotency_key` в `commerce_payments` и partial unique index `provider + idempotency_key` для durable checkout retry без создания второго provider payment.
9. `v9 telegram_stars_price_v5_0_0` — additive `plans.stars_price INTEGER NOT NULL DEFAULT 0` для независимой цены цифровой подписки в Telegram Stars (`XTR`) без неявной конвертации из fiat price.
10. `v10 stars_production_hardening_v5_0_0` — versioned Terms acceptance и persistent one-shot Telegram Stars refund journal.
11. `v11 entitlement_quota_cycle_v5_0_0` — additive `entitlements.quota_reset_status` для durable one-shot quota reset после подтверждённой покупки/продления; существующие entitlement rows маркируются `legacy` и не получают автоматический traffic reset.
12. `v12 bot_update_unknown_ack_v5_0_0` — отдельная append-only таблица `bot_update_acknowledgments` по `job_run_id`, с безопасным read-only evidence, owner actor, reason, timestamp и SQLite triggers против UPDATE/DELETE.


Commerce write contract поверх schema v6: authenticated `payment.confirmed` применяется одной SQLite transaction (`BEGIN IMMEDIATE`). В одной commit boundary фиксируются `commerce_payments.status=confirmed`, `commerce_orders.status=paid`, exactly-one `entitlements` row и `payment_webhook_events.processing_status=applied`. Исключение до commit откатывает весь набор изменений; повтор того же provider event с тем же payload безопасно возвращает уже применённый результат, а повтор event id с другим payload fail-closed.

Entitlement provisioning contract: после подтверждённой оплаты entitlement согласуется через существующий `ProvisioningEngine`, а не прямыми вызовами 3x-ui. Локальный lifecycle — `pending → provisioning → active`; определённая ошибка переводит entitlement в `failed`, но не откатывает `payment=confirmed`/`order=paid`. Целевой expiry фиксируется в entitlement до remote mutation и при активном продлении рассчитывается от `max(now, current_expiry)`, поэтому повторный безопасный recovery не начисляет второй срок. Для finite-traffic Plan после успешного apply/read-back параметров выполняется отдельный quota reset; его durable status проходит `pending/failed → in_flight → success|failed|unknown`. `unknown`/зависший `in_flight` не replay'ится автоматически. Только после доказанного quota reset или `not_required` локальный expiry публикуется клиенту и entitlement становится `active`.

Payment-event recovery contract: только journaled events с `signature_valid=1`, `event_type=payment.confirmed`, `processing_status=failed`, `result_code=payment_not_found` и непустым `provider_payment_id` могут автоматически согласовываться после restart. Reconciliation использует сохранённый payload hash и authenticated journal identity; raw provider payload и webhook secret для replay не требуются. Повтор event ID с другим payment reference считается identity conflict и fail-closed.

Migration v2–v12 имеют `requires_backup=False`: они additive, не удаляют существующие пользовательские записи и проверяют postcondition соответствующей версии schema внутри migration transaction до записи `success`. Для v3 membership хранится по стабильному `telegram_id`; сама migration не назначает пользователей в группы. Для v4 существующие rows не создаются и monitoring начинается только после явного add/subscribe action. Migration v5 сохраняет все существующие subscriptions активными по умолчанию и не меняет notification preferences. Migration v6 только создаёт новые commerce-таблицы и индексы; существующие users, plans, promo codes и legacy admin payments не переписываются. Migration v7 только добавляет безопасный provider payment reference в webhook journal; существующие rows получают пустое значение и не считаются автоматически replayable без нового доверенного provider delivery. Migration v8 только добавляет checkout reference/idempotency columns и partial unique index; существующие payments получают пустые значения и не становятся checkout-retry candidates. Migration v9 только добавляет `stars_price=0`; существующие тарифы не становятся продаваемыми через Stars до явной настройки администратором. Migration v11 добавляет quota-reset journal column, существующие rows явно переводит в `legacy`, а новые entitlement rows получают `pending`; migration не вызывает 3x-ui и не сбрасывает traffic сама.

После успешного применения более новой schema старый application release, который её не знает, обязан остановиться как `DatabaseSchemaTooNewError`. Поэтому downgrade приложения через обычную смену tag без восстановления совместимой pre-migration DB не поддерживается.

## Startup semantics

`Database.init()` сначала запускает migration engine и только после успешного завершения обычный runtime продолжает startup.

Startup блокируется fail-closed, если:

- в journal есть `running` или `failed` migration;
- journal содержит gap/неизвестную migration;
- имя или backup policy опубликованной migration не совпадает с кодом;
- DB имеет schema version новее текущего кода;
- каноническая структура таблиц/indexes не совпадает с ожидаемой;
- `PRAGMA quick_check` не проходит.

Migration с неопределённым/failed результатом автоматически повторно не запускается. Сначала оператор должен диагностировать причину и восстановить/исправить DB контролируемым способом.

## Transaction boundary

Перед schema/data mutation journal отдельно фиксирует состояние `running`.

Сам migration step выполняется в SQLite transaction. При Python/SQLite exception transaction откатывается, а journal после rollback переводится в `failed`.

При аварийном завершении процесса transaction SQLite откатывается, но уже закоммиченный `running` остаётся в journal. Следующий startup блокируется и не повторяет migration автоматически.

## Recovery copy для опасных migrations

Простые идемпотентные additive migrations могут иметь `requires_backup=False`.

Migration, которая меняет/переписывает существующие данные или структуру с риском потери/необратимого преобразования, обязана иметь `requires_backup=True`.

До записи `running` engine создаёт SQLite Online Backup recovery copy и выполняет для неё `PRAGMA quick_check`. Если создать пригодную копию нельзя, migration не начинается.

По умолчанию `Database` хранит такие копии рядом с bot DB:

~~~text
/app/data/
├─ bot.sqlite3
└─ migration-backups/
   └─ migration-v<N>-YYYYMMDD-HHMMSS.sqlite3
~~~

Для Docker deployment это persistent volume `./data`.

Recovery copy является дополнительной защитой migration layer и не заменяет обычный Full Backup и pre-release backup `scripts/deploy-release.sh`.

## Как добавлять новую migration

1. Не изменять уже опубликованные steps.
2. Добавить новый async step с очередным version.
3. Явно решить, нужен ли `requires_backup=True`.
4. Сохранить mutation внутри переданной SQLite connection; не открывать вторую writable connection к той же DB.
5. Сделать postcondition проверки внутри migration, если одного schema validation недостаточно.
6. Добавить regression test upgrade со старого состояния, failure/rollback path и backup path для dangerous migration.
7. Если оператору нужны новые действия при rollout/recovery, обновить `docs/ADMIN_SETUP.md` в том же PR.

## Rollback

Framework является forward-only: автоматических down migrations нет.

Откат application release после уже применённой более новой DB migration может быть несовместим. Старый код обязан увидеть более новую schema version и остановиться fail-closed, а не пытаться работать с неизвестной схемой.

Для восстановления используется проверенная pre-migration recovery copy или Full Backup по документированному recovery flow. Автоматический restore при migration failure не выполняется.

### v10 — stars_production_hardening_v5_0_0

- сохраняет versioned customer Terms acceptance перед созданием Telegram Stars invoice;
- добавляет persistent journal one-shot Stars refund operations (`in_flight/success/failed/unknown`);
- refund с неизвестным исходом не replay'ится автоматически; успешный refund атомарно переводит commerce payment в `refunded`.

### v11 — entitlement_quota_cycle_v5_0_0

- добавляет `entitlements.quota_reset_status` со значениями `pending/legacy/not_required/in_flight/success/failed/unknown`;
- existing rows после upgrade получают `legacy`, чтобы новый release не угадывал, был ли их traffic уже сброшен;
- новый finite paid entitlement перед reset фиксирует `in_flight`, выполняет ровно один `bulkResetTraffic` и сохраняет `success/failed/unknown`;
- `unknown` или crash после `in_flight` блокируют автоматический replay reset;
- target expiry хранится в entitlement до remote provisioning; активное продление добавляет duration к `max(now, current_expiry)`, а не отбрасывает оставшийся срок;
- schema migration сама не выполняет remote mutations и не требует operator action при обычном startup.

### v12 — bot_update_unknown_ack_v5_0_0

Owner подтверждает исторический `bot.update` unknown двухшаговым UI после read-only GET correlation. Одна SQLite transaction атомарно фиксирует acknowledgment и audit event; duplicate noop. Migration не меняет `job_runs.status`, не вызывает Deploy Agent. Attention Center исключает лишь конкретный подтверждённый run ID; новые сбои по тому же job name продолжают отображаться. Откат на `rc.7` после schema v12 требует совместимого pre-migration DB restore.
