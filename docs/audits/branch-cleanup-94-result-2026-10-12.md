# #510 — безопасное удаление 94 исторических веток: scoped PASS

## Baseline / время / scope

- **Дата:** 2026-10-12, Europe/Helsinki (EEST UTC+03:00). One-shot запущен 12:21:05 UTC / 15:21:05 EEST; финальное выполнение и GitHub workflow SUCCESS к 12:28:21 UTC / 15:28:21 EEST; независимый GitHub REST read-back 2026-10-12 после исполнения.
- **Scope:** GitHub-only cleanup конкретных 94 refs из [immutable manifest](branch-cleanup-verified-94-candidates-2026-10-12.json), file blob `0ca0669bcd68461d67d78b431f32d1c01322929a`, exact branch name, immutable tip SHA, original merged PR и squash SHA. Без VPS/Telegram/3x-ui production, payments, Stars, refund, deploy, restart.
- **Baseline main:** protected `ae669ba8bff3b7bf93250bd0efddfb8f89c2f053`, исходный GitHub snapshot **203 refs / 202 non-main**, 0 open PR; отдельный [PR #542](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/542) canonical checkpoint завершён с post-merge CI PASS.
- **Исторический 100-ref FAIL:** [preflight 38246026296](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38246026296) = 94 individual PASS + **6 RETAIN**, deletion 0/100. Этот исторический FAIL не переименован в PASS; original PR #541 closed without merge.

## 94-ref strict proof, PR и CI

- Execution [PR #543](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/543), exact approved head `485862813589f4388f63fe60f43875a8bfea652e`: required `test` PASS [38247932564](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38247932564), latest required `title` PASS [38248234484](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38248234484), supply-chain audit PASS [38247932362](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38247932362).
- Strict independent read-only 94-ref [preflight 38247932389](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38247932389) **PASS**: 94 × `PROOF PASS`, 0 failures, final `DRY-RUN PASS 94/94; deleted=0`. Verifies original name/tip SHA, PR head/base/merge, single-parent squash PR file/status/blob equivalence, ancestry, tracked name refs, remote descendants and live SHA.
- PR #543 squash **MERGED** protected `main` `b3c7c177a23492de5c3b2b38fe3db86a808bd191`; post-merge `Python checks` [38248278340](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38248278340) **PASS**, supply-chain audit [38248278783](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38248278783) **PASS**. One-shot `workflow_run` required main CI and immutable first-parent gate.

## Фактическое исполнение и независимые доказательства

- [One-shot run 38248483933](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38248483933), `retire-once` job `114808312792` completed **SUCCESS**. Exact 94 safety proofs repeated on main, no failed proofs, **94** exactly-once server-side Git `push --force-with-lease` ref deletions with bounded read-only postcondition; **94 × `DELETED / VERIFIED`**, `BATCH94 RESULT verified_deleted=94/94`. **Никаких повторных write при неопределённом результате.**
- **Независимый GitHub REST `GET /branches/{exact name}` для каждого из 94 дал HTTP 404 (94/94).** В этом же read-back complete GitHub branch inventory **100+9+0 = 109 refs**, включая protected main `b3c7c177a23492de5c3b2b38fe3db86a808bd191`; **108 рабочих refs**; 94 target names отсутствуют в inventory. Net delta **203 → 109 = −94**.
- Все **шесть RETAIN** исходного 100-ref scope остались **PRESENT** по неизменённым immutable SHA. Ещё шесть исторических known RETAIN и все остальные нецелевые refs не входили в allowlist. Immutable release tags не затрагивались.
- Старое cumulative историческое наблюдение **267 distinct ABSENT** + независимые новые 94 distinct ABSENT = **361 distinct historical refs ABSENT**. Исторические частичные FAIL и operator-reported/unknown attribution прежних 50 веток не исправлены ретроактивно.

## Шесть исключений, НЕ удалены

| Branch | Причина | Disposition |
| --- | --- | --- |
| `chore/git-conventions` | tracked branch-name source dependency | **RETAIN / MANUAL REVIEW** |
| `chore/publish-v4.10.0` | original PR / one-parent squash file-status-blob mismatch | **RETAIN / MANUAL REVIEW** |
| `chore/release-deploy-helper` | original PR / one-parent squash file-status-blob mismatch | **RETAIN / MANUAL REVIEW** |
| `feature/v4.9.2-system-version-fingerprint` | original PR / one-parent squash file-status-blob mismatch | **RETAIN / MANUAL REVIEW** |
| `feature/v4.10-host-control` | original PR / one-parent squash file-status-blob mismatch | **RETAIN / MANUAL REVIEW** |
| `feature/versions-updates` | original PR / one-parent squash file-status-blob mismatch | **RETAIN / MANUAL REVIEW** |

## Поимённый independent read-back 94/94

| Branch | Immutable tip SHA до удаления | Original merged PR | REST after operation |
| --- | --- | --- | --- |
| `chore/host-control-rollout` | `b2c8d5776d6b85192b8860c33b1a71d896534d9a` | [#15](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/15) | **404 / ABSENT** |
| `chore/living-docs-contract` | `06b4d1e9e62cefa47f77a946ecf4dc80125cf391` | [#289](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/289) | **404 / ABSENT** |
| `chore/pr-checklist-gate` | `5836ffe504dc710a2cfa63a3266975ba35c1de1e` | [#371](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/371) | **404 / ABSENT** |
| `chore/release-automation` | `2b7ad82f47d608cce712f68880ae9d33d8a4db0e` | [#19](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/19) | **404 / ABSENT** |
| `chore/vps-recovery-kit` | `16b1666997a7839c24ffcb5b436b92bd1fc2b643` | [#14](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/14) | **404 / ABSENT** |
| `chore/3xui-living-contract-sync` | `99f781f44af4fdba43a92fb362eccddecf771413` | [#428](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/428) | **404 / ABSENT** |
| `docs/branch-audit-closure-readback-20261012` | `ca4c922e1980c24c6f7e08c48829694213980b7e` | [#512](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/512) | **404 / ABSENT** |
| `feat/master-node-hosts-readonly-422` | `42ccdd740b8a062def3242d1c04574ab72a9d548` | [#424](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/424) | **404 / ABSENT** |
| `feat/v5-checkout-provider-boundary` | `2b5fbd817d2fa107b36d11578016f030fb2aa548` | [#302](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/302) | **404 / ABSENT** |
| `feat/v5-client-onboarding-diagnostics` | `9839396320f37559a1848d144709ce62562f0148` | [#306](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/306) | **404 / ABSENT** |
| `feat/v5-client-portal-shell` | `42b64d2b6d6a5a3f5d9ffd34c4ab28a5acdf7ec7` | [#296](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/296) | **404 / ABSENT** |
| `feat/v5-commerce-foundation` | `9cc2d7cd14c9dfa296bb39834ddf23789a0422e1` | [#290](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/290) | **404 / ABSENT** |
| `feat/v5-customer-service-boundary` | `beb89ecb73513df39691a40f4a3abc968e044d6b` | [#301](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/301) | **404 / ABSENT** |
| `feat/v5-entitlement-fulfillment-worker` | `3d89e083fcaa6b663dc224c75716daeee8ce1ce3` | [#295](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/295) | **404 / ABSENT** |
| `feat/v5-entitlement-provisioning` | `39f374cea8eccdb46f692cad64a55e0fc97aa58d` | [#292](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/292) | **404 / ABSENT** |
| `feat/v5-launch-readiness` | `4e7bb23fe848ad51a82256d3e43a9411e53355bd` | [#307](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/307) | **404 / ABSENT** |
| `feat/v5-payment-entitlement-transaction` | `0831384e76bba14a9905ac80ed7050e46252aea9` | [#291](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/291) | **404 / ABSENT** |
| `feat/v5-payment-event-reconciliation` | `d08fdc87f27ad7028af2255adb2ddd656938e139` | [#294](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/294) | **404 / ABSENT** |
| `feat/v5-payment-webhook-gateway` | `cb731d04c4c57de56bf9b714c47780a1ff54f0de` | [#293](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/293) | **404 / ABSENT** |
| `feat/v5-release-candidate-path` | `c2a76a0132e8bb59ecc7e572475d533ee2c18d8d` | [#310](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/310) | **404 / ABSENT** |
| `feat/v5-stars-production-hardening` | `840c848ef516b2b3b1124770cd646e4ec33f1afb` | [#305](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/305) | **404 / ABSENT** |
| `feat/v5-telegram-stars` | `1eee32586d3ee14bd493037bd3be7f0c6a01c581` | [#304](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/304) | **404 / ABSENT** |
| `feature/admin-username-display-355` | `7d7874aa278d8ab9d99dab4bdfcdbf7e2a78f5b8` | [#364](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/364) | **404 / ABSENT** |
| `feature/attention-center` | `5044031d53279d992faf5719b53ad9b5e7063047` | [#224](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/224) | **404 / ABSENT** |
| `feature/cheburcheck-discovery-v4-23` | `b9da160fb1e8b0283568d65f41553fd8d8f72c7b` | [#154](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/154) | **404 / ABSENT** |
| `feature/cheburcheck-v4-23-2` | `d5df86801329aae29b1a4acd64e2bb96e5aac978` | [#158](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/158) | **404 / ABSENT** |
| `feature/cheburcheck-v4-23` | `517bdddfc31f8b5807d40b3e8c6b8e2e789cf45e` | [#153](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/153) | **404 / ABSENT** |
| `feature/client-portal-stars-switches-342` | `ff0d699ccb80b1fbab5197619976f1f9fc20b444` | [#368](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/368) | **404 / ABSENT** |
| `feature/dashboard-attention` | `5ebcd4c82451fc957a76ba90aff2f619c9e85e04` | [#221](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/221) | **404 / ABSENT** |
| `feature/direct-node-onboarding-wrapper` | `371bb91735207c87f39c49a5005540dfd8f352af` | [#24](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/24) | **404 / ABSENT** |
| `feature/extended-node-backup-clean` | `1b6afc96ecf75cb7310f8d2f7ccfabbd75f3c434` | [#45](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/45) | **404 / ABSENT** |
| `feature/fleet-operations` | `413abf186e093e7ac42f230c2ca4e0e9b82135cf` | [#26](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/26) | **404 / ABSENT** |
| `feature/job-update-unknown-ack-353` | `2552168cbdbc9599eb30da96ed76faec07f387d6` | [#362](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/362) | **404 / ABSENT** |
| `feature/node-drain` | `f3d105bc03fdaf13fe65f46a6cd943d40af3990e` | [#209](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/209) | **404 / ABSENT** |
| `feature/owner-client-session-reset-345` | `680fa7789a12e8c4f42bcf15874f3bd8bbb954df` | [#416](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/416) | **404 / ABSENT** |
| `feature/rbac-privileges` | `44ef8973aeff4238060349a93d984065b785c7f3` | [#42](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/42) | **404 / ABSENT** |
| `feature/telegram-command-catalog-356` | `bf50ffad077a75b066bab1df55ccc2e0cfd8fe7d` | [#365](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/365) | **404 / ABSENT** |
| `feature/user-audience-groups` | `c1b1c44c536f78f8b28517beff0656d152cb496f` | [#147](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/147) | **404 / ABSENT** |
| `feature/user-display-name` | `bf1556cc77e91c3873857008cb56eeae102d1877` | [#136](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/136) | **404 / ABSENT** |
| `feature/v4-24-monitoring-foundation` | `33785ccd9cdb315c92764c3f485bcff36fe4e0ac` | [#165](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/165) | **404 / ABSENT** |
| `feature/v4-24-monitoring-lifecycle` | `3ed7f054f52de2821fd429ce844978d8570d8c45` | [#168](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/168) | **404 / ABSENT** |
| `feature/v4-24-monitoring-ui-runtime` | `8b967aa2eb9435624f4a6aa4affd01e0af737591` | [#166](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/166) | **404 / ABSENT** |
| `feature/v4-24-web-diagnostics` | `089a7a4535463c4f5ba12f7fb9ad29e62cd5b9e2` | [#167](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/167) | **404 / ABSENT** |
| `feature/v4-25-user-bulk-completion` | `6936549fcb25d96056ce8e2c92f525727fdf8ab2` | [#182](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/182) | **404 / ABSENT** |
| `feature/v4-25-user-card-navigation` | `e7d3add006b0124c36a739acf3b71431cccc34fd` | [#177](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/177) | **404 / ABSENT** |
| `feature/v4-25-user-connections` | `7f4a2373954cffcc0c8d42b18203e33a9f26348e` | [#178](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/178) | **404 / ABSENT** |
| `feature/v4-25-user-create` | `3a6a41ef543bc2ae3591e73f09e4151f83838009` | [#180](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/180) | **404 / ABSENT** |
| `feature/v4-25-user-management-foundation` | `23ff19b013ba6339ae510120bdd3969065bad8d3` | [#176](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/176) | **404 / ABSENT** |
| `feature/v4-25-user-payments-activity` | `a2e82cc77ed9d801e3e7207d150b3adc09879be7` | [#179](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/179) | **404 / ABSENT** |
| `feature/v4-25-user-safety-subscription` | `3ff1de440f2fdf4246f60627086de6e9ee126ea3` | [#181](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/181) | **404 / ABSENT** |
| `feature/v4.11.0-node-onboarding` | `dd2744f309346875a0a6468e646d11801d56fc68` | [#17](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/17) | **404 / ABSENT** |
| `feature/v4.16-regression-hardening` | `14dd01729d59e6bf0190574d1254e29be1662fc0` | [#60](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/60) | **404 / ABSENT** |
| `feature/v4.17-openapi-contract-gate` | `a6dc3d1c2f7377d332fcb1fe015b11788d18c9a2` | [#64](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/64) | **404 / ABSENT** |
| `feature/v4.18-offsite-backup` | `45386133476507f20337aa8800366c13d7ec3b7b` | [#68](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/68) | **404 / ABSENT** |
| `feature/v4.19-safe-bot-self-update` | `fa0c21fd8f3c699f05b03216181cf61c8582bba5` | [#73](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/73) | **404 / ABSENT** |
| `feature/versioned-sqlite-migrations` | `20608d01a745a5a0d8a29ac8bab6deaa8a3dc906` | [#55](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/55) | **404 / ABSENT** |
| `fix/attention-navigation-role-heading-354` | `7bb726a31f32403e9fc1c710e62d2271b9733acb` | [#363](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/363) | **404 / ABSENT** |
| `fix/backup-master-fail-closed` | `dda781907b7319ad492865c39bb6438534eeb4af` | [#350](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/350) | **404 / ABSENT** |
| `fix/client-portal-callback-effective-flag` | `c8d1d3ac8df6a89012df42766168937fbbe9fdcc` | [#420](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/420) | **404 / ABSENT** |
| `fix/container-least-privilege-rollout` | `b51b5995af681d217086adae8a50dce92badcb36` | [#269](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/269) | **404 / ABSENT** |
| `fix/container-source-permissions` | `d460f78c708ff3498d034d0da92c930b34761b10` | [#279](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/279) | **404 / ABSENT** |
| `fix/history-secret-audit-fetch` | `c60baf0d975347bf854f9e3c6021663662ac503d` | [#265](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/265) | **404 / ABSENT** |
| `fix/inbound-input-validation` | `186b958cf6d8af7d6f37c794f19405046ae18483` | [#200](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/200) | **404 / ABSENT** |
| `fix/job-alert-repeat-context` | `cfc18797972226e9e0cb227e3e7664aef3543bcf` | [#361](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/361) | **404 / ABSENT** |
| `fix/master-backup-api-wal-acl` | `b1c4df9fa7f83ca5e3e64e52e37070b11e65b44f` | [#351](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/351) | **404 / ABSENT** |
| `fix/node-drain-cancel-navigation` | `a26233176467f23ed537d3e803c4db454389637c` | [#213](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/213) | **404 / ABSENT** |
| `fix/permission-aware-navigation` | `ec36268fa8affdd5e1a845e6930d27326abafacd` | [#228](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/228) | **404 / ABSENT** |
| `fix/qa352-direct-preview-import` | `5305583d4b995949755da4ebc7c05c94862ebead` | [#454](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/454) | **404 / ABSENT** |
| `fix/safari-subscription-assets-nginx` | `048fe4f3f67ebe4cd9d428d1c4d491acdf2f3e50` | [#300](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/300) | **404 / ABSENT** |
| `fix/stars-invoice-use-bot-display-name` | `31baa5427b8a7e0b7cd0e2a1070991b98916bba0` | [#347](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/347) | **404 / ABSENT** |
| `fix/stars-paid-invoice-cleanup-320` | `b525328d2de39b6a3c41b3a44b63c99bf0b99da8` | [#417](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/417) | **404 / ABSENT** |
| `fix/subscription-browser-blank-page` | `76ea0c926adf9805c89d03180baba9f5c6226dd5` | [#297](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/297) | **404 / ABSENT** |
| `fix/subscription-runtime-base-path` | `922af000227da4573ce7367a331d8c3bc40d0248` | [#298](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/298) | **404 / ABSENT** |
| `fix/trial-zero-limits-343` | `5608105300913eefa4fd5c671f99ddd148bc69a0` | [#367](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/367) | **404 / ABSENT** |
| `fix/v4-25-access-navigation-contract` | `b6fbd241054019c5ca9eb62fe253f19bcc4aac46` | [#183](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/183) | **404 / ABSENT** |
| `fix/v4-25-final-ui-contract` | `5c1d115007be49eaef30f6dec8ca5d68c2f44d08` | [#184](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/184) | **404 / ABSENT** |
| `fix/v4.20.8-inbound-capitalization` | `8d57c95c81d61d5c6be08300d50eb7744f2d9070` | [#128](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/128) | **404 / ABSENT** |
| `fix/v4.20.9-post-acceptance-ui-cleanup` | `6de9c6cf2ce1d5fed917c05a00cda560819ab46c` | [#131](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/131) | **404 / ABSENT** |
| `fix/v4.20.10-inbound-keyboard-density` | `b06832e9dfbf63e3f928f77abc13fa506c3fd409` | [#133](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/133) | **404 / ABSENT** |
| `fix/v4.21.1-display-time-consistency` | `faa1ff287dc4013b0c3de58970dee2220a0e87da` | [#140](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/140) | **404 / ABSENT** |
| `fix/v4.21.2-dr-logs` | `8613d075d078b6fd9159290d9314050db89e0b1b` | [#143](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/143) | **404 / ABSENT** |
| `fix/v4.25.8-navigation-owner-safety` | `f5fdb1284286396cb2a7023444da96d9d492473f` | [#205](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/205) | **404 / ABSENT** |
| `fix/v5-expired-customer-status` | `2d5b3fe24f9c6a2e2ffbc706e0ccfd43e1edd268` | [#312](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/312) | **404 / ABSENT** |
| `fix/v5-rc3-provider-access-status` | `41dacac830e26df181bbf7c4280a7611ca50d44e` | [#325](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/325) | **404 / ABSENT** |
| `fix/v5-rc3-quota-ui` | `bb3a326fa9ad908f59751bcdf2887fde6ccfc411` | [#318](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/318) | **404 / ABSENT** |
| `fix/v5-stars-refund-handler-import` | `f3b7f75fa375299f81e25c60174d9e273a72d13a` | [#329](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/329) | **404 / ABSENT** |
| `fix/v5-stars-refund-terminal-and-admin-totals` | `29596f9cdfcba0dfd8eccb275c5e0bcf8cd26f67` | [#335](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/335) | **404 / ABSENT** |
| `fix/v4250-acceptance-readonly-extend` | `4eeca5a076241ddafdb313f57dfc37c15a0b4246` | [#188](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/188) | **404 / ABSENT** |
| `fix/v4251-stabilization` | `837be548cad132b56669ce3ff06c995a1be5fec2` | [#189](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/189) | **404 / ABSENT** |
| `fix/v4252-subscription-compat` | `a78065522e402c0c848b4d500cc12690c09b7849` | [#191](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/191) | **404 / ABSENT** |
| `fix/v4253-incy-desktop-ua` | `453c146d438e2fc32c10b0dd7a10bf589f03d809` | [#193](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/193) | **404 / ABSENT** |
| `fix/v4254-streisand-plain-subscription` | `3a7c87c00c91f400d4ef4c90aa35c48a3fcb9c86` | [#195](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/195) | **404 / ABSENT** |
| `fix/v4255-streisand-force-raw` | `770607de34140d47a4d02b14d02bef5d5a2d9647` | [#196](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/196) | **404 / ABSENT** |
| `fix/v4256-revert-streisand-workarounds` | `03f3ff4d625c147ec5d4c96f3167516b3e1e82f6` | [#197](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/197) | **404 / ABSENT** |

## Завершение канонического checkpoint

Одноразовый workflow `.github/workflows/retire-verified-94-510.yml` и script `scripts/retire-verified-94-510.py` должны быть **удалены через отдельный docs-only PR с required `test`/`title` и squash/main read-back**, чтобы не допустить повторного запуска от следующего main CI. До этого следующая batch **BLOCKED**. Issue #510 остаётся **OPEN/PENDING** — остаточные historical refs и unknown external/dynamic dependencies не проверены полностью.

**Published:** `v5.0.0-rc.9`, immutable tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`. **Deployed:** rc.9 только operator-reported 2026-10-11 16:15 EEST, independent VPS read-back PENDING. **Accepted:** общий v5 NOT PASS. Удаление Git refs не является production acceptance.
