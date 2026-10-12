# #510 — результат первого удаления исторических веток (пилот 3/3)

**Дата результата:** 2026-10-12 10:20:48 Europe/Helsinki (EEST, UTC+03:00). **Источник:** GitHub Actions run [38217186189](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38217186189), GitHub REST независимый read-back веток. **Scope:** только три временных Git branches, без изменений GitHub release tags, runtime/production/VPS/Telegram.

## Provenance / preflight / exact SHA

- Перед пакетом: protected `main` `8684135fa58dd20ceee7fb0725c51bdb31a60d52`; [Roadmap checkpoint PR #520](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/520) merged, required `test`/`title`, post-merge `Python checks` и #510 Issue audit PASS.
- Manifest: [branch-cleanup-pilot-510-2026-10-12.json](branch-cleanup-pilot-510-2026-10-12.json), **ровно 3 refs** `name → SHA` с неизменяемой полной SHA `37b1c700c846791b66a893843e1c68063ab92a6a`.
- Read-only GitHub REST pre-PR: все 3 branches существовали и были unprotected, head SHA совпадали, `compare(main...sha)` = behind, `ahead_by=0` (все commits достижимы из main); GitHub `pulls?head` и `pulls?base` для каждой дали пустой список. Исторический scoped 49-file scan ранее не нашёл операционных literal refs.
- [PR #521](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/521) head `4e5808d39c3cb7143411d95fc49c08c57e2f65d7`: PR read-only preflight **PASS 3/3** [run 38216775728](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38216775728), required `test` **PASS** [38216775778](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38216775778), latest required `title` **PASS** [38216984619](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38216984619), security `audit` **PASS** [38216775774](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38216775774). Squash **MERGED** в `main` `6e42dcd0f8dff011fe6398d468ba53837929e782`; post-merge main `Python checks` **PASS** [38217033193](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38217033193), Supply-chain audit **PASS** [38217033223](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38217033223).
- После main CI: one-shot `workflow_run` [38217186189](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38217186189) **completed / success**. На exact successful-CI commit и expected first-parent SHA проверены main identity, все refs (protected=false, exact SHA, ancestry, no associated PR head/base), отсутствие literal tracked source dependencies вне исторических audit/Roadmap; повторная per-ref проверка перед delete; каждое удаление выполнено через server-side `git push --force-with-lease=refs/heads/name:SHA origin :refs/heads/name` (без неатомарного REST DELETE), затем GitHub GET branch 404 + `git ls-remote` отсутствие.

## Результат (не только план)

| Удалённая Git branch | Перед удалением (exact tip SHA) | Post-delete GitHub REST |
| --- | --- | --- |
| `chore/github-branch-gc-510` | `37b1c700c846791b66a893843e1c68063ab92a6a` | **404 Branch not found / PASS** |
| `docs/branch-policy-and-inventory-510-20261012` | `37b1c700c846791b66a893843e1c68063ab92a6a` | **404 Branch not found / PASS** |
| `docs/git-branch-lifecycle-policy-510` | `37b1c700c846791b66a893843e1c68063ab92a6a` | **404 Branch not found / PASS** |

**Scoped disposition: DELETION PASS 3/3.** Независимый connector GET /branches/{name} дал 404 по всем трём после завершения workflow; `main` остался `6e42dcd0f8dff011fe6398d468ba53837929e782`. Ни tag, Release, production deployment, payment/refund, restore, restart, Node, Master или settings не менялись этим пакетом.

## Риски / остаётся PENDING

1. **#510 OPEN/PENDING в целом:** три подтверждённых удаления — маленькая часть сотен исторических refs. Нет blanket authorization на deletion для десятков refs без поштучного immutable manifest, PR/patch equivalence, unique-commit/ancestry и dependency review; closed-unmerged и diverged branches оставляются. External/branch-name/dynamic consumers за пределами проверенного tracked source не могут быть независимо исключены.
2. Source code workflow/script был **одноразовым** и удаляется из `main` тем же следующим **Roadmap checkpoint PR**; проверка успешного отсутствия этих двух файлов в main выполняется после merge, не подменяется намерением.
3. Нужно синхронизировать результат в верхнем `docs/ROADMAP.md` через отдельный docs-only PR с required `test`/`title`, squash merge и independent main read-back; добавить этот evidence в Issue #510, сравнить Roadmap↔Issues и только потом следующий пакет.
4. Published остаётся immutable `v5.0.0-rc.9` tag `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`, deployed лишь operator-reported rc.9, independent VPS read-back PENDING; overall v5 acceptance NOT PASS, G-01…G-11 без изменения, W-01/W-02 waived NOT PASS.

**Next (только после текущего checkpoint):** на базе нового main отдельно проверить следующий ограниченный набор предковых/no-PR refs либо stronger merged-PR candidates. Больше не удалять старые refs без отдельного SHA-leased plan, complete per-ref verification и последующего Roadmap/Issue checkpoint.
