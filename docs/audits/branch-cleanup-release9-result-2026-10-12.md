# #510 — scoped deletion nine historical release refs: 9/9 PASS

## Время, baseline и среда
- 2026-10-12, Europe/Helsinki EEST UTC+03:00. One-shot [38257977966](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38257977966) начался **16:45:53 EEST**, завершился **16:46:43 EEST**, workflow `completed/success`. Выполнение только GitHub refs, без VPS/3x-ui/Telegram/Stars/refund/deploy/restart.
- Protected main baseline prior to PR #550: `96d3e63738f9501f5b8e744b4c5ad4760cf69184`; execution [PR #550](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/550) squash MERGED main `2cfe1062c397712eaa43863b14272e1e23ad8e57`. Original separate [failed 10-ref run 38256017221](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38256017221) остаётся **FAIL 9 individual PASS / 1 RETAIN**; там `retire-once` SKIPPED, DELETE 0/10. Не переписывать историю.
- [Immutable 9-ref manifest](branch-cleanup-release-9-verified-2026-10-12.json) blob `38b955ef82aa4af808366918527abe2d4f2a1ec2`; исходная `release/v4.12.0` с tracked dependency исключена из allowlist и сохраняется.

## Required PR CI, exact execution и postconditions
- PR #550 final head `b9961d34ed0d68b92e0f260f2578f63fdf05c7fb`: fresh read-only [strict preflight 38257435539](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38257435539) **PASS 9/9**; required `test` [38257435621](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38257435621) **PASS** после исправления русскоязычной строки Roadmap; required final `title` **PASS**, supply-chain audit [38257435558](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38257435558) **PASS**. Старые title/test FAIL остались в Actions как evidence исправления, не выданы за PASS.
- Post-merge main [Python checks 38257777285](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38257777285) **PASS**, supply-chain [38257777310](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38257777310) **PASS**. Only main successful checks and first-parent exact SHA activated `retire-once` run `38257977966`, job `114840878853`.
- Execution log: 9 x `PROOF PASS`, 9 x **`DELETED / VERIFIED`**, `BATCH9 RESULT verified_deleted=9/9`, completed/success. Writes only exact name/tip SHA with `git push --force-with-lease`, each exactly once; bounded read-only confirmations, no retry upon unknown.
- **Independent GitHub REST GET /branches/{exact name}: HTTP 404 for ALL 9/9** (в этом checkpoint). Independent full branch pagination after delete: **101 refs total / 100 non-main**; старый 108-ref inventory — **99/108 remain unchanged exact SHA** и только девять отсутствуют. One extra non-baseline `chore/execute-release-10-510-20261012` from closed-without-merge PR #548 remains PRESENT, intentionally not targeted and not proven safe-to-delete. `release/v4.12.0` remains PRESENT at exact `8ee5ab32db5db676ed59811ed0c5a0c4f756ee77`; protected `main` unchanged after deletion. Immutable `v*` tags not targeted.

## Поимённые девять verified absent

| Ветка | Tip SHA before delete | Merged PR | Independent REST postcondition |
| --- | --- | --- | --- |
| `release/v4-23-0` | `ef39ed8bfc771dc5ea211b2f60b55179614f9c04` | [#155](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/155) | **404 / ABSENT** |
| `release/v4-23-1` | `b4acd456d163fccae43fb8e4c1f275e0af6008a7` | [#156](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/156) | **404 / ABSENT** |
| `release/v4.10.1` | `b1c1e1a00115421641dbb7f1aabc4637457554ea` | [#16](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/16) | **404 / ABSENT** |
| `release/v4.11.0` | `8707f1a67469da802860f2e513cdf1db6585a435` | [#18](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/18) | **404 / ABSENT** |
| `release/v4.11.1` | `8006c5bed107667f981ba668d85bb80ac8b5d326` | [#23](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/23) | **404 / ABSENT** |
| `release/v4.13.0` | `afa770f443d60869e181092f82595e4117302a08` | [#27](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/27) | **404 / ABSENT** |
| `release/v4.13.1` | `a78e454a570a4c67df25012c8df936934d5b0b14` | [#30](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/30) | **404 / ABSENT** |
| `release/v4.13.2` | `1f77dc18a85801aa5024023485cc3f78718e4982` | [#38](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/38) | **404 / ABSENT** |
| `release/v4.14.0` | `d573cbaa61f85140c25b3ad29f630f5656fd3bee` | [#47](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/47) | **404 / ABSENT** |

## Disposition и блокеры
- Scoped **DELETE 9/9 PASS**. Previous **361 historical distinct ABSENT** + nine new exact names = **370 historical distinct ABSENT**; historical unknown executor attribution unchanged. **Global #510 OPEN/PENDING**: original 99 non-main refs plus additional unmerged work branch; retained PR/squash mismatches, no-PR/closed-unmerged, dependency-bearing `release/v4.12.0`, external/dynamic consumers. Не считать global cleanup PASS, stable v5 acceptance или publication/deploy result.
- Privileged one-shot workflow/script удаляются отдельным docs-only checkpoint; до required `test`/`title`, squash main, independent 404 этих двух файлов и Issue closure audit **следующий batch BLOCKED**.
- Published immutable `v5.0.0-rc.9` tag `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; Deployed rc.9 only operator-reported, independent VPS read-back PENDING; Accepted v5 NOT PASS.
