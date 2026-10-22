# v5.0.0-rc.18.10 — адресная HWID UI-приёмка

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-22 21:21 UTC+03:00; сообщение оператора 2026-10-22T18:21:19Z.
- **Окружение:** production controlled pilot, операторский Telegram UI smoke; независимый GitHub tag/Release read-back.
- **Цель:** закрыть только адресные HWID UI-сценарии релизов rc.18.3–rc.18.10 без повторения ранее принятых проверок rc.18.2.
- **Версия и immutable tag/SHA:** v5.0.0-rc.18.10 / dae205ac82762723448f93827b981f89ae622231.
- **Scope:** оператор сообщил PASS по всем 23 пунктам: UA-01…07 (7); MODEL-01…06 (6); OS-01…03 (3); UI-01…05 (5); FINAL-01…02 (2). UA: Happ с 20-значным окончанием, Throne, Incy/Dalvik, OneXray, Karing 191/160, допустимые и опасные UA; MODEL: Android emulator, Android/Apple, macOS/iPad, Windows/Linux; OS: разделённые Windows версии, Windows 10 10.0, Windows 11/конфликты; UI: исходные значения только admin, порядок строк, emoji и privacy; FINAL: post-smoke health и применимость. Без production DELETE, платежей, restore/restart или расширения пилота.
- **Фактический результат:** PASS — 23/23 **operator-reported scoped HWID UI**, не независимая VPS/provider аттестация и не весь v5.
- **Источник и evidence:** сообщение оператора 2026-10-22T18:21:19Z; deployment report 2026-10-22T15:12:23Z; [операторский deployment audit](2026-10-22-v5-rc18-10-operator-deployed-preacceptance.md); [immutable Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.18.10), [PR #864](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/864), [PR #865](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/865); ранее принятые H1–H8 [отдельно](2026-10-20-v5-rc18-2-hwid-final-closure-review.md).
- **Ограничения и остаточные риски:** нет независимых screenshots, per-fixture upstream read-back, VPS image digest, подтверждения конкретной живой negative fixture для каждого условного варианта; offline regression — отдельное свидетельство. Исторические rc.18.1/rc.18.3 FAIL сохраняются. X1/X2/X3 DELETE provenance остаётся PENDING; G-11 PARTIAL/NO-GO, public rollout BLOCKED.
- **Связанные Issues:** #827, #830, #833, #834, #838, #854.
- **Решение по Issues:** #827: completed; #830: completed; #833: completed; #834: completed; #838: completed; #854: completed. Только собственные read-only UI scope по явному решению оператора, не full v5 acceptance.
- **Следующий шаг:** зафиксировать решения в closure registry и удалить завершённые Issues из активного Roadmap; закрыть Issues с read-back, пройти CI test/title, затем отдельное разрешение на merge и независимый main read-back; не начинать новые production mutations.
- **Раздельные состояния:** merged=implementation/release PR уже MERGED, docs PR #867 OPEN до отдельного разрешения; published=v5.0.0-rc.18.10 GitHub PASS; deployed=rc.18.10 exact SHA operator-reported PASS, independent VPS PENDING; accepted=23/23 scoped UI operator-reported PASS, full v5 NOT PASS/G-11 PARTIAL/NO-GO.
