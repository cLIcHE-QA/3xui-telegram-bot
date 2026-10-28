# #977 — source revalidation type-only import repair

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-28 11:08 UTC+03:00
- **Окружение:** локальный CPython3.12.10/Darwin25.6.0/arm64/8CPU, fresh subprocesses с deny-import finder и без application environment, bounded fake transport; без production операций
- **Цель:** устранить source no-config criterion1 FAIL #972 без подмены provider/config, переноса DTO/errors или изменения доменных методов.
- **Версия и immutable tag/SHA:** исправленный source branch `74ac8932a2fe2253e4fb8b31bda762b72f20bfcf`, APP_VERSION5.0.0-rc.28; Published RC28 `fad1fe6641f8fe190bd810ff51e04d91062c7ac7` остаётся с import defect, fix RC29 PENDING.
- **Scope:** минимальный TYPE_CHECKING import repair, pre/post-fix fresh-process guards, DTO/error identity/service injection/actual worker/CLI, новый actual source baseline и неизменность non-import definitions/constants. Не merged/published fix и не runtime API budget/production outcome.
- **Фактический результат:** PASS
- **Источник и evidence:** [Issue #977](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/977), [finding audit](2026-10-28-972-import-isolation-finding.md), finding checkpoint [#978](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/978) main `b6f8d1791e634fabcaab31e5cb5c5d0076e1b9f8`/independent read-back до кода. Новые tests/test_panel_read_import_isolation_977.py до fix:3 failures за0.426s, отказ checkout_service import до config execution; после fix targeted17 PASS1.648s. [Новая матрица15](2026-10-28-977-import-boundary-revalidation-matrix.json), [concurrency32 cases2](2026-10-28-977-import-boundary-revalidation-concurrency32.json): actual raw metrics/source hashes, clean measured source, measured_at2026-10-28T08:01:49.309986Z.
- **Ограничения и остаточные риски:** full suite/required CI/source merge/main/image/fix RC29/publication/own closure ещё PENDING на snapshot. Новый customer_service source hash не byte-identical RC28; старые snapshots не переписаны. Published RC28 import acceptance по-прежнему FAIL, #972/#977 OPEN; parent482 остальные budget/runtime scopes не реализованы.
- **Связанные Issues:** #977, #972, #482
- **Решение по Issues:** #977: keep_open, #972: keep_open, #482: keep_open
- **Следующий шаг:** full repository/required checks, source review/merge/main checkpoint, fresh image/immutable RC29/publication и собственные977/972 audits/closure read-back; parent482 остаётся OPEN, следующий admission/lifecycle scope после checkpoints.
- **Раздельные состояния:** merged=finding978, code977 branch не merged; published=RC28 `fad1fe6641f8fe190bd810ff51e04d91062c7ac7`, исправленный RC29 PENDING; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15, independent VPS read-back PENDING; accepted=source guard/targeted/metrics scoped PASS, Published28 import gate FAIL/fix publication PENDING, parent runtime/G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## Минимальный import change / сохранённые identities

В customer_service.py изменено только исполнение imports: CheckoutService/CheckoutSession/CommerceService/CommerceOrderRecord/Database/PlanRecord находятся под TYPE_CHECKING, future annotations уже существовали. Все module-level domain class/function/constant AST definitions до/после совпадают. По repository не найдено runtime get_type_hints или использования этих annotation names как customer_service exports. Настоящий production entrypoint продолжает собственную конфигурацию; provider/DTO слой её больше не загружает ради annotations.

Ни один DTO/error class не перенесён и не скопирован. Fresh guarded process проверяет семь exact adapter/service aliases и __module__=customer_service; CustomerTraffic equality/shape, error identity и создание CustomerPortalService с injected dependencies сохранились. Config stub/AST extraction/exec provider не используются; выполняется настоящий XUIClient/XuiCustomerProvider path с прежней fake HTTP transport заменой только в benchmark.

## Отрицательная проверка до чтения config

До source fix те же новые три tests предсказуемо дали failures=3: MetaPathFinder установлен до benchmark/provider module load и запрещает config/app_runtime/provisioning/checkout_service/commerce/db/dotenv imports. Первый отказ checkout_service останавливает цепь **до config execution**, поэтому pre-fix proof не требует dotenv lookup или реальных env contents. После fix fresh import, actual provider worker и parent CLI matrix проходят; blocked modules отсутствуют в sys.modules, DTO/error aliases совпадают. Значения env/конфигурации не инспектируются и не выводятся, network/Bot/DB не запускаются.

Existing benchmark10 и customer-service boundary4 вместе с новыми3 — targeted17 PASS. Предыдущий empty-env тест остаётся полезным CLI check, но строгая isolation теперь доказывается отдельным deny-import gate, а не предположением. Published RC28 не объявляется исправленным до нового tag.

## Новый source baseline

Обе новые матрицы выполнены после source commit74ac893, measured_files_dirty=false. Из четырёх measured files изменился только customer_service SHA-256: `ae9dbe78c368900ab77c8646dbaf6c4628422d989647afaf86cb0aaf4eb8735b`; xui/provider/benchmark hashes прежние. Исходные RC28 customer_service hash/metrics сохранены исторически, этот snapshot их не заменяет.

Все15 основных cases сохраняют exact scenario/volume/operations/calls/routes/session count/closed count/JSON bytes/peak transport/backlog относительно первой матрицы. Дополнительные same/unique owner driver32 cases завершаются по128 API calls/128 closed sessions, без singleflight/cache. Реальная panel/Xray capacity не измеряется. Изменение импортного startup и вариация timings не используются как production performance claim.

Пример новой32-operation/driver8/1ms матрицы: get10000 —32 calls/5088 JSON bytes; traffic10000 —32/1664; list10000 —32/47040768, p95546.375ms/CPU2.182s/timed heap6464328 bytes/process RSS82886656 bytes; same/unique1000 —64 calls/6752 bytes. Полные p50/p95/wall/RPS/CPU/heap/RSS/environment — в raw files. Timed heap исключает заранее созданные fixtures, RSS включает imports/fixtures; driver backlog не production queue. Synthetic delay/tracemalloc остаются частью методики, safe server thresholds не выбирались.

## Own acceptance / дальнейшие gates

Source criteria977 import guard/type-only usage/identity/regression/raw provenance scoped PASS. Full/required checks и source/main/image/immutable fix RC/publication ещё должны быть доказаны; затем отдельно перечитываются criteria972, включая уже пойманный criterion1. Оба keep_open до собственных outcomes; VPS/live smoke N/A по их source/import scopes. Parent482 admission/critical priority/session pooling/cache/authoritative/error/limiter/runtime acceptance этим не закрывается. Исторический FAIL сохранён, критерии/thresholds/waivers не ослаблены.
