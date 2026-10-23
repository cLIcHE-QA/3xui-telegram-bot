# Единая страница подписки и Telegram Mini App — решение #887

**Решение оператора 2026-10-23 (UTC+03:00):** использовать один собственный адаптивный веб-интерфейс в двух режимах — standalone subscription page и Telegram Mini App. Этап **D0 (архитектура)** согласован; runtime implementation, публикация, deployment и production acceptance пока **PENDING**. Нормативное состояние задач и релизов — в [Roadmap](../ROADMAP.md), а не в этом документе.

## Границы решения

- Один self-hosted responsive frontend с русским UI, общей компонентной системой и отдельными адаптерами входа. Скриншоты RightSide VPN — референс пользовательского сценария и композиции, **не** разрешение копировать код, изображения или бренд.
- Данные берутся только через provider-neutral `CustomerPortalService` и безопасное web API поверх существующего Python backend. Браузер не обращается напрямую к 3x-ui, SQLite или admin endpoints. Статусы `unknown`, `provisioning`, `inactive` и `active` не подменяются.
- Standalone page и Mini App используют **разные модели аутентификации**, но общий авторизованный read-only customer DTO. Telegram `initData` проверяется на сервере по подписи и времени, `initDataUnsafe` никогда не авторизует запрос. Для standalone нужен отдельный серверный session exchange. Сам `sub_id`/subscription URL не выдаёт доступ к полноценному личному кабинету.
- Сценарий `платформа → VPN-клиент → импорт` повторно использует каталог из #473, отдельный HTTPS handoff #885/PR #886 и fallback Copy/QR. В браузерах, особенно Telegram WebView, custom-scheme запуск может не сработать — честный fallback обязателен.
- Действующий `/compat/{sub_id}` и upstream 3x-ui SPA не заменяются и не переписываются через инъекцию. Новые web routes, ассеты и API — в отдельном пространстве URL с feature/pilot gate. Raw client subscriptions, `?format=info`, Happ/Incy/Shadowrocket/HWID compatibility остаются рабочими.
- Новая frontend session и Telegram Mini App не дают admin RBAC, не обходят pilot/User Groups, не разрешают DELETE, billing или provisioning mutations. Telegram digital purchases только Stars; RUB/СБП и юридические публикации остаются отдельными задачами #336/#707.
- Самостоятельная страница и Mini App не должны загружать секреты, токены, `initData`, `sub_id`, HWID или QR contents в third-party CDN, telemetry, logs или Referrer; required CSRF, CSP, no-store, cookie security, session expiry, replay/rate limits и cross-account negative tests.

## Утверждённый frontend-стек (решение оператора 2026-10-23)

**D1 implementation baseline — React + TypeScript + Vite + Mantine.** Изучен `remnawave/subscription-page` (публичная ветка `main`, `frontend/package.json`): это работающий пример browser-based VPN subscription portal на React, TypeScript, Vite, Mantine и Tabler Icons. Выбираем **технологии и типовые API этих библиотек**, а не исходники или готовый UI Remnawave.

| Область | Утверждённое решение | Ограничение |
| --- | --- | --- |
| UI runtime | React 19 + TypeScript | Один self-hosted frontend build для standalone и Telegram Mini App |
| Build | Vite | Версии и lockfile фиксируются в D1 после dependency/license/security review |
| Компоненты и тема | Mantine, оригинальные собственные компоненты | Тёмно-синяя тема, мятные акценты, карточки и крупные touch targets |
| Системные пиктограммы | `@tabler/icons-react`, при необходимости `react-icons` | Использовать разрешённые пакеты, self-hosted bundle, соблюдать лицензии наборов |
| Навигация | React Router | Использовать при появлении реальных маршрутов; не дублировать backend authorization |
| Локальное состояние | React state; Zustand по обоснованной необходимости | Никогда не сохранять `initData`, bearer subscription URL, HWID и session secrets в persistent client storage |
| Сервер | Существующий Python backend, provider-neutral `CustomerPortalService` | NestJS/Express, Electron, Go/Mihomo и отдельный 3x-ui web backend **не** требуются |

Это **утверждённый stack**, а не утверждение о готовых исходниках, уже установленных зависимостях, проверенных версиях пакетов или опубликованном продукте. В D1 требуется package manifest, pinned lockfile, license/SBOM review, baseline dependency audit, browser/mobile visual tests и проверка accessibility. Контур Telegram Web Apps/API включается только в D2 с серверной проверкой `initData`.

**Лицензионная граница:** `remnawave/subscription-page` лицензирован как `AGPL-3.0-only`; `legiz-ru/Prizrak-Box` — как `GPL-3.0`. Наш репозиторий использует `Apache-2.0`. Прямое копирование UI-компонентов, HTML/CSS, изображений и производного кода из этих проектов **не разрешено этим решением**. Использование независимо опубликованных React/Vite/Mantine/Tabler-библиотек оценивается по **их собственным** лицензиям. Если понадобится внешний код, сначала отдельный copyright/license review с анализом требований распространения и сетевого использования; без ревью — оригинальная реализация.

## Утверждённый визуальный ориентир и политика иконок

- **Цель UI:** собственная визуальная реализация по предоставленным скриншотам RightSide VPN: тёмно-синий фон, мятные акценты, округлые карточки, адаптивная desktop/mobile компоновка, удобные platform tabs, крупный выбор VPN-приложения с логотипом справа, пошаговая установка и рабочие «Назад/Далее». Точная технология самого RightSide VPN по этим скриншотам **не подтверждена**; копировать его бренд/ассеты нельзя.
- **Платформы:** iOS, Android, macOS, Windows, Linux; Android TV и Apple TV — только как UI-кандидаты после проверки реального поддерживаемого пути импорта. Списки клиентов определяет backend capability matrix #473, а не красивое изображение.
- **Клиенты:** Happ, Incy, Shadowrocket, v2raytun, V2Box, Karing, OneXray, Throne; RabbitHole, Prizrak-Box и другие — отдельные кандидаты, только после проверки версии, лицензии и настоящего deep-link/import format. Не добавлять fake-PASS или неработающие кнопки.
- **Иконки ОС:** подобрать сходные со скриншотами чистые SVG/векторные системные символы из лицензируемых наборов; различать обобщённую иконку устройства и защищённый логотип/товарный знак платформы.
- **Логотипы VPN-клиентов:** первичный визуальный источник — предоставленная оператором библиотека из 38 SVG; в D1 использовать её клиентские формы и цвета, сверив каждый публикуемый логотип с официальным источником и разрешением. Лицензия SVG-файла, лицензия репозитория и товарный знак — разные вопросы. `INCY-DEV/incy-icons` — исследованный MIT-кандидат; для каждого конкретного SVG всё равно проверять применимые условия и attribution. Не извлекать логотипы из скриншотов и не объявлять «точные» иконки доступными до проверки.
- **Asset manifest:** inventory предоставленных 39 иконок включён в docs; перед добавлением каждого бренда в runtime зафиксировать `client/platform → official source → asset license → trademark/permission outcome → attribution → stored path`; хранить очищенный SVG/PNG локально, запретить scripts, `foreignObject`, внешние `href`, remote fonts и трекеры. При неизвестных правах показывать нейтральный доступный символ + текст названия.
- **Доступность:** клавиатура и screen reader, контраст, mobile touch targets, `prefers-reduced-motion`, светлые/тёмные системные UI-состояния внутри Telegram и устойчивость при отсутствии изображений. Иконки декоративны и не несут единственный смысл действия.
- **Privacy:** никаких CDN, сторонних icon APIs или публичных QR-сервисов, в которые уходят bearer URL, Telegram identity или subscription metadata. Дизайн не может обойти backend owner/pilot checks.

**Acceptance D1 для этого решения:** (1) общий React/Vite/Mantine shell проверен на desktop и mobile; (2) шаги платформы и приложения сохраняют независимый fallback; (3) у каждого используемого asset есть проверяемое provenance/rights evidence или нейтральная замена; (4) нет скопированных AGPL/GPL компонентов и нет unsafe asset/network dependencies; (5) screenshot-based visual/a11y regressions и browser/WebView smoke выполнены с отдельными свидетельствами.

## Утверждённая SVG-библиотека оператора — 2026-10-23

**Решение:** для D1 использовать предоставленный оператором экспорт `svgLibrary` из Remnawave **как основную библиотеку внешнего вида и кандидатов на локальные SVG-ассеты**, а не заменять характерные клиентские логотипы однотипными пиктограммами. На этом же наборе строить выбор клиента в standalone subscription page и Telegram Mini App. Внешний сервис Remnawave для отображения SVG не нужен.

**Исходный набор:** 39 SVG = 26 логотипов VPN-клиентов, 5 значков платформ и 8 служебных иконок (38 из исходного экспорта Remnawave + отдельный SVG RabbitHole, переданный оператором). Библиотека передана оператором в этом диалоге как `remnawave_svg_library.json` (`svgLibrary`); актуальный расширенный файл — `remnawave_svg_library_39.json`; SHA-256 байтов исходного JSON: `eaa14d5522bccd0fa5f9cc2decb07912416b0b52d3b33d6892c4a97e6e91f64d`; расширенного JSON из 39 SVG: `26101eb3ed72de8af4a4a4cecb87298309ad37746e311912efcbbe9fc41ca8ef`. Перечень ключей и статусов — в [asset inventory](assets/subscription-svg-inventory.json). Есть `Happ`, `Shadowrocket`, `vrayTUN`, `PrizrakBox`, **`RabbitHole`** и остальные; самостоятельного SVG-ключа `INCY` пока **нет** (отрисовка позже). `RabbitHole` не входил в исходный экспорт и добавлен отдельно 2026-10-23. Не утверждать, что библиотека содержит то, чего в файле нет.

**Технический preflight:** все 39 SVG успешно разобраны XML-парсером, прошли базовую статическую проверку на `<script>`, event attributes и внешние ресурсы. Это **не** полноценный security audit, не browser-integration test и не подтверждение авторских/товарных прав. Для D1: повторно запускать sanitizer с allowlist SVG elements/attributes, отклонять `foreignObject`, JavaScript/data/external `href`, `url(...)`, внешние CSS/fonts и динамический markup; проверять SHA и рендер. Не использовать `dangerouslySetInnerHTML` с сырым SVG. После успешного review складывать одобренные изображения в self-hosted статические assets; отсутствие лицензии/прав означает `do_not_ship` для соответствующего **конкретного** SVG, а не отменяет выбор всей библиотеки.

**Права:** эксплуатация иконки в других проектах не доказывает разрешение на копирование. Экспорт из Remnawave тоже не присваивает нам права третьих лиц на дизайн логотипов. Утверждённое решение означает: **использовать предоставленный набор для дизайна, тестов и сопоставления**, затем для каждой публикуемой брендовой иконки проверить исходный официальный источник, лицензию, trademark/attribution и зафиксировать evidence в asset inventory. Если источник или разрешение не установлен, искать официальный аналог; только при отсутствии проверенной альтернативы применять нейтральный fallback с названием клиента. Не переносить вместе с SVG UI-код Remnawave под AGPL-3.0.

**Границы:** текущий PR #888 фиксирует решение и непубликуемый inventory ключей/хэшей, **не коммитит оригинальные SVG в публичный репозиторий до проверки прав**. Создание рабочего каталога/компонентов и встраивание разрешённых SVG — D1 в отдельном implementation PR. Не выставлять визуальный smoke, юридический review или production как PASS лишь на основании XML-разбора.

## Полный функциональный паритет Subscription Page и защищённый веб-редактор — решение оператора 2026-10-23

**Утверждено:** отдельная **защищённая веб-админка** (не редактирование через Telegram `/admin`) для визуального управления собственной standalone subscription page и Telegram Mini App. Один конфигурационный контракт/публичный рендерер, а не два раздельных редактора. Цель — **функциональный паритет** с возможностями Remnawave Subscription Page, установленными по операторскому JSON и изученным upstream исходникам; мы пишем **собственные** React/Mantine/Python реализации. Не копировать AGPL-код, сервер Remnawave, админский дизайн и GPL-компоненты.

### Верифицированный функциональный baseline

Оператор предоставил `subpage-00000000-0000-0000-0000-000000000000.json` (экспорт конфигурации Remnawave, 2026-10-23). Файл **не коммитить и не публиковать** целиком. SHA-256 исходных байтов `acc2a517287832fcf7e42d7482eceea55bdc2b6b670a6e5b3bab23680f323244`; инвентарь без ссылок/текстов/секретов: [subscription-page-feature-inventory.json](assets/subscription-page-feature-inventory.json). Из файла подтверждены **5 языков** `en/ru/zh/fa/fr`, **7 платформ** `ios/android/macos/windows/linux/appleTV/androidTV`, **24 записи приложений на платформах** (**10 уникальных названий**), **92 информационных блока**, **75 кнопок** (`external` 51, `subscriptionLink` 24), **20 ключей базовых переводов**, **38 встроенных SVG**, расширенных ранее отдельным `RabbitHole` до **39 SVG-кандидатов**; `INCY` добавить позже. Экспортные счётчики относятся к **конкретному файлу**, а не к лимитам наших возможностей.

| Раздел | Поддерживаемые настройки/функции | Основание |
| --- | --- | --- |
| Локализация | Включать/выключать доступные языки, `en/ru/zh/fa/fr`, ручное переключение и безопасный язык по умолчанию, автоопределение браузера/Telegram, RTL для `fa`; редактировать 20 базовых и все custom localized поля без silent fallback при обязательном переводе | `locales`, `baseTranslations`; upstream `LocalizationBlockComponent`, `useTranslation`, `i18next-browser-languagedetector` |
| Бренд | `title`, `logoUrl`, `supportUrl`, `metaTitle`, `metaDescription` | `brandingSettings`, `baseSettings` |
| Видимость чувствительных данных | `showConnectionKeys` (экспорт: **false**), `hideGetLinkButton` (экспорт: **false**), причём настройка UI **не равна авторизации**; получаемые raw keys — только отдельный серверный allow/deny и после HWID policy | `baseSettings`; upstream `webpage.service.ts` исключает `links` при выключенных ключах, `main.page.component.tsx` скрывает кнопку |
| Блок подписки | `expanded`, `collapsed`, `cards`, `hidden`; honest status/tariff/traffic/expiry/unknown согласно backend DTO | upstream `SUBSCRIPTION_INFO_BLOCK_RENDERERS` |
| Инструкции | `cards`, `timeline`, `accordion`, `minimal`, перестановка блоков и кнопок, настраиваемые заголовки, описания, предупреждения и цвета, внешний магазин, deep-link и copy | `uiConfig`, `platforms[*].apps[*].blocks`; upstream `BLOCK_RENDERERS` и editor |
| Платформы/клиенты | 7 платформ, редактирование списка/очерёдности, добавление/удаление, `featured`, выбор локального проверенного SVG; iOS/Android/Windows/macOS/Linux и TV **без обещания поддерживаемого импорта без smoke/capability checks** | `platforms`, `svgIconKey`; upstream `PlatformBlockComponent` и `AppEditorDrawerContent` |
| Кнопки | типы `external`, `subscriptionLink` и `copyButton` (последний подтверждён upstream editor/runtime, **не встречается в этом экспорте**), локализованный текст, SVG, шаги и порядок | `buttons`; upstream `ButtonEditor`, `InstallationGuideConnector` |
| SVG | 39 согласованных кандидатов, редактор/селектор/предпросмотр, sanitizer/provenance, локальные ассеты после copyright/trademark review; `INCY` later | `svgLibrary` исходных 38 + отдельный `RabbitHole`; [inventory](assets/subscription-svg-inventory.json) |
| Полный редактор | отдельная protected admin SPA: визуальные секции, редактирование платформ/приложений/переводов/брендинга, валидация, сохранение, импорт/экспорт full JSON, выборочный импорт `baseTranslations` / `platforms` / `svgLibrary`; миграция версий схемы | изученный upstream `subpage-config-editor-page.component.tsx` |
| Наши улучшения | черновики и предпросмотр desktop/mobile/WebView без выдачи секретов, версия/publish-approval, audit diff/history/rollback, проверка ссылок и состояния активной конфигурации | **отдельное оригинальное проектное решение**, а не подтверждённая функция Remnawave |

**Определения:** `hideGetLinkButton=true` скрывает только кнопку в шапке, но не отменяет серверную выдачу ссылки авторизованному клиенту для импорта; если скрыт Get Link, шаги, которым нужен ручной URL, должны предложить разрешённый fallback или быть отредактированы. `showConnectionKeys=true` разрешает **рассмотреть** показ, но **не** выдавать raw keys автоматически: требуются authenticated owner/entitlement/pilot/policy/HWID проверки и `no-store`; `showConnectionKeys=false` — backend исключает ссылки целиком, а не только прячет React-блок. Не раскрывать `{{SUBSCRIPTION_LINK}}`, `{{USERNAME}}` или настоящие ссылки в конфигурационном GET/preview, черновиках, публичном JSON, URL/логе/аналитике. Значения шаблонов подставляет только доверенный сервер или строго owner-scoped runtime после policy.

### Защищённая веб-админка — отдельный trust domain

- **Администратор входит независимо от клиента**: server-side подтверждение текущей operator/admin identity + RBAC, MFA/step-up для публикации по threat model, защищённая серверная сессия (`HttpOnly`, `Secure`, `SameSite`, bounded TTL, rotation и revocation). Точное подключение к существующей identity plane определить на D1 preflight; **не** принимать Telegram `initDataUnsafe`, произвольный ID, bearer subscription URL, `sub_id`, публичный share token или client session как admin-credential.
- Admin routes/API отделить namespace/origin и middleware от client portal и `/compat/{sub_id}`; server-side RBAC **на чтение и запись**. Mutations только через CSRF-protected авторизованные endpoints, origin allowlist, строгий CORS/CSP, rate/size quotas, audit actor/timestamp/old-new hashes; без прямых запросов из React в 3x-ui и без доступа к Docker/host shell.
- Конфигурации хранятся сервером с версионированием (черновик, preview, проверка, публикация, rollback); immutable audit trail и explicit publish action, no last-writer-wins overwrite (ETag/version conflict), transactions/idempotency, поэтапный флаг включения. Реальная публикация, rollout и rollback — после отдельного операционного разрешения/acceptance; один факт успешного `save draft` не равен production Published.
- **Import hardening:** schemaVersion allowlist/migration, max bytes/depth/strings, locale key check, неизвестные поля reject/quarantine, допустимые button types, запрещены arbitrary JS/HTML/CSS, `javascript:`, `data:`, `file:`, unsafe `http:` и непроверенные scheme handlers, server allowlisted/validated download hosts и client import formats из #473. Ссылки/команды из исходного экспорта **не объявлять проверенными**. SVG: allowlisted static sanitizer + provenance, не внедрять untrusted `dangerouslySetInnerHTML`.
- **No secrets in config artifacts**: экспорт и GitHub docs включают только safe template metadata; пользовательский JSON хранится локально у оператора до security review, не становится автоматически публичным asset. Preview использует synthetic/redacted fixtures; security negative tests для cross-account, CSRF, privilege escalation, unauthorized preview, malicious import, poisoned SVG, rollback/restore.
- Граница standalone user auth и Telegram `initData` остаётся этапом D2, а admin auth — самостоятельный этап с более строгим RBAC. Никаких фичи «управлять всеми настройками из клиента».

### Поэтапная реализация, зависимости и acceptance

| Gate | Объём будущего implementation PR | Проверка / переход |
| --- | --- | --- |
| **D0** (текущий docs-only PR #888) | Зафиксировать паритет и защищённый редактор; import/export схему, инвентарь и safety contract | CI docs, GitHub read-back; статус **не merged** пока отдельно не разрешено |
| **D1a** | React 19 + TypeScript + Vite + Mantine; собственный responsive public shell и конфигурационные `expanded/collapsed/cards/hidden`, `cards/timeline/accordion/minimal`; 5 языков, 7 платформ, validated import fixtures и 39 SVG-кандидатов (права отдельно) | Unit/snapshot/a11y/RTL/mobile/desktop/WebView visual smoke; fake fixtures; безопасные fallback, никаких live mutations |
| **D1b** | **Отдельная защищённая веб-админка**: admin-only login/RBAC, browser config editor, translations/platforms/apps/steps/buttons, preview, full/selective JSON import/export, draft, audit, publish proposal + rollback model | Threat model, auth/CSRF/role-negative тесты, конфигурационная schema validator и migration/version conflict тесты; реальные publish actions только после authorization gate |
| **D2** | Клиентский standalone login и Telegram Mini App `initData` verification; provider-neutral customer DTO, safe subscription-link/QR issuance, raw-key/HWID policy | Owner/pilot/expired/replay/IDOR/CSP/session/secret-leak negative tests, `/compat/` unchanged |
| **D3** | Allowlisted pilot, validated install/deeplink templates и TV/device/version checks, per-client import evidence, rollback/release/deployment отдельно | Targeted device/WebView + independent VPS/provider smoke, staged rollout approval, G-11 отдельно |

Acceptance D1b: администратор может локально выполнить полный конфигурационный цикл `import → edit → validate → preview → save draft → diff → publish proposal`, а операция публикации/rollback разрешается лишь проверенным server-side policy; клиент **не может** попасть в admin editor; UI toggles и raw links не обходят backend owner/HWID checks; тесты запрещённых URL/SVG/import и multi-admin races PASS. D1–D3 остаются **PENDING**, Issue #887 **OPEN**, платёжные и самостоятельные mutating функции не расширять этим решением.

## Отдельный внешний проект

[legiz-ru/Prizrak-Box](https://github.com/legiz-ru/Prizrak-Box), ветка `v3`, — Electron/Vue/Mihomo desktop-клиент под GPL-3.0, **не** готовый Mini App или публичный subscription portal. Документированный `prizrak-box://install-config?url=...` — возможная интеграция на Windows/macOS/Linux только после независимого smoke; не копировать GPL code/assets в бот без отдельной оценки license/dependencies/attribution. #702 (page-mascot) остаётся независимым необязательным расширением после собственной страницы.

## Поэтапная реализация

| Этап | Scope | Завершение |
| --- | --- | --- |
| D0 | Issue #887, архитектурное решение, Roadmap и required CI | Только docs PR merged/read-back, не runtime |
| D1 | Собственный responsive UI shell и read-only summary, шаги подключения, доступность | UI/a11y/visual/compat regression |
| D2 | Mini App и standalone authentication/session API | initData signature/freshness, negative IDOR/CSRF, rate/pilot gates |
| D3 | Контролируемый canary, per-client device smoke, provider-neutral traffic/HWID | Отдельные merge/release/deploy и targeted acceptance |

Декомпозиция D1–D3 требует самостоятельных implementation PR и тестов; D0 не означает разрешения deploy. Данные пользователя не маскировать моками в production. Новую веб-плоскость включать только через явный feature flag. Утверждённый frontend-стек и визуальный ориентир определены выше; точные версии зависимостей, hostname, web-session storage и инфраструктурные параметры согласуются в D1/D2 implementation preflight с проверкой threat model. Архитектурное решение D0 не подразумевает самовольной регистрации Telegram Menu Button, новых API публичного кабинета или создания web-session из bearer subscription URL.

## Acceptance и rollback

Для реализации требуются мобильный и desktop a11y smoke, owner/pilot/feature gates, multi-account isolation, чужой/просроченный `initData`, отсутствие утечек bearer в URL/логи/CDN/referrer, сохранение `/compat/` и QR/Copy fallback, честные ошибки и device import/refresh. Offline CI не заменяет устройство/VPS acceptance.

Пока D0 не merged, **Roadmap sync: PENDING**. После D0 acceptance: `#887 keep_open` до D1–D3 и отдельной реальной приёмки; merge документации не закрывает feature. При сбое новой web-плоскости она отключается feature flag, старые bot/compat endpoints остаются рабочими.
