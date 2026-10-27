# RC26 — публикация source-компонентов #949 с отложенным runtime

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-27 23:56 UTC+03:00
- **Окружение:** GitHub / CI / локальный offline read-back; без VPS/Telegram/provider операций
- **Цель:** подтвердить immutable RC26 source-части #949 и сохранить собственные runtime gates #949/#874 открытыми.
- **Версия и immutable tag/SHA:** v5.0.0-rc.26 `b2f7503387fc7bd8465e783c898a0697ec87c541`, Published 2026-10-27T19:37:10Z; release PR #963 exact head `0066238a60baf22ab57d5e4ffb19feefeb1a6dda`.
- **Scope:** source/required CI/security, release-scope, tag/ref/version/канонические notes/unique release-PR provenance, сверка собственных критериев Issues и current-state docs. Runtime wiring, доставка, deployment и полный acceptance не проверялись.
- **Фактический результат:** PASS
- **Источник и evidence:** source [#961](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/961) `baa79b895394a955824ae69ac676082e65b0af6a`; implementation checkpoint [#962](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/962) `16a6b5766a022c9d2185f03c3fa2f4a21734d862`, independent main/Roadmap read-back. Release [#963](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/963) MERGED 2026-10-27T19:33:35Z; [Python40569238514](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40569238514) job122418671090 SUCCESS (1708 tests/3 skipped), [title40570072663](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40570072663) SUCCESS. [Main40570209930](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40570209930) job122422087143 SUCCESS, 1708 tests/3 skipped за120.935s; [Publish40570692284](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40570692284) prepare122423752776/publish122423843829 SUCCESS. GitHub connector Release/ref/commit-to-PR/raw version и независимый CLI/локальный renderer read-back подтверждены 2026-10-27 23:54–23:55 UTC+03:00.
- **Ограничения и остаточные риски:** source factory OFF/DENY_ALL; router/private observer/session/transport не зарегистрированы в app_runtime/dispatcher/client guards/menu. #501, реальные privacy/abuse/allowlist prerequisites не утверждены. FSM TTL ограничивает право действия, а не обещает физическое удаление текста из backend. Настоящее runtime wiring BLOCKED, затем требуется отдельный integration PR и разрешённый deployment/pilot. Schema17 прежняя, migration16/17 на VPS не выполнялась; cumulative upgrade/recovery от deployed15 проверяется позднее.
- **Связанные Issues:** #949, #874
- **Решение по Issues:** #949: keep_open, #874: keep_open
- **Следующий шаг:** required CI/squash этого publication checkpoint и independent main/Issue read-back; после синхронизации — независимая #876/план RC27. Runtime #949/#874 остаётся в завершающем операторском блоке с точным prerequisite, не препятствует независимой разработке.
- **Раздельные состояния:** merged=#961/#962/#963; published=RC26/schema17 `b2f7503387fc7bd8465e783c898a0697ec87c541`; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15, independent VPS read-back PENDING; accepted=source/publication scoped PASS, собственный runtime #949/#874 BLOCKED/PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## Независимые publication gates

Официальные GitHub Status summary/unresolved incidents проверены после зелёных required test/title непосредственно перед release squash: 2026-10-27T19:33:27.037758Z, Actions/Git Operations/API Requests/Pull Requests operational, unresolved incidents0; squash19:33:35Z. Tag и Release созданы штатным workflow, ручной публикации/перемещения refs и обхода checks не было.

Release-scope в PR CI и независимом локальном API gate PASS: ровно один значимый PR #961 после actual immutable RC25. Предыдущий tag `v5.0.0-rc.25` повторно прочитан после публикации — прежний `1c0854c9b416a2d0f2ccbe9083d62d88794307ed`. Исключений release-scope нет. Первый локальный reconciliation при release-prep вернул URLError/UNKNOWN, штатный read-only повтор после восстановления API дал PASS; UNKNOWN не объявлялся PASS и waiver не добавлялся.

Release prerelease=true/draft=false, title/body непустые и точно совпадают с CHANGELOG renderer на release SHA. Git ref type=commit, SHA совпадает с release squash. Commit-to-PR API возвращает ровно один merged main PR #963 с точным title release: v5.0.0-rc.26. APP_VERSION на этом SHA — 5.0.0-rc.26. Поле API immutable=false не является настройкой усиленной GitHub Release immutability: здесь неизменяемость tag обеспечена действующим release contract/ruleset и read-back; этот аудит не утверждает включение другой настройки GitHub. Publication не выполняет deployment.

## Source/security evidence

[Implementation audit](2026-10-27-949-owner-source-postmerge-checkpoint.md) сохраняет исходный checkpoint22:12 и его тогдашний main CI PENDING. Затем main [40566749976](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40566749976) job122409946068 подтверждён SUCCESS. Source PR Python40565248598/job122404650244 (1708/3 skipped)/final title40566343784 SUCCESS; fresh main [Supply-chain40566531082](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40566531082) job122409174309 на точном source SHA SUCCESS: hashed lock, pinned scanner, dependency/license, image build, SBOM, HIGH/CRITICAL gate и artifact. Новых dependencies/Dockerfile/workflow изменений нет.

Checkpoint #962 Python40567750729/job122413444198 (1708/3)/final title40568518667 SUCCESS; main40568651993 и idempotent Publish40569287621 SUCCESS. Independent main/Roadmap/registry read-back подтверждал source/main, оба Issues keep_open.

Source локально: full1708/16 environment skips PASS за91.364s, final targeted83 PASS за8.910s; exact-head CI1708/3 покрывает итоговый tree. Release-prep локально99 release/docs/governance tests PASS, compileall/OpenAPI55/command catalog/living/language/semantics/governance/diff PASS. Trust-boundary review охватывает Owner/private/current-panel/nonce/CAS, default-deny policy, request-identity/HTTP429 rejection proof, unknown/no replay и bounded cancellation; позитивная fake policy не утверждает #501 или eligibility. CI/GitHub evidence не является VPS/Telegram attestation.

Publication checkpoint локально: 93 существующих docs/release/governance tests PASS; compileall, OpenAPI55 и diff --check PASS. Новые тесты для синхронизации статуса не требуются; runtime code не меняется. Required CI этого checkpoint ещё PENDING до фактического результата.

## Собственный Issue closure audit

Сверены все семь acceptance групп #949:

1. Owner-only draft/edit/list/preview/estimate/schedule/progress/stop и stale/forged/FSM/double-confirm source regression — scoped PASS; действующий приватный /admin entry не зарегистрирован, runtime outcome PENDING.
2. Trusted private observation adapter и минимальный proof проверены синтетически; фактическое authenticated client-update wiring отсутствует, BLOCKED до настоящих prerequisites.
3. Bounded existing-bot adapter/typed unknown/no replay проверены fake Bot/Dispatcher/queue/HTTP-response tests; production Bot API assembly и outcome PENDING, listeners/sends не запускались.
4. Factory OFF, DENY_ALL пока #501 не утверждён, bool редактора не bypass — source PASS; это не разрешение включать runtime.
5. Неподтверждённые media/CTA/HTTPS allowlists disabled, raw markup/URL/recipient callbacks не принимаются — source PASS; реальная allowlist не выдумана.
6. Тематические UI/ADMIN/CLIENT/SQLITE/disable docs и полный late checklist согласованы; реальные permission/abuse/privacy/retention prerequisites и pilot identities/sends/eligibility PENDING.
7. Source required checks/security/own RC/publication PASS; этот publication/main checkpoint ещё требует merge/CI/read-back. Даже после него пункты1–3/6 runtime scope остаются непроверенными.

Итог: #949 OPEN/keep_open; parent #874 OPEN/keep_open. Частичная source-публикация не закрывает собственные критерии дочернего Issue и весь эпик. Не повторять HWID scoped PASS или waived burst. Один полный оставшийся checklist — [SERVICE_CAMPAIGNS](../SERVICE_CAMPAIGNS.md#оставшийся-late-checklist); обязательные prerequisites не подменяются фиктивным согласованием.
