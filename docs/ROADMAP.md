# Дорожная карта проекта

> **Канонический актуальный статус.** Старый Roadmap (5803 строки) сохранён побайтово в [тематическом историческом архиве](roadmap/HISTORY_INDEX.md), original blob `7303286842241ee29b7cbefbabbe4780911043dd`. Исторические сведения и прежние FAIL/STOP/WAIVED не стираются и не являются сегодняшними статусами. Нормативная [приёмка v5](V5_PRODUCTION_ACCEPTANCE.md), [release history](../CHANGELOG.md).

## Актуальная сводка проекта

**Published:** immutable prerelease [`v5.0.0-rc.9`](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.9), tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; last stable `v4.26.9`. **Deployed:** rc.9 только operator-reported (11 октября deploy; 12 октября host SHA/image read-back в [G-01 audit](audits/v5-g01-production-baseline-2026-10-12.md)), independent build/VPS attestation PENDING. **Accepted:** общий v5 **NOT PASS**; stable release, public rollout и expansion pilot allowlist **BLOCKED**.

## Статусы дорожной карты

- `⬜ Запланировано` — работа ещё не завершена в `main`;
- `🟡 Реализовано в main` — код/документация уже слиты, но соответствующий release ещё не опубликован;
- `🟠 Опубликовано; acceptance отложен` — release опубликован, но отдельный обязательный production acceptance, targeted smoke или recovery drill ещё не завершён;
- `✅ Выполнено в vX.Y.Z` — изменение опубликовано и весь обязательный acceptance scope подтверждён.

`PASS/PARTIAL/PENDING/FAIL/BLOCKED` — результаты проверок, не дополнительные статусы Roadmap. **Merged, Published, Deployed и Accepted — раздельные состояния.**

**Infrastructure post-upgrade (2026-10-14):** оператор сообщил, что production Master и все direct nodes уже обновлены до **3x-ui v3.10.0**, Xray до **v26.10.10**; сервисы, Fleet UI, bot и доступный VPN-трафик — targeted operator-reported scoped PASS ([audit](audits/2026-10-14-3xui-v3100-production-postupgrade-readback.md)). Master↔Node client/expiry, active/expired VPN smoke на ВСЕХ нодах оператор сообщил PASS; restore/regression не выполнялись (см. [closure audit](audits/2026-10-14-3xui-v3100-issue630-targeted-smoke-closure.md)), #487 PENDING, [#630](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/630) закрыт `completed` в revised smoke-only scope. Это **не** изменение Published bot rc.9, не общий G-11 PASS и не разрешение на stable/public rollout.

## Текущий этап: v5 Client Portal

**🟠 Опубликовано; acceptance отложен — controlled canary `v5.0.0-rc.9`**. Client Portal (Stars, idempotent entitlement, quota-cycle, guarded callbacks), protected `/admin`; schema v13, 3x-ui **v3.10.0 operator-reported deployed** (исходный published rc.9 pinned 3x-ui v3.9.0; новый main OpenAPI v3.10.0). **Общий v5 acceptance NOT PASS**. Действующие gate/risk outcomes — ниже, закрытые feature Issues и результаты — в [GitHub](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues?q=is%3Aissue+is%3Aclosed) и [dated audits](audits/).

## Реестр acceptance-gates rc.9

| Gate | Что проверено | Итог gate | Осталось / риск |
| --- | --- | --- | --- |
| G-01 | Health/source smoke 5/5; A1 parity 7/7; лимит 30/60 — scoped PASS | PARTIAL | Независимая аттестация deployed image PENDING |
| G-02 | Ledger/Master read 5/5, B1 mismatches/orphans/duplicates 0; Node match — scoped PASS | PARTIAL | Full reconciliation и Node offline→return [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) PENDING |
| G-03 | Stars→VPN и B4 архив 4/4 — PASS со слов оператора | PARTIAL | Independent payment→import provenance PENDING |
| G-04 | Refund/Support journal — scoped PASS подтверждён | PARTIAL | Provider/revoke postconditions PENDING; policy [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) future |
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

Прочие незакрытые работы — в gate-реестре и [активных GitHub Issues](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues); W-03 отражает принятое оператором исключение по закрытому как `not_planned` [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466); новый PASS не заявлен. Завершённые D1 [audit](audits/2026-10-14-v5-d1-second-natural-cycle-readback.md) и G-09 [audit](audits/2026-10-14-v5-g09-natural-paid-expiry-readback.md) не являются новыми задачами. Отдельные PASS/waivers не заменяют полного v5 acceptance; новых production mutations без согласования нет.

## Реестр открытых задач и будущие релизы

**Будущая работа:** единственный полный перечень OPEN задач — в реестре ниже; [GitHub Issues](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues) содержат scope и acceptance. Не дублировать отдельные списки и завершённые outcomes в living Roadmap. Рабочие концепции: [provider-neutral](roadmap/concepts/provider-neutral-remnawave.md), [Client Portal UX](roadmap/concepts/client-portal-ux.md).

## Активный Issue-реестр (machine-checked)

Ровно одна строка на каждый открытый GitHub Issue; подробности остаются в Issue. `—` означает отсутствие PR, `TBD` — непublished target, не гарантированный release. Даты/свидетельства проверок — в отдельных audits.

**Объём (предварительная относительная оценка):** `XS` — до 1 инженерного чел.-дня; `S` — 2–3; `M` — 4–8; `L` — 9–15; `XL` — 16+ / эпик с декомпозицией. Включает реализацию, тесты и документацию; **не** календарный срок, SLA или обещание релиза. Юридическая экспертиза, внешние разрешения и отдельный production rollout оцениваются дополнительно. Пересматривать при уточнении scope через PR.

| Issue | Статус | PR | Target release | Evidence | Next / remaining | Объём |
| --- | --- | --- | --- | --- | --- | --- |
| [#336](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/336) | ⬜ Запланировано | — | TBD | Issue #336 (scope), implementation PENDING | внешний платёжный шлюз и СБП с уникальными ссылками: Issue criteria | XL|
| [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) | ⬜ Запланировано | — | rc.10 (plan) | Issue #433 (scope), implementation PENDING | 14-дневные возвраты Stars с отзывом оплаченного срока: Issue criteria | XL|
| [#434](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/434) | ⬜ Запланировано | — | TBD | Issue #434 (scope), implementation PENDING | ненавязчивые условия возврата в клиентском портале: Issue criteria | S|
| [#436](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/436) | ⬜ Запланировано | — | TBD | Issue #436 (scope), implementation PENDING | подготовить правовую политику возвратов РФ для самозанятого: Issue criteria | L|
| [#437](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/437) | ⬜ Запланировано | — | TBD | Issue #437 (scope), implementation PENDING | справочник возвратов для поддержки в админке: Issue criteria | M|
| [#470](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/470) | ⬜ Запланировано | — | TBD | Issue #470 (scope), implementation PENDING | read-only просмотр Stars Orders в админке: Issue criteria | M|
| [#471](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/471) | ⬜ Запланировано | — | TBD | Issue #471 (scope), implementation PENDING | компактный список и карточки устройств клиента: Issue criteria | M|
| [#472](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/472) | ⬜ Запланировано | — | TBD | Issue #472 (scope), implementation PENDING | безопасное удаление одного собственного HWID клиентом: Issue criteria | L|
| [#473](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/473) | ⬜ Запланировано | — | TBD | Issue #473 (scope), implementation PENDING | безопасные VPN-клиентские deep-link импорты: Issue criteria | M|
| [#475](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/475) | ⬜ Запланировано | — | TBD | Issue #475 (scope), implementation PENDING | геометаданные страны для direct nodes: Issue criteria | M|
| [#476](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/476) | ⬜ Запланировано | — | TBD | Issue #476 (scope), implementation PENDING | мультиформатные подписки raw, Xray JSON и Clash/Mihomo: Issue criteria | XL|
| [#477](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/477) | ⬜ Запланировано | — | TBD | Issue #477 (scope), implementation PENDING | provider-neutral control plane и поддержка Remnawave: Issue criteria | XL|
| [#478](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/478) | ⬜ Запланировано | — | TBD | Issue #478 (scope), implementation PENDING | региональная сеть Probe reporters для Cheburcheck: Issue criteria | XL|
| [#479](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/479) | ⬜ Запланировано | — | TBD | Issue #479 (scope), implementation PENDING | внешняя наблюдаемость, сервисный API и signed webhooks: Issue criteria | XL|
| [#482](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/482) | ⬜ Запланировано | — | TBD | Issue #482 (scope), implementation PENDING | ограничить нагрузку на 3x-ui API перед масштабированием: Issue criteria | L|
| [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) | ⬜ Запланировано | — | TBD | Issue #487 (scope), implementation PENDING | Master/Node sync: Issue criteria | M|
| [#496](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/496) | ⬜ Запланировано | — | TBD | Issue #496 (scope), implementation PENDING | ограничивать видимость функций Client Portal через User Groups: Issue criteria | L|
| [#497](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/497) | ⬜ Запланировано | — | TBD | Issue #497 (scope), implementation PENDING | полноценная карточка подписки и контекстные действия клиента: Issue criteria | M|
| [#498](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/498) | ⬜ Запланировано | — | TBD | Issue #498 (scope), implementation PENDING | безопасная ручная синхронизация подписки клиентом: Issue criteria | L|
| [#499](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/499) | ⬜ Запланировано | — | TBD | Issue #499 (scope), implementation PENDING | применение промокодов при покупке Stars в Client Portal: Issue criteria | L|
| [#500](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/500) | ⬜ Запланировано | — | TBD | Issue #500 (scope), implementation PENDING | управляемое клиентом автопродление подписки: Issue criteria | XL|
| [#501](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/501) | ⬜ Запланировано | — | TBD | Issue #501 (scope), implementation PENDING | настройки клиентских уведомлений и напоминаний: Issue criteria | L|
| [#502](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/502) | ⬜ Запланировано | — | TBD | Issue #502 (scope), implementation PENDING | выбор языка интерфейса Client Portal: Issue criteria | XL|
| [#503](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/503) | ⬜ Запланировано | — | TBD | Issue #503 (scope), implementation PENDING | статистика трафика клиента за сегодня, 7 и 30 дней: Issue criteria | L|
| [#504](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/504) | ⬜ Запланировано | — | TBD | Issue #504 (scope), implementation PENDING | пользовательские названия собственных HWID-устройств: Issue criteria | M|
| [#505](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/505) | ⬜ Запланировано | — | TBD | Issue #505 (scope), implementation PENDING | FAQ и общий контакт поддержки в Client Portal: Issue criteria | S|
| [#506](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/506) | ⬜ Запланировано | — | TBD | Issue #506 (scope), implementation PENDING | собственная история заказов и платежей клиента: Issue criteria | M|
| [#507](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/507) | ⬜ Запланировано | — | TBD | Issue #507 (scope), implementation PENDING | выбор варианта срока тарифа при покупке: Issue criteria | L|
| [#510](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/510) | ⬜ Запланировано | — | TBD | Issue #510 (scope), implementation PENDING | определить жизненный цикл и безопасную очистку GitHub-веток: Issue criteria | L|
| [#564](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/564) | ⬜ Запланировано | — | TBD | Issue #564 (scope), implementation PENDING | скрыть legacy /create и /inbounds из актуального интерфейса: Issue criteria | S|
| [#615](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/615) | ⬜ Запланировано | — | TBD | Issue #615 (scope), implementation PENDING | выбор RU Direct / Full VPN на подписку в Happ и Incy; Shadowrocket позже: Issue criteria | XL|
| [#617](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/617) | ⬜ Запланировано | — | TBD | Issue #617 (scope), implementation PENDING | одноразовая emoji-капча для новых клиентов, existing users без повтора: Issue criteria | L|
| [#627](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/627) | ⬜ Запланировано | — | rc.10 (plan) | Код: `expiry_drift=False` объединяет match/нет данных; G-09 F-09 REVIEW | Разделить MATCH/INSUFFICIENT_DATA/MISMATCH и покрыть tests; implementation PENDING | S|
| [#628](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/628) | ⬜ Запланировано | — | rc.10 (plan) | Карточка пользователя читает legacy `payments` без Stars `commerce_payments` | Добавить owner-scoped read-only Stars/refund + legacy history, RBAC/pagination tests; implementation PENDING | M|
| [#636](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/636) | ⬜ Запланировано | — | TBD | Issue #636: estimate/schema/governance docs-only PR PENDING | Ввести шкалу XS–XL, семь полей и CI для всех OPEN Issues; закрыть после merge/read-back | M |


## Завершённые этапы и исторические документы

v4.x: protected Admin Control Plane, RBAC, Host Control, backup/DR, self-update, monitoring, User Management и final security hardening (stable `v4.26.9`). v5 rc.1…rc.9: controlled canary с отдельными findings и scoped smoke; **не** общий v5 PASS. Подробная хронология: [CHANGELOG](../CHANGELOG.md), [Releases](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases), [исторический индекс](roadmap/HISTORY_INDEX.md).

## Правило дальнейшего ведения

**Не добавлять новый длинный датированный раздел в начало Roadmap.** После проверки обновлять **существующую** строку gate/Issue + ссылку на новый датированный audit с tag/SHA, временем/таймзоной, scope, evidence, ограничениями, FAIL/unknown; не переписывать старые snapshots. Обязательны PR, required `test`/`title`, squash merge, независимый read-back `main` и сверка связанных Issues **до следующего пакета**. См. [GIT_WORKFLOW](GIT_WORKFLOW.md) и [LIVING_DOCS](LIVING_DOCS.md).
