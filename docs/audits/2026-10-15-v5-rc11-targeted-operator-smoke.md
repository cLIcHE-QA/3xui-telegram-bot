# v5.0.0-rc.11 — целевая проверка после развёртывания (2026-10-15)

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-15 22:29 UTC+03:00 (EEST), время получения отчёта оператора 2026-10-15T19:29:18Z; точное время выполнения каждого сценария не сообщалось
- **Окружение:** production Telegram bot, controlled v5 pilot, текущий релиз rc.11 со слов оператора; результаты ручного UI/smoke получены в приватном диалоге, прямого доступа исполнителя к VPS, Telegram, Master/Node Panel API, SQLite или Docker не было
- **Цель:** адресный postdeploy smoke rc.11: #648/#659/#663 Reality Flow, #649 восемь Cancel/Back, #650 Traffic, базовые контрольные проверки D1–D6; не подменять scoped PASS полным v5 G-11
- **Версия и immutable tag/SHA:** `v5.0.0-rc.11` / `5f0576417ef3274b92adefa0c9c0932c7a359fd5`; опубликованные [tag/Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.11) подтверждены GitHub; operator-reported `DEPLOY_OK` этого SHA зафиксирован в [deployment checkpoint](2026-10-15-v5-rc11-operator-deployment-checkpoint.md)
- **Scope:** оператор прислал результаты A1–A11, B1–B8, C1–C5, D1–D6. B1–B8, C1–C5, D1–D6 отмечены PASS; A2 вернул прямую диагностику `UNKNOWN` по Node #1, A6 — сообщение о не подтверждённых Master/Inbounds без изменений; A7/A8/A10 заблокированы A6. A1/A3/A4/A5/A9/A11 отмечены PASS, но у A4/A11 нет детального независимого Node/Xray evidence или способа выполнения опасного сценария A11
- **Фактический результат:** PARTIAL — operator-reported scoped PASS для B1–B8 (#649), C1–C5 (#650), D1–D6; в группе A шесть заявленных PASS, A2 `UNKNOWN`, A6 `BLOCKED`, A7/A8/A10 `BLOCKED`. #648/#659/#663 не закрыты, полное сравнение Master/Node Flow и address-scoped изменение не доказаны; G-11 остаётся `PARTIAL / CONDITIONAL / NO-GO`
- **Источник и evidence:** сообщение оператора 2026-10-15T19:29:18Z в приватном рабочем диалоге, содержащее A1–A11/B1–B8/C1–C5/D1–D6; [документационный PR #677](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/677), [GitHub Release rc.11](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.11), [deployment checkpoint](2026-10-15-v5-rc11-operator-deployment-checkpoint.md). Сырые Telegram/API/SQLite логи, screenshot и независимый VPS/image digest не предоставлены
- **Ограничения и остаточные риски:** A2 сообщает `🌐 Direct Node Panel API (read-only): ⚪ Node #1: UNKNOWN · Node inbound tag не найден/неоднозначен`; такое состояние не устанавливает MATCH/MISMATCH и не аттестует Xray. A6 `Master/Inbounds не подтверждены; изменений нет` — общий fail-closed ответ preflight; конкретная причина (shared client, inbound binding, upstream failure или другое) по нему не доказана. A4 PASS не устраняет A2 UNKNOWN; A11 PASS записан как заявление без описания способа проверки, повторный production reproducer/мутация не санкционированы этим отчётом. D2/D4 PASS — без самостоятельного SQL/backup evidence; isolated restore не проверялся. C5/B PASS — без независимых RBAC/side-effect traces; полные V5-A-001/002/003, ownership/rollback/reconciliation и W-01/02/03 не закрыты
- **Связанные Issues:** [#648](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/648) — OPEN/remaining PENDING; [#659](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/659) — OPEN/Node parity UNKNOWN; [#663](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/663) — OPEN/editor blocked; [#649](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/649) и [#650](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/650) — operator-reported targeted PASS, Issue closure audit после Roadmap sync в main PENDING
- **Следующий шаг:** завершить Roadmap/Issue checkpoint штатным PR, дождаться required `test`/`title`, затем только после отдельного merge approval — независимый `main` read-back и closure audit #649/#650. До любого нового production smoke провести read-only разбор exact tag matching Master ↔ Node и причины fail-closed preflight A6 на уже имеющихся обезличенных данных; не запускать опасный A11 reproducer, Flow POST, Stars, restart, restore или другие mutations без отдельного разрешения
- **Раздельные состояния:** merged=release-prep PR #674 / immutable commit `5f0576417ef3274b92adefa0c9c0932c7a359fd5`; published=tag/Release `v5.0.0-rc.11` GitHub 2026-10-15T17:40:22Z; deployed=operator-reported rc.11 `DEPLOY_OK` 2026-10-15T18:07:06Z, independent VPS/image attestation PENDING; accepted=#649/#650 и D1–D6 operator-reported scoped PASS, A partial/blocked, #648/#659/#663 remaining PENDING; overall v5 G-11 PARTIAL / NO-GO

## Полная матрица operator-reported проверки

| Сценарии | Сообщение оператора | Статус / значение для acceptance |
| --- | --- | --- |
| A1 | PASS | Flow Master и начальное «не проверено» заявлены корректными |
| A2 | `UNKNOWN` для Node #1: Node inbound tag не найден/неоднозначен | Нет доказанного node-side Flow MATCH/MISMATCH, Node Panel не равен Xray |
| A3 | PASS | Трёхсостоянийная классификация корректно оставляет UNKNOWN; полное сравнение не доказано |
| A4 | PASS | Заявлен отдельный результат без inbound-specific evidence; не отменяет A2 UNKNOWN |
| A5 | PASS | Заявлен безопасный legacy Flow sync UX; отсутствие фактического `bulkAdjust` независимо не аттестовано |
| A6 | `Master/Inbounds не подтверждены; изменений нет` | BLOCKED / preflight fail closed; конкретная причина неизвестна |
| A7, A8, A10 | `BLOCKED A6` | Не проверены значения/Cancel/адресная mutation; новых изменений не заявлено |
| A9 | PASS | `UNKNOWN`/fail-closed поведение заявлено корректным |
| A11 | PASS | Только операторская отметка; способ проверки и source/node evidence отсутствуют, опасный reproducer не повторять |
| B1–B8 (#649) | PASS по каждому из восьми маршрутов | operator-reported scoped PASS; не выполнять state-changing подтверждения |
| C1–C5 (#650) | PASS по каждому из пяти пунктов | operator-reported scoped PASS: Traffic, Refresh/Back, role-aware/error scenarios |
| D1–D6 | PASS по каждому из шести пунктов | operator-reported scoped PASS: portal baseline, schema/quick_check, health, backup/off-site доступность, pilot/Stars ограничения и обезличенный evidence; isolated restore не проверялся |

Этот отчёт не является разрешением закрывать Issues при незавершённом Roadmap sync и не повышает общий v5 acceptance. Если причины A2/A6 будут доказаны отдельной read-only проверкой, результат фиксируется новым audit, а не ретроспективной правкой текущего.
