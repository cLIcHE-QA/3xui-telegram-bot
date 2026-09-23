# Security

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

## Host Control Agent

Host-control в v4.10.0 не является каналом доступа к VPS. Security boundary:

- agent слушает только `127.0.0.1`;
- remote доступ допускается только через restricted HTTPS reverse proxy и source allowlist;
- Bearer token отдельный для каждого host и не переиспользуется между targets;
- HTTP API не содержит SSH/shell/exec/file/Docker/firewall/reboot/package-management операций;
- action — только `start|stop|restart`, systemd unit жёстко задан как `x-ui.service`;
- OS-команды формируются только статическим argv и запускаются с `shell=False`;
- agent работает непривилегированным пользователем, sudoers разрешает только три точных systemctl-команды без wildcard;
- mutation POST после timeout/lost response автоматически не повторяется;
- destructive Stop service и Stop Xray доступны только Owner.

Любое расширение этого privilege boundary требует отдельного threat-model review.

## Backup/Restore

Полные backup-архивы содержат секреты и должны храниться вне публичных артефактов репозитория. Restore-операции следует выполнять только после preflight/dry-run и наличия rescue-копии текущего состояния.
