# G-07 S01–S04 / G-09 S05 — короткий операторский smoke status (2026-10-12)

## Контекст и provenance

- **Источник:** текстовый ответ оператора **2026-10-12T18:02:39Z = 2026-10-12 21:02:39 EEST (Europe/Helsinki, UTC+03:00)**. Это время **сообщения**, не независимый timestamp исполнения проверки. Не предоставлены скриншот, Telegram API trace, прямой VPS/SSH доступ или новая Docker identity attestation; вывод «S02: PASS» только **operator-reported**.
- **Environment:** production pilot бот, ранее operator-reported deployed `APP_VERSION=5.0.0-rc.9`, immutable published prerelease `v5.0.0-rc.9` tag/commit SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`. Этот ответ оператора **не** пересверял новый deployed build/SHA, subscription/device status, provider access или live role data.
- **Repository baseline:** protected `main` `c3943c9fa4894651741352d73bab4286efc82710` после [#562](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/562), postmerge Python checks [38285565622](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38285565622) PASS. GitHub CI ≠ production acceptance. Новые system mutations (payment/refund/restart/deploy/flags/traffic reset/forced failure) **не выполнялись** в заявленном ответе.
- **Контекст ранее:** G05-R5 один read-only Master GET для существующего refunded pilot клиента вернул `unclassified=1`, `request_errors=0`; статус клиента/отзыва доступа НЕ установлен. [Предыдущий audit](v5-g05-r1r5-readonly-smoke-2026-10-12.md).
- **Методика:** новый **короткий smoke**, не регрессионная матрица, нагрузка или duplicate-payment/replay тест. Повторять уже пройденные сценарии или провоцировать платёж нельзя.

## Фактически сообщено

| Пункт | Операторский результат | Диспозиция |
| --- | --- | --- |
| **S01 / G-04-G-05** — один реальный refunded pilot 3x-ui Master client, карточка `Enable`, `Expiry`, `Inbounds` | Оператор спросил, какие поля нужны; фактического UI результата **не прислал**. После ответа предложены только агрегаты `client_found`, `enabled`, `expiry`, `inbounds`, без email/UUID/subID. | **PENDING / NOT TESTED**; не считать клиент включённым/отключённым, не делать revoke |
| **S02 / G-07** — обычный неадминистративный pilot identity отправляет `/admin`, ожидает отказ в admin доступе | **`S02: PASS`**; без независимого trace/screenshot/identity dump | **PASS, operator-reported scoped** для одного видимого пути `/admin`; не доказывает full RBAC, forged callbacks или IDOR |
| **S03 / G-07** — безопасная устаревшая кнопка просмотра заказа | Оператор уточнил, что кнопка оплаты уже оплаченного заказа штатно выдаёт ошибку, но **не сообщил о новом запуске S03**. Использовать кнопку оплаты ради retest или 3x-ui mutation не нужно. | **N/A / NOT RUN** для предложенного smoke, старую оплату не повторять; ранее известная штатная ошибка ≠ новый PASS |
| **S04 / G-07** — безопасная пересылаемая кнопка *просмотра* между двумя собственными identities | Оператор сообщил: вместе с кнопками пересылаются лишь сообщения с **оплатой за Stars**, а остальные пересылаются **без кнопок**. Изоляция account A→B через безопасный view-only forwarded callback не выполнена. | **N/A / NOT RUN**, не нажимать пересланный Stars invoice, не использовать платёж как IDOR probe |
| **S05 / G-09** — естественное истечение существующего оплаченного тестового entitlement, только read-only `/subscription` | Оператор попросил запланировать на сутки. **Одноразовое напоминание создано** на 2026-10-13 ~21:03 EEST (не удалённый production job). **Сам тест не выполнялся**. | **PENDING / FUTURE OBSERVATION**, нет факта paid expiry; не менять сроки вручную |

**Результат входящего сообщения:** **1 scoped operator PASS (S02), 2 N/A/NOT RUN (S03/S04), 1 PENDING (S01), 1 PENDING/SCHEDULED (S05)**. Ни G-07, ни G-09, ни общий v5 не переходят в PASS. Последний v5 status **NOT PASS**, public rollout BLOCKED; pilot allowlist остаётся.

## Стоп-условия и следующие проверочные действия

- S01 — **единственная актуальная следующая целевая UI-задача:** открыть карточку **одного собственного тестового клиента, который связан с историческим Stars refund**, в Master 3x-ui, *посмотреть*, не менять `Enable`, `Expiry`, `Inbounds`. Записать только `client_found YES/NO`, `enabled YES/NO/UNKNOWN`, `expiry FUTURE/PAST/UNKNOWN`, `inbounds YES/NO/UNKNOWN`. `enabled` после refund не доказывает баг из-за других оплаченных периодов; исходное `rc.9` не отзывает срок при refund (#433 future scope).
- S02 не повторять без новой гипотезы. **S03/S04** не прогонять через Stars invoice: это потенциальная платёжная операция, а уже видимое штатное отклонение оплаченного заказа не образует новый smoke.
- S05 — через одноразовое напоминание **13 октября примерно в 21:03 EEST** проверить **только при естественном истечении** paid test entitlement: `/subscription` state + при наличии уже доступного безопасного read-only evidence провайдера. Если срок ещё не истёк — `PENDING`, не укорачивать вручную и не отключать клиента.
- [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) OPEN future refund-revoke policy, [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) OPEN Master/Node sync, [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466) OPEN natural job_failed; нет нового defect/issue. #317/#342/#422 остаются CLOSED по собственным критериям. W-01/W-02 waived/inconclusive, без повторов. G-07 **PARTIAL**, G-09 **PENDING**, G-05 **PARTIAL**.
- **Синхронизация:** evidence-only docs checkpoint для существующего G-07/G-09, **Issue: N/A — не создано новой отдельной задачи или подтверждённого defect**. Обновить верх `docs/ROADMAP.md`, каноническую G-07/G-09 строку, создать PR и required `test`/`title`, squash, независимый `main` read-back, status/closure audit. До окончания **ROADMAP SYNC PENDING**.
