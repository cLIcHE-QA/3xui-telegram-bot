# G-01–G-11 — актуализация канонической таблицы 11 проверок rc.9 (2026-10-13)

## Источник и границы

**Инициатор:** вопрос оператора **2026-10-13 13:53:53 UTC / 16:53:53 EEST** о таблице `docs/ROADMAP.md#11-проверок-текущей-rc9-перед-следующим-релизом`. **Только документальный read-back** GitHub `main=72750b13d3dc1d79b28b944b4837b5f60bc48915` и сохранённых dated audits A/B/C/D, [review полной smoke-очереди](v5-smoke-scope-completeness-review-2026-10-13.md) и [решения G-09/D1/G-11](v5-g09-d1-before-g11-decision-2026-10-13.md). **Новых production checks, платежей, рестартов, backup и provider mutations нет**; новый outcome не выдумываем.

**Merged:** base protected `main=72750b13d3dc1d79b28b944b4837b5f60bc48915` после [#588](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/588), required test/title PASS, post-merge [Python checks 38408403928](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38408403928) PASS. **Published:** immutable prerelease `v5.0.0-rc.9`, tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; **Deployed:** rc.9 подтверждено ранее только оператором, независимая аттестация Docker image не выполнена; **Accepted:** overall v5 `NOT PASS`, public/stable rollout `BLOCKED`. На момент read-back 0 OPEN PR, Issues #433/#466/#482/#487/#577 OPEN. `main`, `published`, `deployed`, `accepted` не взаимозаменяемы.

## Обнаруженный документационный drift

В прежней таблице G-01 не учитывал operator-reported A1 file parity 7/7 и effective limit 30/60; G-02 — B1 ledger mismatches/orphans/duplicates/unresolved 0; G-03 — B4 четыре архивных operator-reported PASS без независимого review; G-04 — B2 текущая policy; G-05 — B3 manual nested `obj.client.enable=true` scoped PASS и новые C1 no-blind-replay offline tests; G-06/G-07 — C2/C3 offline CI и D1/D2; G-08 — D3 historical `NOT OBSERVED`; G-09 — актуальный `PENDING` natural event и старую неподтверждённую фразу «ChatGPT reminder активна»; G-11 — отсутствующий формальный dependency `BLOCKED ON G-09 + D1`. Короткие текстовые строки в таблице обновлены, **старые отдельные dated audits не переписываются**.

## Честные результаты для таблицы

| Gate | Текущий итог после read-back | Не закрывать ошибочно |
| --- | --- | --- |
| G-01 | A1 7/7 operator file parity, effective 30/60; smoke CLOSED / acceptance PARTIAL | независимую image provenance |
| G-02 | B1 four ledger metrics zero, один Node/Master pilot read; smoke CLOSED / acceptance PARTIAL | полный node-side reconciliation #487 |
| G-03 | B4 4/4 только operator-reported archived PASS; smoke CLOSED / acceptance PARTIAL | independent payment→VPN causal proof |
| G-04 | B2 refund/paid policy consistent для rc.9; PARTIAL | новую #433 refund policy rc.10 |
| G-05 | B3 `obj.client.enable=true` manual scoped PASS, old scripted parser cause PENDING; C1 isolated unknown no-replay PASS; PARTIAL | production interrupted-work / actual recovery postcondition |
| G-06 | C3 isolated per-user concurrency, D1 single resource snapshot, D2 scheduled encrypted offsite journal scoped PASS; smoke CLOSED / acceptance PARTIAL | второй D1 snapshot/full soak; W-02 waived |
| G-07 | C2 isolated forged customer/precheckout/admin RBAC 3 PASS; smoke CLOSED / acceptance PARTIAL | live adversarial transport не заявлять |
| G-08 | D3 historical event=1, invoice/payment counts 0, precheckout NOT_INSTRUMENTED; PARTIAL | live OFF denial `NOT OBSERVED` |
| G-09 | natural paid expiry и read-only postconditions PENDING | не считать прошедшим до реального события; старый reminder не аттестован |
| G-10 | #466 OPEN/PENDING natural job_failed NOT OBSERVED | не создавать искусственный сбой |
| G-11 | **BLOCKED ON G-09 + D1** по решению оператора | не готовить acceptance report до **обоих** датированных checkpoints |

**Минимальная очередь:** G-09 при реальном natural paid expiry → D1 после естественного `BACKUP_HOUR_UTC=2` цикла (ожидается 2026-10-14 02:00 UTC / 05:00 EEST) → только затем G-11. Хронология G-09/D1 может определяться фактической готовностью, но **оба** нужны. G-10/#466 остаётся пассивным, сам по себе не блокирует написание G-11. Никаких отменённых/закрытых сценариев не повторять.

**Полный contract gate:** `docs/V5_PRODUCTION_ACCEPTANCE.md` требует дополнительные V5-A-001/002/003 recovery, load/soak, rollback и cross-system proof. Даже `G-09 scoped PASS` + `D1 snapshot scoped PASS` **не означает** `stable v5.0.0` PASS. Не расширять pilot allowlist, не публиковать stable release без отдельного полного acceptance или согласованного изменения требований.

## Issues, PR и closure audit

- #433 OPEN (future 14-day refund policy), #487 OPEN (node-side offline/recovery), #466 OPEN (natural job_failed), #482 OPEN (future global API budget), #577 OPEN (prerelease audit defect). Исторические закрытые #317/#342/#422 остаются CLOSED в собственном scope; **нет новых доказательств для закрытия Issues**.
- **Issue: N/A** — docs-only синхронизация таблицы существующих gates, без отдельного нового implementation defect. После merge — независимый read-back именно этой таблицы, проверка GitHub Issues/PR и post-merge CI.
- **ROADMAP SYNC: PENDING** пока docs-only PR не пройдёт required test/title, squash merge и read-back из main.
