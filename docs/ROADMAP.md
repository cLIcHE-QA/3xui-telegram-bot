# Дорожная карта проекта

> **Канонический актуальный статус.** Старый Roadmap (5803 строки) сохранён побайтово в [тематическом историческом архиве](roadmap/HISTORY_INDEX.md), original blob `7303286842241ee29b7cbefbabbe4780911043dd`. Исторические сведения и прежние FAIL/STOP/WAIVED не стираются и не являются сегодняшними статусами. Нормативная [приёмка v5](V5_PRODUCTION_ACCEPTANCE.md), [release history](../CHANGELOG.md).

## Актуальная сводка проекта

**GitHub baseline:** 13 октября 2026, protected `main=65cf94e08bc32b8c83f192547962b87f97e1d4c3` после [PR #592](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/592), required/postmerge `test` PASS. **Published:** immutable prerelease [`v5.0.0-rc.9`](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.9), tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; last stable `v4.26.9`. **Deployed:** rc.9 только operator-reported (11 октября deploy; 12 октября host SHA/image read-back в [G-01 audit](audits/v5-g01-production-baseline-2026-10-12.md)), independent build/VPS attestation PENDING. **Accepted:** общий v5 **NOT PASS**, stable release, public rollout и expansion pilot allowlist **BLOCKED**. Docs-only refactoring [#593](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/593) **PENDING до фактического merge/CI** — не приравнивать открытый PR к `main`; новый production deployment не выполнялся.

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
| G-01 | 5/5 health/source baseline, A1 source parity 7/7, rate limit 30/60 | Smoke CLOSED; independent image attestation PENDING, full acceptance PARTIAL |
| G-02 | 5/5 ledger/Master read, B1 mismatches/orphans/duplicates 0, один Node match | Smoke CLOSED; full reconciliation/Node offline→return #487 PENDING |
| G-03 | Existing Stars→VPN и архив B4 4/4 operator-reported PASS | Smoke CLOSED; independent payment→import provenance PARTIAL |
| G-04 | Refund/Support journal scoped PASS | PARTIAL; provider/revoke postconditions, будущая policy #433 |
| G-05 | Post-restart ledger/health, B3 nested provider read, C1 offline no-replay PASS | PARTIAL; interrupted paid-work и full no-replay PENDING |
| G-06 | Offline limiter/concurrency; первый D1 healthy snapshot, D2 scheduled backup metadata | Smoke CLOSED; full soak PARTIAL, второй D1 snapshot PENDING |
| G-07 | Normal A/B isolation, admin UI denies, C2 offline forged-callback cases | Smoke CLOSED; live adversarial transport proof PARTIAL |
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

**⬜ Запланировано, реализация ещё не подтверждена:** [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) 14-дневные voluntary Stars refunds с отзывом оплаченного срока (план rc.10, не опубликован), юридические и UI пункты [#436](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/436), [#434](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/434), [#437](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/437) PENDING. [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466) natural jobs, [#482](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/482) future 3x-ui API budget, [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) Master/Node sync, [#510](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/510) GitHub branch lifecycle, [#564](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/564) legacy command UI, [#593](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/593) Roadmap hygiene — собственные Issue criteria.

**⬜ Отложенный backlog без обещанного релиза:** [#336](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/336) external PSP/СБП с Telegram/legal compliance review; Client Portal features #496–#507, HWID #471–#473, multiformat/geo/Remnawave/Cheburcheck #475–#479. Точные acceptance criteria — в [GitHub Issues](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues). Концепции не являются текущей реализацией: [архитектурное будущее](roadmap/concepts/provider-neutral-remnawave.md), [Client Portal UX](roadmap/concepts/client-portal-ux.md); нормативные детали — в [EXTERNAL_PAYMENT_LINKS](EXTERNAL_PAYMENT_LINKS.md), [CLIENT_SETUP](CLIENT_SETUP.md), [UI_STYLE](UI_STYLE.md).

## Завершённые этапы и исторические документы

v4.x: protected Admin Control Plane, RBAC, Host Control, backup/DR, self-update, monitoring, User Management и final security hardening (stable `v4.26.9`). v5 rc.1…rc.9: controlled canary с отдельными findings и scoped smoke; **не** общий v5 PASS. Подробная хронология: [CHANGELOG](../CHANGELOG.md), [Releases](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases), [исторический индекс](roadmap/HISTORY_INDEX.md).

## Правило дальнейшего ведения

**Не добавлять новый длинный датированный раздел в начало Roadmap.** После проверки обновлять **существующую** строку gate/Issue + ссылку на новый датированный audit с tag/SHA, временем/таймзоной, scope, evidence, ограничениями, FAIL/unknown; не переписывать старые snapshots. Обязательны PR, required `test`/`title`, squash merge, независимый read-back `main` и сверка связанных Issues **до следующего пакета**. См. [GIT_WORKFLOW](GIT_WORKFLOW.md) и [LIVING_DOCS](LIVING_DOCS.md).
