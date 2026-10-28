# #984 — source985 main и fresh image checkpoint

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-28 16:28 UTC+03:00
- **Окружение:** GitHub / required CI / isolated image build / independent Git source hash read-back; без production операций
- **Цель:** зафиксировать actual source985 merge, full/required regressions и fresh source image до отдельного release-prep.
- **Версия и immutable tag/SHA:** source main `7325b170e6851415e34fe40094924bcf1f5ca534`, APP_VERSION5.0.0-rc.29; actual Published RC29 `4422c8b5f1ff8d8a36343f9ef29becd213caab47` не включает984, RC30 плановый до release-prep.
- **Scope:** source985 merge/provenance/required1771/strict imports/52 targeted/raw17 cases/actual5 source hashes/fresh image. Собственный docs checkpoint/main push completion, новый RC и runtime acceptance отдельно.
- **Фактический результат:** PASS
- **Источник и evidence:** [Source985](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/985) MERGED2026-10-28T13:21:53Z, squash7325b170, exact head `c570afee1bc0a32a27826d9d11e7bc38446469e4`. [Required Python40694581300](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40694581300)/job122837835717 SUCCESS1771/3 за213.900s, [final title40695531381](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40695531381)/job122841169571 SUCCESS/actual CLEAN. Independent GitHub main/PR и Git measured SHA-256 read-back13:22:32.691952Z PASS. [Main40695747111](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40695747111)/job122841920138 SUCCESS1771/3 за198.528s; idempotent publisher40696474938 SUCCESS. [Source review/raw](2026-10-28-984-read-admission-source-review.md): targeted52 PASS1.769s/full1771/16 PASS92.245s; exact metadata95 PASS1.504s и static gates. GitHub pre-merge Git tree/blob read-back всех5 measured files и independent reconciliation Published29/ref80/assert41/active41 PASS.
- **Ограничения и остаточные риски:** Main push Python40695747111/job122841920138 и idempotent publisher40696474938 SUCCESS подтверждены повторным read-back перед фиксацией этого audit; прежнее чтение13:26Z было IN_PROGRESS и не считалось PASS. Этот source checkpoint требует собственных required CI/merge/independent main read-back до release-prep RC30. Source/runtime984 OPEN, installed/read R984-01…03 PENDING; parent482 pooling/cache/другие authoritative contexts/общие errors/limiter/runtime scopes OPEN. Deployed18.10/schema15 operator-reported/independent VPS PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.
- **Связанные Issues:** #984, #482
- **Решение по Issues:** #984: keep_open, #482: keep_open
- **Следующий шаг:** завершить этот source checkpoint/required CI/merge/independent main read-back; затем отдельный release-prep RC30/scope/official health/automatic immutable publication/checkpoint. Runtime984 не закрывать по CI, реальные операции отложены.
- **Раздельные состояния:** merged=source985 `7325b170e6851415e34fe40094924bcf1f5ca534`; published=RC29 `4422c8b5f1ff8d8a36343f9ef29becd213caab47` без984; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15/independent VPS PENDING; accepted=source/required1771/raw/hash/image scoped PASS, docs main sync/RC30/runtime984/parent482/G-11 PENDING/PARTIAL/public rollout BLOCKED.

## Source и независимый read-back

Main получен connector branch/merged PR и отдельным git fetch. Все5 measured files actual main7325 побайтово совпали по SHA-256 с clean measured source68c4 из новых raw17 cases; customer_service/provider aliases прежние. Новый `_mutation_request` AST совпадает с previous main983; guards/auth/TLS/response/timeouts/routes/schema17/deps/base image прежние. Header version29 не выдаёт source984 за включённый в immutable Published29.

Current Roadmap/README/Source version Admin Setup отражают actual985 main; child984 🟡 с source PR985, parent482 остаётся 🟠 только для прежнего частичного baseline, остальные scopes незавершены. Unreleased CHANGELOG связывает984/PR985, что необходимо будущему release-scope gate. Исторические972/977 и новые source review/raw artifacts не переписаны. SourceC570 metadata95 и required1771 подтверждают собственный tested head; текущий docs-only checkpoint ещё PENDING своего результата.

## Fresh source image / security evidence

[Supply-chain40695837165](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40695837165)/job122842245981 SUCCESS на точном source main7325. Artifact12818852982, digest `sha256:ce1de63a7a9c6b358d3fab70889216b8df364ccd4a3319f7609b8dc980c575c4`, скачан отдельно. Независимо2026-10-28T13:24:28.745320Z проверены metadata.source_sha, lock SHA-256 `7ff99d772ca5807a23df68d8442707627e1f87a160813a7b7dcb448eab78633d` против файла, SBOM dnspython2.9.0/ISC, Python/image actionable HIGH/CRITICAL0 и отсутствие прежнего CVE-2026-114605. Hash install/scanner/licenses/build/SBOM/gate/artifact steps SUCCESS. Base digest/thresholds/ignore-unfixed policy не менялись, historical966 FAIL не удалялся.

Substantive trust-boundary review — в source audit: credential-free counters, bounded Future queue/weak lifecycle/retained tracebacks, canonical configured targets, exact same-Task critical scope, no child priority/legacy fallback/new HTTP on denial, post-mutation unknown без replay. Green tests сами по себе не являются security или runtime attestation; проверены конкретные observable invariants и scope. Docker COPY включает новый module, secret/env/data/test/script build exclusions прежние.

## Собственные критерии и остаток

Source части критериев984 bounded admission/reservation/cancel/registry/read families/critical provisioning/unknown/regression/provenance/security scoped PASS. Criterion7 source/main/immutable RC/publication checkpoint ещё незавершён; criterion8 installed/read outcome после отдельного deployment PENDING. Отсутствие natural authoritative event не подменяется PASS и не требует новой оплаты/provisioning/mutation. Не проводить production overload/burst ради доказательства capacity; новые limits — engineering caps, не измеренная мощность панели.

Parent482 сохраняет отдельные pooling/lifecycle, presentation-only bounded cache/singleflight/authoritative bypass, общие traffic errors, limiter memory и остальные runtime outcomes; authoritative caller contexts вне Provisioning пока ordinary. #498 не включается по одному admission source или fake RPS. Следующая значимая задача после завершения source/release/publication текущего пакета. VPS/staging/Telegram sends/payments/provider/host writes/refs deletion/public rollout не выполнялись; waived burst/HWID scoped PASS не повторялись.
