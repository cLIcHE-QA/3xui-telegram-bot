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

## Последний проверенный recovery drill

Production off-site recovery drill успешно завершён **2026-10-05** на runtime release `v4.26.4`.

Проверенная цепочка:

- manual Full Backup завершился отдельным `backup.offsite=success`;
- внешняя encrypted copy прошла обязательный upload → HEAD → download → AES-256-GCM authentication/decrypt → plaintext SHA-256/size → повторный deep Full Backup validation round trip;
- отдельный recovery VPS получил latest canonical object через host-side recovery CLI с результатом `OFFSITE_RECOVERY_OK`;
- восстановленный archive имел `manifest.version=4.26.4`;
- bootstrap smoke на recovery VPS восстановил `bot.env` и `bot.sqlite3`, запустил bot container с `APP_VERSION=4.26.4`; health и SQLite quick-check завершились `ok`;
- финальный generic upstream TCP probe с изолированного recovery VPS получил timeout до production subscription endpoint. Это не было ошибкой backup/restore: DNS resolution работал, а сетевой доступ replacement Master к production upstream относится к отдельной инфраструктурной подготовке нового VPS;
- recovery bot после smoke был остановлен до возврата production polling, production Master возвращён в состояние Health/DB/3x-ui connectivity `ok`, временное recovery окружение очищено.

Этот drill подтверждает **off-site backup/read/decrypt/deep-validation и bot-state restore path**, но не означает, что bootstrap автоматически восстанавливает 3x-ui, DNS/TLS/firewall/nginx/MTProxy, Host Control Agent или direct-node network policy. Эти слои по-прежнему выполняются отдельно по разделам ниже.

Drill не публикует bucket credentials, encryption key, bot/panel tokens, archive contents или иные production secrets. Канонический transport для secret-bearing recovery artifacts — только защищённый host-side/off-site path; Telegram/GitHub не используются как backup storage.

## Исправление host identity: rc.7 DR, 2026-10-10

**Окончательное уточнение оператора ~16:20 МСК:** доступная инфраструктура **только два VPS: production Master и отдельная Node**. Третьего Recovery VPS **никогда не было**. Node не объявлялась DR replacement Master. Инструкции запустить recovery-команды на третьем VPS были ошибочным предположением, а не фактом инфраструктуры. Для текущего rc.7 независимый DR **NOT EXECUTED**. Не пытаться искать третий сервер или использовать Node для recovery без отдельного плана/согласования.

**Оператор в ~16:12 МСК уточнил: все DR команды текущей серии, считавшиеся запущенными на отдельном Recovery VPS, на самом деле выполнялись на production Master.** Строки `RECOVERY` в stdout не являются доказательством физического хоста. Предыдущие записи 2026-10-10 о controlled Docker startup, SQLite extraction, S3 verification, Master preflight и version inspection — только **Master-local scoped evidence**, а не independent second-VPS recovery. Независимый Recovery VPS **NOT VERIFIED / PENDING**, полный v5 acceptance **NOT PASS**; исторический drill от 2026-10-05 этим фактом не пересмотрен.

**Пауза на Master:** не запускать дополнительные restore/bootstrap, `x-ui` lifecycle, test images с production mounts и не удалять предполагаемые test DB/plaintext artifacts без inventory. Старое правило «очистка на Recovery VPS» не означает разрешения выполнить wildcard/deletion на Master. Следующий шаг — установить идентичность двух *уже открытых* shell sessions read-only командами `/proc/sys/kernel/random/boot_id` и `hostname` **с локальным сравнением**, не публикуя hostname, IP или сам boot ID в чат. Для доказательства двух машин нужны два различных boot ID, сверенных на обеих SSH-сессиях; метка `ROLE=RECOVERY` недостаточна. При совпадении или отсутствии второго сеанса — STOP. Затем заново выполнить DR только на фактически независимом изолированном VPS.

## Очистка артефактов изолированных DR-тестов

**Обязательное правило для Recovery VPS:** каждый тест до запуска определяет собственные временные файлы, каталоги, Docker image/container, критерий окончания и порядок очистки. `PASS` или `NOT PASS` не отменяют cleanup. Удалять разрешено только после сверки точного владельца/пути и подтверждения, что артефакт не нужен для незавершённого DR; никакого wildcard удаления вне специально созданного disposable workspace.

- **Удалять после завершения теста (в том числе при ошибке):** disposable SQLite snapshots, файлы synthetic env, temporary source checkouts, временные scripts/logs, одноразовые контейнеры (включая failed/stopped); использовать `trap` / `finally` / `docker run --rm`. Диагностические временные файлы при `NOT PASS` можно удержать **до 24 часов** для локального анализа в защищённом workspace, затем удалить; в GitHub/chat только redacted status и класс ошибки, без raw DB/logs/secrets.
- **Сохранить до закрытия DR acceptance (потом удалить с Recovery VPS отдельным scoped cleanup):** зашифрованный объект остаётся в object storage по своей retention policy; скачанный и расшифрованный exact scheduled backup #96/#97, а также изолированные `bot.sqlite3` / Master `x-ui.db`, извлечённые из него, пока нужны для полноценного bot/Master restore drill, остаются в защищённом каталоге с минимумом прав. После фактического завершения, документирования и наличия подтверждённой восстановимой **внешней** копии plaintext архив и восстановленные локальные SQLite удалить; это не удаляет исходные production backup или remote encrypted copy.
- **Локальный образ теста:** `3xui-rc7-recovery-drill:20261010` не содержит секретов/DB, но может быть нужен для исправления failed process smoke; хранить до окончания именно этого тестового этапа и затем удалить **по точному image tag/ID** после проверки, что он не используется контейнерами. Не удалять shared pinned base `python:3.12-slim@sha256:...` и не запускать `docker system prune` ради DR cleanup.
- **Не затрагивать никогда автоматической DR-cleanup:** production SQLite, оригинальные scheduled archives/backups, production Docker containers/images/volumes, `/root/3xui-offsite-recovery.env` и его ключ, проверяемый remote S3 object #97, S3 bucket/prefix, journal/evidence, release tags и любые неизвестные операторские файлы. Remote retention регулирует исключительно `docs/OFFSITE_BACKUP.md`, а не ручная очистка.
- **Before/after audit:** перед удалением проверить отсутствие активного drill/незавершённого investigation, точные абсолютные paths/image IDs, отсутствие symlink, scope только Recovery VPS. После проверить отсутствие временных артефактов и зафиксировать лишь `CLEANUP: PASS/NOT PASS` и категории, **без** списков приватных путей, backup contents или секретов. При сомнении — **не удалять**.

**Состояние на 2026-10-10 ~15:37 МСК:** process/container smoke для `v5.0.0-rc.7` завершился `NOT PASS` с классом `ModuleNotFoundError` (operator-reported); exact missing module не определён, нельзя считать `bot.py` восстановленным. Pinned Docker image build, non-root user, disposable DB preparation — отдельные scoped PASS. Container запущен с `--rm`, disposable workspace из команды использует `trap`, но их post-cleanup физически не проверен. Не удалять source recovery archive и isolated SQLite до успешного повторного smoke и отдельного Master DR.

**Обновление ~15:46 МСК (2026-10-10), operator-reported:** повторный controlled Docker process smoke **scoped PASS**: `PYTHONPATH=/app`, immutable rc.7 image, disposable restored SQLite v11, реальный `app_runtime.main()`, real loopback `/healthz`, router registration и clean shutdown, внутри `--network none` с synthetic tokens, patched Telegram polling/recovery/background workers и без production endpoints. Предыдущее `NOT PASS` остаётся историческим evidence, но текущий ограниченный process smoke PASS. Это не доказательство непатченного production startup, внешнего Telegram transport, provider/3x-ui connectivity либо полного Master restore. Использованный disposable Docker image теперь кандидат для удаления после проверки отсутствия потребителей и закрытия bot-only smoke; plaintext archive и исходные isolated DB остаются до Master DR. Post-cleanup audit ещё PENDING.

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

## Изолированный Master 3x-ui drill при занятом Recovery VPS

Если на Recovery VPS проверка `X-UI SERVICE INACTIVE` или `NO RUNNING X-UI PROCESS` дала `NOT READY`, **host-level восстановление блокировано**. Это не означает ошибку backup; сервис/процесс может уже использовать хостовую панель и её базы. Запрещены `systemctl stop/restart x-ui`, подмена `/etc/x-ui/x-ui.db`, правки host CLI settings, запуск второго `x-ui` с default paths, `docker compose up/down` в чужом stack и любая команда, способная активировать Xray с восстановленными inbounds.

Дальнейшая последовательность:

1. Read-only выяснить версию установленного **на исходном production Master** 3x-ui и версии доступного isolated recovery binary/image; обычное наличие executable и архитектуры `x86_64` **не доказывает** совместимость. Не вызывать меню `/usr/bin/x-ui` (может быть script с управляющими действиями), settings/reset/update/migrate. Если поддерживается установленным *настоящим бинарником*, допустим только безобидный `-v` с таймаутом и подавлением произвольного stderr, без вывода credentials/settings. Версия production может отличаться от версии уже занятого Recovery VPS.
2. Подготовить отдельный **pinned** 3x-ui Docker image по совместимой версии (immutable release/digest, не `latest`), проверить источник. Не давать образу host network, host `/etc/x-ui`, Docker socket, systemd или privilege caps; избегать постоянных volumes и port mappings.
3. Сделать одноразовый SQLite snapshot ранее извлечённой Master `x-ui.db` в новом каталоге mode `0700` на Recovery VPS. Любые миграции/изменения разрешены **только на disposable copy**, никогда на исходной извлечённой DB.
4. Если standalone runtime smoke нужен после отдельного review, запускать в закрытой сети `--network none`, с явным `XUI_DB_FOLDER` на disposable volume и `XUI_LOG_FOLDER` внутри него; обеспечить **отсутствие запуска Xray, управления inbounds, Fail2ban/firewall и любых внешних подключений**, а также безопасную очистку по политике выше. Перед этим проверить конфигурацию именно выбранной версии — `--network none` само по себе не предотвращает запуск Xray внутри контейнера.
5. По итогу отметить отдельно `Master SQLite: scoped PASS`, `compatible 3x-ui startup/read-back: PASS/NOT PASS`, `external panel/Xray connectivity: PENDING`. Если безопасный запуск не обеспечен, **не запускать и сохранять PENDING**. Production и установленный на Recovery VPS x-ui не менять.

**Operator evidence 2026-10-10 ~15:55 МСК:** `MASTER RESTORED DB: PASS`, `MASTER SQLITE INTEGRITY: PASS`, `3X-UI EXECUTABLE: PASS`, `DOCKER ENGINE: PASS`, `MASTER RESTORE PREFLIGHT: PASS`; но отдельный guard дал `X-UI SERVICE INACTIVE: NOT READY`, `NO RUNNING X-UI PROCESS: NOT READY` (`RECOVERY ARCHITECTURE: x86_64`). Следовательно **host isolation NOT READY**, восстановление работающей Master панели не проверено.

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
