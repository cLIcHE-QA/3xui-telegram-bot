# Subscription Page: D1a preview и D1b draft-editor

**Текущее разграничение на 2026-10-24:** D1a изолированный React 19/TypeScript/Vite/Mantine preview уже находится в `main` (PR #889 и docs-sync #895). Независимый D1b `admin.html` и серверный `subscription_page_admin.py` находятся **только в Draft PR #896** по Issue #887: они не подключены к `app_runtime`/3x-ui, не создают production listener и не опубликованы. Клиентские ссылки и подписи на D1a экране синтетические, действия выключены. Ниже сохранены датированные промежуточные CI checkpoints; их старые PENDING относятся только к указанным SHA, а не к текущему `main`.

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


### D1a — закреплённый исходный SVG INCY

В self-hosted build добавлен **официальный** `client-icons/incy.svg`, источник [INCY-DEV/incy-icons](https://github.com/INCY-DEV/incy-icons/blob/3d6e4a076d54ea036c61b34302ecee01bea30a80/INCY-00002.svg), Git blob `cb6c0417b41d77537d2c5fd90225110ad3e57e43`, лицензия MIT сохранена в `client-icons/INCY-LICENSE.txt` (Git blob `9aa242dfc6cba1f491c5d9b198e2ddceb6011860`). При ключе `INCY` используется локальный значок без CDN, если не предоставлен отдельный безопасный operator SVG.

**Граница:** это **1** подтверждённый файл из 40 кандидатов и **не** byte-identical копия инвентаризованного оператором SVG INCY: у того исходная каноникализация не завершена. Остальные 39 исходных SVG по-прежнему отсутствуют как проверяемые байты; не заменять их другими картинками без evidence. Отдельный SVG-прогресс длинных инструкций и scroll-reveal намеренно **не включены**: текущая карусель короткая, а приёмка keyboard/RTL/reduced-motion важнее декоративного scroll. CI на новом SHA PENDING.

## Независимый visual QA — 2026-10-24, Issue #887 / Draft PR #889

Проверены GitHub Actions browser artifact `d1a-browser-smoke` ID `12556500080` на head `437957dd8c39c2c62652113a2ee672525c854d2c` (80 PNG), desktop/mobile Chromium, WebKit-like, полные карточки/карусель, пустые TV-состояния, RU/FA RTL и экран 320 px с увеличением базового текста до 200%. Предыдущий Playwright 41/41 PASS подтверждает browser-test scope, **не** ручную аттестацию устройства или защищённого source JSON.

По независимой проверке PNG выявлен чрезмерно тесный RTL hero-заголовок при 200% увеличении: отрицательный letter-spacing и `line-height:1.11` не подходят для фарси. Добавлены RTL-specific `letter-spacing:normal;line-height:1.4` и computed-style assertions в существующий a11y smoke для FA на 320/390/768 px.

Исправлен конфликт приоритета SVG: **явно импортированная оператором и локально проверенная** SVG-библиотека теперь перекрывает одноимённый SVG из импортируемого конфигурационного JSON, а не наоборот. Перед чтением SVG JSON проверяется лимит 4 МиБ, ошибки локального JSON File.text() показываются пользователю. Добавлен browser regression test на safe SVG override, отказ от oversized input и отсутствие внешних запросов.

**Границы:** это только D1a preview; отсутствующие INCY/RabbitHole инструкции ожидаются от оператора (PENDING), все импортные ссылки `disabled`. Изолированный визуальный review, CI нового head и независимые screenshot read-back после фикса **PENDING до GitHub Actions**; real Telegram WebView/клиентские устройства, 1:1 закрытый экспорт, D1b/D2/D3 и production acceptance не выполнялись. Merge/release/deploy не разрешены.

### Финальный независимый visual read-back — D1a, 2026-10-24

После исправления на commit `08c18b0e28ee7eff56b7491564b619ca84b642b9` все четыре CI задачи **PASS**: `test` [40084080701](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40084080701), `title` [40084080722](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40084080722), `audit` [40084080718](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40084080718), `frontend-model` [40084080736](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40084080736); Playwright **43/43 PASS**, browser artifact `d1a-browser-smoke` ID `12556775908` (82 PNG). Ручное read-only сравнение до/после подтвердило устранение межстрочного наложения Persian hero при 320 px / 200% text zoom. Детали и ограничения в [датированном audit](../../docs/audits/2026-10-24-887-d1a-visual-rtl-svg-review.md). Обновление README/audit само создаёт новый head, CI на нём подтверждается отдельно. Product acceptance, real WebView/device, original JSON 1:1 и инструкции INCY/RabbitHole остаются **PENDING**; #887 keep_open.

## D1b — отдельный opt-in web-editor, начальный инкремент (#887)

Feature branch, не production. HTML admin.html собирается отдельно от публичного index.html. Серверное приложение create_editor_app в subscription_page_admin.py **не подключено** к основному боту и /compat/, порт самостоятельно не открывает. Чтобы вообще пользоваться сервером, нужны отдельные admin password verifiers, Fernet key, защищённый каталог SQLite и канонический HTTPS origin, предоставляемые оператором вне GitHub. Клиентские данные не пишутся в localStorage и не публикуются в assets.

Admin API: /admin/subpage/api/session, /draft, /history, /proposals; server-only RBAC viewer/editor/owner, CSRF, Secure/HttpOnly/Strict cookie, encrypted immutable revisions, version If-Match. Нет publish endpoint. UI реализует визуальное редактирование, локальный full/selective JSON import/export, просмотр и encrypted draft saves, metadata-only proposals. Все URL/SVG и подписочные placeholders — инертные данные, которым требуется отдельная ручная проверка до реальной публикации. Источник инструкции INCY/RabbitHole ожидается от оператора.

Тесты: Python unittest tests/test_subscription_page_admin.py проверяет отрицательные auth/role/origin/CSRF/rate/SQLite cases; web Playwright tests/admin.spec.ts использует синтетический API mock, npm ci и Vite build; это не настоящий HTTPS/device/admin acceptance. Reviewed code head `71f1a66b02c3631a7deb961deed3722f834a0e11`: [required Python test PASS](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40089603636), [frontend-model PASS, 49/49 Playwright](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40089603671); GitHub Actions artifact 12558925705 (88 PNG) проверен через GitHub read-back и вручную осмотрены реальные desktop/mobile screenshot. Первый пустой loading экран из-за отсутствия MantineProvider исправлен на этом head. Для post-audit docs commit CI должен выполняться отдельно. **Production acceptance по-прежнему PENDING**.

## D1b — операторская SVG-библиотека и обязательная MFA (Issue #887, PR #896)

Визуальное соответствие: защищённый React-редактор использует **тот же `SafeSvgIcon` и `STATIC_SVG_PATHS`, что клиентская D1a**. Для 39 self-hosted SVG из операторского набора и отдельной официальной MIT-иконки INCY используется `preferStatic`: одноимённые SVG-значения импортированного JSON не подменяют проверенный локальный файл. Отрисовываются ключи платформ, все клиенты, шаги и безопасные неактивные кнопки; в раскрываемом каталоге — **40 локальных SVG**. Неизвестный/опасный ключ получает заметный fallback вместо сломанного или исполняемого SVG. `svgLibrary` в JSON остаётся инертными данными; отрисовка через `img` и существующий allowlist sanitizer, без `dangerouslySetInnerHTML` или CDN. В Playwright добавлена проверка `naturalWidth` всех файлов и PNG для desktop + 320px/200% mobile. Это **не** доказательство лицензий/брендового соответствия каждой версии клиента: нужна проверка прав и целевых устройств до release.

Security hardening для отдельно включаемого Python API: **все** `viewer/editor/owner` требуют пароль PBKDF2 и независимый 160+ бит RFC6238/TOTP-секрет (Base32, отдельный у каждого администратора); 6-значный код действителен в ограниченном 30-секундном окне с защитой от повторного использования в рамках процесса. При отсутствии/дублировании MFA-секрета API fail-closed при запуске. Нельзя использовать Telegram ID, subscription URL или клиентскую web-session как администратора. Сессии — Secure/HttpOnly/SameSite Strict cookie, CSRF, Origin+Host, absolute TTL 60–3600 c, idle 300 c, ограничение 64 активных сессий и 5 неудачных попыток входа на remote address за 15 мин; IP из `X-Forwarded-For` не принимается. JSON v1 — только encrypted draft в SQLite, родительская директория 0700, файл 0600, uid текущего процесса, без symlink/hardlink; optimistic `If-Match`, роли на server-side и proposals без реальной публикации. Browser login требует поле «Код подтверждения (MFA)» и не сохраняет секреты.

**Только для будущего изолированного окружения:** администраторы должны быть созданы через отдельный secret manager/операторский key ceremony с разными TOTP-ключами, независимо от паролей и Fernet master key. Генерация секретов и enrollment с проверкой приложения-аутентификатора — вне GitHub, без скриншотов QR, seed, конфигураций пользователя и реальных ссылок в артефактах. **PENDING production gates:** реальный TLS/reverse proxy с host policy и distributed login limits, безопасное MFA recovery/enrollment, shared/persistent sessions/replay lock для multi-instance, Fernet key rotation/backup/restore, независимый security review, полноценный approved publish/rollback, приватный JSON 1:1, Telegram WebView/device smoke, INCY/RabbitHole инструкции от оператора. API сейчас **не подключён к бот-runtime**, PR Draft, merge/release/deployment не производятся. Последний GitHub CI и visual artifact должны подтвердить данный код отдельно; старые 49/49 Playwright относятся к первоначальному head D1b.

### D1b — подтверждение SVG и hardening на точном коде (2026-10-24)

Независимая визуальная ревизия десктопа и 320px/200% мобильного view после подключения исходной SVG-библиотеки обнаружила два дефекта **только в редакторе**: тёмные штрихи некоторых иконок на тёмном фоне и слишком тесное расположение мобильных заголовков/бейджа/описаний переключателей при 200% тексте. Исходные 40 SVG не изменялись: безопасный пассивный `img` теперь имеет двухтонную контрастную подложку; React editor использует `preferStatic` и тот же реестр D1a. Переключатели на мобильном экране переносят длинные подписи под тумблер; длинные заголовки и статусные бейджи переносят строки. Playwright дополнительно проверяет отсутствие горизонтального overflow, CSS reflow и 40 успешных загрузок `naturalWidth > 0`, без внешних запросов.

На проверенном code SHA `bd2af2bcf98d954cf259b58ed3dc26e2d22b32d2` required [`test` PASS](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40093105114), [`title` PASS](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40093105121), [`frontend-model` PASS](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40093105162), **53/53 Playwright PASS**, artifact `d1a-browser-smoke` id `12560011649` (94 PNG) скачан и независимо просмотрен. Это свидетельствует о **scoped offline SVG/React+aiohttp tests**, а не о реальном Telegram WebView, production HTTPS/MFA enrollment или 1:1 операторском экспорте. Новый CSS+docs commit требует повторной CI-проверки; старое evidence не переносится на новый SHA автоматически. Отдельный GitHub Roadmap gate однажды получил ошибку GitHub API, был честно повторён без изменения проверки и затем PASS.

**Остаточные security gates:** TOTP-секреты и Fernet key должны быть созданы/храниться оператором вне репозитория; сессии сейчас только в процессе; TOTP replay-state уже долговременный в общей приватной SQLite D1b, но межхостовая распределённая защита не доказана; эксплуатационный reverse proxy/TLS, distributed rate-limit, MFA recovery/enrollment, key backup/rotation/restore, независимая threat-model/race-аттестация, реальная проверка приватного JSON, publish/rollback и device/WebView ещё **PENDING**. Админ API не связан с runtime, `/compat/` и публичными subscriptions; Draft PR #896 не разрешает merge/release/deploy. Исходные материалы INCY/RabbitHole появятся позднее.

 
## D1b — durable TOTP anti-replay (2026-10-24, Issue #887)

Ветка `feature/887-d1b-protected-drafts`: для обязательного MFA по-прежнему используются отдельные пароли и TOTP-seed у каждого администратора. Сервер не сохраняет введённый OTP или MFA seed в базе: `admin_totp_replay` содержит только `username` и максимальный принятый `last_step`. Вход обновляет счётчик атомарно (`BEGIN IMMEDIATE`), повторный/старый шаг отклоняется и на новом процессе с той же SQLite; ошибка записи блокирует вход с `503`. Тесты проверяют две независимые инстанции, persistent ledger и fail-closed на ошибке базы. Новые tests/CI на этом изменении **PENDING до GitHub read-back** — предшествующие 53/53 Playwright и 1353 Python tests относятся к старому SHA `1577512af3848c29e60afa682d30b6bdce8e7264`.

Не являются подтверждёнными: shared storage между VPS, внешние distributed rate limits, MFA enrollment/recovery, rotation/restore ключей, persistent sessions, независимый security audit и реальная HTTPS-приёмка. В `main` и Published/Deployed версию D1b не переносили; общий #887 остаётся `OPEN/PENDING`. При публикации безопасность реального окружения требует отдельного разрешения.

## D1b — persistent sessions и межэкземплярный logout (2026-10-24, Issue #887)

Продолжение Draft PR #896: login теперь одновременно проверяет отсутствие TOTP replay и создаёт серверную сессию в одной приватной SQLite транзакции (`BEGIN IMMEDIATE`). Если достигнута ёмкость сессий, TOTP не расходуется; успешный повторный вход может атомарно заменить прежнюю сессию по cookie. `admin_sessions` хранит только SHA-256 токена, зашифрованный Fernet CSRF, пользователя и серверные TTL/last-seen; исходные cookie и CSRF в plaintext в SQLite не сохраняются. Восстановленный экземпляр с той же базой/ключом видит действующую сессию, logout из любого экземпляра отзывает её везде, idle TTL проверяется атомарно; corrupted Fernet record fail-closed. При ошибке SQLite вход, проверка и logout возвращают `503` без ложного успеха.

Добавлены offline unit/integration проверки persistent session, cross-instance logout, применения текущей роли, отсутствующего администратора, expired/idle sessions, encrypted CSRF, частично записанных данных, глобальной ёмкости и одновременного TOTP. **Новый точный head CI и ручной HTTPS/device smoke PENDING** до независимой проверки; прежние 1356 Python / 53 Playwright PASS относятся к head `77c39bf2e78b7af5e232bea9f7298d025b3ecc11`, не к этому изменению.

Границы: тесты используют одну общую SQLite, не отдельные VPS. Учётные записи/роли пока загружаются при запуске и должны быть синхронизированы оператором до multi-instance использования. `MAX_LOGIN_BUCKETS` и rate limiting остаются локальными; production edge rate-limit, HTTPS, backup/key-rotation, MFA enrollment/recovery, WebView/device, реальный приватный конфигурационный экспорт, approve/publish/rollback и разделённая поставка сессионной базы **PENDING**. Текущий код не подключён к боту и не даёт разрешения на merge/release/deploy.

## D1b — отзыв после смены пароля/MFA и завершение всех сеансов (2026-10-24, #887)

Дополнение к Draft PR #896: `admin_sessions.account_binding` связывает действующую cookie-session с актуальным **keyed HMAC-SHA256 fingerprint** от username, PBKDF2 verifier, MFA enrollment и RBAC role. Это **не** plaintext verifier, TOTP seed, cookie или ключ шифрования. При изменении учётных данных у экземпляра API предыдущие сеансы больше не продлеваются, отклоняются с `401` и удаляются из общей SQLite. При миграции старой отдельной D1b SQLite-базы ранее выданные сессии без binding отзываются fail-closed; уже действующая схема бота и `/compat/` не меняются. На всех экземплярах необходимо настроить один и тот же **стабильный** credential verifier/MFA/role/key; отдельные неподтверждённые конфигурации создают возможное окно несогласованности.

`POST /admin/subpage/api/sessions/revoke` с обязательными cookie, Origin/Host, `X-CSRF-Token` и JSON `{}` отзывает все сессии текущего администратора. Роль `owner` может передать `{"username":"admin_login"}` для отзыва другого аккаунта. Прочие роли не могут отзывать чужие сессии. Кнопка «Завершить все сеансы» работает только после ответа сервера; одиночная кнопка «Выйти» также **не** скрывает ошибку `503` ложным успехом. Ни одно действие не меняет пароль/MFA/enrollment, не публикует конфигурацию и не перезапускает runtime.

Regression tests: смена verifier, TOTP и роли, отключение пользователя, отбрасывание session с прежней схемой, межэкземплярный logout, явный owner-revoke, CSRF/RBAC, ложный success при SQLite error. Новый head CI **PENDING до независимого GitHub read-back**. Операторское credential provisioning, восстановление MFA, key rotation и восстановление базы, production HTTPS/HA/rate-limits, live WebView и приватный JSON 1:1 остаются отдельными обязательными security gates. D1b API/SPA изолированы от бота, PR #896 Draft, Issue #887 OPEN.

## D1b — offline encrypted admin roster и подтверждаемое MFA recovery (2026-10-24, #887)

**Новый изолированный Python API, не веб-route и не готовый операторский CLI.** `subscription_page_admin_vault.EncryptedAdminRoster` хранит список `AdminAccount` под одним Fernet key в отдельном зашифрованном owner-only файле в заранее подготовленной Linux-директории с правами `0700`. Сам файл и постоянный lock-файл имеют `0600`, не допускаются symlinks/hardlinks. Первый вызов `roster.initialize(accounts)` запрещает повторную перезапись. Файл содержит только ciphertext, запись использует lock, `fsync` и атомарную замену; повторный конкурентный вызов `rotate_password(username,new_password,expected_revision)` со старой revision отклоняется. Должен оставаться минимум один `owner` и уникальные MFA-секреты. В GitHub попадают **только исходники и synthetic tests**; действующие пароли/ключи/TOTP/enrollment не добавлять в коммиты или CI.

В доверенном **offline** Python-процессе оператор заранее создаёт `AdminAccount` (через `password_verifier()`, собственный 160–512-битный TOTP seed для каждого пользователя) и инициализирует roster. Затем `create_editor_app(accounts_loader=roster.load_accounts, db_path=..., encryption_key=..., https_origin="https://...")` считывает текущий roster при каждом login и авторизованном запросе. Операторское создание listener/ingress по-прежнему отсутствует. Нельзя передавать одновременно `accounts` и `accounts_loader`; сбой чтения/расшифровки файла при работающем API → `503` без fallback на старые credentials. После password/MFA rotation старые cookie отклоняются (`401`) и удаляются из общей D1b SQLite, если весь пилот использует один общий файл, БД и key.

Для **контролируемого offline MFA recovery уже существующего аккаунта** использовать `pending = roster.prepare_mfa_recovery(username)`, передать `pending.secret_b32` доверенному оператору только по защищённому приватному каналу, зарегистрировать в его authenticator и получить текущий 6-значный код. Только после этого выполнить `roster.confirm_mfa_recovery(pending, otp, new_password=...)`. Без подтверждения или при устаревшей revision roster не изменяется. Нельзя печатать seed, key, recovery artifacts, OTP, verifier и stdout/login screenshots в репозиторий или тикеты. Семантика списка не содержит recovery-token в БД или HTTP; отдельная авторизация оператора, журнал/offline custody, защищённая доставка и key backup — **PENDING**. При смене seed старый TOTP anti-replay шаг остаётся зафиксированным, поэтому первая новая авторизация может потребовать новый 30-секундный шаг; откат защиты от replay запрещён.

**Security limits:** это библиотека для private Linux оператора, без готовых интерфейса администратора, подтверждения личности и восстановления потерянного Fernet key. Независимые VPS без общей файловой/SQLite consistency не синхронизируют rotation. Операторская парольная политика, enrollment/recovery evidence, backup/restore/Fernet key rotation, TLS reverse proxy, HA/rate limits, real-device/Telegram WebView smoke, закрытый JSON 1:1, live publish/rollback и acceptance остаются отдельными gates. Схема `bot.sqlite3`, `app_runtime`, `/compat/` и release/deployment не меняются, PR #896 остаётся Draft.

## D1b — изолированный sealed backup и Fernet key rotation (2026-10-24, #887)

`subscription_page_admin_recovery.py` содержит **только offline Python API**, не recovery route или deployment tool. `OfflineD1bRecovery(private_source_dir, encryption_key)` проверяет исходный encrypted roster и `drafts.sqlite3` под старым ключом, валидирует `PRAGMA quick_check` и digest каждой ревизии. Работает только после остановки **всех** D1b writers/экземпляров по отдельному разрешённому операторскому runbook, так как два файла **не** представляют одну атомарную DB-транзакцию. Действующие `app_runtime`, `/compat/`, `bot.sqlite3`, production listeners и опубликованный релиз не затрагиваются.

- `backup(backup_path, backup_key)` создаёт owner-only `0600` Fernet-sealed ciphertext с полным snapshot и зашифрованным **старым** primary key **внутри** конверта, но только под **независимым** backup key. Он не перезаписывает существующий backup, повторно decrypt/verify содержимое до публикации и не создаёт plaintext dump. Архив и backup key должны храниться раздельно вне GitHub.
- `restore(backup_path, backup_key, new_dir)` восстанавливает старый комплект в **новый** каталог с отзывом старых cookie, когда старый primary key доступен. `OfflineD1bRecovery.recover_lost_key(backup_path, backup_key, new_dir, new_key)` восстанавливает escrowed primary key только в памяти и сразу создаёт новый комплект под **новым** Fernet key без необходимости старой директории/старого ключа. Если backup key и основной ключ оба утрачены, recovery невозможен.
- `stage_rotation(new_dir, new_key, backup_path=sealed_backup_path, backup_key=backup_key)` при известном старом ключе перепаковывает **все** зашифрованные draft revisions + roster, сохраняет `admin_totp_replay`, историю/предложения и намеренно отзывает действующие admin sessions. Исходные файлы не переписывает. Сначала создать отдельный, проверенный sealed backup под другим ключом; только затем stage rotation. Новые каталоги `0700`, файлы `0600`, rollback/activation в этом API отсутствуют.

`stage_rotation` не запускается без независимого *проверенного и актуального* escrow: отсутствие `backup_path`, неверный `backup_key`, изменение SQLite/roster после резервного копирования или несовпадающий old key блокируют stage. Нужен действительно замороженный operator snapshot.

Точные схемы и порядок проверки перед возможным live cutover приведены в [каноническом D1b design contract](../../docs/WEB_SUBSCRIPTION_MINI_APP.md#d1b--sealed-backup-offline-recovery-и-ротация-fernet-2026-10-24-issue-887). Оригинальные credential seed/ключи, enrolment и реальные customer URL **не** должны появляться в PR/CI/screenshots. Текущее proof — synthetic offline tests; настоящая recovery rehearsal на другом узле, operator custody, backup retention, HA/HTTPS и rollout **PENDING**. Даже успешный CI не даёт разрешение на Merge/Release/Deployment.

## D1b — репетиция восстановления в изолированном процессе и HTTPS edge (2026-10-24, #887)

**Новый synthetic offline CI smoke, не запуск production:** `python -m unittest discover -s tests -p 'test_d1b_recovery_drill.py' -v` создаёт только ephemeral encrypted roster, черновик, предложение и TOTP ledger. После запечатывания архива исходная директория убирается, а новый Python `-I` процесс `tests/d1b_recovery_worker.py` получает только пути и backup/new ключи через stdin (не argv, не environment и не stdout); **старый primary key отсутствует**. Отдельный процесс `recover_lost_key` заново создаёт 0700/0600 комплект, проверяет историю, proposal, anti-replay и удаление старых сессий; делает synthetic login с новым ключом через `aiohttp.TestServer` и проверяет strict Host/Origin, Secure cookie и spoofed `X-Forwarded-*`. Wrong key, испорченный архив и повторное восстановление fail-closed без раскрытия ключей. Это НЕ испытание независимого VPS, TLS handshakes и реальных операторских учётных данных.

**Пример reverse proxy (не установлен):** `deploy/subpage-admin/nginx-d1b-admin.conf.example`. До ручного approved deployment его домен `admin.example.invalid`, пути сертификатов, Vite `dist/` и upstream `127.0.0.1:8817` намеренно не привязаны к живому сервису. Шаблон надо подключать внутри Nginx `http {}` только после одобрения отдельного admin-origin: TLS 1.2/1.3, Host+SNI reject, no-store/CSP/HSTS canary, login и API IP rate-limit, отключённый credential route access-log, `admin.html`/`assets`, остальные URL закрыты. Backend ни при каких условиях не слушает `0.0.0.0`; **Origin не подменять прокси-сервером**, backend сравнивает фактический Origin и Host сам. `tests/test_d1b_https_edge_contract.py` проверяет шаблон и, если `nginx` и `openssl` доступны локально, запускает `nginx -t` на одноразовом синтетическом сертификате без сетевого listener.

**Условия будущего VPS canary:** завершённый security review, отдельный проверенный backup+escrow, остановка всех D1b writers, независимое clean-host restore, утверждённые политики сертификатов/ключей/HSTS и проверки реального 443->loopback ingress/429/CSRF, операторская custody и rollback. GitHub Actions подтверждает лишь isolated synthetic code scope; `main`, Published, Deployed и full Acceptance не изменяются. Доступ к real data и publish/rollback не предоставляется.

## D1b — статические SVG через изолированный HTTPS ingress (2026-10-24, #887)

`SafeSvgIcon` запрашивает 39 локальных `/client-icons/library/[A-Za-z0-9_-]+.svg` и точный `/client-icons/incy.svg`. Изначальный HTTPS Nginx preview разрешал лишь `admin.html` и Vite `/assets/`, поэтому при будущем включении иконки отвечали бы `404`. В неактивном `deploy/subpage-admin/nginx-d1b-admin.conf.example` теперь разрешены только эти пути, **не весь** `/client-icons/`; текст лицензии и альтернативные SVG остаются запрещены. Проверка `tests/test_d1b_https_edge_contract.py` включает 40 реальных файлов, узкие маршруты и отрицательные пути, не отключая synthetic `nginx -t`.

Это только изолированная ветка Draft PR #896. Реальная HTTPS-конфигурация, выдача SVG с целевого VPS, TLS/HA, operator credentials, клиентские устройства, acceptance и production deployment остаются PENDING.

## D1b — HTTP/HTTPS smoke на локальном Nginx, не в production (2026-10-24, #887)

`tests/test_d1b_https_edge_runtime.py` дополняет статические проверки `nginx -t` полноценными **синтетическими TLS+HTTP** запросами к временному Nginx на `127.0.0.1:ephemeral` и mock Python API на другом loopback-порту. Никакого deploy, работающего production admin API, чужих ключей, подписок или телеметрии.

Проверяются 40 утверждённых локальных SVG в синтетическом `dist` и заголовки `no-store`/CSP/nosniff, недоступность `/compat/`, `index.html`, текстовой лицензии и альтернативных assets, отказ неправильным Host/SNI и отсутствие SNI, проброс браузерного `Origin`, замена client-controlled `X-Forwarded-*`, ограничение `POST /session` с `429`. Ресурсы SVG искусственные, имена получены из `staticSvgPaths.ts`; права пользователей и CSRF проверяются в отдельных API unit tests. Код `nginx-d1b-admin.conf.example` не устанавливает сервер и не открывает production-порт.

Запуск: `python -m unittest discover -s tests -p 'test_d1b_https_edge_runtime.py' -v`. Для реального теста требуются `nginx` и `openssl`, иначе явный skip, не доказанный PASS. Безопасность настоящего origin, доверенная TLS chain, сертификаты/renewal, nginx-default-host/failover, удалённая сеть, операторские секреты и clean-host DR по-прежнему PENDING.

## D1b — настоящий auth/CSRF/RBAC через синтетический HTTPS (2026-10-24, #887)

`tests/test_d1b_https_real_admin_api.py` запускает реальный `subscription_page_admin.create_editor_app` за **локальным** Nginx с synthetic TLS и owner-only SQLite. Он не использует mock API: тестовые логины `owner/editor/viewer`, MFA/TOTP, cookie, PBKDF2, Fernet и optimistic If-Match работают как в отдельном D1b backend, но без реальных операторских учётных данных, сети/VPS, клиентских URL или publish endpoint.

Негативные сценарии: guest/Bearer не дают админских прав; чужой или отсутствующий Origin и клиентские `X-Forwarded-*` не обходят проверку; отсутствие MFA и повтор кода — отказ; роли `viewer/editor/owner` разделены; отсутствие/неверный CSRF, `428` без If-Match, `409` при stale rev; отзыв cookies и персональный logout; `/publish`, `/rollback`, `/compat/` недоступны; CORS preflight не раскрывает данные. Позитивный путь допускает только сохранение **зашифрованного черновика** и metadata-only предложение, не публикацию.

Запуск: `python -m unittest discover -s tests -p 'test_d1b_https_real_admin_api.py' -v`. Nginx/OpenSSL required для настоящего test: при отсутствии SKIP не означает PASS. Исключения self-signed TLS допустимы только в ephemeral synthetic fixture. Реальный TLS-сертификат, общий security review, операционная custody, off-host DR, WebView/device acceptance и Deployed по-прежнему **PENDING**.

## D1b — fail-closed разграничение login IP на доверенном loopback Nginx (2026-10-24, #887)

Прежде `request.remote` за Nginx на `127.0.0.1` объединял неуспешные логины разных внешних клиентов в **один backend bucket**. Для проверенного отдельного admin ingress реализован **явный opt-in** `create_editor_app(..., trusted_loopback_proxy=True)`: включать его можно **только** если trusted TCP peer — точно `127.0.0.1`, backend доступен исключительно на loopback, а Nginx перезаписывает `X-Forwarded-For $remote_addr`, `X-Forwarded-Host admin.example.invalid`, `X-Forwarded-Proto https`. Backend отвергает отсутствующие, составные, некорректные или неподтверждённые forwarded-заголовки и доверяет одному canonical IPv4/IPv6 только через такую границу. **По умолчанию опция выключена**, браузерные `X-Forwarded-*` не доверяются. Новые CDN/LB/multi-host варианты потребуют нового security design, не автоматического trust.

Исправлено освобождение `MAX_LOGIN_BUCKETS` от устаревших отказов: насыщение активными buckets по-прежнему fail-closed `429`, чужой клиент больше не делит backend-блокировку с предыдущим источником за утверждённым proxy. Тесты в `tests/test_subscription_page_admin.py` и `tests/test_d1b_https_real_admin_api.py` проверяют default distrust, malformed headers, trusted peer, IPv4/IPv6, два loopback source IP, клиентский spoof и сохранённые MFA/CSRF/RBAC. Это **только Draft CI**, а не совет включать D1b в production; действующий `docs/ADMIN_SETUP.md` не изменён, нужен будущий отдельный operator security/installation approval.

## D1b — URL review не разрешает ссылки по одному маркеру (2026-10-24, #887)

`blockedLinks()` раньше принимал любой `link.includes("{{SUBSCRIPTION_LINK}}")`, включая `javascript:` с таким текстом. В новом preview это не XSS (actions disabled), но отчёт ручного review мог скрывать подозрительный URL. Теперь синтаксически безопасная форма-кандидат — только полный `https://` без login/password/placeholder/backslash/пробелов; остальные схемы, empty и шаблонные ссылки отмечаются к ручной проверке. Даже `https://`-кандидат **не** разрешён к исполнению: host allowlist, клиентские deep links и публикация отсутствуют. Новый Playwright regression проверяет, что 5 подозрительных из 6 links отмечены, все действия остаются disabled и нет внешних запросов.
