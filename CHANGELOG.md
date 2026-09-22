# Changelog

Все заметные изменения проекта фиксируются здесь. История до перехода на Git восстановлена по сохранённым релизным архивам. Для исторических версий формулировки сокращены и приведены к единому виду.

> Первый архив проекта не имел номера версии. При миграции в Git он помечен тегом `v1.0.0` как историческая отправная точка.

## v4.9.0 - Versions & Updates
- Added version dashboard and Master/Node shortcuts.
- Added explicit stable-channel panel updates and exact Xray version selection.
- Fresh validated backup, expiring single-use confirmation, durable target lockout and post-update verification.
- Panel updater run IDs are checked; lost responses never trigger automatic retries.
- Read-only views, Admin+ installation and explicit Owner acknowledgement for uncertain outcomes.
- Reused existing audit/job tables; no SQLite schema changes.
- Centralized APP_VERSION and corrected stale backup manifest versions.
- Added automated API/workflow/integration tests and read-only pull-request CI.

## v4.8.0 — Single Message Admin UI
- Админ-панель переведена на один обновляемый Telegram-message.
- Inline-навигация, Back/Refresh/Confirm больше не засоряют чат новыми сообщениями.
- FSM-формы возвращают пользователя в исходную панель; введённые служебные сообщения по возможности удаляются.
- Файлы, alerts и внешние события намеренно остаются отдельными сообщениями.

## v4.7.0 — Disaster Recovery / Restore
- Добавлен безопасный DR/Restore workflow для `bot.sqlite3`, Master 3x-ui DB и node DB.
- Добавлены preflight/dry-run, SQLite `quick_check`, rescue copies и двойное подтверждение.
- Восстановление bot DB выполняется через bootstrap до запуска основного процесса.
- `bot.env` и nginx-конфигурация доступны для извлечения, но не восстанавливаются автоматически.

## v4.6.0 — Logs + Alerts
- Централизованный просмотр bot, 3x-ui, Xray, AmneziaWG и nginx логов.
- Фильтры ALL/WARN+/ERROR и лимиты последних строк.
- Добавлены alert rules: Master/Xray/node offline, failed jobs, disk threshold, stale backup.
- Добавлены recovery-уведомления, cooldown и маскирование чувствительных данных в логах.

## v4.5.0 — Provisioning Engine
- Связана цепочка `Plan → Server Group → Nodes → Inbounds → User`.
- Добавлена provisioning-политика Server Group: все managed inbound'ы или выбранный набор.
- Добавлены per-user preview/drift, safe reconcile и strict reconcile.
- Добавлена массовая policy-aware reconciliation пользователей.
- Default Plan может управлять `/create`, сохраняя legacy trial-режим как fallback.

## v4.4.0 — Advanced Nodes
- Расширена карточка ноды: состояние, версии, ресурсы, latency, inbound'ы и online.
- Добавлены test/recheck, maintenance mode, rename, per-node backup и restart Xray.
- Добавлены штатное обновление 3x-ui и безопасное удаление ноды с проверками.

## v4.3.0 — Advanced Inbound Management
- Добавлены карточки inbound'ов и список клиентов.
- Добавлены безопасное редактирование, enable/disable, sync, reset traffic и clone.
- Добавлены inbound templates и deployment шаблонов на Master/ноды.
- Критичные приватные ключи не выводятся в Telegram UI.

## v4.2.0 — Advanced User Management
- Добавлено расширенное управление пользователем: expiry, traffic, IP limit, Plan, Server Group и note.
- Добавлены управление пользовательскими inbound'ами, reset traffic и rotation subscription ID.
- Добавлены массовые действия над пользователями.
- Добавлена таблица `user_profiles` без изменения существующей `users`.

## v4.1.0 — Business/Admin modules
- Добавлены Payments как внутренний ledger и Promo Codes.
- Добавлены Administrators с ролями Owner / Administrator / Support / Read-only.
- `ADMIN_TELEGRAM_IDS` остаются защищёнными Owner.
- Добавлены Safe Runtime Settings для trial-параметров и default currency.

## v4.0.0 — Monitoring, Jobs, Audit
- Добавлены Monitoring → Traffic и Online.
- Добавлены System → Jobs и Audit Log.
- Добавлен общий lock для backup jobs и журналирование административных действий.
- Dashboard расширен monitoring/system сводкой.

## v3.9.0 — Plans, Server Groups, Hosts
- Добавлены Plans с длительностью, трафиком, IP limit, ценой и статусом.
- Добавлены Server Groups и привязка серверов.
- Добавлен реестр Hosts и обнаружение текущих host-адресов.

## v3.8.0 — Production Admin UI foundation
- Админка реорганизована в Dashboard / Users / Subscriptions / Payments / Plans / Promo Codes / Infrastructure / Monitoring / System.
- Существующая бизнес-логика сохранена, изменён в основном навигационный слой.
- Добавлены рабочие Dashboard и отдельный раздел Subscriptions.

## v3.7.2 — Add Nodes from Telegram
- Добавлен мастер `➕ Добавить ноду` через Telegram.
- Добавлены test connection, TLS verify mode и вызовы native 3x-ui node API.
- Текст пустого списка нод сделан нейтральным.

## v3.7.1 — Master card
- Master отображается первой полноценной карточкой в разделе Nodes.
- Master учитывается в server/online counters и открывается как отдельная карточка состояния.

## v3.7.0 — Multi-node foundation
- Добавлена интеграция с native 3x-ui multi-node API.
- Добавлены отображение нод в System Health и подготовка node DB backup.
- Заложена основа для первой внешней ноды.

## v3.6.0 — Backups
- Добавлен раздел Backups в `/admin`.
- Добавлены ручные и ежедневные backups с retention.
- Полный архив включает bot DB, 3x-ui DB, env, compose и nginx при доступности.
- Добавлен `.dockerignore`, чтобы runtime-секреты/данные не попадали в image build context.

## v3.5.5 — Health + bounded Docker logs
- Добавлен `Состояние сервера` в админку.
- Добавлены disk/RAM/uptime и health checks.
- Docker `json-file` logs ограничены `10m × 3`.

## v3.5.4 — Shadowrocket XHTTP compatibility
- Для Shadowrocket в raw subscription удаляется `fp` только у `VLESS + XHTTP + Reality`.
- INCY и TCP Reality сохраняют прежнее поведение.
- Клиент определяется по User-Agent.

## v3.5.3 — VLESS XTLS flow synchronization
- Добавлена настройка `VLESS_FLOW` и синхронизация flow для VLESS-клиентов там, где это применимо.

## v3.5.2 — Native AmneziaWG page rendering
- HTML-режим compatibility proxy больше не переписывает `vpn://` внутри страницы 3x-ui.
- Raw subscription продолжает преобразование в `amneziawg://` для совместимых клиентов.

## v3.5.1 — 3x-ui page assets
- Исправлено проксирование assets встроенной subscription-страницы 3x-ui через `/compat/`.

## v3.5 — Default 3x-ui page + compatible raw subscription
- Browser-mode сохраняет штатную красивую HTML-страницу 3x-ui.
- Raw-mode отдаёт клиентскую subscription с compatibility-преобразованиями.

## v3.4 — INCY-compatible AmneziaWG subscription proxy
- Добавлен compatibility proxy над native 3x-ui subscription.
- В raw subscription `vpn://` преобразуется в `amneziawg://`.

## v3.3 — Global inbound sync
- Добавлена массовая синхронизация пользователей с разрешёнными inbound'ами.

## v3.2 — Per-user inbound synchronization
- Добавлена синхронизация разрешённых inbound'ов для отдельного пользователя.

## v3.1 — Username-based client names
- 3x-ui client email/remark для новых пользователей формируется из Telegram username с fallback на Telegram ID.

## v3 — Telegram admin panel
- Добавлена Telegram-админка: пользователи, статистика, карточка пользователя, продление, enable/disable и delete.
- SQLite остаётся linkage/business DB, 3x-ui — источником proxy credentials и runtime state.

## v2 — Single-node filtering/API tuning
- Добавлены фильтры разрешённых портов/протоколов и исключения service/API inbound.
- Уточнена работа single-node provisioning через 3x-ui API.

## v1.0.0 — Initial historical snapshot
- Первый сохранённый single-node test bot.
- Базовые `/start`, `/inbounds`, `/create`, `/subscription`.
- Python + aiogram + aiohttp + aiosqlite + Docker Compose.
