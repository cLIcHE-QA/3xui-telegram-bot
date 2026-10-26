# Client Portal v5 — настройка контролируемого пилота

**#814/#816/#820 реализованы в `main` после squash merge [#821](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/821)** (SHA `aff7bde8ec2521fa11f14362c00502737e2b04e5`, offline test/title PASS), новый `v5.0.0-rc.18.2` теперь **Published GitHub prerelease** на SHA `20205a56887cbdf644f604febdd9eb9ac717b914`, и operator-reported Deployed; targeted UI 15/15 и H1–H10 operator-reported PASS; все пять HWID Issues CLOSED/completed, независимая X2/X1/X3 provenance PENDING; при этом клиентская HWID-карточка показывает `VPN-клиент: Happ/Incy/Shadowrocket` или `Не определён`, а Back — только `⬅ Устройства`; `macOS (Designed for iPad)` получает `💻` независимо от модели iPad. Административный HWID-список стал компактным, без fingerprint в списке: максимум 8 устройств на страницу, переключение страниц и сохранение исходной страницы из карточки; клиентский HWID-список остаётся по 5. Полная admin detail и DELETE-flow остаются прежними. Эти изменения **не** являются acceptance deployed `rc.18.1`; его A4/A5 — operator-reported FAIL, отрицательный targeted checkpoint слит в PR #819. [Post-merge audit](audits/2026-10-20-hwid-ui-819-821-postmerge-checkpoint.md) не является production acceptance.

Руководство для оператора ограниченного клиентского пилота: включение и выключение клиентского контура, безопасный read-only smoke, Stars pre-checkout и rollback. Настройка Master/3x-ui, резервного копирования и секретов — в [ADMIN_SETUP.md](ADMIN_SETUP.md); полная приёмка — в [V5_PRODUCTION_ACCEPTANCE.md](V5_PRODUCTION_ACCEPTANCE.md). Это **нормативные инструкции**, а не история релизов.

**CONTROLLED PILOT ONLY / PUBLIC LAUNCH BLOCKED.** **Текущий статус контролируемого пилота:** [Roadmap](ROADMAP.md) — Published `v5.0.0-rc.19` SHA `d738dd970f2215adc346a919c7ed182abaf454b1`; Deployed operator-reported `v5.0.0-rc.18.10` exact SHA, HWID 23/23 operator-reported targeted scoped PASS, #827/#830/#833/#834/#838/#854 completed ([audit](audits/2026-10-22-v5-rc18-10-operator-targeted-hwid-acceptance.md)). Independent VPS read-back PENDING; G-11 PARTIAL/NO-GO, public rollout BLOCKED. Ранние rc.18.2 15/15/H1–H8 PASS не повторялись.

## Client Portal: тарифы и платежные ограничения

- Клиенту показываются только `active` тарифы с положительной ценой Stars/XTR, разрешённые локальными User Groups, `visibility`, `include_group_ids`/`exclude_group_ids` и серверными проверками. `admin_only` и технические бессрочные бесплатные планы не являются публичной продажей. Отсутствующая цена Stars не преобразуется из RUB; Telegram-покупка цифрового продукта использует только Stars.
- Список доступных тарифов после серверной фильтрации сортируется по Stars **по убыванию** со стабильным порядком равных цен **до** лимита в 20 строк. Административный RUB/Stars порядок не меняет клиентскую стоимость или backend pre-checkout: реальный `plan`/`invoice` заново проверяет цену, доступность и владельца.
- Ручная бессрочная выдача живёт в отдельном журнале `manual_entitlements`, а не в `Order → Payment`. Только доказанный provider read-back переводит её в `active`; `in_flight/unknown` закрывают новые операции и требуют ручной read-only сверки без автоматического replay. Никаких нулевых Stars invoices, RUB заказов или выдач через непрозрачный fallback.
- Разрешённые пилотные identity, Terms, private-chat/client authorization, Stars флаги и RBAC применяются на entrypoint, invoice и pre-checkout. Ошибка БД или неопределённость entitlement **не** открывает платёж. Уже доставленный `successful_payment` обрабатывается идемпотентно даже при отключении *новых* платежей.

## #473 — импорт подписки (Published rc.19; deployment и приёмка PENDING)

**Security review #882 (2026-10-23, pre-merge):** в каталоге import URI отклоняются URL с query-delimiter (включая пустой `?`), percent/fragment/userinfo/private IP и небезопасной схемой; `subTitle` валидируется как ограниченное Unicode-имя с отказом на control/bidi, читается только через loopback после owner/private guard, без redirect. Ошибки информационного upstream-запроса логируются по типу исключения, без bearer URL. Добавлены negative tests для forged callbacks, недоступного proxy и title injection. Итог offline CI и реальный post-deploy smoke независимы от самого review; выпуск до обязательных checks запрещён.



**Проверка исправленной ссылки (2026-10-23 14:42 UTC+03:00):** пользователь подтвердил устранение подмены имени при ручном импорте Shadowrocket. Для клиентов с поддержкой имени бот должен брать актуальный `subTitle` 3x-ui из `GET /compat/{sub_id}?format=info` по loopback после owner/private/pilot guards и добавлять его как URL-encoded `remark`, **не хардкодить** `VPN` или название Telegram-бота. Если title недоступен или некорректен, оставить `remark` пустым (без выдуманного названия). Ручной клиентский smoke — operator-reported PASS; получение title самим ботом до deployment не аттестовано. Изменение title в панели влияет на новые импорты, но не гарантирует переименования старых записей.

**Наблюдение 2026-10-23:** оператор сообщил успешный импорт Happ на iOS/Android/macOS и Shadowrocket только на Apple-устройствах (iOS/macOS); версии PENDING. Shadowrocket/Android не проверялся. Скриншот показывает шесть серверов и заголовок VPN в Shadowrocket. Root cause в PR #882 — фиксированный `remark=VPN`; исправлено чтением `subTitle` через read-only локальный `/compat/{sub_id}?format=info`, ограниченная проверка строки и percent-encoding. Если metadata недоступна, фиктивное имя не подставляется. Исправление имени пока не проходило повторный device smoke, Issue #473 keep_open.

**Happ / Shadowrocket test gate:** схема Happ `happ://add/<HTTPS URL>` для iOS/Android/macOS и Shadowrocket `shadowrocket://add/sub://<base64(HTTPS URL + ?flag=shadowrocket)>?remark=<encoded subTitle>` для iOS/macOS сверены с upstream `MHSanaei/3x-ui/frontend/src/pages/sub/subPageModel.ts`. На устройствах ещё PENDING. Для остальных candidate URI тоже required client/version-specific smoke; статус PASS не присваивать по CI. Incy 2.6.4/macOS имеет отдельный operator-reported PASS ([audit](audits/2026-10-23-client-import-473-macos-incy-version-clarification.md)).



В личном чате: «Моя подписка» → «Подключить устройство» → платформа → клиент. Incy и v2raytun получают кандидатный URI для ручного импорта через CopyTextButton или локальный QR. Для неподдержанных приложений/URL есть обычные HTTPS URL/QR. Telegram inline URL-button не поддерживает custom схемы, поэтому external redirect/shortener не используется.

| Приложение | Платформы в меню (candidate) | Название группы | Совместимость |
| --- | --- | --- | --- |
| Incy | iOS, Android, Windows, macOS, Linux | имя задаёт приложение / metadata подписки | iOS/Android 2.6.4 и macOS 2.6.4 operator-reported PASS |
| v2raytun | iOS, Android, Windows, macOS | metadata подписки | iOS/Android 2.4.7 operator-reported PASS; macOS PENDING |
| Happ | iOS, Android, macOS | metadata подписки; URI `happ://add/` | iOS/Android/macOS operator-reported PASS, версии PENDING |
| Shadowrocket | iOS, macOS (Apple) | `?remark=<encoded subTitle>`, `flag=shadowrocket` | Apple operator-reported PASS, Android unsupported/NOT TESTED |
| V2Box | iOS, Android | `&name=<encoded subTitle>` | candidate; версии и импорт PENDING |
| Karing | iOS, Android, Windows, macOS, Linux | `&name=<encoded subTitle>` | candidate; версии и импорт PENDING |
| OneXray | iOS, Android, Windows, macOS, Linux | `#<encoded subTitle>` | candidate; версии и импорт PENDING |
| Throne | Android, Windows, macOS, Linux | Base64(`URL#subTitle`) | candidate; версии и импорт PENDING |

### Полная матрица меню «Подключить устройство» — пять платформ

| ОС | Кандидаты client-specific import URI | Резерв |
| --- | --- | --- |
| iOS | Incy, v2raytun, Happ, V2Box, Shadowrocket, Karing, OneXray | Обычный URL/QR |
| Android | Incy, v2raytun, Happ, V2Box, Karing, OneXray, Throne | Обычный URL/QR |
| Windows | Incy, v2raytun, Karing, OneXray, Throne | Обычный URL/QR |
| macOS | Incy, v2raytun, Happ, Shadowrocket, Karing, OneXray, Throne | Обычный URL/QR |
| Linux | Incy, Karing, OneXray, Throne | Обычный URL/QR |

Кнопки **Windows** и **Linux** и фильтрация по ОС присутствуют в PR #882. Desktop-сценарии (особенно Windows/Linux) являются **candidate-only**, не live PASS: нужны отдельные client/version/build/import/refresh smoke, установка приложения на конкретной ОС не установлена по одному только наличию URI. На Linux инструкция запрещает подставлять bearer URL в shell history. Несовместимые клиенты не отображаются в списке платформы; «Другой клиент» сохраняет ручной URL/QR. Фактический deployed bot end-to-end PENDING.

**Имя и fallback:** `subTitle` читается только после private-owner/pilot/rate guards через read-only local `/compat/{sub_id}?format=info`; ограничение длины, Unicode control/bidi и URL encoding. V2Box/Karing при отсутствии безопасного имени используют обычный URL/QR вместо `name=VPN`, Shadowrocket/OneXray/Throne не подставляют выдуманное имя. URI длиннее 256 символов → manual URL/QR. Это **не** подтверждение import у новых клиентов. Источник V2Box/Shadowrocket/Happ: upstream `MHSanaei/3x-ui/frontend/src/pages/sub/subPageModel.ts`; форматы Karing/OneXray/Throne — соответствующая документация проектов. Happ/macOS и Shadowrocket/macOS — scoped отчёт пользователя; Shadowrocket/Android в меню отсутствует.

**Адресная ручная проверка 2026-10-23 13:38 UTC+03:00:** [операторский аудит 4/4](audits/2026-10-23-client-import-473-operator-smoke.md) подтверждает **по сообщению пользователя** успешный импорт URI Incy 2.6.4 и v2raytun 2.4.7 на iOS 26.5.1 (23F81) и Android 17. Это не независимый device read-back и не тест обновлённого Client Portal после release/deploy; PR #882 остаётся draft, security review и bot end-to-end PENDING. Никаких URL/ключей не сохранено.

**macOS:** Incy 2.6.4 — operator-reported scoped PASS по уточнению пользователя 2026-10-23 14:04 UTC+03:00 ([аудит](audits/2026-10-23-client-import-473-macos-incy-version-clarification.md)); точная версия macOS неизвестна. v2raytun/macOS не проверен (PENDING). Это пятое сочетание ОС/клиента, а не шестой отдельный тест. Остальные новые клиенты также PENDING.

Это candidate matrix, не гарантия установленной версии и не live PASS. До разрешённого targeted smoke для каждого приложения, платформы и версии необходимо проверить реальный import/refresh, наличие узлов и отсутствие повреждения существующих профилей. Результат PASS/UNSUPPORTED/PENDING фиксировать с точной версией, датой и evidence; до этого использовать безопасный ручной URL/QR.

Ссылки и QR содержат bearer credential, не предназначены для сторонних чатов/логов. URI отвергается при HTTP, userinfo, fragment, query, неоднозначном percent encoding, частных/локальных IP, неподдержанной схеме, превышении CopyTextButton 256 символов. Existing portal switch/allowlist/rate/private chat guards обязательны до чтения owner URL. Нет нового storage, payments, HWID, provisioning, migrations или операторских параметров. Rollback: existing portal switch/штатный опубликованный release. Production acceptance, Release/Deployed и G-11 остаются PENDING/BLOCKED.



## Моя подписка: #497 Published в rc.19; deployment и приёмка PENDING

После отдельного выпуска на разрешённом pilot-аккаунте проверьте `/subscription` и `🌐 Моя подписка` в личном чате: статусы VPN/entitlement, план, срок, `CopyTextButton`, возврат из подключения, guarded покупку/продление и диагностику. Проверяйте без изменения доступа случаи «нет аккаунта», disabled/expired/provisioning/unknown, provider outage, нестыковку сроков и отсутствие подтверждённого числа локаций. «Привязки Master Inbounds» **не** означают число доступных серверов. Не переносите реальные URL, ID или ключи в лог/Issue.

При выключенном `CLIENT_PORTAL_ENABLED`, вне pilot allowlist и в group/supergroup команда и callback не должны читать или выдавать секрет; QR также доступен только в личном чате. Просмотр не запускает `provisioning/reconcile`, новые заказы, изменение `sub_id` или рефанды. Rollback: существующий feature switch и штатный release rollback; новых настроек/миграций нет. G-11 остаётся PARTIAL/NO-GO до отдельной приёмки.

## Исторические release и acceptance checkpoints (не текущий статус)

Датированные исходные отчёты об опубликованных/развёрнутых `rc.9`, `rc.10`, `rc.11`, `rc.16.1`, `rc.16.2`, `rc.16.4`, прошлых B5/C3 FAIL и scoped PASS сохранены без изменения в [immutable snapshot этого руководства](https://github.com/cLIcHE-QA/3xui-telegram-bot/blob/8d5b9ad1ce1fecf8f5f1808c786f3b2b3cf32f0b/docs/CLIENT_SETUP.md). Проверяемые источники: [rc.10 acceptance](audits/2026-10-15-v5-rc10-targeted-postdeploy-acceptance.md), [rc.11 deployment](audits/2026-10-15-v5-rc11-operator-deployment-checkpoint.md), [rc.16.1 deployment](audits/2026-10-17-v5-rc16-1-operator-deployment-checkpoint.md), [rc.16.4 smoke](audits/2026-10-18-v5-rc16-4-operator-targeted-smoke.md) и [rc.16.5 acceptance](audits/2026-10-19-v5-rc16-5-operator-targeted-acceptance.md). Старое `OPEN/PENDING` в этих источниках относится к моменту проверки, а не к текущему GitHub Issue.

### #887 D3h — физическая аттестация Copy/QR (ещё PENDING)

Для нового web/Mini App D3g **не переносить** исторические `operator-reported PASS` из #473 в `reviewed` без отдельного physical browser + Telegram WebView smoke **для точной версии на iOS и Android**. Матрица кандидатов, полный targeted checklist D3H-01…D3H-06 и критерии `allowCopy/allowQr` находятся в [WEB_SUBSCRIPTION_MINI_APP.md](WEB_SUBSCRIPTION_MINI_APP.md). Машиночитаемый offline реестр: `docs/assets/subpage-d3h-client-attestations.json`, `reviewed=[]`; он **не подключается** к серверной выдаче или frontend и сам по себе не разрешает запуск.

До отдельного согласования изолированного staging, проверки TLS/edge/session topology, устройства, Clipboard/QR и privacy gates: `VITE_D3G_MANUAL_IMPORT_UI` default false, `pilotEnabled=false`, `REVIEWED_CLIENT_CAPABILITIES=[]`, backend `delivery_enabled=false`, `reviewed_clients=()`. Не включать `app_runtime`, не раскрывать bearer URLs, не расширять pilot и не запускать production smoke/Release/deploy. #887 OPEN/keep_open, G-11 PARTIAL/NO-GO.

## Плановая внешняя оплата

Решение об индивидуальной hosted Platega ссылке из Telegram-бота, отдельных валюте/статистике и предохранителях для будущего PSP зафиксировано в [EXTERNAL_PAYMENT_LINKS.md](EXTERNAL_PAYMENT_LINKS.md). **На текущем пилоте внешняя кнопка НЕ работает и не одобрена к rollout**: merchant/KYC/согласование правил Telegram для цифровых услуг ещё PENDING. До отдельного выпуска остаётся Stars flow с существующими флагами.

## Область ответственности и условия старта

- Инфраструктура Master/direct node, 3x-ui, Docker, TLS, backup и секреты устанавливаются по [ADMIN_SETUP.md](ADMIN_SETUP.md), не повторяются здесь.
- Используйте **только специально разрешённые тестовые Telegram identity** и изолированные тестовые тарифы/подписки. Не расширяйте cohort и не убирайте allowlist ради удобства.
- Перед изменениями зафиксируйте published tag, commit SHA, реально deployed tag/SHA, `APP_VERSION`, SQLite schema, состояние `/healthz`, 3x-ui connectivity, backup/rollback baseline и доступность `/admin`. Published ≠ deployed ≠ accepted.
- Клиентский контур и административный `/admin` имеют отдельные authorization boundaries; включение Client Portal не предоставляет административные права.
- Не публикуйте реальные Telegram ID, subscription URLs, provider payment references, ключи и содержимое приватных БД в Issues, PR или audit evidence.

## Переменные пилота и доступ

На Master в локальной приватной `.env` (без публикации значений):

| Переменная | Значение / правило |
| --- | --- |
| `ALLOWED_TELEGRAM_IDS` | Явная пилотная allowlist; `ADMIN_TELEGRAM_IDS` — отдельный список администраторов. Не используйте фиктивные ID из `.env.example` в production |
| `CLIENT_PORTAL_ENABLED` | `false` запрещает клиентский UI, **не** выключает `/admin`; `true` не отменяет allowlist |
| `CLIENT_PAYMENT_ACCEPTANCE_ENABLED` | `false` блокирует **новые** Stars invoices и pre-checkout; уже подтверждённые `successful_payment` должны быть обработаны безопасно |
| `CLIENT_RATE_LIMIT_COUNT` / `CLIENT_RATE_LIMIT_WINDOW_SECONDS` | Per-user sliding window (в примере `30` / `60`); меняйте только после согласованного canary и проверки лимитов |

Настоящий код определяет доступ как принадлежность к `ALLOWED_TELEGRAM_IDS` **или** `ADMIN_TELEGRAM_IDS`, с отдельным gate Client Portal; административный Telegram ID не становится автоматически внешним клиентом. Для приёмочных прогонов используйте специально выделенные аккаунты, не открывая доступ всем пользователям.

**Fail closed / действующий runtime contract:** `.env` остаётся безусловным veto. Owner-only DB overrides находятся в `/admin → Система → Настройки → 👤 Клиентский портал`; выключенное DB `portal=false` запрещает также **старые inline callbacks**, не только новые кнопки. `/admin` проверяется отдельно и не выключается клиентским флагом. Для break-glass используйте `.env CLIENT_PORTAL_ENABLED=false` с контролируемым применением конфигурации, без изменения уже подтверждённых платежей, 3x-ui entitlements или allowlist. Исторический регрессионный smoke #342 доступен в immutable snapshot и соответствующем аудите; он не подтверждает весь v5 acceptance.

## Плановый read-only smoke #471 (только после разрешённого release/deploy)

Изменения отображения HWID по Issue #814 (Published и operator-reported Deployed `rc.18.1`, targeted UI acceptance PENDING): если upstream отдаёт проверенные `deviceOs`/`osVersion`, в списке и карточке показывается реальная версия ОС; `deviceModel`/`deviceOs` задают только консервативный визуальный тип `📱`/`💻`/`🖥️`/`🔹`, не влияют на owner/id/capability. Некорректная/неизвестная версия не подменяется догадкой. По #816 в детальной карточке дополнительно отображается только распознанное название VPN-приложения (`Happ` или `Incy`) из строго валидированного upstream `userAgent`; сам `userAgent`, его версия и неизвестные значения не выводятся. Это метаданные, не признак ownership/capability.

На выделенном pilot-клиенте сверить количество HWID с upstream: 0 и более 5 записей, листание/Back и полное время в карточке; отключённый/неизвестный `limitHwid` не должен отображаться как числовой лимит. Сменить модельные test identities только в изолированной проверке, проверить отсутствие чужих карточек, устаревшие ID, oversized fields, отключённый portal/allowlist и provider unavailable. Никаких DELETE, payment, расширения pilot или production mutation; результат записать отдельно с tag/SHA/TZ/source. После Published/Deployed `rc.18` — D1–D8 operator-reported PASS (см. [датированный audit](audits/2026-10-20-v5-rc18-hwid-operator-acceptance.md)); отдельные live applicability/provider read-back и closure checkpoint PENDING.

## #472 — плановый security/acceptance checkpoint (до выпуска PENDING)

Новый клиентский `🗑 Удалить устройство` предназначен только для собственного подтверждённого HWID; прошлый Deployed `rc.17` не содержал этот implementation PR; текущий `rc.18` — operator-reported deployed с scoped S1–S4 PASS. Никаких production DELETE в рамках read-only #471 smoke. Клиентский delete flow требует нового отдельно согласованного release/deploy и **отдельного разрешения** на каждую опасную production мутацию; публикация и зелёный CI сами по себе не дают такого разрешения.

Для нового нерешённого security finding/регресса допустима только offline/изолированная проверка без дополнительных production DELETE: чужой/неизвестный ID, смена владельца между экранами, stale token, Cancel без DELETE, двойное подтверждение, concurrency, отсутствие capability, 4xx vs timeout/network/5xx, невалидный/частичный HWID inventory, отсутствие postcondition, общий portal OFF/allowlist и per-user cooldown. Подтверждать `PASS` только для проверенного evidence. При `unknown` выполняется **только read-only inventory lookup**, автоматический DELETE retry запрещён; после `deleted` должен быть независимый полный inventory read-back. Записи личного HWID, email, private token или private subscription URL не включать в отчёт. Текущие G-11 `PARTIAL/NO-GO` и public rollout `BLOCKED` не меняются.

## Безопасный smoke без реальных платежей

1. На разрешённой test identity проверьте `/start`: личный кабинет открывается при разрешённых gate и allowlist. У посторонней identity доступ должен быть отклонён. `/admin` проверяйте отдельно под разрешённой ролью.
2. Проверьте `/subscription` и `/paysupport`; legacy `/create` / `/inbounds` должны вести в личный кабинет, а не создавать обходной mutation path.
3. Проверьте отображение состояния подписки, сроков, трафика и устройств на специально выделенном клиенте, а также импорт/обновление subscription в реальном VPN-клиенте. Сверяйте клиентский UI с read-only 3x-ui состоянием; неизвестное/недоступное состояние не выдавайте за активную подписку.
   Для `🛠 Проверить подписку` различайте `✅ Сроки совпадают` (полные сравнимые применимые источники), `⚪ Недостаточно данных для сравнения` (provider unavailable или незаданный expiry) и `⚠️ Сроки не совпадают` (проверенный drift более 2 секунд). Доказанный mismatch важнее отсутствия третьего источника; диагностика ничего не исправляет и не перезапускает.
4. Убедитесь, что настройки тарифов, `stars_price`, Terms и владельца заказа не дают создать несогласованный платёж. **Не выполняйте реальные Stars purchases/refunds без отдельного одобренного acceptance-сценария**. Внешний fiat/generic HMAC checkout не является одобренным substitute для Telegram Stars в цифровом Telegram product flow.
5. Проверяйте rate limiting и ownership/IDOR только на своих изолированных test identities. Ожидаются fail-closed ответы и отсутствие раскрытия чужого subscription URL/QR.
6. Сохраните scrubbed evidence: tag/SHA, время/таймзону, окружение, сценарий, ожидаемый и фактический результат; отдельно перечислите `PASS`, `PENDING`, `FAIL`, `BLOCKED`, issue и следующий шаг.

Этот smoke — **не** замена [полного production acceptance](V5_PRODUCTION_ACCEPTANCE.md): там отдельно требуются Stars happy path/refund, delayed/duplicate events, uncertain outcome, provisioning/restart, ownership, abuse/load/soak, rollback и финальная межсистемная reconciliation.

## Действия при проблеме / rollback

1. При подозрении на проблему с платежами сначала выключите **новые** платежи: локально `CLIENT_PAYMENT_ACCEPTANCE_ENABLED=false` и контролируемое применение конфигурации. Не удаляйте существующие orders/payments/entitlements и не выполняйте повторные refund/provisioning mutations при `unknown` без доказанного postcondition.
2. При проблеме с доступом дополнительно установите `.env CLIENT_PORTAL_ENABLED=false` и примените только через контролируемый операторский deployment. Не выводите работоспособность emergency stop из исторического smoke: проверяйте точный фактически deployed tag/SHA и DB override `portal=false`, а не приравнивайте публикацию к deployment. `/admin` должен остаться доступным. Не отключайте backup/audit и не меняйте сведения об уже подтверждённых платежах.
3. Проверьте exact deployed tag/SHA, Health/SQLite/3x-ui, read-only payment journal и затронутых тестовых клиентов. Изменение `.env` требует штатного контролируемого применения; редактирование файла само по себе не означает, что контейнер получил новые значения.
4. Возвращайте флаги только после нового targeted PASS с evidence и согласованного решения; прежний `FAIL/unknown` сохраняйте как историю. Для security finding используйте [SECURITY.md](../SECURITY.md) и приватный канал репортинга.

## Gate на публичный запуск

**BLOCKED до полного PASS.** Нельзя расширять pilot allowlist или считать stable `v5.0.0` готовым лишь по публикации RC, зелёному CI или успешному ручному smoke. Необходимы все обязательные проверки из [V5_PRODUCTION_ACCEPTANCE.md](V5_PRODUCTION_ACCEPTANCE.md), закрытие release-blocking findings, безопасное восстановление/резервирование и отдельный approved release/deployment flow. Результаты и оставшиеся gates вносятся в [ROADMAP.md](ROADMAP.md); завершённое выполнение подтверждается evidence, а не галочкой без проверки.

После stable v5 и завершённого acceptance это руководство пересматривается отдельным PR, а не автоматически переименовывается в public launch guide.

## Универсальное имя VPN-клиента (#827; Published rc.18.4, targeted acceptance PENDING)

Опубликованные `rc.18.3`/`rc.18.4` уже включают bounded display-only извлечение заявленного VPN-клиентом имени из `userAgent` без общего brand allowlist (`V2Box 10.1.9/iOS 26.5.1` → `V2Box`, `v2rayNG`, `sing-box`). Сырой UA, версии, неподтверждённые метаданные и опасные хвосты не выводятся в клиенте, имя не подтверждает реальное приложение и не используется для доступа или DELETE. Targeted acceptance остаётся PENDING.

Новое наблюдение после обновления бота (operator-reported, 2026-10-21 21:28 EEST): `Throne/Android/2.0.3` возвращает «Не определён», поскольку формат `Client/Platform/Version` не входил в generic parser. Универсальный ограниченный синтаксис для шести явно названных платформ, без allowlist новых приложений, MERGED через [PR #846](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/846) в `main` (`179c34dad52cf27cb0b3e76f685fbf5c7b54647e`). `v5.0.0-rc.18.5` теперь GitHub Published SHA `b2bdb09778f120aa57c8415ae803394483a2ef8e`, но отдельно разрешённого deployment и targeted acceptance ещё не было; предыдущий `rc.18.4` этого исправления не содержал. Для targeted read-only smoke после выпуска проверить `Throne`, произвольный допустимый новый бренд и опасные suffix; также отсутствие raw UA/fingerprint в клиенте, неизменность ownership и post-deploy health. Не проводить DELETE/Stars/provider mutations.

## Историческая targeted HWID матрица rc.18.5 (закрыта scoped rc.18.10)

По #827/#830 проверить read-only detail после отдельно разрешённого release/deploy: заявленные Incy Android/Windows с Dalvik, OneXray с wrapper v2rayN, полный (не обрезанный до 160 символов) Karing UA и unsafe suffix → безопасный fallback; Google sdk_gphone / generic Android emulator → `Устройство Android`; iPad Pro при `macOS (Designed for iPad)` → `Mac (модель не определена)`; `iPadOS` остаётся iPad. Обязательно отрицательные HTTP-stack UA, ложные OS prefixes и проверка, что клиент не получает fingerprint/raw UA; при отсутствии `deviceOs` сохранять `ОС неизвестна`. Это оставшийся read-only checklist после GitHub Published `rc.18.5`, но не evidence фактического targeted smoke или подтверждение Deployed tag/SHA; отложенные проверки нового формата `Throne` выполнять только после отдельного release/deployment. G-11 PARTIAL/NO-GO, public rollout BLOCKED.


## Karing: усечение предпросмотра и read-only диагностика (#827, implementation candidate)

Finding оператора 2026-10-21 21:41 UTC: клиентская карточка сообщила «Не определён», admin показывал Karing UA длиной ровно 160 символов до `(Prefe`. Это лимит *показа*, не подтверждение длины upstream. В рабочем фиксе admin-only поля сообщают фактическую длину и распознанное имя, не показывая более 160 символов сырого UA. Parser совместим только с точным 160-символьным окончанием известного full-match Karing шаблона; неверная последовательность компонентов, неполный формат иной длины, секретоподобный хвост остаются `Не определён`. Никаких изменений модели и ОС: `Unknown device` на `iOS` → `Устройство iOS`; `iOS 26.5.1` сохраняется. После отдельного разрешённого release/deploy требуется сравнить admin length/result и client display, затем health read-back; не проводить DELETE/Stars/provider mutations. В Published `rc.18.5` исправления нет, target версии не назначен; acceptance PENDING.


**GitHub Published rc.18.6 (tag SHA `46bc24530633d9958278ab56f624c8b8d274f845`; Deployed/Accepted PENDING):** Karing fix [PR #849](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/849) MERGED; теперь Published, но НЕ Deployed/Accepted. После публикации и отдельно разрешённого deployment проверить только read-only admin длину полного UA/результат парсера и client Karing/безопасный fallback, без DELETE или изменения HWID. Current-state Published/Deployed/Accepted — [Roadmap](ROADMAP.md).


## Karing: подтверждённый 191-char suffix, новая регрессия #827 (Published rc.18.7; live acceptance PENDING)

Операторское read-only наблюдение 2026-10-22T07:48:23Z после обновления: admin `UA length=191`, preview `160`, `Распознано по полному User-Agent: Не определён`; Client Portal показывает тот же fallback. В полном формате завершающие маркеры ` (Prefer ClashMeta Format);HiddifyNext`, которых не было в строгой грамматике `rc.18.6`. Подготовлено точечное распознавание второго фиксированного Karing suffix без сканирования произвольных engine names. Старые `(Preferences)` и 160-char fallback, V2Box/OneXray/Incy/Throne, `Устройство iOS` и `iOS 26.5.1` не меняются. Исправление уже Published в `rc.18.7` и входит в `rc.18.8`; deployed tag/SHA и targeted acceptance PENDING. `rc.18.6` его не содержит. Deployment/version provenance VPS и targeted post-deploy Karing PASS PENDING, Issue #827 OPEN, G-11 PARTIAL/NO-GO.


## HWID UI: desktop-иконки и расширенная диагностика (#854; Published rc.18.7)

По сравнительным снимкам оператора 2026-10-22 в админском списке у нормализованного `DESKTOP-…_x86_64` стал отображаться 💻 вместо 🖥️, а `Windows 10_10.0.19045` остался непонятным. Исправление Published с `rc.18.7` через PR #855: значок основан на ограниченном техническом признаке исходного `deviceModel`, а интерфейс показывает только безопасную нормализованную модель; исходную ОС показывает только расширенная админская карточка с фильтром безопасности. Не раскрывать исходные hostname/модель и raw UA в клиентском меню. До отдельного release/deployment и targeted read-only smoke это не Accepted; `rc.18.6` immutable и не содержит исправления.

Дополнение #854: расширенная **клиентская** карточка теперь показывает `⚙️ ОС`, `🛡️ VPN-клиент`, `🕒 Последняя активность`; значок desktop/laptop/mobile одинаков в списке, кнопке и заголовке detail. В клиентские данные добавляется только заранее вычисленная иконка, не исходная модель. `Исходная ОС` доступна исключительно в административной detail-карточке. Back и DELETE не меняются; до отдельного deployment/client-admin targeted smoke статус PENDING.


## Targeted HWID finding #834, 2026-10-22

После сообщения оператора об обновлении при корректной desktop-иконке админская карточка всё ещё показывала технический `Windows 10_10.0.19045` рядом с исходной ОС `Windows`. Причина в неподдержанном разделённом формате `deviceOs=Windows` + `osVersion=10_10.0.19045`. Исправление MERGED в PR #858 и Published в `rc.18.8` через общий `display_os()` для admin/client; проверять только после отдельно разрешённого нового immutable Release/deployment с точным tag/SHA. Исходная ОС отображается только администратору, никаких provider mutations. Наблюдение operator-reported; фактический deployed SHA UNKNOWN, targeted acceptance PENDING.


**Уточнение #834 по согласованному admin UI (2026-10-22):** сначала `Модель`, `Исходная модель`, `ОС`, `Исходная ОС`, затем остальные диагностические строки. Для проверенной пары `deviceOs=Windows` + `osVersion=10_10.0.19045` исходная ОС admin-only — `Windows 10_10.0.19045` (без нормализации), display ОС — `Windows 10 (сборка 19045)`; неизвестный или опасный `osVersion` в исходную строку не добавлять. Client Portal по-прежнему получает только нормализованную ОС.


## Админская исходная ОС Windows 10 + 10.0 (#834, 2026-10-22)

Operator-reported после обновления: 3x-ui показывает `Windows 10 10.0`, а admin-only `Исходная ОС` показывала лишь `Windows 10`. Fix [PR #861](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/861) теперь Published в `rc.18.9` и вычисляет безопасную композицию `deviceOs` и `osVersion` без изменения данных провайдера и нормализованной строки `ОС: Windows 10`. Технические значения остаются admin-only; клиентский интерфейс не получает новых полей. Targeted smoke и точный deployed SHA PENDING.


## Адресная проверка Happ с 20-значным suffix (#827; PENDING)

После отдельно разрешённых merge, release и deployment сверить точный deployed tag/SHA, затем на разрешённом Pixel 6 с Android 17 выполнить только read-only просмотр клиентской и административной HWID-карточек для `Happ/4.7.1/Android/17912108360521999608`. Ожидается `VPN-клиент: Happ` в Client Portal и распознавание `Happ` в admin diagnostic; исходная модель, ОС и timestamps неизменны. Убедиться, что клиентский список и detail не раскрывают сырой User-Agent, suffix либо fingerprint; запрещённые дополнительные хвосты продолжают давать `Не определён`. Проверить health и отдельно записать evidence (точный tag/SHA, время с TZ, источник, результат). Не выполнять DELETE/платежи, не расширять pilot. Пока smoke отсутствует: #827 OPEN/keep_open, scoped acceptance PENDING.


## #887 D2d — отдельный staging Telegram Bot API + HTTPS ingress (не развёрнут)

Для подготовки независимого синтетического staging клиента/Telegram Web login используйте профильный [runbook D2d](SUBPAGE_STAGING.md): отдельные BotFather token/allowlist/0700+0600 файлы, `getMe`/webhook identity verification, одно-процессный локальный SQLite, неизменённый production `app_runtime`, строгий TLS/SNI/Host/Origin, Nginx edge rate/429 и anti-phishing-сверка полного кода. Шаблоны `deploy/subpage-staging/**` default-off и содержат только `.invalid` origin, **это не команда по включению**. До отдельного security/deployment approval нет real Bot API, DNS/TLS, device smoke, CLI start, release или production mutations; #887 `keep_open`, G-11 `PARTIAL/NO-GO`.
