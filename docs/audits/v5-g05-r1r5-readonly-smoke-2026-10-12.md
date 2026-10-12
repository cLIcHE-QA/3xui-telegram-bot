# G-05 — R1–R5 targeted post-restart read-only smoke, 2026-10-12

## Дата, источник, версия, scope

- **Operator-supplied stdout:** `G05_UTC=2026-10-12T17:27:06.543411+00:00` = **2026-10-12 20:27:06.543411 EEST (Europe/Helsinki, UTC+03:00)**; сообщение с выводом оператора 2026-10-12 17:27:19 UTC. Это **не независимый VPS/SSH read-back агента**.
- **Environment:** running production Master bot container, Python `APP_VERSION=5.0.0-rc.9`, `ALLOWED_TELEGRAM_IDS` set size **3** (без ID). SQLite `file:/app/data/bot.sqlite3?mode=ro` + `PRAGMA query_only=ON` + `BEGIN`; G05-R1 касается всех локально `applied` events, G05-R2/R3 ограничены связанными pilot Stars orders/entitlements, G05-R4 — pilot finite-traffic `legacy`, G05-R5 — только существующие refunded pilot owners (макс. 2). В R5 при `VERIFY_TLS=true` и HTTPS выполнено до двух authenticated **GET** Master 3x-ui `get_client`; ошибок запроса 0, результат **не классифицирован**. Script local source checksum candidate: `sha256:3ebb6106fc18dc77cfd3dd231f6833a1ea75214d1758325c8618b917bfe3208f` (не независимая hash-аттестация реально исполненного контейнером stdin).
- **Published:** immutable prerelease `v5.0.0-rc.9` tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; **Deployed:** тот же tag только по предыдущим operator-supplied G-01/controlled restart host/container attestations, нынешний stdout повторно подтверждает лишь `APP_VERSION`, но не image/SHA; **Accepted:** общий v5 `NOT PASS`, G-05 `PARTIAL`.
- **GitHub baseline:** prior docs [PR #561](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/561) squash `main=f001117e72e641f61a944dcdd08879913e192fd3`, required `test`/`title` PASS, postmerge Python checks [38282705372](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38282705372) SUCCESS. GitHub merge/CI proof ≠ production acceptance.
- **Safety:** не запускались Stars purchase/refund, webhook delivery, mutations в SQLite, quota reset, 3x-ui POST, bot restart, deploy, fault injection, нагрузка, DR/W-01 или waived Telegram burst/W-02. Это небольшой existing-state observational check **(smoke)**, не регрессионный прогон и не recovery fault-injection.

## Обезличенный вывод оператора

~~~text
G05_UTC= 2026-10-12T17:27:06.543411+00:00
APP_VERSION= 5.0.0-rc.9
PILOT_SIZE= 3
G05-R1 APPLIED_EVENTS applied= 4 invalid_auth_or_type= 0 broken_reference= 0
G05-R2 MONEY_CLOCK linked= 4 invariant_review= 0
G05-R3 ENTITLEMENT_DRIFT checked= 4 invariant_review= 0
G05-R4 LEGACY_CONTEXT total= 1 active= 1 non_active= 0 not_updated_24h= 1
G05-R5 REFUND_MASTER_STATE eligible_users= 1 sampled= 1 enabled= 0 disabled= 0 expiry_future= 0 expiry_review= 0 missing= 0 unclassified= 1 request_errors= 0
G05_R1_R5=READ_ONLY_COMPLETE; ACCEPTANCE=NOT_AUTO_PASSED
~~~

## Проверки, критерии, статус

| ID | Проверено | Фактический результат | Scoped disposition |
| --- | --- | --- | --- |
| **G05-R1** | У 4 применённых `payment_webhook_events`: подпись `signature_valid=1`, `event_type=payment.confirmed`, связанные order/payment и provider согласованы. Это global aggregate по applied events, не all events или replay test. | `applied=4`, `invalid_auth_or_type=0`, `broken_reference=0` | **PASS** для checked SQL predicates |
| **G05-R2** | Четыре `confirmed/refunded` Stars payments `paid XTR` pilot orders: amounts, currency, `paid_at`/`confirmed_at`, chronology и отсутствие timestamp в будущем (+5m threshold). | `linked=4`, `invariant_review=0` | **PASS** для ограниченного pilot sample |
| **G05-R3** | Для 4 pilot entitlements: `telegram_id`, `plan_id`, отсутствие `active/suspended` на неплаченом заказе, `starts_at/expires_at` chronology. | `checked=4`, `invariant_review=0` | **PASS** для этих полей, не all entitlements/provider |
| **G05-R4** | Состояние исторического `legacy` для finite plan/paid pilot: active/не active, возраст `updated_at`. | `total=1`, `active=1`, `non_active=0`, `not_updated_24h=1` | **REVIEW**: статус reset неизвестен, возраст ≠ сбой и ≠ доказательство выполненного/невыполненного reset |
| **G05-R5** | Ровно одна eligible pilot identity с успешным возвратом, один read-only Master GET по email, без публикации email. | `eligible_users=1`, `sampled=1`, `enabled=0`, `disabled=0`, `missing=0`, **`unclassified=1`**, `request_errors=0` | **INCONCLUSIVE / REVIEW**: полученный `obj` не предоставил однозначно парсируемое на верхнем уровне `enable`, это **не** `disabled`, **не** `missing` и не provider revoke proof |

**Итог пакета:** **3 scoped PASS + 2 REVIEW (включая 1 INCONCLUSIVE)**; G-05 `PARTIAL`. R1–R3 — одномоментная выборка состояния после рестарта, а не фактический duplicate/delayed replay, не immutable before/after diff и не regressions suite. R4 не лечить ручным `quota_reset_status` или `bulkResetTraffic`. R5 не пересчитывать в `enabled=0`/access revoked: произвольная структура response payload требует отдельной безопасной **одной целевой** проверки формы/полей или ручной UI-проверки с обезличенным результатом. Не выводить raw `obj`/email/UUID/subId, URL, token/QR.

## Open criteria и audit Issues

- [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) **OPEN:** Master GET не классифицирован, node-side identity/inbounds/last sync, outage/recovery proof не проверялись; не закрывать.
- [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) **OPEN:** наличие refunded record в pilot и R5 GET не доказывают сокращение `expires_at` или 3x-ui revoke; новая 14-day policy запланирована отдельно, rc.9 её не реализует; не закрывать.
- [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466) **OPEN:** natural production `job_failed`, reminder/recovery и Attention Center не наблюдались в этом пакете, PENDING.
- [#317](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/317), [#342](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/342), [#422](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/422) **CLOSED** по отдельным своим критериям; повода reopen нет.
- G-01…G-04, G-06…G-08 `PARTIAL`, G-09…G-11 `PENDING`; W-01 `SKIPPED/WAIVED/NOT TESTED`, W-02 `INCONCLUSIVE/WAIVED`. Общий v5 `NOT PASS`; public launch запрещён.

**Next after checkpoint:** **не повторять** R1–R4, ранние 3x-ui Master GET, live Telegram burst или уже выполненную UI-изоляцию A/B. В следующем самостоятельном малом smoke-пакете использовать ещё не подтверждённые пользовательские/role-boundary пути G-07 и один целевой non-sensitive provider shape clarification для R5, без финансовых/системных mutations. Для любого нового существенного finding — Issue-first по `AGENTS.md`/`docs/GIT_WORKFLOW.md`. Не смешивать smoke coverage с обязательным полным v5 regression/acceptance.

**GitHub checkpoint:** evidence-only docs scope, **Issue: N/A — дата/контроль существующего G-05 без новой продуктовой задачи**. Верхняя сводка и каноническая строка G-05 в `docs/ROADMAP.md`; отдельный PR, required `test`/`title`, squash merge, independent `main` read-back, связанные Issue comments и closure audit. До этого `ROADMAP SYNC: PENDING`.
