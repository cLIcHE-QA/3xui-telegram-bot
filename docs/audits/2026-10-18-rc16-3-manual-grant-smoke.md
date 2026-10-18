# Targeted UI smoke rc.16.3: PASS и два finding ручной выдачи

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-18 17:07 UTC+03:00
- **Окружение:** production, operator-reported Telegram pilot; VPS/image независимо не прочитан.
- **Цель:** проверить A1–D4 после deployment rc.16.3 и зарегистрировать два новых отказа назначения бессрочного тарифа.
- **Версия и immutable tag/SHA:** `v5.0.0-rc.16.3` / `e814aa3638910cc8add70cbaa44b8200f48b9b24`.
- **Scope:** A1–A5, B1–B7, C1–C7, D1–D4 — все 23 результата PASS по сообщению оператора; попытка назначения недавно созданного bounded бессрочного тарифа — отказ UI, попытка старого бессрочного — `pending commerce must be resolved before manual grant`. M1–M8 не признаны PASS.
- **Фактический результат:** PARTIAL — 23/23 operator-reported UI PASS, ручное назначение BLOCKED двумя отдельными условиями.
- **Источник и evidence:** сообщение оператора в чате 2026-10-18T14:07:47Z; [immutable GitHub Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.16.3); [#730](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/730), [#740](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/740).
- **Ограничения и остаточные риски:** тесты не являются независимой VPS аттестацией; неизвестно, какой конкретно open order/pending entitlement блокирует старого клиента. Нельзя обходить commerce fence, считать payment resolved, повторять mutation при unknown или закрывать #705/#730. Full v5 G-11 PARTIAL/NO-GO, public rollout BLOCKED.
- **Связанные Issues:** #705, #730, #731, #734, #740.
- **Следующий шаг:** required CI исправления; после отдельно разрешённого merge/release/deployment адресный тест UI, проверенный commerce terminal state и read-only 3x-ui/SQLite postcondition, затем post-smoke health и Issue closure audit.
- **Раздельные состояния:** merged=исправление только в отдельной ветке/PR, main неизменён до разрешённого merge; published=immutable rc.16.3; deployed=rc.16.3 operator-reported, independent VPS PENDING; accepted=A1–D4 scoped operator-reported PASS, ручная выдача и полный v5 PENDING/BLOCKED.
