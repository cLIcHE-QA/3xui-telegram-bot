# v5.0.0-rc.10 — targeted post-deploy acceptance #627/#628 (2026-10-15)

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-15 12:52 UTC+03:00 (EEST, время получения итогового сообщения оператора 2026-10-15T09:52:57Z; точное время отдельных smoke-сценариев не сообщалось; deployment output получен 2026-10-14T19:48:49Z)
- **Окружение:** production bot, ограниченный v5 pilot, только обезличенный operator-reported deployment/status и итоговый smoke; прямого VPS/Telegram/SQLite/API доступа для независимого read-back не было
- **Цель:** operational closure immutable release v5.0.0-rc.10 и scoped acceptance UI fixes #627 (трёхсостоянийная диагностика expiry) и #628 (owner-scoped Stars/refund + manual payment history), без ложного повышения общего G-11
- **Версия и immutable tag/SHA:** `v5.0.0-rc.10` / `ef7e655fed6818053ceff1818b64a852c83638ec`, GitHub tag/release подтверждены; release-prep [PR #644](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/644)
- **Scope:** подтверждены release/deployment identity, running/restart/health, DB и 3x-ui, SQLite quick_check/schema v13, исходы #627 MATCH/insufficient/mismatch и navigation/no mutation, #628 две независимые истории/возвраты/owner isolation/back/no mutation, повторный health, Full Backup/off-site aggregate PASS и отсутствие заявленных discrepancies; не выполнялись самостоятельно новые Stars purchases/refunds, provider writes, forced outages, isolated DR restore или full v5 canary acceptance
- **Фактический результат:** PASS — targeted release/deploy/smoke в заявленном оператором scope; все строки его отчёта PASS, discrepancies none reported; независимая VPS/data-plane аттестация не представлена, весь v5 G-11 остаётся PARTIAL / CONDITIONAL / NO-GO
- **Источник и evidence:** итоговое сообщение оператора 2026-10-15T09:52:57Z и deploy/status output 2026-10-14T19:48:49Z в приватном рабочем диалоге; [immutable GitHub Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.10), [post-merge Python checks](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38625491972), [Publish release](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38625748104), [#627](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/627), [#628](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/628); приватные IDs, backup paths, URLs и credentials не публикуются
- **Ограничения и остаточные риски:** нет самостоятельного VPS/image read-back, сырых SQL/3x-ui logs, идентификаторов тестовых аккаунтов или точных timestamp по каждому UI-случаю; operator-reported PASS не равен независимому proof. Full Backup/off-site отмечен оператором PASS агрегированно, но отдельный isolated restore и будущий scheduled cycle этим не доказаны. Полные V5-A-001/002/003, recovery/soak, DR, G-01…G-08/G-10 PARTIAL и W-01/02/03 не переводятся в PASS. #433 deferred, legal #436 не завершён; public/stable/allowlist expansion BLOCKED
- **Связанные Issues:** #627 — ранее CLOSED/completed на release merge, теперь подтверждён targeted smoke; #628 — OPEN до отдельного issue closure checkpoint по собственным критериям; #433 — OPEN/DEFERRED, не в rc.10; общий G-11 остаётся PARTIAL / NO-GO
- **Следующий шаг:** docs PR с required `test`/`title` и независимым `main` read-back, затем closure audit #628 и отдельная сверка OPEN Issue-реестра; глобальную V5-A-001…003 приёмку не расширять без отдельного разрешения оператора
- **Раздельные состояния:** merged=release PR #644 squash `ef7e655fed6818053ceff1818b64a852c83638ec`; published=immutable `v5.0.0-rc.10` tag same SHA, 2026-10-14T19:41:35Z, workflow PASS; deployed=operator-reported production PASS on 2026-10-14T19:48:49Z, independent VPS/image attestation PENDING; accepted=#627/#628 targeted smoke operator-reported PASS (report 2026-10-15T09:52:57Z), entire v5 G-11 PARTIAL/NO-GO

## Обезличенная матрица наблюдений

| Проверка | Сообщено оператором | Статус только этого scope |
| --- | --- | --- |
| Deployment identity | `Production=v5.0.0-rc.10`, `APP_VERSION=5.0.0-rc.10`, immutable SHA совпал с GitHub tag | PASS operator-reported + GitHub provenance |
| Baseline / initial health | `DEPLOY_OK`, container running, `RestartCount=0`, Health/DB/3XUI_TCP `ok`, subnet `172.19.0.0/16`, pre-deploy backup создан | PASS operator-reported |
| SQLite | `quick_check` и schema v13 | PASS operator-reported |
| #627 expiry evidence | `MATCH`, `insufficient_data`, `mismatch` различимы; provider/expiry cases в заявленном targeted scope | PASS operator-reported; offline regression CI PASS |
| #627 navigation / read-only | `Refresh`, `Back`, no mutation | PASS operator-reported |
| #628 ledger separation | Stars (XTR) и ручные платежи отдельно | PASS operator-reported |
| #628 refund / ownership | Refund history, owner isolation, Back | PASS operator-reported; owner-scoped SQL/unit tests CI PASS |
| #628 financial safety | Нет financial mutations от просмотра | PASS operator-reported |
| Post-smoke health | Повторный health | PASS operator-reported |
| Backup | Full Backup / off-site | PASS operator-reported aggregated; independent restore NOT TESTED |
| Findings | «none reported yet» | Нет заявленных замечаний, не доказательство отсутствия всех потенциальных ошибок |

## Граница приёмки и действие по Issues

Это отдельная приёмка изменений `rc.10`, а не завершение всех V5-A-001…003. Опубликованный tag не перемещался. Исторические FAIL/waivers остаются в прежних audits; production не изменялась при подготовке этого documentation checkpoint. Для #627/#628 не нужны новые real-money payments/refunds, искусственный provider outage или манипуляции сроками ради закрытия read-only багов. Для #628 зафиксированы CI и operator-reported targeted PASS исходного дефекта; окончательный `CLOSED/completed` возможен после предусмотренного Issue closure audit и последующей синхронизации Roadmap.
