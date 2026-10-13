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

