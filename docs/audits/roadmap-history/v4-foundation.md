## Граница v4.x / v5.x

### Линейка v4.x — финализация Admin Control Plane

До перехода на `v5.0.0` основной приоритет — довести административную часть `/admin` до финального production-состояния.

В v4.x входят:

- завершение и полировка административных workflows;
- операции с инфраструктурой, нодами и серверным парком;
- monitoring, audit, jobs, backups и disaster recovery;
- admin roles и privilege boundaries;
- базовые операции выдачи доступа и сверки состояния;
- Plans / Server Groups / Payments / Promo Codes как административные и backend-сущности;
- укрепление эксплуатационной безопасности, инструменты миграции/восстановления и регрессионное покрытие;
- исправления UX/навигации `/admin`;
- backend prerequisites, необходимые будущему Client Portal, если они не открывают публичный customer flow.

### Зафиксированные цели финализации v4.x

#### Каталог ролей и привилегий RBAC

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

#### Расширенное резервирование direct nodes

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

#### Безопасное самообновление бота

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

Граница безопасности:

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

##### Восстановление Host Control после запуска

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
- `subscription_proxy.py`: подписки Base64/обычные, выборочное преобразование `vpn://`, ошибки внешнего сервиса и неверный `sub_id`;
- аварийное восстановление: некорректные/неполные резервные копии, целостность, прерванное восстановление и ограничения прав Owner;
- отрицательные authorization tests для sensitive callbacks, чтобы новая mutation не могла случайно стать доступна более слабой роли.

Roadmap не задаёт искусственный глобальный процент coverage. Критерий завершённости — наличие regression tests на security boundaries, state transitions, idempotency/retry semantics и recovery paths перечисленных модулей.

##### Внешнее резервное копирование

**Статус: ✅ Выполнено и принято в production; off-site recovery drill завершён 2026-10-05.**

Encrypted off-site backup опубликован и развернут в production как `v4.18.0` (release commit `1cc730c5929ba8b2fe1152a0db1ade4b1aaa21f9`). Базовый runtime acceptance пройден: exact tag/SHA, container, app version, health, DB и 3x-ui connectivity подтверждены. Full Backup использует checksummed manifest schema 2, S3-compatible transport шифрует canonical archive client-side через AES-256-GCM, local и off-site outcomes записываются раздельно (`backup.daily`/`backup.manual` и `backup.offsite`), после upload обязателен remote download/decrypt/SHA/deep-validation round trip, retention ограничен fixed prefix, а host-side recovery CLI скачивает и проверяет latest external copy перед существующим bootstrap restore flow. Feature выключена по умолчанию и не открывает Telegram доступ к bucket/object key/credentials/filesystem path.

**Приёмка в production завершён 2026-10-05:** на реально внешнем S3-compatible target с dedicated credentials и отдельно сохранённым recovery encryption key создан manual Full Backup; `backup.offsite` завершился `success`, а обязательный upload → HEAD → download → AES-GCM authentication/decrypt → SHA-256/size → повторный deep validation round trip подтверждён. На отдельном recovery VPS host-side CLI получил latest canonical object и завершился `OFFSITE_RECOVERY_OK`; `manifest.version=4.26.4`. Дополнительный bootstrap smoke восстановил `bot.env` и `bot.sqlite3`, поднял container с `APP_VERSION=4.26.4`, Health/DB `ok`; финальный generic upstream TCP probe из изолированного recovery VPS получил timeout, что относится к подготовке полного replacement Master/network path и не входит в критерий этого off-site gate. После smoke recovery bot остановлен, production Master возвращён с Health/DB/3x-ui connectivity `ok`, временное recovery окружение очищено. Секреты bucket credentials/encryption key не публиковались в Telegram/chat/Git.

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

##### Проверка совместимости API 3x-ui и контракта OpenAPI

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

##### Gate перед открытием Client Portal — Клиентский портал

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

Требования к регрессионным проверкам:

- отдельный тест проверяет конкретную Fleet Health строку и запрещает raw direct-node name на этом экране;
- тест списка `Ноды` проверяет одинаковую грамматику статуса Master/direct nodes, включая online/offline/maintenance/unknown варианты;
- navigation regression проверяет, что `admin_menu()` используется только корневым экраном, а `Обзор` имеет локальную навигацию и явный возврат к `Панели администратора`;
- `docs/UI_STYLE.md` остаётся нормативным источником этих правил для следующих UI PR.

Приёмка в production `v4.20.5` закрыт: release развернут в production, и оператор подтвердил успешный targeted smoke по всем трём пунктам — Fleet Health display, симметричный status template списка `Ноды` и локальная навигация `Обзора`. Следующим patch-релизом идёт `v4.20.6` с UI-04, затем последовательность feature-релизов `v4.21.0`–`v4.26.0`; off-site drill и freeze выполняются уже после них.

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

Приёмка в production `v4.20.6` закрыт: release развернут в production, и оператор подтвердил targeted smoke экрана `Мониторинг → Состояние системы`. Общие Master/direct-node labels и statuses отображаются по новому contract, Xray state/version видны у direct node, а Master-only/node-only показатели остаются разделены. Разница RAM представления считается ожидаемой: Master получает used/total из `server_status()`, а агрегированный `NodeInfo` direct node сейчас содержит только `memPct`; дополнительные direct-node API calls ради абсолютных значений не добавляются.

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

Приёмка в production `v4.20.7` закрыт: release развернут в production, и оператор завершил targeted smoke основных operator-facing поверхностей с новым terminology contract — `Обзор`, `Инфраструктура → Inbounds`, карточки Inbound, direct-node Inbounds, карточка пользователя/связи Inbounds, Server Groups, `Мониторинг → Состояние системы`, `Роли и права` и client `/start`. Гибридные формы с апострофом на проверенных поверхностях не обнаружены; runtime/API/DB identifiers и mutation semantics не менялись.

#### v4.20.8 — финальная капитализация Inbound

**Статус: ✅ Выполнено и принято в production в `v4.20.8`.**

Scope ограничен operator-facing строками: оставшийся lowercase `inbound` в edit/clone/delete/error/help flows заменяется на канонические `Inbound` / `Inbounds`. Callback data, audit action ids, API/DB fields, Python identifiers, SQLite schema, provisioning semantics и mutation behavior не меняются. Regression gate отдельно фиксирует это различие между пользовательским термином и technical identifiers.

Приёмка в production `v4.20.8` закрыт: release развернут в production, и оператор успешно завершил targeted smoke по Inbound edit/help prompts, sync/reset confirmations, clone flow, template copy, delete confirmation, user Inbounds copy и Server Group policy text. Проверенные operator-facing поверхности используют канонические `Inbound` / `Inbounds`; destructive actions во время smoke не выполнялись. Callback/API/DB/Python identifiers, SQLite schema, provisioning semantics и mutation behavior не менялись.

#### v4.20.9 — очистка интерфейса оператора после приёмки

**Статус: ✅ Опубликовано в `v4.20.9`; layout follow-up завершён в `v4.20.10`.**

Scope предназначен для небольших presentation findings, найденных уже на production smoke/acceptance и не требующих изменения поведения, storage contract или security boundary.

Подтверждённые findings:

- `Инфраструктура → Inbounds → <Inbound> → Сохранить шаблон`: убрать лишнюю implementation detail `bot.sqlite3` из operator-facing prompt. Канонический текст: `Введи имя шаблона. В шаблон попадёт конфигурация Inbound без клиентов.` Хранилище, SQLite schema, имя DB-файла и persistence semantics не меняются.
- Карточка `Inbound`: сделать inline keyboard устойчивой к узкому client-side layout Telegram и не размещать длинные подписи попарно. Целевая структура: `👥 Клиенты | ✏️ Изменить`; отдельными строками `🔄 Синхронизировать клиентов`, `♻️ Сбросить трафик`, `📋 Клонировать`, `🧩 Сохранить шаблон`; предпоследняя строка `⛔ Отключить | 🗑 Удалить Inbound` (для выключенного Inbound — `✅ Включить | 🗑 Удалить Inbound`); последняя строка `⬅ Inbounds`. Callback identifiers и action semantics не меняются.
- Зафиксировать deletion safety guardrail для Admin Control Plane: любые новые operator-facing delete actions только через отдельный confirmation screen (`confirm` + `✖ Отмена`), без one-click mutation. В `v4.20.9` добавить regression/source-audit для текущих delete flows и нормативный contract в `docs/UI_STYLE.md`; существующие delete semantics не меняются.

Дополнительные findings могут быть добавлены в этот же patch до implementation PR, если они остаются narrowly-scoped UI/copy cleanup без behavior changes.
#### v4.20.10 — доработка компактных кнопок Inbound
