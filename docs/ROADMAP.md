# Дорожная карта проекта

> **Канонический актуальный статус.** Старый Roadmap (5803 строки) сохранён побайтово в [тематическом историческом архиве](roadmap/HISTORY_INDEX.md), original blob `7303286842241ee29b7cbefbabbe4780911043dd`. Исторические сведения и прежние FAIL/STOP/WAIVED не стираются и не являются сегодняшними статусами. Нормативная [приёмка v5](V5_PRODUCTION_ACCEPTANCE.md), [release history](../CHANGELOG.md).

## Актуальная сводка проекта

**Controlled pilot (2026-10-19, operator-reported):** #760/U8 Back остаётся `FAIL/PARTIAL` на deployed `v5.0.0-rc.16.6`; исправление [PR #766](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/766) **MERGED** и доступно только в `main`, но ещё **не Published/Deployed/Accepted**. Для #760 требуется новый отдельно разрешённый immutable Release, deployment и только адресный Back+emoji UI re-smoke. Другие U1–U7/U9–U12/Z1–Z2 — scoped operator-reported PASS; independent VPS/SQLite attestation отсутствует. **G-11 PARTIAL/NO-GO, public rollout BLOCKED**. [Evidence](audits/2026-10-19-v5-rc16-6-operator-ui-acceptance.md); [Issue #760](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/760).

**Published:** immutable [Тег `v5.0.0-rc.16.6`](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.16.6), SHA `1ca049047de2b2ed1761a718604d3d975c54463b`, `2026-10-19T10:01:30Z`, [Publish workflow](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/39234380296) PASS. **Deployed:** operator-reported `v5.0.0-rc.16.6`, SHA `1ca049047de2b2ed1761a718604d3d975c54463b`, health OK; independent VPS read-back PENDING. **Accepted:** #760 U8 Back PARTIAL (operator-reported FAIL), остальные U1–U7/U9–U12/Z1–Z2 scoped operator-reported PASS; исправление #766 только в main, новый release/deploy и адресный re-smoke PENDING; full v5 NOT PASS, G-11 PARTIAL/NO-GO, public rollout BLOCKED.

> **Исторические checkpoints (сохранены без потерь):** [неизменяемая версия предыдущего Roadmap до очистки](https://github.com/cLIcHE-QA/3xui-telegram-bot/blob/7ff06d4041d35af478884507ea9e85230fb02139/docs/ROADMAP.md), включая датированные publication/deployment и OPEN/PENDING snapshots, а также [исторический индекс](roadmap/HISTORY_INDEX.md), [CHANGELOG](../CHANGELOG.md) и [аудиты](audits/). Старые статусы не являются сегодняшним состоянием; новые свидетельства добавляются датированными audit-файлами, не параллельными текущими сводками.

## Статусы дорожной карты

- `⬜ Запланировано` — работа ещё не завершена в `main`;
- `🟡 Реализовано в main` — код/документация уже слиты, но соответствующий release ещё не опубликован;
- `🟠 Опубликовано; acceptance отложен` — release опубликован, но отдельный обязательный production acceptance, targeted smoke или recovery drill ещё не завершён;
- `✅ Выполнено в vX.Y.Z` — изменение опубликовано и весь обязательный acceptance scope подтверждён.

`PASS/PARTIAL/PENDING/FAIL/BLOCKED` — результаты проверок, не дополнительные статусы Roadmap. **Merged, Published, Deployed и Accepted — раздельные состояния.**

> **Историческая аттестация infrastructure (2026-10-14):** [операторский аудит 3x-ui/Xray](audits/2026-10-14-3xui-v3100-production-postupgrade-readback.md) и [closure audit #630](audits/2026-10-14-3xui-v3100-issue630-targeted-smoke-closure.md); исходный checkpoint также сохранён в immutable Roadmap snapshot выше. Не отдельное текущее bot deployment evidence.

## Текущий этап: v5 Client Portal

**🟠 Опубликовано; общий v5 acceptance отложен.** Актуальные Published/Deployed/Accepted определяются только строкой `**Published:**` выше; #760/U8 PARTIAL до отдельного release/deploy/re-smoke. G-11 PARTIAL/NO-GO, public rollout BLOCKED. Предыдущие проверки и их прежние статусы — в датированных audits, не повторяются здесь как текущие.

## Реестр acceptance-gates rc.9

| Gate | Что проверено | Итог gate | Осталось / риск |
| --- | --- | --- | --- |
| G-01 | Health/source smoke 5/5; A1 parity 7/7; лимит 30/60 — scoped PASS | PARTIAL | Независимая аттестация deployed image PENDING |
| G-02 | Ledger/Master read 5/5, B1 mismatches/orphans/duplicates 0; Node match — scoped PASS | PARTIAL | Full reconciliation и Node offline→return [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) PENDING |
| G-03 | Stars→VPN и B4 архив 4/4 — PASS со слов оператора | PARTIAL | Independent payment→import provenance PENDING |
| G-04 | Refund/Support journal — scoped PASS подтверждён | PARTIAL | Provider/revoke postconditions PENDING; policy [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) CLOSED/not_planned, не acceptance PASS |
| G-05 | После перезапуска ledger/health, B3 provider read, C1 offline no-replay — scoped PASS | PARTIAL | Interrupted paid-work/full no-replay PENDING |
| G-06 | Offline limiter; D1 natural-cycle второй снимок и D2 backup — scoped PASS ([audit](audits/2026-10-14-v5-d1-second-natural-cycle-readback.md)) | PARTIAL | Full V5-A-003 soak PENDING; queue NOT_INSTRUMENTED |
| G-07 | Изоляция A/B, отказ админ-доступа, C2 offline forged callbacks — scoped PASS | PARTIAL | Live adversarial transport evidence PENDING |
| G-08 | Portal OFF/ON, Stars toggle audit и health — scoped PASS | PARTIAL | Invoice/precheckout и paid event при OFF PENDING; повторять toggle нельзя |
| G-09 | Natural paid Stars entitlement: SQLite expired ↔ Master disabled/expiry ↔ Telegram/VPN — operator-reported scoped PASS ([audit](audits/2026-10-14-v5-g09-natural-paid-expiry-readback.md)) | PASS | Независимая VPS/data-plane attestation отсутствует; AWG RTT без интернета REVIEW; не full v5 acceptance |
| G-10 | QA synthetic 4/4 и Attention Center UI — scoped PASS; natural main-bot `job_failed` NOT TESTED ([W-03 audit](audits/2026-10-14-v5-g10-w03-natural-job-failed-risk-acceptance.md)) | PARTIAL | W-03 operator-waived для [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466), не PASS; live notification/cooldown/recovery и две проекции не доказаны |
| G-11 | Финальный [acceptance report](audits/v5-production-acceptance-2026-10-14.md) составлен; итог `CONDITIONAL / NO-GO` без full production acceptance | PARTIAL | Обязательные V5-A-001…A-003, ownership/rollback/reconciliation не закрыты; G-01…G-08/G-10 PARTIAL, W-01/W-02/W-03 не PASS; public/stable BLOCKED |

### Реестр принятых исключений

| Исключение | Решение оператора | Не проверено / остаточный риск |
| --- | --- | --- |
| W-01 | OPERATOR-WAIVED / NOT TESTED | Independent cross-host Master DR не проводился; не PASS |
| W-02 | OPERATOR-WAIVED / INCONCLUSIVE | Live Telegram burst не доказан; не PASS |
| W-03 | OPERATOR-WAIVED / NOT TESTED | Natural main-bot `job_failed` [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466): new/reminder/recovery/cooldown и две проекции Attention Center не наблюдались ([audit](audits/2026-10-14-v5-g10-w03-natural-job-failed-risk-acceptance.md)); не PASS |

Полные исторические наблюдения, включая старые FAIL, тайминги, данные G-01…G-11 и правильную идентичность DR-хоста: [архив проверок v5](audits/roadmap-history/v5-gates.md), [датированные audits](audits/), [карта переноса](roadmap/HISTORY_INDEX.md). Итоговые короткие строки не отменяют нормативные критерии [V5_PRODUCTION_ACCEPTANCE](V5_PRODUCTION_ACCEPTANCE.md).

## Текущая очередь и блокировки

1. **G-11 / PARTIAL:** [финальный отчёт](audits/v5-production-acceptance-2026-10-14.md) имеет итог `CONDITIONAL / NO-GO`; полный V5-A-001…A-003, ownership, rollback и global reconciliation требуют нового отдельно согласованного scope/нормативного решения. Нельзя снимать блокировку stable/public rollout; без разрешения production operations не запускать.

**Текущие targeted blockers (Issues, не отдельные G-gates):** #760/U8 — возврат из ручного списка на deployed rc.16.6 ещё не принят; исправление #766 только в `main`, новый tag/deploy и адресная проверка PENDING. #767 и #769 CLOSED/completed после merged PR #768/#770 и scoped docs/CI acceptance; closure decisions зафиксированы. Исторические #705/#730/#731/#743/#752 закрыты по scoped acceptance, подробности — в [аудите](audits/2026-10-19-v5-rc16-5-operator-targeted-acceptance.md). G-11 PARTIAL/NO-GO.

Прочие незакрытые работы — в gate-реестре и [активных GitHub Issues](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues); W-03 отражает принятое оператором исключение по закрытому как `not_planned` [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466); новый PASS не заявлен. Завершённые D1 [audit](audits/2026-10-14-v5-d1-second-natural-cycle-readback.md) и G-09 [audit](audits/2026-10-14-v5-g09-natural-paid-expiry-readback.md) не являются новыми задачами. Отдельные PASS/waivers не заменяют полного v5 acceptance; новых production mutations без согласования нет.

## Будущие release-кандидаты (план, утверждён 2026-10-16)

| Целевой RC | Задачи | Зависимости перед включением |
| --- | --- | --- |
| **v5.0.0-rc.17** | #437, #470 | #437: опубликованная редакция утверждённого соглашения (§ 9); #470: Stars Orders read-only/RBAC |
| **v5.0.0-rc.18** | #471, #472 | Сначала стабильный device ID и UI #471, затем подтверждённый owner/capability/security для DELETE #472 |
| **v5.0.0-rc.19** | #473, #497 | Карточка #497 — стабильный контекст; #473 только verified deep-links, безопасный URL/QR fallback; #476 не обязательный полный prerequisite |
| **v5.0.0-rc.20** | #498, #505 | #498 после #497 и с необходимыми доказательствами Master/Node #487 и API budget #482; FAQ/общий Support #505 независимо |
| **v5.0.0-rc.21** | #506, #564 | #506: Stars-first без обязательного #336; #564: сохранить старые guarded redirects |
| **v5.0.0-rc.22** | #615 | Реальная per-subscription совместимость RU Direct / Full VPN в Happ и Incy, отдельный smoke обеих политик |

**Смысл версий:** приведены только будущие кандидаты; опубликованный rc.16 и исходный план сохранены в immutable snapshot выше. Это предварительно утверждённая последовательность, не milestone/deadline и не доказательство включения. Все перечисленные Issues остаются OPEN, если их индивидуальный acceptance не выполнен. Если dependency не пройдена, переносить незавершённую функцию с обновлением Issue/Roadmap, не выдавать Published/Deployed/Accepted за одно состояние. Отдельные #482/#487 остаются OPEN/TBD — необходимые гарантии для #498 обязательны, закрытие всего их scope не требуется. Общий v5 G-11 PARTIAL/NO-GO, публичный rollout BLOCKED.

## Реестр открытых задач и будущие релизы

**Будущая работа:** единственный полный перечень OPEN задач — в реестре ниже; [GitHub Issues](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues) содержат scope и acceptance. Не дублировать отдельные списки и завершённые outcomes в living Roadmap. Рабочие концепции: [provider-neutral](roadmap/concepts/provider-neutral-remnawave.md), [Client Portal UX](roadmap/concepts/client-portal-ux.md).

## Активный Issue-реестр (machine-checked)

Ровно одна строка на каждый открытый GitHub Issue; подробности остаются в Issue. `—` означает отсутствие PR, `TBD` — непublished target, не гарантированный release. Даты/свидетельства проверок — в отдельных audits.

**Объём (предварительная относительная оценка):** `XS` — до 1 инженерного чел.-дня; `S` — 2–3; `M` — 4–8; `L` — 9–15; `XL` — 16+ / эпик с декомпозицией. Включает реализацию, тесты и документацию; **не** календарный срок, SLA или обещание релиза. Юридическая экспертиза, внешние разрешения и отдельный production rollout оцениваются дополнительно. Пересматривать при уточнении scope через PR.

| Issue | Статус | PR | Target release | Evidence | Next / remaining | Объём |
| --- | --- | --- | --- | --- | --- | --- |
| [#336](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/336) | ⬜ Запланировано | — | TBD | Issue #336: объём определён, реализация PENDING | внешний платёжный шлюз и СБП с уникальными ссылками: критерии приёмки | XL|
| [#437](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/437) | ⬜ Запланировано | — | **v5.0.0-rc.17 (план)** | Решение оператора 2026-10-16: целевой rc.17, реализация / acceptance PENDING | Только утверждённый §9 Пользовательского соглашения; без старой 14-дневной программы; публикация юридической редакции — условие корректной памятки; при неподтверждённых проверках переносить только зависимую функцию, не объявлять её PASS | M|
| [#470](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/470) | ⬜ Запланировано | — | **v5.0.0-rc.17 (план)** | Решение оператора 2026-10-16: целевой rc.17, реализация / acceptance PENDING | Только read-only Stars Orders, нет Payment ≠ ошибка; при неподтверждённых проверках переносить только зависимую функцию, не объявлять её PASS | M|
| [#471](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/471) | ⬜ Запланировано | — | **v5.0.0-rc.18 (план)** | Решение оператора 2026-10-16: целевой rc.18, реализация / acceptance PENDING | Первым этапом стабильный и приватный device ID для безопасной #472; при неподтверждённых проверках переносить только зависимую функцию, не объявлять её PASS | M|
| [#472](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/472) | ⬜ Запланировано | — | **v5.0.0-rc.18 (план)** | Решение оператора 2026-10-16: целевой rc.18, реализация / acceptance PENDING | После #471: подтверждение owner/device, two-step DELETE и UNKNOWN без retry; при неподтверждённых проверках переносить только зависимую функцию, не объявлять её PASS | L|
| [#473](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/473) | ⬜ Запланировано | — | **v5.0.0-rc.19 (план)** | Решение оператора 2026-10-16: целевой rc.19, реализация / acceptance PENDING | Verified deep-link client/version matrix, fallback URL/QR, #476 не обязателен; при неподтверждённых проверках переносить только зависимую функцию, не объявлять её PASS | M|
| [#475](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/475) | ⬜ Запланировано | — | TBD | Issue #475: объём определён, реализация PENDING | геометаданные страны для direct nodes: критерии приёмки | M|
| [#476](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/476) | ⬜ Запланировано | — | TBD | Issue #476: объём определён, реализация PENDING | мультиформатные подписки raw, Xray JSON и Clash/Mihomo: критерии приёмки | XL|
| [#477](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/477) | ⬜ Запланировано | — | TBD | Issue #477: объём определён, реализация PENDING | provider-neutral control plane и поддержка Remnawave: критерии приёмки | XL|
| [#478](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/478) | ⬜ Запланировано | — | TBD | Issue #478: объём определён, реализация PENDING | региональная сеть Probe reporters для Cheburcheck: критерии приёмки | XL|
| [#479](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/479) | ⬜ Запланировано | — | TBD | Issue #479: объём определён, реализация PENDING | внешняя наблюдаемость, сервисный API и signed webhooks: критерии приёмки | XL|
| [#482](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/482) | ⬜ Запланировано | — | TBD | Issue #482: объём определён, реализация PENDING | ограничить нагрузку на 3x-ui API перед масштабированием: критерии приёмки | L|
| [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) | ⬜ Запланировано | — | TBD | Issue #487: объём определён, реализация PENDING | Master/Node sync: критерии приёмки | M|
| [#496](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/496) | ⬜ Запланировано | — | TBD | Issue #496: объём определён, реализация PENDING | ограничивать видимость функций Client Portal через User Groups: критерии приёмки | L|
| [#497](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/497) | ⬜ Запланировано | — | **v5.0.0-rc.19 (план)** | Решение оператора 2026-10-16: целевой rc.19, реализация / acceptance PENDING | Read-only subscription card, база для #498 и контекстного импорта #473; при неподтверждённых проверках переносить только зависимую функцию, не объявлять её PASS | M|
| [#498](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/498) | ⬜ Запланировано | — | **v5.0.0-rc.20 (план)** | Решение оператора 2026-10-16: целевой rc.20, реализация / acceptance PENDING | После #497; scoped Master↔Node read-back #487 и API budget #482 обязательны как доказательства, не как формальное полное закрытие задач; при неподтверждённых проверках переносить только зависимую функцию, не объявлять её PASS | L|
| [#499](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/499) | ⬜ Запланировано | — | TBD | Issue #499: объём определён, реализация PENDING | промокоды отдельно от тарифов: XTR в Telegram и RUB на отдельном сайте, с атомарным redemption и раздельными валютами: критерии приёмки | L|
| [#500](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/500) | ⬜ Запланировано | — | TBD | Issue #500: объём определён, реализация PENDING | управляемое клиентом автопродление подписки: критерии приёмки | XL|
| [#501](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/501) | ⬜ Запланировано | — | TBD | Issue #501: объём определён, реализация PENDING | настройки клиентских уведомлений и напоминаний: критерии приёмки | L|
| [#502](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/502) | ⬜ Запланировано | — | TBD | Issue #502: объём определён, реализация PENDING | выбор языка интерфейса Client Portal: критерии приёмки | XL|
| [#503](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/503) | ⬜ Запланировано | — | TBD | Issue #503: объём определён, реализация PENDING | статистика трафика клиента за сегодня, 7 и 30 дней: критерии приёмки | L|
| [#504](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/504) | ⬜ Запланировано | — | TBD | Issue #504: объём определён, реализация PENDING | пользовательские названия собственных HWID-устройств: критерии приёмки | M|
| [#505](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/505) | ⬜ Запланировано | — | **v5.0.0-rc.20 (план)** | Решение оператора 2026-10-16: целевой rc.20, реализация / acceptance PENDING | Утверждённый FAQ и общий Support, отдельно от /paysupport; при неподтверждённых проверках переносить только зависимую функцию, не объявлять её PASS | S|
| [#506](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/506) | ⬜ Запланировано | — | **v5.0.0-rc.21 (план)** | Решение оператора 2026-10-16: целевой rc.21, реализация / acceptance PENDING | Stars/history в первую очередь, web RUB после #336; при неподтверждённых проверках переносить только зависимую функцию, не объявлять её PASS | M|
| [#507](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/507) | ⬜ Запланировано | — | TBD | Issue #507: объём определён, реализация PENDING | выбор варианта срока тарифа при покупке: критерии приёмки | L|
| [#510](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/510) | ⬜ Запланировано | — | TBD | Issue #510: объём определён, реализация PENDING | определить жизненный цикл и безопасную очистку GitHub-веток: критерии приёмки | L|
| [#564](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/564) | ⬜ Запланировано | — | **v5.0.0-rc.21 (план)** | Решение оператора 2026-10-16: целевой rc.21, реализация / acceptance PENDING | Скрыть legacy подсказки, сохранить guarded redirects и callback compatibility; при неподтверждённых проверках переносить только зависимую функцию, не объявлять её PASS | S|
| [#615](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/615) | ⬜ Запланировано | — | **v5.0.0-rc.22 (план)** | Решение оператора 2026-10-16: целевой rc.22, реализация / acceptance PENDING | Happ и Incy: отдельно подтверждённое per-subscription переключение двух policies; без фиктивного Incy PASS; при неподтверждённых проверках переносить только зависимую функцию, не объявлять её PASS | XL|
| [#617](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/617) | ⬜ Запланировано | — | TBD | Issue #617: объём определён, реализация PENDING | одноразовая emoji-капча для новых клиентов, existing users без повтора: критерии приёмки | L|
| [#699](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/699) | ⬜ Запланировано | — | TBD | 2026-10-16: новый Issue; текущий bot manifest не включает Xray Outbounds API | Read-only просмотр/диагностика Outbounds 3x-ui, затем отдельно защищённое изменение; upstream API contract, RBAC, rollback, #482/#487; без production writes | XL|
| [#700](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/700) | ⬜ Запланировано | — | TBD | 2026-10-16: новый Issue; upstream 3x-ui имеет `routeTest`, бот его не использует | Отдельная серверная маршрутизация Xray: read-only rules и синтетический routeTest, затем gated CRUD; зависит от #699; не client-side #615 и не доказательство live reachability | XL|
| [#701](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/701) | ⬜ Запланировано | — | TBD | 2026-10-16: новый Issue; Host Groups 3x-ui read-only уже по закрытому #422, локальные User Groups — отдельная модель | Группы **клиентов 3x-ui**: read-only Master API, позднее guarded membership/CRUD; не смешивать Telegram audience и Host/Server Groups; #496 отдельно | L|
| [#702](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/702) | ⬜ Запланировано | — | TBD | 2026-10-16: новый Issue, пример `page-mascot`; собственной страницы подписки пока нет | После появления custom subscription page: optional mascot, лицензия/ассеты, reduced-motion, privacy и мобильная доступность; действующий proxy не менять | M|
| [#703](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/703) | ⬜ Запланировано | — | TBD | 2026-10-16: новый Issue, пример iwtsy.com; публичный API третьей стороны не подтверждён | Только свои/разрешённые адреса: региональные TCP/SSH probes, различать connect/RST/banner/timeout; consent, SSRF, rate limits, внешний API или собственные probes; #478 — отдельная система | XL|
| [#760](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/760) | 🟠 Опубликовано; acceptance отложен | [PR #761](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/761) MERGED `05ca1a8936bb5667a8780b899ca6d427ec680bc5` | **v5.0.0-rc.16.6 (Published, Deployed operator-reported)** | 2026-10-19 14/14 [x], но U8 Back FAIL после отчёта; [audit](audits/2026-10-19-v5-rc16-6-operator-ui-acceptance.md) и navigation+emoji [PR #766](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/766) MERGED (только main, не Published/Deployed) | Только адресный Back+emoji smoke после нового release/deploy; затем Issue closure audit, остальные PASS не повторять | S|
| [#707](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/707) | ⬜ Запланировано | [#708](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/708) | TBD | Оператор утвердил юристом подготовленные Terms/Privacy и возвраты по соглашению | План раздела «Документы и условия»: /legal/terms, /legal/privacy, /legal/tariffs; версия/акцепт перед XTR/RUB, без публикации тестового URL; #433/#434/#436 superseded | L|

## Завершённые этапы и исторические документы

v4.x: protected Admin Control Plane, RBAC, Host Control, backup/DR, self-update, monitoring, User Management и final security hardening (stable `v4.26.9`). v5 rc.1…rc.9: controlled canary с отдельными findings и scoped smoke; **не** общий v5 PASS. Подробная хронология: [CHANGELOG](../CHANGELOG.md), [Releases](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases), [исторический индекс](roadmap/HISTORY_INDEX.md).

## План размещения юридических документов (#707)

**План:** Client Portal → `📄 Документы и условия` → `/legal/terms` (Пользовательское соглашение), `/legal/privacy` (Политика конфиденциальности), `/legal/tariffs` (Тарифы и лимиты). Web-сайт показывает те же постоянные ссылки без авторизации и оплаты. В Telegram после publication доступ через клиентский раздел в рамках действующего pilot gate; до публикации — не показывать недоступные URL как рабочие.

**Акцепт:** перед Stars invoice и перед RUB checkout на отдельном сайте нужно явное подтверждение действующей редакции, зафиксированное сервером с version/time/account/order; один `/start` не считается явно подтверждённым согласием. **Возвраты:** утверждённые оператором условия раздела 9 юристом подготовленного соглашения, без дополнительной добровольной 14-дневной опции. #433/#434/#436 — Closed/`not_planned` (заменены, не выполнены). **Связи:** #336 (RUB только на самостоятельном сайте), #705 (RUB/XTR тарифы), #437 (памятка поддержки). Юридические HTML-файлы, тестовый enrollment URL и незаполненные реквизиты не публиковать без позднейшего решения.

## Правило дальнейшего ведения

**Не добавлять новый длинный датированный раздел в начало Roadmap.** После проверки обновлять **существующую** строку gate/Issue + ссылку на новый датированный audit с tag/SHA, временем/таймзоной, scope, evidence, ограничениями, FAIL/unknown; не переписывать старые snapshots. Обязательны PR, required `test`/`title`, squash merge, независимый read-back `main` и сверка связанных Issues **до следующего пакета**. См. [GIT_WORKFLOW](GIT_WORKFLOW.md) и [LIVING_DOCS](LIVING_DOCS.md).
