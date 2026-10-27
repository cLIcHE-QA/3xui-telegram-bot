# Admin Setup: установка и настройка Admin Control Plane

**Каноническая точка входа для оператора.** Полные команды, переменные, preflight/postconditions и ручной fallback сохранены в [пошаговых процедурах Admin Setup](ADMIN_SETUP_PROCEDURES.md). Этот документ определяет **единственный порядок действий**, но не даёт разрешения менять production. Команды на VPS, Docker, firewall, SQLite и 3x-ui выполняются только в отдельно согласованной операции.

**Текущий Published/Deployed/Accepted status:** [каноническая сводка Roadmap](ROADMAP.md) — единственный источник актуальной публикации, deployment (с маркировкой источника), scoped acceptance и решений по Issues. Guide ориентирован на release v5.0.0-rc.25 (текущий Published). Развёрнутая версия по отчёту оператора — `v5.0.0-rc.18.10`. Перед использованием обязательно сверять фактический статус по [Roadmap](ROADMAP.md) и [датированному HWID acceptance audit](audits/2026-10-22-v5-rc18-10-operator-targeted-hwid-acceptance.md). Принятые оператором 23/23 адресных HWID UI-проверок не означают полного v5 acceptance: G-11 PARTIAL/NO-GO, public rollout BLOCKED. Независимый VPS read-back остаётся PENDING; никакие production mutations не разрешены этим документом.

> **Релиз `v5.0.0-rc.25`:** опубликован в GitHub и закреплён неизменяемым тегом на `1c0854c9b416a2d0f2ccbe9083d62d88794307ed`; deployed только `v5.0.0-rc.18.10` по отчёту оператора, новый deployment не подтверждён. Additive schema17 требует cumulative upgrade/recovery review перед отдельно разрешённым deployment; pilot/allowlist сохраняются.

**Исторический checkpoint `rc.18.1` (не текущий статус):** оператор ранее сообщил deployed `rc.18` P0–P2/F1–F3 и scoped D1–D8/S1–S4 PASS, но независимый VPS/provider read-back отсутствует, X2 и destructive postcondition provenance PENDING. Новая версия `rc.18.1` опубликована и развернута по отчёту оператора; targeted UI A4/A5 operator-reported FAIL; реальный DELETE требует отдельного разрешения. Targeted U8/S/R 20/20 operator-reported scoped PASS на `rc.17`, #760/#470 CLOSED/completed, #437/#707 и G-11 PARTIAL/NO-GO, public rollout BLOCKED. [Client Setup](CLIENT_SETUP.md), [release contract](RELEASES.md).

> **Версия исходного кода:** `APP_VERSION=v5.0.0-rc.25`, Published prerelease по [Roadmap](ROADMAP.md) и [publication audit](audits/2026-10-27-rc25-publication-checkpoint.md). Source-only очередь #948/schema17 без runtime observation/UI/worker/transport wiring или отправок; новых env/портов/credentials нет, OFF/DENY_ALL. Deployed rc.18.10 operator-reported; cumulative upgrade/recovery от фактически deployed15 и отдельное разрешение перед установкой обязательны.

## Source-only кампании #947: source schema v16

Foundation additive migration v16 (#947) впервые опубликована в rc.24 и сохранена в rc.25/schema17; предыдущий rc.23 сохраняет schema15. Она создаёт пустые draft/revision/private-contact таблицы, без backfill, runtime observation, worker, UI, transport или отправок; новых env/портов/credentials нет. [Контракт](SERVICE_CAMPAIGNS.md), [SQL migration rules](SQLITE_MIGRATIONS.md). Наличие Telegram ID в старой users/import БД не разрешает рассылку и не доказывает private chat/consent.

Перед будущим отдельно разрешённым deployment tag, содержащего v16, проверить cumulative upgrade от фактически deployed tag и сохранить проверенную pre-migration recovery copy по штатному backup flow. После v16 downgrade на rc.23/каталог v15 без совместимого restore блокируется. Не запускать migration отдельно ради разработки и не включать collection/send автоматически; parent #874, policy #501 и pilot approval остаются отдельно.

## Source-очередь #948 в main: без операционного включения

Source schema17 в main через #956 добавляет пустой queue/attempt/control ledger и generation только для существующих trusted private proofs v16. Published rc.25 содержит schema17; VPS не обновлён. Старый rc.24/schema16 immutable. Worker и transport не зарегистрированы в runtime, новых env/портов/credentials нет; реальное admission DENY_ALL. Не использовать test policy/transport как разрешение на коммуникацию — #501 и parent #874 сохраняют собственные policy/privacy/abuse/UI/pilot gates.

Образ проверяет доступность IANA timezone data под UID10001 при сборке, без нового package или смены привилегий. Отсутствие TZ data означает отказ, fallback к локальному TZ нет. Перед поздним отдельно разрешённым deployment RC с schema17 проверить cumulative путь от фактически deployed15 и recovery copy; старый код16 после upgrade блокируется. Публикация RC не применяет migration и не включает collection/send. [Канонический contract](SERVICE_CAMPAIGNS.md), [SQL migrations](SQLITE_MIGRATIONS.md).

## Перед началом: границы и безопасность

**HTTPS handoff #885 (Published rc.21):** использует тот же compatibility proxy и `/compat/` ingress, без нового порта/mount/env. Перед будущим разрешённым deployment проверь, что `/compat/open/` покрыт существующим `access_log off`/sanitized policy, proxy/CDN не кэширует no-store HTML и не удаляет hash-based CSP/no-referrer. Ticket — одноразовый 90-секундный bearer-like URL из private-owner карточки; общий in-memory предел 256, только тот же процесс бота/proxy, без multi-worker/multi-host guarantees. Copy/QR — fallback. Это не инструкция включить новый listener или проводить live smoke сейчас; #885 Published в rc.21; собственный deployment/device acceptance PENDING.

- Не хранить реальные secrets, enrollment, backup, private IDs или hostnames в Git, PR, Telegram и shared logs; Owner credentials, node-sync, direct-admin, Host Control, Deploy Agent — **разные** privilege domains. Telegram-бот не получает Docker socket, SSH/general shell или произвольный systemd executor.
- Только проверенный HTTPS/TLS, ограниченные IP/port/firewall правила. Cloudflare WARP **не prerequisite**; его подключение требует отдельного изменения.
- До любого обновления нужен совместимый backup; миграции SQLite forward-only, `running/failed/unknown` и непрочитанный postcondition означают **STOP**, без автоматического replay. Не удалять journal и не обходить mismatch.
- Для controlled pilot запрещены public launch и реальные новые payments без отдельного acceptance. Экстренные переключатели клиента описаны в [Client Setup](CLIENT_SETUP.md), они не должны отключать `/admin` и не отменяют обработку ранее подтверждённых платежей.

## Маршрут первоначальной установки

1. **Prerequisites:** подготовить Ubuntu/Debian, Docker/Compose, Python venv, DNS/TLS, firewall, Telegram Owner identity; проверить уникальность токенов. [Шаг 0](ADMIN_SETUP_PROCEDURES.md#0-что-понадобится).
2. **Master и direct-node 3x-ui:** установить native `x-ui.service`, проверить active/HTTPS и panel API отдельно от клиентского data-plane. Для текущего `main` **Pinned supported 3x-ui: `v3.10.2`**; сверить [канонический OpenAPI contract](3XUI_OPENAPI_CONTRACT.md), а фактическую версию панели и совместимость — read-only preflight. [Шаг 1](ADMIN_SETUP_PROCEDURES.md#1-сначала-подготовь-3x-ui-на-всех-vps).
3. **Подготовка Master и опубликованного bot tag:** системные пакеты, read-only git clone, проверить immutable tag и `APP_VERSION`; не переключать VPS на `main`. [Шаги 2–3](ADMIN_SETUP_PROCEDURES.md#2-базовая-подготовка-master-vps).
4. **Admin venv / `.env` / optional services:** mode `0600`, `BOT_TOKEN`, `PANEL_API_TOKEN`, `VERIFY_TLS=true`, `ADMIN_TELEGRAM_IDS`; checkout/payment webhooks и offsite target по умолчанию выключены. [Шаги 4–5](ADMIN_SETUP_PROCEDURES.md#4-создай-local-admin-venv).
5. **Backup paths / ACL / network:** проверить реальные host dirs, backup source, UID/GID 10001, `no-new-privileges`, Docker subnet и firewall до запуска. [Шаг 5](ADMIN_SETUP_PROCEDURES.md#5-настрой-env-бота).
6. **Первый старт:** `docker compose config --quiet`, запуск только после approval, проверки `/healthz`, `./scripts/deploy-release.sh --status`, RestartCount=0, DB/3x-ui connectivity, Owner `/admin`. [Шаги 6–7](ADMIN_SETUP_PROCEDURES.md#6-firewall-master-для-panel-access-из-bot-container).
7. **Master Host Control:** отдельный restricted Agent с localhost listener, приватным bridge proxy и защищённым enrollment; сначала `--check-only`, после только разрешённый импорт, удаление временных секретов после подтверждения. [Шаг 8](ADMIN_SETUP_PROCEDURES.md#8-host-control-для-master).
8. **Deploy Agent (optional):** отдельный system user, restricted operations, собственные токены и immutable published tags, никаких Telegram shell args. [Шаг 8A](ADMIN_SETUP_PROCEDURES.md#8a-safe-bot-self-update-deploy-agent-на-master).
9. **Direct node:** подготовить 3 privilege domains, verified TLS Host Control, локальный nginx source, три enrollment-файла, затем guided bind **preflight → отдельно разрешённый `--apply`**. При неопределённости — read-only сверка, не повтор операции. [Шаги 9–16](ADMIN_SETUP_PROCEDURES.md#9-подготовь-direct-node); [manual fallback](ADMIN_SETUP_PROCEDURES.md#14a-manual-fallback-создай-node-sync-enrollment-на-master).
10. **Readiness и backup:** проверка node_id binding, Agent running, bounded benign Host Control, complete snapshot с SHA-256, Full Backup и защищённый recovery export. При `missing`/degraded не объявлять readiness. [Шаги 17–20](ADMIN_SETUP_PROCEDURES.md#17-readiness-direct-node).
11. **Завершение:** Master `--status`, проверить health, удалить только временные enrollment, повторять с уникальными identity для следующей node. [Шаги 21–23](ADMIN_SETUP_PROCEDURES.md#21-финальный-health-check-master).
12. **Обновления и recovery:** использовать опубликованный tag через deploy helper, pre-migration backup, SQLite `schema_migrations`, `PRAGMA quick_check`, целевой smoke; downgrade невозможен одним checkout. [Шаги 24–27](ADMIN_SETUP_PROCEDURES.md#24-обновления-после-первоначальной-установки); [SQLite migrations](SQLITE_MIGRATIONS.md), [VPS recovery](VPS_RECOVERY.md).

## Definition of Done и troubleshooting

Узел вводится в эксплуатацию только с подтверждённым stable `node_id`, Direct API online, Host Control running, verified TLS, complete node snapshot и Full Backup, green Master health. Никаких разрушительных Stop/Restart/Restore smoke без отдельного разрешения. [Подробные критерии](ADMIN_SETUP_PROCEDURES.md#27-definition-of-done-новой-node) и [диагностика](ADMIN_SETUP_PROCEDURES.md#26-типичные-ошибки).

## Дополнительные операции (не часть установки)

- Ручной тариф, commerce preflight, `manual_entitlements.in_flight/unknown`, независимый 3x-ui read-back и запрет replay: [отдельная процедура Admin](ADMIN_SETUP_PROCEDURES.md#28-ручное-назначение-тарифа-через-admin-отдельный-operational-flow).
- Заказы Stars `/admin → Платежи → Telegram Stars → 📦 Заказы Stars`: read-only `commerce_orders` без требования существующего Payment, с заказом/платежом/entitlement, пагинацией и fail-closed RBAC. `created/awaiting_payment` без оплаты — не ошибка. Никаких invoice retry/refund/provider mutations, post-deploy scoped UI/RBAC/no-mutation smoke на `rc.17` operator-reported PASS; S3/S6 проверены offline fixture тестами без новых production-платежей, #470 CLOSED/completed; [UI contract](UI_STYLE.md).
- Справочник возвратов `/admin → Платежи → 📖 Политика возвратов`: read-only раздел для Support/Admin, условия только по подтверждённой публичной редакции § 9 из [общего versioned source](legal-publication.json). До публикации #707 экран показывает отсутствие актуальной редакции и эскалирует Owner; никаких Stars refund, смены статуса платежа или 3x-ui действий. Факт Published/Deployed/Accepted проверять только по [Roadmap](ROADMAP.md); публикация бота не публикует юридический § 9 по #707; [UI contract](UI_STYLE.md).
- Сброс локальной клиентской сессии, Shadowrocket/Streisand и HWID: [UI/клиентский контракт](UI_STYLE.md), [Client Setup](CLIENT_SETUP.md).
- QA-проверка доставки Telegram: исторический scoped workflow в [исходной версии Admin Setup](https://github.com/cLIcHE-QA/3xui-telegram-bot/blob/1a5a85d1cf154979473464b0305a1fc4acf75a40/docs/ADMIN_SETUP.md#изолированная-проверка-доставки-telegram-352-только-qa-бот). Никаких реальных Telegram сообщений в рамках установки.
- Профильные руководства: [Host Control rollout](HOST_CONTROL_ROLLOUT.md), [Node onboarding](NODE_ONBOARDING.md), [Offsite Backup](OFFSITE_BACKUP.md) и [Safe Bot Self-Update](BOT_SELF_UPDATE.md).

## Исторические checkpoints (не текущий status)

Все датированные отчёты `rc.6`, `rc.9`, `rc.16.1`, `rc.16.2`, #705/#752 и прошлые `OPEN/PENDING` сохранены в [immutable snapshot исходного Admin Setup](https://github.com/cLIcHE-QA/3xui-telegram-bot/blob/1a5a85d1cf154979473464b0305a1fc4acf75a40/docs/ADMIN_SETUP.md) и [датированных аудитах](audits/). Исторические факты не являются текущей приёмкой: проверяйте [Roadmap](ROADMAP.md).


## Source-компоненты #949: подключения ещё нет

Owner UI/private observer/one-shot Bot API adapters описаны в [SERVICE_CAMPAIGNS](SERVICE_CAMPAIGNS.md). Они не подключены к app_runtime/dispatcher/client guards/menu; новых env/портов/credentials нет, schema17 прежняя. Source factory всегда policy=None/DENY_ALL, редактор OFF; включение boolean редактора не даёт прав на sends/collection. Не устанавливать fake policy, не регистрировать router и не заменять shared bot session ради проверки.

Runtime integration BLOCKED до решения #501/category/recipient/defaults и permission-abuse/privacy/retention/allowlist review. После них нужен отдельный reviewed integration PR с no-retry session provenance, stop/disable/recovery checks, затем отдельно разрешённые deployment/pilot. В current autonomous scope только source/fake tests; реальные Telegram identities/доступы/команды VPS сейчас не требуются. Cumulative migrations/recovery от deployed15 остаются отдельным поздним gate.
