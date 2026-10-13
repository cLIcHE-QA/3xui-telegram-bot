# B1–B4 — Finance, entitlement и provider: операторский пакет (2026-10-13)

## Источник, baseline и ограничения

- **Источник:** сообщение оператора `2026-10-13 11:15:45 UTC / 14:15:45 EEST`; скриншот «Пакет B — Finance, entitlement и provider» содержит **план и ожидаемые результаты**, фактические четыре текстовые строки B1/B2 предоставлены отдельно оператором. Время запуска отдельных SQL/3x-ui запросов и stdout детальных предикатов **не представлены**. Эти наблюдения не являются самостоятельным SSH/VPS read-back со стороны агента.
- **Production scope:** ранее оператором подтверждённый Master VPS и существующий pilot; в данном сообщении нет нового image/tag/SHA, идентификаторов и количества строк выборки. Для публикации используется предшествующий operator-reported deployed immutable `v5.0.0-rc.9` (tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`), без новой независимой аттестации runtime.
- **Четыре состояния:** protected `main=a992c24276144f54fb5cd386fdb32cac65d2c413` перед PR, предыдущий [PR #579](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/579) squash MERGED и post-merge [Python checks #38388560780](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38388560780) PASS; **Published** immutable prerelease `v5.0.0-rc.9`, `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; **Deployed** rc.9 — лишь operator-reported и прежний provenance image всё ещё REVIEW; **Accepted** overall v5 **NOT PASS**, public launch **BLOCKED**.
- **Безопасность:** в сообщении нет заявленных deploy/restart, новых Stars payments/refunds, replay, импортов VPN, изменений env/3x-ui, write-запросов. Этот checkpoint **не** запускает дополнительных production команд. Ранее закрытые короткие smoke G-02/G-03 не открываются заново, W-01/W-02 waived не повторяются.

## B1 — Pilot ledger, G-02: четыре нулевых счётчика

Переданный оператором текст:

```text
B1_LEDGER_MISMATCHES= 0
B1_ORPHANS= 0
B1_DUPLICATES= 0
B1_UNRESOLVED= 0
```

**Итог: scoped OPERATOR-REPORTED PASS** для четырёх **выведенных** счётчиков. Подробный SQL/полный набор проверенных rows, время выполнения, границы pilot cohort и идентификаторы связей в этом сообщении не предъявлены. Нельзя утверждать, что **все** orders/payments/events/entitlements production покрыты или что независимый cross-system ledger acceptance завершён. Предыдущие [G-02 5/5 bounded scoped PASS](v5-g02-targeted-reconciliation-2026-10-12.md) сохраняются, без повтора. **G-02 overall acceptance PARTIAL, bounded smoke CLOSED.**

## B2 — Refund и независимые оплаченные периоды, G-04

Переданный оператором текст:

```text
B2_CURRENT_RC9_POLICY_CONSISTENT= YES
B2_OTHER_PAID_ENTITLEMENT= YES
B2_PROVIDER_STATE_MATCH= YES
```

**Итог: scoped OPERATOR-REPORTED PASS** для заявленной сверки текущего refunded owner, его другого оплаченного entitlement и provider state. Отсутствуют построчные доказательства точного attribution, срока/инвариантов всех заказов и independent Master/Node readback. В действующем immutable rc.9 Stars refund меняет `commerce_payments.status`, но автоматически не отзывает оплаченный entitlement/3x-ui доступ: этот результат **согласуется с текущим поведением**, не является тестом новой политики [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) и не доказывает provider revoke. Предыдущий [S01 Master UI scoped PASS](v5-g07-s02-operator-smoke-2026-10-12.md) не повторять. **G-04 full acceptance PARTIAL.**

## B3 — `unclassified=1` Master API, G-05-D: PENDING

Оператор сообщил `B3_API_SHAPE=уточнить, что делать` — **выполненной проверки нет**. Исторический [G05-R5](v5-g05-r1r5-readonly-smoke-2026-10-12.md): один authenticated GET для refunded pilot owner, `request_errors=0`, `unclassified=1`; результат не является `disabled`, `missing` или подтверждённым отзывом доступа. Последующая S01 визуально показала `client_found=YES enabled=YES expiry=FUTURE inbounds=YES`, но не разрешила старую форму ответа API.

**Проверенный контракт исходного кода:** `XUIClient.get_client(email)` выполняет `GET /panel/api/clients/get/{email}`, возвращает `data.obj`, а `XuiCustomerProvider.access()` нормализует `obj.get("client", obj)` и требует `enable` типа `bool`. Возможность вложенного `client` **гипотеза о причине unclassified**, а не подтверждённый результат Master API. Отсутствие значения обязано остаться `UNKNOWN`, без подмены на `enabled`.

**Следующее адресное действие — только после checkpoint и при решении оператора:** однократно по **тому же** существующему пилотному refunded owner выполнить только authenticated HTTPS GET с проверяемым TLS и конечным timeout без retries, вывести **только** HTTP outcome/status, `obj` shape (верхний словарь или вложенный `client`), типы и наличие `enable/expiryTime/inboundIds`, конечную классификацию `enabled/disabled/missing/unavailable/unknown`. Не печатать raw JSON, email, ID, subId, GUID, token/URL или private endpoints. Не выполнять 3x-ui POST/DELETE и не повторять S01 UI.

## B4 — ретроспективное Stars → VPN, G-03: PENDING

Оператор сообщил `B4_HISTORICAL_E2E_PROOF=уточнить, что делать` — **нового доказательства нет**. [Исторический G-03](v5-g03-stars-vpn-existing-pilot-2026-10-12.md) уже имеет **5/5 scoped PASS**: existing paid entitlement/expiry, quota journal, ненулевой cumulative Master traffic, Telegram subscription и рабочий VPN; эти пять smoke **не повторять**. Однако не показана исходная **датированная причинная цепочка** `paid order→confirmed Stars event→entitlement→3x-ui provision→первоначальный client import/use`; current VPN connectivity и cumulative traffic не являются атрибуцией покупки.

**Следующее действие:** проверить **только уже сохранённые** приватные журналы/подтверждения, доступные оператору, и сообщить обезличенные booleans по доступности original `successful_payment`, payment/event/entitlement link, post-provision provider read и исторического импорта/подключения VPN-клиента. Не требовать публикации приватных ссылок/идентификаторов; не проводить новые Stars purchases, refund, QR import, replay или test traffic. Если первоначального import evidence нет, честный результат **B4=PENDING (HISTORICAL_TRACE_MISSING)**, а не `FAIL` работающего клиента и не `PASS`. G-03 остаётся SMOKE CLOSED / ACCEPTANCE PARTIAL.

## Issues, disposition, следующий checkpoint

- [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) **OPEN/PENDING**: будущая refund/entitlement/provider revoke policy не реализована, B2 подтверждает только текущую rc.9 семантику.
- [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) **OPEN/PENDING**: B1/B2 не проверяют direct-node offline/return, exact last sync или propagation/no-blind-replay; B3 API shape также не закроет node acceptance.
- [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466), #510, #564, #577 и остальные запланированные задачи остаются OPEN. #317/#342/#422 CLOSED по своим собственным завершённым критериям.
- **G-02/G-03:** короткий smoke CLOSED, full acceptance PARTIAL. **G-04/G-05:** PARTIAL с B2 scoped PASS и B3 pending. G-08 PARTIAL, G-09/G-10/G-11 PENDING, W-01/W-02 не повторять. Overall v5 NOT PASS/public BLOCKED.
- **Issue: N/A для отдельного нового** — B1/B2 являются evidence уже зарегистрированных acceptance gates; B3/B4 ещё не доказывают самостоятельный дефект. При обнаружении реального нового дефекта зарегистрировать отдельный Issue-first.
- **Checkpoint:** датированная сводка в `docs/ROADMAP.md` через отдельный docs-only PR, required `test`/`title`, squash merge, independent `main`/audits read-back, комментарии в соответствующих Issues, их closure audit и повторная сверка. **ROADMAP SYNC PENDING до всех действий**. Только после завершения — B3 адресная проверка и B4 архивная сверка, без старых smoke/regression.
