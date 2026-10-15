# Client Portal v5 — настройка контролируемого пилота

> **CONTROLLED PILOT ONLY / PUBLIC LAUNCH BLOCKED.** Опубликован GitHub prerelease `v5.0.0-rc.13`, immutable SHA `fbe2cafc3ace3aa54ec2398ddf5ec15cb0c4e9f5`; оператор подтвердил deployment 2026-10-15T23:02:48Z (`DEPLOY_OK`, Health/DB/3XUI_TCP `ok`, container running/restarts 0). Telegram Flow preflight отдельно вернул `CLIENT_RECORD_PROTOCOL` (A6 BLOCKED, изменений нет по сообщению оператора); точное заполненное поле неизвестно. Независимых VPS/image read-back и полноценного v5 acceptance нет. См. [audit](audits/2026-10-16-v5-rc13-client-record-protocol-smoke.md) и [ROADMAP](ROADMAP.md).

## Исторический operator-reported deployment rc.9 (2026-10-11)

Историческая операторская production baseline rc.9 сменила `v5.0.0-rc.8` (2026-10-10 23:13 UTC); в период с 2026-10-14 до обновления 2026-10-15 operator-reported production версией была rc.10, см. отдельный аудит.

По сообщению оператора в 16:15 EEST production развёрнут на immutable `v5.0.0-rc.9` (`13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`). Контейнер running, restart count 0, `Health=ok`, `DB=ok`, `3XUI_TCP=ok`; backup path предоставлен только в приватном отчёте, restore не проверялся. **Нет независимого VPS read-back.** Исправление старых клиентских callbacks (#342) вошло в этот релиз. Оператор 2026-10-11 17:25–17:30 EEST подтвердил targeted **Portal OFF → старая inline-кнопка blocked → Portal ON → /start и /admin доступны**, Stars override без изменений (operator-reported scoped PASS, независимого read-back нет). Для #342 production read-only reconciliation **PENDING**, поэтому полный acceptance и emergency stop за пределами проверенного scope не подтверждены. `.env` veto остаётся доступным по управляемой оператором процедуре. Targeted Hosts API #422 завершён и Issue закрыт; общий v5 acceptance NOT PASS. Public launch и общий v5 acceptance остаются BLOCKED/NOT PASS.

## Operator-reported rc.10 post-deploy targeted acceptance (2026-10-14/15)

Оператор 2026-10-14T19:48:49Z сообщил `DEPLOY_OK` для `v5.0.0-rc.10`, immutable SHA `ef7e655fed6818053ceff1818b64a852c83638ec`, container running, `RestartCount=0`, `Health/DB/3XUI_TCP=ok`, subnet `172.19.0.0/16` и наличие pre-deploy backup. 2026-10-15T09:52:57Z сообщил **PASS** для schema v13/SQLite quick_check, трёх исходов диагностики #627 и её Refresh/Back/no-mutations, раздельных Stars/manual ledger и refund/owner isolation/Back #628, no financial mutations, post-smoke Health и Full Backup/off-site; discrepancies не выявлены в отчёте. Это **operator-reported scoped PASS**, без независимого VPS или детальных raw SQL/API/Telegram артефактов; G-11 остаётся `PARTIAL / NO-GO`. Подробности в [rc.10 audit](audits/2026-10-15-v5-rc10-targeted-postdeploy-acceptance.md). Новая добровольная 14-дневная refund policy #433 отложена и не входит в rc.10. Не проводить реальные refund или перепровижининг ради read-only smoke.

## Operator-reported rc.11 deployment baseline (2026-10-15)

Оператор сообщил `Production=v5.0.0-rc.11` / `GitSHA=5f0576417ef3274b92adefa0c9c0932c7a359fd5`, `APP_VERSION=5.0.0-rc.11`, `DEPLOY_OK`, container `running`, `RestartCount=0`, `Health/DB/3XUI_TCP=ok`, наличие pre-deploy backup (путь остаётся приватным). Время получения 2026-10-15T18:07:06Z, точное время деплоя не сообщено. Это только **operator-reported deployment/health baseline PASS**; нельзя выводить из `DB=ok` SQLite `quick_check`, из `3XUI_TCP=ok` Node Reality Flow parity или backup restore PASS. Нужны отдельные targeted read-only #648/#659, UI/Back/Cancel #649, Traffic #650, безопасный UI preview #663 и post-smoke health. Адресная mutation #663, старый reproducer #648 и любые production writes требуют отдельного разрешения. Full v5 acceptance и public launch остаются BLOCKED. Детали в [датированном checkpoint](audits/2026-10-15-v5-rc11-operator-deployment-checkpoint.md).

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

**Fail closed / историческое ограничение rc.8:** `.env` остаётся безусловным veto. Owner-only runtime DB overrides находятся в `/admin → Система → Настройки → 👤 Клиентский портал`. В `rc.8` обнаружен code-review finding: старые клиентские inline callbacks не учитывали DB `portal=false`. **Исправление опубликовано в immutable `v5.0.0-rc.9` (#342): Portal OFF → старая inline-кнопка denied → ON и `/admin` доступны, operator-reported scoped PASS.** Независимая VPS/build attestation и непроверенные сценарии общего v5 acceptance остаются PENDING. Для break-glass остаётся локальный `.env CLIENT_PORTAL_ENABLED=false` с контролируемым применением конфигурации, без изменения уже подтверждённых платежей, 3x-ui entitlements или allowlist.

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
2. При проблеме с доступом дополнительно установите `.env CLIENT_PORTAL_ENABLED=false` и примените только через контролируемый операторский deployment. Историческое ограничение dynamic UI switch в rc.8 исправлено в опубликованном rc.9 (#342); при сомнениях в фактически deployed версии проверяйте её отдельно, а не считайте публикацию равной deployment. `/admin` должен остаться доступным. Не отключайте backup/audit и не меняйте сведения об уже подтверждённых платежах.
3. Проверьте exact deployed tag/SHA, Health/SQLite/3x-ui, read-only payment journal и затронутых тестовых клиентов. Изменение `.env` требует штатного контролируемого применения; редактирование файла само по себе не означает, что контейнер получил новые значения.
4. Возвращайте флаги только после нового targeted PASS с evidence и согласованного решения; прежний `FAIL/unknown` сохраняйте как историю. Для security finding используйте [SECURITY.md](../SECURITY.md) и приватный канал репортинга.

## Gate на публичный запуск

**BLOCKED до полного PASS.** Нельзя расширять pilot allowlist или считать stable `v5.0.0` готовым лишь по публикации RC, зелёному CI или успешному ручному smoke. Необходимы все обязательные проверки из [V5_PRODUCTION_ACCEPTANCE.md](V5_PRODUCTION_ACCEPTANCE.md), закрытие release-blocking findings, безопасное восстановление/резервирование и отдельный approved release/deployment flow. Результаты и оставшиеся gates вносятся в [ROADMAP.md](ROADMAP.md); завершённое выполнение подтверждается evidence, а не галочкой без проверки.

После stable v5 и завершённого acceptance это руководство пересматривается отдельным PR, а не автоматически переименовывается в public launch guide.
