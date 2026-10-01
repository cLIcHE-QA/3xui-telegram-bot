# Client-side routing profiles for subscription clients

Этот runbook описывает operator-side настройку client-side routing profiles в 3x-ui для клиентов, которые умеют получать routing metadata/profile через subscription.

Документ намеренно не привязан к конкретному routing provider, стране или набору правил. Используй operator-controlled или заранее проверенный постоянный HTTPS URL, например:

~~~text
https://routing.example.com/profile.json
~~~

## Что это делает

Client-side routing profile управляет правилами маршрутизации **в VPN-клиенте** после получения или обновления subscription.

Это не server-side Xray routing и не меняет:

- 3x-ui node routing;
- Inbound listen address/port;
- `shareAddrStrategy` / `shareAddr`;
- Reality/TLS SNI;
- server firewall;
- provisioning/access policy пользователя.

Поэтому client routing не заменяет data-plane readiness и не должен использоваться для исправления неправильного client endpoint.

## Общий contract

Для remote profile предпочтителен постоянный verified HTTPS URL:

~~~text
https://routing.example.com/profile.json
~~~

URL не должен содержать credentials, tokens, `sub_id`, user identifiers или другие secret-like query values.

Routing source рассматривается как внешний read-only policy source. Его временная недоступность не должна приводить к destructive subscription/provisioning mutations.

## Happ

В текущем 3x-ui operator UI настройки находятся на вкладке `Happ`.

Базовая конфигурация:

~~~text
Автоопределение заголовков Happ: ON
Включить маршрутизацию: ON
Правила маршрутизации:
https://routing.example.com/profile.json
~~~

`Режим No-Limit` не является частью routing contract и включается только по отдельной operational причине.

`Скрыть настройки сервера` также не требуется для включения маршрутизации.

Поле routing rules может принимать готовый Happ deeplink вида:

~~~text
happ://routing/onadd/...
~~~

Для постоянного внешнего JSON profile предпочтителен прямой HTTPS URL, если текущая production/pinned версия 3x-ui поддерживает такой режим.

Не применяй preset отключения routing одновременно с включённой routing policy.

## Incy

В текущем 3x-ui operator UI настройки находятся на вкладке `Incy`.

Базовая конфигурация:

~~~text
Включить маршрутизацию: ON
Правила маршрутизации:
https://routing.example.com/profile.json
~~~

Поле также может принимать готовый Incy deeplink вида:

~~~text
incy://autorouting/onadd/...
~~~

Для постоянного remote JSON profile предпочтителен прямой HTTPS URL, если текущая production/pinned версия 3x-ui поддерживает самостоятельное обновление такого profile.

В фактическом поле панели используй обычный URL `https://...`, а не экранированное представление `https\://...`.

## Сохранение и применение

Routing settings относятся к panel/subscription configuration.

После изменения через текущий 3x-ui UI:

1. нажми `Сохранить`;
2. если панель требует restart для применения, нажми `Перезапустить панель`;
3. после restart проверь обычную доступность panel/subscription endpoint;
4. только затем обновляй subscription в тестовом клиенте.

Panel restart не означает обязательный restart Xray service. Не используй Xray/service restart как fallback, если UI требует только panel restart.

## Native 3x-ui subscription и bot compatibility proxy

Нативная 3x-ui subscription и публичный bot path `/compat/{sub_id}` — разные transport boundaries.

Текущий `subscription_proxy.py` намеренно использует explicit allowlist response headers и не является прозрачным reverse proxy всех upstream headers/metadata.

Поэтому настройка routing в 3x-ui **не доказывает**, что routing metadata автоматически доходит через `/compat/{sub_id}`.

До отдельного proxy implementation/acceptance действует следующий contract:

- native 3x-ui subscription routing проверяется отдельно;
- routing через `/compat/{sub_id}` считается непроверенным, пока необходимые client-routing metadata не добавлены в explicit allowlist и не покрыты regression/client smoke;
- нельзя расширять proxy до passthrough-all headers ради routing;
- новые response headers/metadata добавляются только явным allowlist с проверкой privacy и cross-client semantics;
- Happ и Incy проверяются независимо: metadata одного client integration не должна случайно применяться другим клиентом.

## Проверка после настройки

Acceptance выполняется на отдельном test user/subscription, а не только по состоянию toggle в UI.

Минимальная последовательность:

1. сохранить routing settings и выполнить требуемый panel restart;
2. убедиться, что subscription endpoint снова доступен;
3. обновить **native** 3x-ui subscription в соответствующем тестовом клиенте;
4. подтвердить, что routing profile появился/активировался ожидаемым способом;
5. проверить несколько deterministic destinations из тестового profile: как минимум один expected proxy и один expected alternate/direct route, если policy их различает;
6. убедиться, что VPN connectivity и обычные server entries не изменились;
7. если production URL идёт через `/compat/{sub_id}`, повторить тот же smoke через compat path;
8. различие native PASS / compat FAIL фиксировать как proxy compatibility finding, а не как проблему routing source;
9. проверить второй client отдельно, если Happ и Incy включены одновременно.

Не используй реальный customer account для первого acceptance, если доступна безопасная test subscription.

## Диагностика

Если routing не применился:

1. сначала проверь client-specific routing toggle;
2. проверь сохранение и обязательный panel restart;
3. проверь доступность HTTPS JSON URL;
4. проверь native 3x-ui subscription отдельно от `/compat/{sub_id}`;
5. проверь фактический client refresh/import;
6. только после этого исследуй client-specific metadata/headers.

Не меняй server-side Xray routing, Inbounds, Reality SNI или data-plane address в попытке исправить client-side routing metadata.

## Security / privacy

- routing URL — operator-owned configuration;
- не принимай произвольный routing URL из Telegram callback/user input;
- remote URL должен использовать verified HTTPS;
- не отключай TLS verification ради compatibility;
- не помещай credentials/tokens в URL;
- routing profile не должен содержать subscription URL, `sub_id`, customer identifiers или server private keys;
- proxy не должен пересылать secret/device headers на другой origin после redirect;
- полный remote JSON не сохраняется в audit/job history;
- в audit достаточно bounded technical state без query/secrets.

## Regression contract для будущего proxy support

Если routing metadata будет добавляться в `subscription_proxy.py`, минимальный gate:

1. существующие raw subscription transformations не меняются;
2. routing headers/metadata добавляются только explicit allowlist;
3. Happ получает только Happ-compatible routing semantics;
4. Incy получает только Incy-compatible routing semantics;
5. обычный клиент без соответствующей capability не получает неожиданный routing payload;
6. HWID/device forwarding остаётся без изменений;
7. unknown `sub_id` по-прежнему fail closed;
8. redirects не приводят к утечке client/device headers;
9. logs/audit не содержат routing body, subscription URL, `sub_id` или HWID;
10. native и compat client smoke проходят на контролируемом test user;
11. отключение client routing возвращает прежнее subscription behavior без rotation `sub_id`.

До закрытия такого gate production documentation не должна утверждать, что `/compat/{sub_id}` поддерживает Happ/Incy routing автоматически.
