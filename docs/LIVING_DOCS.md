# Living Docs Contract

Этот документ задаёт правила актуальности часто изменяемой документации. Цель — не заставлять менять Markdown в каждом PR, а fail-closed ловить расхождения между текущим кодом, repository state и каноническими current-state документами.

Machine-readable contract: `docs/live-docs.json`.

## Living и historical документы

Living documents описывают текущее состояние проекта и должны оставаться актуальными:

- `README.md` — current architecture и карта документации;
- `CHANGELOG.md` — release ledger и актуальный верхний release scope;
- `SECURITY.md` — текущий security reporting contract;
- `docs/ROADMAP.md` — фактический product/acceptance state;
- `docs/RELEASES.md` — текущий release/tag/deployment contract;
- `docs/GIT_WORKFLOW.md` — текущий Git/PR/issue workflow;
- `docs/ADMIN_SETUP.md` — текущая установка и operator setup;
- `docs/V5_PRODUCTION_ACCEPTANCE.md` — контролируемый v5 canary и обязательный production acceptance;
- operational runbooks и schema/API/UI contracts, перечисленные в `docs/live-docs.json`.

`docs/audits/**` — historical evidence. Старый факт внутри audit artifact не переписывается только потому, что состояние позже изменилось. Вместо этого добавляется closure/revalidation evidence и актуальный итоговый status.

## Diff-trigger rules

`scripts/check-living-docs.py` проверяет PR diff относительно base SHA и применяет rules из `docs/live-docs.json`.

Режимы:

- `require_all` — при trigger-change каждый указанный документ обязан измениться в том же PR;
- `review` — должен измениться хотя бы один релевантный living doc или PR body должен содержать точный waiver из contract.

Waiver означает, что документ фактически просмотрен и изменение не требуется. Он не заменяет обновление документа, если contract/setup/current state реально изменился.

Примеры waiver:

~~~text
Admin Setup: изменений не требуется
Living Docs: release-process — изменений не требуется
Living Docs: database-schema — изменений не требуется
~~~

## Semantic invariants

Diff-trigger не заменяет проверку содержания. `tests/test_living_docs.py` всегда проверяет current-state invariants:

- `version.py` согласован с README/Admin Setup/CHANGELOG;
- текущая SQLite schema version отражена в `docs/SQLITE_MIGRATIONS.md`;
- public security reporting contract присутствует в `SECURITY.md`;
- Git/release docs отражают enforced branch/tag rulesets;
- roadmap показывает текущий активный product track;
- machine-readable contract не ссылается на отсутствующие документы.

Новые постоянные current-state checks добавляются в `test_living_docs.py`, а не накапливаются в version-specific test files.

## Repository state вне Git

Часть критического состояния меняется через GitHub Settings и не видна обычному git diff.

Workflow **Repository state audit** запускается вручную и автоматически раз в неделю. Он читает ожидания из `docs/live-docs.json` и проверяет:

- repository остаётся public;
- `Protect main release path` active и сохраняет PR/squash/required-check/no-delete/no-non-fast-forward/no-bypass contract;
- `Protect release tags` active для `refs/tags/v*`, запрещает update/delete/non-fast-forward и не запрещает creation новых release tags;
- latest GitHub Release tag соответствует `APP_VERSION` на tagged commit;
- latest release tag commit остаётся в истории default branch.

Scheduled audit read-only и не меняет repository settings.

## Roadmap и acceptance

Не каждый product-state transition можно надёжно вывести из списка изменённых файлов. Поэтому начало нового milestone, публикация release, production acceptance, closure/reopen finding/issue и изменение release/public-readiness state должны сопровождаться проверкой `docs/ROADMAP.md` и соответствующего audit/acceptance artifact.

Roadmap меняется только по факту, а не авансом.

## Definition of Done

Перед merge PR:

1. Living Docs check не имеет violations;
2. semantic living-doc tests зелёные;
3. waiver используется только после фактического review;
4. current-state документы не содержат заведомо устаревших pending/private/version/status утверждений;
5. historical evidence сохраняет audit trail.
