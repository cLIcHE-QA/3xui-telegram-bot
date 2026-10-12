# GitHub branch cleanup — merged-PR patch/blob proof, batch 3

**Date/timezone:** 2026-10-12, Europe/Helsinki (EEST, UTC+03:00).
**Issue:** [#510](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/510).
**Exact read-only GitHub baseline:** `main` `967231d708fc243e7cc4cc8193944d22bd5cf72b`.
**Scope:** six *historical* docs PR-head branches (selected from [463-ref historical dry-run manifest](branch-dry-run-inventory-2026-10-12.md)), not the full backlog.
**Disposition:** read-only evidence SCOPED PASS, per-ref cleanup eligibility **PENDING** pending external dependency and SHA-guarded deletion review. No Git refs deleted or changed in this packet.

## Evidence and method

1. Read current GitHub `main`, protected ref, 5 pages of branch refs (100/100/100/100/64 = **464 refs** at snapshot) and all 442 PR records (5 REST pages of 100/100/100/100/42). All six branches are still present, unprotected; current branch tip SHA equals exactly the original merged PR head SHA. All six PRs are `MERGED`, and **no PR (including closed or merged PRs) uses these six names as PR base**. Current open PR count was 0 at the pre-PR read-back.
2. Compared, for each PR, the full GitHub PR changed-files list (`GET /pulls/{n}/files`) to the actual squash merge commit files (`GET /commits/{merge_sha}`): **every filename, status, final blob SHA matched exactly, and there were no missing or extra files**. Each merge commit has precisely one parent (squash). This is stronger than PR-name/head-SHA correlation and proves the PR's final changed file content was represented in the corresponding merged commit, within these exact GitHub file lists.
3. Read all 49 current tracked operational files under `.github/**`, `scripts/**`, `deploy/**` and selected root runtime/config filenames on exact `main`; found **zero exact literal occurrences** of the six branch names. This excludes only *literal references in this bounded source scope*, not external hooks, fork repositories, local clones, branch-local config, dynamic branch-name resolution or other dependencies.
4. GitHub repository `delete_branch_on_merge=true` was independently verified previously; controlled auto-deletion after new PR merge PASS in [#515/#516 checkpoint](../ROADMAP.md). This does **not** remove historical refs. GitHub connector lacks a delete-ref operation, so no manual cleanup was attempted here.

## Per-branch immutable evidence

| Retained branch | Exact tip/original PR head SHA | Merged PR | Squash merge SHA | PR files = squash files and blob hashes |
| --- | --- | --- | --- | --- |
| `docs/branch-lifecycle-audit-20261012` | `78d5f29727f4b4967311cf09cf17ff80f76858d4` | [#511](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/511) | `37b1c700c846791b66a893843e1c68063ab92a6a` | MATCH; `docs/ROADMAP.md` `e89b5e8d02d85180cb34c1b5fc46c42464e3701a` |
| `docs/branch-audit-closure-readback-20261012` | `ca4c922e1980c24c6f7e08c48829694213980b7e` | [#512](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/512) | `fe91d42c23ea4cbf02cbf88b60a1cf580f13c9e3` | MATCH; `docs/ROADMAP.md` `7117af30118fd9b3647c460bdd044ad9ea755aac` |
| `docs/branch-retention-policy-20261012` | `e4de8b36c4dcdd0c2327eb417d8b774591198a95` | [#513](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/513) | `94ff9bc9ced2b45327b6e4d904d11a49bb16afc5` | MATCH; `docs/GIT_WORKFLOW.md` `b4b52d74886dbf92eef236dd92d879c708ae351f`; `docs/ROADMAP.md` `27cbac07654680ac279d0fc5e5d7a1f421b243c9` |
| `docs/aeza-warp-socks-vless-guide-20261012` | `d2e52bf7f1a0c34433294c71b02e62523c74a5c7` | [#490](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/490) | `68213a54a8e3cb20835a310922316bbdbad58e0c` | MATCH; `docs/ROADMAP.md` `4e2f04d0804cddd5aeeb07739215221bece55d90`; `docs/WARP_SETUP.md` `7d26bfbdfddb724e4cfca3c0ffe75d85a3f79df0` |
| `docs/accept-backup-fixes-348-349-20261010` | `ea3921f6896e91c836dd004c744ace358a8978ba` | [#408](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/408) | `b1864a676ed8da91200b1f12f0a4655c0541b025` | MATCH; `docs/ROADMAP.md` `112ae39233d9202b7eb5f13ad911ef261c9b38d5` |
| `docs/client-portal-gate-statuses` | `db818b0ee20819d9995ed8c0376a5643b49489c6` | [#72](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/72) | `f1a2239fc38576641438c0cc5ca0fa7ac8c6ed9d` | MATCH; `docs/ROADMAP.md` `1737cabad88f843b06a8f0d8a1ce2f4403183024` |

**STOP / residual risks:** branch-name consumers outside the inspected 49 tracked operational files remain unknown. No authoritative cross-system check exists for external CI/deploy hooks, operator machines, fork clones or undocumented tooling. Before any deletion recheck exact branch tip SHA, zero open PR head/base, no protected ref, no dependencies, explicit scope approved by operator; delete only with a supported SHA-safe operation and independent 404 read-back, then docs PR/CI and Issue audit. If any uncertainty persists retain ref. A merged source branch is independent of an Issue's own acceptance gates.

**Release/production boundary:** last published immutable prerelease `v5.0.0-rc.9`, tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; latest deployed `rc.9` only operator-reported (2026-10-11 16:15 EEST), no independent VPS read-back. Overall v5 acceptance NOT PASS; G-01…G-11 unchanged, W-01/W-02 waived / NOT PASS. Nothing done to VPS/Telegram/payments/releases.
