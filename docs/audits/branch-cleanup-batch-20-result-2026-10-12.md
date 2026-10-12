# Issue #510 — историческая очистка, пакет 20/20 (completed)

**Фактическая дата:** 2026-10-12 10:39:17 Europe/Helsinki (EEST, UTC+03:00). **Источник:** GitHub Actions [run 38218828761](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38218828761) job `retire-once`, независимые GitHub REST GET `/branches/<name>` для 20 refs (20/20 HTTP 404). Scope **GitHub-only**, не production smoke, не релиз, не изменение самого кода бота.

## Baseline and gates

- Исходный protected `main` до PR: `17ca2a1812941b72d57e2883ea45cf283e4b4099`. Предыдущий пакет 3/3 полностью задокументирован через [PR #522](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/522) и #510 Issue comment, без незавершённого checkpoint.
- Source record для *каждой* ветки: [immutable manifest](branch-cleanup-batch-20-2026-10-12.json), `issue=510`, `baseline_main_sha`, 20 exact `name → full SHA`. Исторический [no-PR ancestry audit](branch-no-pr-ancestry-2026-10-12.md) дал начальный выбор, а **fresh GitHub REST** 2026-10-12 ~10:31 EEST повторно проверил 20/20: existing branch, `protected=false`, exact SHA unchanged, `compare(main...sha): behind / ahead_by=0`, GitHub `pulls?head/base` arrays empty. Ветви с diverged/unique commits и closed-unmerged PR исключены.
- [PR #523](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/523) exact head `90f4f991ac6c3922eaad9526305df7f669a4891c`: separate read-only `preflight` **PASS 20/20** [38218373140](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38218373140), required `test` **PASS** [38218373013](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38218373013), latest required `title` **PASS** [38218608647](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38218608647), supply-chain `audit` **PASS** [38218372964](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38218372964). Squash **MERGED** protected main `d2f7659bd8dd0e654e1c14ac384945c43ee45704`, post-merge `Python checks` **PASS** [38218663122](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38218663122), supply-chain audit PASS [38218663130](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38218663130).
- Лишь **после** main CI GitHub Actions [38218828761](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38218828761) `workflow_run` на exact SHA повторно проверил immutable main identity, first-parent expected baseline, все SHA/ancestry, no current/prior PR head/base, отсутствие literal operational refs в tracked source (кроме historical audit/Roadmap и самого инструмента). Все 20 refs затем удалены `git push --force-with-lease=refs/heads/<name>:<SHA> origin :refs/heads/<name>`, сразу подтверждены API 404 и `git ls-remote` absent, затем **дополнительно** read-back GitHub connector по каждому ref дал HTTP 404. Job completed/success, ошибки/unknown/partial отсутствуют.

## Результаты — индивидуальный GitHub read-back

| № | Удалённая branch | Точный pre-delete tip SHA | GitHub GET branch |
| ---: | --- | --- | --- |
| 1 | `chore/pre-v5-repo-hygiene` | `6f61f092d67376093335094cd85980fe7f0342e9` | **404 PASS** |
| 2 | `docs/a007-fully-remediated` | `3514200d536562e8ee237a418b46c585ef6caf79` | **404 PASS** |
| 3 | `docs/qa352-telegram-4of4-confirmed-20261011` | `aee2df99e878ac705bb953818fe40b3040e9641a` | **404 PASS** |
| 4 | `docs/qa352-tls-restored-20261011` | `779fcc03009dfdadc6c77a11ef20616569b6f7c4` | **404 PASS** |
| 5 | `docs/reschedule-v5-expiry-smoke-oct10` | `0b44ac1c7dd4b53f69092ee8c5a38c7c0c4e504e` | **404 PASS** |
| 6 | `docs/v4-audit-closure` | `e4633406b0cfffe5f8805e816a21728274d650e0` | **404 PASS** |
| 7 | `docs/v4-audit-completion-gates` | `e4633406b0cfffe5f8805e816a21728274d650e0` | **404 PASS** |
| 8 | `docs/v4-audit-finalization` | `e4633406b0cfffe5f8805e816a21728274d650e0` | **404 PASS** |
| 9 | `docs/v4-audit-findings` | `e4633406b0cfffe5f8805e816a21728274d650e0` | **404 PASS** |
| 10 | `docs/v4-audit-follow-up` | `e4633406b0cfffe5f8805e816a21728274d650e0` | **404 PASS** |
| 11 | `docs/v4-audit-followups` | `e4633406b0cfffe5f8805e816a21728274d650e0` | **404 PASS** |
| 12 | `docs/v4-safe-bot-self-update` | `bccb74cb5b9bf6630775defa620dd1e1ba2ca4e2` | **404 PASS** |
| 13 | `docs/v5-a002-two-offline-regressions-20261011` | `d07ee9b762cddce68cd785a120592dd442d9ac93` | **404 PASS** |
| 14 | `docs/v5-commerce-offline-suite-20261010` | `04c951caa5f1b5e7cdd5247b07eeebc536b8af98` | **404 PASS** |
| 15 | `docs/v5-scheduled-backup-deepcheck-20261010` | `b4e7938b7d7c913661b29917ff88492c26d228f3` | **404 PASS** |
| 16 | `docs/v5-stars-refund-unknown-no-retry-rc7-20261011` | `d07ee9b762cddce68cd785a120592dd442d9ac93` | **404 PASS** |
| 17 | `feature/v4.11.1-node-onboarding` | `c3bccf7edfcf0db2ea7513f90483b72111b0b7b5` | **404 PASS** |
| 18 | `fix/roadmap-gate-v4191` | `b8df3aaa828360fca0385b47cd054f971b2dc829` | **404 PASS** |
| 19 | `fix/v4.20.2-admin-navigation` | `7f0f20e27b7394ea91780380b8fecbdb24750f1a` | **404 PASS** |
| 20 | `security/private-admin-chat` | `d4178af779e344f757ee4bed27cc43c675c32794` | **404 PASS** |

**DELETE scope PASS 20/20; cumulative across pilots 23/23 verified.** Привилегированный workflow и одноразовый Python script удаляются через отдельный Roadmap checkpoint PR; их фактическое отсутствие в `main` необходимо проверить **после merge**, не считать авансом завершённым.

## Closure audit / residual risks

- **#510 OPEN / PENDING в целом:** не удалены и не признаны safe сотни оставшихся refs. По каждому следующему merged-PR candidate нужен отдельный proof отсутствия unmerged work / patch/blob equivalence, PR/base relationships, dependency scan, exact SHA lease и independent 404. Не удалять protected `main`, immutable `v*` tags, diverged и closed-unmerged refs. External/fork/operator/dynamic consumers нельзя исчерпывающе исключить одним текущим source scan — residual risk.
- Дальнейший пакет **заблокирован до** Roadmap PR с required `test`/`title`, squash merge, independent main read-back, delete-tool absence, Issue closure audit и повторной сверки Roadmap↔Issues.
- Published по-прежнему immutable prerelease `v5.0.0-rc.9` tag `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; deployed только operator-reported rc.9 (independent VPS read-back PENDING), overall v5 acceptance NOT PASS. G-01…G-11 без promotion, W-01/W-02 waived/NOT PASS. **No deployment/restart/refund/Stars purchase/production smoke/release tag/setting mutation.**
