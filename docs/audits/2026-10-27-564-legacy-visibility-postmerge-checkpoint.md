# #564 — видимость legacy-команд: post-merge checkpoint

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-27 10:57 UTC+03:00
- **Окружение:** GitHub / CI / локальный synthetic Python3.12, без VPS/Telegram/provider операций
- **Цель:** подтвердить merge #943 и фактический implementation state #564 до отдельного rc.23 release-prep.
- **Версия и immutable tag/SHA:** #943 squash main `c738701a606ab92b4a4e94ae3f3053b52d8fbb82`; exact PR head `31c6a66e53e6ca9b18a3cad2c2e439c8c1dc13da`, base `0de289a1b5366bf84601dcd29623f18f8fb646da`; Published v5.0.0-rc.22 `d7739ed8e71444b310e7dbc5bde83f7706dfdb83` без #564.
- **Scope:** active-only справка, полная typed registry/AST проверка скрытых legacy handlers, сохранённые guards/redirects/roles, unit/source review и independent PR/main read-back. Не production deployment/live acceptance.
- **Фактический результат:** PASS
- **Источник и evidence:** [PR #943](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/943) MERGED; independent GitHub PR/main REST read-back. [Final-head Python40469662196](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40469662196) SUCCESS (1596 tests, 3 skipped), [final title40469961373](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40469961373) SUCCESS. Локально targeted14/full1596 (16 environment skips, включая отсутствие Nginx), docs/targeted47 после уточнения checklist, compileall/OpenAPI/catalog/Living Docs/semantics/diff PASS. [main Python40470074849](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40470074849) SUCCESS и fresh [supply-chain40470091691](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40470091691) SUCCESS на implementation SHA; итог независимо прочитан 2026-10-27 10:58 UTC+03:00.
- **Ограничения и остаточные риски:** глобальное меню команд Telegram не менялось и не считается очищенным. Handler compatibility сохраняется; визуальная видимость текущего deployed UI не проверена. Исторический N03 не подтверждает новый UI, но не требует повторного полного старого smoke. Схема v15/env/порты/dependencies не меняются; будущий upgrade требует cumulative compatibility review.
- **Связанные Issues:** #564
- **Решение по Issues:** #564: keep_open
- **Следующий шаг:** required CI и merge этого docs-only checkpoint, independent main read-back; затем rc.23 release-prep с единственным самостоятельным scope #564. Собственный поздний deployment и адресная визуальная проверка новой справки/Back отложены в конец #930; неизменённые N03/guard/role paths повторно не проверять без finding.
- **Раздельные состояния:** merged=#943 `c738701a606ab92b4a4e94ae3f3053b52d8fbb82`; published=v5.0.0-rc.22 без #564; deployed=v5.0.0-rc.18.10 `dae205ac82762723448f93827b981f89ae622231` только operator-reported, independent VPS read-back PENDING; accepted=offline/PR CI scoped PASS, собственный #564 visibility outcome PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## Проверенные границы

`commands_help_text()` валидирует полный registry до фильтра `status=active`. Поэтому скрытая malformed запись не исчезает из контроля. Все 6 slash entries остаются в `COMMANDS`; AST checker не менялся и требует скрытые legacy handlers. Удаление create из registry и неизвестный hidden status приводят к fail-closed regression. Административный `/admin`, dashboard.view и кнопка справки сохраняются для Read-only/Support/Administrator/Owner; экран не запускает handlers, не вызывает Telegram set/delete commands и не меняет global registry.

Сохранены оба slash handlers `/create`/`/inbounds` и saved callbacks create/inbounds/subscription. Новая подсказка указывает `/start`; прежние portal/allowlist/rate guards не ослаблены. Synthetic tests используют настоящие guard functions и FeatureSnapshot: env veto с DB override, DB OFF, unavailable/missing flags, отсутствие actor/чужой allowlist и общий rate limit отказывают до profile/menu. Redirect callback вызывает только profile read; slash не обращается к service. В fake service нет mutation methods, реальных API/отправок не было.

Targeted14 включает 7 catalog/AST/RBAC cases и 7 runtime redirect/guard cases; дополнительный Living Docs invariant держит UI visibility отдельно от authoritative audit. Local full1596/16 skipped PASS; после уточнения только deferred checklist docs/targeted47 PASS, final-head CI1596/3 skipped PASS. Старый CI на e20e9d9 не использован как финальный; checklist/title заполнен после Python success на 31c6a66. README/UI/CLIENT_SETUP/V5 acceptance/CHANGELOG согласованы, нормативные Git/release/AGENTS contracts не менялись.

## Собственный acceptance

Dated planned rc.21 из 16.10 явно заменён rc.23 по #930 в Issue; новый Published пока не утверждается. #564 OPEN/keep_open по собственному критерию deployment + operator-reported новой видимости справки. Старый N03 сохраняет исторический scope; минимум поздней проверки — только новая active-only видимость/основной start/Back в разрешённом пилоте. Полные старые guard/role paths покрыты source/offline tests, production flags ради них не переключаются. #356 не переоткрывается; следующий самостоятельный scope после RC23 publication checkpoint — #874/rc.24.
