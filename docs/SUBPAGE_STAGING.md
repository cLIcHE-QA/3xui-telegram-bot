# #887 — изолированный staging Telegram + HTTPS (D2d, до deployment)

**Статус:** D2d source/template уже MERGED ([#904](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/904), Roadmap [#905](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/905)), **не deployed и не live accepted**. D2e default-off preflight **MERGED** ([#906](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/906), Roadmap [#907](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/907)), но **не deployed и не live accepted**. Каноническая [архитектура #887](WEB_SUBSCRIPTION_MINI_APP.md), [Roadmap](ROADMAP.md), [Client Setup](CLIENT_SETUP.md), [Git workflow](GIT_WORKFLOW.md). Реальный Bot API, VPS, DNS, сертификат и телефонные браузеры в этом PR не проверялись; G-11 PARTIAL/NO-GO, public rollout BLOCKED.

## Границы и режим исполнения

Изолированный entrypoint `subscription_page_staging.py` не импортируется из `app_runtime.py` и никогда не изменяет production dispatcher, bot menu, `/compat/`, 3x-ui или `bot.sqlite3`. При импорте ничего не запускает; без `--run-approved-staging` выполняет только локальную проверку приватного JSON. Даже с этим аргументом обязательны одновременно `mode=isolated-staging`, `enabled=true`, `edge_reviewed=true`, отдельный бот с проверенным `getMe`, отсутствие webhook, отдельный разрешённый оператором HTTPS hostname, конкретный localhost port и owner allowlist. **Одна разрешённая staging Bot polling копия, один host/локальная SQLite, без NFS или второго bot-процесса.** Не публиковать listener на `0.0.0.0`. Никаких admin/3x-ui/provider/real-subscription данных: `_SyntheticCustomer` выдаёт только `unknown` + текст "синтетические данные"; feature flags изолированы от production. Это не может подтверждать реальные entitlement/traffic/HWID.

`deploy/subpage-staging/staging-config.example.json` — заведомо инертный шаблон: `enabled=false`, `edge_reviewed=false`, `staging.example.invalid`, фиктивные ID, порт и пути. Никаких working credentials, готового DNS/cert и source secrets в Git. До отдельного разрешения нельзя менять эти значения на реальные и стартовать процесс/ingress. Не публиковать реальные token, ID allowlist, private config, cookie, challenge, скриншот подписки или внутренние адреса в PR, GitHub Actions artifacts/логах/чате.

**Обязательный предварительный review конфигурации:** выделенный хост/DNS без production сервисов, подтверждённое владение доменом, TLS certificate SAN/SNI/chain, отдельный зарегистрированный BotFather staging-бот (имя содержит `staging`, заканчивается на `bot`), действующий `getMe` с точным ожидаемым Bot ID/username, отсутствие webhook/второго poller. Изолированный приватный каталог владельца `0700`, внутри `staging-config.json` и `staging-bot.token` с mode `0600`, отдельный `standalone-pilot.sqlite3` (создаётся owner-only ledger, mode `0600`). Симлинки, иные имена token-файлов, иные каталоги, root/public bind и неверные права отклоняются; основную БД бота использовать запрещено. Токен передаётся только через 0600-файл, **не** CLI/environment, URL, GitHub secret или общий `.env`. Предусмотреть ротацию/отзыв staging-токена, безопасное удаление staging-сессий и локального SQLite по согласованной процедуре.

## HTTPS ingress и лимиты

`deploy/subpage-staging/nginx-d2d-staging.conf.example` — **не подключённый** пример Nginx для отдельного staging host; его `staging.example.invalid`, `/etc/subpage-staging/tls/*`, `/srv/subpage-staging/dist` и `127.0.0.1:8827` — placeholders/локальный upstream, не реальные значения. Нужен отдельный default-deny HTTP/HTTPS vhost, deny на чужие Host и TLS SNI, верификация публичной цепочки/SAN, TLS 1.2/1.3, безопасная политика логов/сертификатов и rollback. HTTPS static build должен содержать оригинальные self-hosted assets, без CDN/аналитики; никаких client bearer URLs в странице. Экспонируются только `/`, локальные `/assets/` и пять существующих standalone API routes (start/complete/cancel/logout/me). `/compat/`, `/admin/`, `/approve`, webhook, произвольные proxy paths запрещены.

**Nginx edge как обязательный security boundary (per TCP peer):**
- `POST /start`: `5r/m` на адрес TCP peer + burst 2, `429` при превышении.
- `POST /complete`: `12r/m` + burst 3, `429`.
- Все разрешённые API routes: `5r/s` + burst 10; не более **4 одновременных соединений** per peer.
- Request body максимум `2k`, bounded timeouts, no access log, `no-store`, `no-referrer`, restrictive CSP, Host/SNI fail-closed и очищенные `Authorization`/`Forwarded`/пользовательские `X-Forwarded-*`. При пересечении бюджетов применяется любой строгий лимит; результат должен быть доказан негативными тестами с подделанным `X-Forwarded-For`.

**Важное ограничение:** `request.remote` внутри localhost Python видит адрес Nginx и не является пользовательским rate limit. Нельзя доверять `X-Forwarded-For` без vetted доверенного TCP источника. Этот staging-профиль предполагает **прямое** клиентское TLS-подключение к отдельному Nginx; за CDN/LB/NAT агрегированные IP лимиты могут стать неточными. Если topology включает CDN/LB, политика `real_ip`, anti-spoof, individual rate budgets и DoS нужно проектировать и тестировать заново до открытия ingress. CI loopback `127.0.0.2` не доказывает реальный внешний edge или DDoS-защиту.

## Anti-phishing, состояние и защита от replay

Stand­alone браузер показывает весь 16-символьный случайный публичный challenge и адрес в browser address bar. **Только при `display_full_challenge=True` staging-бот после owner/private/allowlist проверок показывает весь этот же 16-символьный код, полный HTTPS origin и предупреждение сверить все символы, источник и факт *собственного* инициирования запроса**. Действующий D2b/D2c default режим по-прежнему показывает только последние 4 символа. Код является публичным ID, **не** credential; он не заменяет защищённую browser binding cookie. `/web_login <code>` принимается только как verified private Telegram Update от самого разрешённого owner без пересылки/группы/чужих callback; кнопка `Подтвердить` требует отдельного явного действия, связана с message ID/chat/owner/TTL и одноразовым nonce. Cookie выдаётся только исходному браузеру после однократного atomic CAS, а не в Telegram.

**Нельзя считать сравнение кода полной защитой от phishing/relay:** владелец способен сознательно или по обману подтвердить чужой вызов. В targeted negative/live acceptance нужно доказать безопасные тексты/UX, сообщение только в официальном staging-чате, отмену чужого запроса, несоответствующего HTTPS origin, невозможность авторизации другого браузера, replay, expiry, cross-account, feature revocation. Секреты подписки, инициирующий Telegram ID и приватные ссылки не должны появляться в HTML, URL, cookie logs, Referrer и third-party requests.

## Обязательные проверки перед любым live device smoke

1. **Source и permissions:** прочитать точный SHA staging PR, убедиться, что `app_runtime.py` и production config не изменены; проверить закрытый файловый каталог, отдельную staging token identity, disable/default-off, синтетический DTO и возможность stop/revoke/rollback без production mutations.
2. **TLS/DNS/Host/SNI:** только после отдельного operator approval доказать настоящий SAN/chain/SNI, редиректы/HTTP denial, уникальный vhost и запрет чужих Host/forwarded заголовков. В CI `tests/test_subscription_page_staging_https.py` поднимает **только ephemeral loopback** Nginx + self-signed сертификат и fake upstream.
3. **Rate/request proof:** синтетические реальные Nginx `429` на start и complete, `413` на 2k body, запрет скрытых путей, spoofed XFF, другой TCP peer; затем независимый read-back **реальной** staging edge-конфигурации и bounded per-peer budget (без массированной нагрузки и без зацепления production/соседних сервисов).
4. **Private real Bot API:** из отдельного staging owner-аккаунта проверить `getMe`/username/ID/webhook state, личную команду `/web_login`, полное сравнение origin/code, явный callback и отмену, отказ группе/forward/чужому аккаунту и expired/replayed request, no credentials in logs. Никаких live mutations через боевого бота.
5. **Browser/device:** адресная строка и сравнение кода на физических iOS Safari + Telegram WebView и Android Chrome + Telegram WebView; проверить Secure/HttpOnly/SameSite Strict, login 202→200 только в исходном браузере, logout/revoke/TTL, чужую cookie/Host/Origin, реальные тайминги и честный отказ WebView. Playwright Chromium/WebKit — только synthetic browser model, не замена физическому устройству.
6. **Postconditions/rollback:** read-only status с синтетическим DTO, отдельный health/monitoring, после остановки polling/loopback ingress должен быть закрыт, токен/сессии отозваны по отдельному плану, independent staging read-back и датированный audit с SHA/источником. **No production release, no deployment, no Issue completion** только по CI.

**Границы acceptance:** Issue [#887](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/887) остаётся `OPEN / keep_open`; #885 и #890 независимы. Published `v5.0.0-rc.19` не включает D2d, Deployed `v5.0.0-rc.18.10` лишь operator-reported; целевой полный v5 G-11 `PARTIAL/NO-GO`. Для настоящей публикации ingress и любого запуска нового poller нужно отдельное явное согласование оператора после review DNS/TLS/secret/config и topology. **Merge новых PR, staging deployment и любые production mutations требуют отдельных явных разрешений.**


## D2e — read-only preflight перед подключением реального staging (merged, 2026-10-25)

Для #887 подготовлен **отдельный и по умолчанию полностью offline** инструмент `subscription_page_staging_preflight.py`. Он не запускает сервер, polling, webhook, команды, транзакции, запись в SQLite или выпуск сертификатов. Не меняет конфигурацию Nginx, DNS и токены. Его синтетические тесты не являются проверкой публичного staging или iOS/Android. Pre-merge required CI PASS, PR #906 MERGED в `main` SHA `ffdb8f27225fbb2dd5221a227fc6fe692c2c7fa4`; post-merge push CI на точном squash SHA независимо не подтверждён. До operator security approval никакие реальные probes не запускались.

**Режим без сети (только закрытый staging JSON):**

```sh
python subscription_page_staging_preflight.py /private/staging-config.json
```

Команда проверяет только JSON и права `0600` приватного файла в каталоге `0700`; **не читает токен**, не делает DNS/API/TLS запросы и печатает только обезличенный JSON `status=PENDING`, `requests_sent=0`. Отсутствие DNS/токена в этой фазе не является ошибкой, но не даёт права включать staging.

**Опциональный read-only Bot API identity gate (строго по отдельному approved staging bot):** до выполнения проверить право владения ботом, отсутствие production token, согласованный `expected_bot_username` и изоляцию polling/webhook. Токен лежит только в приватном `staging-bot.token`, в аргументы/CI logs/GitHub не копируется. Пример команды с **условными значениями**, не исполнять до approval:

```sh
python subscription_page_staging_preflight.py /private/staging-config.json \
  --verify-approved-bot-identity \
  --reviewed-bot-username StagingExampleBot \
  --explicit-telegram-readonly
```

Инструмент при `enabled=false` и совпадении имени читает только приватный staging token, проверяет **ровно `getMe` и `getWebhookInfo`** (с overall timeout) и закрывает клиент. `start_polling`, отправка сообщений, webhook mutations и вход пользователей отсутствуют. `getMe` mismatch или non-empty webhook → fail-closed `BLOCKED`, детали HTTP URL/токена в консоль не выводятся. Успех подтверждает лишь read-only identity, **не** разрешение открыть listener.

**Опциональный public direct-TCP HTTPS edge gate:** только после отдельного review владения staging DNS, chain/SAN/SNI, отсутствия CDN/LB/proxy перед первым Nginx, проверенной отдельной конфигурации ingress и допустимости пяти безопасных HEAD запросов. Для чтения edge конфиг должен иметь `enabled=false` и подтверждённое `edge_reviewed=true`; `reviewed-origin` обязан побайтово совпадать с приватным `https_origin`. Пример синтаксиса после review (адрес заменить только на самостоятельно проверенный, принадлежащий оператору staging host):

```sh
python subscription_page_staging_preflight.py /private/staging-config.json \
  --probe-approved-public-edge \
  --reviewed-origin https://staging.owned-domain.example \
  --direct-tcp-confirmed
```

`.example` в образце намеренно не является разрешённым live DNS. Инструмент fail-closed отклоняет зарезервированные/private/mixed DNS ответы и более одного уникального IP (A/AAAA или multi-host edge — отдельный review), закрепляет единственный публичный IP (без повторного resolver на каждом запросе), делает только **5** HEAD: `/`, `/admin/`, `/compat/`, `/api/subpage/v1/auth/standalone/approve` и `/` с чужим Host. Использует системную доверенную CA, hostname/SNI verification, TLS 1.2+, `no-store`, `no-referrer`, HSTS, CSP/anti-framing; запрещает redirects/cookies на корне, случайно открытые маршруты и положительный ответ на чужой Host. Выводит **только status, количество запросов и SHA-256 публичного TLS-сертификата**, не печатает IP, private bot ID, path конфигурации и токен. Проверка не вносит изменений, но сетевой доступ к реальному staging **сам по себе требует отдельного одобрения и аудита**, даже если запросы read-only.

**Чего preflight не доказывает:** реальную edge конфигурацию, корректные per-IP rate limits `5r/m` / `12r/m` / `5r/s`, а также `429` при burst, CDN/LB anti-spoof/topology, public DoS, Telegram private ownership/anti-relay, browser session binding, production compliance, физический Safari/Chrome/Telegram WebView, rollout/rollback, многопроцессный recovery, D3 import/Copy/QR. Для edge-rate нужен **отдельный** ограниченный сценарий на разрешённом staging с подтверждением Nginx/TCP topology и независимыми `429/413` evidence, без массовой нагрузки; для iOS/Android нужна физическая device matrix. Метки `PARTIAL` и `PENDING` в отчёте — обязательные. **Не использовать синтетический PASS как real staging/device PASS, не закрывать #887.**

**Fail-closed при отсутствии operator evidence:** если нет подтверждённого staging DNS, cert, отдельного токена, разрешённой сетевой среды, direct-TCP topology и безопасного доступа, выполнять только offline JSON preflight и регрессию CI. Не пытаться получить секреты из production, читать Telegram переписку, обращаться к чужим доменам или запускать Bot polling из GitHub Actions. Следующий операторский gate должен отдельно подтвердить точную среду и разрешение на реальные read-only probe, а запуск ingress/Bot polling остаётся ещё одним самостоятельным решением.

## Следующий операторский checkpoint — готовность staging pilot (2026-10-25 UTC)

**Read-only подготовка, не разрешение запускать staging.** Baseline `main` после синхронизации Roadmap: `ebb4ac0bd1b8358a5fc7c433794b81580f3facfd` (PR #907). Установленные факты: D2e code и документация merged; PR-head `test/title` PASS; post-merge push CI D2e на `ffdb8f27225fbb2dd5221a227fc6fe692c2c7fa4` **PENDING независимого подтверждения** (GitHub connector `fetch_commit_workflow_runs` возвращает только PR-triggered runs, поэтому отсутствие результатов не означает отсутствие push CI). Реальный staging: **NOT RUN**, DNS/TLS/Bot API/устройства **PENDING**. Никакие конфигурации, токены и deployment не менялись.

Перед отдельным разрешением на live pilot оператор должен **в закрытом канале** подтвердить владение выделенными staging hostname и ботом, отдельный host/isolated Nginx topology без production, прямой TCP edge либо согласованную модель trusted proxy, изолированные owner-only token/config/SQLite и отзыв токена/rollback. **Не присылать токен, Bot ID, allowlist или private hostname в GitHub/чат.** Для публичного HTTPS probe нужен заранее проверенный public single-IP DNS и корректный SAN/SNI/CA; приватный/VPN edge не обходить через отключение TLS/DNS проверок. Согласовать допустимый ограниченный read-only `HEAD` и `getMe`/`getWebhookInfo` scope отдельно от разрешения на polling/ingress.

**Минимальный непроверенный targeted checklist** (подробные шаги 1–6 выше, без повтора offline PASS): (1) независимый GitHub push-CI evidence на D2e squash SHA либо честный `PENDING`; (2) operator review staging DNS/сертификата/Host/SNI и 0700/0600 секретов; (3) разрешённый offline config preflight и отдельно approved read-only Bot identity/HTTPS HEAD; (4) реальный default-deny ingress, denied paths, spoofed XFF, bounded `429/413` при отдельно согласованном staging запуске; (5) owner/private Telegram challenge/anti-relay/replay/cancel и физические iOS Safari/Telegram WebView, Android Chrome/Telegram WebView; (6) stop/revoke, независимый read-back, датированный audit с immutable SHA и источником evidence. **Пункты 2–6 PENDING, а не PASS.** D3, multi-host recovery и полный G-11 остаются PENDING/NO-GO.

## D3h — offline readiness для Copy/QR (2026-10-26; #887, Draft PR #927)

**Текущий результат — BLOCKED, не live staging acceptance.** Действующий D2d staging edge-пример `deploy/subpage-staging/nginx-d2d-staging.conf.example` разрешает ровно существующие standalone-auth routes и статические файлы, а `/api/subpage/v1/import/preflight/{csrf,issue,deliver}` не публикует; `location /` завершает прочие запросы `404`. `subscription_page_staging.py` не собирает `create_import_preflight_app` и использует synthetic `_SyntheticCustomer`. Frontend D3g получает `clientVersion=""` и `pilotEnabled=false` даже при opt-in build, backend factory имеет `delivery_enabled=false` и `reviewed_clients=()`. Следовательно, физический Copy/QR D3h **невозможно считать выполненным** по D2d login preflight, предыдущему #473 или зелёному CI.

Только для source-only сверки выключенного состояния (без network, DNS, Bot API, TLS, SQLite, реальных config/token, URL и запуска процессов):

```sh
python subscription_page_import_attestations.py --offline-readiness
```

Ожидаемые поля структурированного вывода для текущего checkpoint: `status=BLOCKED`, `candidate_count=7`, `reviewed_count=0`, `staging_import_routes=NOT_WIRED`, `csrf_origin_compat=REVIEW_REQUIRED`, `qr_blob_csp=BLOCKED`, `clipboard_activation=PHYSICAL_WEBVIEW_PENDING`, `frontend_import=OFF`, `server_delivery=OFF`, `device_evidence=PENDING`, `live_requests_sent=0`. Возврат CLI `0` означает **только успешную проверку ожидаемого заблокированного состояния**, а не готовность к device smoke; если source drift или неполный файл — CLI возвращает `2` и обезличенный `BLOCKED`. CI проверяет отрицательные варианты: неожиданное включение флага, клиентской версии, reviewed allowlist, runtime wiring, нового staging route, неполный source/JSON — fail closed. Static source inspection **не заменяет** реальный TLS/ingress read-back и не может подтвердить отсутствие runtime mutations на неизвестном VPS.

**Дополнительные D3g/D2d browser/security blockers (не эксперимент на физическом устройстве):** `manualImportClient.ts` делает same-origin `GET /csrf`, но `subscription_page_import_http.py` требует `Origin` на каждом запросе. Для same-origin `GET`/HEAD браузеры обычно не посылают `Origin` ([MDN Origin](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Origin)); `referrerPolicy=no-referrer` также требует явной проверки совместимости POST-Origin в настоящем браузере, без ослабления owner/session/CSRF. До такого security review `csrf_origin_compat=REVIEW_REQUIRED`, не считать synthetic test с вручную добавленным `Origin` доказательством рабочего frontend. D2d ingress имеет `img-src 'self' data:`, а D3g QR создаёт `blob:`-URL через `URL.createObjectURL`: в нынешнем CSP QR изображение не будет допущено, `qr_blob_csp=BLOCKED`; нельзя просто расширять CSP без независимого privacy/CSP review. `navigator.clipboard.writeText` вызывается **после** трёх асинхронных запросов, хотя Safari может требовать краткоживущую user activation ([MDN Clipboard API](https://developer.mozilla.org/en-US/docs/Web/API/Clipboard_API)). Это гипотеза о совместимости, **не** device-confirmed FAIL; `clipboard_activation=PHYSICAL_WEBVIEW_PENDING`. Для всех трёх — отдельные реальные browser/WebView/edge smoke, минимальное безопасное исправление в отдельном PR до допуска реальных client/version, без включения production.

**Зависимости для будущего разрешённого отдельного staging implementation/review:**

1. Отдельное разрешение на isolated staging deployment, приватная DNS/TLS/Host/SNI и неизменяемое build evidence, явная схема single-host session+SQLite и доверенная edge rate/size/log-redaction модель. Не менять production `app_runtime`, `/compat/`, published tag или операторский бот.
2. Самостоятельный staging-only HTTP integration PR должен после security review свести `D2a/D2b` owner session, `ImportSQLiteLedger` и `create_import_preflight_app` с защищёнными exact routes и запретом всех остальных путей. **Нельзя просто открыть `/import/preflight/*` через старый Nginx:** потребуются verified session/cookie/CSRF/Origin/Host, per-peer `429/413`, cache/privacy headers, отсутствие лога bearer. Не соединять реальные 3x-ui credentials с `_SyntheticCustomer` и не предоставлять настоящие URL через тестовую заглушку.
3. Независимо от staging wiring сначала физическая аттестация точной `platform/clientId/clientVersion` и проверка import/refresh на выделенной изолированной тестовой подписке. При неаттестованном результате — `reviewed=[]`, UI и выдача остаются выключенными. Весь список D3H-01…D3H-06 и критерии по методам — [WEB_SUBSCRIPTION_MINI_APP.md](WEB_SUBSCRIPTION_MINI_APP.md).
4. Отдельный датированный scrubbed audit со статусами native browser/WebView Copy/QR, privacy/owner/TTL/replay и явным source. Независимый review до внесения любых `allowCopy/allowQr` в trusted allowlist. Переход к Release, deployment и G-11 acceptance — только с отдельным разрешением.

**Границы:** этот PR не содержит staging ingress, API listener, реальных test credentials или физических тестов. #887 `OPEN/keep_open`, `G-11 PARTIAL/NO-GO`. Из исходников не следует, что D3g доступен в текущем `v5.0.0-rc.19` Published или на operator-reported Deployed `v5.0.0-rc.18.10`. Public rollout BLOCKED.

