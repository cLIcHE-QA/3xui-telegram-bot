# #510 — фактическое удаление 96/96 и сохранение четырёх исключений

## Timestamp, baseline, scope

- Дата: **2026-10-12, Europe/Helsinki (EEST UTC+03:00)**. GitHub Actions run `38239750817` completed SUCCESS, final executor output 2026-10-12 **11:07:30 UTC / 14:07:30 EEST**. Независимые поимённые REST read-back выполнены после этого в той же сессии 2026-10-12; точное локальное время для них не записывалось.
- Применимая область: исключительно 96 historical branch refs из [immutable 96-ref manifest](branch-cleanup-verified-96-candidates-2026-10-12.json), derived from [original 100-ref manifest](branch-cleanup-next-100-dry-run-2026-10-12.json). GitHub REST/Actions evidence, **не VPS/production/Telegram/3x-ui**.
- Исходный read-only snapshot: protected `main` `6692005c1781221bf49512516e7fe81b81496bf2`, 298 refs до 100-ref prepare branch, 459 исторических PR, 0 open PR. [PR #537](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/537) synced original 100-ref dry-run into `main`.
- Исполняющий [PR #538](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/538): approved HEAD `45186080294fd452f0694cdde2c114df0e292343`, squash **MERGED** `main` `bce772881d0ff68a2502ba4c40cba14677b89085`. Required `test` PASS [38239097513](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38239097513), latest `title` PASS [38239124641](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38239124641), supply chain `audit` PASS [38239097450](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38239097450). Post-merge `Python checks` PASS [38239455901](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38239455901), audit PASS [38239455969](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38239455969).

## Исторические FAIL и решение по scope

- Первый PR preflight — **FAIL** из-за смешения manifest baseline и execution first-parent SHA; обнаружено до writes, исправлено отдельным PR commit, удалений 0.
- Второй полный исходный 100-ref preflight [38238613832](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38238613832) — **FAIL**: 96 scoped PASS, **4 RETAIN**, deleted=0. Исключения сохранены без изменения исходного manifest:

| Ветка (НЕ удалялась) | Причина / disposition |
| --- | --- |
| `fix/stable-bot-docker-network` | PR final file/status/blob mismatch; **RETAIN / REVIEW** |
| `fix/admin-ui-navigation-consistency` | PR final file/status/blob mismatch; **RETAIN / REVIEW** |
| `fix/v4.9.3-node-detail-counters` | PR final file/status/blob mismatch; **RETAIN / REVIEW** |
| `fix/release-tag-probe` | literal tracked source dependency; **RETAIN / REVIEW** |

- Derivative 96-ref immutable allowlist исключает все четыре и не разрешает их удалять. Окончательный независимый read-only preflight [38239097439](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38239097439), job `preflight` — **PASS 96/96**: `PROOF SUMMARY eligible=96 retained=4_excluded`, `DRY-RUN PASS 96/96; deleted=0`. Это включает exact-SHA/PR head+base/merged-main, PR files/status/blob ↔ one-parent squash, ancestry, tracked literal names и remote descendant safety checks.

## Фактическое исполнение

- [One-time workflow run 38239750817](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38239750817), job `retire-once` `114779153086`: **COMPLETED/SUCCESS**. Executor заново вывел `PROOF SUMMARY eligible=96 retained=4_excluded`, выполнил ровно 96 `git push --force-with-lease` ref-delete writes со строго указанным прежним SHA и bounded read-only подтверждением без повторного DELETE. В логе **96 ×** `DELETED / VERIFIED`, итог `BATCH96 RESULT verified_deleted=96/96`.
- После run отдельные GitHub REST `GET /repos/cLIcHE-QA/3xui-telegram-bot/branches/{exact name}` дали **HTTP 404 для каждого из 96** names. Полный независимый snapshot `GET /branches?per_page=100&page=1..3`: **100+100+2 = 202 refs**, включая protected `main` `bce772881d0ff68a2502ba4c40cba14677b89085`; **201 рабочих**. 96 именованных refs отсутствуют в inventory. Все четыре RETAIN refs **PRESENT**. Protected main, immutable `v*` tags и production не удалялись.
- Исходный snapshot перед этим batch 298 refs, net изменение **-96**, соответствует exact deletion manifest. Исторически до этого было **171 distinct historical refs ABSENT**; данный новый независимый disjoint 96-список добавляет 96, итого **267 ранее учтённых distinct refs ABSENT**. Исторический 100-ref partial FAIL со спорной атрибуцией 50 веток по-прежнему **не** стал PASS; 267 — cumulative observation, не 267 proven deletes одного запуска.

## Результат по каждому из 96 exact refs

| Имя ветки | SHA перед delete | Original merged PR | Результат независимого GitHub REST |
| --- | --- | --- | --- |
| `docs/agent-acceptance-issue-checkpoints` | `7160af4b0c3e07010efe6b9b08e563375af1e924` | #421 | **404** |
| `docs/plan-3xui-hosts-rc9` | `54b39deb5a40f44756b5391444f138d989b04d0a` | #423 | **404** |
| `docs/sync-hosts-422-main` | `92dbca1f187c434334315254c6f0a1abfb72fea6` | #425 | **404** |
| `docs/rc9-readiness-checkpoint` | `31426447345c7b9fdd5f14fe6de73a9644b8f13f` | #426 | **404** |
| `docs/read-only-baseline-20261011` | `276df0af3e9f51414246e65501a874112e61fe4b` | #427 | **404** |
| `docs/sync-3xui-contract-governance-428` | `bc069b7e66155458bf24e23251570ef5b0e9d2c0` | #429 | **404** |
| `docs/rc9-release-prep-checkpoint` | `8051360de8adf22738566776d5221fd8faf30f9f` | #431 | **404** |
| `docs/rc9-published-checkpoint` | `ae8651475b391c3f213e5e660fc00b61ba6bdb7b` | #432 | **404** |
| `docs/rc10-refunds-plan` | `2189bb276a85bd9f875f9177a2b5e326baf17f4c` | #435 | **404** |
| `docs/rc10-legal-support-psp-plan` | `cfe78357c4553d11238fe4c4a41779d0092aaad0` | #438 | **404** |
| `docs/platega-payment-link-contract` | `53e3a842678daf401442123caba5af76f4b33f82` | #439 | **404** |
| `docs/rc9-operator-deploy-checkpoint` | `041f9258fb8d0e9cd4f8bf79f8281213671a1c63` | #440 | **404** |
| `docs/rc9-hosts-visibility-checkpoint` | `a6121fdee882e67741b2614130a375d7614ee391` | #441 | **404** |
| `docs/rc9-netherlands-mapping-checkpoint` | `74ae09f683146ceac233d87df7170538b2fc22a6` | #442 | **404** |
| `docs/rc9-host-sources-acceptance` | `bb00c44fc310d8fdaa8829acbfd40a3a484f9db0` | #443 | **404** |
| `docs/rc9-422-closure-sync` | `941a1ce88f4d73fb3c23ab62472267fcb07ce305` | #444 | **404** |
| `docs/rc9-342-portal-off-callback-checkpoint` | `a6f10f501548b8a94d29b2415e320f8a86ec4884` | #445 | **404** |
| `docs/rc9-342-portal-restored-checkpoint` | `4528680e8fdf0ccbe5487510567277df171b2923` | #446 | **404** |
| `docs/rc9-342-readonly-acceptance` | `a2f4913644cd9676ac60699ff3516bda7e18eec7` | #447 | **404** |
| `docs/rc9-342-closed-status` | `110878302e73df79166a37e4cbc09256a65637e8` | #448 | **404** |
| `docs/rc9-352-readonly-preflight` | `4330f75a8ab1f634ef3da974711c912e971e7329` | #449 | **404** |
| `docs/rc9-352-isolated-smoke-result` | `7164e424138d8a579eced577fc31fa39628d07b6` | #451 | **404** |
| `docs/352-qa-runner-merged-sync` | `4a920c75c2999aa8473942965ff8f53cffb9f50e` | #453 | **404** |
| `docs/qa352-preview-pass-20261011` | `f1cedc4815f4477ee80fc0c815c4a2463a6967dc` | #455 | **404** |
| `docs/qa352-enroll-blocked-20261011` | `e97fbab1db03392993792ad60988b5fe63bf1db0` | #456 | **404** |
| `docs/qa352-getme-urlerror-20261011` | `64d4ff09e9e0d5dd895fc1f579a641b03b759a37` | #457 | **404** |
| `docs/qa352-ssl-verification-blocked-20261011` | `66e6efc893b1534de6cfb924dfb77c165d726129` | #458 | **404** |
| `docs/qa352-python-ca-paths-20261011` | `c23a8d2a9aab713cc0ac27029022e2968f676b50` | #459 | **404** |
| `docs/qa352-mac-ca-install-pass-20261011` | `7fbf945e7e835e9ed2636dece02d179243862713` | #460 | **404** |
| `docs/qa352-tls-post-ca-pass-20261011` | `079c37efe7d97651e69b1c5641275108e850cecc` | #461 | **404** |
| `docs/qa352-qa-private-enroll-pass-20261011` | `d36f8a19fa618ba661c559eb4a4bfc5e27b58c78` | #462 | **404** |
| `docs/qa352-first-telegram-delivery-evidence-20261011` | `02dae43803bbe2c51f600fa767bfc073e6ca3699` | #463 | **404** |
| `docs/qa352-telegram-synthetic-visual-4of4-20261011` | `982c2013e54c0a1f84b803a768a959dbd198a84a` | #464 | **404** |
| `docs/qa352-transport-confirmed-4of4-20261011` | `1e0e128dc59fa325a95c4d477c5b597011e35510` | #465 | **404** |
| `docs/qa352-risk-accepted-closure-20261011` | `3879d103409e9e4d7f81b2e02c9c5317d2c4df6c` | #467 | **404** |
| `docs/qa352-closed-followup-open-20261011` | `7d5e34fce161a98c31ac3eaf11182ae637894010` | #468 | **404** |
| `docs/rc9-acceptance-gates-waivers-index-20261011` | `8fab01793ac9e2d84a608424bc82001148c5aa6f` | #469 | **404** |
| `docs/rc11-client-portal-backlog-20261011` | `0f5ddefc215d6804ede5749fc2ad9fe2281d57e6` | #474 | **404** |
| `docs/future-tracks-issues-no-milestone-20261011` | `8eb289a57f20b1485ec838c24aff586b8a86e383` | #480 | **404** |
| `docs/rc9-scale-risk-code-review-20261011` | `e9c1bb6e6424bba67e2284d6810d8c98d8d899ff` | #481 | **404** |
| `docs/scale-issue-482-roadmap-20261011` | `4de4190329a4a7ea6c8bda0ede983cee0b1c64aa` | #483 | **404** |
| `docs/issue-first-tracking-rule-20261011` | `01647ad78e9f7b43682063f6d7c5f2232c76dca8` | #485 | **404** |
| `docs/issue-484-closure-20261011` | `bac07edb6f294043cc16acc191d458464b11f7f1` | #486 | **404** |
| `docs/node-sync-issue-487-20261012` | `d3d5d4eb3a127384193f00960a5e62b3c92a6b32` | #488 | **404** |
| `docs/aeza-warp-socks-vless-guide-20261012` | `d2e52bf7f1a0c34433294c71b02e62523c74a5c7` | #490 | **404** |
| `docs/sub-tls-nginx-readonly-checkpoint-20261012` | `00bed306aaf4c35019d9ea2125494ccef07fa848` | #492 | **404** |
| `docs/sub-tls-nginx-issue491-closure-sync` | `218eeb42d498aef79f10f7d47253b07f7cbbbb7a` | #493 | **404** |
| `docs/warp-issue489-closure-sync-20261012` | `accafeaea8b1ab2a0b9256d6fc05528ebf4996c2` | #494 | **404** |
| `docs/github-baseline-checkpoint-20261012-0130` | `68f25520ee6732f3248332bcac1267528c1d298f` | #495 | **404** |
| `docs/roadmap-future-issue-audit-20261012` | `79587fa9a8976be79f3d4da2071ca1354f0d89c3` | #508 | **404** |
| `docs/future-issues-closure-sync-20261012` | `56746ee597c86901677e1663a24270e8436701fe` | #509 | **404** |
| `docs/branch-lifecycle-audit-20261012` | `78d5f29727f4b4967311cf09cf17ff80f76858d4` | #511 | **404** |
| `docs/branch-retention-policy-20261012` | `e4de8b36c4dcdd0c2327eb417d8b774591198a95` | #513 | **404** |
| `docs/branch-dry-run-inventory-20261012` | `9a7dc1eca791e1e95594b330751869cb90de0798` | #514 | **404** |
| `audit/a011-production-acceptance` | `094dfc224f4ab819dde4754b400d7ef55e582b7b` | #281 | **404** |
| `audit/a012-production-acceptance` | `7c9e1e23625d42c56904fa45bf62590ea46a152d` | #282 | **404** |
| `audit/pre-public-cross-cutting` | `2db20516499d06b878481d0e8baa9310562824bb` | #283 | **404** |
| `audit/clean-room-acceptance` | `c8174517e963d09bdc66b27b95f856f34f68c43d` | #284 | **404** |
| `audit/final-v4-pass` | `eb8d4bf99ec4fd608596a9991fd2fe1b99be128d` | #285 | **404** |
| `audit/v5-launch-gate` | `ffc8e0122d3a42064a379a525c50a37f888f2b09` | #308 | **404** |
| `test/living-docs-release-scope-gates` | `6001b9aa33a4e33d7725786a9c0944dd7392b6d3` | #373 | **404** |
| `test/352-isolated-job-alert-lifecycle` | `c830916d603da8ddcf7818c927c67b0cb2b583af` | #450 | **404** |
| `test/352-qa-telegram-delivery` | `9fea79e08b16c522fe2dfb802a819bafacb863bb` | #452 | **404** |
| `ci/supply-chain-main-gate` | `7ffe500487d5df0ac0c893cf1d3b065c4099ba1c` | #274 | **404** |
| `legal/apache-2-license` | `f8e48f7a59ef450765a36f512580f2650ead335b` | #275 | **404** |
| `refactor/admin-navigation` | `7ba98fea89c2368eedee1f58faf4c1a3cb5dc8a4` | #80 | **404** |
| `refactor/node-ui` | `889a8bf7c6399c7b58fbe8d9c2f9257b01022426` | #81 | **404** |
| `refactor/node-onboarding` | `1692ed8c9aacff57dce4dba5638e09c1b2dff7ea` | #82 | **404** |
| `refactor/node-presentation` | `0747d0c45f76db6f0a214d3625329db239db0209` | #83 | **404** |
| `refactor/node-admin-router` | `4b0f5db853c5f0a0643f700804e10f2170e01e24` | #84 | **404** |
| `refactor/system-admin-router` | `f19f7d116b908bada2652930452c9afd3c2036b7` | #85 | **404** |
| `refactor/backup-admin-router` | `6e2fbf744fe41a5246dd6c5b72a39e7255aac92e` | #86 | **404** |
| `refactor/legacy-user-admin` | `83c670286063f8acf85bb966a8537bd61dc8dfa3` | #87 | **404** |
| `refactor/admin-users-router` | `6e35373a46fa6759e196d02ae9d5a1cb87f0858d` | #88 | **404** |
| `refactor/client-access-router` | `c05257f9d8f08e99ffda745cecfabbe0e3f740fa` | #89 | **404** |
| `refactor/admin-shell-router` | `70c8052fbd3dd2b42480bd0e3a9c3abadb720efa` | #90 | **404** |
| `refactor/app-runtime` | `66927838b2faef5432eb6ccb2a9c269490efefcb` | #91 | **404** |
| `fix/readiness-callback-routing` | `87f3ea394cedbd534d7e334c0e0a0d815a1abf1e` | #22 | **404** |
| `fix/host-control-startup-recovery` | `16bc72fe07d66a672bcc656ea8f452da08e50bc3` | #35 | **404** |
| `fix/recovery-alert-copy` | `27b4dfd7021d452f1f759360d84011f62c1d58d4` | #77 | **404** |
| `fix/roadmap-gate-v4191-2` | `292dc4ff440cb03609d31e76c376135a73fbd9a8` | #78 | **404** |
| `fix/admin-setup-release-version` | `d342721a8153b5f3da7f8d869759c1d77bcdb328` | #79 | **404** |
| `fix/ui-russian-operations` | `9a1b77abf4f2b431b6b2748f3537c6f133ef234f` | #94 | **404** |
| `fix/ui-russian-control` | `c34b298b8fb4bb7726440077aff4cfc48924447c` | #95 | **404** |
| `fix/ui-russian-updates` | `dcf9f9c00dcb8549908fe91e4e725753a946dbe2` | #96 | **404** |
| `fix/ui-russian-domain-followup` | `120ce436bf9c11efa50e4d0176976dd7a4a47d12` | #99 | **404** |
| `fix/ui-russian-final-audit` | `97537cc1c2555b46af61a7c38d15b3a8dc5b13e7` | #102 | **404** |
| `fix/ui-emoji-audit` | `8f2ab26951b1eb3df45f42eedc1419ced18008be` | #103 | **404** |
| `fix/admin-navigation-audit` | `1955646c72b9284c7bcbcf9b97e9b06343804827` | #104 | **404** |
| `fix/public-readiness-copy` | `d19ce4f7271b5f63badb804edd079abd85b9ff75` | #105 | **404** |
| `fix/v4.20.1-release-notes-sigpipe` | `2c1d86e19c481012db1aa90d97395b8a09945df5` | #107 | **404** |
| `fix/admin-navigation-parent-flows` | `0b4e9444aebfd6f24c28b0fa6db09dab46b5257a` | #109 | **404** |
| `fix/v4.20.2-production-smoke` | `086ee56eda3973376bb9ac14d759b9ebaccc654f` | #111 | **404** |
| `fix/v4.20.5-ui-consistency` | `f7bfd3e79f510f8cc11780e5d113974efe07158f` | #117 | **404** |
| `fix/v4.20.6-health-summary` | `0aa3b58a5fdf4165bc8d9f2b21b243cd5e8ccc31` | #121 | **404** |
| `fix/v4.20.7-inbounds-terminology-clean` | `adf4bfa66e59fff820d8b09c30ee393f40f5368e` | #125 | **404** |

## Disposition, риски, следующий checkpoint

**Scoped batch DELETE PASS 96/96; initial 100-candidate batch NOT 100 PASS (4 RETAIN). Общий Issue #510 OPEN/PENDING.** Остаются 201 рабочих GitHub refs на этом snapshot, в том числе 4 новые сохраняемые исключения, два ранее известных docs PR/blob mismatch `docs/russian-documentation` и `docs/v4.10-host-control-contract` и прочие требующие аудита. Наличие внешних/dynamic branch-name потребителей нельзя абсолютным образом доказать отсутствующим; residual risk ограничен согласованным scope. Никакой новый пакет не разрешён до docs-only required-CI checkpoint, squash merge, independent `main` read-back и audit статусов Issues. Одноразовый workflow/script следует удалить через этот же cleanup checkpoint во избежание повторных workflow_run.

**Release/Production:** Published immutable prerelease `v5.0.0-rc.9`, tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`. Deployed `rc.9` **operator-reported only** (2026-10-11 16:15 EEST), independent VPS read-back **PENDING**; overall v5 acceptance **NOT PASS**. Никаких deploy/restart/payment/refund/Stars smoke в этом scope.
