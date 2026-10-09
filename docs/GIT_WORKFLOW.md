# Порядок работы с Git

Основная ветка: `main`.

Новые изменения выполняются через отдельные ветки:

- `feature/<name>` — новая функциональность;
- `fix/<name>` — исправление;
- `hotfix/<name>` — срочное исправление рабочей системы;
- `chore/<name>` — инфраструктура и служебные изменения;
- `docs/<name>` — документация.

## Канонический стиль Git-истории

Этот раздел задаёт стиль для новых изменений. Исторические commits/PR/issues не переписываются ради соответствия новым правилам.

### Ветки

Используются короткие ASCII slug-имена:

- `feature/<slug>` — новая функциональность;
- `fix/<slug>` — исправление;
- `hotfix/<slug>` — срочное production-исправление;
- `security/<slug>` — security hardening/fix;
- `chore/<slug>` — инфраструктура, CI, automation, maintenance;
- `docs/<slug>` — документация;
- `test/<slug>` — тестовая инфраструктура;
- `release/vX.Y.Z` или `release/vX.Y.Z-rc.N` — только release-prep.

Примеры: `feature/node-readiness`, `fix/release-tag-probe`, `chore/git-conventions`, `release/v4.12.0`.

### Commit subjects

Канонический subject использует формат:

~~~text
<type>: <краткое описание>
~~~

Разрешённые типы:

- `feat:` — новая функциональность;
- `fix:` — исправление дефекта;
- `security:` — security hardening/fix;
- `docs:` — документация;
- `test:` — тесты;
- `chore:` — CI, automation, maintenance;
- `refactor:` — внутреннее изменение без изменения ожидаемого поведения;
- `release:` — release-prep.

Описание пишется по-русски, если это не точное техническое имя. Команды, API, identifiers и названия UI сохраняются в исходном виде. Subject по возможности укладывается примерно в 72 символа, не заканчивается точкой и описывает результат изменения.

Не добавляй номер issue/PR вручную в subject. Для squash merge GitHub сам добавит suffix `(#N)`.

Branch-local commits желательно оформлять тем же способом, но **каноническая история `main` определяется PR title**, потому что штатный merge strategy — squash.

### Pull Requests

PR title обязан иметь тот же формат `<type>: <краткое описание>`. Для release-prep используется строго:

~~~text
release: vX.Y.Z[-rc.N]
~~~

PR body должен кратко фиксировать:

1. что изменено;
2. зачем это нужно;
3. проверки/CI/manual smoke-tests;
4. security/compatibility/migration последствия;
5. rollout/rollback, если изменение operational.

Не перечисляй в PR body secrets, tokens, private keys или содержимое mode-0600 enrollment files.

### Язык GitHub-коммуникации

Рабочий язык repository discussions — **русский**.

По-русски оформляются:

- issue title/body и tracking updates;
- PR title/body;
- issue/PR comments и review comments;
- audit/acceptance status notes;
- release и roadmap discussion.

В исходном виде сохраняются точные технические имена: code identifiers, API/routes, filenames, commands, error/status values вроде `unknown`, `failed`, `success`, а также короткие устоявшиеся engineering terms, если перевод ухудшает точность.

Цитаты из logs, CI, API или внешних систем можно оставлять на языке источника, но пояснение к ним пишется по-русски.

AI coding agents и automation, создающие или обновляющие GitHub discussion, следуют тому же правилу. Английский используется как основной язык GitHub-коммуникации только если конкретная задача или существующий внешний thread явно этого требует.

### Merge strategy

Для обычных feature/fix/security/docs/chore/release PR используется **Squash and merge**.

Итоговый commit в `main` получает PR title как subject. Suffix GitHub вида `(#20)` является **ожидаемой и желательной** частью истории: он даёт прямую traceability commit → PR.

Пример:

~~~text
fix: проверка отсутствующего release tag (#20)
~~~

Не переписывай уже опубликованную историю ради удаления или добавления `(#N)`.

Обычный merge commit в `main` не используется, кроме действительно исключительных интеграционных случаев, которые должны быть объяснены в PR. Merge `main` в рабочую ветку для разрешения конфликтов допустим: при последующем squash промежуточная история не попадает в `main`.

Force-push/rebase общей PR-ветки без необходимости не используется.

### GitHub-side enforcement

После public transition текущий `main` дополнительно защищён repository ruleset **Protect main release path** (ID `24575428`):

- Pull Request обязателен;
- разрешён только squash merge;
- required checks: `test` и `title`;
- checks strict/up-to-date policy включена;
- deletion и non-fast-forward запрещены;
- linear history обязательна;
- bypass actors отсутствуют.

Это GitHub-side enforcement канонического workflow, а не замена правилам этого документа.

Для `v*` release tags включён active ruleset **Protect release tags** (ID `24615100`) с pattern `refs/tags/v*`: update/delete/non-fast-forward запрещены, bypass actors отсутствуют (`current_user_can_bypass=never`). Создание новых release tags разрешено и остаётся обязанностью штатного release workflow.

### Issues

Issues используются для работы, которая требует отдельного tracking/discussion. Мелкая очевидная правка может идти сразу через PR.

Канонические issue titles:

- `bug: <симптом>` — воспроизводимый дефект;
- `feature: <результат>` — новая возможность;
- `task: <результат>` — operational/maintenance/documentation задача.

Issue должен содержать факты, expected/actual behavior и acceptance criteria, когда они применимы.

Не публикуй в issue passwords, API tokens, private keys, backup archives, enrollment contents или другие secrets. Security-sensitive материал не переносится в обычный issue; фиксируется только безопасное описание/impact, а секретные данные остаются вне GitHub discussion.

Закрытие issue через PR желательно связывать обычной GitHub-ссылкой/ключевым словом в PR body, а не добавлением номера issue в commit subject.

#### Закрытие bug-issue после исправления

Bug-issue остаётся открытым, пока не доказано выполнение его собственного acceptance scope. Merge fix PR сам по себе не всегда является достаточным основанием для закрытия, если исправление должно пройти release/deployment/production smoke.

После того как:

1. исправление слито и необходимые automated/regression проверки зелёные;
2. соответствующий release опубликован и развёрнут, если bug относится к runtime production;
3. targeted verification подтверждает, что исходный воспроизводимый дефект устранён;
4. финальный health/postcondition check не выявил regression в заявленной области,

issue обновляется фактическими результатами проверки и закрывается как `completed`.

Новый независимый finding, обнаруженный во время acceptance, оформляется отдельным issue и не удерживает уже исправленный bug-issue открытым, если не относится к тому же root cause/acceptance criteria. Если исходный дефект фактически сохраняется, issue не закрывается; если тот же дефект повторно подтверждён после закрытия, существующий issue можно переоткрыть вместо создания дубликата.

### Что считается источником стиля

Для новых чатов/сессий сначала читаются:

1. `docs/GIT_WORKFLOW.md` — branches, commits, PR, merge, issues и правила ведения roadmap;
2. `docs/LIVING_DOCS.md` — current-state documentation contract и правила drift-check;
3. `docs/RELEASES.md` — tags и GitHub Releases;
4. `docs/ROADMAP.md` — текущие продуктовые этапы, acceptance scope и фактические статусы выполнения;
5. `CHANGELOG.md` — пользовательские/операционные изменения опубликованных и подготавливаемых релизов.

Для задач, меняющих установку, инфраструктуру или operational-настройку Admin Control Plane, дополнительно читается `docs/ADMIN_SETUP.md`.

Новые локальные соглашения не вводятся молча: если нужен другой стиль, сначала меняется этот контракт отдельным PR.

## Living Docs Contract

Часто обновляемая current-state документация управляется контрактом:

- human-readable policy: `docs/LIVING_DOCS.md`;
- machine-readable triggers/state expectations: `docs/live-docs.json`;
- PR checker: `scripts/check-living-docs.py`;
- semantic invariants: `tests/test_living_docs.py`;
- GitHub Settings drift: weekly/manual workflow **Repository state audit**.

Перед PR оцени documentation impact по contract. Для `require_all` trigger все перечисленные docs должны обновляться в том же PR. Для `review` trigger допустим либо реальный doc update, либо точный waiver из `docs/live-docs.json` после фактического review.

Waiver не используется для обхода известного drift. Если setup/release/schema/current-state contract изменился, living document обновляется в том же change.

Historical `docs/audits/**` не переписываются как current manual: старые факты сохраняются, а новое состояние добавляется closure/revalidation evidence.

## Обязательное сопровождение Admin Setup

`docs/ADMIN_SETUP.md` — каноническое руководство по установке и настройке **Admin Control Plane** с нуля. Оно не предназначено для будущей client-facing части; для неё используется отдельное руководство.

Любой feature/fix/security/chore PR, который добавляет или меняет действия, необходимые оператору для установки, включения или безопасной эксплуатации административной функции, обязан обновить `docs/ADMIN_SETUP.md` **в том же PR**. Это относится, в частности, к:

- новым или изменённым `.env`-переменным и host paths;
- системным пакетам, Docker mounts/networks и host prerequisites;
- ports, firewall, DNS и TLS;
- systemd services/timers, Host Control Agent и restricted proxy;
- credentials, tokens и enrollment flow без публикации самих secrets;
- Master/direct-node onboarding, backup/restore и migrations;
- обязательным preflight, rollout, post-deploy smoke и operator verification шагам.

Если изменение не требует новой ручной настройки или operator action, `ADMIN_SETUP.md` менять не нужно, но PR body должен явно отметить: `Admin Setup: изменений не требуется`.

Feature не считается полностью документированной, если необходимый setup существует только в коде, issue, PR discussion, release notes или переписке, но отсутствует в `docs/ADMIN_SETUP.md`.

При обновлении руководства изменяется канонический текущий flow, а не добавляется исторический журнал. История версий остаётся в `CHANGELOG.md`.

## Ведение roadmap

`docs/ROADMAP.md` — living document и обязательный источник контекста для новых чатов/сессий. Его актуальная верхняя сводка служит **реестром выполненных изменений и незакрытых проверок**. Исторические даты и evidence в нижних разделах и `docs/audits/**` не переписываются.

Сохраняются **ровно четыре** статуса пунктов дорожной карты:

- `⬜ Запланировано` — работа ещё не завершена в `main`;
- `🟡 Реализовано в main` — код/документация уже слиты, но соответствующий release ещё не опубликован;
- `🟠 Опубликовано; acceptance отложен` — release опубликован, но отдельный обязательный production acceptance, targeted smoke или recovery drill ещё не завершён;
- `✅ Выполнено в vX.Y.Z` — изменение опубликовано в указанном release **и** весь обязательный acceptance scope подтверждён.

**Merge, CI, публикация, production deployment и acceptance — разные события.** Публикация не переводит `🟠` в `✅` автоматически, даже если код и CI исправны. Если публикация уже состоялась, но deployment отсутствует, это также явно указывается: не выдавай `Published` за `Deployed`.

### Фиксация результатов и обязательств

1. **Каждый значимый feature/fix/bug/security/task/docs change** (новое поведение, исправление, operator contract, acceptance finding или состояние release) должен быть прослеживаем в актуальной сводке: Issue/PR, краткий фактический результат и статус. Тривиальные внутренние правки без самостоятельного product/acceptance scope не требуют новой строки.
2. **До merge** в PR указываются связанные Issue/пункт Roadmap, выполненные проверки и оставшиеся gates. Нельзя заранее писать в Roadmap, что PR уже слит. **После merge** зафиксируй результат и ссылку на PR в Roadmap при ближайшей docs-синхронизации **до следующей работы по этому пункту или release-prep**; если нужен отдельный docs-only PR, оформи его. Не превращай документ в перечень неподтверждённых намерений.
3. **После release/deployment** обнови фактическую ступень: immutable tag/SHA (если применимо), Published, Deployed, baseline health и результаты targeted smoke отдельно. Для незавершённого scope сохраняй `🟠` и явные оставшиеся gates. Для docs-only изменения production smoke не изобретается — укажи, почему он не требуется.
4. **После каждой проверки** укажи, что именно проверено, результат, окружение и версию, дату/время с часовым поясом и проверяемый evidence (CI run, PR, job ID, audit или безопасное операторское свидетельство). Не раскрывай secrets, пользовательские идентификаторы или приватные URL. Если фактически проверена лишь часть, не отмечай весь сценарий пройденным.
5. **Незавершённые проверки не теряются:** для каждого применимого gate явно отмечай оставшуюся проверку, блокер/риск и следующее действие. Исходные FAIL и `unknown` не стираются последующим успехом другого запуска; ручная проверка не заменяет scheduled cycle, DR preflight не заменяет isolated restore.
6. **При закрытии Issue / milestone** сверь факты в GitHub, tag/release и собственные acceptance criteria. Закрывай только подтверждённый scope; новый независимый finding веди отдельно. Периодически и перед release-prep сверяй актуальную сводку со слитыми PR, открытыми Issues и опубликованными релизами; несоответствия фиксируй явно.

Результаты **отдельных проверок** можно записывать как `PASS`, `PARTIAL`, `PENDING`, `FAIL`, `BLOCKED`. Это **не новые статусы Roadmap**: `PASS` означает завершённый проверенный сценарий с evidence, `PARTIAL` — только проверенную часть, `PENDING` — ещё не выполнено, `FAIL` — проверка не прошла, `BLOCKED` — проверить пока невозможно с указанной причиной. При `PARTIAL`/`PENDING`/`FAIL`/`BLOCKED` обязательного gate пункт не может перейти в `✅`.

Минимальные поля актуальной сводки (можно оформить таблицей или соседними блоками): **Issue/PR → факт в main/release/production → что проверено и чем подтверждено → что осталось проверить → следующий шаг**. Существующую верхнюю сводку дополняй, не заводя параллельный `CURRENT_STATE.md` и не дублируя подробные audit reports.

Так новые сессии восстанавливают состояние из `docs/ROADMAP.md`, `CHANGELOG.md`, GitHub Releases и evidence, а не из переписки.

## Диагностика GitHub / Actions как внешней dependency

Если CI/PR ведёт себя аномально — workflow не появился, долго остаётся `queued`, runner не назначается, GitHub API/PR UI возвращает ошибки или release workflow не стартует после зелёного `Python checks` — сначала исключи деградацию самой платформы GitHub.

Проверь официальный GitHub Status:

~~~bash
curl -fsS https://www.githubstatus.com/api/v2/summary.json \
  | jq -r '
      .components[]
      | select(
          .name == "Actions"
          or .name == "Git Operations"
          or .name == "API Requests"
          or .name == "Pull Requests"
        )
      | "\(.name): \(.status)"
    '
~~~

И unresolved incidents:

~~~bash
curl -fsS https://www.githubstatus.com/api/v2/incidents/unresolved.json \
  | jq -r '
      if (.incidents | length) == 0 then
        "GitHub incidents: none"
      else
        .incidents[]
        | "GitHub incident: \(.name) — \(.status) — impact=\(.impact)"
      end
    '
~~~

Правила fail-closed:

- при подтверждённой деградации GitHub Actions/API/Git Operations не начинай менять repository code только потому, что workflow завис/не стартовал;
- не обходи required checks ручным merge/tag/release;
- не создавай tag/GitHub Release вручную вместо штатного release workflow;
- после восстановления GitHub повторно проверь affected workflow на том же актуальном head;
- недоступный Status API трактуется как `health unknown`: подтвердить состояние нужно через status page/UI и фактическое состояние GitHub PR/Actions, прежде чем делать вывод о repository failure.

Для обычного feature/fix PR отдельный status preflight перед каждым действием не требуется. Он обязателен перед merge release-prep PR согласно [Release workflow](RELEASES.md) и используется как первый diagnostic step при признаках проблем GitHub.

## Типовой цикл

1. Создать ветку от актуального `main`.
2. Внести изменения и проверить синтаксис Python и тесты.
3. Обновить `CHANGELOG.md` для релизных изменений.
4. Открыть запрос на слияние — Pull Request (PR).
5. Проверить изменения и результаты CI, затем выполнить слияние.
6. Для релиза подготовить и слить отдельный release-prep PR с новым `APP_VERSION` и разделом `CHANGELOG.md`.
7. После зелёного `Python checks` на `main` tag и GitHub Release создаёт `.github/workflows/release.yml`. Вручную tag/Release не создаются.
8. После публикации runtime-релиза выполняется controlled production deployment по опубликованному tag.
9. После deployment выполняется отдельная post-deploy verification; только после неё runtime-релиз считается operationally closed и можно переходить к следующей runtime-задаче.
10. После базовой post-deploy verification выполняется targeted production smoke изменённой критической области: проверяется именно новая feature/fix и её ключевые safety/postcondition свойства. Полный ручной регрессионный прогон всех функций не требуется. Если безопасный production smoke невозможен, это явно фиксируется в release notes/операционном отчёте с указанием, какими CI/regression проверками закрыт риск.

Исторические теги до `v4.8.0` восстановлены по сохранённым снимкам релизов при миграции проекта в Git.

Канонический стиль GitHub Releases, fail-closed правила и автоматизация зафиксированы в [Release workflow](RELEASES.md). Этот документ является источником процесса и для новых чатов/сессий.

## Язык документации

`README.md`, `CHANGELOG.md`, руководства в `docs/`, названия и описания релизов GitHub пишутся на русском языке. Это правило применяется и к последующим изменениям.

Названия продуктов, точные названия кнопок и разделов интерфейса, команды, пути, переменные окружения, поля API, таблицы, теги и фразы подтверждения сохраняются в исходном виде. Их можно сопровождать русским пояснением, но нельзя переводить так, чтобы инструкция перестала соответствовать приложению.

При переводе сохраняются смысл, структура, технические ограничения и исторические сведения исходного материала. Изменения поведения приложения не смешиваются с правками документации.

## Правки опубликованных описаний

Изменение title/body GitHub Release не требует пересоздания релиза или перемещения его тега. Опубликованный tag считается неизменяемым. Канонический title/body генерируются из соответствующего раздела `CHANGELOG.md` через `scripts/render-release-notes.py`.

Если release metadata оформлены неверно, исправляется CHANGELOG/renderer/automation и синхронизируется только metadata Release. Tag не force-move.

Развёртывание на VPS выполняется отдельно от слияния PR и публикации релиза.

## Закрытие runtime-релиза после публикации

Для runtime-релизов различаются три отдельных факта:

1. **Published** — tag и GitHub Release опубликованы штатным workflow;
2. **Deployed** — production VPS обновлён именно на опубликованный tag через `scripts/deploy-release.sh`;
3. **Verified** — после deployment подтверждены version/tag, container health, SQLite quick check, upstream 3x-ui connectivity и отсутствие неожиданного restart loop.

Публикация GitHub Release сама по себе не закрывает operational часть релиза.

При интерактивной работе с оператором production update проводится пошагово: агент даёт **одну команду за раз**, оператор присылает полный вывод, агент проверяет его и только после этого даёт следующую команду. Не следует отправлять оператору длинный набор state-changing и verification-команд одной простынёй.

Если очередная проверка не проходит, следующий state-changing шаг не выполняется до разбора результата.

## Развёртывание опубликованного релиза на VPS

Production разворачивается по опубликованному тегу `vX.Y.Z`, а не по произвольному состоянию `main`. Для стандартного VPS используется `scripts/deploy-release.sh`.

Обычное обновление после появления скрипта в текущем релизе:

```bash
cd /opt/3xui-bot/3xui-telegram-bot
./scripts/deploy-release.sh v4.9.2
```

Проверка текущего состояния без изменений:

```bash
./scripts/deploy-release.sh --status
```

Скрипт сам получает теги, проверяет наличие целевого тега в истории `origin/main`, сопоставляет тег с `APP_VERSION`, сохраняет `.env` и согласованную SQLite-копию, проверяет Compose и Docker-подсеть, собирает образ, пересоздаёт только сервис `bot` и после запуска проверяет `/healthz`, SQLite и TCP-доступ к upstream 3x-ui.

Скрипт намеренно не выполняет `docker compose down`, `docker system prune`, обновление 3x-ui/Xray и автоматический откат базы данных. Если существующая Docker-сеть не соответствует `BOT_DOCKER_SUBNET`, развёртывание останавливается до изменения контейнера: пересоздание сети выполняется как отдельная обслуживаемая операция.

Для намеренного понижения версии нужно явно разрешить его:

```bash
DEPLOY_ALLOW_DOWNGRADE=1 ./scripts/deploy-release.sh v4.9.1
```

### Первое внедрение deploy helper

Тег `v4.9.1` опубликован до появления `scripts/deploy-release.sh`, поэтому для первого перехода на релиз, содержащий helper, его нужно один раз запустить из актуального `origin/main`, не переключая production заранее:

```bash
cd /opt/3xui-bot/3xui-telegram-bot

GIT_SSH_COMMAND="ssh -i $HOME/.ssh/3xui_bot_deploy -o IdentitiesOnly=yes" \
  git fetch origin main --tags --prune

git show origin/main:scripts/deploy-release.sh > /tmp/3xui-bot-deploy-release.sh
chmod 700 /tmp/3xui-bot-deploy-release.sh

DEPLOY_REPO_ROOT="$PWD" /tmp/3xui-bot-deploy-release.sh v4.9.2

rm -f /tmp/3xui-bot-deploy-release.sh
```

Начиная с `v4.9.2` helper находится внутри самого релиза, поэтому следующие обновления выполняются обычной командой из репозитория.

## Язык и UX Telegram-интерфейса

Постоянный контракт языка, терминологии, навигации и пользовательских формулировок зафиксирован в [Стиле Telegram-интерфейса](UI_STYLE.md).

Для новых UI-изменений это означает:

- пользовательский и административный интерфейс по умолчанию пишется по-русски;
- точные технические названия (`3x-ui`, `Xray`, `Reality`, `fingerprint`, protocol/API identifiers и аналогичные термины) не переводятся механически;
- одна сущность или действие должны иметь последовательное display-name во всех экранах;
- новый экран должен иметь логичный parent/Back/Cancel flow;
- тексты не должны зависеть от конкретного production deployment, частного hostname, владельца или временной конфигурации;
- PR с UI-изменением проверяет соседнюю навигацию и обновляет regression tests, если меняется routing/confirmation/navigation contract.

Если появляется новое терминологическое или навигационное соглашение, оно сначала фиксируется в `docs/UI_STYLE.md`, а не распространяется по коду неявно.
## Правило оформления кнопок Telegram

Для единообразия интерфейса все inline-кнопки пользовательского и административного интерфейса должны начинаться с понятного emoji или навигационного символа. Это относится к действиям, выбору сущностей, подтверждениям, отмене, обновлению, пагинации и возврату на родительский экран.

Примеры: `🔄 Обновить`, `✅ Подтвердить`, `✖ Отмена`, `⬅ Система`, `➡ Следующая`, `💎 Тариф`, `🌍 Нода`.

Не добавляй новые кнопки с голыми подписями вроде `System`, `Назад`, `Отмена`, `Открыть` или `Xray Core`. Для статических `InlineKeyboardButton` это правило проверяется тестами CI; динамические подписи нужно проверять при code review.

