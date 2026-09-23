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

## Rollout / rollback

Для operational/release изменений укажи порядок rollout/rollback. Для остальных: `не требуется`.

## Checklist

- [ ] PR title соответствует `<type>: <краткое описание>`.
- [ ] Тип — один из: `feat`, `fix`, `security`, `docs`, `test`, `chore`, `refactor`, `release`.
- [ ] Для release-prep title строго `release: vX.Y.Z`.
- [ ] В PR нет secrets, tokens, private keys, backup/enrollment contents.
- [ ] `CHANGELOG.md` обновлён, если изменение заметно пользователю или оператору.
