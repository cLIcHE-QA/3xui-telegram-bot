# K01–K05 — короткий operator-reported production smoke (2026-10-12)

## Происхождение, environment и версия

- **Источник:** сообщение оператора **2026-10-12T19:04:12Z = 2026-10-12 22:04:12 EEST (Europe/Helsinki, UTC+03:00)** с результатами пяти ручных сценариев K01…K05. Это время **сообщения**, не независимо измеренный timestamp фактических действий. Видеозаписи, Telegram traces, приватные ID или machine-readable admin callbacks не предоставлялись; agent не подключался к production.
- **Target:** production **controlled pilot** Telegram Client Portal и Admin UI, отдельная тестовая identity вне allowlist/администраторов (K01), разрешённая клиентская identity (K02), административный UI (K03/K04), отдельная identity с ролью `Read-only` (K05). Нет расширения allowlist, нового финансового сценария или State mutation.
- **Published:** последний GitHub prerelease `v5.0.0-rc.9` опубликован **2026-10-11 11:24:04 UTC**, immutable tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`. **Deployed:** предыдущий operator-reported производственный bot `v5.0.0-rc.9` подтверждён прежними G-01/G-05 операционными read-backs, но в этом пакете не проверяли container SHA/image/build и не делали независимую VPS аттестацию. **GitHub baseline до docs checkpoint:** protected `main` `120697d3e301dda4441b901fa72c5230ce32ccd0` после [PR #565](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/565), post-merge `test` SUCCESS.
- **Не выполнялись:** deploy, рестарт, покупка/возврат Stars, изменение Stars/Portal flags, создание/отзыв VPN-доступа, резервная копия вручную, SQL writes, намеренное создание `job_failed`, ручной запуск заданий, объёмная регрессия или ранее waived live Telegram burst W-02 / DR W-01.
- **Acceptance отдельно:** опубликован/развёрнут/принят — **разные** статусы. G-06/G-07 остаются `PARTIAL`, G-10 `PENDING`, общий v5 `NOT PASS`, public launch `BLOCKED`.

## Операторские результаты (обезличено)

~~~text
K01: PASS
Access denied: YES

K02: PASS / REVIEW / FAIL    # строка вариантов осталась незаполненной
Entitlement: 🟢 активен
Provider read: 🟢 доступен
VPN access: 🟢 доступен
Expiry drift: согласованы / нет данных

K03: PASS
Attention Center opens: YES
Active incidents: 0
job_failed natural event: NOT OBSERVED

K04: PASS
Schedule: ON
Next run: SHOWN
Last run: SUCCESS

K05: PASS
Read-only view: YES
Run backup button visible: NO
~~~

## Разбор пяти коротких smoke

| ID | Ожидаемый безопасный результат | Фактические данные оператора | Scoped disposition и не доказанное |
| --- | --- | --- | --- |
| **K01 / G-07 — клиент вне pilot и admin allowlist** | `/start` не предоставляет личный кабинет постороннему | `PASS`, `Access denied: YES` | **PASS**, визуальный отказ данному неавторизованному аккаунту; не полное allowlist fuzzing/IDOR/callback авторизационное доказательство |
| **K02 / G-06 — single customer diagnostics** | Один ручной `Личный кабинет → Помощь → 🛠 Проверить подписку` даёт полезный статус без provisioning/reconcile mutation | `Entitlement=🟢 активен`, `Provider read=🟢 доступен`, `VPN access=🟢 доступен`, `Expiry drift=согласованы / нет данных` | **PASS для видимого diagnostic UI** по трём определённым статусам; **REVIEW для согласованности сроков**: единая UI-строка буквально допускает как совпадение, так и отсутствие данных. В сообщении не было однозначно выбранного `PASS` для K02: сохранена незаполненная строка `PASS / REVIEW / FAIL`; scoped disposition выведен по фактическим значениям, не по этой строке. Не доказана точная provider/local expiry equality, QR/URL provenance или no-mutation трасса, однако проверка планировалась view-only |
| **K03 / G-10 — Attention Center overview** | Экран открывается, текущий счётчик виден | `PASS`, `Attention Center opens: YES`, `Active incidents: 0`, `job_failed natural event: NOT OBSERVED` | **PASS только для пустого overview**, **G-10/#466 PENDING**: не было натурального production failure/notification/cooldown/recovery и двух проекций инцидента; `0` не PASS этих критериев |
| **K04 / G-06 — jobs schedule/history read-only** | Экран `/admin → Система → Задания` отображает расписание, следующий и последний запуск | `PASS`, `Schedule: ON`, `Next run: SHOWN`, `Last run: SUCCESS` | **PASS** UI просмотра; нельзя делать вывод о завтрашнем успешном scheduled run, полном soak, отсутствии старых ошибок или natural failure notification |
| **K05 / G-07 — Read-only role job page** | Просмотр разрешён, кнопка `▶ Запустить резервное копирование` скрыта | `PASS`, `Read-only view: YES`, `Run backup button visible: NO` | **PASS** визуальной RBAC-изоляции одного опасного действия; не тестировался crafted callback `admin:jobs:backup` или серверная проверка, не выполнялось резервное копирование |

**Итог:** **5 scoped operator-reported PASS для наблюдавшихся UI-путей** с отдельным `K02 expiry evidence REVIEW` и `G-10 natural job_failed PENDING`. Повторное выполнение этих же smoke без новой гипотезы не требуется. Ошибок оператор в этом сообщении не сообщил; отсутствие события `job_failed` — не bug и не новый результат PASS его production acceptance.

## Критерии Issues, риск, следующий шаг

- [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466) **OPEN/PENDING**: критерии natural production `job_failed` → new/reminder/recovery/cooldown и две Attention Center projections **не выполнялись**; K03 подтверждает только что пустой экран доступен, не провоцировать сбой.
- [#564](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/564) **OPEN/PENDING**, отдельная legacy UX задача без связи с K01–K05, реализация не выполнялась.
- [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) **OPEN/PENDING**: exact Master/Node GUID/mode/timestamp, offline/recovery не подтверждены этими UI smoke; предыдущие N01/N02 сохранены в своём audit.
- [#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) **OPEN/PENDING**: 14-day refund policy/expiry revoke не проверялись; никаких refund mutations.
- [#317](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/317), [#342](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/342), [#422](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/422) **CLOSED** по своим собственным earlier acceptance; K01–K05 не основание для reopen/closure.
- **G-06 PARTIAL:** bounded abuse/load/soak и job natural lifecycle не доказаны одним вызовом diagnostics + UI jobs read. **G-07 PARTIAL:** полный ownership/pre-checkout/callback/B→A IDOR не доказан одним rejected `/start` и отсутствием backup кнопки. **G-10 PENDING:** не было natural incident. **G-09 S05 PENDING:** отдельное одноразовое напоминание на 2026-10-13 21:03:16 EEST; если paid expiry естественно ещё не произошло — сохранять PENDING. W-01/W-02 ранее waived, не возобновлять.
- Следующее содержательное действие: отдельная точечная read-only проверка **непокрытого** критерия, приоритет естественных событий; **не** повторять K01–K05 или G06/W-02 burst. Финальный v5 G-11 только после отдельной сверки обязательных blockers/waivers.

## Документационный checkpoint

Обновить верх `docs/ROADMAP.md` и три канонические строки **G-06/G-07/G-10** по этому датированному operator-reported evidence. **Issue: N/A — только audit/checkpoint для существующего G-06/G-07/G-10, без нового дефекта или feature**. Требуются отдельная `docs/*` ветка, PR по шаблону, required `test`/`title`, squash merge, independent `main` read-back, комментарий/closure audit #466 и повторная сверка статусов. До реального merge/read-back **ROADMAP SYNC: PENDING**.
