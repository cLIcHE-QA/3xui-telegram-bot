# v5.0.0-rc.18 — операторская targeted HWID-приёмка #471/#472

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-20 13:33 UTC+03:00 (EEST); сообщение оператора 2026-10-20T10:33:45Z.
- **Окружение:** production controlled pilot, **operator-reported**; нет независимого VPS/SQLite/provider read-back со стороны агента.
- **Цель:** зафиксировать scoped HWID smoke D1…D8 и S1…S4 на заявленном deployed `v5.0.0-rc.18`, без повторного U8/Stars/Support регресса.
- **Версия и immutable tag/SHA:** `v5.0.0-rc.18` / `0d67eb331535ed081ca8faf77a324848d1b1c65e` (GitHub Release/tag independently confirmed; deployed identity — только operator-reported).
- **Scope:** оператор сообщил `P0–P2 PASS; D1–D8 PASS; S1–S4 PASS; X1–X3 PASS; F1–F3 PASS`. В актуальном ранее редактируемом чек-листе `X2` оставался `[ ]`; это противоречие требует уточнения. Сценарии `X1` и `X3` чувствительны к production mutations/security; явного отдельного разрешения на DELETE и детального postcondition evidence в сообщении нет. Не считать сообщение подтверждением опасных действий и не повторять DELETE ради аудита.
- **Фактический результат:** PARTIAL
- **Пояснение результата:** D1…D8 и S1…S4 `operator-reported scoped PASS` без независимой верификации; `P0–P2` / `F1–F3` заявлены оператором. X1/X3 `operator-reported PASS claimed / provenance incomplete`, X2 `PENDING` до разрешения противоречия и evidence; фактические production DELETE/read-back вне независимой проверки агента. G-11 PARTIAL/NO-GO, public rollout BLOCKED.
- **Источник и evidence:** сообщение оператора 2026-10-20T10:33:45Z в текущем чате; previously edited checklist с X2 unchecked; GitHub Release `v5.0.0-rc.18`, [Issue #471](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/471), [Issue #472](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/472), implementation PR #808/#810.
- **Ограничения и остаточные риски:** не переданы обезличенные журналы provider inventory, exact production deployed tag-SHA output, trace одного разрешённого DELETE, подтверждение отсутствия replay, применимость D3/D6/D8/X3. Заявленные PASS отмечены только со слов оператора, без удаления исторических UNKNOWN/PENDING и без автоматического закрытия Issue.
- **Связанные Issues:** #471, #472; новая отдельная UX-задача #814.
- **Решение по Issues:** #471 `keep_open` до scoped evidence/closure decision; #472 `keep_open` до безопасности DELETE/no-replay и разрешения X2; #814 `OPEN` пока read-only improvement не merged/released/accepted.
- **Следующий шаг:** уточнить X2 и основания X1/X3, получить scrubbed provenance, затем отдельный closure audit/decision и Roadmap sync; для #814 — required PR CI и новый отдельный release/deploy/targeted UI acceptance.
- **Раздельные состояния:** merged=PR #808/#810/#812/#813; published=`rc.18` PASS; deployed=`rc.18` operator-reported по P0, независимый read-back PENDING; accepted=#471/#472 PARTIAL с применимыми operator-reported PASS, полный scope не закрыт.
