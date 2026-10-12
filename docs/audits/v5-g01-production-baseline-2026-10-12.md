# v5 G-01 — production baseline rc.9: операторский read-only пакет 5/5

## Дата, источник и границы

- **Дата самого вывода:** 2026-10-12 **14:36:21 UTC** = **17:36:21 Europe/Helsinki EEST (UTC+03:00)**; пользователь передал stdout 2026-10-12 14:36:38 UTC.
- **Окружение:** production Master VPS, running Docker Compose `bot`, установленный 3x-ui native systemd. Команды выполнял оператор через SSH. У агента не было прямого SSH-доступа; **evidence operator-supplied / operator-reported**, не независимая проверка VPS.
- **Scope:** только пять отдельных G-01 read-only baseline checks, без повторной покупки Stars, refund, redeploy/restart, изменения runtime flags, SQL writes, 3x-ui mutations, Telegram burst, DR.
- **GitHub источник:** protected `main` до checkpoint `bf8d5ff50b65b37cac93244b3e4e5a3e8f596546`; [PR #552](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/552) MERGED, post-merge [Python checks 38262368270](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38262368270) PASS. `main` является documentation/process baseline, **не** production tag.
- **Published immutable:** [`v5.0.0-rc.9`](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.9), tag commit SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`. **Deployed:** fresh **operator-reported** read-back ниже показывает тот же tag SHA, image ID `sha256:efb2fb9ea3dffac70a3ca344d7843cabff67ae737875b461464e0b0705483f4c`. **Accepted:** overall v5 NOT PASS.

## Фактические результаты, ожидаемое и evidence

| ID | Ожидалось | Переданный stdout | Статус проверенного scope |
| --- | --- | --- | --- |
| G01-1 | Published SHA совпадает с host checkout, bot running, `APP_VERSION=5.0.0-rc.9`, без restart loop | `TAG_SHA=13fdbe8...a8db` (полный SHA выше), `HOST_HEAD_SHA=13fdbe8...a8db`, `CONTAINER=running`, `RESTARTS=0`, `APP_VERSION=5.0.0-rc.9`; image ID указан выше | **PASS (operator-supplied)** для конкретных полей |
| G01-2 | Проверить код работающего container против immutable `v5.0.0-rc.9` | `MATCH` 6/6: `version.py`, `client_access.py`, `client_flags.py`, `commerce.py`, `db_migrations.py`, `subscription_proxy.py` | **PASS (6-file SHA-256 comparison)**, не full image/build attestation |
| G01-3 | Базовый health и доступность 3x-ui | `HEALTHZ=ok`, `systemctl is-active x-ui.service` → `active`, `UPSTREAM_TCP=ok` | **PASS** для liveness/service/TCP, **authenticated 3x-ui API NOT TESTED** |
| G01-4 | SQLite quick check ok, schema v13, нет незавершённых миграций | `QUICK_CHECK=ok`, `SCHEMA_VERSION=13`, `MIGRATIONS_NOT_SUCCESS=0` | **PASS** read-only SQLite |
| G01-5 | Ограниченный pilot, фактические effective Portal/Stars flags | `ALLOWLIST_COUNT=3`, `ADMIN_COUNT=1`, `ENV_PORTAL=True`, `ENV_STARS=True`, `DB_PORTAL=True`, `DB_STARS=True`, `EFFECTIVE_PORTAL=True`, `EFFECTIVE_STARS=True` | **PASS** read-only флаги/counts; без раскрытия IDs |

Ни один Telegram ID, subscription URL, auth secret, raw order/payment/entitlement или содержимое SQLite не публикуется. Публикуется только безопасная метаинформация, присланная оператором.

## Scope disposition и остающиеся gates

- **G-01: PARTIAL (5/5 операторских read-only под-проверок scoped PASS)**. Изменять на полноценный независимый `PASS` пока нельзя: отсутствует agent/third-party independent VPS image/SHA read-back, а `UPSTREAM_TCP` не является аутентифицированным API/hosts/nodes status. Также не снят отдельный baseline rate-limit policy (актуальные значения здесь не проверялись). Это не обнаруженный production дефект.
- **G-02/G-03/G-04: PENDING/PARTIAL без нового evidence**; отдельные read-only пакеты по уже существующим событиям/записям с соблюдением privacy, *без* новых Stars purchases/refunds и повторов старых тестов.
- **G-05…G-08:** прежний PARTIAL. **G-09/G-10/G-11:** прежний PENDING. **W-01** independent DR = `SKIPPED/OPERATOR-WAIVED/NOT TESTED`, **W-02** Telegram burst = `INCONCLUSIVE/OPERATOR-WAIVED`; не повторять.
- **Связанные Issues:** [#342](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/342) и [#422](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/422) остаются CLOSED по *их* прежним targeted criteria; этот read-only baseline не повторяет switches/Hosts smoke. [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) остаётся OPEN — TCP/service не доказывают node-side sync. [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466) остаётся OPEN (natural event ещё не наблюдался). [#501](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/501) — unrelated future backlog, OPEN.
- **Следующий шаг:** checkpoint в `docs/ROADMAP.md` → docs-only PR с required `test`/`title` → squash merge → независимый GitHub read-back `main` и issue closure audit. Только затем предложить следующий G-02 пакет из 4–5 строго read-only reconciliation checks. Ни один gate не расширяет cohort/public launch.

**Примечание к provenance:** оператор передал результаты терминала; это существенно сильнее прежнего устного сообщения о deployment, но само по себе всё ещё не является независимым доступом агента к production VPS. `HEALTHZ=ok` не служит доказательством прикладной payment/provisioning/API reconciliation.
