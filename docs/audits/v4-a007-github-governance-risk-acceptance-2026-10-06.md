# A-007 / #240 — GitHub governance risk acceptance — 2026-10-06

Статус: **ACCEPTED RISK / Closed by owner decision**.

## Finding

GitHub API для текущего repository state сообщает:

- `main.protected=false`;
- required status checks enforcement = `off`.

Следовательно, repository-side workflows сами по себе не могут запретить Owner/credential с достаточными правами выполнить direct push в `main`, force/update/delete ref либо иным способом обойти документированный PR/CI release path.

Severity исходного finding: **High**.

## Platform / plan constraint

Для текущей конфигурации private repository владелец не использует платный GitHub plan только ради GitHub-side branch/tag protection/rulesets.

Это не трактуется как техническое устранение finding. GitHub-side enforcement отсутствует, residual risk сохраняется.

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

До фактического включения GitHub-side enforcement остаётся возможность обхода repository policy субъектом с достаточными GitHub write/admin правами.

Operational contract поэтому остаётся строгим:

- обычные изменения — только через PR;
- CI не обходится вручную;
- release tags/releases создаются штатным workflow;
- опубликованные refs не перемещаются и не переиспользуются;
- аномалии GitHub/Actions не являются основанием для manual bypass.

## Closure decision

A-007/#240 закрывается как **accepted risk by explicit owner decision**, а не как remediated control.

Это explicit exception к исходному audit closure criterion. Он снимает A-007 с release blockers, сохраняя residual risk и рекомендуемое GitHub-side hardening в документации.
