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
