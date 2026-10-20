# Стиль Telegram-интерфейса

Этот документ задаёт **действующие нормативные** правила языка, терминологии, навигации, безопасности и пользовательских формулировок Telegram UI. Источники фактических Published/Deployed/Accepted и незавершённых gates — [Roadmap](ROADMAP.md) и [V5 production acceptance](V5_PRODUCTION_ACCEPTANCE.md); реализация в `main` не доказывает deployment.

## Ручные тарифы и статусы пользователей

В `/admin → Пользователи` 3x-ui status `🟢/⚪/🟡` и статус ручной выдачи **независимы**: для `manual_entitlements.active` — `♾️`, для `unknown/in_flight` — `🟡♾️`; `superseded/failed` и один лишь `admin_only` без живой выдачи не отмечаются. Фильтр `♾️ Ручные` действует **до пагинации**, выполняет bounded/batched SQLite read без N+1 и сохраняет RBAC/карточки пользователя. При неизвестном 3x-ui status используйте `🟡`, не объявляя ошибку отключением. Unicode emoji variation selector `U+FE0F` применяется в текущем UI после merge соответствующего исправления, но не означает его Published/Deployed/Accepted.

Для переключения `Все / ♾️ Ручные` `⬅ Пользователи` → `admin:users`, тогда как обычный общий список использует `⬅ Панель администратора` → `admin:home`. Возврат и поиск сохраняют identity/контекст, устаревший callback не создаёт mutation. Исправление [PR #766](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/766) Published `rc.17`, Deployed **operator-reported** (2026-10-20 01:58 EEST), а targeted U8-1…U8-4 operator-reported 4/4 `[x]` (02:10 EEST); [#760](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/760) CLOSED/completed после regression tests `tests/test_manual_user_list_760.py` и `tests/test_rc164_ui_refinements.py`. Условная U8-4 по редкому статусу подтверждена offline fixture, не отдельным наблюдением production-записи. FAIL на старом `rc.16.6` сохранён в audit. Следующие изменения не обходят требования отдельно разрешённого release/deploy и новой адресной приёмки при затронутой регрессии.

## Отображение версии ОС и типа устройства (#814/#816, rc.18.1)

Для зарегистрированных HWID `deviceOs` и подтверждённое `osVersion` из pinned 3x-ui выводятся вместе в компактном списке и карточке, но версия не выводится дважды и не угадывается по `userAgent`, модели или `lastSeen`. Невалидная/отсутствующая версия не показывается, а неизвестная ОС обозначается `ОС неизвестна`. Визуальный hint: `📱` для подтверждённых mobile/tablet, `💻` для известных laptop/desktop-class OS, `🖥️` для явно указанных настольных моделей, `🔹` при отсутствии достоверного типа. Одинаковый тип используется в строке, кнопке и карточке, не меняет authorization/ownership/DELETE. По #816 в карточке можно показать `Приложение: Happ` или `Приложение: Incy` только при точном безопасном совпадении имени приложения в `userAgent`. Сырой `User-Agent`, версия приложения, неизвестные значения и произвольные сведения о клиенте не показываются. В коротком списке приложение отсутствует; `userAgent` не влияет на platform/ownership/DELETE. Функция Published и operator-reported Deployed в `rc.18.1`; targeted UI 2026-10-20 19:34 EEST: A1/A2/A3/A6 operator-reported PASS, A4/A5 **FAIL**. Причины составного A5 и конкретный UI-содержимое не подтверждены, #814/#816 keep_open; подробности — [dated audit](audits/2026-10-20-v5-rc18-1-operator-targeted-acceptance-fail.md).

**Реализовано в main, ещё не Published/Deployed/Accepted ([PR #821](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/821)):** #814/#816/#820 — фактическая `macOS (Designed for iPad)` имеет приоритет над моделью `iPad` при выборе `💻`; `iPadOS` по-прежнему `📱`. Безопасный parser распознаёт только нормализованный известный префикс до первого `/` из `Happ`, `Incy`, `Shadowrocket` с допустимой формой version/OS/CFNetwork suffix, не выводит остальной `userAgent` и не принимает произвольный неизвестный префикс как имя клиента. В detail всегда есть `VPN-клиент: <имя>` либо `VPN-клиент: Не определён`; Back из detail только `⬅ Устройства`, из списка — прежний `⬅ Личный кабинет`. Админский HWID-list использует компактный формат и те же эмодзи/ОС/дату вместо длинного fingerprint, сохраняя карточку, callback identity, delete-flow и RBAC. Админский список — **8 HWID на страницу** с `⬅ Предыдущая`/`➡ Следующая`, абсолютной нумерацией и возвратом из detail на исходную страницу (legacy callbacks — первая); клиентский список — прежние **5 HWID на страницу**. Полный набор устройств доступен перелистыванием, без прежнего обрезания первых 30. Предыдущее deployed `rc.18.1` по #816 A4/A5 operator-reported FAIL; после отдельного release/deploy требуется targeted acceptance. [Issue #820](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/820).

## Клиентские HWID-устройства (#471 в main, #472 implementation PR)

`📱 Устройства` — исключительно записи registered HWID из 3x-ui, не IP/online sessions. Список по пять на страницу, карточка только по уникальному валидному upstream `id`, повторная проверка customer ownership при каждом callback, устаревшая карточка ведёт к обновлению. Не выводить полный fingerprint/HWID, email/subscription URL. Только положительный подтверждённый `limitHwid` показывает `N/limit`; ноль — «отключён», невалидное/недоступное значение — `UNKNOWN`. Для #472 карточка собственного устройства показывает `🗑 Удалить устройство` только при проверенной capability и полном однозначном inventory. Первый callback лишь создаёт одноразовое 90-секундное подтверждение с `🗑 Да, удалить устройство` и `✖ Отмена`; token не раскрывает email/ID. Перед единственным DELETE backend повторно проверяет Telegram identity, текущий customer/email и unique stable device ID. После подтверждённого provider ответа требуется полная read-only сверка отсутствия ID; без неё только `unknown`, без автоматического DELETE retry. Отказ провайдера, unsupported, stale и cooldown показываются отдельно. Успех ведёт в обновлённый список, отмена — в карточку без mutation. Дополнительный per-user cooldown 120 секунд, pending tokens только в памяти текущего процесса (после restart инвалидируются). Клиентский runtime `rc.17` не изменён до отдельного release/deploy; #472 до CI/merge/release/targeted acceptance PENDING.

## Другие устойчивые UI-инварианты

- Статусы `🟢` (enabled), `⚪` (disabled), `🟡` (unknown), `🔴` (offline/error) различаются; один bounded read-only `clients/list` на отображаемую страницу/результат, без N+1 и ложного состояния при API error.
- Вход из `Инфраструктура → Ноды` в read-only карточки 3x-ui/Xray сохраняет origin/родителя; изменения требуют RBAC и отдельного подтверждения.
- Административная сортировка `RUB ↑/↓` и `Stars ↑/↓` независима, сохранение порядка требует Admin/Owner. Клиентский Stars-каталог **после фильтрации прав** сортируется по Stars ↓ до лимита UI; это не новый RUB checkout или конвертация.
- Бессрочная ручная выдача допускает IP/HWID 0…1000, не создаёт Orders/Payments, требует read-only preflight, durable `in_flight`, независимый 3x-ui read-back и ручную сверку `unknown` без replay.

## Исторические UI и acceptance checkpoints

Датированные `rc.16.4`/#742–#745/C3 FAIL, `rc.16.5`/#743/#752 scoped PASS, #745 restart и исходные implementation checkpoints сохранены в [неизменяемом исходном документе](https://github.com/cLIcHE-QA/3xui-telegram-bot/blob/8d5b9ad1ce1fecf8f5f1808c786f3b2b3cf32f0b/docs/UI_STYLE.md). Исходные [rc.16.4 smoke](audits/2026-10-18-v5-rc16-4-operator-targeted-smoke.md) и [rc.16.5 acceptance](audits/2026-10-19-v5-rc16-5-operator-targeted-acceptance.md) также доступны. Эти статусы описывают **время конкретной проверки**, а не нынешний статус проекта.

## Тарифы #705 — разделение каналов

RUB и Stars/XTR — независимые необязательные цены без конвертации. Отсутствующая или нулевая цена означает «покупка недоступна», не бесплатную публичную выдачу. В Telegram оплата только Stars; RUB checkout в Telegram запрещён. Активность, видимость (all/groups/admin_only) и право покупки — разные параметры. Group-only использует локальные User Groups, исключения имеют приоритет. Скрытый бесплатный бессрочный технический тариф назначается вручную, не предлагается клиентам. При `duration_days=0` мастер сразу сообщает обязательные правила (трафик=0, обе цены=0, `admin_only`), автоматически фиксирует эти поля и пропускает их шаги; IP и HWID задаются отдельно от 0 до 1000. Ошибки проверяются в момент ввода, а не при выборе группы серверов; Back/Cancel не создают тариф. При действующей ручной выдаче портал в «Купить / продлить» объясняет причину блокировки вместо сообщения об отсутствии тарифов. При `unknown/in_flight` или ошибке SQLite остаётся fail-closed, без новых платежей; прямые callbacks и pre-checkout не обходят проверку. Остальная фильтрация Stars/group/visibility не меняется. Исторический scope внедрения — в immutable snapshot выше; текущие Published/Deployed/Accepted и остаточные gates — в Roadmap.

Ручное назначение скрытого бессрочного плана требует двух шагов: выбор из админской карточки пользователя и одноразовое подтверждение с ограниченным TTL. До read-back нельзя показывать «Успешно выдано»; при uncertain outcome использовать «Исход не подтверждён, нужна ручная проверка», без новой кнопки повтора mutation.\n\n## Язык интерфейса

Пользовательские и административные тексты Telegram по умолчанию пишутся на русском языке:

- названия разделов и кнопок;
- заголовки экранов;
- пояснения, предупреждения и подтверждения;
- статусы, если это пользовательское описание, а не точное protocol/API value;
- сообщения об ошибках и дальнейших действиях.

Локализация не должна превращаться в механический перевод каждого английского слова.

Точные технические имена сохраняются, когда перевод ухудшает узнаваемость, точность или соответствие upstream-интерфейсу. В частности, обычно сохраняются:

- названия продуктов и компонентов: `3x-ui`, `Xray`, `Reality`, `AmneziaWG`;
- названия протоколов и стандартов: `VLESS`, `VMess`, `Trojan`, `Shadowsocks`, `WireGuard`, `Hysteria2`, `HTTP`, `HTTPS`, `TLS`;
- общепринятые технические термины, если русский вариант выглядит искусственно или неоднозначно: например `fingerprint`, `API`, `URL`, `UUID`;
- точные значения API, identifiers, callback data, filesystem paths, environment variables, service names и code identifiers.

Для пограничных терминов выбирается один вариант и используется последовательно во всём Telegram UI. Нельзя оставлять рядом экраны вида `Dashboard`, `Hosts`, `Fleet Operations` и русские названия только потому, что разные модули создавались в разное время.

Если технический термин требуется объяснить пользователю, предпочтителен русский контекст вокруг неизменённого термина, например `Fingerprint клиента`, `Версия Xray`, `API недоступен`.

## Граница private chat для Admin Control Plane

Административный Telegram UI существует только в личном чате оператора с ботом. Даже валидный Owner/Administrator/Support/Read-only ID не открывает и не продолжает admin session в group, supergroup или channel context.

`/admin`, admin callbacks и FSM text input должны блокироваться до rendering/business logic вне private chat. Это fail-closed security boundary; перенос admin panel в общий чат не является поддерживаемым режимом. Client-facing flow остаётся отдельным navigation/authorization контуром.

## Канонический словарь v4

Для основных разделов и повторяющихся действий используется единый display vocabulary:

- `Dashboard` → `Обзор`;
- `Users` → `Пользователи`;
- `Subscriptions` → `Подписки`;
- `Payments` → `Платежи`;
- `Plans` → `Тарифы`;
- `Plan` → `Тариф`;
- `Server Group` → `Группа серверов`;
- `Server Groups` → `Группы серверов`;
- `Hosts` → `Хосты`;
- `Provisioning` / `reconcile` в display text → `Согласование` / `согласовать`;
- `Promo Codes` → `Промокоды`;
- `Infrastructure` → `Инфраструктура`;
- `Monitoring` → `Мониторинг`;
- `System` → `Система`;
- `Jobs` → `Задания`;
- `Audit Log` → `Журнал аудита`;
- `Backups` → `Резервные копии`;
- `Versions & Updates` → `Версии и обновления`;
- `Bot Updates` → `Обновления бота`;
- `Administrators` → `Администраторы`;
- `Settings` → `Настройки`;
- `Readiness` → `Готовность`;
- `Fleet Operations` → `Операции с нодами`;
- `Fleet Health` → `Состояние нод`;
- `Controlled Rollout` → `Контролируемое обновление`;
- `Maintenance` → `Обслуживание`;
- `3x-ui Control` → `Управление 3x-ui`.

Технические названия `3x-ui`, `Xray`, `Host Control`, `Inbound`, `API`, `TLS`, `URL`, protocol names и machine status values в коде не переименовываются. В пользовательской фразе вокруг них используется русский контекст.

Для сущности 3x-ui используется каноническая терминология `Inbound` / `Inbounds`. В operator-facing тексте не используются ни гибридные русифицированные склонения с апострофом, ни lowercase `inbound` как пользовательский термин; technical identifiers (`inbound_id`, `inbounds`, callback/API/DB keys, audit action ids и Python names) остаются без переименования.

Фиксированные RBAC role names `Read-only`, `Support`, `Administrator`, `Owner` считаются security-boundary identifiers и сохраняются как канонические имена ролей; поясняющий текст вокруг них остаётся русским.

## Терминологическая консистентность

Одна сущность или действие должны называться одинаково во всех экранах, если нет осознанной UX-причины для другого варианта.

При изменении термина проверяются:

- кнопка входа в раздел;
- заголовок экрана;
- кнопка возврата;
- подтверждения и предупреждения;
- audit/job labels, если они видимы оператору;
- README/docs/screenshots, если они описывают этот UI.

Не требуется переводить внутренние enum/status values в коде. Для пользователя при необходимости используется отдельный display label.

## Отображаемое имя пользователя

Для административного UI optional `display_name` является только presentation metadata профиля пользователя.

- если `display_name` пустое, UI использует текущий технический email как fallback;
- если имя задано, карточка показывает его как основной label, а email — отдельно как техническую информацию;
- списки могут показывать `display_name · email`, но callback identity остаётся привязана к `telegram_id`;
- изменение имени не переименовывает 3x-ui client, не меняет email, `sub_id`, provisioning bindings или subscription identity;
- имя нормализуется как однострочный текст, ограничивается 64 символами и не принимает управляющие символы;
- очистка имени должна быть явным действием и возвращать fallback на email.

## Группы пользователей

`Группы пользователей` / User/Audience Groups — отдельная административная сущность для сегментации аудитории. Она не является синонимом `Группы серверов` и не участвует в provisioning.

- `Группа серверов` определяет инфраструктурную policy: Nodes / Inbounds / Plan placement;
- `Группа пользователей` определяет принадлежность пользователя к аудитории для будущих include/exclude rules Client Portal;
- membership хранится по стабильному `telegram_id`; display name и email используются только для поиска и presentation;
- один пользователь может одновременно состоять в нескольких группах пользователей;
- добавление/удаление membership не меняет тариф, `server_group_id`, Nodes, Inbounds, subscription identity или VPN-доступ;
- список групп доступен из `Пользователи → Группы пользователей`, а membership конкретного пользователя — из его карточки;
- удаление группы является двухшаговым destructive flow: удаляется группа и её membership, но не сами пользователи;
- mutation-кнопки скрываются для ролей ниже требуемой, однако handler authorization остаётся обязательной;
- callbacks используют stable numeric `group_id` и `telegram_id`, а не изменяемое название группы или display name.

Operator-facing термин `membership` в обычных экранах не используется: UI говорит «участие в группах», «добавить пользователя» и «убрать из группы».

## Отображение Master и direct nodes

Идентичность ноды и её отображение в Telegram UI разделяются.

- стабильная техническая идентичность direct node — `node_id`;
- `name` является изменяемым display name и не используется как основной binding, если доступен `node_id`;
- operator-facing подпись direct node формируется через единый `node_display_name()` или эквивалентный общий formatter;
- formatter может добавлять presentation metadata, например флаг страны, но эти данные не участвуют в callback/API identity, privilege binding, backup identity или Host Control binding;
- уже размеченное имя не получает повторный флаг;
- произвольное имя, для которого нет presentation metadata, отображается без искусственного угадывания;
- Master не пропускается через formatter direct nodes и отображается отдельно как `🖥 Master` или через фактическое `MASTER_NAME` с Master-маркером;
- если Master и direct nodes показаны в одном списке, строки используют одну грамматику состояния: сначала идентичность сущности, затем status marker и текстовый status label; нельзя оставлять Master как `🖥 Master · 🟢 В сети`, а direct node только как `🟢 🇫🇮 Finland` без текстового статуса;
- рекомендуемый шаблон общего списка: `<identity> · <status icon> <status text>`, где direct-node identity формируется через `node_display_name()`;
- runtime-код не должен содержать специальных веток вида `if node.name == "Finland"` или иной логики, завязанной на конкретную production-географию;
- при добавлении новых operator-facing экранов прямой вывод `node.name` допустим только для machine/internal context; пользовательская подпись должна идти через общий formatter.

Текущий name-based country mapping является только presentation fallback. Будущее optional `country_code` не меняет принцип: `node_id` остаётся identity, `name` — display name, а флаг вычисляется отдельно.

Для экранов health/status действует дополнительный контракт:

- одинаковые метрики Master и direct nodes используют одинаковые русские labels, status grammar и emoji;
- одинаковость означает единое представление доступных данных, а не искусственно одинаковое количество строк;
- direct node всегда получает явный текстовый общий status рядом с identity, а Xray показывает state и version, если version доступна;
- состояния `online/offline/unknown/maintenance` и `running/stopped/error/unknown` визуально различаются и не должны сводиться к ложному бинарному green/red;
- Master-only локальные данные (например disk, Subscription Proxy, nginx/TLS, bot DB/backup) не дорисовываются direct nodes без реального источника;
- node-only aggregate данные (latency, client/online counts и аналогичные поля) можно показывать отдельно;
- дополнительные network calls только ради визуальной симметрии не добавляются без отдельного contract по timeout/failure semantics.

## Часовой пояс operator-facing UI

Абсолютные дата/время в Telegram Admin Control Plane отображаются в **MSK (UTC+3)**.

- Unix timestamps, SQLite values, agent journals, API timestamps, backup filenames и другие machine-level значения не переводятся и сохраняют существующую UTC/epoch semantics;
- `BACKUP_HOUR_UTC` остаётся технической настройкой расписания в UTC; operator UI показывает соответствующее время MSK и при необходимости исходное UTC значение;
- date-only ввод оператора вида `YYYY-MM-DD` для срока пользователя/промокода означает конец выбранного дня (`23:59:59 MSK`);
- relative labels вида `5 мин назад` не зависят от timezone и остаются относительными;
- timezone presentation не должна зависеть от локальной timezone host/container.

## Навигация

Кнопка `👥 Все` из ручного списка ведёт на `admin:users`; различие возврата проверяется построением обеих клавиатур, а не поиском callback в тексте. Нормативный parent/callback контракт приведён выше.

Навигация строится от пользовательской задачи, а не от структуры Python-модулей.

Основные правила:

- каждый экран имеет очевидного родителя и предсказуемую кнопку возврата;
- `✖ Отмена` и контекстная кнопка `⬅ Назад` возвращают на **непосредственный экран входа**, сохраняя проверенную identity выбранного пользователя, bulk selection или резервной копии. Если экран доступен из разных мест, callback явно и безопасно сохраняет источник; устаревшие и неизвестные источники fail closed, без произвольных адресов/переходов и без mutation;
- одинаковые сущности не дублируются в разных top-level разделах без явной причины;
- read-only просмотр и state-changing действия визуально и логически разделены;
- destructive actions не должны выглядеть как обычная навигация;
- любая новая operator-facing операция удаления сущности/записи/ресурса обязана быть двухшаговой: первый клик только открывает отдельный confirmation screen, фактическое удаление выполняется только после явного подтверждения; one-click delete не допускается;
- confirmation удаления явно называет удаляемый объект и существенные последствия, содержит отдельное affirmative действие с warning-маркером и `✖ Отмена`; Cancel возвращает в карточку/родительский экран без mutation;
- для нового delete flow regression coverage должна проверять, что первый delete action не вызывает mutation, а mutation находится только за отдельным confirm callback/handler;
- наиболее частые действия доступны без лишней глубины, но top-level меню не разрастается ради единичной операции;
- после FSM/confirmation flow пользователь возвращается в логичный родительский экран;
- `/admin` и уже существующий пилотный `/start` сохраняют независимые navigation/authorization boundaries; клиентский доступ остаётся ограничен флагами, pilot allowlist и отдельной приёмкой v5;
- `🆘 Помощь → 🛠 Проверить подписку`: `Сроки` имеет ровно три исхода — `✅ Сроки совпадают` при полученных и сравнимых применимых local/entitlement/provider expiry, `⚪ Недостаточно данных для сравнения` при неполном evidence, `⚠️ Сроки не совпадают` при доказанном drift более 2 секунд. Отсутствующий `expiryTime` не равен подтверждённой бессрочности, доказанный mismatch важнее недоступного третьего источника. Refresh/Back остаются read-only, Provider read/VPN-доступ выводятся отдельно;
- названия родительских разделов в кнопках возврата должны совпадать с фактическими названиями этих разделов.

Зафиксированный контракт Admin Control Plane:

- `admin:home` — это корневая `Панель администратора`, а не экран `Обзор`; кнопка на этот callback подписывается `⬅ Панель администратора`;
- корневая клавиатура `admin_menu()` показывается только на `/admin` / `admin:home`; переход по любой top-level кнопке открывает отдельный экран раздела и не сохраняет корневое меню под новым содержимым;
- `admin:dashboard` (`Обзор`) является дочерним экраном `Панели администратора`, а не альтернативным корневым состоянием; он использует собственную локальную навигацию как минимум с `🔄 Обновить` и `⬅ Панель администратора`;
- `Обзор` может содержать bounded read-only summary `⚠️ Требует внимания`: он показывает только агрегированные counts существующих states, явно различает failure/unknown/interrupted/degraded и не выводит secrets, raw upstream payloads или персональные списки; в `v4.26.2` summary не добавляет mutation actions или deep-links;
- `admin:attention` — дочерний read-only экран `Обзора`: grouped detail ограничен пятью items на домен + `… ещё N`, каждый item имеет stable technical identity и bounded context без secrets; экран имеет `🔄 Обновить`, `⬅ Обзор` и только read-only contextual entry callbacks в существующие domain screens, без item-specific mutation callbacks;
- admin keyboard с callbacks разных privilege levels обязан фильтроваться по effective role через канонический callback privilege catalog; UI не показывает action выше роли пользователя, но backend authorization остаётся обязательной fail-closed границей;
- вход из `admin:attention` в `Состояние системы`, `Задания`, `Оповещения`, `Резервные копии` и `Операции с нодами` использует только фиксированные `admin:attention:<domain>` callbacks; domain screen сохраняет `🔄 Обновить` и `⬅ Требует внимания`, а обычный вход из `Система`/`Мониторинг`/`Инфраструктура` сохраняет canonical parent; изменение alert rules, запуск backup, Fleet mutations и другие вложенные операции всегда переходят в собственный canonical flow без унаследованного контекста; нет долговременного/in-memory breadcrumb state;
- `admin_root_heading(role)` задаёт одинаковый title для `/admin` и `admin:home` из актуальной разрешённой роли: `👑 Owner`, `🛡 Administrator`, `🧑‍💻 Support`, `👁 Read-only`; role-catalog и фактическая backend авторизация не меняются;
- для `admin:attention` domain deep-links являются context-aware: показываются только группы, реально присутствующие в текущем detail; calm/empty state оставляет только `🔄 Обновить` и `⬅ Обзор`;
- top-level экраны `Обзор`, `Пользователи`, `Подписки`, `Платежи`, `Тарифы`, `Промокоды`, `Инфраструктура`, `Мониторинг` и `Система` следуют одному правилу: содержимое экрана и его локальная клавиатура принадлежат выбранному разделу, а возврат к корневому меню выполняется явно;
- один экран имеет один канонический раздел-родитель: `Версии и обновления` живут в `Системе`, глобальные пользовательские операции — в `Пользователях`;
- `Проверка блокировок` живёт только в `Мониторинге`: это read-only diagnostics tool, а не инфраструктурная mutation; вход из Monitoring/discovered/manual flow остаётся внутри Cheburcheck/Monitoring navigation;
- карточки Master/direct node могут содержать shortcut в `Проверку блокировок`, но canonical parent остаётся `Мониторинг`; shortcut после result/error/retry/manual-search/Cancel возвращает только в исходную карточку и не создаёт cross-context jump;
- Cheburcheck result card использует compact summary: `Цель`, `Результат`, `Сеть`, bounded static detail, один блок `📋 Списки`, одну агрегированную строку `🌍 Регионы` и attribution `Источник: Cheburcheck.`; IP/PTR/blocked-subnet values ограничены максимум 5 значениями каждого типа + `… ещё N`, optional `rkn_domain`/`subnet_size` показываются только при наличии, raw JSON/SSE/probe payload не выводится;
- пустой список CDN — это известный отрицательный результат и показывается как `🟢 не найден`, а не как неизвестное `—`; optional-данные, которых upstream действительно не предоставил, могут оставаться `—`;
- если static domain/IP result содержит `geo.asn`, compact card может дополнительно выполнить bounded read-only check этого ASN для строки coverage; отсутствие enrichment не меняет основной verdict;
- региональная строка обязана различать фактические состояния: агрегированные ответы, `нет активных региональных сканеров`, `нет ответов`, transport/upstream unavailable и неприменимость для subnet/ASN; отсутствие probe fleet не маскируется нейтральным `—`;
- auto-discovery целей показывает только безопасный hostname/IP и stable display label; URL path, query, credentials, tokens и subscription identifiers в кнопки/текст не попадают;
- Cheburcheck screen не показывает internal service URL/credentials, явно называет внешний источник данных и различает `не настроен`, validation error, rate limit, upstream unavailable и фактический verdict;
- `🌐 Мониторинг сайтов` живёт только в `Мониторинге`; home → список → карточка → incident history образуют один локальный navigation context, а add-site FSM имеет явный `✖ Отмена` обратно в website monitoring;
- карточка monitored site различает `🟢 доступен`, `🟡 перепроверка`, `🔴 недоступен`, `⚪ не проверен` и `⏸ приостановлен`; checker/policy error не маскируется под подтверждённый site-down;
- raw URL никогда не кодируется в website-monitoring callbacks: callbacks содержат только stable numeric monitor ID и fixed action token;
- mutation-кнопки website monitoring privilege-aware: Read-only видит список/карточку/history/contextual diagnostics, Support получает add/manual-check/pause-resume/notifications/unsubscribe, Administrator дополнительно получает global target management; delete/unsubscribe и global delete остаются двухшаговыми;
- pause/resume является watcher-scoped состоянием: приостановка одним администратором не останавливает target для других active watchers; если active watchers не осталось, scheduler перестаёт планировать проверки до resume;
- contextual `🩺 Диагностика` из карточки сайта использует только stable monitor ID в callback, перечитывает canonical URL из SQLite и всегда возвращается в ту же карточку;
- global target removal доступен только Administrator+, явно показывает число watchers и удаляет target/watchers/local incident history только после отдельного confirmation screen; destructive operation сериализуется с check того же target;
- unsubscribe удаляет только watcher текущего администратора; target очищается как orphan только после удаления последнего watcher;
- website incident alerts являются отдельными Telegram notifications, а не заменяют односообщенческую admin panel; repeated/recovery delivery использует persistent idempotency journal;
- `🔎 Разовая диагностика` является дочерним экраном `Мониторинг сайтов` и не создаёт persistent target; WHOIS/DNS/HTTP/redirect/CMS/SEO/PageSpeed/Sitemap/URL-list/QR используют fixed tool callbacks и FSM input с `✖ Отмена`;
- PageSpeed без локального API key показывает `⚪ Не настроен`, а не ошибку target; QR как media utility может отправить отдельное изображение, после чего text-panel остаётся в локальном diagnostics context;
- длинные DNS/Sitemap/URL-list results сворачиваются/truncate до Telegram-safe summary; raw WHOIS/RDAP/PageSpeed payload в UI не выводится;
- shortcut на тот же экран из другого top-level раздела добавляется только при явной UX-причине, а не как дублирующий вход;
- callback-screen после результата или обычной ошибки сохраняет явный путь назад/дальше; в односообщенческой admin-панели вызов `render_callback(...)` без `reply_markup` не должен создавать dead end;
- временный progress screen во время уже запущенной state-changing/fail-closed операции может намеренно скрывать навигацию, если повторный клик или параллельное действие создают риск replay/неопределённого outcome;
- FSM prompt и validation error сохраняют `✖ Отмена` или явный возврат к родителю; после завершения/отмены FSM state очищается и оператор возвращается к исходной сущности или её списку;
- после успешного destructive action результат ведёт в список удалённой сущности; confirmation Cancel возвращает к непосредственному экрану входа без mutation (например, `⚙️ Ещё действия` для удаления пользователя оттуда);
- в карточке пользователя `💳 Платежи` является read-only filtered view существующего payment ledger: кнопки изменения статуса/создания платежа не дублируются, суммы оплаченных не объединяют разные валюты, detail callback сохраняет user context;
- `🧾 Активность` пользователя является filtered view существующего audit log, а не новым журналом: фильтр использует machine identity, timestamps отображаются в MSK, Back возвращает в карточку пользователя, secret-like subscription/device details скрываются;
- `➕ Создать` в `Пользователи` доступен Support+ и ведёт через явный FSM с `✖ Отмена`: Telegram ID → machine email → optional display name → Plan/compatibility → preview → confirm; callback identity не использует display name;
- create-user remote mutation никогда не replay'ится после uncertain outcome: сначала read-only verification, локальная запись появляется только после доказанного remote state; уже существующий 3x-ui client восстанавливается отдельным non-mutating recovery flow;
- экран `🔗 Подписка` предлагает открыть URL, показать URL и сгенерировать QR локально; subscription URL не передаётся внешним QR/shortener сервисам, rotation остаётся отдельной Administrator mutation;
- VLESS Flow sync находится в `🌐 Доступ → ⚙️ Параметры доступа`, доступен Support+ и не является reconcile/attach/detach операцией; после выявленного в #648 сброса Node Flow старая кнопка сохраняется как безопасный переход к адресному выбору, устаревший `flowrun` fail closed без `bulkAdjust`;
- `✏️ Изменить Flow` использует ограниченную пагинацию (по 8) при росте числа нод/Reality Inbounds: вперёд/назад не меняют состояние и требуют того же RBAC. Верхняя граница для одного просмотра — 64 ноды и 256 Inbounds; при превышении операция блокируется, а не возвращает урезанный список. Полные WG/AmneziaWG peer-поля допускаются только при повторно подтверждённом ownership всех tunnel Inbound, совпадении read-only `tunnelAllowedIPs` и безопасном исключении WG peer-полей из VLESS payload (с upstream-доказательством их сохранения в общем ClientRecord); неизвестные связи, MTProto и reverse fail-closed; для WG/AWG разрешена строго аттестованная Master panel version `3.10.2`, а `3.10.0`, неизвестные и более новые версии остаются BLOCKED до отдельного Go/SQLite proof. Даже зелёный offline CI не разрешает production Flow POST без отдельного operator acceptance. 
- `✏️ Изменить Flow` доступен Support+ из `Параметры доступа`: Node по стабильному Master `nodeId` (отдельно `Master`) → Reality TCP VLESS Inbound → `none` / `xtls-rprx-vision` / `xtls-rprx-vision-udp443` → отдельное подтверждение с одноразовым nonce и TTL. Навигация и отмена не меняют 3x-ui. Перед POST проверяются membership, Reality capability, tag, прежний Flow и неизменность общего клиента; только `POST /panel/api/clients/update/{email}?inboundIds=...` через Master, без прямой Node mutation или автоматического повтора. Итог отдельно читает выбранный Master Inbound и direct Node Panel, `MATCH/MISMATCH/UNKNOWN` не заменяет аттестацию работающего Xray;
- При сравнении direct Node Flow разрешено только проверенное upstream v3.10.0 соответствие точного tag и одной формы `n<node_id>-`/без префикса на строго связанной `node_id`. Две формы одновременно либо несколько найденных Inbounds дают `UNKNOWN`; fuzzy matching по порту/имени, подмена Master данными Node и прямые Node mutations запрещены. Ошибка preflight `✏️ Изменить Flow` использует детализированные фиксированные коды `CLIENT_RECORD_MISSING` (недостающие ключи полного record), `CLIENT_RECORD_NULL` (нулевое обязательное значение), `CLIENT_RECORD_PROTOCOL_WG` (группа WireGuard/AmneziaWG), `CLIENT_RECORD_PROTOCOL_MTPROTO` (группа MTProto), `CLIENT_RECORD_PROTOCOL_MIXED` (обе группы) и `CLIENT_RECORD_REVERSE` (непустые reverse settings). Эти коды никогда не содержат имена полей конкретного клиента, их значения или raw payload; **все** исходные fail-closed checks, права, nonce и запрет POST сохраняются. Ошибка preflight `✏️ Изменить Flow` показывает только фиксированный безопасный код (`CLIENT_RECORD`, `INBOUND_CLIENT`, `INBOUND_TAG`, `NODE_IDENTITY`, `UPSTREAM_TIMEOUT` и др.), без raw API/секретов; любой отказ сохраняет fail-closed блокировку изменения.
- **#691 / UX после rc.15:** общие поля `ClientRecord.flow` показывать с явной подписью «общий Flow клиента (не Flow Inbound)»; фактический scoped VLESS Reality Flow брать только из выбранного Master inbound. Имена нод получать строго из read-only Master `nodes/list`, названия inbound из `inbound_get(...).remark`, отображать вместе со стабильными `#id` и fallback. Исторический результат `🔎 Проверить Flow` может отображаться в карточке/Параметрах доступа только с пометкой «последняя проверка, не live» и ограниченным TTL 180 сек; после перезапуска/истечения/отсутствия — «не проверено». UNKNOWN не повышать до MATCH, никаких mutation changes/extra Node writes.
- `🔎 Проверить Flow` сохраняет исходный экран через явный callback: из карточки пользователя `admin:u:flowcheck:<tg_id>` возвращает `⬅ Пользователь`, из `⚙️ Параметры доступа` `admin:u:flowcheck:cfg:<tg_id>` возвращает `⬅ Параметры доступа`; `🔄 Повторить проверку` сохраняет эту точку входа даже при `UNKNOWN`/ошибке Master. После scoped editor result вход считается из `Параметров доступа`. Оба варианта — read-only `users.view` без FSM/breadcrumb state, provider mutations и утечек.
- Flow в карточке пользователя отображается **с указанием источника**: `🖥 Flow Master` из Master API и `🌐 Flow Nodes: ⚪ не проверено` по умолчанию. Только явная read-only кнопка `🔎 Проверить Flow` для роли users.view выполняет ограниченное число GET на direct Node Panel API через настроенный точный `node_id`. Итог конкретного Reality inbound: `MATCH` при независимом совпадении, `MISMATCH` при фактическом отличии (включая `none`), `UNKNOWN` при отсутствии/неоднозначности binding, offline API, missing evidence или неподтверждённом tag; никогда не считать Master Flow доказательством Node PASS. Non-Reality inbounds в сравнении не участвуют, нет mutations, secrets и скрытых blind retries. Показанное Node Panel Flow является config read-back, не runtime Xray attestation;
- enable/disable пользователя всегда двухшаговые: карточка/`Ещё действия` ведут на confirmation screen, state-changing call выполняется только отдельным run callback, Cancel возвращает в пользователя;
- после `successful_payment` bot вправе удалить старое связанное с заказом Stars invoice-сообщение (по сохранённому message ID), только однократно после подтверждения оплаты. Telegram cosmetic cleanup не влияет на платежи, срок доступа или idempotency; при timeout/ошибке не выполняет blind replay и не обещает, что Telegram-клиент покажет invoice закрытым;
- `🔄 Сбросить клиентскую сессию` в `Пользователи → карточка → Ещё действия` доступен только Owner при наличии активного in-memory окна customer rate limiter: отдельное подтверждение с указанным Telegram ID, одноразовым token и сроком действия, очистка только этого limiter bucket в работающем процессе; customer FSM в текущем Client Portal отсутствует, административный FSM не очищается. Это **не** сброс 3x-ui/VPN/платежей и не обход ограничений доставки Telegram; отсутствие состояния показывается как no-op, результат аудитируется;
- bulk selection сохраняет выбранные `telegram_id` в FSM и не использует display name как identity; Plan/Server Group assignment меняют только profile state, а provisioning выполняется отдельно через `🚀 Согласовать`;
- bulk custom expiry/traffic сначала валидируют bounded input и показывают preview с количеством targets; `+30`, enable/disable/reset/reconcile также имеют отдельный confirmation, а audit summary не содержит список email;
- после **выполненной** user detail mutation итоговый экран может вести в canonical раздел: Plan → `💎 Тариф`, expiry/+30 → `📅 Срок`, traffic/reset → `📊 Трафик`, IP limit → `⚙️ Параметры доступа`, subscription rotation/QR → `🔗 Подписка`, name/note → `✏️ Профиль`; **до mutation** `✖ Отмена` из `⚙️ Ещё действия` возвращает именно туда (reset, strict reconcile, subscription rotation, delete), не в другой раздел; возврат из FSM очищает только операционный input-state, а bulk selection сохраняется до выхода из bulk flow;
- subscription summary показывает только masked `sub_id`; полный URL доступен только отдельным read-only действием/URL button, а audit/log contract по-прежнему не допускает credential reconstruction;

Изменение структуры меню требует проверки соседних переходов, Back/Refresh/Cancel flows и callback routing, а не только нового экрана.

## Тексты и формулировки

Текст должен сообщать оператору три вещи, когда они применимы: что происходит, каково текущее состояние и что можно сделать дальше.

Предпочтения:

- короткие прямые фразы без канцелярита;
- конкретное название объекта вместо неоднозначных `это`, `данное`, `текущий элемент`;
- стабильные формулировки, не привязанные к конкретному VPS, владельцу, домену, географии или временной конфигурации проекта;
- техническая точность важнее буквального перевода;
- distinction между `failed`, `unknown`, `offline`, `disabled`, `maintenance` не скрывается общим словом `ошибка`;
- сообщение об ошибке не должно утверждать, что mutation не произошла, если outcome действительно неизвестен;
- инструкции для destructive действий явно называют последствие.

Не следует использовать рекламные или субъективные формулировки вроде `идеальный`, `лучший`, `абсолютно безопасный` в operational UI и документации без объективного основания.

## Emoji в информационных текстах

Emoji в body text используются как семантические визуальные маркеры, а не как обязательное украшение каждой строки.

Для однотипных operational данных выбирается один стабильный prefix и переиспользуется во всех соседних экранах. Master status является базовым ориентиром для общих метрик:

- `🧮 CPU`;
- `🧠 RAM`;
- `💽 Диск`;
- `⏱ Время работы`;
- `🌐 Inbounds`;
- `👥 Пользователи/клиенты`;
- `💾 Резервная копия`.

Статусные строки используют icon по фактическому состоянию: `🟢` для healthy/online/enabled/running, `🟡` для warning/degraded/pending и `🔴` для failed/offline/stopped. Нельзя показывать зелёный icon, если underlying state неизвестен или только предполагается.

Для node-specific operational полей используется следующий display contract:

- `🔗 Адрес`;
- `🔐 Проверка TLS`;
- `🧭 Исходящий маршрут`;
- `📶 Задержка API`;
- `📊 Сеть`;
- `🕒 Последний сигнал`.

Для повторяющихся read-only summaries также используются стабильные смысловые маркеры: `📦` для текущей версии/артефакта, `🆕` для последней доступной версии, `⚙️` для активной операции, `🔎` для фильтра, `☁️` для внешней резервной копии. Эти маркеры не заменяют status icons и не должны создавать ложное впечатление об успешном состоянии.

Техническая строка может оставаться без emoji, если emoji не добавляет отдельного смысла. Например строка `3x-ui: 3.8.5` допустима без префикса, тогда как `🟢 Xray: работает 26.9.9` содержит именно status marker.

Если Master и direct-node экраны показывают одну и ту же метрику, предпочтительно использовать одинаковые emoji и display label. Нельзя оставлять случайную смесь вида `🧮 CPU` на одном экране и `CPU` без префикса на другом без осознанной UX-причины.

## Подготовка к публичному репозиторию

Пользовательские тексты и примеры не должны зависеть от частной инфраструктуры проекта.

Перед публикацией проверяются:

- private hostnames/domains/IP/Telegram IDs;
- имена конкретных операторов или клиентов;
- environment-specific paths, если они не являются каноническими путями проекта;
- временные пояснения из периода разработки;
- сообщения, понятные только автору или текущему deployment;
- устаревшие названия разделов после реорганизации UI.

Примеры используют нейтральные placeholders. Для текущих runbook'ов канонический пример direct node — `Edge-1` с alias `NODE1`; домены используют `example.com`, а публичные IPv4-примеры — документальные диапазоны RFC 5737. Локальные Docker/loopback адреса допускаются, когда они являются частью описываемой topology, а не данными конкретного deployment.

Исторический `CHANGELOG.md` может сохранять прежние названия и примеры, если они нужны для точного описания выпущенной версии; актуальные README/runbook'и и UI hints не должны использовать их как текущий contract.

## Проверка новых UI-изменений

PR, изменяющий Telegram UI, должен проверять как минимум:

1. соответствие этому языковому и терминологическому контракту;
2. логичность родительского раздела и Back/Cancel flow;
3. отсутствие смешения русского и английского без технической причины;
4. понятность текста вне контекста конкретного production deployment;
5. сохранение emoji/navigation prefix для inline-кнопок согласно `docs/GIT_WORKFLOW.md`;
6. консистентность emoji-префиксов в информационном тексте для однотипных status/resource полей;
7. обновление regression tests, если меняются callback routing, critical confirmation text или navigation contract.

Полная интернационализация/i18n framework не является целью текущего v4.x. Сначала фиксируется качественный единый русский UI; отдельная мультиязычность может быть добавлена позже как самостоятельный продуктовый этап.
## User Management v4.25

Для списка пользователей действует отдельный navigation contract:

- список `👥 Пользователи` обязан иметь pagination; пользователь не становится недоступным только потому, что находится за первой страницей;
- `🔎 Поиск` ищет по Telegram ID, техническому email и отображаемому имени, но callback identity всегда остаётся `telegram_id`;
- mutation shortcuts списка показываются только ролям, которым они доступны; handler authorization остаётся обязательной независимо от видимости;
- legacy attach-all действия `Синхронизировать Inbounds` и `Синхронизировать всех` не показываются в новых клавиатурах;
- сохранённые старые callbacks этих действий являются только non-mutating redirect в policy-based `Согласование`;
- массовое автоматическое управление доступом использует `ProvisioningEngine` в safe mode и не заменяется прямым attach всех глобально разрешённых Inbounds;
- audit массовых операций не должен перечислять email пользователей или subscription credentials без необходимости.

Карточка пользователя использует разделы как устойчивые parent screens:

- `💎 Тариф`, `📅 Срок`, `📊 Трафик`, `🌐 Доступ`, `🔗 Подписка`, `✏️ Профиль` и `⚙️ Ещё действия` открываются отдельными read-only callbacks;
- read-only role видит состояние, но не получает ложнодоступные mutation-кнопки;
- `Support` получает обычные lifecycle/configuration actions, `Administrator` — strict reconcile, subscription rotation и delete;
- `🌐 Доступ` является parent для provisioning, manual Inbounds и параметров доступа;
- legacy `adminuser:*` открывает ту же role-aware карточку и не создаёт второй navigation contract.
- `📱 Подключения` различает online/session/IP data и зарегистрированные HWID devices; IP никогда не называется физическим устройством без HWID identity;
- список HWID показывает только bounded upstream metadata/short fingerprint; удаление одного device — двухшаговое и доступно Support+;
- read-only карточка устройства не показывает mutation-кнопку; uncertain DELETE outcome не повторяется автоматически, а оператору предлагается обновить список;
- IP view не создаёт локальный бессрочный history ledger и не пишет IP values в audit только ради просмотра.

## Хосты инфраструктуры и Host Groups 3x-ui (#422)

`/admin → Инфраструктура → 🌐 Хосты` различает два источника: `🗂 Адреса инфраструктуры · SQLite` — текущие локальные метаданные панели/подписок (зелёная отметка = запись enabled, **не** API/node/Xray health); `🌐 Хосты 3x-ui · Master API` — read-only живой `GET /panel/api/hosts/list`, без локального SQLite upsert. Кнопка локального обнаружения переименована в `🔎 Импортировать адреса из конфигурации`: она выполняет только три upsert известных из конфигурации URL и может повторно включить локальную запись. Новые и старые действия не изменяют DNS/nginx/Xray/Host Groups 3x-ui автоматически.

Host Group details отображают адреса/порты, enabled/hidden, inbound aliases (`GET /panel/api/inbounds/options`) и связь `nodeGuids` ↔ `NodeView.guid` (`GET /panel/api/nodes/list`). Несколько GUID могут обозначать разные ноды для одной группы. Имя inbound, страна в домене или индекс панели **не** доказывают физическую Node: для пустого/незнакомого GUID используется `не определена` / `нода не найдена`, при отказе Node API — явное `API недоступен`; отсутствие GUID нельзя автоматически приписывать Master. Данные центральной панели не претендуют на локальную конфигурацию unmanaged/самостоятельной 3x-ui ноды и не свидетельствуют о доступности Xray.

Callbacks `admin:hosts:xui:page:N` и `admin:hosts:xui:detail:N:P:H` — read-only RBAC `hosts.view`, bounded pagination, Refresh, Back → Хосты; числовые индексы используются только для текущего fresh API snapshot и не разрешают mutation. Устаревшая кнопка должна безопасно сообщать, что список изменился. URL path/query, subscription IDs, credentials, raw upstream data не выводятся. При API error возвращать явное состояние `недоступен`, а не `Групп: 0`.

## Historical bot.update unknown acknowledgment (schema v12)

Owner открывает `Система → Обновления бота → Разобрать исторический unknown`, выбирает фиксированное основание и подтверждает отдельным callback. UI использует только Deploy Agent GET, не отправляет deployment POST и не меняет `unknown` в `success`. Read-only evidence разделяет журнал операции и текущий health. SQLite хранит immutable job_run_id, actor, основание, evidence и аудит. Обзор скрывает только acknowledged run; история сохраняет original unknown с отметкой о рассмотрении. Новая проблема с новым ID появляется снова.

## Telegram username в списке администраторов (#355)

Owner-only список `/admin → Система → Администраторы` отображает `@username` только из недавно наблюдавшихся авторизованных private Telegram updates; при отсутствии, удалении, ошибке валидации или истечении 6-часового TTL показывает `TG <telegram_id>`. Кэш изолирован в памяти процесса, ограничен 256 записями, не содержит истории, после restart пуст и не вызывает `getChat`/network lookup или SQLite migration. Факт наблюдения `from_user` не влияет на `get_admin_role`, callback identity, RBAC или audit; одинаковые/изменяющиеся username не создают связей между разными IDs. Карточка всегда содержит цифровой `Telegram ID`, даже если известен username. Telegram keyboard labels ограничены 64 символами; источник/статус/роль и отметка «локальная конфигурация» сохраняются. Не записывать username в audit/log и не показывать вне Owner-only раздела.

## 📚 Команды бота (#356)

`/admin → Система → 📚 Команды бота` — read-only справочник для всех четырёх admin roles; кнопка `⬅ Система` ведёт на `admin:section:system`. Callback `admin:commands` защищён существующим `dashboard.view` (minimum Read-only) и `authorize_callback`. Список строится только из типизированного `telegram_commands.COMMANDS`, включает версию каталога и версию бота, точные slash name, описание, audience/role, статус active/legacy и явный клиентский gate `CLIENT_PORTAL_ENABLED + pilot allowlist`. Просмотр не запускает slash handler, не изменяет Telegram global bot command list и не обещает доступ к клиентским функциям. Для новых/удалённых/переименованных slash handlers обновлять каталог, этот документ и regression tests одновременно; fail-closed AST check `scripts/check-telegram-command-catalog.py` входит в required CI и обнаруживает aliases, `CommandStart` и drift исходных handlers.

## Trial limits (#343)

В `/admin → Система → Настройки` значение `0` для `trial_traffic_gb` — **без квоты трафика** (`totalGB=0` в 3x-ui), для `trial_ip_limit` — **без ограничения одновременных IP** (`limitIp=0`). `trial_days` требует 1..3650, ноль не разрешён. Значение отсутствующего override берётся из `.env`; явная строка `"0"` сохраняется. Некорректный, пустой или выходящий за границы override не маскируется fallback и блокирует новое создание в режиме совместимости до исправления. Значения относятся только к **новым** trial-пользователям режима совместимости; существующие учётные записи, подписки и настройки Xray автоматически не переписываются. Семантика подтверждена исходным UI 3x-ui v3.9.0 (`totalGBDesc`, `limitIpDesc`) и кодом проверки IP (`limitIp <= 0`: no enforcement).

## Owner-only runtime switches (#342)

`/admin → Система → Настройки → 👤 Клиентский портал`: просмотр effective portal/Stars, безопасного DB override и `.env` veto доступен admin roles в private chat; изменение доступно только Owner через `ask → run` с revision-bound callback. SQLite `runtime_settings` хранит точные `true`/`false` и отдельный revision, CAS и аудит пишутся атомарно. При сбое DB/invalid override оба флага закрыты. `effective_portal=env_portal AND db_portal`; `effective_stars=env_stars AND db_stars AND effective_portal`. Отсутствующий override означает разрешение. Кнопки не дают обойти `.env=false`, allowlist/ACL или rate limiting. Проверка выполняется на customer entry, invoice и pre-checkout, включая ранее выданный счёт; обработка пришедшего `successful_payment` не блокируется и остаётся идемпотентной. Не редактировать `.env`/tokens/host или клиентские entitlements через toggle. Меню показывает только количество пилотных аккаунтов (без ID), лимит и окно. `default_currency` теперь подписан «Валюта ручных платежей» и не относится к Stars.

### Карточка пользователя: платежи (candidate rc.10 / #628)

- `admin:u:payments` показывает два отдельных read-only ledger: `⭐ Telegram Stars (XTR)` и `📒 Ручные платежи (учёт)`. Суммы XTR/fiat не складываются, `confirmed` Stars не равен `paid` legacy.
- Stars-detail открывается только при `commerce_payments.order_id → commerce_orders.telegram_id` совпадении с выбранным пользователем; отдельный callback namespace предотвращает пересечение ID. В карточке нет кнопок refund/status mutations, stale callback fail-closed.
- Пагинация ограничена восемью операциями на страницу, выбор ledger и `Назад` сохраняют user context; общий Admin Stars ledger остаётся отдельным экраном.

## Заказы Telegram Stars в административном UI (#470, rc.17)

`/admin → Платежи → ⭐ Telegram Stars → 📦 Заказы Stars` — read-only список `commerce_orders` для `currency=XTR` (до восьми записей на страницу), с отдельной карточкой `admin:starsorder:<id>:<offset>`. Кнопки просмотра, пагинации и возврата имеют privilege `payments.view` (Read-only+), private-chat boundary. Карточка из одного bounded SELECT связывает `Order → последний Telegram Stars Payment → Entitlement` и название тарифа; не раскрывает `provider_payment_id`, invoice payload, checkout URL, subscriptions или secrets. `TG ID` — уже разрешённая административная identity в закрытом /admin, иных PII экран не добавляет. При отсутствии Payment показывается `Платёж ещё не подтверждён / не создан`, не `failed`; отсутствие Entitlement не означает ошибку. Счёт Telegram invoice не проверяется и не объявляется доставленным/активным.

Только чтение: ни `retry`, `refund`, `cancel`, ни webhook/provider mutations, ни отправка invoice. Старые `admin:starspayments` и `admin:starspayment` сохраняются. На карточке доступен переход к существующей карточке Stars-платежа, если платёж найден; Back возвращает на исходную страницу Orders. Invalid/stale callback не выполняет mutation. Targeted operator-reported S1…S8 отмечены 8/8; условные S3/S6 покрыты offline fixture тестами `tests/test_stars_orders_470.py`, без утверждений о реальных production-записях. [#470](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/470) CLOSED/completed; общий G-11 PARTIAL/NO-GO.

## Справочник возвратов поддержки (#437, rc.17)

`/admin → Платежи → 📖 Политика возвратов` — только read-only памятка (callback `admin:refundpolicy`): проверка обращения, спорные `duplicate/unknown/in_flight`, справка по § 9, эскалация Owner. Каждый вложенный экран имеет `⬅ Политика возвратов` и `⬅ Платежи`; новые callbacks защищены `payments.view` и private-chat RBAC для `Read-only` / `Support` / `Administrator` / `Owner`. Сам просмотр не вызывает платежей, Stars refund, provisioning или сохранения PII.

Версия/дата/публичная ссылка Terms поступают только из [versioned publication record](legal-publication.json), общего с планом юридических страниц #707; до подтверждённой публикации и срока вступления в силу UI показывает **не опубликована**, ссылку на неподтверждённый HTML не создаёт и не пересказывает юридические условия. После подтверждения допустима только точная canonical URL `/legal/terms` без идентификаторов клиента в query. Support не предоставляет самостоятельных прав на `admin:starsrefund:ask/run`; без утверждённого § 9 спор передаётся Owner. Отменённый 14-дневный добровольный refund #433/#434/#436 не восстанавливать. `v5.0.0-rc.17` Published/Deployed operator-reported; scoped Support UI/RBAC/no-mutation R1…R8 operator-reported PASS; #437 OPEN до опубликованного § 9 по #707; full v5 G-11 PARTIAL/NO-GO.

## Тарифы: UX после дефектов #705 (2026-10-17)

В карточке вместо сырых `all/groups/admin_only` показываются русские обозначения. Правила локальных групп называются «Группы пользователей», не «Аудитория»; группы серверов — отдельная сущность. `⬅ Назад` ведёт к предыдущему экрану, `✖ Отмена` прекращает операцию. Срок `duration_days=0` отображается как «Бессрочно», без `0 дн.`.

Выбор обычного тарифа требует одноразового подтверждения назначения и применения лимитов в 3x-ui. При `unknown` успех не заявляется и слепой повтор запрещён. Для бессрочной выдачи read-only preflight Inbounds проводится до durable `in_flight`; после неизвестного результата требуется read-only review, не повторное подтверждение.

**Дополнительная ревизия #705:** обычный тариф применяется к 3x-ui с read-back **до** атомарного подтверждения локального `plan_id` и срока; неизвестный результат не маскируется как успешная локальная выдача. Прямой `admin:bulk:runplan` запрещает бессрочную выдачу так же, как экран выбора. Некорректный JSON групп не должен ломать Telegram-карточку. В списке тарифов Stars-only план не показывается как `0 RUB`.

## Независимые лимиты тарифа: IP и HWID (#724, кандидат rc.16.2)

При создании тарифа отдельными шагами указываются `IP limit` и `HWID limit` (зарегистрированные устройства), оба от 0 до 1000, где `0` явно означает без ограничения. Нельзя показывать «IP/устройства» как единое число. Карточка тарифа, review, Admin Create User и профиль пользователя должны выводить оба поля. Для старых тарифов `hwid_limit=NULL` означает «индивидуальный лимит сохраняется» (не равно нулю). В карточке тарифа и пользователя показывать «Лимит HWID: не задан в тарифе — сохраняется текущий лимит пользователя»; значение нельзя представлять как «без лимита» и нельзя менять его при согласовании такого ранее созданного тарифа. Для новых тарифов `limitHwid` применяется только вместе с `limitIp` и проверяется независимым read-back; никакой автоматической конвертации IP→HWID.

**Редактор Flow и источник Node Panel (#691, кандидат rc.16.2):** в экране выбора Flow для локального Master Inbound `node_id=0` выводить `Node Panel: — не требуется (Master)`, а не `не проверено`: отдельного direct Node Panel для Master нет. Для direct node показывать `не проверено на этом экране`, пока этот экран не провёл адресный read-back. Исторический результат `🔎 Проверить Flow` с TTL 180 секунд остаётся только в карточке пользователя/параметрах доступа с пометкой `не live`; он не превращается в разрешение на mutation и не считается новым подтверждением editor. Не менять Flow POST, direct Node matching, nonce, RBAC или Xray attestation.

## Пагинация журналов и истории (#719, кандидат rc.16.2)

Для административных платежных журналов (`💳 Платежи` — ручные и `⭐ Telegram Stars`) и других сопоставимых длинных историй действует единый UI-контракт: **8 записей на страницу**, строго ограниченный запрос (`LIMIT/OFFSET`), детерминированная сортировка, счётчик всех записей, `⬅ Новее` и `➡ Старее` только при доступной соседней странице. `Назад` из detail восстанавливает контекст страницы; старые callback без offset открывают первую страницу. Пустой и устаревший offset не вызывают ошибку или необратимую навигацию; RBAC проверяется для каждой страницы и карточки. Данные платежей, возвраты и статусные mutation не меняются. Для отличающегося размера страницы необходимо явное описание причины в этом документе.

## Переход с ручного бессрочного тарифа (#721, кандидат rc.16.2)

Статус `active` означает подтверждённую бессрочную выдачу, а не ошибку и не «требуется повторное подтверждение». Её нельзя завершать кнопкой `🔎 Сверить ручную выдачу`: read-only review предназначен для `unknown/in_flight`. Выбор обычного конечного тарифа требует отдельного Admin/Owner-confirmation `✅ Подтвердить переход`, предварительного read-only состояния 3x-ui, durable marker, применения целевых лимитов и независимого read-back. Только после этого запись выдачи становится `superseded` и меняется локальный тариф. Неизвестный исход блокирует новый переход; требуется `🔎 Сверить ручную выдачу` без повторного provisioning. Support и Read-only не получают кнопку подтверждения перехода. Нельзя вручную удалять journal или переписывать status через SQLite.
