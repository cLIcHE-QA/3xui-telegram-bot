# D1b #887 — pre-merge security-first editor checkpoint

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-24 14:10 UTC+03:00
- **Окружение:** отдельная GitHub feature branch, aiohttp in-process negative tests, browser Playwright synthetic mocked API; production/VPS/real operator JSON/Telegram WebView не проверялись
- **Цель:** создать самостоятельный защищённый web admin draft editor без связи с /compat и Telegram /admin
- **Версия и immutable tag/SHA:** baseline main SHA f8ff9a18125e24813f9974531e5257d0f8258534; D1b head/CI сверять после последнего commit; Published v5.0.0-rc.19 не содержит D1b
- **Scope:** отдельно не включённый runtime subscription_page_admin.py, D1b React admin.html, роли owner/editor/viewer, CSRF, encrypted SQLite, optimistic If-Match, metadata proposal и synthetic tests
- **Фактический результат:** PENDING — код в feature branch, required test/title/frontend-model/audit на итоговом SHA и независимый security review не подтверждены до GitHub Actions. Backend TLS/real admin/product acceptance не доказаны
- **Источник и evidence:** [Issue #887](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/887), [канонический контракт](../WEB_SUBSCRIPTION_MINI_APP.md), tests/test_subscription_page_admin.py, web/subscription-page/tests/admin.spec.ts; CI ссылки после фактического read-back
- **Ограничения и остаточные риски:** нет production route, TLS bootstrap, MFA, persistent sessions, crypto rotation, staged publish/rollback и device acceptance; private JSON/URLs не коммитятся. SVG/URL не исполняются. INCY и RabbitHole инструкции будут предоставлены позже
- **Связанные Issues:** #887 keep_open; #885 keep_open (отдельный HTTPS handoff); #890 keep_open (отдельный security release/deploy)
- **Следующий шаг:** required CI на PR SHA, негативные auth/CSRF и browser tests, затем отдельное review/merge разрешение; real security/TLS/MFA/публикация — отдельно
- **Раздельные состояния:** merged=D0/D1a #888/#889/#894/#895 в main, D1b не merged; published=v5.0.0-rc.19 без D1b; deployed=v5.0.0-rc.18.10 operator-reported; accepted=D1b PENDING, #887 keep_open, G-11 PARTIAL/NO-GO
