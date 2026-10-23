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

## Отдельный внешний проект

[legiz-ru/Prizrak-Box](https://github.com/legiz-ru/Prizrak-Box), ветка `v3`, — Electron/Vue/Mihomo desktop-клиент под GPL-3.0, **не** готовый Mini App или публичный subscription portal. Документированный `prizrak-box://install-config?url=...` — возможная интеграция на Windows/macOS/Linux только после независимого smoke; не копировать GPL code/assets в бот без отдельной оценки license/dependencies/attribution. #702 (page-mascot) остаётся независимым необязательным расширением после собственной страницы.

## Поэтапная реализация

| Этап | Scope | Завершение |
| --- | --- | --- |
| D0 | Issue #887, архитектурное решение, Roadmap и required CI | Только docs PR merged/read-back, не runtime |
| D1 | Собственный responsive UI shell и read-only summary, шаги подключения, доступность | UI/a11y/visual/compat regression |
| D2 | Mini App и standalone authentication/session API | initData signature/freshness, negative IDOR/CSRF, rate/pilot gates |
| D3 | Контролируемый canary, per-client device smoke, provider-neutral traffic/HWID | Отдельные merge/release/deploy и targeted acceptance |

Декомпозиция D1–D3 требует самостоятельных implementation PR и тестов; D0 не означает разрешения deploy. Данные пользователя не маскировать моками в production. Новую веб-плоскость включать только через явный feature flag. Точный web stack, дизайн-система, hostname и session storage утверждаются в implementation preflight с проверкой threat model. Архитектурное решение D0 не подразумевает самовольной регистрации Telegram Menu Button, новых API публичного кабинета или создания web-session из bearer subscription URL.

## Acceptance и rollback

Для реализации требуются мобильный и desktop a11y smoke, owner/pilot/feature gates, multi-account isolation, чужой/просроченный `initData`, отсутствие утечек bearer в URL/логи/CDN/referrer, сохранение `/compat/` и QR/Copy fallback, честные ошибки и device import/refresh. Offline CI не заменяет устройство/VPS acceptance.

Пока D0 не merged, **Roadmap sync: PENDING**. После D0 acceptance: `#887 keep_open` до D1–D3 и отдельной реальной приёмки; merge документации не закрывает feature. При сбое новой web-плоскости она отключается feature flag, старые bot/compat endpoints остаются рабочими.
