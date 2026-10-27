# Сервисные кампании — source contract

Нормативный контракт компонентов эпика [#874](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/874). Фактические main/Published/Deployed/Accepted и очередь находятся только в [Roadmap](ROADMAP.md); наличие модулей и таблиц не даёт разрешения отправлять сообщения. Политика обязательных/необязательных уведомлений — отдельный prerequisite #501.

## Foundation #947

`service_campaigns.py` — внутренний source-only API; `campaign_store.py` — persistence в существующей bot SQLite через штатный migration framework. Нет runtime assembly, Telegram/HTTP endpoint, UI, worker, scheduler, transport, listeners или новых env. Импорт/конструктор не запускают работу и не создают БД. Подключение к runtime и действительные private observations относятся к последующей части #949; delivery state machine — к #948.

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
