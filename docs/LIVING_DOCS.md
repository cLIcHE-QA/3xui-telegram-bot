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
- `docs/CLIENT_SETUP.md` — настройки и безопасный rollback пилотного Client Portal; public launch до полного acceptance запрещён;
- operational runbooks и schema/API/UI contracts, перечисленные в `docs/live-docs.json`.

`docs/roadmap/HISTORY_INDEX.md` и `docs/audits/roadmap-history/**` — тематический исторический архив исходных 5803 строк Roadmap с точной проверкой Git blob. Это не второй living-state реестр; текущие gate и Issue statuses поддерживаются только в `docs/ROADMAP.md`. Новые подробные checks пишутся в датированные `docs/audits/**`; `scripts/check-roadmap-structure.py` проверяет архив/limiting и запускается через semantic living-doc tests.

`docs/audits/**` — historical evidence. Старый факт внутри audit artifact не переписывается только потому, что состояние позже изменилось. Вместо этого добавляется closure/revalidation evidence и актуальный итоговый status.

## Маршрутизация и контроль новых audits (#597)

Таблица типов изменений и destinations — `docs/GIT_WORKFLOW.md#маршрутизация-изменений-и-evidence-597`. Текущий Roadmap остаётся единственным статусным реестром; `docs/roadmap/concepts/**` — редактируемые проектные документы, а исходные концептуальные snapshots вынесены в immutable `docs/audits/roadmap-history/source-*.md`. `docs/roadmap/archive-manifest.json` воспроизводит исходный Git blob и запрещает изменения исторических свидетельств. Новые audits никогда не меняют старые FAIL.

Новые **и изменяемые структурированные** `docs/audits/*.md` (кроме шаблона и неизменного `roadmap-history/**`) обязаны соответствовать `docs/audits/AUDIT_TEMPLATE.md`: machine-checkable marker, timestamp с TZ, scope, target tag/SHA/N/A с причиной, status, evidence, limitations, Issue/next и четыре отдельных факта merged/published/deployed/accepted. Строгая template-проверка применяется к добавленным и изменённым файлам; legacy audits не переписываются ретроспективно — исправления оформляют новым датированным addendum. Удаление датированных audits запрещено governance CI, включая legacy evidence. `scripts/check-documentation-semantics.py` проверяет текущее содержание Roadmap и локальные ссылки; `scripts/check-roadmap-github.py` отдельно сверяет Issues и последний Published Release по GitHub API. API outage означает UNKNOWN/PENDING, а не PASS; GitHub read-only проверка **не** подтверждает VPS deployment/acceptance.

## Завершающий Roadmap governance contract (#605)

`scripts/check-roadmap-governance.py` запускается в обязательном `Python checks` для каждого PR и push в main: проверяет шесть полей структурированного Issue-реестра, допустимые переходы концепций, самостоятельные поля Published/Deployed/Accepted и изменённые audits (в том числе уже созданные ранее). `scripts/check-roadmap-github.py` дополнительно получает с pagination все OPEN GitHub Issues и сравнивает exact set с активным реестром. Несовпадение — FAIL, недоступность GitHub — UNKNOWN/PENDING. Не считать этот read-only check production attestation, policy/acceptance PASS или подтверждением подлинности evidence.

Concept lifecycle — `docs/roadmap/concept-registry.json`; оригинальные исходные файлы остаются в `docs/audits/roadmap-history/**`. Исторические archives не править ради обновления схемы. Новый результат оформлять отдельным датированным audit/addendum. При merge/version/release/deployment обновлять факты и evidence независимо, с Issue-closure checkpoint до следующего пакета.

## Diff-trigger rules

`scripts/check-living-docs.py` проверяет PR diff относительно base SHA и применяет rules из `docs/live-docs.json`.

Режимы:

- `require_all` — при trigger-change каждый указанный документ обязан измениться в том же PR;
- `review` — должен измениться хотя бы один релевантный living doc или PR body должен содержать точный waiver из contract.

Waiver означает, что документ фактически просмотрен и изменение не требуется. Он не заменяет обновление документа, если contract/setup/current state реально изменился.

Для API 3x-ui действует отдельная граница: изменение `contracts/3xui/contract.json` или vendored `contracts/3xui/**/openapi.json` требует синхронного обновления `docs/3XUI_OPENAPI_CONTRACT.md` (`require_all`, waiver запрещён). Изменения `xui.py` / `version_api.py` требуют фактической проверки влияния на документ или точного waiver `Living Docs: 3xui-client-api — изменений не требуется`. Постоянный semantic invariant сверяет количество endpoints в manifest с документом, даже если PR diff не затрагивает manifest.

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
- machine-readable contract не ссылается на отсутствующие документы;
- число endpoints текущего `contracts/3xui/contract.json` совпадает с `docs/3XUI_OPENAPI_CONTRACT.md`.

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
