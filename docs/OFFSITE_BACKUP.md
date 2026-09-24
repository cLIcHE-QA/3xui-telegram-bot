# Encrypted off-site Full Backup

Этот документ описывает обязательный pre-v5 off-site recovery path, впервые реализованный в v4.18.0.

## Цель

Локальный Full Backup на Master VPS остаётся основным быстрым recovery artifact, но не защищает от полной потери VPS/filesystem. Off-site backup создаёт отдельную зашифрованную копию проверенного Full Backup в S3-compatible object storage.

Off-site transport не является general-purpose remote filesystem API и не управляется произвольными параметрами из Telegram.

## Security boundary

При включённом off-site backup:

- bot принимает bucket, prefix, region, endpoint и credentials только из локального `.env`;
- Telegram callback не может передать bucket, object key, filesystem path, endpoint или credentials;
- custom S3-compatible endpoint допускается только через verified HTTPS;
- используется отдельный object-storage principal, не связанный с `PANEL_API_TOKEN`, Host Control token или GitHub deploy key;
- Full Backup шифруется **client-side AES-256-GCM** до upload;
- encryption key не хранится рядом с object storage и должен иметь отдельную recovery copy вне Master VPS;
- remote object содержит только ciphertext и безопасный metadata subset: source SHA-256, source size, release version и исходное canonical backup filename;
- Telegram не является off-site storage.

## Какие backup'ы разрешено отправлять

Transport принимает только canonical файлы:

~~~text
3xui-bot-backup-YYYYMMDD-HHMMSS.tar.gz
~~~

Перед upload архив обязан пройти:

1. safe tar-member validation;
2. manifest schema `2`;
3. SHA-256/size validation всех обычных файлов из manifest;
4. `PRAGMA quick_check` для `bot.sqlite3`;
5. `PRAGMA quick_check` для `x-ui.db`;
6. наличие `bot.env`.

Если deep validation не проходит, upload не выполняется.

`manifest.json` schema 2 содержит `integrity.files` с `path`, `bytes` и `sha256` для каждого обычного файла архива, кроме самого manifest.

Legacy backup без schema 2 остаётся читаемым обычным DR tooling, но не принимается новым off-site uploader.

## Separate outcomes

Локальный backup и off-site replication — разные операции.

Локальное создание использует существующие jobs:

- `backup.daily`;
- `backup.manual`.

Off-site replication записывается отдельно:

~~~text
backup.offsite
~~~

Если локальный Full Backup уже создан, а off-site upload завершился ошибкой:

- локальный backup не становится failed;
- `backup.offsite` получает `failed`;
- audit фиксирует отдельный `backup.offsite.upload` failure;
- следующий scheduled/manual Full Backup может выполнить новую off-site replication;
- неопределённый upload не считается доказанным success.

## Remote verification

Upload считается успешным только после полного round trip:

1. local archive deep-validated;
2. archive streaming-encrypted AES-256-GCM;
3. ciphertext uploaded;
4. `HEAD` подтверждает encrypted object size и source metadata;
5. object скачивается обратно;
6. ciphertext проходит GCM authentication;
7. plaintext SHA-256/size совпадают с исходным archive;
8. скачанный Full Backup снова проходит deep validation;
9. только затем применяется off-site retention.

Для daily backup это одновременно является ежедневной проверкой читаемости последней внешней копии.

## Retention

`OFFSITE_BACKUP_KEEP` задаёт число последних encrypted Full Backup objects внутри **фиксированного** `OFFSITE_BACKUP_PREFIX`.

Удаляются только canonical objects вида:

~~~text
<prefix>/3xui-bot-backup-*.tar.gz.enc
~~~

Transport не удаляет посторонние objects в bucket.

## Настройка

По умолчанию feature выключена:

~~~env
OFFSITE_BACKUP_ENABLED=false
~~~

Для включения:

~~~env
OFFSITE_BACKUP_ENABLED=true
OFFSITE_BACKUP_BUCKET=my-3xui-backups
OFFSITE_BACKUP_PREFIX=production/master
OFFSITE_BACKUP_REGION=eu-central-1
OFFSITE_BACKUP_ENDPOINT_URL=
OFFSITE_BACKUP_ACCESS_KEY_ID=<dedicated-access-key>
OFFSITE_BACKUP_SECRET_ACCESS_KEY=<dedicated-secret-key>
OFFSITE_BACKUP_KEEP=14
OFFSITE_BACKUP_ENCRYPTION_KEY_B64=<base64-of-32-random-bytes>
~~~

Для AWS S3 `OFFSITE_BACKUP_ENDPOINT_URL` оставляется пустым. Для S3-compatible provider указывается verified HTTPS endpoint.

Сгенерировать отдельный encryption key:

~~~bash
python3 - <<'PY'
import base64
import secrets
print(base64.b64encode(secrets.token_bytes(32)).decode())
PY
~~~

Сохрани этот key отдельно от Master VPS и отдельно от object-storage account. Потеря ключа делает encrypted off-site objects невосстановимыми.

## Минимальные object-storage permissions

Dedicated principal должен иметь доступ только к выбранному bucket/prefix.

Нужны операции уровня:

- list bucket с ограничением prefix;
- put object в prefix;
- get/head object из prefix;
- delete object из prefix для retention.

Не выдавай этому principal административные permissions на account/bucket policy, unrelated buckets или произвольные prefixes.

Конкретный IAM/policy syntax зависит от provider-а.

## Включение на production

После заполнения `.env`:

~~~bash
docker compose config --quiet
docker compose up -d --no-deps --force-recreate bot
./scripts/deploy-release.sh --status
~~~

Затем запусти обычный manual Full Backup из `/admin → Backups → Создать сейчас` или `System → Jobs → Запустить backup сейчас`.

Ожидаемый результат:

- local Full Backup создан;
- UI показывает `☁️ Off-site: загружен и проверен`;
- `System → Jobs` содержит отдельный `backup.offsite` со статусом `success` либо `partial`, если local backup содержит явно отмеченные missing optional components.

## Recovery secrets

Для recovery с нового VPS подготовь отдельный файл, например:

~~~text
/root/3xui-offsite-recovery.env
~~~

Он должен содержать только необходимые `OFFSITE_BACKUP_*` значения и иметь mode `0600`:

~~~bash
chmod 600 /root/3xui-offsite-recovery.env
~~~

Не храни этот файл в Git и не отправляй через Telegram.

## Восстановление с нового VPS

После базовой подготовки host, Git checkout нужного release и установки Python dependencies:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
python3 -m venv .venv-recovery
.venv-recovery/bin/python -m pip install -r requirements.txt
mkdir -p /root/3xui-recovery
chmod 700 /root/3xui-recovery
~~~

Скачать **latest** object из фиксированного configured prefix:

~~~bash
.venv-recovery/bin/python scripts/fetch-offsite-backup.py \
  --env-file /root/3xui-offsite-recovery.env \
  --output /root/3xui-recovery/latest.tar.gz
~~~

Команда:

- не принимает remote object key;
- выбирает latest canonical object только внутри configured prefix;
- проверяет object metadata;
- decrypt/authenticates AES-GCM;
- проверяет plaintext SHA-256/size;
- выполняет deep Full Backup validation;
- не перезаписывает существующий output;
- сохраняет verified archive с mode `0600`.

Успешный результат:

~~~text
OFFSITE_RECOVERY_OK=/root/3xui-recovery/latest.tar.gz
~~~

Далее используется существующий bootstrap path:

~~~bash
./scripts/bootstrap-bot-from-backup.sh vX.Y.Z /root/3xui-recovery/latest.tar.gz
~~~

Используй release tag, соответствующий `manifest.version`, если нет осознанной break-glass причины для version mismatch.

Bootstrap по-прежнему:

- отказывается от in-place restore поверх работающего bot container;
- проверяет archive и SQLite;
- создаёт rescue copy;
- восстанавливает только bot `.env` и `bot.sqlite3`;
- отключает privileged direct-node/Host Control targets до повторной локальной валидации.

`x-ui.db`, nginx и node recovery выполняются по существующему Disaster Recovery runbook отдельно и контролируемо.

## Проверка после recovery

После bootstrap:

~~~bash
./scripts/deploy-release.sh --status
~~~

Проверь:

- exact Git tag/SHA;
- Bot version;
- Health `ok`;
- DB `ok`;
- ожидаемый Docker subnet;
- 3x-ui connectivity;
- privileged target enrollment перед повторным включением Host Control / direct-node mutations.

## Failure semantics

Нельзя считать off-site backup успешным только потому, что provider принял `PUT`.

Успех означает подтверждённый remote round-trip и deep validation.

При timeout после upload, metadata mismatch, GCM authentication failure, checksum mismatch, corrupted tar, invalid SQLite или unreadable object операция `backup.offsite` завершается `failed`. Система не предполагает success и не подменяет локальный backup внешним состоянием.
