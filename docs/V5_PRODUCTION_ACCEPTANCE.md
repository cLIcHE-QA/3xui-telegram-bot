# v5 Production Acceptance and Controlled Canary

Этот runbook закрывает production-only findings V5-A-001…V5-A-003 после repository
launch audit. Он **не** разрешает отмечать сценарий PASS без фактически полученного
evidence на конкретном release tag/SHA.

**Scoped acceptance checkpoint (operator-reported, 2026-10-17 11:58 EEST):** deployed `v5.0.0-rc.16.2`, immutable Published tag SHA `a95b43f2e3322c5d42ee74509727686bf9be5cf2`; S1–S9/A1–A7/B1–B4,B6–B8/C1–C7/D1–D6/E1–E4/F1–F8/G1–G7/H1–H8/I1–I4/Z1–Z2 reported PASS, A2=MATCH. **B5 BLOCKED** — тарифы исчезли из клиентского каталога, root cause неизвестен. Scope #691/#719/#721/#724 CLOSE/completed после адресного smoke, #705 OPEN. Эти результаты не закрывают общие V5-A-001/A-002/A-003 или G-11: **PARTIAL/NO-GO**, public rollout BLOCKED; нет independent VPS/DB/image evidence. План `rc.16.3` (#734/#730/#731) требует отдельного релиза/deploy и собственных targeted проверок.

## Targeted pilot checks опубликованного rc.16.4 (Issues #740, #742–#745)

**Не выполнены / PENDING.** Реализация #740/#742–#745 уже MERGED в `main` через PR #741/#746; immutable `rc.16.4` Published через PR #749 и [штатный GitHub Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.16.4), SHA `114de5af16adcde5e8d128cc5a55d58addc37e73`. Deployment и targeted acceptance **PENDING**. Только после отдельно разрешённого production deployment соберите точный deployed tag/SHA, operator-reported status, DB/3x-ui health и read-only evidence на allowlisted pilot identity.

1. **#742:** в карточках и списках включённых/отключённых Users, Plans, Inbounds и Administrators 🟢/⚪; при API unknown 🟡; offline 🔴 и предупреждающая кнопка ⛔ не подменяются статусом disabled.
2. **#743:** страницы списка и поиска пользователей отображают действительный `enable` 3x-ui, делают не более одного read-only `clients/list` на экран, не переходят к N запросам, отсутствие/ошибка/дубликаты — 🟡; проверить кнопку Back и неизменные callback IDs.
3. **#744:** оба входа `Инфраструктура → Ноды → Master/direct Node → 3x-ui/Xray` возвращаются в ту же карточку, включая пагинацию/ошибку; вход из `Система` остаётся внутри версионного раздела; без запуска обновления/backup/restart.
4. **#745:** admin RUB/Stars ↑/↓, сохранённый режим при повторном входе/перезапуске, отсутствие изменения тарифных цен или DB schema; только Administrator/Owner сохраняют. **Client Portal**: после фильтрации разрешённых планов Stars ↓ до лимита отображения; проверить равные цены/visibility, не подтверждать invoice, сохранённые backend checks.
5. **#740:** отдельный read-only commerce blocker/unknown no-replay; не переписывать orders/entitlements, provider mutations — только отдельно согласованный тест. Финальный health/SQLite/provider read-back не объявлять PASS без evidence.

Фиксировать PASS отдельно по собственному Issue/тегу после targeted Telegram read-back. Эти проверки **не заменяют** V5-A-001…A-003, G-11 остаётся PARTIAL/NO-GO, public rollout BLOCKED.

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
