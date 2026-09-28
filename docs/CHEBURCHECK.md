# Cheburcheck integration

Этот документ описывает optional read-only интеграцию Cheburcheck в Telegram Admin Control Plane.

## Upstream

- repository: `LowderPlay/cheburcheck`
- reviewed revision: `0bbd2be8ca4b8f9ded1407597654314fc2a900c6`
- license: BSD 3-Clause
- upstream API used by bot: `GET /api/v1/check?target=...` и bounded `GET /api/v1/probe/{id}` для regional probe summary

Авторские уведомления и полный license notice находятся в [../THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

## UI

Канонический путь:

~~~text
/admin
└─ 📈 Мониторинг
   └─ 🔎 Проверка блокировок
~~~

Стартовый экран автоматически предлагает безопасные public targets, которые уже известны control plane:

- Master: hostname/IP, извлечённый из `PANEL_URL`;
- direct Nodes: `NodeInfo.address`;
- enabled Hosts: `HostRecord.hostname`.

Дубликаты удаляются, private/loopback/link-local и локальные service names не предлагаются. Для сохранённых URL в Cheburcheck передаётся только hostname/IP: scheme, port, path, query, credentials и token-like части не используются.

Дополнительно карточки Master и direct node содержат read-only shortcut `🔎 Проверить блокировку`. Callback хранит только stable identity (`master` или `node_id`), а актуальный адрес перечитывается в момент проверки; адрес не кодируется в callback data.

Контекст входа сохраняется до конца flow: Monitoring/discovered/manual остаётся внутри `Мониторинг → Проверка блокировок`, shortcut из Master возвращается только в Master, shortcut из direct Node — только в ту же Node. `Проверить ещё`, Cancel, retry и error-state не создают cross-context jump.

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

Воспроизводимая host-side установка, включая pinned checkout, PostgreSQL 18, internal-only Docker networks, secrets, health checks, bot `.env`, rollback и production acceptance: [Cheburcheck deployment](CHEBURCHECK_DEPLOY.md).

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
- ограничивает `/api/v1/check` response body 1 MiB;
- regional SSE `/api/v1/probe/{id}` использует только `id`, полученный из успешного check response, total/connect/read timeouts 12/3/10 s и отдельный hard limit 256 KiB;
- subnet/ASN не запускают regional probe, потому что reviewed upstream endpoint их не принимает;
- для domain/public-IP static result с валидным `geo.asn` bot может выполнить один дополнительный bounded read-only `GET /api/v1/check?target=AS...` и использовать только counts `asn_info.prefixes` / `blocked_prefixes`; основной verdict не зависит от успеха этого enrichment;
- ошибка/недоступность ASN enrichment или regional probe не превращает уже успешный static check в ошибку;
- regional SSE `started.online_probes` сохраняется в summary: `0` отображается как `⚪ нет активных региональных сканеров`, online probes без ответов — как отдельное `🟡 нет ответов`, transport/upstream failure — как `🟡 региональная проверка недоступна`, а subnet/ASN сохраняют `—` как неприменимый probe;
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
- `cdn_providers`;
- `geo`;
- optional `rkn_domain`, `asn_info`, `whitelist`, `subnet_size`;
- `complaints`.

Для domain/public-IP check response `id` может использоваться только для последующего `GET /api/v1/probe/{id}`. Regional SSE results агрегируются в три operator buckets: `🟢` доступно, `🔴` блокирующий verdict/CDN block, `🟡` whitelist/uncertain. `started.online_probes` используется только для честного operator status и не превращается в выдуманные региональные результаты. В основной карточке не выводятся individual probe/region payloads.

Reviewed upstream заполняет `asn_info` только когда target сам является ASN. Поэтому для domain/public-IP строка `ASN: blocked / total` получается отдельным read-only check по уже возвращённому `geo.asn`; если этот follow-up не удался, основной static result всё равно показывается. Пустой `cdn_providers` является фактическим результатом «CDN не найден» и отображается как `🟢 не найден`, а не как неизвестное значение.

Канонический compact result:

~~~text
🔎 Проверка блокировок

Цель: example.org
Результат: 🟢 блокировка не обнаружена
Сеть: Example ISP · AS12345 · Москва

📋 Списки
РКН: 🟢 не найден
CDN: Cloudflare · 3 сети
Исключение CDN: —
ASN: 2 / 184 подсетей в списках

🌍 Регионы: 11 ответов · 🟢 8 · 🔴 2 · 🟡 1

Источник: Cheburcheck.
~~~

Bot показывает только bounded operational summary и не копирует полный raw payload в UI, audit или logs.

Если self-hosted runtime не имеет зарегистрированных/online Cheburcheck Probe reporters, static list/ASN checks продолжают работать, но Telegram явно показывает `🌍 Регионы: ⚪ нет активных региональных сканеров`. Bot hotfix не создаёт собственные regional probes и не эмулирует их данными static API.

## v4.23.1 production note

Production smoke `v4.23.0` выявил штатный ASN response размером около 382 KiB, который превышал исходный hard limit 256 KiB. `v4.23.1` поднимает только bounded response-body limit до 1 MiB; concurrency, redirects policy и timeouts не ослабляются. Bot по-прежнему строит bounded operational summary и не выводит raw JSON.

## Production acceptance

После публикации release:

1. открыть `Мониторинг → Проверка блокировок` и убедиться, что доступные Master/direct Nodes/enabled Hosts появляются как обнаруженные цели без URL path/credentials;
2. проверить shortcut `🔎 Проверить блокировку` из карточки Master и одной direct node;
3. проверить domain, public IP и ASN с предсказуемым fixture/known result;
4. убедиться, что validation отклоняет URL/private IP;
5. проверить rate-limit presentation;
6. временно сделать Cheburcheck endpoint недоступным и подтвердить graceful error только внутри этого screen;
7. после восстановления повторить запрос;
8. проверить base bot health/DB/3x-ui status;
9. убедиться, что internal URL/credentials не появились в UI/audit/logs.
