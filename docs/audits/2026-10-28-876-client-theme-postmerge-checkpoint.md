# #876 — source в main; security prerequisite перед RC27

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-28 00:42 UTC+03:00
- **Окружение:** GitHub / CI / локальные offline fixtures; без VPS/Telegram/provider операций
- **Цель:** зафиксировать фактический source merge #876 и release-blocking security finding до дальнейших изменений.
- **Версия и immutable tag/SHA:** source main `976fc28422ff7cc4db1e8541132a5218f4f095cc`, APP_VERSION 5.0.0-rc.26; новый tag N/A — RC27 ещё не подготовлен/Published. Фактический Published RC26 `b2f7503387fc7bd8465e783c898a0697ec87c541`.
- **Scope:** Owner/default-off theme/source regression/required CI и fresh image audit. Не реальное Telegram право, доставка, deployed dependency или production acceptance.
- **Фактический результат:** PARTIAL
- **Источник и evidence:** [#965](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/965) exact head `2d9020dac893e48a57d7bbbb0123dd117aa65b76`, squash `976fc28422ff7cc4db1e8541132a5218f4f095cc`, MERGED 2026-10-27T21:38:03Z. Required [Python40587572356](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40587572356)/job122483003534 SUCCESS, 1739 tests/3 skipped за217.022s; [final title40588305882](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40588305882)/job122485566991 SUCCESS; actual CLEAN подтверждён перед squash. Main [40588400779](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40588400779)/job122485912964 SUCCESS. Fresh [Supply-chain40588425118](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40588425118)/job122486005382 на том же source SHA, event workflow_dispatch — **FAIL**, actionable HIGH/CRITICAL gate.
- **Ограничения и остаточные риски:** dnspython2.8.0/CVE-2026-114605 HIGH требует исправления2.9.0 и fresh scan PASS до RC27. Bot eligibility/реальные emoji IDs/разрешённый deployment и собственный targeted client rendering/fallback outcome PENDING; локальные veto OFF, DB default disabled. Действующий deployed rc.18.10/schema15 — только operator-reported, package version на VPS не проверена.
- **Связанные Issues:** #876, #966
- **Решение по Issues:** #876: keep_open, #966: keep_open
- **Следующий шаг:** required CI/merge/independent main read-back этого implementation/finding checkpoint; затем минимальный security prerequisite #966 отдельным PR, без unrelated upgrades/CVE waiver; fresh audit PASS и обязательные checkpoints до RC27. #482 пока не начинать.
- **Раздельные состояния:** merged=#965/source976fc284; published=RC26 `b2f7503387fc7bd8465e783c898a0697ec87c541`, RC27 BLOCKED; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15, independent read-back PENDING; accepted=source/test scoped PASS, security gate FAIL, собственный runtime #876 PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## Source и trust-boundary review

Локальный final full suite1739/16 environment skips PASS за95.710s; final targeted80 PASS за5.788s: 30 theme tests, общий living invariant, current-doc/RBAC/client-flags regressions. Compileall, command catalog, OpenAPI55, Living Docs/language/semantics/governance/diff PASS. Independent GitHub reconciliation перед source PR: Published26/referenced76/assertions39/active39 PASS. Первоначальные ошибки порядка нормативных UI/CLIENT sections исправлены; final suite PASS. Изолированный старый client-flags test сначала не имел обязательных fixture env, повтор с синтетическими значениями PASS; production .env не использовался.

25 semantic slots используют неизменные labels/callbacks/copy/URL и Unicode fallback. Owner/private/bot panel/видимая keyboard/nonce/TTL/CAS, роль внутри transaction, cancel-in-flight и bounded metadata input проверены. New command/alias нет. Один JSON+audit в existing runtime_settings, schema17 без DDL/backfill, новых dependencies/привилегий/credentials/портов нет. Конфигурационный bot-bound eligibility veto нельзя заменить RBAC или metadata lookup.

Client context действует только в matched private handler/том же chat и отзывается даже у delayed child task. Fake Dispatcher/session показывает отсутствие custom emoji в admin scope. New send сначала Unicode с exact receipt, далее максимум1 cosmetic edit; failure/unknown не создаёт второй send. Только exact same-request pinned-SDK HTTP400 разрешает один Unicode edit того же panel; фактический SDK test500/error_code400/retry_after не даёт replay. Ошибки не достигают generic admin edit→new-send fallback; circuit возвращает следующие переходы к Unicode. Существующие финансовые/provider mutations не повторяются. Невалидный UTF-16 не порождает новые entities/сырой exception.

## Security finding #966 — не обойдённый gate

Fresh audit действительно установил hashed lock, проверил dependency/license, построил image и SBOM, затем actionable vulnerability gate обнаружил dnspython2.8.0/CVE-2026-114605 HIGH, fixed2.9.0. Artifact12772992027 сохранён штатным CI. Нельзя трактовать предшествующие зелёные steps или старый scanner PASS как PASS этого source image.

[Upstream advisory](https://github.com/rthalley/dnspython/security/advisories/GHSA-45c3-73f7-pv4m) подтверждает affected<2.9.0 и исправление2.9.0 для excessive CPU при недоверенных DNS wire данных. Дубликатов dnspython Issues не найдено; #966 создан **до** dependency edits. Требуются минимальный floor/hashed lock update, offline DNS/API compatibility и новый source/image audit. Exploit/production DNS load не запускался; deployed library version и фактическая внешняя экспозиция неизвестны.

#966 — обязательный security prerequisite текущей выбранной задачи #876 перед её релизом, не следующая самостоятельная feature пула. Оба PR должны честно войти в release-scope; скрытого исключения или ослабления scanner gate нет. Отдельный source/build acceptance #966 не доказывает production устранение риска, #890 сохраняет собственный runtime acceptance.

## Собственный scope #876

Все восемь групп acceptance перечитаны: editor/reset/restart persistence; semantic bindings/screens; button field/typed UTF-16; admin/status/authorization isolation; bad ID/capability/error/unknown Unicode fallback; injection/stale/role/rollback; regressions и отдельно разрешённый pilot; canonical docs/required checks/release states. Source/fake scope PASS. Настоящие BotFather-owner Premium/Fragment evidence, реальные IDs/Telegram rendering, deployment и targeted fallback/disable outcome отсутствуют; #876 OPEN/keep_open. Полный оставшийся checklist — [CLIENT_SETUP](../CLIENT_SETUP.md#оформление-клиентских-значков-876). Старые HWID scoped PASS/waived burst не повторять.
