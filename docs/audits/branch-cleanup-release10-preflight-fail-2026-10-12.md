# #510 — strict 10-ref release branch preflight FAIL / 9 PASS / 1 RETAIN

- Дата: 2026-10-12 16:30 EEST (Europe/Helsinki, UTC+03:00).
- GitHub baseline: protected main `42bb1cfcef94a6e99b1841c74f4481e4a8a869a4`; PR #548 exact head `46e1784a1c227e806ff6199a6fdac5cd41a9a39b` **CLOSED WITHOUT MERGE**.
- Source: [GitHub Actions 38256017221](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38256017221), preflight job `114834179861`, **completed/failure**; `retire-once` skipped; **deleted 0/10 NOT RUN**.
- Read-only deep evidence: 9 full proofs PASS on original exact tip SHA/merged PR/squash file/status/blob/ancestry/dependency; `release/v4.12.0` **RETAIN**: `tracked source contains branch-name dependency` (exact SHA `8ee5ab32db5db676ed59811ed0c5a0c4f756ee77`, original PR #25).
- Nine individual PASS: `release/v4-23-0` #155; `release/v4-23-1` #156; `release/v4.10.1` #16; `release/v4.11.0` #18; `release/v4.11.1` #23; `release/v4.13.0` #27; `release/v4.13.1` #30; `release/v4.13.2` #38; `release/v4.14.0` #47. PASS этих 9 не разрешает удаление до нового immutable 9-ref manifest, повторного full preflight, required CI и post-merge main gates.
- Scoped safety mechanism **PASS fail-closed** при 1/10 exclusion; общий 10-ref deletion preflight **FAIL**. Не переписывать FAIL в PASS. Previous 361 historically ABSENT unchanged; current 108 original non-main refs remain.
- Risk: tracked dependency для 1 RETAIN, potential external/dynamic consumers для остальных, new PR/release refs требуют fresh check. #510 OPEN/PENDING.
- Published immutable `v5.0.0-rc.9` tag `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; deployed rc.9 operator-reported only, independent VPS read-back PENDING; v5 acceptance NOT PASS. No production operations.
