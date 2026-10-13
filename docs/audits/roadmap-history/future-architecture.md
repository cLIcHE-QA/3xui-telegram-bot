### Отложенные инфраструктурные улучшения

#### Географические metadata direct nodes

**Статус: ⬜ Запланировано. Не является блокером `v4.20.4` или обязательным условием перехода к `v5.0.0`.**

После стабилизации единого node display contract допускается добавить optional country metadata к direct nodes без привязки runtime logic к имени ноды.

Целевой контракт:

- стабильная identity остаётся `node_id`;
- `name` остаётся произвольным изменяемым display name;
- optional `country_code` хранится отдельно в формате ISO 3166-1 alpha-2, например `DE`, `FI`, `NL`;
- флаг Telegram UI вычисляется из `country_code`, а не угадывается по `name`;
- пример: `node_id=7`, `name=Frankfurt-1`, `country_code=DE` → `🇩🇪 Frankfurt-1`;
- legacy nodes без `country_code` продолжают работать; текущий name-based formatter может использоваться как presentation fallback;
- изменение `name` или `country_code` не меняет Direct Admin/Host Control bindings, credentials, backup identity и callback identity;
- onboarding/import flows получают country metadata только как отдельное optional поле с validation; миграция не должна требовать destructive schema rewrite.

До реализации этого пункта runtime и документация не должны вводить специальных условий для конкретной страны или production-ноды.

#### Мультиформатные подписки: raw / Xray JSON / Clash-Mihomo

**Статус: ⬜ Отложено. Не является блокером final v4 feature freeze, repository/public-release audit или открытия базового Client Portal v5. Реализация допускается отдельным compatibility track после закрытия текущих обязательных gates.**

Цель — не заменить существующий raw subscription path новым форматом, а добавить явную capability-модель нескольких представлений одной subscription identity. Один и тот же пользовательский `sub_id` может иметь несколько provider/client-facing представлений, но lifecycle подписки, entitlement и ownership остаются едиными.

Текущий v4 baseline остаётся каноническим:

- основной machine subscription — raw/share-link формат из 3x-ui: строки `vless://`, `vmess://`, `trojan://`, `vpn://` и другие поддерживаемые протоколы;
- `subEncrypt=true` означает Base64 encoding raw body и **не является криптографическим шифрованием**;
- `subscription_proxy.py` сейчас рассчитан именно на raw/HTML/info contract: проверяет локальную ownership по `sub_id`, проксирует штатную HTML page/assets, обрабатывает `?format=info` как metadata response и выполняет только reviewed client-compat transformations для raw machine subscription;
- существующие raw compatibility rules включают reviewed HWID/device header forwarding, AmneziaWG compatibility handling и узкий Shadowrocket fix для VLESS + XHTTP + Reality; эти правила не должны автоматически переноситься на JSON/YAML body без отдельного design review;
- raw path остаётся наиболее универсальным форматом и не должен исчезать даже после добавления других outputs.

##### Форматы 3x-ui и важное различие `format=info`

В актуальной subscription subsystem 3x-ui один Sub ID может обслуживаться несколькими отдельными paths:

~~~text
raw/share links  → subPath
Xray JSON        → subJsonPath  (subJsonEnable)
Clash/Mihomo     → subClashPath (subClashEnable)
~~~

Точные setting names/default paths перед implementation должны быть повторно проверены относительно **pinned 3x-ui version/contract**, а не приниматься из upstream `main` автоматически.

`?format=info` на обычном subscription path не является Xray JSON subscription. Это отдельный metadata/view-model response для traffic/expiry/status/UI polling. Нельзя использовать его как замену полноценному JSON client config и нельзя называть его JSON-подпиской в UI/API.

##### Семантическая разница raw и Xray JSON

Raw/share-link subscription передаёт прежде всего параметры отдельных соединений:

~~~text
server address / port
protocol
client UUID/password
transport
TLS/Reality parameters
SNI/serverName
public key / short id
flow
other protocol-specific URI parameters
~~~

После импорта клиент сам строит собственную runtime configuration, DNS, routing, selector/group policy и local inbounds.

Xray JSON представляет уже более целостную Xray client configuration. Помимо proxy outbounds он может включать:

~~~text
inbounds
outbounds
DNS
routing rules
policy
mux/observatory и другие Xray-native sections
~~~

Поэтому JSON полезен там, где оператор действительно хочет централизованно задавать Xray-native DNS/routing/policy и клиент гарантированно понимает такой format.

Для простой VLESS + Reality ноды JSON сам по себе не создаёт нового transport capability: те же connection parameters уже выражаются обычной `vless://` ссылкой. Переход на JSON не нужен только ради явного data-plane IP, Reality SNI, public key или `xtls-rprx-vision`.

##### Адрес data plane и идентичность протокола

Новый format не должен отменять принятый v4.x addressing contract.

Для любого client-facing representation должны одновременно сохраняться два независимых свойства:

~~~text
dial address  = operator-owned data-plane address
protocol identity = TLS/Reality SNI/serverName и другие identity fields
~~~

Пример корректной семантики:

~~~text
dial:       203.0.113.42:443
Reality SNI: www.example.com
~~~

В raw это выражается через host/IP в URI и отдельный `sni=`/Reality parameter. В Xray JSON — через `address`/port и отдельный `realitySettings.serverName` или эквивалентный pinned-schema field.

Acceptance нового JSON path обязан доказать, что operator-managed `shareAddrStrategy=custom` + `shareAddr` приводит к ожидаемому client dial endpoint и при этом не переписывает Reality/TLS identity, transport settings или keys.

Если конкретная версия 3x-ui JSON generator ведёт себя иначе, format нельзя считать принятым только потому, что endpoint возвращает HTTP 200. Silent DNS→IP persistence, неявная подмена SNI или скрытый rewrite JSON со стороны proxy запрещены без отдельного documented contract.

##### Protocol coverage и честная деградация

Raw, Xray JSON и Clash/Mihomo не считаются эквивалентными по protocol coverage.

По текущему upstream 3x-ui contract AmneziaWG и TUIC присутствуют в raw/share-link и Clash/Mihomo outputs, но исключаются из Xray JSON output. Перед implementation это поведение нужно перепроверить на pinned 3x-ui release.

Следствия:

- JSON не может автоматически стать единственным subscription format для пользователя, которому нужен AmneziaWG или TUIC;
- отсутствие protocol entry в JSON не должно маскироваться как полноценный parity success;
- UI/client capability layer должен уметь показать, что выбранный format не покрывает все назначенные пользователю protocols;
- запрещено синтетически переводить AmneziaWG/TUIC в «похожий» Xray outbound ради видимости parity;
- raw остаётся fallback/canonical broad-compat path;
- Clash/Mihomo рассматривается как отдельная capability, а не как «тот же JSON в YAML».

##### Целевая capability model

Формат подписки должен стать явной capability, а не набором scattered client-name checks.

Логическая модель может выглядеть так:

~~~text
subscription formats:
- raw_links
- xray_json
- mihomo_yaml

capabilities:
supports_raw_links
supports_xray_json
supports_mihomo
supports_hwid_headers
supports_protocol:<name>
supports_server_routing
~~~

Точные имена не являются контрактом. Важен принцип: Client Portal/domain layer спрашивает доступные formats/capabilities, а не делает ветвления вида `if client == "Hiddify"` или `if provider == "3xui"` в нескольких UI handlers.

Выбор format должен быть deterministic:

- explicit user/client choice либо documented capability mapping;
- stable URL/path;
- без случайного переключения body format только по `User-Agent`, если это меняет semantics;
- один `sub_id` остаётся stable subscription identity;
- rotation/revocation subscription identity должна согласованно инвалидировать все её representations.

User-Agent detection допускается только как bounded compatibility hint для уже доказанного client-specific workaround, как в текущих узких raw fixes. Он не должен становиться единственным источником истины о требуемом subscription format.

##### Архитектура compatibility proxy

Текущий `/compat/{sub_id}` не следует превращать в универсальный parser/rewriter всех subscription formats.

Рекомендуемая схема:

~~~text
                         3x-ui
                           │
             ┌─────────────┼──────────────┐
             │             │              │
          raw/sub       Xray JSON     Clash/Mihomo
             │             │              │
             ▼             ▼              ▼
      raw compat path   thin facade    thin facade
      (если нужен)      (если нужен)   (если нужен)
             │             │              │
             └─────────────┴──────────────┘
                           │
                     Client Portal
~~~

Правила:

- raw compat path сохраняет существующие proven transformations;
- JSON path не должен проходить через raw Base64/share-link parser;
- YAML path не должен проходить через JSON parser только ради унификации;
- если provider-native URL безопасно и совместимо работает напрямую, proxy не добавляется без причины;
- если proxy нужен для ownership/public URL/HWID/client compatibility, он остаётся thin facade с фиксированным upstream template/path;
- Telegram callback/user input не может передавать arbitrary upstream URL, path, Host header или provider endpoint;
- content type и body format сохраняются корректно;
- response size/timeouts bounded;
- redirects и origin changes не должны утекать auth/device headers на другой origin;
- `Cache-Control: no-store`/privacy semantics сохраняются там, где body содержит customer credentials.

##### HWID и метаданные устройств

Наличие JSON endpoint не означает автоматически, что HWID enforcement работает идентично raw path.

Перед production support нужно отдельно проверить для pinned 3x-ui/client combination:

- передаёт ли конкретный JSON-capable client `X-HWID`;
- какие device metadata headers он использует;
- применяет ли 3x-ui тот же HWID gate к JSON path;
- какие status/headers возвращаются при missing/unsupported HWID;
- поведение при full device limit;
- не меняется ли registration semantics при refresh JSON subscription.

Если JSON идёт через bot compatibility facade, разрешён только тот же reviewed allowlist HWID/device headers, который нужен реальному upstream contract. Значения HWID не логируются, не записываются в audit и не используются как synthetic/fallback identity.

Нельзя «чинить» JSON-клиент, который не умеет HWID, генерацией fake HWID на proxy. Unsupported client должен оставаться честным unsupported state.

##### Матрица совместимости клиентов

До показа альтернативных formats в Client Portal нужна явная проверяемая matrix минимум по используемым клиентам и версиям.

Для каждого client необходимо хранить/документировать:

~~~text
raw links: supported / unsupported
Xray JSON: supported / unsupported / partial
Mihomo YAML: supported / unsupported
HWID header: yes / no / unknown
Reality: supported
XHTTP: supported
AmneziaWG: supported
TUIC: supported
known compatibility workaround
last verified client version/date
~~~

Matrix должна опираться на production-like smoke/tests, а не только на заявление приложения о поддержке «Xray/V2Ray».

Raw path нельзя удалить только потому, что один preferred client хорошо работает с JSON.

##### Управляемые сервером DNS и маршрутизация

Главное функциональное преимущество Xray JSON — возможность централизованно передать Xray-native DNS/routing/policy.

Это одновременно увеличивает blast radius ошибки.

Поэтому:

- global JSON DNS/routing rules являются operator-owned config, а не произвольным user input;
- изменение routing template проходит отдельный review/regression;
- malformed/unsupported rule не должен молча превращаться в direct-all или proxy-all;
- private/local destinations и DNS behavior должны тестироваться отдельно;
- Client Portal не получает generic editor raw JSON;
- Telegram UI не должен позволять вставлять произвольные Xray snippets;
- provider-specific JSON template не становится источником бизнес-policy entitlement;
- rollback должен позволять отключить JSON format без изменения raw subscription identity.

##### Граница безопасности

Любой subscription representation остаётся customer secret/credential-bearing artifact.

Обязательные правила:

- полный subscription URL и `sub_id` не пишутся в общий audit/log/errors;
- JSON/YAML body не сохраняется в diagnostics/job details;
- server private keys никогда не попадают в client output;
- bot проверяет локальную ownership `sub_id` перед выдачей compat representation;
- unknown/invalid `sub_id` fail closed;
- provider endpoint/path задаётся только operator-owned config;
- никаких arbitrary remote fetch/proxy callbacks;
- TLS verification не отключается ради compatibility;
- URL query/headers из клиента проксируются только по explicit allowlist;
- секретные/device headers не forward'ятся на другой origin после redirect;
- unsupported/partial format не возвращается как ложный полноценный success.

##### Семантика ошибок

Новый format должен сохранять понятную ошибочную семантику:

- сетевые тайм-ауты/недоступность внешнего сервиса → ограниченная ошибка gateway/provider unavailable;
- malformed JSON/YAML → format generation failure, а не raw fallback под тем же content type;
- unknown subscription → not found/fail closed;
- HWID rejection → отдельный диагностически полезный state с allowlisted headers без раскрытия HWID;
- unsupported protocol mix → explicit partial/unsupported capability либо format не предлагается;
- lost upstream response не создаёт новую subscription identity и не запускает mutation;
- refresh format является read operation и не должен менять entitlement/provisioning state, кроме документированной provider-side device-registration semantics.

##### Последовательность реализации

Если track будет открыт, рекомендуемый порядок:

1. зафиксировать pinned 3x-ui subscription-server contract для raw/JSON/Clash paths и relevant settings;
2. добавить regression fixture/contract для текущего raw behavior до любых изменений;
3. ввести internal `SubscriptionFormat`/capability abstraction без изменения production URL;
4. добавить read-only provider capability discovery/config;
5. включить JSON subscription только на isolated/test 3x-ui environment;
6. проверить VLESS TCP Reality и XHTTP Reality: address/port, UUID, flow, SNI, public key/short ID и transport parity;
7. отдельно проверить operator-managed data-plane IP + неизменный Reality SNI;
8. проверить mixed subscription с AmneziaWG/TUIC и зафиксировать truthful unsupported/partial semantics;
9. проверить HWID-capable и HWID-incapable clients;
10. только при доказанной необходимости добавить thin JSON compat facade;
11. добавить Client Portal/UI выбор формата только после готовой capability matrix;
12. провести controlled production canary на test user/cohort;
13. сохранить мгновенный rollback: disable JSON/Clash presentation без изменения raw URL/`sub_id`.

##### Проверки регрессий и приёмки

Минимальный acceptance pack:

1. existing raw subscription byte/semantic behavior не регрессирует;
2. HTML subscription page и assets продолжают работать;
3. `?format=info` остаётся metadata path и не смешивается с Xray JSON;
4. JSON feature выключен → JSON URL не рекламируется клиенту;
5. JSON feature включён → валидный known user получает корректный content type/body;
6. unknown/stale `sub_id` fail closed;
7. VLESS TCP Reality raw vs JSON имеют одинаковые dial/identity semantics;
8. VLESS XHTTP Reality raw vs JSON сохраняют transport/Reality fields без случайного Shadowrocket-only rewrite;
9. `shareAddrStrategy=custom` + explicit `shareAddr` отражается ожидаемым dial address;
10. SNI/Reality identity остаётся неизменной при IP dial address;
11. AmneziaWG/TUIC absence в JSON отображается честно и raw path продолжает их выдавать;
12. HWID missing/unsupported/limit/reached behavior проверен для заявленных JSON clients;
13. reviewed HWID/device headers не логируются и не утекут на другой origin;
14. malformed/upstream unavailable response fail closed без подмены format;
15. no subscription URL/`sub_id`/HWID/private key leakage в logs/audit/jobs;
16. реальный импорт/refresh минимум в одном поддерживаемом Xray JSON client проходит end-to-end;
17. текущие production raw clients проходят regression smoke;
18. disable/rollback JSON возвращает систему к raw-only без rotation subscription identity.

Если позже добавляется Clash/Mihomo, для него выполняется отдельный format-specific acceptance, включая YAML parsing, protocol coverage, routing rules и реальные Mihomo clients. Успешный JSON smoke не считается автоматическим acceptance Clash/Mihomo.

##### Критерии завершения

Track считается завершённым только когда:

- raw остаётся стабильным canonical/fallback format;
- JSON/Clash появляются как явные capabilities, а не неявная замена raw;
- client capability matrix документирована и подтверждена smoke;
- data-plane IP и protocol identity сохраняют принятый addressing contract;
- unsupported protocol combinations отображаются честно;
- HWID behavior не ослаблен и synthetic identity отсутствует;
- proxy остаётся thin, fixed-target и secret-safe;
- provider-neutral subscription/domain layer не зависит от 3x-ui-specific path names;
- rollback не требует изменения `sub_id`, entitlement или provisioning;
- README/Admin Setup/subscription docs/security notes и regression tests обновлены в том же implementation track.

До открытия этого track текущая production policy не меняется: raw subscription + существующий `subscription_proxy.py` остаются каноническим и проверенным путём.

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


#### Региональные проверки с помощью сети проб Cheburcheck

**Статус: ⬜ Отложено. Не является блокером `v4.23.3`, `v4.24.0` или обязательным условием перехода к `v5.0.0`.**

Текущий minimal self-hosted Cheburcheck runtime (`website + PostgreSQL`) достаточен для static list/ASN diagnostics, но не даёт реальных региональных результатов без подключённых Probe reporters. Bot начиная с `v4.23.3` должен честно показывать отсутствие active scanners и не эмулировать regional data.

Цель отложенного улучшения — добавить собственный controlled Probe fleet без смешения его lifecycle с Telegram-ботом.

Рекомендуемая реализация в два этапа:

1. **Pilot.**
   - добавить central RMQTT к существующему self-hosted Cheburcheck runtime;
   - связать `website` с broker через отдельный `MQTT_ADMIN_TOKEN`;
   - предоставить probes только authenticated MQTT over WebSocket/TLS endpoint;
   - зарегистрировать один controlled Probe reporter с отдельными `PROBE_ID` / `PROBE_TOKEN` и metadata `region / ASN / provider`;
   - запустить probe на отдельном Linux/Docker host с outbound-only connectivity к broker и только необходимым `NET_RAW` capability;
   - подтвердить end-to-end path: Telegram check → Cheburcheck probe task → MQTT → reporter result → SSE → compact regional summary.

2. **Fleet.**
   - после успешного pilot развернуть несколько независимых reporters в разных сетях/регионах; ориентир для полезного первого fleet — минимум 3–5 probes, а не несколько probes в одном дата-центре;
   - выбирать точки так, чтобы они измеряли действительно разные network paths/ISP/regions, а не только разные VPS одного provider-а;
   - добавить health/readiness для online/offline reporters, `last_connected_at`, версию probe и безопасный operational inventory;
   - определить lifecycle credential rotation/revocation для каждого reporter отдельно;
   - зафиксировать controlled update/rollback procedure для probe packages/images;
   - при необходимости расширять fleet постепенно, не меняя Telegram result contract.

Граница безопасности и эксплуатации:

- RMQTT не должен принимать anonymous/unrestricted clients;
- каждый reporter имеет отдельные ID/token; token не переиспользуется между probes и не совпадает с bot/3x-ui/Host Control/Deploy Agent credentials;
- broker/admin token и probe tokens не хранятся в Telegram, Git или bot SQLite;
- bot не получает shell/container control над RMQTT или Probe hosts и только читает Cheburcheck API/SSE;
- Probe hosts не требуют публичных inbound management ports для обычной работы; основной data path — исходящее WSS/MQTT соединение;
- capability `NET_RAW` выдаётся только probe process/container и не означает общий privileged/root runtime;
- отсутствие части fleet или timeout отдельных reporters не должно превращать static Cheburcheck verdict в ошибку;
- UI показывает только фактически полученные regional responses и явно различает `нет активных сканеров`, `нет ответов` и `regional upstream unavailable`;
- backup/recovery для broker config, reporter registry/tokens и probe deployment является отдельной infrastructure responsibility и не включается автоматически в Full Backup Telegram-бота.

Этот пункт считается отдельной infrastructure-задачей средней сложности. Сам probe runtime лёгкий, но production-ready fleet требует broker/TLS/auth, нескольких независимых точек наблюдения, credential lifecycle, monitoring и runbook'ов.

### Усиление правил сопровождения публичного репозитория

**Статус: ✅ Выполнено 2026-10-07. A-007 технически закрыт полностью.**

После перевода repository в public GitHub-side governance подтверждён двумя active rulesets.

Branch ruleset **Protect main release path** (ID `24575428`):

- PR обязателен;
- merge только `squash`;
- strict required checks `test` и `title`;
- deletion и non-fast-forward запрещены;
- linear history обязательна;
- bypass actors отсутствуют.

Tag ruleset **Protect release tags** (ID `24615100`):

- target: `refs/tags/v*`;
- применение правил: активно;
- `update`, `deletion` и `non_fast_forward` запрещены;
- bypass actors отсутствуют;
- `current_user_can_bypass=never`;
- creation новых release tags не запрещена, поэтому штатный release workflow сохраняет возможность публиковать новые `vX.Y.Z`.

После включения ruleset существующий `v4.26.8` по-прежнему указывает на `e096bf436425ea037399e290a5a54f54c729b352`.

A-007 больше не имеет residual accepted risk: branch и release-tag paths защищены GitHub-side enforcement, а release workflow остаётся единственным штатным способом публикации новых tags/releases.

### v5.0.0 — Client Portal — Клиентский портал

**Статус: 🟠 Опубликовано; acceptance отложен (controlled-canary `v5.0.0-rc.9`).** Backend foundation и pilot Client Portal опубликованы в immutable prerelease; production deployed `rc.9` подтверждён только оператором. Общий v5 acceptance **NOT PASS**, G-01…G-11 остаются `PARTIAL/PENDING`; stable `v5.0.0` не опубликован, публичный launch закрыт allowlist/launch-gates.

Рекомендуемый порядок первой реализации и фактический прогресс:

1. 🟡 customer ownership/auth boundary + feature flag/allowlist без публичного открытия — pilot boundary действует через существующий allowlist/admin policy; public signup, dedicated abuse/rate-limit policy и полный ownership audit ещё не завершены;
2. ✅ долговечные состояния Order / Payment / Entitlement и контракт миграций — PR #290–#294, schema v8, атомарное подтверждение, журнал webhook, сверка после рестарта и устойчивый checkout ID;
3. ✅ provider-neutral customer/subscription service boundary поверх текущего 3x-ui provisioning — `client_access.py` работает через `CustomerPortalService`, provider contract задан `CustomerAccessProvider`, а текущие 3x-ui reads изолированы в `customer_provider_xui.py`; Telegram handlers больше не импортируют `XUIClient`, `Database` или `CommerceService` напрямую;
4. ✅ read-only Client Portal skeleton: Профиль / Моя подписка / Трафик / Устройства / Помощь — PR #296; legacy `/create` / `/inbounds` больше не являются mutation-entrypoints;
5. 🟡 commerce flow + authenticated/idempotent payment event journal — backend journal/state machine и provider-neutral checkout foundation готовы; следующий production path использует native Telegram Stars (`XTR`) для цифровой подписки внутри бота: отдельная Stars-цена тарифа, pre-checkout ownership/amount validation и atomic `successful_payment → Payment confirmed → Order paid → Entitlement` реализуются; после #305 Terms acceptance, `/paysupport` и one-shot refund journal/операторский flow реализованы; остаются test/prod payment smoke и production acceptance;
6. ✅ entitlement → выдача доступа/сверка с правилами no-replay/unknown — PR #292/#295; очередь pending не повторяет `provisioning` при неопределённом результате;
7. 🟡 onboarding/QR UX и self-service diagnostics реализуются в #306: platform selection, local/private QR и read-only entitlement/provider diagnostics; client-specific deep-link остаётся отложен до стабильного безопасного import contract;
8. 🟡 отдельный v5 launch audit выполняется в #308: repository-verifiable ownership/payment/secret/rollback controls закреплены regression gate; production Stars acceptance, failure/restart canary и load/soak остаются release blockers; retention-policy disposition закрыт в `docs/DATA_RETENTION.md`;
9. ⬜ controlled canary rollout по описанному ниже gate;
10. ⬜ только после canary — расширение публичного доступа.

Фактическая v5 foundation-линия на 2026-10-07: #290–#303 уже в `main`, а #304 остаётся открытым draft PR.

После #302 core backend path уже собран сквозным каркасом: `Plan/Order → checkout boundary → Payment → authenticated webhook → Entitlement → Provisioning`. Для цифровой подписки внутри Telegram #304 переводит customer payment entrypoint на native Telegram Stars вместо внешнего PSP checkout. После merge production commerce блокируют уже не выбор PSP, а Stars acceptance: #305 закрывает Terms acceptance UX, `/paysupport` и one-shot refund workflow через Telegram Bot API; после него остаются test/prod payment smoke и controlled canary.

- #290 — commerce foundation;
- #291 — atomic `payment.confirmed → order paid → entitlement`;
- #292 — entitlement → safe provisioning;
- #293 — authenticated payment webhook gateway;
- #294 — payment-event restart reconciliation;
- #295 — durable entitlement fulfillment worker;
- #296 — pilot Client Portal shell;
- #297/#298 — subscription browser compatibility hotfixes, необходимые для корректной customer subscription page;
- #300 — отдельные nginx limits для `/compat/assets/`, подтверждённые на Safari/WebKit;
- #301 — provider-neutral customer service boundary: Client Portal больше не зависит напрямую от `XUIClient`/DB/Commerce;
- #302 — независимая от провайдера основа оплаты, schema v8, устойчивый checkout URL/idempotency и кнопка оплаты Telegram;
- #304 (текущий срез) — native Telegram Stars для цифровой подписки: schema v9, независимая Stars-цена тарифа, XTR invoice/pre-checkout/successful-payment lifecycle.

До перехода к public launch основными implementation-блокерами остаются production acceptance Telegram Stars (после #305 остаются test/prod smoke и acceptance возвратов), после #306 остаются client-specific deep-link при наличии стабильного import contract, production Stars smoke/acceptance, затем launch audit + controlled canary.

Отложенные tracks **не блокируют** базовый v5.0.0: multi-format subscriptions, Remnawave/provider-neutral multi-provider expansion и Cheburcheck Probe fleet могут идти отдельными subsequent tracks после стабилизации core Client Portal. При этом верхний customer/domain слой v5 сразу проектируется так, чтобы не зависеть напрямую от `XUIClient`.

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

