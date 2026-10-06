# Журнал изменений

Все заметные изменения проекта фиксируются здесь на русском языке. Названия элементов интерфейса, API, переменных, таблиц и команд сохраняются в исходном виде, чтобы их можно было сопоставить с кодом.

История до перехода на Git восстановлена по сохранённым релизным архивам. Для исторических версий формулировки сокращены и приведены к единому виду.

> Первый архив проекта не имел номера версии. При миграции в Git он помечен тегом `v1.0.0` как историческая отправная точка.




## v4.26.6 — Final v4 audit remediation: admin boundary, redirects и file modes
- A-004/#237: Admin Control Plane теперь fail-closed работает только в private Telegram chat; общий middleware блокирует /admin, admin callbacks и admin FSM input вне личного чата до rendering/business logic, при этом client-facing router остаётся отдельным контуром.
- A-005/#238: subscription upstream redirects обрабатываются вручную; automatic redirects отключены, HWID/device и auth-like headers удаляются при первом cross-origin hop и не восстанавливаются дальше по chain, HTTPS downgrade и malformed redirect target отклоняются, число redirect hops ограничено.
- A-006/#239: backup/runtime directories и sensitive local artifacts получают явные owner-only modes независимо от host umask; existing backup/log artifacts ужимаются, Full Backup, bot/node snapshots, bot SQLite и local bot logs создаются с private permissions.
- SECURITY/UI contracts и regression coverage обновлены; новый security suite проверяет private-chat boundary, same-origin/cross-origin/TLS-downgrade redirect semantics и file modes под permissive umask.
- SQLite schema остаётся v5, pinned 3x-ui OpenAPI contract остаётся v3.8.5. После публикации обязательны targeted production acceptance A-004/A-005/A-006 и повторный базовый health/status-check.

## v4.26.5 — Final v4 audit remediation: backup, logs и mutation certainty
- A-001/#234: secret-bearing Full Backup/DB/node/DR artifacts больше не передаются через Telegram; recovery transport остаётся только host-side/off-site, без ослабления encrypted off-site/DR flow.
- A-002/#235: встроенный aiohttp access log для secret-bearing `/compat/{sub_id}` отключён, а canonical Nginx `/compat/` route не пишет access log; regression coverage проверяет raw-log boundary.
- A-003/#236: все инвентаризированные state-changing 3x-ui calls используют one-shot/no-redirect mutation boundary с explicit uncertain outcome и без автоматического replay.
- Для destructive и deterministic field mutations, provisioning, bulk, user/node/inbound/create paths добавлен fail-closed read-back: uncertain success признаётся только при доказанном post-condition; иначе состояние остаётся `unknown` с `mutation_not_retried=true`.
- Traffic reset намеренно не объявляется успешным после lost response по нестабильным live counters; локальная SQLite state меняется только после обычного success либо доказанного remote post-condition там, где состояния связаны.
- Patch остаётся в рамках final v4 feature freeze; SQLite schema и pinned 3x-ui OpenAPI v3.8.5 не меняются. После публикации обязательны targeted production acceptance A-001/A-002/A-003 и повторный базовый health/status-check. Admin Setup: изменений не требуется.

## v4.26.4 — Permission-aware admin navigation
- Исправлен production finding #226: admin keyboards теперь могут фильтровать callback buttons по effective role через существующий RBAC callback catalog; неизвестные admin callbacks скрываются fail-closed.
- Role-aware rendering подключён к смешанным экранам `Задания`, `Резервные копии`, `Оповещения`, `Операции с нодами`, а также к core admin/system navigation.
- `read_only`/`support` больше не видят admin/owner actions, `admin` не видит owner-only actions; backend `authorize_callback` остаётся обязательной второй границей.
- Attention Center показывает domain deep-links только для реально присутствующих problem groups; calm/empty state сохраняет только `🔄 Обновить` и `⬅ Обзор`.
- Canonical parent semantics не меняются: переход из Attention Center открывает обычный destination screen, который возвращается в свой канонический раздел.
- Добавлен regression coverage role matrix, unknown-callback fail-closed filtering, context-aware Attention links и wiring затронутых destination screens.

## v4.26.3 — Attention Center drill-down
- Добавлен отдельный read-only экран `⚠️ Требует внимания` из `/admin → Обзор` с grouped detail по инфраструктуре, заданиям, оповещениям, резервным копиям и Fleet/Node Drain problem states.
- Detail использует те же current-state источники, что summary `v4.26.2`: active alerts, latest problematic job per name, offline/unknown infrastructure и latest terminal rollout/drain journals; resolved job исчезает после refresh, а item count согласован с summary contract.
- Каждый item содержит bounded operator context и stable technical identity без job details, alert raw values, credentials, subscription URL/`sub_id` или персональных списков пользователей; на группу показывается не более 5 items + `… ещё N`.
- Добавлены canonical read-only deep-links в `Состояние системы`, `Задания`, `Оповещения`, `Резервные копии` и `Операции с нодами`, а также `🔄 Обновить` и `⬅ Обзор`.
- Новый callback `admin:attention` использует существующий `dashboard.view` / Read-only+ permission; новых privilege IDs, SQLite schema, auto-remediation и remote mutations нет.
- Добавлен regression coverage count/detail parity, resolved/stale semantics, bounded rendering, secret exclusion, canonical navigation и no-mutation handler contract.

## v4.26.2 — Dashboard Attention summary
- В `/admin → Обзор` добавлен compact read-only блок `⚠️ Требует внимания` с общим count и bounded breakdown существующих проблемных состояний.
- Summary агрегирует active alerts, latest problematic background jobs, текущие offline/unknown direct-node states и latest terminal Fleet/Node Drain states; старый failed job не остаётся проблемой после более нового успешного run того же job name.
- `failed`, `unknown`, `interrupted`, degraded/offline и partial Drain отображаются раздельно; при отсутствии проблем показывается `✅ Требует внимания: нет`.
- Fleet/Node Drain журналы читаются локально и не запускают health probes или remote mutations; `Обзор` сохраняет Read-only+ boundary, новых privilege IDs, SQLite schema и auto-remediation нет.
- В summary не выводятся job details, user lists, credentials, subscription URL/`sub_id` или raw upstream payloads. Отдельный drill-down и deep-links остаются scope `v4.26.3`.
- Добавлен regression coverage deterministic/latest-state aggregation, bounded category order и no-mutation wiring. Admin Setup: изменений не требуется.

## v4.26.1 — Node Drain Cancel navigation
- Исправлена навигация `✖ Отмена` на confirmation screen Node Drain: после terminal `review → cancelled` оператор возвращается в read-only preflight той же stable direct node вместо корня `Операции с нодами`.
- Cancel сохраняет no-mutation contract: maintenance, attach/detach, Xray/service и другие remote mutations не выполняются; отменённый plan остаётся terminal `cancelled`.
- Stale `run` для cancelled plan по-прежнему блокируется fail-closed до первой remote mutation; RBAC callback catalog и Administrator+ boundary не меняются.
- Добавлен regression contract на canonical parent, no-mutation Cancel и stale-plan rejection. SQLite schema остаётся v5, pinned 3x-ui OpenAPI contract остаётся v3.8.5.
- Patch закрывает production finding #211 после публикации, deployment и targeted verification `preflight → prepare → ✖ Отмена`; полный Node Drain mutation smoke по-прежнему выполняется только на безопасной test node/user cohort.


## v4.26.0 — Node Drain
- Реализован отдельный graceful Node Drain для direct nodes без изменения семантики maintenance и без автоматического Stop Xray/service.
- Read-only preflight по stable `node_id` определяет управляемые Inbounds target-ноды, затронутых локальных пользователей, policy alternatives, blockers и remaining work; transitive/неоднозначная node identity блокируется fail-closed.
- Эвакуация использует существующий `ProvisioningEngine` как источник policy и соблюдает attach-before-detach: target Inbounds detach'ятся только после read-back подтверждения альтернативного Inbound; disabled target Inbounds также учитываются как оставшиеся назначения.
- Добавлен last-working-Inbound guard; пользователь без подтверждённой policy alternative остаётся blocker и не мутируется. Один Drain ограничен 500 затронутыми пользователями и выполняется последовательно.
- Maintenance enable/disable и client attach/detach переведены на существующую no-retry mutation boundary `XUIMutationError`; uncertain outcome проверяется read-only состоянием и не приводит к автоматическому повтору mutation. Target Inbound IDs фиксируются на preflight, поэтому post-check не зависит от того, продолжает ли disabled node публиковать свои Inbounds в live options.
- Fleet UI получил `🚧 Вывести из трафика`: просмотр/preflight доступен Read-only+, prepare/confirm/run — Administrator+; сначала target node переводится в maintenance, затем выполняется controlled evacuation. Fleet Health и карточка direct-ноды различают `maintenance`, `draining`, `drained` и проблемные terminal states.
- Добавлен parent job `fleet.drain`, audit и private persistent journal `fleet/drain-<id>.json` с mode 0600; journal хранит только stable IDs и техническое состояние без email, subscription URL, `sub_id` или credentials.
- Startup recovery переводит незавершённый `draining` в `interrupted/unknown` без mutation replay. После `partial/unknown/interrupted` продолжение требует нового preflight и нового plan; возврат ноды в работу выполняется через выход из maintenance + обычный policy reconcile без reverse replay. Active Xray sessions специально не обрываются; Stop Xray/service остаются отдельными Owner-only operations.
- Добавлены regression tests safety/RBAC/recovery/bounded-state contract и обновлён Fleet Operations runbook. `APP_VERSION` поднят до `4.26.0` отдельным release-prep; SQLite schema остаётся v5, используемый 3x-ui route surface не меняется, production smoke/acceptance ещё не выполнены.

## v4.25.8 — navigation and Owner self-role safety
- В Clone Inbound кнопка `✖ Отмена` на экране выбора target server теперь возвращает в карточку исходного Inbound; shared target keyboard получает явный parent, а Deploy Template сохраняет собственный parent.
- Self-demotion DB-backed Owner ниже `Owner` больше не выполняется одним нажатием: добавлен отдельный confirmation screen с предупреждением о потере Owner-only доступа.
- Self-demotion mutation выполняется только через Owner-only callback с актуальным FSM state и nonce; direct/stale confirmation блокируется, Cancel очищает confirmation и возвращает в карточку администратора.
- Изменение ролей других DB-администраторов и immutable break-glass Owner из `ADMIN_TELEGRAM_IDS` сохраняют прежнюю семантику; role model и privilege levels не меняются.
- Добавлены regression tests для navigation parent, confirmation/cancel/stale-run/single-mutation/audit, RBAC catalog и lifecycle закрытия проверенных bug issues.
- SQLite schema v5, pinned 3x-ui OpenAPI contract v3.8.5, provisioning, subscription/HWID, Host Control и clone disabled/clientless semantics не меняются.

## v4.25.7 — Inbound input validation
- Исправлен `UnboundLocalError` при неверном вводе порта в clone/deploy Inbound и при неверном имени шаблона: FSM identifiers читаются до validation branch после успешного authorization guard.
- Ошибочный ввод сохраняет исходный FSM/Cancel context и не выполняет remote/database mutation; после исправления можно повторить ввод или отменить действие штатной кнопкой.
- Добавлены исполняемые async regression tests для invalid/boundary input, occupied port, duplicate template name, retry, authorization guard и сохранения disabled/clientless Inbound payload.
- Callback identifiers, RBAC, SQLite schema v5, pinned 3x-ui OpenAPI contract v3.8.5, HWID/subscription proxy и mutation retry semantics не меняются.

## v4.25.6 — revert Streisand subscription workarounds
- Удалены временные `plain=1` workarounds из `v4.25.4–v4.25.5`; runtime subscription proxy возвращён к контракту `v4.25.3`.
- Production diagnosis подтвердил root cause: Streisand raw subscription request не передаёт совместимый `X-HWID`, поэтому при активном HWID limit upstream 3x-ui отвечает `hwid_not_supported`.
- Compat proxy по-прежнему не генерирует synthetic/fallback HWID и не обходит per-device enforcement.
- `v4.25.4` и `v4.25.5` остаются в истории релизов как диагностические попытки и не удаляются.

## v4.25.5 — Streisand plain mode precedence
- `?plain=1` теперь принудительно обходит HTML branch даже если клиент присылает `Accept: text/html`.
- Это закрывает Safari/WebView-like Streisand request path, который ранее получал HTML page вместо raw links.
- Default subscription URL без `plain` не меняется.
- HWID enforcement/diagnostics и client-specific transforms остаются без изменений.

## v4.25.4 — Streisand plain subscription compatibility
- Добавлен opt-in `?plain=1` для raw subscription response: Base64-wrapped upstream body декодируется в newline-separated links.
- `plain` является локальным параметром compat proxy и не пересылается upstream в 3x-ui.
- Default `/compat/{sub_id}` без `plain` сохраняет прежний encoding и client-specific behavior, включая Shadowrocket, V2Box, V2RayTun, Happ и INCY.
- HWID forwarding/enforcement и диагностические response headers не меняются.

## v4.25.3 — INCY Desktop UA compatibility
- Исправлена детекция реального INCY macOS Desktop User-Agent вида `INCY/<version>/mac os x Dalvik/<runtime>`; AWG filtering теперь включается и для этого подтверждённого Desktop UA.
- Парсер остаётся fail-closed для неизвестных INCY platform tokens и не применяет Desktop filtering к неоднозначным User-Agent.
- Сохранены принятые в `v4.25.2` Shadowrocket/HWID diagnostics и strict per-device enforcement.
- Явная инструкция Shadowrocket `Send HWID` добавлена в README/ADMIN_SETUP.

## v4.25.2 — Subscription client compatibility
- INCY Desktop определяется только по documented `INCY/<version>/<platform>` UA для `Windows/Linux/macOS`; неподдерживаемые AmneziaWG entries отфильтровываются только для этих Desktop requests, а INCY mobile сохраняет существующий `vpn:// → amneziawg://` flow.
- HWID-specific upstream `404` больше не маскируется generic `502`: compat proxy сохраняет allowlisted `X-Hwid-Active`, `X-Hwid-Not-Supported`, `X-Hwid-Limit`, `X-Hwid-Max-Devices-Reached` и возвращает диагностически различимый HWID rejection.
- Generic upstream 404/5xx без HWID diagnostic headers остаются fail-closed gateway errors.
- Compat proxy не генерирует synthetic/fallback HWID, не ослабляет per-user limit и не логирует HWID/subscription secrets.
- Документирован Shadowrocket `Send HWID`; production finding подтвердил full-slot scenario как причину отказа и восстановление subscription после увеличения свободных HWID slots.

## v4.25.1 — User Management stabilization / HWID completion
- Исправлены production-acceptance navigation defects: `Показать URL` возвращает в `🔗 Подписка`, user-scoped `💳 Платежи` больше не уводят в глобальный payment ledger, shortcut `⏳ Продлить` удалён из главной карточки.
- Create-user корректно трактует production 3x-ui response `Obtain (record not found)` как отсутствие клиента, сохраняя fail-closed обработку остальных API errors.
- Subscription compatibility proxy передаёт upstream reviewed `X-HWID` / device metadata headers для normal VPN-client requests; значения этих headers не логируются.
- Новые 3x-ui clients получают `limitHwid=5` по умолчанию. Existing clients массово не меняются; per-user HWID limit доступен Support+ в `⚙️ Параметры доступа`, Read-only видит текущее значение.
- Plan apply и reconcile не управляют HWID limit; существующий `update_client()` сохраняет индивидуальный `limitHwid`, если операция явно его не меняет.
- `📱 Подключения` показывает текущий HWID limit рядом с количеством зарегистрированных устройств.
- `Система → Администраторы` разделяет статус и роль: `🟢/⛔` обозначают enable state, а `👑/🛡/🧑‍💻/👁` — фиксированную RBAC роль.

## v4.25.0 — User Management
- Начат рефакторинг `/admin → Пользователи`: список получил bounded pagination и поиск по Telegram ID, техническому email и display name при сохранении `telegram_id` как callback identity.
- Mutation shortcuts списка теперь role-aware: Read-only не получает массовые действия/глобальное согласование, while handler authorization остаётся обязательной.
- Legacy attach-all действия `Синхронизировать Inbounds`, `Синхронизировать всех` и bulk sync удалены из новых клавиатур; сохранённые старые callbacks выполняют только non-mutating redirect в policy-based `Согласование`.
- Bulk access action переведён на `ProvisioningEngine.provision_many(..., strict=False)`; direct attach всех globally allowed Inbounds больше не является каноническим mass workflow.
- Audit bulk operations больше не перечисляет email выбранных пользователей; SQLite schema, 3x-ui/OpenAPI contract и subscription identity на этом foundation-срезе не меняются.
- Карточка пользователя переведена на устойчивые parent sections `Тариф / Срок / Трафик / Доступ / Подписка / Профиль / Ещё действия`; summary routes доступны Read-only, а mutation controls отображаются только для соответствующей роли.
- `🌐 Доступ` объединяет Server Group, policy-based reconcile, manual Inbounds и access parameters; legacy `adminuser:*` продолжает открывать ту же каноническую role-aware карточку.
- Добавлен `📱 Подключения`: online/last-online/IP limit summary, отдельные `📱 Устройства` по HWID и `🌐 IP-адреса` без подмены session/IP данными device identity.
- Pinned 3x-ui API surface расширен тремя reviewed endpoints текущей schema `v3.8.5`: `POST /clients/ips/{email}`, `POST /clients/hwids/{email}`, `DELETE /clients/hwids/{email}/{id}`; manifest теперь покрывает 54 используемых endpoint.
- Удаление одного HWID device выполняется только после отдельного confirmation; DELETE использует no-retry mutation semantics, а uncertain outcome отображается как неизвестный и проверяется read-only обновлением списка.
- Карточка пользователя получила read-only раздел `💳 Платежи`: scoped ledger по `payments.telegram_id`, суммы оплаченных группируются по валюте, detail callback проверяет принадлежность платежа текущему пользователю, write-actions остаются только в каноническом разделе `Платежи`.
- Добавлен `🧾 Активность`: user-scoped presentation существующего `audit_log` по технической identity (`email`/`telegram_id`) с MSK timestamps, pagination и bounded summaries; subscription/device secret-like details не реконструируются в timeline.
- Добавлен Support-level flow `➕ Создать пользователя`: Telegram ID → технический email → display name → тариф/compatibility → preview → подтверждение. Existing 3x-ui identity по `tgId` не дублируется и восстанавливается только отдельным explicit recovery action.
- `XUIClient.create_client()` переведён на no-retry mutation boundary: timeout/network/5xx дают uncertain outcome, POST не повторяется, а локальная запись создаётся только после success или read-only доказательства exact `email + subId`; audit не хранит subscription credential.
- `🔗 Подписка` дополнена `🌐 Открыть ссылку`, `🔗 Показать URL` и локальным `🔳 QR-код`; QR строится внутри bot process и не отправляет subscription URL внешнему сервису.
- `⚙️ Параметры доступа` получил Support-level `🔄 Синхронизировать VLESS Flow`: операция меняет только Flow через существующий bulk-adjust primitive и не выполняет attach/detach Inbounds.
- Enable/Disable переведены с one-click mutations на отдельные confirmation callbacks; stale `admindisable:*` / `adminenable:*` теперь только открывают ask-screen, а mutation выполняется новым run callback.
- Bulk User Management завершён по roadmap: добавлены отдельные Plan/Server Group assignment без implicit provisioning, custom expiry/traffic bounded FSM input с preview, а `+30`, enable/disable/reset/safe reconcile требуют count-based confirmation перед mutation.
- Bulk result/audit summary хранит только counts и outcome, без списка email; custom per-user updates продолжают обработку остальных пользователей при локальной ошибке одного target.
- Финализирован detail/navigation contract User Management: экран тарифа показывает price/period/plan-vs-current параметры, subscription card — masked ID и фактический status, пустой `VLESS Flow` явно отображается как `не настроен`; Plan/expiry/traffic/IP/profile/subscription actions возвращаются в свои canonical detail screens и очищают FSM при Cancel/Back.
- Delete confirmation теперь явно показывает display/machine identity и необратимость; callback-size regression закрепляет Telegram 64-byte boundary для динамических v4.25 routes.

## v4.24.1 — Hotfix web diagnostics и IPv6
- WHOIS/RDAP absolute timestamps в Telegram теперь нормализуются в `DD.MM.YYYY HH:MM MSK`; machine/RDAP instants остаются UTC, а возраст домена рассчитывается как раньше.
- Compact Cheburcheck card снова показывает полезную bounded static detail: resolved IP для domain target, Reverse DNS, blocked subnets и optional `rkn_domain` / `subnet_size`; IP/PTR/subnet lists ограничены 5 значениями + `… ещё N`, raw JSON/SSE/probe payload не выводится.
- Website monitoring корректно распознаёт public IPv6 literals до IDNA/domain validation, сохраняет bracketed canonical URL и по-прежнему fail-closed блокирует loopback/link-local/private/non-global IPv6.
- Safe outbound timeouts/body/redirect/DNS-rebinding policy, SQLite schema, RBAC/navigation, pinned Cheburcheck revision и 3x-ui/OpenAPI contract не меняются.
- `PAGESPEED_API_KEY` остаётся пустым и optional по умолчанию; `docs/ADMIN_SETUP.md` содержит воспроизводимый future setup/disable runbook.

## v4.24.0 — Мониторинг сайтов и web diagnostics
- В `/admin → Мониторинг` добавлен нативный раздел `🌐 Мониторинг сайтов`: persistent targets, many-to-many admin watchers, add/list/card/manual-check, incident history, per-watcher alerts, pause/resume, unsubscribe и Administrator-only global target management.
- Background monitoring использует deterministic state machine `unknown/up → suspect → down → up`: первый candidate failure подтверждается повторной проверкой через 2 s, down-target проверяется каждые 3 минуты, normal target — каждые 10 минут. Incident state и notification journal сохраняются в SQLite, поэтому restart не replay'ит first/recovery alert.
- Site alerts различают first/repeat/recovery и отправляются только active watchers с включёнными notifications. Repeat cadence сохраняет reviewed PackBot defaults: 30 минут, затем 320 минут; один target не получает параллельные checks благодаря per-target lock.
- Добавлен единый SSRF-safe outbound HTTP boundary: только public HTTP/HTTPS на standard ports 80/443, IDNA/syntax validation, fail-closed private/loopback/link-local/CGNAT/reserved/metadata blocking, validation DNS answers в resolver connect path, `trust_env=False`, manual validation каждого redirect, hard limits 5 redirects / 3-7-10 s connect-read-total / 1 MiB ordinary body.
- Добавлена `🔎 Разовая диагностика` и contextual `🩺 Диагностика` из карточки monitored site: RDAP/WHOIS + возраст домена, DNS A/AAAA/CNAME/MX/NS/TXT, HTTP summary, redirect trace, CMS detection, robots/meta/X-Robots indexability, optional Google PageSpeed, bounded Sitemap, local URL-list normalization и QR generation.
- Sitemap ограничен 2 MiB на документ, максимум 10 документов и 5000 URL; raw WHOIS/RDAP/PageSpeed payload не выводится и не сохраняется. QR и URL-list работают local-only.
- Optional PageSpeed использует только локальный `PAGESPEED_API_KEY`; отсутствие key отображается как `не настроен` и не влияет на остальные diagnostics.
- SQLite schema повышена до v5: `v4 website_monitoring_v4_24_0` добавляет targets/watchers/incidents/idempotent notification journal, `v5 website_watcher_lifecycle_v4_24_0` добавляет watcher-scoped `monitoring_enabled`. Обе migration additive и `requires_backup=False`; downgrade на runtime, знающий только schema v3/v4, без совместимого pre-migration backup не поддерживается.
- PackBot `vladpak1/packbot@3c4a5bb29626f8b3e28056bd52cd94fdce9f3c1a` использован как reviewed behavior/reference implementation; production runtime остаётся Python/aiogram/SQLite-native, PHP/MySQL/webhook stack не разворачивается. MIT attribution сохранён в `THIRD_PARTY_NOTICES.md`.
- Screenshot/headless-browser diagnostics и перенос multilingual PackBot UI намеренно не входят в обязательный scope `v4.24.0`; Client Portal `/start` также не расширяется.
- Добавлены `dnspython` и `qrcode[pil]`; новых обязательных host-side services/ports нет. 3x-ui/OpenAPI, provisioning, VPN mutation semantics, Host Control Agent, Deploy Agent и Cheburcheck runtime не меняются.
- Release устанавливается обычным Safe Bot Self-Update. Production acceptance должен отдельно подтвердить add/up/manual diagnostics, controlled down/repeat/recovery, restart idempotency, SSRF rejects, optional PageSpeed-off state и финальный `deploy-release.sh --status`.

## v4.23.3 — Hotfix compact result Cheburcheck
- Production smoke `v4.23.2` подтвердил compact layout и context-preserving navigation, но выявил неполный result enrichment: пустой CDN выглядел неизвестным, domain/IP не показывал ASN coverage, а отсутствие regional Probe reporters маскировалось нейтральным `—`.
- Пустой upstream `cdn_providers` теперь отображается как фактический отрицательный результат `🟢 не найден`; optional значения, которых upstream действительно не предоставил, по-прежнему не выдумываются.
- Для domain/public-IP с валидным `geo.asn` bot выполняет один дополнительный bounded read-only `GET /api/v1/check?target=AS...` и использует только counts `blocked_prefixes / prefixes`; ASN enrichment и regional probe выполняются как независимые follow-up checks, а их failure не меняет уже полученный static verdict.
- Regional SSE сохраняет `started.online_probes`: UI различает реальные агрегированные ответы, `⚪ нет активных региональных сканеров`, online scanners без ответов и `🟡 региональная проверка недоступна`; subnet/ASN regional probe остаётся неприменимым.
- Исправлен edge case классификации target: обычные домены, начинающиеся с букв `as...`, больше не ошибочно считаются ASN.
- Existing network safety сохраняется: static response hard limit 1 MiB, regional SSE 256 KiB, connect/read/total timeouts и запрет redirects не ослаблены; raw upstream/probe payload не выводится.
- Minimal self-hosted Cheburcheck topology `website + PostgreSQL` остаётся поддерживаемой для static diagnostics. Hotfix не создаёт MQTT/Probe fleet и не эмулирует региональные результаты; реальные региональные ответы требуют отдельной инфраструктуры с зарегистрированными Probe reporters.
- SQLite schema остаётся v3; 3x-ui/OpenAPI, provisioning, VPN mutation semantics, Host Control Agent, Deploy Agent и pinned Cheburcheck revision не меняются. `v4.23.3` устанавливается обычным Safe Bot Self-Update и не требует rebuild Cheburcheck runtime или host-side Agent/helper.

## v4.23.2 — Компактный результат Cheburcheck
- Экран `Мониторинг → Проверка блокировок` переведён на компактную operator-facing карточку: цель, итоговый verdict, сеть, единый блок `📋 Списки`, агрегированная строка `🌍 Регионы` и явный `Источник: Cheburcheck.`.
- Static check теперь использует уже доступные в pinned upstream поля `cdn_providers`, `asn_info` и `whitelist`; raw IP/reverse-DNS/probe payload в основной Telegram-карточке не выводится.
- Для domain/public-IP добавлен read-only regional summary через reviewed upstream `GET /api/v1/probe/{id}`: ответы сворачиваются в `🟢 / 🔴 / 🟡`, а subnet/ASN не запускают probe, потому что upstream endpoint их не принимает.
- Regional SSE bounded отдельно: hard limit 256 KiB, connect/read/total timeouts 3/10/12 s, redirects запрещены; при недоступности probe успешный static check сохраняется, а строка регионов показывает `—`.
- Cheburcheck navigation сохраняет исходный parent context: Monitoring/discovered/manual flow не прыгает в карточки серверов, shortcut из Master возвращается в Master, shortcut из direct Node — в ту же Node; result/error/retry/`Проверить ещё`/Cancel сохраняют тот же context.
- Regression coverage закрепляет extended API contract, probe verdict buckets, compact result wording, новые read-only callbacks и отсутствие cross-context navigation.
- SQLite schema остаётся v3; 3x-ui/OpenAPI, provisioning, VPN mutation semantics, Host Control Agent, Deploy Agent и pinned Cheburcheck revision не меняются. `v4.23.2` устанавливается обычным Safe Bot Self-Update и не требует rebuild Cheburcheck runtime или host-side Agent/helper.

## v4.23.1 — Cheburcheck hotfix и navigation regression
- Production smoke `v4.23.0` подтвердил self-hosted Cheburcheck для domain/public IP и shortcuts Master/direct Node, но штатный ASN response размером около 382 KiB превысил исходный hard limit 256 KiB.
- `CheburcheckClient` увеличивает bounded response-body limit до 1 MiB. Concurrency остаётся 4, connect/read/total timeouts — 3/7/10 s, redirects по-прежнему запрещены; произвольные URL/private targets не разрешаются.
- Добавлен reproducible VPS runbook `docs/CHEBURCHECK_DEPLOY.md`: pinned upstream revision, PostgreSQL 18.6, причина требования `uuidv7()`, internal-only Docker networks без host ports, local secrets, health/reachability checks, bot `.env`, rollback и update policy.
- Документация явно фиксирует, что PostgreSQL/cache Cheburcheck являются отдельной operational boundary и не входят в Full Backup Telegram-бота.
- Проведён navigation audit Admin Control Plane; канонические parent/back transitions сохранены, а regression coverage расширяется для repo-wide проверки стабильных Back labels и privilege-backed static admin callbacks.
- Roadmap обновлён по факту: `v4.23.0` опубликован/развернут, acceptance частично пройден, полное закрытие Cheburcheck переносится на `v4.23.1`.
- SQLite schema остаётся v3; 3x-ui/OpenAPI contract, provisioning, VPN mutation semantics, Host Control Agent, Deploy Agent и Cheburcheck upstream revision не меняются.
- Для уже работающего pinned self-hosted Cheburcheck runtime rebuild не требуется: `v4.23.1` обновляет только bot release, после чего повторяется ASN/validation/unavailable/base-health smoke.

## v4.23.0 — Проверка блокировок Cheburcheck
- Добавлен read-only diagnostics flow `Мониторинг → Проверка блокировок` для доменов, публичных IPv4/IPv6, подсетей и ASN через optional Cheburcheck service.
- Стартовый экран автоматически предлагает публичные цели из уже известных Master/direct Nodes/enabled Hosts; карточки Master и direct node получили shortcut `🔎 Проверить блокировку`. Из сохранённых URL передаётся только hostname/IP, без scheme/port/path/query/credentials, а дубликаты и local/private targets отбрасываются.
- Интеграция использует фиксированный `/api/v1/check?target=...` contract и не проксирует произвольные HTTP URL; input нормализуется и ограничивается поддерживаемыми target types.
- `CheburcheckClient` использует bounded concurrency, connect/read/total timeouts, запрет redirect-following и лимит response body 256 KiB; rate limit, validation/rejection, not-found, unavailable и invalid response отображаются отдельно.
- Cheburcheck optional: пустой `CHEBURCHECK_URL` не влияет на startup, 3x-ui или provisioning; internal endpoint не показывается в Telegram UI.
- Reviewed upstream закреплён на `LowderPlay/cheburcheck@0bbd2be8ca4b8f9ded1407597654314fc2a900c6`; README и `THIRD_PARTY_NOTICES.md` сохраняют attribution и BSD-3-Clause notice.
- SQLite schema, 3x-ui/OpenAPI contract и VPN mutation semantics не меняются.
- `v4.23.0` разворачивается обычным Safe Bot Self-Update; обновление Host Control Agent, Deploy Agent, 3x-ui/Xray и SQLite migration не требуется. Bot schema остаётся v3.
- Cheburcheck остаётся optional external service: без `CHEBURCHECK_URL` экран показывает «не настроен», а остальные функции бота работают штатно. Production acceptance Cheburcheck выполняется только после настройки pinned self-hosted service или другого явно доверенного endpoint; rollback самого бота не требует отката БД.

## v4.22.0 — Группы пользователей
- Добавлена отдельная сущность User/Audience Groups для будущей сегментации Client Portal: `user_groups` и many-to-many `user_group_members` хранят membership по стабильному `telegram_id`, не по display name или email.
- Добавлен административный flow `Пользователи → Группы пользователей`: список и карточка групп, создание, переименование, описание, участники, поиск пользователя по Telegram ID/email/display name, добавление/удаление membership и просмотр групп из карточки пользователя.
- RBAC расширен permissions `user_groups.view` / `user_groups.manage` / `user_groups.admin` внутри существующих ролей Read-only / Support / Administrator; новых ролей не добавлено, неизвестные callbacks остаются fail-closed.
- Добавлен reusable backend matcher include/exclude с приоритетом exclude и семантикой «нет ограничений — доступ разрешён». User Groups не связаны с provisioning: membership не меняет Plan, Server Group, Nodes, Inbounds, subscription identity или VPN-доступ.
- SQLite schema повышена до v3 migration `user_audience_groups_v4_22_0`; migration additive и не требует recovery copy. Удаление группы очищает только membership, удаление пользователя очищает его memberships.
- Group и membership mutations записываются в существующий audit; удаление группы и удаление участника используют отдельные confirmation flows.
- Добавлен regression coverage для migration/schema, many-to-many membership, поиска, удаления, matcher edge cases, RBAC и разделения Audience Groups / provisioning. Новых env-переменных и host-side компонентов нет.
- `v4.22.0` разворачивается обычным Safe Bot Self-Update без обновления Host Control/Deploy Agent. После применения SQLite schema v3 downgrade на runtime, знающий только schema v2, несовместим без восстановления pre-v3 backup и должен остановиться fail-closed.

## v4.21.2 — Исправления Disaster Recovery и журнала бота
- Исправлен runtime `NameError` в Disaster Recovery после MSK-перехода: `disaster_recovery.py` теперь явно импортирует `format_datetime` и `format_short_datetime`, поэтому список/карточки резервных копий снова открываются штатно и продолжают показывать operator-facing время в MSK.
- В `Мониторинг → Журналы` режимы `50` и `200` больше не выглядят одинаковыми из-за общего character limit: UI показывает `запрошено N · показано M`, а режим `200` использует расширенный Telegram-safe budget для большего excerpt.
- Raw log timestamps намеренно остаются в исходной machine-level timezone (как правило UTC); MSK применяется к operator-facing structured timestamps, а не переписывает содержимое журналов.
- Regression coverage фиксирует imports DR formatter'ов, различие 50/200 log modes и текущую release version. SQLite schema, 3x-ui/OpenAPI, log redaction, Host Control/Deploy Agent и mutation semantics не меняются; host-side Agent/helper update не требуется.

## v4.21.1 — Консистентность display name и московское время
- Display name пользователя теперь используется последовательно на operator-facing поверхностях: `Подписки`, связанные user actions, список клиентов Inbound, monitoring, bulk selection и платежи; технический email остаётся machine identity, audit target и fallback.
- Добавлены общие presentation helpers для user labels, чтобы новые экраны не дублировали собственную логику `display_name · email` и не меняли callback/provisioning identity.
- Абсолютные дата/время в Telegram Admin Control Plane переведены на `MSK (UTC+3)`: сроки пользователей, audit/jobs, backup/system/DR timestamps, node heartbeat, payments/promos. Machine timestamps, Unix epoch, API semantics, backup filenames и agent journals не меняются.
- Date-only ввод `YYYY-MM-DD` для срока пользователя и промокода теперь означает конец выбранного дня `23:59:59 MSK`. Технический `BACKUP_HOUR_UTC` и фактическое расписание backup остаются UTC; UI показывает соответствующее MSK-время и исходное UTC значение.
- Добавлен regression pack для display-name consistency, MSK formatting и сохранения UTC scheduler boundary. SQLite schema, 3x-ui/OpenAPI contract, provisioning, Host Control/Deploy Agent API и mutation semantics не меняются; host-side Agent/helper update не требуется.

## v4.21.0 — Редактируемое имя пользователя
- Добавлено optional `display_name` в профиль пользователя через forward-only SQLite migration `v2 user_display_name_v4_21_0`; существующие профили получают пустое значение и продолжают отображаться по текущему email без ручной миграции данных.
- В карточке пользователя появилось действие `✏️ Имя`: оператор с ролью Support или выше может задать либо очистить отображаемое имя; ввод нормализуется, ограничен 64 символами и отклоняет управляющие символы.
- Карточка и список пользователей используют display name только как presentation metadata: email остаётся видимым техническим идентификатором, callbacks продолжают использовать `telegram_id`, а 3x-ui email, `sub_id`, provisioning и subscription identity не меняются.
- Изменение/очистка имени записывается в audit без сохранения самого имени в details; regression coverage проверяет schema upgrade, fallback, RBAC, edit/clear semantics и сохранение machine identity.
- Migration additive и не требует отдельной recovery copy, но после применения schema v2 downgrade приложения до `v4.20.10` без восстановления pre-v4.21 database несовместим и должен остановиться fail-closed. `v4.21.0` разворачивается стандартным release flow; host-side Agent/helper update не требуется.

## v4.20.10 — Compact Inbound keyboard follow-up
- По результатам production smoke `v4.20.9` карточка Inbound переведена на компактную пятистрочную двухколоночную клавиатуру, которая лучше переносит различия ширины Telegram Desktop после message edit.
- Зафиксирована целевая структура: `Клиенты | Изменить`, `Синхронизировать клиентов | Сбросить трафик`, `Клонировать | Сохранить шаблон`, `Отключить/Включить | Удалить`, затем `⬅ Inbounds`.
- Короткая кнопка `🗑 Удалить` используется только в карточке; отдельный confirmation screen по-прежнему явно показывает `Удалить Inbound` и требует подтверждения, поэтому deletion safety contract не меняется.
- Добавлен release-specific regression gate для layout и полного wording confirmation. Callback identifiers, SQLite schema, storage/persistence semantics, provisioning, pinned 3x-ui/OpenAPI contract и mutation behavior не меняются; `v4.20.10` устанавливается обычным Safe Bot Self-Update без host-side обновления Agent/helper.
## v4.20.9 — Post-acceptance UI cleanup
- Убран лишний implementation detail `bot.sqlite3` из operator-facing prompt сохранения Inbound template; текст теперь описывает только пользовательский результат без раскрытия внутреннего имени DB-файла.
- Перестроена клавиатура карточки Inbound для устойчивого отображения в узком client-side layout Telegram: длинные действия вынесены в отдельные строки, а `Отключить/Включить` и `Удалить Inbound` сгруппированы в предпоследней строке перед `⬅ Inbounds`.
- Закреплён обязательный двухшаговый deletion contract для Admin Control Plane: operator-facing delete entry открывает отдельный confirmation screen, а фактическое удаление выполняется только после явного confirm; one-click delete запрещён.
- Добавлен release-specific regression/source-audit для layout карточки Inbound и delete safety guardrail. Callback identifiers, SQLite schema, storage/persistence semantics, provisioning, pinned 3x-ui/OpenAPI contract и mutation behavior существующих delete flows не меняются; `v4.20.9` устанавливается обычным Safe Bot Self-Update без host-side обновления Agent/helper.
## v4.20.8 — Финальная капитализация Inbound
- Завершён terminology cleanup после production acceptance `v4.20.7`: оставшийся lowercase `inbound` в operator-facing edit/clone/delete/error/help flows заменён на канонические `Inbound` / `Inbounds`.
- Исправлены тексты Inbound admin UI, карточки пользователя и Server Group policy; `docs/UI_STYLE.md` теперь явно запрещает lowercase `inbound` как пользовательский термин.
- Technical identifiers намеренно не переименовываются: callback data, audit action ids, API/DB fields, Python identifiers и module names сохраняют существующий lowercase contract.
- Добавлен release-specific regression gate для operator-facing capitalization и стабильности technical identifiers. SQLite schema, provisioning semantics, pinned 3x-ui/OpenAPI contract и mutation behavior не меняются; `v4.20.8` устанавливается обычным Safe Bot Self-Update без host-side обновления Agent/helper.

## v4.20.7 — Единая терминология Inbound / Inbounds
- Во всём актуальном operator-facing UI гибридные формы с апострофом заменены на канонические `Inbound` / `Inbounds`: кнопки, заголовки, status/summary строки, ошибки, подсказки, RBAC labels, audit summaries и client-facing тексты используют единый terminology contract.
- README, Admin Setup, Roadmap и UI Style синхронизированы с тем же контрактом; `docs/UI_STYLE.md` явно запрещает русифицированные склонения `Inbound` через апостроф.
- Technical identifiers остаются стабильными: callback data, API/DB fields, Python identifiers, module names и enum не переименовываются; historical release notes не переписываются задним числом.
- Добавлен repo-wide regression/source-audit, запрещающий возврат гибридных operator-facing форм. SQLite schema, provisioning semantics, pinned 3x-ui/OpenAPI contract, Host Control/Deploy Agent API, callback identity и mutation safety не меняются; `v4.20.7` устанавливается обычным Safe Bot Self-Update без host-side обновления Agent/helper.

## v4.20.6 — Симметричный health summary Master и нод
- `Мониторинг → Состояние системы` приведён к общему presentation contract для Master и direct nodes: одинаковые доступные health-метрики используют одинаковые labels, status grammar и emoji.
- Direct node теперь явно показывает общий статус рядом с identity, отдельный статус панели и Xray state + version; `unknown` для Xray отображается отдельным жёлтым состоянием, а не ложным binary failure.
- CPU, RAM, uptime и Inbound'ы имеют симметричные подписи; Master-only disk/Subscription Proxy/nginx-TLS/DB/backup показатели остаются только у Master, а node-only latency/client/online counters сохраняются у direct nodes.
- Дополнительные API-вызовы к direct nodes ради визуального выравнивания не добавлялись; `docs/UI_STYLE.md` закрепляет правило «одинаково представлять одинаковые доступные данные».
- Добавлены regression tests на online/offline/maintenance и tri-state Xray presentation. SQLite schema, pinned 3x-ui/OpenAPI contract, callback identity и mutation safety semantics не меняются; `v4.20.6` устанавливается обычным Safe Bot Self-Update без host-side обновления Agent/helper.

## v4.20.5 — Финальная консистентность Admin UI
- `Инфраструктура → Операции с нодами → Состояние нод` теперь использует общий `node_display_name()` для direct nodes, поэтому operator-facing имя и country presentation fallback совпадают с остальными экранами.
- Список `Ноды` приведён к общей грамматике `identity · status icon status text`: Master и direct nodes явно показывают текстовый online/offline/unknown/maintenance status, сохраняя `node_id` как machine identity.
- `Обзор` стал обычным дочерним экраном `Панели администратора`: корневой `admin_menu()` больше не остаётся под dashboard-content, вместо него используются локальные `🔄 Обновить` и `⬅ Панель администратора`.
- Добавлены targeted regression tests для Fleet Health, списка нод и dashboard navigation; соответствующие display/navigation rules остаются закреплены в `docs/UI_STYLE.md`.
- SQLite schema, pinned 3x-ui/OpenAPI contract, Host Control/Deploy Agent API и mutation safety semantics не меняются; `v4.20.5` устанавливается обычным Safe Bot Self-Update без host-side обновления Agent/helper.

## v4.20.4 — Admin UI consolidation и единое отображение нод
- Карточка пользователя сведена к одному каноническому `admin:u:<tg_id>` flow: список `Пользователи` больше не открывает отдельную legacy-карточку, а `adminuser:<tg_id>` сохранён как compatibility route для старых Telegram-сообщений и рендерит ту же карточку.
- Repo-wide operator-facing node labels переведены на общий `node_display_name()` там, где отображается direct node: Monitoring, Fleet, Logs, Host Control, DR, Versions & Updates, Inbound UI, node backup summaries и связанные nested screens. Master остаётся отдельной сущностью; callback/binding identity по-прежнему строится по `node_id`/существующим machine identifiers, а не по display name.
- `Версии и обновления` получил симметричный overview Master/direct nodes: на главном экране показываются версии компонентов без лишнего Xray runtime-state, а состояние Xray остаётся на detail-screen конкретного сервера.
- Direct-node Xray log empty-state больше не выглядит как сломанный источник: проверено соответствие запроса pinned 3x-ui `v3.8.5` (`/panel/api/server/xraylogs/{count}` + `filter/showDirect/showBlocked/showProxy`); endpoint читает отдельный Xray access log, поэтому служебные `XRAY:`-события панели могут быть видны в журнале 3x-ui при пустом access log. UI теперь объясняет это различие.
- `Журнал аудита` получил читаемые summaries для bot self-update и отдельный read-only detail view с полными `details`, поэтому длинная диагностика больше не теряется из-за жёсткого 140-символьного обрезания.
- Operator-facing тексты очищены от лишних implementation details: `/create` заменён на понятное описание новых пользователей/создания доступа, `.env` — на локальную/административную конфигурацию, а основной экран `Роли и права` показывает человекочитаемые labels без внутренних permission IDs.
- `docs/UI_STYLE.md` закрепляет единый direct-node display contract и запрещает runtime-логику, привязанную к конкретной production-географии; `docs/ROADMAP.md` отдельно фиксирует optional `country_code`/ISO metadata как будущую неблокирующую задачу, не входящую в `v4.20.4`.
- Добавляется regression/source-audit coverage для user-card compatibility, node-display policy, audit detail RBAC и operator-facing text cleanup. SQLite schema, pinned 3x-ui/OpenAPI contract, Host Control/Deploy Agent API и mutation safety semantics не меняются; `v4.20.4` рассчитан на обычный Safe Bot Self-Update без host-side обновления Agent/helper.
## v4.20.3 — Production smoke fixes для backup integrity и Admin UI
- Исправлен Full Backup integrity contract: корневой `manifest.json` по-прежнему не хеширует сам себя, но nested `nodes/*/manifest.json` теперь входит в `integrity.files`; embedded node backup проходит `RestoreManager.inspect_backup()` без ложной ошибки `manifest integrity не покрывает файлы`.
- В Disaster Recovery detail/preflight и история восстановления возвращаются к непосредственному parent `Аварийное восстановление`; restore остаётся fail-closed и Owner-only, mutation semantics не менялись.
- Detail подписки сохраняет контекст входа: из top-level `Подписки` Back возвращает в `Подписки`, а из карточки пользователя — к пользователю; отдельный `adminsublist:<tg_id>` зарегистрирован в RBAC как `read_only`.
- `Состояние системы` теперь имеет локальный `Обновить` и `Назад в Мониторинг`; Server Groups используют общий `node_display_name()`, поэтому direct nodes отображаются единообразно, например `🇫🇮 Finland`.
- Убраны stale operator-facing версии `v4.5`/`v3.9`, сокращена обрезавшаяся подпись inbound sync и устранена тавтология `Master: <flag> Master` на экране настроек.
- Regression coverage расширен на production smoke findings, включая реальный Full Backup → restore inspection contract; SQLite schema, 3x-ui/OpenAPI, Host Control API, Deploy Agent/helper и privilege boundaries не изменены. `v4.20.3` устанавливается обычным Safe Bot Self-Update без host-side обновления Agent/helper.

## v4.20.2 — Исправление parent navigation Admin Control Plane
- Исправлены отклонения от существующего navigation-контракта `docs/UI_STYLE.md`: вложенные экраны возвращаются к фактическому непосредственному parent, а validation/error paths не теряют Back/Cancel.
- `Система → Обновления бота → История обновлений` теперь возвращает в `Обновления бота`; node log view — к источникам выбранной ноды; Host Control и Disaster Recovery сохраняют корректный parent/Cancel в typed-confirmation/error flows.
- Owner unlock flow в `Версии и обновления` получил отдельный read-only operation view `admin:ver:op:<nonce>`, чтобы Cancel возвращал к исходной операции без повторного update/recheck mutation; callback зарегистрирован в RBAC как `read_only`.
- Regression coverage расширен на nested parent flows; source-audit admin UI подтверждает, что без навигации остаются только намеренные progress/transition screens и существующие terminal authorization guards.
- SQLite schema, 3x-ui/OpenAPI contract, Host Control API, Deploy Agent API/host helper и privilege boundaries не изменены; `v4.20.2` можно устанавливать обычным Safe Bot Self-Update без отдельного host-side обновления Agent/helper.

## v4.20.1 — Safe Bot Self-Update release-notes hotfix
- Исправлен intermittent blocker Safe Bot Self-Update: `notes_cmd` больше не использует SIGPIPE-sensitive pipeline `printf | awk` под `set -o pipefail`, из-за которого корректный published release иногда отклонялся как `release_notes_missing` с exit code 141.
- Release notes по-прежнему читаются только из `CHANGELOG.md` целевого опубликованного тега после обычной release validation; fail-closed поведение при реально отсутствующих/ошибочных notes сохраняется.
- Deploy Agent version повышена до `0.1.2`, чтобы установленный host-side control plane можно было однозначно отличить от версии с дефектным helper.
- Добавлен regression source-contract, запрещающий возврат SIGPIPE-sensitive notes pipeline; API surface, sudoers allowlist, mutation semantics, SQLite schema и 3x-ui compatibility contract не изменены.
- Поскольку helper устанавливается host-side и не заменяется пересозданием bot container, перед повторной попыткой self-update production Deploy Agent должен быть обновлён до host bundle из `v4.20.1`.

## v4.20.0 — Подготовка Admin Control Plane к заморозке
- Завершена декомпозиция runtime: `bot.py` оставлен минимальным executable shim, lifecycle/startup/recovery вынесены в `app_runtime.py`, client flow — в `client_access.py`, admin shell и domain handlers — в отдельные routers с закреплённым single ownership.
- Telegram UI Admin Control Plane системно приведён к русской локализации при сохранении технических identifiers, фиксированных RBAC role names и typed confirmation phrases; regression gate блокирует возврат смешанного operator-facing UI.
- Проведён repo-wide аудит информационных emoji/status/resource префиксов и навигации `/admin`: убраны дублирующие входы, выровнены Back/Refresh/Cancel/Confirm flows и закрыты callback/FSM dead ends без изменения domain semantics.
- README и актуальные operator runbook'и синхронизированы с текущей архитектурой и русскими UI-paths; public-facing примеры очищены от private deployment привязок и защищены отдельным public-readiness regression contract.
- Добавлены regression/source-inspection gates на runtime/router ownership, Admin navigation, UI localization, emoji conventions и актуальность public documentation; SQLite schema, pinned 3x-ui OpenAPI contract и существующие Host Control/Deploy Agent privilege boundaries не расширяются.
- Релиз закрывает cleanup/freeze-prep scope раздела roadmap «Желательно закрыть до финальной заморозки v4.x»; отдельный production drill encrypted off-site backup/restore остаётся обязательным pre-v5 gate перед окончательной заморозкой v4.x.

## v4.19.1 — Safe Bot Self-Update acceptance hotfix
- Исправлен production blocker Deploy Agent под hardened systemd sandbox: root helper теперь задаёт отдельный `DOCKER_CONFIG=/var/lib/3xui-deploy-agent/docker-config`, поэтому `docker compose build` не пытается создать `/root/.docker` при `ProtectHome=true`.
- Installer создаёт отдельный root-only writable Docker config directory внутри уже разрешённого `/var/lib/3xui-deploy-agent`; privilege boundary, sudoers allowlist и отсутствие Docker socket в bot container не меняются.
- Release notes стали обязательной частью успешного Deploy Agent preflight: ошибка/timeout/missing notes теперь fail-closed, а не маскируются пустым блоком в Telegram.
- Same-release production acceptance отображается как `same release`, а не как `upgrade`.
- Hotfix закрывает defect, найденный при первом production acceptance `v4.19.0`: операция остановилась после verified backup и checkout, до `deploying`/container recreate, с `deploy_command_failed_before_dispatch`.

## v4.19.0 — Safe Bot Self-Update
- Добавлен отдельный restricted Deploy Agent вне bot container: unprivileged systemd service, bearer-authenticated fixed API и persistent SQLite journal с stable `operation_id` и состояниями `queued/preflight/backup/building/deploying/verifying/success/failed/unknown`.
- Bot container по-прежнему не получает Docker socket, host shell, Git deploy key или arbitrary filesystem access; root boundary сведена к одному root-owned helper с закрытым command surface для published `vX.Y.Z` releases.
- Published release validation проверяет tag в `origin/main`, exact `APP_VERSION`, pinned SSH known_hosts, clean tracked tree и текущий Health/DB/3x-ui status; release notes читаются read-only из target `CHANGELOG.md` без выполнения target code.
- `/admin → System → Bot Updates` доступен только Owner: current/latest, release notes, preflight, exact published tag selection, operation history/status и явный update confirmation. Downgrade требует точной фразы `DOWNGRADE vX.Y.Z` и повторного preflight.
- Потерянный deploy response и restart bot/agent никогда не приводят к автоматическому mutation replay: bot и agent восстанавливают результат только через read-only operation/status lookup; недоказанный итог становится `unknown`.
- Startup recovery двухфазный: мгновенный lookup выполняется до generic stale cleanup, а ожидание terminal state начинается только после поднятия health endpoint, поэтому self-update не блокирует post-deploy health check.
- Manual и agent deployment используют общий host lock под deploy backup root; ручной `scripts/deploy-release.sh vX.Y.Z` остаётся break-glass fallback.
- Добавлены installer/systemd/sudoers tooling, isolated root-only Git key/known_hosts copy, private Docker-bridge listener и regression/security tests; SQLite app schema, 3x-ui OpenAPI contract, Host Control API и off-site backup contract не меняются.

## v4.18.0 — Encrypted off-site backup
- Full Backup manifest переведён на checksummed schema 2: для каждого обычного файла архива фиксируются path, size и SHA-256, а restore validation проверяет coverage/size/hash fail-closed; legacy archives остаются читаемыми обычным DR tooling.
- Добавлена optional S3-compatible off-site replication, выключенная по умолчанию: canonical Full Backup шифруется client-side AES-256-GCM до upload, а bucket/prefix/endpoint/credentials задаются только локально и не управляются через Telegram.
- Local backup и external replication имеют независимые outcomes: `backup.daily`/`backup.manual` фиксируют локальный archive, `backup.offsite` — внешний upload; ошибка provider-а не превращает уже созданную локальную копию в false failure.
- Off-site success требует remote round trip: HEAD metadata verification, download, GCM authentication, plaintext SHA-256/size и повторный deep Full Backup validation; retention выполняется только после подтверждённой читаемости.
- Добавлен host-side `scripts/fetch-offsite-backup.py`: recovery CLI получает latest canonical object только из fixed prefix, decrypt/validates его и выдаёт mode-0600 archive для существующего `bootstrap-bot-from-backup.sh`.
- Добавлены regression tests на manifest tampering, encryption/round trip, fixed-prefix retention, target security boundaries и отдельный failed `backup.offsite` job; SQLite schema, 3x-ui API, Host Control API и RBAC не изменены.

## v4.17.0 — 3x-ui OpenAPI compatibility gate
- Поддерживаемый native API contract зафиксирован на 3x-ui `v3.8.5`: vendored OpenAPI берётся из immutable upstream tag, а exact Git blob SHA хранится в contract manifest.
- `contracts/3xui/contract.json` описывает 51 реально используемый endpoint; CI проверяет route/method, Bearer auth, request body required/media type/mandatory fields и общий JSON response envelope.
- AST source-parity check сопоставляет manifest с фактическими `/panel/api/...` вызовами в `xui.py` и `version_api.py`, поэтому новый или удалённый route требует явного contract review до merge.
- Проверка полностью offline/stdlib-only: CI не скачивает upstream `main` и runtime не переключается автоматически на неизвестную API schema.
- Единственное documented response exception — `GET /panel/api/server/getDb`: OpenAPI v3.8.5 описывает generic JSON envelope, а live endpoint возвращает binary DB attachment; route/method/auth остаются под gate, binary semantics покрываются отдельными regression tests.
- Добавлены regression tests на missing method, новый mandatory field, response-envelope drift, schema tampering и dynamic route discovery; SQLite schema, runtime 3x-ui requests, Host Control API и deployment topology не изменены.

## v4.16.0 — Regression coverage hardening
- Добавлен целевой regression pack для критических admin/business/recovery путей: payment/status и catalog relations, user lifecycle mutation ordering, provisioning idempotency/partial failure, subscription proxy compatibility/error paths, inbound mutation failure paths, disaster recovery и negative authorization boundaries.
- Safe/strict provisioning теперь явно проверяются на разные privilege boundaries: per-user safe reconcile доступен роли `support`, strict reconcile остаётся `admin`; regression tests выявили и исправили drift, при котором privilege catalog излишне требовал `admin` и для safe reconcile.
- User lifecycle tests подтверждают, что local expiry/record/subscription identity не меняются раньше успешной state-changing операции в 3x-ui; failed remote delete сохраняет локальную запись.
- Provisioning tests фиксируют повторный safe reconcile без лишних mutations, stop-safe strict semantics, недоступные node как partial result и изоляцию batch failure одного пользователя от остальных.
- Subscription proxy и restore tests покрывают plain/Base64 subscriptions, selective `vpn://` conversion, Shadowrocket compatibility, invalid `sub_id`, upstream failures, unsafe/malformed backup, staged SHA mismatch, rescue copy и отсутствие replay broken restore.
- Схема SQLite, 3x-ui API contract, Host Control API и deployment topology не изменены.

## v4.15.0 — Versioned SQLite migrations
- Добавлен versioned migration framework для локальной `bot.sqlite3`: source of truth хранится в `schema_migrations`, migrations идут только вперёд и имеют стабильные version/name.
- Текущая схема v4.14.2 оформлена как идемпотентная baseline migration `v1 baseline_v4_14_2`, поэтому существующие installation без migration journal обновляются in-place с сохранением данных.
- Startup работает fail-closed для `running`/`failed` migration, gap/unknown journal, более новой schema version, schema mismatch и failed `PRAGMA quick_check`; неопределённая state-changing migration автоматически не replay'ится.
- Dangerous migrations с `requires_backup=True` до mutation создают проверенную SQLite Online Backup recovery copy в persistent `data/migration-backups/`; автоматических down migrations и automatic restore нет.
- Добавлены regression tests для fresh/legacy DB, newer schema, interrupted/failed migration, обязательной recovery copy и rollback, а operational/developer contract зафиксирован в `docs/SQLITE_MIGRATIONS.md`.
- Схема 3x-ui, Host Control API, RBAC privilege boundaries, provisioning и subscription semantics не изменены.

## v4.14.2 — Исправление guided onboarding direct node
- Исправлен разбор аргументов `--admin-enrollment` и `--host-control-enrollment` в `scripts/onboard-direct-node.sh bind`: значения теперь попадают в канонические переменные, поэтому guided bind проходит preflight/import вместо ложной ошибки отсутствующих enrollment files.
- Добавлен исполняемый regression test, который запускает `bind` с временными enrollment-файлами и проверяет фактические вызовы direct-admin и Host Control importer preflight.
- Security boundary не меняется: node-sync, direct-admin и Host Control credentials остаются раздельными; mutation semantics, stable `node_id` binding и single bot recreate сохранены.

## v4.14.1 — Исправление Host Control snapshot rollout
- Исправлено чтение nginx snapshot в bot client: streaming HTTP response теперь читается до EOF с сохранением жёсткого лимита 10 MiB, поэтому multi-chunk ответы reverse proxy больше не дают ложный `checksum_mismatch`.
- Installer Host Control Agent теперь явно перезапускает `3xui-host-control.service` после обновления runtime files/unit, поэтому повторный rollout действительно активирует новую версию agent без ручного restart.
- Добавлены regression tests для multi-chunk snapshot response и upgrade restart path; security boundary fixed snapshot endpoint, host identity/TLS/checksum validation и mutation allowlist не расширены.

## v4.14.0 — RBAC и расширенные node snapshots
- Добавлен централизованный каталог RBAC privileges для фиксированных ролей `Read-only`, `Support`, `Administrator` и `Owner`; authorization layer использует его как source of truth, неизвестные admin callbacks блокируются fail-closed, а `/admin → Administrators → Roles & Privileges` показывает действующие permission boundaries.
- Direct-node backup расширен до recovery-oriented snapshot `nodes/<node>/` с `x-ui.db`, `nginx/`, `node.json` и `manifest.json`; manifest хранит stable node identity, component status, доступные версии, размеры и SHA-256 файлов, а тот же snapshot включается в обычный Full Backup.
- Host Control Agent получил fixed read-only `GET /v1/snapshots/nginx`: endpoint не принимает filesystem path/filename/query selector, читает только локально настроенный `HOST_CONTROL_AGENT_NGINX_SOURCE` и не расширяет mutation allowlist за пределы `start|stop|restart`.
- Отсутствующий или частично недоступный nginx source отражается как `degraded`/missing component, а не как ложный complete; bot дополнительно валидирует host identity, transport checksum, tar paths, file sizes и per-file checksums.
- Для nginx snapshot source используется отдельный optional `/etc/3xui-host-control/nginx-snapshot.env`, который не входит в enrollment/bot `.env`; automatic remote nginx restore не добавлен, схема SQLite не изменена.
- Добавлены regression/security tests для RBAC route coverage/fail-closed, fixed Host Control snapshot surface, archive integrity/path traversal и полного/degraded node backup.

## v4.13.2 — Host Control startup recovery
- Startup бота теперь запускает `recover_control_jobs()` сразу после `db.init()` и до общего stale-job cleanup, поэтому незавершённые Host Control jobs получают шанс восстановить точный итог из persistent operation journal.
- Recovery использует только read-only lookup сохранённого `operation_id`; state-changing Host Control mutation после рестарта автоматически не повторяется, а недоказуемый результат остаётся `unknown`.
- Добавлены regression tests на порядок startup recovery и отсутствие mutation replay; схема SQLite, Host Control Agent API и privilege boundaries не изменены.
## v4.13.1 — Исправление Fleet Rollout jobs
- Исправлен accounting `Controlled Rollout`: terminal no-op plan с уже актуальными версиями теперь создаёт и завершает parent `fleet.rollout` job со статусом `success`.
- Отмена rollout до запуска canary теперь также фиксируется parent `fleet.rollout` job со статусом `cancelled`, поэтому `🧾 Fleet Jobs` и audit отражают terminal operation.
- Для уже актуальных targets summary parent job использует `skipped`, а не `pending`; update/maintenance mutation при этих сценариях по-прежнему не отправляется.

## v4.13.0 — Fleet Operations
- Добавлен раздел `🌐 Fleet Operations` с read-only `Fleet Health`, controlled Fleet Maintenance, Fleet Jobs и последовательным rollout для direct nodes.
- `Controlled Rollout` переиспользует существующий two-phase `UpdateService`: verified backup выполняется до intentional maintenance, затем update запускается строго по одной node с canary и explicit continue.
- Rollout работает stop-on-failure: при `failed` или `unknown` проблемная node остаётся в maintenance, оставшиеся nodes не затрагиваются, state-changing request автоматически не повторяется.
- Rollout eligibility требует direct online node, доступные Direct Panel API и Host Control, а также stable `node_id` binding для обоих privileged targets; transitive и legacy-name targets не мутируются.
- После рестарта незавершённые fleet operations помечаются interrupted/unknown и не продолжаются автоматически; mass `Stop service` / `Stop Xray`, parallel rollout и automatic rollback намеренно не добавлены.
- Scope и safety contract зафиксированы в `docs/FLEET_OPERATIONS.md`.

## v4.12.0 — Guided onboarding direct node
- Добавлен guided wrapper `scripts/onboard-direct-node.sh`: `prepare` собирает/опционально копирует secret-free Host Control bundle и формирует remote install command, `bind` проводит node registration и оба privileged bindings через единый stable `NODE_ID`.
- `import-node-admin-target.py` получил `--node-id`; ID из enrollment и explicit override проверяются на совпадение fail-closed.
- Guided flow сохраняет разделение node-sync/direct-admin/Host Control secrets, выполняет importer preflights до изменения bot `.env` и пересоздаёт только service `bot` один раз.

## v4.11.1 — Исправление Readiness callback
- Исправлен routing кнопки `🧭 Readiness`: общий handler карточки ноды больше не перехватывает callback `admin:node:<id>:readiness`.
- Node detail handler теперь принимает только точный callback `admin:node:<id>`, а readiness сохраняет отдельный маршрут.
- Добавлен regression-test, который блокирует возврат broad `admin:node:` startswith-handler.
- Stable `NODE_ID` bindings, onboarding helpers, privilege boundaries и схема SQLite не изменены.

## v4.11.0 — Node readiness и безопасный onboarding
- Privileged targets для direct nodes получили стабильную привязку к 3x-ui `node.id` через `NODE_BACKUP_*_NODE_ID` и `HOST_CONTROL_*_NODE_ID`; старый lookup по display name сохранён только как backward-compatible fallback.
- Explicit mismatched `NODE_ID` работает fail-closed: target, привязанный к другому node ID, не может быть подобран только по совпавшему имени.
- Переименование direct node больше не ломает backup, restore, Versions & Updates, Panel/Xray controls и Host Control при наличии stable `NODE_ID`.
- В карточку direct node добавлен read-only экран `🧭 Readiness`: он проверяет Master view, direct Panel API, Host Control Agent, runtime readiness и тип binding без mutation.
- Добавлен `scripts/onboard-node.py` для регистрации node локально на Master из mode-0600 enrollment-файла: по умолчанию только preflight, mutation выполняется только с `--apply`, automatic retry отсутствует.
- Добавлен `scripts/import-node-admin-target.py` для безопасного импорта dedicated direct-admin credential; Host Control enrollment importer получил `--node-id`.
- Рекомендуемый onboarding больше не требует передачи node-sync/direct-admin/Host Control secrets через Telegram; privilege domains остаются раздельными.
- Новые onboarding helpers требуют verified HTTPS для новых direct node/admin endpoints и не печатают secrets.
- Добавлен runbook `docs/NODE_ONBOARDING.md` и regression tests для stable identity, legacy fallback, fail-closed mismatch, local enrollment permissions и onboarding transport policy.
- Схема SQLite, provisioning пользователей, подписки и privilege boundary Host Control Agent не изменены.

## v4.10.1 — Operational rollout и recovery
- Добавлен `scripts/bootstrap-bot-from-backup.sh` для восстановления Telegram-бота на подготовленном новом VPS из Full Backup с проверкой tag/APP_VERSION, tar safety, SQLite `quick_check`, rescue-copy и post-check через `deploy-release.sh --status`.
- Recovery по умолчанию требует совпадения версии backup с целевым release; intentional mismatch возможен только через `RECOVERY_ALLOW_VERSION_MISMATCH=1`.
- При recovery намеренно отключаются `HOST_CONTROL_TARGETS` и `NODE_BACKUP_TARGETS`, чтобы privileged routes/tokens старого deployment не активировались автоматически.
- Добавлен воспроизводимый Host Control rollout: secret-free deployment bundle, отдельный restricted proxy, enrollment-importer для безопасного обновления bot `.env`, идемпотентное добавление target и recreate только service `bot`.
- Remote Host Control proxy получил ежедневный TLS refresh timer: source certificate/key проверяются на hostname и соответствие пары, proxy reload выполняется только при обновлении копий.
- Повторный rollout с `--apply-ufw` хранит managed firewall state и при изменении management source/destination/port удаляет прежнее exact allow-rule перед добавлением нового.
- Добавлены runbook `docs/HOST_CONTROL_ROLLOUT.md`, `docs/VPS_RECOVERY.md`, новые unit/security tests и CI-проверки executable bit/shell syntax для operational helpers.
- Runtime semantics экрана `🧩 3x-ui Control`, privilege boundary Host Control Agent, схема SQLite и provisioning пользователей не изменены.

## v4.10.0 — Безопасный 3x-ui Control
- Реализован restricted `Host Control Agent` для host-level `status/start/stop/restart x-ui.service`: listener только `127.0.0.1`, отдельный token на host, fixed service/action allowlist, `shell=False`, persistent `operation_id`, lost-response recovery без повторного mutation POST.
- Добавлен единый экран `🧩 3x-ui Control` для Master и direct nodes: `Start/Restart service` доступны Admin+, destructive `Stop service` и `Stop Xray` — только Owner; Stop service требует одноразовую typed-фразу `STOP <target>`.
- Добавлены native действия `♻️ Restart Panel process` через `POST /panel/api/setting/restartPanel`, `Stop Xray` через `/server/stopXrayService` и `Restart / Start Xray` через `/server/restartXrayService`.
- Агент не предоставляет SSH/shell/exec/file/Docker/firewall/reboot/package-management API; systemd unit запускает его непривилегированным пользователем, а sudoers разрешает только три точных команды для `x-ui.service`.
- Remote host-control targets требуют verified HTTPS; private HTTP разрешён только для локального `MASTER` через restricted management route.
- Добавлены installer/systemd/sudoers assets, production deployment guide и CI-проверки executable bit, shell syntax, `visudo`, transport policy, host identity, no-retry, privilege boundary и security invariants.

## v4.9.3 — Исправление счётчиков карточки ноды
- Карточка `Infrastructure → Nodes → <node>` теперь использует enriched-данные `/panel/api/nodes/list` для вычисляемых счётчиков `inboundCount`, `clientCount`, `activeCount` и `onlineCount`.
- При недоступности list API или отсутствии нужной ноды сохраняется fallback на `/panel/api/nodes/get/{id}`, поэтому административные действия не блокируются.
- Исправлен визуальный эффект, при котором рабочая удалённая нода показывала `Inbound'ов: 0` и `Клиентов: 0`, несмотря на реально синхронизированные inbound'ы и активный трафик.
- Схема SQLite, provisioning, подписки, direct admin target и управление версиями не изменены.

## v4.9.2 — Deploy helper и улучшения System/Reality
- Добавлен `scripts/deploy-release.sh` для повторяемого развёртывания опубликованных тегов на VPS.
- Перед cutover helper проверяет тег, `APP_VERSION`, текущее здоровье сервиса, SQLite, upstream 3x-ui и соответствие Docker-подсети.
- Перед обновлением сохраняются `.env`, Compose-конфигурация, SHA/образ текущего состояния и согласованная копия `bot.sqlite3`.
- Helper пересоздаёт только сервис `bot` и намеренно не выполняет `docker compose down`, `docker system prune`, обновление 3x-ui/Xray или автоматический откат базы.
- Добавлены режим `--status`, явная защита от случайного downgrade и CI-проверка shell-синтаксиса helper.
- В разделе `System` отображается текущая версия бота из единственного `APP_VERSION`.
- Reality fingerprint inbound'а выбирается кнопками из актуального списка 3x-ui: `chrome`, `firefox`, `safari`, `ios`, `android`, `edge`, `360`, `qq`, `random`, `randomized`, `randomizednoalpn`, `unsafe`.
- Произвольный ручной ввод fingerprint из Telegram удалён; остальные `Reality`/`streamSettings` сохраняются при изменении.
- Схема SQLite и логика подписок не изменены.

## v4.9.1 — Стабилизация сети и интерфейса
- Docker-подсеть проекта закреплена через `BOT_DOCKER_SUBNET` с дефолтом `172.19.0.0/16`, чтобы пересоздание Compose-сети не меняло источник трафика к локальной панели 3x-ui.
- В документацию добавлено требование синхронизировать UFW-правило для порта панели с выбранной Docker-подсетью.
- CI дополнен проверкой `docker compose config` на основе `.env.example`.
- Навигация `Versions & Updates` приведена к общему стилю административной панели с явными кнопками возврата, обновления, подтверждения и пагинации.
- Все статические inline-кнопки пользовательского и административного интерфейса приведены к правилу с emoji или навигационным символом; CI проверяет новые статические кнопки на соответствие этому правилу.
- Схема SQLite, API-контракты 3x-ui и логика подписок не изменены.

## v4.9.0 — Версии и обновления
- Добавлен общий раздел `Versions & Updates` и переходы из карточек Master и нод.
- Добавлены явный выбор стабильного канала обновления 3x-ui и установка конкретной версии Xray.
- Перед установкой создаётся и проверяется свежая резервная копия; используются одноразовое подтверждение с ограниченным сроком действия, сохраняемая блокировка сервера и проверка результата обновления.
- Проверяются идентификаторы запуска обновления панели; потеря ответа не приводит к автоматической повторной отправке команды.
- Просмотр доступен роли `Read-only`, установка — `Admin` и `Owner`; снятие блокировки при неподтверждённом результате требует явного подтверждения `Owner`.
- Повторно используются существующие таблицы аудита и заданий; схема SQLite не изменена.
- Введён единый `APP_VERSION`, исправлены устаревшие номера версии в манифестах резервных копий.
- Добавлены автоматизированные тесты API, сценариев обновления и интеграции, а также проверки PR в CI с правами только на чтение.

## v4.8.0 — Админ-панель в одном сообщении
- Админ-панель переведена на одно обновляемое сообщение Telegram.
- Навигация встроенными кнопками, включая Back/Refresh/Confirm, больше не засоряет чат новыми сообщениями.
- FSM-формы возвращают пользователя в исходную панель; введённые служебные сообщения по возможности удаляются.
- Файлы, уведомления и внешние события намеренно остаются отдельными сообщениями.

## v4.7.0 — Аварийное восстановление
- Добавлен защищённый сценарий восстановления для `bot.sqlite3`, базы 3x-ui на Master и баз нод.
- Добавлены предварительная проверка без применения изменений, SQLite `quick_check`, аварийные копии текущего состояния и двойное подтверждение.
- Восстановление базы бота выполняется на этапе начальной загрузки до запуска основного процесса.
- `bot.env` и конфигурация nginx доступны для извлечения, но не восстанавливаются автоматически.

## v4.6.0 — Журналы и уведомления
- Добавлен централизованный просмотр журналов бота, 3x-ui, Xray, AmneziaWG и nginx.
- Добавлены фильтры `ALL`/`WARN+`/`ERROR` и ограничение количества последних строк.
- Добавлены правила уведомлений: недоступность Master/Xray/ноды, ошибка задания, превышение порога использования диска и устаревшая резервная копия.
- Добавлены уведомления о восстановлении, интервалы между повторными оповещениями и маскирование чувствительных данных в журналах.

## v4.5.0 — Механизм назначения ресурсов пользователям
- Связана цепочка `Plan → Server Group → Nodes → Inbounds → User`.
- Для Server Group добавлена политика назначения ресурсов: все управляемые inbound'ы или выбранный набор.
- Добавлены предварительный просмотр и оценка расхождений для пользователя, безопасное согласование `Safe reconcile` и строгое согласование `Strict reconcile`.
- Добавлено массовое согласование пользователей с учётом их политик.
- Тариф по умолчанию может управлять `/create`; прежний пробный режим сохраняется как резервный вариант.

## v4.4.0 — Расширенное управление нодами
- Расширена карточка ноды: состояние, версии, ресурсы, задержка ответа API, inbound'ы и активные подключения.
- Добавлены проверка соединения и повторная проверка, режим обслуживания, переименование, резервное копирование отдельной ноды и перезапуск Xray.
- Добавлены штатное обновление 3x-ui и безопасное удаление ноды с проверками.

## v4.3.0 — Расширенное управление inbound'ами
- Добавлены карточки inbound'ов и список клиентов.
- Добавлены безопасное редактирование, включение/отключение, синхронизация, сброс трафика и клонирование.
- Добавлены шаблоны inbound'ов и их развёртывание на Master и нодах.
- Приватные ключи не выводятся в интерфейсе Telegram.

## v4.2.0 — Расширенное управление пользователями
- Добавлено управление сроком действия, трафиком, лимитом IP, тарифом, группой серверов и заметкой пользователя.
- Добавлены управление inbound'ами пользователя, сброс трафика и смена идентификатора подписки.
- Добавлены массовые действия над пользователями.
- Добавлена таблица `user_profiles` без изменения существующей `users`.

## v4.1.0 — Платежи и администрирование
- Добавлены внутренний реестр платежей `Payments` и каталог промокодов `Promo Codes`.
- Добавлены администраторы с ролями `Owner` / `Administrator` / `Support` / `Read-only`.
- `ADMIN_TELEGRAM_IDS` остаются защищёнными владельцами `Owner`.
- Добавлены безопасные настройки времени выполнения для параметров пробного доступа и валюты по умолчанию.

## v4.0.0 — Мониторинг, задания и аудит
- Добавлены разделы `Monitoring → Traffic` и `Online`.
- Добавлены разделы `System → Jobs` и `Audit Log`.
- Добавлены общая блокировка заданий резервного копирования и журналирование действий администраторов.
- Главная страница `Dashboard` дополнена сводкой мониторинга и состояния системы.

## v3.9.0 — Тарифы, группы серверов и адреса
- Добавлены тарифы `Plans` со сроком действия, объёмом трафика, лимитом IP, ценой и статусом.
- Добавлены группы `Server Groups` и привязка серверов.
- Добавлены реестр `Hosts` и обнаружение используемых адресов.

## v3.8.0 — Основа рабочей админ-панели
- Админка реорганизована в `Dashboard` / `Users` / `Subscriptions` / `Payments` / `Plans` / `Promo Codes` / `Infrastructure` / `Monitoring` / `System`.
- Существующая бизнес-логика сохранена; изменён в основном навигационный слой.
- Добавлены рабочая сводка `Dashboard` и отдельный раздел подписок `Subscriptions`.

## v3.7.2 — Добавление нод из Telegram
- Добавлен мастер `➕ Добавить ноду` через Telegram.
- Добавлены проверка соединения, выбор режима проверки TLS и вызовы штатного API нод 3x-ui.
- Текст пустого списка нод сделан нейтральным.

## v3.7.1 — Карточка Master
- Master отображается первой полноценной карточкой в разделе `Nodes`.
- Master учитывается в общем числе серверов и доступных серверов и открывается как отдельная карточка состояния.

## v3.7.0 — Основа работы с несколькими нодами
- Добавлена интеграция со штатным API 3x-ui для управления несколькими нодами.
- Добавлены отображение нод в `System Health` и подготовка резервного копирования их баз данных.
- Заложена основа для первой внешней ноды.

## v3.6.0 — Резервное копирование
- Добавлен раздел `Backups` в `/admin`.
- Добавлены ручные и ежедневные резервные копии с ограничением числа хранимых архивов.
- Полный архив включает базу бота, базу 3x-ui, `.env`, Compose и nginx при их доступности.
- Добавлен `.dockerignore`, чтобы секреты и рабочие данные не попадали в контекст сборки образа.

## v3.5.5 — Состояние сервера и ограничение журналов Docker
- В админку добавлен раздел `Состояние сервера`.
- Добавлены показатели диска, оперативной памяти, времени работы и проверки доступности.
- Журналы Docker `json-file` ограничены размером `10m × 3`.

## v3.5.4 — Совместимость Shadowrocket с XHTTP
- Для Shadowrocket в машинном формате подписки удаляется `fp` только у `VLESS + XHTTP + Reality`.
- INCY и TCP Reality сохраняют прежнее поведение.
- Клиент определяется по `User-Agent`.

## v3.5.3 — Синхронизация VLESS XTLS flow
- Добавлены настройка `VLESS_FLOW` и синхронизация `flow` для VLESS-клиентов там, где это применимо.

## v3.5.2 — Штатное отображение AmneziaWG на странице 3x-ui
- HTML-режим прокси совместимости больше не переписывает `vpn://` внутри страницы 3x-ui.
- Машинный формат подписки продолжает преобразование в `amneziawg://` для совместимых клиентов.

## v3.5.1 — Ресурсы страницы 3x-ui
- Исправлено проксирование ресурсов встроенной страницы подписки 3x-ui через `/compat/`.

## v3.5 — Штатная страница 3x-ui и совместимая подписка
- Режим для браузера сохраняет штатную HTML-страницу 3x-ui.
- Режим для VPN-клиента выдаёт подписку с преобразованиями для совместимости.

## v3.4 — Прокси подписок AmneziaWG для INCY
- Добавлен прокси совместимости поверх штатной подписки 3x-ui.
- В машинном формате подписки `vpn://` преобразуется в `amneziawg://`.

## v3.3 — Массовая синхронизация inbound'ов
- Добавлена массовая синхронизация пользователей с разрешёнными inbound'ами.

## v3.2 — Синхронизация inbound'ов отдельного пользователя
- Добавлена синхронизация разрешённых inbound'ов для отдельного пользователя.

## v3.1 — Имена клиентов на основе имени пользователя
- Поля `email`/`remark` клиента 3x-ui для новых пользователей формируются из имени пользователя Telegram; при его отсутствии используется Telegram ID.

## v3 — Админ-панель в Telegram
- Добавлена Telegram-админка: пользователи, статистика, карточка пользователя, продление, включение/отключение и удаление.
- SQLite остаётся базой связей и бизнес-данных, а 3x-ui — источником учётных данных протоколов и текущего состояния.

## v2 — Фильтрация inbound'ов и настройка API для одного сервера
- Добавлены фильтры разрешённых портов и протоколов, а также исключения для служебных inbound'ов и API.
- Уточнена работа назначения ресурсов на одном сервере через API 3x-ui.

## v1.0.0 — Первый исторический снимок
- Первый сохранённый тестовый бот для одного сервера.
- Базовые команды `/start`, `/inbounds`, `/create`, `/subscription`.
- Python + aiogram + aiohttp + aiosqlite + Docker Compose.