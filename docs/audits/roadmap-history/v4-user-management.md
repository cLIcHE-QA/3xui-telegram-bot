##### v4.25.0 — User Management: рефакторинг карточки пользователя

**Статус: ✅ User Management и follow-up релизы `v4.25.0–v4.25.6` проверены и закрыты на `v4.25.6`. Новый validation patch `v4.25.7` отслеживается отдельно.**

Цель — завершить v4.x User Management как цельный операторский workflow: карточка пользователя становится единой точкой входа для профиля, тарифа, срока, трафика, provisioning-доступа, подключений, подписки, платежей и персональной audit timeline. Релиз сохраняет существующие backend primitives и security boundaries, убирает конкурирующие legacy-пути синхронизации Inbounds и добавляет недостающие admin-facing функции без открытия Client Portal.

Implementation scope закрыт и опубликован в `v4.25.0`: User list/search/create, каноническая карточка и detail navigation, policy-based Access/Flow, Connections/HWID/IP, local-only Subscription QR, user-scoped Payments/Activity, confirmation-first lifecycle и завершённый bulk workflow реализованы и защищены regression coverage. Production smoke выполнен; найденные follow-up исправлены и повторно проверены в `v4.25.1–v4.25.6`. Закрытие предыдущих релизов подтверждено владельцем 2026-09-29; новый finding валидации Inbound не переоткрывает их исторический acceptance scope.

Границы релиза:

- scope относится только к `/admin → Пользователи`; публичный `/start` и Client Portal остаются задачей v5.x;
- machine identity не меняется: `telegram_id`, 3x-ui `email` и `sub_id` сохраняют текущую семантику; `display_name` остаётся только presentation metadata;
- текущие полезные возможности User Management не удаляются: срок, лимит трафика, reset traffic, IP limit, тариф, Server Group, ручные Inbounds, safe/strict reconcile, enable/disable, delete, subscription rotation, display name, note, statistics и bulk actions сохраняются;
- отдельный legacy-механизм «подключить все глобально разрешённые Inbounds» больше не считается канонической синхронизацией пользователя и не должен оставаться видимым action в новой карточке;
- автоматическое управление доступом выполняется только через policy-based `ProvisioningEngine` / согласование; ручное исключение выполняется только через экран конкретных Inbounds;
- абсолютные timestamps используют действующий MSK display contract; machine timestamps остаются epoch/UTC;
- Telegram Admin Control Plane остаётся односообщенческой панелью там, где экран является обычным text/keyboard view; FSM и confirmation flows обязаны иметь явный Cancel/Back;
- все новые callback routes включаются в централизованный privilege catalog; неизвестный callback по-прежнему fail-closed;
- реализация UI-контракта этого релиза должна синхронно обновить `docs/UI_STYLE.md`, regression tests и `CHANGELOG.md`; этот roadmap фиксирует planned scope, но не помечает его реализованным до merge/release/acceptance.

###### Каноническая информационная архитектура

~~~text
👥 Пользователи
│
├── 🔎 Поиск
├── ➕ Создать пользователя
├── ☑️ Массовые действия
├── 📊 Статистика
├── 🚀 Согласовать всех
│
└── 👤 Пользователь
    │
    ├── 💎 Тариф
    │   ├── Сменить тариф
    │   ├── Применить параметры тарифа
    │   └── Тариф + согласование
    │
    ├── 📅 Срок
    │   ├── +30 дней
    │   └── Установить дату
    │
    ├── 📊 Трафик
    │   ├── Использование
    │   ├── Изменить лимит
    │   └── Сбросить трафик
    │
    ├── 🌐 Доступ
    │   ├── 🗂 Группа серверов
    │   ├── 🚀 Согласование
    │   │   ├── Безопасное
    │   │   └── Строгое
    │   ├── 📡 Inbounds
    │   │   └── ручной attach/detach
    │   └── ⚙️ Параметры доступа
    │       ├── IP limit
    │       └── VLESS Flow
    │
    ├── 📱 Подключения
    │   ├── Online / last online
    │   ├── Устройства / HWID
    │   │   └── Удалить устройство
    │   └── IP-адреса
    │
    ├── 🔗 Подписка
    │   ├── Открыть ссылку
    │   ├── Показать URL
    │   ├── QR-код
    │   └── Перевыпустить ссылку
    │
    ├── 💳 Платежи
    │   └── История платежей пользователя
    │
    ├── 🧾 Активность
    │   └── Audit timeline пользователя
    │
    ├── ✏️ Профиль
    │   ├── Имя
    │   └── Заметка
    │
    └── ⚙️ Ещё действия
        ├── Enable / Disable
        ├── Reset traffic
        ├── Перевыпустить подписку
        ├── Strict reconcile
        └── Delete
~~~

###### Контракт ролей и прав RBAC

Новые экраны не вводят пятую роль и используют существующий каталог privileges.

- `users.view` / минимум `Read-only`: список, поиск, карточка, тариф/срок/трафик как read-only state, доступ/reconcile preview, Inbounds view, подключения, устройства/IP как read-only data, подписка без rotation;
- `users.support` / минимум `Support`: создание пользователя, display name/note, назначение Plan/Server Group, применение параметров тарифа, safe reconcile, manual attach/detach Inbound, изменение expiry/traffic/IP limit, reset traffic, enable/disable, VLESS Flow sync, bulk lifecycle operations и удаление одного HWID device после confirmation;
- `users.admin` / минимум `Administrator`: strict reconcile, rotation subscription identity, удаление пользователя и другие уже существующие расширенные/destructive user operations;
- `payments.view`: вложенный экран платежей пользователя и карточка платежа; write-actions платежей остаются только в каноническом разделе `Платежи` и под `payments.manage`;
- `monitoring.view`: персональная audit timeline пользователя; она является filtered view общего audit log, а не отдельным журналом;
- `Owner` не получает отдельный новый User Management capability только из-за этого релиза; owner-only boundary возникает только там, где он уже задан отдельным privilege contract.

Keyboard должен быть privilege-aware: mutation-кнопка, на которую текущая роль не имеет права, не показывается как ложнодоступная. Authorization handler остаётся обязательным независимо от видимости кнопки.

###### Экран `Пользователи`

Канонический вход: `/admin → Пользователи`, callback `admin:users`.

Текст:

~~~text
👥 Пользователи

Пользователей: {total}
🟢 Включено: {enabled_count}
⛔ Отключено: {disabled_count}
~~~

Если aggregate enabled/disabled state временно нельзя получить одним bounded read без N+1 запросов, список пользователей не блокируется: строка счётчиков опускается или явно показывает `⚠️ недоступно`, а `Пользователей: {total}` берётся из локальной БД.

Каждый пользователь отображается отдельной кнопкой:

~~~text
👤 {display_name_or_email} · TG {telegram_id}
~~~

Если задан `display_name`, технический email остаётся доступен в карточке пользователя; callback identity всегда использует `telegram_id`.

Клавиатура после списка:

~~~text
[🔎 Поиск]                  [➕ Создать]
[☑️ Массовые действия]     [📊 Статистика]
[🚀 Согласовать всех]
[⬅ Панель администратора]
~~~

При количестве пользователей больше page size обязательна pagination; пользователь не должен становиться недоступным только потому, что текущий экран показывает первые 40 записей:

~~~text
[◀️]        [2/5]        [▶️]
~~~

Page callback не меняет identity пользователя. Центральная кнопка номера страницы не выполняет mutation.

`📊 Статистика` сохраняет существующий `admin:stats`. `🚀 Согласовать всех` сохраняет существующий safe policy-based flow `admin:provision:all:ask → admin:provision:all:run`.

###### Поиск пользователя

`🔎 Поиск` открывает FSM prompt:

~~~text
🔎 Поиск пользователя

Введи Telegram ID, email или отображаемое имя.

[✖ Отмена]
~~~

Поиск:

- exact match по `telegram_id`;
- case-insensitive match по техническому email;
- case-insensitive substring по `display_name`;
- не использует `display_name` как identity;
- при одном exact result может сразу открыть карточку;
- при нескольких result показывает тот же формат строк, что основной список;
- `✖ Отмена` и Back возвращают в `Пользователи`;
- validation error не очищает путь возврата и не создаёт новое сообщение без необходимости.

###### Создание пользователя

`➕ Создать` — новый admin flow под `users.support`. Он должен переиспользовать существующие user/provisioning primitives и не иметь отдельной ad-hoc логики выдачи всех Inbounds.

Порядок:

1. **Telegram ID**

   Prompt:

   ~~~text
   ➕ Новый пользователь

   Отправь Telegram ID пользователя.

   [✖ Отмена]
   ~~~

   ID обязателен, положительный и уникальный в локальной БД. Если локальный пользователь уже существует, mutation не выполняется и предлагается `👤 Открыть пользователя`.

   Если локальной записи нет, но 3x-ui уже возвращает клиента по этому `tgId`, новый remote client не создаётся. Экран предлагает безопасное восстановление локальной записи из существующей 3x-ui identity:

   ~~~text
   ⚠️ Клиент уже существует в 3x-ui.

   Email: {email}
   Telegram ID: {telegram_id}

   [♻️ Восстановить запись бота]
   [✖ Отмена]
   ~~~

2. **Технический email**

   По умолчанию предлагается `tg_{telegram_id}`.

   ~~~text
   Технический email 3x-ui

   По умолчанию:
   tg_{telegram_id}

   [✅ Использовать предложенный]
   [✏️ Ввести другой]
   [✖ Отмена]
   ~~~

   Custom email нормализуется/валидируется теми же правилами, что machine identity 3x-ui, и проверяется на уникальность локально и в панели.

3. **Отображаемое имя**

   ~~~text
   Отображаемое имя

   Можно задать имя для админки.
   Технический email от этого не изменится.

   [⏭ Пропустить]
   [✖ Отмена]
   ~~~

   Используется существующий `display_name` contract: до 64 символов, без управляющих символов, пустое значение означает fallback на email.

4. **Тариф**

   Показывается список активных Plans. Default plan, если он настроен, отмечается как рекомендуемый текущей конфигурацией. Назначение тарифа определяет policy через существующие Plan / Server Group primitives.

   Если тариф не выбран, compatibility/trial path допускается только там, где он уже поддерживается текущим `ProvisioningEngine`; UI обязан явно назвать его `режим совместимости`, а не скрывать отсутствие Plan.

5. **Предпросмотр**

   ~~~text
   ➕ Новый пользователь

   Telegram ID: {telegram_id}
   Email: {email}
   Имя: {display_name_or_—}
   Тариф: {plan_or_compatibility}
   Группа серверов: {group}
   Срок: {expiry_preview}
   Лимит трафика: {traffic_limit}
   IP limit: {ip_limit}
   Целевые Inbounds: {count}

   [✅ Создать пользователя]
   [⬅ Изменить тариф]
   [✖ Отмена]
   ~~~

   Create выполняет remote client creation и локальную запись только через проверяемый workflow. При неопределённом исходе remote mutation нельзя автоматически повторять создание; сначала выполняется read-only verification по `tgId`/email и только доказанный state определяет дальнейший шаг.

Ранее обсуждавшаяся кнопка `💾 Только создать` **не входит в финальный v4.25 contract**: она создаёт неоднозначное partial state между локальной записью, remote client и provisioning. Для пользователя без активного доступа используются существующие Enable/Disable и policy primitives, а не отдельный «полусозданный» режим.

После success открывается новая карточка пользователя. Audit не содержит `sub_id`, subscription URL или другие secrets.

###### Главная карточка пользователя

Канонический callback сохраняется: `admin:u:{telegram_id}`.

Текст:

~~~text
👤 {display_name_or_email}
Email: {email}
Telegram ID: {telegram_id}
Статус: {🟢 включён | ⛔ отключён}

💎 Тариф: {plan}
📅 Срок: {expiry_msk}
📊 Трафик: {used} / {limit_or_без_лимита}
📱 IP limit: {limit_or_без_лимита}
🌐 Группа: {server_group}

🚀 Доступ:
целевых {desired} · подключено {attached_target}
не хватает {missing} · лишних {extra}
~~~

Если policy/read 3x-ui временно недоступен, локальные данные карточки продолжают отображаться, а соответствующая строка становится `🚀 Доступ: ⚠️ не удалось получить состояние`. Ошибка чтения не маскируется зелёным status.

Клавиатура:

~~~text
[💎 Тариф]        [⏳ Продлить]
[📅 Срок]         [📊 Трафик]
[🌐 Доступ]       [📱 Подключения]
[🔗 Подписка]     [💳 Платежи]
[🧾 Активность]   [✏️ Профиль]
[⚙️ Ещё действия]
[⬅ Пользователи]
~~~

`⏳ Продлить` является shortcut существующего `+30 дней`; canonical detail screen срока остаётся `📅 Срок`.

###### `💎 Тариф`

Parent: карточка пользователя. Канонический callback сохраняется: `admin:u:plan:{telegram_id}`.

Текст:

~~~text
💎 Тариф · {user_label}

Текущий тариф: {plan}
Стоимость: {price}
Период: {duration}

Параметры тарифа:
📦 Трафик: {plan_traffic}
📱 IP limit: {plan_ip_limit}
🗂 Группа серверов: {plan_group}

Текущие параметры пользователя:
📦 Трафик: {current_traffic_limit}
📱 IP limit: {current_ip_limit}
🗂 Группа серверов: {current_group}
~~~

Клавиатура:

~~~text
[💎 Сменить тариф]
[▶ Применить параметры тарифа]
[🚀 Тариф + согласование]
[⬅ Пользователь]
~~~

Semantics сохраняют текущее разделение:

- `Сменить тариф` назначает Plan в профиле и не выдаёт скрыто новый remote access;
- `Применить параметры тарифа` использует существующий confirmation flow и применяет текущие plan-limit semantics;
- `Тариф + согласование` применяет параметры тарифа, связанную Server Group и выполняет **безопасное** согласование; лишние управляемые Inbounds не удаляются;
- отсутствие тарифа отображается явно; действия, которым нужен Plan, не делают implicit guess.

Существующие callbacks `admin:u:planset:*`, `admin:u:planapplyask:*`, `admin:u:planapplyrun:*`, `admin:u:planprovask:*`, `admin:u:planprovrun:*` сохраняются, если implementation не требует migration identifier-а.

###### `📅 Срок`

Parent: карточка пользователя. `admin:u:expiry:{telegram_id}` становится detail screen, а не непосредственным FSM prompt.

Текст:

~~~text
📅 Срок действия · {user_label}

Текущий срок:
{expiry_msk}

Осталось:
{relative_duration}
~~~

Клавиатура:

~~~text
[➕ +30 дней]
[📅 Установить дату]
[⬅ Пользователь]
~~~

- `➕ +30 дней` сохраняет существующую семантику `adminextend:{telegram_id}`: база — `max(current_expiry, now)`;
- `📅 Установить дату` открывает отдельный FSM callback, например `admin:u:expiryedit:{telegram_id}`;
- date-only `YYYY-MM-DD` означает `23:59:59 MSK` по действующему UI contract;
- validation error оставляет `✖ Отмена`;
- success возвращает в экран `📅 Срок`, а не в случайный parent.

###### `📊 Трафик`

Parent: карточка пользователя. `admin:u:traffic:{telegram_id}` становится detail screen.

Текст:

~~~text
📊 Трафик · {user_label}

⬆ Upload: {up}
⬇ Download: {down}

Использовано:
{used}

Лимит:
{limit_or_без_лимита}

Осталось:
{remaining_or_без_лимита}
~~~

Клавиатура:

~~~text
[✏️ Изменить лимит]
[♻️ Сбросить трафик]
[⬅ Пользователь]
~~~

- `Изменить лимит` открывает FSM `admin:u:trafficedit:{telegram_id}`; `0`/каноническое значение unlimited отображается как `без лимита`;
- `Сбросить трафик` сохраняет текущий ask/run contract `admin:u:resetask:* → admin:u:resetrun:*`;
- reset screen явно называет пользователя и требует confirmation;
- success возвращает в `📊 Трафик`.

###### `🌐 Доступ`

Новый parent callback: `admin:u:access:{telegram_id}`.

Текст:

~~~text
🌐 Доступ · {user_label}

Источник политики:
{plan/profile/compatibility}

Группа серверов:
{group}

Режим Inbounds:
{all_managed/selected display label}

Целевые: {desired_count}
Текущие: {current_count}
Не хватает: {missing_count}
Лишних управляемых: {extra_count}

{optional unavailable nodes block}
~~~

Клавиатура:

~~~text
[🗂 Группа серверов]
[🚀 Согласование]
[📡 Inbounds]
[⚙️ Параметры доступа]
[⬅ Пользователь]
~~~

Этот экран является единственным parent для автоматического/ручного управления network access пользователя.

###### `🌐 Доступ → 🗂 Группа серверов`

Сохраняется `admin:u:group:{telegram_id}` и существующие `admin:u:groupset:*`.

Текст перед выбором:

~~~text
🗂 Группа серверов · {user_label}

Текущая группа:
{group}

Группа определяет целевой набор согласования.
Само назначение не меняет 3x-ui мгновенно.
~~~

Кнопки используют `✅` для текущей группы и `⬜` для остальных. Последняя кнопка:

~~~text
[⬅ Доступ]
~~~

После назначения:

~~~text
✅ Назначена группа: {group}.

Для применения целевого доступа выполните согласование.

[🚀 Согласовать сейчас]
[⬅ Доступ]
~~~

Назначение Server Group не должно скрытно attach/detach Inbounds.

###### `🌐 Доступ → 🚀 Согласование`

Сохраняется `admin:u:prov:{telegram_id}`.

Текст:

~~~text
🚀 Согласование · {user_label}

Источник: {source}
Тариф: {plan}
Группа серверов: {group}
Режим Inbounds: {mode}

Целевые: {ids}
Текущие: {ids}
Не хватает: {ids}
Лишние управляемые: {ids}

{warnings/unavailable nodes}
~~~

Клавиатура:

~~~text
[✅ Безопасное согласование]
[⚠️ Строгое согласование]
[⬅ Доступ]
~~~

**Безопасное согласование**:

- callback `admin:u:provrun:{telegram_id}:safe`;
- добавляет только отсутствующие actionable target Inbounds;
- лишние текущие Inbounds не удаляет;
- unavailable members остаются целевыми, но не вызывают ложный success;
- результат показывает `Подключены`, `Отключены`, `Всё ещё отсутствуют`, `Лишние управляемые`.

**Строгое согласование**:

- `admin:u:provstrictask:{telegram_id}` всегда открывает отдельный warning screen;
- `admin:u:provrun:{telegram_id}:strict` доступен только `users.admin`;
- добавляет отсутствующие и удаляет только управляемые extras, которых нет в target policy;
- last-access/managed safety guards существующего provisioning engine сохраняются.

Подтверждение:

~~~text
⚠️ Строгое согласование

Будут добавлены отсутствующие целевые Inbounds
и отключены управляемые Inbounds,
которых нет в текущей политике пользователя.

Будут отключены:
{extra_ids_or_нет}

[⚠️ Выполнить строгое согласование]
[✖ Отмена]
~~~

Cancel возвращает в preview согласования.

###### `🌐 Доступ → 📡 Inbounds`

Сохраняется `admin:u:inbounds:{telegram_id}` и `admin:u:ibtoggle:{telegram_id}:{inbound_id}`.

Текст:

~~~text
📡 Inbounds · {user_label}

Нажатие подключает/отключает пользователя
от конкретного Inbound.

⚠️ Ручные изменения могут отличаться от политики
тарифа/Группы серверов. Следующее строгое
согласование может их изменить.
~~~

Каждый Inbound:

~~~text
✅ #1 · 443/VLESS · Germany
⬜ #2 · 443/VLESS · Austria
~~~

Последняя кнопка:

~~~text
[⬅ Доступ]
~~~

Manual toggle остаётся support-operation. Существующая защита от отключения последнего допустимого managed Inbound сохраняется.

###### `🌐 Доступ → ⚙️ Параметры доступа`

Новый callback: `admin:u:accesscfg:{telegram_id}`.

Текст:

~~~text
⚙️ Параметры доступа · {user_label}

📱 IP limit: {limit_or_без_лимита}
🔀 VLESS Flow: {flow_or_none}
~~~

Клавиатура:

~~~text
[📱 Изменить IP limit]
[🔀 Синхронизировать Flow]
[⬅ Доступ]
~~~

- изменение IP limit переиспользует текущий validation/FSM contract `admin:u:ip:*`, но success возвращает в `Параметры доступа`;
- `Синхронизировать Flow` является отдельной mutation и не attach'ит Inbounds;
- flow mutation использует отдельный ask/run pair, например `admin:u:flowask:* → admin:u:flowrun:*`, и применяет только configured `settings.vless_flow`;
- если `settings.vless_flow` пуст, UI показывает `VLESS Flow: не настроен` и не предлагает ложную mutation.

###### Депрекация legacy `Синхронизировать Inbounds`

В v4.25 из visible keyboards удаляются:

- `🔄 Синхронизировать Inbounds` / `adminsync:{telegram_id}`;
- `🔄 Синхронизировать всех` / `admin:syncall:ask` / `admin:syncall:run`;
- bulk `sync`, который attach'ит выбранным пользователям все globally allowed Inbounds.

Причина: эти paths используют глобальный `choose_inbounds(...)` и могут выдать доступ шире индивидуального `Plan → Server Group → target policy`.

Stale Telegram callback не должен молча выполнять старую mutation. На один transition release старые callback identifiers могут оставаться compatibility handlers, но только как **non-mutating redirect**:

~~~text
ℹ️ Это действие устарело.

Автоматическая синхронизация доступа теперь выполняется
через policy-based «Согласование».

[🌐 Открыть доступ]
[⬅ Пользователь]
~~~

Для global stale callback:

~~~text
ℹ️ «Синхронизировать всех» больше не используется.

Используй безопасное policy-based согласование.

[🚀 Согласовать всех]
[⬅ Пользователи]
~~~

После достаточного transition window compatibility handlers могут быть удалены отдельным cleanup; unknown callbacks после этого fail-closed по общему contract.

###### `📱 Подключения`

Новый callback: `admin:u:connections:{telegram_id}`.

Текст:

~~~text
📱 Подключения · {user_label}

{online_status}
Последняя активность: {last_online_msk_or_нет_данных}
IP limit: {limit_or_без_лимита}

Устройств: {hwid_count_or_недоступно}
IP-адресов: {ip_count_or_недоступно}
~~~

Клавиатура:

~~~text
[📱 Устройства]
[🌐 IP-адреса]
[⬅ Пользователь]
~~~

IP limit здесь только показывается. Каноническое изменение лимита находится в `🌐 Доступ → ⚙️ Параметры доступа`, чтобы не создавать два равноправных edit path.

Online/last-online используют существующие read-only 3x-ui primitives. Экран не выдаёт IP/session за физическое устройство без HWID identity.

###### `📱 Подключения → 📱 Устройства`

Для v4.25 используемый 3x-ui contract расширяется reviewed endpoints pinned schema:

- `POST /panel/api/clients/hwids/{email}` — список зарегистрированных HWID devices;
- `DELETE /panel/api/clients/hwids/{email}/{id}` — удаление одного зарегистрированного устройства.

Они добавляются в `contracts/3xui/contract.json`, `XUIClient` и OpenAPI regression coverage до использования в Telegram UI.

Список:

~~~text
📱 Устройства · {user_label}

1. {device_model_or_device_os}
   {fingerprint}
   Последняя активность: {last_seen_msk}

2. ...
~~~

Кнопка каждой записи открывает detail callback `admin:u:device:{telegram_id}:{device_id}`.

Карточка устройства:

~~~text
📱 Устройство · {user_label}

Модель: {device_model_or_—}
ОС: {device_os} {os_version}
Fingerprint: {short_fingerprint}
User-Agent: {safe_user_agent_or_—}
Первое появление: {first_seen_msk}
Последняя активность: {last_seen_msk}

[🗑 Удалить устройство]
[⬅ Устройства]
~~~

Полный HWID/hash не должен выводиться, если upstream deliberately возвращает только short fingerprint.

Удаление устройства обязательно двухшаговое:

~~~text
⚠️ Удалить устройство?

{device_model_or_fingerprint}
Пользователь сможет зарегистрировать устройство заново,
если это разрешает текущий HWID limit.

[🗑 Удалить устройство]
[✖ Отмена]
~~~

Первый callback `admin:u:devdelask:{telegram_id}:{device_id}` не выполняет DELETE; mutation находится только за `admin:u:devdel:{telegram_id}:{device_id}`. Success возвращает в список устройств. В v4.25 не добавляется «Удалить все устройства».

###### `📱 Подключения → 🌐 IP-адреса`

Используется reviewed read-only endpoint pinned schema `/panel/api/clients/ips/{email}` (и только те соседние IP APIs, которые действительно нужны implementation). Contract JSON и tests обновляются до использования.

Текст:

~~~text
🌐 IP-адреса · {user_label}

Сейчас online:
{online_ips_or_нет}

История:
{ip_entries_with_last_seen_if_upstream_provides_it}
~~~

Правила:

- показываются только фактические данные upstream; бот не придумывает device identity по IP;
- если upstream даёт только set/list без timestamp, UI не подписывает его как хронологическую историю;
- v4.25 не добавляет локальное бессрочное хранение IP history и не создаёт новый surveillance-like ledger;
- IP не пишутся целиком в обычный audit/details только ради открытия экрана;
- отдельный `Clear IP history` в этот release не входит;
- Back возвращает в `📱 Подключения`.

###### `🔗 Подписка`

Новый parent callback: `admin:u:subscription:{telegram_id}`.

Текст:

~~~text
🔗 Подписка · {user_label}

ID: {masked_sub_id}
Статус: {active/disabled/expired presentation}
~~~

Клавиатура:

~~~text
[🔗 Открыть ссылку]
[📋 Показать URL]
[📱 QR-код]
[🔐 Перевыпустить ссылку]
[⬅ Пользователь]
~~~

- `Открыть ссылку` использует Telegram URL button только для авторизованного admin view;
- `Показать URL` переиспользует существующий `adminsub:{telegram_id}` либо эквивалентный read-only screen;
- URL и `sub_id` считаются secret-like customer credentials: они не попадают в audit/details/logs;
- QR генерируется **локально** из subscription URL; внешние QR services запрещены, чтобы не раскрывать credential третьей стороне;
- если QR требует отдельного media message, основной admin panel state и кнопка возврата не теряются; generated QR не сохраняется как постоянный файл;
- `🔐 Перевыпустить ссылку` использует существующий admin-only ask/run contract `admin:u:subrotateask:* → admin:u:subrotaterun:*`.

Подтверждение смены:

~~~text
⚠️ Перевыпустить ссылку подписки?

Старая ссылка перестанет работать.
Пользователю потребуется новая ссылка подписки.

[🔐 Перевыпустить]
[✖ Отмена]
~~~

Success показывает новый URL только авторизованному оператору и возвращает в `🔗 Подписка`.

###### `💳 Платежи`

Новый callback: `admin:u:payments:{telegram_id}`, privilege `payments.view`.

Это read-only filtered view существующей payment ledger; финансовые write-actions не дублируются в User Management.

Текст:

~~~text
💳 Платежи · {user_label}

Всего: {count}
Оплачено: {paid_count}

Суммы оплаченных:
{amount_by_currency}

Последние операции:
{status} {date_msk} · {amount} · {plan_or_—}
...
~~~

Если платежи в разных валютах, суммы группируются по currency; нельзя складывать EUR и USD в одно число.

Клавиатура:

~~~text
[📋 Все платежи]
[⬅ Пользователь]
~~~

При необходимости pagination открывает user-scoped список. Карточка конкретного платежа использует context-aware callback, например `admin:u:payment:{telegram_id}:{payment_id}`, чтобы `⬅ Платежи` возвращал именно в историю текущего пользователя. Data source — существующая таблица `payments.telegram_id`; новая финансовая ledger не создаётся.

###### `🧾 Активность`

Новый callback: `admin:u:activity:{telegram_id}`, privilege `monitoring.view`.

Это filtered view существующего `audit_log`. Для current user actions primary filter использует `target_type='user'` и техническую user identity; implementation должен учесть существующие исторические action records, не привязываясь к `display_name`.

Текст:

~~~text
🧾 Активность · {user_label}

Сегодня

18:31 · {actor}
🚀 Безопасное согласование
{safe_summary}

18:25 · {actor}
💎 Изменён тариф
{old} → {new}

...
~~~

Timeline включает релевантные user mutations: Plan, Server Group, expiry, traffic limit/reset, IP limit, enable/disable, manual Inbound attach/detach, safe/strict reconcile, subscription rotation, display name/note, device revoke и другие user-targeted audited actions.

Правила:

- это presentation/filter existing audit, не второй журнал;
- secret values, subscription URL/`sub_id`, full HWID и другие credentials не реконструируются из details;
- timestamps отображаются в MSK;
- pagination/«Показать ещё» сохраняет user context;
- Back возвращает в карточку пользователя.

###### `✏️ Профиль`

Новый parent callback: `admin:u:profile:{telegram_id}`.

Текст:

~~~text
✏️ Профиль · {user_label}

Имя:
{display_name_or_не_задано}

Email:
{email}

Telegram ID:
{telegram_id}

Заметка:
{note_or_—}
~~~

Клавиатура:

~~~text
[✏️ Изменить имя]
[📝 Изменить заметку]
[⬅ Пользователь]
~~~

Существующие `admin:u:name:*` и `admin:u:note:*` сохраняют validation/audit semantics. Email и Telegram ID read-only: этот release не вводит rename machine identity.

###### `⚙️ Ещё действия`

Новый callback: `admin:u:more:{telegram_id}`.

Экран консолидирует mutation shortcuts / danger zone, но не создаёт новые backend semantics:

~~~text
⚙️ Ещё действия · {user_label}

[⛔ Отключить пользователя]   # если включён
[✅ Включить пользователя]    # если отключён
[♻️ Сбросить трафик]
[🔐 Перевыпустить подписку]
[⚠️ Строгое согласование]
[🗑 Удалить пользователя]
[⬅ Пользователь]
~~~

Кнопки показываются по текущему status и privilege. `Reset`, rotation и strict reconcile ведут в те же canonical confirmation screens, что тематические разделы; duplicate backend handler не создаётся.

###### Включение и отключение

Disable переводится из one-click mutation в confirmation flow:

~~~text
⛔ Отключить пользователя?

{user_label}
Email: {email}

Доступ пользователя будет отключён,
но запись и настройки сохранятся.

[⛔ Отключить]
[✖ Отмена]
~~~

Для stale compatibility существующий `admindisable:{telegram_id}` может стать ask-screen, а mutation переносится на новый `admindisablerun:{telegram_id}`.

Enable аналогично:

~~~text
✅ Включить пользователя?

{user_label}

[✅ Включить]
[✖ Отмена]
~~~

Existing `adminenable:{telegram_id}` может стать ask-screen, mutation — `adminenablerun:{telegram_id}`. Success возвращает в карточку пользователя.

###### Удаление пользователя

Сохраняется существующий двухшаговый `admindelask:* → admindel:*`.

Подтверждение:

~~~text
🗑 Удалить пользователя

{user_label}
Email: {email}
Telegram ID: {telegram_id}

Будут удалены пользователь и его доступ
согласно текущему безопасному delete workflow.

Это действие необратимо.

[🗑 Удалить пользователя]
[✖ Отмена]
~~~

Existing remote-before-local safety semantics не ослабляются. После подтверждённого удаления result screen ведёт в `Пользователи`; Cancel возвращает в карточку пользователя.

###### Массовые действия

Bulk selection остаётся отдельным flow от карточки пользователя. Selection screen сохраняет pagination и выбранные IDs в FSM, callback identity — `telegram_id`.

Целевые действия:

~~~text
☑️ Выбрано: {count}

[💎 Назначить тариф]        [🗂 Назначить группу]
[➕ +30 дней]               [📅 Установить срок]
[📦 Лимит трафика]         [🚀 Согласовать]
[✅ Включить]               [⛔ Отключить]
[♻️ Сбросить трафик]
[⬅ К выбору]
[✖ Закрыть]
~~~

Semantics:

- Plan assignment и Server Group assignment изменяют только соответствующий profile state и не скрывают remote provisioning;
- custom expiry/traffic limit используют bounded FSM input и explicit preview/confirmation перед mass mutation;
- `🚀 Согласовать` использует `ProvisioningEngine.provision_many(..., strict=False)`, а не legacy bulk attach-all;
- bulk strict reconcile в v4.25 **не добавляется**: destructive detach нескольких пользователей требует отдельного product/security decision;
- enable/disable/reset сохраняют existing bulk primitives, но confirmation показывает число выбранных пользователей;
- partial failure не останавливает обработку остальных пользователей, а result summary явно разделяет success/failed/unknown там, где backend может доказать разные outcomes;
- audit не перечисляет secret data и не должен без необходимости сохранять полный список email в одной строке.

###### Контракт callback и навигации

Implementation может сохранить существующие identifiers, где это не ухудшает semantics. Целевые parent routes:

| Экран | Callback | Parent / Back |
| --- | --- | --- |
| Пользователи | `admin:users` | `admin:home` |
| Пользователь | `admin:u:{tg_id}` | `admin:users` |
| Тариф | `admin:u:plan:{tg_id}` | пользователь |
| Срок | `admin:u:expiry:{tg_id}` | пользователь |
| Трафик | `admin:u:traffic:{tg_id}` | пользователь |
| Доступ | `admin:u:access:{tg_id}` | пользователь |
| Группа серверов | `admin:u:group:{tg_id}` | Доступ |
| Согласование | `admin:u:prov:{tg_id}` | Доступ |
| Inbounds | `admin:u:inbounds:{tg_id}` | Доступ |
| Параметры доступа | `admin:u:accesscfg:{tg_id}` | Доступ |
| Подключения | `admin:u:connections:{tg_id}` | пользователь |
| Устройства | `admin:u:devices:{tg_id}` | Подключения |
| Устройство | `admin:u:device:{tg_id}:{device_id}` | Устройства |
| IP-адреса | `admin:u:ips:{tg_id}` | Подключения |
| Подписка | `admin:u:subscription:{tg_id}` | пользователь |
| Платежи | `admin:u:payments:{tg_id}` | пользователь |
| Активность | `admin:u:activity:{tg_id}` | пользователь |
| Профиль | `admin:u:profile:{tg_id}` | пользователь |
| Ещё действия | `admin:u:more:{tg_id}` | пользователь |

Все callback payloads обязаны укладываться в Telegram 64-byte limit. IDs берутся только из backend-resolved context; callback payload не является authorization/ownership proof.

Общие navigation rules:

- detail screen всегда возвращает в зафиксированный parent, а не в `admin:home` напрямую;
- FSM `✖ Отмена` возвращает в экран, из которого был начат input;
- confirmation `✖ Отмена` возвращает в карточку/подраздел без mutation;
- после delete result возвращает в список удалённой сущности;
- после device revoke result возвращает в `Устройства`;
- после Plan/expiry/traffic/IP update result возвращает в соответствующий detail screen;
- после safe/strict reconcile result предлагает `⬅ Согласование` или `⬅ Доступ`, но не создаёт dead end;
- read failure не должен уничтожать доступ к Back;
- progress screen state-changing operation может временно скрыть action buttons, если повторный click создаёт риск duplicate mutation.

###### Изменения данных и API

Минимальные backend additions v4.25:

- user-scoped payment query/pagination поверх существующей `payments.telegram_id`, без новой payment schema;
- user-scoped audit query/pagination поверх существующего `audit_log`, без второго audit storage;
- изученные методы `XUIClient` и записи закреплённого OpenAPI для списка HWID, удаления одного устройства и чтения IP клиента;
- локальный QR renderer/library допустим только без передачи subscription URL внешнему сервису;
- search/pagination helpers для users;
- при необходимости небольшие shared presenter/formatter helpers, чтобы card/list labels не расходились.

По умолчанию v4.25 **не требует новой SQLite migration**. Если implementation обнаружит реальную необходимость persistence, она оформляется только через existing forward-only migration framework и должна быть обоснована в implementation PR; UI scope сам по себе не является причиной хранить копии HWID/IP history.

###### Что намеренно не входит в v4.25

- публичный Client Portal и customer self-service;
- смена технического 3x-ui email/machine identity;
- массовый strict reconcile;
- «удалить все HWID устройства»;
- локальная бессрочная IP/device telemetry history;
- новый payment state machine/provider webhook — это v5 commerce scope;
- привязка User/Audience Groups к VPN provisioning;
- новый role model или custom per-admin permissions;
- возврат legacy attach-all sync под новым названием.

###### Контракт регрессионных проверок и приёмки

Implementation PR должен добавить/обновить tests как минимум для:

1. точной структуры main user card keyboard и всех parent/Back paths;
2. privilege catalog parity для каждого нового callback; unknown route fail-closed;
3. role-aware visibility mutation buttons;
4. search по Telegram ID/email/display name и pagination списка >40 пользователей;
5. create-user duplicate detection, 3x-ui recovery path и отсутствие duplicate creation при uncertain mutation outcome;
6. сохранения machine identity при изменении display name/Plan/Group;
7. expiry `+30`, date-only MSK semantics и возврата в экран срока;
8. traffic limit/unlimited/reset confirmation и возврата в экран трафика;
9. safe/strict reconcile semantics и точного parent `Доступ`;
10. manual Inbound toggle и last-managed-Inbound safety;
11. отсутствия visible `Синхронизировать Inbounds`, `Синхронизировать всех` и legacy bulk attach-all action;
12. stale legacy sync callbacks как non-mutating redirect;
13. VLESS Flow sync без attach/detach Inbounds;
14. pinned 3x-ui OpenAPI contract для HWID/IP endpoints;
15. device list/detail и delete-two-step: первый callback не выполняет mutation;
16. IP screen не называет IP физическим устройством и не создаёт local history;
17. subscription URL/`sub_id` redaction из audit/logs и local-only QR generation;
18. user-scoped payments, multi-currency summary и отсутствие payment write-actions в user card;
19. user-scoped audit timeline и отсутствие secret reconstruction;
20. подтверждение включения/отключения, удаления пользователя и корректного перехода после действия;
21. массовые операции с тарифом/группой/сроком/трафиком, безопасной сверкой и сводкой частичных отказов;
22. callback payload length <= 64 bytes;
23. one-message admin navigation/FSM cleanup без dead ends;
24. MSK timestamps на новых operator-facing absolute dates.

Приёмка в production после публикации `v4.25.0` должен пройти минимум под `Read-only`, `Support` и `Administrator` test accounts:

- открыть список, поиск, pagination и карточку пользователя;
- пройти каждый read-only подраздел и Back-chain до `Пользователи`;
- изменить display name/note и проверить неизменность email/`telegram_id`/`sub_id`;
- назначить Plan и Server Group, применить параметры тарифа и выполнить safe reconcile;
- вручную attach/detach test Inbound и проверить предупреждение о policy drift;
- выполнить strict reconcile на контролируемом test user с известным extra Inbound;
- изменить expiry/traffic/IP limit, reset traffic, disable/enable;
- открыть HWID devices/IP data на test user; удалить одно test device через confirmation и проверить post-condition;
- открыть subscription URL/QR, выполнить rotation на test user и подтвердить invalidation старой ссылки;
- проверить user-scoped payments/activity;
- выполнить несколько bulk actions и safe reconcile для test cohort;
- открыть stale legacy sync callback из заранее сохранённого сообщения и подтвердить отсутствие attach-all mutation;
- проверить базовый bot/DB/3x-ui health после smoke.

Acceptance считается закрытым только если navigation contract принят на Telegram Desktop и mobile, privilege boundaries подтверждены, legacy sync paths не выдают лишний доступ, а новые HWID/IP calls соответствуют pinned 3x-ui contract.

Приёмка в production findings от 2026-09-28:

- под `Read-only` главная карточка пользователя ошибочно показывает shortcut `⏳ Продлить` с callback `adminextend:{telegram_id}`, хотя callback защищён privilege `users.support`; backend RBAC корректно не допускает mutation, но keyboard нарушает role-aware UI contract;
- acceptance review подтвердил более чистый fix: полностью убрать shortcut `⏳ Продлить` с главной карточки пользователя для всех ролей; продление срока остаётся только в каноническом parent-screen `📅 Срок → ➕ +30 дней`;
- callback `adminextend:{telegram_id}` не удаляется: он остаётся backend action под `users.support` для кнопки `➕ +30 дней` и для совместимости со старыми сохранёнными Telegram callbacks;
- `Пользователь → 🔗 Подписка → Показать URL` теряет parent context: текущий `adminsub:{telegram_id}` рендерит Back в карточку пользователя; fix — возвращать в канонический parent-screen `🔗 Подписка`;
- `Пользователь → 💳 Платежи → 📋 Все платежи` теряет user-scoped context: кнопка уводит в глобальный `admin:payments`, после чего Back ведёт в admin home; fix — не покидать user-scoped payment flow и сохранять возврат в `💳 Платежи` текущего пользователя;
- create-user flow ломается на проверке нового technical email: `_email_available()` считает email свободным только для ошибки `Client not found:`, тогда как pinned production 3x-ui при отсутствии записи возвращает `Obtain (record not found)`; в результате `✅ Использовать предложенный` (и общий путь проверки нового email) показывает `Не удалось проверить email` вместо продолжения wizard;
- fix: нормализовать штатный upstream not-found response в семантику «email свободен», не ослабляя fail-closed обработку остальных XUI ошибок; добавить regression coverage для фактического `Obtain (record not found)` и обоих create-email paths;
- HWID registration через публичный compat subscription path сломан: `subscription_proxy.py` при `GET /compat/{sub_id}` пересылает upstream только `Accept` и `User-Agent`, отбрасывая `X-HWID` и device metadata headers; при включённом HWID limit upstream отклоняет такой запрос, а compat proxy маскирует upstream `>=400` как HTTP 502;
- fix: для normal VPN-client subscription request безопасно проксировать reviewed HWID/device headers к 3x-ui upstream, не логировать их значения и сохранить существующую фильтрацию остальных headers; добавить regression coverage, что `X-HWID`/device metadata доходят до upstream и upstream HWID error не возникает из-за их потери;
- `⚙️ Ещё действия` под `Read-only` подтверждён как корректный negative case: mutation-кнопки не отображаются, остаётся только возврат к карточке пользователя.

Эти findings блокировали acceptance `v4.25.0`; исправления shortcut/navigation/create/HWID proxy опубликованы в `v4.25.1` и прошли повторную проверку. Исторический stale-callback production exception остаётся явно указан ниже, а не заменяется вымышленным PASS.

Отдельный HWID acceptance после исправления compat proxy:

- prerequisite: на контролируемом test user `Max HWIDs > 0`; при отсутствии HWID limit механизм считается неактивным и реальная device registration не ожидается;
- добавить публичную `/compat/{sub_id}` подписку в реальный mobile client, принудительно обновить subscription и подтвердить появление устройства в `Пользователь → 📱 Подключения → 📱 Устройства`;
- повторить тот же сценарий с реальным desktop client;
- проверить, что отображаются только разрешённые bounded metadata: модель/OS/version/User-Agent/short fingerprint/first+last seen без раскрытия полного HWID;
- удалить одно test-device через двухшаговый confirmation flow, проверить post-condition и отсутствие удаления остальных устройств;
- если конкретный клиент не регистрируется после proxy fix, отдельно подтвердить, отправляет ли он `X-HWID`/device metadata headers; отсутствие HWID headers у клиента не считать дефектом Telegram UI;
- acceptance считается пройденным только после проверки хотя бы одного реального HWID-capable клиента через публичный compat URL, а не только synthetic direct-upstream `curl`.


