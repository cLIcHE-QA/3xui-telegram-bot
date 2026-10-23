# Security review PR #882: client-specific import URI и subTitle

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-23 15:00 UTC+03:00, pre-merge code review.
- **Окружение:** GitHub branch `feature/473-safe-client-import-deeplinks`; offline source review и required CI, без production/VPS запросов.
- **Цель:** проверить owner/private boundaries, bearer URL handling, SSRF/redirect, QR, scheme injection, безопасную обработку upstream metadata и логирование.
- **Версия и immutable tag/SHA:** base `db946755f2383352131a9520f40ee0ccf24018a9`; [PR #882](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/882) текущий head подтверждается GitHub; Published `v5.0.0-rc.18.10` SHA `dae205ac82762723448f93827b981f89ae622231` не включает реализацию.
- **Scope:** статический анализ `client_access.py`, `client_deep_links.py`, `client_import_title.py`, `subscription_proxy.py`, offline tests. По коду доступ к bearer URL/QR после `guard_callback` и `_require_private_subscription_callback`, идентификатор клиента не берётся из `callback_data`; URI ограничены HTTPS/host/scheme/длиной. Metadata fetch фиксирован на loopback, без redirect и с timeout/размером. Подробный upstream exception ранее логировался; исправлено логирование только класса ошибки. Ужесточены title/control/bidi и URL trailing `?`.
- **Фактический результат:** PARTIAL — обнаруженные замечания исправлены в ветке и добавлены targeted negative tests, но окончательные required CI и интеграционный bot-to-client smoke не являются частью этого статического review.
- **Источник и evidence:** [PR #882](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/882), [Issue #473](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/473), `tests/test_client_import_security_473.py`, `tests/test_client_deep_links_473.py` и GitHub Actions на head PR.
- **Ограничения и остаточные риски:** offline mocks не заменяют реальную проверку loopback proxy, Telegram owner guards на deployed build, актуальность схем и third-party app versions. `subTitle` — branding, не trust signal; метаданные не должны содержать токены и HTML-control. URI/QR содержат bearer subscription URL, не следует распространять. Shadowrocket на Android NOT TESTED.
- **Связанные Issues:** #473.
- **Решение по Issues:** #473: keep_open — после required CI требуется независимое review, отдельные разрешения на merge/Release/deployment, адресный post-deploy Client Portal smoke и read-back.
- **Следующий шаг:** проверить CI `test`/`title` на immutable head, повторить owner/proxy/QR/regression smoke на авторизованной тестовой identity только после отдельно разрешённого deployment.
- **Раздельные состояния:** merged=NO; published=`v5.0.0-rc.18.10` без #473; deployed=operator-reported `rc.18.10`, не независимый read-back; accepted=pre-merge static review PARTIAL, G-11 PARTIAL/NO-GO, public rollout BLOCKED.
