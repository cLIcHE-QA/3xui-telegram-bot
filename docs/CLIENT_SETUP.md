# Client Portal v5 — настройка контролируемого пилота

Руководство для оператора ограниченного клиентского пилота: включение и выключение клиентского контура, безопасный read-only smoke, Stars pre-checkout и rollback. Настройка Master/3x-ui, резервного копирования и секретов — в [ADMIN_SETUP.md](ADMIN_SETUP.md); полная приёмка — в [V5_PRODUCTION_ACCEPTANCE.md](V5_PRODUCTION_ACCEPTANCE.md). Это **нормативные инструкции**, а не история релизов.

**CONTROLLED PILOT ONLY / PUBLIC LAUNCH BLOCKED.** **Текущий статус контролируемого пилота:** [Roadmap](ROADMAP.md) — Published `v5.0.0-rc.18`, Deployed operator-reported `v5.0.0-rc.17` (2026-10-20 01:58 EEST, independent VPS read-back PENDING). Targeted U8/S/R 20/20 operator-reported `[x]`; scoped #760/#470 CLOSED/completed по operator-reported UI плюс offline regression условных U8-4/S3/S6; отсутствие соответствующих live-записей не представляется production PASS; #707 § 9 unpublished. G-11 PARTIAL/NO-GO, public launch BLOCKED. Канонические current-state поля — в Roadmap.

## Client Portal: тарифы и платежные ограничения

- Клиенту показываются только `active` тарифы с положительной ценой Stars/XTR, разрешённые локальными User Groups, `visibility`, `include_group_ids`/`exclude_group_ids` и серверными проверками. `admin_only` и технические бессрочные бесплатные планы не являются публичной продажей. Отсутствующая цена Stars не преобразуется из RUB; Telegram-покупка цифрового продукта использует только Stars.
- Список доступных тарифов после серверной фильтрации сортируется по Stars **по убыванию** со стабильным порядком равных цен **до** лимита в 20 строк. Административный RUB/Stars порядок не меняет клиентскую стоимость или backend pre-checkout: реальный `plan`/`invoice` заново проверяет цену, доступность и владельца.
- Ручная бессрочная выдача живёт в отдельном журнале `manual_entitlements`, а не в `Order → Payment`. Только доказанный provider read-back переводит её в `active`; `in_flight/unknown` закрывают новые операции и требуют ручной read-only сверки без автоматического replay. Никаких нулевых Stars invoices, RUB заказов или выдач через непрозрачный fallback.
- Разрешённые пилотные identity, Terms, private-chat/client authorization, Stars флаги и RBAC применяются на entrypoint, invoice и pre-checkout. Ошибка БД или неопределённость entitlement **не** открывает платёж. Уже доставленный `successful_payment` обрабатывается идемпотентно даже при отключении *новых* платежей.

## Исторические release и acceptance checkpoints (не текущий статус)

Датированные исходные отчёты об опубликованных/развёрнутых `rc.9`, `rc.10`, `rc.11`, `rc.16.1`, `rc.16.2`, `rc.16.4`, прошлых B5/C3 FAIL и scoped PASS сохранены без изменения в [immutable snapshot этого руководства](https://github.com/cLIcHE-QA/3xui-telegram-bot/blob/8d5b9ad1ce1fecf8f5f1808c786f3b2b3cf32f0b/docs/CLIENT_SETUP.md). Проверяемые источники: [rc.10 acceptance](audits/2026-10-15-v5-rc10-targeted-postdeploy-acceptance.md), [rc.11 deployment](audits/2026-10-15-v5-rc11-operator-deployment-checkpoint.md), [rc.16.1 deployment](audits/2026-10-17-v5-rc16-1-operator-deployment-checkpoint.md), [rc.16.4 smoke](audits/2026-10-18-v5-rc16-4-operator-targeted-smoke.md) и [rc.16.5 acceptance](audits/2026-10-19-v5-rc16-5-operator-targeted-acceptance.md). Старое `OPEN/PENDING` в этих источниках относится к моменту проверки, а не к текущему GitHub Issue.

## Плановая внешняя оплата

Решение об индивидуальной hosted Platega ссылке из Telegram-бота, отдельных валюте/статистике и предохранителях для будущего PSP зафиксировано в [EXTERNAL_PAYMENT_LINKS.md](EXTERNAL_PAYMENT_LINKS.md). **На текущем пилоте внешняя кнопка НЕ работает и не одобрена к rollout**: merchant/KYC/согласование правил Telegram для цифровых услуг ещё PENDING. До отдельного выпуска остаётся Stars flow с существующими флагами.

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

**Fail closed / действующий runtime contract:** `.env` остаётся безусловным veto. Owner-only DB overrides находятся в `/admin → Система → Настройки → 👤 Клиентский портал`; выключенное DB `portal=false` запрещает также **старые inline callbacks**, не только новые кнопки. `/admin` проверяется отдельно и не выключается клиентским флагом. Для break-glass используйте `.env CLIENT_PORTAL_ENABLED=false` с контролируемым применением конфигурации, без изменения уже подтверждённых платежей, 3x-ui entitlements или allowlist. Исторический регрессионный smoke #342 доступен в immutable snapshot и соответствующем аудите; он не подтверждает весь v5 acceptance.

## Плановый read-only smoke #471 (только после разрешённого release/deploy)

Последующие изменения отображения HWID по Issue #814 (только после отдельного merge/release/deploy): если upstream отдаёт проверенные `deviceOs`/`osVersion`, в списке и карточке показывается реальная версия ОС; `deviceModel`/`deviceOs` задают только консервативный визуальный тип `📱`/`💻`/`🖥️`/`🔹`, не влияют на owner/id/capability. Некорректная/неизвестная версия не подменяется догадкой. По #816 в детальной карточке дополнительно отображается только распознанное название VPN-приложения (`Happ` или `Incy`) из строго валидированного upstream `userAgent`; сам `userAgent`, его версия и неизвестные значения не выводятся. Это метаданные, не признак ownership/capability.

На выделенном pilot-клиенте сверить количество HWID с upstream: 0 и более 5 записей, листание/Back и полное время в карточке; отключённый/неизвестный `limitHwid` не должен отображаться как числовой лимит. Сменить модельные test identities только в изолированной проверке, проверить отсутствие чужих карточек, устаревшие ID, oversized fields, отключённый portal/allowlist и provider unavailable. Никаких DELETE, payment, расширения pilot или production mutation; результат записать отдельно с tag/SHA/TZ/source. До релиза #471 `PENDING`.

## #472 — плановый security/acceptance checkpoint (до выпуска PENDING)

Новый клиентский `🗑 Удалить устройство` предназначен только для собственного подтверждённого HWID; текущий Published/Deployed `rc.17` не содержит этот implementation PR. Никаких production DELETE в рамках read-only #471 smoke. Клиентский delete flow требует нового отдельно согласованного release/deploy и **отдельного разрешения** на каждую опасную production мутацию; публикация и зелёный CI сами по себе не дают такого разрешения.

До live testing допустима только offline/изолированная проверка: чужой/неизвестный ID, смена владельца между экранами, stale token, Cancel без DELETE, двойное подтверждение, concurrency, отсутствие capability, 4xx vs timeout/network/5xx, невалидный/частичный HWID inventory, отсутствие postcondition, общий portal OFF/allowlist и per-user cooldown. Подтверждать `PASS` только для проверенного evidence. При `unknown` выполняется **только read-only inventory lookup**, автоматический DELETE retry запрещён; после `deleted` должен быть независимый полный inventory read-back. Записи личного HWID, email, private token или private subscription URL не включать в отчёт. Текущие G-11 `PARTIAL/NO-GO` и public rollout `BLOCKED` не меняются.

## Безопасный smoke без реальных платежей

1. На разрешённой test identity проверьте `/start`: личный кабинет открывается при разрешённых gate и allowlist. У посторонней identity доступ должен быть отклонён. `/admin` проверяйте отдельно под разрешённой ролью.
2. Проверьте `/subscription` и `/paysupport`; legacy `/create` / `/inbounds` должны вести в личный кабинет, а не создавать обходной mutation path.
3. Проверьте отображение состояния подписки, сроков, трафика и устройств на специально выделенном клиенте, а также импорт/обновление subscription в реальном VPN-клиенте. Сверяйте клиентский UI с read-only 3x-ui состоянием; неизвестное/недоступное состояние не выдавайте за активную подписку.
   Для `🛠 Проверить подписку` различайте `✅ Сроки совпадают` (полные сравнимые применимые источники), `⚪ Недостаточно данных для сравнения` (provider unavailable или незаданный expiry) и `⚠️ Сроки не совпадают` (проверенный drift более 2 секунд). Доказанный mismatch важнее отсутствия третьего источника; диагностика ничего не исправляет и не перезапускает.
4. Убедитесь, что настройки тарифов, `stars_price`, Terms и владельца заказа не дают создать несогласованный платёж. **Не выполняйте реальные Stars purchases/refunds без отдельного одобренного acceptance-сценария**. Внешний fiat/generic HMAC checkout не является одобренным substitute для Telegram Stars в цифровом Telegram product flow.
5. Проверяйте rate limiting и ownership/IDOR только на своих изолированных test identities. Ожидаются fail-closed ответы и отсутствие раскрытия чужого subscription URL/QR.
6. Сохраните scrubbed evidence: tag/SHA, время/таймзону, окружение, сценарий, ожидаемый и фактический результат; отдельно перечислите `PASS`, `PENDING`, `FAIL`, `BLOCKED`, issue и следующий шаг.

Этот smoke — **не** замена [полного production acceptance](V5_PRODUCTION_ACCEPTANCE.md): там отдельно требуются Stars happy path/refund, delayed/duplicate events, uncertain outcome, provisioning/restart, ownership, abuse/load/soak, rollback и финальная межсистемная reconciliation.

## Действия при проблеме / rollback

1. При подозрении на проблему с платежами сначала выключите **новые** платежи: локально `CLIENT_PAYMENT_ACCEPTANCE_ENABLED=false` и контролируемое применение конфигурации. Не удаляйте существующие orders/payments/entitlements и не выполняйте повторные refund/provisioning mutations при `unknown` без доказанного postcondition.
2. При проблеме с доступом дополнительно установите `.env CLIENT_PORTAL_ENABLED=false` и примените только через контролируемый операторский deployment. Не выводите работоспособность emergency stop из исторического smoke: проверяйте точный фактически deployed tag/SHA и DB override `portal=false`, а не приравнивайте публикацию к deployment. `/admin` должен остаться доступным. Не отключайте backup/audit и не меняйте сведения об уже подтверждённых платежах.
3. Проверьте exact deployed tag/SHA, Health/SQLite/3x-ui, read-only payment journal и затронутых тестовых клиентов. Изменение `.env` требует штатного контролируемого применения; редактирование файла само по себе не означает, что контейнер получил новые значения.
4. Возвращайте флаги только после нового targeted PASS с evidence и согласованного решения; прежний `FAIL/unknown` сохраняйте как историю. Для security finding используйте [SECURITY.md](../SECURITY.md) и приватный канал репортинга.

## Gate на публичный запуск

**BLOCKED до полного PASS.** Нельзя расширять pilot allowlist или считать stable `v5.0.0` готовым лишь по публикации RC, зелёному CI или успешному ручному smoke. Необходимы все обязательные проверки из [V5_PRODUCTION_ACCEPTANCE.md](V5_PRODUCTION_ACCEPTANCE.md), закрытие release-blocking findings, безопасное восстановление/резервирование и отдельный approved release/deployment flow. Результаты и оставшиеся gates вносятся в [ROADMAP.md](ROADMAP.md); завершённое выполнение подтверждается evidence, а не галочкой без проверки.

После stable v5 и завершённого acceptance это руководство пересматривается отдельным PR, а не автоматически переименовывается в public launch guide.
