# #948 — source-only очередь кампаний: post-merge checkpoint

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-27 18:39 UTC+03:00
- **Окружение:** GitHub / CI / локальные synthetic Python3.12 и temporary SQLite, без VPS/Telegram/provider операций
- **Цель:** подтвердить implementation merge #956 и собственный source-only scope #948 до отдельного RC25 release-prep.
- **Версия и immutable tag/SHA:** #956 squash main `9ac41354167a3b12a35149ebcfb396fe4065cceb`, exact PR head `b220e988f36f20b459387007edf82400355c0bb2`, base `4f383c2a9ccc222c927f8a3c79c516e67ed241cc`; Published RC24 `d7e224b48b23a315c389c290594c975dba2f9684` содержит schema16 без #948.
- **Scope:** schema17/owned queue/UTC-IANA/snapshot/fencing/durable intents/unknown-no-replay/safe retries/stop/privacy, required PR CI и independent PR/main read-back. Не runtime delivery или production acceptance.
- **Фактический результат:** PASS
- **Источник и evidence:** [#956](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/956) MERGED 2026-10-27T15:33:58Z, independent GitHub PR/main read-back 18:34 UTC+03:00. [Final-head Python40531192474](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40531192474) SUCCESS, 1659 tests/3 skipped, job122284131698; [title40531988045](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40531988045) SUCCESS; [supply-chain40531192410](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40531192410)/job122284129871 SUCCESS, image/TZ-data/SBOM/vulnerability gates PASS. Local targeted116/full1659 (16 environment skips), compileall/OpenAPI/slash catalog/living/language/semantics/governance/diff PASS. Fresh automatic main supply-chain40532243404/job122287913522 SUCCESS на squash SHA, все lock/scan/build/SBOM/vulnerability steps PASS (read-back18:39). Main Python40532243318 пока PENDING и не включён в этот scoped PASS.
- **Ограничения и остаточные риски:** реальные policy501/consent/privacy/abuse/retention и #949 UI/observer/BotAPI/runtime/pilot отсутствуют; current admission DENY_ALL, конфигурация OFF. Позитивные fake policy/transport не являются реальным approval или доставкой. Source schema17 не применена на VPS; поздний cumulative upgrade/recovery и старый каталог16 требуют отдельного review/разрешения.
- **Связанные Issues:** #948, #874
- **Решение по Issues:** #948: keep_open, #874: keep_open
- **Следующий шаг:** required CI/squash этого implementation checkpoint, independent main read-back и Issue state audit; после подтверждения main/supply-chain — RC25 release-prep. Затем immutable publication/own closure checkpoint #948 до #949.
- **Раздельные состояния:** merged=#956 `9ac41354167a3b12a35149ebcfb396fe4065cceb`; published=RC24/schema16; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15, independent VPS read-back PENDING; accepted=source/PR CI scoped PASS, own publication PENDING, parent/runtime PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## Проверенный contract

Frozen snapshot ограничен1000, page8/jobs100 на owner; private proof generation не восстанавливает старый snapshot при delete/recreate. SQL VM ограничен 10 млн операций/5 секунд с rollback без частичного snapshot. Персональные IDs/body не выходят в DTO/repr/errors, raw payload logging отсутствует. Operation UUID4/spec и immutable identity исключают повторный fan-out при double confirmation; SQL guards защищают state graph и terminal outcomes.

UTC/IANA parser требует явные дату/зону, отвергает DST fold/gap, неизвестную/missing TZDB, прошлое и срок далее366дней. Часы обновляются после SQLite write-lock; первый stale start после60секунд pauses без catch-up. Обратный ход часов fail closed. Image проверяет доступность timezone data под UID10001; pinned base/privileges/packages не менялись, source/runtime флагов не добавлено.

Worker не зарегистрирован в app_runtime и не импортирует Bot API/HTTP clients. Trusted Owner/category/recipient checks отказывают по умолчанию; mock не заменяет #501. Один fenced lease30секунд, отдельный budget2секунды, один вызов transport/tick. Durable intent предшествует внешнему обращению. Timeout/network/lost response/lease loss/unknown commit/restart не разрешают replay. Положительный ответ привязан к chat ID и message ID; неверный/mismatched ответ остаётся unknown. Только proven not-accepted429 с retry_after1…3600 допускает до3 intents, 403 terminal. Неизвестный статус не маскируется как безопасный failure.

Graceful close/owner pause/cancel запрещают новые intents, не обещают rollback in-flight. Некооперативная task после timeout может завершиться поздно; unknown не перезаписывается, worker не начинает новую dispatch. Собственный результат close=False сохраняет этот остаток. Per-recipient deny и изменённые membership/proof проходят fail-closed revalidation, без fallback «все»/нового private identity.

## Регрессии и собственный closure

Новые tests покрывают 8 schedule cases, 28 delivery/state/race/privacy cases и 6 migration cases; сохранённые foundation/migration regressions проходят. Local targeted116 и final full1659/16 skipped PASS; первый full имел только duplicate schema-anchor doc-fixture failure, исправленный без ослабления negative test. Current journals расширены17, исторический v15→16 явно выполняет prefix16; production DDL1…16 не переписан.

Первые шесть собственных acceptance групп #948 доказаны isolated tests/CI/source review. Седьмая требует собственного immutable RC и publication/Roadmap/main checkpoint — поэтому keep_open. Реальные sends/deployment не требуются этой source-only частью и не выполнялись; parent #874 остаётся OPEN независимо от завершения дочерней очереди. Normative SERVICE_CAMPAIGNS/SQLITE/ADMIN_SETUP/CLIENT_SETUP/V5/README/CHANGELOG/living-docs обновлены. UI_STYLE reviewed N/A: UI/slash/callbacks не менялись.
