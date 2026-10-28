# Telegram-бот для 3x-ui v5.0.0-rc.27

> **Published `v5.0.0-rc.27`:** выбранная задача #876 — default-off Owner редактор 25 значков Client Portal (#965), обязательный security prerequisite #966/#968 — dnspython2.9.0. [Publication audit](docs/audits/2026-10-28-rc27-publication-checkpoint.md) подтверждает immutable tag/notes/provenance и fresh release image gate. Schema17 прежняя, theme local veto/DB enable OFF. #876/#966 OPEN/keep_open: реальные emoji eligibility/IDs/deployment/rendering и read-only deployed DNS/package/health PENDING; Deployed rc.18.10 только operator-reported.

> **Source #949 впервые Published в `v5.0.0-rc.26`:** закрытые Owner UI/private observer/one-shot Bot/session компоненты #961; [исторический publication audit](docs/audits/2026-10-27-rc26-publication-checkpoint.md). Runtime не зарегистрирован, factory OFF/DENY_ALL; schema17 прежняя. #949/#874 OPEN до #501/privacy/abuse/allowlist и отдельного integration PR/deployment/pilot.

> **Очередь #948, впервые Published в `v5.0.0-rc.25`:** самостоятельная source-only очередь #948 (часть #874): additive schema17, UTC/IANA schedule, immutable candidate snapshot и fenced intent/unknown/recovery. [Publication audit](docs/audits/2026-10-27-rc25-publication-checkpoint.md) подтверждает tag/notes/provenance. Runtime OFF/DENY_ALL, worker/transport не подключены; Deployed rc.18.10 operator-reported, parent #874/policy501/live gates PENDING.







> **Текущий релиз:** [опубликована версия `v5.0.0-rc.27`](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.27), неизменяемый тег указывает на коммит `bd271d583386c13c628899b7e42f550eabe7d6e6` (2026-10-28T06:24:22Z). **На сервере**, по отчёту оператора, установлена только версия `v5.0.0-rc.18.10`, коммит `dae205ac82762723448f93827b981f89ae622231`. Приёмка задач #473/#497/#506/#564/#885/#887/#890/#876/#966 после развёртывания ещё не проведена; G-11 остаётся PARTIAL/NO-GO, публичный запуск запрещён.


**Последний подтверждённый Published до rc.19: `v5.0.0-rc.18.10` (2026-10-22T13:27:26Z):** [PR #864](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/864) и [PR #865](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/865) MERGED, SHA `dae205ac82762723448f93827b981f89ae622231`; Deployed operator-reported, HWID 23/23 targeted scoped PASS ([audit](docs/audits/2026-10-22-v5-rc18-10-operator-targeted-hwid-acceptance.md)), G-11 PARTIAL/NO-GO, public rollout BLOCKED.

**Предыдущий GitHub Published `v5.0.0-rc.18.9` (Deployed/Accepted PENDING):** [PR #861](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/861) MERGED; [release PR #862](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/862) MERGED, tag SHA `7a4ff6be9a6836a2a58547c20b1c916ddea8d88e`, 2026-10-22T11:53:55Z. #834 keep_open до live targeted verification, public rollout BLOCKED.

**GitHub Published `v5.0.0-rc.18.8` (Deployed/Accepted PENDING):** [PR #858](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/858) исправил раздельную Windows OS и admin-only исходную ОС; [release PR #859](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/859) MERGED, immutable tag SHA `8695184b9aea8076e4a2acdbcba7c306ec26655b` (2026-10-22T11:13:22Z). Точный Deployed SHA неизвестен, #834 targeted smoke PENDING; public rollout BLOCKED.

**GitHub Published `v5.0.0-rc.18.7` (Deployed/Accepted PENDING):** исправления #852 (191-char Karing) и #855 (desktop 🖥️, Windows OS, admin/client detail), [PR #856](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/856) MERGED; GitHub Release Published SHA `b5c67fe8078eb87c84cba9382c97fb3da6420de1`. Старый immutable `rc.18.6` сохраняется неизменным; полный v5 public rollout BLOCKED.

**GitHub Published `v5.0.0-rc.18.5`:** универсальный bounded `Client/Platform/Version` parser из [merged PR #846](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/846) включён в immutable tag `b2bdb09778f120aa57c8415ae803394483a2ef8e` после [release PR #847](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/847). Поддержка `Throne` подтверждена offline CI; V2Box/OneXray/Karing/Incy, модели, ОС и security boundaries не изменены. Публикация не выполняет production deployment; targeted acceptance PENDING, public rollout BLOCKED.

**GitHub Published `v5.0.0-rc.18.6`:** [release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.18.6) tag SHA `46bc24530633d9958278ab56f624c8b8d274f845`, 2026-10-21T22:10:48Z. [PR #849](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/849) обеспечивает строго ограниченный Karing 160-character fallback и admin-only диагностику длины/парсера; текущая версия опубликована через [PR #850](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/850). Никакой новой SQLite migration, моделей/ОС или identity change; deployed/live acceptance PENDING, public rollout BLOCKED.

**Актуальный GitHub Published:** `v5.0.0-rc.27`, SHA `bd271d583386c13c628899b7e42f550eabe7d6e6`; Deployed только `v5.0.0-rc.18.10` operator-reported, HWID 23/23 scoped PASS **на rc.18.10**, full v5 G-11 PARTIAL/NO-GO.

**Исторический operator-reported checkpoint (2026-10-21 21:28 EEST; до rc.18.10):** бот успешно обновлён по сообщению оператора, но точный работающий tag/SHA и независимая VPS-проверка отсутствуют. Наблюдение `Throne/Android/2.0.3` на прежнем runtime давало «Не определён»; универсальный патч `Client/Platform/Version` уже merged в `main` через PR #846 и теперь Published в `rc.18.5`, но не Deployed/Accepted и не включён в Published `rc.18.4`. Последний идентифицированный operator-reported Deployed — `rc.18.3` (2026-10-21 13:34 EEST).

**Предыдущий контролируемый пилот (исторический rc.18.2):** `v5.0.0-rc.18.2` Deployed operator-reported 2026-10-20 22:20 EEST, 15/15 targeted HWID UI `[x]` (scoped operator-reported), H1–H8 operator-reported PASS; #472 owner-accepted, независимый DELETE provenance PENDING; прежний `rc.18.1` A4/A5 FAIL — исторический. #814/#816/#820/#471 CLOSED/completed; #472 CLOSED/completed (operator-accepted), G-11 PARTIAL/NO-GO, public rollout BLOCKED.

**Published:** immutable [`v5.0.0-rc.27`](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.27), tag SHA `bd271d583386c13c628899b7e42f550eabe7d6e6`, GitHub Release 2026-10-28T06:24:22Z (GitHub tag/release read-back, проверено). **Deployed:** operator-reported `v5.0.0-rc.18.10`, SHA `dae205ac82762723448f93827b981f89ae622231` (2026-10-22 18:12 UTC+03:00); health OK; independent VPS read-back PENDING. **Accepted:** targeted HWID 23/23 operator-reported scoped PASS (2026-10-22 21:21 UTC+03:00), six Issues completed; independent VPS/provider read-back PENDING, full v5 NOT PASS, G-11 PARTIAL/NO-GO, public rollout BLOCKED.

**Реализовано и опубликовано в `rc.18.2`, operator-reported Deployed:** [PR #821](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/821) MERGED, SHA `aff7bde8ec2521fa11f14362c00502737e2b04e5`, [test PASS](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/39472430277), [title PASS](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/39472796183): карточка показывает безопасное имя VPN-клиента (`Happ`, `Incy`, `Shadowrocket` или «Не определён»), учитывает реальную macOS у iPad-приложения и возвращает к списку; admin HWID-список по **8**, клиентский по **5** устройств на страницу. `rc.18.2` Published/Deployed operator-reported; targeted UI 15/15 и H1–H10 operator-reported PASS; все пять HWID Issues CLOSED/completed, независимая X2/X1/X3 provenance PENDING; [post-merge audit](docs/audits/2026-10-20-hwid-ui-819-821-postmerge-checkpoint.md).

> README описывает актуальное состояние и постоянные интерфейсы проекта, а не хронологию каждого релиза. Ранее опубликованные версии, исторические FAIL/PENDING, даты и evidence сохранены в [CHANGELOG.md](CHANGELOG.md), [GitHub Releases](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases), [датированных аудитах](docs/audits/2026-10-19-v5-rc16-5-operator-targeted-acceptance.md) и [историческом индексе](docs/roadmap/HISTORY_INDEX.md). Исторические статусы не описывают текущий runtime.

## Текущие Issue-статусы (сверяются с Roadmap и GitHub)

Таблица отражает только отдельные явно упомянутые текущие задачи. Полный реестр — в [Roadmap](docs/ROADMAP.md). Состояния `open` и `completed` автоматически сверяются с открытым реестром и closure decisions; `completed` означает только собственный scoped acceptance, не full v5 PASS.

| Issue | GitHub-состояние | Текущий scoped outcome |
| --- | --- | --- |
| [#705](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/705) | `completed` | operator-reported scoped PASS; независимый VPS read-back PENDING |
| [#760](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/760) | `completed` | U1–U7/U9–U12/Z1–Z2 и U8-1…U8-4 operator-reported scoped PASS; conditional U8-4 status covered by offline tests, not live record proof |
| [#336](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/336) | `open` | внешний PSP не реализован; будущий отдельный scope |

## Roadmap: текущие статусы и архив

[Краткий Roadmap](docs/ROADMAP.md) — единственный актуальный источник product и acceptance statuses; [тематический архив старого Roadmap](docs/roadmap/HISTORY_INDEX.md) сохраняет исторические 5803 строки, включая FAIL/STOP, SHA и evidence. Новые проверки записываются в датированные `docs/audits/**`, а не в верхнюю сводку.

Source #876 готовит настраиваемые 25 semantic client emoji slots через Owner-only редактор. По умолчанию Unicode: отдельные локальные veto/attestation текущего бота и DB enable, без вывода eligibility из RBAC/metadata. Admin UI, labels/callbacks, статусы и платёжные/provider boundaries прежние; новые сообщения не повторяются ради cosmetic fallback. Настройки/CAS/audit в существующем runtime_settings, schema17 прежняя. Реальные IDs/Telegram eligibility/pilot и deployment отложены; [контракт UI](docs/UI_STYLE.md#оформление-client-portal-876), [операторская настройка](docs/ADMIN_SETUP.md#оформление-client-portal-876), [late checklist](docs/CLIENT_SETUP.md#оформление-клиентских-значков-876).

## Тарифная модель — RUB, Stars и ручное назначение

[Issue #705](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/705) принят по operator-reported scoped acceptance от 2026-10-19 12:09 EEST: сверка Orders/Payments/Entitlements и собственные критерии подтверждены оператором. [Аудит и provenance](docs/audits/2026-10-19-v5-rc16-5-operator-targeted-acceptance.md), [решение о закрытии](docs/roadmap/issue-closure-decisions.json). Независимый VPS/data-plane read-back отсутствует; завершение #705 не означает общего v5 acceptance, разрешения public rollout или общего G-11 acceptance.

[PR #710](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/710) реализовал независимые RUB и Stars/XTR, правила видимости локальных User Groups и ручную бессрочную выдачу с durable read-back. Первоначальная SQLite schema v14 — исторический этап; **Published rc.27 использует schema v17**, foundation #947 и очередь #948 добавлены без runtime wiring ([контракт миграций](docs/SQLITE_MIGRATIONS.md)). RUB-PSP относится к отдельному [Issue #336](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/336); в Telegram цифровые покупки используют только Stars/XTR.

## План внешних платежей

[Исторический проектный контракт внешних платежей](docs/EXTERNAL_PAYMENT_LINKS.md) описывает отдельный отложенный PSP scope #336. Действующее продуктовое решение #705 имеет приоритет: **в Telegram только Stars/XTR**, RUB-карты/СБП допустимы в будущем лишь на **самостоятельном авторизованном внешнем сайте**, не через персональную RUB-ссылку из бота. Этот релиз не создаёт веб-сайт, не подключает PSP и не разрешает публичные платежи.

## Текущий production path

### Новая установка

Каноническое руководство для чистого Master VPS и direct nodes:

**[Admin Setup — Master + direct nodes](docs/ADMIN_SETUP.md)**

Оно является источником истины для:

- Master 3x-ui и bot container;
- `.env`, Docker/network/firewall и TLS;
- direct-node onboarding;
- dedicated Direct Admin credentials;
- Host Control Agent;
- Extended direct-node backup;
- Safe Bot Self-Update Deploy Agent;
- обязательных preflight/post-deploy проверок.

README не заменяет этот runbook и не содержит отдельной сокращённой последовательности установки.

### Обновление существующего production

Release, GitHub tag и production deployment — отдельные стадии. Канонический контракт публикации и проверки релиза:

**[Release workflow](docs/RELEASES.md)**

Для ручного deployment используется только опубликованный release tag:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
./scripts/deploy-release.sh vX.Y.Z
./scripts/deploy-release.sh --status
~~~

Не используй старые version-specific команды из истории проекта как инструкцию для текущего production. После deployment выполняется targeted smoke именно изменённой области и повторная базовая health/status-проверка.

Если на Master установлен restricted Deploy Agent, Owner может использовать:

`/admin → Система → Обновления бота`

Полный safety/acceptance contract:

**[Safe Bot Self-Update](docs/BOT_SELF_UPDATE.md)**

Deploy Agent принимает только опубликованные `vX.Y.Z` tags и не предоставляет Telegram-боту Docker socket, host shell или Git deploy key.

### Восстановление после потери Master VPS

Канонический disaster-recovery runbook:

**[VPS Recovery](docs/VPS_RECOVERY.md)**

Bootstrap helper намеренно не является универсальным installer инфраструктуры. ОС, Docker, Master 3x-ui, DNS/TLS/firewall и другие host-level слои подготавливаются отдельно.

### Direct nodes и Host Control

Рекомендуемый onboarding новой direct node:

**[Node Onboarding](docs/NODE_ONBOARDING.md)**

Client-facing endpoint/IP policy and inbound firewall checks:

**[Data-plane addressing and inbound firewall](docs/DATA_PLANE_ADDRESSING.md)**

Host-level управление `x-ui.service`:

- [Host Control Agent — security contract](docs/HOST_CONTROL_AGENT.md)
- [Host Control Deploy](docs/HOST_CONTROL_DEPLOY.md)
- [Host Control Rollout](docs/HOST_CONTROL_ROLLOUT.md)
- [Fleet Operations](docs/FLEET_OPERATIONS.md)

Для direct node используются независимые privilege domains:

1. node-sync token: Master 3x-ui → node;
2. dedicated admin-scope token: bot → direct 3x-ui API;
3. отдельный Host Control token.

Один token не переиспользуется между этими domains.

### Backup и off-site recovery

Full Backup включает recovery-ориентированные данные Master и, при настроенных targets, direct-node snapshots.

Encrypted off-site replication и recovery:

**[Off-site Backup](docs/OFFSITE_BACKUP.md)**

Off-site transport выключен по умолчанию. Full Backup содержит secrets; Telegram и GitHub не являются backup storage. Admin UI может создать backup или подготовить DR export, но secret-bearing файлы не прикладываются к Telegram: их получают только через защищённый host-side/off-site recovery path.

## Архитектура текущего runtime (v4 foundation / v5 Client Portal)

После cleanup-декомпозиции entrypoint и runtime разделены:

~~~text
bot.py
└─ минимальный executable shim
   └─ app_runtime.main()

app_runtime.py
├─ startup / recovery order
├─ Subscription Proxy lifecycle
├─ background backup + alerts
├─ Router registration
├─ Telegram polling
└─ graceful task cancellation

client_access.py
└─ v5 Client Portal Telegram UI; не импортирует 3x-ui/storage/commerce напрямую

customer_service.py
└─ provider-neutral customer domain: profile/subscription/plans/orders/traffic/devices

customer_provider_xui.py
└─ текущий 3x-ui adapter для customer read capabilities

admin_shell.py
└─ /admin, Обзор, top-level navigation и compatibility redirects

domain routers
├─ advanced_users.py
├─ user_groups_admin.py
├─ advanced_nodes.py
├─ inbound_admin.py
├─ catalog_admin.py
├─ business_admin.py
├─ admin_observability.py
├─ system_admin.py
├─ storage_admin.py
├─ versions_updates.py
├─ bot_updates.py
├─ host_control_ui.py
├─ fleet_operations.py
├─ website_monitoring.py
├─ website_monitoring_runtime.py
├─ website_monitoring_admin.py
├─ website_diagnostics.py
├─ website_diagnostics_admin.py
└─ disaster_recovery.py
~~~

`bot.py` сохраняется как стабильный executable path, в том числе для `restore_bootstrap.py`, но не владеет domain handlers или lifecycle implementation.

Клиентская история #506 открывается из профиля через `client_access.py` и чистые read-only представления `client_history_ui.py`. `CustomerPortalService` читает owner-scoped безопасную SQL-проекцию в `db.py`: XTR Orders и реальные Telegram Stars Payments по 8 записей, отдельные Entitlement/refund статусы. Схема/retention не меняются; нет checkout/provider/reconcile вызовов. [Контракт UI](docs/UI_STYLE.md#клиентская-история-заказов-и-stars-платежей-506), [поздняя приёмка](docs/CLIENT_SETUP.md#собственная-история-stars-506). Published rc.22; deployment и собственный targeted acceptance PENDING, #506 keep_open.

Source-only foundation сервисных кампаний #947: `service_campaigns.py`/`campaign_store.py` дают owned drafts/frozen revisions и bounded private-candidate dry-run, впервые опубликованные в rc.24/schema v16. Runtime/Telegram UI/worker/transport не подключены, delivery всех категорий unapproved/0; private-contact ledger не backfill из users. [Контракт кампаний](docs/SERVICE_CAMPAIGNS.md), [миграции](docs/SQLITE_MIGRATIONS.md). Parent #874 и policy #501 сохраняют собственные gates.

Source #948 в main через PR #956 `9ac41354167a3b12a35149ebcfb396fe4065cceb`, Published в rc.25/schema17: изолированные UTC/IANA schedule, immutable candidate snapshot, fenced queue/intent ledger и one-tick worker с injected transport. Runtime не подключён; конфигурация OFF и реальное admission DENY_ALL. Test policy/transport — только synthetic evidence, не consent/доставка. [Контракт очереди](docs/SERVICE_CAMPAIGNS.md), [миграции](docs/SQLITE_MIGRATIONS.md).

Source-компоненты #949: `campaign_owner_ui.py` — закрытый owned draft/preview/schedule/progress/stop router, `campaign_telegram.py` — default-deny private observer и bounded one-shot Bot API/session adapters. В `app_runtime`/dispatcher/client guards/menu они не подключены; factory OFF/DENY_ALL. Source/fake tests не Telegram delivery. До настоящих #501/privacy/abuse/allowlist prerequisites runtime registration BLOCKED; затем отдельный reviewed integration PR/deployment/pilot. [Contract](docs/SERVICE_CAMPAIGNS.md).

Client Portal развивается поверх отдельного commerce lifecycle. Для цифровой подписки внутри Telegram customer purchase использует native Telegram Stars (`XTR`): тариф имеет отдельную `stars_price`, pre-checkout проверяет ownership/amount, а `successful_payment` атомарно фиксирует Payment → Order → Entitlement. Fiat `price_minor/currency` остаётся отдельным catalog field и не конвертируется в Stars автоматически. Customer-facing handlers проходят через `CustomerPortalService`; `client_access.py` не импортирует `XUIClient`, `Database` или `CommerceService`. Текущий 3x-ui-specific read adapter изолирован в `customer_provider_xui.py`, поэтому будущий provider не требует provider-name branching в Telegram handlers. Тестовые v4 user actions `/create` и `/inbounds` больше не являются mutation-entrypoint: старые команды/кнопки только перенаправляют в личный кабинет. В pilot-режиме доступ к `/start` всё ещё ограничен существующим allowlist/admin boundary; публичный signup откроется только после отдельного abuse/rate-limit и ownership-аудита. Выбор тарифа создаёт или переиспользует локальный Stars order и отправляет native Telegram invoice; 3x-ui access меняется только после `successful_payment` и последующего durable entitlement provisioning. Production launch остаётся закрыт до Stars acceptance/refund/support hardening и controlled canary.

Линия `v4.25.x` (`v4.25.0–v4.25.8`) полностью опубликована, развёрнута, проверена и закрыта в production. Финальные patch findings закрыты в `v4.25.8`: Clone Inbound сохраняет source parent при `✖ Отмена`, а DB-backed Owner подтверждает self-demotion отдельным fail-closed confirmation flow. Subscription proxy сохраняет принятый контракт `v4.25.3`; временные Streisand workarounds из `v4.25.4–v4.25.5` удалены. Известное ограничение: Streisand не передаёт совместимый `X-HWID`, поэтому при включённом HWID limit 3x-ui отклоняет raw subscription как `hwid_not_supported`.

Historical v4 acceptance остаётся закрытым и документированным: Controlled Node Drain production acceptance #208 завершён 2026-10-01. Encrypted off-site backup/restore drill завершён 2026-10-05 и подтвердил `OFFSITE_RECOVERY_OK`. **Final v4 feature freeze действует с 2026-10-05**; `v4.26.9` является post-freeze operational hotfix для subscription compatibility и публикации уже слитого pilot v5 foundation, а не новым v4 product scope; до закрытия repository/public-release audit после freeze разрешались только narrowly-scoped security/reliability/data-integrity fixes, regression changes и production acceptance; сам audit теперь закрыт PASS.

Линия `v4.24.x` реализована, опубликована и принята в production: `website_monitoring.py` содержит SQLite repository/state machine и SSRF-safe outbound boundary, `website_monitoring_runtime.py` — bounded scheduler/incident notifications, `website_monitoring_admin.py` — persistent monitoring UI, а `website_diagnostics.py` / `website_diagnostics_admin.py` — one-off DNS/WHOIS/HTTP/redirect/CMS/SEO/PageSpeed/Sitemap/URL-list/QR diagnostics. Production smoke `v4.24.0` выявил targeted findings WHOIS MSK, bounded Cheburcheck detail и public IPv6 literal validation; они закрыты в `v4.24.1`, после чего smoke/acceptance линии завершён.

### 3x-ui API contract

Native 3x-ui API используется через `xui.py` / `version_api.py`.

Текущий pinned compatibility contract:

- 3x-ui: `v3.10.2`; поддерживаемый OpenAPI contract (PR #693; vendored schema от `v3.10.0` с идентичным immutable Git blob), отдельно от строгой проверки Flow `panelVersion=3.10.2`;
- vendored OpenAPI: `contracts/3xui/v3.10.0/openapi.json`;
- используемый API surface: `contracts/3xui/contract.json`.

CI проверяет route/method, Bearer auth, request/response contract и source parity fail-closed.

Подробнее: **[3x-ui OpenAPI compatibility contract](docs/3XUI_OPENAPI_CONTRACT.md)**.

### User / Audience Groups

V4.22 добавляет отдельные `Группы пользователей` для сегментации будущего Client Portal:

- membership many-to-many хранится по стабильному `telegram_id`;
- группы и membership управляются из `/admin → Пользователи`;
- backend matcher поддерживает include/exclude, при этом exclude имеет приоритет;
- User Groups не связаны с Server Groups и не меняют Nodes, Inbounds, тариф или VPN-доступ.

`user_groups_admin.py` владеет административным UI, а `audience.py` — reusable matcher без Telegram-specific logic.

### SQLite

Локальное состояние хранится в SQLite. С v4.15 используется явный forward-only migration framework с persistent `schema_migrations` journal.

Подробнее: **[SQLite migrations](docs/SQLITE_MIGRATIONS.md)**.

## Основные security boundaries

Проект намеренно разделяет Telegram UI и privileged host operations.

- Bot container не получает Docker socket или generic host shell.
- Host Control Agent не является SSH gateway и принимает только фиксированный allowlist операций для `x-ui.service`.
- Xray restart, panel-process restart и host-level service restart — разные операции без fallback между privilege domains.
- Direct Admin, Host Control, panel token, Deploy Agent token и object-storage credentials не переиспользуются.
- Unknown admin callbacks должны fail closed через centralized privilege catalog.
- Interrupted state-changing Host Control/Fleet/Deploy mutations автоматически не replay'ятся.
- Backups, `.env`, API tokens, subscription IDs/URLs, private keys и enrollment contents нельзя публиковать в GitHub issues/PR/chat.

Общие правила: **[SECURITY.md](SECURITY.md)**.

## Shadowrocket и HWID

Если для пользователя включён `HWID limit > 0`, в Shadowrocket необходимо включить отправку HWID для subscription requests:

1. Откройте настройки Shadowrocket.
2. Перейдите в настройки подписок / Subscription.
3. Включите `Send HWID` / «Отправлять HWID».
4. Повторно обновите или добавьте subscription URL.

Если все HWID slots уже заняты, 3x-ui отклонит новый device. Освободите один зарегистрированный device slot или увеличьте per-user `HWID limit` в Telegram Admin Control Plane. Compat proxy не генерирует synthetic HWID и не обходит device limit.

Streisand не передаёт совместимый `X-HWID` в raw subscription request. Поэтому при `HWID limit > 0` 3x-ui отклоняет такой request как `hwid_not_supported`. Это ограничение клиента: compat proxy намеренно не подставляет synthetic/fallback HWID и не ослабляет per-device enforcement. Одиночные VLESS links могут импортироваться отдельно, но это не эквивалентно HWID-защищённой subscription.

## Subscription Compatibility Proxy

**#885 / PR #886 — Published rc.21:** private-owner Telegram карточка может выдать короткоживущий same-origin HTTPS handoff к существующему `import_uri()` через `client_import_handoff.py`. Opaque ticket — одноразовый bearer-like URL (90 секунд, process-local limit 256), raw URI не помещается в Telegram URL. Copy/QR сохраняются; новые provider mutations и порты отсутствуют. Handoff опубликован в rc.21; реальные device/import/refresh и deployment PENDING. [Контракт клиента](docs/CLIENT_SETUP.md), [security](SECURITY.md#subscription-credentials-и-access-logs).


Проект сохраняет встроенный compatibility proxy для подписок, управляемых ботом.

Он:

- обслуживает `GET /compat/{sub_id}`;
- предоставляет `GET /healthz`;
- получает upstream subscription через `SUBSCRIPTION_URL_TEMPLATE`;
- проверяет, что `sub_id` принадлежит пользователю из локальной SQLite;
- для raw/machine subscription преобразует 3x-ui AmneziaWG `vpn://` в `amneziawg://`;
- сохраняет штатное HTML-представление 3x-ui;
- проксирует assets встроенной subscription page через `/compat/assets/`;
- применяет ограниченную Shadowrocket compatibility только к соответствующим VLESS/XHTTP/Reality links;
- для Happ requests явно пропускает upstream `Routing` / `Routing-Enable`, не раскрывая эти client-specific headers INCY или generic clients.

Client-side routing profiles Happ/Incy и отдельный Shadowrocket client module имеют разные contracts. Все три independently production-accepted 2026-10-05: Happ через `/compat/{sub_id}`, Incy через собственную body/deeplink семантику при штатном HWID enforcement, Shadowrocket через отдельный client module `RU Direct`. Shadowrocket module не связан с Shadowrocket-only `fp` rewrite в `subscription_proxy.py`. Proxy по-прежнему использует explicit allowlist и не является прозрачным passthrough всех upstream metadata. Настройка и acceptance: **[Subscription client routing](docs/SUBSCRIPTION_ROUTING.md)**.

Основные переменные:

~~~env
SUBSCRIPTION_URL_TEMPLATE=https://sub.example.com:2096/sub/{sub_id}
COMPAT_SUBSCRIPTION_URL_TEMPLATE=https://sub.example.com/compat/{sub_id}

SUBSCRIPTION_PROXY_HOST=0.0.0.0
SUBSCRIPTION_PROXY_PORT=8080
~~~

Если `COMPAT_SUBSCRIPTION_URL_TEMPLATE` пуст, бот продолжает выдавать исходный URL 3x-ui.

Docker Compose публикует proxy только на loopback Master:

~~~text
127.0.0.1:18080 -> container:8080
~~~

Пример reproducible reverse-proxy policy. Zones задаются один раз в `http {}`. Customer subscription requests и browser assets используют разные front-door limits: subscription URL остаётся строгим, а Vite assets получают отдельный bounded burst для browser `modulepreload`.

~~~nginx
# http {}
limit_req_zone $binary_remote_addr zone=sub_compat_rate:10m rate=5r/s;
limit_conn_zone $binary_remote_addr zone=sub_compat_conn:10m;

# Subscription SPA загружает около нескольких десятков JS/CSS resources одним
# burst. Отдельная zone не ослабляет customer subscription endpoint.
limit_req_zone $binary_remote_addr zone=sub_compat_assets_rate:10m rate=40r/s;
limit_conn_zone $binary_remote_addr zone=sub_compat_assets_conn:10m;

location ^~ /compat/assets/ {
    access_log off;

    # Browser-safe, но bounded asset fan-out. Application всё равно сохраняет
    # глобальный MAX_UPSTREAM_CONCURRENCY=32 и 8 MiB response bound.
    limit_req zone=sub_compat_assets_rate burst=80 nodelay;
    limit_conn sub_compat_assets_conn 32;

    proxy_pass http://127.0.0.1:18080;
    proxy_http_version 1.1;

    proxy_connect_timeout 5s;
    proxy_send_timeout 30s;
    proxy_read_timeout 25s;

    proxy_buffering off;
    proxy_request_buffering off;
    proxy_max_temp_file_size 0;
    proxy_redirect off;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
}

location ^~ /compat/ {
    # URI содержит bearer-like sub_id: не сохраняй request URI в access logs.
    access_log off;

    # Customer subscription endpoint остаётся строго ограниченным.
    limit_req zone=sub_compat_rate burst=10 nodelay;
    limit_conn sub_compat_conn 4;

    proxy_pass http://127.0.0.1:18080;
    proxy_http_version 1.1;

    proxy_connect_timeout 5s;
    proxy_send_timeout 30s;
    proxy_read_timeout 25s;

    proxy_buffering off;
    proxy_request_buffering off;
    proxy_max_temp_file_size 0;
    proxy_redirect off;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
}
~~~

Safari/WebKit может агрессивно запускать все `<link rel="modulepreload">` и stylesheet requests параллельно. Нельзя применять к `/compat/assets/` customer-профиль `5r/s + burst=10 + conn=4`: nginx тогда отвечает `503` части JS/CSS и SPA остаётся белой. Отдельный asset profile выше сохраняет bounded front-door policy, а общий application upstream cap остаётся 32.

Локальная health-проверка:

~~~bash
curl -fsS http://127.0.0.1:18080/healthz
~~~

Не публикуй реальный `sub_id` в issue/PR/chat. Runtime proxy допускает максимум 32 одновременных upstream fetch и читает не более 8 MiB одного upstream response; при насыщении очередь ждёт не более 1 секунды и fail-closed возвращает 503. Встроенный aiohttp access log для compatibility proxy отключён. На внешнем reverse proxy для `/compat/` также не включай access log с request URI/`$request_uri`: путь содержит bearer-like credential.

## Telegram surfaces

Текущий controlled canary (см. [Roadmap](docs/ROADMAP.md)) сохраняет два отдельных UI/authorization boundary.

Client Portal (pilot allowlist, `CLIENT_PORTAL_ENABLED`):

- `/start` — личный кабинет;
- `/subscription` — read-only карточка подписки с достоверным статусом и сроком; owner-scoped URL доступен только в личном чате, без создания нового `sub_id`;
- `/paysupport` — помощь по платежам;

Совместимость (#564): прежние `/create` и `/inbounds` скрыты из актуальной справки/рекомендаций; runtime handlers и сохранённые callbacks остаются guarded non-mutating redirects в кабинет. Полный типизированный каталог/AST CI проверяют и скрытые legacy записи. Основной путь — `/start`; Telegram global command menu не меняется.

Admin Control Plane:

- `/admin` открывает корневую панель: Обзор / Пользователи / Подписки / Платежи / Тарифы / Промокоды / Инфраструктура / Мониторинг / Система;
- Пользователи: карточки пользователей / Группы пользователей / массовые действия / согласование доступа; Группы пользователей являются audience-сущностью и не заменяют Группы серверов;
- Инфраструктура: Ноды / Inbounds / Хосты / Операции с нодами / Группы серверов; Host Control открывается из карточки конкретного Master/direct node;
- Мониторинг: Трафик / В сети / Состояние системы / Проверка блокировок / Мониторинг сайтов / Журналы / Оповещения;
- Система: Обновления бота / Версии и обновления / Задания / Резервные копии / Журнал аудита / Администраторы / Настройки.

Client Portal v5 уже реализован в контролируемом pilot scope, но ещё **не прошёл полный production acceptance** и не является общедоступным. Его authorization/navigation boundary остаётся независимой от `/admin`; наличие slash-команды не открывает доступ в обход runtime flags, pilot allowlist и RBAC.

## CI и regression gates

Основной CI выполняет:

~~~bash
python -m compileall -q .
python -m unittest discover -s tests -v
python3 scripts/check-3xui-openapi-contract.py
git diff --check
~~~

Дополнительно regression tests закрепляют:

- centralized RBAC catalog и fail-closed unknown callbacks;
- single ownership Router'ов после декомпозиции;
- Host Control / Deploy Agent startup recovery order;
- отсутствие automatic mutation replay;
- public-readiness contract: нейтральные deployment-примеры и актуальные русские UI-paths в README/runbook'ах;
- provisioning/user mutation ordering;
- backup/restore/off-site integrity semantics;
- release/Git workflow conventions;
- Living Docs diff/semantic contract и current repository-state expectations.
- PR checklist в обязательном `PR conventions` CI: все пункты шаблона PR должны быть отмечены, N/A — обоснован; stage после release не подменяется PR-галочкой.

## Карта документации

| Задача | Канонический документ |
|---|---|
| Установка Admin Control Plane | [docs/ADMIN_SETUP.md](docs/ADMIN_SETUP.md) |
| Release/tag/deployment contract | [docs/RELEASES.md](docs/RELEASES.md) |
| Git/PR/issue conventions | [docs/GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md) |
| Living docs / drift contract | [docs/LIVING_DOCS.md](docs/LIVING_DOCS.md) |
| Source contract сервисных кампаний | [docs/SERVICE_CAMPAIGNS.md](docs/SERVICE_CAMPAIGNS.md) |
| Product roadmap | [docs/ROADMAP.md](docs/ROADMAP.md) |
| Client Portal v5: настройка только контролируемого пилота | [docs/CLIENT_SETUP.md](docs/CLIENT_SETUP.md) |
| v5 Client Portal controlled canary и acceptance | [docs/V5_PRODUCTION_ACCEPTANCE.md](docs/V5_PRODUCTION_ACCEPTANCE.md) |
| UI style | [docs/UI_STYLE.md](docs/UI_STYLE.md) |
| Direct-node onboarding | [docs/NODE_ONBOARDING.md](docs/NODE_ONBOARDING.md) |
| Data-plane address / inbound firewall | [docs/DATA_PLANE_ADDRESSING.md](docs/DATA_PLANE_ADDRESSING.md) |
| Опциональный Cloudflare WARP на VPS и direct nodes (отдельный сетевой change) | [docs/WARP_SETUP.md](docs/WARP_SETUP.md) |
| Client-side subscription routing | [docs/SUBSCRIPTION_ROUTING.md](docs/SUBSCRIPTION_ROUTING.md) |
| Host Control security | [docs/HOST_CONTROL_AGENT.md](docs/HOST_CONTROL_AGENT.md) |
| Host Control deployment | [docs/HOST_CONTROL_DEPLOY.md](docs/HOST_CONTROL_DEPLOY.md) |
| Host Control rollout | [docs/HOST_CONTROL_ROLLOUT.md](docs/HOST_CONTROL_ROLLOUT.md) |
| Fleet Operations | [docs/FLEET_OPERATIONS.md](docs/FLEET_OPERATIONS.md) |
| Bot Self-Update | [docs/BOT_SELF_UPDATE.md](docs/BOT_SELF_UPDATE.md) |
| Off-site Backup | [docs/OFFSITE_BACKUP.md](docs/OFFSITE_BACKUP.md) |
| VPS recovery | [docs/VPS_RECOVERY.md](docs/VPS_RECOVERY.md) |
| SQLite migrations | [docs/SQLITE_MIGRATIONS.md](docs/SQLITE_MIGRATIONS.md) |
| Cheburcheck integration | [docs/CHEBURCHECK.md](docs/CHEBURCHECK.md) |
| Cheburcheck deployment | [docs/CHEBURCHECK_DEPLOY.md](docs/CHEBURCHECK_DEPLOY.md) |
| 3x-ui OpenAPI contract | [docs/3XUI_OPENAPI_CONTRACT.md](docs/3XUI_OPENAPI_CONTRACT.md) |
| Third-party notices | [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) |

## Сторонние компоненты

Read-only проверка блокировок использует API open-source проекта [Cheburcheck](https://github.com/LowderPlay/cheburcheck). Интеграция проверена относительно pinned upstream commit `0bbd2be8ca4b8f9ded1407597654314fc2a900c6`. Авторские уведомления и условия BSD-3-Clause сохранены в [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Website monitoring и web diagnostics `v4.24.0` используют [PackBot](https://github.com/vladpak1/packbot) как reviewed behavior/reference implementation на revision `3c4a5bb29626f8b3e28056bd52cd94fdce9f3c1a`. Production runtime не встраивает PHP/MySQL/webhook stack PackBot; реализация нативная Python/aiogram/SQLite. MIT attribution и copyright сохранены в [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Лицензия

Исходный код этого проекта распространяется по **Apache License 2.0**. Полный текст: [LICENSE](LICENSE).

Third-party компоненты, зависимости, upstream references и адаптированные материалы сохраняют собственные лицензии и attribution requirements; см. [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) и supply-chain license inventory.

## История проекта

Release history не поддерживается второй копией внутри README.

Используй:

- **[CHANGELOG.md](CHANGELOG.md)** — канонический список изменений по версиям;
- GitHub Releases — опубликованные release notes и immutable tags;
- **[docs/RELEASES.md](docs/RELEASES.md)** — правила публикации и production acceptance.

Старые v2/v3/v4 upgrade-команды из исторических релизов не являются текущей процедурой deployment.
