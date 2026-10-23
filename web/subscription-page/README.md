# Subscription Page D1a (isolated preview)

Независимый React 19 + TypeScript + Vite + Mantine frontend. Не подключён к 3x-ui или web admin API, не деплоится. Данные на экране только синтетические.

Локально после фиксации lockfile: `npm ci`, `npm run dev`, `npm run build`, `npm run test:model`, `npm run test:browser`. До подтверждения нового SHA в CI это план проверки, не PASS. Import JSON — исключительно локальный preview с заблокированными ссылками и действиями; production импорт/валидация и серверные админские endpoints относятся к D1b.

Реальный операторский JSON, SVG и subscriber URLs не входят в репозиторий. Python `subscription_page_config.py` — отдельно тестируемый импорт/валидатор. Взаимодействие с `/compat/` не меняется.

## Порядок интеграции

Stacked Draft PR #889 зависит от документационного PR #888: base ref `docs/887-unified-subscription-miniapp` до разрешённого merge #888. После отдельного merge документации необходимо безопасно перепривязать #889 к `main`, убрать дублирующиеся D0 файлы из diff и снова проверить required CI.

#885 / PR #886 (одноразовый HTTPS handoff) — независимая функциональность. Её не требуется включать в D1a: перед совмещением с web/Mini App обязательны отдельные client/version и Telegram WebView device smoke, replay/expiration/secret-log security checks, отсутствие регрессий `/compat/` и Copy/QR fallback.

D1a является только прототипом: frontend `npm run build`, browser tests и production-import policy PENDING, текущий Python private fixture test в CI без `OPERATOR_SUBPAGE_JSON` ожидаемо SKIP. Без разрешения оператора никакого merge, release или deploy.

## D1a проверка источника — 2026-10-23

- Локальный оригинальный экспорт (SHA-256 `acc2a517287832fcf7e42d7482eceea55bdc2b6b670a6e5b3bab23680f323244`) успешно прошёл Python `parse_config→serialize_config→parse_config` с полным равенством объекта.
- Независимый TypeScript `parsePageConfig` проверен на тех же 5 locales, 7 platforms, 24 app slots, 10 client names, 92 instruction blocks, 75 buttons, 38 original SVG; реальные strings и URL не логируются и не публикуются. Node unit tests в GitHub: `.github/workflows/subscription-page-d1a.yml`.
- UI в PR остаётся **preview**: отображаются четыре вида инструкций (`cards`, `timeline`, `accordion`, `minimal`) и четыре вида блока подписки (`expanded`, `collapsed`, `cards`, `hidden`). Содержимое подписки синтетическое, ссылки и операции заблокированы. Реальные действия `external/subscriptionLink`, raw keys, admin publish не разрешены. Обязательные следующие gates: TypeScript/Vite `npm run build`, browser visual/a11y/RTL smoke, пакетный lockfile/dependency review. **Не называть это D1a acceptance** до этих проверок.
- CI исходного приватного экспорта не содержит; для полной проверки оператор запускает локальный `OPERATOR_SUBPAGE_JSON=/secure/path/file.json python -m unittest discover -s tests -p 'test_subscription_page_config.py' -v`.

## Автоматизированный browser smoke (D1a)

`tests/browser.spec.ts` проверяет четыре варианта блока подписки и инструкций, disabled Get Link,
отсутствие внешних запросов, RTL `fa`, клавиатуру, reduced-motion и горизонтальное переполнение
на desktop/mobile Chromium. Применяются только фиктивные данные, никаких реальных
подписок или внешних URI. Выполнение на новом SHA и визуальный screenshot-review
не доказаны до запуска соответствующего CI и проверки артефактов.

`package-lock.json` ещё не зафиксирован: до его получения нельзя утверждать, что
установка воспроизводима или что `npm ci` прошёл. D1b auth и device smoke — отдельно.


## Проверки CI — 2026-10-23

На head `9be0aa9b617a98572b759c34acc2917d8d8fd8a7` GitHub Actions
[Subscription Page D1a checks](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40013712158):
`frontend-model` **PASS**, `npm ci`, модель/TypeScript/Vite **PASS**,
Playwright desktop/mobile Chromium **4/4 PASS**. Required `test` и `title`
также **PASS** на том SHA; общий `audit` **FAIL** по runtime Python-зависимостям
(Pillow/certifi, #890 — отдельная remediation).

CI сформировал lockfile v3 (145 записей, SHA-256
`3ab98b620697640c095f0eb439bad725edda35e1e648072e213394937560fef6`),
артефакт `d1a-npm-lock`. Этот файл **ещё не в Git**:
первичная проверка bootstrap/CI не равна воспроизводимости из committed lockfile;
до его commit временная генерация сохраняется, gate D1a — **PENDING**.

Первый успешный Playwright run не загрузил screenshot artifact:
`test-results/` был пуст (`screenshot: only-on-failure`). В следующем
commit Playwright `screenshot: on` сохраняет скриншоты успешных сценариев
в `test-results/` для существующего `upload-artifact`. Проверка
артефакта именно на новом SHA и визуальный human review **PENDING**.

WebView/реальные подписки, права на SVG и runtime/production acceptance
этим offline PASS не подтверждаются. Issues #887 и #890 остаются OPEN.

## Фирменный дизайн D1a — 2026-10-23

Основа визуальной системы — **переданный оператором знак синего енота с инструментом**.
Для browser preview создан собственный локальный векторный контур
`public/brand/raccoon-wrench.svg` на основе предоставленного изображения (не чужой
Remnawave/RightSide asset). Исходное JPEG-изображение не публикуется в репозитории;
векторная версия повторяет его композицию и цвет `#18A5F9` без внешних запросов.
Операторские права использования собственного логотипа подтверждены выбором для страницы;
отдельные сторонние VPN-клиентские логотипы остаются вне runtime до проверки прав.

Новые блоки: брендированный header и hero, карточка статуса и метрик, компактная и
карточная версии подписки, сетка платформ, отдельный выбор приложения,
четыре режима инструкции, локальный JSON-import и безопасное уведомление о preview.
Демонстрационный status остаётся `Нет данных`, трафик/срок — `—`, не имитируем
активную подписку. `Get Link` и ссылки/кнопки из JSON — `disabled`.
Русский, английский и фарси получили основные оригинальные тексты; остальные локали
отображаются через явный английский fallback до полной локализации. RTL получает
атрибут `dir=rtl`; требуется screenshot-review desktop/mobile, keyboard/a11y и
подтверждение всех семи платформ на полной synthetic fixture.

Scope: #887 D1a UI polish в существующем PR #889, отдельный Issue не создаём
(не самостоятельная функция, а согласованная визуальная реализация acceptance #887).
Проверка после нового commit — CI `test/title/frontend-model`, Chromium visual,
а `audit` Pillow/certifi в отдельном #890. `package-lock.json` в Git и строгий
`npm ci` без bootstrap по-прежнему PENDING.

## Фирменный D1a — состояния и локализация, 2026-10-23

Повторный визуальный пакет #887 / PR #889: компонент `src/SubscriptionPreview.tsx` содержит четыре
**исключительно синтетических** сценария `unknown/active/expired/pending` для визуальной проверки
режимов `expanded/collapsed/cards/hidden`. Пример активной подписки показывает лишь фиктивные
24.6/100 GB и 15 дней с явной пометкой `ДЕМО`, не имитирует backend session или entitlement.
`Get Link`, connection keys и импортирующие действия **не активируются** при переключении.
Новые сценарии не являются production states, не хранят и не создают ключи.

В интерфейсе добавлены локализованные подписи, в том числе для `fr/zh` (пять языков
`en/ru/fr/zh/fa`), направление документа `dir=rtl` только для `fa`.
Вендорские SVG не используются до license/security проверки; статус клиента
не следует интерпретировать как проверенную поддержку версии или импорт в устройство.

Дополнены Playwright проверки сценариев, языков и keyboard/RTL. **CI и visual read-back
на последнем commit PENDING до проверки GitHub Actions**, предыдущие PASS на иных SHA не переносить.
`package-lock.json` пока не закоммичен; `audit` Python/Pillow/certifi — отдельный #890.
#887 keep_open: полный D1a acceptance и D1b/D2/D3 отсутствуют; Roadmap в `main` SYNC PENDING.

## D1a — приложение, изображения и npm lock (2026-10-23)

В #887 / draft PR #889 добавлен `ClientChooser` с отдельными нейтральными пиктограммами
для категорий приложений, явным `aria-pressed`, улучшенной мобильной сеткой и состоянием
отсутствия приложений. Название клиента берётся из валидированной локальной конфигурации;
официальные иконки VPN-клиентов **не импортируются без** asset provenance, license и
trademark review. Иконки — декоративные generic Tabler, а не доказательство реальной
поддержки клиента, устройства или протокола. Кнопки установки и импорта, содержащие
ссылки из JSON, остаются disabled.

Настоящий `package-lock.json` зафиксирован в GitHub из проверенного CI-артефакта
(`lockfileVersion=3`, 145 записей, SHA-256 исходных байтов
`3ab98b620697640c095f0eb439bad725edda35e1e648072e213394937560fef6`).
CI теперь вызывает **только** `npm ci --ignore-scripts --no-audit --no-fund`, без
генерации lockfile. Повторный frontend build и browser smoke на новом commit
**PENDING**, пока они не завершены в GitHub Actions.

Security `audit` Python-зависимостей Pillow/certifi — отдельный #890,
не подавляется и не считается PASS. #887 keep_open (D1a продолжается,
D1b/D2/D3 остаются), Roadmap в `main` SYNC PENDING. Merge/Release/deployment
не выполняются.

## D1a — визуальный мастер подключения и полноэкранный smoke (2026-10-23)

После **подтверждённого PASS 8/8** на SHA `9e53586a5b2b01bdf2b48ee8b347ed5db7ebe303`
([Actions 40021764054](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40021764054))
реализован отдельный `ConnectionGuide.tsx`. Режимы `cards/timeline/accordion/minimal`
получили индивидуальную композицию, явную нумерацию шагов, состояние «нет инструкций»
и нейтральные иконки Tabler. Все кнопки, содержащие реальные JSON URLs, **disabled**;
никакого открытия URI, копирования bearer-токена или обращения к внешнему CDN нет.

Для визуальной проверки добавлены `fullPage: true` attachments для всех 4 режимов,
пустого Android и четырёх синтетических состояний подписки, отдельно desktop/mobile.
Это дополнение к 8 предыдущим smoke-тестам, не свидетельство реальных клиентских
подключений или WebView/Telegram Mini App. Предыдущий артефакт
`d1a-browser-smoke` (ID `12531265902`) содержал лишь 8 **viewport** PNG:
они проверены, но не позволяют видеть нижнюю часть страницы. На новом SHA
**build / smoke / screenshots PENDING** до фактического CI и read-back.

#887 `keep_open`; #890 security `audit` (Pillow/certifi) `keep_open`.
`package-lock.json` в Git, строгий `npm ci` PASS на SHA `9e53586a`.
Roadmap в `main` — SYNC PENDING, D1a PARTIAL/PENDING, merge/release/deploy не выполняются.

**Уточнение visual gate:** CI на SHA `038b41618fc107a2d3bb3a826b205e2782a2da35` —
`frontend-model` 12/12 Playwright PASS, build/`npm ci` PASS; однако артефакт
`12532126063` содержит только **12 viewport screenshots** (desktop 1280×900,
mobile 390×844), не full-page evidence: `testInfo.attach()` не сохранил
дополнительные PNG в `test-results/`. Это **FAIL visual-evidence gate**,
несмотря на зелёный browser run. Исправление переводит screenshot на
`page.screenshot({path:testInfo.outputPath(...),fullPage:true})`, чтобы Actions
действительно загрузил полноэкранные PNG. Потребуется read-back размеров и review
архива **на новом SHA**. Общий security audit FAIL (#890), D1a PARTIAL/PENDING.

## D1a — mobile touch targets и мультиязычность (2026-10-23, UTC+03:00)

После полного visual-evidence PASS на SHA `f4bc291f15ad937642297e31cef0193adcae2f18`
в #887 / PR #889 проведена точечная доработка мобильных переключателей.
Вместо `SegmentedControl` (ранее до 9 px при ширине ≤450 px) используется
собственный `PreviewModePicker` на нативных `button` с `aria-pressed`,
читаемой подписью, видимым `:focus-visible`, не менее 44 px по высоте;
при ширине ≤700 px — сетка 2×2 с 48 px и шрифтом 14 px. Режимы подписки,
статусы и виды инструкций локализованы для `ru/en/fr/zh/fa`.

Playwright покрывает viewport 320, 390, 430, 768, 1024 px,
проверку минимумов touch target и шрифта, горизонтального переполнения,
RTL и keyboard Enter/Space. Это browser-smoke/visual-fixture scope,
не реальная приёмка Telegram WebView или мобильных устройств.
**Итоговый CI и screenshot read-back на новом SHA — PENDING до результатов GitHub Actions**.
Общий Python `audit` FAIL по #890 отдельно; #887 `keep_open`, Roadmap `main`
SYNC PENDING, merge/release/deploy не выполняются.

## Увеличение текста и WebKit-like smoke — 2026-10-23

Продолжение D1a (#887, Draft PR #889): выбранный оператором фирменный desktop
shell сохранён; повышаем удобство без подключения новых backend-интерфейсов.
Ключевые тексты hero, карточек, инструкций, навигации и переключателей переведены
на `rem`, чтобы реагировать на увеличение базового браузерного шрифта
до 200%. Контролируем перенос длинных строк и горизонтальное переполнение
на 320/390/768 px (RU и RTL FA). Фон и текстовую палитру не подменяем.
Контраст основных элементов проверяется на известных тёмных поверхностях
по отношению WCAG 4.5:1; это **целевые образцы**, не полный аудит WCAG.

В HTML добавлен `viewport-fit=cover` и безопасные отступы через
`env(safe-area-inset-*)`. В CI к desktop/mobile Chromium добавлен
`ios-webkit-simulated` (Playwright WebKit, `iPhone 13`) только для
теста совместимости WebView-like оболочки, навигации, RTL и ограниченного
сетевого поведения. Это **не запуск в Telegram** и не доказательство
интеграции Telegram SDK или `initData`; D2 auth/WebView device smoke
по-прежнему PENDING. Адаптивный/контрастный тест также генерирует
скриншот при 200% шрифта. Не выполняется выдача ключей или вызов внешних URI.

Обязательны новый frontend CI, скриншоты и независимый GitHub read-back.
Общий Python security audit (#890) остаётся отдельным FAIL, Issue #887
остаётся OPEN, Roadmap в `main` SYNC PENDING. Merge, release,
deployment и принятие реальных подписок не выполняются.

## Компактные шаги и единая рамка платформ — D1a (#887)

На демонстрационной странице добавлен UI-only режим `carousel`: один видимый шаг, переходы «Назад»/«Далее», выбор шага и доступное управление с клавиатуры. Смена платформы/клиента сбрасывает шаг. Прежние четыре значения конфигурационного JSON v1 (`cards/timeline/accordion/minimal`) **сохранены без изменения схемы**: импорт устанавливает исходный выбранный режим, карусель не записывается в JSON.

Вкладки платформ объединены в одну мягкую рамку: отдельные контуры и нижняя разделительная линия убраны. На узких экранах прокрутка происходит внутри списка платформ. Подписки и действия остаются синтетическими и disabled; никакие реальные URL и ключи не открываются. Проверка CI на новом SHA — PENDING, production WebView отдельно.

## D1a — смысловая палитра и четыре показателя подписки

Для Demo Preview добавлены самостоятельные компоненты-индикаторы: тариф (синий), статус (зелёный при active, янтарный при pending, нейтральный при unknown, красный при expired), трафик (янтарный) и окончание (розовый/красный). Строка сброса трафика выводит «Нет данных» до появления достоверного source. Вымышленные 24.6/100 GB и 15 дней явно помечены «ДЕМО»; тариф не придумывается. `expanded` — сетка 2×2, `cards` — четыре плитки, `collapsed` и `hidden` сохранены. Переключение сценариев не вызывает backend или выдачу URL.

Палитра создана независимо для фирменного Raccoon VPN. Публичные `theme.ts` и `global.css` Remnawave использованы лишь как ориентир семантики цветов; код/CSS/ассеты AGPL не переносились. Реальные plan/expiry/reset/traffic требуют owner-scoped customer DTO и проверок на D2; Issue #497 остаётся самостоятельным server-side scope. CI и screenshot-review на новом SHA PENDING.

## D1a — интерактивные эффекты (2026-10-23)

По видеореференсу оператора добавлены оригинальные фирменные UI-эффекты: очень мягкий подъём карточек и кнопок при hover (2–3 px, 180 ms), контур/тень без изменения размеров блоков и неспешный перелив голубого–сиреневого в акцентной строке hero (8 s). Нет внешних assets, обращения к сервисам, зависимостей JS или изменения JSON v1. Подвижные эффекты работают только при `hover:hover`/`pointer:fine` и `prefers-reduced-motion:no-preference`; на touch-устройствах и при reduced motion текст остаётся статичным. Активные/disabled действия и видимый клавиатурный фокус сохраняются. Добавлен browser smoke hover + reduced-motion, CI на новом SHA требует проверки.

## D1a — исправление 200% текстового переполнения

Диагностика GitHub Actions на 320 px при русском языке/200% текста зафиксировала `rootScroll=437` против viewport 320. Главные источники: нижние `safe-panel`/`import-panel` с intrinsic flex min-size и карточка клиента. Добавлены `min-width:0`, гибкий перенос, адаптивные flex/grid tracks, `overflow-wrap:anywhere`; body/root не обрезаются через `overflow-x:hidden`. Hover/motion остаются отдельным эффектом и отключаются при reduced motion. После исправления браузерный регрессионный тест на новом SHA требует подтверждения, не объявлять PASS до GitHub Actions. #887 OPEN, #890 audit отдельно.

## Фоновое ambient-свечение — D1a #887

В фирменном тёмном shell добавлены две малоконтрастные CSS-only радиальные засветки по верхним углам: холодная голубая и приглушённая сине-сиреневая. Центральная область остаётся тёмной. Слой не перехватывает действия (`pointer-events:none`), расположен под интерфейсом и не создаёт внешних ресурсов. Медленное изменение прозрачности (26 секунд) отключается при `prefers-reduced-motion: reduce`; на mobile уменьшается интенсивность. Playwright проверяет поведение, горизонтальное переполнение и desktop/mobile PNG. CI нового SHA требуется подтвердить.


## D1a — локальная SVG-библиотека и решения по анимациям

Оператор подтвердил разрешение использовать ранее предоставленные SVG. Поскольку в GitHub сохранён только inventory ключей, но не исходные байты SVG, страница позволяет **локально** импортировать операторскую `svgLibrary` из JSON и использовать её для картинок приложения, ОС и шагов инструкции. При импорте выполняется SVG allowlist sanitizer: отклоняются scripts, foreignObject, внешние URL и опасные атрибуты, отображение только в `img` с локальным data URI. Отсутствующий или отвергнутый SVG заменяется нейтральной пиктограммой. Никакие private JSON, URL/ключи или данные оператора не выгружаются на сервер. Runtime self-hosted библиотека всех исходных SVG — PENDING до предоставления исходных байтов и независимого security read-back.

`Scroll-Driven Animations`: для короткой страницы D1a не вводить. В будущем возможна необязательная подсветка progress длинных инструкций при `@supports` + `prefers-reduced-motion`, без зависимости навигации от scroll. Основная карусель — explicit clicks, всегда доступная.
