# Client Portal v5 — настройка контролируемого пилота

> **CONTROLLED PILOT ONLY / PUBLIC LAUNCH BLOCKED.** Это операторское руководство для ограниченной группы уже разрешённых Telegram ID. Оно **не** является подтверждением полного production acceptance, инструкцией по открытию массовой регистрации или разрешением на приём новых реальных платежей. Опубликованный и развёрнутый baseline по состоянию на 9 октября 2026 — `v5.0.0-rc.7`; последующие изменения `main` не считаются частью этого релиза до отдельной публикации и controlled deployment. Факты и незакрытые gates: [ROADMAP.md](ROADMAP.md) и [V5_PRODUCTION_ACCEPTANCE.md](V5_PRODUCTION_ACCEPTANCE.md).

## Область ответственности и условия старта

- Инфраструктура Master/direct node, 3x-ui, Docker, TLS, backup и секреты устанавливаются по [ADMIN_SETUP.md](ADMIN_SETUP.md), не повторяются здесь.
- Используйте **только специально разрешённые тестовые Telegram identity** и изолированные тестовые тарифы/подписки. Не расширяйте cohort и не убирайте allowlist ради удобства.
- Перед изменениями зафиксируйте published tag, commit SHA, реально deployed tag/SHA, `APP_VERSION`, SQLite schema, состояние `/healthz`, 3x-ui connectivity, backup/rollback baseline и доступность `/admin`. Published ≠ deployed ≠ accepted.
- Клиентский контур и административный `/admin` имеют отдельные authorization boundaries; включение Client Portal не предоставляет административные права.
- Не публикуйте реальные Telegram ID, subscription URLs, provider payment references, ключи и содержимое приватных БД в Issues, PR или audit evidence.

## Переменные пилота и доступ

На Master в локальной приватной `.env` (без публикации значений):

| Переменная | Значение / правило |
| --- | --- |
| `ALLOWED_TELEGRAM_IDS` | Явная пилотная allowlist; `ADMIN_TELEGRAM_IDS` — отдельный список администраторов. Не используйте фиктивные ID из `.env.example` в production |
| `CLIENT_PORTAL_ENABLED` | `false` запрещает клиентский UI, **не** выключает `/admin`; `true` не отменяет allowlist |
| `CLIENT_PAYMENT_ACCEPTANCE_ENABLED` | `false` блокирует **новые** Stars invoices и pre-checkout; уже подтверждённые `successful_payment` должны быть обработаны безопасно |
| `CLIENT_RATE_LIMIT_COUNT` / `CLIENT_RATE_LIMIT_WINDOW_SECONDS` | Per-user sliding window (в примере `30` / `60`); меняйте только после согласованного canary и проверки лимитов |

Настоящий код определяет доступ как принадлежность к `ALLOWED_TELEGRAM_IDS` **или** `ADMIN_TELEGRAM_IDS`, с отдельным gate Client Portal; административный Telegram ID не становится автоматически внешним клиентом. Для приёмочных прогонов используйте специально выделенные аккаунты, не открывая доступ всем пользователям.

**Fail closed:** `.env` — верхний запрет. В ещё **не опубликованном** коде после PR #368 добавлены Owner-only runtime switches по пути `/admin → Система → Настройки → 👤 Клиентский портал` с SQLite override и revision-aware audit. **В `rc.7` этого интерфейса нет.** После выпуска новой версии значение `false` в `.env` сильнее любого DB override; при сбое чтения SQLite состояние блокируется. Не пытайтесь использовать UI switches на `rc.7` и не интерпретируйте успешный CI `main` как production PASS.

## Безопасный smoke без реальных платежей

1. На разрешённой test identity проверьте `/start`: личный кабинет открывается при разрешённых gate и allowlist. У посторонней identity доступ должен быть отклонён. `/admin` проверяйте отдельно под разрешённой ролью.
2. Проверьте `/subscription` и `/paysupport`; legacy `/create` / `/inbounds` должны вести в личный кабинет, а не создавать обходной mutation path.
3. Проверьте отображение состояния подписки, сроков, трафика и устройств на специально выделенном клиенте, а также импорт/обновление subscription в реальном VPN-клиенте. Сверяйте клиентский UI с read-only 3x-ui состоянием; неизвестное/недоступное состояние не выдавайте за активную подписку.
4. Убедитесь, что настройки тарифов, `stars_price`, Terms и владельца заказа не дают создать несогласованный платёж. **Не выполняйте реальные Stars purchases/refunds без отдельного одобренного acceptance-сценария**. Внешний fiat/generic HMAC checkout не является одобренным substitute для Telegram Stars в цифровом Telegram product flow.
5. Проверяйте rate limiting и ownership/IDOR только на своих изолированных test identities. Ожидаются fail-closed ответы и отсутствие раскрытия чужого subscription URL/QR.
6. Сохраните scrubbed evidence: tag/SHA, время/таймзону, окружение, сценарий, ожидаемый и фактический результат; отдельно перечислите `PASS`, `PENDING`, `FAIL`, `BLOCKED`, issue и следующий шаг.

Этот smoke — **не** замена [полного production acceptance](V5_PRODUCTION_ACCEPTANCE.md): там отдельно требуются Stars happy path/refund, delayed/duplicate events, uncertain outcome, provisioning/restart, ownership, abuse/load/soak, rollback и финальная межсистемная reconciliation.

## Действия при проблеме / rollback

1. При подозрении на проблему с платежами сначала выключите **новые** платежи: локально `CLIENT_PAYMENT_ACCEPTANCE_ENABLED=false` и контролируемое применение конфигурации. Не удаляйте существующие orders/payments/entitlements и не выполняйте повторные refund/provisioning mutations при `unknown` без доказанного postcondition.
2. При проблеме с доступом дополнительно выключите `CLIENT_PORTAL_ENABLED=false`. `/admin` должен остаться доступным. Не отключайте backup/audit и не меняйте сведения об уже подтверждённых платежах.
3. Проверьте exact deployed tag/SHA, Health/SQLite/3x-ui, read-only payment journal и затронутых тестовых клиентов. Изменение `.env` требует штатного контролируемого применения; редактирование файла само по себе не означает, что контейнер получил новые значения.
4. Возвращайте флаги только после нового targeted PASS с evidence и согласованного решения; прежний `FAIL/unknown` сохраняйте как историю. Для security finding используйте [SECURITY.md](../SECURITY.md) и приватный канал репортинга.

## Gate на публичный запуск

**BLOCKED до полного PASS.** Нельзя расширять pilot allowlist или считать stable `v5.0.0` готовым лишь по публикации RC, зелёному CI или успешному ручному smoke. Необходимы все обязательные проверки из [V5_PRODUCTION_ACCEPTANCE.md](V5_PRODUCTION_ACCEPTANCE.md), закрытие release-blocking findings, безопасное восстановление/резервирование и отдельный approved release/deployment flow. Результаты и оставшиеся gates вносятся в [ROADMAP.md](ROADMAP.md); завершённое выполнение подтверждается evidence, а не галочкой без проверки.

После stable v5 и завершённого acceptance это руководство пересматривается отдельным PR, а не автоматически переименовывается в public launch guide.
