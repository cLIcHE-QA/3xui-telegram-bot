# #989 — повторная проверка descendant main после source checkpoint991

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-28 21:52 UTC+03:00
- **Окружение:** GitHub required CI/descendant main/read-only API; source image evidence; без production операций
- **Цель:** подтвердить устранение factual planned→merged Roadmap drift, сохранив исходный FAIL и собственный runtime остаток.
- **Версия и immutable tag/SHA:** checkpoint991 main `5da950ac7389aeda58b34205688986f318bff7be`; source990 `309ee64bf56a653995d9600b4d3c1c5c5fa05b5d`; actual Published30 `7aa3514194675ae119a2e774e03da150025326b9` без989. Candidate v5.0.0-rc.31 tag N/A — ещё не Published.
- **Scope:** source checkpoint required/full descendant CI/reconciliation/publisher/independent main+source5 hashes/Issue state; не release31/deployment/full v5 acceptance.
- **Фактический результат:** PASS
- **Источник и evidence:** [Source990](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/990) и [checkpoint991](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/991), squash 2026-10-28T18:44:43Z. Checkpoint exactdc985c9 required40746930231/job123023084234 SUCCESS1782/3 за209.323s; final title40747818310/job123026198732 SUCCESS/actual CLEAN. [Descendant main40747968353](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40747968353) SUCCESS: ["Ran 1782 tests in 209.585s", "OK (skipped=3)"]; [idempotent publisher40748684996](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40748684996) SUCCESS. Independent main/Roadmap yellow989/registry/audit/source5 hashes/Issues/read-back 2026-10-28T18:51:20.863204+00:00 + отдельный connector main PASS.
- **Ограничения и остаточные риски:** release-prep31/собственные required CI/release-scope/official health/automatic immutable publication/fresh release image/publication checkpoint PENDING. R989-01 installed release/SHA/health/существующий owner traffic read после отдельно разрешённого deployment PENDING; live failure/load не создавать. Parent482 остальные scopes/#984 runtime/G-11 отдельно, public rollout BLOCKED.
- **Связанные Issues:** #989, #482
- **Решение по Issues:** #989: keep_open, #482: keep_open
- **Следующий шаг:** собственные gates отдельного release-prep RC31, automatic immutable publication и обязательный publication/own Issue checkpoint/main read-back до нового source scope.
- **Раздельные состояния:** merged=990/source309ee64 и991/checkpoint5da950ac; published=RC30 без989; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15, independent VPS PENDING; accepted=source/required/descendant main/reconciliation/image/read-back scoped PASS, RC31/publication/R989-01 и parent482 PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## Исходный FAIL сохранён, причина устранена

[Source postmerge checkpoint](2026-10-28-989-traffic-read-postmerge-checkpoint.md) остаётся историческим PARTIAL. Source990 main40745618678/job123018486972 FAIL на read-only planned989 при уже MERGED990; full tests в том run не запускались, publisher40745684867 SKIPPED. Он не переименован в PASS и не rerun ради ложного green. Состояние исправлено фактической 🟡 строкой с immutable source SHA в штатном docs PR991, required CI полного1782/3 и нынешним descendant main PASS. Checkers/tests/waivers/thresholds не менялись.

## Source identity и acceptance scope

Все5 measured files совпали с actual main991 и raw matrix15/concurrency32x2 source3835, adapter SHA-2561946daed529dff1bb2ab0167e7fd7e9917c08a2339243c35b544460451474b4c. Новый source/main не приписывается старому Published30. Fresh source image40745662736/artifact12841557023/digest5a21f541430d7f394e8c09631041520d034f6d388021e73002a2da27b573d844 проверен на source309ee64: runtime5 bytes идентичны991, lock/base/SBOM dnspython2.9.0/ISC/actionable HIGH-CRITICAL0 PASS. Это не fresh image будущего31: его exact release SHA ещё должен пройти отдельную проверку.

Source pre-fix11 FAIL2/34, post-fix11/targeted94/full1782/16 и metadata96 остаются в source audit; только ожидаемая read-only error boundary изменилась, mutations/auth/TLS/admission/ownership/успешные aliases/нули прежние. Canonical docs/Issue-first/runtime no-replay boundaries reviewed. GitHub OPEN989/482/984 и CLOSED972/977 согласованы с Roadmap/registry; own989 source criteria1…5 завершены после этого read-back, criterion6 release/publication и criterion7 installed/read ещё PENDING. Решение keep_open.

Schema17/deps/env/ports/setup не меняются. Deployed18.10 operator-reported, independent VPS PENDING; waived burst/предыдущие HWID PASS не повторялись, новых Bot/provider/host/DB production действий не было. Release31 metadata не разрешает deployment или stable/public rollout.

Release-prep candidate31 existing96 metadata/release/version tests PASS1.667s, compileall/OpenAPI55/static/diff PASS. Previous immutable30 tag явно fetched и SHA7aa3514 проверен; release-scope PASS1/1 source PR990 since30 без exclusions. Independent GitHub reconciliation current Published30/ref81/assert42/active42 PASS. Собственный required release CI/latest title/CLEAN/official health/publication всё ещё PENDING.
