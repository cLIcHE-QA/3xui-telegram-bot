# v5.0.0-rc.11 — операторское подтверждение развёртывания (2026-10-15)

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-15 21:07 UTC+03:00 (EEST), время получения сообщения оператора 2026-10-15T18:07:06Z; точное время выполнения deployment не сообщалось
- **Окружение:** production bot, controlled v5 pilot; сведения о deployment/health получены из приватного отчёта оператора, без прямого доступа к VPS, Docker, Telegram, SQLite или 3x-ui
- **Цель:** независимо сверить Published tag/SHA в GitHub и документировать операторский baseline Deployed `rc.11` отдельно от не выполненных targeted runtime checks
- **Версия и immutable tag/SHA:** `v5.0.0-rc.11` / `5f0576417ef3274b92adefa0c9c0932c7a359fd5`; GitHub tag и [Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.11) подтверждены; release-prep [PR #674](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/674)
- **Scope:** оператор прислал `DEPLOY_OK`, `Production=v5.0.0-rc.11`, совпадающий `GitSHA`, `APP_VERSION=5.0.0-rc.11`, `Container=running`, `RestartCount=0`, `Health=ok`, `DB=ok`, `3XUI_TCP=ok`, Docker subnet и путь к созданному pre-deploy backup. Значения внутренней сети и приватный путь backup намеренно не публикуются; backup integrity/restore не проверялись
- **Фактический результат:** PASS — только для operator-reported deployment identity и health baseline при подтверждённом GitHub Published tag/SHA; **targeted `rc.11` acceptance PENDING**, общий v5 G-11 `PARTIAL / CONDITIONAL / NO-GO`
- **Источник и evidence:** сообщение оператора 2026-10-15T18:07:06Z (приватный рабочий диалог; independent VPS proof отсутствует), [GitHub Release rc.11](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.11), [release-prep PR #674](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/674), [последний Roadmap checkpoint PR #676](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/676)
- **Ограничения и остаточные риски:** независимые VPS/image digest/read-back и фактическое состояние Xray/direct Node отсутствуют; `DB=ok` не доказывает `PRAGMA quick_check` или SQLite schema v13 для этого deployment; `3XUI_TCP=ok` не доказывает Flow parity. Full Backup/off-site после rc.11, целостность rollback-копии, UI/Node smoke и health после этих проверок ещё не сообщены. Не подтверждены фактические настройки pilot flags; не расширять allowlist, не менять Stars/refund semantics
- **Связанные Issues:** [#648](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/648), [#649](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/649), [#650](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/650), [#659](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/659), [#663](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/663); все остаются OPEN до собственных targeted acceptance criteria
- **Следующий шаг:** после docs-only PR, required CI `test`/`title` и merge с независимым `main` read-back — согласовать bounded read-only Flow #659/#648, UI navigation #649, Traffic #650, health/SQLite/backup checks; #663 state-changing confirmation, тарифный reproducer #648 и любые Stars/provisioning mutations — только после отдельного разрешения. Для каждого результата необходимы timestamp/TZ, source, expected/actual, scope и PENDING
- **Раздельные состояния:** merged=release-prep PR #674 / immutable release commit `5f0576417ef3274b92adefa0c9c0932c7a359fd5`; published=`v5.0.0-rc.11` same tag SHA, 2026-10-15T17:40:22Z, GitHub Release; deployed=operator-reported production baseline 2026-10-15T18:07:06Z (время отчёта), independent VPS/image attestation PENDING; accepted=только deployment/health baseline `PASS` со слов оператора, targeted Issues `PENDING`, общий v5 G-11 PARTIAL / NO-GO

## Матрица deployment baseline и отсутствующего acceptance

| Проверка | Evidence | Результат |
| --- | --- | --- |
| Tag/SHA release | Независимый GitHub tag/Release read-back | PASS Published |
| Deployed image identity | `Production`, `APP_VERSION`, `GitSHA` совпадают в отчёте оператора | PASS operator-reported; independent VPS/image attestation PENDING |
| Running/health | `DEPLOY_OK`, running, restarts 0, Health/DB/3XUI_TCP ok | PASS operator-reported baseline |
| Pre-deploy backup | Оператор сообщил путь созданной копии; содержимое/restore не проверяли | PARTIAL: path reported, integrity/restore PENDING |
| SQLite schema/quick_check и post-smoke health | Для rc.11 отдельных результатов нет | PENDING |
| Reality Flow Master/Node #648/#659 | Нет direct Node API/Xray read-back после deploy | PENDING |
| Адресный выбор и mutation Flow #663 | Нет read-only UI evidence или отдельно разрешённой state-changing проверки | PENDING |
| Навигация Admin UI #649 (8 сценариев), Traffic #650 | Нет Telegram live результатов на rc.11 | PENDING |
| V5-A-001/002/003, ownership, rollback, reconciliation | Нет нового общего evidence; ранее задокументированные исключения сохраняются | PENDING / G-11 NO-GO |

При последующих targeted проверках не запускать небезопасный live reproducer с переснятием тарифа, `bulkAdjust`, прямые Node mutations, реальные Stars purchases/refunds, restart/restore без отдельного разрешения. Этот audit не является разрешением на production операции и не закрывает Issues.
