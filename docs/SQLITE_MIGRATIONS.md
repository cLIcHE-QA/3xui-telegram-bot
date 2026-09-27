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

Для `v4.23.0` текущая bot schema version — **3**:

1. `v1 baseline_v4_14_2` — исходная каноническая схема v4.14.2;
2. `v2 user_display_name_v4_21_0` — additive `display_name TEXT NOT NULL DEFAULT ''` в `user_profiles`;
3. `v3 user_audience_groups_v4_22_0` — additive таблицы `user_groups` / `user_group_members` и индекс `idx_user_group_members_user`.

Migration v2 и v3 имеют `requires_backup=False`: обе additive, не переписывают существующие пользовательские записи и проверяют postcondition соответствующей версии schema внутри migration transaction до записи `success`. Для v3 membership хранится по стабильному `telegram_id`; сама migration не назначает пользователей в группы.

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
