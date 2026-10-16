# Дорожная карта проекта

> **Канонический актуальный статус.** Старый Roadmap (5803 строки) сохранён побайтово в [тематическом историческом архиве](roadmap/HISTORY_INDEX.md), original blob `7303286842241ee29b7cbefbabbe4780911043dd`. Исторические сведения и прежние FAIL/STOP/WAIVED не стираются и не являются сегодняшними статусами. Нормативная [приёмка v5](V5_PRODUCTION_ACCEPTANCE.md), [release history](../CHANGELOG.md).

## Актуальная сводка проекта

**Merged:** защищённая `main` `235ed3835c0de1ba9f326c90476e491b5afb00e9` (GitHub API, 2026-10-16). Исправление пользовательского UI Flow по [#691](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/691) слито через [PR #692](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/692), но не входит в опубликованный `rc.15`. [PR #693](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/693) с обновлением 3x-ui OpenAPI-контракта и закрытием Issues ещё открыт, его изменения отсутствуют в `main`.

**Published:** неизменяемый GitHub Release [`v5.0.0-rc.15`](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.15), tag SHA `9c9245899c7ca949254df92d95f8015e65989645`, опубликован `2026-10-16T12:53:58Z` (источник: GitHub Releases API). Релиз включает безопасный WG/AWG-scoped Flow из [PR #689](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/689), но не исправление интерфейса из PR #692.

**Deployed:** `v5.0.0-rc.15` / `9c9245899c7ca949254df92d95f8015e65989645` — только `operator-reported` по сообщению `2026-10-16T13:16:00Z` ([#691](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/691)): `Health/DB/3XUI_TCP=ok`, `RestartCount=0`. Точное время развёртывания, независимые VPS/image/digest и DB/Xray read-back — **PENDING**; опубликованный тег не доказывает deployment.

**Accepted:** по сообщению оператора `rc.15` адресные A6.1/A6.2/A6.3, N6/R3 `MATCH`, Flow POST выбранного inbound и сохранность соседних протоколов — **scoped PASS** без независимой DB/Xray-аттестации. Закрытые #648/#649/#650/#659/#663/#679 приняты только по собственным критериям. Общий v5 acceptance **NOT PASS**, G-11 **PARTIAL / NO-GO**; stable/public rollout и расширение pilot allowlist **BLOCKED**. Подробности — [датированные audits](audits/), [GitHub Issues](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues?q=is%3Aissue+is%3Aclosed) и [CHANGELOG](../CHANGELOG.md).

**Незавершённые задачи:** [#691](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/691) OPEN — после отдельно разрешённых выпуска и развёртывания проверить UI из `main` (разделение shared/scoped Flow, исторический снимок Node MATCH и имена). [#694](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/694) OPEN — синхронизировать Roadmap/README. Поддерживаемый API-контракт в `main` закреплён на `3x-ui v3.10.0`; обновление до `v3.10.2` предлагается только в PR #693. Версия установленной панели `v3.10.2` подтверждена оператором отдельно. Без нового разрешения не выполнять production mutations или повторять закрытые/отложенные smoke.

## Статусы дорожной карты

- `⬜ Запланировано` — работа ещё не завершена в `main`;
- `🟡 Реализовано в main` — код/документация уже слиты, но соответствующий release ещё не опубликован;
- `🟠 Опубликовано; acceptance отложен` — release опубликован, но отдельный обязательный production acceptance, targeted smoke или recovery drill ещё не завершён;
- `✅ Выполнено в vX.Y.Z` — изменение опубликовано и весь обязательный acceptance scope подтверждён.

`PASS/PARTIAL/PENDING/FAIL/BLOCKED` — результаты проверок, не дополнительные статусы Roadmap. **Merged, Published, Deployed и Accepted — раздельные состояния.**

**Infrastructure post-upgrade (2026-10-14):** оператор сообщил, что production Master и все direct nodes уже обновлены до **3x-ui v3.10.0**, Xray до **v26.10.10**; сервисы, Fleet UI, bot и доступный VPN-трафик — targeted operator-reported scoped PASS ([audit](audits/2026-10-14-3xui-v3100-production-postupgrade-readback.md)). Master↔Node client/expiry, active/expired VPN smoke на ВСЕХ нодах оператор сообщил PASS; restore/regression не выполнялись (см. [closure audit](audits/2026-10-14-3xui-v3100-issue630-targeted-smoke-closure.md)), #487 PENDING, [#630](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/630) закрыт `completed` в revised smoke-only scope. Это **не** изменение Published bot rc.9, не общий G-11 PASS и не разрешение на stable/public rollout.

## Текущий этап: v5 Client Portal

**🟠 Опубликовано; общий v5 acceptance отложен — controlled canary `v5.0.0-rc.15`**. Client Portal (Stars, idempotent entitlement, quota-cycle, guarded callbacks) и защищённый `/admin` доступны только в контролируемом пилоте. SQLite schema **v13**; поддерживаемый OpenAPI-контракт в `main` — 3x-ui **v3.10.0** (обновление в PR #693 ещё не слито), установленная панель **v3.10.2** — со слов оператора. Общий v5 acceptance **NOT PASS**, G-11 **PARTIAL / NO-GO**. Ниже — незакрытые gates; история, завершённые задачи и подробные результаты — в [закрытых Issues](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues?q=is%3Aissue+is%3Aclosed), [CHANGELOG](../CHANGELOG.md) и [датированных audits](audits/).

## Реестр acceptance-gates v5

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

Ровно одна строка на каждый открытый GitHub Issue; критерии приёмки остаются в самом Issue. `—` означает отсутствие PR, `TBD` — неутверждённую целевую версию, не обещание релиза. Даты и доказательства проверок — в отдельных датированных audits.

**Объём (предварительная относительная оценка):** `XS` — до 1 инженерного чел.-дня; `S` — 2–3; `M` — 4–8; `L` — 9–15; `XL` — 16+ / эпик с декомпозицией. Включает реализацию, тесты и документацию; **не** календарный срок, SLA или обещание релиза. Юридическая экспертиза, внешние разрешения и отдельный производственный выпуск оцениваются дополнительно. Пересматривать при уточнении объёма через PR.

| Issue | Статус | PR | Target release | Evidence | Next / remaining | Объём |
| --- | --- | --- | --- | --- | --- | --- |
| [#336](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/336) | ⬜ Запланировано | — | TBD | Issue #336: критерии зафиксированы, реализация PENDING | внешний платёжный шлюз и СБП с уникальными ссылками: критерии приёмки описаны в Issue | XL|
| [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) | ⬜ Запланировано | — | TBD | 2026-10-14 21:44 EEST: оператор отложил работу (DEFERRED), план возобновления в #433, реализации нет | Вернуться только по новому решению: intake, immutable duration snapshot, ручной просмотр исторических заявок, journal/reconciliation, правовые вопросы #436; область rc.10 исключена (EXCLUDED); G-11 NO-GO | XL|
| [#434](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/434) | ⬜ Запланировано | — | TBD | Issue #434: критерии зафиксированы, реализация PENDING | ненавязчивые условия возврата в клиентском портале: критерии приёмки описаны в Issue | S|
| [#436](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/436) | ⬜ Запланировано | — | TBD | Issue #436: критерии зафиксированы, реализация PENDING | подготовить правовую политику возвратов РФ для самозанятого: критерии приёмки описаны в Issue | L|
| [#437](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/437) | ⬜ Запланировано | — | TBD | Issue #437: критерии зафиксированы, реализация PENDING | справочник возвратов для поддержки в админке: критерии приёмки описаны в Issue | M|
| [#470](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/470) | ⬜ Запланировано | — | TBD | Issue #470: критерии зафиксированы, реализация PENDING | read-only просмотр Stars Orders в админке: критерии приёмки описаны в Issue | M|
| [#471](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/471) | ⬜ Запланировано | — | TBD | Issue #471: критерии зафиксированы, реализация PENDING | компактный список и карточки устройств клиента: критерии приёмки описаны в Issue | M|
| [#472](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/472) | ⬜ Запланировано | — | TBD | Issue #472: критерии зафиксированы, реализация PENDING | безопасное удаление одного собственного HWID клиентом: критерии приёмки описаны в Issue | L|
| [#473](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/473) | ⬜ Запланировано | — | TBD | Issue #473: критерии зафиксированы, реализация PENDING | безопасные VPN-клиентские deep-link импорты: критерии приёмки описаны в Issue | M|
| [#475](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/475) | ⬜ Запланировано | — | TBD | Issue #475: критерии зафиксированы, реализация PENDING | геометаданные страны для direct nodes: критерии приёмки описаны в Issue | M|
| [#476](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/476) | ⬜ Запланировано | — | TBD | Issue #476: критерии зафиксированы, реализация PENDING | мультиформатные подписки raw, Xray JSON и Clash/Mihomo: критерии приёмки описаны в Issue | XL|
| [#477](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/477) | ⬜ Запланировано | — | TBD | Issue #477: критерии зафиксированы, реализация PENDING | provider-neutral control plane и поддержка Remnawave: критерии приёмки описаны в Issue | XL|
| [#478](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/478) | ⬜ Запланировано | — | TBD | Issue #478: критерии зафиксированы, реализация PENDING | региональная сеть Probe reporters для Cheburcheck: критерии приёмки описаны в Issue | XL|
| [#479](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/479) | ⬜ Запланировано | — | TBD | Issue #479: критерии зафиксированы, реализация PENDING | внешняя наблюдаемость, сервисный API и signed webhooks: критерии приёмки описаны в Issue | XL|
| [#482](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/482) | ⬜ Запланировано | — | TBD | Issue #482: критерии зафиксированы, реализация PENDING | ограничить нагрузку на 3x-ui API перед масштабированием: критерии приёмки описаны в Issue | L|
| [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) | ⬜ Запланировано | — | TBD | Issue #487: критерии зафиксированы, реализация PENDING | синхронизация Master и Node: критерии приёмки описаны в Issue | M|
| [#496](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/496) | ⬜ Запланировано | — | TBD | Issue #496: критерии зафиксированы, реализация PENDING | ограничивать видимость функций Client Portal через User Groups: критерии приёмки описаны в Issue | L|
| [#497](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/497) | ⬜ Запланировано | — | TBD | Issue #497: критерии зафиксированы, реализация PENDING | полноценная карточка подписки и контекстные действия клиента: критерии приёмки описаны в Issue | M|
| [#498](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/498) | ⬜ Запланировано | — | TBD | Issue #498: критерии зафиксированы, реализация PENDING | безопасная ручная синхронизация подписки клиентом: критерии приёмки описаны в Issue | L|
| [#499](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/499) | ⬜ Запланировано | — | TBD | Issue #499: критерии зафиксированы, реализация PENDING | применение промокодов при покупке Stars в Client Portal: критерии приёмки описаны в Issue | L|
| [#500](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/500) | ⬜ Запланировано | — | TBD | Issue #500: критерии зафиксированы, реализация PENDING | управляемое клиентом автопродление подписки: критерии приёмки описаны в Issue | XL|
| [#501](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/501) | ⬜ Запланировано | — | TBD | Issue #501: критерии зафиксированы, реализация PENDING | настройки клиентских уведомлений и напоминаний: критерии приёмки описаны в Issue | L|
| [#502](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/502) | ⬜ Запланировано | — | TBD | Issue #502: критерии зафиксированы, реализация PENDING | выбор языка интерфейса Client Portal: критерии приёмки описаны в Issue | XL|
| [#503](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/503) | ⬜ Запланировано | — | TBD | Issue #503: критерии зафиксированы, реализация PENDING | статистика трафика клиента за сегодня, 7 и 30 дней: критерии приёмки описаны в Issue | L|
| [#504](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/504) | ⬜ Запланировано | — | TBD | Issue #504: критерии зафиксированы, реализация PENDING | пользовательские названия собственных HWID-устройств: критерии приёмки описаны в Issue | M|
| [#505](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/505) | ⬜ Запланировано | — | TBD | Issue #505: критерии зафиксированы, реализация PENDING | FAQ и общий контакт поддержки в Client Portal: критерии приёмки описаны в Issue | S|
| [#506](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/506) | ⬜ Запланировано | — | TBD | Issue #506: критерии зафиксированы, реализация PENDING | собственная история заказов и платежей клиента: критерии приёмки описаны в Issue | M|
| [#507](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/507) | ⬜ Запланировано | — | TBD | Issue #507: критерии зафиксированы, реализация PENDING | выбор варианта срока тарифа при покупке: критерии приёмки описаны в Issue | L|
| [#510](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/510) | ⬜ Запланировано | — | TBD | Issue #510: критерии зафиксированы, реализация PENDING | определить жизненный цикл и безопасную очистку GitHub-веток: критерии приёмки описаны в Issue | L|
| [#564](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/564) | ⬜ Запланировано | — | TBD | Issue #564: критерии зафиксированы, реализация PENDING | скрыть legacy /create и /inbounds из актуального интерфейса: критерии приёмки описаны в Issue | S|
| [#615](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/615) | ⬜ Запланировано | — | TBD | Issue #615: критерии зафиксированы, реализация PENDING | выбор RU Direct / Full VPN на подписку в Happ и Incy; Shadowrocket позже: критерии приёмки описаны в Issue | XL|
| [#617](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/617) | ⬜ Запланировано | — | TBD | Issue #617: критерии зафиксированы, реализация PENDING | одноразовая emoji-капча для новых клиентов, для существующих пользователей без повтора: критерии приёмки описаны в Issue | L|
| [#691](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/691) | 🟡 Реализовано в main | [#692](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/692) | TBD | 2026-10-16: PR #692 слит в `main` `235ed3835c0de1ba9f326c90476e491b5afb00e9`; required CI `test`/`title` и read-back PASS, но UI не вошёл в опубликованный rc.15 | После разрешённых release/deploy проверить разделение shared/scoped Flow, исторический Node MATCH, подписи Node/Inbound; #691 OPEN до targeted acceptance | S |
| [#694](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/694) | ⬜ Запланировано | — | TBD | 2026-10-16: GitHub выявил шесть закрытых Issues в активном реестре, старый Published и неактуальный README; docs/test исправление готовится в ветке | Проверить PR с required `test`/`title`; после отдельного разрешения merge — сверка `main` с GitHub и Issue audit | S |

## Завершённые этапы и исторические документы

v4.x: protected Admin Control Plane, RBAC, Host Control, backup/DR, self-update, monitoring, User Management и final security hardening (stable `v4.26.9`). v5 rc.1…rc.15: контролируемые предварительные выпуски с отдельными дефектами и адресными проверками; **не** общий v5 PASS. Подробная хронология: [CHANGELOG](../CHANGELOG.md), [Releases](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases), [исторический индекс](roadmap/HISTORY_INDEX.md).

## Правило дальнейшего ведения

**Не добавлять новый длинный датированный раздел в начало Roadmap.** После проверки обновлять **существующую** строку gate/Issue + ссылку на новый датированный audit с tag/SHA, временем/таймзоной, scope, evidence, ограничениями, FAIL/unknown; не переписывать старые snapshots. Обязательны PR, required `test`/`title`, squash merge, независимый read-back `main` и сверка связанных Issues **до следующего пакета**. См. [GIT_WORKFLOW](GIT_WORKFLOW.md) и [LIVING_DOCS](LIVING_DOCS.md).
