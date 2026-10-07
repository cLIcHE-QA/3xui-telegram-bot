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
