# Product Roadmap

Этот документ фиксирует предварительное направление развития проекта после `v4.13.0`.

Roadmap задаёт границы крупных продуктовых этапов, но не заменяет release-specific scope: перед каждым релизом конкретный набор изменений всё равно фиксируется отдельным feature/fix/release PR.

## Граница v4.x / v5.x

### Линейка v4.x — финализация Admin Control Plane

До перехода на `v5.0.0` основной приоритет — довести административную часть `/admin` до финального production-состояния.

В v4.x входят:

- завершение и полировка административных workflows;
- infrastructure/node/fleet operations;
- monitoring, audit, jobs, backups и disaster recovery;
- admin roles и privilege boundaries;
- provisioning/reconcile primitives;
- Plans / Server Groups / Payments / Promo Codes как административные и backend-сущности;
- operational hardening, migration/recovery tooling и regression coverage;
- исправления UX/навигации `/admin`;
- backend prerequisites, необходимые будущему Client Portal, если они не открывают публичный customer flow.

Крупные публичные customer-facing workflows не должны размывать scope v4.x. `/admin` остаётся Control Plane.

### v5.0.0 — Client Portal

`v5.0.0` открывает следующий продуктовый этап: `/start` становится основным пользовательским входом для клиентов.

Архитектурная граница:

~~~text
/start
└─ Client Portal

/admin
└─ Admin Control Plane
~~~

Client Portal и Admin Control Plane живут в одном Telegram-боте и одном репозитории, но имеют независимые navigation/authorization boundaries.

`/admin` никогда не становится публичным из-за открытия `/start`.

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
- subscription URL;
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
- payment/order status;
- результат activation/extension.

Backend lifecycle:

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

На первом этапе раздел должен различать реальные зарегистрированные устройства и наблюдаемые network connections.

Если backend знает только IP/online connections, UI не должен выдавать их за достоверный список физических устройств.

Базовый вариант:

- активные подключения;
- текущий IP/device limit;
- наблюдаемые IP/сессии, если данные надёжно доступны;
- `📱 Как подключить новое устройство`.

Будущее расширение при появлении device registration:

- пользовательское имя устройства;
- platform/device type;
- last seen;
- revoke/unlink;
- device-specific onboarding/deep-link.

## 🆘 Помощь

Подразделы:

- `📱 Как подключиться`;
- `❓ Частые вопросы`;
- `🛠 Проверить подписку`;
- `💬 Связаться с поддержкой`.

Раздел должен помогать решить типовые проблемы без доступа пользователя к административным controls.

`🛠 Проверить подписку` — read-only diagnostics либо безопасная ссылка на reconcile flow; она не должна выполнять опасные infrastructure mutations.

## Authorization boundary

Текущий проект ограничивает пользовательский flow через allowlist. Для публичного Client Portal это должно быть пересмотрено отдельно в v5.x.

Целевое правило:

- `/start` и customer callbacks доступны обычному Telegram-пользователю согласно product/onboarding policy;
- пользователь может читать и изменять только собственный account/subscription context;
- `/admin` и все `admin:*` callbacks продолжают требовать существующие admin roles;
- customer identity никогда не даёт implicit admin access;
- ownership проверяется backend-ом, а не только callback payload.

Открытие публичного `/start` выполняется только после готовности customer authorization, entitlement/payment lifecycle и abuse/rate-limit policy.

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

## Что предварительно не является top-level разделом v5.0.0

- `🔄 Обновить подписку` — находится внутри `🌐 Моя подписка` как `🔄 Синхронизировать подписку`;
- `🎟 Промокод` — часть `💳 Купить / продлить`;
- `📱 Подключить устройство` — действие из `🌐 Моя подписка` и/или `📱 Устройства`;
- payment history — может появиться внутри Profile/Purchase flow позже, если будет полезен клиенту;
- infrastructure/server controls — никогда не относятся к Client Portal.

## Definition of direction

До `v5.0.0`:

> завершаем Admin Control Plane и backend primitives в линейке v4.x.

Начиная с `v5.0.0`:

> `/start` становится Client Portal для покупки, получения, продления и самостоятельного обслуживания подписки; `/admin` остаётся отдельным защищённым Control Plane.
