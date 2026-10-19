# v5.0.0-rc.16.5 — адресная операторская приёмка C3 и manual→manual

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-19 11:18:31 UTC+03:00 (EEST); сообщение оператора 2026-10-19T08:18:31Z.
- **Окружение:** production controlled pilot, Telegram/3x-ui/SQLite и deploy-helper **со слов оператора**; прямого доступа к VPS, image, SQLite или provider API в этом checkpoint нет.
- **Цель:** зафиксировать результаты P1–P2, C3.1–C3.4, S1–S6, Z6–Z7 для опубликованного `rc.16.5`, не повторяя ранее принятые проверки `rc.16.4`.
- **Версия и immutable tag/SHA:** `v5.0.0-rc.16.5` / `0728b8466eb2c4c65f0a36a112ae5c4a3ea60cbc`; GitHub tag SHA независимо проверен, deployed SHA и runtime status — operator-reported.
- **Источник и evidence:** оператор отметил все 14 пунктов чек-листа `P1,P2,C3.1–C3.4,S1–S6,Z6,Z7` как `[x]` 2026-10-19T08:18:31Z. Raw stdout, снимки/логи VPS и отдельная machine-readable provider attestation не приложены. [Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.16.5), [PR #753](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/753), [PR #754](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/754), [release PR #757](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/757), [publication audit](2026-10-19-v5-rc16-5-github-publication-checkpoint.md).

## Результат по проверенным сценариям

| Группа | Результат | Точное свидетельство (operator-reported) |
| --- | --- | --- |
| P1–P2 | PASS (2/2) | pre-deploy backup и baseline rc.16.4; затем rc.16.5 SHA/APP_VERSION, SQLite schema v15, `quick_check`, Health/DB/3x-ui |
| C3.1–C3.4 / #743 | PASS (4/4) | enabled 🟢, disabled ⚪, unknown/error 🟡, read-only bounded search/Back без N+1 и provider mutations; прежний C3 FAIL на rc.16.4 остаётся историческим |
| S1–S6 / #752 | PASS (6/6) | same-group manual→manual preview и однократное подтверждение; read-back expiry=0/traffic=0/new IP/HWID/unchanged Inbounds; SQLite old `superseded`, new `active`, Orders/Payments unchanged; same-plan no-op; недопустимые состояния проверены по offline CI, не создавались в production |
| Z6 | PASS | post-smoke container/restarts, Health/DB/3x-ui, `quick_check`, critical events без отклонений по сообщению оператора |
| Z7 | OPERATOR-REPORTED COMPLETE; GITHUB SYNC PENDING | оператор отметил пункт; факт обновления `docs/ROADMAP.md` в `main` возникает только **после** merge отдельного docs-only PR и независимого GitHub read-back, не из отметки `[x]` |

**Scoped acceptance:** #743 и #752 — **operator-reported PASS** после Published и заявленного Deployed rc.16.5; соответствующие offline PR required `test`/`title` прошли ранее. Никакая новая мутация 3x-ui, DB, Stars/refund или deployment из GitHub для этого аудита не выполнялась. Операторская отметка не является независимой VPS/data-plane аттестацией. Возможное закрытие Issues ограничено их собственным scope и не повышает общий G-11.

## Предыдущие PASS не повторялись

[Аудит rc.16.4](2026-10-18-v5-rc16-4-operator-targeted-smoke.md): 59/60 operator-reported PASS, C3 FAIL на **старом** tag; M1–M8 — 8/8 operator-reported PASS позднее, но timestamp/causal correlation с `commerce_orders.awaiting_payment` остаётся PENDING по #730. #745 restart persistence PASS/CLOSED; не пересоздавать proof повторной выдачей, restart или payment.

## Остаточные gates и следующий шаг

- [#730](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/730): **OPEN/PARTIAL**. Только read-only сверка `manual_entitlements.started_at/confirmed_at/status/result_code`, `commerce_orders.created_at/updated_at/status`, `commerce_payments` и `audit_log` события `user.plan.manual.granted` для доказательства последовательности. Тот же pilot identity и отсутствие payment известны лишь по предыдущему operator report. Ни новый grant, ни SQL status update не разрешены.
- [#731](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/731): **OPEN/PARTIAL**. Исторический B5 на поздних проверках не воспроизводился, но причина исходного исчезновения Stars каталога не установлена. Требуется read-only сопоставление manual gate/Stars flags/visibility/groups/plans/SQLite errors без пользовательских IDs в GitHub.
- [#705](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/705): **OPEN/PARTIAL**. Сначала #730/#731 causal backend evidence, затем сверка оставшихся financial/entitlement postconditions и собственных acceptance criteria. Не повторять уже PASS E/H/G/M без нового доказанного риска.
- **V5-A-001…A-003 / G-11:** остаются `PARTIAL/NO-GO`, public rollout `BLOCKED`; independent VPS/image/SQLite/data-plane attestation отсутствует. Никаких дополнительных реальных оплат/refund/restart/deployment без отдельного согласования.

## Раздельные состояния

- **Merged:** реализация #743/#752 и публикационный #757 уже в main; этот docs-only checkpoint — только PR до отдельного merge.
- **Published:** PASS `v5.0.0-rc.16.5`, immutable GitHub tag SHA `0728b8466eb2c4c65f0a36a112ae5c4a3ea60cbc`.
- **Deployed:** operator-reported `rc.16.5` на тот же SHA, independent VPS attestation PENDING.
- **Accepted:** #743/#752 scoped operator-reported PASS; #730/#731/#705 OPEN, общий G-11 PARTIAL/NO-GO.
