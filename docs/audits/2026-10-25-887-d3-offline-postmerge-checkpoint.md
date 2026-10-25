# #887 — D3a/D3b offline post-merge checkpoint

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-25 22:17 UTC (CI checkpoint)
- **Окружение:** GitHub Actions CI, offline synthetic source-only
- **Цель:** проверить scoped D3a capability policy и D3b default-off preview до merge
- **Версия и immutable tag/SHA:** main после #912 `5f47b9f270b52213f386c81f3e533ce13511843e`; Published `v5.0.0-rc.19` без D3
- **Scope:** D3a TypeScript planner и Node tests, D3b inert React preview, compile-time feature flag default-off; не проверялись реальные VPN clients, ссылки, QR, Copy, deeplink, Telegram WebView, DNS/TLS, device smoke, production
- **Фактический результат:** PASS только для scoped pre-merge CI; D3 end-to-end **PENDING**, G-11 **PARTIAL/NO-GO**
- **Источник и evidence:** [PR #911](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/911) head `e6696e4fa9cf6d40eb0a71e84fda9f3711dabbd0`, squash `0188093380e82c6fce4cb05a6daacd1c0be21fa0`; [PR #912](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/912) head `0e673e43135166161771e837028768585392947c`, squash `5f47b9f270b52213f386c81f3e533ce13511843e`; оба required `PR conventions`, `Python checks`, `Subscription Page D1a checks` PASS на exact heads. Post-merge push CI PENDING independent evidence.
- **Ограничения и остаточные риски:** отсутствие reviewed client/version allowlist, owner-bound URL issuance, real Copy/QR and app launch, targeted device/WebView acceptance, isolated staging и VPS read-back
- **Связанные Issues:** #887 — **keep_open**: D3 real import и G-11 gates PENDING
- **Следующий шаг:** D3c scoped capability allowlist и безопасная owner-bound выдача URL, только после Roadmap merged/read-back; live pilot отдельно
- **Раздельные состояния:** merged=#911/#912; published=rc.19 без D3; deployed=rc.18.10 operator-reported; accepted=offline CI scoped PASS, D3 end-to-end PENDING

## Issue closure decision

- **#887: keep_open** — D3a/D3b только offline CI, реальная выдача URL/Copy/QR и device/WebView acceptance не пройдены; следующий шаг D3c и staging security/device smoke, затем новый Roadmap checkpoint.
