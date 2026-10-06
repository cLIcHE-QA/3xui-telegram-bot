# Финальный аудит v4 перед публикацией репозитория и релиза — базовая ревизия 2026-10-05

## Идентификация аудита

- **Статус:** ✅ PASS
- **Проверенный freeze commit:** `fe34f9dc97f0a6441dde9fcfe865e34ad8696c32`
- **Версия приложения:** `4.26.8`
- **Аудит начат:** 2026-10-05
- **Контракт scope:** `docs/ROADMAP.md` → «Финальный v4 Repository / Public-Release Audit»
- **Решение gate на этой ревизии:** PASS — финальный v4 public-release audit завершён; repository опубликован, A-001–A-013 закрыты, включая post-public техническое закрытие A-007.

Этот отчёт — версионируемый audit artifact, требуемый roadmap. Он фиксирует baseline findings, remediation, production acceptance, clean-room acceptance и public-publication evidence. Финальный gate завершён PASS: unresolved Critical/High/security/data-integrity Medium blockers отсутствуют; исторический owner-accepted A-007 после public transition полностью технически remediated branch/tag rulesets.

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
| A-004 | **Medium / security** | #237 | Telegram Admin | Closed | `v4.26.6` опубликован и развёрнут; production smoke подтвердил fail-closed `/admin` вне private chat, штатную работу в private chat и финальный Health/DB/3x-ui status PASS. |
| A-005 | **Medium / security** | #238 | Subscription Proxy / Redirects | Closed | `v4.26.6` production acceptance подтвердил: same-origin сохраняет разрешённый device header, cross-origin удаляет `X-HWID`/`Authorization`, HTTPS→HTTP downgrade блокируется; финальный status PASS. |
| A-006 | **Medium / security** | #239 | Filesystem / Backup | Closed | `v4.26.6` production acceptance подтвердил owner-only modes `0700/0600` для bot DB, logs, Full Backup и node backup artifacts; повторный Health/DB/3x-ui status PASS. |
| A-007 | **High** | #240 | Repository / Release | Closed / remediated | `main` защищён active PR/CI/squash ruleset, а `refs/tags/v*` — active tag ruleset с update/delete/non-fast-forward restrictions; bypass отсутствует. Evidence: `docs/audits/v4-a007-github-governance-risk-acceptance-2026-10-06.md`. |
| A-008 | **Medium / security** | #241 | Supply chain | Closed | Reproducible baseline merged и подтверждён exact-main Supply-chain audit: hashed `requirements.lock`, digest-pinned base, full-SHA Actions, vulnerability/license reports, CycloneDX SBOM; actionable HIGH/CRITICAL = 0. Closure evidence: `docs/audits/v4-a008-supply-chain-audit-2026-10-06.md`. |
| A-009 | **High** | #242 | Legal / Public release | Closed | Owner выбрал Apache-2.0; canonical `LICENSE`, README license section и compatibility review merged. Third-party obligations документированы; #242 закрыт. |
| A-010 | **High** | #243 | Git history / Secrets | Closed | Full Git-history + retained GitHub Actions storage audit завершены; unresolved real secrets = 0. Closure evidence: `docs/audits/v4-a010-git-history-secret-audit-2026-10-06.md`. |
| A-011 | **Medium / security** | #244 | Container | Closed | `v4.26.8` production retest PASS: non-root runtime, read-only rootfs, zero capabilities, inherited ACL, backup/DR/client smoke и финальный status с `RestartCount=0`. |
| A-012 | **Medium / reliability** | #245 | Public compat proxy | Closed | `v4.26.8` production/load acceptance PASS: nginx `limit_conn=4`, `5r/s` burst 10, bounded 503 under burst/saturation, 8 MiB rejection, health during load и `RestartCount=0`. |
| A-013 | **Medium / public readiness** | #246 | Security process | Closed | Repository опубликован; GitHub Private Vulnerability Reporting включён, custom report form активен, внешний incognito smoke подтвердил `Report a vulnerability`; #246 закрыт completed. |

### Количество findings по severity

- Critical: **0 выявлено на текущем этапе**
- High: **0 open**
- Medium: **0 open**
- Low/Info: на этой ревизии фиксируются только в notes

По audit contract из roadmap release-blocking findings отсутствуют; A-007 post-public hardening полностью remediated.

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

Closure evidence: PR #260 merged; release `v4.26.6` / commit `e04834e9c2d6200fa84896e7c135f476f56bc78e` опубликован и развёрнут. Production smoke подтвердил, что `/admin` в group/supergroup не открывает admin UI и не раскрывает control-plane data, а private chat работает штатно. Финальный status-check: container running, `RestartCount=0`, Bot version `4.26.6`, Health/DB/3x-ui connectivity — `ok`. A-004/#237: **Closed**.

### A-005 — device headers и redirects

Evidence: raw compat requests пересылают reviewed HWID/device headers, в то время как HTTP helper автоматически следует redirects. Документированный routing contract явно требует не допускать утечку device/secret headers на другой origin.

Closure: manual redirect policy с same-origin enforcement либо stripping/rejection headers на cross-origin hops; regression tests должны доказать, что cross-origin target никогда не получает sensitive client headers.

Closure evidence: PR #260 merged; `v4.26.6` production smoke в running container подтвердил synthetic redirect policy без реальных credentials: same-origin сохраняет `X-HWID`, cross-origin удаляет `X-HWID` и `Authorization`, безопасный `User-Agent` сохраняется, HTTPS→HTTP downgrade отклоняется. Финальный Health/DB/3x-ui status-check — PASS. A-005/#238: **Closed**.

### A-006 — private file modes

Evidence: security-sensitive journals/recovery artifacts явно задают `0700/0600`, тогда как обычное создание backup полагается на default directory/file creation modes.

Closure: явно enforce private directory/file modes для Full Backup/snapshots и проверить bot DB/local logs. Tests должны установить permissive umask и всё равно наблюдать private modes.

Closure evidence: PR #260 merged; `v4.26.6` production smoke подтвердил `data/bot.sqlite3=0600`, `data/logs=0700`, `data/logs/bot.log=0600`, `data/backups=0700`, Full Backup archive=`0600`, node backup directories=`0700` и node snapshot archive=`0600`. Финальный Health/DB/3x-ui status-check — PASS. A-006/#239: **Closed**.

### A-007 — GitHub governance

Evidence: GitHub сообщает `main.protected=false`; следовательно, required checks не enforced на уровне repository. Release workflow имеет `contents: write` после успешного main CI.

Исходный closure criterion: GitHub-side branch protection/ruleset equivalent должен блокировать direct push/force-delete и требовать документированный PR/CI path; опубликованные release refs должны оставаться immutable.

Disposition at audit closure: **Accepted risk by owner decision**.

Post-public revalidation: `main` теперь GitHub-side protected active ruleset `Protect main release path` (ID `24575428`). Ruleset требует PR, разрешает только squash merge, требует strict checks `test` и `title`, запрещает deletion/non-fast-forward, требует linear history и не имеет bypass actors.

После public transition исходный branch-side риск был remediated ruleset `Protect main release path`; затем включён tag ruleset `Protect release tags` (ID `24615100`) для `refs/tags/v*`, запрещающий update/delete/non-fast-forward без bypass. Existing release workflow/provenance controls остаются defense-in-depth.

Closure/revalidation evidence: `docs/audits/v4-a007-github-governance-risk-acceptance-2026-10-06.md`.

### A-008 — supply chain

Closure evidence: `docs/audits/v4-a008-supply-chain-audit-2026-10-06.md`.

- exact-main audit SHA: `80a989d0342ffcbb097caf3184d7d5d118ed68b4`;
- Supply-chain audit run `37507349749`: PASS;
- artifact ID `11432761040`;
- artifact digest `sha256:32bffc6ef9bd08d035a044ea7bcd6151276c407a5f455a0e0f4d1289805a2d86`;
- Python actionable HIGH/CRITICAL after remediation: 0;
- container actionable HIGH/CRITICAL with available fix: 0;
- full vendor-unfixed Debian findings remain preserved in JSON evidence;
- dependency/license inventory and CycloneDX SBOM are retained as audit artifacts;
- subsequent Apache-2.0 PR changed only license/docs/tests and did not alter audited supply-chain inputs.

A-008/#241: **Closed**.

### A-009 — project license

Owner decision: **Apache License 2.0**.

Implementation evidence:

- canonical project terms: `LICENSE`;
- README содержит отдельный license section;
- `THIRD_PARTY_NOTICES.md` отделяет project-authored Apache-2.0 code от third-party BSD/MIT material;
- compatibility review: `docs/audits/v4-a009-license-review-2026-10-06.md`;
- Python runtime license inventory review покрывает permissive/notice licenses, PSF-2.0, MPL-2.0 `certifi` и scanner UNKNOWN classifications;
- текущий release process не публикует prebuilt container image; если это изменится, нужен отдельный review GPL/LGPL obligations Debian base packages.

Closure evidence: Apache-2.0 change merged в PR #275; #242 закрыт. Compatibility review: `docs/audits/v4-a009-license-review-2026-10-06.md`. A-009: **Closed**. Это engineering compliance review, не юридическая консультация.

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

Closure evidence: `v4.26.8` production retest PASS — runtime UID/GID `10001:10001`, zero effective capabilities, read-only rootfs, bounded `/tmp`, writable `/app/data` only, inherited ACL read access, Full Backup/off-site verification, DR preflight, representative client/admin flows and final `RestartCount=0` with Health/DB/3x-ui `ok`. Evidence: `docs/audits/v4-a011-a012-production-acceptance-2026-10-06.md`. A-011/#244: **Closed**.

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

Closure evidence: `v4.26.8` production/load acceptance PASS — canonical nginx limits loaded after successful `nginx -t`, normal real refresh PASS, 40-request front-door burst produced `13×404 / 27×503`, isolated 32-slot saturation returned `503 + Retry-After: 1`, >8 MiB loopback response was rejected with 64 KiB chunked reads, health stayed responsive during an 80-request burst (`26×404 / 54×503`), and final status remained `RestartCount=0`, Health/DB/3x-ui `ok`. Evidence: `docs/audits/v4-a011-a012-production-acceptance-2026-10-06.md`. A-012/#245: **Closed**.

### A-013 — private security reporting

Implementation evidence:

- `SECURITY.md` определяет supported versions, canonical private reporting path, reporter guidance и maintainer response expectations;
- public bug/feature/task forms явно запрещают security-sensitive disclosure и направляют в Security → Advisories → Report a vulnerability;
- `.github/VULNERABILITY_REPORT.yml` задаёт custom private report form с минимизацией secret-bearing material;
- regression test закрепляет policy/form/issue-template contract.

Closure evidence:

- repository переведён в public только после финальных secret/private-data scans на frozen SHA `c6066c1ab77e019970a70ebfa7242a66a41ba8a3`;
- GitHub Private Vulnerability Reporting включён владельцем;
- external incognito/unauthenticated smoke подтвердил доступность **Security → Advisories → Report a vulnerability**;
- custom `.github/VULNERABILITY_REPORT.yml` остаётся активной structured form;
- smoke не создавал реальный vulnerability report;
- #246 закрыт как completed.

A-013: **Closed**.

## Final cross-cutting / publication evidence

Все обязательные roadmap gates завершены:

1. full callback/command RBAC/private-chat inventory — PASS;
2. mutation inventory / lost-response semantics — PASS;
3. changed security/network/log boundary review — PASS;
4. clean-room fresh install / migration / restore / restart recovery — PASS;
5. финальный current-tree + full-history scan непосредственно перед visibility change — PASS;
6. retained GitHub Actions storage audit — PASS с coverage issues = 0;
7. post-nginx fresh Full Backup, off-site verification и DR preflight — PASS;
8. repository visibility → public после сканов — PASS;
9. A-013 Private Vulnerability Reporting enablement и внешний `Report a vulnerability` smoke — PASS.

Final pre-public scan evidence на frozen SHA `c6066c1ab77e019970a70ebfa7242a66a41ba8a3`:

- `Python checks` run `37537988957` — PASS;
- History secret audit run `37538268098` — PASS, artifact `11448040442`, digest `sha256:a31fda7f10f2e7d6cd98557ff250839f9cdbdd87c1c78d06193211fb06d46ab0`, 6 unchanged Gitleaks candidates, 147 metadata records / 364 refs, no new unique metadata fingerprints, unresolved real secrets = 0;
- Actions storage secret audit run `37538533256` — PASS, artifact `11447327296`, digest `sha256:d3cd21c28d828e92d518fb90d51e62d1e41ef56b6816d6f314ae4ae46eabdcf7`, 1603 retained logs and 15/15 retained artifacts scanned, coverage issues = 0, 14 unchanged finding groups, current/historical `secrets.*` / `vars.*` refs = 0.

Recovery evidence immediately before publication:

- `3xui-bot-backup-20261006-221647.tar.gz`, 103.3 KB;
- off-site upload/verification — PASS;
- DR preflight — valid archive, manifest `4.26.8`, bot DB, Master x-ui DB, bot env, nginx bundle and Finland node DB present.

## Текущий disposition

**PASS.**

Финальный v4 Repository / Public-Release Audit завершён. Все High findings закрыты либо имеют explicit accepted-risk disposition; security/data-integrity Medium findings закрыты; unresolved real secrets не обнаружены; clean-room и production/recovery acceptance пройдены; repository опубликован; private vulnerability reporting доступен внешним пользователям.

A-007 больше не является residual risk: branch и `v*` release-tag paths защищены enforced GitHub rulesets без bypass.

Post-audit изменения должны снова проходить обычные CI/security/release gates; этот PASS относится к проверенной v4.26.8 public-release линии и зафиксированному evidence выше.

## Журнал remediation

- **2026-10-05 · A-001 / #234:** implementation PR #248 открыт. Secret-bearing Full Backup/DB/node/DR artifacts переводятся на host-side/off-site only; Telegram document delivery и `BACKUP_SEND_TO_ADMINS` удаляются. Finding остаётся **Open / acceptance pending** до публикации patch release, deployment, targeted production smoke и финального health check.

- **2026-10-05 · A-002 / #235:** implementation PR #249 открыт. Built-in aiohttp access log для `/compat/{sub_id}` отключается, canonical Nginx `/compat/` route получает `access_log off`, logging contract закрепляется regression test. Finding остаётся **Open / acceptance pending** до patch release, deployment, targeted raw-log smoke и rotation известных exposed test credentials.

- **2026-10-05 · A-003 / #236:** phase-1 PR #250 merged (`d4178af779e344f757ee4bed27cc43c675c32794`): все инвентаризированные state-changing node/inbound/client/importDB calls используют единый one-shot no-redirect mutation boundary, Disaster Recovery сохраняет uncertain importDB как `unknown` без replay. Phase-2 PR #252 добавил fail-closed read-back для destructive user/inbound/node delete; phase-3 PR #253 — post-condition для deterministic field updates. Phase-4 implementation расширяет ту же semantics на provisioning, bulk, create/reset, manual membership и оставшиеся node/inbound/client handlers; нестабильные traffic-reset post-conditions намеренно не объявляются success. Finding остаётся **Open** до зелёного phase-4 PR, patch release и targeted production acceptance.


- **2026-10-06 · A-001/A-002/A-003 / #234/#235/#236:** `v4.26.5` опубликован и развёрнут; targeted production acceptance завершён. A-001: Full Backup создан локально, off-site upload/verification успешен, Telegram получил только status; A-002: fresh compat request не раскрыл credential в container/new bot/nginx logs, test credential после проверки ротирован; A-003: disable/enable mutation smoke прошёл с read-back и восстановлением исходного состояния. Findings закрыты как completed.

- **2026-10-06 · A-004/A-005/A-006 / #237/#238/#239:** implementation PR #260 merged (`a15ff4beaeae2ec249b729e53b2aeaadf6c349ef`); `v4.26.6` / `e04834e9c2d6200fa84896e7c135f476f56bc78e` опубликован и развёрнут. Targeted production acceptance PASS: private-chat boundary подтверждён; cross-origin device/auth header stripping и TLS downgrade rejection подтверждены synthetic runtime smoke; sensitive runtime/backup modes `0700/0600` подтверждены на production. Повторный status-check: `RestartCount=0`, Health/DB/3x-ui connectivity=`ok`. **Статус: Closed**.


- **2026-10-06 · A-007 / #240:** GitHub-side branch/tag protection для текущего private repository не включена (`main.protected=false`, required checks enforcement off). Owner принял residual risk и решил не переходить на платный GitHub plan только ради этого control. Repository-side provenance/CI defense-in-depth сохраняется, но не считается эквивалентом protection. Closure evidence: `docs/audits/v4-a007-github-governance-risk-acceptance-2026-10-06.md`. **Статус: Accepted risk / Closed by owner decision**.

- **2026-10-06 · A-010 / #243:** full Git-history scan и retained GitHub Actions storage audit завершены. Gitleaks v8.30.1 + metadata scanner проверили 343 reachable refs; отдельный Actions audit проверил 1485 retained log archives и 1 retained artifact без coverage gaps. Все candidates получили safe disposition, high-confidence credential findings отсутствуют, unresolved real secrets = 0. Closure evidence: `docs/audits/v4-a010-git-history-secret-audit-2026-10-06.md`.

- **2026-10-06 · A-011 / #244:** implementation merged в PR #268 (`a9ab0c02…`) и rollout fix PR #269 (`d3f06110…`); hotfix `v4.26.8` устранил restrictive-build-context startup regression. Production retest подтвердил non-root runtime, read-only rootfs, zero capabilities, inherited ACL, Full Backup/off-site, DR preflight, representative client/admin flows и финальный `RestartCount=0`, Health/DB/3x-ui=`ok`. **Статус: Closed**.

- **2026-10-06 · A-012 / #245:** implementation merged в PR #270 (`8485346f…`): hard bounds 32 concurrent upstream fetch, 1s slot wait→503, ≤8 MiB response с chunked read; canonical `/compat/` nginx policy — per-client `limit_conn=4`, `5r/s`, burst 10, без access log bearer-like URI. Production/load acceptance на `v4.26.8` PASS: nginx policy validated/reloaded, real refresh PASS, controlled bursts дали bounded 503, 32-slot saturation вернула `503 + Retry-After: 1`, >8 MiB response отклонён, health сохранился под нагрузкой, финальный `RestartCount=0`. **Статус: Closed**.

- **2026-10-07 · A-013 / #246:** repository переведён в public после финального pre-public scan; GitHub Private Vulnerability Reporting включён, а внешний incognito/unauthenticated smoke подтвердил `Security → Advisories → Report a vulnerability`. Custom `.github/VULNERABILITY_REPORT.yml` доступна как private report form; реальный report во время smoke не создавался. #246 закрыт completed. **Статус: Closed / PASS**.

- **2026-10-06 · A-008 / #241:** reproducible baseline merged и подтверждён exact-main Supply-chain audit run `37507349749` на `80a989d0…`; artifact `11432761040`, digest `sha256:32bffc6e…`; actionable HIGH/CRITICAL = 0, SBOM/license evidence сохранены. **Статус: Closed**.

- **2026-10-06 · A-009 / #242:** owner выбрал Apache-2.0; PR #275 merged, canonical `LICENSE` и compatibility review находятся в `main`, #242 закрыт. **Статус: Closed**.

- **2026-10-06 · Cross-cutting pre-public source gates:** exact main `77da78a1…`, Python checks run `37530118941` PASS. Full admin command/callback RBAC/private-chat inventory, 3x-ui mutation/lost-response inventory и повторный security/network/log boundary review завершены без нового blocker. Evidence: `docs/audits/v4-cross-cutting-pre-public-2026-10-06.md`. Последующие clean-room, final pre-public scan и A-013 gates также завершены PASS.

- **2026-10-07 · Clean-room acceptance:** exact release `v4.26.8` / `e096bf43…` exported into isolated `/tmp`, image rebuilt without production data, migration suite 10/10 PASS, restore suite 5/5 PASS, Deploy restart/recovery suite 20/20 PASS after exact-tag host scripts were mounted read-only, Host Control/Fleet recovery suites PASS, and fresh runtime smoke confirmed UID/GID `10001:10001`, readable entrypoint, schema v5 and SQLite quick-check on read-only rootfs. A transient SSH stall during the first Docker build produced no reboot/OOM/kernel crash evidence and production remained `RestartCount=0`, Health/DB/3x-ui=`ok`. Evidence: `docs/audits/v4-cross-cutting-pre-public-2026-10-06.md`. **Статус: PASS**.

- **2026-10-07 · Final pre-public publication gate:** frozen main `c6066c1…` сохранил green `Python checks`; History secret audit run `37538268098` и Actions storage audit run `37538533256` завершились PASS без новых unique fingerprints/coverage gaps. После этого создан и off-site verified свежий post-nginx Full Backup, DR preflight подтвердил manifest `4.26.8`; repository переведён в public, PVR включён и externally verified. **Финальный audit status: PASS**.

- **2026-10-07 · A-007 post-public revalidation:** GitHub API подтвердил `main.protected=true` через active ruleset `Protect main release path` (ID `24575428`): PR-only, squash-only, strict required checks `test`/`title`, deletion/non-fast-forward blocked, linear history, bypass actors absent. Tag-target rulesets отсутствуют; residual accepted risk сужен до release tag refs. **Branch-side control: remediated; tag-side hardening: recommended**.

- **2026-10-07 · A-007 tag hardening:** создан active ruleset `Protect release tags` (ID `24615100`) для `refs/tags/v*`; update/delete/non-fast-forward запрещены, bypass отсутствует, creation новых release tags разрешена. `v4.26.8` сохранил SHA `e096bf436425ea037399e290a5a54f54c729b352`. **A-007: fully remediated / Closed**.
