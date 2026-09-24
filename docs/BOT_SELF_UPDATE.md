# Safe Bot Self-Update

`v4.19.0` добавляет Owner-only обновление production bot через отдельный restricted Deploy Agent.

## Архитектура

~~~text
Telegram /admin
        |
        | authenticated fixed API
        v
Deploy Agent (host systemd, unprivileged)
        |
        | sudo: one root-owned restricted helper
        v
/usr/local/libexec/3xui-bot-deploy
        |
        | fixed repository/service/credentials
        v
scripts/deploy-release.sh vX.Y.Z
        |
        v
Git tag -> Docker Compose -> production bot
~~~

Deploy Agent переживает recreate bot container и хранит собственный persistent operation journal.

## Security boundary

Bot container по-прежнему НЕ получает Docker socket, host shell, GitHub deploy key, SSH private key, systemd socket, arbitrary host filesystem mount или generic command runner.

Deploy Agent API не принимает shell command, argv, executable, script path, arbitrary Git ref/SHA, Docker arguments, filesystem path или environment overrides.

Разрешён только published release tag формата `vX.Y.Z`. Repository, Compose project/service, health URL, backup directory, Git deploy key и SSH known_hosts зафиксированы host-side helper-ом и не управляются из Telegram.

## API

Agent предоставляет только:

~~~text
GET  /v1/status
GET  /v1/releases/latest
GET  /v1/preflight/<vX.Y.Z>
GET  /v1/history
GET  /v1/operations/<operation_id>
POST /v1/deploy
~~~

POST body имеет ровно три поля: `operation_id`, `release`, `allow_downgrade`. Других mutation endpoints нет.

## Persistent operation journal

Каждый deployment имеет stable `operation_id`. Состояния:

~~~text
queued
preflight
backup
building
deploying
verifying
success
failed
unknown
~~~

`operation_id` сохраняется в bot `job_runs` до POST к Deploy Agent.

Если POST response потерян, bot не отправляет mutation повторно: выполняется только `GET /v1/operations/<operation_id>`. Если результат нельзя доказать, job становится `unknown`.

Если bot container пересоздан во время update, новый process сначала выполняет мгновенный read-only lookup незавершённых `bot.update` jobs до generic stale cleanup. После запуска health endpoint выполняется фоновое ожидание terminal state. Это не блокирует health check самого `deploy-release.sh`.

Если Deploy Agent был перезапущен во время mutation, он также не replay-ит deployment. Он проверяет текущий production status read-only: exact healthy target может быть доказан как `success`, иначе результат становится `unknown`.

## Published release validation

Перед deployment root helper проверяет strict tag `vX.Y.Z`, выполняет authenticated Git fetch через отдельный read-only deploy key и pinned SSH `known_hosts`, убеждается что tag существует и содержится в `origin/main`, проверяет exact `APP_VERSION`, clean tracked working tree, running container и текущие Health / DB / 3x-ui connectivity.

Сам deployment выполняет существующий `scripts/deploy-release.sh`.

## Owner-only UI

~~~text
/admin
  -> System
     -> Bot Updates
~~~

Экран показывает current release, latest published release, Deploy Agent version, Health / DB / 3x-ui status, active operation и update history.

Для latest release доступен preflight. Owner также может вручную ввести точный published tag `vX.Y.Z`; это нужно в том числе для контролируемого downgrade.

## Upgrade confirmation

Upgrade не запускается автоматически при обнаружении нового release. Owner выбирает release, выполняет read-only preflight, видит target SHA и release notes и только затем явно запускает update.

## Downgrade

Downgrade никогда не выполняется автоматически. Если preflight показывает downgrade, Owner обязан отправить точную фразу:

~~~text
DOWNGRADE vX.Y.Z
~~~

После фразы preflight выполняется повторно. Только если target всё ещё является downgrade и валиден, POST отправляется с `allow_downgrade=true`.

## Установка Deploy Agent на Master

Первый release `v4.19.0` устанавливается обычным ручным способом. Self-update control plane начинает использоваться только после этого.

Из checkout `v4.19.0`:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
sudo ./scripts/install-deploy-agent.sh
~~~

Installer создаёт system user `3xui-deploy`, устанавливает agent и root-owned helper, копирует существующий read-only Git deploy key в `/etc/3xui-deploy-agent/deploy-key` mode `0600`, копирует SSH `known_hosts`, генерирует отдельный bearer token, создаёт journal, устанавливает exact sudoers rule и запускает `3xui-deploy-agent.service`. Token и Git key не печатаются.

По умолчанию installer берёт existing key из `/root/.ssh/3xui_bot_deploy` и `known_hosts` из той же директории. При нестандартном расположении source paths задаются только локально через `DEPLOY_AGENT_SOURCE_KEY` и `DEPLOY_AGENT_SOURCE_KNOWN_HOSTS` во время installer запуска.

## Подключение bot container

Agent слушает только private Docker-host route:

~~~text
http://172.19.0.1:18184
~~~

После установки token нужно локально перенести из `/etc/3xui-deploy-agent/token` в production `.env`:

~~~env
DEPLOY_AGENT_URL=http://172.19.0.1:18184
DEPLOY_AGENT_TOKEN=<dedicated-agent-token>
~~~

Не копируй token в чат, Git, issue или Telegram message.

Безопасный локальный способ обновить `.env` без печати token:

~~~bash
sudo python3 - <<'PY'
from pathlib import Path

env_path = Path('/opt/3xui-bot/3xui-telegram-bot/.env')
token_path = Path('/etc/3xui-deploy-agent/token')
token = token_path.read_text(encoding='utf-8').strip()

lines = env_path.read_text(encoding='utf-8').splitlines()
updates = {
    'DEPLOY_AGENT_URL': 'http://172.19.0.1:18184',
    'DEPLOY_AGENT_TOKEN': token,
}
seen = set()
out = []
for line in lines:
    if '=' in line and not line.lstrip().startswith('#'):
        key = line.split('=', 1)[0].strip()
        if key in updates:
            out.append(f'{key}={updates[key]}')
            seen.add(key)
            continue
    out.append(line)
for key, value in updates.items():
    if key not in seen:
        out.append(f'{key}={value}')
env_path.write_text('\n'.join(out) + '\n', encoding='utf-8')
env_path.chmod(0o600)
PY
~~~

Затем recreate только bot service и проверь обычный status.

## Проверка agent

Host-side должны быть active/enabled `3xui-deploy-agent.service`. Token не выводить.

После подключения `.env` открой `/admin -> System -> Bot Updates`. Ожидается current release, доступный agent, latest published release, history и работающий preflight.

Для production acceptance `v4.19.0` допустим controlled same-release deployment `v4.19.0 -> v4.19.0`: он проверяет полный persistent operation/recreate/recovery path без изменения версии. После него exact tag/SHA, health, DB и 3x-ui connectivity должны остаться зелёными.

## Manual break-glass

Self-update не заменяет ручной путь:

~~~bash
./scripts/deploy-release.sh vX.Y.Z
~~~

Если Deploy Agent недоступен или operation имеет `unknown`, оператор сначала диагностирует состояние read-only. Нельзя запускать update повторно только потому, что предыдущий ответ потерян.

## Что Agent сознательно не умеет

Deploy Agent не предоставляет shell/terminal/exec, arbitrary Git checkout/SHA/ref, arbitrary Docker/Compose command, cleanup/prune, arbitrary environment override, arbitrary filesystem API, package manager, firewall, reboot/shutdown, управление x-ui/Xray, автоматический rollback, автоматический mutation retry или автоматический deploy нового release.
