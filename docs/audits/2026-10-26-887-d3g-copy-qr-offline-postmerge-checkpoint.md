# #887 — D3g Copy/QR authorization isolation, offline post-merge checkpoint

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-26 18:01 Z (GitHub read-back checkpoint; точное время merge отдельно не утверждается)
- **Окружение:** GitHub Actions PR CI, synthetic backend/Node frontend/browser tests и GitHub main code read-back; без реального Telegram Bot API, VPS, TLS ingress и physical device smoke
- **Цель:** устранить D3f permission gap: QR-only client/version не должен получать Copy bearer, а Copy-only не должен получать QR; обеспечить manual Telegram WebView fallback без deeplink и секретов в локальном storage
- **Версия и immutable tag/SHA:** PR #925 exact head `691a0f32f0c40a052b39447c888f82ab73b9922c`, squash main `e818625a7b12cbaeb6e192a3d035b8aee49e8208`; Published `v5.0.0-rc.19` без D3g
- **Scope:** `subscription_page_import_issuer.reviewed_import_methods` + `/deliver` обязательный `method=copy|qr`, отдельная policy `allow_copy/allow_qr`, атомарный burn существующего proof, no-store bearer JSON/QR PNG in-memory; `manualImportClient.ts` explicit same-origin no-store 3-step request и строгая валидация JSON/PNG/HTTPS; `ManualImportPanel.tsx` default-off, ephemeral QR Blob URL revoke, no custom schemes/WebView. Тесты backend method/IDOR/PNG/replay и frontend negative model/browsers
- **Фактический результат:** PARTIAL — required pre-merge CI на scoped source/synthetic tests PASS; реальные клиентские версии, URL/Copy/QR/staging acceptance PENDING
- **Источник и evidence:** [PR #925](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/925), [Python checks run #40373218751](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40373218751), [Subscription Page D1a checks run #40373220777](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40373220777), [final PR conventions #40373866713](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40373866713). Первый Python attempt FAIL из-за внешнего GitHub API `Roadmap reconciliation UNKNOWN/PENDING`; retry PASS без изменения кода. Первый PR conventions FAIL до закрытия CI checkbox, окончательный PASS. Post-merge push CI для squash SHA отдельно PENDING
- **Ограничения и остаточные риски:** `REVIEWED_CLIENT_CAPABILITIES=[]`, shipping `delivery_enabled=false`, `reviewed_clients=()`, UI feature flag false/`pilotEnabled=false`, D3g не подключён к production; QR/clipboard являются bearer disclosure и нуждаются в actual device/edge privacy review. Нет независимого HTTPS/SNI/log redaction, multi-host session/ledger, mobile WebView CSP/Clipboard/QR smoke, real client/version attestation, staging DNS/TLS и VPS read-back
- **Связанные Issues:** #887 OPEN/keep_open; #885 OPEN независимый HTTPS handoff/PR #886; #473/#497 OPEN до собственных acceptance gates
- **Следующий шаг:** review и физическая attestation хотя бы одного конкретного client/version с Copy/QR capability, затем isolated staging, trusted TLS/edge, security/device WebView/iOS/Android targeted smoke; только после отдельного approval оператора рассматривать release/deploy
- **Раздельные состояния:** merged=PR #925 squash `e818625a7b12cbaeb6e192a3d035b8aee49e8208`; published=`v5.0.0-rc.19` без D3g; deployed=`v5.0.0-rc.18.10` operator-reported, VPS read-back PENDING; accepted=source-only synthetic CI scoped PASS, real rollout/G-11 PENDING/NO-GO

## Решение по Issues

- **#887: keep_open.** Copy/QR метода разграничены только в изолированном исходном коде, real allowlist пуст; следующий шаг — reviewed client/version, edge/device/staging smoke и очередной Roadmap checkpoint.
- **#885: keep_open.** HTTPS handoff #885 / draft PR #886 остаётся отдельной задачей, не закрывается D3g.
