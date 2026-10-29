# Финальная сверка publication/main #989 и отдельный runtime gate

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-29 10:06 UTC+03:00
- **Окружение:** GitHub required CI/main/publisher и read-only GitHub API; production операции отсутствуют
- **Цель:** завершить source/release/publication checkpoint #989 и убрать выполненные публикационные действия из текущей очереди, сохранив собственный installed/read outcome.
- **Версия и immutable tag/SHA:** v5.0.0-rc.31 `e74aabf827e5683c3528f9bd49e701a1ac17812c`, Published 2026-10-28T19:09:56Z; docs checkpoint main `9b406af42a9f6c99e6d89ed6f99b0b6e3b1eda0b`.
- **Scope:** publication/main/current docs/registry/Issue audit; не runtime deployment или full v5 acceptance.
- **Фактический результат:** PASS
- **Источник и evidence:** Publication checkpoint [#993](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/993) MERGED `9b406af42a9f6c99e6d89ed6f99b0b6e3b1eda0b` 2026-10-29T06:59:21Z; tested head79855bd20936aa806eebff782ed75fc1e53d5db6. Required40831890982/job123307762464 SUCCESS1782/3 за211.574s; final title40832492461/job123309665843 SUCCESS/actual CLEAN. Собственный main40832550636/job123309849569 SUCCESS [Ran 1782 tests in 211.989s; OK (skipped=3)], idempotent publisher40833088630 SUCCESS. Independent main/docs11/runtime5 hashes/Roadmap/registry/OPEN42/Issue/tag read-back 2026-10-29T06:59:50.736490+00:00 PASS.
- **Ограничения и остаточные риски:** own989 R989-01 installed/read PENDING; parent482 pooling/lifecycle/cache/другие critical contexts/admin full-list/limiter/runtime отдельно. #984 R984-01…03 PENDING; Deployed18.10 operator-reported/independent VPS PENDING; G-11 PARTIAL/NO-GO/public rollout BLOCKED.
- **Связанные Issues:** #989, #482
- **Решение по Issues:** #989: keep_open, #482: keep_open
- **Следующий шаг:** после required CI/merge/main read-back этой финальной docs сверки следующий самостоятельный Issue-first scope482; R989-01 и #984 runtime остаются в завершающем операторском блоке930.
- **Раздельные состояния:** merged=source990/checkpoint991/release992/publication993; published=RC31 `e74aabf827e5683c3528f9bd49e701a1ac17812c`; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15; accepted=source/CI/image/publication/main scoped PASS, own runtime/parent482 PENDING, full v5 NOT PASS.

## Полнота checkpoint и история ошибок

[Исходный publication audit](2026-10-28-rc31-publication-checkpoint.md) сохраняет release992 required/main1782/3, release-scope1/1, health preflight, fresh image40751063215/artifact12843572563, digest8e6bf0a5fad4a66c2a56dee5d136ac4c866148398e55fe3fc493b6c8b5d25121, lock/SBOM/security и независимые immutable notes/source5 hashes. Эти проверки не переписаны. Старые source990 main metadata FAIL и truthful991 descendant main PASS сохранены в собственных исторических audits.

Первый title993 был FAIL при ещё unchecked CI item; после фактического Python SUCCESS отдельный title40832416624 FAIL обнаружил объединённый заголовок PR вместо точного `## Что изменено`. Исправлено только описание, повторный title40832492461 SUCCESS, actual CLEAN и tested head прежние. Gate не обходился, code/checkers/tests не менялись. Исходная review failure с сообщением о credits не доказывала фактический баланс; после прямого указания оператора продолжить штатный retry прошёл review. Первый local reconciliation UNKNOWN/URLError устранён системным CA bundle без отключения TLS verification; тот же checker PASS Published31/ref81/assert42/active42.

Main993 содержит ровно11 ожидаемых metadata files; versioned CHANGELOG sections и пять measured runtime hashes из raw989 неизменны. OPEN989/482/984 и CLOSED972/977 подтверждены независимо. Старые immutable RC30/29 не изменились. Новый final docs change не меняет runtime/APP_VERSION/schema17/lock/deps/env/ports; historical raw/audits не редактируются.

## Собственный acceptance и остаток

Issue989 criteria1…6 source/regression/security/required CI/immutable RC/publication/main выполнены; criterion7/R989-01 остаётся PENDING. После отдельно разрешённого deployment нужны exact installed tag/SHA/health и безопасный existing-owner traffic read/Back. Error paths доказаны offline: не создавать live failure/нагрузку. Parent482 не завершается child989; next scope определяется Issue-first. Issue states keep_open не изменяются, следовательно closed Issue не удаляется из active register. Никаких VPS/Telegram sends/polling/payment/provider/host/DB mutations/ref deletion/public rollout не было.

## Проверка финальной docs сверки

[Own989 audit](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/989#issuecomment-6490285875) и обновлённый parent482 сохраняют OPEN/keep_open. Local metadata/release/governance96 PASS1.655s на отдельной tracked fixture с пустым .env и synthetic values; production конфигурация не копировалась. Independent candidate reconciliation PASS Published31/ref81/assert42/active42. Собственный required CI/merge/main read-back этого финального docs PR ещё PENDING.
