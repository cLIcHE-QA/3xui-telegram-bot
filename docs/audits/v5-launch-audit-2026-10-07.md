# v5 Client Portal Launch Audit — 2026-10-07

## Scope

Audit baseline: `main@81b54a0de5d0d892428affb4affbaa1f17845c91` after PR #307.

Scope covers the new v5 customer attack surface: Client Portal authorization/ownership,
Telegram Stars commerce, entitlement/provisioning boundaries, subscription credentials,
QR/onboarding, diagnostics, abuse controls and emergency rollback.

This document deliberately separates repository-verifiable evidence from production
acceptance. A green unit/CI run is not treated as evidence for Telegram/provider/network
behaviour that only exists in a real deployment.

## Automated / repository-verifiable controls

- **Ownership / IDOR:** Stars payload owner is checked against Telegram sender before
  pre-checkout, then order owner/currency/amount/status are revalidated by the
  provider-neutral service. Payment confirmation revalidates the same identity in the
  database transaction.
- **Customer/admin isolation:** Client UI uses `CustomerPortalService`; it does not
  import DB, XUI, CommerceService or admin callbacks directly.
- **Payment idempotency:** provider payment identity and provider event identity are
  unique/journaled; duplicate Stars confirmation reuses the existing payment and
  entitlement.
- **Secret handling:** subscription URL remains bearer-like; QR is generated locally,
  only in private chat, and is not sent to an external QR service.
- **Diagnostics:** customer diagnostics are read-only and do not trigger provisioning
  or reconcile mutations.
- **Abuse controls:** customer commands/callbacks use a bounded per-user sliding window;
  public signup remains closed behind explicit allowlist policy.
- **Rollback:** Client Portal and new payment acceptance have independent emergency
  switches. Disabling new payment acceptance does not discard an already delivered
  Telegram `successful_payment`.
- **Webhook hygiene:** generic provider ingress is HMAC authenticated, bounded to 64 KiB,
  journals digest/normalized metadata rather than raw secret-bearing payload, and
  rejects unsupported/invalid events fail-closed.

Regression contract: `tests/test_v5_launch_audit_contract.py` plus the existing
`test_v5_telegram_stars.py`, `test_payment_webhook.py`,
`test_v5_stars_production_hardening.py`, `test_v5_launch_readiness.py`,
`test_v5_client_onboarding_diagnostics.py` and commerce/provisioning suites.

## Findings / acceptance blockers

### V5-A-001 — production Stars payment acceptance

**Severity:** Release-blocking acceptance item.

Repository tests cannot prove Telegram production/test-environment delivery semantics.
Before v5.0.0, execute a provider-approved Stars flow using dedicated test identities:
invoice → pre-checkout → successful payment → local payment/order/entitlement →
provisioning → subscription use. Verify duplicate delivery and support/refund path
without direct DB repair.

**Status:** Open — production/internal acceptance required.

### V5-A-002 — production-like failure/restart/reconciliation canary

**Severity:** Release-blocking acceptance item.

Exercise delayed/duplicate payment delivery, temporary provisioning failure, node
unavailability and bot restart during background/reconciliation work. Verify no blind
mutation replay, no orphan/duplicate entitlement/client and explainable final state.

**Status:** Open — controlled canary required.

### V5-A-003 — production load/abuse/soak evidence

**Severity:** Release-blocking acceptance item.

The repository now has customer rate limiting, existing compat proxy bounds and
emergency switches, but expected public traffic has not been proven on the v5
deployment. Run command/callback spam, repeated diagnostics, bounded invalid input and
a soak covering scheduled jobs plus at least one restart/deploy cycle.

**Status:** Open — controlled canary required.

### V5-A-004 — privacy/retention review for customer commerce data

**Severity:** Medium / release-blocking policy review.

Confirm the intended retention/support policy for Telegram IDs, orders, payments,
entitlements, Terms acceptance and refund journal. Current implementation minimizes
webhook payload storage, but product/operator retention policy needs an explicit
disposition before broad public access.

**Status:** Repository policy disposition completed in `docs/DATA_RETENTION.md`.
Deployment operator must still confirm applicable business/legal retention obligations
before broad public launch.

## Current disposition

**CONDITIONAL / NOT YET PASS.**

No new repository-verifiable Critical/High ownership, payment-integrity or secret
exposure blocker was identified in this audit slice. V5-A-004 now has a repository policy disposition in `docs/DATA_RETENTION.md`.
v5.0.0 remains blocked by V5-A-001 through V5-A-003, which require actual
production-like/controlled-canary evidence using `docs/V5_PRODUCTION_ACCEPTANCE.md`.

Targeted V5-A-008 / #324 на immutable `v5.0.0-rc.4` получил **PASS 2026-10-08** по операторскому production retest; подробный scoped evidence добавлен ниже. Это не закрывает V5-A-001…V5-A-003 и не переводит общий launch audit в PASS.

Do not remove the customer allowlist or broaden the cohort based only on CI success.


## Canary finding V5-A-005 — expired access presentation/lifecycle

**Severity:** High / release-blocking correctness finding.

На `v5.0.0-rc.1` существующий customer profile отображался как `Подписка: активна` независимо от прошедшего `users.expiry_time`; durable active entitlement также не имел фонового expiry transition. Исправление должно вычислять effective customer status по expiry и локально переводить due active/suspended entitlement в `expired` без remote mutation.

**Status:** Fix in progress; требуется новый RC и повторный canary.


## Canary finding V5-A-006 — Telegram Stars admin ledger runtime crash

**Severity:** High / release-blocking operability finding.

На production canary `v5.0.0-rc.1` переход `Платежи → Telegram Stars` завершался необработанным `NameError: name 'aiosqlite' is not defined`. Stars ledger handler использует `aiosqlite.connect(db.path)` и `aiosqlite.Row`, но `business_admin.py` не импортировал runtime dependency.

**Fix:** явный `import aiosqlite` в `business_admin.py` и regression contract, подтверждающий наличие dependency и Stars ledger handler path.

**Acceptance:** `rc.1` считается failed canary и дальше не тестируется. После публикации `v5.0.0-rc.2` оператор обязан сначала открыть `Платежи → Telegram Stars` и подтвердить отсутствие exception; только вместе с PASS V5-A-005 разрешается продолжить Stars payment acceptance.

**Status:** Fix in PR #312; требуется новый RC и targeted retest.

## rc.2 production retest — 2026-10-08

Baseline: immutable `v5.0.0-rc.2` / `24272d61f87396d365522b0156dff5c3165c682c`.
Container running, `RestartCount=0`, Bot `5.0.0-rc.2`, Health/DB/3x-ui connectivity `ok`.
Фактические Master/direct node работают на 3x-ui `3.9.0` / Xray `26.9.30`; read-only version/status integration smoke — PASS.

Targeted retest:

- **V5-A-005 — PASS:** expired customer access отображается как `истекла`, не как active.
- **V5-A-006 — PASS:** `/admin → Платежи → Telegram Stars` открывается без runtime exception.
- Real Stars path дошёл до invoice, фактического списания 1 XTR, `payment #1 = confirmed`, `order #1 = paid`, `entitlement #1 = active`, сформированного subscription URL и доступного provider read.

### V5-A-007 — paid quota cycle сохраняет старый traffic

**Severity:** High / release-blocking correctness finding.

После подтверждённой покупки Plan с `traffic_gb=1` provisioning установил новый срок и `totalGB=1 GiB`, но не сбросил накопительные 3x-ui counters предыдущего периода. Клиент показывал около 10.47 GiB download + 1.14 GiB upload при новом лимите 1 GiB, 100% usage, 0 B remaining и inactive subscription.

Root cause подтверждён в repository code: `ProvisioningEngine.sync_user(..., apply_plan_limits=True)` обновляет `expiryTime`, `totalGB`, `limitIp`, но paid entitlement path не вызывает существующий one-shot `/panel/api/clients/bulkResetTraffic`. Дополнительно expiry рассчитывался как `now + duration`, что для активного renewal могло терять оставшийся оплаченный срок.

**Required remediation:** durable target expiry; renewal от `max(now, current_expiry)`; отдельный one-shot quota reset с persisted `in_flight/success/failed/unknown`; uncertain reset не replay'ится автоматически; локальный active expiry публикуется только после доказанного reset/skip.

**Status:** Fix merged via PR #318 (`ba4a25980ddb185dd5558d9387a8f4fe9cbed1c8`). `v5.0.0-rc.2` acceptance остаётся FAIL; требуется immutable `v5.0.0-rc.3` и targeted production retest quota/renewal/no-replay.

### UI finding #314

Low / non-blocking. Client Portal имел несколько presentation inconsistencies: home терял status icon, dynamic Stars plan rows не имели leading emoji, command/callback headings расходились. Fix merged via PR #318; на `v5.0.0-rc.3` требуется короткий UI regression, но finding не является причиной остановки commerce acceptance.

## rc.3 targeted production retest — 2026-10-08

Baseline: immutable `v5.0.0-rc.3` / `a4e1e9f5c28b54b209ce4a81b23e5d85a2c9f73a`.
Container `running`, `RestartCount=0`, Bot `5.0.0-rc.3`, Health/DB/3x-ui connectivity `ok`.
SQLite migration v11 применена: `schema_version=11`, `PRAGMA quick_check=ok`, column `entitlements.quota_reset_status` присутствует. Existing entitlement #1 после migration — `active/legacy`, без автоматического remote reset.

### V5-A-007 targeted result

**PASS по production quota/renewal/idempotent reconcile path.**

Перед новой покупкой finite Plan `Смок` имел duration 30 дней, quota 1 GiB, existing expiry `2026-11-07 00:34:29 UTC` и cumulative traffic около 11.6 GiB.

Одна новая Stars-покупка на rc.3 дала:

- order #2 = `paid`;
- entitlement #2 = `active`;
- `quota_reset_status=success`;
- old cumulative traffic `11.6 GB → 0 B`, новый limit 1.0 GB;
- expiry = `1796603669` = `2026-12-07 00:34:29 UTC`, то есть ровно +30 дней от previous expiry, а не от current wall clock;
- entitlement #1 сохранился `active/legacy` и не был автоматически переигран.

После генерации нового ненулевого traffic выполнен повторный application-level `EntitlementProvisioningService.reconcile(2)`. Before/result/after совпали: `2 active success 1791424988 1796603669`. Customer traffic остался ненулевым, expiry не изменился. Это подтверждает отсутствие second quota reset и second renewal increment для уже active/success entitlement.

Uncertain/lost-response reset no-replay покрыт repository regression tests и durable v11 state machine; намеренная fault injection в production paid customer flow на этом этапе не выполнялась. Controlled failure/restart evidence остаётся частью V5-A-002.

### Low UX finding #320

После successful Stars payment native invoice message остаётся визуально с кнопкой оплаты. Backend остаётся fail-closed для `order=paid` через pre-checkout validation, поэтому finding классифицирован Low/non-blocking UX. Issue #320 и roadmap item созданы отдельно; `rc.3` acceptance не останавливается.

## rc.3 production follow-up — V5-A-008, 2026-10-08

**High / release-blocking, issue #324. Full rc.3 acceptance PAUSED.**

### Что уже было проверено

- Exact immutable baseline: `v5.0.0-rc.3` / `a4e1e9f5c28b54b209ce4a81b23e5d85a2c9f73a`, container `running`, `RestartCount=0`, Health/DB/3x-ui connectivity `ok`, SQLite schema 11 / `quick_check=ok`.
- Новый finite paid quota: old 11.6 GB cumulative counters → 0 B после Stars Order #2; `payment #2=confirmed`, `order #2=paid`, `entitlement #2=active/success`, old `entitlement #1=active/legacy`; expiry до `2026-12-07T00:34:29Z` от предыдущего оплаченного expiry.
- Повторный `reconcile(2)`: before/result/after `2 active success 1791424988 1796603669`, ненулевой новый traffic остался ненулевым, срок не увеличился второй раз.
- Повторное локальное Stars confirmation с существующим charge identity и hash: `created=False`, тот же Payment #2/Order #2/Entitlement #2; ровно 1 payment и 1 entitlement, никакого нового Telegram API charge.
- #314 customer home/profile emoji PASS; V5-A-006 Stars admin ledger PASS; V5-A-005 effective-expiry presentation PASS после ручного изменения пользовательского срока, durable expiry не инжектировали; provider traffic/HWID read PASS.
- Пользователь первоначально сообщил PASS subscription import/update, VPN connection и internet via VPN. **Это доказательство относится к более раннему состоянию; после ручного изменения сроков полный working-access E2E не доказан.**
- Refund/support subtest и V5-A-002/V5-A-003/ownership/rollback/load/soak не завершались.

### Новый High finding

После manual expired-state regression пользователь вручную восстановил дату. Read-only provider/status snapshot:

- local bot `users.expiry_time=2026-12-07T20:59:59Z`;
- established `Entitlement #2.expires_at=2026-12-07T00:34:29Z`, различие **20 ч 25 мин 30 сек**;
- 3x-ui `expiryTime=2026-12-07T20:59:59Z`, `enable=False`;
- 3x-ui traffic `enable=False`, `totalGB=1073741824`, `up=3497602`, `down=335255925` (неизрасходованная квота);
- Client Portal по local expiry показывал `🟢 активна`, Admin показывал `⛔ отключён`, 3x-ui HTML subscription — `Неактивна`.

**Причина `enable=False` не доказана:** его могло вызвать ранее выполненное ручное изменение срока или иная admin/provider policy; не утверждать, что Stars оплатa выключила client. Root cause UI divergence — `CustomerPortalService.profile()` использовал только local expiry, игнорируя provider enable.

### Required fix/gate

- Отдельные состояния оплаченного периода / фактического provider access, read-only provider-neutral status path, unknown при provider read failure/expiry drift и согласованный UI/home/profile/diagnostics.
- Manual admin disable **не** отменяется оплатой или обычным customer refresh/reconcile; не выполнять automatic enable или expiry rewrite.
- Проверить explicit expiry source-of-truth/reconciliation policy: local/entitlement/provider mismatch должен быть виден и не скрываться автоматической правкой.
- PR/CI → новый immutable release candidate → targeted regression enabled/disabled/expired/unknown/drift без повреждения оплаченного entitlement → E2E connection/browser/traffic; только затем возобновить V5-A-001 refund и оставшийся full controlled acceptance.

Subscription URL/QR и user identity намеренно не включены в этот audit.


## rc.4 targeted production retest — V5-A-008, 2026-10-08

**Targeted disposition: PASS. Общий v5 production acceptance: NOT YET PASS.**

### Immutable baseline и evidence boundary

- GitHub prerelease: `v5.0.0-rc.4`.
- Exact release tag / source SHA: `d34b76d694a43d3f1d364cc01d9a88bc2b666ee5`.
- Scope: контролируемая production-проверка V5-A-008 / issue #324 после fix PR #325. Результаты реального VPN-теста и счётчиков подтверждены оператором 2026-10-08; это не самостоятельный повтор production-теста из CI/репозитория.
- Customer Telegram ID, subscription URL/QR, `sub_id`, access credentials и raw provider output в audit не публикуются.

### Фактический targeted acceptance

1. Provider-aware Client Portal корректно выявляет отключённый 3x-ui client, не объявляя доступ активным только потому, что Order/Payment/Entitlement и local expiry выглядят действующими.
2. Расхождение `users.expiry_time`, entitlement `expires_at` и provider `expiryTime` диагностируется явно; не выполняются неявное переписывание оплаченного срока или автоматическая разблокировка клиента.
3. После контролируемого операторского восстановления доступа и обновления subscription реальный VPN-клиент успешно подключился и получил доступ в интернет.
4. Read-back счётчика трафика до и после реального подключения подтвердил передачу данных:

   | Измерение | Наблюдаемое значение |
   | --- | ---: |
   | Трафик до | 323,1 MB |
   | Трафик после | 347,6 MB |
   | Прирост | **+24,5 MB** |

   Значения округлены до десятых MB; это наблюдаемые operator-provided counters, а не точные byte-level telemetry или throughput benchmark.

Итог: V5-A-008 **PASS** в пределах проверенного сценария **disabled detection → expiry-drift diagnostics → controlled restore → subscription refresh → VPN connect → internet access → traffic increase**. Исходная причина `enable=False` на `rc.3` не доказана и не приписывается Stars payment/provisioning. Regression-инварианты unknown/provider unavailable и запрета blind replay остаются repository-covered; production fault injection этих отдельных сценариев данным retest не заявляется.

### Решение и оставшиеся gates

- Issue [#324](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/324) уже находится в `closed/completed`; targeted production evidence подтверждает закрытие finding, повторно закрывать issue не требуется.
- V5-A-001 остаётся открытым до контролируемого Stars refund/support acceptance; V5-A-002 — до failure/restart/no-replay/reconciliation; V5-A-003 — до abuse/load/soak. Отдельно не завершены ownership/IDOR, rollback и финальная reconciliation.
- Продолжение только по `docs/V5_PRODUCTION_ACCEPTANCE.md` после актуального health/preflight и явного операторского решения для каждого state-changing теста. Pilot allowlist сохраняется; stable `v5.0.0` и broad public access этим PASS не разрешены.


## rc.4 Stars refund production smoke — V5-A-009, 2026-10-08

**High / release-blocking, issue [#328](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/328). Targeted refund: FAIL. Full v5 acceptance: STOP/NOT PASS.**

Baseline: immutable `v5.0.0-rc.4` / `d34b76d694a43d3f1d364cc01d9a88bc2b666ee5`. Health/SQLite v11/3x-ui connectivity перед тестом — PASS. Admin Stars ledger, payment detail и двухэтапный warning/confirm screen — PASS. На подтверждении возврата по контролируемому тестовому 1 XTR payment aiogram зарегистрировал `NameError: name 'run_stars_refund' is not defined` в `business_admin.stars_refund_run`.

Root cause verified against source: `business_admin.py` обращается к `run_stars_refund(...)`, но не импортирует существующую функцию из `stars_refund.py`. Python `NameError` возникает до вызова helper, следовательно **в этом callback не выполнены** `db.begin_stars_refund` и `Bot.refund_star_payment`. Независимый production journal/provider read-back не проводился: возврат/получение средств не объявлять успешным, однако и не приписывать внешнюю mutation упавшему handler.

Required fix: явный import, regression coverage интеграции admin callback с one-shot refund helper, CI → новый immutable RC. Не replay'ить refund при `unknown`, не переписывать rc.4 и не создавать новый реальный платеж ради проверки. После деплоя проверить journal состояния выделенного тестового платежа, получить отдельное согласие на одну новую refund mutation и проверить `payment=refunded` / journal `success` / подтверждение Telegram. Возврат сам по себе не отзывает entitlement/provider access; это отдельная policy.

Customer identifiers, charge identity и subscription URLs в audit не включены.


## rc.5 Stars refund targeted production retest — V5-A-009 PASS, 2026-10-08

**Disposition: scoped PASS / issue [#328](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/328) closed as completed. Общий v5 production acceptance: NOT PASS.** Исторический FAIL на `rc.4` выше сохранён без изменений.

- Immutable baseline: `v5.0.0-rc.5` / `14042f6dc9d467dc8d0e999eb493f9e1cfc90611`. Operator post-deploy read-back: `Container=running`, `RestartCount=0`, `Bot version=5.0.0-rc.5`, `Health=ok`, `DB=ok`, `3x-ui connectivity=ok` (TCP connectivity; не подтверждение auth API/VPN data plane).
- Перед возвратом read-only SQLite: тестовый Stars payment на **1 XTR** был `confirmed`, возвратных операций **0**, нет in-flight/unknown journal.
- После отдельного явного согласия оператора один вызов двухэтапного UI refund: `✅ Возврат подтверждён Telegram.`; отдельное Telegram-уведомление о возврате **1 ⭐**. Предыдущий `NameError` не повторился.
- Финальная read-only SQLite проверка: `commerce_payments.status=refunded`, количество `stars_refund_operations` **1**, `status=success`, `Consistent=True`. Без ручного исправления БД или повторной refund mutation.
- Fix: [PR #329](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/329), отдельный release-prep [PR #330](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/330), стандартный published prerelease. Подтверждена именно happy-path refund API/UI/journal consistency; network timeout/`unknown` live test, защита от повторного запроса в production и entitlement/VPN revocation **не проверялись**. Обычный Stars refund не отзывает автоматически оплаченный период или provider access, такое действие здесь не выполнялось.
- Оставшиеся gates: V5-A-001 широкая reconciliation/support coverage, V5-A-002 failure/restart/unknown-no-replay, V5-A-003 abuse/load/soak, IDOR/ownership, kill-switch/rollback, отложенный natural expiry V5-A-005, финальный signoff. Pilot allowlist сохраняется; stable/public rollout запрещён до общего PASS.

Customer identifiers, charge reference, subscription URLs и токены не включены.
