# Living Docs Contract

Этот документ задаёт правила актуальности часто изменяемой документации. Цель — не заставлять менять Markdown в каждом PR, а fail-closed ловить расхождения между текущим кодом, repository state и каноническими current-state документами.

Machine-readable contract: `docs/live-docs.json`.

**CI governance #762:** `docs/roadmap/issue-closure-decisions.json` хранит датированное scoped решение `completed/keep_open`, `scripts/check-roadmap-github.py` fail-closed сравнивает его с GitHub и активным реестром Roadmap. Сами checks не закрывают Issues и не подтверждают VPS acceptance; новый closure checkpoint требует отдельно разрешённого merge. 

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

`docs/roadmap/HISTORY_INDEX.md` и `docs/audits/roadmap-history/**` — тематический исторический архив исходных 5803 строк Roadmap с точной проверкой Git blob. Это не второй living-state реестр; текущие gate и OPEN Issue statuses поддерживаются только в `docs/ROADMAP.md`. После закрытия Issue его подробный outcome остаётся в GitHub Issue/PR/CI и датированном audit; completed entries не накапливаются в living Roadmap, кроме одного краткого опционального агрегата актуального этапа. Новые подробные checks пишутся в датированные `docs/audits/**`; `scripts/check-roadmap-structure.py` проверяет архив/limiting и запускается через semantic living-doc tests.

`docs/audits/**` — historical evidence. Старый факт внутри audit artifact не переписывается только потому, что состояние позже изменилось. Вместо этого добавляется closure/revalidation evidence и актуальный итоговый status.

## Маршрутизация и контроль новых audits (#597)

Таблица типов изменений и destinations — `docs/GIT_WORKFLOW.md#маршрутизация-изменений-и-evidence-597`. Текущий Roadmap остаётся единственным статусным реестром; его G-01…G-11 — четырёхколоночные gates с одним статусом, waivers учитываются отдельно, а очередь содержит только незавершённые активные действия. Завершённые D1/scoped PASS сохраняются в dated audits, не как отдельные очередные задачи. Проверка контрактов в scripts/check-documentation-semantics.py обязана отклонять статусный дрейф.  `docs/roadmap/concepts/**` — редактируемые проектные документы, а исходные концептуальные snapshots вынесены в immutable `docs/audits/roadmap-history/source-*.md`. `docs/roadmap/archive-manifest.json` воспроизводит исходный Git blob и запрещает изменения исторических свидетельств. Новые audits никогда не меняют старые FAIL.

Новые **и изменяемые структурированные** `docs/audits/*.md` (кроме шаблона и неизменного `roadmap-history/**`) обязаны соответствовать `docs/audits/AUDIT_TEMPLATE.md`: machine-checkable marker, timestamp с TZ, scope, target tag/SHA/N/A с причиной, status, evidence, limitations, Issue/next и четыре отдельных факта merged/published/deployed/accepted. Строгая template-проверка применяется к добавленным и изменённым файлам; legacy audits не переписываются ретроспективно — исправления оформляют новым датированным addendum. Удаление датированных audits запрещено governance CI, включая legacy evidence. `scripts/check-documentation-semantics.py` проверяет текущее содержание Roadmap и локальные ссылки; `scripts/check-roadmap-github.py` сверяет точный набор OPEN Issues в активном реестре, состояния упомянутых Issues и последний Published Release через GitHub API. Эта read-only проверка выполняется в обязательном PR CI `test` и в отдельном плановом workflow: закрытый Issue в активном реестре или устаревший Published блокирует PR. GitHub API outage означает `UNKNOWN/PENDING`, а не `PASS`; проверка **не** подтверждает VPS deployment/acceptance.

## Завершающий Roadmap governance contract (#605, #636)

`scripts/check-roadmap-governance.py` запускается в обязательном `Python checks` для каждого PR и push в main: проверяет семь полей структурированного Issue-реестра, включая обязательный предварительный объём `XS/S/M/L/XL`, допустимые переходы концепций, самостоятельные поля Published/Deployed/Accepted и изменённые audits (в том числе уже созданные ранее). `scripts/check-roadmap-github.py` дополнительно получает с pagination все OPEN GitHub Issues и сравнивает exact set с активным реестром. Несовпадение — FAIL, недоступность GitHub — UNKNOWN/PENDING. Не считать этот read-only check production attestation, policy/acceptance PASS или подтверждением подлинности evidence.

Concept lifecycle — `docs/roadmap/concept-registry.json`; оригинальные исходные файлы остаются в `docs/audits/roadmap-history/**`. Исторические archives не править ради обновления схемы. Новый результат оформлять отдельным датированным audit/addendum. При merge/version/release/deployment обновлять факты и evidence независимо, с Issue-closure checkpoint до следующего пакета.

## Карта чтения контекста и языковой review

Каждый агент перед задачей читает `AGENTS.md` и актуальный `main`, затем `docs/GIT_WORKFLOW.md`, `docs/LIVING_DOCS.md`, верх `docs/ROADMAP.md` и `CHANGELOG.md`. До изменения Telegram UI читается `docs/UI_STYLE.md`, до API — `docs/3XUI_OPENAPI_CONTRACT.md`, до SQLite — `docs/SQLITE_MIGRATIONS.md`, до setup/deploy — `docs/ADMIN_SETUP.md` и профильные runbooks, до релиза — `docs/RELEASES.md`. Для новых областей и diff-триггеров первичен `docs/live-docs.json`.

Язык новых авторских пояснений — русский. Технические идентификаторы, исходные тексты внешних систем, code fences и исторические audits не переводятся автоматически. CI проверяет очевидную англоязычную прозу в changed Markdown и PR title/body; эта проверка не заменяет семантический review и не обещает полноценную языковую классификацию.

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

**Текущая release-state проекция:** `docs/ROADMAP.md` — единственный текущий status source. `README.md` повторяет только одну машинно проверяемую строку Published/Deployed/Accepted; `docs/ADMIN_SETUP.md` ссылается на неё и не дублирует действующий SHA или предыдущий baseline. Недатированные секции Roadmap «Текущий этап» и «Текущие targeted blockers» обязаны быть согласованы с текущим checkpoint; прежние версии/Issue состояния оставлять только внутри однозначно датированных исторических свидетельств. CI проверяет формат и явные stale-current фразы; исторические audits не переписываются. Эта сверка не является VPS attestation.


Diff-trigger не заменяет проверку содержания. `tests/test_living_docs.py` всегда проверяет current-state invariants:

- `version.py` согласован с README/Admin Setup/CHANGELOG;
- текущая единственная строка `**Published:**` в README и Roadmap имеет одинаковые **значения** `Deployed` (version, 40-char SHA, provenance) и `Accepted` (scoped outcome и PENDING), без чтения исторических checkpoints; отсутствие поля/расхождение — FAIL в обязательном `test`. Roadmap — канонический источник, README — краткая проекция; CI не удостоверяет реальное VPS deployment, даже при совпадении operator-reported текста;
- текущая SQLite schema version отражена в `docs/SQLITE_MIGRATIONS.md`;
- public security reporting contract присутствует в `SECURITY.md`;
- Git/release docs отражают enforced branch/tag rulesets;
- roadmap показывает текущий активный product track;
- machine-readable contract не ссылается на отсутствующие документы;
- число endpoints текущего `contracts/3xui/contract.json` совпадает с `docs/3XUI_OPENAPI_CONTRACT.md`.

Проверка current-release проекции включает также верхний актуальный статус в `docs/CLIENT_SETUP.md`, отсутствие ложных «ещё не Published» в `docs/UI_STYLE.md`, `docs/SQLITE_MIGRATIONS.md`, README и release-prep заголовках CHANGELOG. Датированные исторические checkpoints сохраняются; CI не делает вывода о production acceptance.

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

**Post-merge Issues:** required PR checklist требует явный план `completed`/`keep_open` для связанного Issue, но GitHub CI не закрывает Issues автоматически. Выполненный docs-only scope закрывается после merged/read-back и scoped CI, затем строка удаляется из текущего Roadmap в отдельном docs-only PR; реестр решений сверяется с GitHub. `test`/`title` и сверка OPEN IDs без явного closure решения не являются доказательством полной синхронизации жизненного цикла.

## Definition of Done

Перед merge PR:

1. Living Docs check не имеет violations;
2. semantic living-doc tests зелёные;
3. waiver используется только после фактического review;
4. current-state документы не содержат заведомо устаревших pending/private/version/status утверждений;
5. historical evidence сохраняет audit trail.
