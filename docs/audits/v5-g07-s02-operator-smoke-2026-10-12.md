# G-07 S01–S04 и G-09 S05 — операторский точечный smoke (2026-10-12)

## Provenance, время, environment

- **Первое сообщение оператора:** 2026-10-12 **18:02:39 UTC / 21:02:39 EEST** (S02, объяснение ограничений S03/S04, запрос напомнить S05).
- **Второе сообщение оператора:** 2026-10-12 **18:10:20 UTC / 21:10:20 EEST** (фактический результат S01 и просьба зафиксировать S05 в Roadmap). Время сообщений не является независимо подтверждённым временем выполнения действий.
- **Target:** существующий production pilot Telegram bot и Master 3x-ui; **source: operator-reported** manual UI/text, без agent VPS/SSH read-back, screenshots и независимой Telegram API trace. Последний ранее подтверждённый оператором **Deployed** bot `v5.0.0-rc.9`; эта серия не проверяла host image/SHA. **Published:** immutable `v5.0.0-rc.9` tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`. **Accepted:** G-04/G-05/G-07 остаются `PARTIAL`, G-09 `PENDING`, общий v5 `NOT PASS` и публичный запуск `BLOCKED`.
- **Repository baseline до PR:** protected `main` `c3943c9fa4894651741352d73bab4286efc82710` после [#562](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/562), postmerge Python CI [38285565622](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38285565622) PASS; GitHub CI не заменяет production smoke.
- **Предыдущий контекст:** [G05-R5](v5-g05-r1r5-readonly-smoke-2026-10-12.md) зафиксировал `unclassified=1`, `request_errors=0` у одного существующего refunded-pilot пользователя при Master GET; этот результат *не* означал `disabled`, `enabled` или `missing`.
- Никаких новых Stars purchases/refunds, SQL/3x-ui writes, Telegram payment click, customer expiry edits, quota reset, provisioning, deploy/restart или нагрузочного/регрессионного прогона в этом операторском пакете не заявлено.

## Результаты 4 коротких smoke-сценариев и расписание S05

| ID | Наблюдение из сообщения оператора | Scoped disposition / ограничение |
| --- | --- | --- |
| **S01 / G-04 и G-05: Master client после исторического Stars refund** | `client_found=YES`, `enabled=YES`, `expiry=FUTURE`, `inbounds=YES` у **одного существующего разрешённого тестового клиента**, выбранного оператором для view-only Master 3x-ui UI. | **PASS — просмотр текущего состояния одного клиента**: найден, включён, срок впереди, inbound назначены. **REVIEW для refund/revoke postcondition**: не проверены exact payment→entitlement→provider mapping, дата refund, наличие *других* оплаченных периодов, node-side статус и ожидаемый отзыв доступа; `enabled=YES` сам по себе не означает регрессию или доказанный дефект. Глубинный GET `unclassified` из R5 остаётся историческим фактом ограниченной автоматической классификации. |
| **S02 / G-07: `/admin` на неадминистративной пилотной identity** | `S02: PASS` — оператор подтвердил отсутствие административного доступа. | **PASS, operator-reported, только этот видимый маршрут**, без полного RBAC/IDOR/forged callbacks. Не повторять без гипотезы. |
| **S03: устаревшая кнопка оплаты** | Оператор уточнил, что на уже оплаченном заказе кнопка оплаты штатно выдаёт ошибку. Нового нажатия в этом пакете не сообщил. | **N/A / NOT RUN**: повторять платежный сценарий ради smoke не требуется; ранее известный отказ не выдавать за новый PASS. |
| **S04: пересылка кнопки между тестовыми аккаунтами** | Пересылаемые сообщения сохраняют только **Stars payment** buttons; безопасные view-only кнопки удаляются. | **N/A / NOT RUN**: нельзя превращать payment в access-control probe, нет доказательства A→B IDOR. |
| **S05 / G-09: естественное истечение paid entitlement** | По запросу оператора **запланировано одноразовое напоминание на 2026-10-13 18:03:16 UTC = 21:03:16 EEST**; это задача-напоминание ChatGPT, не cron/VPS job. При проверке настройки задачи `enabled=true`, но `notifications_enabled=false` и `email_enabled=false`. | **PENDING / SCHEDULED / NOT TESTED**: доставка уведомления может требовать включения уведомлений; никакого доказанного естественного истечения paid entitlement пока нет. Если срок не истёк, сохранять `PENDING`, не укорачивать срок вручную. |

**Итог текущих двух сообщений:** **S01 и S02 — 2 scoped operator-reported PASS только в своих узких read-only/role-boundary сценариях; S03 и S04 — N/A / NOT RUN; S05 — scheduled / PENDING**. G-04 refund access/postconditions не принят, G-05 no-replay/legacy не принят, G-07 full RBAC не принят, G-09 pending. Нельзя переименовывать эти факты в полный production acceptance.

## Остаточные критерии и Issue audit

- **[#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) — OPEN:** в опубликованном `rc.9` ещё нет будущей 14-дневной политики вычета срока. Один включённый существующий refunded-pilot Master client с будущим сроком и inbound не доказывает, какой период должен был быть отозван: другие покупки/начисления не сверены. Никаких refund/expiry/provider mutations ради исправления картинки.
- **[#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) — OPEN:** Master-side UI наличия inbound не означает node-side sync, подтверждения identity/last sync/recovery нет.
- **[#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466) — OPEN:** естественного production `job_failed` и Attention Center проверка не затрагивала.
- **#317/#342/#422** — CLOSED по собственным ранее подтверждённым критериям, не переоткрывать. W-01 cross-host DR и W-02 live Telegram burst остаются WAIVED/NOT PASS, не повторять.
- **S05 next:** 13 октября после напоминания открыть `/subscription` только у уже *естественно* истёкшего оплаченного тестового периода, при наличии безопасного read-only источника проверить Master 3x-ui и клиентский UI. Иначе `PENDING`; ни ручного сокращения expiry, ни disabled toggle. Отложенное расписание не означает PASS.
- **S01 next:** дополнительной проверки UI без новой гипотезы не требуется; при необходимости будущего полноценного refund/3x-ui reconciliation — отдельный scoped и согласованный тест с контролем других оплаченных периодов. Не запускать регрессию вместо smoke.

## GitHub checkpoint

Это **evidence-only** docs update существующих G-04/G-05/G-07/G-09 без нового feature/bug scope: **Issue: N/A — отдельная новая задача не создана**. Сохранить верх Roadmap и канонические G-04/G-05/G-07/G-09 строки, запустить required `test` и `title`, squash merge и независимый `main` read-back, сверить own criteria Issues, затем отчитаться о состоянии acceptance. **До реального merge/read-back Roadmap sync PENDING**.
