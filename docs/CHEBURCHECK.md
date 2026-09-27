# Cheburcheck integration

Этот документ описывает optional read-only интеграцию Cheburcheck в Telegram Admin Control Plane.

## Upstream

- repository: `LowderPlay/cheburcheck`
- reviewed revision: `0bbd2be8ca4b8f9ded1407597654314fc2a900c6`
- license: BSD 3-Clause
- upstream API used by bot: `GET /api/v1/check?target=...`

Авторские уведомления и полный license notice находятся в [../THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

## UI

Канонический путь:

~~~text
/admin
└─ 📈 Мониторинг
   └─ 🔎 Проверка блокировок
~~~

Инструмент доступен роли Read-only и выше. Он не меняет VPN state, не выполняет provisioning и не вызывает 3x-ui mutations.

Поддерживаемые цели:

- domain;
- public IPv4 / IPv6;
- public IPv4 / IPv6 subnet;
- ASN в форме `AS12345`.

Произвольные URL, private/loopback/link-local IP и oversized subnet input не принимаются.

## Configuration

По умолчанию функция выключена:

~~~dotenv
CHEBURCHECK_URL=
CHEBURCHECK_VERIFY_TLS=true
~~~

Предпочтительный production path — отдельный pinned self-hosted Cheburcheck deployment во внутренней сети. Бот не запускает и не обновляет upstream service автоматически: third-party runtime остаётся отдельной operational boundary.

В reviewed upstream revision официальный compose stack содержит отдельные `website`, frontend/nginx и MQTT components; backend `website` слушает port 8000 и требует собственный `DATABASE_URL` и связанные upstream settings. Развёртывание этого stack выполняется по документации конкретной pinned revision Cheburcheck, а не копируется в scripts этого repository.

Пример внутреннего fixed endpoint:

~~~dotenv
CHEBURCHECK_URL=http://cheburcheck:8000
CHEBURCHECK_VERIFY_TLS=true
~~~

Plain HTTP допустим только для private/local address либо внутреннего service name. Для remote endpoint используется verified HTTPS; `CHEBURCHECK_VERIFY_TLS=false` для HTTPS запрещён.

Internal URL не показывается в Telegram UI.

## Network safety

Bot client:

- обращается только к configured fixed base URL;
- всегда добавляет фиксированный path `/api/v1/check`;
- передаёт user input только как query parameter `target`;
- не принимает и не проксирует произвольные HTTP URL;
- не следует redirects;
- использует connect timeout 3 s, read timeout 7 s, total timeout 10 s;
- ограничивает response body 256 KiB;
- ограничивает concurrent requests;
- имеет per-admin cooldown;
- различает rate limit, rejected/not-found target, unavailable service и malformed response.

Cheburcheck optional: пустая конфигурация или runtime недоступность сервиса не должны ломать startup бота, 3x-ui control plane, provisioning или остальные разделы `/admin`.

## Response contract

Reviewed upstream response содержит как минимум:

- `target`;
- `target_type`;
- `blocked`;
- `ips`;
- `reverse_lookup`;
- `blocked_subnets`;
- `geo`;
- optional `rkn_domain`, `asn_info`, `whitelist`, `subnet_size`;
- `complaints`.

Bot показывает bounded operational summary и не копирует полный raw payload в UI, audit или logs.

## Production acceptance

После публикации release:

1. открыть `Мониторинг → Проверка блокировок`;
2. проверить domain, public IP и ASN с предсказуемым fixture/known result;
3. убедиться, что validation отклоняет URL/private IP;
4. проверить rate-limit presentation;
5. временно сделать Cheburcheck endpoint недоступным и подтвердить graceful error только внутри этого screen;
6. после восстановления повторить запрос;
7. проверить base bot health/DB/3x-ui status;
8. убедиться, что internal URL/credentials не появились в UI/audit/logs.
