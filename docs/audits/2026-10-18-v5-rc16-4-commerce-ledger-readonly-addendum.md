# Addendum: commerce blocker при нулевом счётчике ожидающих Stars-платежей

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-18 21:52 UTC+03:00
- **Окружение:** operator-reported Telegram UI screenshot на production controlled pilot; независимый GitHub source read-back, без VPS/DB доступа
- **Цель:** установить, почему пользователю нельзя выбрать ручной бессрочный тариф при показателе «Ожидают: 0» в журнале Stars, и проверить прежнее закрытие #740
- **Версия и immutable tag/SHA:** `v5.0.0-rc.16.4` / `114de5af16adcde5e8d128cc5a55d58addc37e73`
- **Scope:** анализ без личных Telegram IDs/платёжных идентификаторов; screenshot Stars UI показывает 11 total, 6 confirmed, 5 refunded, 0 pending и 0 manual accounting; `db.py:manual_grant_commerce_block_reason` запрещает grant при `commerce_orders.created/awaiting_payment` или `entitlements.pending/provisioning`; `advanced_users.py:_user_payments_view` показывает payment counters из `commerce_payments`, а не все `commerce_orders`
- **Фактический результат:** PARTIAL — объяснимое различие между отображаемым payment ledger и order-level blocker; наличие конкретного незавершённого order без payment **вероятно, но НЕ ДОКАЗАНО** без read-only DB query; issue #740 reopened, ранее зафиксированные F1–F7 operator-reported PASS сохранены как scoped свидетельство, но UX read-only diagnostic gate OPEN
- **Источник и evidence:** операторский screenshot 2026-10-18 (не размещён в GitHub из-за персонального идентификатора); [Issue #740](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/740), [`db.py` в release tag](https://github.com/cLIcHE-QA/3xui-telegram-bot/blob/v5.0.0-rc.16.4/db.py), [`advanced_users.py` в release tag](https://github.com/cLIcHE-QA/3xui-telegram-bot/blob/v5.0.0-rc.16.4/advanced_users.py)
- **Ограничения и остаточные риски:** нет read-only owner-scoped DB результата; нулевой счётчик `commerce_payments` не означает отсутствия незавершённых `commerce_orders`. Не удалять/изменять orders/payment/entitlements напрямую, не повторять manual grant, не делать provider mutations ради диагностики. #730 M1–M8 BLOCKED, C3/#743 FAIL, #745 restart-persistence PENDING, G-11 PARTIAL/NO-GO
- **Связанные Issues:** #740 REOPENED/OPEN (диагностика), #730/#705 OPEN (ручная выдача), #743 OPEN, #745 OPEN
- **Следующий шаг:** отдельная безопасная read-only SQLite query по разрешённой pilot identity для `commerce_orders`↔`commerce_payments`↔`entitlements`; по полученному evidence решить, нужен ли safe order-lifecycle reconciliation/UI feature; без override и SQL mutations
- **Раздельные состояния:** merged=PASS (PR #749/#750); published=PASS (immutable `rc.16.4`); deployed=operator-reported PASS (runtime `rc.16.4`); accepted=PARTIAL (59/60 scoped checks, отдельная guide/diagnostic проблема #740 не закрыта)
