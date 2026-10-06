# A-007 / #240 — GitHub governance risk acceptance — 2026-10-06

Статус: **CLOSED / FULLY REMEDIATED after post-public GitHub enforcement**.

## Finding

GitHub API для текущего repository state сообщает:

- `main.protected=false`;
- required status checks enforcement = `off`.

Следовательно, repository-side workflows сами по себе не могут запретить Owner/credential с достаточными правами выполнить direct push в `main`, force/update/delete ref либо иным способом обойти документированный PR/CI release path.

Severity исходного finding: **High**.

## Platform / plan constraint at original closure

На момент исходного closure repository был private, и владелец не использовал платный GitHub plan только ради GitHub-side branch/tag protection/rulesets.

Это решение зафиксировало допустимый residual risk для финального v4 audit на том состоянии платформы. После перехода repository в public GitHub-side enforcement был перепроверен отдельно.

## Post-public revalidation — branch side remediated

После перевода repository в public GitHub API повторно проверен на текущем `main`.

Current evidence:

- `main` reports `protected=true`;
- active repository ruleset: **Protect main release path**, ID `24575428`;
- target: default branch;
- enforcement: `active`;
- bypass actors: none; `current_user_can_bypass=never`;
- Pull Request обязателен;
- allowed merge method: только `squash`;
- required status checks: `test` и `title`;
- strict required-status-check policy: enabled;
- deletion запрещён;
- non-fast-forward/force-update запрещён;
- linear history обязателен.

Это технически устраняет исходный branch-side риск прямого push/force/delete в `main` и делает documented PR/CI/squash path GitHub-enforced.

Проверка rulesets для target `tag` на момент revalidation вернула пустой набор. Следовательно, GitHub-side immutability для опубликованных `v*` tags всё ещё не доказана platform enforcement-ом.

Промежуточный residual risk release tag refs закрыт active tag ruleset `Protect release tags`. Текущий residual risk A-007: **none identified within the original finding scope**.

## Post-public tag enforcement — fully remediated

2026-10-07 создан и проверен active repository tag ruleset **Protect release tags**:

- ruleset ID: `24615100`;
- target: `tag`;
- include condition: `refs/tags/v*`;
- enforcement: `active`;
- rules: `deletion`, `non_fast_forward`, `update`;
- bypass actors: none;
- `current_user_can_bypass=never`;
- tag creation не запрещена.

Existing release tag `v4.26.8` после включения ruleset остался на SHA `e096bf436425ea037399e290a5a54f54c729b352`.

Вместе с branch ruleset **Protect main release path** (ID `24575428`) это закрывает исходный A-007 closure criterion: default branch и опубликованные release refs защищены GitHub-side enforcement.

## Compensating controls

Repository-side defense-in-depth уже реализован:

- изменения ведутся через Pull Request и canonical `Squash and merge`;
- PR conventions и Python checks запускаются автоматически;
- release publication отделена от обычного CI;
- release workflow выполняет read-only provenance validation перед job с `contents: write`;
- release commit должен происходить из canonical release-prep PR;
- version/tag/release consistency проверяется workflow;
- third-party Actions pinned to reviewed commit SHA;
- supply-chain audit и history/Actions secret audits имеют сохранённое evidence;
- release/deployment procedure запрещает ручной обход CI/tag/release path как нормальный operational flow.

Эти controls уменьшают вероятность случайного обхода, но не эквивалентны GitHub-side branch/tag protection.

## Owner disposition

Владелец проекта явно принимает residual risk A-007 при текущем plan/configuration.

Решение:

- не переходить на платный GitHub plan только ради закрытия A-007;
- не считать отсутствие GitHub-side protection release/publication blocker для финального v4 audit;
- сохранить finding и его severity в audit history как **Accepted risk**, а не помечать его как исправленный;
- при появлении доступного GitHub-side enforcement (включая изменение repository visibility/plan/features) включить protection/rulesets как hardening без необходимости переоткрывать уже завершённый v4 audit, если не появляется новый независимый риск.

## Residual risk

Для `main` и опубликованных `v*` tag refs GitHub-side enforcement теперь включён. Residual risk в рамках исходного A-007 closure criterion не остаётся.

Operational contract поэтому остаётся строгим:

- обычные изменения — только через PR;
- CI не обходится вручную;
- release tags/releases создаются штатным workflow;
- опубликованные refs не перемещаются и не переиспользуются;
- аномалии GitHub/Actions не являются основанием для manual bypass.

## Closure decision

A-007/#240 теперь **fully remediated**: branch-side и tag-side controls обеспечиваются enforced GitHub rulesets без bypass. Исходный owner-accepted risk сохранён в документе как исторический audit disposition, но больше не является текущим residual risk.
