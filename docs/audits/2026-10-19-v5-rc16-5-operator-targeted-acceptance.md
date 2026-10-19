# v5.0.0-rc.16.5 — адресная операторская приёмка C3 и manual→manual

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-19 11:18 UTC+03:00 (EEST); сообщение оператора 2026-10-19T08:18:31Z.
- **Окружение:** production controlled pilot, Telegram/3x-ui/SQLite и deploy-helper **со слов оператора**; прямого доступа к VPS, image, SQLite или provider API в этом checkpoint нет.
- **Цель:** зафиксировать targeted acceptance P1–Z7 и последующий R1–R9 read-only checkpoint с сохранением разных уровней доказательности, не повторяя ранее принятые проверки `rc.16.4`.
- **Версия и immutable tag/SHA:** `v5.0.0-rc.16.5` / `0728b8466eb2c4c65f0a36a112ae5c4a3ea60cbc`; GitHub tag SHA независимо проверен, deployed SHA и runtime status — operator-reported.
- **Scope:** адресный P1–P2/C3.1–C3.4/S1–S6/Z6–Z7, позднее отмеченные R1–R9 (сравнение журналов, расследование B5 и closure audit) без новых payments/remote mutations.
- **Фактический результат:** PARTIAL — первый scoped пакет 14/14 operator-reported PASS; R1–R9 отмечены завершёнными, но R4 verdict, R5/R6 root-cause, R7 data-consistency verdict и R8 Issue decisions/подтверждающее evidence не переданы и не объявляются PASS. Общий G-11 PARTIAL/NO-GO.
- **Источник и evidence:** [GitHub Issue #730](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/730) и operator-reported сообщения 2026-10-19T08:18:31Z и 2026-10-19T08:33:37Z; оператор отметил все 14 пунктов чек-листа `P1,P2,C3.1–C3.4,S1–S6,Z6,Z7` как `[x]` 2026-10-19T08:18:31Z. Raw stdout, снимки/логи VPS и отдельная machine-readable provider attestation не приложены. [Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.16.5), [PR #753](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/753), [PR #754](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/754), [release PR #757](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/757), [publication audit](2026-10-19-v5-rc16-5-github-publication-checkpoint.md).

- **Ограничения и остаточные риски:** только отметки пользователя о выполнении, без raw DB/provider logs, значений R4 `MATCH/MISMATCH/UNKNOWN`, причины B5 и доказательств R7/R8; независимая VPS/DB/data-plane аттестация отсутствует; #730/#731/#705 не закрывать по галочкам; старый #743 C3 FAIL остается историческим для rc.16.4.
- **Связанные Issues:** #743, #752 (scoped PASS по отчёту), #730, #731, #705 (OPEN, результаты causal inquiry недостаточны), #470 (read-only Orders отдельно).
- **Следующий шаг:** после required `test/title` PASS и отдельного разрешённого merge docs PR выполнить main read-back; запросить лишь обезличенный R4 verdict и результат R5/R6/R7, оформить Issue closure решения без новых production операций. Новый feature UX ручных выдач — отдельное решение, не scope этого аудита.
- **Раздельные состояния:** merged=PASS (#753/#754/#757, этот docs PR OPEN); published=PASS (immutable rc.16.5); deployed=operator-reported rc.16.5, independent evidence PENDING; accepted=operator-reported #743/#752 PASS, #730/#731/#705 PENDING, G-11 PARTIAL/NO-GO.

## Результат по проверенным сценариям

| Группа | Результат | Точное свидетельство (operator-reported) |
| --- | --- | --- |
| P1–P2 | PASS (2/2) | pre-deploy backup и baseline rc.16.4; затем rc.16.5 SHA/APP_VERSION, SQLite schema v15, `quick_check`, Health/DB/3x-ui |
| C3.1–C3.4 / #743 | PASS (4/4) | enabled 🟢, disabled ⚪, unknown/error 🟡, read-only bounded search/Back без N+1 и provider mutations; прежний C3 FAIL на rc.16.4 остаётся историческим |
| S1–S6 / #752 | PASS (6/6) | same-group manual→manual preview и однократное подтверждение; read-back expiry=0/traffic=0/new IP/HWID/unchanged Inbounds; SQLite old `superseded`, new `active`, Orders/Payments unchanged; same-plan no-op; недопустимые состояния проверены по offline CI, не создавались в production |
| Z6 | PASS | post-smoke container/restarts, Health/DB/3x-ui, `quick_check`, critical events без отклонений по сообщению оператора |
| Z7 | OPERATOR-REPORTED COMPLETE; GITHUB SYNC PENDING | оператор отметил пункт; факт обновления `docs/ROADMAP.md` в `main` возникает только **после** merge отдельного docs-only PR и независимого GitHub read-back, не из отметки `[x]` |

**Scoped acceptance:** #743 и #752 — **operator-reported PASS** после Published и заявленного Deployed rc.16.5; соответствующие offline PR required `test`/`title` прошли ранее. Никакая новая мутация 3x-ui, DB, Stars/refund или deployment из GitHub для этого аудита не выполнялась. Операторская отметка не является независимой VPS/data-plane аттестацией. Возможное закрытие Issues ограничено их собственным scope и не повышает общий G-11.

## Предыдущие PASS не повторялись

[Аудит rc.16.4](2026-10-18-v5-rc16-4-operator-targeted-smoke.md): 59/60 operator-reported PASS, C3 FAIL на **старом** tag; M1–M8 — 8/8 operator-reported PASS позднее, но timestamp/causal correlation с `commerce_orders.awaiting_payment` остаётся PENDING по #730. #745 restart persistence PASS/CLOSED; не пересоздавать proof повторной выдачей, restart или payment.

## Дополнительный read-only checkpoint R1–R9 — 2026-10-19 11:33 UTC+03:00

- **Источник:** сообщение оператора 2026-10-19T08:33:37Z; R1–R9 все отмечены `[x]` как выполненные, без публикации raw SQLite rows, timestamps и identity.
- **R1–R3 (#730):** оператор отметил сравнение `manual_entitlements`, `commerce_orders`, `commerce_payments` и `audit_log`, **но** фактическая временная последовательность и обезличенные значения не переданы; нельзя утверждать, что order fence был соблюден или нарушен.
- **R4 (#730):** пункт выбора `MATCH / MISMATCH / UNKNOWN` отмечен выполненным, **сам выбранный verdict не сообщён**: `PENDING EVIDENCE`. Не менять order и не повторять manual grant.
- **R5–R6 (#731):** диагностика B5 и сопоставление с Client Portal отмечены выполненными; **конкретная причина либо явный вывод `root cause UNKNOWN` не предоставлены**. Не закрывать #731 по чекбоксу.
- **R7 (#705):** сверка Orders/Payments/Entitlements/Manual Entitlements отмечена выполненной, но результат `MATCH/MISMATCH` и безопасное summary отсутствуют.
- **R8 (#705):** Issue closure audit отмечен выполненным, но исход принятия/остатки не представлены; нет оснований закрыть #705.
- **R9:** read-only final status/health отмечен выполненным; датированный GitHub checkpoint обновлён в текущем docs PR; **Roadmap sync в main PENDING** до merge/read-back.
- **Итог R1–R9:** `PARTIAL / EVIDENCE INCOMPLETE` для R1–R9. `[x]` означает заявленное выполнение оператором, а не утверждённый `PASS` по causal/root-cause criteria. Предшествующие P/C3/S/Z по rc.16.5 не требуют повторного smoke.

## Остаточные gates и следующий шаг

- [#730](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/730): **OPEN/PARTIAL**. Только read-only сверка `manual_entitlements.started_at/confirmed_at/status/result_code`, `commerce_orders.created_at/updated_at/status`, `commerce_payments` и `audit_log` события `user.plan.manual.granted` для доказательства последовательности. Тот же pilot identity и отсутствие payment известны лишь по предыдущему operator report. Ни новый grant, ни SQL status update не разрешены.
- [#731](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/731): **OPEN/PARTIAL**. Исторический B5 на поздних проверках не воспроизводился, но причина исходного исчезновения Stars каталога не установлена. Требуется read-only сопоставление manual gate/Stars flags/visibility/groups/plans/SQLite errors без пользовательских IDs в GitHub.
- [#705](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/705): **OPEN/PARTIAL**. Сначала #730/#731 causal backend evidence, затем сверка оставшихся financial/entitlement postconditions и собственных acceptance criteria. Не повторять уже PASS E/H/G/M без нового доказанного риска.
- **V5-A-001…A-003 / G-11:** остаются `PARTIAL/NO-GO`, public rollout `BLOCKED`; independent VPS/image/SQLite/data-plane attestation отсутствует. Никаких дополнительных реальных оплат/refund/restart/deployment без отдельного согласования.

## Раздельные состояния

- **Merged:** реализация #743/#752 и публикационный #757 уже в main; этот docs-only checkpoint — только PR до отдельного merge.
- **Published:** PASS `v5.0.0-rc.16.5`, immutable GitHub tag SHA `0728b8466eb2c4c65f0a36a112ae5c4a3ea60cbc`.
- **Deployed:** operator-reported `rc.16.5` на тот же SHA, independent VPS attestation PENDING.
- **Accepted:** #743/#752 scoped operator-reported PASS; #730/#731/#705 OPEN, общий G-11 PARTIAL/NO-GO.
