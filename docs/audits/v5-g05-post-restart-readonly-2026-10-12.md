# G-05 — пострестартовая read-only сверка журналов (2026-10-12)

## Provenance, дата и точный scope

- **Время snapshot из stdout:** `G05_UTC=2026-10-12T17:05:20.934100+00:00` = **2026-10-12 20:05:20.934100 Europe/Helsinki (EEST, UTC+03:00)**. Оператор прислал агрегированный вывод **2026-10-12 17:05:32 UTC**. Это `operator-supplied` evidence, **не** независимый SSH/VPS read-back агента.
- **Environment/target:** действующий `bot` container production Master, один SQLite snapshot `file:/app/data/bot.sqlite3?mode=ro` c `PRAGMA query_only=ON` и `BEGIN`. `APP_VERSION=5.0.0-rc.9`, `PILOT_SIZE=3` (размер `ALLOWED_TELEGRAM_IDS`, не количество платящих клиентов). G05-P1/P2/P3 ограничены `paid` `XTR` orders из пилотной allowlist; G05-P4 — агрегаты глобальных payment events/job runs. Запросы не выводили Telegram ID, order/payment IDs, subscription URLs, tokens или provider payload.
- **Published:** immutable prerelease [`v5.0.0-rc.9`](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.9), tag/commit `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`. **Deployed:** прежний operator-supplied G-01/R6 production checkout/container read-back по этому tag/SHA, в этом snapshot заново подтверждена **только** `APP_VERSION`, не host SHA/image build/полная provenance. Предыдущий [controlled bot-only restart](v5-g05-controlled-bot-restart-2026-10-12.md) 2026-10-12 19:38 EEST: один restart, post-health/DB/3x-ui PASS; restart проходил при нулевой активной работе. **Accepted:** общий v5 `NOT PASS`, G-05 `PARTIAL`.
- **GitHub baseline перед docs checkpoint:** protected `main` `bbd19d1a365ba75a343d2e7ddad21503de11202e` после [PR #560](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/560); post-merge [Python checks 38279979836](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38279979836) `success`. Это repository/CI proof, **не** production acceptance.
- **Нет state-changing операций в этом пакете:** не выполнялись deploy, restart, backup/restore, refund/Stars purchase, provider mutation, traffic reset, SQL writes, flags/toggles, искусственный `job_failed`, waived DR/W-01 или Telegram burst/W-02.

## Полученный обезличенный stdout

~~~text
G05_UTC= 2026-10-12T17:05:20.934100+00:00
APP_VERSION= 5.0.0-rc.9
PILOT_SIZE= 3
G05-P1 FULFILLMENT unresolved= 0 stale= 0
G05-P2 QUOTA uncertain= 0 failed= 0 legacy= 1
G05-P3 LEDGER payment_mismatch= 0 entitlement_mismatch= 0 refund_mismatch= 0
G05-P4 RECOVERY stale_events= 0 stale_jobs= 0 recent_job_errors= 0
G05_READ_ONLY=COMPLETED; ACCEPTANCE=NOT_AUTO_PASSED
~~~

## Результаты и границы доказательства

| Проверка | Ожидание / фактически просмотренная выборка | Получено | Scoped disposition |
| --- | --- | --- | --- |
| **G05-P1 — Fulfillment** | У `paid` `XTR` pilot orders нет entitlements в `pending/provisioning/failed`; нет `provisioning` старше 600 s | `unresolved=0`, `stale=0` | **PASS** в snapshot, не recovery interrupted work |
| **G05-P2 — Finite quota** | По finite-plan entitlements пилота нет `unknown/in_flight` и `failed`; исторический `legacy` сохраняется отдельно | `uncertain=0`, `failed=0`, **`legacy=1`** | **REVIEW**, не общий PASS и не основание для `bulkResetTraffic` |
| **G05-P3 — Payment/entitlement/refund linkage** | У `paid` XTR orders пилота ровно один `confirmed/refunded` `telegram_stars` payment и один entitlement; у `refunded` Stars payments есть хотя бы один `success` refund journal | Все три счётчика mismatch = **0** | **PASS** для этих трёх проверенных SQL-предикатов; **не** полная ledger reconciliation и **не** доказательство отсутствия duplicate refund operations или provider-side revoke |
| **G05-P4 — Recovery backlog** | Нет `received` signature-valid payment events старше 600 s, `running` jobs старше 6h, `failed/unknown` job runs за 24h | Все три счётчика = **0** | **PASS** для указанных счётчиков в snapshot; другие event states и natural `job_failed` notification не проверены |

**Диагностические пороги** 10 минут и 6 часов — фильтры этой выборки, не формальные SLA. Нулевые счётчики на одном снимке после рестарта не равны полному before/after diff: до рестарта отсутствует immutable набор totals/row identities payment, entitlement, refund и event journals, а G05-P3 проверяет ограниченные связи, а не все денежные/провайдерские postconditions. Поэтому **точное отсутствие финансового replay/двойного refund, периодов или remote traffic reset после interruption не доказано**. Проверка не включала authenticated Master/Node API, VPN clients или новую Health/DB probe.

**Итог пакета:** **3 scoped PASS + 1 REVIEW**, без найденного нового mismatch в проверенных SQL-предикатах, но **G-05 PARTIAL**. `legacy=1` — историческое состояние migration 0011 и не подтверждённый reset; не переводить в `success`, не делать автоматический retry. [Предыдущий пассивный baseline 18:54 EEST](v5-g05-passive-recovery-2026-10-12.md) и [restart 19:38 EEST](v5-g05-controlled-bot-restart-2026-10-12.md) сохраняют отдельные ограниченные results; G05-P1…P4 не являются новым restart/fault injection.

## Issue closure audit, остаток и следующий шаг

- [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) **OPEN/PENDING**: Master/Node version+GUID, exact inbound membership, node-side sync/recovery и offline outage fixture **не проверены** этим Master SQLite snapshot.
- [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466) **OPEN/PENDING**: нулевые `recent_job_errors` **не** подтверждают natural production `job_failed`, cooldown/reminder/recovery или Attention Center projections.
- [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) **OPEN/PENDING**: `refund_mismatch=0` проверяет наличие success journal для refunded payment, **не** сокращение entitlement expiry, provider access revoke или ещё не реализованную 14-дневную политику (плановый будущий scope).
- [#317](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/317), [#342](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/342), [#422](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/422) сохраняют **CLOSED/completed** по собственной ранее подтверждённой приёмке. Оснований переоткрывать нет.
- **Оставшиеся G-05 gates:** interrupted pending/provisioning/reconciliation restart; controlled delayed/duplicate/unknown/no-blind-replay cases; точное ledger before/after и provider postconditions. Реальные финансовые и provider mutations **не разрешены** данным snapshot; для fault/duplicate/replay предпочесть isolated fake-provider + disposable SQLite без реальных Stars/refunds. G-01…G-04 и G-06…G-08 **PARTIAL**, G-09…G-11 **PENDING**; W-01 `SKIPPED/WAIVED/NOT TESTED`, W-02 `INCONCLUSIVE/WAIVED` — не повторять. Общий v5 acceptance `NOT PASS`, public launch заблокирован.

**Checkpoint workflow:** это docs-only evidence по существующему G-05/V5-A-002, самостоятельного issue/fix scope нет (**Issue: N/A**). Обновить текущую верхнюю запись и G-05 строку в `docs/ROADMAP.md` через PR с required `test`/`title`, squash merge, independent `main`/audit read-back и комментарии evidence в затронутых Issues; только после этого разрешён следующий пакет. До merge утверждение о синхронизации с `main` **PENDING**.
