# GitHub Published checkpoint v5.0.0-rc.16.4 — 2026-10-18

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-18 20:30 UTC+03:00
- **Окружение:** GitHub read-only; CI (не VPS)
- **Цель:** подтвердить штатный release-prep merge, immutable `v5.0.0-rc.16.4` и публикацию GitHub prerelease отдельно от production deployment/acceptance
- **Версия и immutable tag/SHA:** `v5.0.0-rc.16.4` / `114de5af16adcde5e8d128cc5a55d58addc37e73`
- **Scope:** GitHub PR #749 Merged, required `test`/`title` PASS, push `Python checks` PASS, `Publish release` `prepare`/`publish` PASS, GitHub tag ref и Release title/body/prerelease read-back; production VPS/SQLite/Telegram/3x-ui live не проверялись
- **Фактический результат:** PASS — только GitHub Published/pre-release scope; Deployed/Accepted rc.16.4 PENDING
- **Источник и evidence:** [PR #749](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/749) merged `114de5af16adcde5e8d128cc5a55d58addc37e73`; [push CI #39149703923](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/39149703923) PASS; [Publish release #39149899084](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/39149899084) `prepare`/`publish` PASS; [immutable prerelease](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.16.4) опубликован `2026-10-18T17:30:44Z`; tag `refs/tags/v5.0.0-rc.16.4` независимо совпал с merge SHA
- **Ограничения и остаточные риски:** `rc.16.4` не Deployed, targeted Telegram/3x-ui/SQLite smoke и финальный health не выполнялись; последнее Deployed `rc.16.3` только operator-reported, independent VPS/image/DB attestation PENDING; #705/#731 и M1–M8 не закрыты, G-11 PARTIAL/NO-GO, public rollout BLOCKED
- **Связанные Issues:** #730, #740, #742, #743, #744, #745 (OPEN, собственные acceptance criteria остаются PENDING)
- **Следующий шаг:** только после отдельного разрешения — controlled deployment по immutable `rc.16.4`, `--status`, независимые/операторские read-back и targeted pilot smoke #730/#740/#742–#745; затем Issue closure audit и Roadmap checkpoint по доказанному outcome
- **Раздельные состояния:** merged=PASS (PR #749, `114de5af16adcde5e8d128cc5a55d58addc37e73`); published=PASS (`v5.0.0-rc.16.4` prerelease, tag SHA тот же); deployed=PENDING (`rc.16.4`, текущий `rc.16.3` operator-reported); accepted=PENDING (`rc.16.4`, G-11 PARTIAL/NO-GO)
