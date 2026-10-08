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

