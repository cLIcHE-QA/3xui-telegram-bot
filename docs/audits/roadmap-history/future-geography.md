### Отложенные инфраструктурные улучшения

#### Географические metadata direct nodes

**Статус: ⬜ Запланировано. Не является блокером `v4.20.4` или обязательным условием перехода к `v5.0.0`.**

После стабилизации единого node display contract допускается добавить optional country metadata к direct nodes без привязки runtime logic к имени ноды.

Целевой контракт:

- стабильная identity остаётся `node_id`;
- `name` остаётся произвольным изменяемым display name;
- optional `country_code` хранится отдельно в формате ISO 3166-1 alpha-2, например `DE`, `FI`, `NL`;
- флаг Telegram UI вычисляется из `country_code`, а не угадывается по `name`;
- пример: `node_id=7`, `name=Frankfurt-1`, `country_code=DE` → `🇩🇪 Frankfurt-1`;
- legacy nodes без `country_code` продолжают работать; текущий name-based formatter может использоваться как presentation fallback;
- изменение `name` или `country_code` не меняет Direct Admin/Host Control bindings, credentials, backup identity и callback identity;
- onboarding/import flows получают country metadata только как отдельное optional поле с validation; миграция не должна требовать destructive schema rewrite.

До реализации этого пункта runtime и документация не должны вводить специальных условий для конкретной страны или production-ноды.

