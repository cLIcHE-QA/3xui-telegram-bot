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
