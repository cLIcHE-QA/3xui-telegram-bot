# B3 — Master API HTTP 200, разбор JSON не завершён (2026-10-13)

## Источник, scope и четыре состояния

**Источник:** фактический текстовый stdout оператора из целевого read-only B3-сценария, `B3_CHECK_UTC=2026-10-13T11:29:47.790884+00:00` (**14:29:47.790884 EEST**), сообщение 2026-10-13 11:30:02 UTC. Проверка запущена оператором на production Master VPS, использован **один** выбранный refunded pilot owner и **один** authenticated HTTPS GET с `ssl=True`, `allow_redirects=False`, timeout 20 секунд в предоставленном сценарии. Сам факт исполнения этих условий подтверждается операторским stdout и описанием команды, не независимым SSH/network trace агента; полный ответ API, content-type, raw headers, schema объекта и источник HTML/другого содержимого **не предоставлены**. Без новых purchases, refunds, Stars toggles, provider mutations, SQL writes, deploy/restart, quota reset или повторного VPN импорта.

- **Merged `main` перед документальным PR:** `97d4a0fcc9d495f4276ba586bba591d3c4b5f1a1` после [PR #580](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/580), required `test` [38389583473](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38389583473) PASS, итоговый `title` [38389808184](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38389808184) PASS, post-merge `Python checks` [38389847307](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38389847307) PASS.
- **Published:** immutable prerelease `v5.0.0-rc.9`, tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; latest stable `v4.26.9` не равен последнему published prerelease.
- **Deployed:** последний подтверждённый оператором production baseline — `v5.0.0-rc.9`; текущий пакет не читал `APP_VERSION`, container SHA или image provenance, его полная независимая аттестация по-прежнему REVIEW.
- **Accepted:** общий v5 **NOT PASS**; публичный rollout **BLOCKED**. G-05 `PARTIAL`, B3 `PENDING` и G-05-D `INCONCLUSIVE` — не считать `PASS` или runtime `FAIL` по одному HTTP 200.

## Дословный предоставленный результат

```text
B3_CHECK_UTC=2026-10-13T11:29:47.790884+00:00
B3_OWNER_SELECTION=ONE
B3_HTTP_STATUS=200
B3_RESULT=PENDING_JSON_SHAPE
```

**Точная интерпретация:**
1. Из read-only SQLite-выборки нашёлся ровно один соответствующий ранее оплаченному/refunded pilot owner — `ONE` только для этой выборки.
2. У запрошенного HTTPS endpoint был статус `200`. Это **не** доказательство, что тело корректно вернул именно 3x-ui JSON envelope, что клиент включён, отключён или вообще найден.
3. Исполнявшийся скрипт остановился при `json.loads(raw)` (ветка `ValueError/UnicodeDecodeError`) и выдал `PENDING_JSON_SHAPE`. Он не дошёл до проверок `data.success`, `obj`, `obj.client`, `enable`, `expiryTime` и `inboundIds`; их значения **UNKNOWN/NOT OBSERVED**.
4. Причины возможны разные (HTML от reverse proxy/auth UI, пустой body, malformed JSON, кодировка и др.), но ни одна **не подтверждена**. Не открывать новый bug как факт неисправности 3x-ui без диагностики. Предыдущий G05-R5 `unclassified=1` и operator-reported S01 Master UI `enabled=YES` остаются в своих исторических scope, без ложного согласования в `DISABLED` или `MISSING`.

## Следующая граница диагностики — после checkpoint

Только если оператор согласует **один следующий ограниченный read-only запрос** к тому же pilot owner: классифицировать HTTP status, нормализованный media type (`application/json`, `text/html`, `other`, `missing`), пустое/непустое тело, признак `HTML/JSON/OTHER`, `redirect` без перехода, присутствие `success`, форму `obj` и тип `enable` **только при корректном JSON**. Не выводить тело ответа, заголовки с cookies/Authorization, URL, IP, email, Telegram ID, subscription link, GUID, source fingerprint или token. Не расширять выборку, не делать retries и не повторять S01 UI. При HTML/API mismatch дальнейший разбор сначала по конфигурации/маршрутизации в read-only режиме, без production changes.

## B4 и Issue audit

- Отдельное сообщение оператора 2026-10-13 11:25:37 UTC: **исторические материалы первоначального VPN импорта сохранились**. Архивные связи Stars payment → event → entitlement → provision → initial VPN import/use ещё не были просмотрены/сверены, поэтому **B4=PENDING, evidence available / NOT VERIFIED**. Не повторять покупку/import.
- [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) **OPEN**: B3 относится к Master provider read-only classification, не подтверждает direct-node sync, offline→return, quota/revoke no-blind-replay.
- [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) **OPEN**: будущая 14-дневная refund/revoke policy ещё не реализована; этот вывод не является её acceptance.
- #466/#510/#564/#577 и прочие незавершённые задачи остаются OPEN; #317/#342/#422 CLOSED по прежним собственным критериям. **Issue: N/A** — уточнение evidence существующего G-05-D, нового доказанного defect нет.
- **Checkpoint:** датированный audit + верхняя сводка `docs/ROADMAP.md`, docs-only PR с required `test`/`title`, squash merge, independent `main`/audit read-back, ссылка на evidence в связанном Issue и финальная сверка статусов. До merge и post-merge проверки **ROADMAP SYNC PENDING** и следующий production-пакет STOP.
