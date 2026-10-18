# Deployment checkpoint: v5.0.0-rc.16.3 — сообщение оператора

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-17 13:52 UTC+03:00
- **Окружение:** production, operator-reported; независимого доступа к VPS нет.
- **Цель:** зафиксировать фактический deployment и безопасно отделить успешный health от незавершённого targeted acceptance.
- **Версия и immutable tag/SHA:** `v5.0.0-rc.16.3` / `e814aa3638910cc8add70cbaa44b8200f48b9b24`.
- **Scope:** сообщение `DEPLOY_OK`, `APP_VERSION`/Git SHA, работающий container, отсутствие рестартов, `Health`, `DB`, `3XUI_TCP` и наличие pre-deploy backup по сообщению оператора; тесты UI, платёжные mutations, DB read-back и восстановление backup не проводились в рамках этого сообщения.
- **Фактический результат:** PASS — только operator-reported deployment/health; целевой smoke и acceptance PENDING.
- **Источник и evidence:** сообщение оператора 2026-10-17T10:52:57Z (без публикации чувствительных путей, Telegram ID или содержимого backup); independent GitHub [Published prerelease](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.16.3) и проверенный GitHub tag SHA.
- **Ограничения и остаточные риски:** independent VPS/container image/SQLite/provider attestation PENDING; backup restore/deep-validation не подтверждены; #730/#731/#734 не прошли targeted post-deploy smoke; #705/B5 BLOCKED, root cause неизвестна; G-11 PARTIAL/NO-GO, public rollout BLOCKED.
- **Связанные Issues:** #730, #731, #734, #705.
- **Следующий шаг:** на разрешённых pilot identities выполнить сначала read-only B5/старый HWID UI и baseline, затем только отдельно согласованные test entitlement/provider mutations; собрать обезличенный targeted результат, финальный health и Issue closure audit.
- **Раздельные состояния:** merged=main `ea9b48684202469c328a3e70ca910954f5960062` (read-back до checkpoint PR); published=`v5.0.0-rc.16.3` SHA `e814aa3638910cc8add70cbaa44b8200f48b9b24` (immutable GitHub prerelease); deployed=`v5.0.0-rc.16.3` operator-reported PASS, independent VPS attestation PENDING; accepted=targeted #730/#731/#734 PENDING, #705/B5 BLOCKED, full v5 NOT PASS.
