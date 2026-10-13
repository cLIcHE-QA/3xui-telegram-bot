## Предварительное главное меню v5.0.0

~~~text
👤 Профиль          🌐 Моя подписка
💳 Купить / продлить   📊 Трафик
📱 Устройства       🆘 Помощь
~~~

Это базовый набор разделов. Новые top-level кнопки добавляются только если действие нельзя естественно разместить внутри одного из этих разделов.

## 👤 Профиль

Назначение: краткий account/entitlement summary клиента.

Предварительные подразделы и данные:

- Telegram ID / внутренний customer identity;
- статус: active / expired / suspended / provisioning;
- текущий Plan;
- дата окончания;
- состояние автопродления, когда оно появится;
- назначенная Server Group или пользовательское понятное описание региона/группы;
- настройки уведомлений;
- язык интерфейса, если будет поддерживаться несколько языков.

Профиль не должен показывать infrastructure secrets, внутренние node credentials или административные identifiers, которые не нужны клиенту.

## 🌐 Моя подписка

Главный рабочий экран действующего клиента.

Предварительно показывает:

- статус подписки;
- Plan;
- срок действия;
- число доступных серверов/локаций;
- URL подписки;
- состояние provisioning/reconcile.

Контекстные действия:

- `📋 Скопировать ссылку`;
- `📱 Подключить устройство`;
- `🔄 Синхронизировать подписку`;
- `💳 Продлить`.

### 🔄 Синхронизировать подписку

Это не отдельный top-level раздел.

Смысл операции:

1. проверить актуальный entitlement клиента;
2. вычислить ожидаемые ресурсы через `Plan → Server Group → Nodes → Inbounds → User`;
3. выполнить безопасный provisioning/reconcile;
4. проверить post-condition;
5. сохранить существующий subscription identity, если нет отдельной причины его менять.

Кнопка не должна по умолчанию генерировать новый `sub_id` или новую ссылку. Subscription URL считается секретом клиента.

## 💳 Купить / продлить

Единый commerce flow для нового и существующего клиента.

Предварительные подразделы:

- каталог доступных Plans;
- период/вариант тарифа;
- итог заказа;
- `🎟 Промокод`;
- выбор доступного способа оплаты;
- статус платежа/заказа;
- результат activation/extension.

Жизненный цикл серверной части:

~~~text
Plan selection
  ↓
Order
  ↓
Promo / pricing
  ↓
Payment
  ↓
Confirmed payment event
  ↓
Entitlement
  ↓
Provisioning / reconcile
  ↓
Subscription available
~~~

### Модель состояний заказа, платежа и entitlement

Commerce flow должен иметь явные persistent states, а не выводить состояние покупки из Telegram message history или набора loosely-related flags.

Минимальная модель должна различать как минимум:

~~~text
order:
created
awaiting_payment
paid
cancelled
expired

payment:
created
pending
confirmed
failed
refunded
unknown

entitlement:
pending
provisioning
active
suspended
expired
failed
~~~

Допустимые переходы фиксируются backend-ом. Telegram UI только запрашивает текущее состояние и инициирует разрешённые команды.

Критические правила:

- подтверждение оплаты сначала надёжно записывается как provider event/payment state и только потом влияет на entitlement;
- `confirmed payment → entitlement/provisioning` выполняется идемпотентно;
- временный provisioning failure не откатывает факт успешной оплаты;
- повторный запуск reconcile не должен создавать второй entitlement или менять subscription identity без отдельной причины;
- `unknown` используется там, где внешний provider мог принять mutation, но итог невозможно доказать;
- ручная коррекция финансовых состояний доступна только через audit-friendly административный workflow.

### Наблюдаемость администратора: заказы Stars и состояние счетов

Текущий экран `/admin → Платежи → Telegram Stars` показывает локальные `commerce_payments`. При этом отправленный, но ещё не оплаченный Telegram Stars invoice может уже иметь локальный `commerce_order` в `created/awaiting_payment`, но ещё не иметь payment row и поэтому не виден оператору в Stars ledger.

Отдельное non-blocking v5.x improvement — read-only просмотр Stars orders/invoice state из Admin Control Plane:

- bounded/paginated список локальных `commerce_orders` для Stars с состояниями `created`, `awaiting_payment`, `paid`, `cancelled`, `expired`;
- в строке/детали показывать order ID, customer identity, Plan, сумму `XTR`, время создания/изменения и текущий order status;
- если payment уже существует, показывать связанную payment ID/status и переход в существующую карточку Stars payment;
- если payment ещё нет, явно показывать `платёж ещё не подтверждён/не создан`, а не маскировать order как failed payment;
- различать локальный order/invoice intent и фактическое Telegram invoice message: бот не пытается получать или воспроизводить содержимое уже отправленного provider-side invoice message;
- экран не выполняет retry, resend, cancel, refund или другие state-changing операции автоматически; первая версия является только observability/support surface;
- raw invoice payload, provider secrets, subscription credentials и другие secret-like данные в UI не выводятся;
- support flow должен позволять без shell/ручного SQL проследить цепочку `Order → Payment → Entitlement` и понять, на каком этапе остановился customer purchase.

Эта задача не является release blocker для текущего controlled acceptance `v5.0.0-rc.2`, но повышает support/observability readiness перед широким customer rollout.

### Customer payment UX: закрытие paid Stars invoice

Во время targeted production retest `v5.0.0-rc.3` подтверждён Low/non-blocking UX finding #320: после успешного `successful_payment` старое native Telegram Stars invoice-сообщение остаётся в customer chat и визуально сохраняет кнопку `Заплатить ⭐…`.

Backend integrity при этом сохраняется: pre-checkout принимает только orders в `created/awaiting_payment`, поэтому уже оплаченный `order=paid` повторно подтвердить нельзя. Проблема — misleading affordance после успешной оплаты.

Желаемый контракт:

- после confirmed payment старый invoice больше не выглядит как payable;
- cleanup не влияет на уже подтверждённые Payment / Order / Entitlement и не может их откатить;
- если для cleanup требуется Telegram message mutation, её uncertain outcome не replay'ится слепо;
- предпочтительно durable связать локальный order/payment с отправленным invoice `message_id`, чтобы после confirmed state удалить/закрыть старое invoice message либо иным Telegram-supported способом показать paid/closed state;
- ошибка cosmetic cleanup не превращает successful payment в failed/unknown commerce state;
- regression coverage подтверждает, что старый paid invoice не создаёт misleading повторный purchase path.

Finding #320 не блокирует targeted acceptance `v5.0.0-rc.3`; закрыть до stable/public rollout либо включить в следующий RC, если он потребуется по release-blocking причинам.

### Журнал webhook платёжного провайдера

Для каждого внешнего payment event хранится immutable/minimally-mutable journal record.

Минимальные данные:

- provider;
- идентификатор события/платежа провайдера;
- время получения;
- результат проверки подписи/аутентификации;
- нормализованный тип события;
- raw payload hash и безопасный диагностический metadata subset;
- статус обработки;
- связанный order/payment;
- время и результат применения.

Требования:

- уникальность provider event ID защищает от повторного применения одного события;
- повторный webhook после успешной обработки возвращает корректный idempotent результат, но не продлевает entitlement повторно;
- невалидная подпись никогда не изменяет финансовое состояние;
- webhook handler не доверяет Telegram callback state;
- ошибка после записи события, но до provisioning, должна быть recoverable через journal/reconcile;
- секреты provider-а и полный sensitive payload не выводятся в audit/UI/logs.

Ключевые требования:

- payment events идемпотентны;
- повторный webhook не должен повторно продлевать entitlement;
- успешная оплата и временная ошибка provisioning не должны приводить к потере покупки;
- failed provisioning попадает в recoverable job/reconcile flow;
- Telegram UI не является источником истины для payment status.

## 📊 Трафик

Назначение: понятная клиенту статистика использования.

Базовый v5.0.0 view:

- использовано;
- лимит;
- осталось;
- дата/период сброса или окончания entitlement;
- состояние unlimited, если лимит отсутствует.

Возможные последующие подразделы:

- сегодня;
- 7 дней;
- 30 дней.

Графики не являются обязательным условием первого Client Portal.

## 📱 Устройства

Раздел должен различать реальные зарегистрированные HWID devices и наблюдаемые network connections.

Если backend знает только IP/online connections, UI не должен выдавать их за достоверный список физических устройств. Для текущего 3x-ui adapter реальные HWID devices уже доступны через reviewed `client_hwids` API; customer-facing слой получает их только через provider-neutral `CustomerPortalService` / provider capability contract и не импортирует `XUIClient` напрямую.

### Компактный customer UX

Текущий длинный текстовый список с полной датой для каждого device неудобен при большом количестве исторических HWID. Целевой вариант — компактный bounded list:

~~~text
📱 Устройства · {registered}/{limit_or_—}

1. iPhone · iOS
   🕒 сегодня, 05:14

2. iPhone 17 Pro · iOS
   🕒 сегодня, 03:39

3. Windows 11 · Windows
   🕒 вчера, 15:44
…
~~~

Правила:

- в summary показывать `N / HWID limit`, если provider действительно сообщает limit; если limit неизвестен/отключён — не придумывать число;
- model/platform показываются кратко, без полного fingerprint/HWID;
- last seen форматируется компактно и локально для пользователя, полный timestamp остаётся допустимым в detail;
- список bounded/paginated; десятки записей не превращают одно Telegram message в длинный diagnostic dump;
- каждый реальный HWID device открывается отдельной inline-кнопкой `📱 {device}`;
- observed IP/session data при необходимости остаются отдельным presentation layer и не смешиваются с HWID inventory.

Карточка конкретного устройства:

~~~text
📱 {device_model_or_platform}

ОС: {os}
Последняя активность: {last_seen}

[🗑 Удалить устройство]
[⬅ Устройства]
~~~

### Customer self-service: удалить одно собственное устройство

Удаление одного HWID device допускается как customer self-service, чтобы обычная замена телефона/клиента не требовала обращения в поддержку. Это не означает `Удалить все устройства` и не даёт customer административный callback.

Безопасный contract:

- customer callback несёт только stable `device_id`; Telegram ID/email другого пользователя не принимаются из customer-controlled payload;
- backend заново разрешает текущий authenticated Telegram ID → customer profile/email и перед DELETE повторно проверяет, что `device_id` действительно входит в HWID inventory этого customer;
- mutation проходит только через provider-neutral service method/capability (`delete_device` / `supports_device_delete`), без прямого `XUIClient` import в `client_access.py`;
- удаляется ровно одно устройство за операцию;
- перед DELETE обязателен отдельный confirmation screen; первый callback mutation не выполняет;
- используется существующая one-shot mutation semantics: timeout/network/5xx → outcome `unknown`, DELETE автоматически не повторяется;
- после `unknown` UI предлагает только обновить device list/read-back; blind retry не выполняется;
- deterministic rejection показывается отдельно от `unknown`;
- success возвращает в обновлённый device list;
- в обычный audit/support output не пишутся полный HWID/fingerprint, subscription URL или другие secret-like identifiers;
- customer delete имеет небольшой bounded rate limit/cooldown, чтобы self-service не превращался в churn API;
- `Удалить все устройства` в базовый customer flow не добавляется.

HWID limit трактуется как ограничение одновременно зарегистрированных устройств: удалив собственный device, пользователь освобождает слот и может зарегистрировать новый, если это допускает текущий provider limit. Это не считается обходом concurrent-device limit. Если продукту понадобится ограничивать частую ротацию устройств между людьми, это отдельная anti-churn policy/cooldown, а не изменение смысла HWID limit.

Будущие расширения:

- пользовательское имя устройства;
- device-specific onboarding/deep-link;
- явные возможности и состояния: управление устройствами доступно, HWID-проверка включена, лимит отключён, неподдерживаемый клиент, лимит достигнут, ошибка провайдера;

## Подключение клиентов и удобство настройки

Первый Client Portal должен уменьшать зависимость от ручной поддержки при подключении устройства.

Базовый UX:

- platform selection: iOS / Android / Windows / macOS / Linux;
- QR для subscription URL там, где это уместно;
- deep-link / import-link только если формат клиента стабилен и безопасен;
- короткие инструкции для поддерживаемых клиентов без привязки backend logic к конкретному приложению;
- read-only диагностика: entitlement active, subscription reachable, provisioning/reconcile state, известные ограничения;
- rotation/reissue credentials выполняется отдельной явной операцией и не маскируется под обычный refresh.

Roadmap не требует device registration в первой версии. Наблюдаемый IP/session не должен называться физическим устройством без надёжной device identity.

## 🆘 Помощь

Подразделы:

- `📱 Как подключиться`;
- `❓ Частые вопросы`;
- `🛠 Проверить подписку`;
- `💬 Связаться с поддержкой`.

Раздел должен помогать решить типовые проблемы без доступа пользователя к административным controls.

`🛠 Проверить подписку` — read-only diagnostics либо безопасная ссылка на reconcile flow; она не должна выполнять опасные infrastructure mutations.

## Граница авторизации

Текущий проект ограничивает пользовательский flow через allowlist. Для публичного Client Portal это должно быть пересмотрено отдельно в v5.x.

Целевое правило:

- `/start` и customer callbacks доступны обычному Telegram-пользователю согласно product/onboarding policy;
- пользователь может читать и изменять только собственный account/subscription context;
- `/admin` и все `admin:*` callbacks продолжают требовать существующие admin roles;
- customer identity никогда не даёт implicit admin access;
- ownership проверяется backend-ом, а не только callback payload.

Открытие публичного `/start` выполняется только после готовности customer authorization, entitlement/payment lifecycle и abuse/rate-limit policy.

## Gate перед публичным запуском Клиентский портал

Финальный v4 audit создаёт проверенную backend/control-plane baseline, но не заменяет review нового public attack surface.

После реализации `v5.0.0`, но **до** снятия allowlist/допуска реальных клиентов, выполняется отдельный launch audit как минимум по следующим направлениям:

- ownership/isolation каждого customer endpoint/callback и защита от IDOR;
- злоупотребления регистрацией/onboarding, лимиты запросов, spam/bot automation и квоты ресурсов;
- автомат состояний Order/Payment/Entitlement, аутентификация/idempotency/replay webhook и сверка;
- subscription URL/credential exposure, rotation и cross-user leakage;
- input/file/deep-link/QR handling и внешние URL;
- privacy/data-minimization/retention для Telegram/customer/payment data;
- customer-visible error states и support/recovery flows;
- load/concurrency/failure testing для ожидаемого публичного трафика;
- повторный dependency/container/secret scan для v5 delta;
- чистый production-like end-to-end сценарий: регистрация → покупка/активация → выдача доступа → использование подписки → продление/истечение/восстановление;

Public launch блокируется до закрытия release-blocking findings этого v5 launch audit.

## Текущий статус v5 Клиентский портал — 2026-10-08

**Актуальный срез на 2026-10-08:** production остаётся на immutable `v5.0.0-rc.5` (`14042f6dc9d467dc8d0e999eb493f9e1cfc90611`); V5-A-009 Stars refund — scoped PASS, V5-A-002 только read-only preflight/reconciliation — scoped PASS (подробности ниже). #333/#334 исправлены и прошли CI в `main` через PR #335, **не выпущены/не проверены в production**. `rc.6` — первоначальный release-prep PR #339 не прошёл CI (2 format-check tests), исправление канонической строки Admin Setup перенесено в пересобранный release-prep от актуального `main`; новый CI/merge/tag/deploy ещё не подтверждены. Будущий внешний PSP/СБП #336 запланирован через PR #338, без реализации. **Общий v5 production acceptance — NOT PASS**, pilot allowlist сохраняется.

- 🟡 commerce/payment/entitlement foundation, Telegram Stars, onboarding/self-service diagnostics и launch safety controls реализованы;
- 🟡 отдельный v5 launch audit выполнен; repository-verifiable controls закреплены regression gate;
- 🟡 retention/data-minimization policy и production acceptance runbook находятся в `main` после #309;
- ✅ #310 реализовал immutable `v5.0.0-rc.N` prerelease/deploy path для controlled canary;
- ✅ `v5.0.0-rc.1` опубликован immutable GitHub prerelease и развёрнут на production canary с exact tag/SHA, `RestartCount=0`, Health/DB/3x-ui connectivity `ok`;
- 🔴 production acceptance `v5.0.0-rc.1` остановлен как **FAIL** после двух release-blocking findings до фактического Stars payment:
  - **V5-A-005 — expired customer access lifecycle:** существующий customer profile после прошедшего `users.expiry_time` отображался как `Подписка: активна`; durable entitlement в `active/suspended` не имел фонового перехода в `expired` после `expires_at`. Fix вычисляет effective customer status по expiry и локально истекает due entitlement без remote mutation/blind retry;
  - **V5-A-006 — Telegram Stars admin ledger runtime crash:** `Платежи → Telegram Stars` падал с `NameError: name 'aiosqlite' is not defined`, потому что handler использовал `aiosqlite.connect(...)` и `aiosqlite.Row` без runtime import. Fix добавляет явный import и regression contract Stars ledger;
- ✅ canary-fix PR #312 слит в `main`: repository fixes и regression coverage для V5-A-005/V5-A-006 входят в новый baseline;
- ✅ release-prep `v5.0.0-rc.2` слит через PR #313, immutable prerelease опубликован и развёрнут на production: tag `v5.0.0-rc.2` → SHA `24272d61f87396d365522b0156dff5c3165c682c`, container `running`, `RestartCount=0`, Bot `5.0.0-rc.2`, Health/DB/3x-ui connectivity `ok`;
- ✅ pinned OpenAPI contract обновлён до 3x-ui `v3.9.0`; production integration smoke прошёл на фактических Master и direct node с `3x-ui 3.9.0` / `Xray 26.9.30`, базовые read-only version/status paths работают;
- ✅ V5-A-005 targeted retest — **PASS**: expired customer profile и home summary больше не показывают доступ активным; effective expiry отображается как `истекла`; durable expiry fix остаётся без remote mutation/blind retry;
- ✅ V5-A-006 targeted retest — **PASS**: `/admin → Платежи → Telegram Stars` открывается без runtime exception;
- ✅ V5-A-001 partial real-payment path на `rc.2` доказал `invoice → successful_payment → payment=confirmed → order=paid → entitlement=active → subscription URL/provider read` без manual DB repair;
- 🔴 **V5-A-007 — paid quota cycle не сбрасывает старый traffic:** после реального Stars payment finite Plan применил новый `totalGB=1 GiB` и новый expiry, но сохранил старые cumulative counters (~11.6 GiB), поэтому subscription сразу показала 100%, 0 B remaining и inactive. Root cause: paid provisioning обновлял `expiryTime/totalGB/limitIp`, но не начинал новый quota cycle; expiry также считался от `now`, а не от `max(now, current_expiry)`. Finding #317 — **High / release-blocking**;
- ✅ stabilization fix V5-A-007 слит через PR #318 (`ba4a25980ddb185dd5558d9387a8f4fe9cbed1c8`): schema v11 добавляет durable quota-reset journal, finite paid entitlement выполняет one-shot reset без blind replay, target expiry фиксируется durable, active renewal сохраняет остаток оплаченного срока;
- ✅ Low UI finding #314 закрыт тем же PR #318: home/profile status emoji синхронизированы, dynamic Stars plan buttons имеют leading `💎`, `/subscription` использует канонический heading, duplicate `/paysupport` renderer удалён;
- 🔴 controlled production acceptance `v5.0.0-rc.2` остаётся **FAIL** на V5-A-007 до нового immutable baseline; broken-quota state rc.2 сохраняется как historical evidence;
- ✅ `v5.0.0-rc.3` опубликован и развёрнут на production: tag `v5.0.0-rc.3` → SHA `a4e1e9f5c28b54b209ce4a81b23e5d85a2c9f73a`, container `running`, `RestartCount=0`, Bot `5.0.0-rc.3`, Health/DB/3x-ui connectivity `ok`, SQLite schema v11 / `quick_check=ok`;
- ✅ V5-A-007 targeted production retest — **PASS по quota/renewal/idempotent reconcile path**: existing entitlement #1 после migration остался `active/legacy`; новая Stars-покупка создала order #2 / entitlement #2 `active/success`; старые cumulative `11.6 GB` сброшены до `0 B`, новый лимит 1 GiB доступен, expiry продлён ровно от предыдущего срока до `2026-12-07 03:34 MSK`; повторный `reconcile(2)` оставил `starts_at/expires_at/quota_reset_status` без изменений, а уже накопленный после покупки traffic не обнулился — второго quota reset и второго +30 дней не произошло;
- 🟡 uncertain/lost-response quota-reset no-replay остаётся repository-covered regression invariant; production fault injection специально не выполнялся на оплаченной customer state. Полный V5-A-002 failure/restart stage позже должен дать controlled evidence без ручной DB repair/blind replay;
- 🔴 **V5-A-008 / #324 — paid entitlement ≠ фактический VPN-доступ (High / release-blocking):** после успешного rc.3 smoke provider `get_client.enable=False` и `traffic.enable=False` при `Order #2=paid`, `Payment #2=confirmed`, `Entitlement #2=active/success`, будущем expiry и оставшейся квоте. Client Portal показывал `🟢 активна` по одному `users.expiry_time`, тогда как Admin и HTML subscription показывали `⛔ отключён / Неактивна`. До проверки вручную изменялся и восстанавливался срок тестового пользователя: **не доказано**, что отключение вызвано оплатой или provisioning;
- 🔴 **Дополнительный expiry drift:** после ручного изменения `users.expiry_time` и 3x-ui `expiryTime` = `2026-12-07T20:59:59Z`, а `Entitlement #2.expires_at` = `2026-12-07T00:34:29Z` (20ч 25м 30с разницы). Не объявлять это Stars defect без воспроизведения; не исправлять автоматически оплаченную историю;
- ✅ **Fix V5-A-008 / #324 слит через PR #325 (`95231befc9988c47d29150f2084d1a8af8444e41`):** разделить entitlement/period и provider access state, provider-neutral read-only 3x-ui `enable/expiry`, одинаковый customer status в `/start`, профиле и диагностике, `⚪ неизвестно` при outage/expiry drift, no direct XUI in handlers, no automatic enable/unblock, no blind retry; scenario tests и targeted acceptance на **новом immutable RC**, не менять опубликованный rc.3;
- ✅ **Уже проверенные rc.3 результаты (сохраняются как scoped evidence):** deploy tag/SHA/health/SQLite v11; реальный Stars invoice→Order #2 paid/Payment #2 confirmed/Entitlement #2 active/success; finite quota 11.6 GB→0 B; renewal до исходного `2026-12-07 00:34:29 UTC`; повторный reconcile без второго quota reset/продления; duplicate local confirmation `created=False`, ровно 1 payment/1 entitlement; customer UI #314; Stars admin ledger V5-A-006; expired-state presentation V5-A-005; traffic/HWID inventory reads; initial subscription import/VPN connection/browser use reported PASS, но **более поздний read-back показал disabled provider client**, поэтому end-to-end фактический доступ после ручного изменения срока не принят;
- ✅ **`v5.0.0-rc.4` — immutable prerelease опубликован и развёрнут для targeted canary:** release tag `v5.0.0-rc.4` → SHA `d34b76d694a43d3f1d364cc01d9a88bc2b666ee5`, bot SQLite schema v11, pinned 3x-ui OpenAPI `v3.9.0`. Fix V5-A-008 сохраняет provider-neutral read-only `enable/expiryTime` status и explicit expiry drift без automatic unblock/expiry rewrite;
- ✅ **V5-A-008 / #324 — targeted production retest на `v5.0.0-rc.4`: PASS (2026-10-08).** Оператор подтвердил корректное обнаружение `provider.enable=False`, диагностику расхождения local/entitlement/provider expiry и контролируемое восстановление доступа. После обновления subscription VPN-клиент подключился, доступ в интернет работал, а счётчик трафика вырос с **323,1 MB** до **347,6 MB** (**+24,5 MB**). Это закрывает targeted finding о расхождении оплаченного периода и фактического VPN-доступа; исходная причина `enable=False` в `rc.3` не объявляется дефектом Stars без отдельного доказательства. Issue #324 уже `closed/completed` в GitHub;
- 🟡 **Исторический disposition после targeted V5-A-008 на `rc.4` (до refund retest на `rc.5`):** блокировка по V5-A-008 снята только в пределах targeted acceptance, общий v5 production acceptance оставался NOT PASS. На тот момент ещё не были завершены V5-A-001 refund/support, V5-A-002 failure/restart/reconciliation, V5-A-003 abuse/load/soak, ownership/IDOR, rollback и финальная reconciliation. Текущие результаты V5-A-009/V5-A-002 указаны ниже; никаких automatic enable, blind mutation retry или незапрошенных изменений оплаченной customer state. #320 (старый payable invoice) — Low/non-blocking.
- 🔴 **V5-A-009 / #328 — Stars refund admin callback NameError (High / release-blocking, `rc.4`):** production 2026-10-08 при подтверждении refund возник `NameError: run_stars_refund is not defined`. `business_admin.py` вызывает существующий helper `stars_refund.run_stars_refund` без import. Ошибка произошла до вызова helper / записи refund journal / Telegram API mutation в данном callback; фактический provider read-back не выполнялся. V5-A-001 refund и общий acceptance **STOP/FAIL**, до нового immutable RC и targeted production retest не повторять refund. Fix выполняется через PR и CI, без изменений one-shot/unknown semantics;
- ✅ **`v5.0.0-rc.5` выпуск и targeted refund:** fix V5-A-009 / #328 слит через PR #329 (`2ba7decc38a7365107a7b4ab3530bc4aa5671c2b`), release-prep PR #330 после исправления примеров Admin Setup прошёл `test/title=success` и влит (`14042f6dc9d467dc8d0e999eb493f9e1cfc90611`). Release опубликован штатным workflow и развёрнут оператором; scoped PASS refund подтверждён отдельно ниже. Официальный GitHub Status перед merge: Actions/Git Operations/API Requests/Pull Requests operational, unresolved incidents нет.
- ✅ **`rc.4` production smoke 2026-10-08 — scoped результаты:** оператор подтвердил exact deployed tag/SHA `v5.0.0-rc.4` / `d34b76d694a43d3f1d364cc01d9a88bc2b666ee5`, `Container=running`, `RestartCount=0`, `Bot version=5.0.0-rc.4`, `Health/DB/3x-ui TCP connectivity=ok`, Docker subnet `172.19.0.0/16`. Отдельный read-only SQLite check: schema v11, 11 migration rows все `success`, `entitlements.quota_reset_status` имеется. UI: V5-A-006 Stars ledger открылся, payment detail по тестовому Payment #1 показал `confirmed`, сумму 1 XTR, refund отсутствует; первый шаг refund показал предупреждение необратимости/one-shot; #314 ручной customer UI smoke на `/start`, `Профиль`, `Моя подписка`, `Купить / продлить` подтвердил согласованные status emoji, heading, `💎` Stars-тарифы (без нового платежа). **Финальное подтверждение refund — V5-A-009 FAIL (`NameError`), внешний возврат этим callback не выполнен; общий acceptance NOT PASS**;
- ⏳ **V5-A-005 — дополнительный expiry smoke перенесён на 2026-10-10 00:00 МСК (2026-10-09 21:00 UTC):** оператор перенёс read-only проверку тестового аккаунта с естественным истечением подписки. Результат `PENDING`; SQL/3x-ui/entitlement сроки не менять. По наступлении момента сверить `/start`, `Профиль`, `Моя подписка`, локальный entitlement и read-only 3x-ui status, зафиксировать evidence отдельно. Прежний targeted PASS на rc.2 сохраняется. Ранее targeted V5-A-005 PASS на rc.2 сохраняется как отдельное evidence;
- ✅ **V5-A-009 / #328 targeted production refund retest — PASS на `v5.0.0-rc.5`, 2026-10-08:** operator deploy tag/SHA `v5.0.0-rc.5` / `14042f6dc9d467dc8d0e999eb493f9e1cfc90611`, container running, `RestartCount=0`, Bot version совпадает, Health/DB/3x-ui TCP connectivity `ok`. Перед mutation read-only SQLite: confirmed test payment на **1 XTR**, `stars_refund_operations` ровно **0**. После отдельного согласия оператора один возврат через двухшаговый Admin UI: бот показал `✅ Возврат подтверждён Telegram.`, Telegram подтвердил возврат **1 ⭐**. Итоговый read-only SQLite: `commerce_payments.status=refunded`, ровно **1** refund journal row, `status=success`, `Consistent=True`. `NameError` на `rc.5` не повторился; issue #328 закрыт `completed`. **Это scoped PASS, не общий PASS v5**: live timeout/`unknown`/no-retry, entitlement/VPN revocation и остальные acceptance stages этим тестом не покрыты;
- ✅ **V5-A-002 — read-only commerce/recovery preflight на deployed `v5.0.0-rc.5`, 2026-10-08: scoped PASS, не финальный V5-A-002.** Оператор выполнил только read-only SQLite агрегаты: `commerce_orders`: 2 × `paid`; `commerce_payments`: 1 × `confirmed`, 1 × `refunded`; `payment_webhook_events`: 2 × `applied`; `entitlements`: 2 × `active`; `quota_reset_status`: 1 × `legacy`, 1 × `success`; `stars_refund_operations`: 1 × `success`; `Recoverable payment events: 0`. Нет наблюдаемых незавершённых платежных событий, но отсутствие данных `unknown` в снимке не доказывает no-retry после сбоя;
- ✅ **V5-A-002 — read-only Order → Payment → Entitlement integrity на `rc.5`, 2026-10-08: scoped PASS.** `Order #1 paid → Payment #1 refunded → Entitlement #1 active/legacy`; `Order #2 paid → Payment #2 confirmed → Entitlement #2 active/success`. Счётчики: orphan payments=0, orphan entitlements=0, duplicate entitlements per order=0, paid orders without entitlement=0. Возврат Stars сам не отзывает entitlement/VPN, а `legacy` не переписывается в `success`; это объяснимые состояния, не доказательство полной provider-side reconciliation. Не проверялись live duplicate/delayed payment delivery, restart/fault injection, provider outage, quota-reset unknown/no-blind-replay, IDOR, rollback и soak; DB/entitlement/3x-ui mutations не выполнялись;
- 🟡 **`v5.0.0-rc.6` — пересобранный release-prep после #339:** первый CI PR #339 показал 2 ошибки формата Admin Setup, fix перенесён в отдельную ветку на актуальном `main`; V5-A-002 read-only evidence и plans #333/#334/#336 сохранены. Текущий этап — required CI → squash merge → стандартная GitHub release публикация; production на `rc.5` до отдельного операторского deploy;
- 🟡 **V5-A-010 / #333 — refunded terminal-state, High code finding:** на `rc.5` из code review обнаружено, что duplicate/delayed `successful_payment` после возврата мог перевести `refunded → confirmed`; live exploit/replay в production **не выполнялся**. Исправлено в `main` через [PR #335](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/335) (`4b66f3ce48afbe3bdd9c979a633825bacd13d55c`), обязательные `test/title` PASS, added regression `payment → refund → duplicate` сохраняет refunded и refund journal. Issue #333 остаётся OPEN / требуется immutable `rc.6` и безопасная targeted валидация; production на `rc.5` пока **не защищён новым кодом**, реальные события повторно не отправлять;
- 🟡 **#334 — платёжная статистика Stars (UI finding `rc.5`):** `/admin → Платежи` показывал `Всего: 0` (только legacy `payments`) при 2 Stars commerce payments (1 `confirmed`, 1 `refunded`). Исправлено в `main` через PR #335 (`4b66f3ce48afbe3bdd9c979a633825bacd13d55c`) с required CI PASS: раздельная read-only сводка Stars/XTR и `📒 Ручные платежи (учёт)`, no XTR/RUB mixing, UI/DB tests. Issue #334 остаётся OPEN; **production UI retest NOT RUN** до публикации/deploy `rc.6`;
- ⬜ **Оставшиеся gates после scoped V5-A-002 preflight/reconciliation PASS:** V5-A-001 полный commerce/support (включая политику refund/entitlement), V5-A-002 controlled duplicate/delayed payment, failure/restart/quota reset unknown-no-replay, provider outage и реальный recovery, V5-A-003 abuse/load/soak, ownership/IDOR, rollback/kill switches, provider/client/VPN state cross-check, финальная reconciliation и deferred natural expiry V5-A-005 (2026-10-09). Не заявлять общий PASS, не снимать allowlist и не публиковать stable `v5.0.0`;
- 🟡 параллельно найден Low/non-blocking UX finding #320: paid native Stars invoice остаётся визуально payable, хотя backend pre-checkout для `order=paid` fail-closed;
- ⬜ отдельный non-blocking v5.x roadmap item: добавить в `/admin → Платежи` read-only Stars Orders view для `created/awaiting_payment` orders и корреляции `Order → Payment → Entitlement`; задача не входит в `rc.3` stabilization и не блокирует targeted retest;
- ⬜ отдельный non-blocking v5.x customer self-service item: сделать `📱 Устройства` компактным (`N/limit`, короткий list/detail UX) и разрешить двухшаговое удаление ровно одного собственного HWID через provider-neutral ownership-checked one-shot flow с no-retry/unknown semantics и bounded anti-churn rate limit; текущий `rc.3` acceptance этим не блокируется;
- ⬜ stable `v5.0.0` публикуется только после PASS acceptance без unresolved Critical/High и без необъяснимых payment/entitlement/provisioning inconsistencies;
- ⬜ broad public access / снятие pilot allowlist выполняется только после успешного controlled rollout; stable tag сам по себе allowlist не снимает.

Актуальная release sequence: **`v5.0.0-rc.1` published/deployed → FAIL (V5-A-005/V5-A-006) → fixes #312 → `rc.2` published/deployed → targeted V5-A-005/V5-A-006 PASS → V5-A-007 FAIL (#317) → fix #318 → `rc.3` published/deployed → V5-A-007 targeted PASS → STOP/FAIL V5-A-008 (#324) → fix #325 → immutable `v5.0.0-rc.4` published/deployed → V5-A-008 targeted production retest PASS (2026-10-08) → V5-A-009 Stars refund FAIL на rc.4 (#328) → fix #329 merged / release-prep rc.5 → immutable rc.5 published/deployed / V5-A-009 targeted refund PASS (#328 closed) → read-only V5-A-002 commerce reconciliation PASS на rc.5 → #333/#334 identified, fix PR #335 merged/CI PASS → rc.6 release-prep PR #339 failed/stale head → пересобранный release-prep от актуального main (required CI pending) → оставшиеся V5-A-001/V5-A-002/V5-A-003, ownership/rollback/reconciliation/soak → общий production acceptance PASS → stable `v5.0.0` → постепенное расширение cohort**.

## План: переключатели Клиентский портал / Stars и ревизия системных настроек (2026-10-08)

**Статус на 2026-10-09: 🟡 Реализовано в `main`, но ещё не опубликовано и не принято в production.** [#342](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/342) слит через [PR #368](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/368), нулевые лимиты [#343](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/343) через [PR #367](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/367). Эти изменения отсутствуют в `v5.0.0-rc.7`, acceptance не выполнен, pilot allowlist не расширять. Приоритет — до широкого customer rollout; решение о включении в текущий v5.0 feature scope принимается отдельно от уже идущего V5-A-001…A-003.

### Два отдельных Owner-only переключателя в /admin → Система → Настройки

1. **👤 Клиентский портал (/start):** оперативно разрешать/запрещать customer UI, сохраняя независимый доступ к `/admin`, существующие entitlements и фактический VPN в 3x-ui.
2. **⭐ Приём новых Stars-платежей:** оперативно запрещать новые invoices и pre-checkout, включая ранее созданные неоплаченные invoices. `successful_payment`, уже доставленный после оплаты, продолжает проходить аутентифицированный journal/entitlement lifecycle независимо от переключателей. Никаких новых платежных событий/refunds для smoke ранее подтверждённых операций.

Предлагаемая архитектура: проверяемые при каждом relevant customer entrypoint persistent bool overrides в существующем `runtime_settings` (не менять `.env` из Telegram, не перезапускать Docker и не выдавать host shell). **Внешний `.env=false` — неотменяемый emergency veto:** effective enable требует одновременно разрешения `.env`, runtime override и существующего pilot allowlist. `portal=false` также запрещает новые invoices/precheckout независимо от payment override. При DB read error — fail-closed, не показывать неуверенное состояние как `enabled`. Owner/private-chat RBAC + двухшаговое подтверждение, защита от stale callback, отдельный audit event, visibility реального effective status/source/reason и persistence после restart. Проверки включают env/DB precedence, concurrency, double-toggle, access isolation, payment idempotency, отсутствие paid entitlement/provider changes и возможность аварийного возврата через host config. Детальный scope и критерии принятия — issue #342.

### Аудит существующего /admin → Система → Настройки на rc.6

| Текущий пункт | Фактическая область применения | Решение |
| --- | --- | --- |
| 🗓 Дней пробного доступа (`trial_days`) | Runtime override при создании пробного пользователя в `advanced_users.py` | Оставить; уточнить, что меняет только новые trial accounts, не продлевает существующих |
| 📦 Трафик пробного доступа (`trial_traffic_gb`) | Runtime override при создании пробного пользователя | Оставить; проверить документированную семантику `0` и граничных значений (#343), не утверждать дефект без воспроизведения |
| 📱 Лимит IP пробного доступа (`trial_ip_limit`) | Runtime override при создании пробного пользователя | Оставить; проверить семантику `0`, валидность downstream 3x-ui/доступа (#343) |
| 💱 Валюта по умолчанию (`default_currency`) | Fallback при ручном добавлении записи `payments` в `business_admin.py`; Stars/XTR независим | Уточнить название UI как «Валюта ручных платежей», исключив двусмысленность с Stars и ценами планов |
| 💾 Резервные копии, 🔐 Проверка TLS, 🖥 Master-сервер | Read-only отображение конфигурации на экране настроек | Оставить только для просмотра; управление backups — в отдельном защищённом разделе, TLS/secrets/host config не редактировать в Telegram |

Полезные **read-only** сведения рядом с двумя переключателями: число записей pilot allowlist (без раскрытия Telegram IDs), лимит customer запросов и окно, источник и причина текущего effective disabled/enabled состояния, краткая инструкция по emergency rollback. Не добавлять произвольный редактор `.env`/secret values, global TLS toggle, destructive control 3x-ui, увеличение allowlist без отдельного ownership/security workflow или однокнопочные refund/reconcile retries.

Текущая production-валидация `rc.6` от оператора (2026-10-08) — только **scoped evidence**, не общий PASS: exact SHA `b9555d685603e82a330e053e3187ac4368231090`, Health/DB/3x-ui ok и SQLite schema v11; Stars summary отдельно XTR/ручной журнал; по read-only SQLite два paid orders, один confirmed/один refunded Stars payment, два applied events, два active entitlement, quota reset `legacy=1/success=1`, один successful refund. После обычного bot restart и контролируемого короткого `x-ui.service` outage/recovery счётчики неизменны, `/admin` доступен, customer provider outage корректно даёт unknown/temporary unavailable; sandboxed offline regression suite на deployed code — `31 tests ... OK`. Payment kill-switch через `.env=false` и последующий возврат `true` оператором отмечены PASS (без фактического provider-authorized платежа при disabled). Это **не** подтверждает live interrupted paid provisioning, uncertain quota reset/no-blind-replay, полноценный V5-A-002, V5-A-003, ownership/rollback портал/soak или общий v5 production acceptance. Stable `v5.0.0` и снятие pilot allowlist до общего PASS запрещены.

## Запланировано: персональный сброс клиентской сессии (2026-10-08)

**⬜ TODO / не реализовано в rc.6.** Отслеживание: [#345](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/345). Добавить в `/admin → Пользователи → карточка пользователя` Owner-only действие **«🔄 Сбросить клиентскую сессию»**: целевой in-memory rate-limit bucket, применимый временный customer dialog/FSM state, confirmation + RBAC + audit, без глобального Docker restart. Операция не меняет 3x-ui, подписку, платежи, entitlement, devices, allowlist, не сбрасывает ограничения Telegram transport. Реализация обязана работать в **живом процессе** бота, а не в отдельном `docker compose exec python`. Acceptance: два пользователя из pilot, isolation A/B, ACL/forged callback, audit, отсутствие финансовых/provider mutation. Полный scope — issue #345.

## Фактические результаты rc.6 production smoke (2026-10-08; scoped, НЕ общий PASS)

Release `v5.0.0-rc.6`, SHA `b9555d685603e82a330e053e3187ac4368231090`, Master, pilot allowlist не снят.

| Проверка | Статус | Основание / ограничения |
| --- | --- | --- |
| Container restart, короткая управляемая недоступность 3x-ui/recovery | **PASS (scoped)** | Health/DB/3x-ui OK, `RestartCount=0`, финансовые счётчики не изменились; не доказывает interrupted paid provisioning / unknown traffic reset |
| Offline deterministic regression на развёрнутом коде | **PASS (31/31)** | Отдельный изолированный/no-network процесс; не live payment/load |
| Stars payment kill switch `.env CLIENT_PAYMENT_ACCEPTANCE_ENABLED=false` | **PASS (UI/config scoped)** | Старт и `/admin` работают, новые покупки блокируются, вернули `true`; ранее созданный invoice precheckout provider-side этим запуском не проверялся |
| Client Portal kill switch `.env CLIENT_PORTAL_ENABLED=false` при Stars=false | **PASS (UI/config scoped)** | `/start` блокируется, `/admin` работает; восстановлены оба `true/true`; pilot allowlist настроен |
| Recovery и reconciliation после двух kill switches | **PASS (scoped)** | `Health: ok`, `DB: ok`, 3x-ui connected, SQLite quick_check ok; `Orders paid=2; Payments confirmed=1/refunded=1; Events applied=2; Entitlements active=2; Quota reset legacy=1/success=1; Refund success=1`; `/start`, планы, `/admin` доступны |
| V5-A-003 customer rate-limit алгоритм | **PASS (offline simulated)** | Фактическая конфигурация `30 requests/60s`; per-user isolation, burst rejection и sliding-window recovery |
| V5-A-003 live Telegram burst | **BLOCKED / INVESTIGATING, НЕ PASS** | После серии `/start` Telegram-клиенты test user A перестали нормально отправлять/синхронизировать `/start` и `/start diag`; `/paysupport`/customer callback у A и `/start` у B работают. Master healthy; processed updates <=533ms, polling/network/429/timeout/handler exceptions = 0; задержка доставки/ограничение Telegram — гипотеза, точная причина не установлена. Повторный burst остановлен |
| Ownership / isolation — A/B, ordinary customer flows | **PASS (scoped live UI)** | 2 pilot identities на deployed rc.6: A/B видят свои профиль и трафик; подписка и QR у каждого свои; устройства: A — свои, B — пусто (нет чужих); B `/admin` — отказ. Нет наблюдаемой утечки в обычных UI-paths; B с пустым HWID-list не доказывает все cross-resource cases |
| Ownership — Stars order amount/owner enforcement | **PASS (offline 1/1)** | Изолированный `tests/test_v5_telegram_stars.py::test_stars_confirmation_rejects_wrong_owner_or_amount_without_mutation`: чужой Telegram ID и изменённая сумма отклоняются; нет `commerce_payments` mutation; order остаётся `awaiting_payment`. Источник: image rc.6 + tests read-only mount, no network / no production data |
| Admin callback RBAC / privilege boundary | **PASS (offline + scoped live)** | B `/admin` — отказ; `tests/test_rbac_privileges.py` — `5 tests OK`; отдельно прямой вызов `authorize_callback()` с 6 fake cases — `6/6 PASS`: обычный клиент отвергнут для admin home/Owner action/admin QR чужого пользователя, read_only→Owner rejected, неизвестный callback fail-closed, Owner valid allowed. Нет live forged callback evidence |
| Ownership — forged client callbacks and cross-account IDOR | **TODO (not full PASS)** | Не проводилась Telegram E2E отправка forged payload, в т. ч. попытка получить чужую customer subscription URL/QR; отсутствует прямой server-side cross-user read test для каждого customer resource. UI и RBAC проверки не подменяют full attack validation |
| V5-A-003: негативные/граничные проверки прокси, повторные callbacks, параллелизм и длительная нагрузка | **PASS (offline 5/5), live burst BLOCKED, soak TODO** | На образе rc.6 offline без сети, только чтение, 5 тестов: неизвестный `sub_id`, traversal, чрезмерный размер ответа/Content-Length, занятые upstream-слоты (503) — **PASS** (оператор, 08.10.2026 21:24 UTC). В production БД и Telegram изменений нет. Два снимка Master через 16m05s (21:33:10 и 21:49:15 UTC): running, 0 рестартов, OOMKilled=false, CPU 0%, MEM 212.4 MiB/1.757 GiB (11.80%), PIDS=6, роста за короткий интервал нет; полноценная нагрузка/soak **NOT TESTED**. По журналу Admin: ежедневный backup включён на 05:00 МСК, прошлый `backup.daily` 08.10 05:00 МСК за 2.2s; ручной backup в 18:56 за 1.5s, offsite в 18:57 за 0.8s (админский запуск), reconciliation пользователей 23.09 11:56 за 0.3s. Журнал истории — scoped PASS, исполнение следующих запланированных задач не проверено. Диагностика пилота B дважды через ~10s — 2/2 PASS нормального UI, не rate-limit test. Некорректные callback `plan_cb`/`terms_accept_cb` (включая 5000 цифр) — 4/4 отклонены без заказа/платежа/мутации; изолированный offline PASS, не реальный transport/ownership Stars. Остаток: live invalid callbacks, front-door load, длительный мониторинг и backup по расписанию. Telegram `/start` burst оставлен BLOCKED, не повторять |
| V5-A-002: полная матрица отказов и восстановления | **PASS (3 целевых offline-теста), остальные сценарии TODO** | В rc.6 offline на временной SQLite тест повторного Stars charge подтвердил 1 payment, 1 entitlement, 1 provider event, `Ran 1 test ... OK` (08.10 22:01 UTC). Тест неопределённого ответа 3x-ui quota reset оставил entitlement `provisioning`, journal `unknown`, повторная сверка вызвала `ProvisioningUnknown`, без повторной отправки (`sync_calls=1`, `reset_calls=1`), `Ran 1 test ... OK` (22:05 UTC). Тест восстановления запоздалого аутентифицированного платежа после пересоздания CommerceService (без настоящего Docker restart): ранее `failed/payment_not_found`, новый payment найден, журнал `applied`, paid order, 1 entitlement, повторная сверка checked=0; `Ran 1 test ... OK` (22:08 UTC). Сеть и production не затрагивались. Полные реальные delayed/duplicate Telegram payments, in-flight/restart, lost-response provider и общая матрица **PENDING**, общий V5-A-002 не PASS |

**Регрессионный пакет rc.6 offline (08.10.2026 22:17 UTC) — PASS 34/34:** неизменный deployed-образ rc.6, тесты в режиме только чтения и без сети, временная SQLite, подменённые зависимости провайдера: `test_commerce_foundation.py` 19, `test_v5_telegram_stars.py` 7, `test_v5_customer_service_boundary.py` 4, `test_v5_launch_readiness.py` 4; `Ran 34 tests in 11.051s`, `OK`, 0 ошибок/сбоев. Проверены оплаты/возвраты, квоты, безопасность Stars, разграничение клиентских сервисов и переключатели запуска. **Не является полным провайдерским/Telegram E2E, реальной матрицей отказов или длительной нагрузкой.**

**Локальная окончательная сверка SQLite только на чтение (08.10.2026 22:14 UTC, rc.6 Master) — PASS (только БД):** `PRAGMA quick_check=ok`; Orders `paid=2`, Payments `confirmed=1/refunded=1`, Events `applied=2`, Entitlements `active=2`, quota reset `legacy=1/success=1`, Stars refunds `success=1`. Все девять проверок целостности нулевые: нет платежей/доступов без соответствующей записи, дубликатов доступа, paid без entitlement, несоответствия владельца, суммы/валюты, подтверждения/возврата по неоплаченному заказу, orphan refund или успешного возврата без статуса refunded. `unapplied_events`, `unfinished_entitlements`, `uncertain_quota_resets`, `unfinished_refunds` — все 0. SQLite `mode=ro`, `query_only=ON`, `BEGIN`; без секретов. Сверка UI ниже — operator-reported, полная независимая сверка 3x-ui/клиента и провайдера ещё PENDING, общий acceptance **NOT PASS**.

**Сопоставление A/B Admin ↔ Customer UI ↔ 3x-ui adapter (08.10.2026 22:26 UTC) — PASS (ограниченный, operator-reported):** оператор подтвердил «везде ок» после read-only пути `/admin → 👥 Пользователи → 🔎 Поиск → A/B → карточка → 🌐 Доступ` и клиентских экранов `👤 Профиль`/`📊 Трафик`. Статус, срок, трафик и текущие/целевые Inbounds совпали по сообщению оператора. Точные числа/скриншоты не представлены — не выводить их самостоятельно. Чтение карточек через адаптер бота не является независимой проверкой VPN transport или полной провайдерской сверкой; изменяющие действия не выполнялись.

**Реальный VPN end-to-end пилотов A/B (08.10.2026 22:29–22:30 UTC) — PASS (operator-reported):** каждый участник обновил свою существующую подписку в VPN-клиенте, подключился к доступной Node и открыл обычный интернет-сайт. Установка, перенастройка и изменение 3x-ui не выполнялись. Это ограниченный smoke клиентского data-plane; исходные ссылки, ключи, измерения Node и артефакты не предоставлялись. Результат не доказывает отказоустойчивость платежей, автоматическую сверку, forged callbacks/IDOR, burst rate-limit или длительный запуск jobs.

### Сводный журнал проверок rc.6 — 2026-10-09, включая контролируемый rollback

**Environment:** Master `/opt/3xui-bot/3xui-telegram-bot`, immutable deployed `v5.0.0-rc.6` / SHA `b9555d685603e82a330e053e3187ac4368231090`. Ограниченный pilot allowlist сохранён. Все результаты ниже относятся к указанному immutable runtime, кроме прямо обозначенного исторического теста refund на rc.5. Время наблюдений — UTC, если не указано MSK. Проверки, повторявшиеся индивидуально и внутри batch, **не суммируются как уникальные тесты**.

| Контроль / evidence | Результат | Граница подтверждения |
| --- | --- | --- |
| Deploy и health: версионный read-back, schema v11, SQLite `quick_check=ok`, 3x-ui connection; controlled container restart / short 3x-ui outage | **PASS (scoped)** | Production `APP_VERSION=5.0.0-rc.6`, container `running`, `RestartCount=0`; recovery без изменения финансовых счётчиков. TCP/provider connectivity и ограниченный outage — не full provisioning failure/restart canary |
| Исходные kill switches и восстановление | **PASS (prior scoped live UI/config)** | Ранее `CLIENT_PAYMENT_ACCEPTANCE_ENABLED=false` блокировал новые клиентские покупки при доступном `/admin`; `CLIENT_PORTAL_ENABLED=false` блокировал customer `/start` при доступном `/admin`; исходные `true/true` восстановлены, health/DB/3x-ui OK. Уже доставленный `successful_payment` при false и paid pre-checkout тогда не проверялись; это не полный rollback |
| Изолированные регрессии на коде контейнера rc.6 | **PASS: 31/31 и отдельный batch 34/34** | `34/34`: `test_commerce_foundation.py` 19, `test_v5_telegram_stars.py` 7, `test_v5_customer_service_boundary.py` 4, `test_v5_launch_readiness.py` 4; `Ran 34 tests in 11.051s; OK; 0 failures/errors`. Отдельные прежние `31 tests OK`; no-network, временная SQLite, не live payment/provider |
| Привилегии/изоляция и защитные callback-проверки | **PASS (scoped)** | A/B свои профиль, трафик, ссылки подписки и QR; A видит свои HWID, B — пусто; B `/admin` — отказ. `test_rbac_privileges.py` 5/5; прямой `authorize_callback()` 6/6 на synthetic IDs; owner/amount mismatch Stars — 1/1; невалидные/длинные `client:plan` и `client:terms` — 4/4 без invoice/order. Полный forged customer IDOR и Telegram E2E callback abuse не тестировались |
| Subscription Proxy, rate limiting и краткосрочные ресурсы | **PASS (offline/scoped), soak TODO** | Offline 5/5: invalid sub ID, traversal, oversized body/Content-Length, saturated upstream slots=503. Rate limiter 30/60 sec per-user/recovery PASS offline; два чтения ресурсов за 16m05s: 212.4 MiB (11.80%), 6 PIDs, 0 restarts/OOM, CPU 0%. B `🛠 Проверить подписку` — 2/2 с паузой. Live repeated `/start` A остаётся BLOCKED/INVESTIGATING, без повторного burst |
| Фоновые задания | **PASS (history visibility, scoped)** | В `/admin → Система → Задания`: расписание enabled, успешный last scheduled backup 2026-10-08 05:00 MSK (2.2s), manual backup 18:56 MSK (1.5s), offsite admin 18:57 MSK (0.8s), last reconciliation 2026-09-23. Запланированный запуск 2026-10-09 05:00 MSK **пока не перепроверен**; полного scheduled-jobs soak нет |
| Commerce failure-model (дубли/потерянный ответ) | **PASS (focused offline), broader TODO** | Stars charge replay: 1/1, one payment/entitlement/event. Неопределённый quota-reset: 1/1, `provisioning/unknown`, нет blind retry. Delayed authenticated event после пересоздания CommerceService: 1/1, recovered exactly once. Это offline имитации, не реальные провайдерские отказы |
| Read-only локальная reconciliation до нового платежа, 2026-10-08 22:14 UTC | **PASS (SQLite snapshot)** | `quick_check=ok`; 2 paid orders, payments 1 confirmed/1 refunded, events 2 applied, entitlements 2 active, quota 1 legacy/1 success, 1 successful Stars refund; 9 structural integrity checks и 4 pending/unknown checks — все нули. **Это датированный срез до заказа #3**, не текущие агрегаты |
| Admin ↔ customer / реальный VPN, пилот A и B, 2026-10-08 | **PASS (operator-reported, scoped)** | Срок, статус, трафик и Inbounds совпали по чтению из `/admin` и кабинетов A/B. Оба пользователя обновили subscription в VPN-клиенте, подключились и открыли сайт. После новой покупки #3 отдельный VPN-client retest B успешно проведён 2026-10-09 11:17 UTC (отдельная строка ниже) |
| **Stars happy path на rc.6, B, 2026-10-09 08:35–08:51 UTC** | **PASS (live payment + entitlement/quota)** | До покупки B: срок 2026-12-07 03:34 MSK, использовано 765.6 MiB из 1 GiB, тариф изменён оператором на `Смок` (1 XTR, 30 дней, 1 GiB, IP limit 1, server group 1). Invoice 1 XTR и Telegram successful-payment UI подтверждены. Read-only SQLite: **order #3** `paid` / `amount_minor=1` / `XTR`; **ровно 1** payment `confirmed`, 1 event `applied`, 1 entitlement по order #3; **entitlement #4** `active`, `quota_reset_status=success`, expiry **2027-01-06 03:34 MSK** (+30 дней). B отдельно подтвердил сброс накопленного лимита/трафика и срок +30; точные post-reset счётчики не приложены. **Не тестировались** реальный повтор Telegram delivery и refund нового платежа; post-payment VPN-connection retest B подтверждён отдельно ниже |
| Исторический реальный Stars refund / поддержку | **PASS (rc.5, не повторялся на rc.6)** | 1 XTR refund подтверждён в Telegram и `stars_refund_operations.status=success`, `commerce_payments.status=refunded`; на rc.6 сохранён в read-only journal (до нового платежа). Unknown/refund timeout и entitlement/VPN revocation не проверялись |
| **Preflight перед следующим rollback, 2026-10-09 10:18 UTC** | **PASS (read-only)** | Runtime portal `True`, payments `True`; в реальном `.env` оба `true`, совпадают с runtime. `commerce_payments.pending/unknown=0`, `entitlements.pending/provisioning=0`, `payment_webhook_events.received/failed=0`, `stars_refund_operations.in_flight/unknown=0`. На момент preflight новый rollback ещё не выполнялся; итог отдельным пунктом ниже |
| **V5 rollback: payment switch OFF → customer denial/admin OK → restore, 2026-10-09 10:24–10:30 UTC** | **PASS (scoped live UI + runtime/health recovery)** | После read-only preflight сохранена защищённая копия исходного `.env`; только `CLIENT_PAYMENT_ACCEPTANCE_ENABLED` временно установлен в `false`, сервис `bot` пересоздан через `docker compose up -d --no-deps --no-build --force-recreate bot` без новой сборки. Оператор подтвердил `Container ... Started`, сообщение customer `Приём новых платежей временно отключён.`, доступность `/admin`. Затем исходный `.env` восстановлен из копии после сравнения содержимого; тот же сервис пересоздан без сборки, `/healthz=ok` (проверка скриптом), runtime `Version: 5.0.0-rc.6`, `Client portal: True`, `Payment acceptance: True`, `ROLLBACK_RESTORED_PASS`. **Нет второго платежа/Stars mutation**, provider-side pre-checkout уже выданного invoice и успешный payment delivery при OFF **НЕ проверены**. Временная секретосодержащая резервная копия `.env` в `/var/tmp` после rollback **удалена** (operator, 2026-10-09 11:09 UTC): перед удалением побайтовое сравнение с рабочим `.env` (`cmp -s`), подтверждение обоих `true`; вывод `TEMP_ENV_BACKUP_REMOVED_PASS` и `Active .env preserved; portal/payments=true`. Удалён только exact временный файл, рабочий `.env` сохранён |
| **Финальная read-only SQLite reconciliation после Stars order #3 и rollback, 2026-10-09 11:11 UTC** | **PASS (local DB/runtime only; cross-system TODO)** | Оператор на Master выполнил SQLite `mode=ro` + `PRAGMA query_only=ON`, `BEGIN`: runtime `5.0.0-rc.6`, `Portal / payments: True / True`, `PRAGMA quick_check=ok`; **order #3** `paid / 1 XTR`, **ровно 1** payment `confirmed` и **1** event `applied`, **entitlement #4** `order_id=3 / active / quota_reset_status=success / expires_at=1799195669` (= **2027-01-06 03:34 MSK**); скрипт также проверил совпадение owner/plan с профилем и локального expiry с entitlement. **13/13** integrity/pending checks = `0`: orphan payments/entitlements, duplicate entitlements, paid_without_entitlement, owner mismatch, amount/currency mismatch, confirmed/refunded on unpaid order, orphan refunds, successful refund mismatch, unprocessed events, unfinished entitlements, uncertain quota resets, unfinished refunds. Итог `POST_PAYMENT_RECONCILIATION: PASS`. Это доказательство сохранённого локального состояния **после двух Compose recreate** (OFF → ON), не независимая проверка реальных 3x-ui/provider counters, Inbounds и post-payment VPN |
| **B: VPN end-to-end после Stars order #3 и двух Compose recreate (payment OFF → ON), 2026-10-09 11:17 UTC** | **PASS (live client data plane, operator-reported, scoped)** | B обновил существующую подписку в VPN-клиенте, успешно подключился к VPN и открыл обычный сайт. Результат подтверждён пользователем после локального `POST_PAYMENT_RECONCILIATION: PASS`, возвращённых `CLIENT_PORTAL_ENABLED=true` / `CLIENT_PAYMENT_ACCEPTANCE_ENABLED=true` и пересоздания контейнера на immutable rc.6. Это фактический успешный доступ клиента **после оплаты и rollback**, но не независимый read-only аудит 3x-ui inbound membership/remote quota/expiry, не controlled provider-delivery failure и не длительный soak; сырые URL/ключи/другие секреты не запрашивались |
| Отдельный UX-fix Stars invoice title | **PR #347 CI PASS, NOT DEPLOYED** | Название бота вместо названия тарифа в invoice — `fix: показывать название бота в заголовке счёта Stars`. Python checks и повторные PR conventions PASS; PR открыт, runtime rc.6 и уже выставленный invoice не менялись |

**Оставшиеся обязательные gates (НЕ PASS):** полный V5-A-002 failure/restart/in-flight/unknown провайдерский сценарий; `successful_payment` после выключения новых оплат и live pre-checkout отказ для уже полученного invoice (поэтому **full rollback acceptance по runbook ещё не PASS**, несмотря на scoped switch/recovery PASS); forged customer callback / cross-account IDOR; Telegram `/start` delivery anomaly (issue #345 не устраняет причину Telegram transport); front-door concurrency/load/длительный soak с новым scheduled backup/restart; финальная **межсистемная** reconciliation **после** order #3 с независимым чтением реальных 3x-ui/provider Inbounds, expiry и traffic (локальная SQLite reconciliation уже PASS); отложенное естественное истечение V5-A-005 и historical acceptance report. Ни stable `v5.0.0`, ни расширение pilot allowlist пока не разрешены.

**Текущий disposition 2026-10-09:** **v5 production acceptance = NOT PASS (много scoped PASS)**. Контролируемый payment switch OFF → клиентский отказ / доступность Admin → восстановление `true/true` / health на rc.6 проведён и подтверждён (scoped PASS). Дальше — отдельно запланировать безопасные provider pre-checkout и delayed successful-payment сценарии без повторной покупки, независимый read-only 3x-ui/provider cross-check после локальной reconciliation order #3 и soak; не смешивать failure canary с реальным оплачиваемым тестом.


**Уточнение после canary (2026-10-09 05:00 MSK, read-only evidence):** scheduled `backup.daily` job #92 ошибочно сообщил `success` для Full Backup с невалидным/пустым Master `x-ui.db`; следом `backup.offsite` job #93 завершился `failed` (`Full Backup failed deep validation: x-ui.db: not SQLite3`). Ранее записанные результаты «Фоновые задания — PASS (history visibility, scoped)» относятся только к проверкам *до* аварии 9 октября и **не являются PASS scheduled backup на rc.6**. Root-cause/fixes: [#348](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/348)/[PR #350](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/350), [#349](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/349)/[PR #351](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/351). Off-site correctly refused invalid archive; текущий overall v5 acceptance **NOT PASS**. Исправления пока в Draft PR, не слиты, не опубликованы и не развёрнуты. Требуется новый immutable RC и verified local/manual/scheduled/off-site/DR round trip; старый архив от 9 октября не считать пригодным recovery copy.

## Gate контролируемого запуска v5.0

После успешного v5 launch audit публичный Client Portal не открывается сразу всему потоку пользователей. Перед широким запуском выполняется отдельный controlled rollout / production acceptance gate.

Минимальный порядок:

1. **Internal acceptance** — Owner/admin test accounts проходят полный customer lifecycle в production-like/production окружении без специальных обходных путей.
2. **Small canary cohort** — доступ открывается ограниченной группе реальных test users через явный allowlist/feature flag; размер cohort остаётся небольшим и управляемым.
3. **Commerce canary** — минимум несколько реальных или provider-approved test payment scenarios проходят цепочку order → provider event → entitlement → provisioning → subscription без ручной правки БД.
4. **Failure canary** — контролируемо проверяются declined/failed payment, delayed webhook, duplicate webhook, temporary provisioning failure, node unavailable, restart бота во время background/reconcile operation и recovery после него.
5. **Ownership/isolation check** — отдельные тестовые аккаунты пытаются открыть чужие callbacks/resources/subscription context; backend должен fail-closed независимо от callback payload.
6. **Abuse/resource check** — проверяются rate limits, repeated callbacks, command spam, oversized/invalid input, monitoring/diagnostics quotas и отсутствие unbounded jobs/queues.
7. **Observability/support readiness** — оператор видит payment/provisioning failures, correlation IDs, audit/job history и понятный recovery path; support не требует доступа к shell/DB для типовых случаев.
8. **Rollback/disable path** — Client Portal и payment acceptance можно быстро выключить независимыми `CLIENT_PORTAL_ENABLED` / `CLIENT_PAYMENT_ACCEPTANCE_ENABLED` без отключения Admin Control Plane; уже полученный `successful_payment` всё равно фиксируется локально, чтобы не потерять подтверждённую оплату.
9. **Data/reconciliation check** — после canary выполняется сверка orders, payments, entitlements, provisioning state и 3x-ui clients; нет orphaned/duplicate resources или необъяснимых state mismatches.
10. **Soak period** — canary работает достаточное время для прохождения scheduled jobs, expiry/renewal/monitoring циклов и хотя бы одного restart/deploy cycle без новых release-blocking findings.

Критерий выхода из gate:

- нет unresolved Critical/High findings;
- нет необъяснимых payment/entitlement/provisioning inconsistencies;
- error/retry/recovery paths проверены на фактическом deployment;
- rollback/disable procedure проверена;
- только после этого allowlist/feature flag может быть расширен до обычного публичного доступа.

Controlled rollout выполняется на опубликованном immutable `v5.0.0-rc.N` GitHub prerelease, а не на произвольном `main`. Результат фиксируется отдельным acceptance report с exact release tag/SHA, cohort scope, проверенными сценариями, найденными findings и итоговым решением о расширении доступа. Канонический runbook и evidence contract: `docs/V5_PRODUCTION_ACCEPTANCE.md`.

## Архитектурный принцип

Client Portal не должен напрямую реализовывать infrastructure logic.

Предпочтительная схема:

~~~text
Telegram Client UI
        ↓
Order / Entitlement / Subscription services
        ↓
ProvisioningEngine / reconcile
        ↓
Plan → Server Group → Nodes → Inbounds
        ↓
3x-ui
~~~

Административный UI использует те же backend primitives для диагностики и управления, но customer flow не вызывает административные callbacks.

## Будущий платёжный канал: внешний шлюз / СБП (после v5.0 acceptance)

**Статус: ⬜ Запланировано; issue [#336](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/336). Не входит в текущий `rc.5`/`rc.6` stabilization scope.**

В дополнение к Telegram Stars (XTR) запланирована оплата VPN-подписки в рублях через **сторонний платёжный шлюз с поддержкой СБП**, формирующий **уникальную ссылку на checkout для каждого заказа**. Платёж будет проходить на защищённом сайте PSP. Конкретный провайдер, API, merchant-контракт и требования к чекам пока не выбраны.

Запрошенный UX предусматривает переход пользователя **из Telegram по персональной ссылке**. **Это идея, а не разрешённый production flow**: продажа цифровых услуг внутри ботов и Telegram Mini Apps обязана использовать Telegram Stars; перед любым bot-linked external checkout необходим отдельный review правил Telegram/юридической допустимости. Без подтверждения compliance не добавлять кнопку или прямую оплатную ссылку в Telegram. Допустимый отдельный внешний канал продаж проектировать независимо от Telegram purchase UX. Справка: [Telegram Stars Payments](https://core.telegram.org/bots/payments-stars) и [Telegram Bot Developer Terms](https://telegram.org/tos/bot-developers).

Предварительный контракт для будущего feature PR:

- провайдер-независимый PSP adapter, уникальный checkout reference/URL, TTL, `idempotency_key`, сумма/валюта `RUB` в minor units и жёсткая привязка к заказу;
- подтверждение только через подписанный и проверенный PSP webhook либо authenticated provider read-back; customer redirect/«оплата успешна» не является платёжным доказательством;
- атомарный `Order → Payment → Entitlement → ProvisioningEngine` с ownership/amount/currency checks, exactly-once local apply, no duplicate entitlement, expiry extension или quota reset при повторном/delayed/out-of-order событии;
- durable payment/refund/chargeback/`unknown` journal, отдельная refund/entitlement revocation policy и no blind retry при uncertain outcome;
- отдельная read-only `RUB` сводка PSP в Admin, не смешивать с Stars/XTR и ручными платежами; безопасные correlation IDs, приватные checkout links, минимизация sensitive logs;
- специфичный для провайдера emergency switch, лимиты запросов, привязка короткоживущего состояния, подпись webhook, fail-closed IDOR/ownership, защита от повтора и проверка восстановления при рестарте;
- перед разработкой: выбрать PSP, изучить API, KYC/фискализацию (если применимо), определить compliance Telegram-linked UX, провести threat-model и отдельный implementation/release/acceptance цикл.

**Пока не создавать** новые ссылки оплаты, кнопки, secrets, миграции или provider mutations. До завершения V5-A-001…A-003, #333, #334 и общего production acceptance эта идея не блокирует текущий canary.

## Observability и внешние интеграции после стабилизации v5

После стабилизации customer/domain model допускается отдельный этап внешних интеграций:

- read-only metrics endpoint для Prometheus-compatible collection;
- ограниченные токены сервисов/API;
- signed outgoing webhooks для событий subscription/payment/provisioning;
- documented API для внешних систем.

Эти интерфейсы не должны становиться источником обхода существующих RBAC, ownership и mutation safety rules.

### Явно вне архитектуры control plane

Даже при расширении observability/automation следующие возможности не считаются целями проекта:

- произвольный удалённый shell/терминал;
- универсальное выполнение команд;
- произвольный script execution из Telegram;
- передача arbitrary filesystem path/unit name/Docker arguments;
- автоматический retry state-changing host/deploy/update operations после uncertain outcome.

Если когда-либо понадобится отдельный automation executor шире текущих restricted agents, это требует отдельного threat-model review и нового privilege domain, а не расширения существующего Host Control Agent.

## Что предварительно не является top-level разделом v5.0.0

- `🔄 Обновить подписку` — находится внутри `🌐 Моя подписка` как `🔄 Синхронизировать подписку`;
- `🎟 Промокод` — часть `💳 Купить / продлить`;
- `📱 Подключить устройство` — действие из `🌐 Моя подписка` и/или `📱 Устройства`;
- payment history — может появиться внутри Profile/Purchase flow позже, если будет полезен клиенту;
- infrastructure/server controls — никогда не относятся к Client Portal.

## Основной принцип развития

До `v5.0.0`:

> завершаем Admin Control Plane и backend primitives в линейке v4.x.

Начиная с `v5.0.0`:

> `/start` становится Client Portal для покупки, получения, продления и самостоятельного обслуживания подписки; `/admin` остаётся отдельным защищённым Control Plane.
