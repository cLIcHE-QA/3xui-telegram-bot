#### Независимая от провайдера панель управления и поддержка Remnawave

**Статус: ⬜ Отложено. Не является текущим блокером финального v4.x freeze, repository/public-release audit или открытия базового Client Portal v5. Реализация допускается только отдельным архитектурным треком после закрытия текущих обязательных gates.**

Цель — не создавать отдельный fork Telegram-бота под Remnawave и не встраивать в Client Portal условные ветки вида `if backend == "3xui"`. Вместо этого текущий проект должен получить provider-neutral boundary, где Telegram UI, commerce, entitlement, audit и customer-facing workflows работают с едиными domain-сущностями, а различия 3x-ui и Remnawave изолированы в отдельных adapters/providers.

Целевая высокоуровневая схема:

~~~text
                 Telegram Bot
                     │
          ┌──────────┴──────────┐
          │                     │
       /start                 /admin
   Client Portal          Admin Control Plane
          │                     │
          └──────────┬──────────┘
                     │
               Domain Services
                     │
          ┌──────────┼───────────┐
          │          │           │
       Orders     Payments   Entitlements
                                │
                         Provisioning
                                │
                     ControlPlaneRegistry
                          ↙          ↘
                    3xUIProvider  RemnawaveProvider
~~~

Ключевой принцип: локальная business-domain модель бота остаётся источником истины для customer/order/payment/entitlement lifecycle. Ни 3x-ui client, ни Remnawave User не становятся эквивалентом локального Customer. Remote control plane считается исполняющим provider-слоем, который может быть временно недоступен, заменён или мигрирован без потери бизнес-состояния.

##### Граница предметной области без привязки к провайдеру

До добавления Remnawave provider-specific calls должны быть вытеснены из Client Portal и по возможности из верхнего слоя Admin UI за интерфейс уровня domain capabilities.

Рекомендуемая логическая граница:

~~~text
control_plane/
├─ base.py
├─ models.py
├─ capabilities.py
├─ registry.py
├─ xui.py
└─ remnawave.py
~~~

Точное имя модулей не является контрактом, но separation of concerns является обязательным.

Минимальный provider-neutral API должен оперировать действиями уровня продукта, а не конкретными HTTP endpoints панели:

~~~text
get_user()
create_user()
update_user()
enable_user()
disable_user()
delete_user()

get_usage()
reset_traffic()

get_access()
set_access()
reconcile_access()

get_subscription()
rotate_subscription()

get_devices()
delete_device()
get_device_limit()

get_nodes()
get_node_health()
~~~

Client Portal и общие domain services не должны импортировать `XUIClient` или `RemnawaveClient` напрямую.

##### Модель возможностей

3x-ui и Remnawave не обязаны поддерживать полностью одинаковый набор операций. Вместо provider-name branching UI и services должны использовать явный capability contract, например:

~~~text
supports_traffic
supports_reset_traffic
supports_subscription_url
supports_subscription_rotation
supports_hwid_devices
supports_device_delete
supports_device_limit
supports_access_reconcile
supports_node_health
supports_graceful_drain
~~~

Если capability отсутствует, UI скрывает или корректно дизейблит действие, а backend authorization/service layer всё равно остаётся финальной защитой. Presentation hiding не заменяет backend validation.

Новые provider-specific возможности не должны автоматически расширять общий contract. Сначала определяется стабильная domain-семантика, затем capability добавляется в интерфейс.

##### Локальная модель Customer / Subscription / Provider Binding

Client Portal не должен моделировать:

~~~text
Telegram user = 3x-ui client
~~~

или:

~~~text
Telegram user = Remnawave User
~~~

Целевая модель:

~~~text
Customer
  ↓
Entitlement
  ↓
Subscription
  ↓
Provider Binding
~~~

Минимально provider binding должен хранить:

- локальный stable subscription/customer identity;
- `provider_type`;
- stable remote user identity;
- remote subscription identity, если она отделена от user identity;
- provider-specific immutable/stable identifiers, необходимые для safe read-back;
- lifecycle/status metadata, достаточные для reconciliation;
- timestamps/version metadata для диагностики drift;
- без хранения remote secrets там, где достаточно ссылочного identifier.

Это позволяет одному Customer иметь несколько subscriptions, включая одновременное использование разных providers.

Пример допустимой модели:

~~~text
Customer
├─ Subscription A
│  ├─ provider: 3x-ui
│  └─ plan: Legacy EU
└─ Subscription B
   ├─ provider: Remnawave
   └─ plan: Premium
~~~

Ограничение "один bot deployment = один VPN backend" не должно закладываться в schema как необратимое архитектурное решение.

##### Plan и provider placement

`Plan` должен описывать коммерческую/доступную пользователю услугу, а provider-specific mapping храниться отдельно.

Допустимая логическая модель:

~~~text
Plan
├─ commercial policy
├─ duration / quota
├─ entitlement rules
└─ placement/access policy
      ↓
Provider Binding / Provider Policy
~~~

Для 3x-ui access policy может сводиться к текущей цепочке:

~~~text
Plan
 ↓
Server Group
 ↓
Nodes
 ↓
Inbounds
 ↓
User
~~~

Для Remnawave целевая access-семантика должна использовать нативные сущности Remnawave:

~~~text
Plan
 ↓
Access Policy
 ↓
Internal Squad(s)
 ↓
User
~~~

При этом инфраструктурная модель Remnawave рассматривается отдельно:

~~~text
Config Profile
 ↓
Inbounds
 ↓
Nodes

Inbound
 ↓
Host
 ↓
client-facing address / connection parameters
~~~

Нельзя пытаться механически переименовать текущий `Server Group` в `Internal Squad` и считать миграцию законченной. Нужен явный mapping layer, потому что сущности имеют разную семантику.

##### Собственная семантика Remnawave

При реализации adapter необходимо исходить из актуальной архитектуры Remnawave, а не эмулировать 3x-ui:

- Remnawave Panel сама не является Xray data-plane runtime; Xray работает на Remnawave Nodes;
- Node использует один Config Profile, внутри которого активируется набор Inbounds;
- Internal Squad является access-control group и определяет, какие Inbounds доступны назначенным пользователям;
- пользователь может состоять в нескольких Internal Squads;
- Host является client-facing gateway/connection description и связывается с конкретным Inbound; его address/port/SNI и другие параметры относятся к пользовательскому data plane;
- External Squads, если будут использоваться, рассматриваются отдельно как subscription/template/settings override и не смешиваются с Internal Squad access policy;
- HWID Device Limit является optional provider capability, а не обязательным свойством каждой subscription.

Эта модель хорошо сочетается с общим hardening-принципом разделения control-plane address и operator-owned data-plane address: Remnawave Node и Remnawave Host не должны схлопываться в одну локальную сущность только ради совместимости со старой моделью.

##### Выдача доступа и сверка состояния

Текущий `ProvisioningEngine` не должен быть выброшен только из-за добавления второго provider. Его policy/reconcile роль сохраняется, но provider-specific primitives должны быть вынесены ниже.

Для 3x-ui desired/current state остаётся связан с managed Inbounds.

Для Remnawave рекомендуемая базовая модель:

~~~text
desired Internal Squad UUIDs
vs
current active Internal Squads
~~~

Безопасная сверка:

- добавляет отсутствующие required managed squads;
- не удаляет дополнительные access assignments;
- после mutation выполняет read-back;
- uncertain mutation не повторяется автоматически.

Строгая сверка:

- сначала добавляет недостающий required access;
- подтверждает post-condition;
- затем удаляет только managed extras, которые больше не входят в policy;
- не трогает unmanaged/operator-owned assignments;
- не должен оставлять пользователя без требуемого рабочего access path;
- uncertain result переводится в explicit unknown/interrupted state и требует read-back/replan, а не POST replay.

Provider adapters обязаны сохранять существующий no-retry safety contract для state-changing операций: timeout/lost response/5xx после возможного применения mutation не является основанием для слепого повторения запроса.

##### Client Portal — Клиентский портал

`/start` должен оставаться полностью provider-neutral.

Пользовательские разделы:

- Профиль;
- Моя подписка;
- Купить / продлить;
- Трафик;
- Устройства;
- Помощь;

работают через Subscription / Entitlement / Provisioning services, а не через прямые control-plane callbacks.

Одинаковый UI может показывать нормализованный subscription summary:

~~~text
status
expires_at
traffic_used
traffic_limit
device_limit
subscription_url
~~~

но поле отображается только если provider/capability реально даёт достоверное значение.

Факт использования 3x-ui или Remnawave не обязан быть customer-facing detail.

##### Подсистема подписок

Для Remnawave сначала следует использовать нативную subscription subsystem и не переносить автоматически весь текущий 3x-ui compatibility proxy.

При Remnawave integration необходимо отдельно проверить:

- native subscription URL и lifecycle;
- subscription templates;
- client compatibility;
- HWID behavior;
- error semantics при unsupported/missing HWID;
- device list/delete behavior;
- rotation/revocation semantics;
- browser subscription page;
- headers, caching и privacy behavior.

`subscription_proxy.py` может остаться для 3x-ui и legacy compatibility. Для Remnawave собственный proxy допускается только при доказанной необходимости и должен быть тонким compatibility facade, а не дублировать всю subscription logic панели.

Нельзя вводить synthetic HWID, обходить provider enforcement или скрывать несовместимость клиента под ложным success.

##### Устройства и HWID

Общий Client Portal API может предоставлять:

~~~text
get_devices()
delete_device()
get_device_limit()
~~~

но provider adapter обязан возвращать capabilities и source semantics.

Для Remnawave HWID limit считается optional; поддержка зависит от client приложения и фактической передачи HWID header. UI должен различать:

- device management supported;
- HWID enforcement enabled;
- limit disabled for конкретного пользователя;
- unsupported client/no HWID;
- limit reached;
- provider error/unknown.

IP observations не должны переименовываться в физические устройства и не должны использоваться как замена HWID inventory.

##### Административный интерфейс инфраструктуры

При включённом Remnawave provider инфраструктурный UI не должен притворяться 3x-ui UI с переименованными labels.

Рекомендуемая модель раздела Remnawave:

~~~text
🌐 Инфраструктура
├─ 🖥 Ноды
├─ ⚙️ Config Profiles
├─ 📡 Inbounds
├─ 🌍 Hosts
├─ 👥 Internal Squads
└─ 🩺 Состояние
~~~

В multi-provider deployment допустимо сначала показывать выбор provider/context, затем provider-native entities.

Stable callback identity должна использовать стабильные UUID/IDs Remnawave, а не display name.

##### Host Control и жизненный цикл нод

Текущий Host Control Agent остаётся 3x-ui-specific boundary для точного allowlist управления `x-ui.service` и не должен искусственно расширяться до generic shell/container agent ради Remnawave.

Для Remnawave:

- сначала используются только documented provider API operations;
- если позже потребуется host/container control, проектируется отдельный restricted Remnawave Node Agent;
- agent не получает generic shell/SSH/exec/file browser/Docker API surface;
- разрешённые actions фиксируются allowlist;
- mutation имеет operation ID, persistent journal и no-replay semantics;
- потерянный POST response восстанавливается только read-only operation lookup;
- credentials отдельны от panel/API/bot/backup credentials;
- lifecycle нового agent проходит отдельный threat model, deploy runbook и acceptance.

##### Плавное выведение ноды из трафика

Концепт Node Drain сохраняется, но 3x-ui алгоритм attach-alternative-Inbound → prove → detach-target-Inbound нельзя напрямую копировать в Remnawave.

Перед реализацией Remnawave Drain нужен отдельный model/preflight, который как минимум определяет:

- target Node UUID;
- Config Profile и активные Inbounds target Node;
- Hosts, через которые этот Node представлен клиентам;
- Internal Squads/users, которым доступен соответствующий Inbound;
- существующие альтернативные Hosts/Nodes для той же access policy;
- blockers, при которых безопасного alternative path нет;
- active/unknown provider state;
- bounded review до mutation.

Mutation plan должен менять routing/visibility/access только после доказанного alternative path и завершаться read-back verification. Никакой автоматический destructive Stop/Restart Node не является частью graceful drain по умолчанию.

Partial/unknown/interrupted operation не replay-ится после restart; требуется новый preflight/replan.

##### API contract и dependency policy

Для Remnawave не следует делать production integration зависимой от случайного community SDK или archived/unmaintained SDK.

Предпочтительный подход повторяет существующий 3x-ui contract discipline:

~~~text
contracts/
├─ 3xui/
│  └─ ...
└─ remnawave/
   ├─ contract.json
   └─ openapi.json
~~~

Требования:

- pin поддерживаемой версии/commit/ref Remnawave API schema;
- хранить hash/source metadata;
- локальный typed/minimal HTTP client только для реально используемых endpoints;
- contract gate проверяет методы, auth, request/response shapes и критические поля;
- upstream schema drift не принимается автоматически;
- unknown/breaking changes fail closed;
- upgrade Remnawave требует отдельного compatibility PR/gate;
- provider-specific runtime exceptions документируются явно и тестируются.

##### Аутентификация и права RBAC

Telegram RBAC остаётся независимым от Remnawave authorization model.

Role names `Read-only`, `Support`, `Administrator`, `Owner` сохраняются как локальная security boundary.

Для Remnawave credentials:

- использовать least-privilege scoped token/API credential, если provider это позволяет;
- не выдавать боту глобальные права без необходимости;
- mapping локального privilege → provider capability/action фиксируется централизованно;
- UI filtering использует тот же privilege catalog, что и backend authorization;
- direct/stale callback не обходит privilege check;
- provider credential никогда не попадает в Telegram, audit payload или SQLite в открытом виде.

##### Журнал изменений, идемпотентность и восстановление

Provider-neutral mutation layer должен иметь единый safety contract:

- каждая destructive/state-changing workflow имеет локальный operation ID;
- request payload и target stable IDs journal-ятся в минимально необходимом виде;
- secrets/subscription URLs/HWIDs не пишутся в общий audit без необходимости;
- network timeout после отправки запроса считается uncertain;
- автоматический retry mutation запрещён, если provider не предоставляет доказанную idempotency key semantics;
- сначала выполняется provider read-back;
- startup recovery не повторяет mutation;
- состояние после crash/restart — recovered-success / recovered-failed / unknown/interrupted;
- Continue после unknown требует нового plan/preflight, если предыдущий post-condition нельзя доказать.

##### Обнаружение расхождений и сверка

Multi-provider deployment требует явного обнаружения расхождений между local desired state и remote actual state.

Нужно различать:

- expected;
- drifted;
- remote missing;
- local binding missing;
- unmanaged remote assignment;
- provider unavailable;
- uncertain;
- migration pending.

Автоматическое исправление drift допускается только для заранее определённых safe reconcile operations. Destructive correction требует явного workflow/confirmation либо отдельного доказанного safe policy.

##### Миграция 3x-ui → Remnawave

Поддержка Remnawave не должна означать big-bang migration.

Предпочтительный rollout:

1. ввести provider-neutral interfaces, не меняя production behavior 3x-ui;
2. перевести существующие 3x-ui workflows на `3xUIProvider` adapter и доказать behavior parity regression tests;
3. добавить read-only Remnawave client/contract и inventory screens;
4. добавить isolated test Remnawave environment;
5. реализовать create/read/update пользователя и access policy через Internal Squads;
6. добавить subscription/device capabilities;
7. выполнить controlled canary на тестовых users;
8. разрешить новым subscriptions выбирать Remnawave placement;
9. только после soak рассматривать миграцию существующих subscriptions;
10. legacy 3x-ui users могут продолжать обслуживаться параллельно до отдельного решения о retirement.

Миграция конкретного пользователя должна быть отдельной state machine, а не набором ручных callbacks.

Минимальные стадии:

~~~text
planned
preflight_ok
target_created
target_access_proven
subscription_ready
cutover_pending
cutover_proven
source_retirement_pending
completed
failed
unknown
~~~

До доказанного target access source account не удаляется автоматически.

Rollback semantics должны быть определены до первого production canary.

##### Commerce и entitlement при нескольких providers

Payment confirmation и entitlement остаются provider-neutral.

Критический контракт:

~~~text
payment = confirmed
        ↓
entitlement = provisioning
        ↓
provider provisioning
~~~

Provider outage не имеет права превращать уже подтверждённый payment в failed/unpaid.

Допустимые состояния:

~~~text
payment: confirmed
entitlement: provisioning
provider: unavailable
~~~

После восстановления provider reconcile продолжает entitlement workflow с read-back/idempotency safeguards.

Provider selection не должен зависеть от Telegram message history. Решение placement должно быть persistent и auditable.

##### Наблюдаемость и Attention Center

Multi-provider слой должен давать одинаково диагностируемые состояния:

- provider availability;
- auth failure;
- API compatibility mismatch;
- latency/timeouts;
- user/access drift;
- failed/unknown provisioning operations;
- subscription/device capability degradation;
- node/host health;
- migration state.

Attention Center может агрегировать эти данные, но не должен смешивать разные причины в одно "provider error".

Provider name, operation ID, stable remote target ID и last verified state допустимы в технической диагностике; secrets и customer subscription URLs — нет.

##### Резервное копирование и восстановление

Локальный Full Backup должен включать только те provider bindings/policies/journals, которые принадлежат самому боту.

Он не считается backup Remnawave Panel/Node infrastructure.

Отдельно должны быть документированы:

- какие remote provider данные восстанавливаются самим Remnawave;
- какие локальные mappings требуются для reconnect после restore бота;
- поведение при restore старой bot DB против уже изменившегося provider state;
- обязательный post-restore reconciliation/read-only inventory до любых mutations;
- отсутствие автоматического destructive "sync remote to local" после restore.

##### Безопасность, SSRF и сетевая граница

Remnawave API endpoint является privileged control-plane destination и проходит отдельную конфигурационную validation policy.

Нельзя разрешать admin callback передавать произвольный URL/host/path для provider requests.

Требования:

- endpoint задаётся только operator-owned config;
- HTTPS обязателен для remote production endpoint, кроме отдельно документированного private/local deployment contract;
- auth header/token не пересылается через redirects на другой origin;
- state-changing requests не follow redirects;
- timeouts bounded;
- response body bounded там, где endpoint может вернуть большой payload;
- proxy environment не используется неявно без отдельного решения;
- TLS verification не отключается production toggle'ом из Telegram UI.

##### Проверки регрессий и приёмкиs

До production включения Remnawave обязательны:

1. provider-neutral architecture regression для существующего 3x-ui behavior;
2. contract tests against pinned Remnawave schema/version;
3. read-only inventory smoke;
4. user create/update/disable/enable/delete safety tests;
5. Internal Squad safe/strict reconcile tests;
6. uncertain mutation / lost response tests без replay;
7. subscription URL secrecy tests;
8. HWID/device capability tests, включая unsupported client;
9. RBAC/IDOR/callback stable-ID tests;
10. multi-provider customer ownership isolation;
11. restart/startup recovery tests;
12. backup/restore binding reconciliation tests;
13. migration/cutover rollback test;
14. production canary на отдельной безопасной cohort;
15. soak минимум через restart/deploy/reconcile cycle;
16. documented disable/fallback path.

Remnawave rollout не считается принятым только потому, что API отвечает `200`.

##### Критерии завершения

Отложенный Remnawave track считается архитектурно завершённым только когда:

- Client Portal не содержит provider-name branching для обычных customer workflows;
- 3x-ui остаётся полностью рабочим через свой adapter;
- Remnawave работает через отдельный provider adapter и pinned contract;
- один deployment может безопасно обслуживать subscriptions разных providers;
- local payment/entitlement state не зависит от availability конкретной панели;
- access reconcile имеет provider-specific реализацию с общими safety invariants;
- subscription/device UI определяется capabilities;
- provider credentials и remote stable IDs защищены и минимизированы;
- mutation replay после timeout/restart отсутствует;
- migration 3x-ui → Remnawave имеет canary/rollback/recovery path;
- Admin UI показывает provider-native infrastructure model, а не вводящую в заблуждение 3x-ui эмуляцию;
- runbooks, Admin Setup, security model, backup/restore docs и acceptance evidence обновлены в том же implementation track.

До начала implementation отдельный design PR должен уточнить точную версию Remnawave, pinned API contract, перечень используемых endpoints, локальную schema migration, capability matrix и rollout plan. Этот roadmap-пункт фиксирует направление архитектуры, но не разрешает обход текущих v4 closure gates и не превращает Remnawave в скрытую зависимость базового Client Portal.


