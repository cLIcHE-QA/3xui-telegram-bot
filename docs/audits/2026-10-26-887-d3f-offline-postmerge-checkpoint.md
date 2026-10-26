# #887 — D3f owner-bound URL disclosure: isolated post-merge checkpoint

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-26 17:06 Z (операторский D3f старт, фактическая GitHub проверка после merge; время CI отдельно в GitHub)
- **Окружение:** GitHub PR CI + independent GitHub main source read-back; D3f isolated/default-off synthetic tests, без live HTTPS/staging/production
- **Цель:** подтвердить fail-closed owner-scoped URL issuance после atomic one-use proof и отдельно задокументировать непройденные production/device gates
- **Версия и immutable tag/SHA:** exact head PR #923 `4a49672fdaa6e73d163d5911ddc0749fca557ef9`, squash main `48f11acb955da4542b6d6fc1a1a72343dfe1834d`; Published `v5.0.0-rc.19` без D3f
- **Scope:** отдельный `subscription_page_import_issuer.py` и default-off `/api/subpage/v1/import/preflight/deliver`, только доверенные D2a/D2b sessions, exact approved client/platform/version, CSRF, atomic SQLite proof burn, fresh owner `CustomerPortalService.subscription_card` вместо слабого `subscription_url(read_access=False)`, active/active, strict reviewed HTTPS origin, final session/feature recheck. Synthetic negative tests: IDOR, wrong client/Origin/CSRF, replay/concurrent consume, revoked/expired owner, provider exception, malicious/encoded control URLs, no-store
- **Фактический результат:** PARTIAL — code/source-only required checks PASS; **real issuance, device/staging and production acceptance PENDING**
- **Источник и evidence:** [PR #923](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/923), [Python checks run 40366842025](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40366842025), [final PR conventions run 40367411486](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40367411486), GitHub main/source read-back; post-merge push CI on squash SHA independently PENDING
- **Ограничения и остаточные риски:** shipping `delivery_enabled=false`, empty reviewed client catalog, no deployed URL route; provider URL is a bearer secret even with response `no-store`. Real TLS/SNI/Host/edge/no-access-log redaction, cross-worker D2a sessions, multi-host atomic ledger, real reviewed client/version, Copy/QR and physical iOS/Android/Telegram WebView smoke PENDING; G-11 NO-GO
- **Связанные Issues:** #887 OPEN/keep_open, #885 OPEN/keep_open independently, #473/#497 OPEN pending their own acceptance
- **Следующий шаг:** провести targeted offline security review of URL disclosure and edge topology, reviewed real client/version allowlist and session/ledger scope; отдельно разрешить isolated staging + device smoke до любого public deployment, затем gated Copy/QR
- **Раздельные состояния:** merged=PR #923 squash `48f11acb955da4542b6d6fc1a1a72343dfe1834d`; published=`v5.0.0-rc.19` без D3f; deployed=`v5.0.0-rc.18.10` operator-reported, independent VPS read-back PENDING; accepted=offline scoped PASS, real importer/G-11 PENDING/NO-GO

## Решение по Issues

- **#887: keep_open.** D3f только source-only / explicit opt-in factory; real client versions, Copy/QR, trusted edge and staging devices PENDING. Отдельный runtime security review + post-merge Roadmap checkpoint обязателен.
- **#885: keep_open.** HTTPS handoff и draft PR #886 независимы от D3f; acceptance не доказан.
