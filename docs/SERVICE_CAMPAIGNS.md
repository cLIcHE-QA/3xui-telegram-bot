# Сервисные кампании — source contract

Нормативный контракт компонентов эпика [#874](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/874). Фактические main/Published/Deployed/Accepted и очередь находятся только в [Roadmap](ROADMAP.md); наличие модулей и таблиц не даёт разрешения отправлять сообщения. Политика обязательных/необязательных уведомлений — отдельный prerequisite #501.

## Foundation #947

`service_campaigns.py` — внутренний source-only API; `campaign_store.py` — persistence в существующей bot SQLite через штатный migration framework. Сам foundation API не содержит runtime assembly, Telegram/HTTP endpoint, UI, worker, scheduler, transport, listeners или новых env. Импорт/конструктор не запускают работу и не создают БД. Подключение к runtime и действительные private observations относятся к последующей части #949; delivery state machine — к #948.

Draft API по умолчанию **DENY**: доверенный адаптер обязан передать асинхронный `authorize_owner(actor)` с актуальным server-side решением Owner. Только точный `True` разрешает операцию; отсутствие callback, неизвестное решение и ошибка авторизации не дают доступа. Role strings/actor из callback payload не являются доказательством полномочий. Каждый owned read/edit/freeze/dry-run повторно ограничен `owner_id` в SQL. Админский `/admin`/client RBAC не меняются этой foundation; здесь нет входного сетевого маршрута, который обходит существующую авторизацию.

Публичные DTO не содержат owner/recipient Telegram IDs. Список возвращает до **8** summaries без body, стабильная сортировка updated_at/id и ограничение stale page последней страницей. Полный текст доступен только через owned API; `repr` DTO не содержит subject/body. Ошибки общие, без текста кампании, SQL, путей БД или сырых исключений. В коде нет логирования body, контактов, подписок или provider payload.

## Plain-text payload и revisions

Разрешены только категории `technical`, `service`, `tariff`. Это тип черновика, **не** admission для доставки и **не** доказательство, что текст не рекламный. Subject 1…120 символов, body 1…3500; control/bidi/surrogate, raw HTML/Markdown links, URI/URL, IP и распространённые credential-shaped значения отклоняются. Media, CTA/inline links и rich-text не реализованы в foundation. Валидация не заменяет operator review содержания/секретов/сервисного назначения. Истинные credentials/подписки/персональные данные запрещено вводить в черновики.

Payload имеет закрытый набор ключей и канонический UTF-8 JSON; include/exclude — уникальные отсортированные IDs **локальных User Groups**, до 50 в каждом правиле, не Host/3x-ui groups. На записи/оценке группы проверяются в локальной БД; отсутствующая группа fail closed, без fallback «все».

Edit использует optimistic expected revision и одну SQLite write transaction. Stale/concurrent edit не подменяет новый текст. Freeze фиксирует текущий canonical payload+SHA-256 в отдельной immutable revision; повтор того же freeze возвращает ту же запись. Последующие edits создают новую draft revision, не меняя frozen. SQLite ownership trigger и запреты UPDATE/DELETE frozen rows являются частью строгой schema postcondition. Freeze **не** создаёт job/recipient snapshot, не подтверждает consent и не разрешает send. Пределы хранения foundation: 100 drafts на owner и 64 frozen revisions на draft; достижения лимита не обходятся автоматическим удалением истории.

Ошибка/потеря результата локального commit или невозможность доказать rollback возвращает `CampaignOutcomeUnknown`, не «точно не записано». Нет автоматического retry: сначала owned read-back/list/revision; CAS и повтор freeze защищают существующие версии. Ранний отказ БД/авторизации — unavailable/denied, без раскрытия исходного исключения.

Отмена async await также не разрешает replay. Если read-back не позволяет однозначно установить outcome, caller останавливается для review, а не создаёт второй запрос автоматически.

## Trusted private contact — отдельная граница

`observe_private_update(actor_id, chat_id, chat_type, is_bot)` предназначен **только** для будущего доверенного адаптера authenticated Telegram update. Actor/chat берутся из реального update, никогда из формы, callback payload, импорта или admin-created ID. Требуются положительные actor/chat IDs, их равенство, `private`, `is_bot=False` и уже существующий локальный user. Вызов не создаёт user. В #947 этот адаптер не подключён: таблица остаётся пустой без явных внутренних вызовов, synthetic fixtures не становятся production evidence.

Хранятся только Telegram ID, first/last UTC timestamp, фиксированный source `private_update` и локальный blocked timestamp. Нет username, chat title, исходного update или содержимого сообщений. Повтор observations дедуплицирован, время не откатывается; observation не снимает blocked и не означает право/согласие на коммуникацию. User delete удаляет contact proof; повторное создание того же user само proof не восстанавливает. Нет backfill из users/entitlements/imports и нет вывода contact list через API.

## Candidate dry-run — не eligibility

Read-only snapshot считает уникальных кандидатов из contact ledger JOIN существующих users, исключает локальный blocked и применяет include/exclude User Groups с **deny/exclude priority**, как `audience.py`. До 1000 кандидатов и флаг truncated; SQL aggregate/ограниченный запрос, без полного in-memory fan-out или возвращаемого списка IDs. Устаревшая revision/группа/неподтверждённая БД не превращается в безопасный полный список.

Результат всегда `deliverable=0`, `policy_status=unapproved` для **всех** категорий. Нет mandatory inference, opt-in/opt-out implementation, owner callback «разрешить сейчас» или режима, который можно включить этим API. #501 и последующий admission contract не заменяются mock/флагом. Known private candidate не означает reachable chat, активный entitlement, consent или подтверждённую доставку. Финальный eligibility/snapshot/revalidation относится к следующим scopes после их prerequisites.

## Schema и дальнейшие границы

Additive schema v16: `service_campaign_drafts`, `service_campaign_revisions`, `service_campaign_contacts`, индексы и triggers. [SQLITE_MIGRATIONS](SQLITE_MIGRATIONS.md) — единственный migration contract. Строгая проверка SQL definitions/constraints/indexes/triggers; unjournaled объекты не принимаются за trusted ledger. DAO открывает только существующий rw/ro DB и требует актуальный successful migration journal. Failed/unsupported schema не чинится этим API.

Следующие части не вправе автоматически replay interrupted sends: timeout/lost response/lease loss остаются unknown. Runtime OFF и category admission DENY_ALL сохраняются до настоящих prerequisites; optional #501, media/CTA allowlists, abuse/privacy review, pilot identities/sends и deployment требуют собственных проверок и отдельного разрешения. UI/transport source mocks не доказывают Telegram delivery. Этот foundation не меняет public rollout или G-11.


## Изолированная очередь #948

`CampaignDelivery` и `CampaignWorker` из `service_campaign_delivery.py` — отдельный source-only слой; persistence находится в `campaign_queue_store.py`, статическая additive schema — в `campaign_queue_schema.py`, расписание — в `campaign_schedule.py`. Импорт/конструктор не создаёт tasks/listeners, не открывает БД и не запускает scheduler. В `app_runtime` ничего не зарегистрировано; Bot API adapter, env flags и реальные credentials отсутствуют. Публикация части не принимает весь #874.

### Реальное admission и тестовые границы

По умолчанию конфигурация OFF и реальное admission DENY_ALL. Отсутствующая policy не разрешает даже создание queue job/snapshot; отсутствие transport не запускает worker. Trusted server-side `CampaignPolicy` обязан отдельно подтвердить category и recipient; только точный True разрешает действие, неизвестный ответ/ошибка не дают прав. Категория не классифицируется как mandatory. Реальная policy #501 здесь не реализована, defaults/consent не выдуманы.

Положительная fake policy используется **только в isolated tests с fake transport**. Это не согласие клиента, операторское approval, продуктовая policy или способ включить рассылку. Python injection point предназначен для будущего проверенного server-side adapter, не для role strings/JSON/callback payload или кнопки Owner «разрешить сейчас». До настоящих #501/privacy/abuse prerequisites runtime wiring запрещено. Прикладной код не должен устанавливать test policy в production.

Owned prepare/get/list/confirm/pause/cancel/resume используют текущий Owner authorizer и owner_id в SQL. Worker повторно проверяет текущего Owner и category/recipient admission перед обращением к transport. Policy/RBAC ожидание ограничено 3 секундами; errors обезличены. Чтение/остановка существующей owned job доступны авторизованному Owner и при выключенном delivery, чтобы OFF не мешал безопасной остановке.

### UTC/IANA расписание

Вход — точная строка `YYYY-MM-DDTHH:MM` без offset/секунд плюс явный IANA key с `/` либо UTC. Нет host-local TZ, fallback UTC или угадывания сокращений. DST gap/fold, неизвестный key, отсутствие timezone data, прошедшее/равное now время и срок далее 366 дней отклоняются. Fold не выбирается автоматически: оператор должен задать однозначное время. Сборка pinned image проверяет UTC и IANA data под UID10001 без новых packages/privileges; policy/runtime от этого не включаются.

Принятый UTC instant фиксируется и не переинтерпретируется после обновления TZ data. Проверка часов обновляется после получения SQLite write transaction, чтобы ожидание lock не сделало прошлое расписание «будущим». Prepare и confirm не принимают уже наступивший срок. Первый старт позже ready_at более чем на 60 секунд переводит job в paused; массового catch-up после простоя нет. Подтверждённый своевременный запуск и ограниченные safe 429 retries — отдельные состояния, не повтор исходной confirmation.

Resume — отдельное явное owned действие с **новым будущим** временем через тот же parser. Исходные due_at/timezone/local_time неизменяемы; ready_at показывает следующее UTC время. Пока intent/lease не завершён, resume блокируется. Unknown recipients не возвращаются в pending. Обратный ход относительно clock_seen закрывает доступ без новых попыток.

### Snapshot, identity и хранение

Prepare требует owned frozen revision и подтверждённый category admission. SQL snapshot включает только unique existing users JOIN trusted private contacts, unblocked и подходящие local User Groups с exclude priority. Сохраняется bounded набор **кандидатов**, не утверждение eligibility/consent/reachability; персональный admission проверяется перед dispatch. Пустой набор либо более 1000 кандидатов откатывает всю transaction, без частичного fan-out. SQL VM ограничен прогресс-бюджетом 10 млн операций/5 секунд; превышение прерывает запрос и откатывает transaction без частичного snapshot. Это не deadline disk commit: при неопределённом commit сохраняется outcome unknown. Fingerprint считается ограниченными batches100; публичный результат содержит только aggregate counts и immutable identities, без ID list/body/owner ID.

В schema17 отдельная private-contact generation создаётся для verified v16 proofs, никогда из users/import. Новый trusted observation создаёт generation, повтор сохраняет её. Удаление contact удаляет generation даже при FK=OFF в старом DB helper; recreate с тем же ID и timestamp получает другую generation. Snapshot привязан к прежней generation и не может приобрести права нового proof. Удалённый/blocked user, изменившаяся membership или отсутствующая группа не обходятся fallback «все».

Job содержит immutable revision/payload SHA, operation UUID4, исходное расписание и sealed snapshot SHA. Одинаковый owner+operation с тем же spec возвращает существующую job; другой spec конфликтует. Повтор confirm того же snapshot не создаёт recipients/attempts заново. Будущий UI обязан сохранять один operation ID на один intent; новый UUID не является механизмом retry неизвестной доставки.

Пределы: 100 jobs на owner, 1000 candidates/job, page8. История identity/snapshot/attempts не удаляется автоматически; terminal outcomes неизменяемы. Retention/privacy и реальный сбор данных требуют отдельного review до runtime activation. SQL guards запрещают прямой переход draft→running, запись sent без intent, смену frozen identity и возврат terminal recipient/attempt в работу. Framework проверяет все SQL definitions/indexes/triggers, control singleton и целостность generation; missing/unjournaled state не чинится DAO.

### Fenced worker и результаты

Один private singleton lease разрешает максимум один campaign worker в БД; token не выходит в DTO. Lease 30 секунд обновляется только с правильным token до истечения. Expired/lost lease или restart с durable intent переводит его в unknown, job в paused; interrupted intent **не повторяется автоматически**. Внутрипроцессный lock дополнительно сериализует tick одного объекта. Один явный tick обращается к transport максимум один раз, отдельный campaign budget допускает не чаще одного dispatch за 2 секунды и не занимает общий client/admin limiter.

Durable intent фиксируется **до** вызова transport. Lost commit result — CampaignOutcomeUnknown, не безопасный failure; автоматического retry нет. Подтверждение требует точного chat ID и положительного message ID. Mismatch/невалидный reply, timeout/network exception и неопределённый 5xx outcome — unknown/no-replay, job paused, экземпляр worker останавливает новые dispatch. Поздний ответ не перезаписывает unknown. Нет обещания exactly-once sendMessage.

Только trusted typed подтверждение «не принято» 429 допускает retry_after 1…3600 секунд, local backoff и максимум **3 durable intents** на recipient. Это включает доказанные not_sent preflight reservations; resume не обнуляет счётчик. Третий safe 429 завершает recipient как failed/retry_exhausted. Неизвестный/невалидный retry_after не становится safe retry. Подтверждённый unavailable/403 — terminal unavailable; blocked proof не снимается новым observation. Иные HTTP/body ошибки нельзя классифицировать по сырому тексту как safe failure.

До обращения повторно проверяются current proof/groups/admission/fence. Доказанный отказ до вызова transport фиксируется not_sent: персональный deny/недоступность кандидата — skipped, глобальный policy/stop — pending в paused job, cancel — terminal cancelled. Эти записи не утверждают доставку. Положительный fake acknowledgment доказывает только обработку isolated ответа в тесте, не Telegram delivery.

Transport ожидание ограничено 10 секундами. Cancellation не гарантирует прекращения внешней операции: некооперативная task может завершиться позднее, результат остаётся unknown; исключение извлекается без логирования payload. Такой worker не начинает новые dispatch. close ждёт текущий bounded tick, приостанавливает остаток и возвращает False, пока некооперативная task ещё pending; True не отменяет прежний unknown outcome.

Pause/cancel запрещают новые intents. Уже in-flight попытка может подтвердиться либо стать unknown; cancel не откатывает отправленное. Pending recipients при cancel становятся cancelled, при pause сохраняются для явного future resume. После owner stop/lease loss нет автоматического replay. Перезапуск worker не является разрешением повторить unknown.

### Собственный acceptance и дальнейшие зависимости

Собственный #948 scope — offline schedule/migration/state/ownership/fencing/retry/stop/privacy regressions, trust-boundary review, required CI, immutable RC и publication/main checkpoint. Реальные сообщения/listeners/боты/VPS здесь не нужны и не разрешаются. Parent #874 остаётся OPEN до #949/policy #501/privacy/abuse/allowlists/deployment/pilot. `app_runtime` не получает fake policy или transport, G-11/public rollout этим источником не принимаются.


## Закрытые source-компоненты Owner UI и Telegram adapters #949

`campaign_owner_ui.py` и `campaign_telegram.py` — source-only библиотечные компоненты, не runtime registration. Они не включены в `app_runtime`, dispatcher, client guards или глобальное меню. Импорт/конструктор не запускают polling, listeners, worker, observation, HTTP или отправку. Нет новых env/credentials/портов; публикация source RC не разрешает подключение.

`create_campaign_owner_ui(db, settings, enabled=False)` всегда создаёт `CampaignDelivery(enabled=False, policy=None)`. Boolean редактора не является delivery approval: UI не принимает policy/role/allowlist из callback или FSM и не содержит переключателя отправки. Настоящее runtime registration BLOCKED до #501/privacy/abuse/allowlist review; затем отдельный integration PR, required checks и разрешённый deployment/pilot. Это точный оставшийся gate #949, не fake policy и не завершение parent #874.

### Приватная source-навигация и ввод

Source router `admin:campaigns` — только текущий Owner в своём private chat. Зарезервированное Owner-only правило `campaigns.manage` отображается в существующем справочнике прав после установки кода, но само не регистрирует runtime handler. Permission повторно проверяется сервером; группы/боты/чужой private context, forwarded/sender_chat/via_bot и callbacks от human panel отклоняются. Существующий Client Portal и его guards не меняются. В живом меню новая кнопка пока отсутствует; будущий parent — `Система`.

Все actions кроме безопасного root используют случайный opaque nonce: привязка actor/chat/message, текущая видимая клавиатура, mutation confirmation TTL90 (navigation600) и consume до первого mutation await. Максимум256 live tokens, capacity fail closed с фиксированным выходом в Систему; restart отзывает confirmations. FSM живёт до600 секунд, input требует тот же active panel и актуального Owner; чужой/старый/сменившийся раздел не продолжает форму. Callback не содержит текста, recipient IDs, URL или авторизации.

Черновик проходит закрытую category → тема → текст → include groups → exclude groups → явное сохранение. Ввод групп — максимум50 существующих stable group IDs, не Telegram IDs; `-` означает пустой include (все proven candidates) либо пустой exclude. Это локальная сегментация, не право отправки. Edit использует expected revision/CAS; stale review не перезаписывает новый текст. Cancel возвращает в непосредственный экран входа, сохранение — в owned карточку.

Local preview — plain text (`parse_mode=None`), без media/CTA/URL actions; вывод ограничен3800 UTF16 units с явным «показан фрагмент». Полный текст остаётся owned draft. Тестовой отправки нет. Черновик с большим количеством emoji можно сохранить для правки, но планирование/adapter требуют максимум4096 UTF16 units для темы + двух переводов строки + тела. Синтаксический фильтр не заменяет смысловую проверку содержания/секретов Owner.

Планирование принимает точные `YYYY-MM-DDTHH:MM IANA`/UTC через прежний parser, показывает MSK и исходный TZ, требует отдельного revision-bound подтверждения. Категория/Owner/private proofs перепроверяются; отсутствующая policy блокирует до snapshot. Server operation UUID сохраняется на один intent; повтор confirmation не создаёт второй fan-out. Progress показывает aggregate counts, не адресатов/body. Pause/cancel двухшаговые и доступны при выключенном редакторе; уже отправленное не откатывается, in-flight может остаться unknown. Resume/автоматический retry через UI не добавлены.

### Trusted private-update adapter

`CampaignPrivateObserver` по умолчанию OFF, authorize_update=None/DENY_ALL. Будущий trusted caller обязан передать только уже аутентифицированный, разрешённый feature/pilot/rate/privacy контуром `Message`. Actor берётся из `from_user`, private chat должен принадлежать ему; bot/forward/sender_chat/via_bot отклоняются. Adapter не принимает отдельные recipient IDs, imports или admin-created identity. Store только обновляет minimal v16 proof существующего user; blocked не снимается, нового пользователя/согласия нет.

Admission ограничен3 секундами и одной task, в том числе при некооперативной отмене; пропущенное наблюдение не ломает client jobs. DB/policy ошибки возвращают False без raw message/error. Сам adapter нигде не установлен; observer/provenance fixtures не доказывают реальные private контакты или consent.

### One-shot Bot API и доказанный HTTP429

`CampaignBotTransport` использует переданный существующий bot, не загружает и не создаёт tokens/другие platform credentials. Отсутствующий trusted authorize_envelope означает DENY_ALL. Будущий authorizer должен повторно проверить immutable intent/proof/policy, не получать chat IDs из UI payload. Один вызов — ровно один фиксированный sendMessage, без redirects/retries/paid broadcasts/markup/CTA/alternate business/thread targets. Plain text и link-preview OFF, protect_content ON. Recipient — только положительный private chat; success требует strict positive message ID, тот же private chat и отправителя того же bot.

SDK `TelegramRetryAfter` сам по себе не доказывает HTTP429: pinned aiogram проверяет retry_after до HTTP status и может поднять его для5xx. Поэтому только `_CampaignSendMessage` через source `CampaignAwareSession.check_response` с фактическим HTTP429, raw JSON ok=false/error_code429 и exact int retry_after1…3600 получает внутренний verified rejection. Adapter принимает его только для того же request object и привязывает typed result к исходному private chat. Обычные bot methods сохраняют прежнюю SDK semantics; session не устанавливается и shared bot не перенастраивается этим кодом. При стандартной session обычный RetryAfter консервативно остаётся unknown, не safe retry. Future runtime review обязан исключить внешние autoretry middleware и отдельно подтвердить composition/session provenance.

Доказанный403/строгое HTTP400 chat-not-found того же request object — terminal unavailable; только точное подтверждение bot-blocked помечает private proof blocked; иные4xx/5xx/network/decode/невалидный reply неизвестны. Adapter ограничивает одну transport task/8 секунд и после unknown/timeout/cancellation закрывает новые calls; late reply не меняет исход. Не кооперативная task не ждётся бесконечно и не даёт запустить fan-out. Worker #948 сохраняет свой durable intent/fencing/10-second boundary и bounded3 verified429 intents, adapter не повторяет запрос сам. Raw SDK/HTTP/body/errors не логируются и не выходят в UI.

### Оставшийся late checklist

Source/fake PASS не является runtime acceptance. В конце #930: утвердить #501 category/recipient/defaults и privacy/abuse/retention, определить разрешённый bounded pilot и allowlist; после этого отдельный reviewed integration PR подключает router/наблюдение/проверенный transport без ослабления guards, подтверждает disable/stop/recovery и session/no-retry provenance. Только затем оператор отдельно разрешает deployment и полный минимальный targeted pilot checklist: Owner/private/stale/stop, достоверный private proof, agreed category admission, receipt/unknown/no-replay/rate budget и финальный health. Реальные identities/sends/Telegram eligibility не запрашиваются сейчас. Старые HWID PASS/waived burst не повторять, Published/Deployed/Accepted различаются.
