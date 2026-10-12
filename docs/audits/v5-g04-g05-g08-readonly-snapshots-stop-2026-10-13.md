# G-04/G-05/G-08 — три operator-supplied SQLite snapshots, G-08 STOP (2026-10-13 EEST)

## Provenance и границы

- **Источник:** оператор прислал обезличенный stdout в чате **2026-10-12 22:49:25 UTC / 2026-10-13 01:49:25 EEST**. Времена самих снимков из `SNAPSHOT_UTC` ниже. Это **operator-supplied stdout**, без независимого доступа агента к VPS, к коду запущенного диагностического скрипта или Owner Telegram UI. Timestamp stdout ≠ независимая attestation выполнения.
- **Target/scope:** production Master, ограниченный pilot `PILOT_SIZE=3`, одноразовая серия *read-only* диагностики по G-04 (refund ledger), G-05 (quota/recovery) и G-08 (Stars owner-flag). Операции со звёздами, факт OFF→ON, Telegram UI, provider Master/Node и full backup **этими строками не подтверждены**; агент никаких production mutations не выполнял.
- **Four states:** baseline до нового Roadmap PR — protected `main` `6063031de87dfe443075a5ae71088772451e6781` (docs checkpoint #569); **Published** immutable prerelease `v5.0.0-rc.9`, tag commit `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; **Deployed** `rc.9` ранее operator-reported (2026-10-11), в этой серии stdout подтверждает только `APP_VERSION=5.0.0-rc.9`, не deployed image/SHA; **Accepted** v5 `NOT PASS`, public rollout `BLOCKED`.
- **Baseline UTC:** `2026-10-12T22:47:32+00:00` = 2026-10-13 01:47:32 EEST.
- **STARS_OFF UTC:** `2026-10-12T22:48:29+00:00` = 2026-10-13 01:48:29 EEST; вывод **заканчивается** `STOP: failed closed on incompatible DB: RuntimeError`. Точный stack trace и исходный script отсутствуют; **невозможно заключить, что SQLite schema повреждена**, либо что Owner действительно произвёл OFF.
- **RESTORED UTC:** `2026-10-12T22:48:50+00:00` = 2026-10-13 01:48:50 EEST. Имя stage задаётся вызовом скрипта, **не доказывает, что производилось восстановление OFF→ON**.

## Факты трёх снимков

| Поле | BASELINE | STARS_OFF | RESTORED |
| --- | --- | --- | --- |
| `APP_VERSION` / `PILOT_SIZE` | `5.0.0-rc.9` / `3` | то же | то же |
| `G04_REFUND_CURRENT` | `success=4 payment_refunded=4 active_entitlement=4 missing_entitlement=0 owners=1 owners_with_other_confirmed_active_entitlement=1` | то же | то же |
| `G04_POLICY` | `rc9_payment_status_only; provider_revoke=NOT_PROVEN` | то же | то же |
| `G05_CONTEXT` | `legacy=1 legacy_active=1 quota_inflight_unknown_failed=0 pilot_provisioning=0 pilot_refund_inflight_unknown=0 running_jobs=0` | то же | то же |
| `G08_ACTIVE_WORK_PREFLIGHT` | `CLEAR` (в пределах проверенных счётчиков) | `CLEAR` | `CLEAR` |
| `G08_FLAG` | `env_portal=true env_stars=true db_portal=true db_stars=true effective_stars=YES stars_revision=2` | **точно те же значения** | **точно те же значения** |
| `G08_STARS_SWITCH_AUDIT_EVENTS` | `2` | не напечатано (STOP) | `2` |
| `PILOT_LEDGER_COUNTS` | `orders:5 payments:5 entitlements:5 refunds:4 events:5` | не напечатано (STOP) | **то же** |
| `PILOT_LEDGER_DIGEST_SHA256` | `09802fd1d96e35a14f44d821a8a1474e4ff779ff8b4dd5d811d0222050c9db1d` | не напечатано (STOP) | **то же** |

**Ограничение:** ledger digest охватывает только pilot ledger и выбранные поля и не доказывает отсутствие внешних Telegram/3x-ui изменений; одинаковые хэши дают scoped before/final consistency, **не** подтверждают промежуточный OFF. Одинаковая `stars_revision=2` и `AUDIT_EVENTS=2` не показывают новых OFF/ON audit событий.

## Disposition по каждому gate

### G-04 — refund
- **G04-A: scoped PASS только для выводимых агрегатов**: `success=4`, `payment_refunded=4`, `missing_entitlement=0`; при этом `active_entitlement=4`. Этот aggregate не доказывает правильность всей связи refund→entitlement→provider и не означает, что доступ должен быть revoked на `rc.9`.
- **G04-B: OTHER_PAID=YES (operator-supplied aggregate)**: один владелец refunded records имеет как минимум один другой confirmed active entitlement. Причина, почему каждый из 4 связанных entitlement остаётся active, и расчёт оставшегося оплаченного срока этим не доказаны.
- **G04-C: PENDING/NOT RUN:** не предоставлено новое Master↔Node сравнение другого refunded клиента; ранее пройденный S01 не повторять без новой гипотезы.
- **G04-D: POLICY_RC9=PENDING_433:** текущий rc.9 изменяет payment/refund journal, **не** реализует новую 14-дневную entitlement/provider revoke policy. [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) остаётся OPEN для своего будущего implementation + release/deployed/smoke scope. **G-04 PARTIAL**, не FAIL новой ещё не выпущенной политики.

### G-05 — recovery/quota
- **G05-A: REVIEW:** `legacy=1 legacy_active=1` сохраняется, единичная строка не классифицирована по exact origin/migration v11; не делать quota reset и не маркировать `EXPECTED` только по счётчику.
- **G05-B: scoped PASS только точечного snapshot:** `quota_inflight_unknown_failed=0`, `pilot_provisioning=0`, `pilot_refund_inflight_unknown=0`, `running_jobs=0`. Эти нули не подтверждают реальный interrupted-work recovery/no-replay и отсутствие всех внешних незавершённых операций.
- **G05-C: DIGEST_SAME=YES только BASELINE↔RESTORED**, counts 5/5/5/4/5 без изменения. Для периода Stars OFF digest не получен; недопустимо приписывать этому G08 ledger safety PASS.
- **G05-D: API_SHAPE=INCONCLUSIVE; UI=previous scoped PASS**: старый `unclassified=1` Master API результат этим SQLite snapshot не переопределён, прежний S01 не повторялся.
- **G05-E: PENDING / ISOLATED ONLY**: реальное прерывание provisioning/payment и отсутствие внешней replay mutation в production не проверены; нужны safe isolated fake-provider/disposable DB evidence или отдельное risk decision. **G-05 PARTIAL**.

### G-08 — Stars OFF→ON
- **G08-A: PARTIAL:** `G08_ACTIVE_WORK_PREFLIGHT=CLEAR` для snapshot counters, flags исходно ON; нет нового подтверждения required health/full backup, отсутствие незавершённого Telegram precheckout и deployment build attestation.
- **G08-B: BLOCKED / OFF NOT PROVEN:** на этапе `STARS_OFF` получено `db_stars=true effective_stars=YES stars_revision=2` и `STOP: failed closed on incompatible DB: RuntimeError`. Нельзя заключить, что UI-toggle сработал; причина guard failure **UNKNOWN** без кода и временного read-back Owner UI. Не повторять toggle вслепую.
- **G08-C: NOT RUN / PENDING:** нет UI evidence отказа нового invoice после OFF, precheckout не проверялся и не должен тестироваться реальной покупкой.
- **G08-D: PARTIAL (только read-only ledger before/final)**; доказательств `/admin`, `/start`, срока клиента или provider availability в OFF нет.
- **G08-E: NOT PROVEN**: `RESTORED` показывает ON с той же DB revision=2, что и baseline, и старым `AUDIT_EVENTS=2`; **не доказано, что OFF был, затем выполнен ON**. Пост-smoke health отдельно не прислан. **G-08 BLOCKED/PENDING**. Fail-closed остановка скрипта — safety behavior, но не acceptance успеха flag-switch.

## Риски, Issue audit и следующий шаг

**Что НЕ доказано:** полная refund→provider reconciliation, новая policy #433, migration origin `legacy`, interrupted-work/no-blind-replay, OFF invoice/precheckout block, already-paid event processing при OFF, независимый VPS image/SHA, live Master/Node, G09/G10 natural events, G11 final acceptance. Script exception не является независимым доказательством DB corruption или runtime bug; перед новым bug Issue нужно выяснить, выполнялся ли подтверждённый Owner OFF и почему проверка в `STARS_OFF` увидела ON.

**Issue closure audit:** #433 OPEN (не реализовано), #342 CLOSED по своему отдельному Portal feature-flags acceptance (этот новый G-08 smoke scope не доказывает его регрессию), #317 CLOSED по своему quota-cycle scope. #466/#487/#564/#510 остаются OPEN по независимым residuals. **Ни одного Issue закрывать/переоткрывать на основании только этих stdout нельзя.** Самостоятельный issue о regression только при подтверждённом фактическом дефекте, а не по одному `RuntimeError`.

**STOP / Next:** зафиксировать этот пакет в верхней `docs/ROADMAP.md` через PR с required `test`/`title`, squash merge, независимый `main` read-back, Issue evidence/comment и повторную сверку статусов. **До checkpoint никакого следующего smoke.** После него выяснить один факт у оператора: была ли реально подтверждена кнопка `Новые Stars: отключить` перед запуском `STARS_OFF` и что отобразил Owner UI; получить код диагностического скрипта или sanitized traceback для локальной read-only диагностики. Ни повторного OFF→ON, ни restart, deploy, refund, Stars payment, provider mutation без отдельного согласия.
