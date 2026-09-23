# Восстановление бота после замены или форматирования VPS

Этот runbook предназначен для **нового/заменённого VPS**. Он не превращает бот в универсальный installer всей инфраструктуры.

## Что обязательно хранить вне VPS

Минимум один свежий Full Backup вида:

```text
3xui-bot-backup-YYYYMMDD-HHMMSS.tar.gz
```

Такой архив содержит secrets. Храни его только в защищённом off-site хранилище. Не коммить в Git и не отправляй в issue/PR/chat.

Full Backup может содержать:

- `bot.sqlite3`;
- `bot.env`;
- `x-ui.db`;
- `docker-compose.yml`;
- nginx config;
- backups direct nodes.

Локальные каталоги `/opt/3xui-bot/deploy-backups` полезны для rollback, но **не являются disaster-recovery копией**, если теряется весь VPS.

## Что bootstrap-скрипт НЕ делает

`scripts/bootstrap-bot-from-backup.sh` намеренно не:

- устанавливает ОС/Docker;
- устанавливает или восстанавливает 3x-ui/Xray;
- меняет UFW/nftables/iptables;
- устанавливает MTProxy/nginx;
- меняет DNS/TLS;
- устанавливает SSH/deploy keys;
- восстанавливает remote nodes;
- автоматически включает Host Control Agent.

Эти слои должны быть подготовлены отдельно.

## Порядок нового VPS

1. Установить базовую ОС и обновления безопасности.
2. Установить Docker Engine + Compose plugin, Git, Python 3, curl, openssh-client.
3. Восстановить/установить Master 3x-ui и проверить его отдельно.
4. Восстановить DNS/TLS/firewall/MTProxy отдельно.
5. Создать read-only GitHub deploy key и клонировать репозиторий в:

```text
/opt/3xui-bot/3xui-telegram-bot
```

6. Передать на VPS свежий Full Backup через защищённый канал.
7. Из репозитория выполнить:

```bash
cd /opt/3xui-bot/3xui-telegram-bot
./scripts/bootstrap-bot-from-backup.sh vX.Y.Z /secure/path/3xui-bot-backup-YYYYMMDD-HHMMSS.tar.gz
```

Скрипт:

- проверит tag и `APP_VERSION`;
- потребует, чтобы `manifest.json.version` backup совпадал с выбранным release;
- безопасно проверит tar paths/types/size;
- выполнит `PRAGMA quick_check` для `bot.sqlite3`;
- сохранит существующие `.env`/DB в rescue-каталог, если они есть;
- восстановит только `bot.env → .env` и `bot.sqlite3`;
- намеренно выставит `HOST_CONTROL_TARGETS=` и `NODE_BACKUP_TARGETS=`, чтобы privileged routes/tokens старого deployment не активировались автоматически;
- соберёт и запустит bot container;
- проверит health, SQLite, фактический `APP_VERSION` и общий `deploy-release.sh --status`, включая доступность upstream 3x-ui.

Если требуется осознанно восстановить backup другой версии, это возможно только как break-glass операция:

```bash
RECOVERY_ALLOW_VERSION_MISMATCH=1 \
  ./scripts/bootstrap-bot-from-backup.sh vX.Y.Z /secure/path/backup.tar.gz
```

Без этого флага отсутствие версии в manifest или несовпадение версии блокируют восстановление.

## После bootstrap

Проверить:

```bash
./scripts/deploy-release.sh --status
curl -fsS http://127.0.0.1:18080/healthz && echo
```

Если поменялись IP/domain, обновить соответствующие значения в `.env` до включения mutations.

Затем заново установить Host Control Agent на новом Master:

```bash
sudo scripts/install-host-control-agent.sh master
```

Настроить restricted Docker-bridge proxy по `docs/HOST_CONTROL_DEPLOY.md`, проверить из bot container `401` без token и успешный status с token, затем локально записать новый token в `.env` и включить:

```env
HOST_CONTROL_TARGETS=MASTER
```

Remote host-control nodes включать только после проверки их HTTPS/source allowlist.

`NODE_BACKUP_TARGETS` также включать заново только после проверки direct admin URL/token каждой ноды. Пер-target значения остаются в восстановленном `.env` для ручной сверки, но активный список намеренно очищен.

## Восстановление x-ui.db

Bootstrap бота **не заменяет** `/etc/x-ui/x-ui.db`.

Восстановление Master x-ui DB делается отдельно, на совместимой версии 3x-ui, при остановленном x-ui и после preflight/rescue-copy. Не подменяй x-ui DB одновременно с bot DB без отдельной проверки.

## Контрольная точка

Нормальное восстановленное состояние:

```text
Bot health: ok
bot.sqlite3 quick_check: ok
APP_VERSION: matches release
3x-ui connectivity: ok
Docker subnet: expected
Host Control Agent: re-enrolled
Host-control token: новый/local, не старый из потерянного VPS
Direct node admin targets: re-validated before NODE_BACKUP_TARGETS is enabled
```

После этого можно возвращать remote targets и выполнять mutations.
