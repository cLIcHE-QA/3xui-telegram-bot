# v5.0.0-rc.22 — publication checkpoint без deployment

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-27 10:28 UTC+03:00; GitHub published_at `2026-10-27T07:26:17Z`
- **Окружение:** GitHub / CI / локальный synthetic Python3.12; без VPS/Telegram/provider операций
- **Цель:** подтвердить отдельный RC задачи #506 после implementation checkpoint #940, до следующего scope #564.
- **Версия и immutable tag/SHA:** `v5.0.0-rc.22` / `d7739ed8e71444b310e7dbc5bde83f7706dfdb83`; release-prep head `b3b40c54f2de8ec7b05c5b10b853cab3cb2c2b38`, base `4b25839b0ec16216b0683add25668d82bb8c77fd`.
- **Scope:** release-prep/required CI/release-scope1/1, GitHub health, main/publish workflow, immutable ref/APP_VERSION/unique PR provenance и точные canonical notes. Не production deployment или runtime acceptance.
- **Фактический результат:** PASS
- **Источник и evidence:** [release PR #941](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/941) MERGED; [PR Python40466360703](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40466360703), [final title40466775768](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40466775768), [main Python40466843720](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40466843720), [Publish40467088224](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40467088224) SUCCESS; [GitHub Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.22). Independent REST ref/release/version.py/commit-to-PR read-back и canonical renderer comparison.
- **Ограничения и остаточные риски:** PASS только release/offline scope. История — локальный журнал, без независимого Telegram/VPN read-back; текущий тариф не исторический snapshot. Retention policy и schema v15 не меняются. Фактический runtime UI/private ownership outcome после отдельно разрешённого deployment PENDING; overall v5 не принят.
- **Связанные Issues:** #506
- **Решение по Issues:** #506: keep_open
- **Следующий шаг:** required CI, squash merge и main read-back этого publication/Roadmap checkpoint, Issue evidence/closure audit; затем #564/rc.23. Deployment/собственные runtime outcomes отдельно в конце пула #930.
- **Раздельные состояния:** merged=#941 `d7739ed8e71444b310e7dbc5bde83f7706dfdb83`; published=v5.0.0-rc.22, prerelease=true/draft=false, `2026-10-27T07:26:17Z`; deployed=v5.0.0-rc.18.10 `dae205ac82762723448f93827b981f89ae622231` только operator-reported, independent VPS read-back PENDING; accepted=publication scoped PASS, собственный #506 live PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## Ожидаемое и полученное

Target ref rc.22 перед merge отсутствовал (GitHub404). Штатный workflow создал commit ref `d7739ed8e71444b310e7dbc5bde83f7706dfdb83`; это единственный merged PR #941 с точным title `release: v5.0.0-rc.22` и base main для tagged commit. version.py на этом SHA содержит `APP_VERSION = "5.0.0-rc.22"`. Release prerelease=true/draft=false; title/body точно совпадают с CHANGELOG renderer для tagged SHA после нормализации LF/trailing newline. Прежний rc.21 ref независимо прочитан после публикации: `35c1a11676bd7fedc1bf386e4f153a3ba454f6e8`, не перемещался. Ручного tag/Release и deployment не было.

Непосредственно перед merge официальные [GitHub summary](https://www.githubstatus.com/api/v2/summary.json) и [unresolved incidents](https://www.githubstatus.com/api/v2/incidents/unresolved.json), `2026-10-27T07:23:22.942004+00:00`: Actions/Git Operations/API Requests/Pull Requests operational, incidents0. Merge завершён `07:23:34Z`.

Release-scope **1/1**: только implementation PR #939 после rc.21. PR/main Python **1586 tests, 3 skipped**; локальная feature регрессия **1586 PASS, 16 skipped** (environment, включая отсутствие Nginx), targeted16, version/living/current release/semantic contracts63 PASS, compileall/OpenAPI/catalog/docs/diff/renderer PASS. [Fresh supply-chain40465276048](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40465276048) SUCCESS на implementation main `fae6cee587e10c22c5f6a055b4a7dd0e63413c77`; после него менялись только docs/version, dependency locks/Docker/base неизменны. Hash-pinned install, Trivy filesystem/container, actionable HIGH/CRITICAL gate и SBOM проверены штатным workflow.

Implementation/Roadmap checkpoint [#940](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/940) merged `4b25839b0ec16216b0683add25668d82bb8c77fd`, required [Python40465727360](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40465727360)/[title40466098846](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40466098846), [main Python40466152527](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40466152527) SUCCESS; independent main Roadmap read-back выполнен до release-prep. First title runs с ещё не подтверждённым code-CI checkbox не приняты за PASS; после Python success финальные checklist/title прошли.

## Проверка собственного acceptance #506

Минимальный Stars-first scope определён в актуальном Issue по #930; прежний planned rc.21 из 16.10 явно заменён rc.22. SQL ownership каждой записи/связанных Entitlement/refund, private-owner guards, read-only mode=ro, pagination8/stale Back, XTR/provider separation, missing/unknown/refunded/duplicate-event/deleted-account boundaries и Terms fail-closed проверены synthetic fixtures. Ни один history callback не вызывает provider/checkout/reconcile/refund/consent; реальные операции не выполнялись.

Собственный deployment и read-only targeted UI/ownership outcome по [CLIENT_SETUP](../CLIENT_SETUP.md#собственная-история-stars-506) ещё PENDING. Поэтому #506 OPEN/keep_open, без auto-close; #336 отдельно и не blocker. #885/#887/#890 и общий v5 acceptance не закрываются этим RC. Deployed/Accepted projection сохраняется; поздняя установка требует cumulative upgrade/config/agent review и отдельного разрешения. Старые HWID PASS и waived burst не повторялись.
