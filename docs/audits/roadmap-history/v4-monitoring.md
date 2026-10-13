
**Статус: ✅ Выполнено и принято в production в `v4.20.10`.**

Production smoke `v4.20.9` подтвердил корректное отображение на мобильном клиенте, но Telegram Desktop сохраняет различия ширины bubble/inline keyboard для одинакового markup после message edit. Бот не управляет шириной InlineKeyboardMarkup, поэтому follow-up не пытается искусственно растягивать bubble и вместо этого фиксирует более компактную двухколоночную структуру.

Целевая структура карточки Inbound:

1. `👥 Клиенты | ✏️ Изменить`
2. `🔄 Синхронизировать клиентов | ♻️ Сбросить трафик`
3. `📋 Клонировать | 🧩 Сохранить шаблон`
4. `⛔ Отключить | 🗑 Удалить` (для выключенного Inbound — `✅ Включить | 🗑 Удалить`)
5. `⬅ Inbounds`

Confirmation screen удаления сохраняет полное `Удалить Inbound` и отдельное явное подтверждение; callback identifiers, deletion safety contract, SQLite schema, storage/persistence semantics и provisioning behavior не меняются.

Приёмка в production `v4.20.10` закрыт: release развернут в production, и оператор завершил targeted smoke после обновления бота. Компактная пятистрочная клавиатура карточки Inbound принята; проверены desktop/mobile presentation, короткая кнопка `🗑 Удалить` в карточке и сохранение полного `Удалить Inbound` на confirmation screen. Delete confirmation guardrail, callback identifiers, SQLite schema, storage/persistence semantics, provisioning и mutation behavior не менялись.

##### Редактируемое имя пользователя

**Статус: ✅ Выполнено и принято в production в `v4.21.0`.**

Цель — добавить оператору и будущему Client Portal человекочитаемое имя пользователя, не смешивая presentation identity с технической identity клиента 3x-ui.

Контракт:

- `email` текущей записи пользователя остаётся machine identity, используемой 3x-ui/provisioning/traffic/update paths, и не переименовывается ради UI;
- отдельное optional `display_name` хранится в профиле пользователя через новую versioned SQLite migration;
- пустое `display_name` означает fallback на текущий `email`, поэтому существующие пользователи не требуют ручной миграции данных;
- расширенная карточка получает действие `✏️ Имя` с обычным FSM/Cancel/Back contract;
- имя валидируется по длине и управляющим символам, нормализуется перед сохранением и не используется как callback/database identity;
- карточки/списки, где это улучшает UX, показывают display name с техническим email как вторичную информацию или fallback;
- изменение/очистка имени записывается в audit;
- provisioning, subscription identity, `telegram_id`, `sub_id` и 3x-ui email не меняются как побочный эффект;
- regression pack проверяет migration upgrade, fallback, edit/clear flow, RBAC и отсутствие использования display name в machine bindings.

Приёмка в production `v4.21.0` закрыт: release развернут через Safe Bot Self-Update, bot штатно запустился с новой SQLite schema v2, и оператор завершил targeted smoke display-name flow. Подтверждены установка отображаемого имени, его явная очистка с возвратом fallback на email и отсутствие наблюдаемых regressions в пользовательской карточке/подписке. Machine identity (`email`, `telegram_id`, `sub_id`, 3x-ui client identity) по contract и regression coverage не изменяется; production smoke не выявил побочных изменений.

##### v4.21.1 — согласованность отображаемого имени и времени МСК

**Статус: ✅ Production smoke выполнен для `v4.21.1`; найденные runtime/UI follow-up закрыты и приняты в `v4.21.2`.**

Patch закрывает два post-acceptance presentation findings `v4.21.0` без изменения product/storage/security boundaries:

- display name используется как основной operator-facing label во всех соседних user surfaces, при этом email остаётся технической identity и fallback;
- абсолютные Telegram Admin timestamps отображаются в MSK (UTC+3), а machine timestamps и `BACKUP_HOUR_UTC` сохраняют UTC/epoch semantics;
- date-only operator input `YYYY-MM-DD` для user/promo expiry интерпретируется как `23:59:59 MSK`;
- SQLite schema, 3x-ui/OpenAPI, provisioning, subscription identity, Host Control/Deploy Agent и mutation semantics не меняются.

Приёмка в production после deployment должен подтвердить:

- display name в `Пользователи` и `Подписки`, а также на нескольких соседних user surfaces;
- fallback на email после очистки display name;
- MSK timestamps на operator-facing экранах;
- отсутствие изменений email / Telegram ID / `sub_id` / VPN access;
- базовый health/status после обновления.

##### v4.21.2 — исправление отображения DR и журнала

**Статус: ✅ Выполнено и принято в production в `v4.21.2`.**

Production smoke `v4.21.1` подтвердил display name в `Подписки` и operator-facing MSK presentation. При дальнейшей проверке найдены два отдельных runtime/UI finding:

- Disaster Recovery падал с `NameError` из-за отсутствующего импорта MSK formatter helper;
- выбор `50` / `200` строк в `Журналы` фактически читал разные объёмы, но одинаковый character cap делал Telegram output почти неразличимым.

`v4.21.2` исправляет оба finding без изменения SQLite schema, 3x-ui/OpenAPI, raw log timezone, redaction/security boundaries или mutation semantics.

Приёмка в production закрыт: оператор подтвердил штатное открытие Disaster Recovery без `NameError`, фактическое различие режимов журнала `50` / `200` и успешный базовый health check `GET /healthz` с HTTP 200. Raw log timestamps продолжают отображаться в machine-level UTC по contract.

##### Группы пользователей и аудиторий

**Статус: ✅ Выполнено и принято в production в `v4.22.0`.**

User Groups являются отдельной продуктовой сущностью и не заменяют существующие Server Groups.

Разделение ответственности:

- **Server Group** отвечает за инфраструктуру/provisioning: Nodes/Inbounds/Plan placement;
- **User/Audience Group** отвечает за аудиторию: кому в будущем разрешено или запрещено показывать конкретный контент/feature в Client Portal.

Целевой контракт:

- отдельные `user_groups` и `user_group_members` вводятся versioned migration;
- membership many-to-many: один пользователь может состоять одновременно в нескольких audience groups;
- group имеет stable internal ID, изменяемое display name, optional description и timestamps;
- membership привязывается к stable user identity (`telegram_id`), а не к display name/email;
- удаление группы не удаляет пользователей и транзакционно очищает только membership/rules, относящиеся к этой группе;
- в `Пользователях` и карточке пользователя доступны просмотр/изменение membership; отдельный admin screen управляет группами и участниками;
- добавляются явные RBAC privileges для просмотра и изменения User Groups;
- все membership/group mutations audit-friendly;
- backend получает единый reusable audience matcher с понятной семантикой include/exclude; deny/exclude должен иметь приоритет над allow/include, а отсутствие ограничений означает доступ всем подходящим пользователям;
- v4.22 не должен сам связывать audience groups с provisioning/Server Groups или менять VPN-доступ пользователя;
- Client Portal v5 использует этот же matcher для content/feature visibility, вместо ad-hoc проверок конкретных group names;
- regression tests покрывают migration, many-to-many membership, rename/delete, RBAC, audit и matcher edge cases.

Приёмка в production `v4.22.0` закрыт на развёрнутом release commit `37e16cf8e2f5a38f7796118c0ac93ba9c78a3c12`. Базовый status до и после targeted smoke подтвердил `Container: running`, `RestartCount=0`, `Bot version: 4.22.0`, `Health: ok`, `DB: ok`, ожидаемый Docker subnet `172.19.0.0/16` и `3x-ui connectivity: ok`. Migration journal подтвердил успешные v1/v2 и `v3 user_audience_groups_v4_22_0`.

Targeted smoke подтвердил production flow: создание временной User Group, поиск существующего пользователя, добавление membership, отображение группы из карточки пользователя, удаление membership через confirmation flow, наличие audit-событий для create/add/remove и двухшаговое удаление пустой группы. Тестовые данные после проверки удалены. Разделение User Groups и VPN provisioning отдельно защищено code/regression contract; production smoke не выполнял искусственных VPN mutations ради проверки.

##### Интеграция Cheburcheck

**Статус: ✅ Выполнено в `v4.23.1`.**

Приёмка в production закрыт после hotfix `v4.23.1` на exact release SHA `ff6638442cbe9c2adc9aa76d74c2cfb4b647aaf6`: Master/direct-node shortcuts, domain/public IP/ASN, URL/private-IP rejection, graceful unavailable/recovery и финальный base health пройдены; `AS213459` с response около 382 KiB успешно обработан новым 1 MiB bounded limit. После остановки и запуска только Cheburcheck backend оба runtime-сервиса вернулись в `healthy`, а bot status остался `RestartCount=0`, Health/DB/3x-ui `ok`. Проверка bot logs по exact internal URL и credential-variable names дала нулевые совпадения. Production flood для backend rate limit намеренно не выполнялся; per-admin 2-second cooldown закреплён отдельным regression-test без нагрузки на upstream.

Цель — встроить в бот функциональность проверки доменов/IP/ASN на блокировки, сохраняя upstream Cheburcheck checker как source of behavior и не переписывая его алгоритм без необходимости.

Upstream: `LowderPlay/cheburcheck`, BSD 3-Clause. При реализации фиксируется reviewed upstream commit/release и сохраняются обязательные copyright/license notices в third-party documentation.

Архитектурный принцип:

~~~text
Telegram UI
    ↓
CheburcheckClient / typed response model
    ↓
internal/self-hosted Cheburcheck service
    ↓
upstream checker/database logic
~~~

Требования:

- предпочтительный production path — pinned self-hosted Cheburcheck service во внутренней сети deployment; публичный `cheburcheck.ru` не становится обязательной single point of failure;
- bot integration использует documented check API semantics (в текущем upstream это `/api/v1/check?target=...`) и не проксирует произвольные HTTP URL;
- service optional и выключаем/настраиваем локально; его недоступность не должна ломать core bot startup или VPN control plane;
- v4.x UI размещает проверку как контролируемый read-only diagnostics tool внутри существующей authorization boundary; открытие её публичным клиентам решается отдельно в v5;
- input ограничивается поддерживаемыми target types и length/rate limits; ошибки/rate limit/upstream unavailable получают отдельные понятные состояния;
- обязательны connect/read/total timeouts, bounded concurrency и response-size limits;
- health/readiness Cheburcheck видимы оператору, но internal endpoint/credentials не раскрываются пользователю;
- CI фиксирует response contract на reviewed upstream revision через fixtures/contract tests;
- third-party notices и лицензия сохраняются при source/binary redistribution;
- production acceptance проверяет корректный verdict на test fixtures/known targets и graceful degradation при недоступном Cheburcheck service.

Реализация в `main` использует reviewed upstream `LowderPlay/cheburcheck@0bbd2be8ca4b8f9ded1407597654314fc2a900c6`, отдельный `CheburcheckClient`, optional `CHEBURCHECK_URL`, read-only RBAC и экран `Мониторинг → Проверка блокировок`. Auto-discovery предлагает безопасные hostname/IP из Master/direct Nodes/enabled Hosts, а карточки Master/direct node имеют shortcut проверки; URL path/query/credentials и private/local targets не передаются.

##### v4.23.2 — Cheburcheck: расширенный результат и контекстная навигация

**Статус: ✅ Production smoke `v4.23.2` выполнен; найденные gaps закрыты и приняты hotfix-релизом `v4.23.3`.**

Scope:

1. **Компактный parity результата с Cheburcheck site.** Расширить текущий bounded summary данными, которые уже доступны/могут быть надёжно получены из pinned Cheburcheck backend: нахождение цели в используемых блок-листах/реестрах и доступность по регионам. Telegram UI должен показывать это максимально компактно, без raw payload и без ослабления существующих response-size/timeouts/concurrency/rate-limit границ.

   Целевой operator-facing формат:

   ~~~text
   🔎 Проверка блокировок

   Цель: example.org
   Результат: 🟢 блокировка не обнаружена
   Сеть: Example ISP · AS12345 · Москва

   📋 Списки
   РКН: 🟢 не найден
   CDN: Cloudflare · 3 сети
   Исключение CDN: —
   ASN: 2 / 184 подсетей в списках

   🌍 Регионы: 11 ответов · 🟢 8 · 🔴 2 · 🟡 1

   Источник: Cheburcheck.
   ~~~

   Контракт представления:
   - верхняя часть содержит только цель, итоговый verdict и доступную network identity: организация / ASN / location;
   - блок `📋 Списки` агрегирует РКН, CDN, CDN exception и ASN/subnet coverage в одну короткую секцию;
   - региональные ответы сворачиваются в одну строку с общим числом и количеством `🟢 / 🔴 / 🟡`, без длинного перечня регионов в основном result card;
   - отсутствующие optional значения отображаются как `—`, а не раздувают карточку дополнительными пояснениями;
   - raw upstream payload и внутренние service details в Telegram UI не выводятся;
   - строка `Источник: Cheburcheck.` сохраняет явную attribution внешнего источника данных.

   Перед реализацией зафиксировать exact upstream fields/semantics для reviewed revision и покрыть их fixtures/contract tests; если часть site-only данных не выдаётся backend API, это явно фиксируется и не эмулируется догадками.

2. **Контекстная навигация Cheburcheck.** Источник входа становится частью UI context:
   - вход из `/admin → Мониторинг → Проверка блокировок` всегда возвращает только в Monitoring/Cheburcheck flow;
   - вход из карточки Master возвращает только в карточку Master;
   - вход из карточки direct Node возвращает только в ту же Node;
   - discovered targets, manual search, result, error, `Проверить ещё` и повторный поиск обязаны сохранять исходный parent context;
   - переход из Monitoring flow в Node/Master card и обратный cross-context jump через Cheburcheck запрещён;
   - callback data хранит только safe stable context/identity, без URL/credentials;
   - regression tests покрывают все entry points и Back/Repeat/Search transitions.

Цель релиза — улучшить информативность и UX Cheburcheck без изменения его read-only security boundary, provisioning/VPN state или 3x-ui mutations.

##### v4.23.3 — Cheburcheck: исправление подробностей компактного результата

**Статус: ✅ Закрыто. `v4.23.3` опубликован и принят; acceptance линии Cheburcheck `v4.23.x` завершён.**

Production smoke `v4.23.2` подтвердил сам compact layout и navigation, но выявил три presentation/data gaps:

1. пустой `cdn_providers` выводился как неизвестное `—`, хотя reviewed upstream однозначно означает «CDN не найден»;
2. для domain/public-IP upstream возвращает ASN в `geo.asn`, но `asn_info` заполняет только при target вида `AS12345`, поэтому ожидаемая строка `blocked / total` оставалась пустой;
3. minimal self-hosted runtime без active Probe reporters возвращает нулевую regional availability, а UI маскировал её нейтральным `—`.

Hotfix scope:

- empty CDN result показывается как `🟢 не найден`;
- domain/public-IP с валидным `geo.asn` выполняет один дополнительный bounded read-only check по этому ASN и использует только counts `blocked_prefixes / prefixes`; failure enrichment не меняет основной verdict;
- regional SSE сохраняет `started.online_probes` и различает агрегированные ответы, отсутствие active scanners, отсутствие ответов при online scanners и upstream/transport unavailable;
- subnet/ASN regional probe остаётся неприменимым и не запускается;
- никакие regional results не эмулируются и не подменяются static API данными;
- SQLite schema, 3x-ui/OpenAPI contract, provisioning/VPN mutations, Host Control, Deploy Agent и pinned Cheburcheck revision не меняются;
- изменение bot-only и не требует rebuild существующего Cheburcheck runtime; отдельное развёртывание probe fleet остаётся отдельной infrastructure задачей.

Итог acceptance: hotfix `v4.23.3` закрывает production findings compact result (`CDN`, domain/IP ASN enrichment и truthful regional probe status). Полноценный multi-region Probe fleet не входит в acceptance этого релиза и зафиксирован отдельно в разделе «Отложенные инфраструктурные улучшения».

##### v4.24.0 — Мониторинг сайтов и web diagnostics

**Статус: ✅ Production smoke `v4.24.0` выполнен; найденные findings закрыты в `v4.24.1`, и acceptance линии `v4.24.x` завершён.**

Runtime scope завершён и опубликован: schema v4/v5 website monitoring, native repository/state machine, SSRF-safe outbound boundary, bounded scheduler/incident notifications, watcher-scoped pause/resume, core admin UI, admin-only global target removal и one-off/contextual diagnostics (WHOIS/DNS/HTTP/redirect/CMS/SEO/optional PageSpeed/Sitemap/URL-list/QR) реализованы. Production smoke `v4.24.0` выявил три narrowly-scoped finding; они исправлены в опубликованном `v4.24.1`, после чего targeted smoke линии `v4.24.x` завершён.

Цель — нативно перенести полезное поведение `vladpak1/packbot` в текущий Admin Control Plane без встраивания отдельного PHP Telegram bot, MySQL runtime, webhook stack или второй application database.

Проверенный контракт upstream:

- project: `vladpak1/packbot`;
- reviewed revision: `3c4a5bb29626f8b3e28056bd52cd94fdce9f3c1a`;
- license: MIT;
- copyright: `Copyright (c) 2023 vladpak1`;
- PackBot используется как behavior/reference implementation; новая реализация остаётся Python/aiogram/SQLite-native и использует существующие jobs/audit/alerts/configuration primitives проекта.

Существенно адаптированный/перенесённый код и алгоритмы сопровождаются required MIT notice/source attribution в `THIRD_PARTY_NOTICES.md`, а release notes явно указывают upstream reference. В Telegram result cards постоянная строка `Источник: PackBot` не нужна: данные получаются нашей реализацией, а не внешним PackBot backend.

###### Границы релиза

- scope относится только к `/admin → Мониторинг`; публичный `/start` и Client Portal не расширяются;
- каноническое display name раздела — `🌐 Мониторинг сайтов`;
- PackBot не запускается как sidecar/service и не получает bot token;
- PHP/Composer/MySQL не становятся production dependencies;
- все persistent изменения выполняются только через versioned SQLite migrations;
- новые callbacks регистрируются в централизованном privilege catalog и неизвестные routes остаются fail-closed;
- реализация синхронно обновляет `docs/UI_STYLE.md`, `README.md`, `THIRD_PARTY_NOTICES.md`, migration docs/tests и `CHANGELOG.md`.

###### Каноническая навигация

~~~text
/admin
└─ 📈 Мониторинг
   ├─ 📊 Трафик
   ├─ 🟢 В сети
   ├─ 🩺 Состояние системы
   ├─ 🔎 Проверка блокировок
   ├─ 🌐 Мониторинг сайтов
   │  ├─ 📋 Сайты
   │  │  ├─ ➕ Добавить сайт
   │  │  └─ 🌐 Карточка сайта
   │  │     ├─ 🔄 Проверить сейчас
   │  │     ├─ 🩺 Диагностика
   │  │     ├─ 📜 История инцидентов
   │  │     ├─ ⏸ Приостановить / ▶️ Возобновить
   │  │     ├─ 🔔 Оповещения
   │  │     └─ 🗑 Удалить / отписаться
   │  ├─ 🛡 Все targets              ← Administrator+
   │  │  └─ 🗑 Глобальное удаление  ← двухшаговое
   │  └─ 🔎 Разовая диагностика
   │     ├─ 🌐 Домен
   │     │  ├─ WHOIS / возраст
   │     │  └─ DNS
   │     ├─ 🩺 Веб
   │     │  ├─ HTTP
   │     │  ├─ Redirect trace
   │     │  └─ CMS
   │     ├─ 🔍 SEO
   │     │  ├─ Индексация / robots / noindex
   │     │  └─ PageSpeed
   │     └─ 🧰 Утилиты
   │        ├─ Sitemap
   │        ├─ Список URL
   │        └─ QR
   ├─ 📜 Журналы
   └─ 🚨 Оповещения
~~~

`Мониторинг сайтов` имеет единственного parent — `Мониторинг`. Back/Cancel из add-site, diagnostics, incident history и utility FSM возвращает только в локальный website-monitoring context. Raw URL не кодируется в callback data; callbacks используют только stable numeric IDs / fixed action tokens.

Предварительный home screen:

~~~text
🌐 Мониторинг сайтов

Сайтов: {total}
🟢 Доступны: {up}
🔴 Недоступны: {down}
⚪ Не проверены: {unknown}

[📋 Сайты]            [➕ Добавить]
[🔎 Разовая диагностика]
[⬅ Мониторинг]
~~~

Карточка сайта:

~~~text
🌐 example.org

Статус: 🟢 доступен
HTTP: 200
Ответ: 184 мс
Последняя проверка: 2 мин назад
Инцидент: —

[🔄 Проверить сейчас] [🩺 Диагностика]
[📜 История]          [🔔 Оповещения]
[🗑 Удалить / отписаться]
[⬅ Сайты]
~~~

Status grammar обязана различать `up`, `suspect`, `down`, `unknown/checker_error` и disabled/paused state; локальная ошибка checker/network safety layer не выдаётся за подтверждённое падение сайта.

###### Контракт ролей и прав RBAC

Новых ролей не появляется.

- `website_monitoring.view` / минимум `Read-only`: home/list/card, incident history, one-off WHOIS/DNS/HTTP/redirect/CMS/SEO/Sitemap/URL-list/QR diagnostics и просмотр текущих notification settings;
- `website_monitoring.manage` / минимум `Support`: добавить сайт в persistent monitoring, подписаться/отписаться от site alerts, ручной `Проверить сейчас`, pause/resume собственной monitoring subscription;
- `website_monitoring.admin` / минимум `Administrator`: глобально удалить monitor target, когда на него ещё подписаны другие администраторы, и выполнять будущие global monitoring mutations;
- `Owner` не получает отдельный capability только из-за `v4.24.0`.

Keyboard privilege-aware: недоступная mutation-кнопка не показывается, но handler authorization остаётся обязательной независимо от UI visibility.

###### Ownership и deduplication

PackBot upstream хранит список owners внутри site record. В текущем проекте это адаптируется в нормализованную many-to-many модель:

- один canonical public URL существует как один monitor target;
- один target может иметь несколько admin-watchers по стабильному Telegram ID;
- повторное добавление того же canonical URL не создаёт второй background checker, а подписывает текущего администратора на существующий target;
- лимит применяется к числу targets/watch subscriptions текущего администратора; начальный parity default — не более **10**;
- удаление собственной подписки не удаляет target, пока существуют другие watchers;
- global removal target при наличии других watchers требует `website_monitoring.admin` и явного confirmation;
- alert delivery идёт только текущим watchers, имеющим право получать Telegram notifications; target ownership не используется как security identity для callback lookup.

###### Модель хранения данных

Новые сущности создаются forward-only migration через существующий `schema_migrations` framework.

Минимальная логическая модель:

~~~text
website_monitors
- id
- canonical_url UNIQUE
- hostname
- enabled
- state: unknown | up | suspect | down
- last_check_at
- next_check_at
- last_http_status
- last_latency_ms
- last_error_kind
- consecutive_failures
- created_at
- updated_at

website_monitor_watchers
- monitor_id
- telegram_id
- notifications_enabled
- monitoring_enabled
- created_at
UNIQUE(monitor_id, telegram_id)

website_incidents
- id
- monitor_id
- opened_at
- resolved_at
- reason_kind
- first_http_status
- last_http_status
- alert_count
- last_alert_at

website_incident_notifications
- incident_id
- telegram_id
- kind: opened | repeat | recovered
- sequence
- sent_at
UNIQUE(incident_id, telegram_id, kind, sequence)
~~~

Raw response bodies, WHOIS payloads, sitemap XML и PageSpeed JSON не сохраняются как persistent monitoring state. Для основной карточки хранится только bounded normalized metadata. Incident history — источник истории availability; `v4.24.0` не обязан вводить неограниченный time-series storage каждого успешного check.

###### Модель состояний мониторинга

PackBot behavior сохраняется по смыслу, но оформляется явной deterministic state machine:

~~~text
unknown
  ├─ success ───────────────→ up
  └─ candidate failure ─────→ suspect

up
  ├─ success ───────────────→ up
  └─ candidate failure ─────→ suspect

suspect
  ├─ recheck success ───────→ up
  ├─ confirmed failure ─────→ down + open incident + first alert
  └─ checker/internal error → previous stable state preserved

down
  ├─ confirmed failure ─────→ down + optional repeated alert
  ├─ success ───────────────→ up + close incident + recovery alert
  └─ checker/internal error → down preserved, no false recovery
~~~

Disabled/paused — отдельный lifecycle flag, а не health verdict.

Начальные parity defaults по reviewed upstream:

- normal check interval: **10 минут**;
- down-site check interval: **3 минуты**;
- confirmation recheck после candidate failure: **2 секунды**;
- response-time threshold: **5 секунд**;
- first repeated-alert interval: **30 минут**;
- после нескольких alerts следующий interval: **320 минут**;
- максимальное число контролируемых целей на администратора: **10**.

Эти значения являются application defaults, а не Telegram-controlled arbitrary scheduler input. Изменение global defaults отдельной UI mutation в `v4.24.0` не требуется.

Candidate failure включает target-attributable timeout/DNS/TLS/connect failure или unhealthy HTTP result. Internal checker error, safety-policy rejection, local resource exhaustion и programming error не открывают site-down incident. Exact HTTP health rule фиксируется implementation tests; базовый parity ориентир — successful canonical/effective request с HTTP 200, как в reviewed upstream, при этом все redirects до canonical target проходят наш safety validation.

Scheduled loop использует persistent `next_check_at` + bounded worker concurrency. Restart не создаёт duplicate incident/alert: current state читается из SQLite, а notification journal делает first/repeat/recovery delivery идемпотентной на уровне recipient/kind/sequence. На каждый future poll не создаётся бесконечная durable job queue.

###### Защита исходящих запросов

Все HTTP(S)-функции `v4.24.0` — monitor check, canonical/effective URL discovery, redirects, CMS, SEO, PageSpeed target validation, robots и Sitemap — обязаны использовать **один общий** safe outbound client.

Fail-closed требования:

- только `http://` и `https://`;
- arbitrary/custom ports запрещены; разрешены только стандартные 80/443;
- URL userinfo/credentials запрещены;
- hostname проходит IDNA normalization и length/syntax validation;
- до connect проверяются все A/AAAA answers; loopback, private/RFC1918, CGNAT, link-local, multicast, documentation/reserved/non-global ranges блокируются;
- известные cloud metadata destinations/hostnames блокируются отдельно;
- фактический connect привязывается к уже validated public address, чтобы validation/connect не расходились из-за DNS rebinding;
- каждый redirect заново проходит полный parse/DNS/address validation;
- environment proxy variables не могут неявно обойти destination policy;
- public diagnostics не получают route к private VPN/control-plane endpoints через supplied URL;
- response body читается streaming/bounded и не буферизуется без лимита;
- transport errors не логируют credentials/query secrets и не сохраняют raw body.

Начальные hard bounds:

- redirects: не более **5**;
- тайм-аут подключения: **3 s**;
- тайм-аут чтения: **7 s**;
- общий тайм-аут HTTP: **10 s**;
- обычный response body: не более **1 MiB**;
- sitemap document: не более **2 MiB**;
- sitemap documents за одну операцию: не более **10**;
- URLs из sitemap: не более **5000**;
- background/manual outbound operations используют общий bounded concurrency limiter; один target не должен одновременно получать несколько scheduled checks.

WHOIS принимает только нормализованный domain и не позволяет пользователю задавать произвольный WHOIS server/port. DNS diagnostics принимает только domain/record-family inputs и не превращается в arbitrary DNS resolver client к указанному пользователем nameserver.

###### Контракт диагностики

`🔎 Разовая диагностика` не создаёт persistent monitor target без отдельного `Добавить в мониторинг`.

Domain:

- WHOIS: creation/expiration при доступности, вычисляемый возраст, bounded operator summary; полный raw WHOIS dump в Telegram не обязателен;
- DNS: bounded A/AAAA/CNAME/MX/NS/TXT summary с pagination/truncation, если records много.

Web:

- HTTP: конечный безопасный URL, статус, задержка, тип сервера/контента и ограниченный набор заголовков;
- Redirect trace: максимум 5 hops, каждый hop safe-validated;
- CMS: best-effort detection; `не определена` отличается от transport failure.

SEO:

- доступность индексации, robots/noindex — сводка без изменений;
- PageSpeed включается только при локально настроенном API key; отсутствие key отображается как disabled/unconfigured, а не ошибка сайта.

Utilities:

- Sitemap — bounded recursive parse по лимитам выше;
- URL list formatting/trimming — локальная операция без outbound requests;
- QR — локальная генерация для предоставленного текста/URL; remote logo fetching в scope `v4.24.0` не входит.

Screenshot/headless-browser diagnostics из README PackBot не входят в обязательный `v4.24.0`: это отдельный browser/runtime attack surface и требует отдельного решения, если когда-либо понадобится.

###### Матрица совместимости с PackBot (PackBot parity matrix)

| PackBot capability | Решение `v4.24.0` |
| --- | --- |
| add/list/remove monitored sites | ✅ нативный parity через SQLite |
| owners нескольких пользователей | ✅ адаптация в many-to-many admin watchers |
| max sites per user | ✅ parity default 10 |
| periodic up/down intervals | ✅ parity 10 min / 3 min |
| second confirmation check | ✅ parity, 2 s |
| первое/повторное уведомление и восстановление | ✅ постоянный журнал инцидентов/уведомлений |
| история и статистика инцидентов | ✅ история инцидентов; без неограниченного временного ряда успехов |
| WHOIS + domain age | ✅ |
| DNS records | ✅ bounded |
| HTTP/server response | ✅ через safe outbound client |
| redirect trace | ✅ max 5 hops |
| CMS detection | ✅ best effort |
| robots/noindex/indexability | ✅ |
| Google PageSpeed | ✅ optional при configured secret key |
| sitemap parsing | ✅ bounded: 10 docs / 5000 URLs |
| URL list formatting/trimming | ✅ local-only |
| QR generation | ✅ local-only |
| screenshots/headless browser | ⏭ вне обязательного scope `v4.24.0` |
| multilingual PackBot UI | ⏭ не переносится; canonical UI остаётся русским |
| PHP/MySQL/webhook runtime | ❌ не переносится |

###### Tests и acceptance

До release обязательны:

- migration tests с upgrade существующей schema и сохранением текущих данных;
- детерминированные тесты автомата состояний: первичный сбой, повторная проверка, ложная тревога, подтверждённое падение, повтор, восстановление и рестарт во время инцидента;
- идемпотентность уведомлений для каждого наблюдателя;
- negative RBAC coverage для всех callbacks;
- набор SSRF-тестов для IPv4/IPv6, частных, локальных, CGNAT, зарезервированных/metadata адресов, переходов на внутренние адреса и имитации повторного DNS-разрешения;
- hard-limit tests для redirects/body/sitemap/count/concurrency;
- fake HTTP/DNS/WHOIS/PageSpeed fixtures; CI не зависит от случайных публичных сайтов;
- navigation tests для Back/Cancel и отсутствие raw URL в callbacks;
- license/attribution regression: reviewed PackBot revision и MIT notice остаются в `THIRD_PARTY_NOTICES.md`.

Приёмка в production после deployment:

1. `deploy-release.sh --status` подтверждает exact tag/version, `RestartCount=0`, Health/DB/3x-ui `ok`;
2. controlled public test target проходит add → initial up → manual check → diagnostics;
3. controlled failure проходит `up → suspect → down`, создаёт ровно один incident и first alert;
4. повторная проверка down target соблюдает repeat-alert cadence без alert storm;
5. recovery закрывает incident и отправляет ровно один recovery alert;
6. restart бота во время открытого incident не создаёт duplicate first/recovery alert;
7. private/local/metadata URLs и redirect-to-private блокируются;
8. concurrency/rate-limit smoke не создаёт unbounded queue;
9. optional PageSpeed без key остаётся корректно disabled;
10. после smoke повторяется базовый status/health check.

Operational closure линии `v4.24.x` достигнут: website monitoring и обязательные diagnostics работают через единый safe outbound boundary, incidents/alerts переживают restart без replay, PackBot attribution/parity соответствуют reviewed revision, а targeted findings `v4.24.0` подтверждены исправленными на deployed `v4.24.1`.


##### v4.24.1 — исправление диагностики и IPv6

**Статус: ✅ Выполнено и принято в production в `v4.24.1`; acceptance линии `v4.24.x` закрыт.**

Production smoke `v4.24.0` подтвердил корректную работу contextual web diagnostics и навигации, но выявил три narrowly-scoped presentation/diagnostics/validation finding, которые не требуют изменения control-plane architecture:

1. WHOIS/RDAP absolute timestamps выводятся в raw RFC3339/UTC (`...Z`) вместо канонического operator-facing MSK.
2. Compact Cheburcheck card, введённая в `v4.23.2`, оказалась слишком агрессивно сокращена: backend продолжает получать/нормализовать IP, reverse DNS и дополнительные static check fields, но часть полезной operational detail намеренно перестала отображаться в Telegram card.
3. Website monitoring URL validation безопасно отклоняет `http://[::1]/`, но делает это через domain-name syntax branch до `ipaddress.ip_address()`. В результате блокируется не только loopback/non-global IPv6, но и любой public IPv6 literal, хотя downstream canonical URL logic уже поддерживает bracketed IPv6.

Scope `v4.24.1`:

**Представление результатов WHOIS/RDAP**

- нормализовать `created_at` / `expires_at` RDAP timestamps в единый presentation helper;
- показывать absolute date/time в формате `DD.MM.YYYY HH:MM MSK` согласно `docs/UI_STYLE.md`;
- machine/RDAP timestamps не изменять и не сохранять в локальном времени;
- `Возраст: N дн` продолжает вычисляться от UTC instant и не зависит от presentation timezone;
- invalid/missing upstream timestamp остаётся `—`, без guess/parsing fallback;
- покрыть regression tests для `Z`, explicit offset и date rollover при переводе в MSK.

**Компактная карточка Cheburcheck**

Вернуть в основную карточку только нормализованные bounded static-check значения, которые реально присутствуют в upstream result:

- `IP` — resolved IP addresses для domain target; для direct IP target не дублировать очевидное значение без UX-пользы;
- `Reverse DNS` — только фактически полученные PTR/reverse lookup values;
- `Заблокированные подсети` — bounded summary фактически возвращённых subnet entries;
- `Домен из реестра` / `rkn_domain` — только когда upstream поле присутствует;
- `Размер подсети` / `subnet_size` — только когда применимо и поле присутствует;
- существующие `Сеть`, `РКН`, `CDN`, `Исключение CDN`, `ASN` и агрегированная строка `🌍 Регионы` сохраняются.

Ограничения размера вывода:

- IP и Reverse DNS: показывать не более **5** значений каждого типа, затем `… ещё N`;
- blocked subnets: показывать не более **5** значений, затем `… ещё N`;
- строки/labels экранируются и ограничиваются по длине; raw upstream JSON/SSE payload в Telegram не выводится;
- отсутствие optional значения отображается только там, где поле является частью канонической карточки; не создавать длинные секции из сплошных `—`.

Regional probe boundary остаётся прежним:

- **не возвращать raw probe payload** в основную карточку;
- `🌍 Регионы` остаётся compact aggregate (`N ответов · 🟢 / 🔴 / 🟡`) либо честным состоянием `нет активных региональных сканеров / нет ответов / unavailable / not applicable`;
- если позже понадобится per-region drill-down, это отдельный bounded `🌍 Детали регионов` workflow, а не dump JSON/SSE в основной result.


**Проверка буквальных IPv6-адресов при мониторинге сайтов**

- распознавать literal IPv4/IPv6 через `ipaddress.ip_address()` **до** domain/IDNA hostname validation;
- public IPv6 literal разрешать при тех же `http/https` и standard-port правилах, что public IPv4;
- canonical URL сохраняет обязательные brackets для IPv6 host (`https://[2001:4860:4860::8888]/`);
- loopback (`::1`), link-local, private/non-global, multicast, reserved и unspecified IPv6 отклонять тем же `unsafe_target` policy, что IPv4;
- пользовательский текст для `::1` и других non-public literals должен быть `Локальные, служебные и непубличные адреса запрещены.`, а не domain-syntax error;
- DNS hostname path и DNS-rebinding protection не ослабляются: A/AAAA answers по-прежнему проверяются на global address до connect;
- добавить регрессионный тест: разрешённый публичный IPv6 literal, запрет `::1`, link-local и непубличных IPv6;

Scope guard:

- не менять Cheburcheck static/probe transport limits, timeouts, redirect policy или pinned upstream revision;
- не менять DNS/HTTP/redirect/CMS/SEO/PageSpeed/Sitemap/QR semantics;
- кроме исправления ordering IPv6-literal validation не менять safe outbound transport semantics, redirect/DNS-rebinding policy, website monitoring state machine, SQLite schema, navigation/RBAC contract, Host Control, Deploy Agent или 3x-ui/OpenAPI;
- `v4.24.1` остаётся presentation/read-only diagnostics hotfix.

Приёмка исправления:

1. WHOIS на controlled domain показывает creation/expiration в `DD.MM.YYYY HH:MM MSK`;
2. UTC → MSK conversion проверяется на значении, которое переходит на следующий календарный день;
3. возраст домена остаётся тем же, что до hotfix;
4. Cheburcheck domain result снова показывает bounded `IP` и доступный `Reverse DNS`;
5. при наличии upstream blocked subnets / `rkn_domain` / `subnet_size` эти значения отображаются без raw payload и без unbounded output;
6. domain с >5 IP/PTR/subnet entries показывает первые 5 и `… ещё N`;
7. regional result остаётся агрегированным; raw probe JSON/SSE в карточке отсутствует;
8. public IPv6 literal canonicalize/add проходит при global address, а `::1`/link-local/non-global IPv6 отклоняются как unsafe target до outbound connect;
9. bracketed IPv6 сохраняется в canonical URL и не ломает standard-port enforcement;
10. contextual `Другой инструмент` / `⬅ Сайт` navigation остаётся без изменений;
11. финальный `deploy-release.sh --status` подтверждает exact `v4.24.1`, `RestartCount=0`, Health/DB/3x-ui `ok`.

`v4.24.1` опубликован как exact release commit после успешных `Python checks` и `Publish release`. Три finding закрыты в release-коде; production smoke линии `v4.24.x` проведён и acceptance закрыт. Targeted hotfix не должен разрастаться в feature scope.


