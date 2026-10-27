# v5.0.0-rc.23 — publication checkpoint без deployment

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-27 11:17 UTC+03:00; GitHub published_at `2026-10-27T08:15:15Z`
- **Окружение:** GitHub / CI / локальный synthetic Python3.12; без VPS/Telegram/provider операций
- **Цель:** подтвердить отдельный RC задачи #564 после implementation checkpoint #944, до следующего scope #874.
- **Версия и immutable tag/SHA:** `v5.0.0-rc.23` / `110bfc4ce9131a366be7ca3503e22ee6349c7372`; release-prep head `82e4649edd61672fbb76848debc0315286ea4302`, base `90d3d09d016cc3bb8d64568512428f4c89655be9`.
- **Scope:** release-prep/required CI/release-scope1/1, GitHub health, main/publish workflow, ref/APP_VERSION/unique PR provenance и точные canonical notes. Не deployment или runtime acceptance.
- **Фактический результат:** PASS
- **Источник и evidence:** [release PR #945](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/945) MERGED; [PR Python40471386366](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40471386366), [final title40471783798](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40471783798), [main Python40471881271](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40471881271), [Publish40472193245](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40472193245) SUCCESS; [GitHub Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.23). Independent REST ref/release/version.py/commit-to-PR read-back, canonical renderer comparison.
- **Ограничения и остаточные риски:** PASS только release/offline scope. Telegram global command registry не менялся и не считается очищенным. Типизированные legacy handlers/guards сохранены; новая видимость deployed UI не проверена. Схема v15/env/порты/dependencies неизменны, overall v5 не принят.
- **Связанные Issues:** #564
- **Решение по Issues:** #564: keep_open
- **Следующий шаг:** required CI, squash merge и independent main read-back этого publication/Roadmap checkpoint, Issue closure/state audit; затем #874/rc.24. Собственный поздний deployment/визуальный outcome справки отложен в конец #930, старые N03/guards/roles не повторять без finding.
- **Раздельные состояния:** merged=#945 `110bfc4ce9131a366be7ca3503e22ee6349c7372`; published=v5.0.0-rc.23, prerelease=true/draft=false, `2026-10-27T08:15:15Z`; deployed=v5.0.0-rc.18.10 `dae205ac82762723448f93827b981f89ae622231` только operator-reported, independent VPS read-back PENDING; accepted=publication scoped PASS, собственный #564 visibility outcome PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## Publication и provenance

Ref rc.23 перед merge отсутствовал (GitHub404). Штатный workflow создал commit ref `110bfc4ce9131a366be7ca3503e22ee6349c7372`, единственный merged PR для tagged commit — #945 с exact title `release: v5.0.0-rc.23` и base main. Tagged version.py: `APP_VERSION = "5.0.0-rc.23"`. Release prerelease=true/draft=false; title/body точно совпали с canonical CHANGELOG renderer для tagged SHA после нормализации LF/trailing newline. Прежний rc.22 ref независимо прочитан после publication: `d7739ed8e71444b310e7dbc5bde83f7706dfdb83`, не перемещался. Ручного tag/Release, deployment и реальных Telegram/provider/платёжных операций не было.

Непосредственно перед merge официальные [GitHub summary](https://www.githubstatus.com/api/v2/summary.json) и [unresolved incidents](https://www.githubstatus.com/api/v2/incidents/unresolved.json), `2026-10-27T08:12:00.483599+00:00`: Actions/Git Operations/API Requests/Pull Requests operational, incidents0. Merge завершён `08:12:10Z`.

Release-scope **1/1**, только implementation PR #943 после rc.22. PR/main Python **1596 tests, 3 skipped**; локально full1596/16 environment skips (включая отсутствие Nginx), targeted14, docs/targeted47, version/living/current/release contracts64 PASS; compileall/OpenAPI/catalog/docs/diff/renderer PASS. Fresh [supply-chain40470091691](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40470091691) SUCCESS на implementation main `c738701a606ab92b4a4e94ae3f3053b52d8fbb82`; hash-pinned install, Trivy filesystem/container, actionable HIGH/CRITICAL gate и CycloneDX SBOM подтверждены workflow steps. После него только docs/version, locks/Docker/dependency surface неизменны.

Implementation/Roadmap [#944](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/944) merged `90d3d09d016cc3bb8d64568512428f4c89655be9`, [PR Python40470478454](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40470478454)/[title40470946867](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40470946867) и [main Python40471066285](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40471066285) SUCCESS; independent main Roadmap/Issue read-back выполнен до release-prep. Финальные CI/title относятся к окончательным heads, не к старому e20e9d9 или незаполненному checklist.

## Собственный acceptance

[Post-merge audit](2026-10-27-564-legacy-visibility-postmerge-checkpoint.md) сохраняет source/security/guard evidence: active-only help, полный typed registry до UI filter, неизменённый AST audit скрытых handlers, оба legacy slash/3 saved callbacks, env/DB/allowlist/rate guards и четыре admin roles. Это не подтверждает новую видимость deployed UI.

#564 OPEN/keep_open по собственному deployment + operator-reported visibility criterion. Минимум поздней проверки — новая справка/основной start/Back по [CLIENT_SETUP](../CLIENT_SETUP.md#актуальные-команды-и-совместимость-564). Старый N03/unchanged guards/roles не повторять, production flags ради них не переключать. #356 не переоткрывается, #506/#885/#887/#890 и общий v5 не закрываются этим RC. Deployed/Accepted projection сохраняется; поздний upgrade требует cumulative compatibility review и отдельного разрешения. Waived burst и прошлые HWID PASS не повторялись.
