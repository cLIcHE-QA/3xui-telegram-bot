# D1 / G-06 — второй read-only snapshot после естественного scheduled backup, 2026-10-14

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-14 12:37 UTC+03:00 (EEST; resource snapshot 2026-10-14T09:37:54Z, SQLite job read 09:37:56Z)
- **Окружение:** действующий production Master, ограниченный v5 controlled canary; только operator-reported read-only stdout; независимого VPS-доступа у агента не было
- **Цель:** согласованный D1/G-06 второй ресурсный snapshot после следующего *естественного* backup cycle, сравнение с первым snapshot 2026-10-13T12:49:45Z; подтвердить scoped job/resource outcome, не подменять full V5-A-003 soak
- **Версия и immutable tag/SHA:** последний Published `v5.0.0-rc.9`, tag `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; source baseline protected main `3af067f357214218788bd5e08db5ee50f2cc1f08`. Deployed rc.9 только operator-reported, Docker image/SHA независимо не аттестован
- **Scope:** `docker inspect`, `docker stats --no-stream`, локальный HTTP GET `/healthz`, SQLite `mode=ro`/`PRAGMA query_only=ON` SELECT для running/scheduled jobs и natural `backup.daily`/`backup.offsite`; ничего не записывалось, не перезапускалось и не запускалось принудительно. Не проверялись archive contents, cloud object, restore/decrypt, full load/soak, all enabled jobs, invoice/refund, Master/3x-ui/paid expiry и отдельный G-09
- **Фактический результат:** PASS — **D1 limited follow-up scoped PASS (operator-reported)**: second snapshot healthy, same container started 2026-10-13T08:05:01.760541938Z, zero restarts/OOM, both natural scheduled backup jobs `success` 2026-10-14 02:00 UTC; **G-06 full V5-A-003 soak PARTIAL**, v5 overall NOT PASS
- **Источник и evidence:** оператор прислал обезличенный stdout в чате 2026-10-14T09:38:07Z (данные ниже); первый снимок и baseline [D1–D3 audit](v5-d1-d3-passive-production-readback-2026-10-13.md), decision [G-09→D1→G-11](v5-g09-d1-before-g11-decision-2026-10-13.md); исходный код scheduled jobs: `app_runtime.py`, `offsite_backup.py`; контекст CI [postmerge Python checks #38539281142](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38539281142) PASS относится к main, не к проверке VPS
- **Ограничения и остаточные риски:** два разнесённых во времени snapshot — не непрерывный CPU/RAM/queue soak и не доказательство отсутствия кратковременных пиков; `D1_QUEUE_SIZE=NOT_INSTRUMENTED`; `backup.offsite: success` — только journal/status, **не независимое** cloud integrity/restore attestation; source/version самого запущенного Docker image не подтверждены; W-01/W-02 остаются WAIVED/NOT PASS, G-09 natural paid expiry PENDING, общий G-06 и v5 acceptance PARTIAL/NOT PASS
- **Связанные Issues:** #482 OPEN — future global 3x-ui API budget/real load measurements, D1 не удовлетворяет его acceptance; #466 OPEN — passive natural `job_failed` NOT OBSERVED (scheduled errors 24h=0 не доказывает notification); #487 OPEN не затронут. **Новый Issue N/A:** docs-only evidence существующего gate G-06, самостоятельного дефекта не обнаружено
- **Следующий шаг:** обновить существующие G-06, D1 и G-11 строки канонического Roadmap через PR с required `test`/`title`, squash merge, postmerge CI и независимый main/Issue read-back; затем только после **реального** G-09 paid entitlement natural expiry и его отдельного read-only + docs checkpoint переходить к G-11 final report
- **Раздельные состояния:** merged=protected main `3af067f357214218788bd5e08db5ee50f2cc1f08` before this docs PR; published=`v5.0.0-rc.9` tag `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; deployed=rc.9 operator-reported (independent image/VPS attestation PENDING); accepted=**D1 limited follow-up scoped PASS** only, G-06 full soak PARTIAL, overall v5 NOT PASS / public rollout BLOCKED

## Сопоставление двух D1 snapshot

| Метрика | 2026-10-13 12:49:45 UTC, до нового scheduled cycle | 2026-10-14 09:37:54 UTC, после цикла |
| --- | --- | --- |
| Container state | running | running |
| Started at (UTC) | 2026-10-13T08:05:01.760541938Z | 2026-10-13T08:05:01.760541938Z |
| Restart count / OOM | 0 / false | 0 / false |
| CPU | 0.00% | 0.00% |
| RAM | 254.9 MiB / 1.757 GiB | 73.57 MiB / 1.757 GiB |
| RAM% | 14.16% | 4.09% |
| PIDs | 6 | 6 |
| GET /healthz | HTTP 200 | HTTP 200 |
| Running jobs | 0 | 0 |
| Scheduled failed/unknown 24h | 0 | 0 |
| Scheduled partial 24h | не измерялось | 0 |
| Queue size | NOT_INSTRUMENTED | NOT_INSTRUMENTED |

Точка 14 октября потребляет на 181.33 MiB меньше RAM (около 71%), но два снимка сами по себе не объясняют изменение и не позволяют оценить пики между измерениями. Контейнер запущен с 13 октября 08:05 UTC и пережил естественный цикл без рестарта.

## Натуральный scheduled cycle: 2026-10-14 02:00 UTC

| Job | Status | Start UTC | Finish UTC |
| --- | --- | --- | --- |
| `backup.daily` | success | 2026-10-14T02:00:00Z | 2026-10-14T02:00:01Z |
| `backup.offsite` | success | 2026-10-14T02:00:01Z | 2026-10-14T02:00:02Z |

`D1_DB_READ=OK`, `D1_BACKUP_HOUR_UTC=2`, `D1_JOB_CHECK_UTC=2026-10-14T09:37:56Z`, `D1_SCHEDULED_ERRORS_24H=0`, `D1_SCHEDULED_PARTIAL_24H=0`. Задания только наблюдались: **новый backup/restore/restart/deploy не запускался**. G-09 не проверялся, G-11 до его реального evidence и Roadmap checkpoint заблокирован.
