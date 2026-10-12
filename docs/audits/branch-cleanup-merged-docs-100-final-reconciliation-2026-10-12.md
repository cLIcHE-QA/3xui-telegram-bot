# #510 — окончательная reconciliation batch100 после двух STOP (84 ABSENT / 16 PRESENT)

**Дата evidence:** 2026-10-12 11:07+ Europe/Helsinki (EEST, UTC+03:00). **Scope:** только 100 ранее отобранных `docs/*` merged-PR candidates из [immutable manifest](branch-cleanup-merged-docs-100-2026-10-12.json). Source — GitHub Actions exact logs, independent GitHub REST full branch-page inventory and PR/CI provenance. **Не production smoke/acceptance, не новый deployment.**

## Доказанный результат, без смешения с успешностью workflow

- Original [PR #525](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/525), exact PR head `5d7d041f65115010bec3cea739c3d66a7d5fc7d5`, baseline main `6ee818cf0ea2e96e138e39c149b2416dac072276`: required `test` PASS [38220249599](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38220249599), latest required `title` PASS [38220474402](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38220474402), audit PASS [38220249624](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38220249624), *read-only* `preflight` PASS [38220249758](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38220249758): 98 candidates met exact PR/squash filename/status/final-blob-SHA and no tracked literal dependencies; two were correctly rejected before deletion (PR #2 and #11). Squash MERGED `main` `a8792aeed90c83bc1171f643dc607e6ad7cdffb4`, post-merge Python checks PASS [38220512890](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38220512890) and audit PASS [38220512904](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38220512904).
- One-shot [GitHub Actions run 38220678414](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38220678414) had **two attempts, both ended FAILURE — do NOT mark workflow PASS**.
  - Attempt 1, 2026-10-12 08:00:21 UTC: 33 `DELETED / VERIFIED` with atomic server-side `git push --force-with-lease`; after further successful deletion of `docs/agents-guidance`, the *immediate* REST GET was not yet 404, so fail-closed STOP. Independent subsequent GitHub GET 404 and full-list read-back verified **34 ABSENT / 66 PRESENT**. This intermediate state is canonically preserved in [previous partial audit](branch-cleanup-merged-docs-100-partial-result-2026-10-12.md) and [PR #526](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/526).
  - Attempt 2, same run, 2026-10-12 08:07:10 UTC: after independent reconciliation of exact 34 vanished/66 stable refs, failed jobs were re-run only for the **same scoped package**; missing branches were skipped and candidate SHA/PR/blob/dependency proof repeated. New log has **50 additional `DELETED / VERIFIED`** through `docs/accept-a007-risk` PR #277; then **STOP/PENDING: main changed; stop without deleting more**. Concurrent [docs PR #526](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/526) merged at 08:07:02 UTC into `main` `57ac6f228cd59418a6f50534ca2754ee6010cd2e` while this job used baseline `a8792aeed90c83bc1171f643dc607e6ad7cdffb4`. Main-SHA guard correctly prevented further mutations. No blind retry or forced continuation after main drift.
- **Final independent GitHub REST inventory** after run 2 (all branch pages: `100+100+100+61=361` refs, fully enumerated (new docs source branch included)) matched exact 100-entry manifest: **84 ABSENT / 16 PRESENT**, all 16 still at original expected full SHA, no drift. Two of these 16 are deliberately **RETAIN / PR-vs-squash blob mismatch**: `docs/russian-documentation` (#2), `docs/v4.10-host-control-contract` (#11). The remaining **14** are **PENDING / NOT DELETED** because main changed before they could be processed. These are not PASS or irreversible failures.
- Together with earlier checkpointed `3+20=23` safe deletions, **107 historical refs are now independently verified ABSENT**; this scoped count is not the number of all eligible historical branches and #510 overall remains OPEN / PENDING.

## Exact 100-ref final state

Each originally selected SHA/pr is in immutable JSON. `ABSENT` denotes independent authoritative complete GitHub REST branch-list absence after the second STOP, *not* a claim that run completed successfully.

| № | Branch | Merged PR | Immutable pre-delete SHA | Final independently observed status |
| ---: | --- | --- | --- | --- |
| 1 | `docs/russian-documentation` | #2 | `40101eec1125b9b1f7077751b42d9f1403195b92` | RETAIN — PR/squash blob mismatch |
| 2 | `docs/v4.10-host-control-contract` | #11 | `e760bd9047066c4118d7b54558d8e85a042de772` | RETAIN — PR/squash blob mismatch |
| 3 | `docs/v5-client-portal-roadmap` | #28 | `64e4b6395c776fa84bdf33711f93264f27db1811` | ABSENT — independently verified |
| 4 | `docs/v4-admin-finalization-scope` | #31 | `9d469bb02b32823d7076cf4f7a5ca316eab377a4` | ABSENT — independently verified |
| 5 | `docs/v4-safe-self-update` | #32 | `26ebd02b7c54d18c341018f08d8dd79e222e06ce` | ABSENT — independently verified |
| 6 | `docs/v4-finalization-audit` | #33 | `247626b9a598602b64bc7a57e0fd1e50ef37ca6a` | ABSENT — independently verified |
| 7 | `docs/roadmap-competitive-benchmark` | #34 | `968ba1bac552c4583aef89dbce7d89b444c26e1f` | ABSENT — independently verified |
| 8 | `docs/roadmap-status-tracking` | #36 | `4f4369ca4038e699760ba776f6c6e1b0d951f43c` | ABSENT — independently verified |
| 9 | `docs/roadmap-status-contract` | #37 | `b93404168cfe35177aafa63572bdb1e09d95a399` | ABSENT — independently verified |
| 10 | `docs/roadmap-v4-13-2-status` | #39 | `15f453e116fa6e0ea38c1fdadbfdc1ed1115e10b` | ABSENT — independently verified |
| 11 | `docs/post-release-verification` | #40 | `3f67f1e3903322619524d18a51c1842feaf28c30` | ABSENT — independently verified |
| 12 | `docs/targeted-release-smoke` | #41 | `4d6301d054a952c86c5f3ee16990000e2b04577d` | ABSENT — independently verified |
| 13 | `docs/rbac-main-status` | #43 | `dddf8007adddf67288c1f53f92b8ea277bb495cd` | ABSENT — independently verified |
| 14 | `docs/extended-node-backup-main-status` | #46 | `cd7fe3ecb369b5c061ba9cf69e5d38cc0f126288` | ABSENT — independently verified |
| 15 | `docs/close-v4.14-roadmap` | #50 | `1784e539e2e8b1e79b2fea7f09a00abc97189c74` | ABSENT — independently verified |
| 16 | `docs/quick-start-v4.14.1` | #51 | `1f3a5c11b5b44fbeb23907a7f33da011e66c4f8a` | ABSENT — independently verified |
| 17 | `docs/admin-setup-guide` | #54 | `ba5bff77ff01e3871cd0558c365dd2b007864d2b` | ABSENT — independently verified |
| 18 | `docs/sqlite-migrations-status` | #56 | `3d7586d3cf2c918c8d5e883a5bfa8c594b1eda43` | ABSENT — independently verified |
| 19 | `docs/sqlite-migrations-complete` | #58 | `c4699f082834d1fdc6b37a0a096042f99e4ce444` | ABSENT — independently verified |
| 20 | `docs/telegram-text-emoji-audit` | #59 | `01cb1f9d63093427c845cea962ae61bd2a2cc19f` | ABSENT — independently verified |
| 21 | `docs/v416-regression-status` | #61 | `78c7a23e0f502d6977c91598ad453b1e085f224d` | ABSENT — independently verified |
| 22 | `docs/v416-regression-accepted` | #63 | `3db78fe96e2bc9f1ecd6e7142039e5879f398875` | ABSENT — independently verified |
| 23 | `docs/v417-openapi-status` | #65 | `e9eae8f2dbff286f2a99699483d4fa4d3279e8bf` | ABSENT — independently verified |
| 24 | `docs/v417-production-acceptance` | #67 | `999685557a380eb5bc7c26f8670439975bd0f3af` | ABSENT — independently verified |
| 25 | `docs/v418-offsite-status` | #69 | `9afb6f46c646f60dc13816aaea8d6a9a8283279c` | ABSENT — independently verified |
| 26 | `docs/v418-deferred-acceptance` | #71 | `8489f2e98e6d760e4bf67e87e539ba54eabba6d4` | ABSENT — independently verified |
| 27 | `docs/client-portal-gate-statuses` | #72 | `db818b0ee20819d9995ed8c0376a5643b49489c6` | ABSENT — independently verified |
| 28 | `docs/v419-self-update-status` | #74 | `cae66ab47da171fc988e3b8cec9cc8cc86d5c5f3` | ABSENT — independently verified |
| 29 | `docs/readme-current-state` | #92 | `bb37d9c7f17e0ca48b6f4df0a510fdb6a4e17f24` | ABSENT — independently verified |
| 30 | `docs/ui-russian-core` | #93 | `3a3928aef13a34b018d0e07cb381c2750a8114b1` | ABSENT — independently verified |
| 31 | `docs/ui-localization-roadmap-status` | #100 | `2f25d804de5011976646dcc3cd0909447656ebaa` | ABSENT — independently verified |
| 32 | `docs/cleanup-roadmap-statuses` | #101 | `2c91abcece68a8b03801fa1be99c3cac5d979f48` | ABSENT — independently verified |
| 33 | `docs/v4.20.1-freeze-prep-acceptance` | #108 | `bb4e39c5c3e6d648019de2401419e8b05f63cf37` | ABSENT — independently verified |
| 34 | `docs/v4.20.5-ui-follow-up` | #114 | `01e5e63b5d37ccd1f2e6537ca1f7c794a65b9615` | ABSENT — independently verified |
| 35 | `docs/pre-v5-feature-roadmap-and-final-audit` | #115 | `3ca415c7a75c30531c559a678bd5016d02cf9e79` | ABSENT — independently verified |
| 36 | `docs/agents-guidance` | #116 | `16f68c919f9a5453d3ebf6d2b6c36357776de71a` | ABSENT — independently verified |
| 37 | `docs/v4.20.5-published-status` | #119 | `ea9c6f5398336e5434248025087c3b828cce2c94` | ABSENT — independently verified |
| 38 | `docs/v4.20.5-production-acceptance` | #120 | `0f6a050646aaf9df06bb4adf8e2103868c642905` | ABSENT — independently verified |
| 39 | `docs/v4.20.6-acceptance-v4.20.7-plan` | #123 | `7ef77eac9e1e95add2b1d8ab0b60e915bfea9e15` | ABSENT — independently verified |
| 40 | `docs/v4.20.7-production-acceptance` | #127 | `3bfd1475c7356a2a88e2c5a7d3292c6f2a10a606` | ABSENT — independently verified |
| 41 | `docs/v4.20.8-production-acceptance` | #130 | `8f4a2175272148a5689d025a978fe32f03e51178` | ABSENT — independently verified |
| 42 | `docs/v4.20.10-production-acceptance` | #135 | `68a8eed587a131147bf21fd816d62b8c4db1b88e` | ABSENT — independently verified |
| 43 | `docs/v4.21.0-published-status` | #138 | `7f9f01169d5af679e5025a4934b002da11fb2266` | ABSENT — independently verified |
| 44 | `docs/v4.21.0-production-acceptance` | #139 | `02cd6213bfeb091dcb64fe339daa5fdc846a5318` | ABSENT — independently verified |
| 45 | `docs/v4.21.1-published-status` | #142 | `576fcb1a3d49dcf8af392bc768d3fa5da3d34238` | ABSENT — independently verified |
| 46 | `docs/v4.21.2-production-acceptance` | #145 | `b4ec3add52eb7ec3f5f99e315280ab275426fa60` | ABSENT — independently verified |
| 47 | `docs/v4-25-user-management-roadmap` | #146 | `bea9773892cb8afce4051f174ff1f5886d8c4e1b` | ABSENT — independently verified |
| 48 | `docs/v4-22-implemented` | #148 | `b2b1d3d5bb4ff4389723557d5eeb412754ceb2d0` | ABSENT — independently verified |
| 49 | `docs/v4-22-published` | #150 | `67d759dfe8dd01d80d2d90a0479aaaafaed2e1f0` | ABSENT — independently verified |
| 50 | `docs/v4-22-production-accepted` | #151 | `96313d018cb41125b3e927db9149f7dbc96b41ad` | ABSENT — independently verified |
| 51 | `docs/v4-26-node-drain` | #152 | `971c1a4cb4febf12571eca82b7de195f92c68a01` | ABSENT — independently verified |
| 52 | `docs/v4-23-1-acceptance` | #157 | `8bc27be8c5c348071c12fa82105a5e5bc78efe0d` | ABSENT — independently verified |
| 53 | `docs/cheburcheck-probe-fleet-roadmap` | #162 | `f3c60d53aae235319b56d727f07914e950568e9f` | ABSENT — independently verified |
| 54 | `docs/close-v4-23-3` | #163 | `2c61c44a55773156d0c7c93bab31f0b26459f9ee` | ABSENT — independently verified |
| 55 | `docs/v4-24-0-release-contract` | #164 | `8f0b7a62662d1f42ee4f5c2148fff597588ce519` | ABSENT — independently verified |
| 56 | `docs/v4-24-1-whois-msk` | #170 | `98b71b134e879cd00e5150671c7e95993534c8f8` | ABSENT — independently verified |
| 57 | `docs/v4-24-1-production-acceptance` | #173 | `29ae304cbbba2327a18af484550f6cd10b7361cc` | ABSENT — independently verified |
| 58 | `docs/close-v4-24-line` | #174 | `0a3e140f98281bedc625b325f346ee85652497b9` | ABSENT — independently verified |
| 59 | `docs/sync-production-acceptance-v4-21-v4-24` | #175 | `9575cc3d1da8c98ad58b3a50962c79dc4b9d72cb` | ABSENT — independently verified |
| 60 | `docs/v4-25-implementation-complete` | #185 | `bdeaa52a7d187863d0e6a44a56654ab63f56ea9e` | ABSENT — independently verified |
| 61 | `docs/v4-25-published-status` | #187 | `088fbf3740f5abe0d68c1f6fce2a177c2c554986` | ABSENT — independently verified |
| 62 | `docs/v4251-production-acceptance` | #190 | `40b5638a14c93040de4a667c1e37f442c0a45f22` | ABSENT — independently verified |
| 63 | `docs/shadowrocket-send-hwid` | #192 | `fe4cbd9f537957751b853b636c7387c29471e4f9` | ABSENT — independently verified |
| 64 | `docs/close-v425-production-line` | #198 | `827f9686638b9e193da08da743cd3a7703b742fb` | ABSENT — independently verified |
| 65 | `docs/roadmap-v4.25.8` | #203 | `79be864b791c1e252e1d84918a56a55e25cac019` | ABSENT — independently verified |
| 66 | `docs/close-v4.25-line` | #207 | `f6d1f60b70f052c919f68b1c09706664e3e1c8da` | ABSENT — independently verified |
| 67 | `docs/v4-26-1-node-drain-navigation` | #212 | `38b61d559d5f46c8e828de5306ebfed9558c0cfc` | ABSENT — independently verified |
| 68 | `docs/v4-26-1-production-acceptance` | #215 | `2f646e5e1f7fea5326f954b903fb9e7a9655a381` | ABSENT — independently verified |
| 69 | `docs/attention-releases-v4-26-2-v4-26-3` | #218 | `c7ac8d22b331e7434f8ffc0041ede200996dc6c3` | ABSENT — independently verified |
| 70 | `docs/data-plane-addressing-firewall` | #220 | `a9e575faacfcb7350ff7b0f5d1cd92c4d29453f7` | ABSENT — independently verified |
| 71 | `docs/v4.26.2-acceptance` | #223 | `4187fa6305ea71912bcfd325477d2e6d217d76cd` | ABSENT — independently verified |
| 72 | `docs/v4.26.4-navigation-fix` | #227 | `92160142d4daa273012799aec4437e3d9ee498c9` | ABSENT — independently verified |
| 73 | `docs/v4.26.4-acceptance` | #230 | `16ce4b2c5e4fba704d9a90e6369c298db9261111` | ABSENT — independently verified |
| 74 | `docs/fix-v4-closure-order` | #231 | `92ff8f1c3da4e4a26fedc7a2bf1795b42c96f556` | ABSENT — independently verified |
| 75 | `docs/remnawave-roadmap` | #232 | `54f84f17e09817adc7c22c3909c15f662742ec2a` | ABSENT — independently verified |
| 76 | `docs/final-v4-feature-freeze` | #233 | `dfa5bc16a7601fcd31d550b3ae4955b7a716eb98` | ABSENT — independently verified |
| 77 | `docs/final-v4-audit-baseline` | #247 | `dc445039a632278150000603c7ae7bc24cb1bccc` | ABSENT — independently verified |
| 78 | `docs/recovery-drill-record` | #251 | `7bc6de5fc9069119fd7d9b3fa32f1b61a882d5f0` | ABSENT — independently verified |
| 79 | `docs/github-communication-language` | #254 | `ee447092fb1ec89e063944e4781fdcb22b10a755` | ABSENT — independently verified |
| 80 | `docs/russian-v4-audit` | #257 | `886c6cc4dcf0914a795717047b6d2c4652e336dc` | ABSENT — independently verified |
| 81 | `docs/full-backup-retrieval` | #259 | `b2956028c9a9f8c2d5839e23e913c6b17ce75b3d` | ABSENT — independently verified |
| 82 | `docs/github-status-health-gate` | #262 | `203a4115692eec4524302db1fb469a2cb0aa9b33` | ABSENT — independently verified |
| 83 | `docs/close-a010-history-secret-audit` | #267 | `719108f62d89b2d5bda38cce3bed73c049e7b0bb` | ABSENT — independently verified |
| 84 | `docs/sync-a011-a012-audit-status` | #271 | `5fe48886123fed36617705a328329560f1a15826` | ABSENT — independently verified |
| 85 | `docs/close-a008-a009` | #276 | `955fa87b7260a2b7c245a0483da486e68733e121` | ABSENT — independently verified |
| 86 | `docs/accept-a007-risk` | #277 | `0eabe4c43bd695340a888b75ca4f09f3e4b0270f` | ABSENT — independently verified |
| 87 | `docs/post-public-roadmap` | #286 | `99a2ba7f1648c1364311bff71632454eb0c11967` | PENDING — unchanged, not deleted after stop |
| 88 | `docs/live-docs-post-public-sync` | #287 | `f66d97549d8a53b37124b9de19e2dbc800750439` | PENDING — unchanged, not deleted after stop |
| 89 | `docs/close-post-public-governance` | #288 | `506f05085c2846f9a62063afdf2a5dc32b918f74` | PENDING — unchanged, not deleted after stop |
| 90 | `docs/v5-roadmap-after-checkout` | #303 | `ff7159520dba4ac402d5b60a25c0f422e6b3d8e2` | PENDING — unchanged, not deleted after stop |
| 91 | `docs/v5-production-acceptance` | #309 | `beac2ee46a83074ca9e91c35dde0392d32815159` | PENDING — unchanged, not deleted after stop |
| 92 | `docs/v5-rc2-acceptance-progress` | #315 | `fdac282b541c426563b1bf8d5a04df696889b58d` | PENDING — unchanged, not deleted after stop |
| 93 | `docs/v5-stars-orders-admin-roadmap` | #316 | `75150b60329b8d870b046e32281849f3deb0561f` | PENDING — unchanged, not deleted after stop |
| 94 | `docs/v5-stars-paid-invoice-ux` | #321 | `ec41ac6cab399a81a182a0828c78112091b17c83` | PENDING — unchanged, not deleted after stop |
| 95 | `docs/v5-rc3-v5-a-007-pass` | #322 | `e9bf880b7de2c67ea78202454bd8e1a616a6567f` | PENDING — unchanged, not deleted after stop |
| 96 | `docs/v5-customer-device-self-service` | #323 | `987562015f1c328a34ef4fde550b55a41e790df8` | PENDING — unchanged, not deleted after stop |
| 97 | `docs/v5-rc4-v5-a-008-targeted-pass` | #327 | `f27c651a67032a9143779a29ddb2e59138211964` | PENDING — unchanged, not deleted after stop |
| 98 | `docs/v5-rc5-production-smoke-evidence` | #331 | `2416de3d59e2123df152752c4e638a51f5991aba` | PENDING — unchanged, not deleted after stop |
| 99 | `docs/v5-rc5-refund-targeted-pass` | #332 | `aaaa51bc049c3b99dce296a6d9665963319b37cf` | PENDING — unchanged, not deleted after stop |
| 100 | `docs/future-external-psp-sbp-checkout-v2` | #338 | `0763ebd29ba4b0641753fde367397a6d7805b163` | PENDING — unchanged, not deleted after stop |

## GitHub / Roadmap checkpoint, guardrails and remaining risks

- [PR #526](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/526) already recorded earlier 34/66 intermediate state and **removed** temporary privileged `.github/workflows/retire-merged-docs-100-510.yml` and `scripts/retire-merged-docs-100-510.py` from main. PR #526 squash merged `57ac6f228cd59418a6f50534ca2754ee6010cd2e`, post-merge Python checks PASS [38221634778](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38221634778), security audit PASS [38221634794](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38221634794). Exact failure chronology remains historical; this new audit supersedes only its **current 34/66 snapshot** with measured 84/16, not the historical first attempt evidence.
- This reconciliation requires its own docs-only PR updating the **top `docs/ROADMAP.md`** and this audit, required `test`/`title` PASS, squash merge, independent `main` Roadmap/audit read-back and #510 Issue status audit before any next batch. **No historical ref deletion in the documentation PR.** Treat new batches as PENDING until authorized preflight / SHA lease / postcondition on a new immutable baseline.
- Limitations: external/fork/local/dynamic branch-name consumers not independently excluded by tracked source scan; some old branches have unique commits and remain RETAIN/REVIEW; two blob mismatch branches definitively retained in this scope. No mutation of `main` contents or release tags by deletion actions; main moved only via the separately merged docs PR #526.
- Latest **published** immutable prerelease `v5.0.0-rc.9`, exact tag `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; **deployed** only operator-reported same rc.9, independent production VPS read-back PENDING; overall v5 **NOT PASS**, G-01…G-11 PARTIAL/PENDING, W-01/W-02 OPERATOR-WAIVED/NOT PASS. No VPS deployment/restart, Telegram burst, Stars purchase/refund, restore, 3x-ui write or production smoke in this GitHub-only scope.

**Disposition:** **batch100 execution FAILURE / two STOP events**, **84 branch absences independently confirmed**, **16 retained/pending**; **#510 OPEN/PENDING**. Do not convert this into a blanket 100/100 PASS.
