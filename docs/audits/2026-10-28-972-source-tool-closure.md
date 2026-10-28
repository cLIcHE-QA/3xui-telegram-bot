# #972 — собственная source-only приёмка и closure после RC29

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-28 15:21 UTC+03:00
- **Окружение:** GitHub / required CI / clean synthetic CPython3.12 / independent read-only repository evidence, без production операций
- **Цель:** проверить все собственные исходные6 критериев #972 и зафиксировать фактическое CLOSED/completed отдельно от полного #482 runtime acceptance.
- **Версия и immutable tag/SHA:** v5.0.0-rc.29 `4422c8b5f1ff8d8a36343f9ef29becd213caab47`, Published2026-10-28T12:05:14Z; publication checkpoint #982 main `33e7ea58ddd54e38c3d43aaa0d9371652aac2e53`.
- **Scope:** собственный source/tool или import repair acceptance, guarded actual paths/raw provenance/required checks/image/immutable publication/main checkpoint и независимый API closure read-back. Не production API budget, deployment, live load или full v5 acceptance.
- **Фактический результат:** PASS
- **Источник и evidence:** [отдельный own audit Issue#972](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/972#issuecomment-6468819788), [publication checkpoint #982](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/982), [publication audit](2026-10-28-rc29-publication-checkpoint.md). Independent main/Roadmap/registry read-back12:14:34Z, immutable Release/OPEN pre-closure read-back12:14:42Z; actual API CLOSED/completed read-back 2026-10-28T12:21:19Z. Issue#972 closed_at=2026-10-28T12:20:40Z; parent482 OPEN.
- **Ограничения и остаточные риски:** required CI/merge/main read-back этого отдельного closure docs PR ещё PENDING; прежде следующего значимого scope обязателен main sync. VPS/live smoke N/A по собственным source-only criteria; parent482 admission/priority/session pooling/cache/authoritative/errors/limiter/runtime outcomes PENDING. Deployed18.10 operator-reported/schema15/independent VPS PENDING; G-11 PARTIAL/NO-GO/public rollout BLOCKED.
- **Связанные Issues:** #972, #482
- **Решение по Issues:** #972: completed, #482: keep_open
- **Следующий шаг:** required test/final title/actual CLEAN, squash и independent main read-back этого closure docs checkpoint; затем определить отдельный следующий child #482 Issue-first. Не повторять waived burst/HWID scoped PASS.
- **Раздельные состояния:** merged=source973/979, source checkpoints974/978/980, release975/981, publication982; published=RC29 `4422c8b5f1ff8d8a36343f9ef29becd213caab47`; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15, independent VPS PENDING; accepted=все собственные source-only criteria#972 PASS/CLOSED, полный parent482/runtime/G-11 PENDING/PARTIAL, public rollout BLOCKED.

## Отдельный собственный audit — без ослабления criteria

Собственный acceptance #972 — 2026-10-28 UTC+03:00, fixed immutable RC29 `4422c8b5f1ff8d8a36343f9ef29becd213caab47` Published12:05:14Z. Publication checkpoint #982 MERGED 33e7ea58ddd54e38c3d43aaa0d9371652aac2e53, required 40685492682/job122806659081 (1754/3,125.685s)/final title40686068500/job122808624137 SUCCESS/actual CLEAN, independent main/Roadmap/registry/Release/Issue read-back PASS 2026-10-28T12:14:34Z/main и12:14:42Z/immutable Release+OPEN Issues.

Все шесть собственных исходных критериев перечитаны и подтверждены:
1. PASS: actual XUIClient/XuiCustomerProvider paths, fixed fake transport; fresh MetaPathFinder до module load запрещает config/app_runtime/provisioning/checkout/commerce/db/dotenv. Строгие import/worker/parent CLI/DTO aliases на точном RC29 PASS, внешних URL/token/env/DB arguments нет. Первоначальный RC28 transitive import FAIL сохранён, исправлен отдельным #977/#979, критерий не ослаблен.
2. PASS: bounded CLI clients1..10000/max3, пять scenarios/max15cases, requests<=256/driver<=32/decodework<=320000 records/case/worker60s. Source15+2 cases actual paths get/traffic/list/same+unique, без cache/singleflight; по2GET на traffic, sessions==closed, distinct owners/driver backlog/transport peak указаны.
3. PASS: original и corrected raw15+2 reports измерены локально, Python/OS/CPU/Git/hash/dirty provenance; calls/JSON/latency/RPS/CPU/heap/RSS scopes/units/limitations явные. Исправленные measured hashes совпали с release29; структурные counts/bytes/peaks совпали с original, timings/RSS не обещаны неизменными. Fake numbers не server capacity/Xray CPU/SLA.
4. PASS: negative method/route/foreign URL/owner/auth/TLS/socket/DNS, shapes/counts/CLI bounds/error/cancel/context cleanup/no partial report без flaky thresholds. Новые3 fresh-process regressions pre-fix FAIL до config execution, после repair PASS; release targeted17 PASS1.668s.
5. PASS: canonical API contract/README/CHANGELOG/Roadmap, original+corrected dated audits и publication read-back. Runtime definitions/constants AST-identical, auth/TLS/mutations/deps/schema17/cache/session lifecycle прежние; только type-only import execution исправлен. Historical RC28/tag/notes/FAIL не переписаны.
6. PASS: source local full1754/16 environment skips93.330s, source/release required1754/3, compileall/OpenAPI55/diff PASS. Source979/main980, release981/health/scope1/1/main199.701s/publisher40684907436, fresh image40684260872/artifact12813958039 source/lock/SBOM dnspython2.9.0/ISC/actionable HIGH-CRITICAL0; immutable ref/rawversion/canonical notes/unique981/flags/old28 unchanged; publication checkpoint982 required/main read-back доказаны. Own source-only scope прямо допускает completed без VPS/live smoke; deployment не требуется для его criteria.

Решение: #972 completed только по source-tool scope. #977 criterion6 получает это отдельное own972 audit и последующий API CLOSED read-back; parent #482 keep_open до admission/priority/pooling/cache/authoritative/errors/limiter/runtime outcomes. После CLOSED read-back обязателен отдельный closure docs PR с registry decisions/active-row removal и main read-back до следующей значимой задачи. G-11 PARTIAL/NO-GO, Deployed18.10 operator-reported, public rollout BLOCKED; реальные операции не проводились.

Evidence: source973/979, checkpoints974/978/980/982, releases975/981; docs/audits/2026-10-28-972-import-isolation-finding.md, 2026-10-28-977-import-boundary-revalidation.md и 2026-10-28-rc29-publication-checkpoint.md.

Последующий main982 Python40686179834/job122808996894 SUCCESS1754/3 за198.233s, idempotent publisher40686819824 SUCCESS; reconciliation step завершён до изменения Issue states, ошибки не обходились.

## История и финальная синхронизация

[Первоначальный RC28 import FAIL](2026-10-28-972-import-isolation-finding.md), [corrected raw/source revalidation](2026-10-28-977-import-boundary-revalidation.md), [source/main checkpoint](2026-10-28-977-import-fix-postmerge-checkpoint.md) и прежние publication audits сохранены неизменно. Empty-env CLI не считается доказательством no-config: строгий finder до module load отдельно проверен на fixed release. Source/local/required CI не подменяются будущим deployment; собственные критерии прямо допускают source-only closure без VPS/live smoke.

Этот новый closure checkpoint отражает уже подтверждённые API CLOSED состояния, удаляет только972/977 из active Roadmap и обновляет их completed decisions. Он не изменяет опубликованные release sections, исходники, tests, trust boundaries или operator prerequisites; новый RC для служебного docs sync не нужен. До его required CI/merge/main read-back Roadmap sync остаётся PENDING, следующая значимая реализация не начинается. При ошибке проверки исправляется evidence/docs, а не ослабляется gate.
