# Versioned SQLite migrations

Этот документ описывает **нормативный контракт** миграций локальной bot database `bot.sqlite3`. Схема Master/direct nodes 3x-ui управляется самим 3x-ui, не данным framework. Каталог `MIGRATIONS` в [db_migrations.py](../db_migrations.py) — единственный source of truth: версия схемы равна последнему элементу каталога, а не версии релиза. Не приписывать `main`-schema уже опубликленному или deployed tag без отдельного подтверждения [Roadmap](ROADMAP.md).

## Текущий контракт schema

- Текущий каталог содержит additive schema **v15** `plan_hwid_limit_v5_0_0`, `plans.hwid_limit INTEGER NULL DEFAULT NULL` (0…1000). Для legacy `NULL` означает «сохранить индивидуальный HWID», **не** «без ограничения» и **не** `0`.
- `v14 plan_audience_v5_0_0` добавляет независимую RUB/Stars видимость, локальные User Groups и `manual_entitlements`; один live/unknown journal запрещает конкурентную выдачу. Schema v15 сохраняет историю, при `in_flight/unknown` запрещён автоматический replay; read-only batch/filter ручных выдач не создаёт новую миграцию, заказ или платёж.
- Все миграции **forward-only**; pre-migration backup, `schema_migrations`, postcondition и `PRAGMA quick_check` обязательны по соответствующим правилам ниже. `requires_backup=True` для опасной миграции, без recovery copy её нельзя начинать. Старый код на более новой schema блокируется `DatabaseSchemaTooNewError`.
- Current Published/Deployed/Accepted всегда проверяйте по [Roadmap](ROADMAP.md), отдельно от schema каталога в `main`. Любое production deployment и DB mutation требуют отдельного разрешения.

## Историческая эволюция release/schema (не действующий статус)

Исходная release-by-release таблица `v4.24`–`rc.16.6`, прежние отметки «ещё не Deployed/Accepted», release-prep `rc.16.1` и кандидат `rc.16.2` сохранены в [immutable snapshot этого документа](https://github.com/cLIcHE-QA/3xui-telegram-bot/blob/8d5b9ad1ce1fecf8f5f1808c786f3b2b3cf32f0b/docs/SQLITE_MIGRATIONS.md), а публикации и приёмка — в [CHANGELOG](../CHANGELOG.md) и [Roadmap](ROADMAP.md). Это исторические утверждения, не фактический текущий deployment.

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

Текущий versioned каталог указан ниже. Историческое соответствие конкретных release-кандидатов версиям schema сохранено в immutable snapshot выше.

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
13. `v13 stars_invoice_cleanup_v5_0_0` — additive `stars_invoice_messages` (order/chat/message identity, `pending/attempted/success/unknown`) для one-shot косметического удаления оплаченных Stars invoices. `attempted` фиксируется до Telegram API; неопределённый результат не повторяется автоматически. Никаких финансовых статусов это не меняет.


14. `v14 plan_audience_v5_0_0` — независимый флаг наличия RUB-цены, правила видимости локальных User Groups и таблица `manual_entitlements` со статусами `in_flight/active/unknown/failed/superseded`. Старые планы мигрируют без удаления валют/истории и без автоматических назначений. Уникальный partial index запрещает вторую live/unknown выдачу одному пользователю.

Commerce write contract поверх schema v6: authenticated `payment.confirmed` применяется одной SQLite transaction (`BEGIN IMMEDIATE`). В одной commit boundary фиксируются `commerce_payments.status=confirmed`, `commerce_orders.status=paid`, exactly-one `entitlements` row и `payment_webhook_events.processing_status=applied`. Исключение до commit откатывает весь набор изменений; повтор того же provider event с тем же payload безопасно возвращает уже применённый результат, а повтор event id с другим payload fail-closed.

Entitlement provisioning contract: после подтверждённой оплаты entitlement согласуется через существующий `ProvisioningEngine`, а не прямыми вызовами 3x-ui. Локальный lifecycle — `pending → provisioning → active`; определённая ошибка переводит entitlement в `failed`, но не откатывает `payment=confirmed`/`order=paid`. Целевой expiry фиксируется в entitlement до remote mutation и при активном продлении рассчитывается от `max(now, current_expiry)`, поэтому повторный безопасный recovery не начисляет второй срок. Для finite-traffic Plan после успешного apply/read-back параметров выполняется отдельный quota reset; его durable status проходит `pending/failed → in_flight → success|failed|unknown`. `unknown`/зависший `in_flight` не replay'ится автоматически. Только после доказанного quota reset или `not_required` локальный expiry публикуется клиенту и entitlement становится `active`.

Payment-event recovery contract: только journaled events с `signature_valid=1`, `event_type=payment.confirmed`, `processing_status=failed`, `result_code=payment_not_found` и непустым `provider_payment_id` могут автоматически согласовываться после restart. Reconciliation использует сохранённый payload hash и authenticated journal identity; raw provider payload и webhook secret для replay не требуются. Повтор event ID с другим payment reference считается identity conflict и fail-closed.

Migration v2–v14 имеют `requires_backup=False`: они additive, не удаляют существующие пользовательские записи и проверяют postcondition соответствующей версии schema внутри migration transaction до записи `success`. Для v3 membership хранится по стабильному `telegram_id`; сама migration не назначает пользователей в группы. Для v4 существующие rows не создаются и monitoring начинается только после явного add/subscribe action. Migration v5 сохраняет все существующие subscriptions активными по умолчанию и не меняет notification preferences. Migration v6 только создаёт новые commerce-таблицы и индексы; существующие users, plans, promo codes и legacy admin payments не переписываются. Migration v7 только добавляет безопасный provider payment reference в webhook journal; существующие rows получают пустое значение и не считаются автоматически replayable без нового доверенного provider delivery. Migration v8 только добавляет checkout reference/idempotency columns и partial unique index; существующие payments получают пустые значения и не становятся checkout-retry candidates. Migration v9 только добавляет `stars_price=0`; существующие тарифы не становятся продаваемыми через Stars до явной настройки администратором. Migration v11 добавляет quota-reset journal column, существующие rows явно переводит в `legacy`, а новые entitlement rows получают `pending`; migration не вызывает 3x-ui и не сбрасывает traffic сама.

После успешного применения более новой schema старый application release, который её не знает, обязан остановиться как `DatabaseSchemaTooNewError`. Поэтому downgrade приложения через обычную смену tag без восстановления совместимой pre-migration DB не поддерживается.


## Тарифный каталог #705 — границы schema v14 (и additive v15 / #724)

`rub_price_enabled=0` выключает лишь будущий RUB-канал, не меняет `price_minor` исторических заказов. `stars_price=0` означает отсутствие продажи в Telegram; RUB-цена не преобразуется в XTR. `visibility` принимает `all`, `groups` или `admin_only`. `include_group_ids` / `exclude_group_ids` — JSON-массивы идентификаторов **локальных** User Groups; `groups` без include deny-by-default, exclude имеет приоритет и при ошибке SQLite/неизвестной группе пользовательская продажа закрывается. Исторические plans получают `all` и сохранённый RUB-признак; существующие `EUR` не переоцениваются и не конвертируются.

Журнал ручных выдач фиксирует идентичность admin actor, план, предыдущий план, временные поля и bounded result_code, но **не** создаёт ни Orders, ни Payments. Успех подтверждается отдельным 3x-ui read-back; `in_flight/unknown` требуют ручного review и блокируют automatic replay после restart. Повтор уже `active` — идемпотентен.

Технический профиль (`duration_days=0`, `traffic_gb=0`, отсутствие двух цен, `rub_price_enabled=0`, `visibility=admin_only`) допускается только для ручной административной выдачи. IP и HWID независимо задаются в диапазоне `0…1000`; для старых тарифов `hwid_limit=NULL` означает сохранить индивидуальный HWID (не равен 0). Ненулевой трафик бессрочных тарифов запрещён до отдельного решения о политике сброса квоты. Миграция не создаёт ни назначений, ни Orders, ни entitlements, ни PSP checkout. Любое применение schema на production требует отдельного разрешённого release/deployment и pre-migration backup. Rollback после применения v14 через downgrade без восстановления совместимой DB не поддерживается.

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

## Исторический release-prep и ручные переходы

Release-prep `rc.16.1` и план `rc.16.2` не вводили новые миграции и не подтверждали production acceptance. Подробный исторический scope и незавершённые тогда проверки доступны в неизменяемой версии документа выше. Для текущих операций применимы нормативные правила `manual_entitlements`, read-back, `unknown/no-replay` и запрещённого downgrade.
