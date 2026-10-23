# Subscription Page D1a (isolated preview)

Независимый React 19 + TypeScript + Vite + Mantine frontend. Не подключён к 3x-ui или web admin API, не деплоится. Данные на экране только синтетические.

Локально: `npm install`, `npm run dev`. Перед merge нужны lockfile pin/dependency audit и браузерные проверки. Import JSON — исключительно локальный preview с заблокированными ссылками и действиями; production импорт/валидация и серверные админские endpoints относятся к D1b.

Реальный операторский JSON, SVG и subscriber URLs не входят в репозиторий. Python `subscription_page_config.py` — отдельно тестируемый импорт/валидатор. Взаимодействие с `/compat/` не меняется.

## Порядок интеграции

Stacked Draft PR #889 зависит от документационного PR #888: base ref `docs/887-unified-subscription-miniapp` до разрешённого merge #888. После отдельного merge документации необходимо безопасно перепривязать #889 к `main`, убрать дублирующиеся D0 файлы из diff и снова проверить required CI.

#885 / PR #886 (одноразовый HTTPS handoff) — независимая функциональность. Её не требуется включать в D1a: перед совмещением с web/Mini App обязательны отдельные client/version и Telegram WebView device smoke, replay/expiration/secret-log security checks, отсутствие регрессий `/compat/` и Copy/QR fallback.

D1a является только прототипом: frontend `npm run build`, browser tests и production-import policy PENDING, текущий Python private fixture test в CI без `OPERATOR_SUBPAGE_JSON` ожидаемо SKIP. Без разрешения оператора никакого merge, release или deploy.
