# G-03 — существующая Stars → VPN подписка, scoped 5/5 PASS (2026-10-12)

## Baseline и provenance

- **Production Master + pilot Telegram/VPN client**, только существующий разрешённый тестовый пользователь; оператор прислал stdout `G03_UTC=2026-10-12T15:20:36.421334+00:00` = **2026-10-12 18:20:36.421334 Europe/Helsinki EEST**. Сообщение получено 15:21:42 UTC. Проверки G03-1..3 — console stdout оператора; G03-4..5 — вручную сообщённый `PASS` без независимой трассировки/скриншота.
- **Published:** immutable prerelease `v5.0.0-rc.9` tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`. **Deployed:** ранее подтверждён operator-supplied production read-back G-01 (2026-10-12 17:36 EEST), тот же host/tag SHA, image `sha256:efb2fb9ea3dffac70a3ca344d7843cabff67ae737875b461464e0b0705483f4c`; G-03 identity повторно не снимал. **main** prior checkpoint [PR #554](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/554) squash `5bf203df94723f7839f4c4fac63f3af78ce4af69` / post-merge [Python checks #38269160401](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38269160401) success; main не следует выдавать за deployed.
- **Scope:** существующий confirmed Stars payment + `active` latest entitlement одного pilot user, finite quota plan; read-only SQLite и authenticated GET Master 3x-ui, ручная проверка существующей Telegram подписки и VPN клиента; не выполнялись покупка/refund, server-side provisioning, replay, traffic reset, config/flag mutations, deploy/restart или новый VPN аккаунт. Секреты, IDs, URL, платежные идентификаторы не извлекались в evidence.

## Фактический stdout и операторское ручное подтверждение

```text
G03_UTC= 2026-10-12T15:20:36.421334+00:00
G03-1 ENTITLEMENT_EXPIRY: PASS
G03-2 QUOTA_JOURNAL: PASS finite= True
G03-3 PROVIDER_TRAFFIC: PASS nonzero_usage= True
G03-4: PASS
G03-5: PASS
```

| ID | Реально проверено | Scoped disposition |
| --- | --- | --- |
| G03-1 | `starts_at > 0`, `entitlements.expires_at>0`; current `users.expiry_time` >= latest active entitlement expiry for confirmed paid pilot | **PASS**; не exact equality для исторических продлений, не proof всей истории |
| G03-2 | Finite `plans.traffic_gb > 0` и durable `quota_reset_status=success` выбранного entitlement | **PASS**; статус журнала не доказывает отсутствие прошлого повторного reset |
| G03-3 | Master 3x-ui authenticated read-only `get_client`/traffic response, `up + down > 0` | **PASS** ненулевого cumulative provider traffic; нет time-delta или прямой атрибуции именно текущему VPN-тесту |
| G03-4 | Оператор подтвердил `PASS` Telegram `/subscription`: видна существующая подписка/срок/собственная ссылка (без её раскрытия) | **Operator-reported PASS**; нет raw Telegram API/скриншота |
| G03-5 | Оператор подтвердил `PASS` существующего VPN клиента/подключения и небольшого объёма трафика, как было предложено в сценарии | **Operator-reported PASS**; нет device trace, node-side sync или независимого user-traffic delta |

## Interpretation, unresolved criteria и Issue audit

**Пять из пяти фактически предоставленных subchecks — scoped operator-reported PASS**, но **G-03 остаётся PARTIAL**. Нет независимого cryptographic end-to-end linkage именно этой Stars покупки с текущей импортированной VPN конфигурацией и node-side state; `nonzero_usage=True` означает cumulative > 0, не traffic attributable to the single test. Replay/idempotency/duplicate payment delivery, полный V5-A-001, историческая reconciliation не входили в этот пакет, их нельзя повышать в PASS. Не повторять ранее пройденные/waived scenarios.

**Related GitHub Issues:** [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) **OPEN/PENDING**: node-side sync/client inbound membership/last sync status не проверены; #342/#422 **CLOSED** по отдельному прошлому scoped acceptance, G-03 не меняет их состояние; [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) **OPEN** — future refund policy вне rc.9; [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466) **OPEN** — natural job_failed PENDING. Изменять Issue state только при выполнении его собственных критериев.

**G-01/G-02** PARTIAL при прежних scoped PASS, **G-04…G-08 PARTIAL**, **G-09…G-11 PENDING**, W-01/W-02 waived/inconclusive и не повторяются. **Accepted overall v5 NOT PASS; public launch BLOCKED.** Следующий пакет — **G-04** 4–5 целевых read-only checks: существующий refund journal/unknown outcome/entitlement+3x-ui postcondition/Support path (без new real refund и без внедрения будущей policy #433). Сначала обновить верх `docs/ROADMAP.md` через PR, required `test`/`title`, squash, independent GitHub main read-back и closure audit связанных Issues.
