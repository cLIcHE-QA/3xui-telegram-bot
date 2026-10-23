# #473 — ручная проверка import URI Incy и v2raytun на iOS/Android

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-23 13:38 UTC+03:00 (время получения итогового сообщения 2026-10-23T10:38:05Z); сведения о версиях получены 2026-10-23T09:38:43Z. Фактические минуты запусков на устройствах не измерялись независимо.
- **Окружение:** user/operator-reported ручная проверка на iOS 26.5.1 (23F81) и Android 17; версии приложений Incy 2.6.4 и v2raytun 2.4.7. Конкретные устройства, раздельные build IDs приложений по ОС и серверная инфраструктура независимо не аттестованы.
- **Цель:** проверить поддержку client-specific URI импорта подписки в указанном сочетании клиентов/ОС и зафиксировать ограниченное evidence для [Issue #473](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/473).
- **Версия и immutable tag/SHA:** реализация-кандидат в [draft PR #882](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/882), branch head до данного audit `7f62721367127b5b72506801453c16a809673035`; `main` `db946755f2383352131a9520f40ee0ccf24018a9`. Текущий Published tag `v5.0.0-rc.18.10`, SHA `dae205ac82762723448f93827b981f89ae622231` **не включает** PR #882.
- **Scope:** ранее пользователю предложены импорт URI, появление серверов, refresh subscription и отдельный VPN-connect check для каждого из четырёх сочетаний. Пользователь сообщил «везде pass», трактуется как **4/4 operator-reported PASS** по этому предложенному ручному сценарию; отдельных per-step logs или независимого device read-back нет.

| ID | ОС | Клиент | Итог сообщения пользователя |
| --- | --- | --- | --- |
| I-01 | iOS 26.5.1 (23F81) | Incy 2.6.4 | PASS (operator-reported) |
| I-02 | Android 17 | Incy 2.6.4 | PASS (operator-reported) |
| V-01 | iOS 26.5.1 (23F81) | v2raytun 2.4.7 | PASS (operator-reported) |
| V-02 | Android 17 | v2raytun 2.4.7 | PASS (operator-reported) |

- **Фактический результат:** PARTIAL для всего #473: **4/4 operator-reported scoped manual import PASS** на этих версиях; это **не** сквозной тест кнопок бота из PR #882, не независимая техническая аттестация, не post-deploy acceptance и не общий v5 PASS.
- **Источник и evidence:** прямое сообщение пользователя 2026-10-23T10:38:05Z «везде pass» в ответ на четыре ранее сформулированные проверки, данные версий 2026-10-23T09:38:43Z; [PR #882](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/882) (required CI `test`/`title` PASS на `7f62721367127b5b72506801453c16a809673035`). Реальный subscription URL/токен/QR из переписки **не переносились в GitHub**.
- **Ограничения и остаточные риски:** результат относится только к указанным версиям и устройствам; нет evidence по Windows/macOS/Linux и другим клиентам, негативным live-сценариям, bot private/ownership/UI/QR с новым опубликованным кодом, стабильности импорта после повторного запуска, VPS read-back и independent security review. В PR #882 доступны offline negative tests, но это не post-deployment safety smoke. Production не менялась.
- **Связанные Issues:** #473 (связанный PR #882).
- **Решение по Issues:** #473: keep_open — manual scope 4/4 PASS, но реализация не в `main`, PR не merged, release/deployment и required end-to-end bot/security acceptance PENDING; без утверждения полного `PASS`.
- **Следующий шаг:** security review PR #882, GitHub required CI и проверка безопасности пробных URI; затем только после отдельного разрешения merge → release → deployment → ограниченный bot-to-client end-to-end smoke, private/ownership/fallback и postcondition; синхронизировать Roadmap с `main`. Не повторять уже подтверждённые четыре импорт-сценария без новой гипотезы/версии.
- **Раздельные состояния:** merged=NO (PR #882 draft OPEN); published=только `v5.0.0-rc.18.10` (без #473); deployed=`rc.18.10` operator-reported, independent VPS read-back PENDING; accepted=4/4 operator-reported manual import URI scoped PASS, весь Issue #473 PARTIAL/keep_open; G-11 PARTIAL/NO-GO, public rollout BLOCKED.
