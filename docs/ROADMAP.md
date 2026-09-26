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
9. финальный Admin UI consistency patch после production acceptance `v4.20.4` — ✅ выполнено и принято в production в `v4.20.5`.
10. UI-04: симметрия Master/direct-node health summary на экране `Мониторинг → Состояние системы` — ✅ выполнено и принято в production в `v4.20.6`.
11. единая operator-facing терминология `Inbound` / `Inbounds` без гибридных форм `Inbounds` / `Inbounds` — ⬜ запланировано на `v4.20.7`.
12. редактируемое display name пользователя без изменения 3x-ui machine identity — ⬜ запланировано на `v4.21.0`.
13. независимые User/Audience Groups для будущей сегментации Client Portal — ⬜ запланировано на `v4.22.0`.
14. Cheburcheck integration как отдельный read-only diagnostics service/tool — ⬜ запланировано на `v4.23.0`.
15. PackBot-compatible website monitoring и diagnostics, нативно встроенные в текущую архитектуру — ⬜ запланировано на `v4.24.0`.
16. финальный repository/public-release audit после feature freeze и до последнего v4.x release — ⬜ запланировано; переход к `v5.0.0` блокируется до его закрытия.

Отдельный release-specific PR может уточнить реализацию каждого пункта, но перенос любого из них за границу v5 должен быть явным решением с обновлением этого roadmap, а не неявным следствием начала Client Portal.

#### Желательно закрыть до финальной заморозки v4.x

Эти работы не меняют security boundary сами по себе, но уменьшают архитектурный долг перед существенным ростом v5.x.

Зафиксированный порядок финального закрытия v4.x:

1. закрыть и принять в production `v4.20.5` с финальными UI consistency fixes;
2. отдельным patch-релизом `v4.20.6` закрыть UI-04 и выровнять health summary Master/direct nodes без искусственного добавления недоступных метрик;
3. отдельным patch-релизом `v4.20.7` привести operator-facing терминологию к `Inbound` / `Inbounds` без изменения technical identifiers;
4. отдельным релизом `v4.21.0` добавить редактируемое display name пользователя;
5. отдельным релизом `v4.22.0` добавить User/Audience Groups;
6. отдельным релизом `v4.23.0` интегрировать Cheburcheck;
7. отдельным релизом `v4.24.0` интегрировать PackBot-compatible monitoring/diagnostics;
8. после acceptance всех feature-релизов выполнить отложенный production drill encrypted off-site backup/restore;
9. объявить **final v4 feature freeze**: после этой точки новые функции в v4.x не добавляются;
10. после feature freeze провести полный финальный repository/public-release audit по всему продукту;
11. исправления findings выполнять только narrowly-scoped fix PR/patch releases v4.x с обязательным regression/production acceptance; номер последнего v4.x patch заранее не фиксируется;
12. только после закрытия audit gate опубликовать/принять финальный v4.x release и открыть реализацию `v5.0.0`.

Feature freeze здесь означает запрет на новый product scope, а не запрет исправлений. Security/reliability/data-integrity findings, найденные финальным аудитом, должны быть закрыты до финального v4 release.

Off-site acceptance остаётся обязательным pre-v5 gate, но теперь выполняется после завершения запланированных `v4.20.5`–`v4.24.0` релизов и непосредственно перед feature freeze. Финальный аудит выполняется **после** freeze, чтобы проверяемый codebase больше не менялся функционально во время review.

##### Финальный Admin UI consistency patch

**Статус: ✅ Выполнено и принято в production в `v4.20.5`.**

Production smoke `v4.20.4` подтвердил основной Admin UI consolidation, но выявил три остаточные несогласованности presentation/navigation contract. Они должны быть закрыты отдельным небольшим regression-safe patch без изменения SQLite schema, 3x-ui/OpenAPI contract, Host Control/Deploy Agent API или mutation-safety semantics.

Scope `v4.20.5`:

1. **Fleet Health использует общий direct-node formatter.** Экран `Инфраструктура → Операции с нодами → Состояние нод` не должен печатать raw `item['name']`; operator-facing имя проходит через `node_display_name()`, поэтому `Finland` отображается как `🇫🇮 Finland` при текущем presentation fallback.
2. **Список `Ноды` использует один status template для Master и direct nodes.** Master и direct nodes показывают идентичность сущности, status icon и текстовый status label в одном формате; direct-node identity формируется через `node_display_name()`. Пример: `🖥 Master · 🟢 В сети` и `🇫🇮 Finland · 🟢 В сети`.
3. **`Обзор` следует общему top-level navigation contract.** `admin:home` остаётся единственным корневым экраном с `admin_menu()`. `admin:dashboard` становится обычным дочерним экраном с собственной локальной клавиатурой (`🔄 Обновить`, `⬅ Панель администратора`) и не сохраняет корневое меню под содержимым overview.

Regression requirements:

- отдельный тест проверяет конкретную Fleet Health строку и запрещает raw direct-node name на этом экране;
- тест списка `Ноды` проверяет одинаковую грамматику статуса Master/direct nodes, включая online/offline/maintenance/unknown варианты;
- navigation regression проверяет, что `admin_menu()` используется только корневым экраном, а `Обзор` имеет локальную навигацию и явный возврат к `Панели администратора`;
- `docs/UI_STYLE.md` остаётся нормативным источником этих правил для следующих UI PR.

Production acceptance `v4.20.5` закрыт: release развернут в production, и оператор подтвердил успешный targeted smoke по всем трём пунктам — Fleet Health display, симметричный status template списка `Ноды` и локальная навигация `Обзора`. Следующим patch-релизом идёт `v4.20.6` с UI-04, затем последовательность feature-релизов `v4.21.0`–`v4.24.0`; off-site drill и freeze выполняются уже после них.

##### UI-04 — симметрия Master/direct-node health summary

**Статус: ✅ Выполнено и принято в production в `v4.20.6`.**

Экран `Мониторинг → Состояние системы` сейчас показывает для Master и direct nodes разные наборы и разную грамматику одинаковых health-метрик. Часть различий архитектурно оправдана, потому что Master имеет локальные показатели и сервисы, которых нет в агрегированном `NodeInfo`; UI-04 не должен скрывать это различие или добавлять лишние network calls только ради визуальной симметрии.

Целевой контракт:

- для метрик, которые доступны и Master, и direct node, используются одинаковые названия, status grammar и emoji: состояние панели/3x-ui, Xray state + version, CPU, RAM, uptime и Inbounds;
- direct node получает явный текстовый статус (`🟢 В сети`, `🔴 Не в сети`, `🟡 Неизвестно`, `🛠 Обслуживание`), а не только status icon;
- Xray direct node показывается с фактическим state и version, например `🟢 Xray: работает 26.9.9`, если version доступна; unknown/error не маскируются зелёным статусом;
- Master-only данные остаются отдельными и не копируются на ноды без источника: disk usage, локальный Subscription Proxy, публичный nginx/TLS path, bot DB и локальный backup state;
- node-only/aggregate данные сохраняются там, где они полезны: latency, client/online counts, heartbeat/network stats и другие реально доступные поля;
- не добавляются дополнительные direct-node API calls только для заполнения отсутствующих строк; расширение data source требует отдельного решения с timeout/failure semantics;
- display contract формулируется как «одинаково представлять одинаковые данные», а не «показывать одинаковое количество строк»;
- regression tests фиксируют online/offline/unknown/maintenance status, Xray running/stopped/unknown, наличие version при доступности и отсутствие ложных Master-only метрик у direct nodes;
- SQLite schema, callback identity, 3x-ui/OpenAPI contract и mutation semantics не меняются.

Пример целевого вида:

~~~text
🩺 Состояние системы

🖥 Master
🟢 Панель: в сети
🟢 Xray: работает 26.9.9
🧮 CPU: 12.4%
🧠 RAM: 1.3 GB / 4.0 GB (33%)
💽 Диск: 18.2 GB / 40.0 GB (46%)
⏱ Время работы: 6д 3ч 14м
🌐 Inbounds: 3/3 включено
🟢 Прокси подписок (локально)
🟢 Подписка через nginx/TLS

Ноды
🇫🇮 Finland · 🟢 В сети
🟢 Панель: в сети
🟢 Xray: работает 26.9.9
🧮 CPU: 8% · 🧠 RAM: 27% · ⏱ Время работы: 5д 21ч 09м
🌐 Inbounds: 3 · 👥 Клиентов: 24 · 📡 В сети: 7 · 📶 42 ms
~~~

Production acceptance `v4.20.6` закрыт: release развернут в production, и оператор подтвердил targeted smoke экрана `Мониторинг → Состояние системы`. Общие Master/direct-node labels и statuses отображаются по новому contract, Xray state/version видны у direct node, а Master-only/node-only показатели остаются разделены. Разница RAM представления считается ожидаемой: Master получает used/total из `server_status()`, а агрегированный `NodeInfo` direct node сейчас содержит только `memPct`; дополнительные direct-node API calls ради абсолютных значений не добавляются.

##### Единая терминология Inbound / Inbounds

**Статус: ✅ Выполнено и принято в production в `v4.20.7`.**

Цель — убрать из operator-facing UI и актуальной документации гибридные русифицированные формы с апострофом и использовать единые технические термины `Inbound` / `Inbounds`.

Контракт:

- кнопки, заголовки, status/summary строки, ошибки, подсказки, audit labels и customer-facing тексты используют `Inbound` / `Inbounds`;
- актуальные README/runbooks/roadmap/UI style синхронизируются с теми же labels;
- technical identifiers не переименовываются: callback data, API paths/fields, Python identifiers, module names, DB fields и существующие enum остаются стабильными;
- исторические release notes в `CHANGELOG.md` не переписываются задним числом; новый release section описывает только изменение текущего terminology contract;
- regression/source-audit запрещает возврат гибридных operator-facing форм и отдельно допускает технические lower-case identifiers там, где они не являются пользовательским текстом;
- SQLite schema, provisioning semantics, 3x-ui/OpenAPI contract, Host Control/Deploy Agent API, callback identity и mutation safety не меняются.

Production acceptance `v4.20.7` закрыт: release развернут в production, и оператор завершил targeted smoke основных operator-facing поверхностей с новым terminology contract — `Обзор`, `Инфраструктура → Inbounds`, карточки Inbound, direct-node Inbounds, карточка пользователя/связи Inbounds, Server Groups, `Мониторинг → Состояние системы`, `Роли и права` и client `/start`. Гибридные формы с апострофом на проверенных поверхностях не обнаружены; runtime/API/DB identifiers и mutation semantics не менялись.

##### Редактируемое имя пользователя

**Статус: ⬜ Запланировано на `v4.21.0`.**

Цель — добавить оператору и будущему Client Portal человекочитаемое имя пользователя, не смешивая presentation identity с технической identity клиента 3x-ui.

Контракт:

- `email` текущей записи пользователя остаётся machine identity, используемой 3x-ui/provisioning/traffic/update paths, и не переименовывается ради UI;
- отдельное optional `display_name` хранится в профиле пользователя через новую versioned SQLite migration;
- пустое `display_name` означает fallback на текущий `email`, поэтому существующие пользователи не требуют ручной миграции данных;
- расширенная карточка получает действие `✏️ Имя` с обычным FSM/Cancel/Back contract;
- имя валидируется по длине и управляющим символам, нормализуется перед сохранением и не используется как callback/database identity;
- карточки/списки, где это улучшает UX, показывают display name с техническим email как вторичную информацию или fallback;
- изменение/очистка имени записывается в audit;
- provisioning, subscription identity, `telegram_id`, `sub_id` и 3x-ui email не меняются как побочный эффект;
- regression pack проверяет migration upgrade, fallback, edit/clear flow, RBAC и отсутствие использования display name в machine bindings.

##### User / Audience Groups

**Статус: ⬜ Запланировано на `v4.22.0`.**

User Groups являются отдельной продуктовой сущностью и не заменяют существующие Server Groups.

Разделение ответственности:

- **Server Group** отвечает за инфраструктуру/provisioning: Nodes/Inbounds/Plan placement;
- **User/Audience Group** отвечает за аудиторию: кому в будущем разрешено или запрещено показывать конкретный контент/feature в Client Portal.

Целевой контракт:

- отдельные `user_groups` и `user_group_members` вводятся versioned migration;
- membership many-to-many: один пользователь может состоять одновременно в нескольких audience groups;
- group имеет stable internal ID, изменяемое display name, optional description и timestamps;
- membership привязывается к stable user identity (`telegram_id`), а не к display name/email;
- удаление группы не удаляет пользователей и транзакционно очищает только membership/rules, относящиеся к этой группе;
- в `Пользователях` и карточке пользователя доступны просмотр/изменение membership; отдельный admin screen управляет группами и участниками;
- добавляются явные RBAC privileges для просмотра и изменения User Groups;
- все membership/group mutations audit-friendly;
- backend получает единый reusable audience matcher с понятной семантикой include/exclude; deny/exclude должен иметь приоритет над allow/include, а отсутствие ограничений означает доступ всем подходящим пользователям;
- v4.22 не должен сам связывать audience groups с provisioning/Server Groups или менять VPN-доступ пользователя;
- Client Portal v5 использует этот же matcher для content/feature visibility, вместо ad-hoc проверок конкретных group names;
- regression tests покрывают migration, many-to-many membership, rename/delete, RBAC, audit и matcher edge cases.

##### Cheburcheck integration

**Статус: ⬜ Запланировано на `v4.23.0`.**

Цель — встроить в бот функциональность проверки доменов/IP/ASN на блокировки, сохраняя upstream Cheburcheck checker как source of behavior и не переписывая его алгоритм без необходимости.

Upstream: `LowderPlay/cheburcheck`, BSD 3-Clause. При реализации фиксируется reviewed upstream commit/release и сохраняются обязательные copyright/license notices в third-party documentation.

Архитектурный принцип:

~~~text
Telegram UI
    ↓
CheburcheckClient / typed response model
    ↓
internal/self-hosted Cheburcheck service
    ↓
upstream checker/database logic
~~~

Требования:

- предпочтительный production path — pinned self-hosted Cheburcheck service во внутренней сети deployment; публичный `cheburcheck.ru` не становится обязательной single point of failure;
- bot integration использует documented check API semantics (в текущем upstream это `/api/v1/check?target=...`) и не проксирует произвольные HTTP URL;
- service optional и выключаем/настраиваем локально; его недоступность не должна ломать core bot startup или VPN control plane;
- v4.x UI размещает проверку как контролируемый read-only diagnostics tool внутри существующей authorization boundary; открытие её публичным клиентам решается отдельно в v5;
- input ограничивается поддерживаемыми target types и length/rate limits; ошибки/rate limit/upstream unavailable получают отдельные понятные состояния;
- обязательны connect/read/total timeouts, bounded concurrency и response-size limits;
- health/readiness Cheburcheck видимы оператору, но internal endpoint/credentials не раскрываются пользователю;
- CI фиксирует response contract на reviewed upstream revision через fixtures/contract tests;
- third-party notices и лицензия сохраняются при source/binary redistribution;
- production acceptance проверяет корректный verdict на test fixtures/known targets и graceful degradation при недоступном Cheburcheck service.

##### PackBot-compatible monitoring и diagnostics

**Статус: ⬜ Запланировано на `v4.24.0`.**

Цель — перенести пользовательскую функциональность `vladpak1/packbot` в текущий проект с сохранением продуктовой/алгоритмической логики там, где она совместима с security model, но **без** встраивания отдельного PHP Telegram bot, MySQL runtime или второго webhook stack.

Upstream PackBot распространяется под MIT. Существенно адаптированный/перенесённый код и алгоритмы должны сопровождаться required copyright/license notice и source attribution.

Implementation strategy:

- PackBot используется как behavior/reference implementation;
- новая реализация нативна для текущего Python/aiogram/SQLite/service architecture;
- Telegram navigation, persistence, jobs, audit, alerts и configuration используют существующие project primitives;
- feature parity фиксируется отдельной matrix во время реализации, чтобы функции не терялись молча.

Минимальный parity scope по текущему upstream:

- website monitoring: add/list/remove sites, ownership, per-user limits, periodic checks, разные интервалы для up/down, повторная проверка подозрительного failure, incident state/history, first/repeated/recovery notifications;
- domain diagnostics: WHOIS/domain age и DNS;
- web diagnostics: HTTP/server response, redirect trace, CMS detection;
- SEO diagnostics: indexability/robots/noindex и optional Google PageSpeed integration;
- utilities: sitemap parsing, URL list formatting/trimming и QR generation;
- multilingual behavior upstream не требует появления i18n framework в v4.x: текущий canonical Russian UI сохраняется, а мультиязычность остаётся отдельной задачей.

Обязательная security adaptation при сохранении пользовательского смысла функций:

- один общий outbound-request safety layer для любых user-supplied domain/URL checks;
- только разрешённые schemes/ports; credentials/userinfo в URL запрещены;
- loopback, RFC1918/private, link-local, multicast, documentation/reserved ranges и cloud metadata endpoints блокируются для IPv4/IPv6;
- DNS resolution проверяется до соединения, каждый redirect валидируется заново, а защита не должна позволять DNS rebinding между validation и connect;
- bounded redirect count, connect/read/total timeout, response body limit, sitemap/file size limit, concurrency limit и per-user/global rate limits обязательны;
- background monitoring не должен создавать unbounded queue или позволять одному пользователю исчерпать worker/network resources;
- external API keys (например PageSpeed) хранятся только в локальной secret configuration и не попадают в UI/audit/logs;
- network failures различаются от confirmed site-down там, где это существенно для alerts;
- public-site diagnostics не получают доступ к внутренней VPN/control-plane сети.

Persistence/reliability:

- сайты, ownership, monitoring state, incidents и notification metadata хранятся через versioned SQLite migrations;
- scheduled checks используют существующие background/job primitives и переживают restart без duplicate alert/mutation replay;
- incident transitions и recovery покрываются deterministic tests с fake HTTP/DNS, а не зависят от случайных внешних сайтов;
- production acceptance включает controlled up/down/recovery scenario и resource/rate-limit smoke.

##### Финальный v4 Repository / Public-Release Audit

**Статус: ⬜ Обязательный gate после final v4 feature freeze и до последнего v4.x release.**

Цель — не очередной поверхностный source review, а воспроизводимый release-readiness audit всего репозитория и deployment surface. После начала этого gate новый feature scope в v4.x запрещён; findings закрываются отдельными fix PR/patch releases, после чего затронутые части аудита повторяются.

Audit должен охватывать как минимум:

1. **Архитектура и runtime:** composition/startup/shutdown, router ownership, background loops, startup recovery order, dead code, duplicate responsibilities, circular coupling, large-module risk, blocking calls в async paths и graceful degradation optional services.
2. **Telegram UI/front surface:** весь `/admin` и существующий client flow как реальные пользовательские сценарии; navigation/Back/Refresh/Cancel/Confirm, FSM cleanup, stale Telegram messages, localization, emoji/status grammar, long text/keyboard limits, escaping/formatting и отсутствие misleading state.
3. **Domain/business logic:** Users, Plans, Server Groups, User Groups, Payments/Promo, provisioning/reconcile, subscription identity, monitoring/diagnostics; invariants, state transitions, partial failures, retries, idempotency и edge cases.
4. **SQLite/data integrity:** schema/version journal, upgrade со всех реально поддерживаемых старых состояний, constraints/indexes, transactions, concurrent access, backup-before-dangerous-migration contract, corruption/failure behavior и rollback/recovery assumptions.
5. **Authorization и object ownership:** полный callback/command inventory, RBAC minimum role, IDOR/callback tampering, typed confirmations, cross-user access, stale callback payloads и fail-closed behavior для неизвестных routes/permissions.
6. **Secrets и sensitive data:** bot token, panel/deploy/host tokens, subscription URLs/`sub_id`, payment/provider data, off-site keys, backup contents и Telegram identifiers; redaction в logs/audit/errors/UI, file permissions, env/secret scopes и rotation procedures.
7. **Outbound/network security:** SSRF, DNS rebinding, redirect validation, TLS verification, timeout/retry policy, proxy behavior, user-controlled URLs/hosts, internal address reachability и egress boundaries для Cheburcheck/PackBot integrations.
8. **Injection/path/archive safety:** SQL parameterization, shell/argv construction, command injection, filesystem traversal, symlink handling, tar/zip extraction, filename handling, HTML/Markdown/Telegram escaping и untrusted external payload rendering.
9. **Mutation safety/concurrency:** no-replay semantics, unknown outcomes, idempotency keys/operation IDs, locks, race conditions, double-click callbacks, concurrent jobs, cancellation/restart windows и post-condition verification.
10. **HTTP/control-plane exposure:** inventory каждого listening port/endpoint (subscription proxy, Host Control, Deploy Agent и optional services), bind address, auth, TLS, rate limits, request/body limits, error disclosure и network reachability.
11. **Backups/DR:** SQLite/full/node/off-site creation, manifests/checksums/encryption, retention, malformed/tampered archives, clean-host restore, missing key/credential scenarios, node loss, Master loss и actual production restore drill evidence.
12. **Deployment/container hardening:** Dockerfile/Compose/systemd/sudoers, running user, writable mounts, capabilities, Docker socket absence, filesystem permissions, health checks, restart behavior, network segmentation и least privilege host helpers.
13. **Supply chain:** Python/system/Rust optional dependencies, lock/pin policy, known-vulnerability scan, container/base-image scan, vendored 3x-ui OpenAPI integrity, GitHub Actions third-party actions/pinning, dependency provenance и upgrade process.
14. **Repository/release security:** branch protection/rulesets, required CI checks, merge/release permissions, immutable tag/release expectations, Actions permissions, secret access, release workflow trust boundary и reproducibility of tag/SHA/version/release notes.
15. **Public-repository readiness:** current tree **и Git history** scan for secrets/private hostnames/IPs/Telegram IDs/credentials, sensitive deleted files, production examples, debug dumps and generated artifacts. Любой реально скомпрометированный secret, найденный в history, сначала ротируется; при необходимости history очищается до открытия repository.
16. **Third-party/legal hygiene:** LICENSE, notices/attribution для Cheburcheck/PackBot и других vendored/adapted компонентов, dependency license review, README attribution и отсутствие неразрешённого копирования assets/code.
17. **Reliability/resource abuse:** rate limits, quotas, max list/file/body sizes, bounded queues/concurrency, memory/disk growth, log rotation, backup growth, pagination and worst-case operator/customer input.
18. **Observability:** health endpoints, logs, audit trail, job history, alert semantics, timestamps/timezones, correlation/operation IDs, operator diagnostics and absence of secret leakage in diagnostics.
19. **Documentation:** README, install/update/recovery runbooks, config examples, UI paths, threat-model/security boundaries, public/private deployment differences and tested disaster recovery steps exactly match released code.
20. **Clean-room acceptance:** installation from documented instructions on a fresh host/environment, migration from representative older DB, restore from verified backup, controlled service/node failures, restart during long-running operation and final production smoke.

Audit output contract:

- отдельный versioned report в `docs/audits/` с exact audited commit SHA;
- findings имеют ID, severity, component, evidence/reproduction, impact, fix/decision и regression test reference;
- automated scanners дополняют, но не заменяют manual code/flow review;
- для security-sensitive code требуется evidence-based review, а не утверждение «безопасно» только потому, что тесты зелёные;
- до финального v4 release не остаётся известных unresolved Critical/High findings; security/data-integrity Medium findings должны быть исправлены, а любой иной Medium имеет явный документированный disposition;
- после каждого fix проверяется затронутая область и regression suite;
- финальный release acceptance фиксирует exact tag/SHA, CI, migration state, backup/restore readiness и production smoke.

Результат этого gate должен дать максимально чистую и проверенную v4 baseline для публикации репозитория. Он не считается автоматической гарантией безопасности будущего Client Portal: новый public/customer/payment attack surface v5 проходит отдельный launch audit перед снятием allowlist/допуском реальных клиентов.

##### Декомпозиция bot.py

Статус: ✅ Выполнено в `v4.20.1`.

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

Статус: ✅ Выполнено в `v4.20.1`.

README теперь является текущей картой проекта и точкой входа в канонические runbook'и, а не второй копией release history.

Зафиксированное состояние:

- current install/update/recovery paths ведут в `docs/ADMIN_SETUP.md`, `docs/RELEASES.md`, `docs/VPS_RECOVERY.md` и профильные runbook'и;
- release-by-release история живёт в `CHANGELOG.md` и GitHub Releases;
- version-specific deploy команды старых релизов не публикуются в README как текущая процедура;
- актуальный Subscription Compatibility Proxy contract сохранён, потому что на него ссылается `.env.example`;
- README фиксирует текущие module boundaries после декомпозиции `bot.py`;
- regression test запрещает возвращать в README release headings и hard-coded старые `deploy-release.sh v4.*` инструкции.

##### Консистентная русская локализация Telegram UI

Статус: ✅ Выполнено в `v4.20.1`.

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

Статус: ✅ Выполнено в `v4.20.1`.

Для inline-кнопок emoji/navigation prefix уже является постоянным UI-контрактом. Repo-wide проход выровнял семантические префиксы в информационных сообщениях без механического добавления emoji на каждую строку.

Целевой принцип — не добавлять emoji механически на каждую строку, а использовать их как стабильные визуальные маркеры состояния и типа метрики.

Минимальный контракт:

- одинаковые поля на Master и direct-node экранах используют одинаковые emoji и, где это возможно, одинаковые display labels;
- для общих resource/status полей базовым ориентиром является уже используемый Master-формат: `🧮 CPU`, `🧠 RAM`, `💽 Диск`, `⏱ Время работы`, `🌐 Inbounds`, `👥 Пользователи/клиенты`, `💾 Резервная копия`;
- health/state строки сохраняют семантические status icons: `🟢` healthy/online/enabled/running, `🟡` warning/degraded/pending и `🔴` failed/offline/stopped, если соответствующее состояние действительно известно;
- для node-specific operational полей закреплены `🔗 Адрес`, `🔐 Проверка TLS`, `🧭 Исходящий маршрут`, `📶 Задержка API`, `📊 Сеть`, `🕒 Последний сигнал`;
- чисто техническая строка без отдельного status/type смысла может оставаться без emoji, например `3x-ui: 3.8.5`; цель — визуальная консистентность, а не декоративное заполнение каждой строки;
- внутри одного смыслового блока не должно быть случайной смеси маркированных и немаркированных однотипных метрик без UX-причины;
- аудит охватывает как минимум Master status, Nodes list/detail, Monitoring, Backups, Версии и обновления, Jobs/Alerts и другие read-only operational summaries;
- изменение display text не меняет callback/API identifiers и сопровождается обновлением regression tests там, где exact labels являются частью проверяемого UI-контракта.

Постоянные правила для новых экранов и последующих PR зафиксированы в `docs/UI_STYLE.md`; regression tests защищают канонические префиксы для основных operational summaries.

##### Аудит информационной архитектуры и навигации

Статус: ✅ Выполнено в `v4.20.1`.

Repo-wide проход `/admin` выполнен как пользовательский сценарий, а не только как проверка существующих callback routes. Убраны дублирующие входы, выровнены parent/back flows и закрыты callback/FSM dead ends без изменения domain logic.

Перед заморозкой v4.x `/admin` навигация проверяется как пользовательский сценарий, а не только как набор работающих callbacks.

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

Зафиксированный результат прохода:

- `Версии и обновления` имеют один top-level parent — `Система`; дублирующий вход из `Инфраструктуры` удалён;
- глобальная синхронизация пользователей остаётся в `Пользователях`, а не дублируется в списке Inbounds;
- `admin:home` отображается как возврат в `Панель администратора`, а не как ложный `Обзор`;
- cancel/result/error paths форм и state-changing действий возвращают к соответствующей сущности или списку;
- regression gate проверяет, что operator-facing `render_callback` и `render_input` не создают экран без явной навигации.

##### Редактура пользовательских текстов и public-repository readiness

Статус: ✅ Выполнено в `v4.20.1`.

Repo-wide проход актуальных Telegram hints, README, `.env.example`, install/onboarding/Host Control runbook'ов и operator helper usage выполнен. Исторические deployment-примеры нейтрализованы, актуальные UI-paths синхронизированы с русскими labels, а regression gate защищает public-facing examples от возврата private-deployment drift.

Перед публикацией тексты Telegram UI и operator-facing documentation проверяются на логическую ясность, стилистическую последовательность и отсутствие случайной привязки к текущему private deployment.

Критерии:

- сообщение понятно без знания истории разработки;
- формулировка точно различает `failed`, `unknown`, `offline`, `maintenance`, `disabled` и другие разные состояния;
- тексты не содержат частные hostnames, IP, Telegram IDs, имена операторов/клиентов или временные инфраструктурные детали;
- примеры используют нейтральные placeholders;
- предупреждения и confirmation screens ясно описывают последствие операции;
- нет рекламных или абсолютных утверждений о безопасности/надёжности там, где это нельзя гарантировать;
- README и docs используют актуальные названия UI и не описывают устаревшую навигацию как текущую.

Эта работа рассматривается как часть подготовки проекта к будущему публичному репозиторию, а не как изменение business logic.

Зафиксированный результат:

- публичные примеры используют нейтральные `Edge-1` / `NODE1` вместо исторической географической привязки;
- default `MASTER_FLAG` нейтрален и не предполагает страну deployment;
- актуальные runbook'и используют фактические русские пути `Инфраструктура / Ноды / Готовность`, `Система / Резервные копии / Задания` и другие текущие labels;
- README отдельно показывает top-level Admin Control Plane и вложенные разделы, не выдавая Host Control за top-level entry;
- public-readiness regression test проверяет актуальные public surfaces; исторический `CHANGELOG.md` не переписывается ради этого cleanup.

Крупные публичные customer-facing workflows не должны размывать scope v4.x. `/admin` остаётся Control Plane.

### Отложенные инфраструктурные улучшения

#### Географические metadata direct nodes

**Статус: ⬜ Запланировано. Не является блокером `v4.20.4` или обязательным условием перехода к `v5.0.0`.**

После стабилизации единого node display contract допускается добавить optional country metadata к direct nodes без привязки runtime logic к имени ноды.

Целевой контракт:

- стабильная identity остаётся `node_id`;
- `name` остаётся произвольным изменяемым display name;
- optional `country_code` хранится отдельно в формате ISO 3166-1 alpha-2, например `DE`, `FI`, `NL`;
- флаг Telegram UI вычисляется из `country_code`, а не угадывается по `name`;
- пример: `node_id=7`, `name=Frankfurt-1`, `country_code=DE` → `🇩🇪 Frankfurt-1`;
- legacy nodes без `country_code` продолжают работать; текущий name-based formatter может использоваться как presentation fallback;
- изменение `name` или `country_code` не меняет Direct Admin/Host Control bindings, credentials, backup identity и callback identity;
- onboarding/import flows получают country metadata только как отдельное optional поле с validation; миграция не должна требовать destructive schema rewrite.

До реализации этого пункта runtime и документация не должны вводить специальных условий для конкретной страны или production-ноды.
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

## Gate перед публичным запуском Client Portal

Финальный v4 audit создаёт проверенную backend/control-plane baseline, но не заменяет review нового public attack surface.

После реализации `v5.0.0`, но **до** снятия allowlist/допуска реальных клиентов, выполняется отдельный launch audit как минимум по следующим направлениям:

- ownership/isolation каждого customer endpoint/callback и защита от IDOR;
- signup/onboarding abuse, rate limits, spam/bot automation и resource quotas;
- Order/Payment/Entitlement state machine, webhook authentication/idempotency/replay и reconciliation;
- subscription URL/credential exposure, rotation и cross-user leakage;
- input/file/deep-link/QR handling и внешние URL;
- privacy/data-minimization/retention для Telegram/customer/payment data;
- customer-visible error states и support/recovery flows;
- load/concurrency/failure testing для ожидаемого публичного трафика;
- повторный dependency/container/secret scan для v5 delta;
- clean production-like end-to-end сценарий: registration → purchase/activation → provisioning → subscription use → renewal/expiry/recovery.

Public launch блокируется до закрытия release-blocking findings этого v5 launch audit.

## Gate контролируемого запуска v5.0

После успешного v5 launch audit публичный Client Portal не открывается сразу всему потоку пользователей. Перед широким запуском выполняется отдельный controlled rollout / production acceptance gate.

Минимальный порядок:

1. **Internal acceptance** — Owner/admin test accounts проходят полный customer lifecycle в production-like/production окружении без специальных обходных путей.
2. **Small canary cohort** — доступ открывается ограниченной группе реальных test users через явный allowlist/feature flag; размер cohort остаётся небольшим и управляемым.
3. **Commerce canary** — минимум несколько реальных или provider-approved test payment scenarios проходят цепочку order → provider event → entitlement → provisioning → subscription без ручной правки БД.
4. **Failure canary** — контролируемо проверяются declined/failed payment, delayed webhook, duplicate webhook, temporary provisioning failure, node unavailable, restart бота во время background/reconcile operation и recovery после него.
5. **Ownership/isolation check** — отдельные тестовые аккаунты пытаются открыть чужие callbacks/resources/subscription context; backend должен fail-closed независимо от callback payload.
6. **Abuse/resource check** — проверяются rate limits, repeated callbacks, command spam, oversized/invalid input, monitoring/diagnostics quotas и отсутствие unbounded jobs/queues.
7. **Observability/support readiness** — оператор видит payment/provisioning failures, correlation IDs, audit/job history и понятный recovery path; support не требует доступа к shell/DB для типовых случаев.
8. **Rollback/disable path** — Client Portal и payment acceptance можно быстро выключить feature flag/allowlist policy без отключения Admin Control Plane и без потери уже подтверждённых платежей/entitlements.
9. **Data/reconciliation check** — после canary выполняется сверка orders, payments, entitlements, provisioning state и 3x-ui clients; нет orphaned/duplicate resources или необъяснимых state mismatches.
10. **Soak period** — canary работает достаточное время для прохождения scheduled jobs, expiry/renewal/monitoring циклов и хотя бы одного restart/deploy cycle без новых release-blocking findings.

Критерий выхода из gate:

- нет unresolved Critical/High findings;
- нет необъяснимых payment/entitlement/provisioning inconsistencies;
- error/retry/recovery paths проверены на фактическом deployment;
- rollback/disable procedure проверена;
- только после этого allowlist/feature flag может быть расширен до обычного публичного доступа.

Результат controlled rollout фиксируется отдельным acceptance report с exact release tag/SHA, cohort scope, проверенными сценариями, найденными findings и итоговым решением о расширении доступа.

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
