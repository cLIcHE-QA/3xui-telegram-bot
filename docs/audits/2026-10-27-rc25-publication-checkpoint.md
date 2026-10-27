# RC25 — публикация source-only очереди #948

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-27 21:02 UTC+03:00
- **Окружение:** GitHub / CI / локальный offline read-back; без VPS/Telegram/provider операций
- **Цель:** подтвердить immutable RC25 одной самостоятельной source-only задачи #948; сохранить отдельные runtime gates parent #874.
- **Версия и immutable tag/SHA:** v5.0.0-rc.25 `1c0854c9b416a2d0f2ccbe9083d62d88794307ed`, Published 2026-10-27T17:59:45Z; release PR #958 exact head `738e6782f6677c709c91f9c54d1034ad2799c967`.
- **Scope:** source/schema17, release-scope, required PR/main/publisher, tag/ref/version/notes/unique release-PR provenance, собственный Issue review и living docs. Не реальная доставка или production acceptance.
- **Фактический результат:** PASS
- **Источник и evidence:** implementation [#956](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/956) `9ac41354167a3b12a35149ebcfb396fe4065cceb`; implementation checkpoint [#957](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/957) `860e9940695ac947d60fe01e945b06fd021d307e`, independent main/Roadmap read-back. Release [#958](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/958) MERGED 2026-10-27T17:54:36Z; [Python40554017568](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40554017568) job122365082827 SUCCESS (1659 tests/3 skipped), [title40554859980](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40554859980) SUCCESS. [Main40554992199](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40554992199) job122368540729 и [Publish40555725657](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40555725657) SUCCESS; main1659/3 skipped. GitHub Release/ref/commit-to-PR/raw version read-back и canonical renderer title/body equality независимо подтверждены 2026-10-27 21:00 UTC+03:00.
- **Ограничения и остаточные риски:** runtime observation/UI/Bot API adapter #949, policy #501, privacy/abuse/allowlists, deployment/pilot parent #874 PENDING. Worker/transport не зарегистрированы, OFF/DENY_ALL; fake policy не согласие/доставка. Source-only scope #948 не требует реальных sends. Schema17 на VPS не применялась; поздний cumulative upgrade от deployed15 и recovery требуют отдельного разрешения, downgrade16/15 после17 блокируется.
- **Связанные Issues:** #948, #874
- **Решение по Issues:** #948: keep_open, #874: keep_open
- **Следующий шаг:** required CI/squash этого publication checkpoint, independent main read-back; затем собственный closure audit #948 по семи acceptance группам и Issue/Roadmap sync до #949. Последний собственный критерий #948 пока PENDING, этот документ ещё не main.
- **Раздельные состояния:** merged=#956/#957/#958; published=RC25/schema17 `1c0854c9b416a2d0f2ccbe9083d62d88794307ed`; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15, independent VPS read-back PENDING; accepted=source/publication scoped PASS, parent/runtime PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## Независимые gates

Официальные GitHub Status summary и unresolved incidents прочитаны после зелёных required test/title непосредственно перед squash: 2026-10-27T17:54:27.898629Z, Actions/Git Operations/API Requests/Pull Requests operational, unresolved incidents0; squash17:54:36Z. Tag/Release созданы только штатным workflow, проверки не обходились.

Release-scope в PR CI и независимом локальном API gate: PASS, ровно один PR #956 после immutable rc.24. Локальный tag-cache предварительно проверен: rc.24 `d7e224b48b23a315c389c290594c975dba2f9684`. После новой публикации старый rc.24 Git ref повторно прочитан — тот же SHA. Исключений release-scope нет.

Release prerelease=true/draft=false, title/body непустые и точно совпадают с CHANGELOG renderer на release SHA. Git ref type=commit и SHA совпадает с release squash; commit-to-PR API возвращает ровно один merged main release PR #958 с точным title release: v5.0.0-rc.25. version.py на этом SHA — APP_VERSION 5.0.0-rc.25. Publication не выполняет deployment.

## Source evidence и собственная граница

[Implementation audit](2026-10-27-948-campaign-queue-postmerge-checkpoint.md) сохраняет первоначальный checkpoint18:39. Его PENDING main Python40532243318 затем подтверждён SUCCESS18:40; свежий main supply-chain40532243404/job122287913522 SUCCESS, все lock/install/scan/build/SBOM/vulnerability gates и IANA UID10001 guard PASS. PR #956 Python40531192474/title40531988045/supply-chain40531192410 SUCCESS. Checkpoint #957 Python40533236623/title40534001162/main40553585182/idempotent Publish40554312639 SUCCESS; independent main/Roadmap read-back PASS.

Final release tree: локальный full unittest1659/16 environment skips PASS (83.315s), targeted release/docs66 PASS; CI1659/3 skipped. Compileall, OpenAPI55, command catalog, Living Docs/language, documentation semantics/governance, diff --check и независимый GitHub reconciliation PASS (до publication: Published24/referenced76/status assertions40/active40). Это CI/GitHub evidence, не VPS attestation.

Семь собственных групп #948 сверены: forward-only17/immutable state и operation dedup; explicit UTC/IANA/DST; source-only OFF/DENY_ALL без runtime/Bot API; durable intent/unknown/no replay; отдельный budget и bounded безопасные429/terminal403/stop races; isolated regression/privacy; required checks/docs/immutable RC. Финальный publication/main checkpoint остаётся незавершённым до merge этого PR; Issue намеренно OPEN/keep_open. Parent #874 этим source PASS не закрывается.
