# B3 — форма JSON Master API классифицирована по ручному read-back (2026-10-13)

## Источник, время и неизменные границы проверки

Оператор в сообщении **2026-10-13 11:45:34 UTC / 14:45:34 EEST** предоставил фрагмент JSON от `GET /panel/api/clients/get/{email}` существующего refunded pilot-клиента Master 3x-ui. Это **время сообщения, а не независимо измеренное время HTTP-запроса**; HTTP status и response Content-Type именно этого ручного обращения отдельно не предоставлены. JSON частично скрыт оператором, но сообщение содержало также частные значения. **Идентификаторы пользователей, email, UUID, IP, subscription/public key material, URL и сырое тело не копируются в канонические документы, Issues или PR.** Ни агентский SSH-доступ, ни новые запросы, платежи, refund, изменения provider/DB, импорт или рестарт в этом документальном checkpoint не выполнялись.

**Четыре состояния:** `main=251f2866aedab03d520d3d0379b93d77ef88060a` до настоящего документационного PR ([PR #581](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/581) squash merged, required `test` [38391117119](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38391117119) PASS, итоговый `title` [38391343949](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38391343949) PASS, post-merge `Python checks` [38391382752](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38391382752) PASS); **Published** immutable prerelease `v5.0.0-rc.9`, tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; **Deployed** rc.9 подтверждено ранее только оператором, новый image/build SHA этим сообщением не аттестован; **Accepted** v5 overall `NOT PASS`, public rollout `BLOCKED`.

## Только обезличенный результат нового ручного JSON

- `success` — тип Boolean, значение `true`; `msg` — пустая строка.
- `obj` — объект; внутри `obj.client` — объект клиента: **вложенная форма `NESTED_CLIENT`**.
- `obj.client.enable` — Boolean `true`, классификация **`ENABLED`** в рамках данного ответа.
- `obj.client.expiryTime` — целочисленный timestamp в миллисекундах. Фактическое значение/точный срок в публичное evidence не переносим; он не доказывает права на любой отдельный refunded период.
- `obj.inboundIds` — непустой массив **на родительском уровне `obj`**, не внутри `obj.client`. Точный состав, приватные идентификаторы и node-side membership не публикуются.
- `obj.usedTraffic` — число; ненулевая величина не привязывает traffic к конкретной покупке или импорту.
- Это **operator-supplied manual endpoint response**, а не независимый agent API readback. Не подтверждено, что свежий ответ прошёл через именно тот же Python runtime-клиент/маршрут, что прежний stdout.

**Disposition:** `B3_MANUAL_API_SHAPE=SCOPED_PASS`; `B3_MANUAL_ACCESS_CLASS=ENABLED` для **одного** существующего клиента. Published rc.9 `XuiCustomerProvider.access()` явно использует `client = obj.get("client", obj)` и требует `enable` типа Boolean; предоставленная вложенная структура **совместима с этим контрактом**. При этом `XUIClient.get_client()` возвращает `data.obj`, а `inboundIds` находится на внешнем уровне; не утверждать, что все потребители `inboundIds` одинаково нормализуют поле, без отдельного code review.

**Исторический результат остаётся:** в предыдущем [B3 audit](v5-b3-master-api-json-shape-pending-2026-10-13.md) однократный операторский scripted GET с `B3_HTTP_STATUS=200` завершился `B3_RESULT=PENDING_JSON_SHAPE` до любых полей `obj`/`enable`. Новый ручной JSON **не доказывает**, почему предыдущий `json.loads` не сработал (разный ответ, маршрут, headers/proxy или иной фактор): `B3_PREVIOUS_SCRIPT_PARSE_CAUSE=PENDING`. Предыдущее `G05-R5 unclassified=1` также сохраняется отдельным фактом; новая ручная классификация не заменяет доказательство его root cause. **G-05 overall PARTIAL**, никакой новой диагностики/повторного GET не запускать только для закрытия отчёта.

## Остальные gates, Issues и следующий checkpoint

- **B4 / G-03:** оператор отдельно подтвердил, что исторические материалы первоначального VPN-импорта **сохранились**, но их causal linkage со Stars payment → event → entitlement → provider provisioning ещё не сверялся: `B4=EVIDENCE_AVAILABLE / PENDING_VERIFICATION`. Уже закрытый G-03 bounded smoke не повторять.
- [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) **OPEN**: Master client `enabled` и непустые inbound IDs не доказывают direct-node last sync/offline→recovery/quota/revoke no-blind-replay.
- [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) **OPEN**: новая 14-дневная refund с вычетом оплаченного срока в rc.9 не реализована; найденный `enabled` не является её дефектом/acceptance.
- [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466)/#510/#564/#577 и прочие не завершённые задачи остаются OPEN; #317/#342/#422 CLOSED по собственным критериям. **Issue: N/A — лишь закрыт узкий manual JSON-shape evidence на существующем G-05-D, нового подтверждённого дефекта нет.** Не закрывать Issues на основании этой формы.
- **Следующий шаг:** docs-only Roadmap PR с required `test` и `title`, squash merge и независимый `main`/audit/Issue read-back. Только после checkpoint, если нужно, переходить к B4 архивному просмотру без повторной покупки/импорта; дополнительный API запрос без новой гипотезы не требуется. **ROADMAP SYNC PENDING** до завершения PR/CI/read-back.
