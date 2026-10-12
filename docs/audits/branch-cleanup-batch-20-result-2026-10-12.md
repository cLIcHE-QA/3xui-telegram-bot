# Issue #510 — второй пакет удаления исторических веток, 20/20 PASS

**Дата:** 2026-10-12, 10:39 Europe/Helsinki (EEST, UTC+03:00). **Scope:** только 20 GitHub branches; production/VPS/Telegram, release tags, `main` history, production payment и deployment не затронуты. **Evidence:** GitHub REST / exact branch SHA / GitHub Actions logs, независимый read-back после run.

## Исходное состояние и preflight

- Source of truth: [immutable batch manifest](branch-cleanup-batch-20-2026-10-12.json); exact 20 branch names and 40-character tip SHA, 14 distinct commit SHAs; historical [no-PR ancestry audit](branch-no-pr-ancestry-2026-10-12.md).
- Base protected `main`: `17ca2a1812941b72d57e2883ea45cf283e4b4099`; previous pilot [#521](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/521) DELETE PASS 3/3 already synchronized through required-CI [PR #522](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/522), squash `17ca2a1812941b72d57e2883ea45cf283e4b4099`, independent Roadmap/Issue audit.
- Fresh GitHub REST preflight **20/20**: branch existed, current full SHA matched manifest, protected=false, compare with exact main gave `ahead_by=0` (branch commit reachable), PR head/base lists for all states empty. Bounded tracked operational source scan found no literal branch-name dependency outside archived audit/Roadmap/manifests. **Not proven:** unknown external/local/fork/dynamic consumers.
- [PR #523](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/523), exact head `90f4f991ac6c3922eaad9526305df7f669a4891c`: separate read-only `preflight` **PASS 20/20** [run 38218373140](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38218373140), required `test` **PASS** [38218373013](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38218373013), required `title` **PASS** [38218608647](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38218608647), supply-chain `audit` **PASS** [38218372964](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38218372964).
- PR squash **MERGED** to `main` `d2f7659bd8dd0e654e1c14ac384945c43ee45704`. Post-merge `Python checks` **PASS** [38218663122](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38218663122); supply-chain audit **PASS** [38218663130](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38218663130).

## Реальное удаление и postcondition

[One-shot GitHub Actions run 38218828761](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38218828761) **completed/success**, выполнялся только после successful `Python checks` on pushed `main`. Guard сверил event, exact main commit и first-parent baseline. Скрипт выполнил preflight всех 20 до мутаций, снова проверял tip SHA, ancestry/protection/PR filters перед каждым `git push --force-with-lease=refs/heads/<name>:<exact-sha> origin :refs/heads/<name>`; после каждого получил GitHub GET branch 404 и отсутствие `git ls-remote`.

В журнале run: `PREFLIGHT PASS` **20/20**, `DELETED / VERIFIED` **20/20**, итог `BATCH20 DELETION: 20/20 confirmed`. Затем **независимое новое чтение** GitHub REST после завершения run вернуло HTTP **404 для всех 20/20** (проверено двумя группами по 10). Ни один ref не был изменён без совпавшего SHA lease. `main` после cleanup остался `d2f7659bd8dd0e654e1c14ac384945c43ee45704`.

| № | Удалённая branch | Ожидаемый SHA до удаления | Независимый post-delete результат |
| ---: | --- | --- | --- |
| 1 | `chore/pre-v5-repo-hygiene` | `6f61f092d67376093335094cd85980fe7f0342e9` | 404 — DELETE PASS |
| 2 | `docs/a007-fully-remediated` | `3514200d536562e8ee237a418b46c585ef6caf79` | 404 — DELETE PASS |
| 3 | `docs/qa352-telegram-4of4-confirmed-20261011` | `aee2df99e878ac705bb953818fe40b3040e9641a` | 404 — DELETE PASS |
| 4 | `docs/qa352-tls-restored-20261011` | `779fcc03009dfdadc6c77a11ef20616569b6f7c4` | 404 — DELETE PASS |
| 5 | `docs/reschedule-v5-expiry-smoke-oct10` | `0b44ac1c7dd4b53f69092ee8c5a38c7c0c4e504e` | 404 — DELETE PASS |
| 6 | `docs/v4-audit-closure` | `e4633406b0cfffe5f8805e816a21728274d650e0` | 404 — DELETE PASS |
| 7 | `docs/v4-audit-completion-gates` | `e4633406b0cfffe5f8805e816a21728274d650e0` | 404 — DELETE PASS |
| 8 | `docs/v4-audit-finalization` | `e4633406b0cfffe5f8805e816a21728274d650e0` | 404 — DELETE PASS |
| 9 | `docs/v4-audit-findings` | `e4633406b0cfffe5f8805e816a21728274d650e0` | 404 — DELETE PASS |
| 10 | `docs/v4-audit-follow-up` | `e4633406b0cfffe5f8805e816a21728274d650e0` | 404 — DELETE PASS |
| 11 | `docs/v4-audit-followups` | `e4633406b0cfffe5f8805e816a21728274d650e0` | 404 — DELETE PASS |
| 12 | `docs/v4-safe-bot-self-update` | `bccb74cb5b9bf6630775defa620dd1e1ba2ca4e2` | 404 — DELETE PASS |
| 13 | `docs/v5-a002-two-offline-regressions-20261011` | `d07ee9b762cddce68cd785a120592dd442d9ac93` | 404 — DELETE PASS |
| 14 | `docs/v5-commerce-offline-suite-20261010` | `04c951caa5f1b5e7cdd5247b07eeebc536b8af98` | 404 — DELETE PASS |
| 15 | `docs/v5-scheduled-backup-deepcheck-20261010` | `b4e7938b7d7c913661b29917ff88492c26d228f3` | 404 — DELETE PASS |
| 16 | `docs/v5-stars-refund-unknown-no-retry-rc7-20261011` | `d07ee9b762cddce68cd785a120592dd442d9ac93` | 404 — DELETE PASS |
| 17 | `feature/v4.11.1-node-onboarding` | `c3bccf7edfcf0db2ea7513f90483b72111b0b7b5` | 404 — DELETE PASS |
| 18 | `fix/roadmap-gate-v4191` | `b8df3aaa828360fca0385b47cd054f971b2dc829` | 404 — DELETE PASS |
| 19 | `fix/v4.20.2-admin-navigation` | `7f0f20e27b7394ea91780380b8fecbdb24750f1a` | 404 — DELETE PASS |
| 20 | `security/private-admin-chat` | `d4178af779e344f757ee4bed27cc43c675c32794` | 404 — DELETE PASS |

**Disposition:** **DELETE PASS 20/20**; суммарно с первым подтверждённым пилотом **23/23** исторические ветки удалены. Это **не** означает удаление всех старых веток или закрытие Issue #510.

## Остаточные риски и следующий checkpoint

- Исторические no-PR branches с отдельными unique commits, divergences и закрытыми без merge PR остались REVIEW/RETAIN; hundreds merged-PR-related source refs требуют поштучной patch/PR/dependency safety verification, а не blind bulk deletion.
- External/branch-name/dynamic refs за пределами tracked GitHub files не исключены; при следующем batch потребуется новый manifest, exact SHA, GitHub dependency review, successful required CI, read-back каждого удаления.
- В **этом отдельном** Roadmap sync PR следует удалить временный privileged workflow `.github/workflows/branch-cleanup-batch-510.yml` и one-shot `scripts/branch-cleanup-batch-510.py` из `main` (проверить post-merge 404), сохранить immutable JSON manifest + historical audit, обновить верхний `docs/ROADMAP.md` и Issue #510, required `test`/`title` → squash merge → read-back. **Новый batch только после checkpoint.**
- Production boundary unchanged: latest **published** immutable prerelease `v5.0.0-rc.9`, tag `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; **deployed** only operator-reported `rc.9`, independent VPS read-back PENDING; v5 overall acceptance **NOT PASS**; G-01…G-11 PARTIAL/PENDING, W-01/W-02 waived NOT PASS. No deploy, restart, refund, Stars purchase, or production smoke occurred.
