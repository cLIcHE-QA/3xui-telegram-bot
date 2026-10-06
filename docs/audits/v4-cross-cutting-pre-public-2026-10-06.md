# v4 pre-public cross-cutting audit — 2026-10-06

Статус: **ALL PRE-PUBLIC GATES PASS; A-013 PUBLIC ACCEPTANCE PASS**.

Exact reviewed main:

- SHA: `825d93b9698168cdefe0ad6b6fb37c70601659af`;
- main `Python checks` run `37531345406` — PASS;
- freeze baseline: `fe34f9dc97f0a6441dde9fcfe865e34ad8696c32`;
- delta from freeze to reviewed main: 36 commits.

Этот artifact закрывает source-level cross-cutting gates после A-001…A-012 remediation и clean-room acceptance. Финальный current-tree/history/retained-Actions scan был выполнен непосредственно перед visibility change, после чего public PVR smoke A-013 также завершился PASS.

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

## 4. Clean-room acceptance — PASS

Exact release artifact under test:

- tag: `v4.26.8`;
- SHA: `e096bf436425ea037399e290a5a54f54c729b352`;
- source exported with `git archive v4.26.8` into isolated `/tmp` directory;
- production `.env`, DB, nginx configuration, runtime volumes and credentials were not mounted into clean-room containers.

Image build:

- clean-room image: `3xui-bot-cleanroom:v4.26.8`;
- digest-pinned Python base resolved successfully;
- `requirements.lock` installed with `--require-hashes`;
- final image normalized the root-owned application tree and retained non-root runtime identity.

SQLite fresh install / representative migration:

- exact-tag migration suite: **10 tests PASS**;
- fresh DB reached current schema v5 and `PRAGMA quick_check=ok`;
- representative legacy schemas upgraded through the real `Database.init()` path;
- legacy user/profile data remained intact;
- interrupted/failed migration journal blocks replay;
- recovery-copy semantics remained fail closed.

Verified restore:

- exact-tag restore suite: **5 tests PASS**;
- malformed/traversal archive rejected;
- invalid staged DB did not create pending restore;
- good restore remained atomic and retained a rescue copy;
- tampered staged DB failed SHA-256 validation without replacing live DB;
- failed restore was not replayed.

Controlled restart / failure semantics:

- Host Control and Fleet restart/recovery suites completed successfully before the Deploy suite;
- initial Deploy suite harness lacked `/app/scripts` because `.dockerignore` intentionally excludes host-side scripts from the runtime image;
- re-run mounted the exact-tag `scripts/` tree read-only and the full `test_v419_bot_self_update.py` suite completed **20/20 PASS**;
- restart recovery remains read-only / no automatic mutation replay.

Fresh runtime artifact smoke:

~~~text
UID_GID=10001:10001
ENTRYPOINT_READABLE=ok
FRESH_RUNTIME_DB=ok
CLEANROOM_RUNTIME=ok
~~~

The smoke used `--network none`, read-only rootfs, dropped capabilities, `no-new-privileges`, bounded tmpfs and an isolated writable `/app/data`.

Operational note:

- during the first Docker build the SSH session experienced a transient stall;
- host uptime showed no reboot since 2026-09-29 22:17:13;
- kernel journal for the event window contained no OOM, killed-process, hung-task, watchdog, lockup or segfault evidence;
- production bot status after the event remained `running`, `RestartCount=0`, Health/DB/3x-ui `ok`;
- subsequent clean-room tests were capped at 256 MiB RAM, 0.5 CPU and 64 PIDs.

Result: clean-room acceptance gate — **PASS**.

## 5. Final pre-public / public gates — PASS

Frozen pre-public main:

- SHA: `c6066c1ab77e019970a70ebfa7242a66a41ba8a3`;
- push `Python checks` run `37537988957` — PASS.

Final Git-history/current-tree scan:

- workflow run `37538268098` — PASS on the exact frozen SHA;
- artifact ID `11448040442`;
- artifact digest `sha256:a31fda7f10f2e7d6cd98557ff250839f9cdbdd87c1c78d06193211fb06d46ab0`;
- Gitleaks v8.30.1 candidates: **6**, identical to the previously dispositioned false positives;
- repository metadata candidates: **147** across **364** reachable refs;
- unique metadata fingerprint set did not grow versus the prior accepted A-010 scan;
- unresolved real secrets: **0**.

Final retained Actions storage scan:

- workflow run `37538533256` — PASS on the same frozen SHA;
- artifact ID `11447327296`;
- artifact digest `sha256:d3cd21c28d828e92d518fb90d51e62d1e41ef56b6816d6f314ae4ae46eabdcf7`;
- completed non-skipped runs considered: **1621**;
- retained log archives scanned: **1603**; GitHub no longer retained **18** older log archives;
- retained artifacts scanned: **15/15**;
- coverage issues: **0**;
- finding groups: **14**, with no new detector/fingerprint pair versus the prior accepted A-010 storage scan;
- current/historical repository workflow references to `secrets.*` and `vars.*`: **0**.

Recovery safety immediately before publication:

- Full Backup `3xui-bot-backup-20261006-221647.tar.gz` created after the A-012 nginx policy change;
- off-site copy uploaded and verified;
- DR preflight: archive valid, manifest version `4.26.8`, bot DB, Master x-ui DB, bot env, nginx bundle and Finland node DB present.

Publication / A-013:

- repository visibility changed from private to public only after the final scans;
- `main` still pointed to the frozen pre-public SHA at the moment of visibility verification;
- GitHub Private Vulnerability Reporting enabled;
- external incognito/unauthenticated smoke confirmed **Security → Advisories → Report a vulnerability** is visible;
- no vulnerability report was submitted during the smoke;
- issue #246 closed as completed.

## Safety ordering

The required ordering was preserved: final secret/private-data scans completed on the frozen SHA before public visibility, then PVR was enabled and externally verified.
