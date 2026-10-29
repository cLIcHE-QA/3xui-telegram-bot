# #995 — завершённый publication/main checkpoint RC32 и собственная приёмка

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-29 15:50 UTC+03:00
- **Окружение:** GitHub required/main CI, idempotent publisher и read-only main/ref/Release/Issue APIs; локальный docs-only review, без production операций
- **Цель:** зафиксировать завершённый publication999/main outcome и собственный acceptance995 перед следующим самостоятельным source scope482.
- **Версия и immutable tag/SHA:** Published v5.0.0-rc.32 `317b8a4661cd100acfe50386a85ba4a66b541dbb`, GitHub Release2026-10-29T08:46:10Z; docs publication999/main `891c2f53de5e799af36cd50111a7bbdd0bbfe28b`.
- **Scope:** docs publication999 required/latest title/CLEAN/squash/own main/publisher/independent main and immutable RC read-back/own995 acceptance audit. Не installed/runtime/load или parent482 whole acceptance.
- **Фактический результат:** PASS
- **Источник и evidence:** [Publication999](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/999) MERGED; [required40874238294](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40874238294)/job123448824398 SUCCESS1796/3 за213.659s; final title40875150205/job123451948522 SUCCESS/REST clean перед expected-head squash. [Own main40875280108](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40875280108)/job123452392572 SUCCESS1796/3 за217.282s; idempotent publisher40875993584 SUCCESS. Independent main11/protected13/source2/registry/OPEN43 read-back 2026-10-29T12:46:44.180045+00:00 PASS; separate immutable32/version/canonical notes/unique998/source5/old31-30-29 read-back 2026-10-29T12:47:11.892760+00:00 PASS. [Own995 audit](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/995#issuecomment-6497094069) и [parent482 audit](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/482#issuecomment-6497097373), последующий API read-back OPEN/6 checked1 pending и OPEN/parent memory source checked подтверждены.
- **Ограничения и остаточные риски:** R995-01 installed/read PENDING после отдельно разрешённого deployment; parent482 pooling/lifecycle/cache/прочие critical contexts/admin full-list и #984/#989 runtime отдельно. Deployed18.10 operator-reported/independent VPS PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED. Этот финальный docs queue sync требует собственных required/main checks и main read-back до следующего significant source.
- **Связанные Issues:** #995, #482
- **Решение по Issues:** #995: keep_open, #482: keep_open
- **Следующий шаг:** required/latest title/merge/own main/read-back финальной docs-only сверки очереди, затем следующий самостоятельный Issue-first scope482; отложенные runtime outcomes в завершающем блоке930.
- **Раздельные состояния:** merged=source996/checkpoint997/release998/publication999; published=RC32 `317b8a4661cd100acfe50386a85ba4a66b541dbb`; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15; accepted=source/release/publication/main999 scoped PASS, own runtime/parent482 PENDING, full v5 NOT PASS.

## Предыдущие наблюдения сохранены

[Исходный publication audit](2026-10-29-rc32-publication-checkpoint.md) сохраняет release998 CI/scope/official health/fresh exact-release image/SBOM/artifact digest и первоначальные metadata96 FAIL1, automatic approval review failure и URLError. Отказ review не доказывал фактический баланс. После явного «запускайся» повтор исполнен через тот же review; штатная reconciliation2026-10-29T12:31:22Z PASS Published32/ref82/assert43/active43 на locked Python3.12 с системным CA bundle и неизменным TLS verification. Никаких gate/approval bypass или правок исторического audit не было.

Первый title40874238317/job123448825434 не принял единственный unchecked code-CI item до фактического required SUCCESS; затем checklist обновлён и final title40875150205 SUCCESS подтверждён. Требуемая проверка не удалялась/не ослаблялась. Local metadata96/compileall/OpenAPI55/language/living/semantics/governance/diff PASS до publication999; дальнейший own main полный PASS указан выше.

## Собственный Issue scope

Own995 criteria1…6 подтверждены; criterion7/R995-01 остаётся unchecked/OPEN/keep_open/🟠. В parent482 отмечен только самостоятельный source-критерий bounded limiter memory; базовый offline baseline уже был checked. Остальные семь parent criteria остаются unchecked; parent не закрыт. Ключи/события4096/limit и sliding-window semantics доказаны synthetic regressions/oracle, не production RAM bytes/SLA/distributed capacity. Не создавать live pressure/новые IDs/Owner reset/Telegram burst ради R995-01; поздний ordinary existing-owner read можно совместить с R989-01 при явном outcome обоих scopes.

Runtime/test/version32/schema17/lock/deps/env/ports/credentials/TLS/auth/no-replay не менялись в publication999, source2 SHA-256 и historical panel-read5 hashes совпали. Все versioned release notes и RC32/31/30/29 immutable. Нового release или deployment для этого docs-only checkpoint не требуется; no real polling/listeners, Telegram sends, money/refund/provider/host/production DB writes/ref deletion/secrets/public rollout.

Локальная проверка финальной docs-only сверки: metadata96 PASS за1.715s (2026-10-29T12:50:13.780595Z), semantics/governance/living/language PR/diff PASS; штатная independent GitHub reconciliation2026-10-29T12:51:49.040230Z PASS Published32/ref82/assert43/active43. Эти результаты не заменяют собственные required/main checks и main read-back нового docs PR.
