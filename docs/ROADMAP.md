# Product Roadmap

Этот документ фиксирует предварительное направление развития проекта после `v4.13.2`.

Roadmap задаёт границы крупных продуктовых этапов, но не заменяет release-specific scope: перед каждым релизом конкретный набор изменений всё равно фиксируется отдельным feature/fix/release PR.

## Статусы roadmap

Roadmap ведётся как living document. Для пунктов, по которым уже началась реализация, используется явный статус:

- `⬜ Запланировано` — работа ещё не завершена в `main`;
- `🟡 Реализовано в main` — код/документация уже слиты, но соответствующий release ещё не опубликован;
- `🟠 Опубликовано; acceptance отложен` — release уже опубликован/развёрнут, но отдельный production acceptance или recovery drill сознательно перенесён и остаётся обязательным до финальной заморозки v4.x;
- `✅ Выполнено в vX.Y.Z` — изменение опубликовано в указанном релизе и обязательный acceptance scope закрыт.

Статус меняется только по фактическому состоянию репозитория. Merge в `main` не считается опубликованным релизом, а публикация release без завершённого acceptance scope не должна автоматически закрывать пункт.

## Граница v4.x / v5.x

### Линейка v4.x — финализация Admin Control Plane

До перехода на `v5.0.0` основной приоритет — довести административную часть `/admin` до финального production-состояния.

В v4.x входят:

- завершение и полировка административных workflows;
- infrastructure/node/fleet operations;
- monitoring, audit, jobs, backups и disaster recovery;
- admin roles и privilege boundaries;
- provisioning/reconcile primitives;
- Plans / Server Groups / Payments / Promo Codes как административные и backend-сущности;
- operational hardening, migration/recovery tooling и regression coverage;
- исправления UX/навигации `/admin`;
- backend prerequisites, необходимые будущему Client Portal, если они не открывают публичный customer flow.

### Зафиксированные цели финализации v4.x

#### RBAC / Roles & Privileges catalog

**Статус: ✅ Выполнено в `v4.14.0`.**

Текущие роли `Read-only`, `Support`, `Administrator` и `Owner` сохраняются как фиксированные security boundaries.

До завершения v4.x требуется единый централизованный каталог privileges, который:

- перечисляет административные разделы и операции в виде стабильных permission identifiers;
- однозначно связывает каждую permission с минимально допустимой ролью;
- используется authorization layer как источник правил доступа, а не только как справочная документация;
- отображается в `/admin → Administrators → Roles & Privileges` в читаемом виде;
- обновляется вместе с добавлением новых admin sections/actions;
- покрывается regression/CI-проверками, чтобы новая административная mutation не могла появиться без явного privilege rule.

Первый вариант не требует custom roles или индивидуальной выдачи произвольных permission отдельным администраторам. Четыре существующие роли остаются каноническими; цель — сделать их возможности полными, прозрачными и поддерживаемыми по мере развития `/admin`.

#### Extended direct-node backup

**Статус: ✅ Выполнено в `v4.14.1`.**

Реализация впервые опубликована в `v4.14.0`, а production acceptance полностью закрыт в `v4.14.1` после исправления multi-chunk чтения Host Control nginx snapshot и upgrade restart path.

Direct-node backup должен быть расширен от одной 3x-ui database до node snapshot, максимально полезного для operational recovery без превращения control plane в arbitrary remote file access.

Минимальный целевой состав snapshot:

~~~text
nodes/<node>/
├─ x-ui.db
├─ nginx/
├─ node.json
└─ manifest.json
~~~

Требования:

- `x-ui.db` по-прежнему получается через существующий direct admin backup path;
- nginx configuration собирается только из заранее разрешённого локального source на конкретной node;
- Telegram/Master не может передавать произвольный filesystem path;
- существующий Host Control Agent не расширяется до general-purpose file API;
- manifest фиксирует stable node identity, timestamp, версии/компоненты при доступности, список включённых файлов и checksums;
- node snapshot включается в обычный Full Backup Master и наследует его правила хранения/секретности;
- отсутствие nginx source должно быть явно отражено как missing/degraded component, а не молча считаться полным backup.

В scope v4.x достаточно надёжно сохранять nginx configuration вместе с node DB. Автоматический remote nginx restore и полный bare-metal disaster recovery remote node не являются обязательными целями этой линии. При необходимости nginx bundle должен оставаться доступным для контролируемого ручного восстановления с обязательной локальной валидацией конфигурации перед reload.

#### Safe Bot Self-Update

**Статус: ✅ Выполнено в `v4.19.1`.**

Restricted Deploy Agent, Owner-only UI, persistent `operation_id` journal, no-replay startup recovery, published-tag validation, explicit downgrade confirmation и host-side install tooling опубликованы и прошли production acceptance в `v4.19.1`. Controlled same-release deployment `v4.19.1 → v4.19.1` завершился `success`; новый bot process восстановил итог через Deploy Agent journal без повторного mutation (`mutation_not_retried=true`), а post-deploy checks подтвердили exact tag/SHA, `RestartCount=0`, Health/DB/3x-ui connectivity `ok`.

До завершения v4.x допускается добавить обновление production bot из `/admin`, но только через отдельный ограниченный deploy control plane. Сам Telegram bot container не получает Docker socket, host shell, GitHub deploy key или произвольный host filesystem access.

Целевая схема:

~~~text
Telegram /admin
        ↓
restricted local Deploy Agent
        ↓
existing scripts/deploy-release.sh
        ↓
Git / Docker Compose / production bot service
~~~

Security boundary:

- update доступен только `Owner`;
- Deploy Agent работает вне bot container и переживает recreate самого bot service;
- agent принимает только ограниченную операцию deployment опубликованного release tag вида `vX.Y.Z`;
- API не принимает shell command, argv, executable, script path, arbitrary git ref/SHA, Docker arguments, filesystem path или environment overrides;
- bot container не получает `/var/run/docker.sock` и не хранит GitHub deploy key;
- deploy repository, service, checkout path и credential paths задаются локально на host и не управляются через Telegram;
- существующий `scripts/deploy-release.sh` остаётся source of truth для release validation, preflight, backup, deploy и post-checks;
- автоматический deploy при появлении нового release запрещён; разрешены только обнаружение/уведомление и явное подтверждение Owner;
- downgrade требует отдельного усиленного подтверждения и никогда не выполняется автоматически;
- ручной VPS deploy через `scripts/deploy-release.sh vX.Y.Z` сохраняется как break-glass fallback.

Deployment operation должна быть persistent и иметь `operation_id`, потому что во время обновления текущий bot container будет уничтожен и создан заново. Минимальные состояния:

~~~text
queued
preflight
backup
building
deploying
verifying
success / failed / unknown
~~~

После старта нового bot container UI должен уметь получить итог операции у Deploy Agent и зафиксировать результат в audit/job history. Потерянный ответ не должен приводить к автоматическому повтору deployment mutation.

Предварительный UI:

~~~text
/admin → Система → Обновления бота
├─ Current version
├─ Latest published release
├─ Release notes
├─ Preflight
├─ Update to <version>
└─ Update history
~~~

Эта функция не должна превращать Telegram bot или Deploy Agent в remote server/general-purpose host administration interface. Любое будущее расширение за пределы строго фиксированного deployment workflow требует отдельного threat-model review.

### Аудит перед заморозкой v4.x

По итогам полного аудита репозитория перед переходом к Client Portal линейка v4.x получает дополнительные критерии завершённости. Цель этого блока — закрыть не новые customer-facing функции, а накопившиеся operational, recovery, migration, regression и maintainability риски.

Уже зафиксированные выше цели `RBAC / Roles & Privileges catalog`, `Extended direct-node backup` и `Safe Bot Self-Update` остаются частью обязательной финализации v4.x и не переносятся молча в v5.x.

#### Обязательные условия перехода к v5.0.0

##### Host Control startup recovery

**Статус: ✅ Выполнено в `v4.13.2`.**

В коде уже существует read-only recovery незавершённых Host Control jobs через `recover_control_jobs()`, но startup path бота должен явно вызывать этот recovery до начала обычной обработки Telegram updates.

Требования:

- recovery запускается после инициализации БД и до начала polling;
- обрабатываются только незавершённые Host Control jobs, для которых уже существует persistent `operation_id`;
- итог восстанавливается только через read-only lookup operation journal/status;
- state-changing Host Control request при recovery никогда не отправляется повторно;
- если результат невозможно доказать, job завершается как `unknown`, а не как предполагаемый success;
- startup recovery покрывается regression-тестом, который одновременно проверяет сам вызов recovery и отсутствие mutation replay.

Общий stale-job cleanup не считается заменой этого механизма: специализированный recovery должен использовать уже сохранённую identity операции и максимально точно восстановить известный итог.

##### Версионные миграции SQLite

**Статус: ✅ Выполнено в `v4.15.0`.**

Versioned migration framework опубликован в `v4.15.0`: `schema_migrations` хранит journal/version, migrations выполняются только вперёд, dangerous steps требуют проверенную recovery copy, а `running`/`failed`/newer schema блокируют startup fail-closed. Production deployment и targeted smoke подтверждены: baseline `v1 baseline_v4_14_2` применился ровно один раз, `PRAGMA quick_check` вернул `ok`, повторный restart не replay'нул migration, а post-restart health/DB/3x-ui checks остались зелёными.

Минимальный контракт:

- в БД хранится текущая schema version / migration journal;
- миграции имеют фиксированный порядок и выполняются только вперёд;
- изменение существующих таблиц/данных выполняется отдельными явно именованными migration steps;
- каждая migration либо завершается полностью, либо оставляет БД в однозначно диагностируемом состоянии;
- опасная migration не выполняется без пригодной recovery copy;
- неизвестная более новая schema version и failed migration блокируют обычный startup fail-closed;
- CI проверяет upgrade как минимум с репрезентативной старой схемы до текущей;
- migration framework не должен зависеть от Telegram UI.

Для простых additive изменений допустимы идемпотентные операции, но версия схемы остаётся источником истины о том, какие преобразования уже применены.

##### Расширение regression coverage

**Статус: ✅ Выполнено в `v4.16.0`.**

Целевой regression pack опубликован в `v4.16.0`: business/catalog transitions, user lifecycle mutation ordering, provisioning idempotency/partial failure, subscription proxy compatibility/error paths, inbound mutation failure paths, disaster recovery и negative RBAC boundaries. Production deployment и targeted smoke подтверждены: release commit развернут штатно, health/DB/3x-ui checks зелёные, а runtime privilege mapping соответствует contract — `safe=support`, `strict=admin`.

Наиболее опасные operational части проекта уже имеют сильные тесты, прежде всего Host Control и update engine. Перед v5.0.0 требуется выровнять regression coverage для административного и business/backend слоя.

Приоритетные области:

- `business_admin.py` — payment/status transitions, promo/application rules и административные mutations;
- `catalog_admin.py` — Plans / Server Groups, ограничения и связи;
- `advanced_users.py` — user lifecycle, enable/disable/extend/delete и role boundaries;
- `inbound_admin.py` — inbound mutations, validation и failure paths;
- `provisioning.py` — reconcile, повторный вызов, partial failure и сохранение subscription identity;
- `subscription_proxy.py` — Base64/plain subscriptions, selective `vpn://` conversion, upstream errors и invalid `sub_id`;
- disaster recovery / restore — malformed/incomplete backup, integrity checks, interrupted/failed recovery и Owner-only boundaries;
- отрицательные authorization tests для sensitive callbacks, чтобы новая mutation не могла случайно стать доступна более слабой роли.

Roadmap не задаёт искусственный глобальный процент coverage. Критерий завершённости — наличие regression tests на security boundaries, state transitions, idempotency/retry semantics и recovery paths перечисленных модулей.

##### Off-site backup

**Статус: 🟠 Опубликовано в `v4.18.0` и развернуто; production off-site acceptance отложен.**

Encrypted off-site backup опубликован и развернут в production как `v4.18.0` (release commit `1cc730c5929ba8b2fe1152a0db1ade4b1aaa21f9`). Базовый runtime acceptance пройден: exact tag/SHA, container, app version, health, DB и 3x-ui connectivity подтверждены. Full Backup использует checksummed manifest schema 2, S3-compatible transport шифрует canonical archive client-side через AES-256-GCM, local и off-site outcomes записываются раздельно (`backup.daily`/`backup.manual` и `backup.offsite`), после upload обязателен remote download/decrypt/SHA/deep-validation round trip, retention ограничен fixed prefix, а host-side recovery CLI скачивает и проверяет latest external copy перед существующим bootstrap restore flow. Feature выключена по умолчанию и не открывает Telegram доступ к bucket/object key/credentials/filesystem path.

**Отложенный acceptance:** после завершения остальных релизов финализации v4.x, но до окончательного v4 freeze / перехода к v5, нужно вернуться к `v4.18.0` и провести отдельный production drill на реально внешнем S3-compatible target: настроить dedicated credentials и recovery encryption key локально, создать manual Full Backup, подтвердить отдельный `backup.offsite` success/допустимый partial, проверить remote round-trip validation и выполнить host-side recovery fetch/deep validation latest external copy. Секреты bucket credentials/encryption key не должны передаваться через Telegram/chat или Git.

Локальный Full Backup остаётся необходимым, но сам по себе не закрывает сценарий полной потери Master VPS. До v5.0.0 должен появиться поддерживаемый способ иметь хотя бы одну актуальную recovery copy вне Master host.

Контракт должен быть provider-neutral:

- off-site target физически/логически не зависит от filesystem Master VPS;
- передаётся именно проверенный Full Backup с manifest/checksums, а не произвольный набор файлов;
- backup, содержащий `.env`, tokens, database или другие secrets, защищён при передаче и хранении;
- retention и удаление старых копий предсказуемы и документированы;
- ошибка off-site upload не делает локальный backup ложным success: локальный и off-site результаты фиксируются отдельно;
- Telegram не используется как единственное off-site хранилище полного архива;
- существует документированный restore flow с нового VPS и периодическая проверка, что выбранная внешняя копия действительно читается и проходит integrity validation.

Конкретная реализация может использовать S3-compatible object storage, отдельный backup host или другой ограниченный transport, но Telegram/Admin UI не должен получать arbitrary remote filesystem access.

##### 3x-ui API compatibility / OpenAPI contract gate

**Статус: ✅ Выполнено в `v4.17.0`.**

Compatibility gate опубликован в `v4.17.0`: поддерживаемая версия 3x-ui зафиксирована как `v3.8.5`, OpenAPI vendored из immutable upstream tag и привязан к exact Git blob SHA, а CI проверяет 51 реально используемый panel API endpoint на route/method, Bearer auth, request media type/mandatory fields, response envelope и parity с `xui.py`/`version_api.py`. Unknown upstream schema автоматически не принимается; единственное documented response exception — binary `GET /panel/api/server/getDb`. Production deployment подтверждён на release commit `cc47384acf311a810b3450250c6c389ba0acea10`: container/health/DB/3x-ui checks зелёные, host-side checker вернул `3x-ui OpenAPI contract OK` для `v3.8.5`, 51 endpoints и pinned blob `d1f9b499e43d4370d68fdf9ca6045e1d967b42ad`.

Современный 3x-ui публикует OpenAPI-схему, поэтому совместимость с upstream API до v5 должна проверяться машинно, а не только ручными smoke tests.

Минимальный контракт:

- поддерживаемая версия 3x-ui и используемая OpenAPI schema фиксируются явно;
- CI проверяет наличие и сигнатуры критических endpoints, на которые опираются `XUIClient`, Версии и обновления, provisioning, node operations и subscription proxy;
- удаление/переименование endpoint, изменение HTTP method или несовместимое изменение обязательных request/response fields должно падать в CI до merge;
- проверка должна быть fail-closed и не маскировать несовместимость fallback-логикой;
- generated client не является обязательным условием первого этапа: допустимо начать с contract tests поверх текущего `xui.py`;
- в дальнейшем допускается генерация DTO/models из OpenAPI, если это уменьшает ручной drift без ухудшения auditability;
- runtime не должен автоматически переключаться на неизвестную API-схему только потому, что endpoint отвечает.

Этот gate нужен именно как защита от тихой несовместимости после обновления 3x-ui и не заменяет integration tests против реального поддерживаемого release.

##### Gate перед открытием Client Portal

Переход к `v5.0.0` предполагает закрытие следующего набора v4.x работ:

1. `RBAC / Roles & Privileges catalog` — ✅ выполнено в `v4.14.0`;
2. `Extended direct-node backup` — ✅ выполнено в `v4.14.1`;
3. `Safe Bot Self-Update` — ✅ выполнено в `v4.19.1`; production same-release/recovery acceptance закрыт (`mutation_not_retried=true`, exact tag/SHA, Health/DB/3x-ui connectivity `ok`);
4. Host Control startup recovery — ✅ выполнено в `v4.13.2`;
5. versioned SQLite migrations — ✅ выполнено в `v4.15.0`;
6. расширенный regression coverage критических admin/business/recovery путей — ✅ выполнено в `v4.16.0`;
7. off-site backup и проверяемый restore path — 🟠 опубликовано в `v4.18.0`, production drill отложен до финального v4 freeze;
8. 3x-ui API compatibility / OpenAPI contract gate — ✅ выполнено в `v4.17.0`.

Отдельный release-specific PR может уточнить реализацию каждого пункта, но перенос любого из них за границу v5 должен быть явным решением с обновлением этого roadmap, а не неявным следствием начала Client Portal.

#### Желательно закрыть до финальной заморозки v4.x

Эти работы не меняют security boundary сами по себе, но уменьшают архитектурный долг перед существенным ростом v5.x.

Зафиксированный порядок финального закрытия v4.x:

1. сначала выполнить cleanup/freeze-подготовку из этого раздела небольшими regression-safe PR;
2. после завершения cleanup вернуться к отложенному production drill для off-site backup;
3. только после успешного off-site drill выполнить финальную заморозку v4.x и открыть работу над `v5.0.0`.

Таким образом off-site acceptance остаётся обязательным pre-v5 gate, но выполняется после архитектурной и UX-подготовки Admin Control Plane, непосредственно перед финальным freeze.

##### Декомпозиция bot.py

Статус: 🟡 Реализовано в main.

`bot.py` теперь является минимальным executable entrypoint. Startup/background orchestration вынесена в `app_runtime.py`, client-facing flow — в `client_access.py`, admin shell/navigation — в `admin_shell.py`, а domain handlers распределены по тематическим routers.

Зафиксированное состояние:

- `bot.py` — минимальный executable shim, запускающий `app_runtime.main()`;
- `app_runtime.py` владеет composition/startup, recovery order, background tasks и lifecycle Telegram polling;
- domain/admin handlers живут в тематических routers, а client-facing flow имеет отдельный `client_access_router`;
- orchestration, которая нужна и Telegram UI, и background/recovery paths, живёт в services, а не внутри callback handlers;
- существующие callback identifiers и внешнее поведение не менялись только ради рефакторинга;
- границы закреплены regression/source-inspection tests, включая startup recovery order и single route ownership.

Эта граница освобождает entrypoint от domain UI и позволяет развивать будущий Client Portal отдельно от `/admin`.

##### Синхронизация README с текущим состоянием

Статус: 🟡 Реализовано в main.

README теперь является текущей картой проекта и точкой входа в канонические runbook'и, а не второй копией release history.

Зафиксированное состояние:

- current install/update/recovery paths ведут в `docs/ADMIN_SETUP.md`, `docs/RELEASES.md`, `docs/VPS_RECOVERY.md` и профильные runbook'и;
- release-by-release история живёт в `CHANGELOG.md` и GitHub Releases;
- version-specific deploy команды старых релизов не публикуются в README как текущая процедура;
- актуальный Subscription Compatibility Proxy contract сохранён, потому что на него ссылается `.env.example`;
- README фиксирует текущие module boundaries после декомпозиции `bot.py`;
- regression test запрещает возвращать в README release headings и hard-coded старые `deploy-release.sh v4.*` инструкции.

##### Консистентная русская локализация Telegram UI

Статус: 🟡 Реализовано в main.

Системный проход выполнен для client access, Admin Shell, Nodes, Monitoring/Logs/Alerts, Backups/DR, Host Control/Fleet, Versions & Updates/Bot Updates и domain UI Users/Catalog/Business/Inbounds.

Зафиксированный контракт:

- кнопки, заголовки, пояснения, предупреждения и пользовательские статусы по умолчанию оформляются на русском языке;
- технические названия сохраняются там, где перевод ухудшает точность: `3x-ui`, `Xray`, `Reality`, `Host Control`, `Deploy Agent`, `Inbound`, `fingerprint`, protocol names, API/TLS/URL/UUID и точные identifiers;
- фиксированные RBAC role names `Read-only`, `Support`, `Administrator`, `Owner` остаются security-boundary identifiers;
- typed confirmation phrases `STOP`, `RESTORE ...`, `UNLOCK ...`, `DOWNGRADE ...` не переводятся и не меняются;
- callback identifiers, API fields, service names, audit/job keys и persisted machine states не менялись ради локализации;
- для machine states используются отдельные русские display mappings;
- `tests/test_ui_localization.py` закрепляет основные labels и запрещает возврат прежнего смешанного UI;
- постоянный словарь и исключения зафиксированы в `docs/UI_STYLE.md`.

Repo-wide source audit после domain-прохода не выявил обычных английских display labels вне документированных технических исключений.

##### Аудит emoji-префиксов в информационных текстах Telegram UI

Статус: 🟡 Реализовано в main.

Для inline-кнопок emoji/navigation prefix уже является постоянным UI-контрактом. Repo-wide проход выровнял семантические префиксы в информационных сообщениях без механического добавления emoji на каждую строку.

Целевой принцип — не добавлять emoji механически на каждую строку, а использовать их как стабильные визуальные маркеры состояния и типа метрики.

Минимальный контракт:

- одинаковые поля на Master и direct-node экранах используют одинаковые emoji и, где это возможно, одинаковые display labels;
- для общих resource/status полей базовым ориентиром является уже используемый Master-формат: `🧮 CPU`, `🧠 RAM`, `💽 Диск`, `⏱ Время работы`, `🌐 Inbound'ы`, `👥 Пользователи/клиенты`, `💾 Резервная копия`;
- health/state строки сохраняют семантические status icons: `🟢` healthy/online/enabled/running, `🟡` warning/degraded/pending и `🔴` failed/offline/stopped, если соответствующее состояние действительно известно;
- для node-specific operational полей закреплены `🔗 Адрес`, `🔐 Проверка TLS`, `🧭 Исходящий маршрут`, `📶 Задержка API`, `📊 Сеть`, `🕒 Последний сигнал`;
- чисто техническая строка без отдельного status/type смысла может оставаться без emoji, например `3x-ui: 3.8.5`; цель — визуальная консистентность, а не декоративное заполнение каждой строки;
- внутри одного смыслового блока не должно быть случайной смеси маркированных и немаркированных однотипных метрик без UX-причины;
- аудит охватывает как минимум Master status, Nodes list/detail, Monitoring, Backups, Версии и обновления, Jobs/Alerts и другие read-only operational summaries;
- изменение display text не меняет callback/API identifiers и сопровождается обновлением regression tests там, где exact labels являются частью проверяемого UI-контракта.

Постоянные правила для новых экранов и последующих PR зафиксированы в `docs/UI_STYLE.md`; regression tests защищают канонические префиксы для основных operational summaries.

##### Аудит информационной архитектуры и навигации

Перед заморозкой v4.x следует отдельно пройти всю `/admin` навигацию как пользовательский сценарий, а не только как набор работающих callbacks.

Проверяются:

- логичность top-level группировки `Обзор / Пользователи / Подписки / Платежи / Тарифы / Промокоды / Инфраструктура / Мониторинг / Система` после локализации;
- отсутствие функционально дублирующих входов и неожиданных переходов между разделами;
- последовательные Back/Refresh/Cancel/Confirm flows;
- возврат из FSM-форм в правильный parent screen;
- расположение destructive operations отдельно от обычной навигации;
- соответствие кнопки возврата фактическому родительскому разделу;
- отсутствие dead-end screens, циклов и callback routes, которые визуально ведут не туда, куда ожидает оператор;
- сохранение независимой границы `/admin` перед добавлением `/start` Client Portal.

Изменения структуры выполняются небольшими regression-safe PR и не должны одновременно переписывать domain logic без необходимости.

##### Редактура пользовательских текстов и public-repository readiness

Отдельным проходом нужно проверить тексты Telegram UI и operator-facing documentation на логическую ясность, стилистическую последовательность и отсутствие случайной привязки к текущему private deployment.

Критерии:

- сообщение понятно без знания истории разработки;
- формулировка точно различает `failed`, `unknown`, `offline`, `maintenance`, `disabled` и другие разные состояния;
- тексты не содержат частные hostnames, IP, Telegram IDs, имена операторов/клиентов или временные инфраструктурные детали;
- примеры используют нейтральные placeholders;
- предупреждения и confirmation screens ясно описывают последствие операции;
- нет рекламных или абсолютных утверждений о безопасности/надёжности там, где это нельзя гарантировать;
- README и docs используют актуальные названия UI и не описывают устаревшую навигацию как текущую.

Эта работа рассматривается как часть подготовки проекта к будущему публичному репозиторию, а не как изменение business logic.
Крупные публичные customer-facing workflows не должны размывать scope v4.x. `/admin` остаётся Control Plane.

### v5.0.0 — Client Portal

`v5.0.0` открывает следующий продуктовый этап: `/start` становится основным пользовательским входом для клиентов.

Архитектурная граница:

~~~text
/start
└─ Client Portal

/admin
└─ Admin Control Plane
~~~

Client Portal и Admin Control Plane живут в одном Telegram-боте и одном репозитории, но имеют независимые navigation/authorization boundaries.

`/admin` никогда не становится публичным из-за открытия `/start`.

## Предварительное главное меню v5.0.0

~~~text
👤 Профиль          🌐 Моя подписка
💳 Купить / продлить   📊 Трафик
📱 Устройства       🆘 Помощь
~~~

Это базовый набор разделов. Новые top-level кнопки добавляются только если действие нельзя естественно разместить внутри одного из этих разделов.

## 👤 Профиль

Назначение: краткий account/entitlement summary клиента.

Предварительные подразделы и данные:

- Telegram ID / внутренний customer identity;
- статус: active / expired / suspended / provisioning;
- текущий Plan;
- дата окончания;
- состояние автопродления, когда оно появится;
- назначенная Server Group или пользовательское понятное описание региона/группы;
- настройки уведомлений;
- язык интерфейса, если будет поддерживаться несколько языков.

Профиль не должен показывать infrastructure secrets, внутренние node credentials или административные identifiers, которые не нужны клиенту.

## 🌐 Моя подписка

Главный рабочий экран действующего клиента.

Предварительно показывает:

- статус подписки;
- Plan;
- срок действия;
- число доступных серверов/локаций;
- subscription URL;
- состояние provisioning/reconcile.

Контекстные действия:

- `📋 Скопировать ссылку`;
- `📱 Подключить устройство`;
- `🔄 Синхронизировать подписку`;
- `💳 Продлить`.

### 🔄 Синхронизировать подписку

Это не отдельный top-level раздел.

Смысл операции:

1. проверить актуальный entitlement клиента;
2. вычислить ожидаемые ресурсы через `Plan → Server Group → Nodes → Inbounds → User`;
3. выполнить безопасный provisioning/reconcile;
4. проверить post-condition;
5. сохранить существующий subscription identity, если нет отдельной причины его менять.

Кнопка не должна по умолчанию генерировать новый `sub_id` или новую ссылку. Subscription URL считается секретом клиента.

## 💳 Купить / продлить

Единый commerce flow для нового и существующего клиента.

Предварительные подразделы:

- каталог доступных Plans;
- период/вариант тарифа;
- итог заказа;
- `🎟 Промокод`;
- выбор доступного способа оплаты;
- payment/order status;
- результат activation/extension.

Backend lifecycle:

~~~text
Plan selection
  ↓
Order
  ↓
Promo / pricing
  ↓
Payment
  ↓
Confirmed payment event
  ↓
Entitlement
  ↓
Provisioning / reconcile
  ↓
Subscription available
~~~

### Order / Payment / Entitlement state machine

Commerce flow должен иметь явные persistent states, а не выводить состояние покупки из Telegram message history или набора loosely-related flags.

Минимальная модель должна различать как минимум:

~~~text
order:
created
awaiting_payment
paid
cancelled
expired

payment:
created
pending
confirmed
failed
refunded
unknown

entitlement:
pending
provisioning
active
suspended
expired
failed
~~~

Допустимые переходы фиксируются backend-ом. Telegram UI только запрашивает текущее состояние и инициирует разрешённые команды.

Критические правила:

- подтверждение оплаты сначала надёжно записывается как provider event/payment state и только потом влияет на entitlement;
- `confirmed payment → entitlement/provisioning` выполняется идемпотентно;
- временный provisioning failure не откатывает факт успешной оплаты;
- повторный запуск reconcile не должен создавать второй entitlement или менять subscription identity без отдельной причины;
- `unknown` используется там, где внешний provider мог принять mutation, но итог невозможно доказать;
- ручная коррекция финансовых состояний доступна только через audit-friendly административный workflow.

### Payment provider webhook journal

Для каждого внешнего payment event хранится immutable/minimally-mutable journal record.

Минимальные данные:

- provider;
- provider event/payment identifier;
- received timestamp;
- signature/authentication result;
- normalized event type;
- raw payload hash и безопасный диагностический metadata subset;
- processing status;
- связанный order/payment;
- applied timestamp/result.

Требования:

- уникальность provider event ID защищает от повторного применения одного события;
- повторный webhook после успешной обработки возвращает корректный idempotent результат, но не продлевает entitlement повторно;
- невалидная подпись никогда не изменяет финансовое состояние;
- webhook handler не доверяет Telegram callback state;
- ошибка после записи события, но до provisioning, должна быть recoverable через journal/reconcile;
- секреты provider-а и полный sensitive payload не выводятся в audit/UI/logs.

Ключевые требования:

- payment events идемпотентны;
- повторный webhook не должен повторно продлевать entitlement;
- успешная оплата и временная ошибка provisioning не должны приводить к потере покупки;
- failed provisioning попадает в recoverable job/reconcile flow;
- Telegram UI не является источником истины для payment status.

## 📊 Трафик

Назначение: понятная клиенту статистика использования.

Базовый v5.0.0 view:

- использовано;
- лимит;
- осталось;
- дата/период сброса или окончания entitlement;
- состояние unlimited, если лимит отсутствует.

Возможные последующие подразделы:

- сегодня;
- 7 дней;
- 30 дней.

Графики не являются обязательным условием первого Client Portal.

## 📱 Устройства

На первом этапе раздел должен различать реальные зарегистрированные устройства и наблюдаемые network connections.

Если backend знает только IP/online connections, UI не должен выдавать их за достоверный список физических устройств.

Базовый вариант:

- активные подключения;
- текущий IP/device limit;
- наблюдаемые IP/сессии, если данные надёжно доступны;
- `📱 Как подключить новое устройство`.

Будущее расширение при появлении device registration:

- пользовательское имя устройства;
- platform/device type;
- last seen;
- revoke/unlink;
- device-specific onboarding/deep-link.

## Client onboarding / connection UX

Первый Client Portal должен уменьшать зависимость от ручной поддержки при подключении устройства.

Базовый UX:

- platform selection: iOS / Android / Windows / macOS / Linux;
- QR для subscription URL там, где это уместно;
- deep-link / import-link только если формат клиента стабилен и безопасен;
- короткие инструкции для поддерживаемых клиентов без привязки backend logic к конкретному приложению;
- read-only диагностика: entitlement active, subscription reachable, provisioning/reconcile state, известные ограничения;
- rotation/reissue credentials выполняется отдельной явной операцией и не маскируется под обычный refresh.

Roadmap не требует device registration в первой версии. Наблюдаемый IP/session не должен называться физическим устройством без надёжной device identity.

## 🆘 Помощь

Подразделы:

- `📱 Как подключиться`;
- `❓ Частые вопросы`;
- `🛠 Проверить подписку`;
- `💬 Связаться с поддержкой`.

Раздел должен помогать решить типовые проблемы без доступа пользователя к административным controls.

`🛠 Проверить подписку` — read-only diagnostics либо безопасная ссылка на reconcile flow; она не должна выполнять опасные infrastructure mutations.

## Authorization boundary

Текущий проект ограничивает пользовательский flow через allowlist. Для публичного Client Portal это должно быть пересмотрено отдельно в v5.x.

Целевое правило:

- `/start` и customer callbacks доступны обычному Telegram-пользователю согласно product/onboarding policy;
- пользователь может читать и изменять только собственный account/subscription context;
- `/admin` и все `admin:*` callbacks продолжают требовать существующие admin roles;
- customer identity никогда не даёт implicit admin access;
- ownership проверяется backend-ом, а не только callback payload.

Открытие публичного `/start` выполняется только после готовности customer authorization, entitlement/payment lifecycle и abuse/rate-limit policy.

## Архитектурный принцип

Client Portal не должен напрямую реализовывать infrastructure logic.

Предпочтительная схема:

~~~text
Telegram Client UI
        ↓
Order / Entitlement / Subscription services
        ↓
ProvisioningEngine / reconcile
        ↓
Plan → Server Group → Nodes → Inbounds
        ↓
3x-ui
~~~

Административный UI использует те же backend primitives для диагностики и управления, но customer flow не вызывает административные callbacks.

## Observability и внешние интеграции после стабилизации v5

После стабилизации customer/domain model допускается отдельный этап внешних интеграций:

- read-only metrics endpoint для Prometheus-compatible collection;
- scoped service/API tokens;
- signed outgoing webhooks для событий subscription/payment/provisioning;
- documented API для внешних систем.

Эти интерфейсы не должны становиться источником обхода существующих RBAC, ownership и mutation safety rules.

### Явно вне архитектуры control plane

Даже при расширении observability/automation следующие возможности не считаются целями проекта:

- arbitrary remote shell/terminal;
- generic command runner;
- произвольный script execution из Telegram;
- передача arbitrary filesystem path/unit name/Docker arguments;
- автоматический retry state-changing host/deploy/update operations после uncertain outcome.

Если когда-либо понадобится отдельный automation executor шире текущих restricted agents, это требует отдельного threat-model review и нового privilege domain, а не расширения существующего Host Control Agent.

## Что предварительно не является top-level разделом v5.0.0

- `🔄 Обновить подписку` — находится внутри `🌐 Моя подписка` как `🔄 Синхронизировать подписку`;
- `🎟 Промокод` — часть `💳 Купить / продлить`;
- `📱 Подключить устройство` — действие из `🌐 Моя подписка` и/или `📱 Устройства`;
- payment history — может появиться внутри Profile/Purchase flow позже, если будет полезен клиенту;
- infrastructure/server controls — никогда не относятся к Client Portal.

## Definition of direction

До `v5.0.0`:

> завершаем Admin Control Plane и backend primitives в линейке v4.x.

Начиная с `v5.0.0`:

> `/start` становится Client Portal для покупки, получения, продления и самостоятельного обслуживания подписки; `/admin` остаётся отдельным защищённым Control Plane.
