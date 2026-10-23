# #473 — уточнение Shadowrocket: Apple-only и тест исправления имени

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-23 14:38 UTC+03:00; сообщение пользователя 2026-10-23T11:38:32Z.
- **Окружение:** операторская проверка client import; Shadowrocket проверен на устройствах Apple (из предыдущего сообщения следует iOS/macOS); Android не проверялся в Shadowrocket. Конкретная версия клиента и модель Apple устройства отдельно не аттестованы.
- **Цель:** исправить ошибочную трактовку предыдущего отчёта как PASS Shadowrocket/Android и зафиксировать границу повторного теста имени.
- **Версия и immutable tag/SHA:** [draft PR #882](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/882) (не merged); `main` `db946755f2383352131a9520f40ee0ccf24018a9`; Published `v5.0.0-rc.18.10`, tag `dae205ac82762723448f93827b981f89ae622231`, без #473.
- **Scope:** оператор уточнил: «Shadowrocket проверен только на apple девайсах». Поэтому Shadowrocket/Android = **NOT TESTED**, не PASS. Happ в ранее сообщённом iOS/Android/macOS scope сохраняет operator-reported результат, без новых самостоятельных proof. Для Shadowrocket на Apple — operator-reported import PASS, но нет независимых per-platform records и точных client versions. Проблема `remark=VPN` наблюдалась на скриншоте; новая реализация берёт `subTitle` панели по read-only пути. Это исправление ещё не прошло end-to-end smoke после release/deployment.
- **Фактический результат:** PARTIAL: уточнённое ограниченное operator-reported evidence; Shadowrocket/Android не проверен, title regression PENDING, весь #473 keep_open.
- **Источник и evidence:** [Issue #473](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/473), прямое уточнение пользователя 2026-10-23T11:38:32Z и ранее датированный [аудит](2026-10-23-happ-shadowrocket-title-checkpoint.md). Реальные bearer subscription URL/QR/токены не включены.
- **Ограничения и остаточные риски:** без отдельной аттестации версии, архитектуры macOS и точных шагов нельзя утверждать совместимость всего семейства; импорт без фиксированного `remark` может использовать локальное имя клиента. Дефект заголовка закрывать только после проверки названия из 3x-ui на обновлённом Telegram Client Portal. Старый аудит — исторический факт до уточнения, не ретушируется.
- **Связанные Issues:** #473.
- **Решение по Issues:** #473: keep_open — название, safety, CI, release/deployment и bot end-to-end acceptance PENDING.
- **Следующий шаг:** проверить, что заголовок после исправления равен `subTitle` панели и узлы сохранились; отдельно при необходимости подтвердить поддержку macOS Client Portal для Shadowrocket.
- **Раздельные состояния:** merged=NO; published=v5.0.0-rc.18.10; deployed=rc.18.10 operator-reported; accepted=scoped Apple import operator-reported PASS, full #473 PARTIAL; public rollout BLOCKED.
