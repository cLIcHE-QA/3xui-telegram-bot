# v5.0.0-rc.16.6 — операторская приёмка UI #760

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-19 13:50 UTC+03:00 EEST; операторские сообщения 2026-10-19T10:16:19Z и 2026-10-19T10:50:19Z.
- **Окружение:** production controlled pilot Telegram, 3x-ui и SQLite; операторский отчёт без независимого VPS-доступа.
- **Цель:** сохранить исходные U1–U12/Z1–Z2 [x] и обнаруженный позднее Back regression без повторения уже принятых тестов.
- **Версия и immutable tag/SHA:** v5.0.0-rc.16.6 / 1ca049047de2b2ed1761a718604d3d975c54463b; tag verified GitHub, deployed identity operator-reported.
- **Scope:** #760, PR #761, U1–U12/Z1–Z2, контролируемый UI pilot; без новых выдач, заказов, платежей и provider writes.
- **Фактический результат:** PARTIAL — оператор сообщил 14/14 [x], но после отчёта выявил фактический FAIL по части U8: Back из списка ручных тарифов ведёт в панель администратора вместо списка всех. U1–U7, U9–U12, Z1–Z2 PASS operator-reported; U8 PARTIAL/FAIL до fix/release/deploy и адресного re-smoke.
- **Источник и evidence:** операторские сообщения в переписке 2026-10-19T10:50:19Z и последующее сообщение о навигации; https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/760 и https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/761.
- **Ограничения и остаточные риски:** U4/U5/U7 могли зачитываться offline CI при отсутствии безопасных production данных; не провоцировать unknown/failed или новые grants. Отсутствует независимая VPS attestation. Navigation FAIL существует на immutable deployed rc.16.6 до следующего отдельно разрешённого release/deploy; G-11 PARTIAL/NO-GO, public rollout BLOCKED.
- **Связанные Issues:** #760: keep_open — навигационный U8 FAIL до исправления и адресной приёмки. Новую Issue для узкой правки не создаём по прямой просьбе оператора.
- **Следующий шаг:** required CI по исправлению Back и emoji, отдельные merge/release/deploy; затем только targeted UI проверка ручные → назад к Пользователям → назад в Панель администратора, нового emoji и post-smoke health. Предыдущие PASS не повторять.
- **Раздельные состояния:** merged=PASS PR #761, новый PR PENDING; published=PASS rc.16.6, исправление не Published; deployed=operator-reported rc.16.6, исправление не Deployed; accepted=PARTIAL #760 U8 FAIL, G-11 PARTIAL/NO-GO.

## Матрица

| Проверка | Оператор | Итог |
| --- | --- | --- |
| U1–U7 | [x] 7/7 | PASS operator-reported, где применимо offline CI |
| U8 | [x] | PARTIAL/FAIL: фактически ошибочный Back; переход Все ранее operator-reported PASS |
| U9–U12 | [x] 4/4 | PASS operator-reported |
| Z1–Z2 | [x] 2/2 | PASS operator-reported, closure самого Issue отложен |

## Root cause и защита

PR #761 расширил единый _users_page_view флагом manual_only, но в обоих режимах оставил безусловную кнопку Панель администратора / admin:home. Это нарушает уже существующий контракт docs/UI_STYLE.md о немедленном родителе. Предыдущий тест проверял filter/page/user callbacks, но не реальную цель кнопки Back. Исправление делает Back из ручных пользователей переходом в admin:users, а общий список сохраняет admin:home. Новый тест проверяет реально сформированные обе клавиатуры.
