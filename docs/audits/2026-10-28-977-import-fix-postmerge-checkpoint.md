# #977 — исправленный import boundary в main перед RC29

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-28 11:25 UTC+03:00
- **Окружение:** GitHub / CI / локальные fresh guarded processes/clean synthetic test checkout и offline reports; без production операций
- **Цель:** подтвердить фактический source merge no-config repair, equivalent measured hashes/DTO identities/required checks и fresh image перед новым immutable fix RC.
- **Версия и immutable tag/SHA:** source main `8d22c2166a9f7f417b68c80e98e9339ca7c4fe1d`, APP_VERSION5.0.0-rc.28; Published RC28 `fad1fe6641f8fe190bd810ff51e04d91062c7ac7` остаётся с defect, fix RC29 ещё PENDING.
- **Scope:** exact source merge/required PR/full local/guarded main import/hash equivalence/fresh source image, own977/972/parent482 audit. Не новый Published/deployed fix и не whole API budget/runtime acceptance.
- **Фактический результат:** PASS
- **Источник и evidence:** source [#979](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/979) exact head `7849993c4f2704e322fe9968a16deb152c07eab2`, squash `8d22c2166a9f7f417b68c80e98e9339ca7c4fe1d`, MERGED2026-10-28T08:21:34Z. [Python40655334790](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40655334790)/job122704881222 SUCCESS1754/3 skips за213.082s, [final title40656073757](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40656073757)/job122707301346 SUCCESS/actual CLEAN. Source main независимо fetched, measured file hashes совпали с [branch revalidation](2026-10-28-977-import-boundary-revalidation.md); fresh guarded main import PASS08:25:06Z. [Supply-chain40656336837](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40656336837)/job122708166564 SUCCESS; main Python40656214283/job122707753280 PENDING на snapshot11:25.
- **Ограничения и остаточные риски:** этот source checkpoint ещё требует CI/merge/independent main read-back; RC29/publication/own977+972 closure PENDING. Source main guard PASS не исправляет immutable Published28. Parent482 остальные budget/cache/lifecycle/limiter/runtime scopes не выполнены; Deployed18.10/G-11 не меняются.
- **Связанные Issues:** #977, #972, #482
- **Решение по Issues:** #977: keep_open, #972: keep_open, #482: keep_open
- **Следующий шаг:** required source checkpoint/merge/main read-back, затем release-prep RC29/scope/health/automatic publisher/independent publication; повторный полный own acceptance977/972 и отдельный closure/API read-back/active-row removal до нового значимого scope482.
- **Раздельные состояния:** merged=#979, source guard исправлен; published=RC28 `fad1fe6641f8fe190bd810ff51e04d91062c7ac7` с прежним defect, исправленный RC29 PENDING; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15, independent VPS read-back PENDING; accepted=source/full+required/image scoped PASS, fix publication/own closure PENDING, parent runtime/G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## До кода / regression / неизменность поведения

Finding [#978](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/978) main `b6f8d1791e634fabcaab31e5cb5c5d0076e1b9f8`/Roadmap/registry/FAIL audit независимо read-back до code repair; #972 не закрывался. Required finding Python40653013356/final title40653531570 SUCCESS; main40653622700/job122699323354 SUCCESS1751/3 за206.820s, idempotent publisher40654183077 SUCCESS.

Новые три fresh-process tests до fix дали failures=3 за0.426s: checkout_service запрещён finder до config execution, без env contents. После TYPE_CHECKING repair targeted17 PASS1.648s: strict import/семь exact DTO+error aliases/injected service/actual provider worker/parent CLI, прежний benchmark10/domain boundary4. Все domain class/function/constant AST definitions до/после идентичны, меняется только выполнение annotation imports; future annotations существовали. Repo runtime introspection этих imports не использует. DTO/errors не переносились, config/provider stubs или AST extraction не применялись.

Local full1754/16 environment skips PASS93.330s на точном head7849993 в чистом временном локальном Git checkout, synthetic env и пустая контролируемая .env fixture; source ignored configuration/секреты не копируются и не читаются. Compileall/OpenAPI55/catalog/living/language/semantics/governance/diff/PR language PASS; независимый reconciliation Published28/ref79/assert42/active42 PASS. Client pilot/setup/flags/billing/ownership/navigation и auth/TLS/mutation semantics не меняются; reviewed v5-client-acceptance/Admin Setup waivers в source PR обоснованы import-only diff.

## Исправленный main / provenance / image

Четыре measured file SHA-256 из новых raw reports совпали с fetched source main; customer_service=`ae9dbe78c368900ab77c8646dbaf6c4628422d989647afaf86cb0aaf4eb8735b`, xui/provider/benchmark hashes прежние. Actual fresh main MetaPathFinder запретил config/app_runtime/provisioning/checkout/commerce/db/dotenv и импорт benchmark прошёл; ни один blocked module не загружен. Это независимое main revalidation после required PR, не предположение о merge.

Новые17 offline cases сохраняют точные fan-out/JSON/session/closed/driver scopes исходного измерения. Старый customer_service hash/metrics/source finding FAIL сохранены как история; новый source не выдаётся за прежний. Timings/CPU/heap/RSS остаются bot/fake-driver/tracing metrics, не реальная panel/Xray capacity/production thresholds. Socket/DNS/connector/mutation/foreign route guards прежние.

Fresh source artifact12801084049, digest `sha256:a2153027c65dfa694e8edce266cd3fb30f7fb329907273b9959cb40596c8e701`, независимо скачан: metadata.source_sha совпал с8d22c21, lock digest совпал с unchanged requirements.lock, container SBOM dnspython2.9.0/ISC, fs/image actionable HIGH/CRITICAL0. Build/install/pinned scanner/license/SBOM/gate/upload SUCCESS. Новых deps/permissions/base/workflow/waivers нет; source image не фактический deployed package.

## Own acceptance остаётся отдельным

#977 source repair/import guard/type-only usage/identity/regression/docs/new hashes/source+image scoped PASS; source checkpoint/fix RC29/publication/final own audit PENDING, keep_open. #972 source criterion1 теперь revalidated на исправленном main, но Published28 остаётся defective: все исходные criteria проверяются после исправленного immutable RC и его main checkpoint, затем completed/read-back/active-row removal при собственном полном PASS. VPS/live smoke N/A по собственным source/import scopes, новые real operations не требуются. Parent482 keep_open до остальных admission/critical priority/pooling/cache/authoritative/error/limiter/runtime outcomes; #498 этим не включается.
