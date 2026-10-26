# #887 — D3e isolated HTTP/SQLite preflight post-merge checkpoint

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-26 16:56 Z (время контрольной сверки GitHub после merge; не точное время merge)
- **Окружение:** GitHub PR CI / independent GitHub main/read-only code read-back; offline synthetic D3e без live staging или production
- **Цель:** проверить, что D3e HTTP preflight/SQLite одноразовые разрешения остаются default-off, owner-bound, fail-closed и не раскрывают subscription bearer
- **Версия и immutable tag/SHA:** PR #921 head `bd19962e507eb7d433d1886f5066644c45cdce10`, squash main SHA `fb69fba8ac6df15f35fb9d910b713362388a98d4`; Published `v5.0.0-rc.19` без D3e
- **Scope:** `subscription_page_import_http.py` separate opt-in HTTP API /csrf /issue /consume и `subscription_page_import_sqlite.py` private local SQLite BEGIN IMMEDIATE, HMAC/hash-only proof and session bindings, D2a/D2b session owner, exact Origin/Host/Sec-Fetch-Site/X-CSRF-Token, no-store, default-off, fresh owner/feature checks; `tests/test_subscription_page_import_http.py` negative and atomic cross-worker regression; не используется из production runtime
- **Фактический результат:** PARTIAL — pre-merge required Python checks/PR conventions PASS, source-only D3e; live/import/URL/device/production acceptance PENDING
- **Источник и evidence:** [PR #921](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/921), [Python checks run 40362844327](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40362844327) и [final PR conventions run 40363417709](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40363417709) SUCCESS на exact head; первоначальная conventions попытка FAIL до отметки завершённого CI; GitHub read-back squash main и source PASS. Post-merge push CI для SHA отдельно PENDING
- **Ограничения и остаточные риски:** никакой реальной URL/Copy/QR выдачи, client/version attestation, реального HTTPS ingress/edge, Bot API, device/WebView, staging DNS/TLS или VPS read-back; D2a session process-local, SQLite only single-host local-fs, NFS/multi-host не покрыты; `preflight=true` не право получать URL
- **Связанные Issues:** #887 OPEN / keep_open; #885 OPEN (HTTPS handoff отдельно); #473/#497 OPEN до собственных acceptance
- **Следующий шаг:** reviewed trusted ingress/origin/TLS/CSRF/edge rate и общая session/topology модель; далее отдельный owner-bound URL issuance с актуальной авторизацией, no-store и IDOR/replay negative tests; затем isolated staging и physical device smoke
- **Раздельные состояния:** merged=PR #921 squash `fb69fba8ac6df15f35fb9d910b713362388a98d4`; published=`v5.0.0-rc.19` без D3e; deployed=`v5.0.0-rc.18.10` только operator-reported, VPS read-back PENDING; accepted=offline scoped CI PASS, real import/G-11 PENDING/NO-GO

## Решение по Issues

- **#887: keep_open.** Доказан лишь source-only HTTP/SQLite preflight. Нет реального URL/Copy/QR/client/device acceptance; следующий шаг — независимый security review и owner-bound issuance с отдельным Roadmap checkpoint.
- **#885: keep_open.** HTTPS handoff PR #886 остаётся отдельным, D3e не означает handoff acceptance.
