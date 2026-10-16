# Дорожная карта проекта

> **Канонический актуальный статус.** Старый Roadmap (5803 строки) сохранён побайтово в [тематическом историческом архиве](roadmap/HISTORY_INDEX.md), original blob `7303286842241ee29b7cbefbabbe4780911043dd`. Исторические сведения и прежние FAIL/STOP/WAIVED не стираются и не являются сегодняшними статусами. Нормативная [приёмка v5](V5_PRODUCTION_ACCEPTANCE.md), [release history](../CHANGELOG.md).

## Актуальная сводка проекта

**Контрольная точка 2026-10-16 (Europe/Helsinki).** По независимому чтению GitHub последний объединённый UI PR — [#692](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/692), commit в `main` `235ed3835c0de1ba9f326c90476e491b5afb00e9`. Изменения интерфейса из #692 **не входят** в опубликованный `rc.15`. Отдельный [PR #693](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/693) с обновлением поддерживаемого OpenAPI 3x-ui и синхронизацией закрытых Issues остаётся **OPEN**, пока не объединён с `main`.

**Published:** GitHub подтвердил immutable prerelease [`v5.0.0-rc.15`](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.15), tag SHA `9c9245899c7ca949254df92d95f8015e65989645`, время публикации `2026-10-16T12:53:58Z`. Публикация не является развёртыванием.

**Deployed:** `v5.0.0-rc.15` / `9c9245899c7ca949254df92d95f8015e65989645` — **только operator-reported** по сообщению от `2026-10-16T13:16:00Z` ([Issue #691](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/691)): `DEPLOY_OK`, `Health/DB/3XUI_TCP=ok`, `RestartCount=0`. Точное время развёртывания неизвестно; независимая аттестация VPS, image/container digest и Xray/DB **PENDING**.

**Accepted:** оператор сообщил ограниченный `PASS` для A6.1/A6.2/A6.3, `MATCH` для N6/R3, успешную адресную запись Flow в выбранный inbound и сохранность соседних протоколов. Это не независимая проверка БД или Xray. Issues #648/#649/#650/#659/#663/#679 закрыты в GitHub по собственным целевым критериям; [#691](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/691) **OPEN**, приёмка его исправления после нового выпуска и развёртывания **PENDING**. Общий v5 acceptance **NOT PASS**, G-11 **PARTIAL / NO-GO**, снятие pilot allowlist и стабильный публичный запуск **BLOCKED**.

**Следующий шаг:** отдельное решение оператора о публикации/развёртывании UI-исправления #691, затем адресная проверка интерфейса. Эта правка документации не выполняет production mutations. Подробные результаты прежних RC, включая неуспешные проверки и ограничения, сохранены в [датированных аудитах](audits/), [CHANGELOG](../CHANGELOG.md) и [GitHub Releases](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases).

## Статусы дорожной карты

- `⬜ Запланировано` — работа ещё не завершена в `main`;
- `🟡 Реализовано в main` — код/документация уже слиты, но соответствующий release ещё не опубликован;
- `🟠 Опубликовано; acceptance отложен` — release опубликован, но отдельный обязательный production acceptance, targeted smoke или recovery drill ещё не завершён;
- `✅ Выполнено в vX.Y.Z` — изменение опубликовано и весь обязательный acceptance scope подтверждён.

`PASS/PARTIAL/PENDING/FAIL/BLOCKED` — результаты проверок, не дополнительные статусы Roadmap. **Merged, Published, Deployed и Accepted — раздельные состояния.**


## Текущий этап: v5 Client Portal

**🟠 Опубликовано; общий v5 acceptance отложен — контролируемый пилот `v5.0.0-rc.15`**. Client Portal (Stars, entitlement, quota cycle, guarded callbacks), защищённый `/admin`; SQLite schema v13. Текущий поддерживаемый OpenAPI в `main` остаётся закреплён за 3x-ui `v3.10.0` до объединения PR #693; для адресного изменения Flow в rc.15 требуется точная версия Master `panelVersion=3.10.2`. По сообщению оператора 3x-ui v3.10.2 установлена, независимое подтверждение сервера PENDING. **Общий v5 acceptance NOT PASS**. Актуальные gates — ниже; история закрытых задач хранится в [GitHub Issues](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues?q=is%3Aissue+is%3Aclosed) и [аудитах](audits/).

## Реестр acceptance-gates v5 (измерения исходного rc.9 сохраняются)

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
| [#336](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/336) | ⬜ Запланировано | — | TBD | Критерии Issue #336; реализация PENDING | внешний платёжный шлюз и СБП с уникальными ссылками: критерии приёмки в Issue | XL|
| [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) | ⬜ Запланировано | — | TBD | 2026-10-14 21:44 EEST: отложено оператором (DEFERRED); условия возобновления Issue #433 описаны, реализации нет | Вернуться только по новому решению: intake, immutable duration snapshot, manual historic review, journal/reconciliation, legal #436; выпуск rc.10 исключён из объёма (EXCLUDED); G-11 NO-GO | XL|
| [#434](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/434) | ⬜ Запланировано | — | TBD | Критерии Issue #434; реализация PENDING | ненавязчивые условия возврата в клиентском портале: критерии приёмки в Issue | S|
| [#436](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/436) | ⬜ Запланировано | — | TBD | Критерии Issue #436; реализация PENDING | подготовить правовую политику возвратов РФ для самозанятого: критерии приёмки в Issue | L|
| [#437](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/437) | ⬜ Запланировано | — | TBD | Критерии Issue #437; реализация PENDING | справочник возвратов для поддержки в админке: критерии приёмки в Issue | M|
| [#470](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/470) | ⬜ Запланировано | — | TBD | Критерии Issue #470; реализация PENDING | read-only просмотр Stars Orders в админке: критерии приёмки в Issue | M|
| [#471](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/471) | ⬜ Запланировано | — | TBD | Критерии Issue #471; реализация PENDING | компактный список и карточки устройств клиента: критерии приёмки в Issue | M|
| [#472](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/472) | ⬜ Запланировано | — | TBD | Критерии Issue #472; реализация PENDING | безопасное удаление одного собственного HWID клиентом: критерии приёмки в Issue | L|
| [#473](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/473) | ⬜ Запланировано | — | TBD | Критерии Issue #473; реализация PENDING | безопасные VPN-клиентские deep-link импорты: критерии приёмки в Issue | M|
| [#475](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/475) | ⬜ Запланировано | — | TBD | Критерии Issue #475; реализация PENDING | геометаданные страны для direct nodes: критерии приёмки в Issue | M|
| [#476](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/476) | ⬜ Запланировано | — | TBD | Критерии Issue #476; реализация PENDING | мультиформатные подписки raw, Xray JSON и Clash/Mihomo: критерии приёмки в Issue | XL|
| [#477](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/477) | ⬜ Запланировано | — | TBD | Критерии Issue #477; реализация PENDING | provider-neutral control plane и поддержка Remnawave: критерии приёмки в Issue | XL|
| [#478](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/478) | ⬜ Запланировано | — | TBD | Критерии Issue #478; реализация PENDING | региональная сеть Probe reporters для Cheburcheck: критерии приёмки в Issue | XL|
| [#479](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/479) | ⬜ Запланировано | — | TBD | Критерии Issue #479; реализация PENDING | внешняя наблюдаемость, сервисный API и signed webhooks: критерии приёмки в Issue | XL|
| [#482](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/482) | ⬜ Запланировано | — | TBD | Критерии Issue #482; реализация PENDING | ограничить нагрузку на 3x-ui API перед масштабированием: критерии приёмки в Issue | L|
| [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) | ⬜ Запланировано | — | TBD | Критерии Issue #487; реализация PENDING | Master/Node sync: критерии приёмки в Issue | M|
| [#496](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/496) | ⬜ Запланировано | — | TBD | Критерии Issue #496; реализация PENDING | ограничивать видимость функций Client Portal через User Groups: критерии приёмки в Issue | L|
| [#497](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/497) | ⬜ Запланировано | — | TBD | Критерии Issue #497; реализация PENDING | полноценная карточка подписки и контекстные действия клиента: критерии приёмки в Issue | M|
| [#498](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/498) | ⬜ Запланировано | — | TBD | Критерии Issue #498; реализация PENDING | безопасная ручная синхронизация подписки клиентом: критерии приёмки в Issue | L|
| [#499](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/499) | ⬜ Запланировано | — | TBD | Критерии Issue #499; реализация PENDING | применение промокодов при покупке Stars в Client Portal: критерии приёмки в Issue | L|
| [#500](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/500) | ⬜ Запланировано | — | TBD | Критерии Issue #500; реализация PENDING | управляемое клиентом автопродление подписки: критерии приёмки в Issue | XL|
| [#501](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/501) | ⬜ Запланировано | — | TBD | Критерии Issue #501; реализация PENDING | настройки клиентских уведомлений и напоминаний: критерии приёмки в Issue | L|
| [#502](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/502) | ⬜ Запланировано | — | TBD | Критерии Issue #502; реализация PENDING | выбор языка интерфейса Client Portal: критерии приёмки в Issue | XL|
| [#503](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/503) | ⬜ Запланировано | — | TBD | Критерии Issue #503; реализация PENDING | статистика трафика клиента за сегодня, 7 и 30 дней: критерии приёмки в Issue | L|
| [#504](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/504) | ⬜ Запланировано | — | TBD | Критерии Issue #504; реализация PENDING | пользовательские названия собственных HWID-устройств: критерии приёмки в Issue | M|
| [#505](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/505) | ⬜ Запланировано | — | TBD | Критерии Issue #505; реализация PENDING | FAQ и общий контакт поддержки в Client Portal: критерии приёмки в Issue | S|
| [#506](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/506) | ⬜ Запланировано | — | TBD | Критерии Issue #506; реализация PENDING | собственная история заказов и платежей клиента: критерии приёмки в Issue | M|
| [#507](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/507) | ⬜ Запланировано | — | TBD | Критерии Issue #507; реализация PENDING | выбор варианта срока тарифа при покупке: критерии приёмки в Issue | L|
| [#510](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/510) | ⬜ Запланировано | — | TBD | Критерии Issue #510; реализация PENDING | определить жизненный цикл и безопасную очистку GitHub-веток: критерии приёмки в Issue | L|
| [#564](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/564) | ⬜ Запланировано | — | TBD | Критерии Issue #564; реализация PENDING | скрыть legacy /create и /inbounds из актуального интерфейса: критерии приёмки в Issue | S|
| [#615](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/615) | ⬜ Запланировано | — | TBD | Критерии Issue #615; реализация PENDING | выбор RU Direct / Full VPN на подписку в Happ и Incy; Shadowrocket позже: критерии приёмки в Issue | XL|
| [#617](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/617) | ⬜ Запланировано | — | TBD | Критерии Issue #617; реализация PENDING | одноразовая emoji-капча для новых клиентов, постоянные клиенты без повтора: критерии приёмки в Issue | L|
| [#691](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/691) | 🟡 Реализовано в main | [#692](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/692) | TBD | Исправлено отображение shared/scoped Flow, исторического Node MATCH и имён Node/Inbound, PR #692 squash merged `235ed3835c0de1ba9f326c90476e491b5afb00e9`; required CI и post-merge PASS | Опубликованный и развёрнутый rc.15 не включает PR #692; целевая проверка интерфейса — только после разрешённых Release/deployment, затем аудит закрытия Issue. Общий G-11 без новых PASS | S|
| [#694](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/694) | ⬜ Запланировано | — | TBD | Проверка GitHub 2026-10-16: устаревшие релизные сведения, закрытые Issues в активном реестре и смешанная локализация; правка в отдельном PR, CI PENDING | Синхронизировать Roadmap и README, добавить регрессионные проверки, получить `test`/`title` PASS и выполнить независимый GitHub read-back; до merge состояние PENDING | S |

## Завершённые этапы и исторические документы

v4.x: protected Admin Control Plane, RBAC, Host Control, backup/DR, self-update, monitoring, User Management и final security hardening (stable `v4.26.9`). v5 rc.1…rc.9: controlled canary с отдельными findings и scoped smoke; **не** общий v5 PASS. Подробная хронология: [CHANGELOG](../CHANGELOG.md), [Releases](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases), [исторический индекс](roadmap/HISTORY_INDEX.md).

## Правило дальнейшего ведения

**Не добавлять новый длинный датированный раздел в начало Roadmap.** После проверки обновлять **существующую** строку gate/Issue + ссылку на новый датированный audit с tag/SHA, временем/таймзоной, scope, evidence, ограничениями, FAIL/unknown; не переписывать старые snapshots. Обязательны PR, required `test`/`title`, squash merge, независимый read-back `main` и сверка связанных Issues **до следующего пакета**. См. [GIT_WORKFLOW](GIT_WORKFLOW.md) и [LIVING_DOCS](LIVING_DOCS.md).
