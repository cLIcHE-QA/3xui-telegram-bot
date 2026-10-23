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

**Исходный набор:** 40 SVG = 27 логотипов VPN-клиентов, 5 значков платформ и 8 служебных иконок (38 из исходного экспорта Remnawave + отдельный SVG RabbitHole, переданный оператором). Библиотека передана оператором в этом диалоге как `remnawave_svg_library.json` (`svgLibrary`); актуальный расширенный файл — `remnawave_svg_library_39.json`; SHA-256 байтов исходного JSON: `eaa14d5522bccd0fa5f9cc2decb07912416b0b52d3b33d6892c4a97e6e91f64d`; расширенного JSON из 40 SVG: `26101eb3ed72de8af4a4a4cecb87298309ad37746e311912efcbbe9fc41ca8ef`. Перечень ключей и статусов — в [asset inventory](assets/subscription-svg-inventory.json). Есть `Happ`, `Shadowrocket`, `vrayTUN`, `PrizrakBox`, **`RabbitHole`** и остальные; SVG `INCY` получен оператором 2026-10-23 как 40-й кандидат; права и sanitizer PENDING. `RabbitHole` не входил в исходный экспорт и добавлен отдельно 2026-10-23. Не утверждать, что библиотека содержит то, чего в файле нет.

**Технический preflight:** все 40 SVG успешно разобраны XML-парсером, прошли базовую статическую проверку на `<script>`, event attributes и внешние ресурсы. Это **не** полноценный security audit, не browser-integration test и не подтверждение авторских/товарных прав. Для D1: повторно запускать sanitizer с allowlist SVG elements/attributes, отклонять `foreignObject`, JavaScript/data/external `href`, `url(...)`, внешние CSS/fonts и динамический markup; проверять SHA и рендер. Не использовать `dangerouslySetInnerHTML` с сырым SVG. После успешного review складывать одобренные изображения в self-hosted статические assets; отсутствие лицензии/прав означает `do_not_ship` для соответствующего **конкретного** SVG, а не отменяет выбор всей библиотеки.

**Права:** эксплуатация иконки в других проектах не доказывает разрешение на копирование. Экспорт из Remnawave тоже не присваивает нам права третьих лиц на дизайн логотипов. Утверждённое решение означает: **использовать предоставленный набор для дизайна, тестов и сопоставления**, затем для каждой публикуемой брендовой иконки проверить исходный официальный источник, лицензию, trademark/attribution и зафиксировать evidence в asset inventory. Если источник или разрешение не установлен, искать официальный аналог; только при отсутствии проверенной альтернативы применять нейтральный fallback с названием клиента. Не переносить вместе с SVG UI-код Remnawave под AGPL-3.0.

**Границы:** текущий PR #888 фиксирует решение и непубликуемый inventory ключей/хэшей, **не коммитит оригинальные SVG в публичный репозиторий до проверки прав**. Создание рабочего каталога/компонентов и встраивание разрешённых SVG — D1 в отдельном implementation PR. Не выставлять визуальный smoke, юридический review или production как PASS лишь на основании XML-разбора.

## Полный функциональный паритет Subscription Page и защищённый веб-редактор — решение оператора 2026-10-23

**Утверждено:** отдельная **защищённая веб-админка** (не редактирование через Telegram `/admin`) для визуального управления собственной standalone subscription page и Telegram Mini App. Один конфигурационный контракт/публичный рендерер, а не два раздельных редактора. Цель — **функциональный паритет** с возможностями Remnawave Subscription Page, установленными по операторскому JSON и изученным upstream исходникам; мы пишем **собственные** React/Mantine/Python реализации. Не копировать AGPL-код, сервер Remnawave, админский дизайн и GPL-компоненты.

### Верифицированный функциональный baseline

Оператор предоставил `subpage-00000000-0000-0000-0000-000000000000.json` (экспорт конфигурации Remnawave, 2026-10-23). Файл **не коммитить и не публиковать** целиком. SHA-256 исходных байтов `acc2a517287832fcf7e42d7482eceea55bdc2b6b670a6e5b3bab23680f323244`; инвентарь без ссылок/текстов/секретов: [subscription-page-feature-inventory.json](assets/subscription-page-export-inventory.json). Из файла подтверждены **5 языков** `en/ru/zh/fa/fr`, **7 платформ** `ios/android/macos/windows/linux/appleTV/androidTV`, **24 записи приложений на платформах** (**10 уникальных названий**), **92 информационных блока**, **75 кнопок** (`external` 51, `subscriptionLink` 24), **20 ключей базовых переводов**, **38 встроенных SVG**, расширенных ранее отдельным `RabbitHole` до **40 SVG-кандидатов**; `INCY` добавлен в inventory после отдельного предоставления. Экспортные счётчики относятся к **конкретному файлу**, а не к лимитам наших возможностей.

| Раздел | Поддерживаемые настройки/функции | Основание |
| --- | --- | --- |
| Локализация | Включать/выключать доступные языки, `en/ru/zh/fa/fr`, ручное переключение и безопасный язык по умолчанию, автоопределение браузера/Telegram, RTL для `fa`; редактировать 20 базовых и все custom localized поля без silent fallback при обязательном переводе | `locales`, `baseTranslations`; upstream `LocalizationBlockComponent`, `useTranslation`, `i18next-browser-languagedetector` |
| Бренд | `title`, `logoUrl`, `supportUrl`, `metaTitle`, `metaDescription` | `brandingSettings`, `baseSettings` |
| Видимость чувствительных данных | `showConnectionKeys` (экспорт: **false**), `hideGetLinkButton` (экспорт: **false**), причём настройка UI **не равна авторизации**; получаемые raw keys — только отдельный серверный allow/deny и после HWID policy | `baseSettings`; upstream `webpage.service.ts` исключает `links` при выключенных ключах, `main.page.component.tsx` скрывает кнопку |
| Блок подписки | `expanded`, `collapsed`, `cards`, `hidden`; honest status/tariff/traffic/expiry/unknown согласно backend DTO | upstream `SUBSCRIPTION_INFO_BLOCK_RENDERERS` |
| Инструкции | `cards`, `timeline`, `accordion`, `minimal`, перестановка блоков и кнопок, настраиваемые заголовки, описания, предупреждения и цвета, внешний магазин, deep-link и copy | `uiConfig`, `platforms[*].apps[*].blocks`; upstream `BLOCK_RENDERERS` и editor |
| Платформы/клиенты | 7 платформ, редактирование списка/очерёдности, добавление/удаление, `featured`, выбор локального проверенного SVG; iOS/Android/Windows/macOS/Linux и TV **без обещания поддерживаемого импорта без smoke/capability checks** | `platforms`, `svgIconKey`; upstream `PlatformBlockComponent` и `AppEditorDrawerContent` |
| Кнопки | типы `external`, `subscriptionLink` и `copyButton` (последний подтверждён upstream editor/runtime, **не встречается в этом экспорте**), локализованный текст, SVG, шаги и порядок | `buttons`; upstream `ButtonEditor`, `InstallationGuideConnector` |
| SVG | 40 согласованных кандидатов, редактор/селектор/предпросмотр, sanitizer/provenance, локальные ассеты после copyright/trademark review; `INCY` SVG-кандидат добавлен | `svgLibrary` исходных 38 + отдельный `RabbitHole`; [inventory](assets/subscription-svg-inventory.json) |
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
| **D1a** | React 19 + TypeScript + Vite + Mantine; собственный responsive public shell и конфигурационные `expanded/collapsed/cards/hidden`, `cards/timeline/accordion/minimal`; 5 языков, 7 платформ, validated import fixtures и 40 SVG-кандидатов (права отдельно) | Unit/snapshot/a11y/RTL/mobile/desktop/WebView visual smoke; fake fixtures; безопасные fallback, никаких live mutations |
| **D1b** | **Отдельная защищённая веб-админка**: admin-only login/RBAC, browser config editor, translations/platforms/apps/steps/buttons, preview, full/selective JSON import/export, draft, audit, publish proposal + rollback model | Threat model, auth/CSRF/role-negative тесты, конфигурационная schema validator и migration/version conflict тесты; реальные publish actions только после authorization gate |
| **D2** | Клиентский standalone login и Telegram Mini App `initData` verification; provider-neutral customer DTO, safe subscription-link/QR issuance, raw-key/HWID policy | Owner/pilot/expired/replay/IDOR/CSP/session/secret-leak negative tests, `/compat/` unchanged |
| **D3** | Allowlisted pilot, validated install/deeplink templates и TV/device/version checks, per-client import evidence, rollback/release/deployment отдельно | Targeted device/WebView + independent VPS/provider smoke, staged rollout approval, G-11 отдельно |

Acceptance D1b: администратор может локально выполнить полный конфигурационный цикл `import → edit → validate → preview → save draft → diff → publish proposal`, а операция публикации/rollback разрешается лишь проверенным server-side policy; клиент **не может** попасть в admin editor; UI toggles и raw links не обходят backend owner/HWID checks; тесты запрещённых URL/SVG/import и multi-admin races PASS. D1–D3 остаются **PENDING**, Issue #887 **OPEN**, платёжные и самостоятельные mutating функции не расширять этим решением.

### Правило точного переиспользования операторского JSON (утверждено 2026-10-23)

**Решение:** предоставленный оператором экспорт Remnawave `subpage-00000000-0000-0000-0000-000000000000.json` использовать как **канонический исходный контент**. Не сочинять новые переводы, не переписывать пользовательские инструкции и не изменять порядок, названия, цвета, выбранные настройки или deep-link шаблоны по собственному усмотрению. Независимо реализовать **наш** валидатор/рендерер/редактор React/Mantine/Python, совместимый с данными формата исходной версии `1`; не копировать AGPL/GPL код редактора Remnawave. Оригинал сохранять неизменным и доступным для сравнения в защищённом operator-controlled хранилище; **не размещать сырой экспорт в открытом GitHub**, его SHA-256 `acc2a517287832fcf7e42d7482eceea55bdc2b6b670a6e5b3bab23680f323244`.

**Acceptance «один-в-один» при импорте:** сохранить порядок языков `en → ru → zh → fa → fr`, все 20 переводимых базовых ключей и все `title/description/button.text` на пяти языках; порядок платформ `ios → linux → macos → android → appleTV → windows → androidTV`; 24 записи приложений (10 уникальных названий), `featured`, `svgIconKey` и `svgIconColor`, последовательность 92 информационных блоков и 75 кнопок с их `type/link/text`. Текущие исходные `expanded` + `cards`, `showConnectionKeys=false` и `hideGetLinkButton=false` сохранять как **настройки импортированного шаблона**, а не насильно принимать как значения всех будущих профилей. `{{SUBSCRIPTION_LINK}}` и `{{USERNAME}}` хранить только как шаблонные маркеры, разрешать их лишь в авторизованном runtime на основе серверного owner/policy.

**Изображения:** исходные 38 SVG из JSON остаются привязанными к своим ключам; `RabbitHole` — дополнение к набору иконок #39, отдельно от неизменного JSON; `INCY` будет добавлена позднее. Проверка происхождения/прав и безопасности SVG обязательна до использования в публичном build. То же относится к внешним URL, командам установки и клиентским URL schemes в инструкциях: сохранить в исходнике точную запись, но потенциально небезопасный/устаревший пункт **отметить как blocked/quarantined и показать в отчёте**, а не самовольно подменять или размещать рабочую небезопасную кнопку. HWID, `/compat/`, ссылки подписок и backend authorization неизменны.

**Наши новые функции** (предпросмотр, админ-аутентификация, версии, история, публикация, откат, дополнительные темы, новые языки/клиенты/иконки) идут **отдельным версионированным overlay**. Кнопка «Вернуться к исходной конфигурации» и file-level / parsed-object diff должны позволять точно восстановить оригинал. D1a: parser+normalizer с roundtrip без необъяснимой потери/замены полей, golden tests на 5/7/24/92/75 и 20 базовых ключей, сравнение реальных строк/порядка, synthetic preview; D1b: защищённый импорт исходного JSON администратором, snapshot/diff, просмотр заблокированных URL/SVG и отдельно одобряемая публикация.

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

### D1a: типографика и имитация мобильного WebView (scope #887)

Для staged Draft PR #889 предусмотрено browser-only покрытие масштабирования
текста до 200%, контраста основных поверхностей и безопасных
`viewport-fit=cover`/`safe-area-inset`. Android-like режим проверяется
mobile Chromium, iOS-like — отдельным Playwright WebKit проектом; используются
только синтетические данные, без Telegram `initData`, backend API,
production credentials или выдачи реальных subscription URLs.

**Граница приёмки:** PASS таких эмуляций подтверждает лишь отдельные
браузерные сценарии D1a. Реальная Telegram WebView-навигация,
обработка viewport событий, клавиатура устройства, смена системного шрифта
и безопасная авторизация по `initData` требуют отдельных device/
integration smoke на D2. CI нового SHA и визуальный review — PENDING до
read-back. Issue #887 остаётся открытым, общий audit #890 отдельно.

### D1a — компактная карусель инструкций и рамка ОС

По предложению оператора на основе референса RightSide VPN используется **оригинальный** UI-only режим `carousel` с одним шагом на экране, нумерацией и навигацией. Четыре контрактных вида из JSON v1 (`cards/timeline/accordion/minimal`) остаются без изменений; при локальном импорте исходная настройка не подменяется. Действия с URL и ключами остаются заблокированы.

Выбор ОС помещён в общую округлую рамку без нижней линии и отдельных контуров; mobile-список прокручивается локально с touch targets и клавиатурой. Новый UI не доказывает реальное подключение VPN или готовность Telegram Mini App. Scoped browser CI и visual evidence требуют независимого подтверждения на head PR #889; #887 OPEN, security #890 отдельно.

### D1a — статус, тариф, трафик, окончание и сброс

Новый фирменный Demo Preview для `expanded` и `cards` показывает четыре смысловые плитки: тариф, статус, трафик и срок действия, плюс отдельное поле сброса трафика. В основе собственные графитовые поверхности и цветовая кодировка статусов: синий/cyan, зелёный, янтарный, розовый/красный. Подлинный `plan`, `traffic reset`, `expiresAt` и quota должны поступать только из авторизованного provider-neutral DTO при D2. Неизвестное значение всегда «Нет данных»/«Не указан», не ACTIVE. В демо 24.6/100 GB и 15 дней вымышленные и обозначены. Схема экспортируемого JSON не изменена, real credentials и bearer URLs не рендерятся. Reference Remnawave использован только для смысловой группировки цветов; AGPL CSS/код не копировался. #887 OPEN, #497 отдельный backend/Telegram issue, CI нового head PENDING.

### D1a — умеренная анимация и доступность

Внешний вид Raccoon VPN допускает original micro-interactions: подъём карточек 3px, кнопок 2px при десктопном hover и медленный 8-секундный перелив фирменного текста hero в голубой/сиреневой гамме. Нельзя имитировать доступность disabled CTA, вводить внешний CDN или копировать визуальные ассеты из пользовательского видеореференса. При coarse pointer, отсутствии hover и `prefers-reduced-motion:reduce` движение отсутствует; focus-visible сохраняется. Playwright проверяет hover и reduced-motion отдельно, новый SHA требует CI read-back. #887 OPEN; backend, реальные подписки, Mini App и security #890 отдельно.

### D1a — фоновые световые акценты

В D1a Draft #889 добавлены оригинальные негромкие ambient-градиенты в верхних углах тёмной страницы на чистом CSS без ассетов внешнего референса: голубой и приглушённый фиолетовый. Слой находится под содержимым, не блокирует клики/фокус, центр почти чёрный, на мобильных интенсивность меньше. Лёгкая 26-секундная вариация прозрачности отключается при reduced motion. Scoped CI и снимки desktop/mobile обязательны, реальный Telegram WebView отдельно; #887 OPEN.


### D1a — локальная интеграция проверяемых SVG

Оператор подтвердил допустимость использования ранее согласованных внешних SVG-кандидатов. Реестр `docs/assets/subscription-svg-inventory.json` содержит 40 ключей и SHA-префиксы, **не содержит байты SVG** и не является доказательством их технического включения в публичный build. Поэтому D1a добавляет локальный операторский импорт `svgLibrary` из JSON с allowlist sanitizer и fallback. SVG показаны только в пассивных `img` с data URI; опасные XML/SVG конструкты не проходят, никаких CDN/JS/сырого `dangerouslySetInnerHTML` нет. Реальное закрепление всех 40 статических ассетов и SVG lifecycle — отдельный шаг после точного подтверждения содержимого. Scroll-driven эффекты необязательны и не вводятся для ключевого UI.


### D1a — закреплённый исходный SVG INCY

В self-hosted build добавлен **официальный** `client-icons/incy.svg`, источник [INCY-DEV/incy-icons](https://github.com/INCY-DEV/incy-icons/blob/3d6e4a076d54ea036c61b34302ecee01bea30a80/INCY-00002.svg), Git blob `cb6c0417b41d77537d2c5fd90225110ad3e57e43`, лицензия MIT сохранена в `client-icons/INCY-LICENSE.txt` (Git blob `9aa242dfc6cba1f491c5d9b198e2ddceb6011860`). При ключе `INCY` используется локальный значок без CDN, если не предоставлен отдельный безопасный operator SVG.

**Граница:** это **1** подтверждённый файл из 40 кандидатов и **не** byte-identical копия инвентаризованного оператором SVG INCY: у того исходная каноникализация не завершена. Исходные 39 SVG получены от оператора локальным `svg.zip` и точно сопоставлены с каталогом и реестром; **в GitHub/runtime их байты не размещены** до отдельного review прав. Не заменять их другими картинками без evidence. Отдельный SVG-прогресс длинных инструкций и scroll-reveal намеренно **не включены**: текущая карусель короткая, а приёмка keyboard/RTL/reduced-motion важнее декоративного scroll. CI на новом SHA PENDING.


### D1a — восстановлен SVG-пакет и проверена целостность (2026-10-24)

Оператор предоставил локальный архив `svg.zip`: `svg/svgLibrary.json`, `svg/manifest.json`, 39 отдельных `svg/icons/*.svg` и `README_REVIEW_ONLY.txt`. **SHA-256 ZIP:** `75602476eab4b08e4e6b3c8d0e680defc1be6929d6482585277bd724656ad76b`. **SHA-256 `svgLibrary.json`:** `26101eb3ed72de8af4a4a4cecb87298309ad37746e311912efcbbe9fc41ca8ef` — точное совпадение с ранее зафиксированным источником. Проверены 39/39 имён, индивидуальные SHA по manifest/inventory, 39/39 побайтовых соответствий отдельного SVG содержимому JSON и статический XML preflight. `RabbitHole` входит в 39; `INCY` — отдельный, ранее закреплённый официальный MIT-ассет, не часть ZIP.

Веточная проверка воспроизводима локально: `python3 scripts/check-subscription-svg-package.py --archive /private/path/svg.zip`. Тесты `tests/test_subscription_svg_package.py` используют **только синтетические SVG** и отрицательные сценарии; реальные 39 файлов в GitHub и CI не передаются. Ни SVG-содержимое, ни приватный конфигурационный экспорт, ни источники подписок не помещаются в PR/логи.

Проверка целостности **PASS** не заменяет индивидуальные provenance, license, trademark, полноценный security review и визуальную аттестацию: для 39 SVG `PENDING/BLOCKED`, нейтральный fallback сохраняется. Это offline D1a evidence, не `Published`, `Deployed` или production `Accepted`; Issue #887 `keep_open`. См. [датированный audit](audits/2026-10-24-svg-package-integrity-887.md) и [inventory](assets/subscription-svg-inventory.json).
