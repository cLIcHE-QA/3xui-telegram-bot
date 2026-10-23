# #473 — уточнение версии Incy на macOS

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-23 14:04 UTC+03:00 (сообщение пользователя 2026-10-23T11:04:36Z).
- **Окружение:** macOS, VPN-клиент Incy 2.6.4; точная версия macOS и build ID приложения не сообщены; независимый read-back отсутствует.
- **Цель:** уточнить версию в ранее зарегистрированном успешном macOS deep-link тесте.
- **Версия и immutable tag/SHA:** implementation [PR #882](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/882) открыт, не merged; Published v5.0.0-rc.18.10, tag SHA dae205ac82762723448f93827b981f89ae622231, не содержит #473.
- **Scope:** оператор ранее сообщил macOS deep-link PASS, затем уточнил «пока только Incy», теперь уточнил версию «incy на macos 2.6.4». **Incy 2.6.4 / macOS: 1/1 operator-reported scoped PASS**. Это уточнение уже зарегистрированного теста, **не шестой независимый запуск**. v2raytun/macOS PENDING. Ранее подтверждённые Incy/v2raytun на iOS/Android 4/4 не изменились.
- **Фактический результат:** PARTIAL по Issue #473: пять различных сочетаний приложения/ОС имеют operator-reported PASS, но bot-to-client и release acceptance PENDING.
- **Источник и evidence:** сообщения пользователя 2026-10-23T10:49:08Z, 2026-10-23T11:01:16Z, 2026-10-23T11:04:36Z; [первый macOS checkpoint](2026-10-23-client-import-473-macos-incy-checkpoint.md), [первые 4/4 iOS/Android](2026-10-23-client-import-473-operator-smoke.md). Ни URL подписки, ни QR, ни токены в audit не переносились.
- **Ограничения и остаточные риски:** версия macOS неизвестна, нет самостоятельного evidence состояния GUI, независимой проверки и тестирования остальных шести приложений. Дополнительные URI в PR #882 — только candidate schemes без ручного PASS.
- **Связанные Issues:** #473.
- **Решение по Issues:** #473: keep_open — security review, совместимость новых клиентов, merge, release/deploy и end-to-end bot smoke PENDING; общий v5 G-11 PARTIAL/NO-GO.
- **Следующий шаг:** подтвердить контракты и версии остальных клиентов, синхронизировать документальную матрицу, завершить security review #882; не повторять уже подтверждённый Incy/macOS без изменения версии/гипотезы.
- **Раздельные состояния:** merged=NO (PR #882 Draft); published=v5.0.0-rc.18.10; deployed=rc.18.10 operator-reported, независимый VPS read-back PENDING; accepted=Incy 2.6.4/macOS operator-reported scoped PASS; full #473 PARTIAL, public rollout BLOCKED.
