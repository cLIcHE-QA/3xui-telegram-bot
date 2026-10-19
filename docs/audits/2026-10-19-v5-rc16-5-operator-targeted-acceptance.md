# v5.0.0-rc.16.5 — адресная операторская приёмка C3 и manual→manual

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-19 11:49 UTC+03:00 (EEST); исходные сообщения оператора 2026-10-19T08:18:31Z и 2026-10-19T08:33:37Z, итоговые ответы 2026-10-19T08:49:05Z.
- **Окружение:** production controlled pilot, Telegram/3x-ui/SQLite и deploy-helper **со слов оператора**; прямого доступа к VPS, image, SQLite или provider API в этом checkpoint нет.
- **Цель:** зафиксировать targeted acceptance P1–Z7 и последующий R1–R9 read-only checkpoint с сохранением разных уровней доказательности, не повторяя ранее принятые проверки `rc.16.4`.
- **Версия и immutable tag/SHA:** `v5.0.0-rc.16.5` / `0728b8466eb2c4c65f0a36a112ae5c4a3ea60cbc`; GitHub tag SHA независимо проверен, deployed SHA и runtime status — operator-reported.
- **Scope:** адресный P1–P2/C3.1–C3.4/S1–S6/Z6–Z7, позднее отмеченные R1–R9 (сравнение журналов, расследование B5 и closure audit) без новых payments/remote mutations.
- **Фактический результат:** PARTIAL — P/C3/S/Z пакет 14/14 PASS по сообщению оператора; R1–R9 отмечены выполненными, и 2026-10-19 11:49 EEST оператор уточнил R4: выдача **до** заказа (хронология MATCH по отчёту), R5–R6: выбран ручной тариф, что включает documented ручной purchase guard (B5 root cause operator-reported), R7–R8: «да» — согласованность ledger и критерии #705 подтверждены оператором. Raw read-only строки, SQL timestamps и machine evidence не предоставлены; Issues остаются OPEN до отдельного closure audit, G-11 PARTIAL/NO-GO.
- **Источник и evidence:** [GitHub Issue #730](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/730) и operator-reported сообщения 2026-10-19T08:18:31Z, 2026-10-19T08:33:37Z и 2026-10-19T08:49:05Z; оператор отметил все 14 пунктов чек-листа `P1,P2,C3.1–C3.4,S1–S6,Z6,Z7` как `[x]` 2026-10-19T08:18:31Z. Raw stdout, снимки/логи VPS и отдельная machine-readable provider attestation не приложены. [Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.16.5), [PR #753](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/753), [PR #754](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/754), [release PR #757](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/757), [publication audit](2026-10-19-v5-rc16-5-github-publication-checkpoint.md).

- **Ограничения и остаточные риски:** результаты R4, B5 и R7–R8 сообщены в краткой форме, без таймштампов SQLite и независимых DB/provider logs; валидность causal attribution и own Issue closure criteria оцениваются с provenance operator-reported, не independent attested. Не утверждать, что само наличие только `plan_id` без live `manual_entitlements` включает клиентский purchase guard: подтверждающий код проверяет именно live journal. Не перепроверять уже зачтённые сценарии ради отдельного evidence. #730/#731/#705 остаются OPEN до Issue closure checkpoint. Независимая VPS/DB/data-plane аттестация и общий G-11 PENDING; прежний C3 FAIL на rc.16.4 — исторический.
- **Связанные Issues:** #743, #752 (scoped PASS по отчёту), #730, #731, #705 (OPEN, результаты causal inquiry недостаточны), #470 (read-only Orders отдельно).
- **Следующий шаг:** результаты R4/R5–R8 уже сообщены, новых запросов оператору и новых production проверок не требуется. Дождаться required `test/title` PASS, отдельного разрешённого merge docs PR и `main` read-back; провести scoped Issue closure audit #730/#731/#705 (и #743/#752) по собранным operator evidence без provider mutations. План feature UX #760 — отдельный scope для rc.16.6.
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

## Финальные выводы по R1–R9 — 2026-10-19 11:49 UTC+03:00

**Источник:** сообщение оператора 2026-10-19T08:49:05Z после ранее отмеченных R1–R9 (2026-10-19T08:33:37Z). Это **уточнение результатов уже сделанных проверок**, а не новые тесты или GitHub-side read-only SQLite.

| Gate | Результат оператора | Интерпретация и provenance |
| --- | --- | --- |
| R4 / #730 | «до» — успешная ручная выдача была **до** создания `commerce_orders.awaiting_payment` | **MATCH / scoped operator-reported PASS** по хронологии: `begin_manual_entitlement` запрещает новую выдачу при уже существующем pending order, поэтому порядок не доказывает обход guard. Не считать проверенным численное SQL timestamp delta; записи не приложены |
| R5–R6 / #731 | «был выбран ручной тариф» | **Cause identified / operator-reported**: ранее существовавшая ручная выдача блокировала клиентский Stars purchase catalog; `customer_service.py:_plan_visible` проверяет именно `get_live_manual_entitlement` и fail-closes для `active/unknown/in_flight`. Если подтверждён только профильный plan, а не live journal, независимая причинная аттестация PENDING; отдельная повторная проверка не требуется |
| R7–R8 / #705 | «да» — ответ на запрос `MATCH/MISMATCH/UNKNOWN` и «Критерии #705 выполнены полностью: да/нет» | **MATCH и own scoped criteria fulfilled — operator-reported**. Не приравнивать к независимому 3x-ui/DB/finance evidence и не распространять на чужие scope (#336/#499/#507) или широкий G-11 |

**Итог пакета:** R1–R9 завершены по сообщению оператора; уточнения закрывают ранее невыясненные ответы, не добавляют production mutations. #730/#731/#705 требуют административного GitHub Issue closure audit с сохранением provenance и синхронизированным Roadmap, а не нового повтора M1–M8/H1–H6. Публичный rollout остаётся BLOCKED при G-11 PARTIAL/NO-GO.

## Остаточные gates и следующий шаг

- [#730](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/730): **OPEN / operator-reported scoped MATCH**: ручная выдача была до создания ожидающего заказа; старый M1–M8 smoke PASS. GitHub Issue closure/roadmap sync PENDING; новых grant/SQL операций не требуется.
- [#731](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/731): **OPEN / cause operator-reported**: был выбран ручной тариф, что при live manual grant блокирует покупку/каталог. H1–H6 PASS ранее; closure audit PENDING, никаких повторных B5 smoke и новых invoices.
- [#705](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/705): **OPEN / operator-reported MATCH и own criteria PASS** по R7–R8; scope не включает PSP #336/промокоды #499/варианты срока #507. Issue closure audit и Roadmap main sync PENDING, новых payment/grant проверок нет.
- **V5-A-001…A-003 / G-11:** остаются `PARTIAL/NO-GO`, public rollout `BLOCKED`; independent VPS/image/SQLite/data-plane attestation отсутствует. Никаких дополнительных реальных оплат/refund/restart/deployment без отдельного согласования.

## Раздельные состояния

- **Merged:** реализация #743/#752 и публикационный #757 уже в main; этот docs-only checkpoint — только PR до отдельного merge.
- **Published:** PASS `v5.0.0-rc.16.5`, immutable GitHub tag SHA `0728b8466eb2c4c65f0a36a112ae5c4a3ea60cbc`.
- **Deployed:** operator-reported `rc.16.5` на тот же SHA, independent VPS attestation PENDING.
- **Accepted:** #743/#752 scoped operator-reported PASS; #730/#731/#705 OPEN, общий G-11 PARTIAL/NO-GO.
