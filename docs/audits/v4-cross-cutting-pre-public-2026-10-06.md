# v4 pre-public cross-cutting audit — 2026-10-06

Статус: **SOURCE GATES PASS; CLEAN-ROOM / FINAL SECRET SCAN / A-013 PENDING**.

Exact reviewed main:

- SHA: `77da78a1e2b72d9402291bda319160639a1739bf`;
- main `Python checks` run `37530118941` — PASS;
- freeze baseline: `fe34f9dc97f0a6441dde9fcfe865e34ad8696c32`;
- delta from freeze to reviewed main: 35 commits.

Этот artifact закрывает source-level cross-cutting gates после A-001…A-012 remediation. Он намеренно не объявляет общий audit PASS до clean-room acceptance, финального current-tree/history scan непосредственно перед visibility change и A-013 public PVR smoke.

## 1. Full command/callback authorization inventory — PASS

Runtime router boundary:

- `app_runtime.ADMIN_ROUTERS` содержит все административные routers;
- на каждый admin router навешиваются `AdminPrivateChatMiddleware` для message и callback paths;
- client `client_access_router` намеренно не входит в admin router set;
- `/admin` дополнительно проверяет `is_private_admin_event()` непосредственно в handler;
- repo-wide `Command(...)` surface разделён на administrative `/admin` и client `/inbounds` / `/create`.

Callback authorization:

- `authorize_callback()` сначала требует private chat, затем effective admin role;
- unknown callback, для которого privilege rule отсутствует, fail closed;
- `CALLBACK_RULES` связывает routes с explicit privilege/minimum role;
- `tests/test_rbac_privileges.py::test_literal_admin_routes_are_declared_in_catalog` AST-сканирует admin handler files и требует declaration для exact/prefix/regex admin callbacks;
- representative role boundaries и unknown-route fail-closed закреплены regression tests;
- A-004 private-chat regression отдельно подтверждает middleware placement и исключение client router.

Результат: новых uncovered administrative callback/command routes в reviewed tree не обнаружено.

## 2. 3x-ui mutation inventory / lost-response semantics — PASS

Canonical inventory в `tests/test_audit_xui_mutation_certainty.py` покрывает 26 state-changing `XUIClient` methods:

- node update/delete/enable/update-panel/add;
- Xray/panel restart/stop;
- database import;
- inbound add/update/enable/delete/reset-traffic;
- client create/update/attach/detach;
- bulk attach/detach/enable/disable/reset/adjust;
- client delete и HWID delete.

Для каждого inventory method regression gate требует `_mutation_request()`, а не generic `_request()`.

Mutation boundary:

- one-shot request;
- `allow_redirects=False`;
- отсутствует automatic retry loop;
- network/timeout/5xx/ambiguous response классифицируются как uncertain;
- deterministic 4xx/panel rejection классифицируется как definite failure.

Post-condition/read-back coverage после A-003 включает destructive user/inbound/node delete, deterministic field updates, create paths, provisioning/membership helpers, bulk operations и traffic-reset paths. Uncertain mutation не replay'ится; где post-condition нельзя доказать, результат остаётся unknown/not-provable.

Read-only POST endpoints (`node_probe`, `node_test`, logs, online/IP/HWID/last-online queries) не включаются в mutation inventory по documented API semantics.

Результат: нового state-changing XUI path, обходящего explicit mutation boundary, в reviewed tree не обнаружено.

## 3. Re-review changed security/network/log boundaries — PASS

Reviewed delta от freeze включает A-001…A-012 remediation files и соответствующие regression contracts.

### Secret-bearing backup transport

- Telegram document delivery для Full Backup/DB/node/DR artifacts отсутствует;
- legacy backup-download callbacks удалены/fail closed;
- automatic `BACKUP_SEND_TO_ADMINS` transport удалён;
- host-side DR exports создаются private `0700/0600`.

### Subscription credential / logging

- aiohttp compat proxy запускается с `access_log=None`;
- canonical nginx `/compat/` route имеет `access_log off`;
- `sub_id` документирован как bearer-like credential;
- runtime compat warnings фиксируют bounded error/status, а не request URL/`sub_id`.

### Redirect / outbound boundaries

- subscription proxy follows redirects manually;
- same-origin сохраняет только reviewed device headers;
- cross-origin необратимо удаляет HWID/device/auth/cookie/proxy-auth sensitive headers;
- HTTPS→HTTP downgrade отклоняется;
- website monitoring и Cheburcheck сохраняют bounded response/concurrency/timeout contracts и explicit redirect/public-address validation.

### Runtime/container/filesystem

- dedicated runtime `10001:10001`;
- root-owned application tree read/traverse-only for runtime user;
- read-only rootfs, `cap_drop: ALL`, `no-new-privileges`;
- bounded tmpfs `/tmp`;
- only `/app/data` persistent bind is writable;
- Docker socket/privileged/host-network surfaces отсутствуют;
- bot DB/log/backup paths enforce private modes independently of permissive umask;
- host ACL helper is bounded to documented data/read-only source trees.

### Resource abuse

A-012 production evidence on `v4.26.8` confirmed:

- nginx per-client `limit_conn=4`, `5r/s`, burst 10;
- front-door burst rejected excess requests with bounded 503;
- application concurrency bound = 32 with `503 + Retry-After: 1`;
- upstream body >8 MiB rejected with 64 KiB chunk reads;
- health remained responsive under controlled load;
- final `RestartCount=0`.

Результат: повторный source/network/log review не выявил нового release-blocking finding.

## 4. Gates still pending

До visibility change остаются обязательны:

1. clean-room acceptance: fresh install, representative migration, verified restore, controlled service/restart failures и final smoke;
2. финальный current-tree + full-history + retained Actions storage secret/private-data scan на exact pre-public main;
3. при необходимости повторный exact-main supply-chain run, если security-sensitive dependency/base/workflow inputs изменятся;
4. только после зелёных pre-public gates — repository visibility → public;
5. сразу после visibility change — enable GitHub Private Vulnerability Reporting и внешний `Report a vulnerability` smoke (A-013/#246);
6. финальная revision `docs/audits/v4-final-audit-2026-10-05.md` → PASS при отсутствии новых blockers.

## Safety ordering

Repository **не переводится в public до финального secret/private-data scan**. Это уточняет operational ordering: требование выполнить final scan непосредственно перед visibility change имеет приоритет над ранним A-013 enablement, которое технически возможно только после public visibility.
