# G-05 — controlled production bot-only restart, scoped PASS (2026-10-12)

## Provenance, baseline, scope

- **Дата выполнения из stdout:** `UTC=2026-10-12T16:38:41Z` = **2026-10-12 19:38:41 Europe/Helsinki (EEST, UTC+03:00)**. Оператор предоставил полный sanitised вывод **2026-10-12 16:39:26 UTC / 19:39:26 EEST**. Внешнего независимого SSH/VPS-доступа у агента нет. Часы stdout — момент запуска preflight, не точный момент остановки или старта процесса.
- **Production target:** единственный Compose service `bot` на Master VPS, pilot allowlist не менялся; `x-ui.service` и direct nodes **не рестартовали**. Оператор ранее явно разрешил controlled restart. Нет deploy, rebuild, правки `.env`, SQLite, провайдера, Stars payment/refund, traffic quota, replacement image или direct-node mutations.
- **Published:** immutable prerelease `v5.0.0-rc.9`, tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`. **Deployed operator-reported:** перед restart `git rev-parse HEAD` совпал с тегом по guard; после restart `APP_VERSION=5.0.0-rc.9`, `./scripts/deploy-release.sh --status` вывел `Git tag=v5.0.0-rc.9`, `Git SHA=13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`, running, Bot version, health/DB/upstream OK; скрипт явно проверил unchanged Docker image ID, но не напечатал ID. Agent-side build attestation отсутствует. **Accepted:** overall v5 `NOT PASS`; G-05 `PARTIAL`.
- **Prerequisite read-only Full Backup:** [G-05 verified preflight](v5-g05-restart-preflight-verified-2026-10-12.md) (оператор 19:29:59 EEST) — existing local Full Backup `rc.9`, возраст 14.5h, manifest schema 2 + SHA-256 sizes, обе SQLite DB quick_check, `bot.env`, errors=0, health and 4 active-work counters zero, **3/3 scoped PASS**. Старый blocked guard [отдельный audit](v5-g05-restart-preflight-blocked-2026-10-12.md) остаётся в истории; не стирать. Никакого cross-host DR/off-site round-trip/restore при restart не выполняли.
- **GitHub baseline перед docs PR:** `main` `8e9d0c9f90a3f99b8e78ddaebe5a9adee8103850` после [PR #559](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/559), postmerge [Python checks 38278603518](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38278603518) **SUCCESS**.

## Фактический sanitized stdout

```text
=== G05-R4: IMMEDIATE PREFLIGHT ===
UTC=2026-10-12T16:38:41Z
PROVISIONING 0
QUOTA_INFLIGHT 0
REFUND_INFLIGHT 0
RUNNING_JOBS 0
IMMEDIATE_PREFLIGHT=PASS
=== G05-R5: RESTART BOT ONCE ===
[+] restart 0/1
 ⠇ Container 3xui-telegram-bot-bot-1 Restarting 3.8s
=== G05-R6: HEALTH READ-BACK ===
CONTAINER=running RESTARTS=0
APP_VERSION=5.0.0-rc.9
Git tag: v5.0.0-rc.9
Git SHA: 13fdbe8bccfbe92cffc4117b79083bbdcad5a8db
Container: running
RestartCount=0
Bot version: 5.0.0-rc.9
Health: ok
DB: ok
Docker subnet: [redacted private CIDR]
3x-ui connectivity: ok
G05_BOT_RESTART=COMPLETED
G05_IMAGE_UNCHANGED=PASS
G05_HEALTH_RECOVERED=PASS
```

## Что проверено, что не подтверждено

| ID | Expected | Actual | Scoped disposition |
| --- | --- | --- | --- |
| G05-R4 | Pre-restart released SHA, health, 0 active provisioning/quota/refund/jobs | `IMMEDIATE_PREFLIGHT=PASS`; all four counts = 0; no changes | **PASS** at sample time. Race between check and restart cannot be ruled out categorically |
| G05-R5 | Exactly one controlled `docker compose ... restart bot` | Restart command emitted Docker Compose `Restarting`; script advanced to health and completed | **PASS** for command execution; service is back, no evidence of restart loop. `RestartCount=0` after manual restart is not independent proof process was never restarted. Did not record `StartedAt` |
| G05-R6 | Health, version, image, DB, upstream restored | Running; image equal by guard; version/tag/SHA matches immutable release; `Health=ok`, `DB=ok`, 3x-ui connectivity OK; final `G05_BOT_RESTART=COMPLETED` and PASS markers | **PASS**, targeted post-restart liveness/baseline; no independent traffic/Telegram-message proof |

**Result: 3/3 targeted restart subchecks operator-reported PASS**, **G-05 remains PARTIAL**. A clean restart *with no active work at preflight* is not a test of restart **during** paid provisioning/transaction reconciliation; it is not evidence that an unknown provider outcome cannot trigger blind quota reset, a second purchase charge, duplicate entitlement or refund after restart. No real financial replay or intentional natural `job_failed` occurred. Earlier G05-1/3/4 passive PASS, G05-2 `legacy=1` **REVIEW** remain unchanged.

**Next evidence (new independent read-only checkpoint required):** bounded immediate post-restart snapshot compared against previous 18:54 baseline (no new stale/unknown/failed, lost entitled access/paid-sum drift); latest few pilot paid/refunded counts and no duplicate entitlement/payment/refund operation; inspect selected 3x-ui client provider current-state/traffic if available; 2-device pilot app UI/Telegram access only if new risk hypothesis, no repeat of settled smoke. Exact before/after counts for paid ledger were **not captured in this restart stdout**, so diff baseline is partial/incomplete; do not claim no replay until verified. For fault/duplicate/delayed payment and provider timeouts, prefer isolated fake provider + disposable SQLite; no unapproved real payment/refund, no blind retries at `unknown`.

**Issue audit:** [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466) **OPEN** natural job_failed PENDING, no forced natural event; [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) **OPEN** Master↔Node identity/sync/recovery not tested, Master bot restart ≠ node sync; [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) **OPEN** future refund-access policy. #342/#422 **CLOSED** per earlier scoped acceptance, do not reopen. G-01…G-04 and G-06…G-08 **PARTIAL**; G-09…G-11 **PENDING**. W-01 DR operator-waived/not tested, W-02 Telegram burst waived/inconclusive, **do not repeat**. Public launch BLOCKED.

**Workflow:** update current top `docs/ROADMAP.md` **and** G-05 line in canonical 11-gate table, docs-only PR, required `test`/`title`, squash merge, independent `main` audit/table read-back and Issue closure audit before next set of live tests. **Issue: N/A** — acceptance evidence-only checkpoint under existing G-05/V5-A-002, no independent implementation/bug finding.
