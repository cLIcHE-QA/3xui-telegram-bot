# #972 / #482-A — implementation/main checkpoint offline baseline

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-28 09:57 UTC+03:00
- **Окружение:** GitHub / CI / локальные offline reports и immutable main source read-back; без production операций
- **Цель:** подтвердить source merge/required CI/измеряемые hashes/security для первого самостоятельного #482-A перед отдельным RC28.
- **Версия и immutable tag/SHA:** source main `5564bf1cf52f6666e0dc74860b086e35fd2f3ec6`, APP_VERSION5.0.0-rc.27; Published RC27 `bd271d583386c13c628899b7e42f550eabe7d6e6`, RC28 ещё не подготовлен/Published.
- **Scope:** merge exact implementation head, offline source measurements, source regression/required checks, неизменность runtime files, fresh main image/security, собственные Issue criteria. Не реальная API/Xray capacity и не runtime budget/acceptance всего parent482.
- **Фактический результат:** PASS
- **Источник и evidence:** [#973](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/973) exact head `aea450afef0e2a8e3e6f2a9e65aec4845b33cd5c`, squash `5564bf1cf52f6666e0dc74860b086e35fd2f3ec6`, MERGED2026-10-28T06:55:24Z. [Python40646152895](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40646152895)/job122675327553 SUCCESS (1751 tests/3 skips,177.248s), [final title40646720556](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40646720556)/job122677134314 SUCCESS; actual CLEAN до squash. [Baseline/raw reports](2026-10-28-972-panel-read-baseline.md) и independently fetched main file hashes совпадают. Fresh [Supply-chain40646878603](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40646878603)/job122677641033 SUCCESS. Main Python40646826288/job122677466787 PENDING на snapshot09:57; PR PASS не подменяет push outcome.
- **Ограничения и остаточные риски:** implementation checkpoint CI/merge/read-back и RC28/publication/own closure ещё PENDING. Fake transport/tracing/driver metrics не real network/server limits; runtime files/auth/TLS/mutations/cache/lifecycle прежние. Parent482 admission/critical priority/pooling/cache/authoritative/errors/limiter/runtime scopes не выполнены. Deployed не менялся, G-11 PARTIAL/NO-GO/public rollout BLOCKED.
- **Связанные Issues:** #972, #482
- **Решение по Issues:** #972: keep_open, #482: keep_open
- **Следующий шаг:** required CI/merge/independent main read-back этого source checkpoint; отдельный release-prep RC28 с #973 в release-scope/CHANGELOG, health/automatic publication и собственный closure checkpoint #972. Затем новый самостоятельный runtime scope482, без live load.
- **Раздельные состояния:** merged=#973; published=RC27 `bd271d583386c13c628899b7e42f550eabe7d6e6`, RC28 PENDING; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15, independent VPS read-back PENDING; accepted=offline/source/required PR/image scoped PASS, source-tool publication/parent runtime PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## Измерения / исходники

Две raw матрицы сохраняют17 последовательных isolated cases с Git head `1bed2ba24491df6a3f99d0f88e06866a2380ff8e`, measured_files_dirty=false и четырьмя file SHA-256. После squash checked-out source main независимо сравнен с каждым hash; все совпали. xui.py/customer_provider_xui.py/customer_service.py byte-unchanged относительно base main `c30dee4f8e4683b3a8e076ff3ac78510575d7565`. Документация измерений не переписана задним числом: branch provenance остаётся исходной, этот checkpoint добавляет main equivalence.

Targeted10 PASS0.794s; local full1751/16 environment skips PASS94.221s; compileall/OpenAPI55/catalog/living/language/semantics/governance/diff PASS. Independent GitHub reconciliation до merge: Published27/ref78/assert41/active41 PASS. Нормальные get/traffic/list shapes, same/unique fan-out, client isolation на fixture routing, known mutation/URL/header/TLS denial, socket guard, cleanup/error/cancellation и bounded CLI проверены без сетевых operations. Не заявлены UI/RBAC/payments/production guarantees по fake benchmark.

## Source/security review

Source-tool не регистрируется в runtime, slash-командах, jobs или listeners. Нет URL/token/config/DB/live input и shell subprocess; command/worker matrix bounded, socket/DNS/connector fail closed, report только после полного успеха. Нет новых deps/base/actions/permissions, provider data/header payload не выводится. Это фактический trust-boundary review; зелёный CI сам по себе не доказывает отсутствие live path.

Manual fresh main Supply-chain нужен для точного source/image evidence, автоматический paths trigger не менялся. Artifact12798191742, digest `sha256:4fe00ef21e4739669fee8332775746e91adef5fc4c0ea744dca037666f4f62af`, скачан независимо: metadata.source_sha совпал с source main, lock digest совпал с unchanged requirements.lock; container SBOM dnspython2.9.0/ISC, fs/image actionable HIGH/CRITICAL0. Hashed install/scanner/license/image/SBOM/gate/upload SUCCESS. Historical #966 FAIL сохраняется; пороги/ignores/waivers не менялись.

## Own acceptance audit

Перечитаны шесть критериев #972: фактические XUIClient/provider paths с fake transport/no config/live input; bounded matrix/shapes/same/unique counts; реальные локальные metrics/provenance и ограничения; negative/cleanup regressions; canonical docs/датированный audit/unchanged runtime; full/required/source/image и будущий immutable RC/publication. Первые пять и source checks scoped PASS; требуемая публикация/финальный main read-back PENDING, поэтому keep_open. Этот самостоятельный source/tool scope не требует VPS или Telegram smoke; после его immutable publication нужен собственный completed/read-back/active-row removal checkpoint.

Перечитаны критерии parent482: offline baseline source часть выполнена; общий read budget/admission/critical priority, session pooling/shutdown, presentation-only cache/singleflight/authoritative bypass, traffic transport normalization, limiter memory и соответствующие runtime/own operator outcomes остаются PENDING. Parent keep_open; #498 не включается на основании одного baseline. Исторические ограничения future backlog после rc.9 заменены автономным #930; waived burst и live load не возобновлялись.
