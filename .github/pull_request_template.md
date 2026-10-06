## Что изменено

Кратко опиши результат изменения.

## Зачем

Почему изменение нужно и какую проблему/цель закрывает.

## Проверки

- [ ] CI зелёный.
- [ ] Добавлены/обновлены тесты, если изменилось поведение.
- [ ] Выполнен manual smoke-test, если он нужен.

## Совместимость и security

Опиши migration/backward-compatibility/security последствия или явно укажи, что их нет.

## Documentation impact

Проверь `docs/LIVING_DOCS.md` и `docs/live-docs.json`.

- [ ] Затронутые living docs обновлены.
- [ ] Если trigger требует review, но обновление не нужно, добавлен точный waiver из contract.

Примеры waiver: `Admin Setup: изменений не требуется`, `Living Docs: release-process — изменений не требуется`.

## Rollout / rollback

Для operational/release изменений укажи порядок rollout/rollback. Для остальных: `не требуется`.

## Checklist

- [ ] PR title соответствует `<type>: <краткое описание>`.
- [ ] Тип — один из: `feat`, `fix`, `security`, `docs`, `test`, `chore`, `refactor`, `release`.
- [ ] Для release-prep title строго `release: vX.Y.Z`.
- [ ] В PR нет secrets, tokens, private keys, backup/enrollment contents.
- [ ] `CHANGELOG.md` обновлён, если изменение заметно пользователю или оператору.
- [ ] Living Docs impact проверен по `docs/LIVING_DOCS.md`.
