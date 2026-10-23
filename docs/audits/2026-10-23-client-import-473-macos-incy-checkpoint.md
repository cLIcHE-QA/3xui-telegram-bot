# #473 — уточнение macOS-проверки Incy

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-23 14:01 UTC+03:00 (сообщение пользователя 2026-10-23T11:01:16Z; исходное сообщение о macOS PASS — 2026-10-23T10:49:08Z).
- **Окружение:** macOS, локальный VPN-клиент Incy; точная версия macOS и Incy на Mac не указаны, независимого device read-back нет.
- **Цель:** атрибутировать ранее сообщённый успешный macOS deep-link одному конкретному клиенту в #473.
- **Версия и immutable tag/SHA:** кандидат [PR #882](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/882), не merged; Published v5.0.0-rc.18.10, tag SHA dae205ac82762723448f93827b981f89ae622231, не содержит #473.
- **Scope:** оператор уточнил «пока только Incy» применительно к ранее сообщённому macOS deep-link PASS. **Incy/macOS — 1 operator-reported scoped PASS**; v2raytun/macOS и остальные приложения на macOS **PENDING, не проверены**. Версия Incy 2.6.4 относилась к более ранним данным для iOS/Android и не переносится на macOS без доказательства.
- **Фактический результат:** PARTIAL по всему #473; 4/4 [ранее проверенных iOS/Android](2026-10-23-client-import-473-operator-smoke.md) остаются operator-reported PASS, плюс один отдельный macOS/Incy operator-reported PASS с неизвестными версиями. Полный bot-to-client smoke и production acceptance PENDING.
- **Источник и evidence:** прямые сообщения пользователя 2026-10-23T10:49:08Z и 2026-10-23T11:01:16Z. Реальные subscription URL, токены, QR и private user data не публиковались.
- **Ограничения и остаточные риски:** нет независимого воспроизведения, client/version matrix для прочих ОС/приложений PENDING, security review и postdeploy проверки не выполнены; не утверждать успех v2raytun/macOS.
- **Связанные Issues:** #473.
- **Решение по Issues:** #473: keep_open — только отдельный клиентский scoped smoke, draft PR не merged, release/deploy/end-to-end acceptance PENDING.
- **Следующий шаг:** дополнить current-state матрицу этим scoped evidence, завершить security review и подтвердить новые приложения/версии до соответствующих заявлений PASS.
- **Раздельные состояния:** merged=NO; published=v5.0.0-rc.18.10 (без #473); deployed=rc.18.10 operator-reported, независимая VPS-аттестация PENDING; accepted=Incy/macOS scoped operator-reported PASS, full #473 PARTIAL, G-11 PARTIAL/NO-GO.
