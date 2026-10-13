# A1–A4: Docker image, rate-limit и Master → Node — targeted read-only пакет (2026-10-13)

## Источник и четыре статуса

- **Source:** обезличенный операторский вывод в чате **2026-10-13 10:10:14 UTC / 13:10:14 EEST**; точное время выполнения каждой команды и отдельные node-side screenshots/logs не присланы. Production Master VPS Docker Compose bot и одна показанная direct Node, клиент из уже разрешённого pilot. Код/документация прочитаны из актуального GitHub; **агент не имел самостоятельного SSH/VPS доступа**.
- **Merged/main на момент до PR:** `0dc2496c76397885f06f9eb08d19ca2def9b1d58` (актуальный docs HEAD, **не** release SHA). **Published:** prerelease `v5.0.0-rc.9` tag commit `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`. **Deployed:** operator-reported host HEAD и release tag оба указывают на этот SHA, работающий контейнер предъявил **другой** image ID, чем ранее, поэтому exact build/source provenance ещё **REVIEW**. **Accepted:** общий v5 `NOT PASS`, public rollout `BLOCKED`.
- **Историческая исходная точка:** [G-01 audit от 2026-10-12 14:36:21 UTC](v5-g01-production-baseline-2026-10-12.md) содержал image ID `sha256:efb2fb9ea3dffac70a3ca344d7843cabff67ae737875b461464e0b0705483f4c` и сравнение **6/6** source-file digests. **Не повторять** это сравнение без новой целевой гипотезы. Тот audit остаётся неизменным.

## A1 — image identity / provenance: REVIEW, не runtime FAIL

Новый stdout дважды подтверждает running `IMAGE_ID=CURRENT_IMAGE_ID=sha256:a82ce075cb35d71bc400863474e80efd9afd7ce307daceda3c7f0a2b1bf2de01`; image ref `3xui-telegram-bot-bot`. `HOST_GIT_SHA=RELEASE_TAG_SHA=13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`. **A1_IMAGE_ID_MATCH=NO_REVIEW**, поскольку прежний image ID был `sha256:efb2fb9ea3dffac70a3ca344d7843cabff67ae737875b461464e0b0705483f4c`.

- Само несовпадение доказывает **смену image identity** между двумя операторскими наблюдениями. Не доказывает deploy, rebuild, tampering, runtime defect или изменённый исходный код. Совпадение host tag SHA не доказывает, что новый образ собран из этого же дерева. В `Dockerfile` отсутствует `org.opencontainers.image.revision` label, а `docker-compose.yml` собирает локальный `build: .`. Поэтому A1 **REVIEW / IMAGE BUILD PROVENANCE PENDING**.
- Следующий безопасный шаг **после checkpoint**, если нужен: сравнить только `docker image inspect` creation timestamp/ID и `docker inspect` container Created + локальную git dirty state; при неожиданном изменении — отдельно согласовать адресное read-only code-fingerprint сравнение для нового image (не общую регрессию), без `docker build/up/restart/pull`. Не пытаться принудительно восстановить прежний image.

## A2 — effective client rate-limit: PARTIAL / default contract verified

Операторский скрипт вывел `CLIENT_RATE_LIMIT_COUNT = UNSET_OR_INVALID`, `CLIENT_RATE_LIMIT_WINDOW_SECONDS = UNSET_OR_INVALID`. Его ветка объединяет **отсутствующую env-переменную** с **некорректным значением**, поэтому отдельный runtime effective count/window **не доказан**.

Read-only сверка *того же опубликованного tag* `config.py` подтверждает, что при отсутствующих env-переменных используются defaults **30 запросов / 60 секунд** (`int(os.getenv("CLIENT_RATE_LIMIT_COUNT", "30"))`, `int(os.getenv("CLIENT_RATE_LIMIT_WINDOW_SECONDS", "60"))`), допустимые диапазоны 1..1000 и 1..3600. `client_access.py` инициализирует `SlidingWindowRateLimiter` этими settings; `business_admin.py` умеет показывать `Rate limit: X / Y сек.`. Следовательно `UNSET_OR_INVALID` **не равно limiter OFF**. **A2 = PARTIAL** до одного адресного read-only effective-settings readback или операторского уже сохранённого UI вывода; менять env не нужно.

## A3 — direct Node identity/state: scoped PASS для наблюдаемой Node; last successful sync не доказан

Оператор показал ответ Master nodes API `success=true` и **одну** node view. Без публикации node hostname, API basePath, private GUID, parent GUID и другой связанной с инфраструктурой информации в публичный audit:

- `inboundSyncMode=all`, `status=online`, `xrayState=running`, `configDirty=false`, `lastError` пусто; `panelVersion=3.9.0`, `xrayVersion=26.9.30`.
- `lastHeartbeat=1791886160` → **2026-10-13 10:09:20 UTC / 13:09:20 EEST**, за ~54 секунды до времени операторского сообщения. Это свежий **heartbeat**, но не непременно время последней успешно применённой конфигурации на Node. `configDirty=false` не доказывает offline→recovery или поступление новой mutation.
- **A3 scoped operator-reported PASS** для одной node API entry и текущих mode/status/identity fields. Master/Node GUID сравнение `NODE_GUID_MATCH=YES` сообщено оператором; сами идентификаторы не публикуются. **Точный last-successful-sync state и offline/recovery остаются PENDING** по [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487).

## A4 — существующий разрешённый клиент: scoped operator-reported PASS

`A4_NODE_INBOUND_EXACT=PASS`, `INBOUND_SET_MATCH=YES`, `EXPIRY_MATCH=YES`, `NODE_GUID_MATCH=YES` — сообщены оператором для одного разрешённого существующего клиента. **Scoped PASS** только для этих сравнений, без raw customer IDs, subscription URLs или полного provider dump. Отдельное табличное значение `enabled` в присланном тексте не приведено, хотя A4 общий PASS заявлен; **не считать его независимым read-back**. Не доказывает все клиентские mappings, изменённый квотный доступ или node-side recovery после недоступности.

## Issue audit / remaining gates / следующее действие

- **G-01:** ранее SMOKE CLOSED; текущий A1 image ID drift означает **недоказанный image/build provenance**, A2 default contract известен, effective values PENDING. **G-01 full acceptance PARTIAL**, не `✅`.
- **G-02:** ранее SMOKE CLOSED; A3/A4 добавляют точные versions, режим, node heartbeat и совпадения одного клиента, но full ledger / всех Node sync / offline return не подтверждены. **G-02 full acceptance PARTIAL**. [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) **OPEN**, его offline/return и no-replay criteria ещё не выполнены; только evidence-comment, не закрывать.
- G-03/G-04/G-05/G-06/G-07/G-08 и G-11 сохраняют прежние full-acceptance residuals. **G-09** ожидает естественного события вечером; **G-10** отложен оператором и не тормозит следующие пакеты, но `PENDING`/[#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466) OPEN, не `WAIVED`. W-01/W-02 не повторять.
- **STOP/checkpoint:** новый датированный Roadmap через docs-only PR с required CI, squash и `main` readback, Issue evidence and closure audit. Только затем следующий пакет B. Никаких production мутаций, deploy/restart, Stars payment/refund или новых provider edits агент не производил. Публикация этого audit не является независимой deployed attestation.
