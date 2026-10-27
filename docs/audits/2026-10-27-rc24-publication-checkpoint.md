# RC24 — публикация source-only foundation #947

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-27 16:54 UTC+03:00
- **Окружение:** GitHub / CI / локальный offline read-back; без VPS/Telegram/provider операций
- **Цель:** подтвердить immutable publication RC24 одной самостоятельной задачи #947, не завершать весь #874.
- **Версия и immutable tag/SHA:** v5.0.0-rc.24 `d7e224b48b23a315c389c290594c975dba2f9684`, Published 2026-10-27T13:49:49Z; release PR #953 exact head `5e750225fddc87c364a16e0f0f58be755df12441`.
- **Scope:** source foundation/schema16, release-scope, required PR/main/publisher, tag/ref/version/notes/unique release-PR provenance, Issue own-scope review и текущие living docs. Не runtime delivery/production acceptance.
- **Фактический результат:** PASS
- **Источник и evidence:** implementation [#951](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/951) `114619c9086d4e2dfff263b04ca75467c6a3862e`; implementation checkpoint [#952](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/952) `de0541fed555f290144bcc0075b1651d15e6c7cb`; release [#953](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/953) MERGED 2026-10-27T13:45:37Z. [Python40514125901](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40514125901) SUCCESS (1616 tests/3 skipped), [title40514744813](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40514744813) SUCCESS; [main40514910162](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40514910162) и [Publish40515480760](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40515480760) SUCCESS. GitHub release/ref/commit-to-PR/raw version read-back и canonical renderer notes equality подтверждены 2026-10-27 16:50 UTC+03:00.
- **Ограничения и остаточные риски:** #948/#949/policy #501, UI/queue/abuse/privacy/allowlists/deployment/pilot остаются PENDING у parent #874. Все категории delivery0/unapproved, нет runtime observation/worker/transport. Source-only собственный scope #947 не требует реальных sends. Additive schema16 ещё не применена на VPS; старый код15 после upgrade остановится, поздний cumulative deploy/recovery требует отдельного разрешения.
- **Связанные Issues:** #947, #874
- **Решение по Issues:** #947: keep_open, #874: keep_open
- **Следующий шаг:** required CI/squash этого publication checkpoint, independent main read-back; затем собственный closure audit #947 по всем семи acceptance группам и синхронизация Issue/Roadmap до #948. Пока этот checkpoint не merged, последний собственный критерий #947 остаётся PENDING.
- **Раздельные состояния:** merged=#951/#953; published=RC24/schema16 `d7e224b48b23a315c389c290594c975dba2f9684`; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15, independent VPS read-back PENDING; accepted=source/publication scoped PASS, parent runtime PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## Независимые gates

Официальные GitHub Status summary и unresolved incidents прочитаны после green release test/title непосредственно перед squash: 2026-10-27T13:45:27.901511Z, Actions/Git Operations/API Requests/Pull Requests operational, unresolved incidents0; squash13:45:37Z. Workflow не обходился, tag/Release вручную не создавались.

Release-scope в PR CI: PASS, один PR #951 после immutable rc.23. Локальный первый scope запрос использовал устаревший tag-cache (rc.19), был FAIL; после fetch опубликованного rc.23 `110bfc4ce9131a366be7ca3503e22ee6349c7372` повтор PASS1/1. Это исправление локального baseline, не waiver. Старый rc.23 Git ref повторно прочитан после новой публикации — тот же SHA.

Release prerelease=true/draft=false, title/body непустые и точно совпадают с каноническим CHANGELOG renderer на release SHA. Git ref type=commit и SHA совпадает с main release squash. Commit-to-PR API возвращает ровно один merged main release PR #953 с точным title release: v5.0.0-rc.24; version.py на этом SHA — APP_VERSION 5.0.0-rc.24.

Implementation final-head targeted19/full1616 (16 local environment skips), PR CI1616/3 skipped PASS; source regression/security review см. [implementation audit](2026-10-27-947-campaign-foundation-postmerge-checkpoint.md). Его PENDING main/supply-chain на момент16:29 затем завершены: main40512294154 и fresh supply-chain40512333699/job122217153355 SUCCESS, все lock/scan/build/SBOM/vulnerability gates PASS. Checkpoint #952 test40512620582/title40513479201/main40513803691/idempotent Publish40514249337 SUCCESS, independent main/file read-back PASS. Это последующее подтверждение, старый датированный audit не переписывался.
