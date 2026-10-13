# A1/A2 — соответствие исходников Docker image и effective rate-limit (2026-10-13)

## Источник, время и границы
Оператор предоставил скриншоты прежних инструкций и фактический обезличенный stdout от production Master VPS, `CHECK_UTC=2026-10-13T11:04:09Z` (14:04:09 EEST). Временная отметка — значение, выведенное скриптом; отдельной независимой аттестации VPS/источника скриншотов нет. Только **две адресные read-only проверки** A1/A2, **без** rebuild, deployment, restart, изменения .env, оплаты, refund или новых Telegram smoke. Скриншоты объяснений сами по себе не являются proof выполнения — итог основан на присланном фактическом stdout.

**Baseline:** protected `main=1866eb043ad2bb43b03bb174e4f7a6785f17fcd1` (предыдущий PR #578 merged после required `test` и `title`, независимый Roadmap read-back); опубликован immutable prerelease `v5.0.0-rc.9`, tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`. **Deployed:** на Master оператор сообщает `HOST_SHA=TAG_SHA=13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`, контейнер запущен; полная аттестация Docker build не выполнена. **Accepted:** overall v5 **NOT PASS**, public rollout **BLOCKED**. Предыдущий [A1–A4 audit](v5-a1-a4-master-node-readback-2026-10-13.md) сохраняет историческое отличие image ID.

## A1 — 7/7 release-file source parity: scoped PASS; provenance REVIEW
Оператор сообщил:
- `CURRENT_IMAGE_ID=sha256:a82ce075cb35d71bc400863474e80efd9afd7ce307daceda3c7f0a2b1bf2de01` — совпадает с последним показанным образом из предыдущего audit, **но отличается** от исторического `sha256:efb2fb9ea3dffac70a3ca344d7843cabff67ae737875b461464e0b0705483f4c`.
- `IMAGE_CREATED=2026-10-13T11:04:21.587374105+03:00` (08:04:21 UTC), `CONTAINER_CREATED=2026-10-13T08:04:54.417877892Z`, `CONTAINER_STARTED=2026-10-13T08:05:01.760541938Z`, `RESTART_COUNT=0`. Времена создания/старта согласованы между собой после конвертации UTC+03:00. Время `CHECK_UTC` 11:04:09Z позднее указанных событий. **Причина смены image ID не доказана**.
- `HOST_WORKTREE=MODIFIED`, `OLD_IMAGE_AVAILABLE=NO`: не угадывать природу локальных изменений и не считать отсутствие старого образа доказательством нарушения или автоматической пересборки.
- `version.py`, `config.py`, `client_access.py`, `client_flags.py`, `commerce.py`, `db_migrations.py`, `subscription_proxy.py` — **каждый `MATCH`**; `A1_FILES_MATCH=7/7`, `A1_SOURCE_PARITY=PASS`. Операторский проверочный скрипт сообщил байтовый паритет этих семи файлов с immutable release tag.

**Disposition:** `A1 SOURCE PARITY = operator-reported scoped PASS 7/7`; это не подтверждение всех файлов сборки, provenance base image/dependencies/build args, причин появления нового образа или неизменности локальной рабочей директории. **Full image/build attestation = REVIEW/PENDING**, no runtime FAIL confirmed. Не повторять прежние пройденные smoke и не выполнять image rebuild ради доказательства.

## A2 — фактические effective settings: scoped PASS
Из того же запущенного контейнера `config.load_settings()` оператор сообщил:
- `CLIENT_RATE_LIMIT_COUNT_SOURCE=DEFAULT`, `CLIENT_RATE_LIMIT_COUNT_EFFECTIVE=30`;
- `CLIENT_RATE_LIMIT_WINDOW_SECONDS_SOURCE=DEFAULT`, `CLIENT_RATE_LIMIT_WINDOW_SECONDS_EFFECTIVE=60`;
- `A2_POLICY_30_60_MATCH=YES`.

**Disposition:** `A2 EFFECTIVE RATE-LIMIT CONFIG = operator-reported scoped PASS` для фактически прочитанных settings 30/60 на данном контейнере и моменте. Ранее неопределённое `UNSET_OR_INVALID` теперь разрешено для **effective** значений; отсутствие прогонки burst/лимитера **не** превращает этот read-only proof в полноценный runtime abuse/load/soak acceptance. Нет основания менять .env или повторять ранее пройденные limiter CI.

## Issues, риски и checkpoint
- [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) **OPEN**: A1/A2 не подтверждают offline→return Node, revoke/quota propagation или no-blind-replay; A3/A4 предыдущего пакета имеют лишь scoped PASS.
- [#577](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/577) **OPEN**: scheduled governance audit остаётся FAIL до отдельного fix и повторного успешного workflow. Предыдущий Roadmap [PR #578](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/578) MERGED, post-merge `Python checks` [38387881994](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38387881994) PASS; это **не** успешный scheduled governance audit.
- #433/#466/#510/#564 продолжают быть OPEN; #317/#342/#422 CLOSED в ранее доказанных scope. G-01/G-02/G-03/G-06/G-07 короткие smoke CLOSED/полный acceptance PARTIAL, G-04/G-05/G-08 PARTIAL, G-09/G-10/G-11 PENDING. Не повторять закрытые/waived сценарии.
- **Следующий шаг:** отдельный docs-only Roadmap PR с required `test`/`title`, squash merge, независимый read-back `main`/Roadmap/Issues, только потом следующий короткий production-пакет. До checkpoint **ROADMAP SYNC PENDING**. Новый standalone Issue по A1 **не создаётся**: на основании показанного расхождения не подтверждён runtime defect; residual provenance фиксируется в G-01.
