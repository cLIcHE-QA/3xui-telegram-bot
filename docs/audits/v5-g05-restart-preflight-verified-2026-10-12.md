# G-05 — controlled restart preflight: Full Backup PASS, restart NOT EXECUTED (2026-10-12)

## Время, provenance и target

- **Источник:** оператор прислал результат исполнения read-only блока в **2026-10-12 16:29:59 UTC / 19:29:59 Europe/Helsinki EEST**; точное время запуска внутри stdout не напечатано. Дата сообщения служит отметкой evidence, **не** утверждением о времени последнего backup/restart.
- **Target:** production Master VPS, deployed Docker Compose сервис `bot`; установленный в host checkout release идентифицировался только guard `git rev-parse HEAD == 13fdbe8bccfbe92cffc4117b79083bbdcad5a8db` (успешно прошёл), с заданной командой health `curl -fsS ... /healthz`. Нет agent-side SSH; это **operator-supplied terminal evidence**.
- **Published:** immutable `v5.0.0-rc.9` SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; **Deployed:** ранее operator-supplied image fingerprint G-01 совпал с этим релизом (2026-10-12 17:36 EEST), данный G-05 preflight только проверил host checkout SHA/health, контейнерный image/version на этом пакете не считывался. **Accepted:** общий v5 `NOT PASS`.
- **GitHub baseline до checkpoint:** protected `main` `156701e98f9ec209ca7b84311a47fac665e7c4a4` после [PR #558](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/558) MERGED; post-merge [Python checks 38277660358](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38277660358) SUCCESS.
- **Previous attempt:** `BACKUP_VERIFIED=NO` → `STOP: verified Full Backup required` (2026-10-12 19:11:45 EEST), archive *не проверялся*, Docker restart не выполнялся; [blocked checkpoint audit](v5-g05-restart-preflight-blocked-2026-10-12.md) сохранён отдельно. Новый результат *дополняет*, но **не стирает** прошлое STOP.

## Фактический безопасный вывод оператора

```text
=== G05-R1: PRODUCTION PREFLIGHT ===
HEALTH=ok
=== G05-R2: DEEP FULL BACKUP VALIDATION ===
BACKUP_FOUND=True
BACKUP_AGE_HOURS= 14.5
BACKUP_VALID= True
MANIFEST_SCHEMA= 2
BACKUP_VERSION= 5.0.0-rc.9
BOT_DB_OK= True
XUI_DB_OK= True
HAS_BOT_ENV= True
ERROR_COUNT= 0
BACKUP_DEEP_VALIDATION=PASS
=== G05-R3: ACTIVE WORK GUARD ===
PROVISIONING 0
QUOTA_INFLIGHT 0
REFUND_INFLIGHT 0
RUNNING_JOBS 0
ACTIVE_WORK_GUARD=PASS
G05_RESTART_PREFLIGHT=PASS
RESTART=NOT_EXECUTED
```

| ID | Ожидалось | Что действительно получено | Disposition |
| --- | --- | --- | --- |
| G05-R1 | Released host checkout SHA `v5.0.0-rc.9`, Docker container exists, `/healthz=ok` | Guard прошёл до health, `HEALTH=ok`; image ID/restart counter не выводились | **PASS** для guard и health, не full deployed attestation |
| G05-R2 | Последний существующий Full Backup deep-inspection `RestoreManager.inspect_backup(deep=True)`: манифест schema 2, SHA-256 и размеры, SQLite quick-check, `bot.env`, version `rc.9`, возраст ≤ 24h | Архив найден; 14.5 h, valid True, schema 2, version `5.0.0-rc.9`, обе DB OK, env present, error count 0 | **PASS**, локальная integrity/restore *preflight*, а не actual restore/off-site round-trip |
| G05-R3 | Нет `entitlements.provisioning`, quota reset `in_flight`, refund `in_flight`, job_runs `running` перед потенциальным restart | Все 4 счётчика 0, `ACTIVE_WORK_GUARD=PASS` | **PASS** на момент read-only snapshot; новые операции теоретически возможны позже |
| Restart | Только после preflight, с повторной immediate проверкой перед mutation | `RESTART=NOT_EXECUTED` | **PENDING/NOT EXECUTED**, никаких post-restart health/reconciliation PASS |

**Dispostion:** **3/3 scoped production preflight PASS**; **G-05 остаётся PARTIAL** (ранее 3/4 passive PASS + `legacy=1` REVIEW; actual restart/no replay/fault recovery ещё не пройдены). Одна `legacy` finite-traffic entitlement остаётся **REVIEW** и не подлежит автоматическому `bulkResetTraffic`.

## Безопасная дальнейшая последовательность

- Full Backup локальный и подходит под текущую version/integrity preflight; **не проверялся фактический restore, off-site encrypted round-trip, scheduled jobs, доступность recovery VPS/host**. W-01 cross-host DR waived/not tested и не возобновляется.
- Оператор ранее разрешил controlled production restart. После PR и Issue audit допустим **один** `docker compose restart bot` при непосредственных no-inflight/health/version/backup stop-условиях, без deploy/rebuild/flag mutations и без 3x-ui/native host/node restart. Нужно записать `StartedAt`/image ID/health до и после и отдельно изучить отсутствие unexplained payment/entitlement/quota mutation replay. **Time-of-check/time-of-use race** полностью не исключается; выполнять в спокойное pilot окно, stop on drift.
- Никакие *реальные* Telegram Stars payments/refunds не повторяются, provider fail injection/duplicate/delayed event не запускаются на production без безопасной изоляции с fake provider и disposable SQLite. Никаких намеренных `job_failed` на deployed instance.
- #466 OPEN (natural job_failed PENDING), #487 OPEN (node-side recovery/sync PENDING), #433 OPEN (future refund policy). #317/#342/#422 сохраняют CLOSED по своим отдельным критериям. Все Issue states сверить после merge.
- Следующий пакет: один controlled `bot` restart с чётким postcondition, **только после** required `test`/`title`, squash merge, независимого `main` Roadmap/audit read-back и Issue audit.
- G-01…G-04 PARTIAL; G-06…G-08 PARTIAL; G-09…G-11 PENDING; общий v5 `NOT PASS`; public expansion заблокирован. Не повторять W-02 Telegram burst (waived/inconclusive).
