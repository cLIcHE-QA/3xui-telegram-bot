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

Карточка конкретного устройства в read-only #471 (кнопка DELETE относится только к будущему #472):

~~~text
📱 {device_model_or_platform}

ОС: {os}
Последняя активность: {last_seen}

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

