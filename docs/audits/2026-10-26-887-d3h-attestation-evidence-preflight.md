# #887 D3h — предварительный аудит точного client/version evidence (без device smoke)

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-26 21:51 UTC+03:00
- **Окружение:** GitHub repository-only, исходники и изолированный offline preflight; физических iOS/Android, реального Telegram WebView, staging HTTPS и VPS нет
- **Цель:** перед device smoke разделить прежние #473 candidate imports и реально проверенный D3h allowlist, не активируя URL/Copy/QR
- **Версия и immutable tag/SHA:** `v5.0.0-rc.19` tag `d738dd970f2215adc346a919c7ed182abaf454b1`; pre-change `main` `04273fa5c126eb9f0c8a0877f3789f235664d596`; PR #927 (рабочая ветка, не immutable merge)
- **Scope:** создан `docs/assets/subpage-d3h-client-attestations.json` с семью кандидатами и `reviewed=[]`, offline `subscription_page_import_attestations.py`, synthetic negative tests и D3H-01…D3H-06 checklist в `docs/WEB_SUBSCRIPTION_MINI_APP.md`; `app_runtime`, runtime allowlists, `delivery_enabled` и frontend pilot OFF не менялись
- **Фактический результат:** PENDING — приём реальных client/version/device доказательств ещё не проведён; PR CI ожидает независимого результата. Никаких device Copy/QR PASS и подтверждённой webview-совместимости нет
- **Источник и evidence:** [Issue #887](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/887), [PR #927](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/927), [исторический #473](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/473), [канонический Client Setup](../CLIENT_SETUP.md); прежние operator-reported версии Incy 2.6.4/v2raytun 2.4.7 — кандидаты, не D3h device PASS
- **Ограничения и остаточные риски:** реальный iOS/Android app version/build, OS, Chrome/Safari/Telegram WebView, clipboard permission, QR reader, import/refresh и trusted TLS/SNI/edge/session topology не проверены; структурный валидатор не удостоверяет подлинность ручного evidence; будущие права требуют независимой human review, CI и отдельного разрешения
- **Связанные Issues:** #887: keep_open (D3h device review PENDING); #473: исторический source без изменения его acceptance
- **Следующий шаг:** только после разрешённого isolated staging провести D3H-01…D3H-06 на физических устройствах, сохранить обезличенный датированный audit, проверить оба контекста и предложить точный trusted allowlist отдельным PR. До этого не включать backend URL delivery и UI
- **Раздельные состояния:** merged=NO (PR #927 Draft); published=`v5.0.0-rc.19` без D3h; deployed=`v5.0.0-rc.18.10` только operator-reported, независимый VPS read-back PENDING; accepted=D3h PENDING, G-11 PARTIAL/NO-GO, public rollout BLOCKED
