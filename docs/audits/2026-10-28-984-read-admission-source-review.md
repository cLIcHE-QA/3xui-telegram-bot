# #984 — source admission/critical priority и actual offline remeasurement

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-28 16:07 UTC+03:00
- **Окружение:** clean tracked Git checkout CPython3.12.10/Darwin25.6.0/arm64/8CPU, synthetic empty .env, fake transport/socket-DNS denial; без production операций
- **Цель:** ограничить source read fan-out общей admission, сохранить authoritative priority/postconditions и проверить все bounds/cleanup без вывода server capacity из fake RPS.
- **Версия и immutable tag/SHA:** source branch `68c4c2d07b1c2d12ef0345a9ed9a78e614b82f64`, APP_VERSION5.0.0-rc.29; actual Published RC29 `4422c8b5f1ff8d8a36343f9ef29becd213caab47` ещё не включает984, новый RC30 плановый до release-prep.
- **Scope:** per-loop/configured-target bounded admission/common+versionGET+binary reads, trusted same-task provisioning priority, no legacy fallback на admission denial, unknown/no-replay, new actual source hashes/metrics и regression/security review. Не session pooling/cache/все privilege domains/полный parent482, не server capacity/deployment/runtime acceptance.
- **Фактический результат:** PASS
- **Источник и evidence:** [Issue984](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/984) создан до кода/после duplicate search; source68c4c2d. New tests/test_panel_read_admission_984.py16 tests + existing import/baseline/provisioning/mutation suites: targeted52 PASS1.769s. Clean full1771/16 environment skips PASS92.245s на source68c4c2d; compileall/OpenAPI55/diff PASS. [Матрица15](2026-10-28-984-read-admission-matrix.json), [driver32 cases2](2026-10-28-984-read-admission-concurrency32.json), measured_at2026-10-28T13:03:38.522842+00:00, clean5 measured files/source hashes.
- **Ограничения и остаточные риски:** required CI/source merge/main/image/release-scope/RC30/publication ещё PENDING. Собственный installed/read runtime outcome984 после отдельно разрешённого deployment PENDING, child keep_open. Parent482 pooling/cache/authoritative/общие traffic errors/limiter/runtime scopes OPEN. Caps не server SLA, multiple loops/processes не distributed cap; synchronous CPU pause не preemptится asyncio wait deadline. Deployed18.10/schema15 operator-reported/independent VPS PENDING; G-11 PARTIAL/NO-GO/public rollout BLOCKED.
- **Связанные Issues:** #984, #482
- **Решение по Issues:** #984: keep_open, #482: keep_open
- **Следующий шаг:** required CI/review/merge/independent main/source checkpoint и fresh source image; затем отдельный release-prep RC30/scope/health/automatic publication/main checkpoint. Runtime984 не закрывать по одному CI, следующие независимые child scopes482 после checkpoints.
- **Раздельные состояния:** merged=предыдущий closure983 `4420b829690e6eaeac2d179a5d18128fad02be76`, source984 branch ещё не merged; published=RC29 `4422c8b5f1ff8d8a36343f9ef29becd213caab47` без984; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15/independent VPS PENDING; accepted=source52/full1771/metrics/security scoped PASS, runtime984/parent482/G-11 PENDING/PARTIAL/public rollout BLOCKED.

## Issue-first и сохранение предыдущих checkpoints

Перед984 источник — actual GitHub main983, its required Python40687457590/final title40688235042 SUCCESS/actual CLEAN; independent main/Issue/Roadmap/registry/read-back12:30:35Z и immutable RC29 read-back12:30:45Z PASS. Main40688352541/job122816470163 SUCCESS1754/3, idempotent publisher40689038372 SUCCESS до создания984. Own972/977 CLOSED/completed, parent482 OPEN; исходные audits/RC28 FAIL и закрытые source criteria не переписаны. GitHub search admission/read budget не нашёл отдельного дубликата.

Source984 не запускает production Bot/listeners/HTTP/DB operations. Full suite использует штатные isolated regression fixtures, synthetic settings и пустую .env в отдельном clean Git checkout; исходные ignored env/данные не копировались и не выводились. Новых deps/DDL/env/ports/credentials/flags нет. Обнаруженная при review устаревшая current Published28 projection в V5_PRODUCTION_ACCEPTANCE синхронизирована с actual29; это исправление факта, не новое deployment evidence.

## Admission и trust boundary

В одном поддерживаемом asyncio loop все XUI instances canonical configured endpoint (scheme/host case/IDNA/IP/default port/base path) делят8 grants/normal<=6/waiters<=32/wait1s, максимум64 simultaneously held targets. Token/TLS/userinfo/query/fragment не создают bypass key и не передаются другим клиентам; credentials/responses/sessions не кешируются. Ключи hash-only, process-internal snapshot aggregate-only, не endpoint/owner/token/payload. Этот key не заменяет существующую URL validation/SSRF/auth политику, неизвестный endpoint не становится authorized.

Weak registry не держит idle budgets/завершённые loops. На последнем release idle key удаляется даже если caller хранит exception traceback; тест удерживает65 таких errors, active/targets остаются0. Отдельно проверены64 реально занятых synthetic targets, fail-closed65-й и освобождение. Очередь bounded до Future creation для overflow; FIFO critical прежде normal, reserved2 не занимают ordinary reads. Under constant critical load ordinary может получить timeout; это документированный temporary unavailable. Wait deadline cooperative: проверяется до grant, не обещает wall-clock preemption заблокированного Python loop или общий UI SLA.

Critical context задаётся кодом ProvisioningEngine только вокруг initial/uncertain/final get_client; email/Telegram/HTTP payload не задаёт priority. Owner — exact current Task, child/background task даже с inherited ContextVar остаётся ordinary; nested scope/reset проверены. Это availability reservation, не новая auth capability; общий8/queue32 не обходится. Начальный отказ не делает writes, uncertain/final недоказанный readback остаётся ProvisioningUnknown/mutation_not_retried. Проверены XUIError/ClientConnectionError/Timeout/OSError, ровно одна fake mutation и отсутствие локального expiry commit/replay.

Общий_request/read-only POST, version GET и binarygetDb берут permit до ClientSession; HTTP20s/binary60s/headers/TLS/response semantics прежние. Admission denial — XUIReadUnavailable(XUIError) или definitive read VersionAPIError. При substantive review найден старый generic XUIError fallback options→list/node-list→detail и empty provisioning node map: typed denial теперь проходит мимо этих fallbacks, новый test доказывает ровно один attempted read и preflight failure. Другие уже подтверждённые API errors сохраняют старую compatibility policy. XUI._mutation_request class method AST byte-equivalent actual main983 (кроме расположения в файле); version non-GET использует nullcontext, one-shot/no redirects/uncertainty tests PASS. Budget не превращается в shared session, SSH gateway, Direct Admin/Host/Fleet/proxy fallback или provider writes.

## Проверки и честная история

Первый targeted49 PASS1.916s до дополнительного canonicalization/idle traceback hardening. Source63a1 targeted51 имел1 regression failure: provenance report теперь5 measured files, старый strict expected set был4. В том же scope test явно обновлён до точного5 и проверяет actual SHA-256 каждого файла; guard/shape/counts не ослаблены. Source5cc6 targeted51 PASS1.749s/full1770/16 PASS92.959s. После typed no-fallback hardening source68c4 targeted52 PASS1.769s и полный1771/16 PASS92.245s. Это разные exact source snapshots, старый результат не выдаётся за проверку нового кода.

Новые16 source tests проверяют observable bounds/FIFO/reserve/cancel-after-grant/timeout/expired grant/weak lifecycle/retained tracebacks/canonical aliases/task context/all3 read families/legacy-denial/no-mutation-replay. Delays/RPS не зашиты в flaky thresholds; scheduling barriers и fake transport вместо реального сервера. Existing strict no-config977 и baseline972 также PASS, DTO/error aliases и actual provider paths сохранены. Новый общий living-doc invariant сверяет canonical table caps с AST constants без frozen version/Issue number. Дополнительный required CI ещё должен подтвердить собственный final metadata head.

## Actual offline remeasurement

Обе матрицы измерены последовательно после full suite, без concurrent test load. Default15: clients1/1000/10000, get/traffic/list/same+unique,32ops/driver8/1ms fake delay. Extra2: clients1000/same+unique/64ops/driver32/2ms. Измерение выполняет настоящий XUI/provider path с admission, заменён только HTTP transport; no-config/route/method/owner/token/TLS/socket/DNS guards прежние.

Все17 cases завершены: calls/sessions/closed/response JSON counts совпали с corrected977 baseline, cache/singleflight нет. Transport peak теперь6 вместо прежнего8/32, driver peak8/32 и initial backlog24/32 прежние. Latency внутри operation включает новое admission wait, driver backlog по-прежнему не входит; production queue NOT_INSTRUMENTED, реальная capacity/Xray CPU не измерялась. CPU/heap/RSS/provenance/limits явно разделены, session на call прежняя.

| Сценарий | Clients | Calls/closed | JSON bytes | Driver/transport peak | p95 ms | CPU s | Timed heap bytes | Process RSS bytes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| get | 10000 | 32/32 | 5088 | 8/6 | 5.657 | 0.0134 | 376099 | 55902208 |
| traffic | 10000 | 32/32 | 1664 | 8/6 | 5.094 | 0.0127 | 372617 | 55885824 |
| list | 10000 | 32/32 | 47040768 | 8/6 | 543.167 | 1.9518 | 6559623 | 80805888 |
| traffic_same | 10000 | 64/64 | 6752 | 8/6 | 7.333 | 0.0175 | 376185 | 55885824 |
| traffic_unique | 10000 | 64/64 | 6752 | 8/6 | 7.385 | 0.0181 | 376185 | 55885824 |
| traffic_same driver32 | 1000 | 128/128 | 13504 | 32/6 | 34.939 | 0.0242 | 617805 | 42516480 |
| traffic_unique driver32 | 1000 | 128/128 | 13504 | 32/6 | 34.977 | 0.0239 | 618099 | 42516480 |

Exact measured SHA-256:

- customer_provider_xui.py: `b1c906a35a61222f5e9c7e1213a80fdabf00027f4b1f6115eb055c9c9273cbcf`;
- customer_service.py: `ae9dbe78c368900ab77c8646dbaf6c4628422d989647afaf86cb0aaf4eb8735b`;
- panel_read_budget.py: `90ef608ca5ebb05e3342846fdc55d5bf3def53a58092580199fc7b1419f907e5`;
- scripts/benchmark-panel-reads.py: `839ba3c52fc2e4860b7793428618e6f68aa828bbd279c9450622aa578a6fcb1f`;
- xui.py: `6047f76e37303a81a8bfd7d8eb2f87703319898f2a369971c5a5bdcea1d6a173`;

Timed heap исключает подготовленные fixtures, process RSS включает imports/fixtures/worker lifetime; raw values в bytes (Darwin), wall/CPU/RPS — только local fake workload с tracing. Этот outcome не разрешает live load/burst или новые defaults на основе измеренной panel capacity. Все original972/977 raw/audits неизменны.

## Own runtime и следующий scope

#984 keep_open: source/CI/main/image/immutable RC/publication отдельны от installed runtime outcome. После отдельного deployment только собственные R984-01…03 из CLIENT_SETUP: exact installed tag/SHA/caps/health, естественные read-only client/admin paths и уже имеющийся authoritative outcome. Нет нового natural outcome — соответствующий пункт PENDING; не создавать Stars/provisioning/reconcile/mutation или production load ради полноты. G-11 и прежние HWID scoped PASS/waived burst не пересматриваются.

Parent482 keep_open: pooling/lifecycle, presentation-only bounded cache/singleflight/authoritative bypass, общие traffic errors/limiter memory/прочие operator outcomes отдельно. #498 не включается по fake RPS или одному admission module. Следующая самостоятельная задача — после source/main/release/publication checkpoints текущей984.
