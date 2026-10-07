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

**Статус: ✅ Выполнено и принято в production; off-site recovery drill завершён 2026-10-05.**

Encrypted off-site backup опубликован и развернут в production как `v4.18.0` (release commit `1cc730c5929ba8b2fe1152a0db1ade4b1aaa21f9`). Базовый runtime acceptance пройден: exact tag/SHA, container, app version, health, DB и 3x-ui connectivity подтверждены. Full Backup использует checksummed manifest schema 2, S3-compatible transport шифрует canonical archive client-side через AES-256-GCM, local и off-site outcomes записываются раздельно (`backup.daily`/`backup.manual` и `backup.offsite`), после upload обязателен remote download/decrypt/SHA/deep-validation round trip, retention ограничен fixed prefix, а host-side recovery CLI скачивает и проверяет latest external copy перед существующим bootstrap restore flow. Feature выключена по умолчанию и не открывает Telegram доступ к bucket/object key/credentials/filesystem path.

**Production acceptance завершён 2026-10-05:** на реально внешнем S3-compatible target с dedicated credentials и отдельно сохранённым recovery encryption key создан manual Full Backup; `backup.offsite` завершился `success`, а обязательный upload → HEAD → download → AES-GCM authentication/decrypt → SHA-256/size → повторный deep validation round trip подтверждён. На отдельном recovery VPS host-side CLI получил latest canonical object и завершился `OFFSITE_RECOVERY_OK`; `manifest.version=4.26.4`. Дополнительный bootstrap smoke восстановил `bot.env` и `bot.sqlite3`, поднял container с `APP_VERSION=4.26.4`, Health/DB `ok`; финальный generic upstream TCP probe из изолированного recovery VPS получил timeout, что относится к подготовке полного replacement Master/network path и не входит в критерий этого off-site gate. После smoke recovery bot остановлен, production Master возвращён с Health/DB/3x-ui connectivity `ok`, временное recovery окружение очищено. Секреты bucket credentials/encryption key не публиковались в Telegram/chat/Git.

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
7. off-site backup и проверяемый restore path — ✅ выполнено в `v4.18.0`; production off-site recovery drill завершён 2026-10-05 (`backup.offsite=success`, remote round trip, isolated host-side `OFFSITE_RECOVERY_OK`);
8. 3x-ui API compatibility / OpenAPI contract gate — ✅ выполнено в `v4.17.0`.
9. финальный Admin UI consistency patch после production acceptance `v4.20.4` — ✅ выполнено и принято в production в `v4.20.5`.
10. UI-04: симметрия Master/direct-node health summary на экране `Мониторинг → Состояние системы` — ✅ выполнено и принято в production в `v4.20.6`.
11. единая operator-facing терминология `Inbound` / `Inbounds` без гибридных форм с апострофом — ✅ выполнено и принято в production в `v4.20.7`.
12. финальная капитализация `Inbound` в operator-facing edit/clone/delete/error/help flows — ✅ выполнено и принято в production в `v4.20.8`.
13. post-acceptance operator-facing UI cleanup без изменения behavior/storage semantics — ✅ опубликовано в `v4.20.9`; desktop layout follow-up закрыт в `v4.20.10`.
14. compact Inbound keyboard follow-up после production smoke `v4.20.9` — ✅ выполнено и принято в production в `v4.20.10`.
15. редактируемое display name пользователя без изменения 3x-ui machine identity — ✅ выполнено и принято в production в `v4.21.0`; follow-up fixes закрыты и приняты в production в `v4.21.2`.
16. независимые User/Audience Groups для будущей сегментации Client Portal — ✅ выполнено и принято в production в `v4.22.0`.
17. Cheburcheck integration как отдельный read-only diagnostics service/tool — ✅ закрыто в `v4.23.3`: базовая интеграция принята в production в `v4.23.1`, findings `v4.23.2` закрыты hotfix-релизом `v4.23.3`; дальнейший Cheburcheck Probe fleet вынесен в «Отложенные инфраструктурные улучшения» и не блокирует следующий feature release.
18. PackBot-compatible website monitoring и diagnostics, нативно встроенные в текущую архитектуру — ✅ выполнено и принято в production в линии `v4.24.x`; smoke `v4.24.0` выявил targeted findings, закрытые и повторно проверенные в `v4.24.1`.
19. целостный User Management и follow-up линия `v4.25.x` — ✅ выполнено; релизы `v4.25.0–v4.25.8` опубликованы, развёрнуты и приняты в production, Streisand при активном HWID limit остаётся зафиксированным expected limitation.
20. graceful Node Drain / вывод direct-ноды из пользовательского трафика без смешения с maintenance или destructive Stop Xray — ✅ `v4.26.0` опубликован и развёрнут; navigation fix #211 выполнен и принят в production в `v4.26.1`; controlled state-changing production acceptance на безопасной test node/user cohort завершён 2026-10-01, issue #208 закрыт как `completed`.
21. финальный repository/public-release audit после feature freeze — ✅ завершён PASS 2026-10-07; final report: [`docs/audits/v4-final-audit-2026-10-05.md`](audits/v4-final-audit-2026-10-05.md). A-001–A-013 закрыты; repository опубликован, PVR включён, final secret/history/Actions-storage gates пройдены, а A-007 дополнительно технически закрыт enforced branch/tag rulesets; `v4.26.8` является финальной audited v4 baseline для перехода к `v5.0.0`.
22. исправление неверного ввода Inbound/шаблонов — ✅ выполнено, опубликовано и принято в production в `v4.25.7`; targeted smoke и final health — PASS.
23. исправление навигации Clone Inbound (`✖ Отмена` на выборе target server возвращает в исходный Inbound) — ✅ выполнено и принято в production в `v4.25.8`; issue #202 закрыт как `completed`.
24. защита DB-backed Owner от случайного self-demotion одним нажатием — ✅ выполнено и принято в production в `v4.25.8`; issue #204 закрыт как `completed`.

Отдельный release-specific PR может уточнить реализацию каждого пункта, но перенос любого из них за границу v5 должен быть явным решением с обновлением этого roadmap, а не неявным следствием начала Client Portal.

#### Желательно закрыть до финальной заморозки v4.x

Эти работы не меняют security boundary сами по себе, но уменьшают архитектурный долг перед существенным ростом v5.x.

Зафиксированный порядок финального закрытия v4.x:

**Текущий статус после off-site acceptance, freeze и public-release audit:**

1. ✅ production drill encrypted off-site backup/restore завершён 2026-10-05;
2. ✅ **final v4 feature freeze объявлен 2026-10-05**; после этой точки новые функции в v4.x не добавляются;
3. ✅ **Активный gate:** провести полный финальный repository/public-release audit — завершён PASS 2026-10-07;
4. ✅ audit findings A-001–A-013 закрыты; required regression/production acceptance завершён, A-007 post-public governance hardening технически закрыт;
5. ✅ `v4.26.8` опубликован, развёрнут и принят как финальная audited v4 baseline; repository public, PVR active;
6. ▶ **Следующий product track:** `v5.0.0 — Client Portal`.

Все обязательные v4 gates закрыты. Final v4 feature freeze действует с 2026-10-05 как historical boundary: новый product scope в v4.x не возвращается. После PASS public-release audit новые customer-facing функции реализуются только в v5.x; v4.x остаётся только для действительно необходимых security/reliability/data-integrity hotfixes.

`v4.26.9` готовится как narrowly-scoped operational hotfix для восстановления browser subscription links после обнаруженного compatibility defect в `/compat/`. Релизный tag также включает уже слитый v5 pilot foundation из `main`, но не снимает allowlist, не включает production checkout и не считается публичным запуском Client Portal.

Ниже сохранён исторический порядок уже выполненных и оставшихся этапов:

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
13. отдельным релизом `v4.24.0` интегрировать PackBot-compatible monitoring/diagnostics; targeted production findings закрыть patch-релизом `v4.24.1`, а финальный acceptance линии проводить на `v4.24.1`;
14. User Management и follow-up линия `v4.25.0–v4.25.8` завершены и приняты в production; линия `v4.25.x` закрыта;
15. отдельным релизом `v4.26.0` добавить graceful Node Drain / controlled traffic evacuation для direct nodes;
16. controlled state-changing Node Drain production smoke на безопасной test node/user cohort — ✅ выполнен 2026-10-01; issue #208 закрыт как `completed`;
17. отдельным patch-релизом `v4.26.2` добавить read-only Dashboard Attention summary (`⚠️ Требует внимания`);
18. отдельным patch-релизом `v4.26.3` добавить read-only Attention Center drill-down и canonical deep-links;
19. закрыть production navigation finding #226 отдельным fix-релизом `v4.26.4`, затем завершить production acceptance #217;
20. data-plane address hardening #219 — ✅ закрыт 2026-10-01: для v4.x зафиксирован operator-managed per-Inbound contract `shareAddrStrategy=custom` + явный `shareAddr`; отдельная node-level `data_plane_address` metadata до freeze не вводится, automatic DNS→IP persistence запрещён;
21. ✅ production drill encrypted off-site backup/restore завершён 2026-10-05;
22. ✅ **final v4 feature freeze объявлен 2026-10-05**: после этой точки новые функции в v4.x не добавляются;
23. ✅ **активно:** после feature freeze провести полный финальный repository/public-release audit по всему продукту — завершено PASS 2026-10-07;
24. ✅ findings A-001–A-013 закрыты с regression/production/governance evidence; финальная audited baseline — `v4.26.8`;
25. ✅ audit gate закрыт, repository опубликован; реализация `v5.0.0` теперь открыта как следующий product track.

Feature freeze означает запрет на новый product scope, а не запрет исправлений. Security/reliability/data-integrity findings, найденные финальным аудитом, должны быть закрыты до финального v4 release; необходимые regression tests, docs и production acceptance остаются разрешены.

Pre-freeze gates закрыты: Controlled Node Drain production acceptance #208 и data-plane hardening #219 закрыты 2026-10-01, encrypted off-site backup/restore production acceptance закрыт 2026-10-05. Финальный аудит выполняется **после** freeze, чтобы проверяемый codebase больше не менялся функционально во время review.

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

**Статус: ✅ Production smoke выполнен для `v4.21.1`; найденные runtime/UI follow-up закрыты и приняты в `v4.21.2`.**

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

**Статус: ✅ Production smoke `v4.23.2` выполнен; найденные gaps закрыты и приняты hotfix-релизом `v4.23.3`.**

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

**Статус: ✅ Закрыто. `v4.23.3` опубликован и принят; acceptance линии Cheburcheck `v4.23.x` завершён.**

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

Итог acceptance: hotfix `v4.23.3` закрывает production findings compact result (`CDN`, domain/IP ASN enrichment и truthful regional probe status). Полноценный multi-region Probe fleet не входит в acceptance этого релиза и зафиксирован отдельно в разделе «Отложенные инфраструктурные улучшения».

##### v4.24.0 — Мониторинг сайтов и web diagnostics

**Статус: ✅ Production smoke `v4.24.0` выполнен; найденные findings закрыты в `v4.24.1`, и acceptance линии `v4.24.x` завершён.**

Runtime scope завершён и опубликован: schema v4/v5 website monitoring, native repository/state machine, SSRF-safe outbound boundary, bounded scheduler/incident notifications, watcher-scoped pause/resume, core admin UI, admin-only global target removal и one-off/contextual diagnostics (WHOIS/DNS/HTTP/redirect/CMS/SEO/optional PageSpeed/Sitemap/URL-list/QR) реализованы. Production smoke `v4.24.0` выявил три narrowly-scoped finding; они исправлены в опубликованном `v4.24.1`, после чего targeted smoke линии `v4.24.x` завершён.

Цель — нативно перенести полезное поведение `vladpak1/packbot` в текущий Admin Control Plane без встраивания отдельного PHP Telegram bot, MySQL runtime, webhook stack или второй application database.

Reviewed upstream contract:

- project: `vladpak1/packbot`;
- reviewed revision: `3c4a5bb29626f8b3e28056bd52cd94fdce9f3c1a`;
- license: MIT;
- copyright: `Copyright (c) 2023 vladpak1`;
- PackBot используется как behavior/reference implementation; новая реализация остаётся Python/aiogram/SQLite-native и использует существующие jobs/audit/alerts/configuration primitives проекта.

Существенно адаптированный/перенесённый код и алгоритмы сопровождаются required MIT notice/source attribution в `THIRD_PARTY_NOTICES.md`, а release notes явно указывают upstream reference. В Telegram result cards постоянная строка `Источник: PackBot` не нужна: данные получаются нашей реализацией, а не внешним PackBot backend.

###### Release boundary

- scope относится только к `/admin → Мониторинг`; публичный `/start` и Client Portal не расширяются;
- каноническое display name раздела — `🌐 Мониторинг сайтов`;
- PackBot не запускается как sidecar/service и не получает bot token;
- PHP/Composer/MySQL не становятся production dependencies;
- все persistent изменения выполняются только через versioned SQLite migrations;
- новые callbacks регистрируются в централизованном privilege catalog и неизвестные routes остаются fail-closed;
- реализация синхронно обновляет `docs/UI_STYLE.md`, `README.md`, `THIRD_PARTY_NOTICES.md`, migration docs/tests и `CHANGELOG.md`.

###### Каноническая навигация

~~~text
/admin
└─ 📈 Мониторинг
   ├─ 📊 Трафик
   ├─ 🟢 В сети
   ├─ 🩺 Состояние системы
   ├─ 🔎 Проверка блокировок
   ├─ 🌐 Мониторинг сайтов
   │  ├─ 📋 Сайты
   │  │  ├─ ➕ Добавить сайт
   │  │  └─ 🌐 Карточка сайта
   │  │     ├─ 🔄 Проверить сейчас
   │  │     ├─ 🩺 Диагностика
   │  │     ├─ 📜 История инцидентов
   │  │     ├─ ⏸ Приостановить / ▶️ Возобновить
   │  │     ├─ 🔔 Оповещения
   │  │     └─ 🗑 Удалить / отписаться
   │  ├─ 🛡 Все targets              ← Administrator+
   │  │  └─ 🗑 Глобальное удаление  ← двухшаговое
   │  └─ 🔎 Разовая диагностика
   │     ├─ 🌐 Домен
   │     │  ├─ WHOIS / возраст
   │     │  └─ DNS
   │     ├─ 🩺 Веб
   │     │  ├─ HTTP
   │     │  ├─ Redirect trace
   │     │  └─ CMS
   │     ├─ 🔍 SEO
   │     │  ├─ Индексация / robots / noindex
   │     │  └─ PageSpeed
   │     └─ 🧰 Утилиты
   │        ├─ Sitemap
   │        ├─ Список URL
   │        └─ QR
   ├─ 📜 Журналы
   └─ 🚨 Оповещения
~~~

`Мониторинг сайтов` имеет единственного parent — `Мониторинг`. Back/Cancel из add-site, diagnostics, incident history и utility FSM возвращает только в локальный website-monitoring context. Raw URL не кодируется в callback data; callbacks используют только stable numeric IDs / fixed action tokens.

Предварительный home screen:

~~~text
🌐 Мониторинг сайтов

Сайтов: {total}
🟢 Доступны: {up}
🔴 Недоступны: {down}
⚪ Не проверены: {unknown}

[📋 Сайты]            [➕ Добавить]
[🔎 Разовая диагностика]
[⬅ Мониторинг]
~~~

Карточка сайта:

~~~text
🌐 example.org

Статус: 🟢 доступен
HTTP: 200
Ответ: 184 мс
Последняя проверка: 2 мин назад
Инцидент: —

[🔄 Проверить сейчас] [🩺 Диагностика]
[📜 История]          [🔔 Оповещения]
[🗑 Удалить / отписаться]
[⬅ Сайты]
~~~

Status grammar обязана различать `up`, `suspect`, `down`, `unknown/checker_error` и disabled/paused state; локальная ошибка checker/network safety layer не выдаётся за подтверждённое падение сайта.

###### RBAC contract

Новых ролей не появляется.

- `website_monitoring.view` / минимум `Read-only`: home/list/card, incident history, one-off WHOIS/DNS/HTTP/redirect/CMS/SEO/Sitemap/URL-list/QR diagnostics и просмотр текущих notification settings;
- `website_monitoring.manage` / минимум `Support`: добавить сайт в persistent monitoring, подписаться/отписаться от site alerts, ручной `Проверить сейчас`, pause/resume собственной monitoring subscription;
- `website_monitoring.admin` / минимум `Administrator`: глобально удалить monitor target, когда на него ещё подписаны другие администраторы, и выполнять будущие global monitoring mutations;
- `Owner` не получает отдельный capability только из-за `v4.24.0`.

Keyboard privilege-aware: недоступная mutation-кнопка не показывается, но handler authorization остаётся обязательной независимо от UI visibility.

###### Ownership и deduplication

PackBot upstream хранит список owners внутри site record. В текущем проекте это адаптируется в нормализованную many-to-many модель:

- один canonical public URL существует как один monitor target;
- один target может иметь несколько admin-watchers по стабильному Telegram ID;
- повторное добавление того же canonical URL не создаёт второй background checker, а подписывает текущего администратора на существующий target;
- лимит применяется к числу targets/watch subscriptions текущего администратора; начальный parity default — не более **10**;
- удаление собственной подписки не удаляет target, пока существуют другие watchers;
- global removal target при наличии других watchers требует `website_monitoring.admin` и явного confirmation;
- alert delivery идёт только текущим watchers, имеющим право получать Telegram notifications; target ownership не используется как security identity для callback lookup.

###### Persistence model

Новые сущности создаются forward-only migration через существующий `schema_migrations` framework.

Минимальная логическая модель:

~~~text
website_monitors
- id
- canonical_url UNIQUE
- hostname
- enabled
- state: unknown | up | suspect | down
- last_check_at
- next_check_at
- last_http_status
- last_latency_ms
- last_error_kind
- consecutive_failures
- created_at
- updated_at

website_monitor_watchers
- monitor_id
- telegram_id
- notifications_enabled
- monitoring_enabled
- created_at
UNIQUE(monitor_id, telegram_id)

website_incidents
- id
- monitor_id
- opened_at
- resolved_at
- reason_kind
- first_http_status
- last_http_status
- alert_count
- last_alert_at

website_incident_notifications
- incident_id
- telegram_id
- kind: opened | repeat | recovered
- sequence
- sent_at
UNIQUE(incident_id, telegram_id, kind, sequence)
~~~

Raw response bodies, WHOIS payloads, sitemap XML и PageSpeed JSON не сохраняются как persistent monitoring state. Для основной карточки хранится только bounded normalized metadata. Incident history — источник истории availability; `v4.24.0` не обязан вводить неограниченный time-series storage каждого успешного check.

###### Monitoring state machine

PackBot behavior сохраняется по смыслу, но оформляется явной deterministic state machine:

~~~text
unknown
  ├─ success ───────────────→ up
  └─ candidate failure ─────→ suspect

up
  ├─ success ───────────────→ up
  └─ candidate failure ─────→ suspect

suspect
  ├─ recheck success ───────→ up
  ├─ confirmed failure ─────→ down + open incident + first alert
  └─ checker/internal error → previous stable state preserved

down
  ├─ confirmed failure ─────→ down + optional repeated alert
  ├─ success ───────────────→ up + close incident + recovery alert
  └─ checker/internal error → down preserved, no false recovery
~~~

Disabled/paused — отдельный lifecycle flag, а не health verdict.

Начальные parity defaults по reviewed upstream:

- normal check interval: **10 минут**;
- down-site check interval: **3 минуты**;
- confirmation recheck после candidate failure: **2 секунды**;
- response-time threshold: **5 секунд**;
- first repeated-alert interval: **30 минут**;
- после нескольких alerts следующий interval: **320 минут**;
- max monitored targets per admin: **10**.

Эти значения являются application defaults, а не Telegram-controlled arbitrary scheduler input. Изменение global defaults отдельной UI mutation в `v4.24.0` не требуется.

Candidate failure включает target-attributable timeout/DNS/TLS/connect failure или unhealthy HTTP result. Internal checker error, safety-policy rejection, local resource exhaustion и programming error не открывают site-down incident. Exact HTTP health rule фиксируется implementation tests; базовый parity ориентир — successful canonical/effective request с HTTP 200, как в reviewed upstream, при этом все redirects до canonical target проходят наш safety validation.

Scheduled loop использует persistent `next_check_at` + bounded worker concurrency. Restart не создаёт duplicate incident/alert: current state читается из SQLite, а notification journal делает first/repeat/recovery delivery идемпотентной на уровне recipient/kind/sequence. На каждый future poll не создаётся бесконечная durable job queue.

###### Outbound request safety layer

Все HTTP(S)-функции `v4.24.0` — monitor check, canonical/effective URL discovery, redirects, CMS, SEO, PageSpeed target validation, robots и Sitemap — обязаны использовать **один общий** safe outbound client.

Fail-closed требования:

- только `http://` и `https://`;
- arbitrary/custom ports запрещены; разрешены только стандартные 80/443;
- URL userinfo/credentials запрещены;
- hostname проходит IDNA normalization и length/syntax validation;
- до connect проверяются все A/AAAA answers; loopback, private/RFC1918, CGNAT, link-local, multicast, documentation/reserved/non-global ranges блокируются;
- известные cloud metadata destinations/hostnames блокируются отдельно;
- фактический connect привязывается к уже validated public address, чтобы validation/connect не расходились из-за DNS rebinding;
- каждый redirect заново проходит полный parse/DNS/address validation;
- environment proxy variables не могут неявно обойти destination policy;
- public diagnostics не получают route к private VPN/control-plane endpoints через supplied URL;
- response body читается streaming/bounded и не буферизуется без лимита;
- transport errors не логируют credentials/query secrets и не сохраняют raw body.

Начальные hard bounds:

- redirects: не более **5**;
- connect timeout: **3 s**;
- read timeout: **7 s**;
- total HTTP timeout: **10 s**;
- обычный response body: не более **1 MiB**;
- sitemap document: не более **2 MiB**;
- sitemap documents за одну операцию: не более **10**;
- URLs из sitemap: не более **5000**;
- background/manual outbound operations используют общий bounded concurrency limiter; один target не должен одновременно получать несколько scheduled checks.

WHOIS принимает только нормализованный domain и не позволяет пользователю задавать произвольный WHOIS server/port. DNS diagnostics принимает только domain/record-family inputs и не превращается в arbitrary DNS resolver client к указанному пользователем nameserver.

###### Diagnostics contract

`🔎 Разовая диагностика` не создаёт persistent monitor target без отдельного `Добавить в мониторинг`.

Domain:

- WHOIS: creation/expiration при доступности, вычисляемый возраст, bounded operator summary; полный raw WHOIS dump в Telegram не обязателен;
- DNS: bounded A/AAAA/CNAME/MX/NS/TXT summary с pagination/truncation, если records много.

Web:

- HTTP: final safe URL, status, latency, server/content-type и bounded headers subset;
- Redirect trace: максимум 5 hops, каждый hop safe-validated;
- CMS: best-effort detection; `не определена` отличается от transport failure.

SEO:

- indexability/robots/noindex — read-only summary;
- PageSpeed включается только при локально настроенном API key; отсутствие key отображается как disabled/unconfigured, а не ошибка сайта.

Utilities:

- Sitemap — bounded recursive parse по лимитам выше;
- URL list formatting/trimming — локальная операция без outbound requests;
- QR — локальная генерация для предоставленного текста/URL; remote logo fetching в scope `v4.24.0` не входит.

Screenshot/headless-browser diagnostics из README PackBot не входят в обязательный `v4.24.0`: это отдельный browser/runtime attack surface и требует отдельного решения, если когда-либо понадобится.

###### PackBot parity matrix

| PackBot capability | Решение `v4.24.0` |
| --- | --- |
| add/list/remove monitored sites | ✅ нативный parity через SQLite |
| owners нескольких пользователей | ✅ адаптация в many-to-many admin watchers |
| max sites per user | ✅ parity default 10 |
| periodic up/down intervals | ✅ parity 10 min / 3 min |
| second confirmation check | ✅ parity, 2 s |
| first/repeated/recovery alerts | ✅ с persistent incident/notification journal |
| incident history/statistics | ✅ incident history; без unbounded success time-series |
| WHOIS + domain age | ✅ |
| DNS records | ✅ bounded |
| HTTP/server response | ✅ через safe outbound client |
| redirect trace | ✅ max 5 hops |
| CMS detection | ✅ best effort |
| robots/noindex/indexability | ✅ |
| Google PageSpeed | ✅ optional при configured secret key |
| sitemap parsing | ✅ bounded: 10 docs / 5000 URLs |
| URL list formatting/trimming | ✅ local-only |
| QR generation | ✅ local-only |
| screenshots/headless browser | ⏭ вне обязательного scope `v4.24.0` |
| multilingual PackBot UI | ⏭ не переносится; canonical UI остаётся русским |
| PHP/MySQL/webhook runtime | ❌ не переносится |

###### Tests и acceptance

До release обязательны:

- migration tests с upgrade существующей schema и сохранением текущих данных;
- deterministic state-machine tests: first failure/recheck, false alarm, confirmed down, repeated down, recovery, restart during incident;
- notification idempotency per watcher;
- negative RBAC coverage для всех callbacks;
- SSRF suite для IPv4/IPv6/private/link-local/CGNAT/reserved/metadata, redirect-to-private и simulated DNS rebinding;
- hard-limit tests для redirects/body/sitemap/count/concurrency;
- fake HTTP/DNS/WHOIS/PageSpeed fixtures; CI не зависит от случайных публичных сайтов;
- navigation tests для Back/Cancel и отсутствие raw URL в callbacks;
- license/attribution regression: reviewed PackBot revision и MIT notice остаются в `THIRD_PARTY_NOTICES.md`.

Production acceptance после deployment:

1. `deploy-release.sh --status` подтверждает exact tag/version, `RestartCount=0`, Health/DB/3x-ui `ok`;
2. controlled public test target проходит add → initial up → manual check → diagnostics;
3. controlled failure проходит `up → suspect → down`, создаёт ровно один incident и first alert;
4. повторная проверка down target соблюдает repeat-alert cadence без alert storm;
5. recovery закрывает incident и отправляет ровно один recovery alert;
6. restart бота во время открытого incident не создаёт duplicate first/recovery alert;
7. private/local/metadata URLs и redirect-to-private блокируются;
8. concurrency/rate-limit smoke не создаёт unbounded queue;
9. optional PageSpeed без key остаётся корректно disabled;
10. после smoke повторяется базовый status/health check.

Operational closure линии `v4.24.x` достигнут: website monitoring и обязательные diagnostics работают через единый safe outbound boundary, incidents/alerts переживают restart без replay, PackBot attribution/parity соответствуют reviewed revision, а targeted findings `v4.24.0` подтверждены исправленными на deployed `v4.24.1`.


##### v4.24.1 — Hotfix diagnostics и IPv6

**Статус: ✅ Выполнено и принято в production в `v4.24.1`; acceptance линии `v4.24.x` закрыт.**

Production smoke `v4.24.0` подтвердил корректную работу contextual web diagnostics и навигации, но выявил три narrowly-scoped presentation/diagnostics/validation finding, которые не требуют изменения control-plane architecture:

1. WHOIS/RDAP absolute timestamps выводятся в raw RFC3339/UTC (`...Z`) вместо канонического operator-facing MSK.
2. Compact Cheburcheck card, введённая в `v4.23.2`, оказалась слишком агрессивно сокращена: backend продолжает получать/нормализовать IP, reverse DNS и дополнительные static check fields, но часть полезной operational detail намеренно перестала отображаться в Telegram card.
3. Website monitoring URL validation безопасно отклоняет `http://[::1]/`, но делает это через domain-name syntax branch до `ipaddress.ip_address()`. В результате блокируется не только loopback/non-global IPv6, но и любой public IPv6 literal, хотя downstream canonical URL logic уже поддерживает bracketed IPv6.

Scope `v4.24.1`:

**WHOIS/RDAP presentation**

- нормализовать `created_at` / `expires_at` RDAP timestamps в единый presentation helper;
- показывать absolute date/time в формате `DD.MM.YYYY HH:MM MSK` согласно `docs/UI_STYLE.md`;
- machine/RDAP timestamps не изменять и не сохранять в локальном времени;
- `Возраст: N дн` продолжает вычисляться от UTC instant и не зависит от presentation timezone;
- invalid/missing upstream timestamp остаётся `—`, без guess/parsing fallback;
- покрыть regression tests для `Z`, explicit offset и date rollover при переводе в MSK.

**Cheburcheck compact card detail**

Вернуть в основную карточку только нормализованные bounded static-check значения, которые реально присутствуют в upstream result:

- `IP` — resolved IP addresses для domain target; для direct IP target не дублировать очевидное значение без UX-пользы;
- `Reverse DNS` — только фактически полученные PTR/reverse lookup values;
- `Заблокированные подсети` — bounded summary фактически возвращённых subnet entries;
- `Домен из реестра` / `rkn_domain` — только когда upstream поле присутствует;
- `Размер подсети` / `subnet_size` — только когда применимо и поле присутствует;
- существующие `Сеть`, `РКН`, `CDN`, `Исключение CDN`, `ASN` и агрегированная строка `🌍 Регионы` сохраняются.

Output bounds:

- IP и Reverse DNS: показывать не более **5** значений каждого типа, затем `… ещё N`;
- blocked subnets: показывать не более **5** значений, затем `… ещё N`;
- строки/labels экранируются и ограничиваются по длине; raw upstream JSON/SSE payload в Telegram не выводится;
- отсутствие optional значения отображается только там, где поле является частью канонической карточки; не создавать длинные секции из сплошных `—`.

Regional probe boundary остаётся прежним:

- **не возвращать raw probe payload** в основную карточку;
- `🌍 Регионы` остаётся compact aggregate (`N ответов · 🟢 / 🔴 / 🟡`) либо честным состоянием `нет активных региональных сканеров / нет ответов / unavailable / not applicable`;
- если позже понадобится per-region drill-down, это отдельный bounded `🌍 Детали регионов` workflow, а не dump JSON/SSE в основной result.


**Website monitoring IPv6 literal validation**

- распознавать literal IPv4/IPv6 через `ipaddress.ip_address()` **до** domain/IDNA hostname validation;
- public IPv6 literal разрешать при тех же `http/https` и standard-port правилах, что public IPv4;
- canonical URL сохраняет обязательные brackets для IPv6 host (`https://[2001:4860:4860::8888]/`);
- loopback (`::1`), link-local, private/non-global, multicast, reserved и unspecified IPv6 отклонять тем же `unsafe_target` policy, что IPv4;
- пользовательский текст для `::1` и других non-public literals должен быть `Локальные, служебные и непубличные адреса запрещены.`, а не domain-syntax error;
- DNS hostname path и DNS-rebinding protection не ослабляются: A/AAAA answers по-прежнему проверяются на global address до connect;
- добавить regression: positive public IPv6 literal + negative `::1`, link-local и non-global IPv6.

Scope guard:

- не менять Cheburcheck static/probe transport limits, timeouts, redirect policy или pinned upstream revision;
- не менять DNS/HTTP/redirect/CMS/SEO/PageSpeed/Sitemap/QR semantics;
- кроме исправления ordering IPv6-literal validation не менять safe outbound transport semantics, redirect/DNS-rebinding policy, website monitoring state machine, SQLite schema, navigation/RBAC contract, Host Control, Deploy Agent или 3x-ui/OpenAPI;
- `v4.24.1` остаётся presentation/read-only diagnostics hotfix.

Acceptance hotfix:

1. WHOIS на controlled domain показывает creation/expiration в `DD.MM.YYYY HH:MM MSK`;
2. UTC → MSK conversion проверяется на значении, которое переходит на следующий календарный день;
3. возраст домена остаётся тем же, что до hotfix;
4. Cheburcheck domain result снова показывает bounded `IP` и доступный `Reverse DNS`;
5. при наличии upstream blocked subnets / `rkn_domain` / `subnet_size` эти значения отображаются без raw payload и без unbounded output;
6. domain с >5 IP/PTR/subnet entries показывает первые 5 и `… ещё N`;
7. regional result остаётся агрегированным; raw probe JSON/SSE в карточке отсутствует;
8. public IPv6 literal canonicalize/add проходит при global address, а `::1`/link-local/non-global IPv6 отклоняются как unsafe target до outbound connect;
9. bracketed IPv6 сохраняется в canonical URL и не ломает standard-port enforcement;
10. contextual `Другой инструмент` / `⬅ Сайт` navigation остаётся без изменений;
11. финальный `deploy-release.sh --status` подтверждает exact `v4.24.1`, `RestartCount=0`, Health/DB/3x-ui `ok`.

`v4.24.1` опубликован как exact release commit после успешных `Python checks` и `Publish release`. Три finding закрыты в release-коде; production smoke линии `v4.24.x` проведён и acceptance закрыт. Targeted hotfix не должен разрастаться в feature scope.


##### v4.25.0 — User Management: рефакторинг карточки пользователя

**Статус: ✅ User Management и follow-up релизы `v4.25.0–v4.25.6` проверены и закрыты на `v4.25.6`. Новый validation patch `v4.25.7` отслеживается отдельно.**

Цель — завершить v4.x User Management как цельный операторский workflow: карточка пользователя становится единой точкой входа для профиля, тарифа, срока, трафика, provisioning-доступа, подключений, подписки, платежей и персональной audit timeline. Релиз сохраняет существующие backend primitives и security boundaries, убирает конкурирующие legacy-пути синхронизации Inbounds и добавляет недостающие admin-facing функции без открытия Client Portal.

Implementation scope закрыт и опубликован в `v4.25.0`: User list/search/create, каноническая карточка и detail navigation, policy-based Access/Flow, Connections/HWID/IP, local-only Subscription QR, user-scoped Payments/Activity, confirmation-first lifecycle и завершённый bulk workflow реализованы и защищены regression coverage. Production smoke выполнен; найденные follow-up исправлены и повторно проверены в `v4.25.1–v4.25.6`. Закрытие предыдущих релизов подтверждено владельцем 2026-09-29; новый finding валидации Inbound не переоткрывает их исторический acceptance scope.

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

Production acceptance findings от 2026-09-28:

- под `Read-only` главная карточка пользователя ошибочно показывает shortcut `⏳ Продлить` с callback `adminextend:{telegram_id}`, хотя callback защищён privilege `users.support`; backend RBAC корректно не допускает mutation, но keyboard нарушает role-aware UI contract;
- acceptance review подтвердил более чистый fix: полностью убрать shortcut `⏳ Продлить` с главной карточки пользователя для всех ролей; продление срока остаётся только в каноническом parent-screen `📅 Срок → ➕ +30 дней`;
- callback `adminextend:{telegram_id}` не удаляется: он остаётся backend action под `users.support` для кнопки `➕ +30 дней` и для совместимости со старыми сохранёнными Telegram callbacks;
- `Пользователь → 🔗 Подписка → Показать URL` теряет parent context: текущий `adminsub:{telegram_id}` рендерит Back в карточку пользователя; fix — возвращать в канонический parent-screen `🔗 Подписка`;
- `Пользователь → 💳 Платежи → 📋 Все платежи` теряет user-scoped context: кнопка уводит в глобальный `admin:payments`, после чего Back ведёт в admin home; fix — не покидать user-scoped payment flow и сохранять возврат в `💳 Платежи` текущего пользователя;
- create-user flow ломается на проверке нового technical email: `_email_available()` считает email свободным только для ошибки `Client not found:`, тогда как pinned production 3x-ui при отсутствии записи возвращает `Obtain (record not found)`; в результате `✅ Использовать предложенный` (и общий путь проверки нового email) показывает `Не удалось проверить email` вместо продолжения wizard;
- fix: нормализовать штатный upstream not-found response в семантику «email свободен», не ослабляя fail-closed обработку остальных XUI ошибок; добавить regression coverage для фактического `Obtain (record not found)` и обоих create-email paths;
- HWID registration через публичный compat subscription path сломан: `subscription_proxy.py` при `GET /compat/{sub_id}` пересылает upstream только `Accept` и `User-Agent`, отбрасывая `X-HWID` и device metadata headers; при включённом HWID limit upstream отклоняет такой запрос, а compat proxy маскирует upstream `>=400` как HTTP 502;
- fix: для normal VPN-client subscription request безопасно проксировать reviewed HWID/device headers к 3x-ui upstream, не логировать их значения и сохранить существующую фильтрацию остальных headers; добавить regression coverage, что `X-HWID`/device metadata доходят до upstream и upstream HWID error не возникает из-за их потери;
- `⚙️ Ещё действия` под `Read-only` подтверждён как корректный negative case: mutation-кнопки не отображаются, остаётся только возврат к карточке пользователя.

Эти findings блокировали acceptance `v4.25.0`; исправления shortcut/navigation/create/HWID proxy опубликованы в `v4.25.1` и прошли повторную проверку. Исторический stale-callback production exception остаётся явно указан ниже, а не заменяется вымышленным PASS.

Отдельный HWID acceptance после исправления compat proxy:

- prerequisite: на контролируемом test user `Max HWIDs > 0`; при отсутствии HWID limit механизм считается неактивным и реальная device registration не ожидается;
- добавить публичную `/compat/{sub_id}` подписку в реальный mobile client, принудительно обновить subscription и подтвердить появление устройства в `Пользователь → 📱 Подключения → 📱 Устройства`;
- повторить тот же сценарий с реальным desktop client;
- проверить, что отображаются только разрешённые bounded metadata: модель/OS/version/User-Agent/short fingerprint/first+last seen без раскрытия полного HWID;
- удалить одно test-device через двухшаговый confirmation flow, проверить post-condition и отсутствие удаления остальных устройств;
- если конкретный клиент не регистрируется после proxy fix, отдельно подтвердить, отправляет ли он `X-HWID`/device metadata headers; отсутствие HWID headers у клиента не считать дефектом Telegram UI;
- acceptance считается пройденным только после проверки хотя бы одного реального HWID-capable клиента через публичный compat URL, а не только synthetic direct-upstream `curl`.


##### v4.25.1 — User Management stabilization / HWID completion

**Статус: ✅ Опубликовано в `v4.25.1` и принято в production.**

`v4.25.0` остаётся опубликованным baseline. Все production-acceptance blockers и незавершённые HWID operational flows исправляются в одном patch-релизе `v4.25.1`, после чего выполняется повторный acceptance только затронутых сценариев. `v4.26.0` по-прежнему остаётся Node Drain и не поглощает эти исправления.

Объём `v4.25.1`:

- удалить shortcut `⏳ Продлить` из главной карточки пользователя для всех ролей; канонический путь остаётся `📅 Срок → ➕ +30 дней`, stale `adminextend:{telegram_id}` остаётся backend-compatible;
- исправить `Пользователь → 🔗 Подписка → Показать URL`: Back обязан возвращать в `🔗 Подписка`;
- исправить `Пользователь → 💳 Платежи → 📋 Все платежи`: user-scoped context не должен теряться и Back не должен уводить в admin home;
- исправить create-user email availability: production response `Obtain (record not found)` нормализуется как штатный not-found / «email свободен», остальные XUI errors остаются fail-closed;
- исправить compat subscription proxy: для normal VPN-client request проксировать reviewed `X-HWID` и device metadata headers к upstream 3x-ui, не логировать их значения и не ослаблять фильтрацию остальных headers;
- добавить явный HWID limit при создании клиента: новые пользователи создаются с `limitHwid=5` по умолчанию;
- существующих пользователей автоматически массово на `5` не переводить;
- добавить per-user HWID limit в `🌐 Доступ → ⚙️ Параметры доступа` и summary в `📱 Подключения`;
- Read-only видит текущее значение HWID limit, но не получает mutation control;
- Support+ получает `📱 Изменить HWID limit` с bounded FSM input и явной семантикой `0 = HWID limit отключён`;
- изменение HWID limit выполняется через существующий `XUIClient.update_client(..., limitHwid=value)` и после success возвращает в `⚙️ Параметры доступа`;
- Plan apply, safe reconcile и strict reconcile не меняют индивидуальный `limitHwid`; HWID limit в этом patch-релизе остаётся per-user override и не добавляется в Plan schema;
- create-user preview показывает итоговый `HWID limit: 5` до подтверждения;
- обычные update-client операции обязаны сохранять существующий `limitHwid`, если операция явно его не меняет;
- привести `Система → Администраторы` к раздельной визуальной семантике status + role: каждая строка всегда показывает status marker и role emoji, используя существующий role mapping `👑 Owner / 🛡 Administrator / 🧑‍💻 Support / 👁 Read-only`;
- активный администратор отображается как `🟢 {role_emoji} TG … · {Role}`; отключённый — как `⛔ {role_emoji} TG … · {Role} · отключён`; неоднозначный `⚪` для disabled больше не используется;
- локальный break-glass Owner сохраняет явный source suffix и отображается консистентно как `🟢 👑 TG … · Owner · локальная конфигурация`;
- экран списка содержит короткую legend `Статус: 🟢 включён · ⛔ отключён`, а detail screen использует ту же status semantics; role/security identifiers и RBAC behavior не меняются.

Минимальные regression tests `v4.25.1`:

1. новый клиент получает `limitHwid=5`;
2. manual change `5 → 2` и `2 → 0`;
3. Read-only видит значение без edit button, Support+ видит mutation control;
4. Plan apply / safe reconcile / strict reconcile не меняют индивидуальный HWID limit;
5. другие `update_client()` mutations не обнуляют `limitHwid`;
6. create-user availability принимает фактический `Obtain (record not found)` как not-found и покрывает default/custom email paths;
7. compat proxy передаёт reviewed HWID/device headers upstream и не пишет их значения в logs;
8. subscription `Показать URL` возвращает в `🔗 Подписка`;
9. user-scoped payments сохраняют user context и корректный Back;
10. главная карточка больше не показывает `⏳ Продлить`;
11. список администраторов всегда показывает отдельные status + role indicators для Owner/Administrator/Support/Read-only;
12. disabled administrator использует явный `⛔ … · отключён`, detail/list semantics совпадают, а enable/disable и RBAC behavior не меняются.

Повторный production acceptance `v4.25.1`:

- повторить затронутые navigation/RBAC/back-chain cases;
- повторить create-user test 17 целиком до успешного создания контролируемого test user;
- выполнить отдельный real-device HWID acceptance, описанный выше, через публичный `/compat/{sub_id}`;
- проверить default `HWID limit = 5` на новом пользователе и ручное изменение через Telegram UI;
- подтвердить, что Plan apply/reconcile не перезаписывают индивидуальный HWID limit;
- повторить HWID delete two-step с реальным или контролируемым test-device;
- проверить `Система → Администраторы` на active/disabled Administrator, Support, Read-only и локальном Owner: role emoji всегда видим, disabled явно обозначен `⛔ … · отключён`, toggle не меняет назначенную роль;
- выполнить final bot/DB/3x-ui health smoke.

`v4.25.1` production-accepted по своему User Management/HWID scope после targeted re-acceptance от 2026-09-29.

Production evidence `v4.25.1`:

- deployment: tag `v4.25.1`, commit `99e51b8988ffd90413b324021cac352ee71b39b7`, container running, `RestartCount=0`, bot version `4.25.1`;
- baseline health: `Health: ok`, `DB: ok`, expected Docker subnet, 3x-ui connectivity `ok`;
- targeted re-acceptance cases 28–37: **PASS**;
- подтверждены navigation/back-chain fixes, create-user production not-found handling, default/per-user HWID limit, preservation across Plan/reconcile, real mobile + desktop HWID registration через public compat path, HWID delete two-step, administrator status/role emoji contract и single-user traffic limit;
- final post-smoke health: **PASS**;
- исторический stale legacy sync callback production-click (бывший test 25) не воспроизведён из-за отсутствия сохранённого старого Telegram message и зафиксирован как **N/A production exception**; compatibility handler и non-mutating redirect покрыты code review/regression tests, mutation path через старый callback не используется.

Acceptance `v4.25.1` закрыт. Выявленные затем client-compatibility findings были выделены в `v4.25.2–v4.25.6` и также проверены и закрыты; незавершённого acceptance прежних релизов `v4.25.x` не осталось.



##### v4.25.2 — Subscription client compatibility

**Статус: ✅ Проверено и закрыто: Shadowrocket/HWID acceptance пройден в `v4.25.2`, INCY Desktop UA finding исправлен и принят в `v4.25.3`.**

После успешного production acceptance `v4.25.1` отдельно выявлены client-side compatibility проблемы, не относящиеся к User Management logic:

- INCY Desktop получает AmneziaWG entries из raw subscription, но Desktop-клиент не должен представлять неподдерживаемый AWG path как рабочий узел; требуется client-aware output/filtering для INCY Desktop без регрессии INCY mobile;
- Shadowrocket mobile/desktop при активном HWID limit может получать generic «URL сервера столкнулся с проблемой», потому что 3x-ui HWID gate отвечает `404`, а compat proxy сейчас сворачивает любой upstream `>=400` в непрозрачный `502 subscription upstream error`;
- production diagnosis подтвердил штатный full-slot case: `hwid-status` вернул `active=true, limit=3, registered=3, remaining=0, full=true`; после увеличения HWID limit проблема Shadowrocket исчезла;
- следовательно, HWID enforcement 3x-ui сохраняется, а compatibility layer должен уметь отличать HWID gate от реального upstream outage.

Объём `v4.25.2`:

- добавить bounded client-aware subscription output для INCY Desktop: неподдерживаемые AmneziaWG entries не должны показываться как рабочие Desktop-ноды; остальные протоколы и порядок подписки сохраняются;
- сохранить текущую `vpn:// → amneziawg://` совместимость для INCY mobile/поддерживаемых клиентов; нельзя глобально удалять AWG из raw subscription;
- определить INCY Desktop только по подтверждённому User-Agent/platform contract; при неоднозначном UA не применять агрессивный filtering;
- добавить явную operator/user documentation для Shadowrocket: при включённом per-user HWID limit необходимо включить `Send HWID` / «Отправлять HWID»;
- распознавать allowlisted HWID response headers 3x-ui: `X-Hwid-Active`, `X-Hwid-Not-Supported`, `X-Hwid-Limit`, `X-Hwid-Max-Devices-Reached`;
- HWID-specific upstream `404` не маскировать generic `502`: сохранить/перевести HWID gate в диагностически полезный ответ с allowlisted headers, не раскрывая `sub_id`, HWID value/hash или device secrets;
- generic network/timeout/real upstream 5xx по-прежнему возвращать как fail-closed gateway error; HWID diagnostics не должны превращать настоящий upstream outage в ложный client-limit response;
- в logs разрешены только bounded reason/status fields (например, `hwid_not_supported` / `hwid_max_devices_reached`), но не значения `X-HWID`, subscription URL или `sub_id`;
- **не синтезировать и не подменять fake HWID в compat proxy**: device identity всегда приходит от клиента; proxy не должен обходить реальный per-device limit и не должен объединять разные устройства под одной synthetic identity;
- сохранить forwarding reviewed client headers из `v4.25.1`: `X-HWID`, `X-Device-OS`, `X-Ver-OS`, `X-Device-Model`, при сохранении фильтрации остальных request headers;
- при полном лимите пользователь/operator должен иметь однозначный operational path: освободить device slot или увеличить per-user HWID limit; автоматическое ослабление лимита запрещено.

Минимальные regression tests `v4.25.2`:

1. active HWID + свободный slot + валидный `X-HWID` → subscription `200`, устройство регистрируется ровно один раз;
2. active HWID + missing/слишком короткий HWID → HWID gate остаётся отказом с `X-Hwid-Not-Supported`, а не generic `502`;
3. active HWID + все slots заняты + новый HWID → отказ сохраняет `X-Hwid-Max-Devices-Reached` / `X-Hwid-Limit` и не маскируется generic `502`;
4. известный зарегистрированный HWID продолжает получать subscription при заполненном лимите;
5. `limitHwid=0` не вводит новый HWID gate;
6. proxy никогда не генерирует synthetic/fallback HWID и не логирует HWID/subscription secrets;
7. Shadowrocket с включённым `Send HWID` и свободным slot получает subscription; full-slot scenario даёт диагностически различимый отказ, после освобождения/увеличения slot subscription снова загружается;
8. INCY Desktop не получает неподдерживаемые AWG entries как рабочие nodes, при этом VLESS/другие поддерживаемые entries сохраняются;
9. INCY mobile сохраняет существующую AmneziaWG conversion/работоспособность;
10. generic upstream 404/5xx без HWID diagnostic headers не переопределяются как HWID-limit case.

Production acceptance `v4.25.2`:

- проверить INCY Desktop на реальной подписке: неподдерживаемые AWG entries не создают «мёртвые» Desktop-ноды, остальные протоколы работают;
- повторить INCY mobile AWG smoke и подтвердить отсутствие regression;
- проверить Shadowrocket mobile и desktop с включённым `Send HWID` при свободном HWID slot;
- воспроизвести controlled full-slot case и подтвердить диагностически понятный HWID-limit response вместо generic gateway failure;
- освободить/увеличить slot и подтвердить восстановление той же Shadowrocket subscription без rotation identity;
- выполнить final bot/DB/3x-ui health smoke.

Acceptance `v4.25.2` завершён с follow-up в `v4.25.3`: первоначальный INCY Desktop FAIL сохранён в истории ниже, а исправление подтверждено последующим smoke. Этот finding больше не блокирует дальнейшие релизы.


##### v4.25.3 — INCY Desktop UA compatibility

**Статус: ✅ Опубликовано в `v4.25.3` и принято в production; последующие `v4.25.4–v4.25.6` относились только к Streisand compatibility investigation/revert.**

Production acceptance `v4.25.2` от 2026-09-29:

- INCY mobile: **PASS**;
- Shadowrocket mobile: **PASS**;
- Shadowrocket desktop: **PASS**;
- controlled full-slot diagnostic: **PASS**, proxy log reason `hwid_max_devices_reached`;
- same-URL recovery после освобождения/увеличения HWID slot: **PASS**;
- final health: **PASS**;
- INCY Desktop: **FAIL** — AWG entries остались.

Root cause подтверждён по безопасно извлечённому User-Agent без subscription URL/sub_id: реальный Desktop UA — `INCY/3.8.8/mac os x Dalvik/21.0.12.1+1-LTS`. Реализация `v4.25.2` ожидала ровно три slash-сегмента и platform token `macos`, поэтому этот валидный Desktop request не попадал под filtering.

Объём `v4.25.3`:

- поддержать подтверждённый INCY macOS Desktop UA prefix `mac os x` с optional runtime suffix после platform token;
- сохранить поддержку Windows/Linux/macOS desktop variants и Android/iOS mobile variants;
- неизвестные/неоднозначные INCY platform tokens не классифицировать как Desktop;
- не менять Shadowrocket/HWID gate semantics, уже принятые в `v4.25.2`;
- включить явную операционную инструкцию Shadowrocket `Send HWID` в README и ADMIN_SETUP.

Targeted acceptance `v4.25.3`:

1. INCY Desktop macOS с реальным UA больше не получает AWG entries;
2. VLESS/прочие поддерживаемые entries остаются и работают;
3. INCY mobile сохраняет AWG;
4. Shadowrocket/HWID smoke не регрессирует;
5. final bot/DB/3x-ui health остаётся PASS.

Targeted acceptance `v4.25.3` закрыт; принятый runtime contract повторно подтверждён финальным smoke `v4.25.6`.


##### v4.25.4 — Streisand plain subscription compatibility

**Статус: ✅ Проверено и закрыто как исторический diagnostic release; гипотеза `plain=1` не решила Streisand compatibility и была удалена в `v4.25.6`.**

Production finding после успешного acceptance `v4.25.3`:

- Shadowrocket, V2Box, V2RayTun, Happ и INCY subscription import работают;
- Streisand получает `HTTP 200`, но сообщает «подписка не содержит действующей конфигурации»;
- та же subscription, сокращённая до двух VLESS entries, продолжает давать ту же ошибку;
- оба VLESS entries импортируются в Streisand по одному успешно;
- следовательно, finding локализован на subscription-container parsing, а не на VLESS transport/Reality URI.

Объём `v4.25.4`:

- добавить opt-in query flag `plain=1` / `plain=true` / `plain=yes`;
- при `plain` возвращать decoded newline-separated subscription links после существующих client compatibility transforms;
- не пересылать `plain` upstream в 3x-ui;
- default `/compat/{sub_id}` без `plain` оставить неизменным по encoding/semantics;
- сохранить HWID forwarding/enforcement и fail-closed error handling;
- не добавлять UA-based Streisand detection: фактический Streisand request использует обычный Safari UA и неотличим от browser/WebView traffic.

Исторический план targeted acceptance `v4.25.4` (не список полученных PASS):

1. Streisand с `?plain=1` импортирует subscription;
2. те же VLESS entries появляются как валидные configs;
3. обычный URL без `plain` остаётся byte-compatible по default encoding path;
4. Shadowrocket/V2Box/V2RayTun/Happ/INCY smoke не регрессирует;
5. HWID gate/full-slot diagnostics не регрессируют;
6. final bot/DB/3x-ui health остаётся PASS.

Проверка `v4.25.4` завершена отрицательным результатом для гипотезы `plain=1`; investigation и forward-revert закрыты в `v4.25.6`. Поддержка Streisand при активном HWID limit не заявляется.


##### v4.25.5 — Streisand plain mode precedence

**Статус: ✅ Проверено и закрыто как исторический diagnostic release; HTML-precedence fix не устранил корневую HWID-несовместимость и был удалён в `v4.25.6`.**

Production finding после deploy `v4.25.4`:

- Streisand с `?plain=1` продолжил сообщать, что subscription не содержит действующих конфигураций;
- фактический request использует Safari/WebView-like UA и `Accept: text/html`;
- `v4.25.4` вычислял `plain_mode`, но HTML branch выполнялся раньше raw response path, поэтому `plain=1` не гарантировал raw subscription;
- root cause подтверждён кодом compat proxy.

Fix `v4.25.5`:

- при `plain_mode` HTML branch всегда пропускается;
- upstream raw fetch получает `Accept: text/plain`;
- default URL без `plain` не меняется;
- добавлен regression на Safari-like UA + `Accept: text/html` + `plain=1`.

Исторический план targeted acceptance `v4.25.5` (не список полученных PASS):

1. Streisand с `?plain=1` импортирует subscription;
2. те же VLESS configs появляются как валидные;
3. обычные Shadowrocket/V2Box/V2RayTun/Happ/INCY URLs продолжают работать без regression;
4. final bot/DB/3x-ui health остаётся PASS.


##### v4.25.6 — Streisand incompatibility / forward revert

**Статус: ✅ Опубликовано в `v4.25.6`, принято в production; предыдущие релизы `v4.25.0–v4.25.6` закрыты.**

Итог production investigation:

- Streisand получает обычный browser/HTML path с HTTP 200;
- при принудительном raw subscription path клиент доходит до compat proxy, но upstream 3x-ui отвечает HTTP 404 с bounded reason `hwid_not_supported`;
- в access log подтверждён реальный Streisand UA `Streisand/50 CFNetwork/... Darwin/...`;
- клиент не передаёт совместимый `X-HWID` для raw subscription requests;
- те же VLESS links импортируются по одному, поэтому VLESS/Reality URI сами по себе валидны;
- следовательно, Streisand несовместим с HWID-protected subscription flow при `HWID limit > 0`.

Решение:

- удалить временные `plain=1` workarounds из `v4.25.4–v4.25.5`;
- вернуть runtime subscription proxy и его regression contract к `v4.25.3`;
- не генерировать synthetic/fallback HWID;
- не ослаблять или обходить per-device HWID enforcement ради Streisand;
- оставить `v4.25.4` и `v4.25.5` в Git/release history как диагностические релизы;
- документировать Streisand как известное client limitation для пользователей с активным HWID limit.

Targeted acceptance `v4.25.6`:

1. default subscription behavior совпадает с `v4.25.3`;
2. Shadowrocket/V2Box/V2RayTun/Happ/INCY smoke не регрессирует;
3. HWID full-slot / unsupported diagnostics остаются fail-closed;
4. `plain=1` больше не является поддерживаемым compatibility contract;
5. final bot/DB/3x-ui health остаётся PASS.


Production acceptance `v4.25.6` от 2026-09-29:

- release: tag `v4.25.6`, commit `b3fb80d334c8cded51e4bc9de4b08af2e31d0cd6`;
- test 50 — version/health: **PASS**;
- test 51 — Shadowrocket: **PASS**;
- test 52 — V2Box / V2RayTun / Happ: **PASS**;
- test 53 — INCY mobile + desktop: **PASS**;
- test 54 — HWID full-slot / recovery diagnostics: **PASS**;
- test 55 — Streisand: **EXPECTED LIMITATION** — raw subscription при `HWID limit > 0` несовместим, потому что клиент не передаёт совместимый `X-HWID`; 3x-ui корректно отвечает `hwid_not_supported`;
- test 56 — final bot/DB/3x-ui health: **PASS**;
- временные `plain=1` workarounds отсутствуют в финальном runtime; subscription proxy соответствует принятому контракту `v4.25.3`;
- synthetic/fallback HWID не добавляется, per-device enforcement не ослабляется.

**Итог: релизы `v4.25.0–v4.25.7` полностью проверены и закрыты.** Владелец повторно подтвердил завершение предыдущих релизов 2026-09-29. `v4.25.4–v4.25.5` закрыты как диагностические попытки с forward-revert в `v4.25.6`, а не как успешная поддержка Streisand.

Следующий активный патч — `v4.25.8` с navigation hotfix Clone Inbound и Owner self-role safety. После его отдельного release/acceptance следующий feature release — `v4.26.0` Node Drain.


##### v4.25.7 — Inbound input validation

**Статус: ✅ Выполнено в `v4.25.7`; опубликовано, развёрнуто и принято в production 2026-09-29. Issue #199 закрыт как completed после targeted smoke.**

Tracking: [issue #199](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/199) (closed/completed), [fix PR #200](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/200), [release PR #201](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/201). Fix PR #200 слит в `main` squash-коммитом `2b24ce709ffe77d479c98e1604462deb4910c072`; release-prep PR #201 слит коммитом `053b9fecb85d009e5cfe9b323c1f4cf6d4e7d890`, на который указывает tag `v4.25.7`.

Новый post-acceptance finding: в `inbound_admin.py` ветки ошибочного ввода строят Cancel keyboard с локальным `iid`/`tid` до его присваивания. Нечисловой/вне диапазона порт в `inbound_clone_port` и `template_deploy_port`, а также пустое/слишком длинное имя в `inbound_template_save` приводят к `UnboundLocalError` вместо подсказки.

Scope:

- считывать FSM data и существующие идентификаторы сразу после успешного `guard_message()` и до проверки пользовательского ввода в трёх обработчиках;
- сохранять текущий FSM и корректный Cancel parent при неверном вводе, позволяя повторить ввод;
- ошибочный ввод не вызывает создание Inbound, запись шаблона или успешный audit;
- не менять callback identifiers, RBAC, допустимые диапазоны, payload semantics, схему SQLite, pinned 3x-ui/OpenAPI, HWID/proxy, Host Control/Deploy Agent или политику повторов запросов;
- не смешивать исправление с Node Drain, общим рефакторингом или новыми возможностями.

Regression contract:

1. нечисловой, пустой и отсутствующий текст порта; `0`, отрицательный порт и `65536`;
2. пустое/пробельное/отсутствующее имя и имя длиннее 64 символов;
3. точная подсказка и Cancel callback исходного Inbound/шаблона, сохранение реального FSM state/data;
4. отсутствие remote/database mutations при неверном вводе и занятом порте;
5. допустимые порты `1`, `65535`, обычный порт с пробелами, Master и direct-node targets;
6. успешное создание по-прежнему отключено и без клиентов, исходный payload не изменяется;
7. допустимые имена, duplicate-name retry, последовательность invalid → valid input и отказ авторизации до чтения FSM.

Tests: `tests/test_inbound_input_validation.py` выполняет реальные async handlers с `MemoryStorage`; внешние вызовы и Telegram rendering заменены моками. Итоговый fix PR HEAD `186b958cf6d8af7d6f37c794f19405046ae18483` прошёл штатные `Python checks` и `PR conventions`; после squash merge повторный `Python checks` на `main` commit `2b24ce709ffe77d479c98e1604462deb4910c072` также завершился success (576 tests).

Production acceptance `v4.25.7` от 2026-09-29:

- tag/GitHub Release `v4.25.7` опубликованы штатным workflow; tag указывает на `053b9fecb85d009e5cfe9b323c1f4cf6d4e7d890`;
- production deployment выполнен на опубликованный tag;
- invalid/non-numeric/out-of-range port, invalid template name, invalid → valid retry, Cancel context, occupied port, Master/direct-node и controlled valid disabled/clientless flows — **PASS**;
- финальный bot/DB/3x-ui health — **PASS**;
- исходный `UnboundLocalError` finding устранён; issue #199 обновлён evidence и закрыт как `completed`;
- отдельный Low/UX navigation finding Clone Inbound вынесен в issue #202 / `v4.25.8` и не переоткрывает #199.

Admin Setup: новых настроек и действий установки для `v4.25.7` не потребовалось.


##### v4.25.8 — Inbound clone navigation hotfix

**Статус: ✅ Выполнено в `v4.25.8`; опубликовано, развёрнуто и принято в production 2026-09-29. Issue #202 закрыт как `completed`.**

Production finding:

- путь: `/admin → Инфраструктура → Inbounds → <Inbound> → 📋 Клонировать`;
- до исправления `✖ Отмена` на выборе target server возвращала в общий список `📡 Inbounds`;
- после исправления вложенный flow возвращается в карточку исходного Inbound: `admin:inbound:{source_id}`.

Implementation:

- shared `_target_keyboard(...)` получает явный Cancel parent;
- Clone Inbound передаёт `admin:inbound:{iid}`;
- Deploy Template сохраняет собственный parent `admin:inboundtemplate:{tid}`;
- invalid-port Cancel по-прежнему возвращает в исходный Inbound;
- clone target callbacks, disabled/clientless payload, RBAC, audit и 3x-ui API semantics не изменены.

Tracking: [issue #202](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/202) (closed/completed), [fix PR #205](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/205), [release PR #206](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/206).

##### v4.25.8 — Owner self-role safety

**Статус: ✅ Выполнено в `v4.25.8`; опубликовано, развёрнуто и принято в production 2026-09-29. Issue #204 закрыт как `completed`.**

DB-backed Owner теперь не может понизить собственную роль ниже Owner одним нажатием:

- self-demotion требует отдельного confirmation screen с явным предупреждением о потере Owner-only прав;
- mutation выполняется только через Owner-only confirm callback с актуальным FSM state + nonce;
- direct/stale confirmation fail-closed;
- Cancel очищает confirmation и возвращает в собственную карточку без mutation;
- изменение ролей других DB-администраторов Owner'ом сохраняет прежнюю семантику;
- локальный break-glass Owner из `ADMIN_TELEGRAM_IDS` остаётся immutable;
- audit фиксирует actor/target и переход роли;
- role model, privilege catalog и уровни ролей не меняются.

Tracking: [issue #204](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/204) (closed/completed), [fix PR #205](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/205), [release PR #206](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/206).

Production acceptance `v4.25.8`:

- tag/GitHub Release `v4.25.8` опубликованы штатным workflow; tag указывает на `768fc0e4b9a0c0d2e35508febf272709896c3e7f`;
- implementation PR #205 и release-prep PR #206 слиты в `main`;
- post-merge `Python checks` на release commit: **587 tests OK**, compileall, OpenAPI gate, release-notes smoke, deploy/helper/Compose checks и `git diff --check` — success;
- production deployment выполнен на опубликованный tag;
- targeted production tests navigation hotfix и Owner self-demotion safety — **PASS**;
- final bot/DB/3x-ui health — **PASS**;
- issues #202 и #204 обновлены acceptance evidence и закрыты как `completed`.

**Итог линии: `v4.25.0–v4.25.8` полностью проверены и operationally закрыты. Следующий активный runtime-релиз — `v4.26.0` Node Drain.**

Admin Setup: новых настроек и действий установки для `v4.25.8` не потребовалось.


##### v4.26.0 — Node Drain / graceful traffic evacuation

**Статус: ✅ `v4.26.0` опубликован и развёрнут; полный controlled state-changing production acceptance завершён 2026-10-01, issue #208 закрыт как `completed`.**

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

Implementation / production evidence:

- feature issue #208 на момент release оставался открытым до полного targeted production smoke; обязательный smoke завершён 2026-10-01 и issue закрыт как `completed`;
- implementation PR #209 слит в `main` squash commit `e46c58870ea31b3a0532bd69b9b2dc01ba9bfa4a`;
- post-merge `Python checks` на implementation merge commit — **PASS**: compileall, полный unittest suite, pinned 3x-ui OpenAPI contract, release tooling и `git diff --check`;
- release-prep PR #210 слит в `main` squash commit `cd39048a2da00443523e7b33b400f4c8b5dcd608`; штатный workflow опубликовал tag/GitHub Release `v4.26.0`;
- production deployment `v4.26.0` выполнен; базовые release status и runtime version checks подтверждены оператором;
- read-only Node Drain preflight на production direct node показал 4 target Inbounds, 2 затронутых пользователей, 2 готовых к переносу и 0 blockers;
- pre-mutation confirmation был отменён без remote mutation; finding #211: `✖ Отмена` вернула в корень `Операции с нодами` вместо canonical parent — preflight той же ноды;
- полный targeted production smoke из пункта 11 был отложен до безопасной test node/user cohort и завершён 2026-10-01: read-only preflight показал affected=1, movable=1, blockers=0; state-changing run выполнил maintenance → attach-before-detach с read-back → detach с read-back → `drained`; remaining assignments=0, blockers=0; reconnect через альтернативный Master прошёл успешно; test node возвращена из maintenance и обычное policy reconciliation восстановило исходную тестовую политику; временные test user/plan/server group/Inbound/node bindings после acceptance удалены с Master, audit/job/Drain history сохранена.

##### v4.26.1 — Node Drain Cancel navigation

**Статус: ✅ Выполнено в `v4.26.1`; patch опубликован, развёрнут и targeted production verification завершён, issue #211 закрыт как `completed`.**

Production pre-mutation smoke `v4.26.0` подтвердил safety path: `✖ Отмена` помечает review-plan как `cancelled` до remote mutation. При этом navigation parent нарушает общий UI contract: после Cancel пользователь попадает сразу в `Операции с нодами`, а не в read-only preflight выбранной direct node.

Scope patch:

1. `✖ Отмена` на Node Drain confirmation возвращает в `admin:fleet:drain:n<node_id>` — preflight той же stable direct node.
2. Отменённый plan остаётся terminal `cancelled`; stale `run` callback не может его запустить.
3. Cancel не выполняет maintenance, attach, detach или другую remote mutation.
4. RBAC остаётся без изменений: preflight — Read-only+, prepare/cancel/run — Administrator+.
5. Regression test закрепляет canonical parent, no-mutation Cancel и stale-plan rejection.
6. После release/deployment выполняется targeted production verification именно navigation path; полный Node Drain mutation smoke по-прежнему проводится только на безопасной test node/user cohort.

Этот patch не расширяет Node Drain scope и не меняет SQLite schema, 3x-ui API contract или destructive Host Control boundaries.

Implementation / production evidence:

- fix PR #213 слит в `main` squash commit `218f2e9fda914b05121051dd0dd00a94ba99dc6b`;
- release-prep PR #214 слит в `main` squash commit `c2fc8baee1c11a716babb4bfc72743dface686ed`; штатный workflow опубликовал tag/GitHub Release `v4.26.1`;
- `PR conventions` и `Python checks` для fix/release-prep — **PASS**;
- production deployment `v4.26.1` выполнен, runtime version `4.26.1` подтверждён;
- targeted smoke: read-only preflight blockers 0, confirmation screen PASS, `✖ Отмена` вернула в preflight той же direct node, node осталась в рабочем состоянии без maintenance/draining/drained;
- финальный health/status — **PASS**;
- issue #211 закрыт как `completed`;
- на момент acceptance `v4.26.1` полный state-changing Node Drain mutation smoke оставался отдельным scope #208; он выполнен 2026-10-01 на безопасной test node/user cohort и issue #208 закрыт как `completed`.

##### Data-plane address hardening — issue #219

**Статус: ✅ Pre-freeze hardening принят 2026-10-01; issue #219 закрыт как `completed` документированным v4.x product decision и production proof.**

Production diagnosis подтвердил, что control-plane адрес панели и client-facing data-plane endpoint являются независимыми сущностями. Канонический runbook `docs/DATA_PLANE_ADDRESSING.md` уже фиксирует текущую policy: `Node.address` может оставаться verified HTTPS hostname, а client-facing Inbounds используют явный operator-supplied public IP через `shareAddrStrategy=custom`; protocol-specific SNI/Reality names не переписываются, а readiness включает host/provider firewall для каждого TCP/UDP Inbound.

Принятый v4.x product decision:

1. `Node.address` остаётся только control-plane endpoint и может быть verified HTTPS hostname.
2. Отдельная node-level `data_plane_address` / public-IP metadata до final v4 freeze не вводится.
3. Client-facing Inbounds на direct node используют operator-managed per-Inbound contract `shareAddrStrategy=custom` + явный `shareAddr`.
4. Automatic DNS→IP persistence из panel hostname запрещён; existing nodes не переписываются автоматически.
5. Protocol identity fields, включая Reality SNI/serverNames, независимы от dial address и не изменяются побочно.
6. Secrets/client identifiers не попадают в audit/log/docs evidence.

Production proof 2026-10-01 на безопасной test node подтвердил реальный drift: исходный Inbound имел `shareAddrStrategy=node` и пустой `shareAddr`. Выполнена одна контролируемая mutation только share-address полей, после которой read-back подтвердил `custom` и явный operator-supplied public data-plane IP. `Node.address`, `settings`, `streamSettings`, `sniffing` и Reality SNI остались без изменений; обновлённая subscription успешно переподключилась через test node. После acceptance временный тестовый контур удалён с Master. Issue #219 закрыт как `completed`.

##### v4.26.2 — Dashboard Attention summary

**Статус: ✅ Выполнено в `v4.26.2`; release опубликован, развёрнут и production acceptance завершён, issue #216 закрыт как `completed`.**

Цель — добавить в `/admin → Обзор` компактный read-only блок `⚠️ Требует внимания`, который агрегирует уже существующие problem states без нового mutation surface.

Scope:

1. Сводка показывает общий count и bounded breakdown проблем прямо на `Обзор`.
2. Источники — только существующие read-only/local states: active alerts, failed/unknown/interrupted jobs, unhealthy/offline/unknown infrastructure, problematic terminal Fleet/Node Drain states и иные уже существующие operator-facing failures.
3. `failed`, `unknown`, `interrupted` и degraded/unhealthy не смешиваются в один неразличимый статус.
4. При отсутствии проблем выводится явное спокойное состояние `✅ Требует внимания: нет`.
5. Summary не содержит credentials, subscription URL/`sub_id`, raw upstream payloads или персональные списки пользователей.
6. `Обзор` остаётся Read-only+; новых privilege IDs, auto-remediation и remote mutations нет.
7. Regression coverage фиксирует deterministic aggregation, bounded output и отсутствие state-changing calls.

Отдельный drill-down screen и canonical deep-links не входят в этот релиз и переносятся в `v4.26.3`.

Implementation evidence перед release:

- implementation PR #221 слит в `main` squash commit `1b6c72a91f2aac340bca2df37220f8934a8bc52c`;
- `PR conventions` и `Python checks` на финальном head implementation PR — **PASS**;
- summary читает active alerts/job history/local Fleet/Node Drain journals и не добавляет mutation callback, privilege ID или auto-remediation;
- regression coverage закрепляет calm state, latest-state aggregation, различение `failed/unknown/interrupted`, bounded output и no-mutation wiring;
- release-prep PR #222 слит в `main` squash commit `467d4f5609290622f0f839ce103fbf606f6f29b6`; штатный workflow опубликовал tag/GitHub Release `v4.26.2`;
- production deployment `v4.26.2` выполнен, exact tag/SHA и runtime version `4.26.2` подтверждены;
- targeted read-only smoke `/admin → Обзор` — **PASS**: блок `⚠️ Требует внимания` отображается, calm state `✅ Требует внимания: нет`, остальной dashboard остаётся работоспособным;
- финальный status — **PASS**: container running, `RestartCount=0`, Health/DB/3x-ui connectivity — ok;
- issue #216 закрыт как `completed`.

##### v4.26.3 — Attention Center drill-down

**Статус: ✅ Выполнено; production acceptance завершён через fix `v4.26.4`, issue #217 закрыт как `completed`.**

Цель — добавить отдельный read-only экран `⚠️ Требует внимания` как drill-down для summary из `v4.26.2`, не создавая новый incident/ticket subsystem.

Scope:

1. Вход — из `/admin → Обзор`; экран имеет `🔄 Обновить` и `⬅ Обзор`.
2. Detail группируется по существующим доменам: infrastructure/health, jobs, alerts, backups и Fleet/Node Drain problem states.
3. Каждый item содержит bounded operator context и stable identity без secrets.
4. Переходы ведут только в существующие canonical screens: `Состояние системы`, `Задания`, `Оповещения`, `Резервные копии`, `Операции с нодами` и аналогичные уже существующие родители.
5. Navigation permission-aware: drill-down не повышает роль и не открывает actions выше текущего RBAC.
6. Resolved item исчезает после read-only refresh; собственного acknowledge/snooze/assignment storage нет.
7. Stale/deleted objects не создают dead-end или callback exception.
8. Count/detail согласованы с `v4.26.2`; regression tests фиксируют navigation/back/refresh и no-mutation contract.

Implementation evidence перед release:

- implementation PR #224 слит в `main` squash commit `9acbbe85d16a6907b11e477d96245a7cc3be656d`;
- `PR conventions` и финальный `Python checks` на implementation PR — **PASS**;
- `Python checks` на merge commit в `main` — **PASS**;
- `admin:attention` использует существующий `dashboard.view` / Read-only+ boundary, новых privilege IDs и storage нет;
- detail использует те же current-state semantics, что summary `v4.26.2`, а item rendering bounded и secret-free;
- issue #217 остаётся открыт до publication/deployment `v4.26.3`, targeted navigation/refresh smoke и финального health/status-check.

Production smoke `v4.26.3` подтвердил сам Attention Center, но выявил navigation/RBAC presentation finding #226:

- первый уровень Attention Center соответствует canonical contract: `🔄 Обновить`, `⬅ Обзор` и deep-links ведут в существующие screens;
- backend RBAC остаётся fail-closed, privilege escalation не подтверждён;
- destination screens строят часть keyboards статически и показывают actions выше роли текущего оператора:
  - `⚙️ Задания` показывает manual backup (`jobs.manage`, admin);
  - `💾 Резервные копии` показывает create/download actions (`backups.manage`, admin) и Restore/DR (`restore.manage`, owner);
  - `🚨 Оповещения` показывает rule toggle/threshold actions (`alerts.manage`, admin);
  - `🌐 Операции с нодами` показывает maintenance/rollout management entry points (`fleet.manage`, admin);
- static `attention_menu()` показывает domain deep-links даже при calm/empty state; это не прямой RBAC defect, но создаёт misleading drill-down UX и включается в fix scope.

##### v4.26.4 — Permission-aware admin navigation fix

**Статус: ✅ Выполнено в `v4.26.4`; release опубликован, развёрнут и production acceptance завершён. Bug #226 и issue #217 закрыты как `completed`.**

Цель — устранить presentation-level RBAC drift без ослабления backend authorization и без нового product scope.

Scope:

1. Ввести общий role-aware keyboard filtering/rendering helper, использующий существующий callback privilege catalog как single source of truth; не создавать второй ручной permission map.
2. Применить helper как минимум к `Jobs`, `Backups`, `Alerts`, `Fleet` и другим затронутым admin keyboards, обнаруженным regression inventory.
3. `read_only` и `support` не видят admin/owner actions; `admin` не видит owner-only actions; `owner` сохраняет полный разрешённый UI.
4. Backend `authorize_callback` / minimum-role checks остаются обязательной второй границей и не упрощаются.
5. Attention Center сохраняет canonical `Refresh/Back`; domain deep-links становятся context-aware по реально присутствующим problem groups. В empty state остаются только нейтральная навигация/refresh, без misleading problem links.
6. Canonical parent semantics не меняются: destination screen возвращается в свой обычный раздел, а не в Attention Center.
7. Stale callback для скрытого/недоступного action по-прежнему fail-closed и не выполняет mutation.
8. Regression matrix покрывает роли `read_only / support / admin / owner`, direct entry и переход из Attention Center, `Back/Refresh`, empty state, stale callbacks и no-mutation-on-view.
9. Перед release выполнить полный стандартный gate: compileall, unittest, 3x-ui OpenAPI contract, `git diff --check`.
10. После publication/deployment выполнить targeted production smoke минимум под `read_only` и `admin`, затем final health/status. Только после PASS закрыть #226 и #217.

Дополнительно в рамках fix провести bounded inventory остальных статических admin keyboards: если screen содержит callbacks с разными minimum roles, rendering должен быть role-aware. Это считается исправлением общей причины finding, а не расширением feature scope.

Implementation evidence перед release:

- fix PR #228 вводит общий `filter_keyboard_for_role()` на базе канонического callback privilege catalog;
- role-aware rendering подключён к `Jobs`, `Backups`, `Alerts`, `Fleet`, core `/admin` / `Система` navigation и legacy parent menus;
- Attention Center передаёт фактический набор problem categories в keyboard builder; empty state не показывает domain deep-links;
- regression matrix покрывает `read_only / support / admin / owner`, unknown admin callback fail-closed и wiring затронутых screens;
- `PR conventions` и финальный `Python checks` на head fix PR — **PASS**;
- SQLite schema, pinned 3x-ui OpenAPI contract и backend mutation/RBAC boundaries не меняются.
- merge fix PR #228 в `main`: `7e34a61354a94f8565cd94967654f127ec0f258d`;
- `Python checks` на merge commit в `main` — **PASS**;
- release-prep обновляет только versioned metadata/docs/tests; runtime behavior после #228 не меняется.
- release-prep PR #229 слит в `main` squash commit `e2b6834d549a6b3272702fc27570c8a8a3a99bfe`; штатный workflow опубликовал tag/GitHub Release `v4.26.4`;
- production deployment exact tag `v4.26.4` / SHA `e2b6834d549a6b3272702fc27570c8a8a3a99bfe` подтверждён;
- targeted role smoke — **PASS**: `read_only` не видит admin/owner actions, `admin` не видит owner-only actions;
- Attention Center `Refresh/Back` и context-aware navigation — **PASS**;
- финальный status — **PASS**: container running, `RestartCount=0`, Bot version `4.26.4`, Health/DB/3x-ui connectivity — ok;
- bug #226 и feature acceptance #217 закрыты как `completed`.

После closure #208 и #219 2026-10-01 следующий порядок: encrypted off-site backup/restore drill → final v4 feature freeze → repository/public-release audit.

Оба Attention-релиза и их fix относятся к финальной полировке Admin Control Plane и должны быть operationally приняты до off-site drill и final v4 feature freeze. Они не меняют SQLite schema по умолчанию, pinned 3x-ui API contract или destructive Host Control boundaries.

##### Финальный v4 Repository / Public-Release Audit

**Статус: ✅ PASS. Audit начат 2026-10-05 на freeze commit `fe34f9dc97f0a6441dde9fcfe865e34ad8696c32` и завершён 2026-10-07 после remediation, clean-room acceptance, финальных pre-public scans и public/PVR acceptance.**

Канонический versioned report: [`docs/audits/v4-final-audit-2026-10-05.md`](audits/v4-final-audit-2026-10-05.md). Findings #234–#246 закрыты либо получили documented disposition; unresolved Critical/High/security/data-integrity Medium blockers отсутствуют. Final pre-public history/current-tree и retained-Actions scans завершены PASS на frozen SHA `c6066c1ab77e019970a70ebfa7242a66a41ba8a3`, после чего repository переведён в public и Private Vulnerability Reporting проверен с внешней стороны.

A-007/#240 на момент private baseline был принят как owner residual risk. После public transition finding технически закрыт: `main` защищён active GitHub ruleset **Protect main release path**, а `refs/tags/v*` — active ruleset **Protect release tags** (update/delete/non-fast-forward blocked, no bypass).

Историческая freeze-запись сохраняется для audit trail: **Активный gate:** провести полный финальный repository/public-release audit — этот gate теперь закрыт PASS.

Цель этого gate была не в поверхностном source review, а в воспроизводимом release-readiness audit всего repository/deployment surface. После его закрытия новый product scope переносится в v5.x; v4.x остаётся только для действительно необходимых security/reliability/data-integrity hotfixes.

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

#### Мультиформатные подписки: raw / Xray JSON / Clash-Mihomo

**Статус: ⬜ Отложено. Не является блокером final v4 feature freeze, repository/public-release audit или открытия базового Client Portal v5. Реализация допускается отдельным compatibility track после закрытия текущих обязательных gates.**

Цель — не заменить существующий raw subscription path новым форматом, а добавить явную capability-модель нескольких представлений одной subscription identity. Один и тот же пользовательский `sub_id` может иметь несколько provider/client-facing представлений, но lifecycle подписки, entitlement и ownership остаются едиными.

Текущий v4 baseline остаётся каноническим:

- основной machine subscription — raw/share-link формат из 3x-ui: строки `vless://`, `vmess://`, `trojan://`, `vpn://` и другие поддерживаемые протоколы;
- `subEncrypt=true` означает Base64 encoding raw body и **не является криптографическим шифрованием**;
- `subscription_proxy.py` сейчас рассчитан именно на raw/HTML/info contract: проверяет локальную ownership по `sub_id`, проксирует штатную HTML page/assets, обрабатывает `?format=info` как metadata response и выполняет только reviewed client-compat transformations для raw machine subscription;
- существующие raw compatibility rules включают reviewed HWID/device header forwarding, AmneziaWG compatibility handling и узкий Shadowrocket fix для VLESS + XHTTP + Reality; эти правила не должны автоматически переноситься на JSON/YAML body без отдельного design review;
- raw path остаётся наиболее универсальным форматом и не должен исчезать даже после добавления других outputs.

##### Форматы 3x-ui и важное различие `format=info`

В актуальной subscription subsystem 3x-ui один Sub ID может обслуживаться несколькими отдельными paths:

~~~text
raw/share links  → subPath
Xray JSON        → subJsonPath  (subJsonEnable)
Clash/Mihomo     → subClashPath (subClashEnable)
~~~

Точные setting names/default paths перед implementation должны быть повторно проверены относительно **pinned 3x-ui version/contract**, а не приниматься из upstream `main` автоматически.

`?format=info` на обычном subscription path не является Xray JSON subscription. Это отдельный metadata/view-model response для traffic/expiry/status/UI polling. Нельзя использовать его как замену полноценному JSON client config и нельзя называть его JSON-подпиской в UI/API.

##### Семантическая разница raw и Xray JSON

Raw/share-link subscription передаёт прежде всего параметры отдельных соединений:

~~~text
server address / port
protocol
client UUID/password
transport
TLS/Reality parameters
SNI/serverName
public key / short id
flow
other protocol-specific URI parameters
~~~

После импорта клиент сам строит собственную runtime configuration, DNS, routing, selector/group policy и local inbounds.

Xray JSON представляет уже более целостную Xray client configuration. Помимо proxy outbounds он может включать:

~~~text
inbounds
outbounds
DNS
routing rules
policy
mux/observatory и другие Xray-native sections
~~~

Поэтому JSON полезен там, где оператор действительно хочет централизованно задавать Xray-native DNS/routing/policy и клиент гарантированно понимает такой format.

Для простой VLESS + Reality ноды JSON сам по себе не создаёт нового transport capability: те же connection parameters уже выражаются обычной `vless://` ссылкой. Переход на JSON не нужен только ради явного data-plane IP, Reality SNI, public key или `xtls-rprx-vision`.

##### Data-plane address и protocol identity

Новый format не должен отменять принятый v4.x addressing contract.

Для любого client-facing representation должны одновременно сохраняться два независимых свойства:

~~~text
dial address  = operator-owned data-plane address
protocol identity = TLS/Reality SNI/serverName и другие identity fields
~~~

Пример корректной семантики:

~~~text
dial:       203.0.113.42:443
Reality SNI: www.example.com
~~~

В raw это выражается через host/IP в URI и отдельный `sni=`/Reality parameter. В Xray JSON — через `address`/port и отдельный `realitySettings.serverName` или эквивалентный pinned-schema field.

Acceptance нового JSON path обязан доказать, что operator-managed `shareAddrStrategy=custom` + `shareAddr` приводит к ожидаемому client dial endpoint и при этом не переписывает Reality/TLS identity, transport settings или keys.

Если конкретная версия 3x-ui JSON generator ведёт себя иначе, format нельзя считать принятым только потому, что endpoint возвращает HTTP 200. Silent DNS→IP persistence, неявная подмена SNI или скрытый rewrite JSON со стороны proxy запрещены без отдельного documented contract.

##### Protocol coverage и честная деградация

Raw, Xray JSON и Clash/Mihomo не считаются эквивалентными по protocol coverage.

По текущему upstream 3x-ui contract AmneziaWG и TUIC присутствуют в raw/share-link и Clash/Mihomo outputs, но исключаются из Xray JSON output. Перед implementation это поведение нужно перепроверить на pinned 3x-ui release.

Следствия:

- JSON не может автоматически стать единственным subscription format для пользователя, которому нужен AmneziaWG или TUIC;
- отсутствие protocol entry в JSON не должно маскироваться как полноценный parity success;
- UI/client capability layer должен уметь показать, что выбранный format не покрывает все назначенные пользователю protocols;
- запрещено синтетически переводить AmneziaWG/TUIC в «похожий» Xray outbound ради видимости parity;
- raw остаётся fallback/canonical broad-compat path;
- Clash/Mihomo рассматривается как отдельная capability, а не как «тот же JSON в YAML».

##### Целевая capability model

Формат подписки должен стать явной capability, а не набором scattered client-name checks.

Логическая модель может выглядеть так:

~~~text
subscription formats:
- raw_links
- xray_json
- mihomo_yaml

capabilities:
supports_raw_links
supports_xray_json
supports_mihomo
supports_hwid_headers
supports_protocol:<name>
supports_server_routing
~~~

Точные имена не являются контрактом. Важен принцип: Client Portal/domain layer спрашивает доступные formats/capabilities, а не делает ветвления вида `if client == "Hiddify"` или `if provider == "3xui"` в нескольких UI handlers.

Выбор format должен быть deterministic:

- explicit user/client choice либо documented capability mapping;
- stable URL/path;
- без случайного переключения body format только по `User-Agent`, если это меняет semantics;
- один `sub_id` остаётся stable subscription identity;
- rotation/revocation subscription identity должна согласованно инвалидировать все её representations.

User-Agent detection допускается только как bounded compatibility hint для уже доказанного client-specific workaround, как в текущих узких raw fixes. Он не должен становиться единственным источником истины о требуемом subscription format.

##### Архитектура compatibility proxy

Текущий `/compat/{sub_id}` не следует превращать в универсальный parser/rewriter всех subscription formats.

Рекомендуемая схема:

~~~text
                         3x-ui
                           │
             ┌─────────────┼──────────────┐
             │             │              │
          raw/sub       Xray JSON     Clash/Mihomo
             │             │              │
             ▼             ▼              ▼
      raw compat path   thin facade    thin facade
      (если нужен)      (если нужен)   (если нужен)
             │             │              │
             └─────────────┴──────────────┘
                           │
                     Client Portal
~~~

Правила:

- raw compat path сохраняет существующие proven transformations;
- JSON path не должен проходить через raw Base64/share-link parser;
- YAML path не должен проходить через JSON parser только ради унификации;
- если provider-native URL безопасно и совместимо работает напрямую, proxy не добавляется без причины;
- если proxy нужен для ownership/public URL/HWID/client compatibility, он остаётся thin facade с фиксированным upstream template/path;
- Telegram callback/user input не может передавать arbitrary upstream URL, path, Host header или provider endpoint;
- content type и body format сохраняются корректно;
- response size/timeouts bounded;
- redirects и origin changes не должны утекать auth/device headers на другой origin;
- `Cache-Control: no-store`/privacy semantics сохраняются там, где body содержит customer credentials.

##### HWID / device metadata

Наличие JSON endpoint не означает автоматически, что HWID enforcement работает идентично raw path.

Перед production support нужно отдельно проверить для pinned 3x-ui/client combination:

- передаёт ли конкретный JSON-capable client `X-HWID`;
- какие device metadata headers он использует;
- применяет ли 3x-ui тот же HWID gate к JSON path;
- какие status/headers возвращаются при missing/unsupported HWID;
- поведение при full device limit;
- не меняется ли registration semantics при refresh JSON subscription.

Если JSON идёт через bot compatibility facade, разрешён только тот же reviewed allowlist HWID/device headers, который нужен реальному upstream contract. Значения HWID не логируются, не записываются в audit и не используются как synthetic/fallback identity.

Нельзя «чинить» JSON-клиент, который не умеет HWID, генерацией fake HWID на proxy. Unsupported client должен оставаться честным unsupported state.

##### Client compatibility matrix

До показа альтернативных formats в Client Portal нужна явная проверяемая matrix минимум по используемым клиентам и версиям.

Для каждого client необходимо хранить/документировать:

~~~text
raw links: supported / unsupported
Xray JSON: supported / unsupported / partial
Mihomo YAML: supported / unsupported
HWID header: yes / no / unknown
Reality: supported
XHTTP: supported
AmneziaWG: supported
TUIC: supported
known compatibility workaround
last verified client version/date
~~~

Matrix должна опираться на production-like smoke/tests, а не только на заявление приложения о поддержке «Xray/V2Ray».

Raw path нельзя удалить только потому, что один preferred client хорошо работает с JSON.

##### Server-managed DNS/routing

Главное функциональное преимущество Xray JSON — возможность централизованно передать Xray-native DNS/routing/policy.

Это одновременно увеличивает blast radius ошибки.

Поэтому:

- global JSON DNS/routing rules являются operator-owned config, а не произвольным user input;
- изменение routing template проходит отдельный review/regression;
- malformed/unsupported rule не должен молча превращаться в direct-all или proxy-all;
- private/local destinations и DNS behavior должны тестироваться отдельно;
- Client Portal не получает generic editor raw JSON;
- Telegram UI не должен позволять вставлять произвольные Xray snippets;
- provider-specific JSON template не становится источником бизнес-policy entitlement;
- rollback должен позволять отключить JSON format без изменения raw subscription identity.

##### Security boundary

Любой subscription representation остаётся customer secret/credential-bearing artifact.

Обязательные правила:

- полный subscription URL и `sub_id` не пишутся в общий audit/log/errors;
- JSON/YAML body не сохраняется в diagnostics/job details;
- server private keys никогда не попадают в client output;
- bot проверяет локальную ownership `sub_id` перед выдачей compat representation;
- unknown/invalid `sub_id` fail closed;
- provider endpoint/path задаётся только operator-owned config;
- никаких arbitrary remote fetch/proxy callbacks;
- TLS verification не отключается ради compatibility;
- URL query/headers из клиента проксируются только по explicit allowlist;
- секретные/device headers не forward'ятся на другой origin после redirect;
- unsupported/partial format не возвращается как ложный полноценный success.

##### Failure semantics

Новый format должен сохранять понятную ошибочную семантику:

- network timeout/upstream outage → bounded gateway/provider unavailable;
- malformed JSON/YAML → format generation failure, а не raw fallback под тем же content type;
- unknown subscription → not found/fail closed;
- HWID rejection → отдельный диагностически полезный state с allowlisted headers без раскрытия HWID;
- unsupported protocol mix → explicit partial/unsupported capability либо format не предлагается;
- lost upstream response не создаёт новую subscription identity и не запускает mutation;
- refresh format является read operation и не должен менять entitlement/provisioning state, кроме документированной provider-side device-registration semantics.

##### Implementation sequence

Если track будет открыт, рекомендуемый порядок:

1. зафиксировать pinned 3x-ui subscription-server contract для raw/JSON/Clash paths и relevant settings;
2. добавить regression fixture/contract для текущего raw behavior до любых изменений;
3. ввести internal `SubscriptionFormat`/capability abstraction без изменения production URL;
4. добавить read-only provider capability discovery/config;
5. включить JSON subscription только на isolated/test 3x-ui environment;
6. проверить VLESS TCP Reality и XHTTP Reality: address/port, UUID, flow, SNI, public key/short ID и transport parity;
7. отдельно проверить operator-managed data-plane IP + неизменный Reality SNI;
8. проверить mixed subscription с AmneziaWG/TUIC и зафиксировать truthful unsupported/partial semantics;
9. проверить HWID-capable и HWID-incapable clients;
10. только при доказанной необходимости добавить thin JSON compat facade;
11. добавить Client Portal/UI выбор формата только после готовой capability matrix;
12. провести controlled production canary на test user/cohort;
13. сохранить мгновенный rollback: disable JSON/Clash presentation без изменения raw URL/`sub_id`.

##### Regression / acceptance gate

Минимальный acceptance pack:

1. existing raw subscription byte/semantic behavior не регрессирует;
2. HTML subscription page и assets продолжают работать;
3. `?format=info` остаётся metadata path и не смешивается с Xray JSON;
4. JSON feature выключен → JSON URL не рекламируется клиенту;
5. JSON feature включён → валидный known user получает корректный content type/body;
6. unknown/stale `sub_id` fail closed;
7. VLESS TCP Reality raw vs JSON имеют одинаковые dial/identity semantics;
8. VLESS XHTTP Reality raw vs JSON сохраняют transport/Reality fields без случайного Shadowrocket-only rewrite;
9. `shareAddrStrategy=custom` + explicit `shareAddr` отражается ожидаемым dial address;
10. SNI/Reality identity остаётся неизменной при IP dial address;
11. AmneziaWG/TUIC absence в JSON отображается честно и raw path продолжает их выдавать;
12. HWID missing/unsupported/limit/reached behavior проверен для заявленных JSON clients;
13. reviewed HWID/device headers не логируются и не утекут на другой origin;
14. malformed/upstream unavailable response fail closed без подмены format;
15. no subscription URL/`sub_id`/HWID/private key leakage в logs/audit/jobs;
16. реальный импорт/refresh минимум в одном поддерживаемом Xray JSON client проходит end-to-end;
17. текущие production raw clients проходят regression smoke;
18. disable/rollback JSON возвращает систему к raw-only без rotation subscription identity.

Если позже добавляется Clash/Mihomo, для него выполняется отдельный format-specific acceptance, включая YAML parsing, protocol coverage, routing rules и реальные Mihomo clients. Успешный JSON smoke не считается автоматическим acceptance Clash/Mihomo.

##### Definition of Done

Track считается завершённым только когда:

- raw остаётся стабильным canonical/fallback format;
- JSON/Clash появляются как явные capabilities, а не неявная замена raw;
- client capability matrix документирована и подтверждена smoke;
- data-plane IP и protocol identity сохраняют принятый addressing contract;
- unsupported protocol combinations отображаются честно;
- HWID behavior не ослаблен и synthetic identity отсутствует;
- proxy остаётся thin, fixed-target и secret-safe;
- provider-neutral subscription/domain layer не зависит от 3x-ui-specific path names;
- rollback не требует изменения `sub_id`, entitlement или provisioning;
- README/Admin Setup/subscription docs/security notes и regression tests обновлены в том же implementation track.

До открытия этого track текущая production policy не меняется: raw subscription + существующий `subscription_proxy.py` остаются каноническим и проверенным путём.

#### Provider-neutral Control Plane и поддержка Remnawave

**Статус: ⬜ Отложено. Не является текущим блокером финального v4.x freeze, repository/public-release audit или открытия базового Client Portal v5. Реализация допускается только отдельным архитектурным треком после закрытия текущих обязательных gates.**

Цель — не создавать отдельный fork Telegram-бота под Remnawave и не встраивать в Client Portal условные ветки вида `if backend == "3xui"`. Вместо этого текущий проект должен получить provider-neutral boundary, где Telegram UI, commerce, entitlement, audit и customer-facing workflows работают с едиными domain-сущностями, а различия 3x-ui и Remnawave изолированы в отдельных adapters/providers.

Целевая высокоуровневая схема:

~~~text
                 Telegram Bot
                     │
          ┌──────────┴──────────┐
          │                     │
       /start                 /admin
   Client Portal          Admin Control Plane
          │                     │
          └──────────┬──────────┘
                     │
               Domain Services
                     │
          ┌──────────┼───────────┐
          │          │           │
       Orders     Payments   Entitlements
                                │
                         Provisioning
                                │
                     ControlPlaneRegistry
                          ↙          ↘
                    3xUIProvider  RemnawaveProvider
~~~

Ключевой принцип: локальная business-domain модель бота остаётся источником истины для customer/order/payment/entitlement lifecycle. Ни 3x-ui client, ни Remnawave User не становятся эквивалентом локального Customer. Remote control plane считается исполняющим provider-слоем, который может быть временно недоступен, заменён или мигрирован без потери бизнес-состояния.

##### Provider-neutral domain boundary

До добавления Remnawave provider-specific calls должны быть вытеснены из Client Portal и по возможности из верхнего слоя Admin UI за интерфейс уровня domain capabilities.

Рекомендуемая логическая граница:

~~~text
control_plane/
├─ base.py
├─ models.py
├─ capabilities.py
├─ registry.py
├─ xui.py
└─ remnawave.py
~~~

Точное имя модулей не является контрактом, но separation of concerns является обязательным.

Минимальный provider-neutral API должен оперировать действиями уровня продукта, а не конкретными HTTP endpoints панели:

~~~text
get_user()
create_user()
update_user()
enable_user()
disable_user()
delete_user()

get_usage()
reset_traffic()

get_access()
set_access()
reconcile_access()

get_subscription()
rotate_subscription()

get_devices()
delete_device()
get_device_limit()

get_nodes()
get_node_health()
~~~

Client Portal и общие domain services не должны импортировать `XUIClient` или `RemnawaveClient` напрямую.

##### Capability model

3x-ui и Remnawave не обязаны поддерживать полностью одинаковый набор операций. Вместо provider-name branching UI и services должны использовать явный capability contract, например:

~~~text
supports_traffic
supports_reset_traffic
supports_subscription_url
supports_subscription_rotation
supports_hwid_devices
supports_device_delete
supports_device_limit
supports_access_reconcile
supports_node_health
supports_graceful_drain
~~~

Если capability отсутствует, UI скрывает или корректно дизейблит действие, а backend authorization/service layer всё равно остаётся финальной защитой. Presentation hiding не заменяет backend validation.

Новые provider-specific возможности не должны автоматически расширять общий contract. Сначала определяется стабильная domain-семантика, затем capability добавляется в интерфейс.

##### Локальная модель Customer / Subscription / Provider Binding

Client Portal не должен моделировать:

~~~text
Telegram user = 3x-ui client
~~~

или:

~~~text
Telegram user = Remnawave User
~~~

Целевая модель:

~~~text
Customer
  ↓
Entitlement
  ↓
Subscription
  ↓
Provider Binding
~~~

Минимально provider binding должен хранить:

- локальный stable subscription/customer identity;
- `provider_type`;
- stable remote user identity;
- remote subscription identity, если она отделена от user identity;
- provider-specific immutable/stable identifiers, необходимые для safe read-back;
- lifecycle/status metadata, достаточные для reconciliation;
- timestamps/version metadata для диагностики drift;
- без хранения remote secrets там, где достаточно ссылочного identifier.

Это позволяет одному Customer иметь несколько subscriptions, включая одновременное использование разных providers.

Пример допустимой модели:

~~~text
Customer
├─ Subscription A
│  ├─ provider: 3x-ui
│  └─ plan: Legacy EU
└─ Subscription B
   ├─ provider: Remnawave
   └─ plan: Premium
~~~

Ограничение "один bot deployment = один VPN backend" не должно закладываться в schema как необратимое архитектурное решение.

##### Plan и provider placement

`Plan` должен описывать коммерческую/доступную пользователю услугу, а provider-specific mapping храниться отдельно.

Допустимая логическая модель:

~~~text
Plan
├─ commercial policy
├─ duration / quota
├─ entitlement rules
└─ placement/access policy
      ↓
Provider Binding / Provider Policy
~~~

Для 3x-ui access policy может сводиться к текущей цепочке:

~~~text
Plan
 ↓
Server Group
 ↓
Nodes
 ↓
Inbounds
 ↓
User
~~~

Для Remnawave целевая access-семантика должна использовать нативные сущности Remnawave:

~~~text
Plan
 ↓
Access Policy
 ↓
Internal Squad(s)
 ↓
User
~~~

При этом инфраструктурная модель Remnawave рассматривается отдельно:

~~~text
Config Profile
 ↓
Inbounds
 ↓
Nodes

Inbound
 ↓
Host
 ↓
client-facing address / connection parameters
~~~

Нельзя пытаться механически переименовать текущий `Server Group` в `Internal Squad` и считать миграцию законченной. Нужен явный mapping layer, потому что сущности имеют разную семантику.

##### Remnawave-native semantics

При реализации adapter необходимо исходить из актуальной архитектуры Remnawave, а не эмулировать 3x-ui:

- Remnawave Panel сама не является Xray data-plane runtime; Xray работает на Remnawave Nodes;
- Node использует один Config Profile, внутри которого активируется набор Inbounds;
- Internal Squad является access-control group и определяет, какие Inbounds доступны назначенным пользователям;
- пользователь может состоять в нескольких Internal Squads;
- Host является client-facing gateway/connection description и связывается с конкретным Inbound; его address/port/SNI и другие параметры относятся к пользовательскому data plane;
- External Squads, если будут использоваться, рассматриваются отдельно как subscription/template/settings override и не смешиваются с Internal Squad access policy;
- HWID Device Limit является optional provider capability, а не обязательным свойством каждой subscription.

Эта модель хорошо сочетается с общим hardening-принципом разделения control-plane address и operator-owned data-plane address: Remnawave Node и Remnawave Host не должны схлопываться в одну локальную сущность только ради совместимости со старой моделью.

##### Provisioning / reconcile

Текущий `ProvisioningEngine` не должен быть выброшен только из-за добавления второго provider. Его policy/reconcile роль сохраняется, но provider-specific primitives должны быть вынесены ниже.

Для 3x-ui desired/current state остаётся связан с managed Inbounds.

Для Remnawave рекомендуемая базовая модель:

~~~text
desired Internal Squad UUIDs
vs
current active Internal Squads
~~~

Safe reconcile:

- добавляет отсутствующие required managed squads;
- не удаляет дополнительные access assignments;
- после mutation выполняет read-back;
- uncertain mutation не повторяется автоматически.

Strict reconcile:

- сначала добавляет недостающий required access;
- подтверждает post-condition;
- затем удаляет только managed extras, которые больше не входят в policy;
- не трогает unmanaged/operator-owned assignments;
- не должен оставлять пользователя без требуемого рабочего access path;
- uncertain result переводится в explicit unknown/interrupted state и требует read-back/replan, а не POST replay.

Provider adapters обязаны сохранять существующий no-retry safety contract для state-changing операций: timeout/lost response/5xx после возможного применения mutation не является основанием для слепого повторения запроса.

##### Client Portal

`/start` должен оставаться полностью provider-neutral.

Пользовательские разделы:

- Профиль;
- Моя подписка;
- Купить / продлить;
- Трафик;
- Устройства;
- Помощь;

работают через Subscription / Entitlement / Provisioning services, а не через прямые control-plane callbacks.

Одинаковый UI может показывать нормализованный subscription summary:

~~~text
status
expires_at
traffic_used
traffic_limit
device_limit
subscription_url
~~~

но поле отображается только если provider/capability реально даёт достоверное значение.

Факт использования 3x-ui или Remnawave не обязан быть customer-facing detail.

##### Subscription subsystem

Для Remnawave сначала следует использовать нативную subscription subsystem и не переносить автоматически весь текущий 3x-ui compatibility proxy.

При Remnawave integration необходимо отдельно проверить:

- native subscription URL и lifecycle;
- subscription templates;
- client compatibility;
- HWID behavior;
- error semantics при unsupported/missing HWID;
- device list/delete behavior;
- rotation/revocation semantics;
- browser subscription page;
- headers, caching и privacy behavior.

`subscription_proxy.py` может остаться для 3x-ui и legacy compatibility. Для Remnawave собственный proxy допускается только при доказанной необходимости и должен быть тонким compatibility facade, а не дублировать всю subscription logic панели.

Нельзя вводить synthetic HWID, обходить provider enforcement или скрывать несовместимость клиента под ложным success.

##### Devices / HWID

Общий Client Portal API может предоставлять:

~~~text
get_devices()
delete_device()
get_device_limit()
~~~

но provider adapter обязан возвращать capabilities и source semantics.

Для Remnawave HWID limit считается optional; поддержка зависит от client приложения и фактической передачи HWID header. UI должен различать:

- device management supported;
- HWID enforcement enabled;
- limit disabled for конкретного пользователя;
- unsupported client/no HWID;
- limit reached;
- provider error/unknown.

IP observations не должны переименовываться в физические устройства и не должны использоваться как замена HWID inventory.

##### Admin Infrastructure UI

При включённом Remnawave provider инфраструктурный UI не должен притворяться 3x-ui UI с переименованными labels.

Рекомендуемая модель раздела Remnawave:

~~~text
🌐 Инфраструктура
├─ 🖥 Ноды
├─ ⚙️ Config Profiles
├─ 📡 Inbounds
├─ 🌍 Hosts
├─ 👥 Internal Squads
└─ 🩺 Состояние
~~~

В multi-provider deployment допустимо сначала показывать выбор provider/context, затем provider-native entities.

Stable callback identity должна использовать стабильные UUID/IDs Remnawave, а не display name.

##### Host Control / node lifecycle

Текущий Host Control Agent остаётся 3x-ui-specific boundary для точного allowlist управления `x-ui.service` и не должен искусственно расширяться до generic shell/container agent ради Remnawave.

Для Remnawave:

- сначала используются только documented provider API operations;
- если позже потребуется host/container control, проектируется отдельный restricted Remnawave Node Agent;
- agent не получает generic shell/SSH/exec/file browser/Docker API surface;
- разрешённые actions фиксируются allowlist;
- mutation имеет operation ID, persistent journal и no-replay semantics;
- потерянный POST response восстанавливается только read-only operation lookup;
- credentials отдельны от panel/API/bot/backup credentials;
- lifecycle нового agent проходит отдельный threat model, deploy runbook и acceptance.

##### Graceful Node Drain

Концепт Node Drain сохраняется, но 3x-ui алгоритм attach-alternative-Inbound → prove → detach-target-Inbound нельзя напрямую копировать в Remnawave.

Перед реализацией Remnawave Drain нужен отдельный model/preflight, который как минимум определяет:

- target Node UUID;
- Config Profile и активные Inbounds target Node;
- Hosts, через которые этот Node представлен клиентам;
- Internal Squads/users, которым доступен соответствующий Inbound;
- существующие альтернативные Hosts/Nodes для той же access policy;
- blockers, при которых безопасного alternative path нет;
- active/unknown provider state;
- bounded review до mutation.

Mutation plan должен менять routing/visibility/access только после доказанного alternative path и завершаться read-back verification. Никакой автоматический destructive Stop/Restart Node не является частью graceful drain по умолчанию.

Partial/unknown/interrupted operation не replay-ится после restart; требуется новый preflight/replan.

##### API contract и dependency policy

Для Remnawave не следует делать production integration зависимой от случайного community SDK или archived/unmaintained SDK.

Предпочтительный подход повторяет существующий 3x-ui contract discipline:

~~~text
contracts/
├─ 3xui/
│  └─ ...
└─ remnawave/
   ├─ contract.json
   └─ openapi.json
~~~

Требования:

- pin поддерживаемой версии/commit/ref Remnawave API schema;
- хранить hash/source metadata;
- локальный typed/minimal HTTP client только для реально используемых endpoints;
- contract gate проверяет методы, auth, request/response shapes и критические поля;
- upstream schema drift не принимается автоматически;
- unknown/breaking changes fail closed;
- upgrade Remnawave требует отдельного compatibility PR/gate;
- provider-specific runtime exceptions документируются явно и тестируются.

##### Auth / RBAC

Telegram RBAC остаётся независимым от Remnawave authorization model.

Role names `Read-only`, `Support`, `Administrator`, `Owner` сохраняются как локальная security boundary.

Для Remnawave credentials:

- использовать least-privilege scoped token/API credential, если provider это позволяет;
- не выдавать боту глобальные права без необходимости;
- mapping локального privilege → provider capability/action фиксируется централизованно;
- UI filtering использует тот же privilege catalog, что и backend authorization;
- direct/stale callback не обходит privilege check;
- provider credential никогда не попадает в Telegram, audit payload или SQLite в открытом виде.

##### Mutation journal / idempotency / recovery

Provider-neutral mutation layer должен иметь единый safety contract:

- каждая destructive/state-changing workflow имеет локальный operation ID;
- request payload и target stable IDs journal-ятся в минимально необходимом виде;
- secrets/subscription URLs/HWIDs не пишутся в общий audit без необходимости;
- network timeout после отправки запроса считается uncertain;
- автоматический retry mutation запрещён, если provider не предоставляет доказанную idempotency key semantics;
- сначала выполняется provider read-back;
- startup recovery не повторяет mutation;
- состояние после crash/restart — recovered-success / recovered-failed / unknown/interrupted;
- Continue после unknown требует нового plan/preflight, если предыдущий post-condition нельзя доказать.

##### Drift detection и reconciliation

Multi-provider deployment требует явного обнаружения расхождений между local desired state и remote actual state.

Нужно различать:

- expected;
- drifted;
- remote missing;
- local binding missing;
- unmanaged remote assignment;
- provider unavailable;
- uncertain;
- migration pending.

Автоматическое исправление drift допускается только для заранее определённых safe reconcile operations. Destructive correction требует явного workflow/confirmation либо отдельного доказанного safe policy.

##### Миграция 3x-ui → Remnawave

Поддержка Remnawave не должна означать big-bang migration.

Предпочтительный rollout:

1. ввести provider-neutral interfaces, не меняя production behavior 3x-ui;
2. перевести существующие 3x-ui workflows на `3xUIProvider` adapter и доказать behavior parity regression tests;
3. добавить read-only Remnawave client/contract и inventory screens;
4. добавить isolated test Remnawave environment;
5. реализовать create/read/update пользователя и access policy через Internal Squads;
6. добавить subscription/device capabilities;
7. выполнить controlled canary на тестовых users;
8. разрешить новым subscriptions выбирать Remnawave placement;
9. только после soak рассматривать миграцию существующих subscriptions;
10. legacy 3x-ui users могут продолжать обслуживаться параллельно до отдельного решения о retirement.

Миграция конкретного пользователя должна быть отдельной state machine, а не набором ручных callbacks.

Минимальные стадии:

~~~text
planned
preflight_ok
target_created
target_access_proven
subscription_ready
cutover_pending
cutover_proven
source_retirement_pending
completed
failed
unknown
~~~

До доказанного target access source account не удаляется автоматически.

Rollback semantics должны быть определены до первого production canary.

##### Commerce и entitlement при нескольких providers

Payment confirmation и entitlement остаются provider-neutral.

Критический контракт:

~~~text
payment = confirmed
        ↓
entitlement = provisioning
        ↓
provider provisioning
~~~

Provider outage не имеет права превращать уже подтверждённый payment в failed/unpaid.

Допустимые состояния:

~~~text
payment: confirmed
entitlement: provisioning
provider: unavailable
~~~

После восстановления provider reconcile продолжает entitlement workflow с read-back/idempotency safeguards.

Provider selection не должен зависеть от Telegram message history. Решение placement должно быть persistent и auditable.

##### Observability / Attention Center

Multi-provider слой должен давать одинаково диагностируемые состояния:

- provider availability;
- auth failure;
- API compatibility mismatch;
- latency/timeouts;
- user/access drift;
- failed/unknown provisioning operations;
- subscription/device capability degradation;
- node/host health;
- migration state.

Attention Center может агрегировать эти данные, но не должен смешивать разные причины в одно "provider error".

Provider name, operation ID, stable remote target ID и last verified state допустимы в технической диагностике; secrets и customer subscription URLs — нет.

##### Backup / restore

Локальный Full Backup должен включать только те provider bindings/policies/journals, которые принадлежат самому боту.

Он не считается backup Remnawave Panel/Node infrastructure.

Отдельно должны быть документированы:

- какие remote provider данные восстанавливаются самим Remnawave;
- какие локальные mappings требуются для reconnect после restore бота;
- поведение при restore старой bot DB против уже изменившегося provider state;
- обязательный post-restore reconciliation/read-only inventory до любых mutations;
- отсутствие автоматического destructive "sync remote to local" после restore.

##### Security / SSRF / network boundary

Remnawave API endpoint является privileged control-plane destination и проходит отдельную конфигурационную validation policy.

Нельзя разрешать admin callback передавать произвольный URL/host/path для provider requests.

Требования:

- endpoint задаётся только operator-owned config;
- HTTPS обязателен для remote production endpoint, кроме отдельно документированного private/local deployment contract;
- auth header/token не пересылается через redirects на другой origin;
- state-changing requests не follow redirects;
- timeouts bounded;
- response body bounded там, где endpoint может вернуть большой payload;
- proxy environment не используется неявно без отдельного решения;
- TLS verification не отключается production toggle'ом из Telegram UI.

##### Regression / acceptance gates

До production включения Remnawave обязательны:

1. provider-neutral architecture regression для существующего 3x-ui behavior;
2. contract tests against pinned Remnawave schema/version;
3. read-only inventory smoke;
4. user create/update/disable/enable/delete safety tests;
5. Internal Squad safe/strict reconcile tests;
6. uncertain mutation / lost response tests без replay;
7. subscription URL secrecy tests;
8. HWID/device capability tests, включая unsupported client;
9. RBAC/IDOR/callback stable-ID tests;
10. multi-provider customer ownership isolation;
11. restart/startup recovery tests;
12. backup/restore binding reconciliation tests;
13. migration/cutover rollback test;
14. production canary на отдельной безопасной cohort;
15. soak минимум через restart/deploy/reconcile cycle;
16. documented disable/fallback path.

Remnawave rollout не считается принятым только потому, что API отвечает `200`.

##### Definition of Done

Отложенный Remnawave track считается архитектурно завершённым только когда:

- Client Portal не содержит provider-name branching для обычных customer workflows;
- 3x-ui остаётся полностью рабочим через свой adapter;
- Remnawave работает через отдельный provider adapter и pinned contract;
- один deployment может безопасно обслуживать subscriptions разных providers;
- local payment/entitlement state не зависит от availability конкретной панели;
- access reconcile имеет provider-specific реализацию с общими safety invariants;
- subscription/device UI определяется capabilities;
- provider credentials и remote stable IDs защищены и минимизированы;
- mutation replay после timeout/restart отсутствует;
- migration 3x-ui → Remnawave имеет canary/rollback/recovery path;
- Admin UI показывает provider-native infrastructure model, а не вводящую в заблуждение 3x-ui эмуляцию;
- runbooks, Admin Setup, security model, backup/restore docs и acceptance evidence обновлены в том же implementation track.

До начала implementation отдельный design PR должен уточнить точную версию Remnawave, pinned API contract, перечень используемых endpoints, локальную schema migration, capability matrix и rollout plan. Этот roadmap-пункт фиксирует направление архитектуры, но не разрешает обход текущих v4 closure gates и не превращает Remnawave в скрытую зависимость базового Client Portal.


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

### Post-public governance hardening

**Статус: ✅ Выполнено 2026-10-07. A-007 технически закрыт полностью.**

После перевода repository в public GitHub-side governance подтверждён двумя active rulesets.

Branch ruleset **Protect main release path** (ID `24575428`):

- PR обязателен;
- merge только `squash`;
- strict required checks `test` и `title`;
- deletion и non-fast-forward запрещены;
- linear history обязательна;
- bypass actors отсутствуют.

Tag ruleset **Protect release tags** (ID `24615100`):

- target: `refs/tags/v*`;
- enforcement: active;
- `update`, `deletion` и `non_fast_forward` запрещены;
- bypass actors отсутствуют;
- `current_user_can_bypass=never`;
- creation новых release tags не запрещена, поэтому штатный release workflow сохраняет возможность публиковать новые `vX.Y.Z`.

После включения ruleset существующий `v4.26.8` по-прежнему указывает на `e096bf436425ea037399e290a5a54f54c729b352`.

A-007 больше не имеет residual accepted risk: branch и release-tag paths защищены GitHub-side enforcement, а release workflow остаётся единственным штатным способом публикации новых tags/releases.

### v5.0.0 — Client Portal

**Статус: 🟡 Реализуется в `main`. Backend foundation и pilot Client Portal уже слиты; публичный launch ещё закрыт allowlist/launch-gates.**

Рекомендуемый порядок первой реализации и фактический прогресс:

1. 🟡 customer ownership/auth boundary + feature flag/allowlist без публичного открытия — pilot boundary действует через существующий allowlist/admin policy; public signup, dedicated abuse/rate-limit policy и полный ownership audit ещё не завершены;
2. ✅ persistent Order / Payment / Entitlement states и migration contract — PR #290–#294 + checkout schema v8, atomic payment confirmation, webhook journal, restart reconciliation и durable checkout identity;
3. ✅ provider-neutral customer/subscription service boundary поверх текущего 3x-ui provisioning — `client_access.py` работает через `CustomerPortalService`, provider contract задан `CustomerAccessProvider`, а текущие 3x-ui reads изолированы в `customer_provider_xui.py`; Telegram handlers больше не импортируют `XUIClient`, `Database` или `CommerceService` напрямую;
4. ✅ read-only Client Portal skeleton: Профиль / Моя подписка / Трафик / Устройства / Помощь — PR #296; legacy `/create` / `/inbounds` больше не являются mutation-entrypoints;
5. 🟡 commerce flow + authenticated/idempotent payment event journal — backend journal/state machine и provider-neutral checkout foundation готовы; следующий production path использует native Telegram Stars (`XTR`) для цифровой подписки внутри бота: отдельная Stars-цена тарифа, pre-checkout ownership/amount validation и atomic `successful_payment → Payment confirmed → Order paid → Entitlement` реализуются; после #305 Terms acceptance, `/paysupport` и one-shot refund journal/операторский flow реализованы; остаются test/prod payment smoke и production acceptance;
6. ✅ entitlement → provisioning/reconcile с no-replay/unknown semantics — PR #292/#295; durable pending worker не replay'ит `provisioning` с uncertain outcome;
7. 🟡 onboarding/QR UX и self-service diagnostics реализуются в #306: platform selection, local/private QR и read-only entitlement/provider diagnostics; client-specific deep-link остаётся отложен до стабильного безопасного import contract;
8. 🟡 отдельный v5 launch audit выполняется в #308: repository-verifiable ownership/payment/secret/rollback controls закреплены regression gate; production Stars acceptance, failure/restart canary и load/soak остаются release blockers; retention-policy disposition закрыт в `docs/DATA_RETENTION.md`;
9. ⬜ controlled canary rollout по описанному ниже gate;
10. ⬜ только после canary — расширение публичного доступа.

Фактическая v5 foundation-линия на 2026-10-07: #290–#303 уже в `main`, а #304 остаётся открытым draft PR.

После #302 core backend path уже собран сквозным каркасом: `Plan/Order → checkout boundary → Payment → authenticated webhook → Entitlement → Provisioning`. Для цифровой подписки внутри Telegram #304 переводит customer payment entrypoint на native Telegram Stars вместо внешнего PSP checkout. После merge production commerce блокируют уже не выбор PSP, а Stars acceptance: #305 закрывает Terms acceptance UX, `/paysupport` и one-shot refund workflow через Telegram Bot API; после него остаются test/prod payment smoke и controlled canary.

- #290 — commerce foundation;
- #291 — atomic `payment.confirmed → order paid → entitlement`;
- #292 — entitlement → safe provisioning;
- #293 — authenticated payment webhook gateway;
- #294 — payment-event restart reconciliation;
- #295 — durable entitlement fulfillment worker;
- #296 — pilot Client Portal shell;
- #297/#298 — subscription browser compatibility hotfixes, необходимые для корректной customer subscription page;
- #300 — отдельные nginx limits для `/compat/assets/`, подтверждённые на Safari/WebKit;
- #301 — provider-neutral customer service boundary: Client Portal больше не зависит напрямую от `XUIClient`/DB/Commerce;
- #302 — provider-neutral checkout foundation, schema v8, durable checkout URL/idempotency и Telegram payment button.
- #304 (текущий срез) — native Telegram Stars для цифровой подписки: schema v9, независимая Stars-цена тарифа, XTR invoice/pre-checkout/successful-payment lifecycle.

До перехода к public launch основными implementation-блокерами остаются production acceptance Telegram Stars (после #305 остаются test/prod smoke и acceptance возвратов), после #306 остаются client-specific deep-link при наличии стабильного import contract, production Stars smoke/acceptance, затем launch audit + controlled canary.

Отложенные tracks **не блокируют** базовый v5.0.0: multi-format subscriptions, Remnawave/provider-neutral multi-provider expansion и Cheburcheck Probe fleet могут идти отдельными subsequent tracks после стабилизации core Client Portal. При этом верхний customer/domain слой v5 сразу проектируется так, чтобы не зависеть напрямую от `XUIClient`.

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

## Текущий статус v5 Client Portal — 2026-10-07

- 🟡 commerce/payment/entitlement foundation, Telegram Stars, onboarding/self-service diagnostics и launch safety controls уже реализованы в `main`;
- 🟡 отдельный v5 launch audit выполнен: repository-verifiable controls закреплены regression gate;
- 🟡 retention/data-minimization policy и production acceptance runbook находятся в `main` после #309;
- 🟡 #310 реализует immutable `v5.0.0-rc.N` prerelease/deploy path для controlled canary;
- ⬜ после merge #310 требуется отдельный release-prep `release: v5.0.0-rc.1`;
- ⬜ на опубликованном RC требуется фактический production acceptance по `docs/V5_PRODUCTION_ACCEPTANCE.md`: Stars happy path/refund, failure/restart/reconciliation, ownership/isolation, abuse/load/soak и rollback;
- ⬜ stable `v5.0.0` публикуется только после PASS acceptance без unresolved Critical/High и без необъяснимых payment/entitlement/provisioning inconsistencies;
- ⬜ broad public access / снятие pilot allowlist выполняется только после успешного controlled rollout; публикация stable tag сама по себе allowlist не снимает.

Таким образом, ближайшая release sequence: **#310 → `v5.0.0-rc.1` → controlled production acceptance → при необходимости `rc.2+` → PASS → `v5.0.0` → постепенное расширение cohort**.

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
8. **Rollback/disable path** — Client Portal и payment acceptance можно быстро выключить независимыми `CLIENT_PORTAL_ENABLED` / `CLIENT_PAYMENT_ACCEPTANCE_ENABLED` без отключения Admin Control Plane; уже полученный `successful_payment` всё равно фиксируется локально, чтобы не потерять подтверждённую оплату.
9. **Data/reconciliation check** — после canary выполняется сверка orders, payments, entitlements, provisioning state и 3x-ui clients; нет orphaned/duplicate resources или необъяснимых state mismatches.
10. **Soak period** — canary работает достаточное время для прохождения scheduled jobs, expiry/renewal/monitoring циклов и хотя бы одного restart/deploy cycle без новых release-blocking findings.

Критерий выхода из gate:

- нет unresolved Critical/High findings;
- нет необъяснимых payment/entitlement/provisioning inconsistencies;
- error/retry/recovery paths проверены на фактическом deployment;
- rollback/disable procedure проверена;
- только после этого allowlist/feature flag может быть расширен до обычного публичного доступа.

Controlled rollout выполняется на опубликованном immutable `v5.0.0-rc.N` GitHub prerelease, а не на произвольном `main`. Результат фиксируется отдельным acceptance report с exact release tag/SHA, cohort scope, проверенными сценариями, найденными findings и итоговым решением о расширении доступа. Канонический runbook и evidence contract: `docs/V5_PRODUCTION_ACCEPTANCE.md`.

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