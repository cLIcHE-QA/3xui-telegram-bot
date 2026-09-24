# 3x-ui OpenAPI compatibility contract

Этот документ описывает fail-closed compatibility gate между ботом и native API 3x-ui.

## Поддерживаемая версия

Текущий pinned contract:

- 3x-ui: `v3.8.5`;
- upstream repository: `MHSanaei/3x-ui`;
- upstream schema: `frontend/public/openapi.json` из тега `v3.8.5`;
- upstream Git blob SHA: `d1f9b499e43d4370d68fdf9ca6045e1d967b42ad`;
- vendored copy: `contracts/3xui/v3.8.5/openapi.json`;
- manifest используемого bot API surface: `contracts/3xui/contract.json`.

Schema берётся из immutable release tag, а не из upstream `main`. CI не скачивает OpenAPI из сети и поэтому не меняет compatibility contract самопроизвольно.

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

В OpenAPI 3x-ui v3.8.5 этот endpoint описан generic JSON response envelope, тогда как фактический endpoint выдаёт database backup как binary attachment.

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
