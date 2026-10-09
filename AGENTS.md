# AGENTS.md

Этот файл задаёт правила работы AI coding agents с репозиторием.

Главный принцип: **состояние проекта восстанавливается из репозитория и его канонической документации, а не из истории чата**.

Не дублируй существующие project contracts в этом файле. Читай соответствующие документы перед изменением затрагиваемой области.

## 1. Перед началом любой задачи

Сначала:

1. Проверь текущее состояние working tree:

   ```bash
   git status --short
   ```

2. Не удаляй, не reset'ь, не перезаписывай и не откатывай существующие пользовательские изменения без явного запроса.

3. Определи текущую версию и архитектуру проекта по:
   - `README.md`;
   - `version.py`.

4. Для понимания текущего product state и незавершённой работы прочитай релевантные части:
   - `docs/ROADMAP.md`;
   - верхнюю актуальную часть `CHANGELOG.md`.

5. Перед изменением процесса разработки, Git, roadmap или release flow прочитай:
   - `docs/GIT_WORKFLOW.md`;
   - при необходимости `docs/RELEASES.md`.

6. Перед изменением current-state contract/setup/version/schema/CI оцени documentation impact по:
   - `docs/LIVING_DOCS.md`;
   - `docs/live-docs.json`.

Не восстанавливай статус задачи по старой переписке, если его можно проверить по коду, Git history, roadmap, changelog, tests или опубликованным releases.

Если информация в чате противоречит фактическому состоянию репозитория, сначала укажи на расхождение. Не подгоняй код или документацию под устаревший контекст молча.

## 2. Канонические источники

Используй документы по их назначению:

- `README.md` — текущая архитектура, module boundaries и карта документации;
- `docs/ROADMAP.md` — product stages, acceptance scope и фактические статусы;
- `CHANGELOG.md` — пользовательские и операционные изменения по версиям;
- `docs/GIT_WORKFLOW.md` — branches, commits, PR, merge, issues и roadmap workflow;
- `docs/LIVING_DOCS.md` — living/historical docs boundary, diff triggers, waivers и external repository-state drift contract;
- `docs/RELEASES.md` — tags, GitHub Releases и release contract;
- `SECURITY.md` — общие security boundaries;
- `docs/UI_STYLE.md` — Telegram UI, терминология и navigation contract;
- `docs/ADMIN_SETUP.md` — канонический current setup Admin Control Plane;
- `docs/3XUI_OPENAPI_CONTRACT.md` — контракт интеграции с 3x-ui API;
- `docs/SQLITE_MIGRATIONS.md` — правила SQLite migrations;
- профильные документы `docs/` — Host Control, Fleet, Backup, Recovery, Deploy и другие operational subsystems.

Код и tests должны соответствовать этим contracts.

Если изменение требует смены самого contract, обновляй соответствующую документацию и regression coverage в том же change.

## 3. Критические архитектурные инварианты

Не нарушай следующие границы без задачи, которая явно требует изменения архитектуры, соответствующей документации и tests.

### Runtime

- `bot.py` остаётся минимальным executable shim, запускающим `app_runtime.main()`.
- Domain handlers не должны возвращаться в `bot.py`.
- Client-facing flow и `/admin` сохраняют отдельные navigation/authorization boundaries.

### Privileges и security

- Bot container не получает Docker socket.
- Bot container не получает generic host shell.
- Host Control не превращается в SSH gateway или arbitrary remote executor.
- Разные privilege domains используют отдельные credentials/tokens.
- Direct Admin, Host Control, panel, Deploy Agent и object-storage credentials не переиспользуются между domains.
- Unknown administrative routes/callbacks/permissions должны fail closed.
- Не добавляй fallback между разными privilege domains только ради того, чтобы операция «сработала».

### Mutations

Для state-changing операций:

- не предполагай success без подтверждённого post-condition;
- отличай `failed` от `unknown outcome`;
- interrupted Host Control/Fleet/Deploy mutations не должны автоматически replay'иться;
- retries и idempotency должны учитывать возможность того, что первоначальная mutation уже произошла;
- UI не должен маскировать unknown outcome как безопасный failure.

### SQLite

SQLite schema развивается через существующий forward-only migration framework.

Не заменяй migration изменением существующей production schema «на месте» и не обходи `schema_migrations`.

### Releases

- Published `vX.Y.Z` tag считается immutable.
- Не force-move опубликованные tags.
- Release notes происходят из `CHANGELOG.md`.
- Production deployment выполняется по опубликованному release tag, а не по произвольному `main`.

## 4. Secrets и sensitive data

Следуй `SECURITY.md`.

Никогда не помещай в код, documentation, tests, issues, PR body, logs или chat output реальные:

- bot/API/Bearer tokens;
- passwords;
- private keys;
- production `.env`;
- subscription IDs или private subscription URLs;
- backup contents;
- enrollment contents;
- private hostnames/IPs/Telegram identifiers, если они не предназначены для публикации;
- object-storage credentials.

`.env.example`, tests и documentation используют только явно фиктивные значения и нейтральные placeholders.

Если обнаружен возможный secret, не копируй его в ответ или новый файл.

## 5. Правила для конкретных типов изменений

### Telegram UI

Перед UI change прочитай `docs/UI_STYLE.md`.

Проверь:

- каноническую русскую терминологию;
- parent/Back/Cancel navigation;
- отсутствие callback/FSM dead ends;
- корректное различение `failed`, `unknown`, `offline`, `disabled`, `maintenance` и других состояний;
- consistency соседних экранов;
- соответствующие regression tests.

Не добавляй production-specific geography, hostname или operator-specific behavior в runtime UI logic.

### Installation / infrastructure / operations

Если change добавляет или меняет действия, необходимые оператору для установки, включения или безопасной эксплуатации функции, обнови в том же change:

`docs/ADMIN_SETUP.md`

Если operator action не меняется, не добавляй туда ненужную историю.

### 3x-ui API

Перед изменением используемого 3x-ui API surface прочитай:

`docs/3XUI_OPENAPI_CONTRACT.md`

Не обходи contract checks ради прохождения конкретного кейса.

### SQLite

Перед schema/data migration прочитай:

`docs/SQLITE_MIGRATIONS.md`

Добавляй regression tests для migration и backward data state, когда это применимо.

### Releases

Перед release-related change прочитай:

- `docs/GIT_WORKFLOW.md`;
- `docs/RELEASES.md`;
- актуальный раздел `CHANGELOG.md`.

Не создавай вручную tag/Release в обход установленного workflow, если задача явно этого не требует.

## 6. Tests и проверки

Во время разработки запускай targeted tests изменяемой области.

Перед завершением code change выполни стандартные repository gates:

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
python3 scripts/check-3xui-openapi-contract.py
git diff --check
```

Если какая-либо проверка неприменима или не может быть выполнена в текущем environment, явно укажи:

- что именно не было запущено;
- почему;
- какие проверки были выполнены вместо неё.

Не утверждай, что tests/CI зелёные, если они фактически не запускались.

Behavior change должен получать regression coverage, когда его можно надёжно проверить автоматически.

Security-sensitive change требует reasoning/review фактического trust boundary; зелёные tests сами по себе не доказывают безопасность.

## 7. Documentation при изменениях

Не создавай новую документацию, если уже существует канонический документ для этой темы.

Избегай параллельных файлов вроде:

- `CURRENT_STATE.md`;
- `AI_CONTEXT.md`;
- альтернативного roadmap;
- второго release process;
- второго setup guide.

Обновляй существующий source of truth.

### Living Docs

Перед PR проверь `docs/LIVING_DOCS.md` и `docs/live-docs.json`.

PR diff автоматически проверяет `scripts/check-living-docs.py` внутри required `Python checks`.

Если изменён trigger из machine-readable contract:

- `require_all` требует обновить все перечисленные living docs в том же PR;
- `review` требует doc update либо точный PR-body waiver после фактического review;
- не добавляй waiver автоматически только ради прохождения CI;
- новые постоянные current-state invariants добавляй в `tests/test_living_docs.py`;
- historical audit evidence сохраняй как историю, добавляя closure/revalidation вместо стирания старого состояния.

### CHANGELOG

Обновляй `CHANGELOG.md`, если change заметен пользователю или оператору либо должен войти в release notes.

Не используй CHANGELOG как current setup manual.

### ROADMAP

`docs/ROADMAP.md` отражает фактическое состояние, а не намерения.

Не помечай работу завершённой только потому, что код написан локально.

Различай как минимум:

- запланировано;
- реализовано в `main`;
- опубликовано;
- acceptance завершён.

Перед изменением roadmap сверяй статус с фактическим repository/release state.

## 8. Git workflow

Следуй `docs/GIT_WORKFLOW.md`.

Основные правила:

- рабочая ветка создаётся от актуального `main`;
- PR title использует установленный `<type>: <краткое описание>`;
- стандартный merge strategy — Squash and merge;
- release-prep оформляется отдельным release PR;
- не добавляй secrets в issue/PR/commit;
- не переписывай shared history без необходимости.

Не выполняй push, merge, tag, release или production deployment только потому, что code change готов. Такие действия выполняются, когда они входят в поставленную задачу.

## 9. Production operations

Не выполняй production deployment, destructive infrastructure action, secret rotation, restore или release publication без явного запроса.

При интерактивной production работе следуй `docs/GIT_WORKFLOW.md` и профильным runbook'ам.

Если оператор выполняет state-changing команды вручную:

1. дай одну операционную команду;
2. получи полный результат;
3. проверь outcome;
4. только после этого переходи к следующему state-changing шагу.

Не отправляй длинную последовательность зависимых production mutations как один необратимый блок.

## 10. Definition of Done

Перед тем как считать задачу завершённой, проверь:

- implementation соответствует существующей архитектуре;
- security/privilege boundaries сохранены;
- добавлены или обновлены tests при изменении behavior;
- стандартные repository checks пройдены либо явно перечислены непроведённые проверки;
- documentation impact проверен по `docs/LIVING_DOCS.md` / `docs/live-docs.json`;
- документация обновлена там, где изменился соответствующий contract;
- `CHANGELOG.md` обновлён для release-visible change;
- `docs/ROADMAP.md` изменён только если изменилось его фактическое состояние;
- в diff нет secrets или production-specific sensitive data;
- `git diff --check` проходит;
- итоговый diff не содержит случайного unrelated cleanup.

Перед финальным ответом кратко сообщи:

1. что изменено;
2. какие tests/checks выполнены;
3. есть ли оставшиеся риски, manual verification или operational steps.

## Telegram slash-команды (#356)

Любое добавление, удаление, переименование slash-команды, alias, `CommandStart` или route handler обязательно сопровождается одновременным изменением `telegram_commands.py`, `docs/UI_STYLE.md` и regression tests. `scripts/check-telegram-command-catalog.py` сканирует исходные обработчики через AST и выполняется в обязательном CI `Python checks`; появление неизвестной или динамической формы фильтра без review должно блокировать CI. Каталог только справочный: не регистрирует Telegram global commands, не исполняет команды и не даёт доступ в обход клиентских флагов/allowlist и административного RBAC.
