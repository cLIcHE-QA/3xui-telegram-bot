# v5 Production Acceptance and Controlled Canary

**Следующий candidate (не Published и не Deployed) #814/#816/#820:** bounded allowlist VPN app по первому идентификатору `userAgent`, постоянное поле `VPN-клиент`, приоритет реальной macOS перед моделью iPad, parity admin HWID списка с Client Portal с отдельным ограничением **8 записей на админ-страницу**, сохранением исходной страницы при Back и независимым неизменным лимитом **5 устройств в клиентском списке**; возврат из client HWID detail только к списку. Для закрытия нужна отдельная публикация/deployment и адресная проверка новых A4/A5, OS emoji и admin list, без повторного DELETE или Stars.

**Действующий нормативный план приёмки**, не свидетельство успешного public rollout. Статусы Published/Deployed/Accepted — только [Roadmap](ROADMAP.md): `v5.0.0-rc.18.1` Published и Deployed operator-reported по новому checkpoint (2026-10-20 19:01 EEST); #814/#816 targeted UI A4/A5 operator-reported FAIL 2026-10-20 19:34 EEST ([audit](audits/2026-10-20-v5-rc18-1-operator-targeted-acceptance-fail.md)); A1/A2/A3/A6 PASS, B1–B4 PASS только по отметкам, детали B1–B3 PENDING; независимый VPS read-back PENDING. Результаты HWID D1–D8 / S1–S4 — operator-reported scoped PASS ([audit](audits/2026-10-20-v5-rc18-hwid-operator-acceptance.md)); X1/X3 claimed без детального postcondition/approval provenance, X2 имеет противоречивые отметки и остаётся PENDING. На старом `rc.16.6` #760/U8 был FAIL; 2026-10-20 02:10 EEST после нового deployment оператор отметил U8-1…U8-4 (4/4), S1…S8 (8/8), R1…R8 (8/8) `[x]`: применимые targeted UI пути scoped operator-reported PASS, но условные U8-4/S3/S6 без подтверждения применимости PENDING/N/A, #707 § 9 unpublished. [Audit](audits/2026-10-20-v5-rc17-operator-targeted-ui-acceptance.md). Не приравнивать scoped UI к полному G-11 или V5-A-001…003; G-11 `PARTIAL/NO-GO`, public rollout `BLOCKED`.

## Исторические operator-reported checkpoints (не текущие статусы)

Первоначальные записи `rc.16.2` и `rc.16.4` о B5/C3 findings, scoped PASS, прошлом #705 OPEN и тогдашних `Published/Deployed/PENDING` сохранены в [immutable snapshot](https://github.com/cLIcHE-QA/3xui-telegram-bot/blob/b1f86cdf7c420b4e133c85578c8d42a006043e15/docs/V5_PRODUCTION_ACCEPTANCE.md) и [датированных аудитах](audits/). Это evidence на момент соответствующего release и не обновляет текущий Issue/release state. Targeted UI сценарии #740/#742–#745 ниже могут оставаться как шаблоны проверки, но не заменяют V5-A gates.

## 0. Зафиксировать baseline

Перед тестами запишите:

- exact release tag и 40-char SHA;
- `APP_VERSION`;
- deployed container image/build identity;
- cohort Telegram IDs (без публикации их в repository);
- текущие значения `CLIENT_PORTAL_ENABLED`,
  `CLIENT_PAYMENT_ACCEPTANCE_ENABLED`, rate-limit policy;
- timestamp начала acceptance.

Базовый health gate:

- container без restart loop;
- `/healthz` = ok;
- SQLite `PRAGMA quick_check` = ok;
- upstream 3x-ui connectivity = ok;
- `CLIENT_PORTAL_ENABLED=true`;
- cohort остаётся ограничен allowlist.

### Targeted prerequisite после failed RC

Если предыдущий immutable RC остановлен release-blocking finding, полный acceptance не
продолжается «с середины». Сначала на новом RC повторяется targeted regression самого
finding и ближайших инвариантов.

Для `v5.0.0-rc.3` после V5-A-007 требуется до нового Stars happy path доказать:

- SQLite schema v11 применена успешно, `PRAGMA quick_check` = ok;
- finite-traffic test customer имеет известный pre-purchase cumulative traffic > 0;
- если тестируется active renewal, до покупки зафиксирован оставшийся срок;
- после одной подтверждённой покупки target expiry равен
  `max(now, previous_expiry) + plan.duration`;
- новый finite quota cycle не наследует старые cumulative counters: remaining quota
  соответствует новому Plan, а customer access не становится inactive сразу после покупки;
- ровно один quota reset связан с новым entitlement; duplicate payment delivery/reconcile
  не выполняет второй reset и не добавляет duration повторно;
- uncertain/lost response traffic reset остаётся `unknown/provisioning` и не replay'ится
  автоматически;
- regression V5-A-005, V5-A-006 и customer UI finding #314 остаётся PASS.

Только после targeted PASS продолжается раздел V5-A-001.

## 1. V5-A-001 — Stars happy path

На dedicated test customer:

1. открыть `/start`;
2. выбрать доступный Stars plan;
3. подтвердить Terms;
4. получить invoice;
5. выполнить provider-approved/test Stars payment;
6. подтвердить, что Telegram доставил `successful_payment`;
7. проверить локально:
   - order = paid;
   - payment = confirmed;
   - ровно один entitlement для order;
   - entitlement проходит pending/provisioning → active;
   - finite-traffic Plan завершает quota reset как `success`, unlimited Plan — как
     `not_required`;
   - expiry не укорачивает существующий оплаченный остаток;
8. открыть subscription и реально импортировать/обновить её в клиенте;
9. проверить traffic/device read и для finite Plan подтвердить, что новый quota cycle
   начинается без старых cumulative counters;
10. повторно доставить/симулировать duplicate confirmation допустимым тестовым способом и
    убедиться, что второй payment/entitlement не появляется, quota reset не повторяется,
    а expiry не увеличивается второй раз.

Stars invoice UX subtest на новом RC: после одной контролируемой подтверждённой покупки проверить, что исходный invoice не продолжает выглядеть как payable; при Telegram-side ограничении удаления проверить подтверждённый платёж, журнал косметической очистки `unknown` и отсутствие повторных mutations. Не повторять списания ради косметики.

Refund/support subtest:

- открыть Stars payment в Admin;
- выполнить двухшаговый refund только для тестового платежа;
- проверить journal status и отсутствие blind retry;
- при unknown outcome не повторять mutation вручную без provider-side confirmation.

PASS evidence: timestamps, order/payment/entitlement IDs, provider/test reference,
финальный status и отсутствие manual DB repair.

## 2. V5-A-002 — failure / restart / reconciliation

Минимум по одному контролируемому сценарию:

- duplicate payment delivery;
- delayed payment event;
- temporary provisioning failure;
- uncertain/lost response во время paid quota reset;
- недоступная node/provider read;
- restart бота при pending/provisioning/reconciliation work.

Для каждого сценария:

1. записать initial state;
2. создать failure безопасным контролируемым способом;
3. выполнить restart/deploy только там, где сценарий этого требует;
4. дождаться recovery/reconciliation;
5. сравнить order/payment/entitlement/3x-ui state;
6. доказать отсутствие duplicate resource и blind mutation replay;
7. сохранить operator-visible recovery path.

PASS: финальное состояние объяснимо, нет orphan/duplicate ресурсов и нет ручной правки БД.
Для quota reset отдельно требуется доказать, что `unknown/in_flight` не приводит к
автоматическому повтору state-changing request после restart/reconcile.

## 3. V5-A-003 — abuse / load / soak

На canary cohort проверить:

- repeated customer callbacks;
- command spam;
- repeated `🛠 Проверить подписку`;
- после отдельного согласования targeted read-only диагностика `Сроки`: `match` / `insufficient_data` / `mismatch`, включая provider unavailable, expired entitlement, legacy/trial и отсутствующий expiry; одиночный scoped PASS не является общим PASS V5-A-003;
- invalid/oversized callback/input where applicable;
- одновременные subscription refresh через canonical proxy limits.

Ожидается:

- customer rate limiter ограничивает burst одного Telegram user;
- Admin Control Plane остаётся доступным;
- health endpoint остаётся responsive;
- нет unbounded task/job growth;
- container memory/CPU не демонстрируют runaway pattern;
- rate-limit response не содержит secret/customer data.

Soak должен включать минимум один полный restart/deploy cycle и пройти scheduled jobs,
которые реально включены в deployment. Duration фиксируется фактически в acceptance report;
repository не подменяет его заранее выбранным «магическим» числом часов.

## 4. Ownership / isolation canary

Использовать как минимум два test customer identity.

Проверить, что customer A не может:

- получить profile/subscription/traffic/devices customer B;
- подтвердить pre-checkout/order customer B;
- использовать callback payload для доступа к admin resource;
- получить чужой subscription URL/QR.

Backend должен fail-closed независимо от того, как сформирован callback payload.

## 5. Rollback test

1. установить `CLIENT_PAYMENT_ACCEPTANCE_ENABLED=false`;
2. убедиться, что новые invoice/pre-checkout отклоняются;
3. убедиться, что Admin Control Plane работает;
4. отдельно проверить, что уже доставленный `successful_payment` не теряется;
5. при необходимости установить `CLIENT_PORTAL_ENABLED=false`;
6. убедиться, что customer UI отключён, а `/admin` остаётся доступен;
7. вернуть исходные flags и повторить health check.

## 6. Финальная reconciliation

После canary сверить:

- `commerce_orders`;
- `commerce_payments`;
- `payment_webhook_events`;
- `entitlements`, включая quota reset status;
- Stars refund journal;
- 3x-ui clients/inbound membership;
- customer-visible subscription/traffic state.

Не должно оставаться необъяснимых mismatches.

## 7. Acceptance report

Создайте historical artifact:

`docs/audits/v5-production-acceptance-YYYY-MM-DD.md`

Минимальные поля:

- exact tag/SHA;
- environment/cohort scope;
- сценарии и фактический результат каждого;
- payment/order/entitlement references без secrets;
- restart/deploy evidence;
- load/soak duration и наблюдения;
- reconciliation result;
- findings и severity;
- rollback test;
- итоговый disposition: PASS / CONDITIONAL / FAIL.

Только **PASS** без unresolved Critical/High и без payment/entitlement/provisioning
inconsistency разрешает закрыть V5-A-001…A-003 и перейти к release/canary expansion.
