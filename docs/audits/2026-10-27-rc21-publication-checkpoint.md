# v5.0.0-rc.21 — publication checkpoint без deployment

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-27 09:33 UTC+03:00; GitHub published_at `2026-10-27T06:32:15Z`
- **Окружение:** GitHub / CI / локальный synthetic Python3.12, без VPS/Telegram/provider операций
- **Цель:** подтвердить отдельный RC задачи #885 после implementation checkpoint #936, до следующего scope #506.
- **Версия и immutable tag/SHA:** `v5.0.0-rc.21` / `35c1a11676bd7fedc1bf386e4f153a3ba454f6e8`; release-prep head `75310b6892cd5ba1aa9c336a19cbc42d9ec378be`, base `e87760ca176c4c73ab0187c4c0be16dac6f32217`.
- **Scope:** release-prep/required CI/release-scope1/1, GitHub health, main/publish workflow, immutable tag/APP_VERSION/unique PR provenance и точные canonical notes. Не actual device/deployment/production acceptance.
- **Фактический результат:** PASS
- **Источник и evidence:** [release PR #937](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/937) MERGED; [PR Python40460904782](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40460904782), [final title40461300052](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40461300052), [main Python40461394036](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40461394036), [Publish40461667790](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40461667790) SUCCESS; [GitHub Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.21), independent REST ref/release/version.py/commit-to-PR read-back и canonical renderer comparison.
- **Ограничения и остаточные риски:** PASS только release/offline scope. Ticket — кратковременный bearer-like URL, HTTP не переаутентифицирует owner, process-local only. Физические Telegram/browser/client import/refresh/expiry и фактический TLS/log/cache/CSP ingress PENDING; overall v5 не принят.
- **Связанные Issues:** #885
- **Решение по Issues:** #885: keep_open
- **Следующий шаг:** required CI, squash merge и main read-back этого publication/Roadmap checkpoint, Issue evidence; затем #506/rc.22. Deployment/device шаги отдельно в конце пула #930.
- **Раздельные состояния:** merged=#937 `35c1a11676bd7fedc1bf386e4f153a3ba454f6e8`; published=v5.0.0-rc.21, prerelease=true/draft=false, `2026-10-27T06:32:15Z`; deployed=v5.0.0-rc.18.10 `dae205ac82762723448f93827b981f89ae622231` только operator-reported, independent VPS read-back PENDING; accepted=publication scoped PASS, собственный #885 live PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## Ожидаемое и полученное

Target ref rc.21 до merge отсутствовал (GitHub404). Штатный workflow создал commit ref `35c1a11676bd7fedc1bf386e4f153a3ba454f6e8`; это единственный merged PR #937 с точным title `release: v5.0.0-rc.21` в main. version.py на tagged SHA: `APP_VERSION = "5.0.0-rc.21"`. Release prerelease=true/draft=false; title/body точно совпадают с CHANGELOG renderer для этого SHA после нормализации LF/trailing newline. Прежний rc.20 ref независимо прочитан: `929e9950a9d831ef72271f99b226a3315cfef709`, не перемещался. Ручного tag/Release или deployment не было.

Непосредственно перед merge официальные [GitHub summary](https://www.githubstatus.com/api/v2/summary.json) и [unresolved incidents](https://www.githubstatus.com/api/v2/incidents/unresolved.json), `2026-10-27T06:29:07.334503+00:00`: Actions/Git Operations/API Requests/Pull Requests operational, incidents0. Merge завершён `06:29:17Z`.

Release-scope **1/1**: только implementation PR #886 после rc.20. PR Python **1569 tests, 3 skipped**, локально **1569 PASS, 16 skipped** (Nginx отсутствует), targeted29, version/living/roadmap67, compileall/OpenAPI/catalog/docs/diff/renderer PASS. [Fresh supply-chain40459701390](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40459701390) SUCCESS на implementation main `b10fe96faa78f55b78116da7de426f9863c59a83`; после него менялись только docs/version, dependency locks/Docker/base неизменны. Hash-pinned install, Trivy filesystem/container, actionable HIGH/CRITICAL gate и SBOM проверены штатным workflow.

## Проверка собственного acceptance #885

Owner/private issuance, exact import_uri URL/client/platform/title binding, TTL90/MAX256/one GET, malformed/HEAD/query/noncanonical path/replay и Copy/QR/Back доказаны offline fixtures и CI. Это не physical-device evidence. Последний критерий Issue требует отдельного разрешённого deployment и targeted Telegram iOS/Android/desktop → client import/refresh/expiry с postcondition; он PENDING, поэтому #885 OPEN/keep_open. #473/#887/#890 не закрываются этим RC. Deployed/Accepted projection сохранена без повышения; поздняя установка требует cumulative upgrade/config/agent review и отдельного разрешения.
