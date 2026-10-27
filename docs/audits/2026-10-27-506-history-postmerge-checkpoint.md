# #506 — собственная история Stars: post-merge checkpoint

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-27 10:08 UTC+03:00
- **Окружение:** GitHub / CI / локальные synthetic Python3.12 SQLite/UI fixtures; без VPS/Telegram/provider операций
- **Цель:** подтвердить merge #939 и фактический implementation state #506 до отдельного rc.22 release-prep.
- **Версия и immutable tag/SHA:** #939 squash main `fae6cee587e10c22c5f6a055b4a7dd0e63413c77`; exact PR head `a1c73bb5f4e150cc66aa4ebfd57df408da950650`, base `89de68bd729043c0421bc95336046c2831d359d4`; Published v5.0.0-rc.21 `35c1a11676bd7fedc1bf386e4f153a3ba454f6e8` без #506.
- **Scope:** собственные XTR Orders/telegram_stars Payments, bounded pagination/private-owner/SQL IDOR, независимые payment/refund/Entitlement статусы, support/Terms без mutations, PR/main read-back. Не production deployment/live acceptance.
- **Фактический результат:** PASS
- **Источник и evidence:** [PR #939](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/939) MERGED; независимые GitHub PR/main REST read-back. [PR Python40464742412](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40464742412) SUCCESS (1586 tests, 3 skipped), [final title40465163321](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40465163321) SUCCESS. Локально targeted16/full1586 (16 skipped по окружению, включая отсутствие Nginx), compileall/OpenAPI/catalog/Living Docs/documentation semantics/diff PASS. [main Python40465243531](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40465243531) SUCCESS и fresh [supply-chain40465276048](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40465276048) SUCCESS на implementation SHA; итог независимо прочитан 2026-10-27 10:12 UTC+03:00.
- **Ограничения и остаточные риски:** это локальный журнал, без независимого read-back Telegram/VPN. Текущая метка тарифа не исторический snapshot. Retention policy не меняется; новый аккаунт с тем же Telegram actor остаётся той же идентичностью. Published/Deployed/Accepted не следуют из CI. Поздняя установка требует cumulative upgrade/config/agent review.
- **Связанные Issues:** #506
- **Решение по Issues:** #506: keep_open
- **Следующий шаг:** required CI и merge этого docs-only checkpoint, independent main read-back; затем rc.22 release-prep с единственным самостоятельным scope #506. Deployment/targeted runtime UI/ownership outcome отложен в завершающий операторский блок #930.
- **Раздельные состояния:** merged=#939 `fae6cee587e10c22c5f6a055b4a7dd0e63413c77`; published=v5.0.0-rc.21 без #506; deployed=v5.0.0-rc.18.10 `dae205ac82762723448f93827b981f89ae622231` только operator-reported, independent VPS read-back PENDING; accepted=offline/PR CI scoped PASS, собственный #506 live PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## Проверенные границы и результат review

Actor берётся только из Telegram from_user, callback не содержит owner. Private chat.id должен совпасть до чтения. Каждая SQL-проекция проверяет Order owner и существование users; Entitlement/refund дополнительно проверяют того же actor. Explicit поля исключают provider charge IDs, invoice payload, checkout/subscription URLs и сырые ошибки. SQLite mode=ro не создаёт отсутствующую БД, count/page читаются в одном snapshot. При недоступности журнала — безопасный текст и Back без repair/fallback.

Вкладки Orders/Payments независимы, XTR и provider проверяются одновременно; RUB/manual/future PSP не смешиваются. Сортировка created_at/id стабильна, LIMIT8, stale/huge page ограничивается фактическим count. В деталях Order — последний фактический Stars Payment, все остальные попытки доступны отдельно. Paid Order без Payment не подтверждает списание. Unknown/refunded и отдельный refund journal не превращаются в состояние VPN; Entitlement — только локальный период, без утверждения о текущем доступе.

16 synthetic тестов проверяют multi-account IDOR, malformed/stale callbacks, missing Payment, повтор одного успешного события без дубликата, refunded/unknown, misowned related rows, deleted-account retention boundary, обе вкладки/Back, приватный owner и отказ guard, XTR/provider boundary, неполную/полную публикацию Terms и недоступную БД. Navigation не вызывает provider/checkout, не меняет SQLite; Terms просмотр не принимает согласие. Slash-команды неизменны, существующий `/paysupport` сохранён. Новых env/портов/dependencies/schema migrations нет, schema v15.

Первый локальный full run нашёл только порядок нормативных UI разделов; исправлено без ослабления checker. Повтор полный 1586 PASS/16 skipped; CI 1586 PASS/3 skipped. Первый title с незаполненным code-CI checkbox корректно FAIL; после фактического Python success финальный title PASS. Проверки не обходились.

## Собственный acceptance и текущая очередь

В Issue явно сохранено расхождение планов: dated 16.10 target rc.21 заменён утверждённой очередью #930 на rc.22. Минимальная проекция следует согласованному Stars-first scope и существующему read-only контракту #470; нового PSP/финансовой политики не вводит.

#506 OPEN/keep_open: позднее отдельно разрешённое deployment и read-only targeted UI/ownership outcome по CLIENT_SETUP, без новых Stars/refund/Telegram sends. #336 отдельно и не blocker. #885 остаётся Published rc.21/keep_open со своим device acceptance. После publication checkpoint rc.22 следующая независимая задача #564/rc.23. Старые HWID PASS и waived burst не повторяются.
