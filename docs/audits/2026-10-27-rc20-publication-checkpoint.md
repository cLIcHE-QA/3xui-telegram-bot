# v5.0.0-rc.20 — publication checkpoint, deployment отложен

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-27 02:28 UTC+03:00 (Europe/Moscow); GitHub published_at `2026-10-26T23:26:39Z`
- **Окружение:** GitHub / CI / локальные synthetic tests; без VPS, staging или live Telegram
- **Цель:** подтвердить штатную публикацию начального объединённого RC #930 с накопленными #887/#890, отдельно от deployment/acceptance.
- **Версия и immutable tag/SHA:** `v5.0.0-rc.20` / `929e9950a9d831ef72271f99b226a3315cfef709`; release-prep PR head `eb3f5d6a706fd22927eead2aa6acda45cfc59a5d`, base `6ad096d4bd1458510409689237e8f8c8376bb118`.
- **Scope:** release-prep, required CI, release-scope17/17, GitHub health, provenance, immutable tag/ref, APP_VERSION, prerelease metadata и точное совпадение notes с CHANGELOG. Реальный deployment/product acceptance исключены.
- **Фактический результат:** PASS
- **Источник и evidence:** [release PR #934](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/934) MERGED; [PR Python40418953922](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40418953922), [final title40419409766](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40419409766), [main Python40419464825](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40419464825), [Publish release40419757404](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40419757404) SUCCESS; [GitHub Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.20), независимые REST tag/Release/commit-to-PR и version.py read-back.
- **Ограничения и остаточные риски:** PASS только publication/offline scope. Source-only web factories и выдача URL OFF, reviewed allowlists пусты, staging не запущен. Private JSON1:1, реальные client/version/device и production compatibility/health PENDING. Operator-reported старый deployment не является независимой VPS аттестацией.
- **Связанные Issues:** #887, #890
- **Решение по Issues:** #887: keep_open; #890: keep_open
- **Следующий шаг:** провести этот publication/Roadmap checkpoint через required PR CI, squash merge и независимый main read-back, обновить Issue evidence; затем #885/PR #886 для отдельного rc.21. Операторские проверки отложены в конец пула #930.
- **Раздельные состояния:** merged=#934 `929e9950a9d831ef72271f99b226a3315cfef709`; published=v5.0.0-rc.20, prerelease=true, draft=false, `2026-10-26T23:26:39Z`; deployed=v5.0.0-rc.18.10 `dae205ac82762723448f93827b981f89ae622231`, только operator-reported, independent VPS read-back PENDING; accepted=publication scoped PASS, runtime #887/#890 PENDING, общий G-11 PARTIAL/NO-GO, public rollout BLOCKED.

## Ожидаемое и полученное

До merge target ref rc.20 отсутствовал (GitHub404). После штатного workflow `refs/tags/v5.0.0-rc.20` — commit `929e9950a9d831ef72271f99b226a3315cfef709`; это единственный squash commit merged PR с точным title `release: v5.0.0-rc.20` в main. `version.py` на этом SHA содержит `APP_VERSION = "5.0.0-rc.20"`. Release metadata: prerelease=true, draft=false; title/body после нормализации окончания строк и завершающего newline точно совпадают с canonical renderer из CHANGELOG для этого SHA. Tag/Release вручную не создавались.

Непосредственно перед merge, `2026-10-26T23:23:37.655888+00:00`, официальные [GitHub Status summary](https://www.githubstatus.com/api/v2/summary.json) и [unresolved incidents](https://www.githubstatus.com/api/v2/incidents/unresolved.json) подтвердили Actions/Git Operations/API Requests/Pull Requests=operational, unresolved incidents=0. Merge завершён `23:23:46Z`, после зелёного PR CI.

Release-scope gate: **17/17** merged feat/fix/security PR после rc.19 учтены. PR Python: **1557 tests, 3 skipped**; локально **1557 PASS, 16 skipped** (Nginx отсутствует), 67 version/living/roadmap tests, compileall/OpenAPI/docs/diff и renderer PASS. Synthetic Node33/build/browser57+2+2+1 подтверждены на #929 и его post-merge main; release-prep меняет только version/docs.

Свежий [supply-chain audit40418537797](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40418537797), job121906824788, SUCCESS на `97270d8e354e3615fa49f484a41c218badd3bfc6`: hash-pinned install/pip check, Trivy filesystem/container, actionable HIGH/CRITICAL gate, license reports и CycloneDX SBOM. После audited SHA requirements.lock/requirements.txt/npm lock/Docker/base-image не менялись, проверено Git diff. Версионные и документационные изменения не являются новой аттестацией production.

## Проверка закрытия Issues

**#887 keep_open:** опубликованы изолированные D1a/D1b/D2a–D2e/D3a–D3j исходники; полный private JSON1:1, реальные reviewed client/version, trusted staging TLS/edge/session topology и physical iOS/Android/Telegram WebView остаются PENDING. CI не доказывает весь продуктовый scope.

**#890 keep_open:** patched Pillow13.0.0/certifi2026.10.19 Published, hashes/QR/CI security доказаны. По собственному post-merge checkpoint Issue отдельно остаются deployment и targeted production QR/device/API compatibility/health; они перенесены в завершающий операторский этап, не объявлены PASS по scanner. Другие runtime Issues не закрывались. После будущего deployment нужен cumulative migration/config/agent review от фактически установленного tag, отдельное разрешение и собственный targeted outcome.
