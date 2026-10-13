# D1–D3 — пассивные production observations: ресурсный snapshot, scheduled backup и исторический Stars OFF (2026-10-13)

## Источник, scope и четыре состояния

- **Источник:** обезличенный stdout оператора в чате **2026-10-13 12:51:23 UTC / 15:51:23 EEST**. Снимок D1: **2026-10-13 12:49:45 UTC / 15:49:45 EEST**; SQLite job/history read: **2026-10-13 12:51:10 UTC / 15:51:10 EEST**. Исторический интервал D3 относится к **2026-10-12 22:58:57–22:59:28 UTC** (13 октября **01:58:57–01:59:28 EEST**), а не времени нынешнего запроса.
- **Область:** действующий Master VPS и ограниченный production pilot. Оператор запустил только `docker inspect`, `docker stats --no-stream`, `GET /healthz`, чтение настроенного backup hour и SQLite `mode=ro`/query-only SELECT. Нет evidence нового Stars OFF/ON, invoice, precheckout, Stars payment/refund, нового backup, restore/decrypt/download, restart, deploy, 3x-ui mutation или искусственного сбоя. Агент не имел прямого VPS/SQLite доступа и не подтверждал вывод независимо.
- **Merged:** protected `main=fc113df13961036fbfcb429fa14fd6fd1ea16779` непосредственно до checkpoint (test-only #584, docs #585 MERGED, последний [CI run 38398461295](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38398461295) PASS; [publish/prepare 38398645457](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38398645457) PASS как CI, **не** новый Release). **Published:** последний GitHub Release immutable prerelease `v5.0.0-rc.9`, tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db` (2026-10-11). **Deployed:** последняя production-версия `rc.9` сообщена оператором; ни этот вывод, ни новые CI не подтверждают deployed image SHA или изменённый deployment. **Accepted:** v5 overall **NOT PASS**, public rollout **BLOCKED**.

## D1 / G-06 — один ресурсный snapshot, не bounded soak

```text
D1_CHECK_UTC=2026-10-13T12:49:45Z
D1_STATUS=running
D1_RESTART_COUNT=0
D1_OOM_KILLED=false
D1_CONTAINER_STARTED=2026-10-13T08:05:01.760541938Z
D1_CPU=0.00%
D1_RAM=254.9MiB / 1.757GiB
D1_RAM_PERCENT=14.16%
D1_PIDS=6
D1_HEALTH_HTTP=200
D1_BACKUP_HOUR_UTC=2
D1_JOB_CHECK_UTC=2026-10-13T12:51:10Z
D1_RUNNING_JOBS=0
D1_SCHEDULED_ERRORS_24H=0
D1_QUEUE_SIZE=NOT_INSTRUMENTED
```

**Итог D1: operator-reported health/resource single-snapshot scoped PASS, bounded-soak/cycle acceptance PARTIAL/PENDING.** Нет второго сопоставимого CPU/RAM/PIDs/health/queue snapshot после ближайшего естественного scheduled cycle; одна точка не измеряет тренд или runaway pattern. Последние scheduled backup jobs завершились в 02:00 UTC **за ~10 ч 50 мин до снимка**, поэтому не были охвачены двумя ресурсными снимками «до/после». Размер очереди неизвестен. Код rc.9 планирует backup в `BACKUP_HOUR_UTC` (здесь 02:00 UTC): следующий естественный цикл ожидается **2026-10-14 02:00 UTC** при неизменных настройках, без запуска или рестарта; снять второй resource snapshot можно только по уже согласованному отдельному read-only действию. **Не считать полный V5-A-003 soak PASS**: контракт также предусматривает full restart/deploy cycle и иные включённые scheduled jobs, а таких действий этот пакет не выполнял.

## D2 — scheduled Full Backup + encrypted off-site journal

```text
D2_DAILY_STATUS=success
D2_DAILY_START_UTC=2026-10-13T02:00:00Z
D2_DAILY_FINISH_UTC=2026-10-13T02:00:01Z
D2_DAILY_DURATION_MS=1405
D2_OFFSITE_STATUS=success
D2_OFFSITE_START_UTC=2026-10-13T02:00:01Z
D2_OFFSITE_FINISH_UTC=2026-10-13T02:00:02Z
D2_OFFSITE_DURATION_MS=784
D2_ARCHIVE_PAIR_MATCH=True
D2_OFFSITE_METADATA_COMPLETE=True
```

**Итог D2: operator-reported scheduled-journal scoped PASS**, в пределах одного natural 2026-10-13 scheduled `backup.daily`→`backup.offsite` цикла. Ссылки на канонический архив совпали по алгоритму сравнения имени, metadata fields присутствуют/типизированы. В **исходном коде rc.9**, успешное создание Full Backup выполняет `inspect_backup(..., deep=True)` до публикации архива; `OffsiteBackupService.upload_and_verify` вызывает `_validate_source` (manifest schema 2, bot DB, 3x-ui DB и bot env), шифрует, загружает, проверяет HEAD metadata и выполняет `download → decrypt → checksum/size → deep validation` до возврата успеха, а job status `success` сохраняется после успешного возврата. Эта согласованность кода и job journal — **не независимая проверка текущего remote object**. Нельзя объявлять реальное recovery/restore, сохранность recovery secret, самостоятельный новый decrypt/download или полный DR acceptance; raw archive, object keys и credentials не читать/не публиковать.

## D3 / G-08 — архивное окно Stars OFF: событие было, denial НЕ НАБЛЮДАЛСЯ

```text
D3_HISTORICAL_WINDOW_UTC=[2026-10-12T22:58:57Z,2026-10-12T22:59:28Z)
D3_FEATURE_AUDIT_EVENTS=1
D3_INVOICE_RECORDS=0
D3_STARS_PAYMENT_EVENTS=0
D3_CONFIRMED_PAYMENTS=0
D3_PRECHECKOUT_AUDIT=NOT_INSTRUMENTED
D3_SCOPE=HISTORICAL_JOURNAL_ONLY
```

Один `client.feature.toggle` audit event наблюдался внутри интервала; запрос специально использовал правую **исключительную** границу (`created_at < end`), поэтому событие ровно в 22:59:28 UTC не попадёт в выборку. Запись не включала в safe stdout значение OFF/ON или actor — не утверждать отдельный новый флаг-transition только по счётчику. `stars_invoice_messages` хранит **необязательные косметические** invoice message records, а не все попытки `sendInvoice` и `pre_checkout_query`. Нули платежей и invoice по SQLite не доказывают, что invoice или precheckout реально отклонялись. **Итог D3: исторический журнал OBSERVED (1 event), denial `NOT OBSERVED / PENDING`**, не `PASS` и не `FAIL`. Ранее пройденный G08 flag OFF→ON scoped PASS и восстановление сохраняются как отдельное evidence; флаг Stars **не переключать снова**, реальные покупки не инициировать.

## Issues и следующий checkpoint

- [#482](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/482) **OPEN**, собственные acceptance criteria включают измеренный synthetic load, bounded global read-only API budget, pooling и future code; D1 не закрывает и не является доказательством работы глобального API limiter.
- [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466) **OPEN / PENDING / NATURAL EVENT NOT OBSERVED**: `D1_SCHEDULED_ERRORS_24H=0` не доказывает фактический `job_failed` notification, cooldown/recovery или две проекции одного инцидента. Не генерировать fake failure на production.
- [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487), #433/#577 и остальные невыполненные Issues остаются OPEN; D1–D3 их критерии не закрывают. #317/#342/#422 CLOSED по отдельным прежним evidence.
- **Issue: N/A для нового**: docs-only синхронизация operator-supplied наблюдения существующих acceptance gates, самостоятельный подтверждённый defect отсутствует.
- **Next:** датированный audit + обновление верхней сводки Roadmap в docs-only PR с required `test`/`title`, squash merge, независимый `main`/audit read-back, evidence comments в #482/#466, собственные closure criteria и сверка Issues; post-merge CI отдельно. До checkpoint следующий пакет STOP. Для D1 можно позже получить только второй read-only snapshot после следующего естественного scheduled run; D3 не повторять Stars OFF.
