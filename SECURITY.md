# Security

## Supported versions

Security fixes are provided for the latest published v4 release line only.

| Version | Supported |
| --- | --- |
| Latest published v4.x | ✅ |
| Older v4 releases | ❌ |
| Unreleased development branches | Best effort; not a supported production release |

Before reporting, reproduce against the latest published v4 release when safely possible. Do not publish a proof of concept, exploit details, credentials, subscription identifiers, private hostnames/IPs, database content, backup artifacts, or secret-bearing logs in a public issue.

## Reporting a vulnerability

For public releases, the canonical reporting channel is **GitHub Private Vulnerability Reporting**:

1. Open the repository's **Security** tab.
2. Open **Advisories**.
3. Click **Report a vulnerability**.
4. Submit the report privately.

Do **not** open a normal public issue for a vulnerability or suspected secret exposure.

Private Vulnerability Reporting can only be enabled by GitHub for a public repository. While this repository remains private during the final v4 audit, external public reporting is not active. Before changing repository visibility to public, maintainers must enable **Settings → Security and quality → Advanced Security → Private vulnerability reporting** and verify that the **Report a vulnerability** flow is available.

If the report itself contains an active credential, rotate/revoke it first when you control that credential, then include only the minimum information needed to identify the affected boundary. Never attach production databases, backups, private keys, full subscription URLs, or raw secrets.

### What to include

Include:

- affected version/tag and commit SHA when known;
- affected component and attack surface;
- minimal reproduction steps;
- impact and required attacker prerequisites;
- sanitized logs or fingerprints where useful;
- whether an active credential may already be exposed.

Do not include unnecessary personal data or unrelated production material.

### Response expectations

This is a maintainer-operated project, not a staffed security operations service. Reports are handled on a best-effort basis.

Maintainers should:

- acknowledge a valid private report as soon as practical;
- keep security-sensitive discussion private until a fix/mitigation is available;
- prioritize active credential exposure, remote compromise, privilege-boundary bypass, destructive data-integrity issues, and unauthenticated public attack paths;
- coordinate disclosure timing with the reporter when practical;
- publish a security advisory when public disclosure is appropriate.

No fixed SLA is promised. If immediate containment is required, rotate/revoke exposed credentials and disable the affected public path before waiting for a code fix.


Репозиторий предназначен для управления VPN-инфраструктурой и может работать с административными токенами, subscription identifiers, базами 3x-ui и другими чувствительными данными.

## Не коммитить

Никогда не добавляйте в Git:

- `.env` и его реальные копии;
- `BOT_TOKEN`, `PANEL_API_TOKEN`, `NODE_*_API_TOKEN`, `HOST_CONTROL_*_TOKEN`;
- `bot.sqlite3`, `x-ui.db`, WAL/SHM и другие runtime DB;
- backup-архивы и содержимое `data/`;
- Reality/AWG/private keys, PEM private keys;
- реальные subscription URLs/IDs, если они дают доступ к конфигурации пользователя;
- приватные TLS-ключи и каталоги secrets/certs.

`.env.example` должен содержать только заведомо фиктивные значения.

## Если секрет попал в Git

1. Сразу отозвать/перегенерировать секрет в исходной системе.
2. Не ограничиваться удалением в следующем commit: секрет останется в истории.
3. Очистить Git history специализированным инструментом (`git filter-repo`/аналог) и force-push только после согласования.
4. Проверить forks, CI logs, artifacts и GitHub Actions secrets.

## Telegram Admin Control Plane

Admin Control Plane работает только в личном чате оператора с ботом. Это отдельная trust boundary, а не UX-предпочтение:

- `/admin`, admin callbacks и admin FSM input принимаются только при `chat.type=private`;
- group, supergroup и channel context fail closed до выполнения handler и не получают admin rendering;
- проверка private-chat context дополняет RBAC по Telegram ID/role и не заменяет его;
- client-facing router остаётся отдельным контуром и не получает это ограничение автоматически.

## Subscription credentials и access logs

`sub_id` и полный subscription URL считаются bearer-like credentials. Compatibility path `/compat/{sub_id}` поэтому не должен попадать в raw HTTP access logs:

- встроенный aiohttp access logger compatibility proxy отключён;
- reverse proxy для `/compat/` должен использовать `access_log off` либо доказанно sanitized формат без request URI/`$request_uri`;
- HWID/device headers и subscription identifiers не выводятся в application/audit diagnostics;
- upstream redirects обрабатываются вручную: HWID/device headers сохраняются только на same-origin hop, при первом cross-origin hop удаляются и не восстанавливаются дальше по chain; HTTPS downgrade отклоняется;
- если действующий `sub_id` попал в raw logs/chat/issue, его следует ротировать как скомпрометированный credential.

## Host Control Agent

Host-control в v4.10.0 не является каналом доступа к VPS. Security boundary:

- agent слушает только `127.0.0.1`;
- remote доступ допускается только через restricted HTTPS reverse proxy и source allowlist;
- Bearer token отдельный для каждого host и не переиспользуется между targets;
- HTTP API не содержит SSH/shell/exec/Docker/firewall/reboot/package-management операций и не предоставляет general-purpose file access;
- единственное чтение host filesystem — fixed read-only `GET /v1/snapshots/nginx` из локально заданного `HOST_CONTROL_AGENT_NGINX_SOURCE`; request не принимает path/filename/query selector;
- action — только `start|stop|restart`, systemd unit жёстко задан как `x-ui.service`;
- OS-команды формируются только статическим argv и запускаются с `shell=False`;
- agent работает непривилегированным пользователем, sudoers разрешает только три точных systemctl-команды без wildcard;
- mutation POST после timeout/lost response автоматически не повторяется;
- destructive Stop service и Stop Xray доступны только Owner.

Любое расширение этого privilege boundary требует отдельного threat-model review.

## 3x-ui mutation safety

State-changing 3x-ui API calls используют отдельную one-shot mutation boundary:

- redirects запрещены;
- request автоматически не повторяется после timeout/lost response/5xx или другого uncertain outcome;
- uncertain outcome поднимается как `XUIMutationError(uncertain=True)`, а не как доказанный failure;
- read-only POST diagnostics не считаются mutation только из-за HTTP method;
- `importDB` использует тот же one-shot boundary, несмотря на multipart payload;
- после uncertain outcome caller должен выполнить read-back/post-condition там, где это возможно, либо явно оставить состояние `unknown`; слепой повтор запрещён.

Особенно для restore/import unknown outcome не означает «restore не произошёл»: сначала проверяется фактическое состояние 3x-ui и rescue copy.
## Backup/Restore

Полные backup-архивы, `bot.sqlite3`, direct-node snapshots и exports вроде `bot.env` являются secret-bearing artifacts. Telegram используется только как control UI: такие файлы не прикладываются к сообщениям и не рассылаются администраторам. Получение выполняется только через защищённый host-side/off-site recovery path.

Полные backup-архивы содержат секреты и должны храниться вне публичных артефактов репозитория. Backup/runtime directories для этих данных имеют mode `0700`; Full Backup, bot/node snapshots, bot SQLite и local bot log files — `0600`. Startup/creation path ужимает существующие permissive modes и не полагается на host umask. Restore-операции следует выполнять только после preflight/dry-run и наличия rescue-копии текущего состояния.

Direct-node snapshot собирается из двух раздельных privilege domains: `x-ui.db` приходит через dedicated `NODE_BACKUP_*` direct-admin token, а nginx configuration — через fixed read-only Host Control snapshot source. Telegram/Master не передаёт filesystem path на node. `node.json` и `manifest.json` не должны содержать API/Host Control tokens; manifest фиксирует checksums и явно отмечает missing/degraded components.

Nginx configuration из remote node не применяется автоматически. При ручном восстановлении сначала проверяется содержимое bundle и локальная конфигурация валидируется штатным `nginx -t` до reload.
