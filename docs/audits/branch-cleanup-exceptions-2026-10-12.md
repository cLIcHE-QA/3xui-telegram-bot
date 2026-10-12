# Branch cleanup exceptions — read-only compare batch 1 (2026-10-12 EEST)

**Repo:** `cLIcHE-QA/3xui-telegram-bot`. **Base main SHA:** `c682d8ff4263c67bc938109180a6eca2d7a318f3`. **Evidence:** GitHub REST /branches (five pages), GitHub compare_commits base main SHA → branch current tip SHA. **No deletion, no setting change, no production mutation.** All statuses **MANUAL REVIEW / RETAIN** until unique work, PR outcome, downstream dependencies, and exact refs are independently proven. This is not an executable delete list.

| Branch | Current tip SHA | Compare main→tip | Ahead | Behind | Files reported changed | Disposition |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `chore/publish-v4.9.1` | `9b959657e46d3aae73789560d0b4c4ab3b23c456` | diverged | 2 | 550 | 0 | REVIEW — zero file diff ≠ safe |
| `chore/publish-v4.9.2` | `b27ca479822878ebefc594acde6bd158e8fee2d1` | diverged | 2 | 532 | 0 | REVIEW — zero file diff ≠ safe |
| `chore/publish-v4.9.3` | `62c4aad2b9100fbd97dbab646f0e71f936263699` | diverged | 4 | 522 | 0 | REVIEW — zero file diff ≠ safe |
| `fix/ui-russian-domain` | `21a6dd32a38e488d9f67e23948be975321e99832` | diverged | 33 | 352 | 12 | RETAIN — significant unique graph/history |
| `docs/future-external-psp-sbp-checkout` | `3c7968ff227d51cdad1aa4b6d6de45003dbee203` | diverged | 1 | 133 | 1 | REVIEW — PR closed unmerged |
| `docs/v5-rc7-production-smoke-20261010` | `1307dba03350fe0222050f126986617f97892e6d` | diverged | 1 | 81 | 1 | REVIEW — PR closed unmerged |
| `docs/v4253-production-acceptance` | `3f3059ae436d52b42c2ed73287aa2638815033a2` | diverged | 2 | 257 | 2 | REVIEW — PR closed unmerged |
| `feature/extended-node-backup` | `c0c9fa11ed1b773935d09e89baf459c701d8e6a1` | diverged | 25 | 404 | 21 | RETAIN — substantial unreconciled history |
| `fix/v4.20.7-inbounds-terminology` | `84ac14637f859ce79700eed55787a3730a630a2e` | diverged | 24 | 327 | 22 | RETAIN — substantial unreconciled history |
| `release/v5.0.0-rc.6` | `6b98592204a64dbd660035a0dcaadf37a04e842a` | diverged | 10 | 131 | 9 | RETAIN — closed-unmerged release PR |

**Interpretation:** `ahead_by` is graph divergence relative to recent `main`; it is not the number of real, unapplied product changes after squash. A zero-file-diff comparison is only a current-tree result, not proof of no protected reference/downstream use. Historical PR relationship is from [prior manifest](branch-dry-run-inventory-2026-10-12.md). Further manual inspection required: PR closed reason, original vs current SHA, unique commits and patch IDs, references in workflows/deploy, downstream branches and branch tip freshness.

**Next:** finish docs PR required CI + Roadmap main sync + #510 audit before another batch. Do not delete any of these ten on this evidence.
