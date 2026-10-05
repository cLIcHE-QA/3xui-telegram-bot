# Final v4 Repository / Public-Release Audit — baseline 2026-10-05

## Audit identity

- **Status:** 🟡 IN PROGRESS / NOT PASS
- **Audited freeze commit:** `fe34f9dc97f0a6441dde9fcfe865e34ad8696c32`
- **Application version:** `4.26.4`
- **Audit started:** 2026-10-05
- **Scope contract:** `docs/ROADMAP.md` → «Финальный v4 Repository / Public-Release Audit»
- **Gate decision at this revision:** final v4 release and public repository publication remain blocked.

This report is the versioned audit artifact required by the roadmap. It records evidence and findings against the frozen v4 baseline. It is intentionally **not** a statement that the audit is complete: required history-aware scanners, container/SBOM work and clean-room acceptance remain open, and all release-blocking findings below must be closed or receive the disposition allowed by the roadmap.

## Baseline evidence

### Repository / CI

- GitHub repository visibility at audit start: private.
- `main` at the audited SHA is not branch-protected according to the GitHub branch API.
- Push workflow `Python checks` for the exact audited SHA completed successfully.
- Exact audited SHA CI: **651 tests OK**.
- Pinned 3x-ui OpenAPI contract check: **v3.8.5 · 54 endpoints · blob `d1f9b499e43d4370d68fdf9ca6045e1d967b42ad`**.
- Compile, release/deploy helper checks, Compose config and `git diff --check` were part of the successful workflow.
- Current-tree pattern review did not reveal an obvious committed production credential. This does **not** replace the required full-history secret scan.

### Production / recovery evidence

Before freeze, encrypted off-site recovery acceptance was completed:

- `backup.offsite=success`;
- encrypted remote round-trip validation completed;
- isolated recovery host returned `OFFSITE_RECOVERY_OK`;
- recovered manifest version matched `4.26.4`;
- bootstrap smoke restored bot env/database and reached Health/DB `ok`;
- production Master was returned to Health/DB/3x-ui connectivity `ok`.

No secret values from that acceptance are recorded in this report.

### Positive security controls confirmed by source review

The following are positive controls, not substitutes for closing findings:

- central callback privilege catalog fails closed for unknown admin callbacks;
- immutable environment Owners remain a separate break-glass boundary;
- Host Control and Deploy Agent do not expose a generic shell/command API and use dedicated tokens;
- Docker socket is not mounted into the bot container;
- Host Control/Deploy Agent request bodies and listeners are bounded/restricted;
- Node Drain and Fleet journals use private file modes and no automatic mutation replay;
- critical Node Drain/Host Control/Deploy paths distinguish uncertain outcomes and use reconciliation/read-back;
- restore tooling validates archive paths/types/sizes and SQLite before replacement;
- off-site Full Backup uses client-side AES-256-GCM and verified remote round trip;
- website monitoring implements a custom public-only resolver, redirect revalidation, response bounds and concurrency limits;
- `.gitignore` / `.dockerignore` exclude common env/database/backup/key artifacts from normal source/build context.

## Findings

| ID | Severity | Tracking | Component | Status | Summary |
| --- | --- | --- | --- | --- | --- |
| A-001 | **High** | #234 | RBAC / Backups | Open | Administrator can request a secret-bearing Full Backup containing `bot.env`; this can cross privilege domains. |
| A-002 | **High** | #235 | Subscription Proxy / Logs | Open | Standard aiohttp access logging records `/compat/{sub_id}`, exposing bearer-like subscription credentials in raw logs. |
| A-003 | **High** | #236 | 3x-ui mutations | Open | Multiple state-changing API methods still use generic retry/failure semantics instead of no-retry uncertain-outcome handling. |
| A-004 | **Medium / security** | #237 | Telegram Admin | Open | Admin authorization checks sender role but does not fail closed outside private chats. |
| A-005 | **Medium / security** | #238 | Subscription Proxy / Redirects | Open | Raw proxy forwards device headers while automatic redirects are enabled; cross-origin header isolation requires explicit enforcement/tests. |
| A-006 | **Medium / security** | #239 | Filesystem / Backup | Open | Secret-bearing local backup artifacts do not enforce private modes independent of process umask. |
| A-007 | **High** | #240 | Repository / Release | Open | `main` is not protected; direct push can bypass the documented PR/required-CI contract and feed the release workflow. |
| A-008 | **Medium / security** | #241 | Supply chain | Open | Python deps, Docker base and third-party Actions are not pinned to a reproducible immutable dependency graph. |
| A-009 | **High** | #242 | Legal / Public release | Open | No project `LICENSE`/terms file exists; public distribution rights are undefined until owner/legal decision. |
| A-010 | **High** | #243 | Git history / Secrets | Open | Required full-history secret/private-data scan has not yet been performed; current-tree search is insufficient. |
| A-011 | **Medium / security** | #244 | Container | Open | Bot container lacks explicit non-root/no-new-privileges/capability hardening required by the audit least-privilege gate. |
| A-012 | **Medium / reliability** | #245 | Public compat proxy | Open | Proxy lacks an explicit reproducible concurrency/rate/upstream-body resource bound. |
| A-013 | **Medium / public readiness** | #246 | Security process | Open | SECURITY.md lacks a concrete private vulnerability-reporting path and supported-version policy. |

### Severity count

- Critical: **0 identified so far**
- High: **6 open**
- Medium: **7 open**
- Low/Info: tracked in notes only at this revision

Under the roadmap audit contract, this state is **release-blocking**.

## Finding evidence and required closure

### A-001 — secret-bearing backup export

Evidence: `backups.manage` permits Administrator; `admin:backup:full` uses that privilege; the handler sends the created Full Backup as a Telegram document; Full Backup includes `bot.env`.

Impact: an Administrator can obtain credentials whose authority exceeds Telegram RBAC.

Closure: make secret-bearing export Owner-only or remove Full Backup delivery through Telegram in favor of host/off-site retrieval. Add direct-callback tampering and role-matrix regression coverage. Production acceptance must prove Admin cannot obtain the archive.

### A-002 — subscription credential in raw logs

Evidence: `SubscriptionProxy.start()` enables aiohttp access logging on a route whose path contains `sub_id`. UI log rendering redacts the path, but raw stdout/file access logs are created before that redaction.

Impact: log access can become subscription credential access.

Closure: disable or sanitize raw access logs for the secret-bearing route, define safe reverse-proxy logging, add raw-log regression coverage, and perform targeted production acceptance. Any known credential exposed during testing/operations is rotated without recording it in GitHub.

### A-003 — inconsistent mutation safety

Evidence: the client contains a hardened one-shot mutation primitive, but legacy state-changing node/inbound/client/import methods still use the generic request path. The generic path does not currently contain a retry loop, but it does not preserve explicit outcome certainty and follows normal HTTP redirect behavior.

Impact: a lost response can be shown as ordinary failure even when the remote mutation was applied, enabling manual duplicate/repeated operations and state divergence.

Closure: inventory all state-changing calls, move them to no-retry mutation handling and implement read-back/post-condition reconciliation where practical. Tests must simulate lost response after remote commit.

Progress evidence:
- transport phase #250 moved the state-changing 3x-ui surface to the explicit one-shot mutation boundary;
- destructive phase #252 added fail-closed absence read-back for user/inbound/node delete without replay;
- phase 3 (#253) covers deterministic field updates: node rename, inbound enable/disable and user expiry/traffic/flow only resolve uncertain success when a read-only post-condition matches; unavailable/mismatched read-back remains `unknown` with `mutation_not_retried=true`;
- phase 4 covers the remaining handler/service classes: provisioning attach/detach/limits/flow, bulk enable/disable/extend/reset, plan/apply/extend/IP/HWID/subscription mutations, manual inbound membership, node/inbound/client create, inbound full updates/sync and maintenance. Create/update success after a lost response requires an exact or unique read-only post-condition; traffic reset remains `unknown` because a live counter cannot provide a stable proof of reset.
- A-003 remains open until phase-4 CI/merge, patch release and targeted production acceptance are completed.

### A-004 — admin chat boundary

Evidence: command/callback/FSM authorization is based on the Telegram sender role; a central private-chat requirement is absent.

Impact: authorized operators can accidentally expose control-plane data in group/supergroup context.

Closure: enforce private chat centrally for `/admin`, callbacks and admin FSM input, with regression coverage and security documentation.

### A-005 — device headers and redirects

Evidence: raw compat requests forward reviewed HWID/device headers while the HTTP helper follows redirects automatically. The documented routing contract explicitly requires no device/secret header leak to another origin.

Closure: manual redirect policy with same-origin enforcement or header stripping/rejection on cross-origin hops; regression tests must prove the cross-origin target never receives sensitive client headers.

### A-006 — private file modes

Evidence: security-sensitive journals/recovery artifacts explicitly set `0700/0600`, while normal backup creation relies on default directory/file creation modes.

Closure: explicitly enforce private directory/file modes for Full Backup/snapshots and review bot DB/local logs. Tests must set a permissive umask and still observe private modes.

### A-007 — GitHub governance

Evidence: GitHub reports `main.protected=false`; required checks therefore are not repository-enforced. The release workflow has `contents: write` after successful main CI.

Closure: GitHub-side protection/ruleset equivalent must block direct push/force-delete and require the documented PR/CI path; published release refs must remain immutable. If the current private-plan feature set cannot provide this, enforcement must be solved before public visibility/final release.

### A-008 — reproducible supply chain

Evidence: requirements are version ranges, the Python base image is a mutable tag, and Actions use mutable major refs.

The exact audited-sha CI resolver happened to install recent packages, including `aiogram 3.31.0`, `aiohttp 3.14.4`, `boto3 1.43.108`, `cryptography 46.0.7`, `Pillow 12.3.0` and `urllib3 2.8.0`; this does not make future rebuilds deterministic.

Closure: reviewed exact dependency lock/hash mechanism, base-image digest, Actions commit pins, vulnerability/license scan, SBOM/container scan and documented update process.

### A-009 — project license

Evidence: no project LICENSE/COPYING terms exist; third-party notices do not define rights for the project itself.

Closure requires an explicit owner/legal licensing decision. The audit must not invent that decision.

### A-010 — full-history scan

Evidence: connector/current-tree search is not a history scanner and cannot prove deleted blobs/old commits are clean.

Closure: trusted full clone + history-aware secret scan plus targeted private hostname/IP/identifier/artifact review. Any real leaked secret is rotated before possible history sanitization.

### A-011 — bot container least privilege

Evidence: no dedicated image `USER`, `cap_drop`, `no-new-privileges` or read-only root-filesystem policy is currently defined. Positive boundary: no Docker socket is mounted and backup/log source mounts are read-only where expected.

Closure: implement the least-privilege subset compatible with backup/recovery/runtime behavior and prove it on a clean host.

### A-012 — compat proxy resource bounds

Evidence: per request the proxy creates a client session, reads upstream response fully, and has no local global concurrency/rate/response-size contract.

Closure: explicit bounded concurrency and upstream response size plus reproducible front-door rate policy or equivalent; load/resource tests required.

### A-013 — private security reporting

Evidence: SECURITY.md defines trust boundaries and leak response but not a concrete private vulnerability reporting channel/supported versions.

Closure: configure/document a private reporting path and supported-version expectations before public publication.

## Required audit work not yet complete

The following required roadmap areas are still open even if all source findings above are fixed:

1. **Full Git-history secret/private-data scan** with scanner versions/commands and evidence — tracked by A-010.
2. **Dependency vulnerability + license scan** from the final exact lock — A-008.
3. **Container/base-image scan + SBOM** for the release image — A-008.
4. **Third-party license compatibility review** after project license decision — A-009.
5. **Full callback/command inventory** against RBAC/private-chat/ownership after A-001/A-004 changes.
6. **Mutation inventory** and lost-response tests after A-003.
7. **Clean-room acceptance** after fixes: documented fresh install, representative migration, verified restore, controlled failure/restart scenarios and final production smoke.
8. **Repeat source/network/log review** of every changed security boundary after fix PRs.
9. **Final current-tree + history scan immediately before changing repository visibility**.
10. **Final audit revision** with every High closed, every security/data-integrity Medium closed, and explicit disposition for any remaining non-security Medium.

## Current disposition

**NOT PASS.**

Final v4 release publication and repository visibility change are blocked by open audit findings. The required remediation order is:

1. secret/privilege boundaries: A-001, A-002, A-004, A-005, A-006;
2. mutation/data integrity: A-003;
3. repository/public-release gates: A-007, A-009, A-010;
4. supply-chain/container hardening: A-008, A-011;
5. resource/disclosure readiness: A-012, A-013;
6. repeat scanners + clean-room acceptance;
7. final audit revision and production release acceptance.

Each remediation is a narrowly scoped v4 fix under the active feature freeze. Findings are not considered closed by source changes alone: regression/CI and the required production/operational acceptance must be recorded.


## Remediation log

- **2026-10-05 · A-001 / #234:** implementation PR #248 открыт. Secret-bearing Full Backup/DB/node/DR artifacts переводятся на host-side/off-site only; Telegram document delivery и `BACKUP_SEND_TO_ADMINS` удаляются. Finding остаётся **Open / acceptance pending** до публикации patch release, deployment, targeted production smoke и финального health check.

- **2026-10-05 · A-002 / #235:** implementation PR #249 открыт. Built-in aiohttp access log для `/compat/{sub_id}` отключается, canonical Nginx `/compat/` route получает `access_log off`, logging contract закрепляется regression test. Finding остаётся **Open / acceptance pending** до patch release, deployment, targeted raw-log smoke и rotation известных exposed test credentials.

- **2026-10-05 · A-003 / #236:** phase-1 PR #250 merged (`d4178af779e344f757ee4bed27cc43c675c32794`): все инвентаризированные state-changing node/inbound/client/importDB calls используют единый one-shot no-redirect mutation boundary, Disaster Recovery сохраняет uncertain importDB как `unknown` без replay. Phase-2 PR #252 добавил fail-closed read-back для destructive user/inbound/node delete; phase-3 PR #253 — post-condition для deterministic field updates. Phase-4 implementation расширяет ту же semantics на provisioning, bulk, create/reset, manual membership и оставшиеся node/inbound/client handlers; нестабильные traffic-reset post-conditions намеренно не объявляются success. Finding остаётся **Open** до зелёного phase-4 PR, patch release и targeted production acceptance.
