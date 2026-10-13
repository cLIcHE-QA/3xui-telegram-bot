# Дорожная карта проекта

> **Канонический актуальный статус.** Старый Roadmap (5803 строки) сохранён побайтово в [тематическом историческом архиве](roadmap/HISTORY_INDEX.md), original blob `7303286842241ee29b7cbefbabbe4780911043dd`. Исторические сведения и прежние FAIL/STOP/WAIVED не стираются и не являются сегодняшними статусами. Нормативная [приёмка v5](V5_PRODUCTION_ACCEPTANCE.md), [release history](../CHANGELOG.md).

## Актуальная сводка проекта

**Исторический GitHub baseline до PR #594:** 13 октября 2026, `main=65cf94e08bc32b8c83f192547962b87f97e1d4c3` после [PR #592](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/592), required/postmerge `test` PASS. **Published:** immutable prerelease [`v5.0.0-rc.9`](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.9), tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; last stable `v4.26.9`. **Deployed:** rc.9 только operator-reported (11 октября deploy; 12 октября host SHA/image read-back в [G-01 audit](audits/v5-g01-production-baseline-2026-10-12.md)), independent build/VPS attestation PENDING. **Accepted:** общий v5 **NOT PASS**, stable release, public rollout и expansion pilot allowlist **BLOCKED**. Docs-only reorganization [#593](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/593) **CLOSED/completed** по собственным документационным критериям: [PR #594](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/594) squash MERGED `6bfbfddb47f487e4044b43f1bce44b7b521b385d`, required `test`/`title` PASS, postmerge [Python checks #38424087246](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38424087246) PASS; история 5803 строк сохранена и проверена по blob, текущая сводка 64 строки до этого docs-only closure update. Нет нового Release/deployed/acceptance v5.

## Статусы дорожной карты

- `⬜ Запланировано` — работа ещё не завершена в `main`;
- `🟡 Реализовано в main` — код/документация уже слиты, но соответствующий release ещё не опубликован;
- `🟠 Опубликовано; acceptance отложен` — release опубликован, но отдельный обязательный production acceptance, targeted smoke или recovery drill ещё не завершён;
- `✅ Выполнено в vX.Y.Z` — изменение опубликовано и весь обязательный acceptance scope подтверждён.

`PASS/PARTIAL/PENDING/FAIL/BLOCKED` — результаты проверок, не дополнительные статусы Roadmap. **Merged, Published, Deployed и Accepted — раздельные состояния.**

## Текущий этап: v5 Client Portal

**🟠 Опубликовано; acceptance отложен — controlled canary `v5.0.0-rc.9`**. Pilot Client Portal со Stars, idempotent commerce/entitlement, provisioning/quota-cycle, guarded callbacks и отдельный protected `/admin`; SQLite schema v13, pinned 3x-ui v3.9.0. **✅ Выполнено в v5.0.0-rc.9:** [#342](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/342) Portal stale-callback guard и [#422](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/422) Master Host Groups — CLOSED по собственным scoped operator-reported PASS. [#317](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/317) quota cycle CLOSED; [#577](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/577) GitHub governance audit CLOSED. Эти closure не закрывают полный v5 acceptance.

## Реестр acceptance-gates rc.9

| Gate | Проверено в ограниченном объёме | Остаток и фактический статус |
| --- | --- | --- |
| G-01 | 5/5 базовый health/source, A1 совпадение исходников 7/7, лимит 30/60 | Проверенный smoke закрыт; независимая аттестация образа PENDING, полная приёмка PARTIAL |
| G-02 | 5/5 ledger/Master read, B1 mismatches/orphans/duplicates 0, один Node match | Smoke CLOSED; full reconciliation/Node offline→return #487 PENDING |
| G-03 | Existing Stars→VPN и архив B4 4/4 operator-reported PASS | Smoke CLOSED; independent payment→import provenance PARTIAL |
| G-04 | Refund/Support journal scoped PASS | PARTIAL; provider/revoke postconditions, будущая policy #433 |
| G-05 | Post-restart ledger/health, B3 nested provider read, C1 offline no-replay PASS | PARTIAL; interrupted paid-work и full no-replay PENDING |
| G-06 | Offline limiter/concurrency; первый D1 healthy snapshot, D2 scheduled backup metadata | Smoke CLOSED; full soak PARTIAL, второй D1 snapshot PENDING |
| G-07 | Обычная A/B-изоляция, отказ в Admin UI, C2 offline forged-callback cases | Проверенный smoke закрыт; live adversarial transport proof PARTIAL |
| G-08 | Portal OFF→old callback deny→ON; Stars OFF/ON audit и health scoped PASS | PARTIAL; invoice/precheckout и уже paid event при OFF не подтверждены, toggle повторять нельзя |
| G-09 | Natural expiry оплаченного entitlement НЕ наблюдался | **PENDING**: SQLite ↔ Master 3x-ui ↔ customer read-only только после natural expiry |
| G-10 | QA synthetic 4/4 и main-bot Attention Center empty-UI smoke | **PENDING**: natural `job_failed` #466 NOT OBSERVED, passive/nonblocking |
| G-11 | Финальный v5 acceptance report отсутствует | **BLOCKED ON G-09 + D1** |
| W-01 | Independent cross-host Master DR отсутствовал | **OPERATOR-WAIVED / NOT TESTED** — НЕ PASS |
| W-02 | Live Telegram burst inconclusive | **OPERATOR-WAIVED / INCONCLUSIVE** — НЕ PASS |

Полные исторические наблюдения, включая старые FAIL, тайминги, данные G-01…G-11 и правильную идентичность DR-хоста: [архив проверок v5](audits/roadmap-history/v5-gates.md), [датированные audits](audits/), [карта переноса](roadmap/HISTORY_INDEX.md). Итоговые короткие строки не отменяют нормативные критерии [V5_PRODUCTION_ACCEPTANCE](V5_PRODUCTION_ACCEPTANCE.md).

## Текущая очередь и блокировки

1. **G-09 PENDING:** только после естественного paid entitlement expiry — read-only SQLite / Master / client; датированный audit, затем Roadmap PR с required `test`/`title`, squash merge и Issue audit. Не менять срок вручную.
2. **D1 PENDING:** второй resource snapshot после естественного scheduled cycle 14.10.2026 около 02:00 UTC / 05:00 EEST; отдельный checkpoint. Два снимка не full soak PASS; forced backup/restart не выполнять.
3. **G-11 BLOCKED ON G-09 + D1:** оба checkpoints должны быть синхронизированы в main до итогового acceptance report. Stable/public rollout всё ещё BLOCKED.
4. **G-10/#466:** пассивное ожидание естественного `job_failed` без срока, не блокирует старт G-11; [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) offline→return/last sync OPEN.

Уже пройденные scoped или waived проверки не повторять. На production — лишь 3–4 новых целевых smoke за пакет с обязательным PR+CI+Issue checkpoint; никакого deploy/restart/refund/Stars/DB/3x-ui mutations без отдельного согласия.

## Реестр открытых задач и будущие релизы

**⬜ Запланировано, реализация ещё не подтверждена:** [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) 14-дневные voluntary Stars refunds с отзывом оплаченного срока (план rc.10, не опубликован), юридические и UI пункты [#436](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/436), [#434](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/434), [#437](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/437) PENDING. [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466) natural jobs, [#482](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/482) future 3x-ui API budget, [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) Master/Node sync, [#510](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/510) GitHub branch lifecycle, [#564](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/564) legacy command UI — собственные Issue criteria. 

**⬜ Отложенный backlog без обещанного релиза:** [#336](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/336) external PSP/СБП с Telegram/legal compliance review; Client Portal features #496–#507, HWID #471–#473, multiformat/geo/Remnawave/Cheburcheck #475–#479. Точные acceptance criteria — в [GitHub Issues](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues). Концепции не являются текущей реализацией: [архитектурное будущее](roadmap/concepts/provider-neutral-remnawave.md), [Client Portal UX](roadmap/concepts/client-portal-ux.md); нормативные детали — в [EXTERNAL_PAYMENT_LINKS](EXTERNAL_PAYMENT_LINKS.md), [CLIENT_SETUP](CLIENT_SETUP.md), [UI_STYLE](UI_STYLE.md).

**Закрытый docs-only Issue:** [#593](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/593) — CLOSED/completed по PR #594/#595 и CI; не новый production/release acceptance.

**✅ Завершено в docs/CI scope:** [#597](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/597) CLOSED/completed: маршрутизация документации, audit template + semantic tests, редактируемые concepts отдельно от immutable source (PR [#596](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/596), [#598](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/598); main `9b38246711f811cff63442738942fc5f3e8061ac`, required/postmerge CI PASS). Первый реальный **manual workflow_dispatch PASS** 2026-10-13 19:41 EEST: [run #38432290724](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38432290724) на `main=1bd969bdeab8786fb90e79b6d2a06a73a8c142a4`, published rc.9 и 12 tracked Issues, [датированный audit](audits/2026-10-13-roadmap-github-first-dispatch.md). Weekly scheduled execution **PENDING observation**; full Issues/documents/production acceptance не подтверждён. Общий v5 по-прежнему NOT PASS.

**✅ Завершено в docs/CI scope:** [#601](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/601) CLOSED/completed по [PR #602](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/602), squash main `520dddd42a723015345a4d6967329b8de90226a3`, required `test`/`title` и postmerge [Python checks #38434463785](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38434463785) PASS. Новые audits, Markdown anchors и все напрямую связанные Issue URLs проверяются автоматикой; первый live run расширенной версии **PASS в GitHub-only scope** 2026-10-13 20:05 EEST: [Actions #38435743560](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38435743560), `main=fc50bbc3ba7d17703852fea067e3087ec7a46ae6`, 17 прямых Issue URLs / 13 status assertions, published rc.9, [audit](audits/2026-10-13-roadmap-github-expanded-dispatch.md). Weekly scheduled run **PENDING observation**; не production PASS. Первый ограниченный 12-Issue PASS от 2026-10-13 — [dated audit](audits/2026-10-13-roadmap-github-first-dispatch.md).

## Активный Issue-реестр (machine-checked)

Ровно одна строка на каждый открытый GitHub Issue; подробности остаются в Issue. `—` означает отсутствие PR, `TBD` — непublished target, не гарантированный release. Даты/свидетельства проверок — в отдельных audits.

| Issue | Статус | PR | Target release | Evidence | Next / remaining |
| --- | --- | --- | --- | --- | --- |
| [#336](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/336) | ⬜ Запланировано | — | TBD | Issue #336 (scope), implementation PENDING | внешний платёжный шлюз и СБП с уникальными ссылками: Issue criteria |
| [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) | ⬜ Запланировано | — | rc.10 (plan) | Issue #433 (scope), implementation PENDING | 14-дневные возвраты Stars с отзывом оплаченного срока: Issue criteria |
| [#434](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/434) | ⬜ Запланировано | — | TBD | Issue #434 (scope), implementation PENDING | ненавязчивые условия возврата в клиентском портале: Issue criteria |
| [#436](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/436) | ⬜ Запланировано | — | TBD | Issue #436 (scope), implementation PENDING | подготовить правовую политику возвратов РФ для самозанятого: Issue criteria |
| [#437](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/437) | ⬜ Запланировано | — | TBD | Issue #437 (scope), implementation PENDING | справочник возвратов для поддержки в админке: Issue criteria |
| [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466) | ⬜ Запланировано | — | TBD | Issue #466 (scope), implementation PENDING | Natural job_failed, passive: Issue criteria |
| [#470](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/470) | ⬜ Запланировано | — | TBD | Issue #470 (scope), implementation PENDING | read-only просмотр Stars Orders в админке: Issue criteria |
| [#471](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/471) | ⬜ Запланировано | — | TBD | Issue #471 (scope), implementation PENDING | компактный список и карточки устройств клиента: Issue criteria |
| [#472](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/472) | ⬜ Запланировано | — | TBD | Issue #472 (scope), implementation PENDING | безопасное удаление одного собственного HWID клиентом: Issue criteria |
| [#473](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/473) | ⬜ Запланировано | — | TBD | Issue #473 (scope), implementation PENDING | безопасные VPN-клиентские deep-link импорты: Issue criteria |
| [#475](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/475) | ⬜ Запланировано | — | TBD | Issue #475 (scope), implementation PENDING | геометаданные страны для direct nodes: Issue criteria |
| [#476](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/476) | ⬜ Запланировано | — | TBD | Issue #476 (scope), implementation PENDING | мультиформатные подписки raw, Xray JSON и Clash/Mihomo: Issue criteria |
| [#477](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/477) | ⬜ Запланировано | — | TBD | Issue #477 (scope), implementation PENDING | provider-neutral control plane и поддержка Remnawave: Issue criteria |
| [#478](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/478) | ⬜ Запланировано | — | TBD | Issue #478 (scope), implementation PENDING | региональная сеть Probe reporters для Cheburcheck: Issue criteria |
| [#479](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/479) | ⬜ Запланировано | — | TBD | Issue #479 (scope), implementation PENDING | внешняя наблюдаемость, сервисный API и signed webhooks: Issue criteria |
| [#482](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/482) | ⬜ Запланировано | — | TBD | Issue #482 (scope), implementation PENDING | ограничить нагрузку на 3x-ui API перед масштабированием: Issue criteria |
| [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) | ⬜ Запланировано | — | TBD | Issue #487 (scope), implementation PENDING | Master/Node sync: Issue criteria |
| [#496](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/496) | ⬜ Запланировано | — | TBD | Issue #496 (scope), implementation PENDING | ограничивать видимость функций Client Portal через User Groups: Issue criteria |
| [#497](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/497) | ⬜ Запланировано | — | TBD | Issue #497 (scope), implementation PENDING | полноценная карточка подписки и контекстные действия клиента: Issue criteria |
| [#498](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/498) | ⬜ Запланировано | — | TBD | Issue #498 (scope), implementation PENDING | безопасная ручная синхронизация подписки клиентом: Issue criteria |
| [#499](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/499) | ⬜ Запланировано | — | TBD | Issue #499 (scope), implementation PENDING | применение промокодов при покупке Stars в Client Portal: Issue criteria |
| [#500](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/500) | ⬜ Запланировано | — | TBD | Issue #500 (scope), implementation PENDING | управляемое клиентом автопродление подписки: Issue criteria |
| [#501](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/501) | ⬜ Запланировано | — | TBD | Issue #501 (scope), implementation PENDING | настройки клиентских уведомлений и напоминаний: Issue criteria |
| [#502](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/502) | ⬜ Запланировано | — | TBD | Issue #502 (scope), implementation PENDING | выбор языка интерфейса Client Portal: Issue criteria |
| [#503](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/503) | ⬜ Запланировано | — | TBD | Issue #503 (scope), implementation PENDING | статистика трафика клиента за сегодня, 7 и 30 дней: Issue criteria |
| [#504](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/504) | ⬜ Запланировано | — | TBD | Issue #504 (scope), implementation PENDING | пользовательские названия собственных HWID-устройств: Issue criteria |
| [#505](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/505) | ⬜ Запланировано | — | TBD | Issue #505 (scope), implementation PENDING | FAQ и общий контакт поддержки в Client Portal: Issue criteria |
| [#506](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/506) | ⬜ Запланировано | — | TBD | Issue #506 (scope), implementation PENDING | собственная история заказов и платежей клиента: Issue criteria |
| [#507](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/507) | ⬜ Запланировано | — | TBD | Issue #507 (scope), implementation PENDING | выбор варианта срока тарифа при покупке: Issue criteria |
| [#510](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/510) | ⬜ Запланировано | — | TBD | Issue #510 (scope), implementation PENDING | определить жизненный цикл и безопасную очистку GitHub-веток: Issue criteria |
| [#564](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/564) | ⬜ Запланировано | — | TBD | Issue #564 (scope), implementation PENDING | скрыть legacy /create и /inbounds из актуального интерфейса: Issue criteria |

**✅ Документационное governance #605:** [Issue #605](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/605) CLOSED/completed по собственным docs/CI критериям; [PR #606](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/606) squash `7d879216bf232ea107b8417d2496c47f19ecf797`, required `test`/`title` PASS и postmerge [Python checks #38439409323](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38439409323) PASS. Machine-checked шестипольный Issue-реестр, concept lifecycle, changed-audit CI, release-state provenance; **живой запуск новой pagination-сверки PENDING observation**. Нет production acceptance.

## Завершённые этапы и исторические документы

v4.x: protected Admin Control Plane, RBAC, Host Control, backup/DR, self-update, monitoring, User Management и final security hardening (stable `v4.26.9`). v5 rc.1…rc.9: controlled canary с отдельными findings и scoped smoke; **не** общий v5 PASS. Подробная хронология: [CHANGELOG](../CHANGELOG.md), [Releases](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases), [исторический индекс](roadmap/HISTORY_INDEX.md).

## Правило дальнейшего ведения

**Не добавлять новый длинный датированный раздел в начало Roadmap.** После проверки обновлять **существующую** строку gate/Issue + ссылку на новый датированный audit с tag/SHA, временем/таймзоной, scope, evidence, ограничениями, FAIL/unknown; не переписывать старые snapshots. Обязательны PR, required `test`/`title`, squash merge, независимый read-back `main` и сверка связанных Issues **до следующего пакета**. См. [GIT_WORKFLOW](GIT_WORKFLOW.md) и [LIVING_DOCS](LIVING_DOCS.md).
