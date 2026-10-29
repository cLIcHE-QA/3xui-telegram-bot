# 3x-ui OpenAPI compatibility contract

Этот документ описывает fail-closed compatibility gate между ботом и native API 3x-ui.

## Поддерживаемая версия

Текущий pinned contract:

- 3x-ui: `v3.10.2`;
- upstream repository: `MHSanaei/3x-ui`;
- upstream schema: `frontend/public/openapi.json` из тега `v3.10.2`;
- upstream Git blob SHA: `b50cb368f43bd54583189453ce96ceebc431b2a5`;
- vendored copy: `contracts/3xui/v3.10.0/openapi.json`;
- manifest используемого bot API surface: `contracts/3xui/contract.json`.

**Доказательство идентичности схем:** Git blob `frontend/public/openapi.json` upstream tags `v3.10.0` и `v3.10.2` имеет идентичный SHA `b50cb368f43bd54583189453ce96ceebc431b2a5`. Поэтому существующая vendored copy `contracts/3xui/v3.10.0/openapi.json` **переиспользуется по exact blob SHA**, не копируется под новым именем: route/method/body/Bearer/response surface не изменился. Обновление supported version в manifest не означает совместимость вне использованных 55 API operations или Xray runtime attestation.

**Операторская приёмка 2026-10-16:** Master и direct panels `v3.10.2` установлены по сообщению оператора; rc.15 deployed, A6.1–A6.3 PASS, N6/R3 MATCH, selected scoped Flow POST меняет VLESS без затрагивания AWG/прочих протоколов; также отдельно подтверждён прежний bug #648 «снять тариф → назначить → Тариф + согласование». Это **operator-reported scoped PASS**, не independent read-back установленного binary для каждого VPS и не общий G-11 acceptance. Интеграционные pinned Go+SQLite tests: v3.10.0 UNSAFE для WG-scoped Flow, v3.10.2 SAFE для тестированного случая; точный runtime `panelVersion=3.10.2` guard и fail-closed для других версий **сохраняются**.

Schema берётся из immutable release tag, а не из upstream `main`. CI не скачивает OpenAPI из сети и поэтому не меняет compatibility contract самопроизвольно.

В #663 используется существующий `POST /panel/api/clients/update/{email}` с query-фильтром `inboundIds` по одному Master Inbound ID. Фильтр подтверждён на закреплённом реальном сервисном коде v3.10.0 и временной SQLite ([PR #665](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/665)); OpenAPI surface/method/Bearer/body не меняются. Отсутствие в machine-schema явного описания query-фильтра не подменяет upstream source-parity evidence. Напрямую Node API не изменяется, чтение Node Panel независимо и остаётся только read-only.

При подготовке rc.11 выявлены два edge cases pinned 3x-ui v3.10.0: `ClientRecord.reverse` сериализуется строкой `""` для обычного клиента; `model.Client.flow` использует `omitempty`, поэтому поле Flow выбранного Inbound при `none` может отсутствовать. Scoped editor принимает пустой reverse без преобразования, непустой fail closed; отсутствие Flow у подтверждённого клиента означает `none`. Offline regression не заменяет Node/Xray acceptance.

Начиная с `v4.25.0` bot API surface включает reviewed client-connections routes: `POST /panel/api/clients/ips/{email}`, `POST /panel/api/clients/hwids/{email}` и `DELETE /panel/api/clients/hwids/{email}/{id}`. Текущий manifest содержит **55** endpoints, включая `GET /panel/api/hosts/list` (Issue #422 / PR #424). При переходе `v3.9.0 → v3.10.0` этот используемый surface сохранил route/method, Bearer auth, request body/media/mandatory fields и проверяемый JSON response envelope; runtime client changes для contract parity не потребовались. Новая upstream schema имеет 184 paths; 55/55 используемых operation definitions byte-equivalent по структурному сравнению pinned v3.9.0/v3.10.0. Новые возможности v3.10.0 (MASQUE, XDRIVE, обновлённая Node sync) и изменение неиспользуемых операций не становятся автоматически поддержанными ботом.

При изменении `contracts/3xui/contract.json` или vendored `contracts/3xui/**/openapi.json` Living Docs требует синхронного изменения этого документа в том же PR (`require_all`, без waiver). Изменения API-клиентов `xui.py` / `version_api.py` требуют review документа либо точного обоснованного waiver. Semantic test сверяет количество endpoints с manifest; это не требует обновления pinned upstream версии при расширении уже существующего API surface.

**#663 / multi-protocol fleet follow-up:** У 3x-ui v3.10.0/v3.10.2 общий ClientRecord хранит поля WG/AWG вне VLESS inbound; их присутствие нельзя трактовать как мусор и удалять. Текущий scoped payload из `xui.py` не сериализует эти поля. Для подготовки fix #663 guard может быть условно снят **только при успешной read-only аттестации всей attachment/peer-карты** (`tunnelAllowedIPs` и точный email на каждом tunnel inbound), исключении peer-полей из VLESS payload и доказанном сохранении существующих peer-полей общим upstream service и совпадающем fingerprint; MTProto, reverse, missing/ambiguous связи по-прежнему fail closed. Go/SQLite upstream service integration на v3.10.0/v3.10.2 подтверждает v3.10.0 как UNSAFE для WG и v3.10.2 как SAFE в проверяемом scoped scope; рантайм требует точную `panelVersion=3.10.2` с Master `/panel/api/server/status` и fail-closed для других/неизвестных версий. Этот GET уже входит в контракт; Go/SQLite integration обеих версий является обязательным pre-merge gate, а production Flow POST остаётся запрещённым до отдельного разрешения. Пагинация чтения ограничена 64 нодами, 256 inbound и параллелизмом 8. Новые API endpoints не добавляются; bot API contract теперь pinned v3.10.2 (та же OpenAPI blob); отдельное Go/SQLite и operator-reported runtime evidence получено. Это не снимает точный runtime version guard.

Для #663 безопасные коды `CLIENT_RECORD_MISSING`, `CLIENT_RECORD_NULL`, `CLIENT_RECORD_PROTOCOL_WG`, `CLIENT_RECORD_PROTOCOL_MTPROTO`, `CLIENT_RECORD_PROTOCOL_MIXED`, `CLIENT_RECORD_REVERSE` уточняют причину отказа Master preflight в Telegram. Клиентские поля, структура POST и требования к полноте общего record не меняются; это диагностика без обхода safety checks. Production root cause `CLIENT_RECORD` на rc.12 пока не доказан и требует нового targeted read-only UI наблюдения после отдельно разрешённого Release/deploy.

Для #659 read-only сопоставление Node inbound tags учитывает строго одну native alias-форму `n<node_id>-` в соответствии с закреплённым [upstream v3.10.0 remote tag cache](https://github.com/MHSanaei/3x-ui/blob/v3.10.0/internal/web/runtime/remote.go). API endpoints и schema не меняются. Дубли/коллизии остаются `UNKNOWN`, Node Panel не аттестует работающий Xray. Для #663 отказ preflight теперь выдаёт ограниченный фиксированный код причины, не сырой API response; full-row/identity/membership/nonce проверки, POST и запрет прямого Node write не меняются.

## Что проверяет CI

`python3 scripts/check-3xui-openapi-contract.py` сопоставляет три источника истины:

1. vendored OpenAPI должен иметь exact Git blob SHA pinned upstream schema;
2. каждый endpoint из `contracts/3xui/contract.json` должен существовать с тем же HTTP method;
3. request body semantics, media type и mandatory fields должны совпадать с pinned OpenAPI там, где схема их объявляет;
4. JSON response envelope должен сохранять используемые поля `success`, `msg`, `obj`;
5. API operation должен по-прежнему поддерживать Bearer authentication;
6. AST scan `xui.py` и `version_api.py` должен давать ровно тот же набор panel API routes, что и manifest.

Поэтому новый вызов `/panel/api/...` нельзя тихо добавить в client code: CI потребует одновременно проверить его в pinned OpenAPI и явно добавить в manifest.

Gate также падает, если из новой schema исчезает route/method, меняется обязательность body, media type, набор mandatory request fields или используемый response envelope.

## Почему schema vendored

Network fetch из upstream во время обычного CI запрещён намеренно:

- upstream `main` может измениться независимо от этого проекта;
- transient GitHub/network failure не должен определять совместимость production release;
- review должен видеть schema diff в том же PR, который меняет supported 3x-ui version;
- release должен быть воспроизводимым после публикации.

Vendored OpenAPI не используется runtime-кодом для автоматического переключения API behavior. Это CI/review contract.

## Исключение: `GET /panel/api/server/getDb`

В OpenAPI 3x-ui v3.10.0 этот endpoint по-прежнему описан generic JSON response envelope, тогда как фактический endpoint выдаёт database backup как binary attachment.

Поэтому для `GET /panel/api/server/getDb` OpenAPI gate проверяет route, HTTP method и Bearer auth, но не применяет общий JSON-response-envelope check. Binary download semantics отдельно покрываются runtime regression tests `XUIClient.download_database()`.

Это исключение должно оставаться единственным и явно записано в `documented_exceptions` manifest. Новое ослабление response checks требует отдельного review.

## Как обновлять supported 3x-ui

При переходе на новую версию панели:

1. выбрать конкретный upstream release tag, не ветку `main`;
2. взять `frontend/public/openapi.json` именно из этого tag;
3. добавить новую vendored copy в `contracts/3xui/<version>/openapi.json`;
4. обновить `supported_3xui_version`, upstream ref/blob SHA и schema path в manifest;
5. запустить checker и полный regression suite;
6. разобрать каждый compatibility failure явно:
   - изменённый route/method;
   - новый mandatory field;
   - новый media type;
   - изменённый response contract;
   - новый или удалённый client route;
7. только после review обновить runtime client, если upstream contract действительно изменился;
8. выполнить integration smoke против реальной панели поддерживаемой версии до production acceptance.

Нельзя заставлять checker принимать новую schema удалением endpoint из manifest, если runtime всё ещё вызывает его. Source parity специально блокирует такой обход.

## Переход v3.9.0 → v3.10.0: граница production rollout

Обновление pinned schema в `main` — **CI/contract scope**, не установка панели и не релиз бота. У upstream `v3.10.0` изменены миграции Xray-конфигов (xdns/udpHop/Shadowsocks-2022), systemd sandbox и bundled CA roots; Node sync fixes требуют обновить **все** ноды, не только Master. Для клиентских port hopping/xdns нужен подходящий Xray-core. Preflight: backup с проверяемой restore-совместимостью, фактические версии Master/direct nodes, TLS/CA, custom `ReadWritePaths`, rollout/rollback/STOP и отдельное окно обслуживания. До production перехода необходимы изолированные интеграционные проверки и отдельное разрешение оператора; отсутствие этих evidence означает PENDING, не PASS. [Upstream release](https://github.com/MHSanaei/3x-ui/releases/tag/v3.10.0), [Issue #630](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/630).

## Runtime boundary

Compatibility gate не является runtime service discovery и не добавляет fallback на неизвестные API variants.

Bot продолжает использовать только явно реализованные endpoints. Если установленная панель несовместима с поддерживаемым contract, это должно проявиться как явная ошибка/blocked operation, а не как автоматическое переключение на непроверенную schema.

## Локальная проверка

Проверка запускается из repository checkout на host/CI runner. Каталог `scripts/` намеренно исключён из production Docker image через `.dockerignore`, поэтому checker не является runtime-командой контейнера.

~~~bash
python3 scripts/check-3xui-openapi-contract.py
python -m unittest tests.test_v417_openapi_contract -v
~~~

Успешный checker печатает pinned version, количество покрытых endpoints и upstream blob SHA.


## Offline baseline чтений (#482/#972)

Свежие измерения после #984 дополнительно включают SHA-256 `panel_read_budget.py`: actual read path теперь проходит admission ниже. Driver backlog и transport peak остаются разными метриками; execution latency включает admission wait внутри операции. Исторические raw972/977 отражают прежний source без этого budget и не переписываются. Реальная production queue/latency/capacity по offline fixture не аттестована.

Новая source989 [matrix15](audits/2026-10-28-989-traffic-read-matrix.json)/[driver32x2](audits/2026-10-28-989-traffic-read-concurrency32.json) фиксирует изменившийся adapter SHA-256 и тот же deterministic call/session/byte/peak/owner contract. Source review — [989](audits/2026-10-28-989-traffic-read-source-review.md); historical984/972/977 raw неизменны, timing/CPU/RSS не panel capacity и не доказательство runtime deployment.

**Начиная с RC29: import isolation принята по собственному source-only scope.** #977/#979 Published `4422c8b5f1ff8d8a36343f9ef29becd213caab47`; TYPE_CHECKING изолирует annotation-only checkout/commerce/DB/config graph при сохранённых DTO/errors и actual provider paths. Fresh strict guard/worker/CLI/release17/raw hashes/required1754/image/immutable publication и checkpoint982/main read-back PASS. [Own972 closure](audits/2026-10-28-972-source-tool-closure.md)/[own977 closure](audits/2026-10-28-977-import-repair-closure.md), оба CLOSED/completed; parent482 остальные budget/runtime scopes OPEN. Исторический [RC28 import FAIL](audits/2026-10-28-972-import-isolation-finding.md), исходные metrics/audits/tag неизменны; RC28 tool не считать config-independent.


`scripts/benchmark-panel-reads.py` измеряет существующие `XUIClient.get_client/traffic/clients_list` и `XuiCustomerProvider.traffic` с заменой только HTTP transport. Fixture соответствует потребляемой bot shape, а не обещает исчерпывающую модель upstream. CLI не принимает адрес/токен/config/DB и не импортирует app_runtime; только фиксированные synthetic identities `example.invalid`. В измеряемом scope конструктор socket, DNS и real aiohttp connector запрещены, любые незнакомые method/route/header/TLS варианты завершают case ошибкой. Нет live mode, listeners, mutations или автоматического polling.

```bash
python3 scripts/benchmark-panel-reads.py > /tmp/panel-read-baseline.json
```

Утилиту из текущего Published tag запускать в штатном CPython3.12 environment с hashed dependencies; независимость import graph исправлена начиная с RC29. Поддерживаемые environments измерения — Linux/macOS (`resource.ru_maxrss`); новых dependencies/env/credentials/операторского setup нет. Фикстуры сериализуются до timed phase, для каждого case отдельный subprocess; ошибка/timeout не печатает неполный report. Параметры: до3 уникальных `--clients` (1…10000), до5 `--scenario` из фиксированного списка, `--requests`1…256, `--concurrency`1…32 и не больше числа операций, `--delay-ms`0…20. Дополнительно list work ограничен320000 records/case, worker timeout60s, максимальная матрица15 cases. Raw report содержит timestamp/Python/OS/architecture/logical CPU, Git head/dirty flag и SHA-256 измеряемых файлов.

`operations_per_second`, API calls/sec и p50/p95 — execution в синтетическом driver с включённым tracemalloc, без ожидания в driver backlog; synthetic delay не является измеренной network latency. `driver_initial_backlog` — размер начального остатка после выделения driver workers, не production admission queue. `peak_transport_active`/calls/session counts наблюдаются fake transport; runtime queue NOT_INSTRUMENTED. Timed heap исключает заранее созданные fixtures; process peak RSS включает imports/fixtures/весь worker и нормализован в bytes (macOS bytes/Linux KiB). Не сравнивать эти разные memory scopes и не выводить safe production defaults из fake RPS. Текущий baseline, границы измерений и source hashes сохраняются в [датированном audit](audits/2026-10-28-972-panel-read-baseline.md).

Сам baseline не добавляет общий admission/critical priority, pooling, TTL cache/singleflight или limiter cleanup. Admission выделен в самостоятельный #984; остальные scopes #482 остаются отдельно. Все paid/entitlement/quota/provisioning/post-mutation reads authoritative; утилита их не исполняет и не меняет TLS/Bearer/no-blind-retry/mutation semantics. Реальная capacity/health и собственный deployment scope #482 отложены; Telegram burst/CPU Xray не измеряются.

## Отказ клиентского чтения трафика (#989)

Source [#990](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/990) и checkpoint991 MERGED; #989 впервые Published в RC31, [publication checkpoint](audits/2026-10-28-rc31-publication-checkpoint.md). Required/full descendant CI/source5 hashes/fresh release image scoped PASS; старый990 main metadata FAIL сохранён исторически и исправлен991. Собственный installed/read R989-01 PENDING, current Published/Deployed/Accepted — [Roadmap](ROADMAP.md).

`XuiCustomerProvider.traffic()` сохраняет два существующих адресных reads: `get_client(email)` и `traffic(email)`. Native `aiohttp.ClientError`, timeout, `OSError`, некорректная mapping shape и ожидаемая ошибка преобразования counters (TypeError/ValueError/OverflowError) дают постоянный обезличенный `CustomerProviderUnavailable`. Raw response/endpoint/owner/error message не включается в сообщение или обычный formatted traceback. Cancellation не перехватывается; неожиданный programming RuntimeError не скрывается общим `except Exception`.

Сначала проверяются object/client mappings, затем traffic mapping и прежние int conversions. Nested/direct client records, `up/down` и `uplink/downlink`, действительные нули и прежние missing-counter defaults совместимы; native failure или повреждённый ответ не превращаются в успешный нулевой DTO. Новых reads/retries/fallback/cache нет. Devices inventory уже имеет transport normalization и сохраняет независимый unknown limit; mutation/no-replay, auth/TLS/admission и authoritative postconditions не меняются.

Existing server-owned CustomerPortalService profile/private/allowlist/SQL ownership и UI temporary-unavailable/Back сохраняются. Error paths и session/admission cleanup проверяются offline; [поздний installed/read outcome](CLIENT_SETUP.md#отказ-чтения-клиентского-трафика-989) требует отдельного deployment. Source/release state — [Roadmap](ROADMAP.md), no live failure/load или искусственной недоступности ради проверки.

## Ограничение panel reads (#984, часть #482)

Фактические Merged/Published/Deployed/Accepted — только в [Roadmap](ROADMAP.md). #984 впервые Published в RC30; [publication checkpoint](audits/2026-10-28-rc30-publication-checkpoint.md), собственный installed/read acceptance PENDING. `panel_read_budget.py` не импортирует config/app_runtime и не создаёт tasks/network/listeners/sessions. В поддерживаемом single-loop bot runtime все XUIClient instances одного canonical configured endpoint делят budget: максимум8 active, ordinary максимум6, общая очередь32 и admission wait1s. Два свободных места зарезервированы для critical reads, critical могут занять все8; critical FIFO раньше ordinary FIFO. Постоянная critical нагрузка может дать ordinary timeout; это temporary unavailable, не stale success. HTTP timeout20s и binary60s отдельно, очередь не увеличивает transport deadline. Caps — инженерная защита, не измеренная безопасная мощность панели; несколько processes/loops не образуют distributed общий лимит.

| Source limit | Значение |
| --- | --- |
| `MAX_ACTIVE` | 8 |
| `MAX_NORMAL_ACTIVE` | 6 |
| `MAX_WAITERS` | 32 |
| `WAIT_SECONDS` | 1.0 |
| `MAX_TARGETS` | 64 |

Wait deadline обслуживается event loop и проверяется до grant. Синхронная CPU-пауза процесса не preemptится этим механизмом; 1s не является wall-clock SLA для заблокированного loop или всей цепочки UI/API calls.

Canonical key нормализует scheme/host/IDNA/IP/default port/base path и не разделяется по token/TLS/userinfo/query/fragment. Это только объединение admission counters, не URL validation, authorization, credential/session/response cache или fallback между privilege domains. Реестр ограничен64 занятыми/ожидающими targets на loop; idle leases снимаются даже при сохранённом exception traceback, weak references не удерживают завершённые loops. Диагностика содержит только aggregate counters, без endpoint/owner/token/payload.

Общий `_request` включает существующие GET/read-only POST diagnostics; version GET и binary getDb тоже берут permit до ClientSession. Очередь полна/timeout/registry cap дают sanitized `XUIReadUnavailable` (подкласс XUIError) либо definitive read `VersionAPIError` без HTTP/retry. Внутренние legacy options→list/node-list→detail fallbacks не запускаются на admission denial; provisioning preflight не превращает такой отказ в пустую node map. Cancellation остаётся CancelledError; grant/cancel race возвращает permit один раз. Session close/JSON/transport errors также освобождают lease. `_mutation_request` и version mutations не используют read budget; прежние one-shot/redirect/uncertainty contracts сохраняются. Direct Admin/Host/Fleet/proxy остаются отдельными контурами; этот budget не заявляет охват их transport.

Critical context выставляет сервер вокруг `ProvisioningEngine` initial/uncertain/final authoritative get_client, только для текущего asyncio Task. Входные email/Telegram/HTTP данные не выбирают priority, child/background tasks её не наследуют. Priority не даёт права mutation, stale cache не применяется. Начальный отказ прекращает sync до writes; недоказанный final/uncertain readback после mutation остаётся `ProvisioningUnknown`/mutation_not_retried, без replay. Pooling, TTL cache/singleflight, общие traffic transport errors, limiter cleanup и остальные parent482 outcomes — отдельные scopes.
