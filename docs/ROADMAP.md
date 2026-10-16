# Дорожная карта проекта

> **Канонический актуальный статус.** Старый Roadmap (5803 строки) сохранён побайтово в [тематическом историческом архиве](roadmap/HISTORY_INDEX.md), original blob `7303286842241ee29b7cbefbabbe4780911043dd`. Исторические сведения и прежние FAIL/STOP/WAIVED не стираются и не являются сегодняшними статусами. Нормативная [приёмка v5](V5_PRODUCTION_ACCEPTANCE.md), [release history](../CHANGELOG.md).

## Актуальная сводка проекта

**Сверка 2026-10-16 (Europe/Helsinki), GitHub API:** [PR #695](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/695) успешно слит в `main` (неизменяемый squash SHA `afee9474bdcba2026c6ba363fc3db961d800977f`); повторный [CI `test`](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38926712452) и `audit` — PASS. [Issue #694](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/694) закрыт `completed` после независимого чтения документации в `main`: docs-only критерии приняты, без production операций. Исправление UI [#691](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/691) слито [PR #692](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/692) только в `main`, **не входит** в rc.15 и требует нового release/deployment/адресной проверки. [PR #693](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/693) закрепляет совместимый OpenAPI contract 3x-ui `v3.10.2`; OpenAPI schema blob идентичен upstream `v3.10.0`, runtime routes и опубликованный rc.15 не изменяются.

**Published:** immutable [Тег `v5.0.0-rc.15`](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.15), SHA `9c9245899c7ca949254df92d95f8015e65989645`, опубликован GitHub `2026-10-16T12:53:58Z`. **Deployed:** rc.15 с этим SHA только operator-reported в [#691](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/691) `2026-10-16T13:16:00Z`; `Health/DB/3XUI_TCP=ok`, `RestartCount=0`; независимый VPS/image/DB/Xray read-back **PENDING**. **Accepted:** scoped A6.1/A6.2/A6.3 и N6/R3 MATCH, адресный Flow POST operator-reported PASS; полный v5 **NOT PASS**, G-11 **PARTIAL / NO-GO**. Stable/public rollout и расширение pilot allowlist **BLOCKED**.

**Текущая незавершённая работа:** #691 — отображение shared `client.flow` и адресного Flow, исторический Node MATCH и подписи нод/inbound исправлены в `main` через #692. **Целевой релиз: `v5.0.0-rc.16` (ПЛАН, не Published)**; отдельные разрешённые release/deployment и адресный UI smoke — **PENDING**. Пока нет evidence по этим gate, #691 остаётся OPEN. #482 (нагрузка API), #487 (сверка Master/Node) и прочие будущие задачи — в реестре ниже. Закрытые #648/#649/#650/#659/#663/#679 и #694 не являются активными задачами; доказательства доступны в Issues, PR, [CHANGELOG](../CHANGELOG.md) и [датированных audits](audits/). **Сверка статусов GitHub на 2026-10-16:** `38 OPEN Issues = 38 строк реестра`; фактическое попадание этой версии Roadmap в `main` подтверждается отдельно по SHA после merge. При изменении Issues сверку выполнить повторно. **Новый будущий backlog (оценка возможности, не начало реализации):** [#699](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/699) Outbounds, [#700](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/700) серверный Routing, [#701](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/701) Client Groups 3x-ui, [#702](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/702) маскот после собственной страницы подписки, [#703](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/703) разрешённая TCP/SSH диагностика через независимые пробы. Все пять — OPEN / ⬜ Запланировано, версии TBD, не часть rc.16. Дополнительные production mutations и публичный запуск не разрешены.

## Статусы дорожной карты

- `⬜ Запланировано` — работа ещё не завершена в `main`;
- `🟡 Реализовано в main` — код/документация уже слиты, но соответствующий release ещё не опубликован;
- `🟠 Опубликовано; acceptance отложен` — release опубликован, но отдельный обязательный production acceptance, targeted smoke или recovery drill ещё не завершён;
- `✅ Выполнено в vX.Y.Z` — изменение опубликовано и весь обязательный acceptance scope подтверждён.

`PASS/PARTIAL/PENDING/FAIL/BLOCKED` — результаты проверок, не дополнительные статусы Roadmap. **Merged, Published, Deployed и Accepted — раздельные состояния.**

**Infrastructure post-upgrade (2026-10-14):** оператор сообщил, что production Master и все direct nodes уже обновлены до **3x-ui v3.10.0**, Xray до **v26.10.10**; сервисы, Fleet UI, bot и доступный VPN-трафик — targeted operator-reported scoped PASS ([audit](audits/2026-10-14-3xui-v3100-production-postupgrade-readback.md)). Master↔Node client/expiry, active/expired VPN smoke на ВСЕХ нодах оператор сообщил PASS; restore/regression не выполнялись (см. [closure audit](audits/2026-10-14-3xui-v3100-issue630-targeted-smoke-closure.md)), #487 PENDING, [#630](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/630) закрыт `completed` в revised smoke-only scope. Это **не** изменение Published bot rc.9, не общий G-11 PASS и не разрешение на stable/public rollout.

## Текущий этап: v5 Client Portal

**🟠 Опубликовано; общий v5 acceptance отложен — controlled canary `v5.0.0-rc.15`**. Client Portal (Stars, idempotent entitlement, quota-cycle, guarded callbacks), protected `/admin`; schema v13, 3x-ui **v3.10.2 operator-reported installed/tested**; общий pinned OpenAPI contract `v3.10.2` (PR #693; тот же immutable schema blob, что и `v3.10.0`). **Общий v5 acceptance NOT PASS**. Действующие gate/risk outcomes — ниже, закрытые feature Issues и результаты — в [GitHub](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues?q=is%3Aissue+is%3Aclosed) и [dated audits](audits/).

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
| [#336](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/336) | ⬜ Запланировано | — | TBD | Issue #336: объём определён, реализация PENDING | внешний платёжный шлюз и СБП с уникальными ссылками: критерии приёмки | XL|
| [#437](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/437) | ⬜ Запланировано | — | TBD | Issue #437: объём определён, реализация PENDING | справочник возвратов для поддержки в админке: критерии приёмки | M|
| [#470](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/470) | ⬜ Запланировано | — | TBD | Issue #470: объём определён, реализация PENDING | read-only просмотр Stars Orders в админке: критерии приёмки | M|
| [#471](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/471) | ⬜ Запланировано | — | TBD | Issue #471: объём определён, реализация PENDING | компактный список и карточки устройств клиента: критерии приёмки | M|
| [#472](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/472) | ⬜ Запланировано | — | TBD | Issue #472: объём определён, реализация PENDING | безопасное удаление одного собственного HWID клиентом: критерии приёмки | L|
| [#473](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/473) | ⬜ Запланировано | — | TBD | Issue #473: объём определён, реализация PENDING | безопасные VPN-клиентские deep-link импорты: критерии приёмки | M|
| [#475](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/475) | ⬜ Запланировано | — | TBD | Issue #475: объём определён, реализация PENDING | геометаданные страны для direct nodes: критерии приёмки | M|
| [#476](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/476) | ⬜ Запланировано | — | TBD | Issue #476: объём определён, реализация PENDING | мультиформатные подписки raw, Xray JSON и Clash/Mihomo: критерии приёмки | XL|
| [#477](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/477) | ⬜ Запланировано | — | TBD | Issue #477: объём определён, реализация PENDING | provider-neutral control plane и поддержка Remnawave: критерии приёмки | XL|
| [#478](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/478) | ⬜ Запланировано | — | TBD | Issue #478: объём определён, реализация PENDING | региональная сеть Probe reporters для Cheburcheck: критерии приёмки | XL|
| [#479](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/479) | ⬜ Запланировано | — | TBD | Issue #479: объём определён, реализация PENDING | внешняя наблюдаемость, сервисный API и signed webhooks: критерии приёмки | XL|
| [#482](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/482) | ⬜ Запланировано | — | TBD | Issue #482: объём определён, реализация PENDING | ограничить нагрузку на 3x-ui API перед масштабированием: критерии приёмки | L|
| [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) | ⬜ Запланировано | — | TBD | Issue #487: объём определён, реализация PENDING | Master/Node sync: критерии приёмки | M|
| [#496](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/496) | ⬜ Запланировано | — | TBD | Issue #496: объём определён, реализация PENDING | ограничивать видимость функций Client Portal через User Groups: критерии приёмки | L|
| [#497](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/497) | ⬜ Запланировано | — | TBD | Issue #497: объём определён, реализация PENDING | полноценная карточка подписки и контекстные действия клиента: критерии приёмки | M|
| [#498](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/498) | ⬜ Запланировано | — | TBD | Issue #498: объём определён, реализация PENDING | безопасная ручная синхронизация подписки клиентом: критерии приёмки | L|
| [#499](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/499) | ⬜ Запланировано | — | TBD | Issue #499: объём определён, реализация PENDING | применение промокодов при покупке Stars в Client Portal: критерии приёмки | L|
| [#500](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/500) | ⬜ Запланировано | — | TBD | Issue #500: объём определён, реализация PENDING | управляемое клиентом автопродление подписки: критерии приёмки | XL|
| [#501](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/501) | ⬜ Запланировано | — | TBD | Issue #501: объём определён, реализация PENDING | настройки клиентских уведомлений и напоминаний: критерии приёмки | L|
| [#502](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/502) | ⬜ Запланировано | — | TBD | Issue #502: объём определён, реализация PENDING | выбор языка интерфейса Client Portal: критерии приёмки | XL|
| [#503](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/503) | ⬜ Запланировано | — | TBD | Issue #503: объём определён, реализация PENDING | статистика трафика клиента за сегодня, 7 и 30 дней: критерии приёмки | L|
| [#504](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/504) | ⬜ Запланировано | — | TBD | Issue #504: объём определён, реализация PENDING | пользовательские названия собственных HWID-устройств: критерии приёмки | M|
| [#505](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/505) | ⬜ Запланировано | — | TBD | Issue #505: объём определён, реализация PENDING | FAQ и общий контакт поддержки в Client Portal: критерии приёмки | S|
| [#506](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/506) | ⬜ Запланировано | — | TBD | Issue #506: объём определён, реализация PENDING | собственная история заказов и платежей клиента: критерии приёмки | M|
| [#507](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/507) | ⬜ Запланировано | — | TBD | Issue #507: объём определён, реализация PENDING | выбор варианта срока тарифа при покупке: критерии приёмки | L|
| [#510](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/510) | ⬜ Запланировано | — | TBD | Issue #510: объём определён, реализация PENDING | определить жизненный цикл и безопасную очистку GitHub-веток: критерии приёмки | L|
| [#564](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/564) | ⬜ Запланировано | — | TBD | Issue #564: объём определён, реализация PENDING | скрыть legacy /create и /inbounds из актуального интерфейса: критерии приёмки | S|
| [#615](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/615) | ⬜ Запланировано | — | TBD | Issue #615: объём определён, реализация PENDING | выбор RU Direct / Full VPN на подписку в Happ и Incy; Shadowrocket позже: критерии приёмки | XL|
| [#617](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/617) | ⬜ Запланировано | — | TBD | Issue #617: объём определён, реализация PENDING | одноразовая emoji-капча для новых клиентов, existing users без повтора: критерии приёмки | L|
| [#691](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/691) | 🟡 Реализовано в main | [#692](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/692) | **v5.0.0-rc.16 (план)** | UI исправлен в `main` после выпуска rc.15: PR #692, commit `235ed3835c0de1ba9f326c90476e491b5afb00e9`; Issue OPEN | Запланировать отдельный release-prep rc.16 с разрешёнными merge/publish/deploy и адресным UI smoke после deployment; только после evidence закрыть #691. rc.16 пока **не Published / не Deployed / не Accepted** | S|
| [#699](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/699) | ⬜ Запланировано | — | TBD | 2026-10-16: новый Issue; текущий bot manifest не включает Xray Outbounds API | Read-only просмотр/диагностика Outbounds 3x-ui, затем отдельно защищённое изменение; upstream API contract, RBAC, rollback, #482/#487; без production writes | XL|
| [#700](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/700) | ⬜ Запланировано | — | TBD | 2026-10-16: новый Issue; upstream 3x-ui имеет `routeTest`, бот его не использует | Отдельная серверная маршрутизация Xray: read-only rules и синтетический routeTest, затем gated CRUD; зависит от #699; не client-side #615 и не доказательство live reachability | XL|
| [#701](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/701) | ⬜ Запланировано | — | TBD | 2026-10-16: новый Issue; Host Groups 3x-ui read-only уже по закрытому #422, локальные User Groups — отдельная модель | Группы **клиентов 3x-ui**: read-only Master API, позднее guarded membership/CRUD; не смешивать Telegram audience и Host/Server Groups; #496 отдельно | L|
| [#702](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/702) | ⬜ Запланировано | — | TBD | 2026-10-16: новый Issue, пример `page-mascot`; собственной страницы подписки пока нет | После появления custom subscription page: optional mascot, лицензия/ассеты, reduced-motion, privacy и мобильная доступность; действующий proxy не менять | M|
| [#703](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/703) | ⬜ Запланировано | — | TBD | 2026-10-16: новый Issue, пример iwtsy.com; публичный API третьей стороны не подтверждён | Только свои/разрешённые адреса: региональные TCP/SSH probes, различать connect/RST/banner/timeout; consent, SSRF, rate limits, внешний API или собственные probes; #478 — отдельная система | XL|
| [#705](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/705) | ⬜ Запланировано | — | TBD | 2026-10-16: проверены форма создания тарифов, SQLite `stars_price`, локальные User Groups и отложенный PSP #336 | Раздельные необязательные цены: Telegram только Stars/XTR, независимый сайт только RUB (без RUB checkout/ссылок из бота); общая авторизованная выдача entitlement с раздельным учётом; активность ≠ видимость/продаваемость, группы User Groups; скрытый бесплатный бессрочный (`duration_days=0`) безлимитный план только для ручной выдачи; #336/#496/#507, безопасная миграция и тесты | XL|
| [#707](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/707) | ⬜ Запланировано | — | TBD | 2026-10-16: утверждены предоставленные оператором Terms/Privacy и правила возвратов | Раздел `📄 Документы и условия` с `/legal/terms`, `/legal/privacy`, `/legal/tariffs`; публичные web URLs, версионированный явный акцепт перед Stars/RUB checkout; не публиковать тестовую ссылку и черновики; #433/#434/#436 superseded/not_planned | L|

## Завершённые этапы и исторические документы

v4.x: protected Admin Control Plane, RBAC, Host Control, backup/DR, self-update, monitoring, User Management и final security hardening (stable `v4.26.9`). v5 rc.1…rc.9: controlled canary с отдельными findings и scoped smoke; **не** общий v5 PASS. Подробная хронология: [CHANGELOG](../CHANGELOG.md), [Releases](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases), [исторический индекс](roadmap/HISTORY_INDEX.md).

## План размещения юридических документов (#707)

**План:** Client Portal → `📄 Документы и условия` → `/legal/terms` (Пользовательское соглашение), `/legal/privacy` (Политика конфиденциальности), `/legal/tariffs` (Тарифы и лимиты). Web-сайт показывает те же постоянные ссылки без авторизации и оплаты. В Telegram после publication доступ через клиентский раздел в рамках действующего pilot gate; до публикации — не показывать недоступные URL как рабочие.

**Акцепт:** перед Stars invoice и перед RUB checkout на отдельном сайте нужно явное подтверждение действующей редакции, зафиксированное сервером с version/time/account/order; один `/start` не считается явно подтверждённым согласием. **Возвраты:** утверждённые оператором условия раздела 9 юристом подготовленного соглашения, без дополнительной добровольной 14-дневной опции. #433/#434/#436 — Closed/`not_planned` (заменены, не выполнены). **Связи:** #336 (RUB только на самостоятельном сайте), #705 (RUB/XTR тарифы), #437 (памятка поддержки). Юридические HTML-файлы, тестовый enrollment URL и незаполненные реквизиты не публиковать без позднейшего решения.

## Правило дальнейшего ведения

**Не добавлять новый длинный датированный раздел в начало Roadmap.** После проверки обновлять **существующую** строку gate/Issue + ссылку на новый датированный audit с tag/SHA, временем/таймзоной, scope, evidence, ограничениями, FAIL/unknown; не переписывать старые snapshots. Обязательны PR, required `test`/`title`, squash merge, независимый read-back `main` и сверка связанных Issues **до следующего пакета**. См. [GIT_WORKFLOW](GIT_WORKFLOW.md) и [LIVING_DOCS](LIVING_DOCS.md).
