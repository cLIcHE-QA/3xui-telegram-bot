# #482-A / #972 — полностью offline baseline чтений panel API

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-28 09:45 UTC+03:00
- **Окружение:** локальный CPython3.12.10, Darwin25.6.0/arm64, 8 logical CPU; отдельный свежий process на каждый synthetic case, fake transport, без sockets/DNS/DB/production операций
- **Цель:** измерить source/bot JSON cost и request fan-out до изменения global API budget, не подменять гипотезу CPU Xray реальным наблюдением.
- **Версия и immutable tag/SHA:** текущий Published v5.0.0-rc.27 `bd271d583386c13c628899b7e42f550eabe7d6e6`; base main checkpoint #971 `c30dee4f8e4683b3a8e076ff3ac78510575d7565`; измеряемая implementation branch `1bed2ba24491df6a3f99d0f88e06866a2380ff8e` (ещё не merged), runtime files unchanged.
- **Scope:** текущие XUIClient GET get/traffic/list и XuiCustomerProvider traffic same/unique owner; bounded fake JSON fixtures, driver concurrency, request/session counts, execution latency/RPS, CPU/Python heap/process RSS. Не TLS/network/3x-ui/Xray/server CPU/real deployment capacity, не полноценная RBAC/платёжная или production API проверка.
- **Фактический результат:** PASS
- **Источник и evidence:** [исходная матрица15 cases](2026-10-28-972-panel-read-baseline-matrix.json), [два concurrency32 cases](2026-10-28-972-panel-read-baseline-concurrency32.json), source `scripts/benchmark-panel-reads.py`, targeted regression `tests/test_panel_read_baseline_972.py` (10 tests PASS за0.794s); [Issue #972](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/972), parent #482. Timestamp raw default matrix 2026-10-28T06:41:40.990799Z; оба reports содержат exact source SHA/file hashes и measured_files_dirty=false.
- **Ограничения и остаточные риски:** fixture сериализация/imports исключены из timed phase, timed tracing включён; RSS lifetime worker включает fixtures/imports, heap их исключает. Нет production admission/cache/singleflight/pooling/limiter изменений. Source-tool full/required CI/merge/RC/publication ещё PENDING на этом snapshot; parent482 runtime acceptance не выполнен.
- **Связанные Issues:** #972, #482
- **Решение по Issues:** #972: keep_open, #482: keep_open
- **Следующий шаг:** полный repository/required CI и review source-tool; merge/independent main/source checkpoint, отдельный RC28/publication/own closure #972. Затем определить следующий самостоятельный read admission/lifecycle scope #482 по baseline; live load не требуется для разработки.
- **Раздельные состояния:** merged=предыдущий publication checkpoint #971, source972 branch ещё не merged; published=RC27 `bd271d583386c13c628899b7e42f550eabe7d6e6`, RC28 PENDING; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15, independent VPS read-back PENDING; accepted=offline baseline scoped PASS, source-tool publication/full parent runtime PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## Методика / воспроизводимость

До этого scope #971 required Python40644030986/final title40644585075 SUCCESS, actual CLEAN/squash/main read-back подтверждены. Последующий main40644673123/job122670592802 SUCCESS (1741/3 skips,265.657s) и idempotent publisher40645277943 SUCCESS; самостоятельные #876/#966 остаются OPEN. Поиск дубликатов benchmark/offline/budget не нашёл отдельной задачи кроме родительской482; child972 создан до кода, parent scope сохранён.

Запуск в штатном hashed CPython3.12 environment:

```bash
python scripts/benchmark-panel-reads.py > /tmp/panel-read-baseline.json
python scripts/benchmark-panel-reads.py --clients 1000 --scenario traffic_same traffic_unique --requests 64 --concurrency 32 --delay-ms 2 > /tmp/panel-read-baseline-concurrency32.json
```

Первый запуск: fixture clients1/1000/10000, пять сценариев,32 operations/case, driver8, synthetic delay1ms/HTTP call; пятнадцать последовательных изолированных workers. Второй: два сценария,64 operations/case/driver32/2ms, также последовательные workers. `driver_initial_backlog`24 или32 — начальный остаток после выделения workers, не измеренная production queue. Execution latency исключает ожидание в этом backlog. `api_calls_per_second` и `operations_per_second` относятся только к fake transport с включённым tracing/synthetic delay, не к реальной панели.

Source provenance в обоих raw reports: Git head `1bed2ba24491df6a3f99d0f88e06866a2380ff8e`, все измеряемые файлы clean. SHA-256:

- xui.py: `97c2095325ce831e5620eb085bd93c759dfbf2d4fbddcd968a06cc1f6621457f`;
- customer_provider_xui.py: `b1c906a35a61222f5e9c7e1213a80fdabf00027f4b1f6115eb055c9c9273cbcf`;
- customer_service.py: `4dc803fc11c6cc183c70a09b1980ba74bbb4d6f5859223fa133d685c55f6eda0`;
- benchmark script: `bcddc94b8c668f5d74aa240cd8371cdae058b904588580d7ede7da44a6f19dc2`.

## Измеренный результат

Ниже32 operations/driver8/1ms; bytes — сумма JSON по всем API calls, CPU — process time timed phase, heap/RSS — bytes разных явно указанных scopes. Метрики округлены; точные значения/RPS/p50/wall/environment — в raw reports.

| Сценарий | Fixture clients | Calls / sessions | JSON bytes | p95 ms | CPU s | Timed heap peak | Process peak RSS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| get | 10000 | 32 / 32 | 5088 | 1.468 | 0.003 | 229940 | 57835520 |
| traffic | 10000 | 32 / 32 | 1664 | 1.434 | 0.003 | 225602 | 57622528 |
| list | 1 | 32 / 32 | 5472 | 1.508 | 0.003 | 196034 | 42139648 |
| list | 1000 | 32 / 32 | 4704768 | 53.925 | 0.214 | 815926 | 46792704 |
| list | 10000 | 32 / 32 | 47040768 | 528.913 | 2.102 | 6419288 | 83689472 |
| traffic_same | 1000 | 64 / 64 | 6752 | 2.760 | 0.006 | 315866 | 44171264 |
| traffic_unique | 1000 | 64 / 64 | 6752 | 2.831 | 0.006 | 316018 | 43368448 |

Все case полностью завершились, session count=closed count; peak transport active8. При driver32 и64 operations same/unique дали по128 API calls/128 sessions и peak32, без дедупликации: по64 GET get и traffic,13504 JSON bytes. Initial backlog32, p95 5.300/5.363ms, timed CPU0.009/0.010s. Fake operations/sec5545.687/5428.444 и API calls/sec11091.374/10856.889 явно не являются production limits.

Результат подтверждает измеренный source fan-out: по два адресных GET на каждый traffic запрос даже для одного owner. Full list объём растёт с числом записей; targeted get/traffic JSON size в этих fixtures не зависит от общей list cardinality. `XUIClient` создаёт session на каждый call; допущенный driver32 наблюдает32 одновременных fake requests. Из этого нельзя вывести отсутствие любых иных production ограничений или загрузку Xray; в проверяемом XUIClient path общего admission нет по static review. В этой задаче safe production thresholds не выбирались.

## Security / regression / оставшийся scope

Tool не принимает live URL/token/env/config/DB, использует только synthetic example.invalid identities и проверяет exact GET/route/header/TLS contract. Внутри измерения patched socket constructor/DNS/real connector отказывают даже при непредвиденном network path. Mutation/foreign URL/owner/token/TLS варианты отклонены regression; cancellation/JSON failure закрывают contexts, отменяют siblings, восстанавливают transport и tracemalloc, не печатают частичный report. Матрица/fixture/driver/decoding work/worker deadline bounded. Отдельный CLI test без application environment подтверждает отсутствие зависимости от production config.

Десять targeted tests проверяют observable counts/response scaling/negative transport/CLI bounds/cleanup, без flaky time/RPS порогов. CPU/tracing/fixture effects явно отмечены; benchmark не меняет auth/ownership/TLS/mutation retry/storage. Полный suite и required CI выполняются отдельно после документации; этот timestamp не объявляет их будущий результат.

#972 keep_open до собственного full/required/source checkpoint/immutable RC/publication. Его source-only acceptance не требует VPS/live smoke, parent #482 остаётся OPEN. Ближайший runtime scope должен отдельно определить bounded per-panel process admission, critical authoritative reads и session shutdown; presentation cache/singleflight, traffic transport normalization, limiter cleanup и настоящие operator outcomes не включены в baseline PASS. #498 не выпускается без необходимых budget/authoritative guarantees.
