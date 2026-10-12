# #510 — выполненный пакет SHA-lease cleanup 50/50 (2026-10-12)

## Scope и provenance

- **Дата:** 2026-10-12, Europe/Helsinki, EEST (UTC+03:00). Run завершился 13:09:50 EEST (10:09:50 UTC); отдельные GitHub API read-back выполнены после завершения в тот же день, точное время запросов не логировалось.
- **Target:** только 50 исторических `docs/*` branches из immutable [50-ref manifest](branch-cleanup-next-50-dry-run-2026-10-12.json); никаких VPS/Telegram/production операций, платежей, release/tag изменений или удаления protected `main`.
- **Основание:** [Issue #510](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/510) (остаётся OPEN), [PR #535](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/535), PR head `94c446b2b440481a4258479dba851ed87821f8b1`, squash `main` `22f3a4550f4f1dded4c77720c71d445277c6b629` (2026-10-12 13:03 EEST). Workflow first-parent prerequisite `635453d7694cd73192b363106f7c745f999b4e96`.
- **PR checks:** required `test` [38233567885](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38233567885) PASS, latest required `title` [38233826180](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38233826180) PASS (ранний `title` FAIL сохранён как отдельный факт), read-only `preflight` [38233568098](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38233568098) PASS 50/50, supply-chain [38233567679](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38233567679) PASS.
- **Post-merge:** `Python checks` [38233866941](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38233866941) PASS, [Supply-chain audit 38233866931](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38233866931) PASS. [One-shot execution 38234063682](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38234063682), job `retire-once` `114760283380`, `COMPLETED/SUCCESS`: `PROOF SUMMARY eligible=50 retained=0`, по одному exact-SHA `--force-with-lease` на ref, 50 строк `DELETED / VERIFIED`, итог `BATCH50 RESULT verified_deleted=50/50`. GitHub Actions log — прямой источник действия; его итог независимо сверялся ниже.

## Независимый read-back GitHub (только этот пакет)

- **PASS 50/50:** независимые GitHub REST `GET /repos/cLIcHE-QA/3xui-telegram-bot/branches/{exact-name}` вернули HTTP **404 по всем 50** distinct names ниже. Это отдельная проверка после Actions, а не только доверие stdout job.
- **PASS:** полная пагинация `GET /branches?per_page=100&page=1..5`: длины **100, 100, 98, 0, 0**, **298 всего**, из них **297 рабочих** и 1 protected `main`; ни одного из 50 names в списке нет. `main` по-прежнему `22f3a4550f4f1dded4c77720c71d445277c6b629`.
- **RETAIN / PASS сохранности:** две ранее исключённые PR/blob mismatch ветки `docs/russian-documentation` и `docs/v4.10-host-control-contract` всё ещё присутствуют. Исходная branch PR #535 автоматически удалена после merge (только проверка её отсутствия в полном списке).
- **Публикация/production не менялись:** последний опубликованный GitHub Release `v5.0.0-rc.9`, immutable tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db` (GitHub REST `git/ref/tags`); deployed `rc.9` — **только operator-reported** 2026-10-11 16:15 EEST, независимый VPS read-back **PENDING**, overall v5 acceptance **NOT PASS**.

## 50 именованных результатов

| Branch из immutable manifest | Ожидаемый исходный SHA | Merged PR | Независимый GET |
| --- | --- | --- | --- |
| `docs/v5-rc5-reconciliation-and-rc6-status` | `fa0ef4abf09003540fa8581eaed1585972f19136` | #340 | **404** |
| `docs/v5-admin-settings-review` | `2de080e12ef1ef44994cde58a7763a0a73d5b752` | #344 | **404** |
| `docs/v5-rc6-ownership-canary` | `7210caf46e13ac3b31a7029c8af145ab8f37bbb6` | #346 | **404** |
| `docs/v5-rc6-post-canary-fix-backlog` | `eab829444ae030a009e923ce4794c7d6383fc387` | #358 | **404** |
| `docs/rc7-backup-acceptance-evidence` | `17c933336fc28d17e06d5119d5649c343372d804` | #360 | **404** |
| `docs/cloudflare-warp-runbook-357` | `7a18cd74da982dc48834fe9cf32d8dc722978e2b` | #366 | **404** |
| `docs/roadmap-release-acceptance-l10n-audit` | `8976fe856d9ef4083d4f72c1c51402a6112b01f9` | #369 | **404** |
| `docs/roadmap-acceptance-ledger` | `fb4b10986433580b34fdfeb174aa93deddd5807b` | #370 | **404** |
| `docs/reconcile-current-living-docs` | `f7ddeeaf793bd1b5314ec3092279d450f0fe8435` | #372 | **404** |
| `docs/security-v5-rc-limited-support` | `a0a4243214c3fe9de4cf0e58a1c382602e3170f8` | #374 | **404** |
| `docs/client-portal-controlled-pilot-setup` | `3b1d562f62621ada3eb592b9f350fc74acaaaefb` | #375 | **404** |
| `docs/v5-trial-expiry-20261010` | `eab797147576d62a31da2125c63e0529c936fb52` | #376 | **404** |
| `docs/docker-hub-status-diagnostics` | `4125816c46b2b8c49cb4e741eec58771d3d05e87` | #377 | **404** |
| `docs/v5-order3-provider-reconciliation-20261010` | `eac3521727abe304806397238812165d902af365` | #379 | **404** |
| `docs/v5-paid-customer-ui-20261010` | `600a838c105062fd43766fea5a70b9ff174f9604` | #380 | **404** |
| `docs/v5-isolated-ownership-smoke-20261010` | `cc6807dc0a51dadd821b65c1f470e6edf0b2f152` | #381 | **404** |
| `docs/v5-tempdb-handler-ownership-20261010` | `00b491a1810573a8437e2d5538d37f10f901e7ec` | #382 | **404** |
| `docs/v5-offline-callback-rbac-smoke-20261010` | `c6b5d906068988086167f28f281dbdc56073fa72` | #383 | **404** |
| `docs/v5-dispatcher-offline-smoke-20261010` | `d0f1e21386cb6d6b51fd11a0950393a7e60d1e08` | #384 | **404** |
| `docs/v5-quota-reset-no-replay-offline-20261010` | `b22472cee81a17586edd0ea445582e82027370b0` | #385 | **404** |
| `docs/v5-commerce-offline-regression-20261010` | `d0a7a5bc6ae2c1dfda05ba4236ca680582ad2303` | #386 | **404** |
| `docs/v5-stars-isolated-regression-20261010` | `0b6259cba53c3a8ae7f92cc111cb6f91ac52b8cd` | #387 | **404** |
| `docs/v5-stars-kill-switch-offline-20261010` | `6297f525b281f01aea5db610b8acfdd0c808c34d` | #388 | **404** |
| `docs/v5-provider-outage-recovery-20261010` | `04a9e4264ffb228c29870c32e96db7393365c9ff` | #389 | **404** |
| `docs/v5-scheduled-backup-job-pass-20261010` | `d0651ba60ea0aa366db3ae4c73310cded0ebfb77` | #390 | **404** |
| `docs/v5-scheduled-archive-deep-check-20261010` | `deacc86ef4b85be0a6b49aad33fcf4039c8cc5f1` | #391 | **404** |
| `docs/v5-offsite-97-independent-linkage-20261010` | `20a356f80312cd52dd58db1fff85d74acdefbbc9` | #392 | **404** |
| `docs/v5-isolated-restore-preflight-20261010` | `f762c0016e4a24d5af440d4bfed265ff5a348df5` | #393 | **404** |
| `docs/v5-recovery-97-archive-linkage-20261010` | `040be4c835e9da32a8a8e906f871398b5d544673` | #394 | **404** |
| `docs/v5-rc7-recovery-component-startup-20261010` | `cdb76a200939f101bf8d9d7c13254c11263c1f1d` | #395 | **404** |
| `docs/recovery-drill-artifact-cleanup-20261010` | `6766cf68bc9790b4b3f93b6c477090226ecd1db4` | #396 | **404** |
| `docs/v5-rc7-isolated-container-process-pass-20261010` | `9fad528f68acf1a35cfdfc195645e3f3d689b9cf` | #397 | **404** |
| `docs/v5-master-xui-isolation-preflight-20261010` | `24b9f674a1139e74cadf67a39823c821f546865f` | #398 | **404** |
| `docs/correct-rc7-dr-host-identity-20261010` | `f3f53db4a175d71e2b10d45ee453261f322d4232` | #399 | **404** |
| `docs/record-master-cleanup-and-dr-waiver-20261010` | `b4da705df678f84ee76318ad934f6d7df8e26e49` | #400 | **404** |
| `docs/roadmap-current-rc7-acceptance-20261010` | `9c97d1e365b218f6bef5918d5147af8bbe904df4` | #401 | **404** |
| `docs/record-real-telegram-ab-canary-20261010` | `f51c24e8e75aa7eb4448b4c964e7c4d97be44f8c` | #402 | **404** |
| `docs/v5-rc7-smoke-current-main-20261010` | `e1b639f58b152b4513003f68f445ce47a4e827a6` | #404 | **404** |
| `docs/close-334-stars-summary-20261010` | `bc5a17e71f29bb2961a061e320547534deb6c6ad` | #405 | **404** |
| `docs/close-333-refunded-stars-20261010` | `fd3b8453b30f244f40156c1565e917c46993110f` | #406 | **404** |
| `docs/stars-invoice-ui-rc7-20261010` | `bfd5262208744eb21ef6e538039ad76315279c7f` | #407 | **404** |
| `docs/accept-backup-fixes-348-349-20261010` | `ea3921f6896e91c836dd004c744ace358a8978ba` | #408 | **404** |
| `docs/stars-sqlite-ledger-reconciliation-20261010` | `93bb065a12c438a031a33e82b6d8c8928d3eeb86` | #409 | **404** |
| `docs/v5-client-subscription-refresh-smoke-20261010` | `299ef84c95634af0aeda4af62389f94e257622c9` | #410 | **404** |
| `docs/v5-nonpilot-telegram-auth-denial-20261010` | `d270e74f818c973988de3ad40f88bf82ce0b547a` | #411 | **404** |
| `docs/v5-nonpilot-subscription-command-denied-20261010` | `afb07907cc17080ff0a8397d70dfd998a7f9b2e8` | #412 | **404** |
| `docs/v5-telegram-burst-transport-waiver-20261010` | `09191322e02e3ce173c704406312c6c577970aa8` | #413 | **404** |
| `docs/v5-a002-refund-unknown-and-quota-success-recovery-20261011` | `4c3a450606132571ddd2b07e0c67d9e421aa3c4e` | #414 | **404** |
| `docs/v5-a002-cross-process-recovery-20261011` | `180fa527546f75aad2f0ebd38deabca3a94544e2` | #415 | **404** |
| `docs/rc8-production-smoke-evidence` | `d0dc7df9540ab9d3ee61a70be08903c1881ccb42` | #419 | **404** |

## Ограничения и обязательный checkpoint

**Этот batch: DELETE PASS 50/50. Общий #510: OPEN/PENDING.** Ранее было **121 различных исторически отсутствующих refs** (из них 50 с operator-reported attribution без независимого per-ref execution log); плюс 50 из данного, однозначно подтверждённого не пересекающегося пакета = **171 ранее учтённых refs ABSENT**. Старый 100-ref execution остаётся `FAIL/PARTIAL`, не превращается в PASS.

Несколько сотен других рабочих refs требуют отдельного fresh dry-run/provenance review. Нельзя считать доказанным отсутствие внешних/dynamic branch consumers; два blob-mismatch refs остаются RETAIN, другие исключения и downstream dependencies нуждаются в ручном решении. Операции над следующим batch запрещены до успешного docs-only PR с required `test`/`title`, squash merge, read-back `main` и сверки Issue. Штатный one-shot workflow/script следует удалить в том же документальном checkpoint, чтобы будущие `main` `Python checks` не запускали повторный cleanup. Полный #510 закрывать нельзя.

**Evidence scope:** GitHub REST, GitHub Actions, immutable manifest и PR. Локальный working tree и VPS/3x-ui/Telegram не проверялись; новых production smoke не было.
