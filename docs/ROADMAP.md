# Дорожная карта проекта

> **Канонический актуальный статус.** Старый Roadmap (5803 строки) сохранён побайтово в [тематическом историческом архиве](roadmap/HISTORY_INDEX.md), original blob `7303286842241ee29b7cbefbabbe4780911043dd`. Исторические сведения и прежние FAIL/STOP/WAIVED не стираются и не являются сегодняшними статусами. Нормативная [приёмка v5](V5_PRODUCTION_ACCEPTANCE.md), [release history](../CHANGELOG.md).

## Актуальная сводка проекта

**Срез на 2026-10-16 (EEST, UTC+03:00).** Источник текущих фактов — GitHub `main`, опубликованные immutable tags, состояния Issues и датированные сообщения оператора. Хронология rc.11–rc.14 сохраняется в [CHANGELOG](../CHANGELOG.md), [GitHub Releases](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases) и [датированных audits](audits/); исторические scoped проверки не заменяют текущую приёмку.

**Published:** immutable [`v5.0.0-rc.15`](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.15), tag SHA `9c9245899c7ca949254df92d95f8015e65989645`, публикация `2026-10-16T12:53:58Z`. **Deployed:** `rc.15` с этим SHA — **только по сообщению оператора** от `2026-10-16T13:16:00Z` ([#691](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/691)); точное время развёртывания, независимое чтение VPS/image/container digest/Xray **PENDING**. **Accepted:** оператор сообщил A6.1/A6.2/A6.3 `PASS`, N6/R3 `MATCH`, успешный scoped Flow POST и сохранность соседних протоколов для конкретного пользователя и двух нод; независимая DB/Xray attestation **PENDING**. Общий v5 `NOT PASS`, G-11 `PARTIAL / NO-GO`; stable/public rollout и расширение pilot allowlist **BLOCKED**.

**В `main`:** UI-only [PR #692](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/692) (раздельный shared/scoped Flow, исторический Node read-back и подписи) squash merged `235ed3835c0de1ba9f326c90476e491b5afb00e9`; этого кода **нет** в immutable `rc.15`. [Issue #691](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/691) `OPEN` до отдельно разрешённых release/deployment, целевого UI smoke и closure audit. [PR #693](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/693) по контракту 3x-ui v3.10.2 и закрытию Issues — `OPEN`, его изменения пока не являются состоянием `main`.

**Состояние Issues:** #648, #649, #650, #659, #663 и #679 в GitHub закрыты; их узкие подтверждения не означают общий v5 `PASS` и не входят в активный реестр. [#694](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/694) отслеживает актуализацию Roadmap и README. Следующие незавершённые направления: UI acceptance #691, нагрузка 3x-ui API #482, сверка Master↔Node #487 и незакрытые критерии G-11. Любые production mutations, merge, release и deployment требуют отдельного разрешения.

## Статусы дорожной карты

- `⬜ Запланировано` — работа ещё не завершена в `main`;
- `🟡 Реализовано в main` — код/документация уже слиты, но соответствующий release ещё не опубликован;
- `🟠 Опубликовано; acceptance отложен` — release опубликован, но отдельный обязательный production acceptance, targeted smoke или recovery drill ещё не завершён;
- `✅ Выполнено в vX.Y.Z` — изменение опубликовано и весь обязательный acceptance scope подтверждён.

`PASS/PARTIAL/PENDING/FAIL/BLOCKED` — результаты проверок, не дополнительные статусы Roadmap. **Merged, Published, Deployed и Accepted — раздельные состояния.**

**Infrastructure post-upgrade (2026-10-14):** оператор сообщил, что production Master и все direct nodes уже обновлены до **3x-ui v3.10.0**, Xray до **v26.10.10**; сервисы, Fleet UI, bot и доступный VPN-трафик — targeted operator-reported scoped PASS ([audit](audits/2026-10-14-3xui-v3100-production-postupgrade-readback.md)). Master↔Node client/expiry, active/expired VPN smoke на ВСЕХ нодах оператор сообщил PASS; restore/regression не выполнялись (см. [closure audit](audits/2026-10-14-3xui-v3100-issue630-targeted-smoke-closure.md)), #487 PENDING, [#630](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/630) закрыт `completed` в revised smoke-only scope. Это **не** изменение Published bot rc.9, не общий G-11 PASS и не разрешение на stable/public rollout.

## Текущий этап: v5 Client Portal

**🟠 Опубликовано; общий v5 acceptance отложен — controlled canary `v5.0.0-rc.15`.** Pilot Client Portal (Stars, idempotent entitlement, quota-cycle, guarded callbacks) и защищённый `/admin`; SQLite schema `v13`. По сообщению оператора установлена 3x-ui `v3.10.2`, но закреплённый API contract текущего `main` — `v3.10.0` (изменение manifest находится только в [PR #693](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/693)). Общий v5 `NOT PASS`: актуальные G-01…G-11 и waivers — ниже, результаты завершённых этапов — в [аудитах](audits/) и [закрытых Issues](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues?q=is%3Aissue+is%3Aclosed).

## Реестр acceptance-gates v5

| Gate | Что проверено | Итог gate | Осталось / риск |
| --- | --- | --- | --- |
| G-01 | Health/source smoke 5/5; A1 parity 7/7; лимит 30/60 — scoped PASS | PARTIAL | Независимая аттестация deployed image PENDING |
| G-02 | Ledger/Master read 5/5, B1 mismatches/orphans/duplicates 0; Node match — scoped PASS | PARTIAL | Полная сверка и Node offline→return [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) PENDING |
| G-03 | Stars→VPN и B4 архив 4/4 — PASS со слов оператора | PARTIAL | Независимое подтверждение происхождения payment→import PENDING |
| G-04 | Refund/Support journal — scoped PASS подтверждён | PARTIAL | Provider/revoke postconditions PENDING; policy [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) future |
| G-05 | После перезапуска ledger/health, B3 provider read, C1 offline no-replay — scoped PASS | PARTIAL | Interrupted paid-work/full no-replay PENDING |
| G-06 | Offline limiter; D1 natural-cycle второй снимок и D2 backup — scoped PASS ([audit](audits/2026-10-14-v5-d1-second-natural-cycle-readback.md)) | PARTIAL | Full V5-A-003 soak PENDING; queue NOT_INSTRUMENTED |
| G-07 | Изоляция A/B, отказ админ-доступа, C2 offline forged callbacks — scoped PASS | PARTIAL | Подтверждение реального транспорта при недоверенных входных данных PENDING |
| G-08 | Portal OFF/ON, Stars toggle audit и health — scoped PASS | PARTIAL | Invoice/precheckout и paid event при OFF PENDING; повторять toggle нельзя |
| G-09 | Natural paid Stars entitlement: SQLite expired ↔ Master disabled/expiry ↔ Telegram/VPN — operator-reported scoped PASS ([audit](audits/2026-10-14-v5-g09-natural-paid-expiry-readback.md)) | PASS | Независимая VPS/data-plane attestation отсутствует; AWG RTT без интернета REVIEW; не full v5 acceptance |
| G-10 | QA synthetic 4/4 и Attention Center UI — scoped PASS; natural main-bot `job_failed` NOT TESTED ([W-03 audit](audits/2026-10-14-v5-g10-w03-natural-job-failed-risk-acceptance.md)) | PARTIAL | W-03 operator-waived для [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466), не PASS; live notification/cooldown/recovery и две проекции не доказаны |
| G-11 | Финальный [acceptance report](audits/v5-production-acceptance-2026-10-14.md) составлен; итог `CONDITIONAL / NO-GO` без full production acceptance | PARTIAL | Обязательные V5-A-001…A-003, ownership/rollback/reconciliation не закрыты; G-01…G-08/G-10 PARTIAL, W-01/W-02/W-03 не PASS; public/stable BLOCKED |

### Реестр принятых исключений

| Исключение | Решение оператора | Не проверено / остаточный риск |
| --- | --- | --- |
| W-01 | OPERATOR-WAIVED / NOT TESTED | Независимый cross-host Master DR не проводился; не PASS |
| W-02 | OPERATOR-WAIVED / INCONCLUSIVE | Реальный Telegram burst не доказан; не PASS |
| W-03 | OPERATOR-WAIVED / NOT TESTED | Естественное событие main-bot `job_failed` [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466): new/reminder/recovery/cooldown и две проекции Attention Center не наблюдались ([audit](audits/2026-10-14-v5-g10-w03-natural-job-failed-risk-acceptance.md)); не PASS |

Полные исторические наблюдения, включая старые FAIL, тайминги, данные G-01…G-11 и правильную идентичность DR-хоста: [архив проверок v5](audits/roadmap-history/v5-gates.md), [датированные audits](audits/), [карта переноса](roadmap/HISTORY_INDEX.md). Итоговые короткие строки не отменяют нормативные критерии [V5_PRODUCTION_ACCEPTANCE](V5_PRODUCTION_ACCEPTANCE.md).

## Текущая очередь и блокировки

1. **G-11 / PARTIAL:** [финальный отчёт](audits/v5-production-acceptance-2026-10-14.md) имеет итог `CONDITIONAL / NO-GO`; полный V5-A-001…A-003, ownership, rollback и global reconciliation требуют нового отдельно согласованного scope/нормативного решения. Нельзя снимать блокировку stable/public rollout; без разрешения production operations не запускать.

Прочие незакрытые работы — в gate-реестре и [активных GitHub Issues](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues); W-03 отражает принятое оператором исключение по закрытому как `not_planned` [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466); новый PASS не заявлен. Завершённые D1 [audit](audits/2026-10-14-v5-d1-second-natural-cycle-readback.md) и G-09 [audit](audits/2026-10-14-v5-g09-natural-paid-expiry-readback.md) не являются новыми задачами. Отдельные PASS/waivers не заменяют полного v5 acceptance; новых production mutations без согласования нет.

## Реестр открытых задач и будущие релизы

**Будущая работа:** единственный полный перечень OPEN задач — в реестре ниже; [GitHub Issues](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues) содержат scope и acceptance. Не дублировать отдельные списки и завершённые outcomes в living Roadmap. Рабочие концепции: [provider-neutral](roadmap/concepts/provider-neutral-remnawave.md), [Client Portal UX](roadmap/concepts/client-portal-ux.md).

## Активный Issue-реестр (machine-checked)

Ровно одна строка на каждый открытый GitHub Issue; подробности остаются в Issue. `—` означает отсутствие PR, `TBD` — ещё не опубликованная целевая версия, не гарантированный release. Даты и свидетельства проверок — в отдельных аудитах.

**Объём (предварительная относительная оценка):** `XS` — до 1 инженерного чел.-дня; `S` — 2–3; `M` — 4–8; `L` — 9–15; `XL` — 16+ / эпик с декомпозицией. Включает реализацию, тесты и документацию; **не** календарный срок, SLA или обещание релиза. Юридическая экспертиза, внешние разрешения и отдельный production rollout оцениваются дополнительно. Пересматривать при уточнении scope через PR.

| Issue | Статус | PR | Target release | Evidence | Next / remaining | Объём |
| --- | --- | --- | --- | --- | --- | --- |
| [#336](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/336) | ⬜ Запланировано | — | TBD | Критерии Issue #336; реализация PENDING | внешний платёжный шлюз и СБП с уникальными ссылками: критерии в Issue | XL|
| [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) | ⬜ Запланировано | — | TBD | 2026-10-14 21:44 EEST: оператор отложил #433, план возобновления в Issue; реализации нет | Возобновить только по новому решению: приём запросов, неизменяемый снимок оплаченного срока, ручная проверка истории, журнал/сверка, юридическая часть #436; в rc.10 не входило; G-11 NO-GO | XL|
| [#434](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/434) | ⬜ Запланировано | — | TBD | Критерии Issue #434; реализация PENDING | ненавязчивые условия возврата в клиентском портале: критерии в Issue | S|
| [#436](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/436) | ⬜ Запланировано | — | TBD | Критерии Issue #436; реализация PENDING | подготовить правовую политику возвратов РФ для самозанятого: критерии в Issue | L|
| [#437](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/437) | ⬜ Запланировано | — | TBD | Критерии Issue #437; реализация PENDING | справочник возвратов для поддержки в админке: критерии в Issue | M|
| [#470](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/470) | ⬜ Запланировано | — | TBD | Критерии Issue #470; реализация PENDING | read-only просмотр Stars Orders в админке: критерии в Issue | M|
| [#471](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/471) | ⬜ Запланировано | — | TBD | Критерии Issue #471; реализация PENDING | компактный список и карточки устройств клиента: критерии в Issue | M|
| [#472](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/472) | ⬜ Запланировано | — | TBD | Критерии Issue #472; реализация PENDING | безопасное удаление одного собственного HWID клиентом: критерии в Issue | L|
| [#473](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/473) | ⬜ Запланировано | — | TBD | Критерии Issue #473; реализация PENDING | безопасные VPN-клиентские deep-link импорты: критерии в Issue | M|
| [#475](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/475) | ⬜ Запланировано | — | TBD | Критерии Issue #475; реализация PENDING | геометаданные страны для direct nodes: критерии в Issue | M|
| [#476](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/476) | ⬜ Запланировано | — | TBD | Критерии Issue #476; реализация PENDING | мультиформатные подписки raw, Xray JSON и Clash/Mihomo: критерии в Issue | XL|
| [#477](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/477) | ⬜ Запланировано | — | TBD | Критерии Issue #477; реализация PENDING | provider-neutral control plane и поддержка Remnawave: критерии в Issue | XL|
| [#478](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/478) | ⬜ Запланировано | — | TBD | Критерии Issue #478; реализация PENDING | региональная сеть Probe reporters для Cheburcheck: критерии в Issue | XL|
| [#479](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/479) | ⬜ Запланировано | — | TBD | Критерии Issue #479; реализация PENDING | внешняя наблюдаемость, сервисный API и signed webhooks: критерии в Issue | XL|
| [#482](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/482) | ⬜ Запланировано | — | TBD | Критерии Issue #482; реализация PENDING | ограничить нагрузку на 3x-ui API перед масштабированием: критерии в Issue | L|
| [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) | ⬜ Запланировано | — | TBD | Критерии Issue #487; реализация PENDING | сверка Master/Node: критерии в Issue | M|
| [#496](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/496) | ⬜ Запланировано | — | TBD | Критерии Issue #496; реализация PENDING | ограничивать видимость функций Client Portal через User Groups: критерии в Issue | L|
| [#497](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/497) | ⬜ Запланировано | — | TBD | Критерии Issue #497; реализация PENDING | полноценная карточка подписки и контекстные действия клиента: критерии в Issue | M|
| [#498](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/498) | ⬜ Запланировано | — | TBD | Критерии Issue #498; реализация PENDING | безопасная ручная синхронизация подписки клиентом: критерии в Issue | L|
| [#499](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/499) | ⬜ Запланировано | — | TBD | Критерии Issue #499; реализация PENDING | применение промокодов при покупке Stars в Client Portal: критерии в Issue | L|
| [#500](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/500) | ⬜ Запланировано | — | TBD | Критерии Issue #500; реализация PENDING | управляемое клиентом автопродление подписки: критерии в Issue | XL|
| [#501](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/501) | ⬜ Запланировано | — | TBD | Критерии Issue #501; реализация PENDING | настройки клиентских уведомлений и напоминаний: критерии в Issue | L|
| [#502](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/502) | ⬜ Запланировано | — | TBD | Критерии Issue #502; реализация PENDING | выбор языка интерфейса Client Portal: критерии в Issue | XL|
| [#503](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/503) | ⬜ Запланировано | — | TBD | Критерии Issue #503; реализация PENDING | статистика трафика клиента за сегодня, 7 и 30 дней: критерии в Issue | L|
| [#504](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/504) | ⬜ Запланировано | — | TBD | Критерии Issue #504; реализация PENDING | пользовательские названия собственных HWID-устройств: критерии в Issue | M|
| [#505](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/505) | ⬜ Запланировано | — | TBD | Критерии Issue #505; реализация PENDING | FAQ и общий контакт поддержки в Client Portal: критерии в Issue | S|
| [#506](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/506) | ⬜ Запланировано | — | TBD | Критерии Issue #506; реализация PENDING | собственная история заказов и платежей клиента: критерии в Issue | M|
| [#507](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/507) | ⬜ Запланировано | — | TBD | Критерии Issue #507; реализация PENDING | выбор варианта срока тарифа при покупке: критерии в Issue | L|
| [#510](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/510) | ⬜ Запланировано | — | TBD | Критерии Issue #510; реализация PENDING | определить жизненный цикл и безопасную очистку GitHub-веток: критерии в Issue | L|
| [#564](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/564) | ⬜ Запланировано | — | TBD | Критерии Issue #564; реализация PENDING | скрыть legacy /create и /inbounds из актуального интерфейса: критерии в Issue | S|
| [#615](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/615) | ⬜ Запланировано | — | TBD | Критерии Issue #615; реализация PENDING | выбор RU Direct / Full VPN на подписку в Happ и Incy; Shadowrocket позже: критерии в Issue | XL|
| [#617](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/617) | ⬜ Запланировано | — | TBD | Критерии Issue #617; реализация PENDING | одноразовая emoji-капча для новых клиентов, для существующих пользователей без повтора: критерии в Issue | L|

| [#691](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/691) | 🟡 Реализовано в main | [#692](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/692) | TBD | UI-only раздельный shared/scoped Flow, исторический Node MATCH и имена Node/Inbound: [PR #692](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/692) merged `235ed3835c0de1ba9f326c90476e491b5afb00e9`, required CI и post-merge PASS | Опубликованный/развёрнутый `rc.15` не включает #692; после отдельно разрешённого release/deploy — целевой UI smoke, проверка границы источников Flow и closure audit; G-11 без нового общего PASS | S |
| [#694](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/694) | ⬜ Запланировано | — | TBD | 2026-10-16: сверка GitHub main/Release/Issues; отслеживание в #694, PR PENDING | Обновить Roadmap/README, русскую терминологию и CI; после merge проверить GitHub main и закрыть собственный Issue только при PASS | S |
## Завершённые этапы и исторические документы

v4.x: protected Admin Control Plane, RBAC, Host Control, backup/DR, self-update, monitoring, User Management и final security hardening (stable `v4.26.9`). v5 rc.1…rc.9: controlled canary с отдельными findings и scoped smoke; **не** общий v5 PASS. Подробная хронология: [CHANGELOG](../CHANGELOG.md), [Releases](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases), [исторический индекс](roadmap/HISTORY_INDEX.md).

## Правило дальнейшего ведения

**Не добавлять новый длинный датированный раздел в начало Roadmap.** После проверки обновлять **существующую** строку gate/Issue + ссылку на новый датированный audit с tag/SHA, временем/таймзоной, scope, evidence, ограничениями, FAIL/unknown; не переписывать старые snapshots. Обязательны PR, required `test`/`title`, squash merge, независимый read-back `main` и сверка связанных Issues **до следующего пакета**. См. [GIT_WORKFLOW](GIT_WORKFLOW.md) и [LIVING_DOCS](LIVING_DOCS.md).
