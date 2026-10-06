# Публикация GitHub Releases

Этот документ — постоянный контракт проекта для подготовки tag и GitHub Release.

Его нужно использовать в новых чатах/сессиях и при ручной работе вместо предположений о том, какие GitHub write-actions доступны конкретному клиенту.

## Источник правды

Для релиза `vX.Y.Z` используются три связанных источника:

1. `version.py` — точная версия приложения: `APP_VERSION = "X.Y.Z"`;
2. `CHANGELOG.md` — канонический заголовок и список изменений;
3. merge commit release-prep PR — commit, на который должен указывать tag.

Раздел CHANGELOG обязан иметь вид:

~~~markdown
## vX.Y.Z — Краткое название релиза
- Первое существенное изменение.
- Второе существенное изменение.
- Ограничения/совместимость, если они важны.
~~~

Заголовок и bullets этого раздела являются источником GitHub Release notes. Не веди отдельную вручную написанную версию release notes, которая может разойтись с CHANGELOG.

## Канонический стиль GitHub Release

Название:

~~~text
vX.Y.Z — Краткое название релиза
~~~

Body:

````markdown
## vX.Y.Z — Краткое название релиза

- Те же bullets, что в CHANGELOG.md.
- Без маркетингового пересказа и без скрытия ограничений.

Коммит релиза: <40-char SHA>

Production deployment:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
./scripts/deploy-release.sh vX.Y.Z
./scripts/deploy-release.sh --status
~~~

Публикация GitHub Release не выполняет production deployment автоматически.
````

Технические имена, команды, API paths, переменные окружения и названия кнопок сохраняются в исходном виде. Остальной текст пишется на русском языке.

Release не должен иметь пустой `name` или пустой `body`.

## Стандартный release flow

Feature/fix изменения сначала сливаются в `main`.

Затем создаётся отдельный release-prep PR, в котором:

1. `APP_VERSION` меняется на новую версию;
2. новый раздел добавляется в верхнюю часть `CHANGELOG.md`;
3. README обновляется, если новая версия меняет пользовательский/операционный flow;
4. version-specific tests обновляются до новой версии;
5. runtime-функциональность не добавляется без отдельной причины.

### GitHub platform health gate

Перед merge release-prep PR в `main` обязательно проверь доступность GitHub как внешней dependency. Проверка выполняется **после зелёного PR CI и непосредственно перед merge**, потому что после merge release flow зависит от push-triggered `Python checks` и последующего `Publish release`.

Критичные для этого проекта компоненты GitHub Status:

- `Actions`;
- `Git Operations`;
- `API Requests`;
- `Pull Requests`.

Официальный preflight:

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

Нормальный результат для release path — все четыре компонента имеют status `operational`.

Дополнительно проверь unresolved incidents:

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

Если любой критичный компонент имеет `degraded_performance`, `partial_outage` или `major_outage`, либо GitHub Actions/API явно не отвечает штатно:

- release-prep PR в `main` не сливается до восстановления GitHub;
- required CI не обходится ручным запуском локальных checks «вместо» GitHub Actions;
- tag и GitHub Release вручную не создаются;
- timeout/queued/no-run не трактуется автоматически как дефект repository code;
- incident фиксируется как внешняя dependency degradation, после восстановления affected workflow запускается/перепроверяется штатным GitHub flow.

Если Status API недоступен, это означает `health unknown`, а не доказательство `operational`. Перед release merge нужно подтвердить GitHub health через status page/UI и фактическое состояние PR/Actions.

После зелёного CI release-prep PR сливается в `main`.

Дальше tag и GitHub Release вручную не создаются.

Workflow `.github/workflows/release.yml` запускается только после успешного `Python checks` на `main` и:

1. читает текущий `APP_VERSION`;
2. находит commit в истории `version.py`, где эта версия была введена;
3. проверяет, что commit входит в проверенный `main`;
4. генерирует title/body через `scripts/render-release-notes.py`;
5. создаёт tag `vX.Y.Z`, если его ещё нет;
6. если tag уже существует, проверяет его SHA и никогда не перемещает tag;
7. создаёт или синхронизирует GitHub Release с каноническим title/body.

Такой алгоритм важен: если после release-prep в `main` попал documentation/chore commit, tag всё равно ставится на commit, где был введён текущий `APP_VERSION`, а не на более поздний произвольный HEAD.

Текст commit subject и GitHub suffix вида `(#N)` на определение release commit не влияют: automation опирается на историю `version.py` и `APP_VERSION`, а не на формулировку commit message.

## Fail-closed правила

Workflow должен остановиться, а не угадывать, если:

- `APP_VERSION` не имеет формат `X.Y.Z`;
- в CHANGELOG нет ровно одного заголовка `## vX.Y.Z — ...`;
- release section пустой или не содержит bullets;
- невозможно однозначно найти release commit;
- существующий tag указывает не на ожидаемый release commit;
- release commit не является предком проверенного main commit.

Опубликованный tag считается неизменяемым. Его нельзя force-move для исправления release notes.

## Исправление release notes

Если tag правильный, но title/body GitHub Release оформлены неверно, tag не пересоздаётся и не перемещается.

Нужно исправить CHANGELOG/renderer/automation и синхронизировать только metadata GitHub Release.

Исторический `v4.10.1` был один раз опубликован вручную с пустыми `name` и `body`. Release workflow содержит идемпотентную миграцию: если metadata `v4.10.1` всё ещё пустые, он заполняет их из CHANGELOG, не меняя tag.

## Production

Публикация GitHub Release, production deployment и post-deploy verification — три разные стадии.

Release workflow никогда не подключается к VPS и не запускает deploy.

После опубликованного runtime-release production обновляется отдельно через `scripts/deploy-release.sh`. После успешного deploy обязательно выполняется отдельная проверка `--status` и анализ её результата.

Минимальный acceptance для operational closure:

- production checkout/container соответствует опубликованному tag/version;
- container запущен без неожиданного restart loop;
- `/healthz` возвращает `ok`;
- SQLite `PRAGMA quick_check` проходит;
- TCP-доступ к upstream 3x-ui проходит;
- Docker subnet соответствует ожидаемому;
- deployment helper завершил обновление без uncertain/partial состояния.

После этих базовых проверок обязателен **targeted production smoke** именно изменённой критической области релиза. Он должен:

- проверять новую feature/fix или её ключевой runtime-path на production;
- по возможности подтверждать safety-инварианты и postcondition, ради которых выпускался релиз;
- не превращаться в полный ручной regression suite всего бота;
- не создавать искусственно опасные mutations только ради теста: используются read-only/контролируемые диагностические сценарии, а если безопасного production smoke нет — причина фиксируется явно и опирается на CI/regression evidence;
- завершаться повторным базовым health/status-check, чтобы убедиться, что smoke не оставил production в деградированном состоянии.

Runtime-релиз считается operationally closed только после успешных базовых проверок и такого targeted smoke (либо документированного исключения, когда production smoke небезопасен/неприменим).

В интерактивной сессии команды deployment/verification выдаются оператору по одной: команда → полный вывод → проверка → следующая команда. Это уменьшает риск продолжить deployment после уже возникшей ошибки и сохраняет понятный audit trail диалога.

После опубликованного release обычная последовательность начинается так:

~~~bash
cd /opt/3xui-bot/3xui-telegram-bot
~~~

Дальнейшая команда выдаётся только после проверки результата предыдущего шага.


## Обязательная GitHub-side защита release path

Repository-side workflow checks не заменяют GitHub branch/tag protection. Для закрытия audit finding A-007/#240 GitHub должен фактически блокировать обход release path на уровне repository settings.

Минимальный обязательный baseline:

- `main` защищён от direct push;
- изменения `main` проходят только через Pull Request;
- required status checks включают `Python checks / test` и `PR conventions / title`;
- запрещены force push и удаление `main`;
- разрешён только canonical `Squash and merge` для обычных изменений;
- опубликованные `v*` refs/tags защищены от перемещения и удаления;
- release workflow имеет `contents: write` только в отдельном publish job после read-only provenance validation.

После настройки repository settings acceptance проверяется фактической попыткой обхода: direct push в `main` и изменение опубликованного `v*` ref должны отклоняться GitHub. До этой проверки A-007 не считается закрытым.


## Для новых чатов/сессий

Не полагайся на память о том, какие connector actions были доступны раньше.

Перед публикацией нового release сначала проверь:

- `docs/RELEASES.md`;
- `docs/GIT_WORKFLOW.md`;
- `.github/workflows/release.yml`;
- актуальный верхний раздел `CHANGELOG.md`.

Нормальный путь: подготовить и merge release-prep PR. Tag и GitHub Release после этого публикует GitHub Actions.
