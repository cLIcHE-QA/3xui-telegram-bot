# #947 — source-only основа кампаний: post-merge checkpoint

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-27 16:29 UTC+03:00
- **Окружение:** GitHub / CI / локальные synthetic Python3.12 и временные SQLite; без VPS/Telegram/provider операций
- **Цель:** подтвердить implementation merge #951 и собственный source-only scope #947 до отдельного RC24 release-prep.
- **Версия и immutable tag/SHA:** #951 squash main `114619c9086d4e2dfff263b04ca75467c6a3862e`; exact PR head `22417b732057e6466022d3541463382e96dee510`, base `bfa4daa5b5b6379cde61942aa57027e949596777`. Published v5.0.0-rc.23 `110bfc4ce9131a366be7ca3503e22ee6349c7372` без новой foundation/schema16.
- **Scope:** additive migration16, default-deny owned drafts/revisions, trusted private-observation API без runtime adapter, bounded aggregate candidate dry-run, offline regression/security review/required PR checks и независимый PR/main read-back.
- **Фактический результат:** PASS
- **Источник и evidence:** [#951](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/951) MERGED; independent GitHub REST PR/main read-back 2026-10-27 16:28 UTC+03:00. [Final-head Python40480838527](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40480838527) SUCCESS (1616 tests / 3 skipped, job122110439512), [final title40512184340](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40512184340) SUCCESS. Local targeted19/full1616 (16 environment skips), compileall/OpenAPI/slash catalog/living docs/semantics/governance/diff PASS. Main Python40512294154 и fresh supply-chain40512333699 запущены на squash SHA; их результат пока PENDING, не включён в этот scoped PASS.
- **Ограничения и остаточные риски:** parent #874 реализован только частично; #948/#949, policy #501, abuse/privacy/media/CTA/allowlists, deployment и pilot delivery не завершены. Равенство actor/chat IDs не является Telegram authentication: adapter обязан получать их из authenticated update и пока отсутствует. Нет semantic advertising/secret detector; ограниченная shape validation не заменяет operator review. Source schema16 не применяется на VPS публикацией.
- **Связанные Issues:** #947, #874
- **Решение по Issues:** #947: keep_open, #874: keep_open
- **Следующий шаг:** required CI и merge этого docs-only checkpoint, independent main read-back; после подтверждения main/supply-chain — RC24 release-prep, публикация/immutable proof и отдельный own closure checkpoint #947. Следующий самостоятельный #948 начинается только после штатного publication checkpoint.
- **Раздельные состояния:** merged=#951 `114619c9086d4e2dfff263b04ca75467c6a3862e`; published=v5.0.0-rc.23/schema15; deployed=v5.0.0-rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported, independent VPS read-back PENDING; accepted=source/offline/PR CI scoped PASS, parent runtime PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## Regression и trust boundary

19 targeted tests проверяют default-deny/exact-True Owner authorizer и все owned операции/IDOR, CAS/concurrent edits, immutable frozen revision и idempotent freeze, clock/errors/commit unknown без replay, private actor/chat/human/existing user без backfill, delete/recreate/blocked, local group include/exclude и missing group fail closed, bounded list8/candidate1000 без recipient projection, payload/control/markup/credential/URL shapes включая bare domain/IDN/mailto/tg, corrupt/deep JSON и failed future migration journal. Только synthetic fixtures, не production private-chat evidence.

Migration v15→16 сохраняет существующие данные, создаёт пустые ledgers, выполняется повторно без изменений и откатывает DDL при injected failure; failed journal запрещает replay. Проверены strict SQL definitions/constraints/indexes/triggers и отказ принять unjournaled contact ledger; downgrade catalog15 отказывается от schema16. Исторические steps1…15 не переписаны; historical feature assertions сохраняют свои data/behavior checks.

Candidate count не означает eligibility/consent/reachability. Все три category возвращают deliverable=0/unapproved; нет recipients/jobs/sends, transport import или runtime assembly. Нет новых env/credentials/портов. Owner/recipient IDs и body не попадают в public DTO repr/error/log. Frozen identity защищена SQL ownership/immutability triggers; SQL параметризован, local group deny совпадает с audience.py. DAO открывает только существующую БД и проверяет полный successful journal; не создаёт/не чинит schema.

## Собственный closure audit

Первые шесть source-only acceptance групп #947 доказаны кодом/regressions/PR CI; седьмая требует immutable RC и publication/Roadmap/main checkpoint. Поэтому #947 остаётся OPEN/keep_open до собственного publication audit, без искусственного требования реальных отправок. Parent #874 остаётся OPEN независимо от завершения дочерней foundation. README/ADMIN_SETUP/SQLITE_MIGRATIONS/CLIENT_SETUP/V5 acceptance/SERVICE_CAMPAIGNS и living-docs rule/invariant обновлены; UI_STYLE reviewed N/A, экранов/slash/callbacks нет.

