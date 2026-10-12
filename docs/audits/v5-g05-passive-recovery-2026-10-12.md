# G-05 — пассивная проверка production recovery/no-replay, 2026-10-12

## Provenance, scope и baseline

- **Дата stdout:** `G05_UTC=2026-10-12T15:54:56.831789+00:00` = **2026-10-12 18:54:56.831789 Europe/Helsinki, EEST (UTC+03)**. Оператор предоставил агрегированные результаты в сообщении от 2026-10-12 15:55:41 UTC. Это **operator-supplied terminal evidence**, а не независимый SSH/VPS access агента.
- **Target:** production Master, только чтение существующего SQLite v13 в `bot` через `file:/app/data/bot.sqlite3?mode=ro`, `PRAGMA query_only=ON`, транзакционный snapshot; cohort ограничен `ALLOWED_TELEGRAM_IDS`, webhook/job summary — global aggregate без IDs или содержимого логов. Не использовался provider API и не инициировался сетевой/финансовый mutation.
- **Published:** immutable `v5.0.0-rc.9`, tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; **Deployed:** тот же RC только по предыдущему operator-supplied G-01 read-back (2026-10-12 17:36 EEST, image `sha256:efb2fb9ea3dffac70a3ca344d7843cabff67ae737875b461464e0b0705483f4c`), в G-05 повторной version/image проверки нет; **Accepted:** overall v5 **NOT PASS**.
- **GitHub baseline:** перед checkpoint `main` `4bd95dd04e82a90eba8b68b855dc8b745d71803b`, [PR #556](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/556) MERGED, post-merge [Python checks 38271938574](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38271938574) **PASS**; immutable tag ≠ `main` ≠ deployed ≠ accepted.

## Фактический вывод пакета

```text
G05_UTC= 2026-10-12T15:54:56.831789+00:00
G05-1 FULFILLMENT: PASS pending= 0 stale_pending= 0 stale_provisioning= 0 failed= 0
G05-2 QUOTA_UNKNOWN: REVIEW uncertain= 0 legacy= 1 failed= 0 stale_pending= 0
G05-3 EVENT_RECOVERY: PASS recoverable= 0 stale_received= 0
G05-4 JOB_RECOVERY: PASS stale_running= 0 unknown_24h= 0 failed_24h= 0
G05_DISPOSITION: read_only_observation; gate=PARTIAL
```

| Под-проверка | Что реально проверено | Scope disposition |
| --- | --- | --- |
| G05-1 | Для paid pilot entitlements нет `pending`, aged `pending/provisioning` по диагностическому порогу 10 минут, `failed` | **PASS** в snapshot; не доказательство успешной recovery после специально созданного сбоя |
| G05-2 | Среди finite-traffic paid pilot entitlements `unknown/in_flight=0`, `failed=0`, aged pending=0, но **`legacy=1`** | **REVIEW**: `legacy` отдельно от `unknown`; ручная reconciliation, без reset/retry |
| G05-3 | Глобальные `signature_valid` payment events `failed/payment_not_found` recoverable=0 и aged `received`=0 | **PASS** текущей очереди; no evidence реального delayed delivery/replay |
| G05-4 | Глобальные job runs: `running` старше 6h=0, `unknown/failed` за 24h=0 | **PASS** в snapshot; `job_failed` natural event не наблюдался, [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466) по-прежнему OPEN/PENDING |

**Итог:** **3/4 scoped PASS и 1/4 REVIEW; G-05 остаётся PARTIAL**, весь V5-A-002 и общий v5 acceptance **NOT PASS**. Порог 10 минут — диагностический, не официальный SLA. Нет data race proof, боевых injection/restart/recovery или подтверждения отсутствия future unknown.

## Отдельный разбор `legacy=1`

- Опубликованный `db_migrations.py`, migration 0011: при добавлении durable quota-reset journal **ранее существующим entitlements присваивается `quota_reset_status='legacy'`**, поскольку прошлый сброс трафика нельзя подтверждать задним числом. Это **не синоним** `unknown` и не доказательство, что quota reset выполнялся/не выполнялся.
- `commerce.py` запрещает автоматический повтор provisioning при `legacy`, `in_flight`, `unknown` и требует ручной operator review. **Никакой `bulkResetTraffic` в production не выполнять автоматически**, не менять SQLite status для косметического PASS.
- Связанная историческая задача [#317](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/317) **CLOSED** по своему уже завершённому bugfix-сценарию, но это не доказывает reset одной конкретной legacy-записи; повторение его теста не требуется. Результат этой проверки не даёт основания reopen/close Issue.
- Для legacy row нужны только privacy-preserving read-only cross-check текущего `entitlement`/плана/статуса и ограниченного provider current-state (если релевантно); отсутствие evidence = **PENDING/REVIEW**, не manual repair.

## Согласие оператора и граница следующих тестов

Оператор в том же сообщении от **2026-10-12 18:55:41 EEST** разрешил рассмотреть **production restart**, искусственные provider failures и повторное выполнение payment operations для controlled G-05 acceptance. **В рамках этого пакета ни одно из таких действий НЕ выполнялось.** Разрешение не является результатом тестов и не превращает `unknown`/финансовый replay в безопасную повторную мутацию.

Безопасная последовательность: (1) закончить этот Roadmap/Issue checkpoint; (2) приватный операторский preflight, наличие актуального проверяемого backup/rollback и отсутствие опасных inflight/quota/reconcile операций; (3) ограниченный restart одного bot container только при выполнении стоп-условий, затем health/CI-independent read-back; (4) provider fault injection и payment duplicate/late/unknown **в изолированном fake-provider + disposable SQLite окружении без реальных Telegram Stars/3x-ui mutations**, с точным release SHA, сравнением journals before/after. Реальное повторное списание/refund/forced unknown по production payment не выполнять вслепую: **нельзя повторять фактическую внешнюю платёжную mutation при `unknown` без provider-side подтверждения**. Каждый следующий пакет 3–4 scoped проверки — отдельный checkpoint; никакой deploy/upgrade/host restart, fake `job_failed` и waived W-01/W-02.

## Issues и следующий шаг

- [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466) **OPEN**: G05-4 zero recent failures ≠ доказательство natural production alert; не имитировать `job_failed` ради закрытия.
- [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) **OPEN**: Master→Node restart/recovery/side state не доказаны.
- [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) **OPEN**: новая возвратная policy отложена до будущего RC; G-05 не включает refund implementation.
- [#317](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/317), #342 и #422 **CLOSED** по самостоятельным критериям; не переоткрывать без отдельного confirmed finding.
- **W-01** (DR) `SKIPPED/WAIVED/NOT TESTED`, **W-02** (Telegram burst) `INCONCLUSIVE/WAIVED` без повторения. G-01…G-04 сохраняют PARTIAL, G-06…G-08 PARTIAL, G-09…G-11 PENDING.

**Checkpoint:** верхний `docs/ROADMAP.md` + собственная строка G-05 канонической таблицы → docs-only PR, required `test`/`title`, squash merge, independent `main` read-back и Issue closure audit **до** следующего пакета. Переход к controlled tests остаётся PENDING до этого checkpoint.
