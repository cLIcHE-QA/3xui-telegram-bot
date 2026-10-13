# C1–C4 — изолированные failure/security/concurrency/Node проверки (2026-10-13)

## Основа и неизменные ограничения

**Проверка:** GitHub Actions required CI на test-only [PR #584](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/584). Исходный операторский запрос со скриншотом от **2026-10-13 12:08:20 UTC / 15:08:20 EEST**. Команды проверок запускались GitHub hosted runner с синтетическими идентификаторами, временной SQLite и fake/mocked provider. **Production Telegram, Stars, Node, VPS, хранилище и реальные outage/deploy/restart не затрагивались**. Изолированные проверки не доказывают полного production V5-A-002/V5-A-003.

**Четыре состояния:** code `main=080ab79bb2e86d8bf6dd329e9999cbce9174810e` (PR #584 squash MERGED; source tests `tests/test_v5_c_isolated_packet.py`); Published immutable `v5.0.0-rc.9` tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; deployed rc.9 ранее подтверждено **только оператором**, новый runtime read-back не делали; full accepted v5 **NOT PASS**, public rollout **BLOCKED**. Новые tests находятся **в main**, но **не** в immutable published/deployed rc.9 — не смешивать code CI и production.

## Проверка существующего coverage и фактический результат

[Последний pre-code checkpoint CI](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38394736100) — `Ran 936 tests ... OK`. Из уже существовавших PASS выбраны no-blind-replay quota, delayed payment, fake unavailable node, Stars owner/amount, admin privilege fail-closed, limiter sliding-window. Эти fixtures **не повторялись вручную** и не выдаются за новые уникальные сценарии.

На [PR #584](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/584) добавлены **7 новых** детерминированных тестов:

- **C1 / G-05-E (1):** временная SQLite, один confirmed payment и один entitlement; fake provider теряет ответ на quota reset, журнал сохраняет `provisioning/unknown`; после создания нового Database/Service `reconcile_pending` **не включает unsafe record в автоматическую очередь**, reset/sync call counts остаются неизменны, explicit reconcile возвращает `ProvisioningUnknown`, никаких второго entitlement и продления срока.
- **C2 / G-07 (3):** forged customer callback suffix не может сменить owner для profile/subscription/traffic/devices/QR; чужой order owner в Stars precheckout отвергается до DB validation; forged owner-only admin callback отвергается для обычного пользователя и роли read_only.
- **C3 / G-06 (2):** синтетические concurrent callback guard requests: пользователь A 40 → 30 accepted / 10 rejected при per-user лимите 30/60; пользователь B 1 → accepted; oversized synthetic plan callback не создаёт заказ.
- **C4 / #487 (1):** fake Node offline сохраняется в desired policy, но не actionable; возвращение `online` позволяет ровно одну missing attach; повторное согласование не делает второй attach/detach. **Это имитация bot-side policy**, не фактический Master→Node 3x-ui propagation/last sync.

**CI evidence:** первичный [PR test run #38397162743](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38397162743) завершился **FAIL**: C1 ошибочно ожидал `unknown ≥ 1` в `reconcile_pending`. Actual `checked=0` означает safety policy: persistent `provisioning/unknown` исключён из автоматической очереди. Тест скорректирован, исторический FAIL сохранён. Итоговый required [PR test run #38397436967](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38397436967) **PASS**, итоговый [title run #38397706075](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38397706075) **PASS**; merge commit `080ab79bb2e86d8bf6dd329e9999cbce9174810e`. Post-merge [Python checks](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38397751630) отдельно проверить перед завершением checkpoint.

## Acceptance/Issues и безопасный следующий шаг

**C1–C4 offline scope PASS по corrected PR CI**, полный G-05/G-06/G-07 acceptance **PARTIAL**, #487 **OPEN**: offline/online fake не измеряет реальный status/last-sync, authentic Node mutation/recovery или real provider no-blind-replay. Не считать mock Node accepted. G-06 W-02 live Telegram burst `WAIVED/BLOCKED`, повтор запрещён; G-09 natural expiry и G-10 natural job_failed PENDING.

[#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433), [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487), [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466), [#577](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/577) и другие самостоятельные задачи остаются OPEN по своим критериям. #317/#342/#422 CLOSED; нет оснований закрывать новые Issues. **Issue: N/A для нового**, C1–C4 — тестовое evidence уже существующих acceptance gates; самостоятельного подтверждённого runtime defect нет. Следующий пакет — только после docs-only Roadmap PR, required CI, squash merge, независимого read-back и Issue closure audit. Никаких production операций.
