# Финальный аудит v4 перед публикацией репозитория и релиза — базовая ревизия 2026-10-05

## Идентификация аудита

- **Статус:** 🟡 IN PROGRESS / NOT PASS
- **Проверенный freeze commit:** `fe34f9dc97f0a6441dde9fcfe865e34ad8696c32`
- **Версия приложения:** `4.26.4`
- **Аудит начат:** 2026-10-05
- **Контракт scope:** `docs/ROADMAP.md` → «Финальный v4 Repository / Public-Release Audit»
- **Решение gate на этой ревизии:** финальный релиз v4 и публикация репозитория остаются заблокированными.

Этот отчёт — версионируемый audit artifact, требуемый roadmap. Он фиксирует evidence и findings относительно замороженного baseline v4. Документ намеренно **не** утверждает, что аудит завершён: обязательные history-aware scanners, container/SBOM work и clean-room acceptance всё ещё не выполнены, а все release-blocking findings ниже должны быть закрыты либо получить допустимый по roadmap disposition.

## Evidence базовой ревизии

### Репозиторий / CI

- Видимость GitHub-репозитория на момент начала аудита: private.
- `main` на проверяемом SHA не защищён branch protection согласно GitHub branch API.
- Push workflow `Python checks` для точного проверяемого SHA завершился успешно.
- CI точного проверяемого SHA: **651 tests OK**.
- Проверка pinned 3x-ui OpenAPI contract: **v3.8.5 · 54 endpoints · blob `d1f9b499e43d4370d68fdf9ca6045e1d967b42ad`**.
- Compile, проверки release/deploy helpers, Compose config и `git diff --check` входили в успешный workflow.
- Pattern review текущего tree не выявил очевидного committed production credential. Это **не** заменяет обязательный full-history secret scan.

### Production / recovery evidence

До freeze был завершён acceptance encrypted off-site recovery:

- `backup.offsite=success`;
- завершена проверка encrypted remote round-trip;
- изолированный recovery host вернул `OFFSITE_RECOVERY_OK`;
- версия восстановленного manifest совпала с `4.26.4`;
- bootstrap smoke восстановил bot env/database и достиг Health/DB `ok`;
- production Master возвращён в состояние Health/DB/3x-ui connectivity `ok`.

Значения secrets из этого acceptance в отчёте не фиксируются.

### Положительные security controls, подтверждённые source review

Следующие пункты являются положительными controls, но не заменяют закрытие findings:

- central callback privilege catalog fail closed для неизвестных admin callbacks;
- immutable environment Owners остаются отдельной break-glass boundary;
- Host Control и Deploy Agent не предоставляют generic shell/command API и используют отдельные tokens;
- Docker socket не монтируется в bot container;
- request bodies и listeners Host Control/Deploy Agent имеют bounds/restrictions;
- журналы Node Drain и Fleet используют private file modes и не выполняют automatic mutation replay;
- критические paths Node Drain/Host Control/Deploy различают uncertain outcomes и используют reconciliation/read-back;
- restore tooling валидирует archive paths/types/sizes и SQLite перед заменой;
- off-site Full Backup использует client-side AES-256-GCM и проверенный remote round trip;
- website monitoring реализует custom public-only resolver, повторную валидацию redirects, response bounds и concurrency limits;
- `.gitignore` / `.dockerignore` исключают распространённые env/database/backup/key artifacts из обычного source/build context.

## Findings

| ID | Severity | Tracking | Component | Status | Summary |
| --- | --- | --- | --- | --- | --- |
| A-001 | **High** | #234 | RBAC / Backups | Closed | `v4.26.5` удалил Telegram transport secret-bearing backup; production Full Backup/off-site smoke и финальный health/status прошли. |
| A-002 | **High** | #235 | Subscription Proxy / Logs | Closed | `v4.26.5` отключил raw compat access logging; targeted container/bot/nginx log smoke прошёл, использованный test credential ротирован. |
| A-003 | **High** | #236 | 3x-ui mutations | Closed | `v4.26.5` унифицировал mutation certainty/read-back; production disable/enable smoke прошёл с восстановлением исходного состояния. |
| A-004 | **Medium / security** | #237 | Telegram Admin | Acceptance pending | PR #260 merged: все admin routers fail closed вне private chat; regression/CI зелёные, `v4.26.6` production smoke ещё требуется. |
| A-005 | **Medium / security** | #238 | Subscription Proxy / Redirects | Acceptance pending | PR #260 merged: redirects manual/bounded, cross-origin strips device/auth-like headers, TLS downgrade blocked; `v4.26.6` production acceptance ещё требуется. |
| A-006 | **Medium / security** | #239 | Filesystem / Backup | Acceptance pending | PR #260 merged: sensitive dirs/files enforce `0700/0600`, existing artifacts tighten, permissive-umask regression зелёный; `v4.26.6` production acceptance ещё требуется. |
| A-007 | **High** | #240 | Repository / Release | Open | `main` не защищён; direct push может обойти документированный PR/required-CI contract и попасть в release workflow. |
| A-008 | **Medium / security** | #241 | Supply chain | Open | Python deps, Docker base и third-party Actions не закреплены в воспроизводимый immutable dependency graph. |
| A-009 | **High** | #242 | Legal / Public release | Open | Project `LICENSE`/terms file отсутствует; права публичного распространения не определены до решения owner/legal. |
| A-010 | **High** | #243 | Git history / Secrets | Closed | Full Git-history + retained GitHub Actions storage audit завершены; unresolved real secrets = 0. Closure evidence: `docs/audits/v4-a010-git-history-secret-audit-2026-10-06.md`. |
| A-011 | **Medium / security** | #244 | Container | Acceptance pending | Runtime hardening merged: dedicated UID/GID `10001:10001`, root-owned app tree, read-only rootfs, `no-new-privileges`, `cap_drop: ALL`, bounded `/tmp`, writable `/app/data` only, inherited host ACL rollout. CI clean-container smoke PASS; production runtime smoke ещё не зафиксирован. |
| A-012 | **Medium / reliability** | #245 | Public compat proxy | Acceptance pending | Resource bounds merged: global upstream concurrency 32, slot wait 1s→503, upstream body ≤8 MiB chunked; canonical nginx per-client `limit_conn=4`, `5r/s`, burst 10. Regression CI PASS; production/load smoke ещё не зафиксирован. |
| A-013 | **Medium / public readiness** | #246 | Security process | Open | SECURITY.md не содержит конкретного private vulnerability-reporting path и supported-version policy. |

### Количество findings по severity

- Critical: **0 выявлено на текущем этапе**
- High: **3 open**
- Medium: **7 open**
- Low/Info: на этой ревизии фиксируются только в notes

По audit contract из roadmap это состояние является **release-blocking**.

## Evidence findings и условия закрытия

### A-001 — экспорт secret-bearing backup

Evidence: `backups.manage` разрешён Administrator; `admin:backup:full` использует эту privilege; handler отправляет созданный Full Backup как Telegram document; Full Backup включает `bot.env`.

Impact: Administrator может получить credentials, authority которых превышает Telegram RBAC.

Closure: сделать secret-bearing export Owner-only либо убрать доставку Full Backup через Telegram в пользу host/off-site retrieval. Добавить regression coverage для direct-callback tampering и role matrix. Production acceptance должен доказать, что Admin не может получить archive.

### A-002 — subscription credential в raw logs

Evidence: `SubscriptionProxy.start()` включает aiohttp access logging на route, path которого содержит `sub_id`. UI rendering logs редактирует path, но raw stdout/file access logs создаются до этой redaction.

Impact: доступ к logs может превратиться в доступ к subscription credential.

Closure: отключить либо sanitize raw access logs для secret-bearing route, определить безопасный reverse-proxy logging, добавить raw-log regression coverage и выполнить targeted production acceptance. Любой известный credential, раскрытый во время testing/operations, должен быть rotated без фиксации его значения в GitHub.

### A-003 — несогласованная mutation safety

Evidence: client содержит hardened one-shot mutation primitive, но legacy state-changing node/inbound/client/import methods всё ещё используют generic request path. Generic path сейчас не содержит retry loop, но не сохраняет явную outcome certainty и следует обычному HTTP redirect behavior.

Impact: потерянный response может быть показан как обычный failure, даже если remote mutation была применена, что допускает manual duplicate/repeated operations и state divergence.

Closure: инвентаризировать все state-changing calls, перевести их на no-retry mutation handling и реализовать read-back/post-condition reconciliation там, где это практически возможно. Tests должны моделировать lost response после remote commit.

Progress evidence:
- transport phase #250 перевела state-changing 3x-ui surface на explicit one-shot mutation boundary;
- destructive phase #252 добавила fail-closed absence read-back для user/inbound/node delete без replay;
- phase 3 (#253) покрывает deterministic field updates: node rename, inbound enable/disable и user expiry/traffic/flow разрешают uncertain success только когда read-only post-condition совпадает; недоступный/несовпадающий read-back остаётся `unknown` с `mutation_not_retried=true`;
- phase 4 покрывает оставшиеся handler/service classes: provisioning attach/detach/limits/flow, bulk enable/disable/extend/reset, plan/apply/extend/IP/HWID/subscription mutations, manual inbound membership, node/inbound/client create, inbound full updates/sync и maintenance. Create/update success после lost response требует exact либо unique read-only post-condition; traffic reset остаётся `unknown`, потому что live counter не даёт стабильного доказательства reset.
- A-003 закрыт после merge phase-4, публикации/deploy `v4.26.5` и targeted production disable/enable acceptance с подтверждённым read-back и восстановленным исходным состоянием.

### A-004 — admin chat boundary

Evidence: authorization command/callback/FSM основана на роли Telegram sender; central private-chat requirement отсутствует.

Impact: авторизованные операторы могут случайно раскрыть control-plane data в group/supergroup context.

Closure: централизованно enforce private chat для `/admin`, callbacks и admin FSM input, с regression coverage и security documentation.

### A-005 — device headers и redirects

Evidence: raw compat requests пересылают reviewed HWID/device headers, в то время как HTTP helper автоматически следует redirects. Документированный routing contract явно требует не допускать утечку device/secret headers на другой origin.

Closure: manual redirect policy с same-origin enforcement либо stripping/rejection headers на cross-origin hops; regression tests должны доказать, что cross-origin target никогда не получает sensitive client headers.

### A-006 — private file modes

Evidence: security-sensitive journals/recovery artifacts явно задают `0700/0600`, тогда как обычное создание backup полагается на default directory/file creation modes.

Closure: явно enforce private directory/file modes для Full Backup/snapshots и проверить bot DB/local logs. Tests должны установить permissive umask и всё равно наблюдать private modes.

### A-007 — GitHub governance

Evidence: GitHub сообщает `main.protected=false`; следовательно, required checks не enforced на уровне repository. Release workflow имеет `contents: write` после успешного main CI.

Closure: GitHub-side branch protection/ruleset equivalent должен блокировать direct push/force-delete и требовать документированный PR/CI path; опубликованные release refs должны оставаться immutable. Если текущий feature set private plan этого не поддерживает, enforcement должен быть решён до public visibility/final release.

### A-008 — воспроизводимый supply chain

Evidence: requirements заданы version ranges, Python base image — mutable tag, Actions используют mutable major refs.

CI на точном audited SHA на момент проверки установил, среди прочего, `aiogram 3.31.0`, `aiohttp 3.14.4`, `boto3 1.43.108`, `cryptography 46.0.7`, `Pillow 12.3.0` и `urllib3 2.8.0`; это не делает будущие rebuilds deterministic.

Closure: reviewed exact dependency lock/hash mechanism, base-image digest, Actions commit pins, vulnerability/license scan, SBOM/container scan и документированный update process.

### A-009 — project license

Evidence: project LICENSE/COPYING terms отсутствуют; third-party notices не определяют права на сам проект.

Closure требует явного licensing decision со стороны owner/legal. Audit не должен придумывать это решение.

### A-010 — full-history scan

Closure evidence: `docs/audits/v4-a010-git-history-secret-audit-2026-10-06.md`.

History-aware scan выполнен на exact SHA `c8a15362d82bfae812dc93758568602a1475febd`: Gitleaks v8.30.1 + repository metadata scanner проверили 343 reachable refs. Все 6 Gitleaks candidates и 135 metadata candidates получили безопасный disposition; unresolved real secrets = 0.

Отдельный retained GitHub Actions storage audit выполнен на exact SHA `f5b30900e8c53e47bb27b3e30d145b9feff81d20`: 1485 retained log archives и 1 retained artifact проверены, coverage issues = 0, high-confidence credential findings = 0. Current и historical workflow history не содержат repository `secrets.*` / `vars.*` references. A-010 закрыт.

### A-011 — least privilege для bot container

Implementation evidence:

- PR #268 merged as `a9ab0c02b019bbaa086d72bd02749543bca9e796`;
- follow-up rollout fix PR #269 merged as `d3f0611060292e0609a10128e1351bcfdbabe18f`;
- runtime UID/GID: `10001:10001`;
- root filesystem: read-only;
- effective Linux capabilities: dropped via `cap_drop: ALL`;
- `no-new-privileges`: enabled;
- persistent writable tree: `/app/data`;
- temporary writable tree: bounded tmpfs `/tmp`;
- backup/config/log host mounts remain read-only inside container;
- host permission helper adds current + inherited default ACL so new SQLite WAL/SHM and rotated nginx logs remain readable by the non-root runtime;
- root-owned release deployment runs the permission helper before container recreate.

CI evidence: PR #268 `Python checks` run `37474609300` PASS; PR #269 `Python checks` run `37483324260` PASS. Clean-container smoke checks UID/GID, zero `CapEff`, `NoNewPrivs=1`, read-only `/app`, writable `/app/data` and `/tmp`, plus read access to canonical backup/log mounts.

Closure remaining: targeted production/runtime acceptance on the actual Master host — health, SQLite, backup/recovery preflight, representative client/admin flows and no restart loop. Evidence template: `docs/audits/v4-a011-a012-production-acceptance-2026-10-06.md`.

### A-012 — resource bounds compat proxy

Implementation evidence:

- PR #270 merged as `8485346f0fbe99732a7e4b3d69f9ca28f96ac1af`;
- global upstream concurrency: **32**;
- wait for an upstream slot: **1 second**, then fail-closed HTTP 503 + `Retry-After: 1`;
- maximum upstream response body: **8 MiB**;
- response body is read in bounded chunks rather than unbounded `resp.read()`;
- canonical public nginx policy: per-client `limit_conn 4`, `limit_req 5r/s`, burst 10, `proxy_read_timeout 25s`;
- bearer-like `sub_id` URI remains excluded from access logging.

CI evidence: PR #270 `Python checks` run `37488293491` PASS. Regression coverage includes oversized `Content-Length`, oversized body, saturated application semaphore and canonical nginx rate/connection contract.

Closure remaining: targeted production/load acceptance on the deployed release — normal subscription refresh, burst/parallel requests, bounded 503 behavior under saturation, no process memory/restart anomaly and final health/status. Evidence template: `docs/audits/v4-a011-a012-production-acceptance-2026-10-06.md`.

### A-013 — private security reporting

Evidence: SECURITY.md определяет trust boundaries и leak response, но не конкретный private vulnerability reporting channel/supported versions.

Closure: настроить/документировать private reporting path и supported-version expectations до public publication.

## Обязательные audit work, которые ещё не завершены

Следующие обязательные области roadmap остаются открытыми, даже если все source findings выше исправлены:

1. **Dependency vulnerability + license scan** по финальному exact lock — A-008.
2. **Container/base-image scan + SBOM** release image — A-008.
3. **Third-party license compatibility review** после решения по project license — A-009.
4. **Full callback/command inventory** относительно RBAC/private-chat/ownership после изменений A-001/A-004.
5. **Mutation inventory** и lost-response tests после A-003.
6. **Clean-room acceptance** после исправлений: документированный fresh install, representative migration, verified restore, controlled failure/restart scenarios и финальный production smoke.
7. **Повторный source/network/log review** каждой изменённой security boundary после fix PRs.
8. **Финальный current-tree + history scan непосредственно перед изменением repository visibility**.
9. **Финальная ревизия аудита**: каждый High закрыт, каждый security/data-integrity Medium закрыт, для любого оставшегося non-security Medium указан explicit disposition.

## Текущий disposition

**NOT PASS.**

Публикация финального v4 release и изменение видимости репозитория заблокированы открытыми audit findings. Требуемый порядок remediation:

1. secret/privilege boundaries: A-001, A-002, A-004, A-005, A-006;
2. mutation/data integrity: A-003;
3. repository/public-release gates: A-007, A-009, A-010;
4. supply-chain/container hardening: A-008, A-011;
5. resource/disclosure readiness: A-012, A-013;
6. повторные scanners + clean-room acceptance;
7. финальная audit revision и production release acceptance.

Каждая remediation — narrowly scoped v4 fix в рамках активного feature freeze. Findings не считаются закрытыми только за счёт source changes: должны быть зафиксированы regression/CI и требуемый production/operational acceptance.

## Журнал remediation

- **2026-10-05 · A-001 / #234:** implementation PR #248 открыт. Secret-bearing Full Backup/DB/node/DR artifacts переводятся на host-side/off-site only; Telegram document delivery и `BACKUP_SEND_TO_ADMINS` удаляются. Finding остаётся **Open / acceptance pending** до публикации patch release, deployment, targeted production smoke и финального health check.

- **2026-10-05 · A-002 / #235:** implementation PR #249 открыт. Built-in aiohttp access log для `/compat/{sub_id}` отключается, canonical Nginx `/compat/` route получает `access_log off`, logging contract закрепляется regression test. Finding остаётся **Open / acceptance pending** до patch release, deployment, targeted raw-log smoke и rotation известных exposed test credentials.

- **2026-10-05 · A-003 / #236:** phase-1 PR #250 merged (`d4178af779e344f757ee4bed27cc43c675c32794`): все инвентаризированные state-changing node/inbound/client/importDB calls используют единый one-shot no-redirect mutation boundary, Disaster Recovery сохраняет uncertain importDB как `unknown` без replay. Phase-2 PR #252 добавил fail-closed read-back для destructive user/inbound/node delete; phase-3 PR #253 — post-condition для deterministic field updates. Phase-4 implementation расширяет ту же semantics на provisioning, bulk, create/reset, manual membership и оставшиеся node/inbound/client handlers; нестабильные traffic-reset post-conditions намеренно не объявляются success. Finding остаётся **Open** до зелёного phase-4 PR, patch release и targeted production acceptance.


- **2026-10-06 · A-001/A-002/A-003 / #234/#235/#236:** `v4.26.5` опубликован и развёрнут; targeted production acceptance завершён. A-001: Full Backup создан локально, off-site upload/verification успешен, Telegram получил только status; A-002: fresh compat request не раскрыл credential в container/new bot/nginx logs, test credential после проверки ротирован; A-003: disable/enable mutation smoke прошёл с read-back и восстановлением исходного состояния. Findings закрыты как completed.

- **2026-10-06 · A-004/A-005/A-006 / #237/#238/#239:** implementation PR #260 merged (`a15ff4beaeae2ec249b729e53b2aeaadf6c349ef`) с зелёными `PR conventions` и `Python checks`. Private-chat admin boundary, cross-origin redirect header stripping/TLS downgrade rejection и owner-only sensitive file modes закреплены regression coverage и SECURITY/UI contracts. Findings остаются **Open / acceptance pending** до публикации/deploy `v4.26.6`, targeted production smoke и повторного health/status-check.


- **2026-10-06 · A-010 / #243:** full Git-history scan и retained GitHub Actions storage audit завершены. Gitleaks v8.30.1 + metadata scanner проверили 343 reachable refs; отдельный Actions audit проверил 1485 retained log archives и 1 retained artifact без coverage gaps. Все candidates получили safe disposition, high-confidence credential findings отсутствуют, unresolved real secrets = 0. Closure evidence: `docs/audits/v4-a010-git-history-secret-audit-2026-10-06.md`.

- **2026-10-06 · A-011 / #244:** implementation merged в PR #268 (`a9ab0c02…`) и rollout fix PR #269 (`d3f06110…`). Dedicated UID/GID `10001:10001`, read-only rootfs, `no-new-privileges`, `cap_drop: ALL`, bounded `/tmp`, writable `/app/data` only, read-only source mounts и inherited host ACL закреплены CI clean-container smoke. **Статус: acceptance pending** — остался production runtime smoke.

- **2026-10-06 · A-012 / #245:** implementation merged в PR #270 (`8485346f…`): hard bounds 32 concurrent upstream fetch, 1s slot wait→503, ≤8 MiB response с chunked read; canonical `/compat/` nginx policy — per-client `limit_conn=4`, `5r/s`, burst 10, без access log bearer-like URI. Regression CI PASS. **Статус: acceptance pending** — остался production/load smoke.
