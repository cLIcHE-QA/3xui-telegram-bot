# Операторская приёмка rc.16.3: 23/23 UI PASS, ручная выдача BLOCKED

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-18 17:07 UTC+03:00
- **Окружение:** production, operator-reported Telegram pilot; независимого VPS/SQLite read-back нет.
- **Цель:** датированно зафиксировать targeted A1–D4, closure #734 и отдельные блокировки ручной выдачи.
- **Версия и immutable tag/SHA:** `v5.0.0-rc.16.3` / `e814aa3638910cc8add70cbaa44b8200f48b9b24`.
- **Scope:** A1–A5, B1–B7, C1–C7, D1–D4 = 23 PASS по сообщению оператора. Старый `hwid_limit=NULL`, буквальная подпись и user card A1–A5 PASS, D4 health PASS; B1–B7 мастер bounded тарифов PASS, C1–C7 включая повтор B5/C2 PASS. Попытка назначить новый bounded indefinite заблокирована устаревшим валидатором; старая бессрочная выдача блокируется pending commerce. Remote grant M1–M8 и платежная сверка не проверены.
- **Фактический результат:** PARTIAL — UI 23/23 scoped PASS; #734 scoped PASS/CLOSED, выдача #730/#740 BLOCKED.
- **Источник и evidence:** операторское сообщение 2026-10-18T14:07:47Z; [GitHub Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.16.3), [Issue #734](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/734), [#730](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/730), [#740](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/740).
- **Ограничения и остаточные риски:** root cause первоначального B5 и точный live pending commerce неизвестны; independent VPS provider/DB state и M1–M8 PENDING. Не обходить commerce gate и не повторять unknown. G-11 PARTIAL/NO-GO, публичный rollout BLOCKED.
- **Связанные Issues:** #705, #730, #731, #734, #740.
- **Следующий шаг:** #740 запланирован для `v5.0.0-rc.16.4` (не Published); проверить отдельный PR #741, после отдельно разрешённых merge/release/deploy выполнить scoped ручную выдачу и read-only payment/provider read-back.
- **Раздельные состояния:** merged=PR #729/#732/#733 в main, PR #741 OPEN и не merged; published=rc.16.3 immutable; deployed=rc.16.3 operator-reported; accepted=#734 scoped PASS, A1–D4 UI 23/23 scoped PASS, M1–M8/полный v5 NOT PASS.
