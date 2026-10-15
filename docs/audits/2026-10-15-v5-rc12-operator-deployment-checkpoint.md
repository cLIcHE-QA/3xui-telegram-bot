# v5.0.0-rc.12 — операторское подтверждение production deployment (2026-10-15)

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-15 23:59 UTC+03:00 (EEST), отчёт оператора получен 2026-10-15T20:59:01Z; точное время выполнения deployment не сообщалось
- **Окружение:** production Telegram bot, controlled v5 pilot; operator-reported deployment/health из приватного диалога, без независимого доступа исполнителя к VPS, container/image digest, SQLite, Master/Node 3x-ui или Telegram
- **Цель:** зафиксировать operator-reported deployment rc.12 на уже независимо опубликованном immutable release tag без автоматического подтверждения функциональной приёмки A2/A6/#679 или общего v5 gate
- **Версия и immutable tag/SHA:** `v5.0.0-rc.12` / `a88fd6947f04d40570413e792cda7150e738abbd`; GitHub [tag и Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.12) независимо подтверждены, published_at 2026-10-15T20:43:58Z, prerelease non-draft
- **Scope:** оператор прислал `DEPLOY_OK`, `Production=v5.0.0-rc.12`, совпадающий 40-символьный `GitSHA`, `APP_VERSION=5.0.0-rc.12`, git tag, `Container=running`, `RestartCount=0`, `Health=ok`, `DB=ok`, `3XUI_TCP=ok`, Docker subnet `172.19.0.0/16`, а также путь к pre-deploy backup. Приватный путь backup не публикуется; существование, integrity, off-site availability или restore не подтверждены независимо
- **Фактический результат:** PARTIAL — operator-reported deployment identity и baseline health PASS в предоставленном scope, Published tag/SHA PASS по независимому GitHub read-back; SQLite `PRAGMA quick_check`, image provenance, прямое Node Flow сравнение, preflight A6, navigation #679 и все более широкие acceptance gates ещё PENDING
- **Источник и evidence:** сообщение оператора 2026-10-15T20:59:01Z (приватный диалог); [release-prep PR #681](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/681), [Python checks](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38804031873) PASS, [Publish release](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38804276349) PASS, [GitHub Release rc.12](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.12), [publication audit](2026-10-15-v5-rc12-github-publication-checkpoint.md). Raw VPS/SQL/Xray read-back не предоставлены
- **Ограничения и остаточные риски:** `DB=ok` — не свидетельство `PRAGMA quick_check` или SQLite schema v13; TCP-connectivity — не Node API Flow и не Xray data-plane attestation. Backups только заявлены по пути; не проверены off-site, checksum или восстановление. #659 A2 на rc.11 давал UNKNOWN, #663 A6 BLOCKED, #679 навигация FAIL до исправления; rc.12 targeted smoke ещё не получен. #648 известный state-changing regression «снять тариф → назначить → Тариф + согласование» повторять без отдельного разрешения нельзя. Public launch, pilot expansion, Stars mutation, restart, restore или Flow POST не разрешаются этим audit
- **Связанные Issues:** [#648](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/648), [#659](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/659), [#663](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/663), [#679](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/679) — OPEN, rc.12 targeted acceptance PENDING. Ранее #649/#650 получили только operator-reported scoped PASS на rc.11; new rc.12 smoke не заявлен
- **Следующий шаг:** оператору дать bounded read-only/UI checklist: Flow Master и Node отдельно с `MATCH/MISMATCH/UNKNOWN`; точный `n<node_id>-` tag alias, A6 фиксированные коды fail-closed preflight без raw данных, #679 оба origin-aware Back/Refresh включая unknown/error, UI preview/Cancel без POST, затем SQLite quick_check, health/restars, backup availability и privacy/allowlist checks. Любые адресные Flow writes/A10, опасный reproducer A11, платежи/Stars, restore, reboot, provider mutation — только после отдельного approval. Отдельный dated acceptance audit после результатов, Issue closure только по доказанным критериям
- **Раздельные состояния:** merged=PR #681 SHA `a88fd6947f04d40570413e792cda7150e738abbd`; published=`v5.0.0-rc.12` immutable prerelease GitHub Release PASS; deployed=`v5.0.0-rc.12` operator-reported baseline 2026-10-15T20:59:01Z, independent VPS/image attestation PENDING; accepted=targeted rc.12 A2/A6/#679 PENDING, общий v5 G-11 PARTIAL / CONDITIONAL / NO-GO

## Матрица подтверждений

| Группа | Evidence | Scope status |
| --- | --- | --- |
| GitHub release provenance | Immutable tag SHA совпадает с merged PR #681, Release published | PASS — Published |
| Production tag/SHA/APP_VERSION | Прямой текстовый операторский отчёт, без VPS read-back | PASS operator-reported only |
| Container, health, DB, 3XUI TCP | `running`, restarts 0, Health/DB/TCP `ok` по отчёту | PASS operator-reported baseline only |
| Backup | Оператор указал путь pre-deploy backup, bytes/restore не аттестованы | PARTIAL / PENDING |
| SQLite schema v13, PRAGMA quick_check | Отдельного SQL evidence для rc.12 нет | PENDING |
| Node-side Flow #659/#648 | Новый прямой Master/Node read-only result не предоставлен | PENDING |
| Scoped Flow edit preflight #663 | Кода причины отказа, списка нод/вариантов на rc.12 ещё нет | PENDING |
| Navigation #679 | Origin-aware Back/Refresh UI smoke на rc.12 ещё нет | PENDING |
| B1–B8 #649 и C1–C5 #650 | Предыдущий rc.11 operator-reported scoped PASS, не новая rc.12 аттестация | Historical scoped PASS; rc.12 optional spot smoke PENDING |
| V5-A-001/002/003, ownership, rollback, reconciliation | Требуют отдельных gates/evidence | NOT PASS / G-11 NO-GO |

В этом checkpoint нет разрешения на дополнительные production mutations, merge, full rollout, Release или закрытие Issues.
