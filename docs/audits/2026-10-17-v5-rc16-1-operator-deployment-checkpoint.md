# v5.0.0-rc.16.1 — операторский deployment checkpoint (2026-10-17)

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-17 08:27 UTC+03:00 (EEST); сообщение о deployment получено 2026-10-17T05:27:19Z, результат отдельного `--status` — 2026-10-17T05:34:10Z; точное время завершения deployment отдельно не зафиксировано
- **Окружение:** production Telegram bot, controlled v5 pilot; operator-reported stdout `deploy-release.sh` в приватной беседе; прямого доступа к VPS, Docker, Telegram, SQLite или upstream 3x-ui у исполнителя нет
- **Цель:** подтвердить по отчёту оператора успешное deployment immutable `v5.0.0-rc.16.1` и разграничить baseline deployment от ещё не проведённой функциональной приёмки тарифов #705
- **Версия и immutable tag/SHA:** `v5.0.0-rc.16.1` / `31401e81e3f02d1220fc55a55eb8e3b3d61499a0`; [GitHub Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.16.1) и tag SHA независимо подтверждены; release-prep [PR #716](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/716)
- **Scope:** оператор сообщил `DEPLOY_OK`, `Production=v5.0.0-rc.16.1`, совпадающие `GitSHA`/`APP_VERSION`, `DB=ok`, `3XUI_TCP=ok`, subnet `172.19.0.0/16`, `RestartCount=0` и путь к pre-deploy backup. Штатный `deploy-release.sh` печатает `DEPLOY_OK` только после собственного health-поллинга, версии контейнера и проверок DB/TCP/subnet; затем отдельно получен полный `./scripts/deploy-release.sh --status`: Git tag `v5.0.0-rc.16.1`, Git SHA `31401e81e3f02d1220fc55a55eb8e3b3d61499a0`, `Container: running`, `RestartCount=0`, `Bot version: 5.0.0-rc.16.1`, `Health: ok`, `DB: ok`, `Docker subnet: 172.19.0.0/16`, `3x-ui connectivity: ok`. Независимого VPS/image/SQLite/Xray read-back у исполнителя нет. Приватный путь к backup намеренно не публикуется
- **Фактический результат:** PARTIAL — operator-reported deployment и встроенные post-deploy baseline checks PASS в указанном объёме; Published tag/SHA PASS по независимому GitHub; отдельный операторский `--status` PASS; schema v14/journal, Telegram/UI и 3x-ui read-back, фактическая выдача тарифа и post-smoke health — PENDING
- **Источник и evidence:** отчёт оператора 2026-10-17T05:27:19Z (приватная беседа без raw VPS API evidence), [PR #714](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/714) с исправлениями #705, [PR #716](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/716), [публикация GitHub Actions](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38983982658) PASS и [GitHub Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.16.1). Отдельный operator-reported `--status` 2026-10-17T05:34:10Z получен; raw SQLite schema journal и 3x-ui/Telegram evidence не получены
- **Ограничения и остаточные риски:** `3XUI_TCP=ok` проверяет сетевое соединение, но не подтверждает API provisioning или достижение пользовательских лимитов. `DB=ok` в штатном deploy и отдельном `--status` основано на `PRAGMA quick_check`, однако это операторский вывод и не отдельное подтверждение применения bot schema v14. Наличие пути к backup не подтверждает его bytes, integrity, off-site и restore. Telegram Back/Cancel, User Groups visibility, ручная бессрочная выдача, назначение обычного тарифа с 3x-ui read-back, safety инварианты `unknown` и журнал оплат/Stars не проверены на production. Ранее локальный скрипт из старого checkout не принимал `rc.N.M`; повторный запуск скрипта из подтверждённого immutable tag завершился `DEPLOY_OK`
- **Связанные Issues:** [#705](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/705) — OPEN; [#691](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/691) — OPEN; общий v5 G-11 остаётся PARTIAL/NO-GO
- **Следующий шаг:** после подтверждённого оператором `--status` выполнить ограниченную read-only сверку SQLite schema v14 + журнал migration и безопасный targeted Telegram/UI smoke тарифов, не создавая реальных Stars/RUB платежей и не выполняя manual grant/provider mutation без отдельного разрешения. Закончить повторной проверкой health; Issue закрывать только по его собственным доказанным acceptance criteria
- **Раздельные состояния:** merged=PR #714 / PR #716, release SHA `31401e81e3f02d1220fc55a55eb8e3b3d61499a0`; published=`v5.0.0-rc.16.1`, immutable prerelease PASS; deployed=operator-reported `v5.0.0-rc.16.1` baseline и отдельный `--status` PASS (сообщения 2026-10-17T05:27:19Z и 2026-10-17T05:34:10Z), independent VPS/image attestation PENDING; accepted=targeted #705/#691 PENDING, G-11 PARTIAL/NO-GO

## Матрица проверки

| Проверка | Evidence | Итог |
| --- | --- | --- |
| Published tag и commit | GitHub tag/release read-back, SHA совпадает с release-prep PR #716 | PASS |
| Deployment identity | `DEPLOY_OK`, версия и SHA из отчёта оператора | PASS — operator-reported |
| Health/DB/3XUI_TCP, subnet, restarts | Штатный post-deploy script и отдельный operator-reported `--status` 2026-10-17T05:34:10Z; `Health/DB/3x-ui connectivity=ok`, subnet совпал, restarts 0 | PASS — operator-reported, independent VPS/image attestation PENDING |
| Backup | Путь pre-deploy backup сообщён приватно, содержимое/restore не проверены | PARTIAL |
| Schema v14 и миграционный журнал | Новый `DB=ok` не показывает `schema_migrations.version` | PENDING |
| Тарифы #705 | Нет post-deploy UI/backend read-back и проверки безопасной выдачи | PENDING |
| Flow UI #691 и общий G-11 | Нет нового targeted smoke для текущего release | PENDING / NO-GO |

Этот checkpoint не разрешает новые production mutations, платежи, refund, restore, restart, расширение pilot или общий v5 rollout.
