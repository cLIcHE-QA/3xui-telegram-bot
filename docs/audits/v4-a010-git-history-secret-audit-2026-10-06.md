# A-010 / #243 — Git-history и GitHub Actions secret audit — 2026-10-06

## Итог

**Статус scope A-010:** PASS.

На проверенном repository/history/retained-Actions scope не обнаружено unresolved real secrets или production-specific private data, требующих rotation/revocation либо history sanitization.

Raw secret-bearing values в этот отчёт не включаются.

## 1. Full Git-history scan

### Exact source

- SHA: `c8a15362d82bfae812dc93758568602a1475febd`
- GitHub Actions workflow: `History secret audit`
- Run ID: `37460704620`
- Job: `audit` — success
- Artifact ID: `11412911409`
- Artifact ZIP digest: `sha256:d8b82f83480cba56881af9e0087c175a1006bbc57a81ca728749667181f12bee`

### Scanner baseline

- Gitleaks: `v8.30.1`
- Linux x64 release archive SHA-256:
  `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`
- repository metadata scanner: `scripts/scan-git-history-sensitive.py`, scanner version `1`

Canonical command:

~~~bash
bash scripts/run-history-secret-audit.sh /tmp/3xui-history-secret-audit
~~~

Gitleaks запускается с history-aware `gitleaks git` и `--redact=100`; raw Gitleaks JSON остаётся во временном каталоге и не публикуется как evidence.

### Coverage и результаты

- reachable refs: **343**
- sanitized Gitleaks candidates: **6**
- sensitive metadata candidates: **135**
- sensitive committed path candidates для real `.env`, DB, private key, credential file или backup archive: **0**

Disposition Gitleaks candidates:

- documentation placeholder token — false positive;
- truncated/sample key из pinned 3x-ui OpenAPI — false positive;
- historical Git commit SHA в integration helper — false positive.

Metadata candidates после review:

- RFC1918/test/default Docker bridge values;
- example/test Telegram ID;
- example URLs и source-syntax matches;
- production-specific private hostname/IP не обнаружен.

Итог full-history части: **unresolved real secrets = 0**.

## 2. Retained GitHub Actions storage scan

### Exact source

- SHA: `f5b30900e8c53e47bb27b3e30d145b9feff81d20`
- GitHub Actions workflow: `Actions storage secret audit`
- Run ID: `37468941581`
- Job: `audit` — success
- Artifact ID: `11415224479`
- Artifact ZIP digest: `sha256:6d6463078215f33d3beb103cb5c3439d3eaf0313686d8c4db60f3aeb8f7861ca`
- scanner: `scripts/scan-github-actions-storage.py`, scanner version `1`

Canonical invocation:

~~~bash
python3 scripts/scan-github-actions-storage.py \
  --report "$RUNNER_TEMP/actions-storage-audit.json"
~~~

Workflow permissions:

- `contents: read`
- `actions: read`

### Coverage

- workflow runs visible to scanner: **1932**
- completed non-skipped runs considered: **1500**
- retained log archives scanned: **1485**
- completed runs whose logs GitHub больше не хранит: **15**
- retained artifacts present before output artifact creation: **1**
- retained artifacts scanned: **1**
- scanner coverage issues: **0**

`not-retained` не считается coverage gap для retained-storage audit: соответствующий log archive уже отсутствует на стороне GitHub и не является retained storage.

Новый artifact самого Actions-storage audit содержит только sanitized JSON report и создаётся после завершения scanner step.

### Findings

Найдено **14 unique fingerprint groups**, все из low-confidence metadata detectors:

- **3 private IPv4 groups**:
  - standard Docker bridge/network examples `172.19.0.0` и `172.19.0.1`;
  - test target `10.0.0.1`.
- **11 private-endpoint candidate groups**:
  - source/assertion fragments вроде `host`, `hostname`, `_normalize_hostname(...)` и escaped formatting fragments;
  - реального hostname/domain/endpoint среди этих groups нет.

High-confidence credential detectors в retained logs/artifacts не нашли:

- private keys;
- GitHub tokens;
- Telegram bot tokens;
- AWS access keys;
- JWT;
- URL credentials;
- generic long secret assignments.

Sensitive artifact filenames/content также не обнаружены.

Итог retained-Actions части: **unresolved real secrets = 0**.

## 3. GitHub Actions Secrets / Variables exposure

GitHub-provided `GITHUB_TOKEN` не имеет права перечислять repository Actions Secrets/Variables names: REST inventory вернул `HTTP 403` для обоих endpoints. Secret values GitHub API всё равно не возвращает.

Exposure проверен через полный source/history workflow inventory:

- current workflow refs `secrets.*`: **0**
- historical workflow refs `secrets.*`: **0**
- current workflow refs `vars.*`: **0**
- historical workflow refs `vars.*`: **0**
- release workflow использует только автоматически выдаваемый `${{ github.token }}`.

Следовательно, repository-defined Actions Secrets/Variables не инжектировались в workflow execution через repository workflow definitions. Evidence утечки repository-defined Actions secrets отсутствует.

Наличие неиспользуемых secret entries в GitHub Settings, если они существуют, не является exposure в repository/history/logs; их можно удалить как отдельную hygiene cleanup. Для A-010 blocker является фактическая exposure/unresolved secret, которой не обнаружено.

## 4. Safety / handling

Во всех audit artifacts соблюдалось:

- raw secret values не публиковались в issue/PR/versioned report;
- Gitleaks raw report оставался ephemeral;
- metadata values хранились как SHA-256 fingerprints;
- Actions logs/artifacts не переупаковывались и не публиковались обратно;
- redirect на GitHub artifact blob storage выполнялся без forwarding repository token.

## 5. Closure decision

Acceptance A-010/#243 выполнен:

- full Git history проверена history-aware scanner;
- exact scanner versions/commands/SHA зафиксированы;
- deleted/old reachable objects и sensitive artifact paths проверены;
- retained GitHub Actions logs/artifacts проверены;
- workflow history не содержит repository `secrets.*` / `vars.*` usage;
- все candidates получили безопасный disposition;
- **unresolved real secrets = 0**.

A-010 может быть закрыт. Перед фактическим изменением repository visibility остаётся обязательным финальный повторный current-tree/history scan согласно общему public-release gate.
