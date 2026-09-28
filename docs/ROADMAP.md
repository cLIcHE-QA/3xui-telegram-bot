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
11. единая operator-facing терминология `Inbound` / `Inbounds` без гибридных форм с апострофом — ✅ выполнено и принято в production в `v4.20.7`.
12. финальная капитализация `Inbound` в operator-facing edit/clone/delete/error/help flows — ✅ выполнено и принято в production в `v4.20.8`.
13. post-acceptance operator-facing UI cleanup без изменения behavior/storage semantics — ✅ опубликовано в `v4.20.9`; desktop layout follow-up закрыт в `v4.20.10`.
14. compact Inbound keyboard follow-up после production smoke `v4.20.9` — ✅ выполнено и принято в production в `v4.20.10`.
15. редактируемое display name пользователя без изменения 3x-ui machine identity — ✅ выполнено и принято в production в `v4.21.0`; follow-up fixes закрыты и приняты в production в `v4.21.2`.
16. независимые User/Audience Groups для будущей сегментации Client Portal — ✅ выполнено и принято в production в `v4.22.0`.
17. Cheburcheck integration как отдельный read-only diagnostics service/tool — ✅ базовая интеграция принята в production в `v4.23.1`; `v4.23.2` опубликован и развернут, production smoke выявил incomplete compact enrichment; hotfix `v4.23.3` уже реализован в `main`, release ещё не опубликован.
18. PackBot-compatible website monitoring и diagnostics, нативно встроенные в текущую архитектуру — ⬜ запланировано на `v4.24.0`.
19. целостный User Management и рефакторинг карточки пользователя без legacy attach-all sync — ⬜ запланировано на `v4.25.0`.
20. graceful Node Drain / вывод direct-ноды из пользовательского трафика без смешения с maintenance или destructive Stop Xray — ⬜ запланировано на `v4.26.0`.
21. финальный repository/public-release audit после feature freeze и до последнего v4.x release — ⬜ запланировано; переход к `v5.0.0` блокируется до его закрытия.

Отдельный release-specific PR может уточнить реализацию каждого пункта, но перенос любого из них за границу v5 должен быть явным решением с обновлением этого roadmap, а не неявным следствием начала Client Portal.

#### Желательно закрыть до финальной заморозки v4.x

Эти работы не меняют security boundary сами по себе, но уменьшают архитектурный долг перед существенным ростом v5.x.

Зафиксированный порядок финального закрытия v4.x:

1. закрыть и принять в production `v4.20.5` с финальными UI consistency fixes;
2. отдельным patch-релизом `v4.20.6` закрыть UI-04 и выровнять health summary Master/direct nodes без искусственного добавления недоступных метрик;
3. отдельным patch-релизом `v4.20.7` привести operator-facing терминологию к `Inbound` / `Inbounds` без изменения technical identifiers;
4. отдельным patch-релизом `v4.20.8` завершить capitalization `Inbound` в operator-facing edit/clone/delete/error/help flows;
5. отдельным patch-релизом `v4.20.9` закрыть post-acceptance operator-facing UI findings без изменения behavior/storage semantics;
6. отдельным patch-релизом `v4.20.10` скорректировать плотность клавиатуры карточки Inbound по результатам production smoke `v4.20.9`;
7. отдельным релизом `v4.21.0` добавить редактируемое display name пользователя;
8. отдельным релизом `v4.22.0` добавить User/Audience Groups;
9. отдельным релизом `v4.23.0` интегрировать Cheburcheck;
10. patch-релизом `v4.23.1` закрыть ASN response-limit acceptance defect;
11. patch-релизом `v4.23.2` завершить compact result parity и context-preserving navigation Cheburcheck;
12. hotfix-релизом `v4.23.3` закрыть production findings `v4.23.2`: explicit CDN negative state, domain/IP ASN enrichment и truthful regional probe availability;
13. отдельным релизом `v4.24.0` интегрировать PackBot-compatible monitoring/diagnostics;
14. отдельным релизом `v4.25.0` завершить User Management и рефакторинг карточки пользователя;
15. отдельным релизом `v4.26.0` добавить graceful Node Drain / controlled traffic evacuation для direct nodes;
16. после acceptance всех feature-релизов выполнить отложенный production drill encrypted off-site backup/restore;
17. объявить **final v4 feature freeze**: после этой точки новые функции в v4.x не добавляются;
18. после feature freeze провести полный финальный repository/public-release audit по всему продукту;
19. исправления findings выполнять только narrowly-scoped fix PR/patch releases v4.x с обязательным regression/production acceptance; номер последнего v4.x patch заранее не фиксируется;
20. только после закрытия audit gate опубликовать/принять финальный v4.x release и открыть реализацию `v5.0.0`.

Feature freeze здесь означает запрет на новый product scope, а не запрет исправлений. Security/reliability/data-integrity findings, найденные финальным аудитом, должны быть закрыты до финального v4 release.

Off-site acceptance остаётся обязательным pre-v5 gate, но теперь выполняется после завершения запланированных `v4.20.5`–`v4.26.0` релизов и непосредственно перед feature freeze. Финальный аудит выполняется **после** freeze, чтобы проверяемый codebase больше не менялся функционально во время review.

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

Production acceptance `v4.20.5` закрыт: release развернут в production, и оператор подтвердил успешный targeted smoke по всем трём пунктам — Fleet Health display, симметричный status template списка `Ноды` и локальная навигация `Обзора`. Следующим patch-релизом идёт `v4.20.6` с UI-04, затем последовательность feature-релизов `v4.21.0`–`v4.26.0`; off-site drill и freeze выполняются уже после них.

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

#### v4.20.8 — финальная капитализация Inbound

**Статус: ✅ Выполнено и принято в production в `v4.20.8`.**

Scope ограничен operator-facing строками: оставшийся lowercase `inbound` в edit/clone/delete/error/help flows заменяется на канонические `Inbound` / `Inbounds`. Callback data, audit action ids, API/DB fields, Python identifiers, SQLite schema, provisioning semantics и mutation behavior не меняются. Regression gate отдельно фиксирует это различие между пользовательским термином и technical identifiers.

Production acceptance `v4.20.8` закрыт: release развернут в production, и оператор успешно завершил targeted smoke по Inbound edit/help prompts, sync/reset confirmations, clone flow, template copy, delete confirmation, user Inbounds copy и Server Group policy text. Проверенные operator-facing поверхности используют канонические `Inbound` / `Inbounds`; destructive actions во время smoke не выполнялись. Callback/API/DB/Python identifiers, SQLite schema, provisioning semantics и mutation behavior не менялись.

#### v4.20.9 — post-acceptance operator-facing UI cleanup

**Статус: ✅ Опубликовано в `v4.20.9`; layout follow-up завершён в `v4.20.10`.**

Scope предназначен для небольших presentation findings, найденных уже на production smoke/acceptance и не требующих изменения поведения, storage contract или security boundary.

Подтверждённые findings:

- `Инфраструктура → Inbounds → <Inbound> → Сохранить шаблон`: убрать лишнюю implementation detail `bot.sqlite3` из operator-facing prompt. Канонический текст: `Введи имя шаблона. В шаблон попадёт конфигурация Inbound без клиентов.` Хранилище, SQLite schema, имя DB-файла и persistence semantics не меняются.
- Карточка `Inbound`: сделать inline keyboard устойчивой к узкому client-side layout Telegram и не размещать длинные подписи попарно. Целевая структура: `👥 Клиенты | ✏️ Изменить`; отдельными строками `🔄 Синхронизировать клиентов`, `♻️ Сбросить трафик`, `📋 Клонировать`, `🧩 Сохранить шаблон`; предпоследняя строка `⛔ Отключить | 🗑 Удалить Inbound` (для выключенного Inbound — `✅ Включить | 🗑 Удалить Inbound`); последняя строка `⬅ Inbounds`. Callback identifiers и action semantics не меняются.
- Зафиксировать deletion safety guardrail для Admin Control Plane: любые новые operator-facing delete actions только через отдельный confirmation screen (`confirm` + `✖ Отмена`), без one-click mutation. В `v4.20.9` добавить regression/source-audit для текущих delete flows и нормативный contract в `docs/UI_STYLE.md`; существующие delete semantics не меняются.

Дополнительные findings могут быть добавлены в этот же patch до implementation PR, если они остаются narrowly-scoped UI/copy cleanup без behavior changes.
#### v4.20.10 — compact Inbound keyboard follow-up

**Статус: ✅ Выполнено и принято в production в `v4.20.10`.**

Production smoke `v4.20.9` подтвердил корректное отображение на мобильном клиенте, но Telegram Desktop сохраняет различия ширины bubble/inline keyboard для одинакового markup после message edit. Бот не управляет шириной InlineKeyboardMarkup, поэтому follow-up не пытается искусственно растягивать bubble и вместо этого фиксирует более компактную двухколоночную структуру.

Целевая структура карточки Inbound:

1. `👥 Клиенты | ✏️ Изменить`
2. `🔄 Синхронизировать клиентов | ♻️ Сбросить трафик`
3. `📋 Клонировать | 🧩 Сохранить шаблон`
4. `⛔ Отключить | 🗑 Удалить` (для выключенного Inbound — `✅ Включить | 🗑 Удалить`)
5. `⬅ Inbounds`

Confirmation screen удаления сохраняет полное `Удалить Inbound` и отдельное явное подтверждение; callback identifiers, deletion safety contract, SQLite schema, storage/persistence semantics и provisioning behavior не меняются.

Production acceptance `v4.20.10` закрыт: release развернут в production, и оператор завершил targeted smoke после обновления бота. Компактная пятистрочная клавиатура карточки Inbound принята; проверены desktop/mobile presentation, короткая кнопка `🗑 Удалить` в карточке и сохранение полного `Удалить Inbound` на confirmation screen. Delete confirmation guardrail, callback identifiers, SQLite schema, storage/persistence semantics, provisioning и mutation behavior не менялись.

##### Редактируемое имя пользователя

**Статус: ✅ Выполнено и принято в production в `v4.21.0`.**

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

Production acceptance `v4.21.0` закрыт: release развернут через Safe Bot Self-Update, bot штатно запустился с новой SQLite schema v2, и оператор завершил targeted smoke display-name flow. Подтверждены установка отображаемого имени, его явная очистка с возвратом fallback на email и отсутствие наблюдаемых regressions в пользовательской карточке/подписке. Machine identity (`email`, `telegram_id`, `sub_id`, 3x-ui client identity) по contract и regression coverage не изменяется; production smoke не выявил побочных изменений.

##### v4.21.1 — display name consistency и MSK

**Статус: 🟠 Опубликовано в `v4.21.1`; production acceptance ещё не выполнен.**

Patch закрывает два post-acceptance presentation findings `v4.21.0` без изменения product/storage/security boundaries:

- display name используется как основной operator-facing label во всех соседних user surfaces, при этом email остаётся технической identity и fallback;
- абсолютные Telegram Admin timestamps отображаются в MSK (UTC+3), а machine timestamps и `BACKUP_HOUR_UTC` сохраняют UTC/epoch semantics;
- date-only operator input `YYYY-MM-DD` для user/promo expiry интерпретируется как `23:59:59 MSK`;
- SQLite schema, 3x-ui/OpenAPI, provisioning, subscription identity, Host Control/Deploy Agent и mutation semantics не меняются.

Production acceptance после deployment должен подтвердить:

- display name в `Пользователи` и `Подписки`, а также на нескольких соседних user surfaces;
- fallback на email после очистки display name;
- MSK timestamps на operator-facing экранах;
- отсутствие изменений email / Telegram ID / `sub_id` / VPN access;
- базовый health/status после обновления.

##### v4.21.2 — DR formatter и log viewer follow-up

**Статус: ✅ Выполнено и принято в production в `v4.21.2`.**

Production smoke `v4.21.1` подтвердил display name в `Подписки` и operator-facing MSK presentation. При дальнейшей проверке найдены два отдельных runtime/UI finding:

- Disaster Recovery падал с `NameError` из-за отсутствующего импорта MSK formatter helper;
- выбор `50` / `200` строк в `Журналы` фактически читал разные объёмы, но одинаковый character cap делал Telegram output почти неразличимым.

`v4.21.2` исправляет оба finding без изменения SQLite schema, 3x-ui/OpenAPI, raw log timezone, redaction/security boundaries или mutation semantics.

Production acceptance закрыт: оператор подтвердил штатное открытие Disaster Recovery без `NameError`, фактическое различие режимов журнала `50` / `200` и успешный базовый health check `GET /healthz` с HTTP 200. Raw log timestamps продолжают отображаться в machine-level UTC по contract.

##### User / Audience Groups

**Статус: ✅ Выполнено и принято в production в `v4.22.0`.**

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

Production acceptance `v4.22.0` закрыт на развёрнутом release commit `37e16cf8e2f5a38f7796118c0ac93ba9c78a3c12`. Базовый status до и после targeted smoke подтвердил `Container: running`, `RestartCount=0`, `Bot version: 4.22.0`, `Health: ok`, `DB: ok`, ожидаемый Docker subnet `172.19.0.0/16` и `3x-ui connectivity: ok`. Migration journal подтвердил успешные v1/v2 и `v3 user_audience_groups_v4_22_0`.

Targeted smoke подтвердил production flow: создание временной User Group, поиск существующего пользователя, добавление membership, отображение группы из карточки пользователя, удаление membership через confirmation flow, наличие audit-событий для create/add/remove и двухшаговое удаление пустой группы. Тестовые данные после проверки удалены. Разделение User Groups и VPN provisioning отдельно защищено code/regression contract; production smoke не выполнял искусственных VPN mutations ради проверки.

##### Cheburcheck integration

**Статус: ✅ Выполнено в `v4.23.1`.**

Production acceptance закрыт после hotfix `v4.23.1` на exact release SHA `ff6638442cbe9c2adc9aa76d74c2cfb4b647aaf6`: Master/direct-node shortcuts, domain/public IP/ASN, URL/private-IP rejection, graceful unavailable/recovery и финальный base health пройдены; `AS213459` с response около 382 KiB успешно обработан новым 1 MiB bounded limit. После остановки и запуска только Cheburcheck backend оба runtime-сервиса вернулись в `healthy`, а bot status остался `RestartCount=0`, Health/DB/3x-ui `ok`. Проверка bot logs по exact internal URL и credential-variable names дала нулевые совпадения. Production flood для backend rate limit намеренно не выполнялся; per-admin 2-second cooldown закреплён отдельным regression-test без нагрузки на upstream.

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

Реализация в `main` использует reviewed upstream `LowderPlay/cheburcheck@0bbd2be8ca4b8f9ded1407597654314fc2a900c6`, отдельный `CheburcheckClient`, optional `CHEBURCHECK_URL`, read-only RBAC и экран `Мониторинг → Проверка блокировок`. Auto-discovery предлагает безопасные hostname/IP из Master/direct Nodes/enabled Hosts, а карточки Master/direct node имеют shortcut проверки; URL path/query/credentials и private/local targets не передаются.

##### v4.23.2 — Cheburcheck: расширенный результат и контекстная навигация

**Статус: 🟠 `v4.23.2` опубликован и развернут; production smoke выявил incomplete result enrichment, acceptance закрывается обязательным hotfix `v4.23.3`.**

Scope:

1. **Компактный parity результата с Cheburcheck site.** Расширить текущий bounded summary данными, которые уже доступны/могут быть надёжно получены из pinned Cheburcheck backend: нахождение цели в используемых блок-листах/реестрах и доступность по регионам. Telegram UI должен показывать это максимально компактно, без raw payload и без ослабления существующих response-size/timeouts/concurrency/rate-limit границ.

   Целевой operator-facing формат:

   ~~~text
   🔎 Проверка блокировок

   Цель: example.org
   Результат: 🟢 блокировка не обнаружена
   Сеть: Example ISP · AS12345 · Москва

   📋 Списки
   РКН: 🟢 не найден
   CDN: Cloudflare · 3 сети
   Исключение CDN: —
   ASN: 2 / 184 подсетей в списках

   🌍 Регионы: 11 ответов · 🟢 8 · 🔴 2 · 🟡 1

   Источник: Cheburcheck.
   ~~~

   Presentation contract:
   - верхняя часть содержит только цель, итоговый verdict и доступную network identity: организация / ASN / location;
   - блок `📋 Списки` агрегирует РКН, CDN, CDN exception и ASN/subnet coverage в одну короткую секцию;
   - региональные ответы сворачиваются в одну строку с общим числом и количеством `🟢 / 🔴 / 🟡`, без длинного перечня регионов в основном result card;
   - отсутствующие optional значения отображаются как `—`, а не раздувают карточку дополнительными пояснениями;
   - raw upstream payload и внутренние service details в Telegram UI не выводятся;
   - строка `Источник: Cheburcheck.` сохраняет явную attribution внешнего источника данных.

   Перед реализацией зафиксировать exact upstream fields/semantics для reviewed revision и покрыть их fixtures/contract tests; если часть site-only данных не выдаётся backend API, это явно фиксируется и не эмулируется догадками.

2. **Контекстная навигация Cheburcheck.** Источник входа становится частью UI context:
   - вход из `/admin → Мониторинг → Проверка блокировок` всегда возвращает только в Monitoring/Cheburcheck flow;
   - вход из карточки Master возвращает только в карточку Master;
   - вход из карточки direct Node возвращает только в ту же Node;
   - discovered targets, manual search, result, error, `Проверить ещё` и повторный поиск обязаны сохранять исходный parent context;
   - переход из Monitoring flow в Node/Master card и обратный cross-context jump через Cheburcheck запрещён;
   - callback data хранит только safe stable context/identity, без URL/credentials;
   - regression tests покрывают все entry points и Back/Repeat/Search transitions.

Цель релиза — улучшить информативность и UX Cheburcheck без изменения его read-only security boundary, provisioning/VPN state или 3x-ui mutations.

##### v4.23.3 — Cheburcheck: hotfix compact result enrichment

**Статус: 🟡 Реализовано в `main`; release `v4.23.3` ещё не опубликован.**

Production smoke `v4.23.2` подтвердил сам compact layout и navigation, но выявил три presentation/data gaps:

1. пустой `cdn_providers` выводился как неизвестное `—`, хотя reviewed upstream однозначно означает «CDN не найден»;
2. для domain/public-IP upstream возвращает ASN в `geo.asn`, но `asn_info` заполняет только при target вида `AS12345`, поэтому ожидаемая строка `blocked / total` оставалась пустой;
3. minimal self-hosted runtime без active Probe reporters возвращает нулевую regional availability, а UI маскировал её нейтральным `—`.

Hotfix scope:

- empty CDN result показывается как `🟢 не найден`;
- domain/public-IP с валидным `geo.asn` выполняет один дополнительный bounded read-only check по этому ASN и использует только counts `blocked_prefixes / prefixes`; failure enrichment не меняет основной verdict;
- regional SSE сохраняет `started.online_probes` и различает агрегированные ответы, отсутствие active scanners, отсутствие ответов при online scanners и upstream/transport unavailable;
- subnet/ASN regional probe остаётся неприменимым и не запускается;
- никакие regional results не эмулируются и не подменяются static API данными;
- SQLite schema, 3x-ui/OpenAPI contract, provisioning/VPN mutations, Host Control, Deploy Agent и pinned Cheburcheck revision не меняются;
- изменение bot-only и не требует rebuild существующего Cheburcheck runtime; отдельное развёртывание probe fleet остаётся отдельной infrastructure задачей.

Acceptance `v4.23.3` должен подтвердить на production domain target: explicit CDN negative/positive state, заполненный ASN coverage при доступном `geo.asn` и честную regional status строку; после smoke повторяется базовый `deploy-release.sh --status`.

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


##### v4.25.0 — User Management: рефакторинг карточки пользователя

**Статус: ⬜ Запланировано на `v4.25.0`.**

Цель — завершить v4.x User Management как цельный операторский workflow: карточка пользователя становится единой точкой входа для профиля, тарифа, срока, трафика, provisioning-доступа, подключений, подписки, платежей и персональной audit timeline. Релиз сохраняет существующие backend primitives и security boundaries, убирает конкурирующие legacy-пути синхронизации Inbounds и добавляет недостающие admin-facing функции без открытия Client Portal.

Release boundary:

- scope относится только к `/admin → Пользователи`; публичный `/start` и Client Portal остаются задачей v5.x;
- machine identity не меняется: `telegram_id`, 3x-ui `email` и `sub_id` сохраняют текущую семантику; `display_name` остаётся только presentation metadata;
- текущие полезные возможности User Management не удаляются: срок, лимит трафика, reset traffic, IP limit, тариф, Server Group, ручные Inbounds, safe/strict reconcile, enable/disable, delete, subscription rotation, display name, note, statistics и bulk actions сохраняются;
- отдельный legacy-механизм «подключить все глобально разрешённые Inbounds» больше не считается канонической синхронизацией пользователя и не должен оставаться видимым action в новой карточке;
- автоматическое управление доступом выполняется только через policy-based `ProvisioningEngine` / согласование; ручное исключение выполняется только через экран конкретных Inbounds;
- абсолютные timestamps используют действующий MSK display contract; machine timestamps остаются epoch/UTC;
- Telegram Admin Control Plane остаётся односообщенческой панелью там, где экран является обычным text/keyboard view; FSM и confirmation flows обязаны иметь явный Cancel/Back;
- все новые callback routes включаются в централизованный privilege catalog; неизвестный callback по-прежнему fail-closed;
- реализация UI-контракта этого релиза должна синхронно обновить `docs/UI_STYLE.md`, regression tests и `CHANGELOG.md`; этот roadmap фиксирует planned scope, но не помечает его реализованным до merge/release/acceptance.

###### Каноническая информационная архитектура

~~~text
👥 Пользователи
│
├── 🔎 Поиск
├── ➕ Создать пользователя
├── ☑️ Массовые действия
├── 📊 Статистика
├── 🚀 Согласовать всех
│
└── 👤 Пользователь
    │
    ├── 💎 Тариф
    │   ├── Сменить тариф
    │   ├── Применить параметры тарифа
    │   └── Тариф + согласование
    │
    ├── 📅 Срок
    │   ├── +30 дней
    │   └── Установить дату
    │
    ├── 📊 Трафик
    │   ├── Использование
    │   ├── Изменить лимит
    │   └── Сбросить трафик
    │
    ├── 🌐 Доступ
    │   ├── 🗂 Группа серверов
    │   ├── 🚀 Согласование
    │   │   ├── Безопасное
    │   │   └── Строгое
    │   ├── 📡 Inbounds
    │   │   └── ручной attach/detach
    │   └── ⚙️ Параметры доступа
    │       ├── IP limit
    │       └── VLESS Flow
    │
    ├── 📱 Подключения
    │   ├── Online / last online
    │   ├── Устройства / HWID
    │   │   └── Удалить устройство
    │   └── IP-адреса
    │
    ├── 🔗 Подписка
    │   ├── Открыть ссылку
    │   ├── Показать URL
    │   ├── QR-код
    │   └── Перевыпустить ссылку
    │
    ├── 💳 Платежи
    │   └── История платежей пользователя
    │
    ├── 🧾 Активность
    │   └── Audit timeline пользователя
    │
    ├── ✏️ Профиль
    │   ├── Имя
    │   └── Заметка
    │
    └── ⚙️ Ещё действия
        ├── Enable / Disable
        ├── Reset traffic
        ├── Перевыпустить подписку
        ├── Strict reconcile
        └── Delete
~~~

###### RBAC contract

Новые экраны не вводят пятую роль и используют существующий каталог privileges.

- `users.view` / минимум `Read-only`: список, поиск, карточка, тариф/срок/трафик как read-only state, доступ/reconcile preview, Inbounds view, подключения, устройства/IP как read-only data, подписка без rotation;
- `users.support` / минимум `Support`: создание пользователя, display name/note, назначение Plan/Server Group, применение параметров тарифа, safe reconcile, manual attach/detach Inbound, изменение expiry/traffic/IP limit, reset traffic, enable/disable, VLESS Flow sync, bulk lifecycle operations и удаление одного HWID device после confirmation;
- `users.admin` / минимум `Administrator`: strict reconcile, rotation subscription identity, удаление пользователя и другие уже существующие расширенные/destructive user operations;
- `payments.view`: вложенный экран платежей пользователя и карточка платежа; write-actions платежей остаются только в каноническом разделе `Платежи` и под `payments.manage`;
- `monitoring.view`: персональная audit timeline пользователя; она является filtered view общего audit log, а не отдельным журналом;
- `Owner` не получает отдельный новый User Management capability только из-за этого релиза; owner-only boundary возникает только там, где он уже задан отдельным privilege contract.

Keyboard должен быть privilege-aware: mutation-кнопка, на которую текущая роль не имеет права, не показывается как ложнодоступная. Authorization handler остаётся обязательным независимо от видимости кнопки.

###### Экран `Пользователи`

Канонический вход: `/admin → Пользователи`, callback `admin:users`.

Текст:

~~~text
👥 Пользователи

Пользователей: {total}
🟢 Включено: {enabled_count}
⛔ Отключено: {disabled_count}
~~~

Если aggregate enabled/disabled state временно нельзя получить одним bounded read без N+1 запросов, список пользователей не блокируется: строка счётчиков опускается или явно показывает `⚠️ недоступно`, а `Пользователей: {total}` берётся из локальной БД.

Каждый пользователь отображается отдельной кнопкой:

~~~text
👤 {display_name_or_email} · TG {telegram_id}
~~~

Если задан `display_name`, технический email остаётся доступен в карточке пользователя; callback identity всегда использует `telegram_id`.

Клавиатура после списка:

~~~text
[🔎 Поиск]                  [➕ Создать]
[☑️ Массовые действия]     [📊 Статистика]
[🚀 Согласовать всех]
[⬅ Панель администратора]
~~~

При количестве пользователей больше page size обязательна pagination; пользователь не должен становиться недоступным только потому, что текущий экран показывает первые 40 записей:

~~~text
[◀️]        [2/5]        [▶️]
~~~

Page callback не меняет identity пользователя. Центральная кнопка номера страницы не выполняет mutation.

`📊 Статистика` сохраняет существующий `admin:stats`. `🚀 Согласовать всех` сохраняет существующий safe policy-based flow `admin:provision:all:ask → admin:provision:all:run`.

###### Поиск пользователя

`🔎 Поиск` открывает FSM prompt:

~~~text
🔎 Поиск пользователя

Введи Telegram ID, email или отображаемое имя.

[✖ Отмена]
~~~

Поиск:

- exact match по `telegram_id`;
- case-insensitive match по техническому email;
- case-insensitive substring по `display_name`;
- не использует `display_name` как identity;
- при одном exact result может сразу открыть карточку;
- при нескольких result показывает тот же формат строк, что основной список;
- `✖ Отмена` и Back возвращают в `Пользователи`;
- validation error не очищает путь возврата и не создаёт новое сообщение без необходимости.

###### Создание пользователя

`➕ Создать` — новый admin flow под `users.support`. Он должен переиспользовать существующие user/provisioning primitives и не иметь отдельной ad-hoc логики выдачи всех Inbounds.

Порядок:

1. **Telegram ID**

   Prompt:

   ~~~text
   ➕ Новый пользователь

   Отправь Telegram ID пользователя.

   [✖ Отмена]
   ~~~

   ID обязателен, положительный и уникальный в локальной БД. Если локальный пользователь уже существует, mutation не выполняется и предлагается `👤 Открыть пользователя`.

   Если локальной записи нет, но 3x-ui уже возвращает клиента по этому `tgId`, новый remote client не создаётся. Экран предлагает безопасное восстановление локальной записи из существующей 3x-ui identity:

   ~~~text
   ⚠️ Клиент уже существует в 3x-ui.

   Email: {email}
   Telegram ID: {telegram_id}

   [♻️ Восстановить запись бота]
   [✖ Отмена]
   ~~~

2. **Технический email**

   По умолчанию предлагается `tg_{telegram_id}`.

   ~~~text
   Технический email 3x-ui

   По умолчанию:
   tg_{telegram_id}

   [✅ Использовать предложенный]
   [✏️ Ввести другой]
   [✖ Отмена]
   ~~~

   Custom email нормализуется/валидируется теми же правилами, что machine identity 3x-ui, и проверяется на уникальность локально и в панели.

3. **Отображаемое имя**

   ~~~text
   Отображаемое имя

   Можно задать имя для админки.
   Технический email от этого не изменится.

   [⏭ Пропустить]
   [✖ Отмена]
   ~~~

   Используется существующий `display_name` contract: до 64 символов, без управляющих символов, пустое значение означает fallback на email.

4. **Тариф**

   Показывается список активных Plans. Default plan, если он настроен, отмечается как рекомендуемый текущей конфигурацией. Назначение тарифа определяет policy через существующие Plan / Server Group primitives.

   Если тариф не выбран, compatibility/trial path допускается только там, где он уже поддерживается текущим `ProvisioningEngine`; UI обязан явно назвать его `режим совместимости`, а не скрывать отсутствие Plan.

5. **Предпросмотр**

   ~~~text
   ➕ Новый пользователь

   Telegram ID: {telegram_id}
   Email: {email}
   Имя: {display_name_or_—}
   Тариф: {plan_or_compatibility}
   Группа серверов: {group}
   Срок: {expiry_preview}
   Лимит трафика: {traffic_limit}
   IP limit: {ip_limit}
   Целевые Inbounds: {count}

   [✅ Создать пользователя]
   [⬅ Изменить тариф]
   [✖ Отмена]
   ~~~

   Create выполняет remote client creation и локальную запись только через проверяемый workflow. При неопределённом исходе remote mutation нельзя автоматически повторять создание; сначала выполняется read-only verification по `tgId`/email и только доказанный state определяет дальнейший шаг.

Ранее обсуждавшаяся кнопка `💾 Только создать` **не входит в финальный v4.25 contract**: она создаёт неоднозначное partial state между локальной записью, remote client и provisioning. Для пользователя без активного доступа используются существующие Enable/Disable и policy primitives, а не отдельный «полусозданный» режим.

После success открывается новая карточка пользователя. Audit не содержит `sub_id`, subscription URL или другие secrets.

###### Главная карточка пользователя

Канонический callback сохраняется: `admin:u:{telegram_id}`.

Текст:

~~~text
👤 {display_name_or_email}
Email: {email}
Telegram ID: {telegram_id}
Статус: {🟢 включён | ⛔ отключён}

💎 Тариф: {plan}
📅 Срок: {expiry_msk}
📊 Трафик: {used} / {limit_or_без_лимита}
📱 IP limit: {limit_or_без_лимита}
🌐 Группа: {server_group}

🚀 Доступ:
целевых {desired} · подключено {attached_target}
не хватает {missing} · лишних {extra}
~~~

Если policy/read 3x-ui временно недоступен, локальные данные карточки продолжают отображаться, а соответствующая строка становится `🚀 Доступ: ⚠️ не удалось получить состояние`. Ошибка чтения не маскируется зелёным status.

Клавиатура:

~~~text
[💎 Тариф]        [⏳ Продлить]
[📅 Срок]         [📊 Трафик]
[🌐 Доступ]       [📱 Подключения]
[🔗 Подписка]     [💳 Платежи]
[🧾 Активность]   [✏️ Профиль]
[⚙️ Ещё действия]
[⬅ Пользователи]
~~~

`⏳ Продлить` является shortcut существующего `+30 дней`; canonical detail screen срока остаётся `📅 Срок`.

###### `💎 Тариф`

Parent: карточка пользователя. Канонический callback сохраняется: `admin:u:plan:{telegram_id}`.

Текст:

~~~text
💎 Тариф · {user_label}

Текущий тариф: {plan}
Стоимость: {price}
Период: {duration}

Параметры тарифа:
📦 Трафик: {plan_traffic}
📱 IP limit: {plan_ip_limit}
🗂 Группа серверов: {plan_group}

Текущие параметры пользователя:
📦 Трафик: {current_traffic_limit}
📱 IP limit: {current_ip_limit}
🗂 Группа серверов: {current_group}
~~~

Клавиатура:

~~~text
[💎 Сменить тариф]
[▶ Применить параметры тарифа]
[🚀 Тариф + согласование]
[⬅ Пользователь]
~~~

Semantics сохраняют текущее разделение:

- `Сменить тариф` назначает Plan в профиле и не выдаёт скрыто новый remote access;
- `Применить параметры тарифа` использует существующий confirmation flow и применяет текущие plan-limit semantics;
- `Тариф + согласование` применяет параметры тарифа, связанную Server Group и выполняет **безопасное** согласование; лишние управляемые Inbounds не удаляются;
- отсутствие тарифа отображается явно; действия, которым нужен Plan, не делают implicit guess.

Существующие callbacks `admin:u:planset:*`, `admin:u:planapplyask:*`, `admin:u:planapplyrun:*`, `admin:u:planprovask:*`, `admin:u:planprovrun:*` сохраняются, если implementation не требует migration identifier-а.

###### `📅 Срок`

Parent: карточка пользователя. `admin:u:expiry:{telegram_id}` становится detail screen, а не непосредственным FSM prompt.

Текст:

~~~text
📅 Срок действия · {user_label}

Текущий срок:
{expiry_msk}

Осталось:
{relative_duration}
~~~

Клавиатура:

~~~text
[➕ +30 дней]
[📅 Установить дату]
[⬅ Пользователь]
~~~

- `➕ +30 дней` сохраняет существующую семантику `adminextend:{telegram_id}`: база — `max(current_expiry, now)`;
- `📅 Установить дату` открывает отдельный FSM callback, например `admin:u:expiryedit:{telegram_id}`;
- date-only `YYYY-MM-DD` означает `23:59:59 MSK` по действующему UI contract;
- validation error оставляет `✖ Отмена`;
- success возвращает в экран `📅 Срок`, а не в случайный parent.

###### `📊 Трафик`

Parent: карточка пользователя. `admin:u:traffic:{telegram_id}` становится detail screen.

Текст:

~~~text
📊 Трафик · {user_label}

⬆ Upload: {up}
⬇ Download: {down}

Использовано:
{used}

Лимит:
{limit_or_без_лимита}

Осталось:
{remaining_or_без_лимита}
~~~

Клавиатура:

~~~text
[✏️ Изменить лимит]
[♻️ Сбросить трафик]
[⬅ Пользователь]
~~~

- `Изменить лимит` открывает FSM `admin:u:trafficedit:{telegram_id}`; `0`/каноническое значение unlimited отображается как `без лимита`;
- `Сбросить трафик` сохраняет текущий ask/run contract `admin:u:resetask:* → admin:u:resetrun:*`;
- reset screen явно называет пользователя и требует confirmation;
- success возвращает в `📊 Трафик`.

###### `🌐 Доступ`

Новый parent callback: `admin:u:access:{telegram_id}`.

Текст:

~~~text
🌐 Доступ · {user_label}

Источник политики:
{plan/profile/compatibility}

Группа серверов:
{group}

Режим Inbounds:
{all_managed/selected display label}

Целевые: {desired_count}
Текущие: {current_count}
Не хватает: {missing_count}
Лишних управляемых: {extra_count}

{optional unavailable nodes block}
~~~

Клавиатура:

~~~text
[🗂 Группа серверов]
[🚀 Согласование]
[📡 Inbounds]
[⚙️ Параметры доступа]
[⬅ Пользователь]
~~~

Этот экран является единственным parent для автоматического/ручного управления network access пользователя.

###### `🌐 Доступ → 🗂 Группа серверов`

Сохраняется `admin:u:group:{telegram_id}` и существующие `admin:u:groupset:*`.

Текст перед выбором:

~~~text
🗂 Группа серверов · {user_label}

Текущая группа:
{group}

Группа определяет целевой набор согласования.
Само назначение не меняет 3x-ui мгновенно.
~~~

Кнопки используют `✅` для текущей группы и `⬜` для остальных. Последняя кнопка:

~~~text
[⬅ Доступ]
~~~

После назначения:

~~~text
✅ Назначена группа: {group}.

Для применения целевого доступа выполните согласование.

[🚀 Согласовать сейчас]
[⬅ Доступ]
~~~

Назначение Server Group не должно скрытно attach/detach Inbounds.

###### `🌐 Доступ → 🚀 Согласование`

Сохраняется `admin:u:prov:{telegram_id}`.

Текст:

~~~text
🚀 Согласование · {user_label}

Источник: {source}
Тариф: {plan}
Группа серверов: {group}
Режим Inbounds: {mode}

Целевые: {ids}
Текущие: {ids}
Не хватает: {ids}
Лишние управляемые: {ids}

{warnings/unavailable nodes}
~~~

Клавиатура:

~~~text
[✅ Безопасное согласование]
[⚠️ Строгое согласование]
[⬅ Доступ]
~~~

**Безопасное согласование**:

- callback `admin:u:provrun:{telegram_id}:safe`;
- добавляет только отсутствующие actionable target Inbounds;
- лишние текущие Inbounds не удаляет;
- unavailable members остаются целевыми, но не вызывают ложный success;
- результат показывает `Подключены`, `Отключены`, `Всё ещё отсутствуют`, `Лишние управляемые`.

**Строгое согласование**:

- `admin:u:provstrictask:{telegram_id}` всегда открывает отдельный warning screen;
- `admin:u:provrun:{telegram_id}:strict` доступен только `users.admin`;
- добавляет отсутствующие и удаляет только управляемые extras, которых нет в target policy;
- last-access/managed safety guards существующего provisioning engine сохраняются.

Confirmation:

~~~text
⚠️ Строгое согласование

Будут добавлены отсутствующие целевые Inbounds
и отключены управляемые Inbounds,
которых нет в текущей политике пользователя.

Будут отключены:
{extra_ids_or_нет}

[⚠️ Выполнить строгое согласование]
[✖ Отмена]
~~~

Cancel возвращает в preview согласования.

###### `🌐 Доступ → 📡 Inbounds`

Сохраняется `admin:u:inbounds:{telegram_id}` и `admin:u:ibtoggle:{telegram_id}:{inbound_id}`.

Текст:

~~~text
📡 Inbounds · {user_label}

Нажатие подключает/отключает пользователя
от конкретного Inbound.

⚠️ Ручные изменения могут отличаться от политики
тарифа/Группы серверов. Следующее строгое
согласование может их изменить.
~~~

Каждый Inbound:

~~~text
✅ #1 · 443/VLESS · Germany
⬜ #2 · 443/VLESS · Austria
~~~

Последняя кнопка:

~~~text
[⬅ Доступ]
~~~

Manual toggle остаётся support-operation. Существующая защита от отключения последнего допустимого managed Inbound сохраняется.

###### `🌐 Доступ → ⚙️ Параметры доступа`

Новый callback: `admin:u:accesscfg:{telegram_id}`.

Текст:

~~~text
⚙️ Параметры доступа · {user_label}

📱 IP limit: {limit_or_без_лимита}
🔀 VLESS Flow: {flow_or_none}
~~~

Клавиатура:

~~~text
[📱 Изменить IP limit]
[🔀 Синхронизировать Flow]
[⬅ Доступ]
~~~

- изменение IP limit переиспользует текущий validation/FSM contract `admin:u:ip:*`, но success возвращает в `Параметры доступа`;
- `Синхронизировать Flow` является отдельной mutation и не attach'ит Inbounds;
- flow mutation использует отдельный ask/run pair, например `admin:u:flowask:* → admin:u:flowrun:*`, и применяет только configured `settings.vless_flow`;
- если `settings.vless_flow` пуст, UI показывает `VLESS Flow: не настроен` и не предлагает ложную mutation.

###### Депрекация legacy `Синхронизировать Inbounds`

В v4.25 из visible keyboards удаляются:

- `🔄 Синхронизировать Inbounds` / `adminsync:{telegram_id}`;
- `🔄 Синхронизировать всех` / `admin:syncall:ask` / `admin:syncall:run`;
- bulk `sync`, который attach'ит выбранным пользователям все globally allowed Inbounds.

Причина: эти paths используют глобальный `choose_inbounds(...)` и могут выдать доступ шире индивидуального `Plan → Server Group → target policy`.

Stale Telegram callback не должен молча выполнять старую mutation. На один transition release старые callback identifiers могут оставаться compatibility handlers, но только как **non-mutating redirect**:

~~~text
ℹ️ Это действие устарело.

Автоматическая синхронизация доступа теперь выполняется
через policy-based «Согласование».

[🌐 Открыть доступ]
[⬅ Пользователь]
~~~

Для global stale callback:

~~~text
ℹ️ «Синхронизировать всех» больше не используется.

Используй безопасное policy-based согласование.

[🚀 Согласовать всех]
[⬅ Пользователи]
~~~

После достаточного transition window compatibility handlers могут быть удалены отдельным cleanup; unknown callbacks после этого fail-closed по общему contract.

###### `📱 Подключения`

Новый callback: `admin:u:connections:{telegram_id}`.

Текст:

~~~text
📱 Подключения · {user_label}

{online_status}
Последняя активность: {last_online_msk_or_нет_данных}
IP limit: {limit_or_без_лимита}

Устройств: {hwid_count_or_недоступно}
IP-адресов: {ip_count_or_недоступно}
~~~

Клавиатура:

~~~text
[📱 Устройства]
[🌐 IP-адреса]
[⬅ Пользователь]
~~~

IP limit здесь только показывается. Каноническое изменение лимита находится в `🌐 Доступ → ⚙️ Параметры доступа`, чтобы не создавать два равноправных edit path.

Online/last-online используют существующие read-only 3x-ui primitives. Экран не выдаёт IP/session за физическое устройство без HWID identity.

###### `📱 Подключения → 📱 Устройства`

Для v4.25 используемый 3x-ui contract расширяется reviewed endpoints pinned schema:

- `POST /panel/api/clients/hwids/{email}` — список зарегистрированных HWID devices;
- `DELETE /panel/api/clients/hwids/{email}/{id}` — удаление одного зарегистрированного устройства.

Они добавляются в `contracts/3xui/contract.json`, `XUIClient` и OpenAPI regression coverage до использования в Telegram UI.

Список:

~~~text
📱 Устройства · {user_label}

1. {device_model_or_device_os}
   {fingerprint}
   Последняя активность: {last_seen_msk}

2. ...
~~~

Кнопка каждой записи открывает detail callback `admin:u:device:{telegram_id}:{device_id}`.

Карточка устройства:

~~~text
📱 Устройство · {user_label}

Модель: {device_model_or_—}
ОС: {device_os} {os_version}
Fingerprint: {short_fingerprint}
User-Agent: {safe_user_agent_or_—}
Первое появление: {first_seen_msk}
Последняя активность: {last_seen_msk}

[🗑 Удалить устройство]
[⬅ Устройства]
~~~

Полный HWID/hash не должен выводиться, если upstream deliberately возвращает только short fingerprint.

Удаление устройства обязательно двухшаговое:

~~~text
⚠️ Удалить устройство?

{device_model_or_fingerprint}
Пользователь сможет зарегистрировать устройство заново,
если это разрешает текущий HWID limit.

[🗑 Удалить устройство]
[✖ Отмена]
~~~

Первый callback `admin:u:devdelask:{telegram_id}:{device_id}` не выполняет DELETE; mutation находится только за `admin:u:devdel:{telegram_id}:{device_id}`. Success возвращает в список устройств. В v4.25 не добавляется «Удалить все устройства».

###### `📱 Подключения → 🌐 IP-адреса`

Используется reviewed read-only endpoint pinned schema `/panel/api/clients/ips/{email}` (и только те соседние IP APIs, которые действительно нужны implementation). Contract JSON и tests обновляются до использования.

Текст:

~~~text
🌐 IP-адреса · {user_label}

Сейчас online:
{online_ips_or_нет}

История:
{ip_entries_with_last_seen_if_upstream_provides_it}
~~~

Правила:

- показываются только фактические данные upstream; бот не придумывает device identity по IP;
- если upstream даёт только set/list без timestamp, UI не подписывает его как хронологическую историю;
- v4.25 не добавляет локальное бессрочное хранение IP history и не создаёт новый surveillance-like ledger;
- IP не пишутся целиком в обычный audit/details только ради открытия экрана;
- отдельный `Clear IP history` в этот release не входит;
- Back возвращает в `📱 Подключения`.

###### `🔗 Подписка`

Новый parent callback: `admin:u:subscription:{telegram_id}`.

Текст:

~~~text
🔗 Подписка · {user_label}

ID: {masked_sub_id}
Статус: {active/disabled/expired presentation}
~~~

Клавиатура:

~~~text
[🔗 Открыть ссылку]
[📋 Показать URL]
[📱 QR-код]
[🔐 Перевыпустить ссылку]
[⬅ Пользователь]
~~~

- `Открыть ссылку` использует Telegram URL button только для авторизованного admin view;
- `Показать URL` переиспользует существующий `adminsub:{telegram_id}` либо эквивалентный read-only screen;
- URL и `sub_id` считаются secret-like customer credentials: они не попадают в audit/details/logs;
- QR генерируется **локально** из subscription URL; внешние QR services запрещены, чтобы не раскрывать credential третьей стороне;
- если QR требует отдельного media message, основной admin panel state и кнопка возврата не теряются; generated QR не сохраняется как постоянный файл;
- `🔐 Перевыпустить ссылку` использует существующий admin-only ask/run contract `admin:u:subrotateask:* → admin:u:subrotaterun:*`.

Confirmation rotation:

~~~text
⚠️ Перевыпустить ссылку подписки?

Старая ссылка перестанет работать.
Пользователю потребуется новая ссылка подписки.

[🔐 Перевыпустить]
[✖ Отмена]
~~~

Success показывает новый URL только авторизованному оператору и возвращает в `🔗 Подписка`.

###### `💳 Платежи`

Новый callback: `admin:u:payments:{telegram_id}`, privilege `payments.view`.

Это read-only filtered view существующей payment ledger; финансовые write-actions не дублируются в User Management.

Текст:

~~~text
💳 Платежи · {user_label}

Всего: {count}
Оплачено: {paid_count}

Суммы оплаченных:
{amount_by_currency}

Последние операции:
{status} {date_msk} · {amount} · {plan_or_—}
...
~~~

Если платежи в разных валютах, суммы группируются по currency; нельзя складывать EUR и USD в одно число.

Клавиатура:

~~~text
[📋 Все платежи]
[⬅ Пользователь]
~~~

При необходимости pagination открывает user-scoped список. Карточка конкретного платежа использует context-aware callback, например `admin:u:payment:{telegram_id}:{payment_id}`, чтобы `⬅ Платежи` возвращал именно в историю текущего пользователя. Data source — существующая таблица `payments.telegram_id`; новая финансовая ledger не создаётся.

###### `🧾 Активность`

Новый callback: `admin:u:activity:{telegram_id}`, privilege `monitoring.view`.

Это filtered view существующего `audit_log`. Для current user actions primary filter использует `target_type='user'` и техническую user identity; implementation должен учесть существующие исторические action records, не привязываясь к `display_name`.

Текст:

~~~text
🧾 Активность · {user_label}

Сегодня

18:31 · {actor}
🚀 Безопасное согласование
{safe_summary}

18:25 · {actor}
💎 Изменён тариф
{old} → {new}

...
~~~

Timeline включает релевантные user mutations: Plan, Server Group, expiry, traffic limit/reset, IP limit, enable/disable, manual Inbound attach/detach, safe/strict reconcile, subscription rotation, display name/note, device revoke и другие user-targeted audited actions.

Правила:

- это presentation/filter existing audit, не второй журнал;
- secret values, subscription URL/`sub_id`, full HWID и другие credentials не реконструируются из details;
- timestamps отображаются в MSK;
- pagination/«Показать ещё» сохраняет user context;
- Back возвращает в карточку пользователя.

###### `✏️ Профиль`

Новый parent callback: `admin:u:profile:{telegram_id}`.

Текст:

~~~text
✏️ Профиль · {user_label}

Имя:
{display_name_or_не_задано}

Email:
{email}

Telegram ID:
{telegram_id}

Заметка:
{note_or_—}
~~~

Клавиатура:

~~~text
[✏️ Изменить имя]
[📝 Изменить заметку]
[⬅ Пользователь]
~~~

Существующие `admin:u:name:*` и `admin:u:note:*` сохраняют validation/audit semantics. Email и Telegram ID read-only: этот release не вводит rename machine identity.

###### `⚙️ Ещё действия`

Новый callback: `admin:u:more:{telegram_id}`.

Экран консолидирует mutation shortcuts / danger zone, но не создаёт новые backend semantics:

~~~text
⚙️ Ещё действия · {user_label}

[⛔ Отключить пользователя]   # если включён
[✅ Включить пользователя]    # если отключён
[♻️ Сбросить трафик]
[🔐 Перевыпустить подписку]
[⚠️ Строгое согласование]
[🗑 Удалить пользователя]
[⬅ Пользователь]
~~~

Кнопки показываются по текущему status и privilege. `Reset`, rotation и strict reconcile ведут в те же canonical confirmation screens, что тематические разделы; duplicate backend handler не создаётся.

###### Enable / Disable

Disable переводится из one-click mutation в confirmation flow:

~~~text
⛔ Отключить пользователя?

{user_label}
Email: {email}

Доступ пользователя будет отключён,
но запись и настройки сохранятся.

[⛔ Отключить]
[✖ Отмена]
~~~

Для stale compatibility существующий `admindisable:{telegram_id}` может стать ask-screen, а mutation переносится на новый `admindisablerun:{telegram_id}`.

Enable аналогично:

~~~text
✅ Включить пользователя?

{user_label}

[✅ Включить]
[✖ Отмена]
~~~

Existing `adminenable:{telegram_id}` может стать ask-screen, mutation — `adminenablerun:{telegram_id}`. Success возвращает в карточку пользователя.

###### Удаление пользователя

Сохраняется существующий двухшаговый `admindelask:* → admindel:*`.

Confirmation:

~~~text
🗑 Удалить пользователя

{user_label}
Email: {email}
Telegram ID: {telegram_id}

Будут удалены пользователь и его доступ
согласно текущему безопасному delete workflow.

Это действие необратимо.

[🗑 Удалить пользователя]
[✖ Отмена]
~~~

Existing remote-before-local safety semantics не ослабляются. После подтверждённого удаления result screen ведёт в `Пользователи`; Cancel возвращает в карточку пользователя.

###### Массовые действия

Bulk selection остаётся отдельным flow от карточки пользователя. Selection screen сохраняет pagination и выбранные IDs в FSM, callback identity — `telegram_id`.

Target actions:

~~~text
☑️ Выбрано: {count}

[💎 Назначить тариф]        [🗂 Назначить группу]
[➕ +30 дней]               [📅 Установить срок]
[📦 Лимит трафика]         [🚀 Согласовать]
[✅ Включить]               [⛔ Отключить]
[♻️ Сбросить трафик]
[⬅ К выбору]
[✖ Закрыть]
~~~

Semantics:

- Plan assignment и Server Group assignment изменяют только соответствующий profile state и не скрывают remote provisioning;
- custom expiry/traffic limit используют bounded FSM input и explicit preview/confirmation перед mass mutation;
- `🚀 Согласовать` использует `ProvisioningEngine.provision_many(..., strict=False)`, а не legacy bulk attach-all;
- bulk strict reconcile в v4.25 **не добавляется**: destructive detach нескольких пользователей требует отдельного product/security decision;
- enable/disable/reset сохраняют existing bulk primitives, но confirmation показывает число выбранных пользователей;
- partial failure не останавливает обработку остальных пользователей, а result summary явно разделяет success/failed/unknown там, где backend может доказать разные outcomes;
- audit не перечисляет secret data и не должен без необходимости сохранять полный список email в одной строке.

###### Callback / navigation contract

Implementation может сохранить существующие identifiers, где это не ухудшает semantics. Целевые parent routes:

| Экран | Callback | Parent / Back |
| --- | --- | --- |
| Пользователи | `admin:users` | `admin:home` |
| Пользователь | `admin:u:{tg_id}` | `admin:users` |
| Тариф | `admin:u:plan:{tg_id}` | пользователь |
| Срок | `admin:u:expiry:{tg_id}` | пользователь |
| Трафик | `admin:u:traffic:{tg_id}` | пользователь |
| Доступ | `admin:u:access:{tg_id}` | пользователь |
| Группа серверов | `admin:u:group:{tg_id}` | Доступ |
| Согласование | `admin:u:prov:{tg_id}` | Доступ |
| Inbounds | `admin:u:inbounds:{tg_id}` | Доступ |
| Параметры доступа | `admin:u:accesscfg:{tg_id}` | Доступ |
| Подключения | `admin:u:connections:{tg_id}` | пользователь |
| Устройства | `admin:u:devices:{tg_id}` | Подключения |
| Устройство | `admin:u:device:{tg_id}:{device_id}` | Устройства |
| IP-адреса | `admin:u:ips:{tg_id}` | Подключения |
| Подписка | `admin:u:subscription:{tg_id}` | пользователь |
| Платежи | `admin:u:payments:{tg_id}` | пользователь |
| Активность | `admin:u:activity:{tg_id}` | пользователь |
| Профиль | `admin:u:profile:{tg_id}` | пользователь |
| Ещё действия | `admin:u:more:{tg_id}` | пользователь |

Все callback payloads обязаны укладываться в Telegram 64-byte limit. IDs берутся только из backend-resolved context; callback payload не является authorization/ownership proof.

Общие navigation rules:

- detail screen всегда возвращает в зафиксированный parent, а не в `admin:home` напрямую;
- FSM `✖ Отмена` возвращает в экран, из которого был начат input;
- confirmation `✖ Отмена` возвращает в карточку/подраздел без mutation;
- после delete result возвращает в список удалённой сущности;
- после device revoke result возвращает в `Устройства`;
- после Plan/expiry/traffic/IP update result возвращает в соответствующий detail screen;
- после safe/strict reconcile result предлагает `⬅ Согласование` или `⬅ Доступ`, но не создаёт dead end;
- read failure не должен уничтожать доступ к Back;
- progress screen state-changing operation может временно скрыть action buttons, если повторный click создаёт риск duplicate mutation.

###### Data/API changes

Минимальные backend additions v4.25:

- user-scoped payment query/pagination поверх существующей `payments.telegram_id`, без новой payment schema;
- user-scoped audit query/pagination поверх существующего `audit_log`, без второго audit storage;
- reviewed `XUIClient` methods + pinned OpenAPI contract entries для HWID list/delete-one и client IP read endpoints;
- локальный QR renderer/library допустим только без передачи subscription URL внешнему сервису;
- search/pagination helpers для users;
- при необходимости небольшие shared presenter/formatter helpers, чтобы card/list labels не расходились.

По умолчанию v4.25 **не требует новой SQLite migration**. Если implementation обнаружит реальную необходимость persistence, она оформляется только через existing forward-only migration framework и должна быть обоснована в implementation PR; UI scope сам по себе не является причиной хранить копии HWID/IP history.

###### Что намеренно не входит в v4.25

- публичный Client Portal и customer self-service;
- смена технического 3x-ui email/machine identity;
- массовый strict reconcile;
- «удалить все HWID устройства»;
- локальная бессрочная IP/device telemetry history;
- новый payment state machine/provider webhook — это v5 commerce scope;
- привязка User/Audience Groups к VPN provisioning;
- новый role model или custom per-admin permissions;
- возврат legacy attach-all sync под новым названием.

###### Regression / acceptance contract

Implementation PR должен добавить/обновить tests как минимум для:

1. точной структуры main user card keyboard и всех parent/Back paths;
2. privilege catalog parity для каждого нового callback; unknown route fail-closed;
3. role-aware visibility mutation buttons;
4. search по Telegram ID/email/display name и pagination списка >40 пользователей;
5. create-user duplicate detection, 3x-ui recovery path и отсутствие duplicate creation при uncertain mutation outcome;
6. сохранения machine identity при изменении display name/Plan/Group;
7. expiry `+30`, date-only MSK semantics и возврата в экран срока;
8. traffic limit/unlimited/reset confirmation и возврата в экран трафика;
9. safe/strict reconcile semantics и точного parent `Доступ`;
10. manual Inbound toggle и last-managed-Inbound safety;
11. отсутствия visible `Синхронизировать Inbounds`, `Синхронизировать всех` и legacy bulk attach-all action;
12. stale legacy sync callbacks как non-mutating redirect;
13. VLESS Flow sync без attach/detach Inbounds;
14. pinned 3x-ui OpenAPI contract для HWID/IP endpoints;
15. device list/detail и delete-two-step: первый callback не выполняет mutation;
16. IP screen не называет IP физическим устройством и не создаёт local history;
17. subscription URL/`sub_id` redaction из audit/logs и local-only QR generation;
18. user-scoped payments, multi-currency summary и отсутствие payment write-actions в user card;
19. user-scoped audit timeline и отсутствие secret reconstruction;
20. enable/disable confirmation, user delete confirmation и correct post-action parent;
21. bulk Plan/Group/expiry/traffic/safe-reconcile behavior и partial-failure summary;
22. callback payload length <= 64 bytes;
23. one-message admin navigation/FSM cleanup без dead ends;
24. MSK timestamps на новых operator-facing absolute dates.

Production acceptance после публикации `v4.25.0` должен пройти минимум под `Read-only`, `Support` и `Administrator` test accounts:

- открыть список, поиск, pagination и карточку пользователя;
- пройти каждый read-only подраздел и Back-chain до `Пользователи`;
- изменить display name/note и проверить неизменность email/`telegram_id`/`sub_id`;
- назначить Plan и Server Group, применить параметры тарифа и выполнить safe reconcile;
- вручную attach/detach test Inbound и проверить предупреждение о policy drift;
- выполнить strict reconcile на контролируемом test user с известным extra Inbound;
- изменить expiry/traffic/IP limit, reset traffic, disable/enable;
- открыть HWID devices/IP data на test user; удалить одно test device через confirmation и проверить post-condition;
- открыть subscription URL/QR, выполнить rotation на test user и подтвердить invalidation старой ссылки;
- проверить user-scoped payments/activity;
- выполнить несколько bulk actions и safe reconcile для test cohort;
- открыть stale legacy sync callback из заранее сохранённого сообщения и подтвердить отсутствие attach-all mutation;
- проверить базовый bot/DB/3x-ui health после smoke.

Acceptance считается закрытым только если navigation contract принят на Telegram Desktop и mobile, privilege boundaries подтверждены, legacy sync paths не выдают лишний доступ, а новые HWID/IP calls соответствуют pinned 3x-ui contract.


##### v4.26.0 — Node Drain / graceful traffic evacuation

**Статус: ⬜ Запланировано на `v4.26.0`.**

Цель — добавить управляемый вывод direct-ноды из пользовательского VPN-трафика перед обслуживанием, миграцией или decommission, не смешивая три разные операции: control-plane maintenance, graceful drain и destructive stop.

Текущий `🛠 Обслуживание` сохраняет существующую семантику: Master ставит node `enable=false` и перестаёт использовать её для новых provisioning/sync операций, но Xray и Inbounds продолжают работать, поэтому уже назначенные пользователи могут продолжать подключаться. `Drain` должен быть отдельным явным workflow и не менять эту семантику задним числом.

Целевая модель:

~~~text
🟢 В работе
    │
    ├─ 🛠 Обслуживание
    │     control plane pause
    │     пользовательский traffic не выключается
    │
    └─ 🚧 Вывести из трафика
          ↓
       draining
          ↓
       drained
          ↓
       optional Owner-only Stop Xray / Stop service
~~~

Обязательный safety contract:

- Drain применяется только к direct node с stable `node_id`; transitive/неоднозначные targets не мутируются.
- Старт Drain сначала блокирует новые назначения на target node через существующую maintenance/control-plane primitive или эквивалентную fail-closed блокировку.
- Перед пользовательскими mutations строится read-only review: затронутые пользователи, Inbounds target-ноды, доступные policy alternatives, blockers и оценка remaining work.
- Для каждого затронутого пользователя действует attach-before-detach: сначала безопасно обеспечиваются альтернативные Inbounds согласно текущим Plan / Server Group / ProvisioningPolicy, и только после доказанного post-condition допускается detach Inbounds выводимой ноды.
- Нельзя оставлять клиента без единого рабочего Inbound. Пользователь без подтверждённой альтернативы становится blocker и не переводится автоматически.
- Drain не должен выполнять legacy attach-all и не должен обходить `ProvisioningEngine`; policy остаётся источником ожидаемого доступа.
- Активные Xray-сессии не обрываются специально. После detach/обновления конфигурации пользователь может оставаться на уже установленной сессии до reconnect/timeout; это отображается как нормальная graceful семантика, а не как ошибка.
- `drained` означает, что бот доказал отсутствие управляемых пользовательских назначений на Inbounds target-ноды либо явно показывает оставшиеся blockers. Нельзя объявлять success только по `node.enable=false`.
- Drain **никогда автоматически не вызывает** `Stop Xray` или `Stop service`. Эти destructive Owner-only операции сохраняют отдельный privilege/confirmation boundary.
- Отмена/возврат ноды в работу не выполняет слепой reverse replay старых attachments. Нода снова становится eligible, а нужные назначения восстанавливаются обычным policy-based reconcile.
- Batch mutations выполняются bounded и последовательно либо через существующий безопасный bulk primitive; `failed` и `unknown` различаются, state-changing запрос после неопределённого исхода автоматически не повторяется.
- Состояние drain/job переживает restart: незавершённый workflow после рестарта не продолжается автоматически и требует read-only verification/operator decision.
- Все этапы audit-friendly; в audit/jobs не попадают credentials, subscription URL, `sub_id` или другие secret-like данные.

Operator UX:

~~~text
/admin
└─ Инфраструктура
   └─ Операции с нодами
      └─ 🚧 Вывести из трафика
          ├─ выбрать direct node
          ├─ preflight / affected users / blockers
          ├─ confirmation
          ├─ progress
          └─ result: drained | partial | failed | unknown
~~~

Карточка ноды и Fleet Health должны визуально различать как минимум `maintenance`, `draining` и `drained`; нельзя показывать `drained`, пока Xray просто продолжает обслуживать пользователей с прежними assignments.

RBAC / destructive boundary:

- read-only status/progress Drain — `fleet.view` / Read-only+;
- start/cancel/continue controlled Drain — `fleet.manage` / Administrator+;
- `Stop Xray` и `Stop service` остаются Owner-only и не становятся частью Admin-level Drain confirmation.

Regression / acceptance minimum:

1. maintenance по-прежнему не трактуется как traffic cutoff;
2. node в draining немедленно исключается из новых provisioning targets;
3. attach-before-detach и last-working-Inbound safety;
4. blocker при отсутствии policy alternative;
5. no legacy attach-all;
6. no automatic Stop Xray/service;
7. restart/interrupted job не replay'ит mutation;
8. failed/unknown outcomes и read-back verification;
9. RBAC/callback catalog fail-closed;
10. audit без secrets;
11. production smoke на контролируемой test node/user cohort: новые назначения прекращаются, тестовый пользователь получает альтернативу до detach, после refresh/reconnect target node исчезает из рабочего пути, базовый health остаётся green.

Конкретный способ определения remaining active sessions должен использовать только реально доступные 3x-ui/Xray данные и документировать их ограничения. Online/IP наблюдение не должно выдаваться за точный учёт физических устройств или гарантированный session drain, если upstream этого не доказывает.

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

#### Cheburcheck Probe fleet для региональных проверок

**Статус: ⬜ Отложено. Не является блокером `v4.23.3`, `v4.24.0` или обязательным условием перехода к `v5.0.0`.**

Текущий minimal self-hosted Cheburcheck runtime (`website + PostgreSQL`) достаточен для static list/ASN diagnostics, но не даёт реальных региональных результатов без подключённых Probe reporters. Bot начиная с `v4.23.3` должен честно показывать отсутствие active scanners и не эмулировать regional data.

Цель отложенного улучшения — добавить собственный controlled Probe fleet без смешения его lifecycle с Telegram-ботом.

Рекомендуемая реализация в два этапа:

1. **Pilot.**
   - добавить central RMQTT к существующему self-hosted Cheburcheck runtime;
   - связать `website` с broker через отдельный `MQTT_ADMIN_TOKEN`;
   - предоставить probes только authenticated MQTT over WebSocket/TLS endpoint;
   - зарегистрировать один controlled Probe reporter с отдельными `PROBE_ID` / `PROBE_TOKEN` и metadata `region / ASN / provider`;
   - запустить probe на отдельном Linux/Docker host с outbound-only connectivity к broker и только необходимым `NET_RAW` capability;
   - подтвердить end-to-end path: Telegram check → Cheburcheck probe task → MQTT → reporter result → SSE → compact regional summary.

2. **Fleet.**
   - после успешного pilot развернуть несколько независимых reporters в разных сетях/регионах; ориентир для полезного первого fleet — минимум 3–5 probes, а не несколько probes в одном дата-центре;
   - выбирать точки так, чтобы они измеряли действительно разные network paths/ISP/regions, а не только разные VPS одного provider-а;
   - добавить health/readiness для online/offline reporters, `last_connected_at`, версию probe и безопасный operational inventory;
   - определить lifecycle credential rotation/revocation для каждого reporter отдельно;
   - зафиксировать controlled update/rollback procedure для probe packages/images;
   - при необходимости расширять fleet постепенно, не меняя Telegram result contract.

Security / operational boundary:

- RMQTT не должен принимать anonymous/unrestricted clients;
- каждый reporter имеет отдельные ID/token; token не переиспользуется между probes и не совпадает с bot/3x-ui/Host Control/Deploy Agent credentials;
- broker/admin token и probe tokens не хранятся в Telegram, Git или bot SQLite;
- bot не получает shell/container control над RMQTT или Probe hosts и только читает Cheburcheck API/SSE;
- Probe hosts не требуют публичных inbound management ports для обычной работы; основной data path — исходящее WSS/MQTT соединение;
- capability `NET_RAW` выдаётся только probe process/container и не означает общий privileged/root runtime;
- отсутствие части fleet или timeout отдельных reporters не должно превращать static Cheburcheck verdict в ошибку;
- UI показывает только фактически полученные regional responses и явно различает `нет активных сканеров`, `нет ответов` и `regional upstream unavailable`;
- backup/recovery для broker config, reporter registry/tokens и probe deployment является отдельной infrastructure responsibility и не включается автоматически в Full Backup Telegram-бота.

Этот пункт считается отдельной infrastructure-задачей средней сложности. Сам probe runtime лёгкий, но production-ready fleet требует broker/TLS/auth, нескольких независимых точек наблюдения, credential lifecycle, monitoring и runbook'ов.

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
