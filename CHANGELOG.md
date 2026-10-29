# Журнал изменений

> **Текущий checkpoint 2026-10-29:** GitHub Published `v5.0.0-rc.31`, immutable `e74aabf827e5683c3528f9bd49e701a1ac17812c` (2026-10-28T19:09:56Z), prerelease; [финальная сверка](docs/audits/2026-10-29-989-publication-main-checkpoint.md). #989/#990 source/required+main1782/3/fresh image/source5 hashes/tag/notes и publication checkpoint #993 main `9b406af42a9f6c99e6d89ed6f99b0b6e3b1eda0b`/required+main1782/3/publisher/independent main read-back/own Issue audit scoped PASS; только R989-01 installed/read PENDING. Parent482 остальные scopes и #984 runtime отдельно. Deployed18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/independent VPS PENDING; G-11 PARTIAL/NO-GO/public rollout BLOCKED. [Roadmap](docs/ROADMAP.md).

> **Предыдущий checkpoint 2026-10-22 21:21 UTC+03:00:** GitHub Published `v5.0.0-rc.18.10` (immutable SHA `dae205ac82762723448f93827b981f89ae622231`), Deployed с точным SHA **operator-reported**; targeted HWID UI 23/23 operator-reported scoped PASS. #827/#830/#833/#834/#838/#854 CLOSED/completed по собственным критериям, [датированный audit](docs/audits/2026-10-22-v5-rc18-10-operator-targeted-hwid-acceptance.md), [Roadmap](docs/ROADMAP.md). Independent VPS/provider attestation PENDING; G-11 PARTIAL/NO-GO, public rollout BLOCKED. Дата operator report: 2026-10-22T18:21:19Z.

> **Исторические publication checkpoints (не текущий deployed/accepted статус):** `rc.18.5` PR #847 SHA `b2bdb09778f120aa57c8415ae803394483a2ef8e` (2026-10-21); `rc.18.6` PR #850 SHA `46bc24530633d9958278ab56f624c8b8d274f845` (2026-10-21); `rc.18.9` PR #862 SHA `7a4ff6be9a6836a2a58547c20b1c916ddea8d88e` (2026-10-22). Прежние `PENDING` по этим RC относятся к моменту их публикации, а не к нынешней `rc.18.10`. Полные release notes и старые состояния сохранены в истории Git и GitHub Releases.

Все заметные изменения проекта фиксируются здесь на русском языке. Названия элементов интерфейса, API, переменных, таблиц и команд сохраняются в исходном виде, чтобы их можно было сопоставить с кодом.

История до перехода на Git восстановлена по сохранённым релизным архивам. Для исторических версий формулировки сокращены и приведены к единому виду.

> Первый архив проекта не имел номера версии. При миграции в Git он помечен тегом `v1.0.0` как историческая отправная точка.

> **Актуализация статуса, 2026-10-20:** `v5.0.0-rc.18.1` уже Published (immutable tag `7b3cd54e41246212c6313b815e571d180e5a4475`) и Deployed **по отчёту оператора**; targeted A4/A5 — **FAIL**, полный acceptance PENDING. Формулировки секции релиза ниже отражают исторический release-prep checkpoint и сохраняются без переписывания опубликованных release notes. Следующий HWID fix [#821](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/821) MERGED в `main` (`aff7bde8ec2521fa11f14362c00502737e2b04e5`), и теперь Published в `v5.0.0-rc.18.2` (immutable tag SHA `20205a56887cbdf644f604febdd9eb9ac717b914`), при этом новый `rc.18.2` Deployed operator-reported 2026-10-20 22:20 EEST и targeted HWID 15/15 `[x]` reported 22:25 EEST и H1–H8 operator-reported PASS 22:48 EEST; #814/#816/#820/#471 CLOSED/completed, #472 CLOSED/completed (operator-accepted); full v5 NOT PASS. Текущий статус — [Roadmap](docs/ROADMAP.md).

## Unreleased

- #995 / PR #996 — bounded process-local клиентский rate limiter:4096 retained keys, global idle-window cleanup по обращению, отказ нового ID без allocation/вытеснения живого окна; per-user sliding window/default30/60s и Owner-only target reset прежние. Новых env/schema/deps/портов нет; свой installed/read outcome отложен, cap не capacity/SLA и не distributed guarantee.

## v5.0.0-rc.31 — Безопасный отказ чтения клиентского трафика

- #989 / PR #990 — клиентский traffic read даёт существующий обезличенный временный отказ при native transport/timeout/OS, malformed mappings и ошибках числовых counters на любом из двух адресных reads. Raw cause подавлен в обычном traceback; cancellation, успешные aliases/нули, private-owner/Back и mutation/no-replay прежние. Никаких retry/fallback/cache/schema/deps/env/ports; installed/read acceptance отдельно.

## v5.0.0-rc.30 — Ограничение параллельных чтений panel API

- #984 / PR #985 — ограниченный shared read admission общего XUI panel API: active8/ordinary6/critical reserve2, queue32/wait1s/targets64 на loop; common reads/read-only POST/version GET/getDb без обхода через новый XUIClient/token/TLS. Cancellation/timeout/ошибки освобождают permit, idle tracebacks не занимают registry slots. Доверенные provisioning initial/post-mutation reads получают priority; недоказанный postcondition unknown/no replay. Auth/TLS/routes/transport timeouts/mutation one-shot/schema/deps прежние; pooling/cache/прочие domains отдельно. Caps — инженерная защита, не production SLA; deployment/собственный runtime acceptance PENDING.

## v5.0.0-rc.29 — Изоляция импорта инструментов чтения panel API

- #977 / PR #979 — import repair offline baseline #972: annotation-only checkout/commerce/DB dependencies CustomerPortalService перенесены под TYPE_CHECKING при существующих future annotations. Fresh subprocess guard запрещает config/app_runtime/provisioning/checkout/commerce/DB/dotenv imports до module execution; actual worker/CLI и прежние DTO/error aliases проверены без app configuration. Доменные definitions/constants, provider paths/auth/TLS/mutations/schema/deps прежние; новые baseline snapshots сохраняют изменившийся source hash, старые RC28 notes/audits неизменны. Прежний immutable RC28 сохраняет import defect; исправление поставляется новым RC без изменения старого tag.

## v5.0.0-rc.28 — Измерение стоимости чтений panel API

- #972 / PR #973 / часть #482-A: воспроизводимый полностью offline baseline текущих XUIClient get/traffic/list и same/unique owner traffic. Ограниченные synthetic fixtures/driver, отдельный process на case, реальные call/JSON/latency/CPU/heap/RSS метрики и source hashes; fake transport с запретом sockets/DNS, без live mode/config/DB. Runtime/auth/TLS/mutations/cache/session lifecycle не меняются; это стоимость разбора в боте, не throughput панели/Xray или production SLA. Остальные budget/cache/lifecycle/limiter/runtime gates #482 отдельно.

## v5.0.0-rc.27 — Настраиваемые значки клиентского портала

- #966 / PR #968 — обязательный security prerequisite текущего пакета #876: dnspython2.8.0 → 2.9.0 для публичного CVE-2026-114605 (excessive DNS decompression CPU). Direct floor>=2.9,<3 и hashed lock сгенерированы pip-tools7.6.1; оба official PyPI wheel/sdist SHA-256 проверены, другие pins и base image прежние. Новых env/портов/DDL нет. Source/build проверки не доказывают установленную версию на VPS; #966 keep_open до отдельно разрешённого deployment и собственного read-only DNS/package/health outcome.

- #876 / PR #965: Owner-only редактор 25 semantic Client Portal emoji slots, bounded entity/metadata/draft/preview/confirm/reset, CAS/audit в существующем runtime_settings без новой schema. Сохраняются канонические labels/callbacks/Unicode и обычная админка; custom icon field и типизированные UTF-16 entities не принимают произвольный HTML/recipient/URL input.
- Default-off local veto + операторская attestation текущего bot ID и DB enable; metadata/роль Owner не доказывают Telegram entitlement. Client-only контекст, одна Unicode send с необязательным cosmetic edit; proven HTTP400 допускает только Unicode edit того же panel, unknown не replay и не попадает в admin edit→send fallback. Реальные IDs/eligibility/deployment/pilot отложены, #876 keep_open; G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## v5.0.0-rc.26 — Подготовка закрытых сервисных сообщений

- #949 / PR #961 / часть #874-C: private Owner-only source router/controller для owned черновиков, CAS-редактирования, локального preview, bounded оценки, планирования/прогресса и двухшаговой остановки. Opaque подтверждения привязаны к actor/chat/message, текущей клавиатуре и TTL; callbacks не содержат получателей, текста или ссылок. Новый глобальный пункт меню и slash-команды не регистрируются.
- Source factory редактора по умолчанию OFF и всегда создаёт delivery с policy=None/DENY_ALL; даже включённый локальный редактор не утверждает #501 и не запускает доставку. Trusted private-update adapter требует отдельного server-side admission и существующего пользователя, не берёт identity из imports/admin create. Реальный observer/dispatcher/client guards не подключены.
- Bounded one-shot адаптер существующего Bot API: plain text, no links/markup/paid broadcasts, строгий receipt того же bot/private chat. Только узкий CampaignAwareSession с проверенным HTTP429/JSON rejection даёт safe retry; обычный SDK RetryAfter, включая retry_after в 5xx, остаётся unknown/no-replay. Noncooperative timeout/cancellation не считается доказанным отказом.
- Schema17 остаётся прежней; новых env/credentials/портов нет. Source/fake integration tests не доказывают реальный Telegram outcome. Runtime registration BLOCKED до #501/privacy/abuse/allowlist review, затем нужен отдельный integration PR и разрешённый deployment/pilot. #949/#874 остаются OPEN, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## v5.0.0-rc.25 — Изолированная очередь сервисных кампаний

- #948 / PR #956 / часть #874-B: source-only API подготовки и подтверждения immutable candidate snapshot, owned controls, UTC/IANA расписание с отказом для DST gap/fold и прошедшего времени; один operation ID не создаёт второй fan-out.
- Additive schema17: job/recipient/attempt ledger, singleton fenced lease и отдельный бюджет; private-contact generation запрещает восстановление старого snapshot после delete/recreate. В ledger не backfill из users/import; существующая schema16 не переписана. Никаких runtime observers/worker/Bot API wiring или реальных отправок.
- Durable intent сохраняется до обращения к injected transport; unknown/lost response/lease loss/restart не replay. Ограниченные доказанно безопасные 429 retries, terminal unavailable и stop/cancel без обещания отката уже отправленного. Реальная policy DENY_ALL, нет вывода mandatory из category; позитивная test policy не является продуктовым решением #501.
- Сборка image проверяет IANA timezone data под UID10001 без установки новых packages/credentials/портов. Поздний upgrade требует cumulative migration/recovery review; старый rc.24/schema16 после schema17 остановится. Родительский #874 и policy/UI/privacy/deployment/pilot gates PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## v5.0.0-rc.24 — Изолированная основа сервисных кампаний

- #947 / PR #951 / часть #874-A: внутренний API owned drafts, optimistic revisions и immutable frozen payload SHA-256; bounded list8 и private-candidate dry-run1000. Нет runtime/worker/UI/transport wiring, scheduled jobs, реальных сообщений или нового сетевого surface.
- Additive schema v16 создаёт пустые campaign drafts/revisions/private-contact таблицы через штатный forward-only framework, с strict SQL/trigger/index postconditions. Unjournaled ledger не принимается, users/import не backfill в private contacts; existing data сохраняются, старый код v15 после upgrade останавливается. Предыдущий rc.23 содержит schema v15; позднее применение этого RC требует cumulative upgrade/recovery review.
- Trusted private observation API требует actor=private chat.id, human actor и existing user; не создаёт user, не снимает blocked и не означает consent. User delete очищает proof. Все DTO/errors/счётчики не содержат recipient lists/сырых исключений; text repr скрыт, link/markup/control/credential-shaped payload отклоняется.
- Dry-run применяет local User Groups/deny priority, не выдаёт eligibility или recipients: deliverable=0/unapproved для всех категорий, policy #501 не изобретена. Parent #874 и runtime/policy/pilot/deployment gates остаются OPEN/PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## v5.0.0-rc.23 — Актуальные команды без legacy-рекомендаций

- #564 / PR #943: read-only справочник «Команды бота» показывает только active записи, основной путь клиента — `/start`; `/create` и `/inbounds` скрыты из текущих рекомендаций. Версия отображения каталога — v2; полный типизированный registry сохраняет legacy записи и fail-closed AST CI продолжает требовать все зарегистрированные handlers.
- Старые slash-вызовы и callbacks `create/inbounds/subscription` сохраняют guarded non-mutating redirects через Client Portal/allowlist/rate limit. Подсказка старого slash-вызова указывает `/start`. Административные роли, `/admin` и global command registry Telegram не меняются; новых env/портов/migrations/dependencies нет.
- #564 OPEN/keep_open: собственный deployment/targeted UI visibility/redirect outcome отложен по #930. Published/Deployed/Accepted различаются, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## v5.0.0-rc.22 — Собственная история заказов и Stars-платежей

- #506 / PR #939: в профиле появилась read-only история собственных XTR-заказов и фактических Telegram Stars платежей, по 8 записей на страницу, с деталями и возвратом на исходную страницу. Статусы заказа, платежа, возврата и локального периода доступа показаны отдельно; отсутствие платежа не подтверждает списание, unknown не маскируется как успех.
- Ownership каждого объекта проверяется в SQL, доступ только в собственном private chat через существующие portal/allowlist/rate-limit guards. После удаления аккаунта сохранённый журнал через клиентский UI недоступен; retention policy не меняется. Секреты, invoice payload и provider charge IDs не выводятся.
- Поддержка `/paysupport` и Terms доступны как read-only справка; неподтверждённая публичная редакция не получает ссылку. Нет повторных invoice/refund/cancel/consent/reconcile/provider mutations, новых env/портов/зависимостей или bot migrations; schema v15. RUB/manual/PSP не смешиваются с Stars, #336 остаётся отдельно.
- #506 остаётся OPEN/keep_open до отдельного deployment и targeted acceptance; G-11 PARTIAL/NO-GO, public rollout BLOCKED.

## v5.0.0-rc.21 — HTTPS handoff из Telegram к VPN-клиенту

- #885 / PR #886: guarded private-owner карточка совместимого VPN-клиента предлагает «🚀 Открыть в <клиент>» через собственный same-origin HTTPS /compat/open/{ticket}. Telegram URL содержит только случайный ticket, а raw subscription URI выдаётся в одноразовом HTML без provider fetch и внешних redirectors.
- Ticket — bearer-like credential: TTL 90 секунд, максимум 256 в process-local памяти, один успешный GET; restart/другой worker теряет билет. Payload должен точно совпасть с import_uri по тому же owner URL/client/platform/title, не только со scheme prefix. Malformed template/URI, HEAD/POST/query/encoded path, expiry и replay fail closed; ошибочный запрос не потребляет действующий билет.
- HTML использует no-store/no-referrer и hash-based CSP; auto-open остаётся best-effort с явной ручной кнопкой. CopyTextButton/локальный QR и Back сохранены. При отключённом/невалидном compatibility template кнопки и инструкции нажать её нет. Browser/Telegram может блокировать custom scheme, успешный импорт или VPN-соединение не обещаются.
- Обновлены UI/Client Setup/Admin Setup и security boundaries: /compat/open/ входит в существующий no-log/no-cache HTTPS ingress, ticket нельзя пересылать или логировать; HTTP-страница не переаутентифицирует Telegram owner. Новых портов, provider mutations, dependency changes или SQLite migrations нет, bot schema v15 сохранена.
- Required CI: 1569 Python tests (3 skipped); локально targeted29/full1569 (16 skipped — Nginx отсутствует). Main и fresh supply-chain audit PASS. Это отдельный RC одной задачи #885 по #930; #885 остаётся OPEN/keep_open до отдельно разрешённых deployment и targeted Telegram iOS/Android/desktop → client import/refresh/expiry postconditions.
- Публикация не обновляет VPS: Deployed остаётся v5.0.0-rc.18.10 только operator-reported, independent VPS read-back PENDING. Накопленный upgrade path проверяется перед поздним deployment. #887/#890 и прочие runtime acceptance gates сохраняются; G-11 PARTIAL/NO-GO, public rollout BLOCKED.

## v5.0.0-rc.20 — Изолированная web-основа и безопасность зависимостей

- #890 / PR #891: обновлены hash-pinned Pillow 13.0.0 и certifi 2026.10.19 после dependency audit. Это изменение Python-окружения; целевые compatibility/health проверки после deployment остаются PENDING.
- #887 / PR #889 и #896: добавлены оригинальный React/TypeScript/Vite/Mantine frontend, локальные проверенные assets и начальный защищённый редактор черновиков с отдельными auth/MFA/session/recovery границами. Полный паритет операторского private JSON и production publish не заявлены.
- #887 / PR #898, #900 и #902: подготовлены изолированные Telegram Mini App и standalone owner-confirmation pilot, single-host SQLite session ledger и synthetic Dispatcher/API wiring. Production app_runtime не подключает эти factories, публичный доступ не включается.
- #887 / PR #904 и #906: добавлены default-off staging runner/неустановленный HTTPS ingress example и read-only preflight с offline режимом по умолчанию. Реальные Bot API, DNS/TLS, polling/listeners и physical devices не запускаются публикацией RC.
- #887 / PR #911, #912 и #915: добавлены offline import planner, инертный preview и отдельный reviewed client/platform/version contract. Shipping reviewed allowlist пуст; imported JSON, SVG и название клиента не дают права на URL/Copy/QR.
- #887 / PR #917, #919 и #921: server-side owner eligibility, session-bound одноразовые proofs и приватный single-host SQLite digest ledger; Host/Origin/CSRF, replay/revocation и fail-closed проверки. Multi-host/NFS и production ingress не аттестованы.
- #887 / PR #923, #925 и #929: source-only owner-bound delivery с раздельными Copy/QR правами, безопасный manual WebView fallback без custom schemes, browser-compatible GET CSRF и ClipboardItem в исходном click; объединены D3h evidence intake и D3i synthetic staging. По умолчанию delivery OFF, allowlists пусты, staging /deliver запрещён; offline readiness остаётся BLOCKED до независимой device/staging проверки.
- #930 / PR #931, #932 и #933: зафиксирована автономная очередь разработки с обязательными review/tests/CI/checkpoints и отложенными VPS/live acceptance. Это начальный объединённый RC с накопленными #887/#890; последующие самостоятельные задачи получают отдельный RC.
- Новых bot SQLite migrations нет, schema v15 сохраняется. Это prerelease без deployment: фактически Deployed остаётся v5.0.0-rc.18.10 только operator-reported; independent VPS read-back PENDING. #887/#890 и прочие runtime Issues сохраняют собственные acceptance gates, G-11 PARTIAL/NO-GO, public rollout BLOCKED. Установка итогового RC позднее требует проверки всего накопленного migration/config/agent пути и отдельного разрешения.

## D2e — read-only staging preflight, ещё не объединён (2026-10-25)

- Для #887 подготовлен default-off CLI `subscription_page_staging_preflight.py` с тремя независимыми режимами: offline-проверка закрытого staging JSON без сети/токена, отдельно разрешённые read-only Telegram Bot API `getMe`/`getWebhookInfo` identity checks без polling, и до пяти явно разрешённых `HEAD` к публичному staging HTTPS через system-CA/TLS/SNI с pinned DNS single-IP, запретом чужих Host и `/admin/`/`/compat/`/`/approve`, проверкой no-store/HSTS/CSP. В любой ошибке обезличенный `BLOCKED`; offline/test scope не равен live acceptance.
- Новые synthetic unit-negative тесты: отсутствие сетевых вызовов/чтения токена по умолчанию, запреты смешанных flags, test/private/multiple DNS, ошибочного origin, недостаточных HTTPS headers и identity mismatch; [runbook](docs/SUBPAGE_STAGING.md) уточняет trusted edge, consent и физические устройства. Required CI/merge нового PR **PENDING**; live staging Bot API, TLS/edge rate/429, phishing/relay и iOS/Android WebView smoke **не проводились**.
- Это не Release/Deployed/Accepted: текущий main после D2d #904/docs #905 SHA `2f721670cf6573ea50839cdb57f0ee4e8817f7cd`; Published `v5.0.0-rc.19` без D2d/D2e, Deployed `v5.0.0-rc.18.10` только operator-reported, #887 OPEN/keep_open, G-11 PARTIAL/NO-GO и public rollout BLOCKED.
## D2d — изолированный staging Telegram/HTTPS security-gates, MERGED в main (2026-10-25)

- Для #887 подготовлены строго default-off staging Bot API runner с отдельным проверяемым Bot ID/username/webhook, закрытой token/config директорией, синтетическим read-only owner DTO и localhost-only API; **реального live Telegram/polling или production wiring нет** до отдельного разрешённого запуска.
- В отдельном неактивном staging Nginx template: SNI/Host denial, узкие пять API endpoints, trusted TCP-peer rate/429 и no-store/no-log. Опциональный staging frontend и private Telegram approval сверяют **весь 16-символьный код** с HTTPS origin, при этом обычный D2c default behaviour прежний. Синтетические Python/Playwright/ephemeral TLS негативные тесты: [PR #904](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/904) squash MERGED 2026-10-25T16:30:54Z, independent `main` read-back SHA `42afc79eccbbe0237fb5112abdd3d59abe46d998`. На exact pre-merge head `add64b5e61930f92f4f18bd8b063ce6c1349bc62`: [`test` PASS](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40211280015) (1483 tests, 3 skipped), [`title` PASS](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40211585788), [`frontend` PASS](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40211280089), [`supply-chain` PASS](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40211280010); post-merge push [`test` PASS](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40212046681), [`frontend` PASS](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40212046656) и [`audit` PASS](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40212046635); Roadmap docs PR проходит независимый CI и не merged.
- Это **не** Release/Deployed/Accepted: Published rc.19 не включает D2d; Deployed rc.18.10 только operator-reported, #887 OPEN, G-11 PARTIAL/NO-GO; operator secrets/review, реальные TLS/VPS и iOS/Android/WebView/Telegram acceptance PENDING. [Staging runbook](docs/SUBPAGE_STAGING.md).

## D2c — изолированное подключение Telegram Router и localhost API, не опубликовано (2026-10-25)

- В #887 новая **выключенная по умолчанию** фабрика `subscription_page_pilot_wiring.py` связывает standalone HTTP API, приватный aiogram Router и отдельный защищённый local SQLite CAS ledger внутри явно разрешённого pilot. По умолчанию ничего не запускается: `app_runtime`/production dispatcher, webhook/polling, TLS/edge и `/compat/` не изменяются. Проверка `explicitly_enabled is True` обязательна при создании и при запуске отдельного listener, который может слушать только `127.0.0.1`; запрет публичного bind и произвольного пути основной БД.
- Сквозные synthetic тесты `tests/test_subscription_page_pilot_wiring.py` покрывают действительный `Dispatcher.feed_update()`, fake Bot API transport, localhost `aiohttp`, private owner confirmation → one-time browser session, cross-account/forwarded/replay/expiry/feature-off/Host/Origin denial, logout и cleanup. Не используются реальные Telegram/3x-ui/пользовательские токены, нет доказательства TLS/WebView или anti-phishing UX на устройствах.
- CI exact-head/merge остаются **PENDING** до независимого GitHub Actions read-back. Published `v5.0.0-rc.19` без D2b/D2c; Deployed `v5.0.0-rc.18.10` только operator-reported; Issue #887 keep_open, full G-11 PARTIAL/NO-GO, публичный rollout BLOCKED.

## D2b standalone — merge #900 в main, без публикации и deployment (2026-10-25)

- [PR #900](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/900) **squash MERGED** 2026-10-24T21:34:55Z, независимый GitHub read-back `main` SHA `54e045e827b65b62e5a8a010fe3ef6582a2f0b54`; Issue [#887](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/887) остаётся `OPEN / keep_open`. Предыдущие Draft-разделы ниже — история разработки.
- В `main` добавлены **инертные, default-off** private Telegram approval Router, standalone browser-bound challenge/session API, origin-pinned local SQLite atomic one-time CAS, React pilot UI и негативные тесты. **Ни Telegram Router, ни standalone HTTP listener не подключены к `app_runtime`/production**; реальные bearer URL, ключи и `/compat/` не изменены.
- Предмерджевые required [`test` PASS](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40133402660) (1465 Python tests, 3 skipped), [`title` PASS](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40133693328), [frontend-model PASS](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40133402635) (15 Node, 57 default + 4 opt-in Playwright), [supply-chain PASS](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40133402662). Post-merge push CI отдельно не аттестован. [Post-merge audit](docs/audits/2026-10-25-887-d2b-postmerge-roadmap-checkpoint.md); локальная SQLite не заменяет shared multi-VPS state. Published `v5.0.0-rc.19` **без D2b**, Deployed `v5.0.0-rc.18.10` operator-reported; real Telegram/HTTPS/edge/WebView, private JSON 1:1, D3/Copy/QR и G-11 production acceptance **PENDING**.

## D2b private Telegram owner approval и shared SQLite — исторический Draft checkpoint #900, не опубликован (2026-10-25)

- В #887/PR #900 реализована **изолированная, не подключённая к production** фабрика aiogram Router: `/web_login <challenge>` только из приватного verified Update, повторная проверка pilot/owner, явное `✅ Подтвердить вход` / `✖ Отмена`. Callback привязан к одному owner/private chat/bot message ID, с одноразовым nonce; не содержит bearer URL, cookie или `sub_id`. Нельзя подтвердить чужой browser identity только из URL/группы/forwarded message.
- Опциональный локальный `StandaloneSQLiteLedger` в отдельном защищённом файле (0700 dir/0600 DB) добавляет транзакционный `BEGIN IMMEDIATE`, SHA-256 identifiers, atomic one-time challenge→session, согласованный отзыв и TTL между экземплярами. Это **не** миграция `bot.sqlite3` и не multi-VPS storage. Тесты aiogram private callback, двух веб-воркеров, SQLite CAS, permissions/restore и отдельного `python -I` read-back; свежий exact-head CI до подтверждения **PENDING**.
- Bot Router/web app всё ещё **не подключены** к `app_runtime`, нет публичного URL, edge IP/rate/SNI, подтверждённой реальной Telegram Update и distributed multi-bot prompt persistence. Публичный standalone login, D3, Release, Deployment, Acceptance остаются PENDING; G-11 PARTIAL/NO-GO.

## D2b standalone owner-proof challenge — feature branch, не опубликован (2026-10-24)

- #887: добавлен изолированный серверный обмен `standalone/start → доверенное private Telegram подтверждение → standalone/complete`, отдельные ограниченные Secure/HttpOnly browser/session cookies и одноразовый challenge. Публичный код браузера сам по себе не является credential, одобрение возможно только через будущий verified private bot handler. Отдельный `standalone/me` использует тот же минимальный owner-scoped DTO, что Mini App, без bearer URL, `sub_id`, email, key/HWID и admin RBAC.
- Новый выключенный по умолчанию React/Mantine standalone pilot UI и Node/Python/Playwright негативные regression tests: cross-browser binding, private-chat approval, replay/expiry, Origin/Host, provider/pilot revocation, limit. Никакой код не импортируется в действующий `app_runtime`, Telegram handler и HTTPS listener ещё не подключены. Доверенная bot approval integration, shared multi-worker sessions, реальный TLS/edge/WebView, полный D2/D3, Release/Deployed/Accepted — **PENDING**, G-11 PARTIAL/NO-GO.

## D2a Telegram Mini App / React pilot — merged в main, не опубликован (2026-10-24 23:15 UTC+03:00)

- [PR #898](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/898) **squash MERGED** на `main` SHA `9f6619162b4150a282ae2ef75ce271664b30938f`; GitHub read-back подтвердил merged и открытый [Issue #887](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/887). Исходные два раздела D2a ниже — исторические pre-merge checkpoints, не новые ветки.
- Изолированный backend проверяет подписанный Telegram `initData` и freshness, выдаёт bounded owner/pilot customer session и read-only минимальный DTO. React pilot bridge в обычной сборке выключен; ручной вход без bearer URL, ключей или `initDataUnsafe`. `app_runtime`/`/compat/` не менялись; production endpoint не включён.
- Предмерджевые required `test/title` PASS: 1436 Python (3 skipped), 9 Node, 57 default/2 opt-in Playwright; supply-chain audit PASS. Post-merge push CI отдельно PENDING. [Post-merge audit](docs/audits/2026-10-24-887-d2a-postmerge-roadmap-checkpoint.md). **Published** остаётся `v5.0.0-rc.19`, **Deployed** `v5.0.0-rc.18.10` только operator-reported, D2b standalone auth, D3/TLS/WebView/device и acceptance PENDING, G-11 PARTIAL/NO-GO. Roadmap docs checkpoint отдельным PR, пока не merged — ROADMAP SYNC PENDING.

## D2a frontend pilot bridge — feature branch, не опубликован (2026-10-24)

- В #887/PR #898 добавлен выключенный по умолчанию TypeScript transport и отдельная React/Mantine pilot-панель для raw Telegram `initData` → server session → read-only DTO. Вход только по клику, никаких auth URL, persistent browser storage и прямых 3x-ui вызовов; исходные D1a demo/Copy-QR действия не активируются.
- Node unit tests и browser default-off regression проверяют тот факт, что обычная страница не открывает pilot без build flag. Backend не запущен, standalone login, реальный TLS/WebView, multi-worker sessions, release/deploy и acceptance **PENDING**.

## D2a Telegram Mini App auth — feature branch, не опубликован (2026-10-24)

- Для #887 подготовлен изолированный серверный контур Mini App: HMAC/freshness проверка `initData`, одноразовые bounded cookie-сессии и replay/rate guards, повторная проверка pilot + feature flags при каждом запросе.
- Только read-only customer DTO без bearer subscription URL, `sub_id`, email и admin RBAC; синтетические regression tests для tamper/replay/CSRF/IDOR/expiry/revocation. Нет изменений `app_runtime`, `/compat/`, frontend и production listener. Standalone auth, TLS, device/WebView, release/deploy/acceptance — **PENDING**.

## D1b защищённый редактор — feature branch, не опубликован (2026-10-24)

- Отдельные admin login/roles, CSRF, Fernet-encrypted SQLite drafts, optimistic revision locks, audit metadata, React editor (брендинг, переводы, платформы, шаги, кнопки, full/selective JSON import/export, инертный preview); metadata-only review proposal.
- UI D1b предпросмотра показывает те же 39 исходных локальных SVG + INCY (MIT), что D1a, включая платформы, клиентов, шаги и инертные кнопки; подозрительные ключи остаются fallback. Browser tests проверяют фактическую загрузку всех 40 иконок, контраст исходных светлых/тёмных SVG и адаптацию 320px/200% (включая длинные подписи переключателей). Исходные ассеты не переписаны.
- Изолированный admin API усилен обязательным отдельным TOTP для каждого пользователя, replay и shared-seed denial, bounded/idle sessions, строгими Host/Origin/CSRF и owner-only encrypted SQLite. В production не интегрирован. Реальная публикация/rollback, TLS/MFA enrollment, key rotation, multi-node sessions, оригинальный JSON 1:1 и инструкции INCY/RabbitHole — PENDING. Issue #887 keep_open.

- D1b security follow-up (#887): анти-replay TOTP переведён из памяти процесса в приватную SQLite-таблицу с атомарным `BEGIN IMMEDIATE`, отказом повторного шага между экземплярами с общей базой и fail-closed `503` при ошибке записи. Добавлены тесты устойчивости после пересоздания API; подтверждение нового head CI и эксплуатационная проверка распределённой инфраструктуры остаются PENDING. Это **не** release/deployment/acceptance.

- D1b admin session hardening (#887, только Draft PR #896): session cookie теперь представлен в private SQLite только SHA-256, CSRF — Fernet ciphertext; TTL/idle-expiry и общий logout сохраняются после перезапуска и между экземплярами с одной SQLite. Выдача сессии и TOTP anti-replay стали атомарной операцией; при отказе SQLite вход/проверка/отзыв fail-closed. Добавлены тесты межэкземплярных сессий, лимита, ротации, ролей и race. Это **не** включение runtime или security approval: HTTPS/HA/rate-limits/enrollment/key rotation и реальный canary PENDING.

- D1b security hardening #887 (только Draft PR #896): cookie-сессии дополнительно привязаны keyed HMAC-SHA256 к текущим PBKDF2 verifier, TOTP enrollment и role. Старые неподписанные D1b-сессии отзываются при SQLite schema upgrade; смена пароля/MFA/role или удаление аккаунта делает прежние cookie недействительными при обращении к обновлённому экземпляру. Добавлен защищённый owner/self `POST /sessions/revoke` для общего отзыва и UI «Завершить все сеансы»; одиночный logout больше не имитирует успех при `503`. Добавлены отрицательные тесты RBAC, CSRF, миграции, fail-closed и межэкземплярного отзыва. Условие синхронизации конфигурации учётных записей, HTTPS, MFA enrollment/recovery, multi-VPS/rate-limits и key rotation ещё **PENDING**; ни merge, ни Release, ни deployment не выполнялись.

- D1b офлайн lifecycle администратора (#887, только Draft PR #896): отдельный зашифрованный Fernet roster-файл с owner-only 0700/0600, сериализованной и атомарной CAS-записью, первичной инициализацией, ротацией парольного verifier и подтверждаемым TOTP recovery существующего администратора. API поддерживает динамический `accounts_loader` и fail-closed `503` при недоступном roster; после ротации актуальные учётные данные повторно проверяются без перезапуска. Секреты/verifiers скрыты из `repr`, файлы/токены не попадают в исходники. Подтверждение личности оператора, secret delivery, резервные копии, Fernet key rotation, общая файловая синхронизация разных VPS и production acceptance остаются **PENDING**. Никаких новых recovery web-routes, ботовых миграций, release/deploy нет.

- D1b Fernet escrow/recovery (#887, **только Draft PR #896**): добавлен изолированный offline `OfflineD1bRecovery` для зашифрованного sealed backup под независимым ключом, обязательной полной проверки snapshot перед публикацией, восстановления в новый приватный каталог и согласованной ротации roster + SQLite revisions с сохранением истории/TOTP anti-replay и отзывом всех cookie sessions. При потере основного Fernet key возможно восстановление из backup-escrow под **новым** ключом без plaintext key/dump в файлах. Остановка всех D1b writers, операторская key custody/retention, реальный recovery drill и cutover остаются **PENDING**; никаких автоматических production mutations, merge/release/deploy нет.

- D1b recovery/HTTPS rehearsal (#887, **только Draft PR #896**): отдельный hermetic subprocess-based disaster-recovery drill восстанавливает синтетические Fernet escrow/SQLite/roster после удаления исходного каталога и без старого ключа, подтверждает сохранение TOTP replay/proposals, отзыв cookies, новый login/CSRF+Host/Origin и fail-closed wrong/corrupt/replay restore. Добавлен **неактивный** Nginx HTTPS-конфиг с placeholder `admin.example.invalid`, loopback-only upstream, SNI/Host validation, CSP/no-store и per-IP login/API limits; статические контрактные и опциональные синтаксические `nginx -t` тесты. Реальный separate-host DR drill, TLS DNS/cert, custody, approval, rollout и acceptance **PENDING**. Никаких deploy, публичного listener или включения в `app_runtime`.

- D1b HTTPS edge SVG paths (#887, только Draft PR #896): исправлен будущий `404` для 39 утверждённых self-hosted SVG и точного `/client-icons/incy.svg` в неактивном Nginx preview. Широкий `/client-icons/` и альтернативные файлы не открываются, а контрактный тест сверяет `staticSvgPaths.ts`, реальные файлы и узкие `location`. Настоящий TLS/VPS, acceptance, Merge, Release и Deployment PENDING.

- D1b HTTPS loopback smoke (#887, **только Draft PR #896**): добавлены отдельный `nginx`+`openssl` TLS/HTTP тест на ephemeral `127.0.0.1`, synthetic admin backend, 40 SVG/asset `200`, запреты `404`, Host/SNI `444`, no-store/CSP, forwarded-header hardening и `429` login. Это не VPS/deployment; дальнейшая проверка production TLS, HA, admin RBAC/CSRF совместно с реальным edge, D2/D3 и полная приёмка PENDING.

- D1b TLS→real-admin API integration security smoke (#887, **только Draft PR #896**): изолированный HTTPS Nginx теперь проверяется с настоящим `create_editor_app` и синтетическим owner/editor/viewer MFA/TOTP, encrypted SQLite и сессиями; проверяются guest/Bearer, Origin/forged headers, CSRF, RBAC, `428`/`409`, anti-replay, отзыв cookies, запрет publish/rollback и CORS. Публичный port/DNS, реальный cert/key, recovery/VPS и полная приёмка не проверялись, Merge/Release/Deployment отсутствуют.

- D1b aiohttp deny-path compatibility (#887, **только Draft PR #896**): защищённая middleware теперь `raise` для `web.HTTPException` после добавления `no-store`/CSP/frame/nosniff, вместо устаревающего возврата объекта исключения. Отдельный test фиксирует guest `401`/wrong-origin `403`, security headers и отсутствие соответствующего `aiohttp` deprecation warning; это не изменение привилегий, auth-политики или production deployment.

- D1b pre-merge edge login hardening (#887, только Draft PR #896): backend больше не обязан использовать единственный `request.remote=127.0.0.1` bucket для всех клиентов доверенного Nginx. Добавлен explicit `trusted_loopback_proxy` (default OFF), fail-closed проверка peer/Proto/Host/единственного canonical forwarded client IP и очистка истёкших buckets без ослабления active 429. Новые offline unit/real TLS 2-client tests; никаких изменений deployed bot, DNS/TLS, Release и production.

- D1b security review URL safety signal (#887, только Draft PR #896): убран обход предупреждения по `{{SUBSCRIPTION_LINK}}` для произвольных URI; `javascript:`, unknown schemes, шаблонные URL и credentials/empty ссылки не принимаются за синтаксически безопасные HTTPS. Добавлен Playwright negative test с инертным preview, host allowlist и реальная публикация по-прежнему BLOCKED.

## Неопубликованные изменения в main — D1a preview #887 (2026-10-24)

- [PR #889](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/889) **Squash MERGED** в `main` `74038c37ddbc13d312727c5f1e5c247c8eb1d8ba`. Добавлен **изолированный offline React 19/TypeScript/Vite/Mantine предпросмотр** страницы подписки и инструкций, локальный JSON v1 импорт, UI с пятью языками и семью платформами, 39 оригинальных SVG из операторского набора и отдельная MIT-иконка INCY. Ссылки и действия в превью заблокированы; auth, API, реальная выдача подписок и deployment не добавлены.
- Перед merge required `test/title/audit/frontend-model` PASS и Playwright **43/43**; post-merge `main test/audit/frontend-model` PASS, проведена независимая визуальная проверка фарси при 320 px / 200% zoom; детали [аудита](docs/audits/2026-10-24-887-d1a-visual-rtl-svg-review.md). Это не полная приёмка D1a/продукта и не публикация версии: Published по-прежнему `v5.0.0-rc.19`, Deployed `v5.0.0-rc.18.10` только operator-reported.
- [Issue #887](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/887) **OPEN**: D1b защищённый веб-редактор, D2 безопасная auth/Telegram Mini App, D3 device/WebView/реальные ссылки/canary и оригинальный JSON 1:1 — PENDING. Инструкции INCY/RabbitHole будут предоставлены оператором позже, без подмены вымышленными шагами. Release и deployment не выполнялись; [post-merge checkpoint](docs/audits/2026-10-24-887-d1a-postmerge-checkpoint.md) требует отдельного docs-only merge.

## v5.0.0-rc.19 — Client Portal: карточка подписки и импорт в VPN-клиенты

- [#497 / PR #880](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/880): единая read-only карточка подписки показывает status/entitlement, тариф, подтверждённый срок и состояние активации; неизвестная доступность провайдера не маскируется как active. Пилот сохраняет owner/private/feature guards.
- [#473 / PR #882](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/882): Client Portal предлагает client-specific deep-link/локальный QR для Incy, v2raytun, Happ, Shadowrocket, V2Box, Karing, OneXray и Throne с матрицей iOS/Android/Windows/macOS/Linux. Для клиентов с поддержкой заголовка используется динамический безопасный `subTitle` из 3x-ui, не фиксированное `VPN`.
- `CopyTextButton` и локальный QR доступны только после owner/private/pilot guards; URL/QR fallback сохранён, неизвестные и неоднозначные URI fail-closed. Нет новых платежей, миграций SQLite, новых provider mutations или автоматического запуска VPN.
- **Совместимость:** ручной URI-import Incy 2.6.4 / v2raytun 2.4.7 на iOS/Android, Incy 2.6.4 на macOS, Happ iOS/Android/macOS и Shadowrocket только Apple — operator-reported scoped PASS; исправление заголовка Shadowrocket operator-reported PASS. V2Box/Karing/OneXray/Throne и Windows/Linux version-specific smoke PENDING. Реальные клиентские версии/сборки и успешное подключение ко всем серверам не гарантированы.
- [PR #871](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/871): исправлена CI-only классификация Roadmap и сохранён fail-closed для runtime реализации; не меняет функциональность бота или acceptance, но входит в воспроизводимый release scope.
- **Controlled-canary prerelease:** публикация не запускает deployment. До post-deploy проверки Telegram→подписка→клиент, QR, privacy/ownership, safe fallback, `subTitle` и release-tag/health read-back — Issue #473/#497 keep_open, G-11 PARTIAL/NO-GO, public rollout BLOCKED. Published до этого RC: `v5.0.0-rc.18.10`; Deployed `rc.18.10` operator-reported.

## v5.0.0-rc.18.10 — безопасное распознавание Happ на Android

- [PR #864](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/864) / [Issue #827](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/827): полный User-Agent `Happ/4.7.1/Android/17912108360521999608` теперь строго распознаётся как `Happ`, включая 20-значное непрозрачное окончание; Android 17 и Pixel 6 не изменяют правила определения приложения.
- Только точный ограниченный формат `Happ/<version>/Android/<20 цифр>`. Числовое окончание не считается номером сборки и не отображается клиенту. Добавлены позитивные/негативные regression cases, сохранён fail-closed для произвольных дополнительных полей, URL, токенов и других брендов.
- Обновлены `docs/UI_STYLE.md`, `docs/CLIENT_SETUP.md` и Roadmap; общие VPN-client parser, identity/ownership/RBAC, HWID DELETE/no-replay, pinned 3x-ui API, SQLite schema v15 и платежи не изменены, миграций нет.
- **Исторический release-prep checkpoint:** публикация сама не выполняла deployment. Позже `rc.18.10` развернута по отчёту оператора, 23/23 targeted HWID UI PASS, #827 closed/completed; полный G-11 PARTIAL/NO-GO, public rollout BLOCKED. См. текущий checkpoint выше.

## v5.0.0-rc.18.9 — исходная Windows ОС в админской карточке

- [PR #861](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/861) / [Issue #834](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/834): исходные безопасные поля 3x-ui `deviceOs=Windows 10` и `osVersion=10.0` теперь показываются в **административной** строке `Исходная ОС: Windows 10 10.0`. Человекочитаемая `ОС: Windows 10`, порядок полей и клиентская карточка без изменения.
- Проверено, что `Windows` + `10_10.0.19045` сохраняет ранее поддержанный составной исходный вид, а опасные/длинные исходные версии не отображаются. Regression tests, `docs/UI_STYLE.md`, `docs/CLIENT_SETUP.md` и Roadmap обновлены.
- **Совместимость:** только admin-only display, без изменений metadata провайдера, HWID identity/ownership, RBAC, DELETE/no-replay, pinned 3x-ui API, SQLite schema v15 и платежей.
- **Controlled canary:** публикация GitHub Release не выполняет deployment; #834 остаётся OPEN/keep_open до exact deployed tag/SHA и targeted read-only original OS/client privacy/health smoke. G-11 PARTIAL/NO-GO; public rollout BLOCKED.

## v5.0.0-rc.18.8 — Windows OS и исходные HWID-поля

- [PR #858](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/858) / [Issue #834](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/834): при раздельных полях `deviceOs=Windows`, `osVersion=10_10.0.19045` общий renderer показывает `Windows 10 (сборка 19045)` в admin list/detail и Client Portal. Согласованные Windows 10/11 build поддерживаются; неподтверждённая marketing version не угадывается, конфликтующие значения не маскируются.
- В расширенной admin-only HWID-карточке порядок `Модель` → `Исходная модель` → `ОС` → `Исходная ОС` → остальные поля; исходная строка для безопасной split-пары — `Windows 10_10.0.19045`. Значок desktop и исходная модель сохраняются; клиент не видит технические исходные поля, fingerprint или raw UA.
- Добавлены регрессионные тесты исходной составной ОС, порядка полей, безопасности входных данных и клиентского rendering; только read-only представление. Нет изменений HWID identity/ownership, RBAC, DELETE/no-replay, pinned 3x-ui API, SQLite schema v15 или платежей.
- **Controlled canary:** публикация prerelease не выполняет deployment. Issue #834 остаётся OPEN/keep_open до подтверждённого exact deployed tag/SHA и targeted read-only проверки Windows/admin/client parity, privacy и health; G-11 PARTIAL/NO-GO, public rollout BLOCKED.

## v5.0.0-rc.18.7 — Karing 191 символ и HWID-интерфейс

- [PR #852](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/852) / [#827](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/827): распознавание ровно заданного 191-символьного составного Karing User-Agent с терминальным ` (Prefer ClashMeta Format);HiddifyNext`, без произвольных хвостов; 167-символьный ` (Preferences)`, строго 160-символьный fallback и отрицательные security cases сохранены.
- [PR #855](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/855) / [#854](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/854): для ограниченной Windows `DESKTOP-…` возвращён 🖥️ после нормализации имени, одинаково в административном списке и клиентских списке/кнопках/detail; ноутбуки остаются 💻. Известная `Windows 10_10.0.19045` отображается как `Windows 10 (сборка 19045)` без угадывания неподтверждённых версий.
- [PR #855](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/855): смысловые эмодзи в подробных admin/client HWID-карточках; bounded поле `Исходная ОС` показывается только администратору и только при безопасном значении. В клиентский контур передаётся лишь готовая ограниченная иконка, не техническая исходная модель/hostname, Fingerprint или сырой User-Agent.
- **Совместимость и безопасность:** только read-only представление, без изменения device identity, HWID ownership, RBAC, callbacks, DELETE/no-replay, платежей, HTTP/API, SQLite schema v15 или 3x-ui v3.10.2. [PR #853](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/853) — только post-merge Roadmap checkpoint; runtime-содержимого не добавляет.
- **Controlled canary:** публикация prerelease не выполняет deployment. #827/#830/#833/#834/#838/#854 остаются OPEN; требуется exact deployed tag/SHA и targeted read-only Karing 191/167/160, desktop/Windows/client-admin parity, приватность/health; G-11 PARTIAL/NO-GO, public rollout BLOCKED.

## v5.0.0-rc.18.6 — Диагностика и безопасное распознавание Karing

- [PR #849](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/849) / [#827](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/827): сохранён прежний full-match Karing User-Agent длиной 167 символов; для ровно 160-символьного обрыва известного составного UA `(Prefe` добавлен строго ограниченный fallback только при правильной последовательности версий и компонентов. Невалидные, произвольные и секретоподобные хвосты по-прежнему дают «Не определён».
- [PR #849](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/849): административная детальная HWID-карточка сохраняет прежнюю строку `User-Agent` с preview до 160 символов и дополнительно показывает фактическую длину/отметку обрезки preview и результат полного display-only парсера. Client Portal не показывает raw UA, fingerprint или скрытые хвосты.
- **Совместимость:** сохранены определения Throne, V2Box, OneXray, Karing, Incy, Happ, прочих безопасных generic клиентов; `deviceModel`, `deviceOs`, `osVersion`, HWID ownership/identity, RBAC, callbacks и DELETE/no-replay неизменны. Нет изменений SQLite schema v15, pinned 3x-ui API v3.10.2, подписок или платежей. Offline PR CI `test`/`title` PASS, полный unittest 1273 (2 skipped).
- **Controlled canary:** только после отдельного deployment и независимой/операторской targeted read-only проверки фактической длины полного Karing UA, `Karing`/fallback, моделей/ОС, приватности и health можно оценивать acceptance. Новый релиз не является deployed/accepted; #827/#830/#833/#834/#838 keep_open, G-11 PARTIAL/NO-GO, public rollout BLOCKED.

## v5.0.0-rc.18.5 — Универсальное определение VPN-клиента по платформе

- [PR #846](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/846) / [#827](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/827): расширено безопасное display-only распознавание любого синтаксически допустимого `Client/Platform/Version` для Android, iOS, iPadOS, macOS, Windows и Linux без allowlist брендов: `Throne/Android/2.0.3` → `Throne`, `FutureVPN/iOS/1.2.3` → `FutureVPN`.
- [PR #846](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/846): сохранены прежние особенности форматов `V2Box 10.1.9/iOS 26.5.1` → `V2Box`, определение `OneXray` из составного `v2rayN` User-Agent, строго заданные `Karing`/`Incy` и обычные `Happ`/`Shadowrocket`/`v2rayNG`/`sing-box`; модели iPhone/Android/Windows/Linux, iPad/macOS, ОС и admin-only исходные HWID-метаданные не меняются.
- [PR #846](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/846): техназвания ОС/HTTP-stack, control/Unicode, нестандартные suffix, URL и `Throne/Android/2.0.3 token=secret` остаются «Не определён»; raw UA/fingerprint не выводятся в Client Portal. Offline required `test` PASS: 1269 unittest (2 skipped), `title` PASS.
- **Совместимость и безопасность:** только read-only имя заявленного приложения, не подтверждение подлинности клиента. Без изменения `deviceModel`, `deviceOs`, SQLite schema v15, pinned 3x-ui API v3.10.2, HWID identity/ownership, RBAC, callback, DELETE/no-replay, подписок или платежей.
- **Controlled canary:** публикация `rc.18.5` через immutable tag и GitHub Release не означает deployment/acceptance; targeted read-only HWID smoke `Throne`/неизвестный безопасный бренд/unsafe suffix, модели/ОС и health после отдельно разрешённого deployment PENDING. #827/#830/#833/#834/#838 keep_open; full v5 NOT PASS, G-11 PARTIAL/NO-GO, public rollout BLOCKED.

## v5.0.0-rc.18.4 — Корректные HWID-модели и VPN-клиенты

- [PR #844](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/844) / [#827](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/827): read-only распознавание ограниченных составных User-Agent Incy (Android/Windows Dalvik), OneXray и Karing; безопасное определение версий приложений с v/beta/rc, исключение технических идентификаторов Dalvik, okhttp, Mozilla и curl из поля «VPN-клиент».
- [PR #844](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/844) / [#830](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/830): Android-эмуляторы получают «Устройство Android», а iPad Pro с заявленной macOS — «Mac (модель не определена)»; усилено сопоставление Apple Model ID, неоднозначных Android Device-кодов разных производителей и известных Samsung SM-…/DS моделей.
- [PR #844](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/844): offline regression проверяет исходные пять операторских случаев, безопасность неизвестных и опасных User-Agent, отсутствие ложной классификации поддельных названий ОС и сохранение известных настоящих моделей.
- **Ограничения:** поддерживаются только строго распознанные форматы, произвольный или усечённый Karing/другой User-Agent остаётся «Не определён»; заявленное имя в User-Agent не доказывает идентичность приложения. Не изменены SQLite schema v15, API 3x-ui v3.10.2, device identity, RBAC, callback, HWID ownership/DELETE/no-replay, подписки и платежи.
- **Controlled canary:** prerelease и deployment выполняются отдельно после разрешений; целевая адресная read-only приёмка объединяет непроверенные критерии rc.18.3 и новые исправления rc.18.4. До evidence #827/#830/#833/#834/#838 остаются OPEN, full v5 G-11 PARTIAL/NO-GO, public rollout BLOCKED.

## v5.0.0-rc.18.3 — Безопасные HWID-карточки для разных устройств

- [PR #828](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/828) / [#827](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/827): поле `VPN-клиент` безопасно извлекает синтаксически допустимое заявленное имя из `userAgent` без фиксированного списка (`V2Box`, `v2rayNG`, `sing-box`); версии и опасные/неоднозначные значения не отображаются, fallback — «Не определён».
- [PR #832](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/832) / [#830](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/830): общие read-only названия мобильных HWID-моделей по проверенным справочникам Apple и Android, с ограниченным извлечением Apple Model ID из `User-Agent` и консервативным fallback при неизвестном или противоречивом идентификаторе. Исходные каталоги подготовлены в [PR #831](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/831).
- [PR #835](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/835) / [#833](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/833): технические и неизвестные названия моделей Windows/Linux заменяются на безопасные «Устройство Windows» / «Устройство Linux» только при достаточном OS-признаке; реальные коммерческие названия сохраняются.
- [PR #836](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/836) / [#834](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/834): строки `deviceOs` Windows 10/11 нормализуются с достоверным номером сборки, например `Windows 10_10.0.19045` → `Windows 10 (сборка 19045)`; версия Windows не угадывается по NT 10.0, Linux/mobile OS не изменяются.
- [PR #839](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/839) / [#838](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/838): в административной подробной карточке при нормализации модели/ОС доступны ограниченные фильтром необязательные поля `Исходная модель` и `Исходная ОС`; опасные значения скрываются и не попадают в клиентский интерфейс.
- **Совместимость и безопасность:** изменения относятся к read-only HWID presentation; идентичность устройств, authorization/ownership, callback-ID, подтверждение/DELETE и no-replay не меняются. Новых SQLite migrations и расширения 3x-ui API нет: schema v15, pinned 3x-ui v3.10.2.
- **Controlled canary:** выпуск prerelease через штатный immutable tag и GitHub Actions сам по себе не выполняет production deployment. После отдельно разрешённого deployment требуется targeted read-only HWID smoke по #827/#830/#833/#834/#838 с проверкой unsafe/unknown fallback, разграничения admin/client, неизменности DELETE и финального health. Эти Issues остаются OPEN до собственного scoped acceptance; full v5 NOT PASS, G-11 PARTIAL/NO-GO, public rollout BLOCKED.

## v5.0.0-rc.18.2 — VPN-клиенты и постраничные устройства

- [PR #821](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/821) / [#816](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/816): карточка собственного HWID всегда показывает «VPN-клиент», безопасно распознаёт Happ, Incy и Shadowrocket по валидированному префиксу `userAgent`; для неизвестного клиента выводит «Не определён», не раскрывая сырой `userAgent`.
- [PR #821](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/821) / [#814](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/814): фактическая `macOS (Designed for iPad)` определяет эмодзи `💻`, даже если модель содержит iPad; на `iPadOS` остаётся `📱`.
- [PR #821](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/821) / [#820](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/820): административный HWID-список использует компактное описание и эмодзи как Client Portal, не более 8 устройств на страницу, кнопки навигации и возврат на исходную страницу; клиентский список сохраняет лимит 5 устройств на страницу.
- [PR #821](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/821) / [#471](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/471): из клиентской подробной HWID-карточки оставлен переход «⬅ Устройства»; кнопка «Личный кабинет» остаётся в списке.
- **Совместимость и безопасность:** SQLite schema v15, API 3x-ui v3.10.2, RBAC, ownership, стабильные callback-ID и guarded DELETE/no-replay не изменялись. Regression/CI подтверждены; неизвестные и недоверенные `userAgent` не передаются в UI.
- **Controlled canary:** выпуск `rc.18.2` через отдельный release-prep PR и штатный immutable prerelease workflow не выполняет production deployment. Предыдущий `rc.18.1` опубликован и operator-reported deployed, targeted A4/A5 там **FAIL**. После отдельно разрешённого deployment `rc.18.2` необходим scoped read-only smoke VPN-клиента, emoji, admin 8/client 5 pagination, Back и post-smoke health. #814/#816/#820/#471 CLOSED/completed по H1–H8; #472 CLOSED/completed по owner acceptance; independent X2/X1/X3 evidence PENDING; X2/X1/X3 provenance #472 PENDING. G-11 PARTIAL/NO-GO, public rollout BLOCKED.

## v5.0.0-rc.18.1 — Версия ОС, тип устройства и Happ/Incy в HWID-карточке

- [PR #815](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/815) / [#814](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/814): real upstream `osVersion` дополняет `deviceOs` в списке и карточке зарегистрированных HWID, без догадки и повторов; безопасные `📱`, `💻`, `🖥️`, `🔹` отражают только консервативный UI form-factor.
- [PR #815](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/815) / [#816](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/816): в карточке показывается только allowlisted имя приложения `Happ` или `Incy`, извлечённое из недоверенного upstream `userAgent`; версия приложения, raw User-Agent, неизвестные/вредоносные строки не выводятся.
- **Совместимость/security:** только read-only presentation; customer ownership, provider capability, HWID identity, лимиты, paginated callbacks, confirmation/DELETE/no-replay и SQLite schema v15 не меняются. API закреплён за 3x-ui v3.10.2.
- **Controlled canary:** `rc.18.1` — отдельный release-prep; **не Published, не Deployed и не Accepted** до отдельных разрешений/свидетельств. Текущий Published `rc.18`; его Deployed только operator-reported. Для #471/#472 D1–D8 / S1–S4 reported PASS, X1/X3 provenance неполное и X2 PENDING; G-11 PARTIAL/NO-GO, public rollout BLOCKED.

## v5.0.0-rc.18 — Карточки HWID и безопасное удаление устройства

- [PR #808](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/808) / [#471](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/471): в Client Portal добавлены компактный постраничный список по пять зарегистрированных HWID и отдельные read-only карточки с краткими model/OS/last-seen. Учитываются только проверенные уникальные upstream `id`; неизвестный/отключённый `limitHwid` не подменяется выдуманной квотой. При каждом открытии проверяются актуальная identity/ownership и недоступность провайдера; fingerprints, subscription credentials и чужие устройства не показываются.
- [PR #810](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/810) / [#472](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/472): клиенту доступно удаление **ровно одного собственного HWID** через отдельный confirmation screen. Provider-neutral `supports_device_delete/delete_device`, повторная проверка Telegram account/email и уникального `device_id` непосредственно перед запросом, одноразовый token с TTL 90 секунд, per-user cooldown 120 секунд и сериализация подтверждений в одном bot-процессе. Автоматического или слепого повтора `DELETE` нет.
- **Неопределённый результат:** timeout/network/5xx и недостоверный postcondition дают `unknown`, а однозначный отказ провайдера — `rejected`. Сообщение об успехе допускается только после полного независимого HWID inventory read-back, подтверждающего отсутствие удалённого ID. При `unknown` разрешён только read-only просмотр устройств, не blind retry; повторные/устаревшие callbacks отвергаются.
- **Совместимость:** SQLite schema остаётся **v15**, дополнительных migrations, новых 3x-ui API endpoints, привилегий, разрешений публичного Client Portal и изменений конфигурации нет. Pinned 3x-ui contract остаётся `v3.10.2`; используется уже известный `DELETE /panel/api/clients/hwids/{email}/{id}`. Process-local confirmation/cooldown не является multi-replica coordination: deployment с несколькими bot-процессами требует отдельного safety review.
- **Controlled canary:** выпуск RC **не выполняет deployment**, не открывает public rollout и не означает принятия #471/#472. На момент release-prep опубликован и operator-reported развёрнут только `v5.0.0-rc.17`; `rc.18` не Published, не Deployed и не Accepted. После отдельного разрешения на release/deployment нужны backup, SQLite `quick_check`, health/3x-ui preflight, scoped read-only smoke #471 и заранее согласованная **безопасная** targeted-проверка owner/confirm/Cancel/unknown/no-replay/read-back для #472 без необоснованных production DELETE. Issues #471/#472 остаются OPEN/keep_open до собственного acceptance; общий G-11 PARTIAL/NO-GO, юридический § 9 по #707 unpublished, public rollout BLOCKED.

## v5.0.0-rc.17 — Заказы Stars и справочник возвратов для поддержки

- [PR #801](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/801) / [#470](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/470): в `/admin → Платежи → Telegram Stars → Заказы Stars` добавлены ограниченный постраничный read-only список и карточка `Order → Payment → Entitlement`. `created/awaiting_payment` без Payment показываются как ожидание, а не ошибка; отсутствуют повторная отправка счёта, refund и provider mutations. Действует `payments.view` и прежний RBAC.
- [PR #799](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/799) / [#437](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/437): read-only справочник обращений по возвратам для Support/Admin, с навигацией, разграничением Stars/RUB, состояниями `unknown` и эскалацией Owner. Условия § 9 ещё **не опубликованы** по [#707](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/707): `docs/legal-publication.json` имеет `publication_state=unpublished`, поэтому действующие условия и ссылка не подменяются юридическим черновиком. Дополнительная 14-дневная программа не вводится; новые права на refund не выдаются.
- [PR #766](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/766) / [#760](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/760): исправлены возврат из списка ручных тарифов и отображение `♾️`/`🟡♾️`. На прежнем deployed `rc.16.6` адресная проверка U8 была FAIL; исправление требует нового deployment и targeted Back+emoji re-smoke, а не объявляется принятым при публикации.
- [PR #768](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/768), [PR #770](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/770), [PR #772](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/772), [PR #775](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/775): исправлены расхождения живой документации о Published/Deployed/Accepted и правила документированного закрытия Issues; без новых runtime payment/3x-ui mutations.
- **Совместимость:** SQLite schema остаётся **v15**; новых migrations, внешнего RUB checkout, provider API endpoints, секретов и изменений production-конфигурации нет. Pinned 3x-ui API contract — `v3.10.2`. До отдельного разрешённого deployment — immutable tag, совместимый backup, SQLite `quick_check`, Health/DB/3x-ui read-back.
- **Controlled canary:** выпуск RC не выполняет deployment и не закрывает #437/#470/#760. После отдельного deployment нужны targeted UI/RBAC/no-mutation smoke #437/#470 и U8 Back+emoji smoke #760, post-smoke health и решение по каждому Issue. Юридическая публикация #707 остаётся PENDING; общий v5 `G-11 PARTIAL/NO-GO`, public rollout `BLOCKED`.

## Подготовка v5.0.0-rc.17 — просмотр Stars Orders (#470, кандидат)

> Исторический pre-merge snapshot. Текущие результаты выпуска отражены в каноническом разделе `v5.0.0-rc.17` выше и в Roadmap.

- В админке `Платежи → Telegram Stars → Заказы Stars` добавлен bounded read-only список заказов XTR и карточка `Order → Payment → Entitlement` с точными статусами и возвратом к списку. `created/awaiting_payment` без Payment отображается как ожидание, не ошибка и не доказательство отправки invoice. Платёжные provider payload/keys не выводятся; mutation кнопок нет.
- Задача #470 в implementation PR, до merge, immutable release/deploy и адресной приёмки — PENDING. `version.py` пока `5.0.0-rc.16.6`; release candidate rc.17 плановый, не Published/Deployed/Accepted; G-11 PARTIAL/NO-GO.

## Подготовка v5.0.0-rc.17 — справочник возвратов для Support (#437, кандидат)

> Исторический pre-merge snapshot. Не подтверждает действующую публикацию § 9 или acceptance.

- Подготовлен read-only экран `/admin → Платежи → Политика возвратов` с навигацией, проверкой типа платежа/unknown, рекомендацией эскалации Owner и RBAC `payments.view`; никакого нового права на Stars refund и никакой payment/3x-ui mutation. #433/#434/#436 остаются отменёнными, добровольная 14-дневная программа не возвращается.
- Единый `docs/legal-publication.json` изначально `unpublished`: до фактической проверенной публикации соглашения § 9 (#707) раздел не показывает черновик или неработающую ссылку. Ни Terms, ни механизм акцепта не реализованы; для содержательной части #437 остаётся зависимость.
- **Статус:** это подготовка в implementation-ветке, не релиз. `version.py` остаётся `5.0.0-rc.16.6`; `v5.0.0-rc.17` не Published, не Deployed, не Accepted. Required CI, merge, согласованный immutable release и адресная приёмка — отдельные gates. G-11 PARTIAL/NO-GO, public rollout BLOCKED.

## Подготовка v5.0.0-rc.16.6 — исторический release-prep scope

- [Issue #760](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/760): подготовлена реализация read-only значка `♾` в списке и поиске пользователей, `🟡♾` при `unknown/in_flight`, фильтра `♾ Ручные` с пагинацией и batch SQLite-выборкой; без migration, 3x-ui mutation и платежей. **На дату подготовки scope не был Published/Deployed/Accepted**; позднее rc.16.6 опубликован и operator-reported развёрнут, приёмка #760/U8 остаётся PARTIAL (см. текущий Roadmap).

## v5.0.0-rc.16.6 — Ручные тарифы в списке и контроль закрытия Issues

- [PR #761](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/761) / [#760](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/760): отметка `♾` для активных ручных тарифов и `🟡♾` для `unknown/in_flight` в общем списке и поиске пользователей, read-only фильтр `Все / ♾ Ручные` с пагинацией и пакетной SQLite-выборкой без N+1; прежние статусы 3x-ui и RBAC сохранены.
- [PR #763](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/763) / [#762](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/762): fail-closed CI-сверка явных решений `completed/keep_open` с GitHub Issues и активным Roadmap, негативные регрессионные тесты; исторические operator-reported scoped acceptance #705/#730/#731/#743/#752 закрыты без изменения production.
- [PR #759](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/759): документационный checkpoint приёмки `rc.16.5`, без новых runtime mutations (docs-only).
- **Controlled canary:** версия SQLite остаётся **v15**, новых миграций, `.env`, платежей и provider mutations нет. GitHub **Published не означает Deployed/Accepted**; для `rc.16.6` после отдельно разрешённого deployment обязательны backup, `quick_check`, Health/DB/3x-ui и адресный UI smoke меток, фильтра/пагинации и RBAC без повторения прежних PASS. G-11 PARTIAL/NO-GO, public rollout BLOCKED.

## v5.0.0-rc.16.5 — Статус в поиске и безопасная замена ручного тарифа

- [PR #753](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/753) / [#743](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/743): поиск пользователей в Admin теперь показывает уже вычисленный read-only статус `enable` 3x-ui (🟢/⚪/🟡) вместо постоянного `👤`; существующий bounded `clients/list`, RBAC и callback сохранены. C3 на ранее deployed rc.16.4 был FAIL; проверка после deployment rc.16.5 ещё PENDING.
- [PR #754](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/754) / [#752](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/752): для Admin/Owner добавлена одноразовая подтверждаемая замена одного активного скрытого бесплатного бессрочного ручного тарифа другим **в пределах той же Server Group**. До remote mutation — read-only preflight, проверка прежних лимитов/Inbounds и atomic commerce CAS; после mutation — независимый read-back 3x-ui, старый manual journal становится `superseded`, новый — `active`. При `unknown` запрещён автоматический replay; доступна read-only сверка. Cross-group не поддерживается; реальные orders/payments/invoices не меняются.
- [PR #756](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/756) / [#755](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/755): исправлена синхронизация #752 в Roadmap как 🟡 `Реализовано в main` и добавлена required/scheduled CI-сверка этапа реализации с merged runtime PR; docs-only PR не считается runtime-реализацией, GitHub API unknown = FAIL/UNKNOWN.
- **Совместимость:** SQLite schema **v15** без новых миграций, `.env`, внешних платёжных сервисов и новых API endpoints. `rc.16.5` — controlled-canary prerelease: публикация не выполняет deployment и не означает acceptance. До pilot smoke нужны разрешённый deploy, совместимый DB backup, приёмка статуса поиска и одной замены manual→manual с независимым 3x-ui read-back; G-11 `PARTIAL/NO-GO`, public rollout BLOCKED.

## v5.0.0-rc.16.4 — Безопасная ручная выдача и единые статусы

- [PR #741](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/741) / [#730](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/730) / [#740](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/740): для скрытого бесплатного бессрочного тарифа разрешены независимые IP/HWID 0…1000; read-only commerce preflight различает незавершённый заказ и ожидающий применения entitlement до подтверждения ручной выдачи. Атомарный order/entitlement fence, fail-closed, одноразовый nonce и unknown/no-replay не обходятся; платежи и provider state автоматически не меняются.
- [PR #746](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/746) / [#742](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/742): единая грамматика 🟢 включён / ⚪ отключён / 🟡 неизвестно; ошибки/offline 🔴 и запреты ⛔ не подменяются состоянием disabled.
- [PR #746](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/746) / [#743](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/743): в списках и поиске пользователей — read-only статус `enable` 3x-ui через ограниченный `clients/list` при открытии страницы или поиске, без фонового polling и provider mutations; неоднозначный/недоступный источник обозначен 🟡.
- [PR #746](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/746) / [#744](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/744): из экранов версий 3x-ui/Xray навигация Back/Cancel сохраняет исходную карточку Master/direct Node, не запускает update/restart и не ослабляет RBAC.
- [PR #746](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/746) / [#745](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/745): независимые RUB/Stars ↑/↓ в административном каталоге, сохранение выбора Administrator/Owner в существующих `runtime_settings`; доступные клиенту Stars-планы сортируются по убыванию **после** backend-фильтрации. RUB invoice, конвертации валют и новых платёжных flow нет.
- [PR #747](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/747) и [PR #748](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/748): актуализированы UI, setup, Roadmap и acceptance-документы после реализации; их слияние не означает production acceptance.
- **Совместимость:** SQLite schema остаётся **v15**, новых migrations, `.env`, permissions или внешних платёжных сервисов нет. До отдельно разрешённого deployment нужны совместимый backup, journal/`PRAGMA quick_check`, проверка 3x-ui и health.
- **Controlled canary prerelease:** GitHub Published не означает Deployed/Accepted. Требуются отдельное разрешение на deployment, targeted pilot smoke #730/#740/#742–#745, independent VPS read-back и post-smoke health; #705/#731 и M1–M8 остаются PENDING/BLOCKED по своим критериям, G-11 PARTIAL/NO-GO, public rollout BLOCKED.

## v5.0.0-rc.16.3 — Понятный HWID, ограниченные бессрочные тарифы и объяснение покупки

- [PR #729](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/729) / [#734](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/734): в карточке старого тарифа вместо `legacy` показано «Лимит HWID: не задан в тарифе — сохраняется текущий лимит пользователя». Семантика `NULL`/0 и действующие ограничения 3x-ui не меняются.
- [PR #732](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/732) / [#730](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/730): у скрытого бесплатного бессрочного ручного тарифа разрешены независимые IP/HWID 0…1000; трафик и цены RUB/Stars остаются 0, видимость admin_only. Мастер объясняет ограничения сразу и пропускает неприменимые шаги; независимый read-back и защита unknown/no-replay сохраняются.
- [PR #733](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/733) / [#731](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/731): при действующей или неопределённой ручной выдаче Client Portal объясняет блокировку самостоятельной покупки, вместо ошибочного впечатления о пропавшем каталоге; backend Stars/group/visibility остаётся fail-closed.
- **Ограничение B5:** конкретная причина отсутствия тарифов в текущем pilot пока не доказана; UI-объяснение ручной выдачи не гарантирует устранения всех причин пустого каталога. #705/#731 OPEN, G-11 PARTIAL / NO-GO, public rollout BLOCKED.
- **Controlled canary:** требуется отдельное разрешение на deployment по immutable tag, post-deploy health и targeted smoke в Telegram/3x-ui (IP=2, HWID=5, отсутствие платежей, исторический NULL, Back/Cancel и причина недоступности покупок). Schema остаётся v15; дополнительных миграций нет. Published не означает Deployed/Accepted.

## v5.0.0-rc.16.2 — Раздельные IP/HWID, безопасная смена тарифа и журналы платежей

- [PR #725](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/725) / [#724](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/724): раздельные IP/HWID лимиты при настройке тарифа, в карточке и provisioning; additive SQLite v15 `plans.hwid_limit` с сохранением legacy `NULL`, независимый 3x-ui read-back `limitIp` и `limitHwid`.
- [PR #722](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/722) / [#721](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/721): Admin-only перевод `active` бессрочной ручной выдачи на finite-тариф через одноразовое подтверждение, provider postcondition, SQLite CAS; при `unknown/in_flight` — только read-only recovery, без повторной mutation.
- [PR #720](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/720) / [#719](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/719): постраничные read-only журналы Stars и ручных платежей (по 8), «Новее/Старее» и возврат из карточки; прежний `payments.view` и refund semantics сохраняются.
- [PR #723](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/723) / [#691](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/691): корректное различение `Node Panel` для Master (`не требуется`) и direct node (`не проверено на этом экране`) без изменения Flow mutations и TTL.
- **Controlled canary prerelease:** после публикации `Published` не означает `Deployed` или `Accepted`. Нужны отдельное разрешение на deployment, совместимый backup перед schema v15, read-only migration journal/SQLite `PRAGMA quick_check`, targeted Telegram/3x-ui smoke и post-smoke health; G-11 PARTIAL / NO-GO, public rollout BLOCKED.

## v5.0.0-rc.16.1 — Исправления назначения тарифов после rc.16

- [PR #714](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/714) / [#705](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/705): назначение обычного тарифа: одноразовое подтверждение и проверяемое применение в 3x-ui; read-only preflight до бессрочной ручной выдачи.
- Русские подписи видимости и групп пользователей, навигация «Назад», отображение бессрочности и сообщения подтверждения.
- Подготовлена поддержка точечного RC `rc.N.M` в release notes, GitHub CI и controlled deploy helper; `rc.17+` не затрагиваются. PR #715 синхронизировал Roadmap после merge исправлений.
- **Controlled canary candidate:** публикация только через отдельный release-prep PR, required CI и GitHub Actions. Deployed/Accepted #705 и общий G-11 — PENDING / NO-GO; нет автоматического production deployment, RUB checkout/PSP и нового public rollout.

## v5.0.0-rc.16 — Достоверный Flow и управляемые тарифы RUB/Stars

- [PR #692](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/692) / [#691](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/691): административная карточка теперь явно отличает общий `ClientRecord.flow` от Flow конкретного VLESS Reality Inbound, включая `none`. Результат `🔎 Проверить Flow` сохраняется лишь как **последняя read-only проверка, не live** (in-memory TTL 180 сек., до 128 пользователей); после истечения срока или restart — «не проверено». Имена нод и Inbound отображаются по Master `NodeInfo.name`/`Inbound.remark` с неизменными стабильными `#id`; Flow POST, provider mutations, RBAC, nonce и Node matching не изменены.
- [PR #710](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/710) / [#705](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/705): административный каталог хранит **две независимые цены** — будущую RUB в копейках и Telegram Stars/XTR в целых единицах — с возможностью отключить каждую или обе. Финальные RUB-цены 30/90/180/365 дней из утверждённой матрицы: **200 / 540 / 1020 / 1800 ₽** при настройке соответствующих отдельных планов; автоматических промокодов или создания этих записей миграцией нет, XTR автоматически из RUB не рассчитывается.
- [PR #710](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/710) / #705: отдельная `active` и `visibility=all/groups/admin_only`, include/exclude локальных User Groups, динамический backend authorization списка, карточки, прямого callback, заказа и `precheckout`; удаление группы/смена membership и ошибки SQLite обрабатываются fail-closed. В Telegram клиент покупает **только Stars/XTR**; RUB/СБП/Platega-витрина и PSP [#336](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/336) **не включены**.
- [PR #710](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/710) / #705: SQLite **schema v14** (additive), `plans.rub_price_enabled`, правила аудитории и отдельный журнал `manual_entitlements`. Скрытый бесплатный бессрочный безлимитный технический тариф назначается только Administrator/Owner после одноразового подтверждения, **без** `Order`/`Payment` и без нулевого invoice; результат `ProvisioningEngine → 3x-ui` подтверждается независимым read-back. Неоднозначный `in_flight/unknown` никогда автоматически не повторяется после сбоя/restart, доступна read-only проверка администратором. Finite plans и legacy payment snapshots сохраняются.
- **Совместимость и ограничения:** full Python CI с SQLite v1→v14, fake-3x-ui/manual entitlement, audience/RBAC, Stars snapshots и негативными тестами — PASS до release-prep. Новая schema требует предварительного контролируемого backup и read-back после отдельно разрешённого deployment; downgrade без совместимого восстановления SQLite не поддерживается. Legacy `EUR/USD` планы не конвертируются и не открывают новые продажи; #499 промокоды, #507 варианты срока и #336 внешний PSP не входят.
- **Controlled canary / release-prep only:** этот раздел — кандидат, **не подтверждение Published/Deployed/Accepted**. Предыдущий Published/операторский Deployed — `v5.0.0-rc.15`; #691 targeted UI smoke и #705 targeted schema/manual-3x-ui/Telegram smoke **PENDING** после отдельного разрешения Release/deployment. Полный v5 **NOT PASS**, G-11 PARTIAL/NO-GO, расширение pilot allowlist и public rollout **BLOCKED**.

## v5.0.0-rc.15 — Адресный Flow при действующем AmneziaWG и росте нод

- [PR #689](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/689) / #663: `✏️ Изменить Flow` допускает выбор конкретного VLESS TCP Reality inbound у многопротокольного клиента с WG/AmneziaWG **только** после read-only проверки ownership всех tunnel attachments, совпадения `tunnelAllowedIPs` и точного `Master panelVersion=3.10.2`. Неполные/неоднозначные данные, MTProto/reverse и другие/неизвестные версии остаются BLOCKED. Запрос scoped `inboundIds` через Master не включает WG/AWG private keys, адреса или peer поля и не выполняет прямых Node writes.
- [PR #689](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/689) / #663: UI выбора нод и inbound постраничный (8 элементов), bounded discovery до 64 нод / 256 inbound, параллелизм не выше 8, общий timeout 30s; при превышении лимитов или неудаче проверки — fail closed, без частичного списка. RBAC и одноразовый nonce сохраняются.
- Offline Python/CI, реальный upstream Go service + временная SQLite для v3.10.0 и v3.10.2: подтверждено, что v3.10.0 **небезопасен** для WG-scoped VLESS update, а v3.10.2 в проверенном сценарии сохраняет peer поля и соседние VLESS/XHTTP/Hysteria2/AWG inbound без утечки WG credentials в VLESS. Общий pinned 3x-ui API contract `v3.10.0`, SQLite schema v13, платежи и pilot allowlist не изменены.
- **Controlled canary / release-prep only:** rc.15 не является Published/Deployed до отдельного разрешения на merge release-prep и успешной штатной публикации; deployment проводится отдельно по immutable tag. До операторского targeted read-only A6 и разрешённого отдельного Flow POST **A6/N6/R3 BLOCKED, G-11 PARTIAL/NO-GO**, stable/public rollout запрещён. Никакие клиентские WG-поля в production не удалять и не очищать.

## v5.0.0-rc.14 — Групповая диагностика общих полей Flow

- [PR #686](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/686) / #663: read-only preflight `✏️ Изменить Flow` безопасно различает наличие непустых полей WireGuard/AmneziaWG (`CLIENT_RECORD_PROTOCOL_WG`), MTProto (`CLIENT_RECORD_PROTOCOL_MTPROTO`) либо обеих групп (`CLIENT_RECORD_PROTOCOL_MIXED`); значения, имена конкретных заполненных полей, API payload, UUID и credentials не выводятся. Неизвестная причина не трактуется как PASS.
- Все группы продолжают **fail closed** блокировку изменения Flow: общую Master client record не обнулять и не преобразовывать; существующие full-row/identity/membership, RBAC, одноразовый nonce и запрет прямых Node mutations сохраняются. Регрессионные тесты покрывают WG, MTProto, MIXED, пустые значения, неизвестные сообщения, отсутствие write/POST и утечек.
- **Controlled canary only:** immutable GitHub prerelease публикуется штатным workflow **после отдельно разрешённого merge release-prep PR и успешного CI**. Публикация **не означает production deployment или acceptance**; развёртывание выполняется отдельно по immutable tag с разрешения оператора. API surface, 3x-ui pinned v3.10.0, SQLite schema **v13**, платежи, pilot allowlist и migrations не меняются. После отдельно разрешённого deployment нужен только targeted **read-only** A6.1/A6.2 UI smoke с сообщением безопасной категории; A6/N6/R3 **BLOCKED/PENDING**, G-11 **PARTIAL / NO-GO**, Flow POST/A10 и stable/public rollout **не разрешены**.

## v5.0.0-rc.13 — Уточнение безопасной диагностики Flow

- [PR #683](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/683) / #663: общий отказ `CLIENT_RECORD` в `✏️ Изменить Flow` разделён на фиксированные безопасные коды `CLIENT_RECORD_MISSING`, `CLIENT_RECORD_NULL`, `CLIENT_RECORD_PROTOCOL`, `CLIENT_RECORD_REVERSE`; поля и их значения, raw Master API и секреты не выводятся.
- Не ослаблены условия full-row Master client record preflight; forbidden/unknown значения по-прежнему блокируют scoped Flow POST. Не меняются API surface, inbound membership, nonce, RBAC, Node mutations, платежи, pilot allowlist и SQLite schema **v13**; новых migrations нет.
- **Controlled canary only:** это release-prep candidate, не Published и не Deployed до отдельно разрешённого merge/publish/deploy. После deployment безопасно повторить только A6.1/A6.2 и прислать новый код; это **не** автоматическое исправление фактического Master client record и не разрешение на Flow POST/A10. A6.4–A6.9, N6/R3 остаются BLOCKED до успешного preflight, общий G-11 PARTIAL / NO-GO, stable/public rollout BLOCKED.

## v5.0.0-rc.12 — Безопасная проверка Reality Flow и возврат в параметры доступа

- [PR #678](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/678) / #659: независимая read-only проверка direct Node Panel теперь сопоставляет однозначный Reality Inbound по точному `tag` или допустимому alias `n<node_id>-` закреплённого 3x-ui v3.10.0; несовпадение/неоднозначность сохраняет `UNKNOWN`, не выдаёт неподтверждённый `MATCH`, не изменяет Node.
- [PR #678](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/678) / #663: fail-closed preflight редактора Flow вместо общей причины отказа показывает фиксированный безопасный код (например, `INBOUND_TAG`, `CLIENT_RECORD`, `UPSTREAM_TIMEOUT`); identity, full-row validation, inbound membership, RBAC, nonce и запрет опасных повторов сохранены. Реальная причина production A6 после выпуска должна быть подтверждена отдельно, preflight не обходится.
- [PR #680](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/680) / #679: `🔎 Проверить Flow` сохраняет точку входа: из `⚙️ Параметры доступа` кнопка «⬅» возвращает к параметрам, из карточки пользователя — к пользователю; «🔄 Повторить проверку» сохраняет исходный контекст, включая `UNKNOWN` и ошибки API. Старый callback и `users.view` поддерживаются.
- **Controlled canary only:** pinned 3x-ui `v3.10.0`, SQLite schema **v13**, без миграций и изменений Stars/refund, платежей, pilot allowlist или production конфигурации. Это только release-prep candidate: до отдельного merge, успешной публикации и разрешённого deployment версия **не** является Published или Deployed. После release/deploy нужны targeted read-only A2/A6, UI refresh/back #679 и повторный health; A7/A8/A10 остаются PENDING/BLOCKED до подтверждения preflight и отдельного разрешения на state-changing A10. Node Panel не аттестует работающий Xray; общий v5 G-11 **PARTIAL / NO-GO**, stable/public rollout **BLOCKED**.

## v5.0.0-rc.11 — Адресный Reality Flow и стабилизация административного интерфейса

- [PR #652](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/652) / #650: исправлено падение «📈 Мониторинг → 📊 Трафик» из-за неопределённой `role`; role-aware доступ и кнопки сохраняют RBAC.
- [PR #653](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/653) / #649: восстановлены восемь маршрутов «Назад»/«Отмена» в Admin UI, включая bulk actions, карточку пользователя, import SQLite metadata и историю восстановления конкретной резервной копии.
- [PR #655](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/655) / #648: при «Тариф + согласование» убран избыточный no-op `bulkAdjust`, когда Master уже показывает требуемый Reality Flow; предотвращается известный путь отправки пустого Flow на direct Node.
- [PR #661](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/661) / #659: read-only диагностика раздельно показывает Master EffectiveFlow и результат прямого Node Panel GET по точному `node_id`; отсутствие привязки/связи помечается `UNKNOWN`, не `MATCH`.
- [PR #667](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/667) / #663: Support+ адресно выбирает Node → Reality Inbound → Flow (`none`, `xtls-rprx-vision`, `xtls-rprx-vision-udp443`) с отдельным одноразовым подтверждением и scoped Master `inboundIds` update. Нет прямой Node mutation, небезопасного повтора или legacy `flowrun` `bulkAdjust`; Master/Node postcondition читаются отдельно.
- [PR #673](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/673) / #663: устранено ложное отклонение валидного `ClientRecord.reverse=""` и отсутствие `flow` (`omitempty`) в pinned 3x-ui v3.10.0; непустой reverse по-прежнему fail closed. Исправление уже слито в `main` (`2df0ff893d94fdae045077424c432346c1d434b4`), его post-merge evidence — PR #675. Regression tests PASS на fix branch; required CI релизного PR, публикация и Node/Xray acceptance являются отдельными проверками.
- **Controlled canary only:** pinned 3x-ui `v3.10.0`, SQLite schema **v13** без новых migrations, пилотный allowlist прежний; Stars/refund semantics и #433 не изменяются. Новый RC сам по себе не означает Deployed/Accepted. После отдельного разрешённого deployment обязательны targeted Node Reality Flow #648/#659/#663, навигация #649, мониторинг трафика #650 и базовый health; опасный production reproducer и live mutations не повторять без явного согласования. Общий G-11 остаётся **PARTIAL / NO-GO**, stable/public rollout BLOCKED.

## v5.0.0-rc.10 — Диагностика сроков и история Stars в карточке пользователя

- #628 / PR #641: в карточке пользователя отдельные read-only журналы Stars (XTR) и ручных платежей, owner-scoped detail, refund journal status и ограниченная пагинация. Не смешиваются валюты/ledger; чужие payment IDs недоступны через callbacks.

- #627 / PR #639: read-only диагностика подписки показывает подтверждённое совпадение сроков, недостаточность данных или расхождение; отсутствующий `expiryTime` 3x-ui не выдаётся за подтверждённую бессрочность.
- #433 **исключён из rc.10 решением оператора 2026-10-14**: добровольное 14-дневное eligibility/revocation и корректировка entitlement/3x-ui после Stars refund НЕ реализованы, Issue OPEN/DEFERRED, target TBD. Клиентские условия #434 и памятка #437 не активируются до юридической проверки #436. Existing refund accounting semantics rc.9 неизменны.
- **Controlled canary only:** schema SQLite **v13** без новых migrations, pinned 3x-ui API contract main **v3.10.0**. Никаких новых Star refund mutations, изменений provider provisioning или customer allowlist. Immutable Published/Deployed/Accepted — отдельные gates; после разрешённого deployment провести targeted read-only smoke #627/#628 и базовый health, G-11 остаётся PARTIAL / NO-GO. Stable/public rollout BLOCKED.

## v5.0.0-rc.9 — Portal callbacks fail-closed и Host Groups 3x-ui

- #342 / PR #420: существующие клиентские inline callbacks теперь проверяют effective `CLIENT_PORTAL_ENABLED` и persistent DB override через fail-closed gate, как `/start`; выключение портала не открывает обход через старые кнопки. Административный `/admin`, обработка уже полученного `successful_payment`, 3x-ui доступы и pilot allowlist не изменяются.
- #422 / PR #424: раздел `/admin → Инфраструктура → Хосты` разделяет локальные SQLite metadata и read-only Host Groups Master 3x-ui (`GET /panel/api/hosts/list`). Ноды связываются только по `nodeGuids` ↔ `NodeView.guid`, inbound — по Master metadata; unknown/unmapped/offline не маскируются как Master/healthy. Добавлены pagination, защита stale callbacks, fail-closed ошибки API; импорт локальных URL явно маркирован как SQLite write, live Hosts API не выполняет mutations.
- Контракт 3x-ui остаётся pinned к `v3.9.0` (55 endpoints); SQLite schema — **v13**, новых migrations, секретов и изменений production конфигурации нет.
- Это **controlled-canary prerelease**, не public launch. GitHub Release не выполняет production deployment автоматически. После отдельного operator-approved deployment обязательны targeted production smoke: #342 Portal OFF → старые callbacks denied → ON и доступность `/admin`; #422 — три read-only проверки локальных metadata, реальных Master Host Groups/inbound и GUID-привязок нод. Каждая серия фиксируется в Roadmap с PR/CI и Issue audit. До фактических результатов #342/#422 **PENDING**, общий v5 acceptance **NOT PASS**; повторять ранее пройденные или waived smoke не требуется.

## v5.0.0-rc.8 — Client Portal, Stars invoice UX и Owner recovery

- #320 / PR #417: после сохранённого `successful_payment` бот однократно удаляет старые Stars invoice-сообщения, привязанные к заказу и владельцу. Косметическая ошибка/timeout не меняет confirmed payment/entitlement и не приводит к повторной Telegram mutation; доставка уже оплаченного события остаётся рабочей.

- #345 / PR #416: Owner в карточке пользователя может после одноразового подтверждения очистить только in-memory customer rate-limit bucket выбранного Telegram ID в работающем процессе. Действие логируется, не затрагивает customer платежи/VPN/других пользователей и не устраняет ограничения Telegram-side flood/delivery; окно сброса отображается только при наличии актуального limiter state. Клиентский FSM не используется.

- #352 / PR #361: уведомления о новых сбоях фоновых заданий отличают новый `job_run_id` от повторного напоминания о той же старой ошибке; повторы не выдаются за новые инциденты.
- #353 / PR #362: Owner-only подтверждение исторического `bot.update: unknown` фиксирует read-only evidence и append-only acknowledgment (schema **v12**), не переписывая `job_runs.status` и не повторяя deployment.
- #354 / PR #363: исправлены `Назад`/`Обновить` при входе из Attention Center и отображение текущей роли в заголовке Admin UI.
- #355 / PR #364: экран администраторов показывает подтверждённый `@username` с ограниченным TTL-кэшем и безопасным fallback на Telegram ID.
- #357 / PR #366: добавлен отдельный [runbook Cloudflare WARP](docs/WARP_SETUP.md) для test/canary VPS; сам WARP не устанавливается ботом и не входит в обязательный production setup.


- #342 / PR #368: Owner-only persistent переключатели Client Portal и новых Stars оплат с двухшаговым CAS/audit; `.env` имеет безусловный приоритет, новые invoices/precheckout fail-closed, уже полученный successful_payment обрабатывается; UI показывает effective причины и pilot/rate-limit, валюта ручных платежей названа точнее.

- #343 / PR #367: нулевые лимиты нового trial сохраняются как `0` (3x-ui: без ограничений); пустые/некорректные значения больше не маскируются fallback, `/admin → Система → Настройки` показывает понятную семантику и границы. Изменения не касаются существующих клиентов.

- #356 / PR #365: `/admin → Система → 📚 Команды бота` показывает read-only реестр фактических slash-команд, отдельно активные клиентские, административную и legacy redirects; источник — типизированный каталог, новая fail-closed CI-проверка сопоставляет его с aiogram handlers. Ни публикации/деплоя, ни новой версии приложения в рамках этого change нет.

- SQLite schema **v13**: migration v12 — историческое Owner acknowledgment, migration v13 — одноразовая безопасная косметическая очистка Stars invoices. Обратное переключение на rc.7 после применения миграции не поддерживается без проверенного восстановления подходящего backup.
- Это prerelease только для controlled canary. Pilot allowlist, запрет public rollout и full v5 acceptance **NOT PASS** сохраняются; после публикации и отдельного controlled deployment обязателен targeted smoke новых функций.

Процесс сопровождения (без runtime-изменений): PR #370 закрепил реестр слитых изменений, отдельных acceptance-gates и четыре статуса Roadmap; PR #371 сделал заполненность канонического PR checklist обязательным CI gate. Никакая новая функциональность из `main` от этого не стала опубликованной или проверенной в production.

## v5.0.0-rc.7 — Надёжный Master Full Backup и WAL-safe API snapshot

- #348 / PR #350: Full Backup теперь блокирует создание ложного `backup.daily=success`, если обязательная Master `x-ui.db` отсутствует, недоступна или повреждена; частичный SQLite snapshot удаляется, `PRAGMA quick_check` обязателен.
- Новый Full Backup сначала пишется в приватный временный архив с правами `0600`, проходит deep validation, после чего публикуется атомарно; при tar/validation failure неполный архив не становится доступным для off-site/restore.
- #349 / PR #351: Master `x-ui.db` получается через authenticated `GET /panel/api/server/getDb` существующего panel-domain API token. В 3x-ui v3.9.0 этот endpoint использует SQLite Online Backup API и не зависит от ACL живых `x-ui.db{-wal,-shm}`; API-failure не разрешает небезопасный fallback на файловый mount.
- PR #347: заголовок нового Telegram Stars invoice показывает отображаемое имя бота вместо названия тарифа; описание плана, сумма, платежный payload и обработка событий не изменены.
- PR #346 и #358: зафиксированы scoped A/B, RBAC, rollback/backup findings и дальнейший backlog; прошлые PASS не считаются полным v5 production acceptance.
- SQLite schema остаётся **v11**, pinned 3x-ui OpenAPI contract — **v3.9.0**. Новых миграций, внешнего платежного шлюза или расширения pilot allowlist в этом RC нет.
- После публикации immutable prerelease и controlled deployment требуются read-only preflight, manual Full Backup с deep validation, зашифрованный off-site upload → download → decrypt → deep validation, DR preflight и следующий **реальный** scheduled `backup.daily` / `backup.offsite` cycle. До подтверждения этих шагов P0 backup и общий v5 acceptance остаются **NOT PASS**.

## v5.0.0-rc.6 — Stars accounting и payment idempotency

- V5-A-010 / #333: повторное `successful_payment` после Stars refund больше не может перевести terminal `commerce_payments.status=refunded` обратно в `confirmed`. Регрессия `оплата → однократный возврат → дубликат payment` сохраняет refund journal и не создаёт лишних entitlement/payment/event.
- #334: `/admin → Платежи` показывает отдельную read-only сводку `⭐ Telegram Stars` (`confirmed/refunded/pending/unknown/failed` и суммы в XTR) и `📒 Ручные платежи (учёт)` с прежней выручкой по fiat. Звёзды не конвертируются в рубли и не суммируются с внутренним журналом.
- SQLite schema остаётся **v11**, pinned 3x-ui contract — **v3.9.0**; никакого нового webhook provider/СБП или изменения runtime secrets в этом RC. Будущая внешняя PSP/СБП интеграция зарегистрирована как roadmap #336 (после v5.0 acceptance, отдельный Telegram platform compliance review).
- После immutable release/pilot deploy нужны targeted read-only Stars totals и payment/refund journal smoke. Live duplicate `successful_payment` на возвращённый платёж **не отправлять**; #333 закрывать только после review CI и контролируемого validation scope. Общий v5 production acceptance пока **NOT PASS**.

## v5.0.0-rc.5 — Telegram Stars refund callback stabilization
- V5-A-009 / #328: production targeted refund на `v5.0.0-rc.4` остановлен как High / release-blocking — `business_admin.stars_refund_run` падал с `NameError: run_stars_refund is not defined` после подтверждения оператором двухшагового возврата; helper не вызывался, Telegram refund request из этого обработчика не отправлялся.
- Добавлен отсутствующий явный import `run_stars_refund` из `stars_refund.py` в `business_admin.py`; regression contract проверяет runtime wiring admin callback. Existing one-shot Stars refund journal, RBAC, отсутствие blind retry при `unknown`, оплату/entitlement и 3x-ui provider access не меняли.
- После публикации immutable `v5.0.0-rc.5` требуется controlled production deploy, health/SQLite/3x-ui preflight, read-only проверка платежа и `stars_refund_operations` перед любой новой mutation; только после отдельного operator confirmation разрешён один targeted Stars refund и provider/journal read-back. До targeted PASS V5-A-009 issue #328 и V5-A-001 остаются открытыми.
- SQLite schema остаётся **v11**, pinned 3x-ui OpenAPI contract — `v3.9.0`; stable `v5.0.0`, снятие customer allowlist и общий production acceptance **не разрешены**.

## v5.0.0-rc.4 — Customer provider access state stabilization
- V5-A-008 на production rc.3: paid entitlement active/local expiry в будущем не гарантировали доступ — 3x-ui `enable=False` при customer UI `🟢 активна`; отдельный expiry drift возник после ручной проверки сроков. Полный acceptance остановлен; новые production mutations/автоматическое включение не выполнялись.
- Client Portal теперь отделяет local entitlement/period state от read-only provider `enable/expiryTime`: `⛔ отключён`, `⌛ истёк`, `🟡 активация`, `⚪ неизвестно` при provider unavailable либо expiry drift; диагностика не выдаёт успешный provider read за реальное право доступа.
- При несовпадении `users.expiry_time`, established entitlement expiry и provider expiry выводится предупреждение; remote `enable`, оплаченный срок, quota и journals автоматически не изменяются. Добавлены regression tests provider-neutral ownership/status и read-only contract; новый immutable RC и targeted production retest обязательны до возобновления payment/refund acceptance.

## v5.0.0-rc.3 — Client Portal quota-cycle stabilization
- Production acceptance `v5.0.0-rc.2` остановлен после V5-A-007: реальный Stars payment дошёл до `payment=confirmed`, `entitlement=active` и доступного subscription URL, но старые накопительные 3x-ui traffic counters не были сброшены, поэтому новый finite quota сразу считался исчерпанным.
- Paid entitlement теперь фиксирует target expiry до remote provisioning; активное продление использует `max(now, current_expiry) + duration`, поэтому оставшийся оплаченный срок не теряется и безопасный recovery не начисляет duration повторно.
- Для finite-traffic Plan новый quota cycle выполняет durable one-shot `bulkResetTraffic`: `in_flight/success/failed/unknown` хранится в entitlement, uncertain outcome не replay'ится автоматически, а локальный access expiry публикуется только после доказанного reset либо `not_required`.
- SQLite schema повышена до v11 migration `entitlement_quota_cycle_v5_0_0`; existing entitlement rows маркируются `legacy` и не получают автоматических remote mutations.
- Закрывается Low UI finding #314: home/profile используют одинаковые status emoji, динамические Stars plan buttons получают leading `💎`, `/subscription` использует канонический заголовок, duplicate `/paysupport` renderer удалён.
- Stars Orders/Admin observability из roadmap в этот stabilization scope не входит. После deployment `v5.0.0-rc.3` сначала выполняется targeted V5-A-007 quota/renewal/no-replay retest и regression V5-A-005/V5-A-006/#314; полный acceptance возобновляется только после PASS.
- Pinned 3x-ui OpenAPI contract остаётся `v3.9.0`; используемый 54-endpoint bot API surface не меняется.

## v5.0.0-rc.2 — Client Portal canary fixes
- Новый immutable release candidate после остановленного canary `v5.0.0-rc.1`: pilot allowlist сохраняется, публичный signup не открывается, а production acceptance продолжается только на новом baseline.
- Stars admin ledger больше не падает с `NameError`: `business_admin.py` явно импортирует `aiosqlite`; добавлен regression contract для `Платежи → Telegram Stars`.
- Исправлен acceptance finding: просроченный customer access больше не отображается как активный; diagnostics учитывает effective expiry, а runtime локально переводит due active/suspended entitlements в `expired` без remote mutation.
- После deployment `v5.0.0-rc.2` сначала повторяются V5-A-005 и V5-A-006; только после targeted PASS продолжается полный controlled production acceptance по `docs/V5_PRODUCTION_ACCEPTANCE.md`.
- SQLite schema остаётся v10; pinned 3x-ui OpenAPI contract обновлён до `v3.9.0` по immutable upstream tag/blob. Используемый bot API surface остаётся прежним: 54 endpoint, contract gate не выявил route/method/body/auth/response drift.

## v5.0.0-rc.1 — Client Portal controlled canary
- Первый immutable release candidate Client Portal для controlled production acceptance; pilot allowlist сохраняется, публичный signup не открывается.
- Client Portal включает provider-neutral customer boundary, профиль/подписку/трафик/устройства, Telegram Stars purchase/renewal с Terms acceptance, idempotent payment/order/entitlement journal и provisioning worker.
- Добавлены onboarding для iOS/Android/Windows/macOS/Linux, локальный private-chat QR subscription URL и read-only self-service diagnostics без provisioning/reconcile mutations.
- Stars production hardening включает строгую pre-checkout/owner/amount/currency validation, refund/support flow, отдельный payment kill-switch и обработку уже подтверждённого successful_payment даже при остановке новых платежей.
- Launch safety включает независимый Client Portal kill-switch, per-user rate limit, v5 launch audit regression gate, data-retention policy и production acceptance/canary runbook.
- Release/deploy tooling поддерживает immutable `vX.Y.Z-rc.N` GitHub prerelease; финальный `v5.0.0` остаётся заблокирован до PASS acceptance по `docs/V5_PRODUCTION_ACCEPTANCE.md`.
- Текущий SQLite schema level включает v10 Stars production hardening; pinned 3x-ui OpenAPI contract остаётся v3.8.5.




## v4.26.9 — Subscription browser compatibility hotfix
- Исправлена белая страница встроенной subscription SPA за compatibility proxy: статические JS/CSS assets сохраняют корректные MIME/cache headers, а runtime `window.X_UI_BASE_PATH` переписывается на `/compat/`, поэтому Vite lazy/runtime chunks больше не уходят на upstream subscription path вроде `/clichegamesub/assets/*`.
- Canonical nginx contract для `/compat/` дополнен `proxy_max_temp_file_size 0;`; application asset responses также выставляют `X-Accel-Buffering: no`. При уже настроенном `proxy_buffering off` это defensive hardening, а не замена корректному runtime base-path rewrite.
- Добавлены browser regression tests для HTML asset rewrite, runtime base path, case-insensitive `Content-Type`/`ETag`/`Cache-Control` passthrough и path-traversal boundary.
- В этот release также входит уже слитый v5 Client Portal foundation: commerce schema v6/v7, authenticated/idempotent payment webhook journal, payment-event restart reconciliation, entitlement provisioning worker и pilot `/start` с меню Профиль / Моя подписка / Купить или продлить / Трафик / Устройства / Помощь.
- Client Portal остаётся pilot-only за существующим allowlist/admin boundary; публичный signup не открыт, production payment provider/checkout ещё не подключён, а создание локального order само по себе не изменяет доступ. Legacy admin `payments` остаётся отдельным bookkeeping-контуром.
- Текущая bot SQLite schema version — **7**; migration v6/v7 additive, а downgrade на старый release без совместимой pre-migration DB не поддерживается. Pinned 3x-ui OpenAPI contract остаётся v3.8.5.

## v4.26.8 — A-011 non-root startup hotfix
- Исправлен production blocker `v4.26.7`: после перехода container runtime на UID/GID `10001:10001` restrictive host checkout modes могли сохраниться через Docker `COPY . .`, из-за чего Python не мог прочитать `/app/restore_bootstrap.py` и container уходил в restart loop.
- Application tree внутри image теперь после copy принудительно остаётся root-owned, но получает `u=rwX,go=rX`; runtime user может читать/обходить source tree, но не получает write-доступ, а read-only rootfs, `cap_drop: ALL` и `no-new-privileges` сохраняются.
- CI least-privilege smoke теперь перед build выставляет ключевым source files mode `0600` и проверяет их читаемость из container под UID/GID `10001:10001`; fix также прошёл Supply-chain audit.
- Последующий production acceptance A-011/#244 и A-012/#245 завершён PASS на `v4.26.8`: non-root runtime/backup/DR/client smoke, nginx/resource bounds, controlled load и финальный Health/DB/3x-ui status подтверждены; оба findings закрыты.
- SQLite schema остаётся v5, pinned 3x-ui OpenAPI contract остаётся v3.8.5; новых migrations и 3x-ui routes нет.

## v4.26.7 — Final v4 audit hardening: container, proxy и supply chain
- A-011/#244: bot container переведён на dedicated UID/GID `10001:10001`, read-only root filesystem, `no-new-privileges`, `cap_drop: ALL`, bounded tmpfs `/tmp` и единственный persistent writable tree `/app/data`; permission helper/ACL сохраняют read-only доступ к backup/config/log mounts и устойчивость к новым WAL/SHM/rotated log files.
- A-012/#245: Subscription Compatibility Proxy получил hard resource bounds — максимум 32 concurrent upstream fetch, ожидание slot не более 1 секунды с fail-closed HTTP 503 + `Retry-After: 1`, upstream response не более 8 MiB с chunk-bounded read; canonical Nginx policy ограничивает одного клиента `limit_conn=4`, `5r/s`, burst 10.
- Release/repository hardening после v4.26.6 включает hashed `requirements.lock`, digest-pinned Python base image, full-SHA GitHub Actions, pinned Trivy supply-chain audit/SBOM, history/retained-Actions secret audits, Apache-2.0 project license и private vulnerability reporting contract; A-007 зафиксирован отдельно как owner-accepted residual risk.
- Для production rollout требуется актуальный `docs/ADMIN_SETUP.md`: пакет `acl`, `scripts/prepare-bot-container-permissions.sh`, затем deployment только опубликованного tag и targeted smoke A-011/A-012. Findings не считаются закрытыми до production acceptance.
- SQLite schema остаётся v5, pinned 3x-ui OpenAPI contract остаётся v3.8.5; новых migrations и новых 3x-ui routes нет.

## v4.26.6 — Final v4 audit remediation: admin boundary, redirects и file modes
- A-004/#237: Admin Control Plane теперь fail-closed работает только в private Telegram chat; общий middleware блокирует /admin, admin callbacks и admin FSM input вне личного чата до rendering/business logic, при этом client-facing router остаётся отдельным контуром.
- A-005/#238: subscription upstream redirects обрабатываются вручную; automatic redirects отключены, HWID/device и auth-like headers удаляются при первом cross-origin hop и не восстанавливаются дальше по chain, HTTPS downgrade и malformed redirect target отклоняются, число redirect hops ограничено.
- A-006/#239: backup/runtime directories и sensitive local artifacts получают явные owner-only modes `0700/0600` независимо от host umask; existing backup/log artifacts ужимаются, Full Backup, bot/node snapshots, bot SQLite и local bot logs создаются с private permissions.
- SECURITY/UI contracts и regression coverage обновлены; новый security suite проверяет private-chat boundary, same-origin/cross-origin/TLS-downgrade redirect semantics и file modes под permissive umask.
- SQLite schema остаётся v5, pinned 3x-ui OpenAPI contract остаётся v3.8.5. После публикации обязательны targeted production acceptance A-004/A-005/A-006 и повторный базовый health/status-check.

## v4.26.5 — Final v4 audit remediation: backup, logs и mutation certainty
- A-001/#234: secret-bearing Full Backup/DB/node/DR artifacts больше не передаются через Telegram; recovery transport остаётся только host-side/off-site, без ослабления encrypted off-site/DR flow.
- A-002/#235: встроенный aiohttp access log для secret-bearing `/compat/{sub_id}` отключён, а canonical Nginx `/compat/` route не пишет access log; regression coverage проверяет raw-log boundary.
- A-003/#236: все инвентаризированные state-changing 3x-ui calls используют one-shot/no-redirect mutation boundary с explicit uncertain outcome и без автоматического replay.
- Для destructive и deterministic field mutations, provisioning, bulk, user/node/inbound/create paths добавлен fail-closed read-back: uncertain success признаётся только при доказанном post-condition; иначе состояние остаётся `unknown` с `mutation_not_retried=true`.
- Traffic reset намеренно не объявляется успешным после lost response по нестабильным live counters; локальная SQLite state меняется только после обычного success либо доказанного remote post-condition там, где состояния связаны.
- Patch остаётся в рамках final v4 feature freeze; SQLite schema и pinned 3x-ui OpenAPI v3.8.5 не меняются. После публикации обязательны targeted production acceptance A-001/A-002/A-003 и повторный базовый health/status-check. Admin Setup: изменений не требуется.

## v4.26.4 — Permission-aware admin navigation
- Исправлен production finding #226: admin keyboards теперь могут фильтровать callback buttons по effective role через существующий RBAC callback catalog; неизвестные admin callbacks скрываются fail-closed.
- Role-aware rendering подключён к смешанным экранам `Задания`, `Резервные копии`, `Оповещения`, `Операции с нодами`, а также к core admin/system navigation.
- `read_only`/`support` больше не видят admin/owner actions, `admin` не видит owner-only actions; backend `authorize_callback` остаётся обязательной второй границей.
- Attention Center показывает domain deep-links только для реально присутствующих problem groups; calm/empty state сохраняет только `🔄 Обновить` и `⬅ Обзор`.
- Canonical parent semantics не меняются: переход из Attention Center открывает обычный destination screen, который возвращается в свой канонический раздел.
- Добавлен regression coverage role matrix, unknown-callback fail-closed filtering, context-aware Attention links и wiring затронутых destination screens.

## v4.26.3 — Attention Center drill-down
- Добавлен отдельный read-only экран `⚠️ Требует внимания` из `/admin → Обзор` с grouped detail по инфраструктуре, заданиям, оповещениям, резервным копиям и Fleet/Node Drain problem states.
- Detail использует те же current-state источники, что summary `v4.26.2`: active alerts, latest problematic job per name, offline/unknown infrastructure и latest terminal rollout/drain journals; resolved job исчезает после refresh, а item count согласован с summary contract.
- Каждый item содержит bounded operator context и stable technical identity без job details, alert raw values, credentials, subscription URL/`sub_id` или персональных списков пользователей; на группу показывается не более 5 items + `… ещё N`.
- Добавлены canonical read-only deep-links в `Состояние системы`, `Задания`, `Оповещения`, `Резервные копии` и `Операции с нодами`, а также `🔄 Обновить` и `⬅ Обзор`.
- Новый callback `admin:attention` использует существующий `dashboard.view` / Read-only+ permission; новых privilege IDs, SQLite schema, auto-remediation и remote mutations нет.
- Добавлен regression coverage count/detail parity, resolved/stale semantics, bounded rendering, secret exclusion, canonical navigation и no-mutation handler contract.

## v4.26.2 — Dashboard Attention summary
- В `/admin → Обзор` добавлен compact read-only блок `⚠️ Требует внимания` с общим count и bounded breakdown существующих проблемных состояний.
- Summary агрегирует active alerts, latest problematic background jobs, текущие offline/unknown direct-node states и latest terminal Fleet/Node Drain states; старый failed job не остаётся проблемой после более нового успешного run того же job name.
- `failed`, `unknown`, `interrupted`, degraded/offline и partial Drain отображаются раздельно; при отсутствии проблем показывается `✅ Требует внимания: нет`.
- Fleet/Node Drain журналы читаются локально и не запускают health probes или remote mutations; `Обзор` сохраняет Read-only+ boundary, новых privilege IDs, SQLite schema и auto-remediation нет.
- В summary не выводятся job details, user lists, credentials, subscription URL/`sub_id` или raw upstream payloads. Отдельный drill-down и deep-links остаются scope `v4.26.3`.
- Добавлен regression coverage deterministic/latest-state aggregation, bounded category order и no-mutation wiring. Admin Setup: изменений не требуется.

## v4.26.1 — Node Drain Cancel navigation
- Исправлена навигация `✖ Отмена` на confirmation screen Node Drain: после terminal `review → cancelled` оператор возвращается в read-only preflight той же stable direct node вместо корня `Операции с нодами`.
- Cancel сохраняет no-mutation contract: maintenance, attach/detach, Xray/service и другие remote mutations не выполняются; отменённый plan остаётся terminal `cancelled`.
- Stale `run` для cancelled plan по-прежнему блокируется fail-closed до первой remote mutation; RBAC callback catalog и Administrator+ boundary не меняются.
- Добавлен regression contract на canonical parent, no-mutation Cancel и stale-plan rejection. SQLite schema остаётся v5, pinned 3x-ui OpenAPI contract остаётся v3.8.5.
- Patch закрывает production finding #211 после публикации, deployment и targeted verification `preflight → prepare → ✖ Отмена`; полный Node Drain mutation smoke по-прежнему выполняется только на безопасной test node/user cohort.


## v4.26.0 — Node Drain
- Реализован отдельный graceful Node Drain для direct nodes без изменения семантики maintenance и без автоматического Stop Xray/service.
- Read-only preflight по stable `node_id` определяет управляемые Inbounds target-ноды, затронутых локальных пользователей, policy alternatives, blockers и remaining work; transitive/неоднозначная node identity блокируется fail-closed.
- Эвакуация использует существующий `ProvisioningEngine` как источник policy и соблюдает attach-before-detach: target Inbounds detach'ятся только после read-back подтверждения альтернативного Inbound; disabled target Inbounds также учитываются как оставшиеся назначения.
- Добавлен last-working-Inbound guard; пользователь без подтверждённой policy alternative остаётся blocker и не мутируется. Один Drain ограничен 500 затронутыми пользователями и выполняется последовательно.
- Maintenance enable/disable и client attach/detach переведены на существующую no-retry mutation boundary `XUIMutationError`; uncertain outcome проверяется read-only состоянием и не приводит к автоматическому повтору mutation. Target Inbound IDs фиксируются на preflight, поэтому post-check не зависит от того, продолжает ли disabled node публиковать свои Inbounds в live options.
- Fleet UI получил `🚧 Вывести из трафика`: просмотр/preflight доступен Read-only+, prepare/confirm/run — Administrator+; сначала target node переводится в maintenance, затем выполняется controlled evacuation. Fleet Health и карточка direct-ноды различают `maintenance`, `draining`, `drained` и проблемные terminal states.
- Добавлен parent job `fleet.drain`, audit и private persistent journal `fleet/drain-<id>.json` с mode 0600; journal хранит только stable IDs и техническое состояние без email, subscription URL, `sub_id` или credentials.
- Startup recovery переводит незавершённый `draining` в `interrupted/unknown` без mutation replay. После `partial/unknown/interrupted` продолжение требует нового preflight и нового plan; возврат ноды в работу выполняется через выход из maintenance + обычный policy reconcile без reverse replay. Active Xray sessions специально не обрываются; Stop Xray/service остаются отдельными Owner-only operations.
- Добавлены regression tests safety/RBAC/recovery/bounded-state contract и обновлён Fleet Operations runbook. `APP_VERSION` поднят до `4.26.0` отдельным release-prep; SQLite schema остаётся v5, используемый 3x-ui route surface не меняется, production smoke/acceptance ещё не выполнены.

## v4.25.8 — navigation and Owner self-role safety
- В Clone Inbound кнопка `✖ Отмена` на экране выбора target server теперь возвращает в карточку исходного Inbound; shared target keyboard получает явный parent, а Deploy Template сохраняет собственный parent.
- Self-demotion DB-backed Owner ниже `Owner` больше не выполняется одним нажатием: добавлен отдельный confirmation screen с предупреждением о потере Owner-only доступа.
- Self-demotion mutation выполняется только через Owner-only callback с актуальным FSM state и nonce; direct/stale confirmation блокируется, Cancel очищает confirmation и возвращает в карточку администратора.
- Изменение ролей других DB-администраторов и immutable break-glass Owner из `ADMIN_TELEGRAM_IDS` сохраняют прежнюю семантику; role model и privilege levels не меняются.
- Добавлены regression tests для navigation parent, confirmation/cancel/stale-run/single-mutation/audit, RBAC catalog и lifecycle закрытия проверенных bug issues.
- SQLite schema v5, pinned 3x-ui OpenAPI contract v3.8.5, provisioning, subscription/HWID, Host Control и clone disabled/clientless semantics не меняются.

## v4.25.7 — Inbound input validation
- Исправлен `UnboundLocalError` при неверном вводе порта в clone/deploy Inbound и при неверном имени шаблона: FSM identifiers читаются до validation branch после успешного authorization guard.
- Ошибочный ввод сохраняет исходный FSM/Cancel context и не выполняет remote/database mutation; после исправления можно повторить ввод или отменить действие штатной кнопкой.
- Добавлены исполняемые async regression tests для invalid/boundary input, occupied port, duplicate template name, retry, authorization guard и сохранения disabled/clientless Inbound payload.
- Callback identifiers, RBAC, SQLite schema v5, pinned 3x-ui OpenAPI contract v3.8.5, HWID/subscription proxy и mutation retry semantics не меняются.

## v4.25.6 — revert Streisand subscription workarounds
- Удалены временные `plain=1` workarounds из `v4.25.4–v4.25.5`; runtime subscription proxy возвращён к контракту `v4.25.3`.
- Production diagnosis подтвердил root cause: Streisand raw subscription request не передаёт совместимый `X-HWID`, поэтому при активном HWID limit upstream 3x-ui отвечает `hwid_not_supported`.
- Compat proxy по-прежнему не генерирует synthetic/fallback HWID и не обходит per-device enforcement.
- `v4.25.4` и `v4.25.5` остаются в истории релизов как диагностические попытки и не удаляются.

## v4.25.5 — Streisand plain mode precedence
- `?plain=1` теперь принудительно обходит HTML branch даже если клиент присылает `Accept: text/html`.
- Это закрывает Safari/WebView-like Streisand request path, который ранее получал HTML page вместо raw links.
- Default subscription URL без `plain` не меняется.
- HWID enforcement/diagnostics и client-specific transforms остаются без изменений.

## v4.25.4 — Streisand plain subscription compatibility
- Добавлен opt-in `?plain=1` для raw subscription response: Base64-wrapped upstream body декодируется в newline-separated links.
- `plain` является локальным параметром compat proxy и не пересылается upstream в 3x-ui.
- Default `/compat/{sub_id}` без `plain` сохраняет прежний encoding и client-specific behavior, включая Shadowrocket, V2Box, V2RayTun, Happ и INCY.
- HWID forwarding/enforcement и диагностические response headers не меняются.

## v4.25.3 — INCY Desktop UA compatibility
- Исправлена детекция реального INCY macOS Desktop User-Agent вида `INCY/<version>/mac os x Dalvik/<runtime>`; AWG filtering теперь включается и для этого подтверждённого Desktop UA.
- Парсер остаётся fail-closed для неизвестных INCY platform tokens и не применяет Desktop filtering к неоднозначным User-Agent.
- Сохранены принятые в `v4.25.2` Shadowrocket/HWID diagnostics и strict per-device enforcement.
- Явная инструкция Shadowrocket `Send HWID` добавлена в README/ADMIN_SETUP.

## v4.25.2 — Subscription client compatibility
- INCY Desktop определяется только по documented `INCY/<version>/<platform>` UA для `Windows/Linux/macOS`; неподдерживаемые AmneziaWG entries отфильтровываются только для этих Desktop requests, а INCY mobile сохраняет существующий `vpn:// → amneziawg://` flow.
- HWID-specific upstream `404` больше не маскируется generic `502`: compat proxy сохраняет allowlisted `X-Hwid-Active`, `X-Hwid-Not-Supported`, `X-Hwid-Limit`, `X-Hwid-Max-Devices-Reached` и возвращает диагностически различимый HWID rejection.
- Generic upstream 404/5xx без HWID diagnostic headers остаются fail-closed gateway errors.
- Compat proxy не генерирует synthetic/fallback HWID, не ослабляет per-user limit и не логирует HWID/subscription secrets.
- Документирован Shadowrocket `Send HWID`; production finding подтвердил full-slot scenario как причину отказа и восстановление subscription после увеличения свободных HWID slots.

## v4.25.1 — User Management stabilization / HWID completion
- Исправлены production-acceptance navigation defects: `Показать URL` возвращает в `🔗 Подписка`, user-scoped `💳 Платежи` больше не уводят в глобальный payment ledger, shortcut `⏳ Продлить` удалён из главной карточки.
- Create-user корректно трактует production 3x-ui response `Obtain (record not found)` как отсутствие клиента, сохраняя fail-closed обработку остальных API errors.
- Subscription compatibility proxy передаёт upstream reviewed `X-HWID` / device metadata headers для normal VPN-client requests; значения этих headers не логируются.
- Новые 3x-ui clients получают `limitHwid=5` по умолчанию. Existing clients массово не меняются; per-user HWID limit доступен Support+ в `⚙️ Параметры доступа`, Read-only видит текущее значение.
- Plan apply и reconcile не управляют HWID limit; существующий `update_client()` сохраняет индивидуальный `limitHwid`, если операция явно его не меняет.
- `📱 Подключения` показывает текущий HWID limit рядом с количеством зарегистрированных устройств.
- `Система → Администраторы` разделяет статус и роль: `🟢/⛔` обозначают enable state, а `👑/🛡/🧑‍💻/👁` — фиксированную RBAC роль.

## v4.25.0 — User Management
- Начат рефакторинг `/admin → Пользователи`: список получил bounded pagination и поиск по Telegram ID, техническому email и display name при сохранении `telegram_id` как callback identity.
- Mutation shortcuts списка теперь role-aware: Read-only не получает массовые действия/глобальное согласование, while handler authorization остаётся обязательной.
- Legacy attach-all действия `Синхронизировать Inbounds`, `Синхронизировать всех` и bulk sync удалены из новых клавиатур; сохранённые старые callbacks выполняют только non-mutating redirect в policy-based `Согласование`.
- Bulk access action переведён на `ProvisioningEngine.provision_many(..., strict=False)`; direct attach всех globally allowed Inbounds больше не является каноническим mass workflow.
- Audit bulk operations больше не перечисляет email выбранных пользователей; SQLite schema, 3x-ui/OpenAPI contract и subscription identity на этом foundation-срезе не меняются.
- Карточка пользователя переведена на устойчивые parent sections `Тариф / Срок / Трафик / Доступ / Подписка / Профиль / Ещё действия`; summary routes доступны Read-only, а mutation controls отображаются только для соответствующей роли.
- `🌐 Доступ` объединяет Server Group, policy-based reconcile, manual Inbounds и access parameters; legacy `adminuser:*` продолжает открывать ту же каноническую role-aware карточку.
- Добавлен `📱 Подключения`: online/last-online/IP limit summary, отдельные `📱 Устройства` по HWID и `🌐 IP-адреса` без подмены session/IP данными device identity.
- Pinned 3x-ui API surface расширен тремя reviewed endpoints текущей schema `v3.8.5`: `POST /clients/ips/{email}`, `POST /clients/hwids/{email}`, `DELETE /clients/hwids/{email}/{id}`; manifest теперь покрывает 54 используемых endpoint.
- Удаление одного HWID device выполняется только после отдельного confirmation; DELETE использует no-retry mutation semantics, а uncertain outcome отображается как неизвестный и проверяется read-only обновлением списка.
- Карточка пользователя получила read-only раздел `💳 Платежи`: scoped ledger по `payments.telegram_id`, суммы оплаченных группируются по валюте, detail callback проверяет принадлежность платежа текущему пользователю, write-actions остаются только в каноническом разделе `Платежи`.
- Добавлен `🧾 Активность`: user-scoped presentation существующего `audit_log` по технической identity (`email`/`telegram_id`) с MSK timestamps, pagination и bounded summaries; subscription/device secret-like details не реконструируются в timeline.
- Добавлен Support-level flow `➕ Создать пользователя`: Telegram ID → технический email → display name → тариф/compatibility → preview → подтверждение. Existing 3x-ui identity по `tgId` не дублируется и восстанавливается только отдельным explicit recovery action.
- `XUIClient.create_client()` переведён на no-retry mutation boundary: timeout/network/5xx дают uncertain outcome, POST не повторяется, а локальная запись создаётся только после success или read-only доказательства exact `email + subId`; audit не хранит subscription credential.
- `🔗 Подписка` дополнена `🌐 Открыть ссылку`, `🔗 Показать URL` и локальным `🔳 QR-код`; QR строится внутри bot process и не отправляет subscription URL внешнему сервису.
- `⚙️ Параметры доступа` получил Support-level `🔄 Синхронизировать VLESS Flow`: операция меняет только Flow через существующий bulk-adjust primitive и не выполняет attach/detach Inbounds.
- Enable/Disable переведены с one-click mutations на отдельные confirmation callbacks; stale `admindisable:*` / `adminenable:*` теперь только открывают ask-screen, а mutation выполняется новым run callback.
- Bulk User Management завершён по roadmap: добавлены отдельные Plan/Server Group assignment без implicit provisioning, custom expiry/traffic bounded FSM input с preview, а `+30`, enable/disable/reset/safe reconcile требуют count-based confirmation перед mutation.
- Bulk result/audit summary хранит только counts и outcome, без списка email; custom per-user updates продолжают обработку остальных пользователей при локальной ошибке одного target.
- Финализирован detail/navigation contract User Management: экран тарифа показывает price/period/plan-vs-current параметры, subscription card — masked ID и фактический status, пустой `VLESS Flow` явно отображается как `не настроен`; Plan/expiry/traffic/IP/profile/subscription actions возвращаются в свои canonical detail screens и очищают FSM при Cancel/Back.
- Delete confirmation теперь явно показывает display/machine identity и необратимость; callback-size regression закрепляет Telegram 64-byte boundary для динамических v4.25 routes.

## v4.24.1 — Hotfix web diagnostics и IPv6
- WHOIS/RDAP absolute timestamps в Telegram теперь нормализуются в `DD.MM.YYYY HH:MM MSK`; machine/RDAP instants остаются UTC, а возраст домена рассчитывается как раньше.
- Compact Cheburcheck card снова показывает полезную bounded static detail: resolved IP для domain target, Reverse DNS, blocked subnets и optional `rkn_domain` / `subnet_size`; IP/PTR/subnet lists ограничены 5 значениями + `… ещё N`, raw JSON/SSE/probe payload не выводится.
- Website monitoring корректно распознаёт public IPv6 literals до IDNA/domain validation, сохраняет bracketed canonical URL и по-прежнему fail-closed блокирует loopback/link-local/private/non-global IPv6.
- Safe outbound timeouts/body/redirect/DNS-rebinding policy, SQLite schema, RBAC/navigation, pinned Cheburcheck revision и 3x-ui/OpenAPI contract не меняются.
- `PAGESPEED_API_KEY` остаётся пустым и optional по умолчанию; `docs/ADMIN_SETUP.md` содержит воспроизводимый future setup/disable runbook.

## v4.24.0 — Мониторинг сайтов и web diagnostics
- В `/admin → Мониторинг` добавлен нативный раздел `🌐 Мониторинг сайтов`: persistent targets, many-to-many admin watchers, add/list/card/manual-check, incident history, per-watcher alerts, pause/resume, unsubscribe и Administrator-only global target management.
- Background monitoring использует deterministic state machine `unknown/up → suspect → down → up`: первый candidate failure подтверждается повторной проверкой через 2 s, down-target проверяется каждые 3 минуты, normal target — каждые 10 минут. Incident state и notification journal сохраняются в SQLite, поэтому restart не replay'ит first/recovery alert.
- Site alerts различают first/repeat/recovery и отправляются только active watchers с включёнными notifications. Repeat cadence сохраняет reviewed PackBot defaults: 30 минут, затем 320 минут; один target не получает параллельные checks благодаря per-target lock.
- Добавлен единый SSRF-safe outbound HTTP boundary: только public HTTP/HTTPS на standard ports 80/443, IDNA/syntax validation, fail-closed private/loopback/link-local/CGNAT/reserved/metadata blocking, validation DNS answers в resolver connect path, `trust_env=False`, manual validation каждого redirect, hard limits 5 redirects / 3-7-10 s connect-read-total / 1 MiB ordinary body.
- Добавлена `🔎 Разовая диагностика` и contextual `🩺 Диагностика` из карточки monitored site: RDAP/WHOIS + возраст домена, DNS A/AAAA/CNAME/MX/NS/TXT, HTTP summary, redirect trace, CMS detection, robots/meta/X-Robots indexability, optional Google PageSpeed, bounded Sitemap, local URL-list normalization и QR generation.
- Sitemap ограничен 2 MiB на документ, максимум 10 документов и 5000 URL; raw WHOIS/RDAP/PageSpeed payload не выводится и не сохраняется. QR и URL-list работают local-only.
- Optional PageSpeed использует только локальный `PAGESPEED_API_KEY`; отсутствие key отображается как `не настроен` и не влияет на остальные diagnostics.
- SQLite schema повышена до v5: `v4 website_monitoring_v4_24_0` добавляет targets/watchers/incidents/idempotent notification journal, `v5 website_watcher_lifecycle_v4_24_0` добавляет watcher-scoped `monitoring_enabled`. Обе migration additive и `requires_backup=False`; downgrade на runtime, знающий только schema v3/v4, без совместимого pre-migration backup не поддерживается.
- PackBot `vladpak1/packbot@3c4a5bb29626f8b3e28056bd52cd94fdce9f3c1a` использован как reviewed behavior/reference implementation; production runtime остаётся Python/aiogram/SQLite-native, PHP/MySQL/webhook stack не разворачивается. MIT attribution сохранён в `THIRD_PARTY_NOTICES.md`.
- Screenshot/headless-browser diagnostics и перенос multilingual PackBot UI намеренно не входят в обязательный scope `v4.24.0`; Client Portal `/start` также не расширяется.
- Добавлены `dnspython` и `qrcode[pil]`; новых обязательных host-side services/ports нет. 3x-ui/OpenAPI, provisioning, VPN mutation semantics, Host Control Agent, Deploy Agent и Cheburcheck runtime не меняются.
- Release устанавливается обычным Safe Bot Self-Update. Production acceptance должен отдельно подтвердить add/up/manual diagnostics, controlled down/repeat/recovery, restart idempotency, SSRF rejects, optional PageSpeed-off state и финальный `deploy-release.sh --status`.

## v4.23.3 — Hotfix compact result Cheburcheck
- Production smoke `v4.23.2` подтвердил compact layout и context-preserving navigation, но выявил неполный result enrichment: пустой CDN выглядел неизвестным, domain/IP не показывал ASN coverage, а отсутствие regional Probe reporters маскировалось нейтральным `—`.
- Пустой upstream `cdn_providers` теперь отображается как фактический отрицательный результат `🟢 не найден`; optional значения, которых upstream действительно не предоставил, по-прежнему не выдумываются.
- Для domain/public-IP с валидным `geo.asn` bot выполняет один дополнительный bounded read-only `GET /api/v1/check?target=AS...` и использует только counts `blocked_prefixes / prefixes`; ASN enrichment и regional probe выполняются как независимые follow-up checks, а их failure не меняет уже полученный static verdict.
- Regional SSE сохраняет `started.online_probes`: UI различает реальные агрегированные ответы, `⚪ нет активных региональных сканеров`, online scanners без ответов и `🟡 региональная проверка недоступна`; subnet/ASN regional probe остаётся неприменимым.
- Исправлен edge case классификации target: обычные домены, начинающиеся с букв `as...`, больше не ошибочно считаются ASN.
- Existing network safety сохраняется: static response hard limit 1 MiB, regional SSE 256 KiB, connect/read/total timeouts и запрет redirects не ослаблены; raw upstream/probe payload не выводится.
- Minimal self-hosted Cheburcheck topology `website + PostgreSQL` остаётся поддерживаемой для static diagnostics. Hotfix не создаёт MQTT/Probe fleet и не эмулирует региональные результаты; реальные региональные ответы требуют отдельной инфраструктуры с зарегистрированными Probe reporters.
- SQLite schema остаётся v3; 3x-ui/OpenAPI, provisioning, VPN mutation semantics, Host Control Agent, Deploy Agent и pinned Cheburcheck revision не меняются. `v4.23.3` устанавливается обычным Safe Bot Self-Update и не требует rebuild Cheburcheck runtime или host-side Agent/helper.

## v4.23.2 — Компактный результат Cheburcheck
- Экран `Мониторинг → Проверка блокировок` переведён на компактную operator-facing карточку: цель, итоговый verdict, сеть, единый блок `📋 Списки`, агрегированная строка `🌍 Регионы` и явный `Источник: Cheburcheck.`.
- Static check теперь использует уже доступные в pinned upstream поля `cdn_providers`, `asn_info` и `whitelist`; raw IP/reverse-DNS/probe payload в основной Telegram-карточке не выводится.
- Для domain/public-IP добавлен read-only regional summary через reviewed upstream `GET /api/v1/probe/{id}`: ответы сворачиваются в `🟢 / 🔴 / 🟡`, а subnet/ASN не запускают probe, потому что upstream endpoint их не принимает.
- Regional SSE bounded отдельно: hard limit 256 KiB, connect/read/total timeouts 3/10/12 s, redirects запрещены; при недоступности probe успешный static check сохраняется, а строка регионов показывает `—`.
- Cheburcheck navigation сохраняет исходный parent context: Monitoring/discovered/manual flow не прыгает в карточки серверов, shortcut из Master возвращается в Master, shortcut из direct Node — в ту же Node; result/error/retry/`Проверить ещё`/Cancel сохраняют тот же context.
- Regression coverage закрепляет extended API contract, probe verdict buckets, compact result wording, новые read-only callbacks и отсутствие cross-context navigation.
- SQLite schema остаётся v3; 3x-ui/OpenAPI, provisioning, VPN mutation semantics, Host Control Agent, Deploy Agent и pinned Cheburcheck revision не меняются. `v4.23.2` устанавливается обычным Safe Bot Self-Update и не требует rebuild Cheburcheck runtime или host-side Agent/helper.

## v4.23.1 — Cheburcheck hotfix и navigation regression
- Production smoke `v4.23.0` подтвердил self-hosted Cheburcheck для domain/public IP и shortcuts Master/direct Node, но штатный ASN response размером около 382 KiB превысил исходный hard limit 256 KiB.
- `CheburcheckClient` увеличивает bounded response-body limit до 1 MiB. Concurrency остаётся 4, connect/read/total timeouts — 3/7/10 s, redirects по-прежнему запрещены; произвольные URL/private targets не разрешаются.
- Добавлен reproducible VPS runbook `docs/CHEBURCHECK_DEPLOY.md`: pinned upstream revision, PostgreSQL 18.6, причина требования `uuidv7()`, internal-only Docker networks без host ports, local secrets, health/reachability checks, bot `.env`, rollback и update policy.
- Документация явно фиксирует, что PostgreSQL/cache Cheburcheck являются отдельной operational boundary и не входят в Full Backup Telegram-бота.
- Проведён navigation audit Admin Control Plane; канонические parent/back transitions сохранены, а regression coverage расширяется для repo-wide проверки стабильных Back labels и privilege-backed static admin callbacks.
- Roadmap обновлён по факту: `v4.23.0` опубликован/развернут, acceptance частично пройден, полное закрытие Cheburcheck переносится на `v4.23.1`.
- SQLite schema остаётся v3; 3x-ui/OpenAPI contract, provisioning, VPN mutation semantics, Host Control Agent, Deploy Agent и Cheburcheck upstream revision не меняются.
- Для уже работающего pinned self-hosted Cheburcheck runtime rebuild не требуется: `v4.23.1` обновляет только bot release, после чего повторяется ASN/validation/unavailable/base-health smoke.

## v4.23.0 — Проверка блокировок Cheburcheck
- Добавлен read-only diagnostics flow `Мониторинг → Проверка блокировок` для доменов, публичных IPv4/IPv6, подсетей и ASN через optional Cheburcheck service.
- Стартовый экран автоматически предлагает публичные цели из уже известных Master/direct Nodes/enabled Hosts; карточки Master и direct node получили shortcut `🔎 Проверить блокировку`. Из сохранённых URL передаётся только hostname/IP, без scheme/port/path/query/credentials, а дубликаты и local/private targets отбрасываются.
- Интеграция использует фиксированный `/api/v1/check?target=...` contract и не проксирует произвольные HTTP URL; input нормализуется и ограничивается поддерживаемыми target types.
- `CheburcheckClient` использует bounded concurrency, connect/read/total timeouts, запрет redirect-following и лимит response body 256 KiB; rate limit, validation/rejection, not-found, unavailable и invalid response отображаются отдельно.
- Cheburcheck optional: пустой `CHEBURCHECK_URL` не влияет на startup, 3x-ui или provisioning; internal endpoint не показывается в Telegram UI.
- Reviewed upstream закреплён на `LowderPlay/cheburcheck@0bbd2be8ca4b8f9ded1407597654314fc2a900c6`; README и `THIRD_PARTY_NOTICES.md` сохраняют attribution и BSD-3-Clause notice.
- SQLite schema, 3x-ui/OpenAPI contract и VPN mutation semantics не меняются.
- `v4.23.0` разворачивается обычным Safe Bot Self-Update; обновление Host Control Agent, Deploy Agent, 3x-ui/Xray и SQLite migration не требуется. Bot schema остаётся v3.
- Cheburcheck остаётся optional external service: без `CHEBURCHECK_URL` экран показывает «не настроен», а остальные функции бота работают штатно. Production acceptance Cheburcheck выполняется только после настройки pinned self-hosted service или другого явно доверенного endpoint; rollback самого бота не требует отката БД.

## v4.22.0 — Группы пользователей
- Добавлена отдельная сущность User/Audience Groups для будущей сегментации Client Portal: `user_groups` и many-to-many `user_group_members` хранят membership по стабильному `telegram_id`, не по display name или email.
- Добавлен административный flow `Пользователи → Группы пользователей`: список и карточка групп, создание, переименование, описание, участники, поиск пользователя по Telegram ID/email/display name, добавление/удаление membership и просмотр групп из карточки пользователя.
- RBAC расширен permissions `user_groups.view` / `user_groups.manage` / `user_groups.admin` внутри существующих ролей Read-only / Support / Administrator; новых ролей не добавлено, неизвестные callbacks остаются fail-closed.
- Добавлен reusable backend matcher include/exclude с приоритетом exclude и семантикой «нет ограничений — доступ разрешён». User Groups не связаны с provisioning: membership не меняет Plan, Server Group, Nodes, Inbounds, subscription identity или VPN-доступ.
- SQLite schema повышена до v3 migration `user_audience_groups_v4_22_0`; migration additive и не требует recovery copy. Удаление группы очищает только membership, удаление пользователя очищает его memberships.
- Group и membership mutations записываются в существующий audit; удаление группы и удаление участника используют отдельные confirmation flows.
- Добавлен regression coverage для migration/schema, many-to-many membership, поиска, удаления, matcher edge cases, RBAC и разделения Audience Groups / provisioning. Новых env-переменных и host-side компонентов нет.
- `v4.22.0` разворачивается обычным Safe Bot Self-Update без обновления Host Control/Deploy Agent. После применения SQLite schema v3 downgrade на runtime, знающий только schema v2, несовместим без восстановления pre-v3 backup и должен остановиться fail-closed.

## v4.21.2 — Исправления Disaster Recovery и журнала бота
- Исправлен runtime `NameError` в Disaster Recovery после MSK-перехода: `disaster_recovery.py` теперь явно импортирует `format_datetime` и `format_short_datetime`, поэтому список/карточки резервных копий снова открываются штатно и продолжают показывать operator-facing время в MSK.
- В `Мониторинг → Журналы` режимы `50` и `200` больше не выглядят одинаковыми из-за общего character limit: UI показывает `запрошено N · показано M`, а режим `200` использует расширенный Telegram-safe budget для большего excerpt.
- Raw log timestamps намеренно остаются в исходной machine-level timezone (как правило UTC); MSK применяется к operator-facing structured timestamps, а не переписывает содержимое журналов.
- Regression coverage фиксирует imports DR formatter'ов, различие 50/200 log modes и текущую release version. SQLite schema, 3x-ui/OpenAPI, log redaction, Host Control/Deploy Agent и mutation semantics не меняются; host-side Agent/helper update не требуется.

## v4.21.1 — Консистентность display name и московское время
- Display name пользователя теперь используется последовательно на operator-facing поверхностях: `Подписки`, связанные user actions, список клиентов Inbound, monitoring, bulk selection и платежи; технический email остаётся machine identity, audit target и fallback.
- Добавлены общие presentation helpers для user labels, чтобы новые экраны не дублировали собственную логику `display_name · email` и не меняли callback/provisioning identity.
- Абсолютные дата/время в Telegram Admin Control Plane переведены на `MSK (UTC+3)`: сроки пользователей, audit/jobs, backup/system/DR timestamps, node heartbeat, payments/promos. Machine timestamps, Unix epoch, API semantics, backup filenames и agent journals не меняются.
- Date-only ввод `YYYY-MM-DD` для срока пользователя и промокода теперь означает конец выбранного дня `23:59:59 MSK`. Технический `BACKUP_HOUR_UTC` и фактическое расписание backup остаются UTC; UI показывает соответствующее MSK-время и исходное UTC значение.
- Добавлен regression pack для display-name consistency, MSK formatting и сохранения UTC scheduler boundary. SQLite schema, 3x-ui/OpenAPI contract, provisioning, Host Control/Deploy Agent API и mutation semantics не меняются; host-side Agent/helper update не требуется.

## v4.21.0 — Редактируемое имя пользователя
- Добавлено optional `display_name` в профиль пользователя через forward-only SQLite migration `v2 user_display_name_v4_21_0`; существующие профили получают пустое значение и продолжают отображаться по текущему email без ручной миграции данных.
- В карточке пользователя появилось действие `✏️ Имя`: оператор с ролью Support или выше может задать либо очистить отображаемое имя; ввод нормализуется, ограничен 64 символами и отклоняет управляющие символы.
- Карточка и список пользователей используют display name только как presentation metadata: email остаётся видимым техническим идентификатором, callbacks продолжают использовать `telegram_id`, а 3x-ui email, `sub_id`, provisioning и subscription identity не меняются.
- Изменение/очистка имени записывается в audit без сохранения самого имени в details; regression coverage проверяет schema upgrade, fallback, RBAC, edit/clear semantics и сохранение machine identity.
- Migration additive и не требует отдельной recovery copy, но после применения schema v2 downgrade приложения до `v4.20.10` без восстановления pre-v4.21 database несовместим и должен остановиться fail-closed. `v4.21.0` разворачивается стандартным release flow; host-side Agent/helper update не требуется.

## v4.20.10 — Compact Inbound keyboard follow-up
- По результатам production smoke `v4.20.9` карточка Inbound переведена на компактную пятистрочную двухколоночную клавиатуру, которая лучше переносит различия ширины Telegram Desktop после message edit.
- Зафиксирована целевая структура: `Клиенты | Изменить`, `Синхронизировать клиентов | Сбросить трафик`, `Клонировать | Сохранить шаблон`, `Отключить/Включить | Удалить`, затем `⬅ Inbounds`.
- Короткая кнопка `🗑 Удалить` используется только в карточке; отдельный confirmation screen по-прежнему явно показывает `Удалить Inbound` и требует подтверждения, поэтому deletion safety contract не меняется.
- Добавлен release-specific regression gate для layout и полного wording confirmation. Callback identifiers, SQLite schema, storage/persistence semantics, provisioning, pinned 3x-ui/OpenAPI contract и mutation behavior не меняются; `v4.20.10` устанавливается обычным Safe Bot Self-Update без host-side обновления Agent/helper.
## v4.20.9 — Post-acceptance UI cleanup
- Убран лишний implementation detail `bot.sqlite3` из operator-facing prompt сохранения Inbound template; текст теперь описывает только пользовательский результат без раскрытия внутреннего имени DB-файла.
- Перестроена клавиатура карточки Inbound для устойчивого отображения в узком client-side layout Telegram: длинные действия вынесены в отдельные строки, а `Отключить/Включить` и `Удалить Inbound` сгруппированы в предпоследней строке перед `⬅ Inbounds`.
- Закреплён обязательный двухшаговый deletion contract для Admin Control Plane: operator-facing delete entry открывает отдельный confirmation screen, а фактическое удаление выполняется только после явного confirm; one-click delete запрещён.
- Добавлен release-specific regression/source-audit для layout карточки Inbound и delete safety guardrail. Callback identifiers, SQLite schema, storage/persistence semantics, provisioning, pinned 3x-ui/OpenAPI contract и mutation behavior существующих delete flows не меняются; `v4.20.9` устанавливается обычным Safe Bot Self-Update без host-side обновления Agent/helper.
## v4.20.8 — Финальная капитализация Inbound
- Завершён terminology cleanup после production acceptance `v4.20.7`: оставшийся lowercase `inbound` в operator-facing edit/clone/delete/error/help flows заменён на канонические `Inbound` / `Inbounds`.
- Исправлены тексты Inbound admin UI, карточки пользователя и Server Group policy; `docs/UI_STYLE.md` теперь явно запрещает lowercase `inbound` как пользовательский термин.
- Technical identifiers намеренно не переименовываются: callback data, audit action ids, API/DB fields, Python identifiers и module names сохраняют существующий lowercase contract.
- Добавлен release-specific regression gate для operator-facing capitalization и стабильности technical identifiers. SQLite schema, provisioning semantics, pinned 3x-ui/OpenAPI contract и mutation behavior не меняются; `v4.20.8` устанавливается обычным Safe Bot Self-Update без host-side обновления Agent/helper.

## v4.20.7 — Единая терминология Inbound / Inbounds
- Во всём актуальном operator-facing UI гибридные формы с апострофом заменены на канонические `Inbound` / `Inbounds`: кнопки, заголовки, status/summary строки, ошибки, подсказки, RBAC labels, audit summaries и client-facing тексты используют единый terminology contract.
- README, Admin Setup, Roadmap и UI Style синхронизированы с тем же контрактом; `docs/UI_STYLE.md` явно запрещает русифицированные склонения `Inbound` через апостроф.
- Technical identifiers остаются стабильными: callback data, API/DB fields, Python identifiers, module names и enum не переименовываются; historical release notes не переписываются задним числом.
- Добавлен repo-wide regression/source-audit, запрещающий возврат гибридных operator-facing форм. SQLite schema, provisioning semantics, pinned 3x-ui/OpenAPI contract, Host Control/Deploy Agent API, callback identity и mutation safety не меняются; `v4.20.7` устанавливается обычным Safe Bot Self-Update без host-side обновления Agent/helper.

## v4.20.6 — Симметричный health summary Master и нод
- `Мониторинг → Состояние системы` приведён к общему presentation contract для Master и direct nodes: одинаковые доступные health-метрики используют одинаковые labels, status grammar и emoji.
- Direct node теперь явно показывает общий статус рядом с identity, отдельный статус панели и Xray state + version; `unknown` для Xray отображается отдельным жёлтым состоянием, а не ложным binary failure.
- CPU, RAM, uptime и Inbound'ы имеют симметричные подписи; Master-only disk/Subscription Proxy/nginx-TLS/DB/backup показатели остаются только у Master, а node-only latency/client/online counters сохраняются у direct nodes.
- Дополнительные API-вызовы к direct nodes ради визуального выравнивания не добавлялись; `docs/UI_STYLE.md` закрепляет правило «одинаково представлять одинаковые доступные данные».
- Добавлены regression tests на online/offline/maintenance и tri-state Xray presentation. SQLite schema, pinned 3x-ui/OpenAPI contract, callback identity и mutation safety semantics не меняются; `v4.20.6` устанавливается обычным Safe Bot Self-Update без host-side обновления Agent/helper.

## v4.20.5 — Финальная консистентность Admin UI
- `Инфраструктура → Операции с нодами → Состояние нод` теперь использует общий `node_display_name()` для direct nodes, поэтому operator-facing имя и country presentation fallback совпадают с остальными экранами.
- Список `Ноды` приведён к общей грамматике `identity · status icon status text`: Master и direct nodes явно показывают текстовый online/offline/unknown/maintenance status, сохраняя `node_id` как machine identity.
- `Обзор` стал обычным дочерним экраном `Панели администратора`: корневой `admin_menu()` больше не остаётся под dashboard-content, вместо него используются локальные `🔄 Обновить` и `⬅ Панель администратора`.
- Добавлены targeted regression tests для Fleet Health, списка нод и dashboard navigation; соответствующие display/navigation rules остаются закреплены в `docs/UI_STYLE.md`.
- SQLite schema, pinned 3x-ui/OpenAPI contract, Host Control/Deploy Agent API и mutation safety semantics не меняются; `v4.20.5` устанавливается обычным Safe Bot Self-Update без host-side обновления Agent/helper.

## v4.20.4 — Admin UI consolidation и единое отображение нод
- Карточка пользователя сведена к одному каноническому `admin:u:<tg_id>` flow: список `Пользователи` больше не открывает отдельную legacy-карточку, а `adminuser:<tg_id>` сохранён как compatibility route для старых Telegram-сообщений и рендерит ту же карточку.
- Repo-wide operator-facing node labels переведены на общий `node_display_name()` там, где отображается direct node: Monitoring, Fleet, Logs, Host Control, DR, Versions & Updates, Inbound UI, node backup summaries и связанные nested screens. Master остаётся отдельной сущностью; callback/binding identity по-прежнему строится по `node_id`/существующим machine identifiers, а не по display name.
- `Версии и обновления` получил симметричный overview Master/direct nodes: на главном экране показываются версии компонентов без лишнего Xray runtime-state, а состояние Xray остаётся на detail-screen конкретного сервера.
- Direct-node Xray log empty-state больше не выглядит как сломанный источник: проверено соответствие запроса pinned 3x-ui `v3.8.5` (`/panel/api/server/xraylogs/{count}` + `filter/showDirect/showBlocked/showProxy`); endpoint читает отдельный Xray access log, поэтому служебные `XRAY:`-события панели могут быть видны в журнале 3x-ui при пустом access log. UI теперь объясняет это различие.
- `Журнал аудита` получил читаемые summaries для bot self-update и отдельный read-only detail view с полными `details`, поэтому длинная диагностика больше не теряется из-за жёсткого 140-символьного обрезания.
- Operator-facing тексты очищены от лишних implementation details: `/create` заменён на понятное описание новых пользователей/создания доступа, `.env` — на локальную/административную конфигурацию, а основной экран `Роли и права` показывает человекочитаемые labels без внутренних permission IDs.
- `docs/UI_STYLE.md` закрепляет единый direct-node display contract и запрещает runtime-логику, привязанную к конкретной production-географии; `docs/ROADMAP.md` отдельно фиксирует optional `country_code`/ISO metadata как будущую неблокирующую задачу, не входящую в `v4.20.4`.
- Добавляется regression/source-audit coverage для user-card compatibility, node-display policy, audit detail RBAC и operator-facing text cleanup. SQLite schema, pinned 3x-ui/OpenAPI contract, Host Control/Deploy Agent API и mutation safety semantics не меняются; `v4.20.4` рассчитан на обычный Safe Bot Self-Update без host-side обновления Agent/helper.
## v4.20.3 — Production smoke fixes для backup integrity и Admin UI
- Исправлен Full Backup integrity contract: корневой `manifest.json` по-прежнему не хеширует сам себя, но nested `nodes/*/manifest.json` теперь входит в `integrity.files`; embedded node backup проходит `RestoreManager.inspect_backup()` без ложной ошибки `manifest integrity не покрывает файлы`.
- В Disaster Recovery detail/preflight и история восстановления возвращаются к непосредственному parent `Аварийное восстановление`; restore остаётся fail-closed и Owner-only, mutation semantics не менялись.
- Detail подписки сохраняет контекст входа: из top-level `Подписки` Back возвращает в `Подписки`, а из карточки пользователя — к пользователю; отдельный `adminsublist:<tg_id>` зарегистрирован в RBAC как `read_only`.
- `Состояние системы` теперь имеет локальный `Обновить` и `Назад в Мониторинг`; Server Groups используют общий `node_display_name()`, поэтому direct nodes отображаются единообразно, например `🇫🇮 Finland`.
- Убраны stale operator-facing версии `v4.5`/`v3.9`, сокращена обрезавшаяся подпись inbound sync и устранена тавтология `Master: <flag> Master` на экране настроек.
- Regression coverage расширен на production smoke findings, включая реальный Full Backup → restore inspection contract; SQLite schema, 3x-ui/OpenAPI, Host Control API, Deploy Agent/helper и privilege boundaries не изменены. `v4.20.3` устанавливается обычным Safe Bot Self-Update без host-side обновления Agent/helper.

## v4.20.2 — Исправление parent navigation Admin Control Plane
- Исправлены отклонения от существующего navigation-контракта `docs/UI_STYLE.md`: вложенные экраны возвращаются к фактическому непосредственному parent, а validation/error paths не теряют Back/Cancel.
- `Система → Обновления бота → История обновлений` теперь возвращает в `Обновления бота`; node log view — к источникам выбранной ноды; Host Control и Disaster Recovery сохраняют корректный parent/Cancel в typed-confirmation/error flows.
- Owner unlock flow в `Версии и обновления` получил отдельный read-only operation view `admin:ver:op:<nonce>`, чтобы Cancel возвращал к исходной операции без повторного update/recheck mutation; callback зарегистрирован в RBAC как `read_only`.
- Regression coverage расширен на nested parent flows; source-audit admin UI подтверждает, что без навигации остаются только намеренные progress/transition screens и существующие terminal authorization guards.
- SQLite schema, 3x-ui/OpenAPI contract, Host Control API, Deploy Agent API/host helper и privilege boundaries не изменены; `v4.20.2` можно устанавливать обычным Safe Bot Self-Update без отдельного host-side обновления Agent/helper.

## v4.20.1 — Safe Bot Self-Update release-notes hotfix
- Исправлен intermittent blocker Safe Bot Self-Update: `notes_cmd` больше не использует SIGPIPE-sensitive pipeline `printf | awk` под `set -o pipefail`, из-за которого корректный published release иногда отклонялся как `release_notes_missing` с exit code 141.
- Release notes по-прежнему читаются только из `CHANGELOG.md` целевого опубликованного тега после обычной release validation; fail-closed поведение при реально отсутствующих/ошибочных notes сохраняется.
- Deploy Agent version повышена до `0.1.2`, чтобы установленный host-side control plane можно было однозначно отличить от версии с дефектным helper.
- Добавлен regression source-contract, запрещающий возврат SIGPIPE-sensitive notes pipeline; API surface, sudoers allowlist, mutation semantics, SQLite schema и 3x-ui compatibility contract не изменены.
- Поскольку helper устанавливается host-side и не заменяется пересозданием bot container, перед повторной попыткой self-update production Deploy Agent должен быть обновлён до host bundle из `v4.20.1`.

## v4.20.0 — Подготовка Admin Control Plane к заморозке
- Завершена декомпозиция runtime: `bot.py` оставлен минимальным executable shim, lifecycle/startup/recovery вынесены в `app_runtime.py`, client flow — в `client_access.py`, admin shell и domain handlers — в отдельные routers с закреплённым single ownership.
- Telegram UI Admin Control Plane системно приведён к русской локализации при сохранении технических identifiers, фиксированных RBAC role names и typed confirmation phrases; regression gate блокирует возврат смешанного operator-facing UI.
- Проведён repo-wide аудит информационных emoji/status/resource префиксов и навигации `/admin`: убраны дублирующие входы, выровнены Back/Refresh/Cancel/Confirm flows и закрыты callback/FSM dead ends без изменения domain semantics.
- README и актуальные operator runbook'и синхронизированы с текущей архитектурой и русскими UI-paths; public-facing примеры очищены от private deployment привязок и защищены отдельным public-readiness regression contract.
- Добавлены regression/source-inspection gates на runtime/router ownership, Admin navigation, UI localization, emoji conventions и актуальность public documentation; SQLite schema, pinned 3x-ui OpenAPI contract и существующие Host Control/Deploy Agent privilege boundaries не расширяются.
- Релиз закрывает cleanup/freeze-prep scope раздела roadmap «Желательно закрыть до финальной заморозки v4.x»; отдельный production drill encrypted off-site backup/restore остаётся обязательным pre-v5 gate перед окончательной заморозкой v4.x.

## v4.19.1 — Safe Bot Self-Update acceptance hotfix
- Исправлен production blocker Deploy Agent под hardened systemd sandbox: root helper теперь задаёт отдельный `DOCKER_CONFIG=/var/lib/3xui-deploy-agent/docker-config`, поэтому `docker compose build` не пытается создать `/root/.docker` при `ProtectHome=true`.
- Installer создаёт отдельный root-only writable Docker config directory внутри уже разрешённого `/var/lib/3xui-deploy-agent`; privilege boundary, sudoers allowlist и отсутствие Docker socket в bot container не меняются.
- Release notes стали обязательной частью успешного Deploy Agent preflight: ошибка/timeout/missing notes теперь fail-closed, а не маскируются пустым блоком в Telegram.
- Same-release production acceptance отображается как `same release`, а не как `upgrade`.
- Hotfix закрывает defect, найденный при первом production acceptance `v4.19.0`: операция остановилась после verified backup и checkout, до `deploying`/container recreate, с `deploy_command_failed_before_dispatch`.

## v4.19.0 — Safe Bot Self-Update
- Добавлен отдельный restricted Deploy Agent вне bot container: unprivileged systemd service, bearer-authenticated fixed API и persistent SQLite journal с stable `operation_id` и состояниями `queued/preflight/backup/building/deploying/verifying/success/failed/unknown`.
- Bot container по-прежнему не получает Docker socket, host shell, Git deploy key или arbitrary filesystem access; root boundary сведена к одному root-owned helper с закрытым command surface для published `vX.Y.Z` releases.
- Published release validation проверяет tag в `origin/main`, exact `APP_VERSION`, pinned SSH known_hosts, clean tracked tree и текущий Health/DB/3x-ui status; release notes читаются read-only из target `CHANGELOG.md` без выполнения target code.
- `/admin → System → Bot Updates` доступен только Owner: current/latest, release notes, preflight, exact published tag selection, operation history/status и явный update confirmation. Downgrade требует точной фразы `DOWNGRADE vX.Y.Z` и повторного preflight.
- Потерянный deploy response и restart bot/agent никогда не приводят к автоматическому mutation replay: bot и agent восстанавливают результат только через read-only operation/status lookup; недоказанный итог становится `unknown`.
- Startup recovery двухфазный: мгновенный lookup выполняется до generic stale cleanup, а ожидание terminal state начинается только после поднятия health endpoint, поэтому self-update не блокирует post-deploy health check.
- Manual и agent deployment используют общий host lock под deploy backup root; ручной `scripts/deploy-release.sh vX.Y.Z` остаётся break-glass fallback.
- Добавлены installer/systemd/sudoers tooling, isolated root-only Git key/known_hosts copy, private Docker-bridge listener и regression/security tests; SQLite app schema, 3x-ui OpenAPI contract, Host Control API и off-site backup contract не меняются.

## v4.18.0 — Encrypted off-site backup
- Full Backup manifest переведён на checksummed schema 2: для каждого обычного файла архива фиксируются path, size и SHA-256, а restore validation проверяет coverage/size/hash fail-closed; legacy archives остаются читаемыми обычным DR tooling.
- Добавлена optional S3-compatible off-site replication, выключенная по умолчанию: canonical Full Backup шифруется client-side AES-256-GCM до upload, а bucket/prefix/endpoint/credentials задаются только локально и не управляются через Telegram.
- Local backup и external replication имеют независимые outcomes: `backup.daily`/`backup.manual` фиксируют локальный archive, `backup.offsite` — внешний upload; ошибка provider-а не превращает уже созданную локальную копию в false failure.
- Off-site success требует remote round trip: HEAD metadata verification, download, GCM authentication, plaintext SHA-256/size и повторный deep Full Backup validation; retention выполняется только после подтверждённой читаемости.
- Добавлен host-side `scripts/fetch-offsite-backup.py`: recovery CLI получает latest canonical object только из fixed prefix, decrypt/validates его и выдаёт mode-0600 archive для существующего `bootstrap-bot-from-backup.sh`.
- Добавлены regression tests на manifest tampering, encryption/round trip, fixed-prefix retention, target security boundaries и отдельный failed `backup.offsite` job; SQLite schema, 3x-ui API, Host Control API и RBAC не изменены.

## v4.17.0 — 3x-ui OpenAPI compatibility gate
- Поддерживаемый native API contract зафиксирован на 3x-ui `v3.8.5`: vendored OpenAPI берётся из immutable upstream tag, а exact Git blob SHA хранится в contract manifest.
- `contracts/3xui/contract.json` описывает 51 реально используемый endpoint; CI проверяет route/method, Bearer auth, request body required/media type/mandatory fields и общий JSON response envelope.
- AST source-parity check сопоставляет manifest с фактическими `/panel/api/...` вызовами в `xui.py` и `version_api.py`, поэтому новый или удалённый route требует явного contract review до merge.
- Проверка полностью offline/stdlib-only: CI не скачивает upstream `main` и runtime не переключается автоматически на неизвестную API schema.
- Единственное documented response exception — `GET /panel/api/server/getDb`: OpenAPI v3.8.5 описывает generic JSON envelope, а live endpoint возвращает binary DB attachment; route/method/auth остаются под gate, binary semantics покрываются отдельными regression tests.
- Добавлены regression tests на missing method, новый mandatory field, response-envelope drift, schema tampering и dynamic route discovery; SQLite schema, runtime 3x-ui requests, Host Control API и deployment topology не изменены.

## v4.16.0 — Regression coverage hardening
- Добавлен целевой regression pack для критических admin/business/recovery путей: payment/status и catalog relations, user lifecycle mutation ordering, provisioning idempotency/partial failure, subscription proxy compatibility/error paths, inbound mutation failure paths, disaster recovery и negative authorization boundaries.
- Safe/strict provisioning теперь явно проверяются на разные privilege boundaries: per-user safe reconcile доступен роли `support`, strict reconcile остаётся `admin`; regression tests выявили и исправили drift, при котором privilege catalog излишне требовал `admin` и для safe reconcile.
- User lifecycle tests подтверждают, что local expiry/record/subscription identity не меняются раньше успешной state-changing операции в 3x-ui; failed remote delete сохраняет локальную запись.
- Provisioning tests фиксируют повторный safe reconcile без лишних mutations, stop-safe strict semantics, недоступные node как partial result и изоляцию batch failure одного пользователя от остальных.
- Subscription proxy и restore tests покрывают plain/Base64 subscriptions, selective `vpn://` conversion, Shadowrocket compatibility, invalid `sub_id`, upstream failures, unsafe/malformed backup, staged SHA mismatch, rescue copy и отсутствие replay broken restore.
- Схема SQLite, 3x-ui API contract, Host Control API и deployment topology не изменены.

## v4.15.0 — Versioned SQLite migrations
- Добавлен versioned migration framework для локальной `bot.sqlite3`: source of truth хранится в `schema_migrations`, migrations идут только вперёд и имеют стабильные version/name.
- Текущая схема v4.14.2 оформлена как идемпотентная baseline migration `v1 baseline_v4_14_2`, поэтому существующие installation без migration journal обновляются in-place с сохранением данных.
- Startup работает fail-closed для `running`/`failed` migration, gap/unknown journal, более новой schema version, schema mismatch и failed `PRAGMA quick_check`; неопределённая state-changing migration автоматически не replay'ится.
- Dangerous migrations с `requires_backup=True` до mutation создают проверенную SQLite Online Backup recovery copy в persistent `data/migration-backups/`; автоматических down migrations и automatic restore нет.
- Добавлены regression tests для fresh/legacy DB, newer schema, interrupted/failed migration, обязательной recovery copy и rollback, а operational/developer contract зафиксирован в `docs/SQLITE_MIGRATIONS.md`.
- Схема 3x-ui, Host Control API, RBAC privilege boundaries, provisioning и subscription semantics не изменены.

## v4.14.2 — Исправление guided onboarding direct node
- Исправлен разбор аргументов `--admin-enrollment` и `--host-control-enrollment` в `scripts/onboard-direct-node.sh bind`: значения теперь попадают в канонические переменные, поэтому guided bind проходит preflight/import вместо ложной ошибки отсутствующих enrollment files.
- Добавлен исполняемый regression test, который запускает `bind` с временными enrollment-файлами и проверяет фактические вызовы direct-admin и Host Control importer preflight.
- Security boundary не меняется: node-sync, direct-admin и Host Control credentials остаются раздельными; mutation semantics, stable `node_id` binding и single bot recreate сохранены.

## v4.14.1 — Исправление Host Control snapshot rollout
- Исправлено чтение nginx snapshot в bot client: streaming HTTP response теперь читается до EOF с сохранением жёсткого лимита 10 MiB, поэтому multi-chunk ответы reverse proxy больше не дают ложный `checksum_mismatch`.
- Installer Host Control Agent теперь явно перезапускает `3xui-host-control.service` после обновления runtime files/unit, поэтому повторный rollout действительно активирует новую версию agent без ручного restart.
- Добавлены regression tests для multi-chunk snapshot response и upgrade restart path; security boundary fixed snapshot endpoint, host identity/TLS/checksum validation и mutation allowlist не расширены.

## v4.14.0 — RBAC и расширенные node snapshots
- Добавлен централизованный каталог RBAC privileges для фиксированных ролей `Read-only`, `Support`, `Administrator` и `Owner`; authorization layer использует его как source of truth, неизвестные admin callbacks блокируются fail-closed, а `/admin → Administrators → Roles & Privileges` показывает действующие permission boundaries.
- Direct-node backup расширен до recovery-oriented snapshot `nodes/<node>/` с `x-ui.db`, `nginx/`, `node.json` и `manifest.json`; manifest хранит stable node identity, component status, доступные версии, размеры и SHA-256 файлов, а тот же snapshot включается в обычный Full Backup.
- Host Control Agent получил fixed read-only `GET /v1/snapshots/nginx`: endpoint не принимает filesystem path/filename/query selector, читает только локально настроенный `HOST_CONTROL_AGENT_NGINX_SOURCE` и не расширяет mutation allowlist за пределы `start|stop|restart`.
- Отсутствующий или частично недоступный nginx source отражается как `degraded`/missing component, а не как ложный complete; bot дополнительно валидирует host identity, transport checksum, tar paths, file sizes и per-file checksums.
- Для nginx snapshot source используется отдельный optional `/etc/3xui-host-control/nginx-snapshot.env`, который не входит в enrollment/bot `.env`; automatic remote nginx restore не добавлен, схема SQLite не изменена.
- Добавлены regression/security tests для RBAC route coverage/fail-closed, fixed Host Control snapshot surface, archive integrity/path traversal и полного/degraded node backup.

## v4.13.2 — Host Control startup recovery
- Startup бота теперь запускает `recover_control_jobs()` сразу после `db.init()` и до общего stale-job cleanup, поэтому незавершённые Host Control jobs получают шанс восстановить точный итог из persistent operation journal.
- Recovery использует только read-only lookup сохранённого `operation_id`; state-changing Host Control mutation после рестарта автоматически не повторяется, а недоказуемый результат остаётся `unknown`.
- Добавлены regression tests на порядок startup recovery и отсутствие mutation replay; схема SQLite, Host Control Agent API и privilege boundaries не изменены.
## v4.13.1 — Исправление Fleet Rollout jobs
- Исправлен accounting `Controlled Rollout`: terminal no-op plan с уже актуальными версиями теперь создаёт и завершает parent `fleet.rollout` job со статусом `success`.
- Отмена rollout до запуска canary теперь также фиксируется parent `fleet.rollout` job со статусом `cancelled`, поэтому `🧾 Fleet Jobs` и audit отражают terminal operation.
- Для уже актуальных targets summary parent job использует `skipped`, а не `pending`; update/maintenance mutation при этих сценариях по-прежнему не отправляется.

## v4.13.0 — Fleet Operations
- Добавлен раздел `🌐 Fleet Operations` с read-only `Fleet Health`, controlled Fleet Maintenance, Fleet Jobs и последовательным rollout для direct nodes.
- `Controlled Rollout` переиспользует существующий two-phase `UpdateService`: verified backup выполняется до intentional maintenance, затем update запускается строго по одной node с canary и explicit continue.
- Rollout работает stop-on-failure: при `failed` или `unknown` проблемная node остаётся в maintenance, оставшиеся nodes не затрагиваются, state-changing request автоматически не повторяется.
- Rollout eligibility требует direct online node, доступные Direct Panel API и Host Control, а также stable `node_id` binding для обоих privileged targets; transitive и legacy-name targets не мутируются.
- После рестарта незавершённые fleet operations помечаются interrupted/unknown и не продолжаются автоматически; mass `Stop service` / `Stop Xray`, parallel rollout и automatic rollback намеренно не добавлены.
- Scope и safety contract зафиксированы в `docs/FLEET_OPERATIONS.md`.

## v4.12.0 — Guided onboarding direct node
- Добавлен guided wrapper `scripts/onboard-direct-node.sh`: `prepare` собирает/опционально копирует secret-free Host Control bundle и формирует remote install command, `bind` проводит node registration и оба privileged bindings через единый stable `NODE_ID`.
- `import-node-admin-target.py` получил `--node-id`; ID из enrollment и explicit override проверяются на совпадение fail-closed.
- Guided flow сохраняет разделение node-sync/direct-admin/Host Control secrets, выполняет importer preflights до изменения bot `.env` и пересоздаёт только service `bot` один раз.

## v4.11.1 — Исправление Readiness callback
- Исправлен routing кнопки `🧭 Readiness`: общий handler карточки ноды больше не перехватывает callback `admin:node:<id>:readiness`.
- Node detail handler теперь принимает только точный callback `admin:node:<id>`, а readiness сохраняет отдельный маршрут.
- Добавлен regression-test, который блокирует возврат broad `admin:node:` startswith-handler.
- Stable `NODE_ID` bindings, onboarding helpers, privilege boundaries и схема SQLite не изменены.

## v4.11.0 — Node readiness и безопасный onboarding
- Privileged targets для direct nodes получили стабильную привязку к 3x-ui `node.id` через `NODE_BACKUP_*_NODE_ID` и `HOST_CONTROL_*_NODE_ID`; старый lookup по display name сохранён только как backward-compatible fallback.
- Explicit mismatched `NODE_ID` работает fail-closed: target, привязанный к другому node ID, не может быть подобран только по совпавшему имени.
- Переименование direct node больше не ломает backup, restore, Versions & Updates, Panel/Xray controls и Host Control при наличии stable `NODE_ID`.
- В карточку direct node добавлен read-only экран `🧭 Readiness`: он проверяет Master view, direct Panel API, Host Control Agent, runtime readiness и тип binding без mutation.
- Добавлен `scripts/onboard-node.py` для регистрации node локально на Master из mode-0600 enrollment-файла: по умолчанию только preflight, mutation выполняется только с `--apply`, automatic retry отсутствует.
- Добавлен `scripts/import-node-admin-target.py` для безопасного импорта dedicated direct-admin credential; Host Control enrollment importer получил `--node-id`.
- Рекомендуемый onboarding больше не требует передачи node-sync/direct-admin/Host Control secrets через Telegram; privilege domains остаются раздельными.
- Новые onboarding helpers требуют verified HTTPS для новых direct node/admin endpoints и не печатают secrets.
- Добавлен runbook `docs/NODE_ONBOARDING.md` и regression tests для stable identity, legacy fallback, fail-closed mismatch, local enrollment permissions и onboarding transport policy.
- Схема SQLite, provisioning пользователей, подписки и privilege boundary Host Control Agent не изменены.

## v4.10.1 — Operational rollout и recovery
- Добавлен `scripts/bootstrap-bot-from-backup.sh` для восстановления Telegram-бота на подготовленном новом VPS из Full Backup с проверкой tag/APP_VERSION, tar safety, SQLite `quick_check`, rescue-copy и post-check через `deploy-release.sh --status`.
- Recovery по умолчанию требует совпадения версии backup с целевым release; intentional mismatch возможен только через `RECOVERY_ALLOW_VERSION_MISMATCH=1`.
- При recovery намеренно отключаются `HOST_CONTROL_TARGETS` и `NODE_BACKUP_TARGETS`, чтобы privileged routes/tokens старого deployment не активировались автоматически.
- Добавлен воспроизводимый Host Control rollout: secret-free deployment bundle, отдельный restricted proxy, enrollment-importer для безопасного обновления bot `.env`, идемпотентное добавление target и recreate только service `bot`.
- Remote Host Control proxy получил ежедневный TLS refresh timer: source certificate/key проверяются на hostname и соответствие пары, proxy reload выполняется только при обновлении копий.
- Повторный rollout с `--apply-ufw` хранит managed firewall state и при изменении management source/destination/port удаляет прежнее exact allow-rule перед добавлением нового.
- Добавлены runbook `docs/HOST_CONTROL_ROLLOUT.md`, `docs/VPS_RECOVERY.md`, новые unit/security tests и CI-проверки executable bit/shell syntax для operational helpers.
- Runtime semantics экрана `🧩 3x-ui Control`, privilege boundary Host Control Agent, схема SQLite и provisioning пользователей не изменены.

## v4.10.0 — Безопасный 3x-ui Control
- Реализован restricted `Host Control Agent` для host-level `status/start/stop/restart x-ui.service`: listener только `127.0.0.1`, отдельный token на host, fixed service/action allowlist, `shell=False`, persistent `operation_id`, lost-response recovery без повторного mutation POST.
- Добавлен единый экран `🧩 3x-ui Control` для Master и direct nodes: `Start/Restart service` доступны Admin+, destructive `Stop service` и `Stop Xray` — только Owner; Stop service требует одноразовую typed-фразу `STOP <target>`.
- Добавлены native действия `♻️ Restart Panel process` через `POST /panel/api/setting/restartPanel`, `Stop Xray` через `/server/stopXrayService` и `Restart / Start Xray` через `/server/restartXrayService`.
- Агент не предоставляет SSH/shell/exec/file/Docker/firewall/reboot/package-management API; systemd unit запускает его непривилегированным пользователем, а sudoers разрешает только три точных команды для `x-ui.service`.
- Remote host-control targets требуют verified HTTPS; private HTTP разрешён только для локального `MASTER` через restricted management route.
- Добавлены installer/systemd/sudoers assets, production deployment guide и CI-проверки executable bit, shell syntax, `visudo`, transport policy, host identity, no-retry, privilege boundary и security invariants.

## v4.9.3 — Исправление счётчиков карточки ноды
- Карточка `Infrastructure → Nodes → <node>` теперь использует enriched-данные `/panel/api/nodes/list` для вычисляемых счётчиков `inboundCount`, `clientCount`, `activeCount` и `onlineCount`.
- При недоступности list API или отсутствии нужной ноды сохраняется fallback на `/panel/api/nodes/get/{id}`, поэтому административные действия не блокируются.
- Исправлен визуальный эффект, при котором рабочая удалённая нода показывала `Inbound'ов: 0` и `Клиентов: 0`, несмотря на реально синхронизированные inbound'ы и активный трафик.
- Схема SQLite, provisioning, подписки, direct admin target и управление версиями не изменены.

## v4.9.2 — Deploy helper и улучшения System/Reality
- Добавлен `scripts/deploy-release.sh` для повторяемого развёртывания опубликованных тегов на VPS.
- Перед cutover helper проверяет тег, `APP_VERSION`, текущее здоровье сервиса, SQLite, upstream 3x-ui и соответствие Docker-подсети.
- Перед обновлением сохраняются `.env`, Compose-конфигурация, SHA/образ текущего состояния и согласованная копия `bot.sqlite3`.
- Helper пересоздаёт только сервис `bot` и намеренно не выполняет `docker compose down`, `docker system prune`, обновление 3x-ui/Xray или автоматический откат базы.
- Добавлены режим `--status`, явная защита от случайного downgrade и CI-проверка shell-синтаксиса helper.
- В разделе `System` отображается текущая версия бота из единственного `APP_VERSION`.
- Reality fingerprint inbound'а выбирается кнопками из актуального списка 3x-ui: `chrome`, `firefox`, `safari`, `ios`, `android`, `edge`, `360`, `qq`, `random`, `randomized`, `randomizednoalpn`, `unsafe`.
- Произвольный ручной ввод fingerprint из Telegram удалён; остальные `Reality`/`streamSettings` сохраняются при изменении.
- Схема SQLite и логика подписок не изменены.

## v4.9.1 — Стабилизация сети и интерфейса
- Docker-подсеть проекта закреплена через `BOT_DOCKER_SUBNET` с дефолтом `172.19.0.0/16`, чтобы пересоздание Compose-сети не меняло источник трафика к локальной панели 3x-ui.
- В документацию добавлено требование синхронизировать UFW-правило для порта панели с выбранной Docker-подсетью.
- CI дополнен проверкой `docker compose config` на основе `.env.example`.
- Навигация `Versions & Updates` приведена к общему стилю административной панели с явными кнопками возврата, обновления, подтверждения и пагинации.
- Все статические inline-кнопки пользовательского и административного интерфейса приведены к правилу с emoji или навигационным символом; CI проверяет новые статические кнопки на соответствие этому правилу.
- Схема SQLite, API-контракты 3x-ui и логика подписок не изменены.

## v4.9.0 — Версии и обновления
- Добавлен общий раздел `Versions & Updates` и переходы из карточек Master и нод.
- Добавлены явный выбор стабильного канала обновления 3x-ui и установка конкретной версии Xray.
- Перед установкой создаётся и проверяется свежая резервная копия; используются одноразовое подтверждение с ограниченным сроком действия, сохраняемая блокировка сервера и проверка результата обновления.
- Проверяются идентификаторы запуска обновления панели; потеря ответа не приводит к автоматической повторной отправке команды.
- Просмотр доступен роли `Read-only`, установка — `Admin` и `Owner`; снятие блокировки при неподтверждённом результате требует явного подтверждения `Owner`.
- Повторно используются существующие таблицы аудита и заданий; схема SQLite не изменена.
- Введён единый `APP_VERSION`, исправлены устаревшие номера версии в манифестах резервных копий.
- Добавлены автоматизированные тесты API, сценариев обновления и интеграции, а также проверки PR в CI с правами только на чтение.

## v4.8.0 — Админ-панель в одном сообщении
- Админ-панель переведена на одно обновляемое сообщение Telegram.
- Навигация встроенными кнопками, включая Back/Refresh/Confirm, больше не засоряет чат новыми сообщениями.
- FSM-формы возвращают пользователя в исходную панель; введённые служебные сообщения по возможности удаляются.
- Файлы, уведомления и внешние события намеренно остаются отдельными сообщениями.

## v4.7.0 — Аварийное восстановление
- Добавлен защищённый сценарий восстановления для `bot.sqlite3`, базы 3x-ui на Master и баз нод.
- Добавлены предварительная проверка без применения изменений, SQLite `quick_check`, аварийные копии текущего состояния и двойное подтверждение.
- Восстановление базы бота выполняется на этапе начальной загрузки до запуска основного процесса.
- `bot.env` и конфигурация nginx доступны для извлечения, но не восстанавливаются автоматически.

## v4.6.0 — Журналы и уведомления
- Добавлен централизованный просмотр журналов бота, 3x-ui, Xray, AmneziaWG и nginx.
- Добавлены фильтры `ALL`/`WARN+`/`ERROR` и ограничение количества последних строк.
- Добавлены правила уведомлений: недоступность Master/Xray/ноды, ошибка задания, превышение порога использования диска и устаревшая резервная копия.
- Добавлены уведомления о восстановлении, интервалы между повторными оповещениями и маскирование чувствительных данных в журналах.

## v4.5.0 — Механизм назначения ресурсов пользователям
- Связана цепочка `Plan → Server Group → Nodes → Inbounds → User`.
- Для Server Group добавлена политика назначения ресурсов: все управляемые inbound'ы или выбранный набор.
- Добавлены предварительный просмотр и оценка расхождений для пользователя, безопасное согласование `Safe reconcile` и строгое согласование `Strict reconcile`.
- Добавлено массовое согласование пользователей с учётом их политик.
- Тариф по умолчанию может управлять `/create`; прежний пробный режим сохраняется как резервный вариант.

## v4.4.0 — Расширенное управление нодами
- Расширена карточка ноды: состояние, версии, ресурсы, задержка ответа API, inbound'ы и активные подключения.
- Добавлены проверка соединения и повторная проверка, режим обслуживания, переименование, резервное копирование отдельной ноды и перезапуск Xray.
- Добавлены штатное обновление 3x-ui и безопасное удаление ноды с проверками.

## v4.3.0 — Расширенное управление inbound'ами
- Добавлены карточки inbound'ов и список клиентов.
- Добавлены безопасное редактирование, включение/отключение, синхронизация, сброс трафика и клонирование.
- Добавлены шаблоны inbound'ов и их развёртывание на Master и нодах.
- Приватные ключи не выводятся в интерфейсе Telegram.

## v4.2.0 — Расширенное управление пользователями
- Добавлено управление сроком действия, трафиком, лимитом IP, тарифом, группой серверов и заметкой пользователя.
- Добавлены управление inbound'ами пользователя, сброс трафика и смена идентификатора подписки.
- Добавлены массовые действия над пользователями.
- Добавлена таблица `user_profiles` без изменения существующей `users`.

## v4.1.0 — Платежи и администрирование
- Добавлены внутренний реестр платежей `Payments` и каталог промокодов `Promo Codes`.
- Добавлены администраторы с ролями `Owner` / `Administrator` / `Support` / `Read-only`.
- `ADMIN_TELEGRAM_IDS` остаются защищёнными владельцами `Owner`.
- Добавлены безопасные настройки времени выполнения для параметров пробного доступа и валюты по умолчанию.

## v4.0.0 — Мониторинг, задания и аудит
- Добавлены разделы `Monitoring → Traffic` и `Online`.
- Добавлены разделы `System → Jobs` и `Audit Log`.
- Добавлены общая блокировка заданий резервного копирования и журналирование действий администраторов.
- Главная страница `Dashboard` дополнена сводкой мониторинга и состояния системы.

## v3.9.0 — Тарифы, группы серверов и адреса
- Добавлены тарифы `Plans` со сроком действия, объёмом трафика, лимитом IP, ценой и статусом.
- Добавлены группы `Server Groups` и привязка серверов.
- Добавлены реестр `Hosts` и обнаружение используемых адресов.

## v3.8.0 — Основа рабочей админ-панели
- Админка реорганизована в `Dashboard` / `Users` / `Subscriptions` / `Payments` / `Plans` / `Promo Codes` / `Infrastructure` / `Monitoring` / `System`.
- Существующая бизнес-логика сохранена; изменён в основном навигационный слой.
- Добавлены рабочая сводка `Dashboard` и отдельный раздел подписок `Subscriptions`.

## v3.7.2 — Добавление нод из Telegram
- Добавлен мастер `➕ Добавить ноду` через Telegram.
- Добавлены проверка соединения, выбор режима проверки TLS и вызовы штатного API нод 3x-ui.
- Текст пустого списка нод сделан нейтральным.

## v3.7.1 — Карточка Master
- Master отображается первой полноценной карточкой в разделе `Nodes`.
- Master учитывается в общем числе серверов и доступных серверов и открывается как отдельная карточка состояния.

## v3.7.0 — Основа работы с несколькими нодами
- Добавлена интеграция со штатным API 3x-ui для управления несколькими нодами.
- Добавлены отображение нод в `System Health` и подготовка резервного копирования их баз данных.
- Заложена основа для первой внешней ноды.

## v3.6.0 — Резервное копирование
- Добавлен раздел `Backups` в `/admin`.
- Добавлены ручные и ежедневные резервные копии с ограничением числа хранимых архивов.
- Полный архив включает базу бота, базу 3x-ui, `.env`, Compose и nginx при их доступности.
- Добавлен `.dockerignore`, чтобы секреты и рабочие данные не попадали в контекст сборки образа.

## v3.5.5 — Состояние сервера и ограничение журналов Docker
- В админку добавлен раздел `Состояние сервера`.
- Добавлены показатели диска, оперативной памяти, времени работы и проверки доступности.
- Журналы Docker `json-file` ограничены размером `10m × 3`.

## v3.5.4 — Совместимость Shadowrocket с XHTTP
- Для Shadowrocket в машинном формате подписки удаляется `fp` только у `VLESS + XHTTP + Reality`.
- INCY и TCP Reality сохраняют прежнее поведение.
- Клиент определяется по `User-Agent`.

## v3.5.3 — Синхронизация VLESS XTLS flow
- Добавлены настройка `VLESS_FLOW` и синхронизация `flow` для VLESS-клиентов там, где это применимо.

## v3.5.2 — Штатное отображение AmneziaWG на странице 3x-ui
- HTML-режим прокси совместимости больше не переписывает `vpn://` внутри страницы 3x-ui.
- Машинный формат подписки продолжает преобразование в `amneziawg://` для совместимых клиентов.

## v3.5.1 — Ресурсы страницы 3x-ui
- Исправлено проксирование ресурсов встроенной страницы подписки 3x-ui через `/compat/`.

## v3.5 — Штатная страница 3x-ui и совместимая подписка
- Режим для браузера сохраняет штатную HTML-страницу 3x-ui.
- Режим для VPN-клиента выдаёт подписку с преобразованиями для совместимости.

## v3.4 — Прокси подписок AmneziaWG для INCY
- Добавлен прокси совместимости поверх штатной подписки 3x-ui.
- В машинном формате подписки `vpn://` преобразуется в `amneziawg://`.

## v3.3 — Массовая синхронизация inbound'ов
- Добавлена массовая синхронизация пользователей с разрешёнными inbound'ами.

## v3.2 — Синхронизация inbound'ов отдельного пользователя
- Добавлена синхронизация разрешённых inbound'ов для отдельного пользователя.

## v3.1 — Имена клиентов на основе имени пользователя
- Поля `email`/`remark` клиента 3x-ui для новых пользователей формируются из имени пользователя Telegram; при его отсутствии используется Telegram ID.

## v3 — Админ-панель в Telegram
- Добавлена Telegram-админка: пользователи, статистика, карточка пользователя, продление, включение/отключение и удаление.
- SQLite остаётся базой связей и бизнес-данных, а 3x-ui — источником учётных данных протоколов и текущего состояния.

## v2 — Фильтрация inbound'ов и настройка API для одного сервера
- Добавлены фильтры разрешённых портов и протоколов, а также исключения для служебных inbound'ов и API.
- Уточнена работа назначения ресурсов на одном сервере через API 3x-ui.

## v1.0.0 — Первый исторический снимок
- Первый сохранённый тестовый бот для одного сервера.
- Базовые команды `/start`, `/inbounds`, `/create`, `/subscription`.
- Python + aiogram + aiohttp + aiosqlite + Docker Compose.

- Повторный аудит назначения: провайдер проверяется до сохранения локального тарифа; прямое массовое назначение бессрочного технического тарифа блокируется, повреждённые правила групп не ломают карточку, Stars-only тариф не подписывается как `0 RUB`.
