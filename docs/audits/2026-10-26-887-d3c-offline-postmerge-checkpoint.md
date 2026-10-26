# #887 — D3c offline capability-evidence post-merge checkpoint

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-26 07:23 Z (операторское разрешение на merge; GitHub read-back после merge, точное время отдельно не установлено)
- **Окружение:** GitHub Actions, source-only offline/synthetic D3c
- **Цель:** проверить fail-closed capability evidence до использования real subscription URLs
- **Версия и immutable tag/SHA:** main squash PR #915 `4e830428661a4b35ba7ac161afe0b8ce0e631554`; Published `v5.0.0-rc.19` без D3c
- **Scope:** TypeScript reviewed capability resolver с пустым shipping allowlist, exact client/version/platform, duplicate/malformed/unknown evidence rejection, WebView no-handoff и synthetic Node regression tests; без server-side owner proof, выдачи URL, Copy/QR/deeplink и device/live staging
- **Фактический результат:** PARTIAL — exact-head CI PASS; real D3c import и G-11 PENDING/NO-GO
- **Источник и evidence:** [PR #915](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/915), head `281652b71ada2c3611746aef1568523359fb2b0c`, squash `4e830428661a4b35ba7ac161afe0b8ce0e631554`; required `PR conventions`, `Python checks`, `Subscription Page D1a checks` PASS на exact head; post-merge push CI PENDING
- **Ограничения и остаточные риски:** shipping allowlist empty; review ID не заменяет независимую attestation; нет owner-bound subscription delivery, реальных Copy/QR, client/device/WebView smoke, isolated staging, VPS read-back
- **Связанные Issues:** #887 keep_open, #885 keep_open; нельзя закрывать по offline CI
- **Следующий шаг:** reviewed client/version evidence, server-side owner-bound URL issuance и targeted Copy/QR/WebView smoke только с соответствующими security gates; staging подготовить отдельно
- **Раздельные состояния:** merged=#915; published=rc.19 без D3c; deployed=rc.18.10 operator-reported; accepted=offline scoped PASS, end-to-end PENDING

## Issue closure decision

- **#887: keep_open** — D3c foundation-only, empty allowlist и отсутствующие owner-bound URL/Copy/QR/device acceptance; следующий шаг — gated integration и новый Roadmap checkpoint.
- **#885: keep_open** — отдельный HTTPS handoff PR #886 не заменяется D3c; его собственная приёмка PENDING.
