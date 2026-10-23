# Subscription Page D1a (isolated preview)

Независимый React 19 + TypeScript + Vite + Mantine frontend. Не подключён к 3x-ui или web admin API, не деплоится. Данные на экране только синтетические.

Локально: `npm install`, `npm run dev`. Перед merge нужны lockfile pin/dependency audit и браузерные проверки. Import JSON — исключительно локальный preview с заблокированными ссылками и действиями; production импорт/валидация и серверные админские endpoints относятся к D1b.

Реальный операторский JSON, SVG и subscriber URLs не входят в репозиторий. Python `subscription_page_config.py` — отдельно тестируемый импорт/валидатор. Взаимодействие с `/compat/` не меняется.
