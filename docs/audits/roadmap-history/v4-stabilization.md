##### v4.25.1 — стабилизация управления пользователями и HWID

**Статус: ✅ Опубликовано в `v4.25.1` и принято в production.**

`v4.25.0` остаётся опубликованным baseline. Все production-acceptance blockers и незавершённые HWID operational flows исправляются в одном patch-релизе `v4.25.1`, после чего выполняется повторный acceptance только затронутых сценариев. `v4.26.0` по-прежнему остаётся Node Drain и не поглощает эти исправления.

Объём `v4.25.1`:

- удалить shortcut `⏳ Продлить` из главной карточки пользователя для всех ролей; канонический путь остаётся `📅 Срок → ➕ +30 дней`, stale `adminextend:{telegram_id}` остаётся backend-compatible;
- исправить `Пользователь → 🔗 Подписка → Показать URL`: Back обязан возвращать в `🔗 Подписка`;
- исправить `Пользователь → 💳 Платежи → 📋 Все платежи`: user-scoped context не должен теряться и Back не должен уводить в admin home;
- исправить create-user email availability: production response `Obtain (record not found)` нормализуется как штатный not-found / «email свободен», остальные XUI errors остаются fail-closed;
- исправить compat subscription proxy: для normal VPN-client request проксировать reviewed `X-HWID` и device metadata headers к upstream 3x-ui, не логировать их значения и не ослаблять фильтрацию остальных headers;
- добавить явный HWID limit при создании клиента: новые пользователи создаются с `limitHwid=5` по умолчанию;
- существующих пользователей автоматически массово на `5` не переводить;
- добавить per-user HWID limit в `🌐 Доступ → ⚙️ Параметры доступа` и summary в `📱 Подключения`;
- Read-only видит текущее значение HWID limit, но не получает mutation control;
- Support+ получает `📱 Изменить HWID limit` с bounded FSM input и явной семантикой `0 = HWID limit отключён`;
- изменение HWID limit выполняется через существующий `XUIClient.update_client(..., limitHwid=value)` и после success возвращает в `⚙️ Параметры доступа`;
- Plan apply, safe reconcile и strict reconcile не меняют индивидуальный `limitHwid`; HWID limit в этом patch-релизе остаётся per-user override и не добавляется в Plan schema;
- create-user preview показывает итоговый `HWID limit: 5` до подтверждения;
- обычные update-client операции обязаны сохранять существующий `limitHwid`, если операция явно его не меняет;
- привести `Система → Администраторы` к раздельной визуальной семантике status + role: каждая строка всегда показывает status marker и role emoji, используя существующий role mapping `👑 Owner / 🛡 Administrator / 🧑‍💻 Support / 👁 Read-only`;
- активный администратор отображается как `🟢 {role_emoji} TG … · {Role}`; отключённый — как `⛔ {role_emoji} TG … · {Role} · отключён`; неоднозначный `⚪` для disabled больше не используется;
- локальный break-glass Owner сохраняет явный source suffix и отображается консистентно как `🟢 👑 TG … · Owner · локальная конфигурация`;
- экран списка содержит короткую legend `Статус: 🟢 включён · ⛔ отключён`, а detail screen использует ту же status semantics; role/security identifiers и RBAC behavior не меняются.

Минимальные regression tests `v4.25.1`:

1. новый клиент получает `limitHwid=5`;
2. manual change `5 → 2` и `2 → 0`;
3. Read-only видит значение без edit button, Support+ видит mutation control;
4. Plan apply / safe reconcile / strict reconcile не меняют индивидуальный HWID limit;
5. другие `update_client()` mutations не обнуляют `limitHwid`;
6. create-user availability принимает фактический `Obtain (record not found)` как not-found и покрывает default/custom email paths;
7. compat proxy передаёт reviewed HWID/device headers upstream и не пишет их значения в logs;
8. subscription `Показать URL` возвращает в `🔗 Подписка`;
9. user-scoped payments сохраняют user context и корректный Back;
10. главная карточка больше не показывает `⏳ Продлить`;
11. список администраторов всегда показывает отдельные status + role indicators для Owner/Administrator/Support/Read-only;
12. disabled administrator использует явный `⛔ … · отключён`, detail/list semantics совпадают, а enable/disable и RBAC behavior не меняются.

Повторный production acceptance `v4.25.1`:

- повторить затронутые navigation/RBAC/back-chain cases;
- повторить create-user test 17 целиком до успешного создания контролируемого test user;
- выполнить отдельный real-device HWID acceptance, описанный выше, через публичный `/compat/{sub_id}`;
- проверить default `HWID limit = 5` на новом пользователе и ручное изменение через Telegram UI;
- подтвердить, что Plan apply/reconcile не перезаписывают индивидуальный HWID limit;
- повторить HWID delete two-step с реальным или контролируемым test-device;
- проверить `Система → Администраторы` на active/disabled Administrator, Support, Read-only и локальном Owner: role emoji всегда видим, disabled явно обозначен `⛔ … · отключён`, toggle не меняет назначенную роль;
- выполнить final bot/DB/3x-ui health smoke.

`v4.25.1` production-accepted по своему User Management/HWID scope после targeted re-acceptance от 2026-09-29.

Свидетельства эксплуатации `v4.25.1`:

- развёртывание: тег `v4.25.1`, commit `99e51b8988ffd90413b324021cac352ee71b39b7`, container running, `RestartCount=0`, bot version `4.25.1`;
- исходное состояние: `Health: ok`, `DB: ok`, expected Docker subnet, 3x-ui connectivity `ok`;
- повторные адресные проверки 28–37: **PASS**;
- подтверждены navigation/back-chain fixes, create-user production not-found handling, default/per-user HWID limit, preservation across Plan/reconcile, real mobile + desktop HWID registration через public compat path, HWID delete two-step, administrator status/role emoji contract и single-user traffic limit;
- финальная проверка состояния после smoke: **PASS**;
- исторический stale legacy sync callback production-click (бывший test 25) не воспроизведён из-за отсутствия сохранённого старого Telegram message и зафиксирован как **N/A production exception**; compatibility handler и non-mutating redirect покрыты code review/regression tests, mutation path через старый callback не используется.

Acceptance `v4.25.1` закрыт. Выявленные затем client-compatibility findings были выделены в `v4.25.2–v4.25.6` и также проверены и закрыты; незавершённого acceptance прежних релизов `v4.25.x` не осталось.



##### v4.25.2 — совместимость клиентов подписки

**Статус: ✅ Проверено и закрыто: Shadowrocket/HWID acceptance пройден в `v4.25.2`, INCY Desktop UA finding исправлен и принят в `v4.25.3`.**

После успешного production acceptance `v4.25.1` отдельно выявлены client-side compatibility проблемы, не относящиеся к User Management logic:

- INCY Desktop получает AmneziaWG entries из raw subscription, но Desktop-клиент не должен представлять неподдерживаемый AWG path как рабочий узел; требуется client-aware output/filtering для INCY Desktop без регрессии INCY mobile;
- Shadowrocket mobile/desktop при активном HWID limit может получать generic «URL сервера столкнулся с проблемой», потому что 3x-ui HWID gate отвечает `404`, а compat proxy сейчас сворачивает любой upstream `>=400` в непрозрачный `502 subscription upstream error`;
- production diagnosis подтвердил штатный full-slot case: `hwid-status` вернул `active=true, limit=3, registered=3, remaining=0, full=true`; после увеличения HWID limit проблема Shadowrocket исчезла;
- следовательно, HWID enforcement 3x-ui сохраняется, а compatibility layer должен уметь отличать HWID gate от реального upstream outage.

Объём `v4.25.2`:

- добавить bounded client-aware subscription output для INCY Desktop: неподдерживаемые AmneziaWG entries не должны показываться как рабочие Desktop-ноды; остальные протоколы и порядок подписки сохраняются;
- сохранить текущую `vpn:// → amneziawg://` совместимость для INCY mobile/поддерживаемых клиентов; нельзя глобально удалять AWG из raw subscription;
- определить INCY Desktop только по подтверждённому User-Agent/platform contract; при неоднозначном UA не применять агрессивный filtering;
- добавить явную operator/user documentation для Shadowrocket: при включённом per-user HWID limit необходимо включить `Send HWID` / «Отправлять HWID»;
- распознавать allowlisted HWID response headers 3x-ui: `X-Hwid-Active`, `X-Hwid-Not-Supported`, `X-Hwid-Limit`, `X-Hwid-Max-Devices-Reached`;
- HWID-specific upstream `404` не маскировать generic `502`: сохранить/перевести HWID gate в диагностически полезный ответ с allowlisted headers, не раскрывая `sub_id`, HWID value/hash или device secrets;
- generic network/timeout/real upstream 5xx по-прежнему возвращать как fail-closed gateway error; HWID diagnostics не должны превращать настоящий upstream outage в ложный client-limit response;
- в logs разрешены только bounded reason/status fields (например, `hwid_not_supported` / `hwid_max_devices_reached`), но не значения `X-HWID`, subscription URL или `sub_id`;
- **не синтезировать и не подменять fake HWID в compat proxy**: device identity всегда приходит от клиента; proxy не должен обходить реальный per-device limit и не должен объединять разные устройства под одной synthetic identity;
- сохранить forwarding reviewed client headers из `v4.25.1`: `X-HWID`, `X-Device-OS`, `X-Ver-OS`, `X-Device-Model`, при сохранении фильтрации остальных request headers;
- при полном лимите пользователь/operator должен иметь однозначный operational path: освободить device slot или увеличить per-user HWID limit; автоматическое ослабление лимита запрещено.

Минимальные regression tests `v4.25.2`:

1. active HWID + свободный slot + валидный `X-HWID` → subscription `200`, устройство регистрируется ровно один раз;
2. active HWID + missing/слишком короткий HWID → HWID gate остаётся отказом с `X-Hwid-Not-Supported`, а не generic `502`;
3. active HWID + все slots заняты + новый HWID → отказ сохраняет `X-Hwid-Max-Devices-Reached` / `X-Hwid-Limit` и не маскируется generic `502`;
4. известный зарегистрированный HWID продолжает получать subscription при заполненном лимите;
5. `limitHwid=0` не вводит новый HWID gate;
6. proxy никогда не генерирует synthetic/fallback HWID и не логирует HWID/subscription secrets;
7. Shadowrocket с включённым `Send HWID` и свободным slot получает subscription; full-slot scenario даёт диагностически различимый отказ, после освобождения/увеличения slot subscription снова загружается;
8. INCY Desktop не получает неподдерживаемые AWG entries как рабочие nodes, при этом VLESS/другие поддерживаемые entries сохраняются;
9. INCY mobile сохраняет существующую AmneziaWG conversion/работоспособность;
10. generic upstream 404/5xx без HWID diagnostic headers не переопределяются как HWID-limit case.

Приёмка в production `v4.25.2`:

- проверить INCY Desktop на реальной подписке: неподдерживаемые AWG entries не создают «мёртвые» Desktop-ноды, остальные протоколы работают;
- повторить INCY mobile AWG smoke и подтвердить отсутствие regression;
- проверить Shadowrocket mobile и desktop с включённым `Send HWID` при свободном HWID slot;
- воспроизвести controlled full-slot case и подтвердить диагностически понятный HWID-limit response вместо generic gateway failure;
- освободить/увеличить slot и подтвердить восстановление той же Shadowrocket subscription без rotation identity;
- выполнить final bot/DB/3x-ui health smoke.

Acceptance `v4.25.2` завершён с follow-up в `v4.25.3`: первоначальный INCY Desktop FAIL сохранён в истории ниже, а исправление подтверждено последующим smoke. Этот finding больше не блокирует дальнейшие релизы.


##### v4.25.3 — совместимость User-Agent настольного INCY

**Статус: ✅ Опубликовано в `v4.25.3` и принято в production; последующие `v4.25.4–v4.25.6` относились только к Streisand compatibility investigation/revert.**

Приёмка в production `v4.25.2` от 2026-09-29:

- INCY на мобильном устройстве: **PASS**;
- Shadowrocket на мобильном устройстве: **PASS**;
- Shadowrocket на компьютере: **PASS**;
- контролируемая диагностика заполненного лимита устройств: **PASS**, proxy log reason `hwid_max_devices_reached`;
- same-URL recovery после освобождения/увеличения HWID slot: **PASS**;
- итоговое состояние: **PASS**;
- INCY Desktop: **FAIL** — AWG entries остались.

Root cause подтверждён по безопасно извлечённому User-Agent без subscription URL/sub_id: реальный Desktop UA — `INCY/3.8.8/mac os x Dalvik/21.0.12.1+1-LTS`. Реализация `v4.25.2` ожидала ровно три slash-сегмента и platform token `macos`, поэтому этот валидный Desktop request не попадал под filtering.

Объём `v4.25.3`:

- поддержать подтверждённый INCY macOS Desktop UA prefix `mac os x` с optional runtime suffix после platform token;
- сохранить поддержку Windows/Linux/macOS desktop variants и Android/iOS mobile variants;
- неизвестные/неоднозначные INCY platform tokens не классифицировать как Desktop;
- не менять Shadowrocket/HWID gate semantics, уже принятые в `v4.25.2`;
- включить явную операционную инструкцию Shadowrocket `Send HWID` в README и ADMIN_SETUP.

Адресная приёмка `v4.25.3`:

1. INCY Desktop macOS с реальным UA больше не получает AWG entries;
2. VLESS/прочие поддерживаемые entries остаются и работают;
3. INCY mobile сохраняет AWG;
4. Shadowrocket/HWID smoke не регрессирует;
5. final bot/DB/3x-ui health остаётся PASS.

Адресная приёмка `v4.25.3` закрыт; принятый runtime contract повторно подтверждён финальным smoke `v4.25.6`.


##### v4.25.4 — Streisand plain subscription compatibility — совместимость текстовой подписки Streisand

**Статус: ✅ Проверено и закрыто как исторический diagnostic release; гипотеза `plain=1` не решила Streisand compatibility и была удалена в `v4.25.6`.**

Production finding после успешного acceptance `v4.25.3`:

- Shadowrocket, V2Box, V2RayTun, Happ и INCY subscription import работают;
- Streisand получает `HTTP 200`, но сообщает «подписка не содержит действующей конфигурации»;
- та же subscription, сокращённая до двух VLESS entries, продолжает давать ту же ошибку;
- оба VLESS entries импортируются в Streisand по одному успешно;
- следовательно, finding локализован на subscription-container parsing, а не на VLESS transport/Reality URI.

Объём `v4.25.4`:

- добавить opt-in query flag `plain=1` / `plain=true` / `plain=yes`;
- при `plain` возвращать decoded newline-separated subscription links после существующих client compatibility transforms;
- не пересылать `plain` upstream в 3x-ui;
- default `/compat/{sub_id}` без `plain` оставить неизменным по encoding/semantics;
- сохранить HWID forwarding/enforcement и fail-closed error handling;
- не добавлять UA-based Streisand detection: фактический Streisand request использует обычный Safari UA и неотличим от browser/WebView traffic.

Исторический план targeted acceptance `v4.25.4` (не список полученных PASS):

1. Streisand с `?plain=1` импортирует subscription;
2. те же VLESS entries появляются как валидные configs;
3. обычный URL без `plain` остаётся byte-compatible по default encoding path;
4. Shadowrocket/V2Box/V2RayTun/Happ/INCY smoke не регрессирует;
5. HWID gate/full-slot diagnostics не регрессируют;
6. final bot/DB/3x-ui health остаётся PASS.

Проверка `v4.25.4` завершена отрицательным результатом для гипотезы `plain=1`; investigation и forward-revert закрыты в `v4.25.6`. Поддержка Streisand при активном HWID limit не заявляется.


##### v4.25.5 — Streisand plain mode precedence — приоритет текстового режима Streisand

**Статус: ✅ Проверено и закрыто как исторический diagnostic release; HTML-precedence fix не устранил корневую HWID-несовместимость и был удалён в `v4.25.6`.**

Production finding после deploy `v4.25.4`:

- Streisand с `?plain=1` продолжил сообщать, что subscription не содержит действующих конфигураций;
- фактический request использует Safari/WebView-like UA и `Accept: text/html`;
- `v4.25.4` вычислял `plain_mode`, но HTML branch выполнялся раньше raw response path, поэтому `plain=1` не гарантировал raw subscription;
- root cause подтверждён кодом compat proxy.

Fix `v4.25.5`:

- при `plain_mode` HTML branch всегда пропускается;
- upstream raw fetch получает `Accept: text/plain`;
- default URL без `plain` не меняется;
- добавлен regression на Safari-like UA + `Accept: text/html` + `plain=1`.

Исторический план targeted acceptance `v4.25.5` (не список полученных PASS):

1. Streisand с `?plain=1` импортирует subscription;
2. те же VLESS configs появляются как валидные;
3. обычные Shadowrocket/V2Box/V2RayTun/Happ/INCY URLs продолжают работать без regression;
4. final bot/DB/3x-ui health остаётся PASS.


##### v4.25.6 — Streisand incompatibility / forward revert — несовместимость Streisand и отмена изменений новым коммитом

**Статус: ✅ Опубликовано в `v4.25.6`, принято в production; предыдущие релизы `v4.25.0–v4.25.6` закрыты.**

Итог production investigation:

- Streisand получает обычный browser/HTML path с HTTP 200;
- при принудительном raw subscription path клиент доходит до compat proxy, но upstream 3x-ui отвечает HTTP 404 с bounded reason `hwid_not_supported`;
- в access log подтверждён реальный Streisand UA `Streisand/50 CFNetwork/... Darwin/...`;
- клиент не передаёт совместимый `X-HWID` для raw subscription requests;
- те же VLESS links импортируются по одному, поэтому VLESS/Reality URI сами по себе валидны;
- следовательно, Streisand несовместим с HWID-protected subscription flow при `HWID limit > 0`.

Решение:

- удалить временные `plain=1` workarounds из `v4.25.4–v4.25.5`;
- вернуть runtime subscription proxy и его regression contract к `v4.25.3`;
- не генерировать synthetic/fallback HWID;
- не ослаблять или обходить per-device HWID enforcement ради Streisand;
- оставить `v4.25.4` и `v4.25.5` в Git/release history как диагностические релизы;
- документировать Streisand как известное client limitation для пользователей с активным HWID limit.

Адресная приёмка `v4.25.6`:

1. default subscription behavior совпадает с `v4.25.3`;
2. Shadowrocket/V2Box/V2RayTun/Happ/INCY smoke не регрессирует;
3. HWID full-slot / unsupported diagnostics остаются fail-closed;
4. `plain=1` больше не является поддерживаемым compatibility contract;
5. final bot/DB/3x-ui health остаётся PASS.


Приёмка в production `v4.25.6` от 2026-09-29:

- выпуск: тег `v4.25.6`, commit `b3fb80d334c8cded51e4bc9de4b08af2e31d0cd6`;
- test 50 — version/health: **PASS**;
- проверка 51 — Shadowrocket: **PASS**;
- проверка 52 — V2Box / V2RayTun / Happ: **PASS**;
- проверка 53 — INCY mobile + desktop: **PASS**;
- проверка 54 — HWID full-slot / recovery diagnostics: **PASS**;
- test 55 — Streisand: **EXPECTED LIMITATION** — raw subscription при `HWID limit > 0` несовместим, потому что клиент не передаёт совместимый `X-HWID`; 3x-ui корректно отвечает `hwid_not_supported`;
- test 56 — final bot/DB/3x-ui health: **PASS**;
- временные `plain=1` workarounds отсутствуют в финальном runtime; subscription proxy соответствует принятому контракту `v4.25.3`;
- synthetic/fallback HWID не добавляется, per-device enforcement не ослабляется.

**Итог: релизы `v4.25.0–v4.25.7` полностью проверены и закрыты.** Владелец повторно подтвердил завершение предыдущих релизов 2026-09-29. `v4.25.4–v4.25.5` закрыты как диагностические попытки с forward-revert в `v4.25.6`, а не как успешная поддержка Streisand.

Следующий активный патч — `v4.25.8` с navigation hotfix Clone Inbound и Owner self-role safety. После его отдельного release/acceptance следующий feature release — `v4.26.0` Node Drain.


##### v4.25.7 — Inbound input validation — проверка ввода Inbound

**Статус: ✅ Выполнено в `v4.25.7`; опубликовано, развёрнуто и принято в production 2026-09-29. Issue #199 закрыт как completed после targeted smoke.**

Отслеживание: [issue #199](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/199) (closed/completed), [fix PR #200](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/200), [release PR #201](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/201). Fix PR #200 слит в `main` squash-коммитом `2b24ce709ffe77d479c98e1604462deb4910c072`; release-prep PR #201 слит коммитом `053b9fecb85d009e5cfe9b323c1f4cf6d4e7d890`, на который указывает tag `v4.25.7`.

Новый post-acceptance finding: в `inbound_admin.py` ветки ошибочного ввода строят Cancel keyboard с локальным `iid`/`tid` до его присваивания. Нечисловой/вне диапазона порт в `inbound_clone_port` и `template_deploy_port`, а также пустое/слишком длинное имя в `inbound_template_save` приводят к `UnboundLocalError` вместо подсказки.

Scope:

- считывать FSM data и существующие идентификаторы сразу после успешного `guard_message()` и до проверки пользовательского ввода в трёх обработчиках;
- сохранять текущий FSM и корректный Cancel parent при неверном вводе, позволяя повторить ввод;
- ошибочный ввод не вызывает создание Inbound, запись шаблона или успешный audit;
- не менять callback identifiers, RBAC, допустимые диапазоны, payload semantics, схему SQLite, pinned 3x-ui/OpenAPI, HWID/proxy, Host Control/Deploy Agent или политику повторов запросов;
- не смешивать исправление с Node Drain, общим рефакторингом или новыми возможностями.

Контракт регрессионной проверки:

1. нечисловой, пустой и отсутствующий текст порта; `0`, отрицательный порт и `65536`;
2. пустое/пробельное/отсутствующее имя и имя длиннее 64 символов;
3. точная подсказка и Cancel callback исходного Inbound/шаблона, сохранение реального FSM state/data;
4. отсутствие remote/database mutations при неверном вводе и занятом порте;
5. допустимые порты `1`, `65535`, обычный порт с пробелами, Master и direct-node targets;
6. успешное создание по-прежнему отключено и без клиентов, исходный payload не изменяется;
7. допустимые имена, duplicate-name retry, последовательность invalid → valid input и отказ авторизации до чтения FSM.

Tests: `tests/test_inbound_input_validation.py` выполняет реальные async handlers с `MemoryStorage`; внешние вызовы и Telegram rendering заменены моками. Итоговый fix PR HEAD `186b958cf6d8af7d6f37c794f19405046ae18483` прошёл штатные `Python checks` и `PR conventions`; после squash merge повторный `Python checks` на `main` commit `2b24ce709ffe77d479c98e1604462deb4910c072` также завершился success (576 tests).

Приёмка в production `v4.25.7` от 2026-09-29:

- tag/GitHub Release `v4.25.7` опубликованы штатным workflow; tag указывает на `053b9fecb85d009e5cfe9b323c1f4cf6d4e7d890`;
- production deployment выполнен на опубликованный tag;
- ошибочный/нечисловой/вне диапазона порт, некорректный шаблон, повтор после исправления, отмена, занятый порт, Master/direct-node и разрешённые сценарии с выключенными клиентами — **PASS**;
- финальный bot/DB/3x-ui health — **PASS**;
- исходный `UnboundLocalError` finding устранён; issue #199 обновлён evidence и закрыт как `completed`;
- отдельный Low/UX navigation finding Clone Inbound вынесен в issue #202 / `v4.25.8` и не переоткрывает #199.

Admin Setup: новых настроек и действий установки для `v4.25.7` не потребовалось.


##### v4.25.8 — Inbound clone navigation hotfix — исправление навигации клонирования Inbound

**Статус: ✅ Выполнено в `v4.25.8`; опубликовано, развёрнуто и принято в production 2026-09-29. Issue #202 закрыт как `completed`.**

Проблема, найденная в production:

- путь: `/admin → Инфраструктура → Inbounds → <Inbound> → 📋 Клонировать`;
- до исправления `✖ Отмена` на выборе target server возвращала в общий список `📡 Inbounds`;
- после исправления вложенный flow возвращается в карточку исходного Inbound: `admin:inbound:{source_id}`.

Реализация:

- shared `_target_keyboard(...)` получает явный Cancel parent;
- Clone Inbound передаёт `admin:inbound:{iid}`;
- Deploy Template сохраняет собственный parent `admin:inboundtemplate:{tid}`;
- invalid-port Cancel по-прежнему возвращает в исходный Inbound;
- clone target callbacks, disabled/clientless payload, RBAC, audit и 3x-ui API semantics не изменены.

Отслеживание: [issue #202](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/202) (closed/completed), [fix PR #205](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/205), [release PR #206](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/206).

##### v4.25.8 — Owner self-role safety — защита Owner от изменения собственной роли

**Статус: ✅ Выполнено в `v4.25.8`; опубликовано, развёрнуто и принято в production 2026-09-29. Issue #204 закрыт как `completed`.**

DB-backed Owner теперь не может понизить собственную роль ниже Owner одним нажатием:

- self-demotion требует отдельного confirmation screen с явным предупреждением о потере Owner-only прав;
- mutation выполняется только через Owner-only confirm callback с актуальным FSM state + nonce;
- прямые и устаревшие подтверждения блокируются;
- Cancel очищает confirmation и возвращает в собственную карточку без mutation;
- изменение ролей других DB-администраторов Owner'ом сохраняет прежнюю семантику;
- локальный break-glass Owner из `ADMIN_TELEGRAM_IDS` остаётся immutable;
- audit фиксирует actor/target и переход роли;
- role model, privilege catalog и уровни ролей не меняются.

Отслеживание: [issue #204](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/204) (closed/completed), [fix PR #205](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/205), [release PR #206](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/206).

Приёмка в production `v4.25.8`:

- tag/GitHub Release `v4.25.8` опубликованы штатным workflow; tag указывает на `768fc0e4b9a0c0d2e35508febf272709896c3e7f`;
- implementation PR #205 и release-prep PR #206 слиты в `main`;
- post-merge `Python checks` для release-коммита: **587 tests OK**, компиляция, OpenAPI gate, проверка release notes, deploy/helper/Compose и `git diff --check` — success;
- production deployment выполнен на опубликованный tag;
- целевые production-тесты исправления навигации и защиты от снятия Owner собственных прав — **PASS**;
- final bot/DB/3x-ui health — **PASS**;
- issues #202 и #204 обновлены acceptance evidence и закрыты как `completed`.

**Итог линии: `v4.25.0–v4.25.8` полностью проверены и operationally закрыты. Следующий активный runtime-релиз — `v4.26.0` Node Drain.**

Admin Setup: новых настроек и действий установки для `v4.25.8` не потребовалось.


##### v4.26.0 — Node Drain / graceful traffic evacuation — плавное выведение ноды из трафика

**Статус: ✅ `v4.26.0` опубликован и развёрнут; полный controlled state-changing production acceptance завершён 2026-10-01, issue #208 закрыт как `completed`.**

Цель — добавить управляемый вывод direct-ноды из пользовательского VPN-трафика перед обслуживанием, миграцией или decommission, не смешивая три разные операции: control-plane maintenance, graceful drain и destructive stop.

Текущий `🛠 Обслуживание` сохраняет существующую семантику: Master ставит node `enable=false` и перестаёт использовать её для новых provisioning/sync операций, но Xray и Inbounds продолжают работать, поэтому уже назначенные пользователи могут продолжать подключаться. `Drain` должен быть отдельным явным workflow и не менять эту семантику задним числом.

Целевая модель:

~~~text
🟢 В работе
    │
    ├─ 🛠 Обслуживание
    │     control plane pause
    │     пользовательский traffic не выключается
    │
    └─ 🚧 Вывести из трафика
          ↓
       draining
          ↓
       drained
          ↓
       optional Owner-only Stop Xray / Stop service
~~~

Обязательный safety contract:

- Drain применяется только к direct node с stable `node_id`; transitive/неоднозначные targets не мутируются.
- Старт Drain сначала блокирует новые назначения на target node через существующую maintenance/control-plane primitive или эквивалентную fail-closed блокировку.
- Перед пользовательскими mutations строится read-only review: затронутые пользователи, Inbounds target-ноды, доступные policy alternatives, blockers и оценка remaining work.
- Для каждого затронутого пользователя действует attach-before-detach: сначала безопасно обеспечиваются альтернативные Inbounds согласно текущим Plan / Server Group / ProvisioningPolicy, и только после доказанного post-condition допускается detach Inbounds выводимой ноды.
- Нельзя оставлять клиента без единого рабочего Inbound. Пользователь без подтверждённой альтернативы становится blocker и не переводится автоматически.
- Drain не должен выполнять legacy attach-all и не должен обходить `ProvisioningEngine`; policy остаётся источником ожидаемого доступа.
- Активные Xray-сессии не обрываются специально. После detach/обновления конфигурации пользователь может оставаться на уже установленной сессии до reconnect/timeout; это отображается как нормальная graceful семантика, а не как ошибка.
- `drained` означает, что бот доказал отсутствие управляемых пользовательских назначений на Inbounds target-ноды либо явно показывает оставшиеся blockers. Нельзя объявлять success только по `node.enable=false`.
- Drain **никогда автоматически не вызывает** `Stop Xray` или `Stop service`. Эти destructive Owner-only операции сохраняют отдельный privilege/confirmation boundary.
- Отмена/возврат ноды в работу не выполняет слепой reverse replay старых attachments. Нода снова становится eligible, а нужные назначения восстанавливаются обычным policy-based reconcile.
- Batch mutations выполняются bounded и последовательно либо через существующий безопасный bulk primitive; `failed` и `unknown` различаются, state-changing запрос после неопределённого исхода автоматически не повторяется.
- Состояние drain/job переживает restart: незавершённый workflow после рестарта не продолжается автоматически и требует read-only verification/operator decision.
- Все этапы audit-friendly; в audit/jobs не попадают credentials, subscription URL, `sub_id` или другие secret-like данные.

Operator UX:

~~~text
/admin
└─ Инфраструктура
   └─ Операции с нодами
      └─ 🚧 Вывести из трафика
          ├─ выбрать direct node
          ├─ preflight / affected users / blockers
          ├─ confirmation
          ├─ progress
          └─ result: drained | partial | failed | unknown
~~~

Карточка ноды и Fleet Health должны визуально различать как минимум `maintenance`, `draining` и `drained`; нельзя показывать `drained`, пока Xray просто продолжает обслуживать пользователей с прежними assignments.

Граница полномочий RBAC и разрушительных действий:

- read-only status/progress Drain — `fleet.view` / Read-only+;
- start/cancel/continue controlled Drain — `fleet.manage` / Administrator+;
- `Stop Xray` и `Stop service` остаются Owner-only и не становятся частью Admin-level Drain confirmation.

Минимальные регрессионные и приёмочные проверки:

1. maintenance по-прежнему не трактуется как traffic cutoff;
2. node в draining немедленно исключается из новых provisioning targets;
3. attach-before-detach и last-working-Inbound safety;
4. blocker при отсутствии policy alternative;
5. no legacy attach-all;
6. no automatic Stop Xray/service;
7. restart/interrupted job не replay'ит mutation;
8. failed/unknown outcomes и read-back verification;
9. RBAC/callback catalog fail-closed;
10. audit без secrets;
11. production smoke на контролируемой test node/user cohort: новые назначения прекращаются, тестовый пользователь получает альтернативу до detach, после refresh/reconnect target node исчезает из рабочего пути, базовый health остаётся green.

Конкретный способ определения remaining active sessions должен использовать только реально доступные 3x-ui/Xray данные и документировать их ограничения. Online/IP наблюдение не должно выдаваться за точный учёт физических устройств или гарантированный session drain, если upstream этого не доказывает.

Реализация и свидетельства эксплуатации:

- feature issue #208 на момент release оставался открытым до полного targeted production smoke; обязательный smoke завершён 2026-10-01 и issue закрыт как `completed`;
- implementation PR #209 слит в `main` squash commit `e46c58870ea31b3a0532bd69b9b2dc01ba9bfa4a`;
- post-merge `Python checks` на implementation-коммите — **PASS**: компиляция, полный unittest, закреплённый OpenAPI 3x-ui, release tooling и `git diff --check`;
- release-prep PR #210 слит в `main` squash commit `cd39048a2da00443523e7b33b400f4c8b5dcd608`; штатный workflow опубликовал tag/GitHub Release `v4.26.0`;
- production deployment `v4.26.0` выполнен; базовые release status и runtime version checks подтверждены оператором;
- read-only Node Drain preflight на production direct node показал 4 target Inbounds, 2 затронутых пользователей, 2 готовых к переносу и 0 blockers;
- pre-mutation confirmation был отменён без remote mutation; finding #211: `✖ Отмена` вернула в корень `Операции с нодами` вместо canonical parent — preflight той же ноды;
- полный targeted production smoke из пункта 11 был отложен до безопасной test node/user cohort и завершён 2026-10-01: read-only preflight показал affected=1, movable=1, blockers=0; state-changing run выполнил maintenance → attach-before-detach с read-back → detach с read-back → `drained`; remaining assignments=0, blockers=0; reconnect через альтернативный Master прошёл успешно; test node возвращена из maintenance и обычное policy reconciliation восстановило исходную тестовую политику; временные test user/plan/server group/Inbound/node bindings после acceptance удалены с Master, audit/job/Drain history сохранена.

##### v4.26.1 — Node Drain Cancel navigation — навигация отмены Node Drain

**Статус: ✅ Выполнено в `v4.26.1`; patch опубликован, развёрнут и targeted production verification завершён, issue #211 закрыт как `completed`.**

Production pre-mutation smoke `v4.26.0` подтвердил safety path: `✖ Отмена` помечает review-plan как `cancelled` до remote mutation. При этом navigation parent нарушает общий UI contract: после Cancel пользователь попадает сразу в `Операции с нодами`, а не в read-only preflight выбранной direct node.

Scope patch:

1. `✖ Отмена` на Node Drain confirmation возвращает в `admin:fleet:drain:n<node_id>` — preflight той же stable direct node.
2. Отменённый plan остаётся terminal `cancelled`; stale `run` callback не может его запустить.
3. Cancel не выполняет maintenance, attach, detach или другую remote mutation.
4. RBAC остаётся без изменений: preflight — Read-only+, prepare/cancel/run — Administrator+.
5. Regression test закрепляет canonical parent, no-mutation Cancel и stale-plan rejection.
6. После release/deployment выполняется targeted production verification именно navigation path; полный Node Drain mutation smoke по-прежнему проводится только на безопасной test node/user cohort.

Этот patch не расширяет Node Drain scope и не меняет SQLite schema, 3x-ui API contract или destructive Host Control boundaries.

Реализация и свидетельства эксплуатации:

- fix PR #213 слит в `main` squash commit `218f2e9fda914b05121051dd0dd00a94ba99dc6b`;
- release-prep PR #214 слит в `main` squash commit `c2fc8baee1c11a716babb4bfc72743dface686ed`; штатный workflow опубликовал tag/GitHub Release `v4.26.1`;
- `PR conventions` и `Python checks` для fix/release-prep — **PASS**;
- production deployment `v4.26.1` выполнен, runtime version `4.26.1` подтверждён;
- targeted smoke: read-only preflight blockers 0, confirmation screen PASS, `✖ Отмена` вернула в preflight той же direct node, node осталась в рабочем состоянии без maintenance/draining/drained;
- финальный health/status — **PASS**;
- issue #211 закрыт как `completed`;
- на момент acceptance `v4.26.1` полный state-changing Node Drain mutation smoke оставался отдельным scope #208; он выполнен 2026-10-01 на безопасной test node/user cohort и issue #208 закрыт как `completed`.

##### Data-plane address hardening — issue #219 — усиление защиты адреса data plane

**Статус: ✅ Pre-freeze hardening принят 2026-10-01; issue #219 закрыт как `completed` документированным v4.x product decision и production proof.**

Production diagnosis подтвердил, что control-plane адрес панели и client-facing data-plane endpoint являются независимыми сущностями. Канонический runbook `docs/DATA_PLANE_ADDRESSING.md` уже фиксирует текущую policy: `Node.address` может оставаться verified HTTPS hostname, а client-facing Inbounds используют явный operator-supplied public IP через `shareAddrStrategy=custom`; protocol-specific SNI/Reality names не переписываются, а readiness включает host/provider firewall для каждого TCP/UDP Inbound.

Принятый v4.x product decision:

1. `Node.address` остаётся только control-plane endpoint и может быть verified HTTPS hostname.
2. Отдельная node-level `data_plane_address` / public-IP metadata до final v4 freeze не вводится.
3. Client-facing Inbounds на direct node используют operator-managed per-Inbound contract `shareAddrStrategy=custom` + явный `shareAddr`.
4. Automatic DNS→IP persistence из panel hostname запрещён; existing nodes не переписываются автоматически.
5. Protocol identity fields, включая Reality SNI/serverNames, независимы от dial address и не изменяются побочно.
6. Secrets/client identifiers не попадают в audit/log/docs evidence.

Production proof 2026-10-01 на безопасной test node подтвердил реальный drift: исходный Inbound имел `shareAddrStrategy=node` и пустой `shareAddr`. Выполнена одна контролируемая mutation только share-address полей, после которой read-back подтвердил `custom` и явный operator-supplied public data-plane IP. `Node.address`, `settings`, `streamSettings`, `sniffing` и Reality SNI остались без изменений; обновлённая subscription успешно переподключилась через test node. После acceptance временный тестовый контур удалён с Master. Issue #219 закрыт как `completed`.

##### v4.26.2 — Dashboard Attention summary — сводка требующих внимания событий

**Статус: ✅ Выполнено в `v4.26.2`; release опубликован, развёрнут и production acceptance завершён, issue #216 закрыт как `completed`.**

Цель — добавить в `/admin → Обзор` компактный read-only блок `⚠️ Требует внимания`, который агрегирует уже существующие problem states без нового mutation surface.

Scope:

1. Сводка показывает общий count и bounded breakdown проблем прямо на `Обзор`.
2. Источники — только существующие read-only/local states: active alerts, failed/unknown/interrupted jobs, unhealthy/offline/unknown infrastructure, problematic terminal Fleet/Node Drain states и иные уже существующие operator-facing failures.
3. `failed`, `unknown`, `interrupted` и degraded/unhealthy не смешиваются в один неразличимый статус.
4. При отсутствии проблем выводится явное спокойное состояние `✅ Требует внимания: нет`.
5. Summary не содержит credentials, subscription URL/`sub_id`, raw upstream payloads или персональные списки пользователей.
6. `Обзор` остаётся Read-only+; новых privilege IDs, auto-remediation и remote mutations нет.
7. Regression coverage фиксирует deterministic aggregation, bounded output и отсутствие state-changing calls.

Отдельный drill-down screen и canonical deep-links не входят в этот релиз и переносятся в `v4.26.3`.

Implementation evidence перед release:

- implementation PR #221 слит в `main` squash commit `1b6c72a91f2aac340bca2df37220f8934a8bc52c`;
- `PR conventions` и `Python checks` на финальном head implementation PR — **PASS**;
- summary читает active alerts/job history/local Fleet/Node Drain journals и не добавляет mutation callback, privilege ID или auto-remediation;
- regression coverage закрепляет calm state, latest-state aggregation, различение `failed/unknown/interrupted`, bounded output и no-mutation wiring;
- release-prep PR #222 слит в `main` squash commit `467d4f5609290622f0f839ce103fbf606f6f29b6`; штатный workflow опубликовал tag/GitHub Release `v4.26.2`;
- production deployment `v4.26.2` выполнен, exact tag/SHA и runtime version `4.26.2` подтверждены;
- targeted read-only smoke `/admin → Обзор` — **PASS**: блок `⚠️ Требует внимания` отображается, calm state `✅ Требует внимания: нет`, остальной dashboard остаётся работоспособным;
- финальный status — **PASS**: container running, `RestartCount=0`, Health/DB/3x-ui connectivity — ok;
- issue #216 закрыт как `completed`.

##### v4.26.3 — детализация Attention Center

**Статус: ✅ Выполнено; production acceptance завершён через fix `v4.26.4`, issue #217 закрыт как `completed`.**

Цель — добавить отдельный read-only экран `⚠️ Требует внимания` как drill-down для summary из `v4.26.2`, не создавая новый incident/ticket subsystem.

Scope:

1. Вход — из `/admin → Обзор`; экран имеет `🔄 Обновить` и `⬅ Обзор`.
2. Detail группируется по существующим доменам: infrastructure/health, jobs, alerts, backups и Fleet/Node Drain problem states.
3. Каждый item содержит bounded operator context и stable identity без secrets.
4. Переходы ведут только в существующие canonical screens: `Состояние системы`, `Задания`, `Оповещения`, `Резервные копии`, `Операции с нодами` и аналогичные уже существующие родители.
5. Navigation permission-aware: drill-down не повышает роль и не открывает actions выше текущего RBAC.
6. Resolved item исчезает после read-only refresh; собственного acknowledge/snooze/assignment storage нет.
7. Stale/deleted objects не создают dead-end или callback exception.
8. Count/detail согласованы с `v4.26.2`; regression tests фиксируют navigation/back/refresh и no-mutation contract.

Implementation evidence перед release:

- implementation PR #224 слит в `main` squash commit `9acbbe85d16a6907b11e477d96245a7cc3be656d`;
- `PR conventions` и финальный `Python checks` на implementation PR — **PASS**;
- `Python checks` на merge commit в `main` — **PASS**;
- `admin:attention` использует существующий `dashboard.view` / Read-only+ boundary, новых privilege IDs и storage нет;
- detail использует те же current-state semantics, что summary `v4.26.2`, а item rendering bounded и secret-free;
- issue #217 остаётся открыт до publication/deployment `v4.26.3`, targeted navigation/refresh smoke и финального health/status-check.

Production smoke `v4.26.3` подтвердил сам Attention Center, но выявил navigation/RBAC presentation finding #226:

- первый уровень Attention Center соответствует canonical contract: `🔄 Обновить`, `⬅ Обзор` и deep-links ведут в существующие screens;
- backend RBAC остаётся fail-closed, privilege escalation не подтверждён;
- destination screens строят часть keyboards статически и показывают actions выше роли текущего оператора:
  - `⚙️ Задания` показывает manual backup (`jobs.manage`, admin);
  - `💾 Резервные копии` показывает create/download actions (`backups.manage`, admin) и Restore/DR (`restore.manage`, owner);
  - `🚨 Оповещения` показывает rule toggle/threshold actions (`alerts.manage`, admin);
  - `🌐 Операции с нодами` показывает maintenance/rollout management entry points (`fleet.manage`, admin);
- static `attention_menu()` показывает domain deep-links даже при calm/empty state; это не прямой RBAC defect, но создаёт misleading drill-down UX и включается в fix scope.

##### v4.26.4 — Permission-aware admin navigation fix — исправление административной навигации с учётом прав

**Статус: ✅ Выполнено в `v4.26.4`; release опубликован, развёрнут и production acceptance завершён. Bug #226 и issue #217 закрыты как `completed`.**

Цель — устранить presentation-level RBAC drift без ослабления backend authorization и без нового product scope.

Scope:

1. Ввести общий role-aware keyboard filtering/rendering helper, использующий существующий callback privilege catalog как single source of truth; не создавать второй ручной permission map.
2. Применить helper как минимум к `Jobs`, `Backups`, `Alerts`, `Fleet` и другим затронутым admin keyboards, обнаруженным regression inventory.
3. `read_only` и `support` не видят admin/owner actions; `admin` не видит owner-only actions; `owner` сохраняет полный разрешённый UI.
4. Backend `authorize_callback` / minimum-role checks остаются обязательной второй границей и не упрощаются.
5. Attention Center сохраняет canonical `Refresh/Back`; domain deep-links становятся context-aware по реально присутствующим problem groups. В empty state остаются только нейтральная навигация/refresh, без misleading problem links.
6. Canonical parent semantics не меняются: destination screen возвращается в свой обычный раздел, а не в Attention Center.
7. Stale callback для скрытого/недоступного action по-прежнему fail-closed и не выполняет mutation.
8. Regression matrix покрывает роли `read_only / support / admin / owner`, direct entry и переход из Attention Center, `Back/Refresh`, empty state, stale callbacks и no-mutation-on-view.
9. Перед release выполнить полный стандартный gate: compileall, unittest, 3x-ui OpenAPI contract, `git diff --check`.
10. После publication/deployment выполнить targeted production smoke минимум под `read_only` и `admin`, затем final health/status. Только после PASS закрыть #226 и #217.

Дополнительно в рамках fix провести bounded inventory остальных статических admin keyboards: если screen содержит callbacks с разными minimum roles, rendering должен быть role-aware. Это считается исправлением общей причины finding, а не расширением feature scope.

Implementation evidence перед release:

- fix PR #228 вводит общий `filter_keyboard_for_role()` на базе канонического callback privilege catalog;
- role-aware rendering подключён к `Jobs`, `Backups`, `Alerts`, `Fleet`, core `/admin` / `Система` navigation и legacy parent menus;
- Attention Center передаёт фактический набор problem categories в keyboard builder; empty state не показывает domain deep-links;
- regression matrix покрывает `read_only / support / admin / owner`, unknown admin callback fail-closed и wiring затронутых screens;
- `PR conventions` и финальный `Python checks` на head fix PR — **PASS**;
- SQLite schema, pinned 3x-ui OpenAPI contract и backend mutation/RBAC boundaries не меняются.
- merge fix PR #228 в `main`: `7e34a61354a94f8565cd94967654f127ec0f258d`;
- `Python checks` на merge commit в `main` — **PASS**;
- release-prep обновляет только versioned metadata/docs/tests; runtime behavior после #228 не меняется.
- release-prep PR #229 слит в `main` squash commit `e2b6834d549a6b3272702fc27570c8a8a3a99bfe`; штатный workflow опубликовал tag/GitHub Release `v4.26.4`;
- production deployment exact tag `v4.26.4` / SHA `e2b6834d549a6b3272702fc27570c8a8a3a99bfe` подтверждён;
- targeted role smoke — **PASS**: `read_only` не видит admin/owner actions, `admin` не видит owner-only actions;
- Attention Center `Refresh/Back` и context-aware navigation — **PASS**;
- финальная проверка — **PASS**: контейнер работает, `RestartCount=0`, версия бота `4.26.4`, Health/DB/3x-ui connectivity — ok;
- bug #226 и feature acceptance #217 закрыты как `completed`.

После closure #208 и #219 2026-10-01 следующий порядок: encrypted off-site backup/restore drill → final v4 feature freeze → repository/public-release audit.

Оба Attention-релиза и их fix относятся к финальной полировке Admin Control Plane и должны быть operationally приняты до off-site drill и final v4 feature freeze. Они не меняют SQLite schema по умолчанию, pinned 3x-ui API contract или destructive Host Control boundaries.

##### Финальный v4 аудит репозитория перед публичным выпуском

**Статус: ✅ PASS. Audit начат 2026-10-05 на freeze commit `fe34f9dc97f0a6441dde9fcfe865e34ad8696c32` и завершён 2026-10-07 после remediation, clean-room acceptance, финальных pre-public scans и public/PVR acceptance.**

Канонический versioned report: [`docs/audits/v4-final-audit-2026-10-05.md`](audits/v4-final-audit-2026-10-05.md). Findings #234–#246 закрыты либо получили documented disposition; unresolved Critical/High/security/data-integrity Medium blockers отсутствуют. Final pre-public history/current-tree и retained-Actions scans завершены PASS на frozen SHA `c6066c1ab77e019970a70ebfa7242a66a41ba8a3`, после чего repository переведён в public и Private Vulnerability Reporting проверен с внешней стороны.

A-007/#240 на момент private baseline был принят как owner residual risk. После public transition finding технически закрыт: `main` защищён active GitHub ruleset **Protect main release path**, а `refs/tags/v*` — active ruleset **Protect release tags** (update/delete/non-fast-forward blocked, no bypass).

Историческая freeze-запись сохраняется для audit trail: **Активный gate:** провести полный финальный repository/public-release audit — этот gate теперь закрыт PASS.

Цель этого gate была не в поверхностном source review, а в воспроизводимом release-readiness audit всего repository/deployment surface. После его закрытия новый product scope переносится в v5.x; v4.x остаётся только для действительно необходимых security/reliability/data-integrity hotfixes.

Audit должен охватывать как минимум:

1. **Архитектура и runtime:** composition/startup/shutdown, router ownership, background loops, startup recovery order, dead code, duplicate responsibilities, circular coupling, large-module risk, blocking calls в async paths и graceful degradation optional services.
2. **Telegram UI/front surface:** весь `/admin` и существующий client flow как реальные пользовательские сценарии; navigation/Back/Refresh/Cancel/Confirm, FSM cleanup, stale Telegram messages, localization, emoji/status grammar, long text/keyboard limits, escaping/formatting и отсутствие misleading state.
3. **Доменная логика:** пользователи, тарифы, группы серверов/пользователей, платежи/промо, выдача доступа/сверка, идентификаторы подписок, мониторинг и диагностика; инварианты, переходы, частичные отказы, повторы, идемпотентность, пограничные случаи.
4. **SQLite/data integrity:** schema/version journal, upgrade со всех реально поддерживаемых старых состояний, constraints/indexes, transactions, concurrent access, backup-before-dangerous-migration contract, corruption/failure behavior и rollback/recovery assumptions.
5. **Authorization и object ownership:** полный callback/command inventory, RBAC minimum role, IDOR/callback tampering, typed confirmations, cross-user access, stale callback payloads и fail-closed behavior для неизвестных routes/permissions.
6. **Секреты и конфиденциальные данные:** токены бота/панели/агентов, URL подписок/`sub_id`, платежные и провайдерские данные, ключи внешнего хранения и содержимое резервных копий, Telegram ID; маскировка в логах, UI, аудитах и ошибках, разрешения и ротация.
7. **Исходящие соединения и безопасность сети:** SSRF, DNS rebinding, проверка переходов и TLS, тайм-ауты/повторы, прокси, пользовательские URL/хосты, доступность внутренних адресов, ограничения исходящего трафика Cheburcheck/PackBot.
8. **Безопасность запросов, путей и архивов:** параметризация SQL, команды shell, внедрение команд, traversal, символические ссылки, извлечение tar/zip, имена файлов, экранирование HTML/Markdown/Telegram и обработка недоверенных данных.
9. **Безопасность изменений и параллелизма:** запрет слепых повторов, неопределённые исходы, idempotency keys, блокировки, гонки, двойные callback, параллельные jobs, отмены/рестарты и проверка постусловий.
10. **Открытые HTTP и управляющие интерфейсы:** инвентаризация listening endpoints (proxy, Host Control, Deploy Agent), bind address, аутентификация, TLS, ограничение запросов/размера, раскрытие ошибок и доступность по сети.
11. **Резервное копирование и DR:** SQLite/full/node/off-site, манифесты/контрольные суммы/шифрование, хранение, повреждённые архивы, восстановление на чистом хосте, отсутствие ключей, потеря Node/Master и доказательства фактического восстановления.
12. **Укрепление контейнеров и deployment:** Dockerfile/Compose/systemd/sudoers, пользователь процесса, права на тома, capabilities, отсутствие Docker socket, файловые права, health, поведение при рестарте, сегментация сети и минимальные права помощников.
13. **Цепочка поставки:** зависимости Python/system/Rust, версии/lock, поиск уязвимостей, сканирование контейнеров, контроль vendored OpenAPI, закрепление сторонних GitHub Actions, происхождение зависимостей и обновления.
14. **Безопасность репозитория и релиза:** защита веток/тегов, required CI, доступ к merge/release, неизменяемые теги, права Actions, секреты, границы доверия workflow и воспроизводимость tag/SHA/version/release notes.
15. **Public-repository readiness:** current tree **и Git history** scan for secrets/private hostnames/IPs/Telegram IDs/credentials, sensitive deleted files, production examples, debug dumps and generated artifacts. Любой реально скомпрометированный secret, найденный в history, сначала ротируется; при необходимости history очищается до открытия repository.
16. **Third-party/legal hygiene:** LICENSE, notices/attribution для Cheburcheck/PackBot и других vendored/adapted компонентов, dependency license review, README attribution и отсутствие неразрешённого копирования assets/code.
17. **Надёжность и защита ресурсов:** лимиты запросов/очередей/памяти, максимальные размеры файлов/ответов, рост логов/backup, пагинация и худшие входные данные операторов/клиентов.
18. **Наблюдаемость:** health, логи, аудит, история jobs, смысл уведомлений, часовые пояса, идентификаторы корреляции, диагностика и недопущение утечек секретов.
19. **Документация:** README, инструкции установки/обновления/восстановления, примеры config, пути UI и модель угроз должны совпадать с реальным опубликованным кодом и проверенными DR-действиями.
20. **Приёмка с чистого окружения:** установка на новом хосте, миграция старой БД, восстановление из проверенной копии, управляемые отказы сервисов/Node, рестарт длительной операции и итоговый production smoke.

Контракт вывода аудита:

- отдельный versioned report в `docs/audits/` с exact audited commit SHA;
- для каждого finding: ID, серьёзность, компонент, evidence/reproduction, последствия, исправление/решение и ссылка на regression-test;
- automated scanners дополняют, но не заменяют manual code/flow review;
- для security-sensitive code требуется evidence-based review, а не утверждение «безопасно» только потому, что тесты зелёные;
- до финального v4 release не остаётся известных unresolved Critical/High findings; security/data-integrity Medium findings должны быть исправлены, а любой иной Medium имеет явный документированный disposition;
- после каждого fix проверяется затронутая область и regression suite;
- финальный release acceptance фиксирует exact tag/SHA, CI, migration state, backup/restore readiness и production smoke.

Результат этого gate должен дать максимально чистую и проверенную v4 baseline для публикации репозитория. Он не считается автоматической гарантией безопасности будущего Client Portal: новый public/customer/payment attack surface v5 проходит отдельный launch audit перед снятием allowlist/допуском реальных клиентов.

##### Декомпозиция bot.py

Статус: ✅ Выполнено в `v4.20.1`.

`bot.py` теперь является минимальным executable entrypoint. Startup/background orchestration вынесена в `app_runtime.py`, client-facing flow — в `client_access.py`, admin shell/navigation — в `admin_shell.py`, а domain handlers распределены по тематическим routers.

Зафиксированное состояние:

- `bot.py` — минимальный executable shim, запускающий `app_runtime.main()`;
- `app_runtime.py` управляет композицией/startup, порядком восстановления, фоновыми задачами и жизненным циклом Telegram polling;
- domain/admin handlers живут в тематических routers, а client-facing flow имеет отдельный `client_access_router`;
- orchestration, которая нужна и Telegram UI, и background/recovery paths, живёт в services, а не внутри callback handlers;
- существующие callback identifiers и внешнее поведение не менялись только ради рефакторинга;
- границы закреплены regression/source-inspection tests, включая startup recovery order и single route ownership.

Эта граница освобождает entrypoint от domain UI и позволяет развивать будущий Client Portal отдельно от `/admin`.

##### Синхронизация README с текущим состоянием

Статус: ✅ Выполнено в `v4.20.1`.

README теперь является текущей картой проекта и точкой входа в канонические runbook'и, а не второй копией release history.

Зафиксированное состояние:

- current install/update/recovery paths ведут в `docs/ADMIN_SETUP.md`, `docs/RELEASES.md`, `docs/VPS_RECOVERY.md` и профильные runbook'и;
- release-by-release история живёт в `CHANGELOG.md` и GitHub Releases;
- version-specific deploy команды старых релизов не публикуются в README как текущая процедура;
- актуальный Subscription Compatibility Proxy contract сохранён, потому что на него ссылается `.env.example`;
- README фиксирует текущие module boundaries после декомпозиции `bot.py`;
- regression test запрещает возвращать в README release headings и hard-coded старые `deploy-release.sh v4.*` инструкции.

##### Консистентная русская локализация Telegram UI

Статус: ✅ Выполнено в `v4.20.1`.

Системный проход выполнен для client access, Admin Shell, Nodes, Monitoring/Logs/Alerts, Backups/DR, Host Control/Fleet, Versions & Updates/Bot Updates и domain UI Users/Catalog/Business/Inbounds.

Зафиксированный контракт:

- кнопки, заголовки, пояснения, предупреждения и пользовательские статусы по умолчанию оформляются на русском языке;
- технические названия сохраняются там, где перевод ухудшает точность: `3x-ui`, `Xray`, `Reality`, `Host Control`, `Deploy Agent`, `Inbound`, `fingerprint`, protocol names, API/TLS/URL/UUID и точные identifiers;
- фиксированные RBAC role names `Read-only`, `Support`, `Administrator`, `Owner` остаются security-boundary identifiers;
- typed confirmation phrases `STOP`, `RESTORE ...`, `UNLOCK ...`, `DOWNGRADE ...` не переводятся и не меняются;
- callback identifiers, API fields, service names, audit/job keys и persisted machine states не менялись ради локализации;
- для machine states используются отдельные русские display mappings;
- `tests/test_ui_localization.py` закрепляет основные labels и запрещает возврат прежнего смешанного UI;
- постоянный словарь и исключения зафиксированы в `docs/UI_STYLE.md`.

Repo-wide source audit после domain-прохода не выявил обычных английских display labels вне документированных технических исключений.

##### Аудит emoji-префиксов в информационных текстах Telegram UI

Статус: ✅ Выполнено в `v4.20.1`.

Для inline-кнопок emoji/navigation prefix уже является постоянным UI-контрактом. Repo-wide проход выровнял семантические префиксы в информационных сообщениях без механического добавления emoji на каждую строку.

Целевой принцип — не добавлять emoji механически на каждую строку, а использовать их как стабильные визуальные маркеры состояния и типа метрики.

Минимальный контракт:

- одинаковые поля на Master и direct-node экранах используют одинаковые emoji и, где это возможно, одинаковые display labels;
- для общих resource/status полей базовым ориентиром является уже используемый Master-формат: `🧮 CPU`, `🧠 RAM`, `💽 Диск`, `⏱ Время работы`, `🌐 Inbounds`, `👥 Пользователи/клиенты`, `💾 Резервная копия`;
- health/state строки сохраняют семантические status icons: `🟢` healthy/online/enabled/running, `🟡` warning/degraded/pending и `🔴` failed/offline/stopped, если соответствующее состояние действительно известно;
- для node-specific operational полей закреплены `🔗 Адрес`, `🔐 Проверка TLS`, `🧭 Исходящий маршрут`, `📶 Задержка API`, `📊 Сеть`, `🕒 Последний сигнал`;
- чисто техническая строка без отдельного status/type смысла может оставаться без emoji, например `3x-ui: 3.8.5`; цель — визуальная консистентность, а не декоративное заполнение каждой строки;
- внутри одного смыслового блока не должно быть случайной смеси маркированных и немаркированных однотипных метрик без UX-причины;
- аудит охватывает как минимум Master status, Nodes list/detail, Monitoring, Backups, Версии и обновления, Jobs/Alerts и другие read-only operational summaries;
- изменение display text не меняет callback/API identifiers и сопровождается обновлением regression tests там, где exact labels являются частью проверяемого UI-контракта.

Постоянные правила для новых экранов и последующих PR зафиксированы в `docs/UI_STYLE.md`; regression tests защищают канонические префиксы для основных operational summaries.

##### Аудит информационной архитектуры и навигации

Статус: ✅ Выполнено в `v4.20.1`.

Repo-wide проход `/admin` выполнен как пользовательский сценарий, а не только как проверка существующих callback routes. Убраны дублирующие входы, выровнены parent/back flows и закрыты callback/FSM dead ends без изменения domain logic.

Перед заморозкой v4.x `/admin` навигация проверяется как пользовательский сценарий, а не только как набор работающих callbacks.

Проверяются:

- логичность top-level группировки `Обзор / Пользователи / Подписки / Платежи / Тарифы / Промокоды / Инфраструктура / Мониторинг / Система` после локализации;
- отсутствие функционально дублирующих входов и неожиданных переходов между разделами;
- последовательные Back/Refresh/Cancel/Confirm flows;
- возврат из FSM-форм в правильный parent screen;
- расположение destructive operations отдельно от обычной навигации;
- соответствие кнопки возврата фактическому родительскому разделу;
- отсутствие dead-end screens, циклов и callback routes, которые визуально ведут не туда, куда ожидает оператор;
- сохранение независимой границы `/admin` перед добавлением `/start` Client Portal.

Изменения структуры выполняются небольшими regression-safe PR и не должны одновременно переписывать domain logic без необходимости.

Зафиксированный результат прохода:

- `Версии и обновления` имеют один top-level parent — `Система`; дублирующий вход из `Инфраструктуры` удалён;
- глобальная синхронизация пользователей остаётся в `Пользователях`, а не дублируется в списке Inbounds;
- `admin:home` отображается как возврат в `Панель администратора`, а не как ложный `Обзор`;
- cancel/result/error paths форм и state-changing действий возвращают к соответствующей сущности или списку;
- regression gate проверяет, что operator-facing `render_callback` и `render_input` не создают экран без явной навигации.

##### Редактура пользовательских текстов и public-repository readiness

Статус: ✅ Выполнено в `v4.20.1`.

Repo-wide проход актуальных Telegram hints, README, `.env.example`, install/onboarding/Host Control runbook'ов и operator helper usage выполнен. Исторические deployment-примеры нейтрализованы, актуальные UI-paths синхронизированы с русскими labels, а regression gate защищает public-facing examples от возврата private-deployment drift.

Перед публикацией тексты Telegram UI и operator-facing documentation проверяются на логическую ясность, стилистическую последовательность и отсутствие случайной привязки к текущему private deployment.

Критерии:

- сообщение понятно без знания истории разработки;
- формулировка точно различает `failed`, `unknown`, `offline`, `maintenance`, `disabled` и другие разные состояния;
- тексты не содержат частные hostnames, IP, Telegram IDs, имена операторов/клиентов или временные инфраструктурные детали;
- примеры используют нейтральные placeholders;
- предупреждения и confirmation screens ясно описывают последствие операции;
- нет рекламных или абсолютных утверждений о безопасности/надёжности там, где это нельзя гарантировать;
- README и docs используют актуальные названия UI и не описывают устаревшую навигацию как текущую.

Эта работа рассматривается как часть подготовки проекта к будущему публичному репозиторию, а не как изменение business logic.

Зафиксированный результат:

- публичные примеры используют нейтральные `Edge-1` / `NODE1` вместо исторической географической привязки;
- default `MASTER_FLAG` нейтрален и не предполагает страну deployment;
- актуальные runbook'и используют фактические русские пути `Инфраструктура / Ноды / Готовность`, `Система / Резервные копии / Задания` и другие текущие labels;
- README отдельно показывает top-level Admin Control Plane и вложенные разделы, не выдавая Host Control за top-level entry;
- public-readiness regression test проверяет актуальные public surfaces; исторический `CHANGELOG.md` не переписывается ради этого cleanup.

Крупные публичные customer-facing workflows не должны размывать scope v4.x. `/admin` остаётся Control Plane.

