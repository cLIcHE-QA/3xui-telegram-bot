# Единая страница подписки и Telegram Mini App — решение #887

**Решение оператора 2026-10-23 (UTC+03:00):** использовать один собственный адаптивный веб-интерфейс в двух режимах — standalone subscription page и Telegram Mini App. Архитектурный D0 [PR #888](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/888) и изолированный D1a offline/browser preview [PR #889](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/889) **MERGED** в `main` (D1a SHA `74038c37ddbc13d312727c5f1e5c247c8eb1d8ba`), но D1b защищённый редактор, D2 авторизация, D3 действующие подключения, публикация, deployment и production acceptance **PENDING**. Нормативное состояние задач и релизов — в [Roadmap](../ROADMAP.md); финальный [D1a post-merge audit](audits/2026-10-24-887-d1a-postmerge-checkpoint.md).

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

**Границы:** слитый docs-only PR #888 фиксирует архитектурное решение и обезличенный inventory ключей/хэшей, **не коммитит оригинальные SVG в публичный репозиторий**. Создание рабочего каталога/компонентов и встраивание разрешённых SVG — D1 в отдельном implementation PR. Не выставлять визуальный smoke, юридический review или production как PASS лишь на основании XML-разбора.

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
| **D0** ([docs-only PR #888](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/888), MERGED) | Паритет и защищённый редактор; import/export схема, инвентарь и safety contract | Squash merge `3828a417bc0de6fe61f9df878cce043c15bfd343`; предмерджевые `test/title` и post-merge `main test` PASS, независимый GitHub read-back PASS. Это D0 docs-only, не runtime-acceptance |
| **D1a** ([PR #889](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/889), MERGED) | React 19 + TypeScript + Vite + Mantine; собственный responsive public shell и конфигурационные `expanded/collapsed/cards/hidden`, `cards/timeline/accordion/minimal` + visual-only carousel; 5 языков, 7 платформ, локальный JSON v1 parser, 39 оригинальных self-hosted SVG + отдельный INCY MIT | Squash `74038c37ddbc13d312727c5f1e5c247c8eb1d8ba`; pre-merge `test/title/audit/frontend-model` PASS, 43/43 browser smoke, RTL 200% visual review. **Только изолированный offline preview**: real content parity/WebView/device/авторизация/импорт остаются PENDING |
| **D1b** | **Отдельная защищённая веб-админка**: admin-only login/RBAC, browser config editor, translations/platforms/apps/steps/buttons, preview, full/selective JSON import/export, draft, audit, publish proposal + rollback model | Threat model, auth/CSRF/role-negative тесты, конфигурационная schema validator и migration/version conflict тесты; реальные publish actions только после authorization gate |
| **D2** | Клиентский standalone login и Telegram Mini App `initData` verification; provider-neutral customer DTO, safe subscription-link/QR issuance, raw-key/HWID policy | Owner/pilot/expired/replay/IDOR/CSP/session/secret-leak negative tests, `/compat/` unchanged |
| **D3** | Allowlisted pilot, validated install/deeplink templates и TV/device/version checks, per-client import evidence, rollback/release/deployment отдельно | Targeted device/WebView + independent VPS/provider smoke, staged rollout approval, G-11 отдельно |

Acceptance D1b: администратор может локально выполнить полный конфигурационный цикл `import → edit → validate → preview → save draft → diff → publish proposal`, а операция публикации/rollback разрешается лишь проверенным server-side policy; клиент **не может** попасть в admin editor; UI toggles и raw links не обходят backend owner/HWID checks; тесты запрещённых URL/SVG/import и multi-admin races PASS. D1a offline/browser scoped PASS в `main`; D1b/D2/D3 и product acceptance **PENDING**, Issue #887 **OPEN**, платёжные и самостоятельные mutating функции не расширять этим решением.

### Правило точного переиспользования операторского JSON (утверждено 2026-10-23)

**Решение:** предоставленный оператором экспорт Remnawave `subpage-00000000-0000-0000-0000-000000000000.json` использовать как **канонический исходный контент**. Не сочинять новые переводы, не переписывать пользовательские инструкции и не изменять порядок, названия, цвета, выбранные настройки или deep-link шаблоны по собственному усмотрению. Независимо реализовать **наш** валидатор/рендерер/редактор React/Mantine/Python, совместимый с данными формата исходной версии `1`; не копировать AGPL/GPL код редактора Remnawave. Оригинал сохранять неизменным и доступным для сравнения в защищённом operator-controlled хранилище; **не размещать сырой экспорт в открытом GitHub**, его SHA-256 `acc2a517287832fcf7e42d7482eceea55bdc2b6b670a6e5b3bab23680f323244`.

**Acceptance «один-в-один» при импорте:** сохранить порядок языков `en → ru → zh → fa → fr`, все 20 переводимых базовых ключей и все `title/description/button.text` на пяти языках; порядок платформ `ios → linux → macos → android → appleTV → windows → androidTV`; 24 записи приложений (10 уникальных названий), `featured`, `svgIconKey` и `svgIconColor`, последовательность 92 информационных блоков и 75 кнопок с их `type/link/text`. Текущие исходные `expanded` + `cards`, `showConnectionKeys=false` и `hideGetLinkButton=false` сохранять как **настройки импортированного шаблона**, а не насильно принимать как значения всех будущих профилей. `{{SUBSCRIPTION_LINK}}` и `{{USERNAME}}` хранить только как шаблонные маркеры, разрешать их лишь в авторизованном runtime на основе серверного owner/policy.

**Изображения:** исходные 38 SVG из JSON остаются привязанными к своим ключам; `RabbitHole` — дополнение к набору иконок #39, отдельно от неизменного JSON; `INCY` — отдельный официальный MIT-ассет, добавленный в D1a [PR #889](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/889), без инструкции подключения. Проверка происхождения/прав и безопасности SVG обязательна до использования в публичном build. То же относится к внешним URL, командам установки и клиентским URL schemes в инструкциях: сохранить в исходнике точную запись, но потенциально небезопасный/устаревший пункт **отметить как blocked/quarantined и показать в отчёте**, а не самовольно подменять или размещать рабочую небезопасную кнопку. HWID, `/compat/`, ссылки подписок и backend authorization неизменны.

**Отложенные инструкции INCY и RabbitHole (решение оператора 2026-10-24, #887):** в неизменяемом исходном экспорте v1 (SHA-256 `acc2a517287832fcf7e42d7482eceea55bdc2b6b670a6e5b3bab23680f323244`) среди 10 уникальных названий приложений **нет `INCY` и `RabbitHole`**. Следовательно, их собственные пошаговые инструкции, локализованные тексты и кнопки **не входят** в исходные 92 блока / 75 кнопок. Оператор предоставит материалы для обоих клиентов **позже; срок не назначен**. Это **PENDING**, а не пропуск проверки или разрешение придумывать шаги. Отдельно от инструкций: SVG-иконки обоих клиентов находятся в слитом в `main` D1a [PR #889](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/889); наличие иконки не означает готовность инструкций, проверенных ссылок либо работающий import/deeplink. После получения материалов проверить точные тексты, языки, платформы, версии клиентов, URL/deeplink, права на материалы и безопасные fallback; добавить инструкции как отдельное версионированное расширение, **не изменяя эталонный JSON**, с regression и targeted device/WebView smoke до включения действий. До этого в preview допустим только честный empty/PENDING, без вымышленных кнопок или ложного `PASS`.

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

D0 docs-only PR #888 **MERGED** 2026-10-24 в `main` `3828a417bc0de6fe61f9df878cce043c15bfd343` (required `test/title` pre-merge и `main test` post-merge PASS; независимый GitHub read-back подтверждён). D0 Roadmap checkpoint [PR #894](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/894) **MERGED** в `main` `a59da4ede21803b634eea5da584efea2a13e7efa`; GitHub PR/file/read-back подтверждён, предмерджевые `test/title` PASS. Это не runtime/product acceptance. После архитектурного D0: `#887 keep_open` до D1–D3, инструкций INCY/RabbitHole и отдельной реальной приёмки; merge документации не закрывает feature. При сбое новой web-плоскости она отключается feature flag, старые bot/compat endpoints остаются рабочими.

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

### D1a — операторское разрешение и локальная поставка 40 SVG (2026-10-24)

Оператор 2026-10-24 **подтвердил урегулирование лицензий и товарных знаков и явно разрешил включить весь набор в репозиторий/интерфейс**. Это operator-reported permission, не независимая юридическая экспертиза. В Draft PR #889 включены **39 исходных** self-hosted SVG, сверенных с JSON/manifest, и отдельный ранее закреплённый официальный MIT INCY; дополнительный предоставленный монохромный INCY сохранён отдельным вариантом и не заменяет основной. Статический список ключей `staticSvgPaths.ts` не позволяет формировать произвольные URL. Приоритет имеет безопасный локальный импорт; при его отсутствии используется проверенный статический asset, иначе — нейтральный fallback. CDN и внешние запросы не добавлены.

**Область разрешения:** D1a preview/статические ресурсы в ветке PR; это не автоматическое разрешение merge/release/deployment и не PASS реального WebView/production. Исходный приватный конфигурационный экспорт по-прежнему не коммитится. Ранее зафиксированные `PENDING` по отсутствующим байтам/разрешению оператора в исторических блоках отражают прежнее состояние; текущий статус задан этим новым checkpoint и inventory.

### D1a — проверяемый импорт и покрытие пошаговых инструкций (2026-10-24)

Предпросмотр PR #889 теперь показывает **только структурный отчёт локально импортированной конфигурации**: число платформ, слотов приложений, шагов и кнопок, отдельные счётчики типов `external`/`subscriptionLink`/`copyButton` и покрытие по каждой из семи платформ. Названия, тексты, пользовательские URL, SVG и маркеры `{{SUBSCRIPTION_LINK}}` в отчёт не попадают. Сами шаги уже рендерятся строго в порядке импорта на пяти языках, включая RTL `fa`; клиентские кнопки **всегда disabled** в D1a независимо от формата ссылки. Никакого сетевого запроса или выполнения импортируемого URL в preview не возникает.

Добавлен чисто **синтетический** golden test на структуру известного baseline `5 локалей / 7 платформ / 24 app slots / 10 уникальных клиентов / 92 шага / 75 кнопок (51 external + 24 subscriptionLink) / 20 базовых переводов / 38 встроенных SVG`; тест проверяет точный JSON roundtrip, порядок платформ, счётчики и отсутствие URL в отчёте. Browser test покрывает смену платформы, `ru/fa` и RTL, а также инертность вредоносного `javascript:` в импортируемом JSON. **Это не утверждение о побайтовом совпадении с оригинальным экспортом**, которого нет в публичном репозитории: original SHA `acc2a517287832fcf7e42d7482eceea55bdc2b6b670a6e5b3bab23680f323244` можно проверить только в операторском закрытом окружении (существующий optional test `OPERATOR_SUBPAGE_JSON`). Подмена оригинальных текстов и URL синтетикой запрещена; контент/проверенные клиентские deep-links, D2 auth, D3 device/WebView acceptance — PENDING. #887 keep_open.

D1a default synthetic UI показывает **все 7 платформ**. У Apple TV и Android TV до импорта проверенной конфигурации — **пустой список клиентов** и честное сообщение об отсутствии инструкций; это не утверждение о поддержанном VPN-приложении или протестированном TV-deeplink. Реальный TV client/import требует D3 capability/device evidence.

### D1a — синхронизация с D0 и Roadmap main после #894 (2026-10-24)

GitHub-проверка: архитектурный docs-only PR #888 Squash MERGED (`3828a417bc0de6fe61f9df878cce043c15bfd343`), отдельный Roadmap checkpoint #894 Squash MERGED (`a59da4ede21803b634eea5da584efea2a13e7efa`). Ветвь D1a PR #889 синхронизируется через **двухродительский merge commit без force-push**: `docs/ROADMAP.md` взят целиком из `main`, нормативная D0-основа `docs/WEB_SUBSCRIPTION_MINI_APP.md` взята из `main` и дополнена сохранёнными выше 9 разделами D1a, операторский SVG inventory и весь исходный D1a код/тесты оставлены в исходной ветке. Датированный D0 audit #894 сохранён из `main`. Это не merge PR #889 и не release.

**Отложено по решению оператора:** проверенные инструкции для `INCY` и `RabbitHole` будут предоставлены позднее (срок не определён), исходный JSON v1 их не содержит; исходный экспорт неизменен, SVG ≠ инструкции. В D1a действия и ссылки остаются `disabled`/PENDING; не конструировать сценарии без проверенных материалов. 

Новые required `test/title/audit/frontend-model` и независимый GitHub read-back **PENDING** до CI на новом head PR #889; прежний 41/41 Playwright PASS относится только к предыдущему SHA. D1a/D1b/D2/D3 product acceptance, реальный приватный 1:1 JSON, Telegram WebView, device import и release/deploy остаются PENDING. #887 OPEN/keep_open.


### D1a — факт слияния и границы приёмки (2026-10-24)

По отдельному разрешению оператора D1a [PR #889](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/889) **Squash MERGED** 2026-10-24T10:25:46Z в `main` `74038c37ddbc13d312727c5f1e5c247c8eb1d8ba`; head перед merge `dd3effe46fffc57fe1d9bbe6c94a1fc2dc7b4aa3`. Сквозной кодовый/визуальный preview gate `test/title/audit/frontend-model` и Playwright 43/43 PASS относится к закрытому **D1a offline preview scope**, а не реальному Telegram Mini App. Постмерджевое `main` Actions evidence и Roadmap reconciliation закреплены в [аудите](audits/2026-10-24-887-d1a-postmerge-checkpoint.md); синхронизация статуса Roadmap требует отдельного docs-only PR и merge approval.

**Безопасные границы:** исходный JSON v1 не публикуется; D1a локально показывает только синтетическую подписку и инструкции, кнопки `external/subscriptionLink/copyButton` заблокированы. Отсутствующие материалы INCY/RabbitHole оператор предоставит позднее (без срока); SVG не даёт оснований утверждать готовность инструкций. D1b admin RBAC/CSRF/editor, D2 separate standalone + Telegram `initData` server-side auth, D3 validated real links/fallback и device/WebView/canary, целостный 1:1 операторский экспорт, Release, Deployed, Accepted и G-11 остаются разными gates. #887 `keep_open`, публикация/развёртывание не выполнялись.

### D1b — начальный защищённый браузерный редактор (2026-10-24, Issue #887)

**Изменения только в отдельной feature branch; ещё не main, не Published и не Deployed.**
Новый opt-in Python модуль subscription_page_admin.py и независимая React-страница admin.html/src/admin.tsx. Ни бот, ни /compat/, ни текущий app_runtime не подключают сервер D1b. Новый runtime listener, publish/rollback и реальные подписки отсутствуют.

Безопасность: отдельные пароли PBKDF2, роли viewer/editor/owner, Secure/HttpOnly/SameSite Strict cookie, ограниченные по времени сессии, точный HTTPS Origin+Host, CSRF, лимит login attempts; Telegram ID и subscription URL не дают права на admin. Черновики оригинального JSON v1 хранятся только в отдельной SQLite базе с Fernet-шифрованием и owner-only правами, ревизии проверяются через обязательный If-Match с 409 при конфликте. Audit сохраняет лишь актор, SHA-256 и timestamp, не URL/SVG/текст конфигурации.

UI поддерживает отдельный login, редактирование локализаций, брендинга, настроек, платформ, VPN-клиентов, шагов, кнопок, полный/выборочный JSON import/export и инертный preview. Owner может создать только metadata-only предложение pending_manual_review, не публикацию. Сырые SVG/URL не вставляются в исполняемый HTML, ссылки и импорт подписок не запускаются.

**Усиление Draft D1b (не merged):** предпросмотр платформ/клиентов/шагов/заблокированных действий теперь привязан к тем же 40 локальным SVG, что D1a (39 + INCY MIT) через `SafeSvgIcon` и статический реестр с приоритетом проверенного файла; неизвестные SVG явно обозначаются, исполняемые HTML/URL не внедряются. Пароль и отдельный TOTP-код обязательны для `viewer/editor/owner`, повтор кода и общие MFA-seed разных пользователей запрещены; 300s idle, bounded session/login state и строгий SQLite owner-only усилены отрицательными тестами. **Это кодовый preview, не operator enrollment и не production-approved auth.**

**PENDING до product acceptance:** production HTTPS/TLS reverse proxy и distributed rate limiting, безопасное офлайн-MFA enrollment/recovery, ротация/восстановление Fernet ключа, persistent/distributed sessions и межхостовой MFA replay state, независимые security и race tests, утверждение реальных URL/SVG, publish/rollback, 1:1 закрытый оригинал, D2/D3 и реальный WebView/device smoke. Инструкции INCY/RabbitHole оператор предоставит позже. Roadmap #887 остаётся 🟡 лишь за уже слитый D1a; D1b Draft не равен Merged/Published/Accepted.

### D1b — долговременная защита от повторного TOTP (2026-10-24, Issue #887)

В Draft PR #896 защита от повторного TOTP-подтверждения больше не опирается только на память отдельного процесса. В отдельной приватной базе D1b хранится минимальный реестр `admin_totp_replay(username, last_step)`: **не** секрет TOTP и **не** введённый код. `issue_session()` атомарно отклоняет тот же либо более старый временной шаг в транзакции SQLite `BEGIN IMMEDIATE`; отказ записи состояния блокирует вход (`503`), а не пропускает MFA. Два экземпляра, использующие одну базу, не могут повторно принять использованный шаг; проверка перезапуска/общей базы покрыта отдельными тестами. Это изменение изолированной D1b schema, не миграция действующей SQLite базы бота.

**Граница доказательств:** GitHub CI нового head и операторский runtime пока PENDING; общее хранилище между разными VPS, recovery/enrollment, ротация Fernet/TOTP, защищённый HTTPS, защита распределённой сессии, независимая threat-model/race проверка и реальная приёмка остаются PENDING. Ни готовность к публикации, ни разрешение на merge/release/deploy этим исправлением не утверждаются.

### D1b — защищённое общее хранилище админ-сессий (2026-10-24, Issue #887)

В той же **изолированной** owner-only SQLite базе D1b находятся `admin_sessions` и `admin_totp_replay`. Идентификаторы cookie в SQLite не сохраняются: ключ — SHA-256 от непредсказуемого session token; CSRF секрет зашифрован Fernet. Сеансы ограничены TTL, 300-секундным idle timeout и суммарной ёмкостью 64 записи. Проверка и продление idle времени выполняются сервером через атомарную SQLite-транзакцию; logout отзывает сессию и для других экземпляров, использующих ту же базу. При порче Fernet-записи сессия отклоняется. Host/Origin проверяются до продления времени активности. Действующие права берутся из текущей конфигурации учётной записи экземпляра, а не из старой роли в cookie/DB; согласованная смена ролей на всех серверах и отзыв после удаления администратора остаются operator lifecycle gate.

Вход сначала подтверждает пароль + TOTP, затем **в одной транзакции** проверяет неповторяемость TOTP, глобальный лимит живых сессий, отзывает предыдущую session при ротации и создаёт новый зашифрованный CSRF/session record. При превышении лимита одноразовый код не расходуется. Отказ SQLite при выдаче, проверке или отзыве сессии означает отказ действия (`503`), а не возвращение в память процесса. Regression tests охватывают обмен сессией между независимыми экземплярами, общий logout, expiration, corrupted CSRF, роль и удалённого администратора, session cap, атомарную ротацию и конкурентный anti-replay.

**Ограничения:** схема хранится только в отдельной D1b базе и не меняет миграции действующего бота. Не доказаны безопасная синхронизация конфигурации аккаунтов и часы разных серверов, общий storage между разными VPS, устойчивость к нагрузке SQLite и HA, межхостовой rate limit, MFA enrollment/recovery и Fernet key rotation/restore. Реальные HTTPS reverse proxy, закрытый JSON 1:1, устройство/WebView, publish/rollback, Release и deployment не проводились. До независимого CI на конечном head — `PENDING`; PR #896 остаётся Draft, Issue #887 `keep_open`.

### D1b — привязка админ-сессий к учётной записи и управляемый отзыв (2026-10-24, Issue #887)

Каждый новый серверный сеанс получает **`account_binding`** — HMAC-SHA256 от текущего username, PBKDF2 password verifier, TOTP enrollment и роли, со специализированным доменным префиксом и ключом, производным от Fernet master key. В SQLite хранится только keyed fingerprint (не пароль, не verifier, не TOTP-seed, не cookie). При каждом обращении backend сравнивает fingerprint с конфигурацией текущей учётной записи **до продления idle TTL**. Если пароль, seed или роль в загруженной конфигурации изменились либо администратор удалён, старый cookie отклоняется (`401`) и запись отзывается в общей SQLite. Старые pre-binding сеансы мигрируются fail-closed: новая колонка добавляется в транзакции, прежние непроверяемые записи удаляются; повторный запуск сохраняет новые корректные сессии.

Отдельное защищённое действие `POST /admin/subpage/api/sessions/revoke` требует действующего cookie, HTTPS Origin/Host и CSRF. По умолчанию оно отзывает **все** сеансы текущего администратора; владелец `owner` может указать `{"username":"..."}` для отзыва сеансов другого пользователя. `viewer/editor` не могут отзывать чужие сеансы, backend возвращает только количество удалённых записей без каких-либо токенов и секретов. Успешный отзыв собственного аккаунта удаляет cookie; сбой SQLite возвращает `503` и не маскируется под успешный logout. React D1b показывает «Завершить все сеансы»; обычный «Выйти» больше не показывает ложный успех при серверной ошибке.

**Обязательные ограничения:** учётные записи сейчас задаются извне при запуске API. Для двух экземпляров необходимы **одинаковые стабильные PBKDF2 verifiers, TOTP-enrollment, роли и Fernet key**; генерация нового salt для прежнего пароля на каждом запуске намеренно сделает все предыдущие cookie недействительными. При рассогласовании credentials/roles между процессами старый экземпляр может ещё принимать сессию **до** запроса к обновлённому экземпляру или явного owner-revoke: синхронный распределённый credential manager не реализован. In-flight requests нельзя считать ретроспективно остановленными. Настоящие изменения паролей/seed, MFA recovery/enrollment, rotation/Fernet restore, межхостовой rate-limit, HA/TLS/reverse-proxy и operator device smoke относятся к отдельным gates. Здесь нет новых production listeners, публикации/отката и интеграции с ботом.

Проверки до финального GitHub Checks read-back нового head: **PENDING**; не переносить старые PASS. Для security/Issue checkpoint нужны негативные тесты password/MFA/role rotation, удаления пользователя, невалидной session DB migration, собственного и owner-отзыва, CSRF/RBAC, недоступной БД и отсутствие утечки секретов. D1b остаётся Draft PR #896, #887 `keep_open`, Roadmap в `main` фиксирует только ранее слитый D1a.
