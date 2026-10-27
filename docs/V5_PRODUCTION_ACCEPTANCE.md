# v5 Production Acceptance and Controlled Canary

**Merged implementation #814/#816/#820 ([PR #821](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/821))** — `main` `aff7bde8ec2521fa11f14362c00502737e2b04e5`, required test/title PASS, Published `v5.0.0-rc.18.2` (tag SHA `20205a56887cbdf644f604febdd9eb9ac717b914`) PASS; Deployed operator-reported и targeted 15/15 и H1–H8 operator-reported PASS; #814/#816/#820/#471 completed, #472 CLOSED/completed (operator-accepted) ([post-merge audit](audits/2026-10-20-hwid-ui-819-821-postmerge-checkpoint.md)):  bounded allowlist VPN app по первому идентификатору `userAgent`, постоянное поле `VPN-клиент`, приоритет реальной macOS перед моделью iPad, parity admin HWID списка с Client Portal с отдельным ограничением **8 записей на админ-страницу**, сохранением исходной страницы при Back и независимым неизменным лимитом **5 устройств в клиентском списке**; возврат из client HWID detail только к списку. Адресный smoke после публикации и deployment rc.18.2 подтверждён оператором; пять HWID Issues CLOSED/completed, независимый VPS/DELETE postcondition read-back не заявлен; без повторного DELETE или Stars.

**Действующий нормативный план приёмки**, не доказательство public rollout. [Roadmap](ROADMAP.md): Published `v5.0.0-rc.25` SHA `1c0854c9b416a2d0f2ccbe9083d62d88794307ed`, Deployed `v5.0.0-rc.18.10` exact SHA `dae205ac82762723448f93827b981f89ae622231` operator-reported, HWID 23/23 targeted scoped PASS ([audit](audits/2026-10-22-v5-rc18-10-operator-targeted-hwid-acceptance.md)), #827/#830/#833/#834/#838/#854 completed; independent VPS read-back PENDING. Полные V5-A-001…003 и G-11 PARTIAL/NO-GO, public rollout BLOCKED. Не повторять старые HWID H1–H8 и не проводить новые DELETE/Stars/refund/restore/burst.

## Исторические operator-reported checkpoints (не текущие статусы)

Первоначальные записи `rc.16.2` и `rc.16.4` о B5/C3 findings, scoped PASS, прошлом #705 OPEN и тогдашних `Published/Deployed/PENDING` сохранены в [immutable snapshot](https://github.com/cLIcHE-QA/3xui-telegram-bot/blob/b1f86cdf7c420b4e133c85578c8d42a006043e15/docs/V5_PRODUCTION_ACCEPTANCE.md) и [датированных аудитах](audits/). Это evidence на момент соответствующего release и не обновляет текущий Issue/release state. Targeted UI сценарии #740/#742–#745 ниже могут оставаться как шаблоны проверки, но не заменяют V5-A gates.

## Собственная история #506 — отдельный отложенный targeted gate

Source-only разработка по #930 не подтверждает deployment или live acceptance. После отдельного разрешённого обновления проверить read-only сценарии из [CLIENT_SETUP](CLIENT_SETUP.md#собственная-история-stars-506): private-owner и SQL IDOR для Order/Payment, XTR-only вкладки по 8 записей, возврат на исходную страницу, отдельные missing/unknown/refunded/Entitlement состояния, support/Terms без invoice/consent/refund/reconcile. Использовать существующие безопасные записи/fixtures; новые финансовые операции и Telegram sends в автономный scope не входят. Offline tests и required CI подтверждают только проверенный source scope; #506 keep_open до своего targeted outcome. Общие G-11 PARTIAL/NO-GO и public rollout BLOCKED сохраняются; прежние HWID PASS/waived burst не повторять.

## Видимость legacy-команд #564 — отдельный отложенный targeted gate

После будущего отдельно разрешённого deployment проверить новую видимость справочника по [CLIENT_SETUP](CLIENT_SETUP.md#актуальные-команды-и-совместимость-564): active-only команды, основной `/start`, отсутствие legacy рекомендаций и Back. Четыре admin roles, 2 legacy slash/3 saved callbacks и portal/allowlist guards подтверждаются source/offline regression; старый N03 не повторять, production flags ради неизменённых paths не переключать. Типизированный каталог/AST CI проверяют и скрытые handlers. Telegram global command registry не изменялся и не считается очищенным; старый N03 не доказывает новый visibility outcome. Offline/CI не заменяют собственный operator-reported visibility outcome; #564 keep_open, deployment/live smoke отложены по #930. G-11 PARTIAL/NO-GO/public rollout BLOCKED, waived burst и прошлые HWID PASS не повторять.

## Кампании #947 — source-only schema/API scope

Foundation не подключена к runtime и не имеет sender/worker/UI. Собственные storage/migration/ownership/dry-run критерии проверяются offline/CI; реальные Telegram sends не требуются и не разрешаются ради этой части. Parent #874 сохраняет отдельные policy #501, UI/integration, permission/abuse/privacy, deployment и pilot delivery gates. Foundation v16 впервые опубликована в rc.24; текущий rc.25 добавляет source queue v17, предыдущие tags immutable; будущая установка проверяет cumulative upgrade/recovery по [SQLITE_MIGRATIONS](SQLITE_MIGRATIONS.md). Source PASS не подтверждает runtime delivery/G-11, прежние scoped PASS/waived burst не повторять.

## Очередь #948 — собственный source-only scope

Acceptance этой части — isolated migration/state/ownership/schedule/fencing/unknown/retry/stop/privacy regressions, security review, required CI, immutable RC и publication/main checkpoint. Реальные sends/listeners/VPS операции не требуются и не разрешаются ради source части. Positive fake admission используется только с isolated transport; в текущем runtime настоящая policy отсутствует и delivery DENY_ALL, категории не становятся mandatory.

Свой source PASS не заменяет policy #501, UI/observer/transport #949, privacy/abuse review, runtime authentication, поздний deployment и разрешённый pilot parent #874. Source schema17 из main (#956) теперь Published в rc.25; старый rc.24/schema16 immutable; будущий cumulative upgrade/recovery проверяется по SQL contract. Старые HWID PASS/waived burst не повторять, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

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


**Targeted Karing gate #827, GitHub Published rc.18.6 (tag SHA `46bc24530633d9958278ab56f624c8b8d274f845`; Deployed/Accepted PENDING):** fix [#849](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/849) MERGED `79c3700a5933707e21b0e564eab2276744762d0e`, offline `test`/`title` PASS. Фактические version/tag SHA running container, полная длина Karing UA из 3x-ui, client/admin parity и targeted health/read-only acceptance PENDING. Не возобновлять production DELETE, Stars/payments, provider mutations или public rollout; #827/#830/#833/#834/#838 keep_open, G-11 PARTIAL/NO-GO.
