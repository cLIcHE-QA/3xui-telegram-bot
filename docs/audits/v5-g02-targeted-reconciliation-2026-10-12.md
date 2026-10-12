# v5 G-02 — production Master, точечная read-only reconciliation (2026-10-12)

## Дата, provenance и границы

- **Время исполнявшегося пакета:** `G02_UTC=2026-10-12T15:09:53+00:00` = **2026-10-12 18:09:53 Europe/Helsinki (EEST, UTC+03)**. Сообщение с итоговым stdout предоставил оператор в 15:09:59 UTC. Это **operator-supplied terminal evidence**, не прямое SSH наблюдение GitHub-агента.
- **Target:** production Master VPS, running Docker container `bot`. Read-only SQLite URI `file:/app/data/bot.sqlite3?mode=ro`, `PRAGMA query_only=ON`; один клиент через аутентифицированные **GET** `/panel/api/clients/get/{email}` и `/panel/api/clients/traffic/{email}` через существующий `XUIClient`, только при `VERIFY_TLS=true` и HTTPS. Таймаут ограничен. Ни одного raw ID/email/URL/token/order/refund reference в evidence нет.
- **Context:** защищённый GitHub `main` baseline `7113b65bf4ce7015104e5157ecd538b6064c9757` после [PR #553](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/553), post-merge [Python checks #38266517270](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38266517270) **SUCCESS**; latest GitHub Published immutable prerelease `v5.0.0-rc.9`, tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`.
- **Deployed:** предшествующий 2026-10-12 **17:36 EEST** [G-01 read-only baseline](v5-g01-production-baseline-2026-10-12.md) сообщил `HOST_HEAD_SHA` = immutable tag SHA, `APP_VERSION=5.0.0-rc.9`, image ID `sha256:efb2fb9ea3dffac70a3ca344d7843cabff67ae737875b461464e0b0705483f4c`. Текущий G-02 пакет повторную runtime identity проверку **не выполнял**. Production runtime остаётся подтверждён только операторским выводом (не агентским независимым SSH).
- **Scope:** до 8 последних существующих `paid` `XTR` orders среди текущего `ALLOWED_TELEGRAM_IDS` (нашлось 4), linked `telegram_stars` payments, webhook events, entitlements/quota, до 5 existing refunded payments среди pilot (нашлось 2), до 2 подходящих active/confirmed pilot customers через Master API (нашёлся 1). **Никаких новых Stars purchases, real refund, import/provisioning, node-side mutations, flag toggles, SQL writes или restart.**

## Предоставленный stdout (не секретные агрегаты)

```text
G02_UTC= 2026-10-12T15:09:53+00:00
G02-1 ORDER_PAYMENT: sample=4 linked=4 mismatches=0 status=PASS
G02-2 WEBHOOK_LINK: checked=4 missing_applied=0 status=PASS
G02-3 ENTITLEMENT_QUOTA: linked=4 mismatches=0 quota_review=0 status=PASS
G02-4 REFUND_JOURNAL: sampled=2 mismatches=0 status=PASS
G02-5 MASTER_PROVIDER: sampled=1 drift_or_missing=0 status=PASS
G02_DISPOSITION: targeted read-only; overall G-02 remains PARTIAL
```

## Фактический outcome и interpretation

| ID | Что сравнили | Результат в ограниченном scope |
| --- | --- | --- |
| G02-1 | Последние paid XTR pilot orders ↔ ровно один `confirmed/refunded` Telegram Stars payment на order, сумма и currency | 4/4 связаны, 0 mismatch — **scoped PASS**, не global ledger |
| G02-2 | Для каждого выбранного payment есть хотя бы один `signature_valid=1`, `applied`, `payment.confirmed` Telegram Stars webhook event с теми же `order_id/payment_id` | 4/4, missing 0 — **scoped PASS**; не проверены все события/replay истории |
| G02-3 | Ровно один entitlement на выбранный order, owner/plan совпадают; для active/suspended нет `pending/in_flight/unknown/failed` quota reset | 4/4, mismatch=0, quota_review=0 — **scoped PASS**; нет proof идемпотентности reset или фактического provider quota |
| G02-4 | Refund operation с `status=success` для `refunded` payment, согласованные владельцы и provider reference без раскрытия их значений | 2/2, mismatch=0 — **scoped PASS**; не проверен отзыв access/policy, нет нового refund |
| G02-5 | Одному `active` entitlement c `confirmed` paid payment соответствуют Master 3x-ui client: `enable=true`, expiry равен локальному (допуск ±2000 ms), `inboundIds` непустой список, поля traffic present | 1/1, mismatch=0 — **scoped PASS**. Важно: `traffic_present` проверяет наличие полей, **не фактические ненулевые bytes**; `inboundIds` непуст, но **не сверяли exact expected membership**, node-side и клиентское приложение. API authenticated read-through — **operator-supplied**, не агентский independent read-back |

## Disposition, issue closure audit, next

- **G-02: PARTIAL**, **все пять исполненных read-only subchecks scoped PASS по операторскому stdout**. Не выдавать `G02_DISPOSITION` за полный acceptance либо за доказательство отсутствия несверенных событий/клиентов: просмотрены лишь 4 pilot paid orders / 2 refunded / 1 активный Master client; не было full ledger, cross-node state, subscriber VPN import/use, customer-visible UI/traffic и всех unknown failure/retry paths. Previous local-only scoped checks на rc.7 сохраняют свой собственный исторический scope; не повторять/не считать заменой свежего Master sample.
- **G-03 PARTIAL:** full Stars → VPN client import/use and provider postcondition across real access/traffic still PENDING; никакой оплаты без отдельно согласованного разрешения. Предлагается **новый targeted read-only evidence-only пакет из 4–5 проверок** на существующих разрешённых pilot accounts, без перебора/раскрытия credentials или повторения завершённых сценариев.
- **G-04 PARTIAL:** refund journal link для 2 existing записей PASS, но customer Support path, entitlement/access postconditions, replay/unknown и текущая policy остаются PENDING; `#433` future 14-day policy **не включена в rc.9**.
- **Issues:** [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) **OPEN/PENDING**: один Master 3x-ui client read-only `PASS` не закрывает node-side sync/last state/identity; [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) **OPEN**, будущий refund contract не реализован; [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466) **OPEN**, natural `job_failed` не observed; #342 и #422 **CLOSED** только по ранее пройденному scoped acceptance. Ничего не закрывать данным пакетом.
- **G-01 PARTIAL** после 5/5 своего scoped PASS; **G-05…G-08 PARTIAL; G-09…G-11 PENDING**, **W-01 SKIPPED/OPERATOR-WAIVED/NOT TESTED**; **W-02 INCONCLUSIVE/OPERATOR-WAIVED**, оба не повторять. **Accepted overall v5 NOT PASS; public launch BLOCKED**.
- **Checkpoint:** обновить верхний `docs/ROADMAP.md` на отдельной ветке с этим audit, обязательный `test`/`title` CI, squash merge, независимый GitHub `main` read-back, сверка Issues и comments **до** передачи следующего пакета. Не смешивать `main` / Published / Deployed / Accepted.

**Evidence source** — stdout оператора, переданный в рамках текущего G-02 production acceptance; метаданные release/tag/PR/CI сверены отдельным read-only GitHub API.
