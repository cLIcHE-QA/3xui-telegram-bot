# Закрытие Issue #609 — документация и защита audit evidence

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-13 23:29 UTC+03:00 (EEST; GitHub Actions UTC timestamps в evidence)
- **Окружение:** protected GitHub main, PR required/postmerge CI, offline regression; не production
- **Цель:** подтвердить завершение stale rc.8/rc.9 docs, согласование Living Docs, fail-closed удаления датированных audits, pagination теста и логов GitHub checker
- **Версия и immutable tag/SHA:** source main `75d367048378cceda5ef9b3680b3ce6212546739` after PR #610; Published v5.0.0-rc.9 immutable tag `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`
- **Scope:** README, CLIENT_SETUP, EXTERNAL_PAYMENT_LINKS, LIVING_DOCS, check-roadmap-governance.py (ACMRD, deletion ban), check-roadmap-github.py (active_issues count), deterministic offline regression second page with 100 response items including pull_request objects; Roadmap Issue status and acceptance invariants. VPS/Telegram/real payment/production/release/deploy не проверялись
- **Фактический результат:** PASS — #609 own docs/CI scope; initial PR test FAIL only for stale historical rc.8 assertion, corrected before final required/postmerge CI; Issue CLOSED/completed. Не full v5 acceptance
- **Источник и evidence:** [Issue #609](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/609), [PR #610](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/610), required [Python #38462273731](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38462273731), required [PR conventions #38462641821](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38462641821), postmerge [Python #38462707346](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38462707346), original test FAIL [#38461948481](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38461948481)
- **Ограничения и остаточные риски:** weekly scheduled Roadmap GitHub reconciliation не наблюдался; published и operator-reported deployed rc.9 не доказывают independent build/VPS attestation. Результаты #609 не покрывают G-09 natural expiry, D1 second snapshot, G-11 final acceptance
- **Связанные Issues:** #609 CLOSED/completed после own acceptance/CI; #605 CLOSED/completed previous full GitHub reconciliation, no reopening
- **Следующий шаг:** docs-only closure PR с required test/title, squash merge, independent main/Issues read-back и проверкой 31 открытого Issue в реестре; продолжить G-09 и D1 в ранее согласованном порядке
- **Раздельные состояния:** merged=main `75d367048378cceda5ef9b3680b3ce6212546739`; published=v5.0.0-rc.9 immutable tag `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; deployed=rc.9 operator-reported, independent VPS attestation PENDING; accepted=overall v5 NOT PASS
