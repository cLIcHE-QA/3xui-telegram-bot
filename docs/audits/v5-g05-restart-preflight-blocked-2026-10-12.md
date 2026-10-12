# G-05 — controlled bot restart: защитный preflight BLOCKED (2026-10-12)

## Фактическое свидетельство

- **Источник:** вывод SSH-консоли, переданный оператором в сообщении **2026-10-12 16:11:45 UTC / 19:11:45 Europe/Helsinki EEST**. Точное время исполнения команды в stdout не указано; timestamp сообщения — верхняя граница события, а не якобы измеренное время restart.
- **Предоставленный sanitized stdout:**

```text
STOP: verified Full Backup required
logout
Connection to [redacted] closed.
```

- **Контекст запуска:** предложенный controlled restart runbook имеет явный `BACKUP_VERIFIED=NO`, затем до обращения к Docker вызывается guard `[ "$BACKUP_VERIFIED" = YES ] || { echo "STOP: verified Full Backup required"; exit 1; }`. Exit status после guard: команда **не дошла до** deployed checkout check, Docker container probe, health, SQLite snapshot, запуска `docker compose restart bot` и post-restart read-back. `logout` доказывает лишь завершение SSH-сессии; не Docker restart.
- **Что известно:** **preflight guard WORKED / scoped PASS**; проверка существования, свежести, checksum/manifest и пригодности конкретного Full Backup **NOT EXECUTED / PENDING**, фактический backup status **UNKNOWN**, а не `corrupt`/`missing`; **production restart BLOCKED / NOT EXECUTED**, resulting container/health state **NOT RECHECKED**. No intentionally injected provider failures, no payment/reconciliation replay, no refund, no DB writes, no deploy/image rebuild and no runtime flag changes.
- **Целевой production scope:** Master controlled-pilot service `bot` only, no 3x-ui/node lifecycle. **Published** immutable `v5.0.0-rc.9` SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; **Deployed** `rc.9` по предыдущему операторскому read-back G-01, **в этом blocked запуске identity не перечитывалась**, independent VPS attestation отсутствует; **Accepted** overall v5 **NOT PASS**.
- **GitHub prior checkpoint:** protected `main` `8b85cdfe6e23c7b654eb37e2eeeb26ba528e9f9d`; [PR #557](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/557) squash merged, required `test`/`title` PASS; post-merge [Python checks 38275048499](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38275048499) **SUCCESS**. Last Published release unchanged. Previous [G-05 passive audit](v5-g05-passive-recovery-2026-10-12.md) remains **3 scoped PASS + 1 REVIEW (`legacy=1`)**; this attempt does not supersede it.

## Correct disposition / next gate

**G-05 PARTIAL:** additional restart preflight **BLOCKED** at unconfirmed Full Backup, actual restart/recovery **PENDING**, no new runtime PASS. Source code fail-closed guard is intentionally restrictive and should not be bypassed by blindly setting `BACKUP_VERIFIED=YES`. Operator's approval for controlled restart does **not** mean backup has been verified.

**Следующий пакет только после данного Roadmap/Issue checkpoint:** 3–4 targeted backup/health read-only checks (existing archive inventory, canonical deep validation `RestoreManager.inspect_backup(..., deep=True)` with manifest schema 2, bot DB + Master x-ui DB integrity, and operator review of restorable version/path/age plus expected rollback). Это локальная проверка имеющегося archive, **не** off-site upload/restore. Не выводить `.env`, backup files, panel tokens/URL, Telegram IDs, raw node metadata. Python deep validator распаковывает SQLite bytes во временный приватный каталог только для `PRAGMA quick_check`, не пишет в production databases. Stop on archive missing/old, deep validation errors, wrong version, required components missing, unable to verify backup provenance, or lack of restore path. До успешного preflight **не** запускать restart. Если backup не найден/невалиден, создание нового Full Backup либо refresh/restore — отдельная approval/action с собственным checkpoint.

**Связанные Issues:** #466 **OPEN** (natural production job_failed не наблюдался; fake failure запрещено выдавать за natural event), #487 **OPEN** (node-side sync/recovery не проверялись), #433 **OPEN** (будущая refund policy не относится к этой попытке). #317, #342, #422 **CLOSED** по прежним scoped criteria — не переоткрывать. **Issue: N/A** для этой записи: только accepted G-05/V5-A-002 preflight checkpoint без нового дефекта или самостоятельной задачи. W-01 DR waived/untested и W-02 burst inconclusive/waived не повторяли.

**Checkpoint workflow:** обновить верхнюю текущую сводку и G-05 строку в `docs/ROADMAP.md` через docs-only PR, required `test`/`title`, squash, независимый GitHub `main` read-back и Issue audit прежде чем давать следующий пакет; не путать `main`, Published, Deployed, Accepted.
