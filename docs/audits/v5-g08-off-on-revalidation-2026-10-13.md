# G-08 — повторный read-only snapshot подтверждает Stars OFF → ON (2026-10-13 EEST)

## Provenance и исходные границы

- **Источник:** оператор прислал в чат 2026-10-12 22:59:34 UTC три обезличенных stdout `BASELINE`, `STARS_OFF`, `RESTORED` за 2026-10-12 22:58:21, 22:58:57, 22:59:28 UTC (**2026-10-13 01:58:21, 01:58:57, 01:59:28 EEST**). Это данные скриптового read-only наблюдения, **не** самостоятельный VPS/Telegram/API read-back агента. Исходный скрипт/traceback недоступны, точное состояние Owner UI или precheckout им не подтверждены.
- **Target:** production Master, `APP_VERSION=5.0.0-rc.9`, `PILOT_SIZE=3` во всех снимках; published immutable prerelease `v5.0.0-rc.9` tag commit `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`. Последний deployed rc.9 ранее operator-reported, **здесь нет** image/build SHA read-back. Предыдущий protected main `9d334fbe9cbd06ce9340e904993b0529fe495a6b` (PR #570). Accepted v5: `NOT PASS`; public rollout `BLOCKED`.
- **История не переписана:** [первый STOP audit](v5-g04-g05-g08-readonly-snapshots-stop-2026-10-13.md) сохраняет неуспешную раннюю стадию `STARS_OFF` с `db_stars=true effective_stars=YES revision=2` и `STOP: failed closed on incompatible DB: RuntimeError` (01:48 EEST). Повторный успешный snapshot **не объясняет root cause** первой остановки и не даёт права назвать её повреждением DB или runtime defect.

## Три новых operator-supplied снимка

| Поле | BASELINE 22:58:21 UTC | STARS_OFF 22:58:57 UTC | RESTORED 22:59:28 UTC |
| --- | --- | --- | --- |
| `APP_VERSION`, pilot | `5.0.0-rc.9`, 3 | то же | то же |
| `env_portal`, `env_stars`, `db_portal` | `true/true/true` | `true/true/true` | `true/true/true` |
| `db_stars` | `true` | **`false`** | **`true`** |
| `effective_stars` | `YES` | **`NO`** | **`YES`** |
| `stars_revision` | `2` | **`3`** | **`4`** |
| `G08_STARS_SWITCH_AUDIT_EVENTS` | `2` | **`3`** | **`4`** |
| `G08_ACTIVE_WORK_PREFLIGHT` | `CLEAR` | `CLEAR` | `CLEAR` |
| `G04_REFUND_CURRENT` | `success=4 payment_refunded=4 active_entitlement=4 missing_entitlement=0 owners=1 owners_with_other_confirmed_active_entitlement=1` | то же | то же |
| `G04_POLICY` | `rc9_payment_status_only; provider_revoke=NOT_PROVEN` | то же | то же |
| `G05_CONTEXT` | `legacy=1 legacy_active=1 quota_inflight_unknown_failed=0 pilot_provisioning=0 pilot_refund_inflight_unknown=0 running_jobs=0` | то же | то же |
| `PILOT_LEDGER_COUNTS` | `orders:5 payments:5 entitlements:5 refunds:4 events:5` | **то же** | **то же** |
| `PILOT_LEDGER_DIGEST_SHA256` | `09802fd1d96e35a14f44d821a8a1474e4ff779ff8b4dd5d811d0222050c9db1d` | **совпадает** | **совпадает** |

**Измеренный результат:** два последовательных изменения DB Stars (`true→false→true`), effective Stars (`YES→NO→YES`), revisions `2→3→4`, audit events `2→3→4`, при неизменном pilot ledger digest во **всех трёх** снимках. **G08-B и read-only компонент G08-E: scoped operator-reported PASS** именно для flag/audit transition. Это также G05-C `DIGEST_SAME=YES` для всех трёх snapshot. `G08_ACTIVE_WORK_PREFLIGHT=CLEAR` ограничен категориями, читаемыми скриптом.

## Disposition и оставшиеся проверки

- **G08-A: PARTIAL:** флаги перед OFF = ON и счётчики active work `CLEAR`, но в этой серии нет независимого health, Full Backup freshness/deep validation, Telegram precheckout-in-progress или build identity evidence; предыдущие отдельные G05 health/backup PASS остаются историческими.
- **G08-B: scoped PASS:** реальный `db_stars=false`, `effective_stars=NO`, revision 3, audit 3; нет подтверждения фактического Owner UI экрана, хотя наблюдаемая DB-последовательность соответствует одному выключению.
- **G08-C: PENDING/NOT RUN:** не проверен пользовательский отказ нового Stars invoice/callback и server-side `pre_checkout_query` при OFF; **не** запускать Stars payment или старый payable invoice.
- **G08-D: PARTIAL:** неизменный pilot ledger во всех трёх snapshot (digest + counts) подтверждён в пределах охвата скрипта, но доступность `/admin`, `/start`, действующего VPN клиента/provider и Health при OFF/после ON **не** доказана этим выводом. Digest не включает внешний Telegram/3x-ui.
- **G08-E: scoped PASS только DB/effective flag restoration и audit**: `db_stars=true effective_stars=YES revision=4 audit=4`. Отдельный финальный Health/Owner UI read-back не представлен.
- **G-08 в целом: PARTIAL** (вместо раннего `BLOCKED`); ни полный emergency-stop acceptance, ни общий v5 acceptance не получили PASS. Не повторять обычный OFF→ON просто ради дополнительного smoke. Уже полученный `successful_payment` при OFF/правильность precheckout требуют isolated CI/evidence или отдельного согласованного безопасного scope, не реального списания.
- **G-04: PARTIAL** — прежние refund aggregates те же, `active_entitlement=4` и другой confirmed active entitlement у владельца; `rc9_payment_status_only`, [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) будущая policy OPEN, provider revoke NOT PROVEN. Нет нового Master/Node evidence.
- **G-05: PARTIAL** — `legacy=1/legacy_active=1` REVIEW; active work counters 0; `unclassified=1` Master API прежний INCONCLUSIVE; interrupted-work/no-blind-replay PENDING. Улучшено именно G05-C, теперь есть digest и на этапе OFF; `ISOLATED_ONLY` для будущего failure injection.

## GitHub checkpoint, Issue audit и next

Этот audit и актуальная верхняя сводка `docs/ROADMAP.md` подлежат docs-only PR с required `test`/`title`, squash merge, postmerge CI и независимым `main`+Issue read-back. **До завершения checkpoint следующий smoke PENDING.** В этой работе агент не инициировал Telegram Owner switches, purchases, refunds, VPS writes, restart/deploy, provider mutations или разрешение public launch.

**Issues:** #342/#317/#422 остаются CLOSED по собственным завершённым scoped criteria; #433/#466/#487/#510/#564 OPEN по несвязанным/незавершённым критериям. Новый runtime bug не следует автоматически из первого `RuntimeError`, который теперь исторически сохраняется; новый Issue нужен только при подтверждённом самостоятельном defect. **Next после checkpoint:** обсудить лишь недостающий evidence без повтора OFF→ON (зафиксировать UI outcome, Health, immutable deployment identity либо existing isolated tests, если доступны); G-09/G-10 — только естественные события, G-11 — финальный disposition.
