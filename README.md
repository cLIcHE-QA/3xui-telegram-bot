# Telegram-бот для 3x-ui v4.25.2

Административный Telegram Control Plane для 3x-ui. Текущая production-линия проекта — **v4.x Admin Control Plane**; полноценный client-facing Client Portal запланирован отдельно для v5.x.

Источник версии приложения: `version.py`. История изменений: [CHANGELOG.md](CHANGELOG.md). Граница v4/v5 и оставшиеся freeze-задачи: [Product Roadmap](docs/ROADMAP.md).

> README — актуальная карта проекта и точка входа в runbook'и. Исторические upgrade-инструкции и release-by-release описание не дублируются здесь: для них используются `CHANGELOG.md`, GitHub Releases и специализированные документы в `docs/`.

## Текущий production path

### Новая установка

Каноническое руководство для чистого Master VPS и direct nodes:

**[Admin Setup — Master + direct nodes](docs/ADMIN_SETUP.md)**

Оно является источником истины для:

- Master 3x-ui и bot container;
- `.env`, Docker/network/firewall и TLS;
- direct-node onboarding;
- dedicated Direct Admin credentials;
- Host Control Agent;
- Extended direct-node backup;
- Safe Bot Self-Update Deploy Agent;
- обязательных preflight/post-deploy проверок.

README не заменяет этот runbook и не содержит отдельной сокращённой последовательности установки.

### Обновление существующего production

Release, GitHub tag и production deployment — отдельные стадии. Канонический контракт публикации и проверки релиза:

**[Release workflow](docs/RELEASES.md)**

Для ручного deployment используется только опубликованный release tag:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
./scripts/deploy-release.sh vX.Y.Z
./scripts/deploy-release.sh --status
~~~

Не используй старые version-specific команды из истории проекта как инструкцию для текущего production. После deployment выполняется targeted smoke именно изменённой области и повторная базовая health/status-проверка.

Если на Master установлен restricted Deploy Agent, Owner может использовать:

`/admin → Система → Обновления бота`

Полный safety/acceptance contract:

**[Safe Bot Self-Update](docs/BOT_SELF_UPDATE.md)**

Deploy Agent принимает только опубликованные `vX.Y.Z` tags и не предоставляет Telegram-боту Docker socket, host shell или Git deploy key.

### Восстановление после потери Master VPS

Канонический disaster-recovery runbook:

**[VPS Recovery](docs/VPS_RECOVERY.md)**

Bootstrap helper намеренно не является универсальным installer инфраструктуры. ОС, Docker, Master 3x-ui, DNS/TLS/firewall и другие host-level слои подготавливаются отдельно.

### Direct nodes и Host Control

Рекомендуемый onboarding новой direct node:

**[Node Onboarding](docs/NODE_ONBOARDING.md)**

Host-level управление `x-ui.service`:

- [Host Control Agent — security contract](docs/HOST_CONTROL_AGENT.md)
- [Host Control Deploy](docs/HOST_CONTROL_DEPLOY.md)
- [Host Control Rollout](docs/HOST_CONTROL_ROLLOUT.md)
- [Fleet Operations](docs/FLEET_OPERATIONS.md)

Для direct node используются независимые privilege domains:

1. node-sync token: Master 3x-ui → node;
2. dedicated admin-scope token: bot → direct 3x-ui API;
3. отдельный Host Control token.

Один token не переиспользуется между этими domains.

### Backup и off-site recovery

Full Backup включает recovery-ориентированные данные Master и, при настроенных targets, direct-node snapshots.

Encrypted off-site replication и recovery:

**[Off-site Backup](docs/OFFSITE_BACKUP.md)**

Off-site transport выключен по умолчанию. Full Backup содержит secrets; Telegram и GitHub не являются backup storage.

## Архитектура v4.x

После cleanup-декомпозиции entrypoint и runtime разделены:

~~~text
bot.py
└─ минимальный executable shim
   └─ app_runtime.main()

app_runtime.py
├─ startup / recovery order
├─ Subscription Proxy lifecycle
├─ background backup + alerts
├─ Router registration
├─ Telegram polling
└─ graceful task cancellation

client_access.py
└─ /start, /inbounds, /create, /subscription

admin_shell.py
└─ /admin, Обзор, top-level navigation и compatibility redirects

domain routers
├─ advanced_users.py
├─ user_groups_admin.py
├─ advanced_nodes.py
├─ inbound_admin.py
├─ catalog_admin.py
├─ business_admin.py
├─ admin_observability.py
├─ system_admin.py
├─ storage_admin.py
├─ versions_updates.py
├─ bot_updates.py
├─ host_control_ui.py
├─ fleet_operations.py
├─ website_monitoring.py
├─ website_monitoring_runtime.py
├─ website_monitoring_admin.py
├─ website_diagnostics.py
├─ website_diagnostics_admin.py
└─ disaster_recovery.py
~~~

`bot.py` сохраняется как стабильный executable path, в том числе для `restore_bootstrap.py`, но не владеет domain handlers или lifecycle implementation.

Линия `v4.25.x` завершается compatibility hotfix `v4.25.2`: `v4.25.1` уже закрывает User Management/HWID acceptance, а `v4.25.2` добавляет client-aware INCY Desktop filtering и диагностическую обработку 3x-ui HWID gate для Shadowrocket/других клиентов без ослабления per-device enforcement. Переход к `v4.26.0` допускается только после targeted production acceptance `v4.25.2`.

Линия `v4.24.x` реализована, опубликована и принята в production: `website_monitoring.py` содержит SQLite repository/state machine и SSRF-safe outbound boundary, `website_monitoring_runtime.py` — bounded scheduler/incident notifications, `website_monitoring_admin.py` — persistent monitoring UI, а `website_diagnostics.py` / `website_diagnostics_admin.py` — one-off DNS/WHOIS/HTTP/redirect/CMS/SEO/PageSpeed/Sitemap/URL-list/QR diagnostics. Production smoke `v4.24.0` выявил targeted findings WHOIS MSK, bounded Cheburcheck detail и public IPv6 literal validation; они закрыты в `v4.24.1`, после чего smoke/acceptance линии завершён.

### 3x-ui API contract

Native 3x-ui API используется через `xui.py` / `version_api.py`.

Текущий pinned compatibility contract:

- 3x-ui: `v3.8.5`;
- vendored OpenAPI: `contracts/3xui/v3.8.5/openapi.json`;
- используемый API surface: `contracts/3xui/contract.json`.

CI проверяет route/method, Bearer auth, request/response contract и source parity fail-closed.

Подробнее: **[3x-ui OpenAPI compatibility contract](docs/3XUI_OPENAPI_CONTRACT.md)**.

### User / Audience Groups

V4.22 добавляет отдельные `Группы пользователей` для сегментации будущего Client Portal:

- membership many-to-many хранится по стабильному `telegram_id`;
- группы и membership управляются из `/admin → Пользователи`;
- backend matcher поддерживает include/exclude, при этом exclude имеет приоритет;
- User Groups не связаны с Server Groups и не меняют Nodes, Inbounds, тариф или VPN-доступ.

`user_groups_admin.py` владеет административным UI, а `audience.py` — reusable matcher без Telegram-specific logic.

### SQLite

Локальное состояние хранится в SQLite. С v4.15 используется явный forward-only migration framework с persistent `schema_migrations` journal.

Подробнее: **[SQLite migrations](docs/SQLITE_MIGRATIONS.md)**.

## Основные security boundaries

Проект намеренно разделяет Telegram UI и privileged host operations.

- Bot container не получает Docker socket или generic host shell.
- Host Control Agent не является SSH gateway и принимает только фиксированный allowlist операций для `x-ui.service`.
- Xray restart, panel-process restart и host-level service restart — разные операции без fallback между privilege domains.
- Direct Admin, Host Control, panel token, Deploy Agent token и object-storage credentials не переиспользуются.
- Unknown admin callbacks должны fail closed через centralized privilege catalog.
- Interrupted state-changing Host Control/Fleet/Deploy mutations автоматически не replay'ятся.
- Backups, `.env`, API tokens, subscription IDs/URLs, private keys и enrollment contents нельзя публиковать в GitHub issues/PR/chat.

Общие правила: **[SECURITY.md](SECURITY.md)**.

## Subscription Compatibility Proxy

V4 сохраняет встроенный compatibility proxy для подписок, управляемых ботом.

Он:

- обслуживает `GET /compat/{sub_id}`;
- предоставляет `GET /healthz`;
- получает upstream subscription через `SUBSCRIPTION_URL_TEMPLATE`;
- проверяет, что `sub_id` принадлежит пользователю из локальной SQLite;
- для raw/machine subscription преобразует 3x-ui AmneziaWG `vpn://` в `amneziawg://`;
- сохраняет штатное HTML-представление 3x-ui;
- проксирует assets встроенной subscription page через `/compat/assets/`;
- применяет ограниченную Shadowrocket compatibility только к соответствующим VLESS/XHTTP/Reality links.

Основные переменные:

~~~env
SUBSCRIPTION_URL_TEMPLATE=https://sub.example.com:2096/sub/{sub_id}
COMPAT_SUBSCRIPTION_URL_TEMPLATE=https://sub.example.com/compat/{sub_id}

SUBSCRIPTION_PROXY_HOST=0.0.0.0
SUBSCRIPTION_PROXY_PORT=8080
~~~

Если `COMPAT_SUBSCRIPTION_URL_TEMPLATE` пуст, бот продолжает выдавать исходный URL 3x-ui.

Docker Compose публикует proxy только на loopback Master:

~~~text
127.0.0.1:18080 -> container:8080
~~~

Пример reverse-proxy route:

~~~nginx
location /compat/ {
    proxy_pass http://127.0.0.1:18080;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
~~~

Локальная health-проверка:

~~~bash
curl -fsS http://127.0.0.1:18080/healthz
~~~

Не публикуй реальный `sub_id` в issue/PR/chat.

## Telegram surfaces

Текущий v4 содержит два разных UI boundary.

Client-access compatibility flow:

- `/start`;
- `/inbounds`;
- `/create`;
- `/subscription`.

Admin Control Plane:

- `/admin` открывает корневую панель: Обзор / Пользователи / Подписки / Платежи / Тарифы / Промокоды / Инфраструктура / Мониторинг / Система;
- Пользователи: карточки пользователей / Группы пользователей / массовые действия / согласование доступа; Группы пользователей являются audience-сущностью и не заменяют Группы серверов;
- Инфраструктура: Ноды / Inbounds / Хосты / Операции с нодами / Группы серверов; Host Control открывается из карточки конкретного Master/direct node;
- Мониторинг: Трафик / В сети / Состояние системы / Проверка блокировок / Мониторинг сайтов / Журналы / Оповещения;
- Система: Обновления бота / Версии и обновления / Задания / Резервные копии / Журнал аудита / Администраторы / Настройки.

Наличие v4 client-access команд не означает, что v5 Client Portal уже реализован. Новый client-facing product flow должен сохранять отдельную authorization/navigation boundary от `/admin`.

## CI и regression gates

Основной CI выполняет:

~~~bash
python -m compileall -q .
python -m unittest discover -s tests -v
python3 scripts/check-3xui-openapi-contract.py
git diff --check
~~~

Дополнительно regression tests закрепляют:

- centralized RBAC catalog и fail-closed unknown callbacks;
- single ownership Router'ов после декомпозиции;
- Host Control / Deploy Agent startup recovery order;
- отсутствие automatic mutation replay;
- public-readiness contract: нейтральные deployment-примеры и актуальные русские UI-paths в README/runbook'ах;
- provisioning/user mutation ordering;
- backup/restore/off-site integrity semantics;
- release/Git workflow conventions.

## Карта документации

| Задача | Канонический документ |
|---|---|
| Установка Admin Control Plane | [docs/ADMIN_SETUP.md](docs/ADMIN_SETUP.md) |
| Release/tag/deployment contract | [docs/RELEASES.md](docs/RELEASES.md) |
| Git/PR/issue conventions | [docs/GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md) |
| Product roadmap | [docs/ROADMAP.md](docs/ROADMAP.md) |
| UI style | [docs/UI_STYLE.md](docs/UI_STYLE.md) |
| Direct-node onboarding | [docs/NODE_ONBOARDING.md](docs/NODE_ONBOARDING.md) |
| Host Control security | [docs/HOST_CONTROL_AGENT.md](docs/HOST_CONTROL_AGENT.md) |
| Host Control deployment | [docs/HOST_CONTROL_DEPLOY.md](docs/HOST_CONTROL_DEPLOY.md) |
| Host Control rollout | [docs/HOST_CONTROL_ROLLOUT.md](docs/HOST_CONTROL_ROLLOUT.md) |
| Fleet Operations | [docs/FLEET_OPERATIONS.md](docs/FLEET_OPERATIONS.md) |
| Bot Self-Update | [docs/BOT_SELF_UPDATE.md](docs/BOT_SELF_UPDATE.md) |
| Off-site Backup | [docs/OFFSITE_BACKUP.md](docs/OFFSITE_BACKUP.md) |
| VPS recovery | [docs/VPS_RECOVERY.md](docs/VPS_RECOVERY.md) |
| SQLite migrations | [docs/SQLITE_MIGRATIONS.md](docs/SQLITE_MIGRATIONS.md) |
| Cheburcheck integration | [docs/CHEBURCHECK.md](docs/CHEBURCHECK.md) |
| Cheburcheck deployment | [docs/CHEBURCHECK_DEPLOY.md](docs/CHEBURCHECK_DEPLOY.md) |
| 3x-ui OpenAPI contract | [docs/3XUI_OPENAPI_CONTRACT.md](docs/3XUI_OPENAPI_CONTRACT.md) |
| Third-party notices | [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) |

## Сторонние компоненты

Read-only проверка блокировок использует API open-source проекта [Cheburcheck](https://github.com/LowderPlay/cheburcheck). Интеграция проверена относительно pinned upstream commit `0bbd2be8ca4b8f9ded1407597654314fc2a900c6`. Авторские уведомления и условия BSD-3-Clause сохранены в [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Website monitoring и web diagnostics `v4.24.0` используют [PackBot](https://github.com/vladpak1/packbot) как reviewed behavior/reference implementation на revision `3c4a5bb29626f8b3e28056bd52cd94fdce9f3c1a`. Production runtime не встраивает PHP/MySQL/webhook stack PackBot; реализация нативная Python/aiogram/SQLite. MIT attribution и copyright сохранены в [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## История проекта

Release history не поддерживается второй копией внутри README.

Используй:

- **[CHANGELOG.md](CHANGELOG.md)** — канонический список изменений по версиям;
- GitHub Releases — опубликованные release notes и immutable tags;
- **[docs/RELEASES.md](docs/RELEASES.md)** — правила публикации и production acceptance.

Старые v2/v3/v4 upgrade-команды из исторических релизов не являются текущей процедурой deployment.
