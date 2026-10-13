# B4 — архивная цепочка Stars → VPN: operator-reported 4/4 PASS (2026-10-13)

## Provenance и ограничения

**Источник:** краткий ответ оператора «все PASS», полученный **2026-10-13 12:00:18 UTC / 15:00:18 EEST**, непосредственно на четыре адресных вопроса B4-1…B4-4. Это время сообщения, **не время исходной Stars-транзакции, первоначального импорта, соединения или архивного review**. Оператор ранее (11:25:37 UTC) сообщил о наличии сохранённых исторических материалов. **Первичные архивы, timestamps событий, число проверенных записей, соответствие одному order/client, точные предикаты и тестовые снимки до/после нам не предъявлены.** Нельзя утверждать независимый read-back, cryptographic linkage или `complete V5-A-001 PASS`; отдельные поля шаблона (например, `B4_SAME_PILOT_CUSTOMER` и `B4_HISTORICAL_EVIDENCE_DATES_AVAILABLE`) не были заполнены индивидуально.

**Четыре состояния:** protected `main=e1f8b22708656e2817929cc1f5069184e8eb1454` перед docs PR ([PR #582](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/582) MERGED; required `test` [38392850454](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38392850454) PASS, final `title` [38393103315](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38393103315) PASS; post-merge `Python checks` [38393145244](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38393145244) PASS); **Published:** immutable `v5.0.0-rc.9` SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; **Deployed:** последняя подтверждённая оператором production-версия rc.9, без нового независимого image/VPS read-back; **Accepted:** общий v5 `NOT PASS`, публичный запуск `BLOCKED`.

## Четыре адресные проверки — только устное подтверждение оператора

| Проверка | Что оператор подтвердил фразой «все PASS» | Disposition |
| --- | --- | --- |
| B4-1 | По сохранённой истории первоначальная Stars-оплата связана с `paid` order, `confirmed` payment (или исходно confirmed, затем refunded), `applied` event и хронологией | **OPERATOR-REPORTED scoped PASS**, timestamps и первичный ledger не показаны |
| B4-2 | Для выбранной покупки исторические entitlement/provisioning и provider read-back связаны с выдачей доступа | **OPERATOR-REPORTED scoped PASS**, нет independently verified one-to-one causal identity и quota snapshot |
| B4-3 | Сохранённые сообщения/архив содержат первоначальный VPN-import/обновление subscription после покупки | **OPERATOR-REPORTED scoped PASS**, QR/URL/исторический import trace не публикуется, доказательная привязка не прочитана агентом |
| B4-4 | Сохранённое свидетельство первого VPN подключения и связанного исторического traffic-delta | **OPERATOR-REPORTED scoped PASS**, снимки/дельта и атрибуция к покупке не представлены |

**Результат:** `B4_1..4=OPERATOR_REPORTED_PASS` по ответу оператора; это не четыре независимых stdout результата и не четыре verified PASS. Архивные материалы остаются у оператора. Честная остаточная запись: `ARCHIVE_LINKAGE_INDEPENDENTLY_VERIFIED=NO`, `EVENT_TIMESTAMPS_NOT_PROVIDED`; **G-03 bounded smoke CLOSED, overall acceptance PARTIAL**, не повышать до полного PASS. Предыдущий [G-03 5/5 scoped PASS](v5-g03-stars-vpn-existing-pilot-2026-10-12.md) сохраняет отдельный объём доказательств; повторять его нельзя. Replay/idempotency, provider/node evidence и полный V5-A-001 не закрыты одним архивным сообщением.

## Безопасность, Issues и checkpoint

Только review ранее сохранённого evidence; ни новый Stars invoice/payment/refund, ни VPN import, test traffic, provider mutation, restart, deploy или DB writes не выполнялись агентом и не запрашивались. **Не переносить** в канонические документы Telegram IDs, UUID, QR, subscription URL, платёжные references, node addresses, токены или исходное тело ответа.

[#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) остаётся **OPEN**: нет подтверждения node-side last sync/offline→return/access quota/revoke propagation/no-blind-replay. [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) остаётся OPEN: будущая refund policy rc.10 не реализована. #466/#510/#564/#577 и остальные незавершённые Issues OPEN; ранее закрытые #317/#342/#422 остаются CLOSED по собственным критериям. Новый Issue: **N/A — документирование operator-reported evidence существующего G-03, самостоятельный defect не установлен.**

**Следующий шаг:** docs-only Roadmap checkpoint PR, required `test`/`title`, squash merge, независимый `main`/audit/Issues read-back, post-merge CI и closure audit. До завершения **ROADMAP SYNC PENDING**, следующий production-пакет не начинать. При необходимости усиления доказательств запросить лишь обезличенную таблицу датированных архивных связей, без повторных операций.
