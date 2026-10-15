# v5.0.0-rc.13 — публикация GitHub prerelease (2026-10-16)

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-16 01:02 UTC+03:00 (EEST), GitHub `published_at=2026-10-15T22:02:32Z`; одобрение merge оператором 2026-10-15T21:58:26Z
- **Окружение:** GitHub repository, protected main и release automation; production VPS не трогали
- **Цель:** подтвердить merge release-prep #684, provenance опубликованного prerelease и строго отделить от Deployed/Accepted
- **Версия и immutable tag/SHA:** `v5.0.0-rc.13`, `fbe2cafc3ace3aa54ec2398ddf5ec15cb0c4e9f5` (GitHub main ref == tag ref == release-prep merge SHA)
- **Scope:** [PR #684](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/684) после required `test/title` PASS squash merged; [post-merge Python checks](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38814071258) PASS; [Publish release](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38814292814) prepare/publish PASS; release non-draft prerelease с непустыми canonical notes
- **Фактический результат:** PASS только GitHub `Merged` и `Published`; production Deployed `rc.13` PENDING, acceptance нового кода A6 PENDING
- **Источник и evidence:** независимый GitHub REST GET refs/heads/main, refs/tags/v5.0.0-rc.13, releases/tags/v5.0.0-rc.13, Actions runs #38814071258/#38814292814, PR #684; production read-back отсутствует
- **Ограничения и остаточные риски:** Production остаётся `v5.0.0-rc.12` по последнему operator-reported deploy. `rc.13` уточняет категорию старого `CLIENT_RECORD`, но не исправляет непроверенные поля Master автоматически; никаких client/Node/Flow mutations не выполнять. A6/N6/R3 BLOCKED до live read-only diagnosis и отдельного доказанного исправления; v5 G-11 PARTIAL / CONDITIONAL / NO-GO; stable/public rollout BLOCKED
- **Связанные Issues:** [#663](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/663) OPEN, [#648](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/648), [#659](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/659), [#679](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/679) OPEN
- **Следующий шаг:** после отдельного operator approval deployed именно immutable `v5.0.0-rc.13`, только targeted `✏️ Изменить Flow` read-only preflight A6.1/A6.2 и сообщить безопасный код `CLIENT_RECORD_MISSING/NULL/PROTOCOL/REVERSE` или иной фиксированный результат. Без разрешения не выполнять Flow POST/A10, тарифный #648 reproducer, restart/restore/rollout
- **Раздельные состояния:** Merged=PR #684 `fbe2cafc3ace3aa54ec2398ddf5ec15cb0c4e9f5` PASS; Published=`v5.0.0-rc.13` immutable prerelease PASS; Deployed=`v5.0.0-rc.12` только operator-reported; Accepted=rc.13 targeted PENDING, G-11 NO-GO
