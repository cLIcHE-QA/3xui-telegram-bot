# Branch cleanup: 26 no-PR historical refs — GitHub-only ancestry/dependency preflight

**Date/timezone:** 2026-10-12, Europe/Helsinki (EEST, UTC+03). **Scope:** #510, read-only inspection; **baseline immutable main SHA:** `4be8dee2e3096806034a15bf3ad8c4e07a3b7ec4`. **No historical deletions, no settings or production writes.**

## Methods / evidence

- Reused complete historical [branch↔PR manifest](branch-dry-run-inventory-2026-10-12.md), 437 PRs on its baseline. Selected all **26** branches previously marked `MANUAL_REVIEW / no PR matching head name`. This classification means no matching PR head ref in the retrieved historical PR list, not proof that the work is unmerged.
- New fresh GitHub REST branch-list read-back: five `per_page=100` pages (100+100+100+100+64 = **464 current refs** at that instant), all 26 exact names still present, non-protected, and all 26 current SHA **identical** to the historical manifest. New refs / docs PRs may change live counts later.
- GitHub Compare from exact `main` `4be8dee2e3096806034a15bf3ad8c4e07a3b7ec4` to each of the 26 immutable tip SHAs: **23 `status=behind`, `ahead_by=0`**, hence branch tip commits are ancestors of `main` in Git history. No unique branch commits need this temporary ref for reachability; this does **not** prove no consumer references the branch **name**. Three others `status=diverged` with nonzero ahead despite **0 reported file differences**; retain for extra history/dependency review.
- Inspected all **49 GitHub-tracked operational files** from the recursive `main` tree, specifically `.github/**`, `scripts/**`, `deploy/**`, `Dockerfile`, `docker-compose.yml`, selected root config (including `.env.example`). **No exact literal mention of any of these 26 branch names** found in those files. This is a bounded static scan, not a scan of external systems, branch-local configurations, forks, older manifests, operator machines or remote deployments. The full tree was not dependency-analyzed.
- Repository settings `delete_branch_on_merge=true`, first new PR auto-delete independently verified in [PR #515/#516 checkpoint](../ROADMAP.md). **Historical deletion operation is not supported by currently available GitHub connector write actions.**

## SHA-stable per-branch table

| Historical branch (all unchanged on fresh read-back) | Exact current tip SHA | Ahead | Behind | Current disposition |
| --- | --- | ---: | ---: | --- |
| `chore/github-branch-gc-510` | `37b1c700c846791b66a893843e1c68063ab92a6a` | 0 | 6 | BEHIND / precheck only |
| `chore/localize-release-v490` | `c0b40a3d1169163bb86a15daa2f1327aa4ba8122` | 2 | 581 | DIVERGED / RETAIN REVIEW |
| `chore/pre-v5-repo-hygiene` | `6f61f092d67376093335094cd85980fe7f0342e9` | 0 | 172 | BEHIND / precheck only |
| `chore/publish-v4.9.0` | `d4861cf2d18cc4fc38caa2997a4989729701d6bc` | 3 | 581 | DIVERGED / RETAIN REVIEW |
| `docs/a007-fully-remediated` | `3514200d536562e8ee237a418b46c585ef6caf79` | 0 | 174 | BEHIND / precheck only |
| `docs/branch-policy-and-inventory-510-20261012` | `37b1c700c846791b66a893843e1c68063ab92a6a` | 0 | 6 | BEHIND / precheck only |
| `docs/git-branch-lifecycle-policy-510` | `37b1c700c846791b66a893843e1c68063ab92a6a` | 0 | 6 | BEHIND / precheck only |
| `docs/qa352-telegram-4of4-confirmed-20261011` | `aee2df99e878ac705bb953818fe40b3040e9641a` | 0 | 25 | BEHIND / precheck only |
| `docs/qa352-tls-restored-20261011` | `779fcc03009dfdadc6c77a11ef20616569b6f7c4` | 0 | 29 | BEHIND / precheck only |
| `docs/reschedule-v5-expiry-smoke-oct10` | `0b44ac1c7dd4b53f69092ee8c5a38c7c0c4e504e` | 0 | 119 | BEHIND / precheck only |
| `docs/v4-audit-closure` | `e4633406b0cfffe5f8805e816a21728274d650e0` | 0 | 416 | BEHIND / precheck only |
| `docs/v4-audit-completion-gates` | `e4633406b0cfffe5f8805e816a21728274d650e0` | 0 | 416 | BEHIND / precheck only |
| `docs/v4-audit-finalization` | `e4633406b0cfffe5f8805e816a21728274d650e0` | 0 | 416 | BEHIND / precheck only |
| `docs/v4-audit-findings` | `e4633406b0cfffe5f8805e816a21728274d650e0` | 0 | 416 | BEHIND / precheck only |
| `docs/v4-audit-follow-up` | `e4633406b0cfffe5f8805e816a21728274d650e0` | 0 | 416 | BEHIND / precheck only |
| `docs/v4-audit-followups` | `e4633406b0cfffe5f8805e816a21728274d650e0` | 0 | 416 | BEHIND / precheck only |
| `docs/v4-safe-bot-self-update` | `bccb74cb5b9bf6630775defa620dd1e1ba2ca4e2` | 0 | 417 | BEHIND / precheck only |
| `docs/v5-a002-two-offline-regressions-20261011` | `d07ee9b762cddce68cd785a120592dd442d9ac93` | 0 | 71 | BEHIND / precheck only |
| `docs/v5-commerce-offline-suite-20261010` | `04c951caa5f1b5e7cdd5247b07eeebc536b8af98` | 0 | 98 | BEHIND / precheck only |
| `docs/v5-scheduled-backup-deepcheck-20261010` | `b4e7938b7d7c913661b29917ff88492c26d228f3` | 0 | 93 | BEHIND / precheck only |
| `docs/v5-stars-refund-unknown-no-retry-rc7-20261011` | `d07ee9b762cddce68cd785a120592dd442d9ac93` | 0 | 71 | BEHIND / precheck only |
| `feature/v4.11.1-node-onboarding` | `c3bccf7edfcf0db2ea7513f90483b72111b0b7b5` | 0 | 432 | BEHIND / precheck only |
| `fix/roadmap-gate-v4191` | `b8df3aaa828360fca0385b47cd054f971b2dc829` | 0 | 372 | BEHIND / precheck only |
| `fix/v4.20.2-admin-navigation` | `7f0f20e27b7394ea91780380b8fecbdb24750f1a` | 0 | 342 | BEHIND / precheck only |
| `release/v4.10.0-publish` | `11dbf45fd95de9c9092668015404e48233a64540` | 2 | 435 | DIVERGED / RETAIN REVIEW |
| `security/private-admin-chat` | `d4178af779e344f757ee4bed27cc43c675c32794` | 0 | 210 | BEHIND / precheck only |

### Additional evidence for 3 diverged, zero-tree-diff refs

GitHub raw compare commit lists independently read; all three return no file differences from the recent `main` despite separate commits that remain outside the `main` ancestry.

- `chore/localize-release-v490`: `fabde307904b50fafa64537892facb9c4698b313` — release v4.9.0 Russian notes; `c0b40a3d1169163bb86a15daa2f1327aa4ba8122` — removal of one-time translation procedure (2026-09-22 UTC). Retain unique commits until provenance/archival decision.
- `chore/publish-v4.9.0`: `181671f735edd8614197912399352ec2e913a8e7`, `ff0f5897bd838279b84e13f567001a77d3b689c6`, `d4861cf2d18cc4fc38caa2997a4989729701d6bc` — temporary release publishing, preflight, removal (2026-09-22 UTC). Retain unique commits until review.
- `release/v4.10.0-publish`: `2c007b90a5f1000f9f0e8c38a47a766efe91dccd`, `11dbf45fd95de9c9092668015404e48233a64540` — temporary publishing workflow and removal (2026-09-23 UTC). Retain unique commits until review.

## Disposition / next safe gate

**23 `ahead=0`: SOURCE-COMMITS-IN-MAIN / potential small pilot candidates, NOT YET AUTHORISED FOR DELETION.** Best low-risk precheck subset is `chore/github-branch-gc-510`, `docs/branch-policy-and-inventory-510-20261012`, `docs/git-branch-lifecycle-policy-510`, all tips `37b1c700c846791b66a893843e1c68063ab92a6a` already in `main`; no PR matched and no exact branch-name references in scanned 49 operational files. Before any deletion: confirm no external/other-branch operational dependency, current no-open-PR head/base, exact tip SHA compare-and-delete, no protected ref and independent post-delete ref read-back, then Roadmap/Issue checkpoint.

**3 `diverged`: RETAIN / MANUAL REVIEW.** Their complete trees currently match `main`, but graph retains 2/3/2 unique commits. Do not delete based on zero file diff.

**Rest of backlog:** 10 SHA-diverged/closed-only exceptions were reviewed separately in [batch 1 audit](branch-cleanup-exceptions-2026-10-12.md), remain retained. The other 426 PR-associated head-matching candidates still lack individual patch/dependency review. External branch-name consumers cannot be ruled out by the current source scan. No GitHub deletion-capable tool is available; do not fake deletion by updating refs. #510 OPEN/PENDING and overall v5 acceptance NOT PASS.
