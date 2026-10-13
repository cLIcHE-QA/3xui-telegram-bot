# G05-A / G08-D / G08-E — операторские статусы и безопасный provenance-check (2026-10-13)

## Источник, дата, scope

- **Источник:** операторское сообщение в текущем чате **2026-10-13 06:39:11 UTC / 09:39:11 EEST**: `G05-A: PENDING`, `G08-E: PASS`, `G08-D: PASS`, запрос инструкции проверки origin `legacy=1`. В сообщении **не приложены** timestamps выполнения G08-D/E, health output, UI screen/readback, DB quick_check, 3x-ui/VPN raw or sanitized result. Сообщение не является независимой VPS attestation.
- **Target/scope:** production Master и существующий pilot из 3 ранее разрешённых identities; текущая **после Stars ON** проверка post-cycle Health/DB/3x-ui (G08-E) и доступность Owner `/admin`, существующей `/subscription`/VPN (G08-D) — **только заявленный оператором PASS**. Это **не** доказательство этих postconditions *при Stars OFF* и не новая общая регрессия.
- **Version states:** перед текущим docs PR защищённый `main=6922f0b348a72fb0845c1edfb27cff9981df4c1a` (PR #572); **Published** immutable prerelease `v5.0.0-rc.9`, tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; **Deployed** rc.9 подтверждён ранее только оператором, в этом сообщении нет нового image/build SHA; **Accepted** v5 `NOT PASS`, public rollout `BLOCKED`. Не смешивать GitHub postmerge CI и production observations.
- **Provenance уровня приложения:** read-only repo inspection `db_migrations.py::_migration_0011_entitlement_quota_cycle_v5_0_0`: существующие entitlement при добавлении `quota_reset_status` получают `legacy` одним `UPDATE`, без remote reset. `schema_migrations` содержит `version/name/status/started_at/finished_at` (Unix seconds), `entitlements.created_at` также Unix seconds. `docker-compose.yml` задаёт `DB_PATH=/app/data/bot.sqlite3`. Это **source-contract**, а не доказательство временной истории конкретной production строки.

## Outcome / remaining evidence

| Check | Result / limit |
| --- | --- |
| `G05-A` | **PENDING / ROW_ORIGIN_REVIEW**: `legacy=1 legacy_active=1` по предыдущим скриптовым снимкам; migration v11 code+existing CI подтверждают *механизм*, но нет факта `schema_migrations.version=11 status=success` вместе с `entitlements.created_at < started_at` для текущей строки. |
| `G08-E` | **OPERATOR-REPORTED PASS / DETAIL PENDING**: заявлено текущее post-cycle Health после восстановленного ON; в сообщении не даны конкретные `/healthz`, DB quick_check, 3x-ui connectivity, effective Stars flag и время. Ранее `db_stars=true/effective_stars=YES revision=4` — scoped PASS по снимку 2026-10-13 01:59:28 EEST, не следует автоматически считать новый health attested. |
| `G08-D` | **OPERATOR-REPORTED PASS / DETAIL PENDING**: заявлено текущее Owner `/admin` и пилотное `/subscription`/VPN после ON; фактическое read-only evidence/expiry comparison и время в сообщении не приведены. **Никаких повторов**, если уже есть безопасные существующие результаты. Нет evidence доступности во время OFF. |

### Адресный G05-A provenance check (одна read-only операция, не регрессия)

Оператору предоставлена отдельная инструкция запустить через `docker compose exec -T bot python -` запрос к **уже существующей** `/app/data/bot.sqlite3`, SQLite URI `mode=ro` и `PRAGMA query_only=ON`; выборки только `schema_migrations` version 11 и `entitlements` with `quota_reset_status='legacy'`. Напечатать только aggregations: `SCHEMA_VERSION`, validity/version/status и UTC времена V11, `LEGACY_TOTAL`, `LEGACY_ACTIVE`, `LEGACY_CREATED_BEFORE_V11`, `LEGACY_OTHER_OR_INVALID_TIME`, `G05_A=CONSISTENT_WITH_V11/REVIEW`. **Не печатать** telegram_id, order_id, subscription URLs, backup paths, tokens, event raw payload; не выполнять migration, SQLite UPDATE, traffic reset, bot restart, deploy или 3x-ui mutation.

**Ожидаемое `CONSISTENT_WITH_V11`**: migration 11 `entitlement_quota_cycle_v5_0_0` успешно закончилась, валидный `started_at≤finished_at`, единственная активная `legacy` строка и её `created_at` строго раньше `v11.started_at`. Это сильное совместимое **scoped provenance** свидетельство, но timestamps могут быть изменены/импортированы вручную: без исторического до-v11 snapshot это не криптографическое доказательство отсутствия поздних изменений. Любое несовпадение — `REVIEW`, без автоматического исправления.

## Issue audit и стоп

- [#342](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/342) остаётся **CLOSED/completed** по самостоятельному acceptance; текущие заявленные health/UI checks не переоткрывают его и не закрывают общий G-08.
- [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433), [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466), [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487), [#510](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/510) и [#564](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/564) **OPEN/PENDING**; собственные acceptance criteria не выполнены новым заявлением.
- **Следующий шаг:** этот частичный checkpoint только через docs PR с required `test`/`title`, squash и independent `main`+Issue read-back. Затем дождаться **одного** G05-A агрегированного stdout от оператора, при необходимости запросить уже имеющиеся безличные подробности G08-D/E. После G05-A завершить пакет отдельным canonical Roadmap/Issues checkpoint. **Никакой новый пакет production smoke** до синхронизации; не повторять Stars OFF→ON, плавающие платежи, refund, quota reset или restart.
