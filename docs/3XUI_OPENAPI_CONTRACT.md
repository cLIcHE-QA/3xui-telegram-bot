# 3x-ui OpenAPI compatibility contract

Этот документ описывает fail-closed compatibility gate между ботом и native API 3x-ui.

## Поддерживаемая версия

Текущий pinned contract:

- 3x-ui: `v3.10.0`;
- upstream repository: `MHSanaei/3x-ui`;
- upstream schema: `frontend/public/openapi.json` из тега `v3.10.0`;
- upstream Git blob SHA: `b50cb368f43bd54583189453ce96ceebc431b2a5`;
- vendored copy: `contracts/3xui/v3.10.0/openapi.json`;
- manifest используемого bot API surface: `contracts/3xui/contract.json`.

Schema берётся из immutable release tag, а не из upstream `main`. CI не скачивает OpenAPI из сети и поэтому не меняет compatibility contract самопроизвольно.

В #663 используется существующий `POST /panel/api/clients/update/{email}` с query-фильтром `inboundIds` по одному Master Inbound ID. Фильтр подтверждён на закреплённом реальном сервисном коде v3.10.0 и временной SQLite ([PR #665](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/665)); OpenAPI surface/method/Bearer/body не меняются. Отсутствие в machine-schema явного описания query-фильтра не подменяет upstream source-parity evidence. Напрямую Node API не изменяется, чтение Node Panel независимо и остаётся только read-only.\n\nПри подготовке rc.11 выявлены два edge cases pinned 3x-ui v3.10.0: `ClientRecord.reverse` сериализуется строкой `""` для обычного клиента; `model.Client.flow` использует `omitempty`, поэтому поле Flow выбранного Inbound при `none` может отсутствовать. Scoped editor принимает пустой reverse без преобразования, непустой fail closed; отсутствие Flow у подтверждённого клиента означает `none`. Offline regression не заменяет Node/Xray acceptance.

Начиная с `v4.25.0` bot API surface включает reviewed client-connections routes: `POST /panel/api/clients/ips/{email}`, `POST /panel/api/clients/hwids/{email}` и `DELETE /panel/api/clients/hwids/{email}/{id}`. Текущий manifest содержит **55** endpoints, включая `GET /panel/api/hosts/list` (Issue #422 / PR #424). При переходе `v3.9.0 → v3.10.0` этот используемый surface сохранил route/method, Bearer auth, request body/media/mandatory fields и проверяемый JSON response envelope; runtime client changes для contract parity не потребовались. Новая upstream schema имеет 184 paths; 55/55 используемых operation definitions byte-equivalent по структурному сравнению pinned v3.9.0/v3.10.0. Новые возможности v3.10.0 (MASQUE, XDRIVE, обновлённая Node sync) и изменение неиспользуемых операций не становятся автоматически поддержанными ботом.

При изменении `contracts/3xui/contract.json` или vendored `contracts/3xui/**/openapi.json` Living Docs требует синхронного изменения этого документа в том же PR (`require_all`, без waiver). Изменения API-клиентов `xui.py` / `version_api.py` требуют review документа либо точного обоснованного waiver. Semantic test сверяет количество endpoints с manifest; это не требует обновления pinned upstream версии при расширении уже существующего API surface.

**#663 / multi-protocol fleet follow-up:** У 3x-ui v3.10.0/v3.10.2 общий ClientRecord хранит поля WG/AWG вне VLESS inbound; их присутствие нельзя трактовать как мусор и удалять. Текущий scoped payload из `xui.py` не сериализует эти поля. Для подготовки fix #663 guard может быть условно снят **только при успешной read-only аттестации всей attachment/peer-карты** (`tunnelAllowedIPs` и точный email на каждом tunnel inbound), исключении peer-полей из VLESS payload и доказанном сохранении существующих peer-полей общим upstream service и совпадающем fingerprint; MTProto, reverse, missing/ambiguous связи по-прежнему fail closed. Go/SQLite upstream service integration на v3.10.0/v3.10.2 является обязательным pre-merge gate, а production Flow POST остаётся запрещённым до отдельного разрешения. Пагинация чтения ограничена 64 нодами, 256 inbound и параллелизмом 8. Новые API endpoints не добавляются; bot API contract pinned v3.10.0, а v3.10.2 требует отдельного evidence.

Для #663 безопасные коды `CLIENT_RECORD_MISSING`, `CLIENT_RECORD_NULL`, `CLIENT_RECORD_PROTOCOL_WG`, `CLIENT_RECORD_PROTOCOL_MTPROTO`, `CLIENT_RECORD_PROTOCOL_MIXED`, `CLIENT_RECORD_REVERSE` уточняют причину отказа Master preflight в Telegram. Клиентские поля, структура POST и требования к полноте общего record не меняются; это диагностика без обхода safety checks. Production root cause `CLIENT_RECORD` на rc.12 пока не доказан и требует нового targeted read-only UI наблюдения после отдельно разрешённого Release/deploy.

Для #659 read-only сопоставление Node inbound tagsДля #659 read-only сопоставление Node inbound tags учитывает строго одну native alias-форму `n<node_id>-` в соответствии с закреплённым [upstream v3.10.0 remote tag cache](https://github.com/MHSanaei/3x-ui/blob/v3.10.0/internal/web/runtime/remote.go). API endpoints и schema не меняются. Дубли/коллизии остаются `UNKNOWN`, Node Panel не аттестует работающий Xray. Для #663 отказ preflight теперь выдаёт ограниченный фиксированный код причины, не сырой API response; full-row/identity/membership/nonce проверки, POST и запрет прямого Node write не меняются.

## Что проверяет CI

`python3 scripts/check-3xui-openapi-contract.py` сопоставляет три источника истины:

1. vendored OpenAPI должен иметь exact Git blob SHA pinned upstream schema;
2. каждый endpoint из `contracts/3xui/contract.json` должен существовать с тем же HTTP method;
3. request body semantics, media type и mandatory fields должны совпадать с pinned OpenAPI там, где схема их объявляет;
4. JSON response envelope должен сохранять используемые поля `success`, `msg`, `obj`;
5. API operation должен по-прежнему поддерживать Bearer authentication;
6. AST scan `xui.py` и `version_api.py` должен давать ровно тот же набор panel API routes, что и manifest.

Поэтому новый вызов `/panel/api/...` нельзя тихо добавить в client code: CI потребует одновременно проверить его в pinned OpenAPI и явно добавить в manifest.

Gate также падает, если из новой schema исчезает route/method, меняется обязательность body, media type, набор mandatory request fields или используемый response envelope.

## Почему schema vendored

Network fetch из upstream во время обычного CI запрещён намеренно:

- upstream `main` может измениться независимо от этого проекта;
- transient GitHub/network failure не должен определять совместимость production release;
- review должен видеть schema diff в том же PR, который меняет supported 3x-ui version;
- release должен быть воспроизводимым после публикации.

Vendored OpenAPI не используется runtime-кодом для автоматического переключения API behavior. Это CI/review contract.

## Исключение: `GET /panel/api/server/getDb`

В OpenAPI 3x-ui v3.10.0 этот endpoint по-прежнему описан generic JSON response envelope, тогда как фактический endpoint выдаёт database backup как binary attachment.

Поэтому для `GET /panel/api/server/getDb` OpenAPI gate проверяет route, HTTP method и Bearer auth, но не применяет общий JSON-response-envelope check. Binary download semantics отдельно покрываются runtime regression tests `XUIClient.download_database()`.

Это исключение должно оставаться единственным и явно записано в `documented_exceptions` manifest. Новое ослабление response checks требует отдельного review.

## Как обновлять supported 3x-ui

При переходе на новую версию панели:

1. выбрать конкретный upstream release tag, не ветку `main`;
2. взять `frontend/public/openapi.json` именно из этого tag;
3. добавить новую vendored copy в `contracts/3xui/<version>/openapi.json`;
4. обновить `supported_3xui_version`, upstream ref/blob SHA и schema path в manifest;
5. запустить checker и полный regression suite;
6. разобрать каждый compatibility failure явно:
   - изменённый route/method;
   - новый mandatory field;
   - новый media type;
   - изменённый response contract;
   - новый или удалённый client route;
7. только после review обновить runtime client, если upstream contract действительно изменился;
8. выполнить integration smoke против реальной панели поддерживаемой версии до production acceptance.

Нельзя заставлять checker принимать новую schema удалением endpoint из manifest, если runtime всё ещё вызывает его. Source parity специально блокирует такой обход.

## Переход v3.9.0 → v3.10.0: граница production rollout

Обновление pinned schema в `main` — **CI/contract scope**, не установка панели и не релиз бота. У upstream `v3.10.0` изменены миграции Xray-конфигов (xdns/udpHop/Shadowsocks-2022), systemd sandbox и bundled CA roots; Node sync fixes требуют обновить **все** ноды, не только Master. Для клиентских port hopping/xdns нужен подходящий Xray-core. Preflight: backup с проверяемой restore-совместимостью, фактические версии Master/direct nodes, TLS/CA, custom `ReadWritePaths`, rollout/rollback/STOP и отдельное окно обслуживания. До production перехода необходимы изолированные интеграционные проверки и отдельное разрешение оператора; отсутствие этих evidence означает PENDING, не PASS. [Upstream release](https://github.com/MHSanaei/3x-ui/releases/tag/v3.10.0), [Issue #630](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/630).

## Runtime boundary

Compatibility gate не является runtime service discovery и не добавляет fallback на неизвестные API variants.

Bot продолжает использовать только явно реализованные endpoints. Если установленная панель несовместима с поддерживаемым contract, это должно проявиться как явная ошибка/blocked operation, а не как автоматическое переключение на непроверенную schema.

## Локальная проверка

Проверка запускается из repository checkout на host/CI runner. Каталог `scripts/` намеренно исключён из production Docker image через `.dockerignore`, поэтому checker не является runtime-командой контейнера.

~~~bash
python3 scripts/check-3xui-openapi-contract.py
python -m unittest tests.test_v417_openapi_contract -v
~~~

Успешный checker печатает pinned version, количество покрытых endpoints и upstream blob SHA.
