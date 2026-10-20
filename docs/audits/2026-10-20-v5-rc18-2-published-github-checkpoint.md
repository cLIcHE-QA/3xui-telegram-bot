# v5.0.0-rc.18.2 — GitHub prerelease publication checkpoint

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-20 21:42 UTC+03:00.
- **Окружение:** GitHub read-only REST, Actions release workflow; production VPS/Telegram не затрагивались.
- **Цель:** удостоверить штатную публикацию `v5.0.0-rc.18.2` и отделить Published от Deployed/Accepted.
- **Версия и immutable tag/SHA:** `v5.0.0-rc.18.2` — immutable tag `20205a56887cbdf644f604febdd9eb9ac717b914`; previous deployed tag `v5.0.0-rc.18.1` — `7b3cd54e41246212c6313b815e571d180e5a4475`.
- **Scope:** release-prep [PR #824](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/824) MERGED `20205a56887cbdf644f604febdd9eb9ac717b914`; [main push Python checks](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/39476667012) SUCCESS; [Publish release](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/39477041117) SUCCESS; [GitHub prerelease](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.18.2) `prerelease=true`, `draft=false`, published `2026-10-20T18:42:25Z`; tag, release и main имеют одинаковый SHA. Подготовка release scope #821 — HWID VPN-client, реальные macOS emoji, admin pagination 8 и client 5; SQLite v15/3x-ui pinned contract неизменны. VPS rollout/production smoke не проводились.
- **Фактический результат:** PARTIAL
- **Источник и evidence:** независимое чтение [GitHub Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.18.2), [tag ref](https://github.com/cLIcHE-QA/3xui-telegram-bot/tree/v5.0.0-rc.18.2), [PR #824](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/824) и [Publish run](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/39477041117).
- **Ограничения и остаточные риски:** Publication scoped PASS; deployment `rc.18.2` **не выполнен и не подтверждён**. Production остаётся `rc.18.1` по операторскому сообщению с targeted A4/A5 FAIL; B1–B3 provenance/independent VPS read-back PENDING; #814/#816/#820/#471/#472 remain OPEN/keep_open. G-11 PARTIAL/NO-GO, public rollout BLOCKED. Не повторять опасные DELETE/Stars/restore/restart для проверки публикации.
- **Связанные Issues:** #814, #816, #820, #471, #472.
- **Решение по Issues:** #814: keep_open; #816: keep_open; #820: keep_open; #471: keep_open; #472: keep_open.
- **Следующий шаг:** только после отдельного разрешения на production deploy выполнить backup/health/DB/3x-ui preflight, обновление на immutable `v5.0.0-rc.18.2`, `--status` и целевой read-only smoke A4/A5, macOS icon, admin 8/client 5, Back/ownership; собрать безопасный provenance и post-smoke health. До этого не закрывать Issues.
- **Раздельные состояния:** merged=#824 SHA `20205a56887cbdf644f604febdd9eb9ac717b914`; published=`v5.0.0-rc.18.2` GitHub immutable tag/Release PASS; deployed=`v5.0.0-rc.18.1` operator-reported, `rc.18.2` NOT Deployed; accepted=`rc.18.1` targeted A4/A5 FAIL и `rc.18.2` PENDING, full v5 NOT PASS.
