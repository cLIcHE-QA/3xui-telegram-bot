# GitHub publication checkpoint v5.0.0-rc.18.3 — 21.10.2026

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-21 11:52:37 UTC+03:00
- **Окружение:** GitHub API / GitHub Actions, read-only verification после штатной публикации
- **Цель:** проверить наличие immutable release tag, GitHub prerelease и успешных required checks без смешения публикации с production deployment
- **Версия и immutable tag/SHA:** `v5.0.0-rc.18.3` / `4b7785557097b6b71324e8f53e9504ad898e43c4`
- **Scope:** PR #841 squash MERGED в `main`, required `test`/`title` PASS, push `Python checks` SUCCESS, `Publish release` SUCCESS, отдельный REST read-back `refs/tags/v5.0.0-rc.18.3` и `releases/tags/v5.0.0-rc.18.3` с непустым русским title/body. VPS, runtime health, deployment, Telegram/3x-ui и targeted HWID acceptance не проверялись
- **Фактический результат:** PARTIAL — GitHub publication scoped PASS; production deployment и targeted acceptance PENDING
- **Источник и evidence:** [release-prep PR #841](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/841), [required test](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/39571713864), [required title](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/39572116230), [main push CI](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/39572181736), [Publish release](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/39572548919), [GitHub Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.18.3); independent tag SHA `4b7785557097b6b71324e8f53e9504ad898e43c4` совпал с squash merge SHA
- **Ограничения и остаточные риски:** нет нового VPS evidence, предыдущий `rc.18.2` Deployed только operator-reported; G-11 PARTIAL/NO-GO, full v5 NOT PASS, public rollout BLOCKED, independent X2/X1/X3 provenance PENDING. Не заявлен новый smoke, не проводились платежи или DELETE
- **Связанные Issues:** #827, #830, #833, #834, #838 (все OPEN до собственных критериев приёмки)
- **Решение по Issues:** #827: keep_open; #830: keep_open; #833: keep_open; #834: keep_open; #838: keep_open (релиз Published, но targeted deployment acceptance отсутствует)
- **Следующий шаг:** после отдельного разрешения на controlled production deployment зафиксировать точный deployed tag/SHA и провести безопасный targeted read-only HWID smoke каждого Issue, затем проверить scoped acceptance и Roadmap
- **Раздельные состояния:** merged=PR #841 / `4b7785557097b6b71324e8f53e9504ad898e43c4`; published=PASS / `v5.0.0-rc.18.3` / immutable SHA; deployed=PENDING для rc.18.3 (предыдущий rc.18.2 operator-reported); accepted=PENDING для #827/#830/#833/#834/#838, G-11 PARTIAL/NO-GO
