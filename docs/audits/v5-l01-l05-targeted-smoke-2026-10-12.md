# L01–L05 — короткий операторский production smoke (2026-10-12)

## Источник, baseline и ограничения

- **Источник:** сообщение оператора **2026-10-12 19:36:16 UTC = 2026-10-12 22:36:16 EEST (Europe/Helsinki, UTC+03:00)**. Это время сообщения, а не независимое измеренное время запуска проверок. Указаны пять ручных `PASS` и конкретные `YES/NO`, без screenshots, raw logs, Telegram ID, email, GUID, provider payload или подписочных секретов. Agent не подключался к VPS/Telegram/3x-ui для независимого production read-back.
- **Environment:** действующий controlled pilot Telegram bot, существующие тестовые identities вне allowlist и в allowlist, один текущий клиент и его Master 3x-ui, Read-only Admin, экран синхронизации Master/Node. **Не выполнялись** Stars payment/refund, QR отправка третьему лицу, client creation, runtime mutation, expiry edit, flag toggle, manual backup, Node reboot/outage, SQL write, deploy/restart, нагрузка и регрессия.
- **Published:** immutable GitHub prerelease `v5.0.0-rc.9` tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`, published 2026-10-11 11:24:04 UTC. **Deployed:** та же версия только по предыдущим операторским attestations (G-01/G-05); этот пакет не собирал новый container-image SHA/Build ID, versions Master/Node не указаны числом. **GitHub baseline:** protected `main` SHA `54460f377747020586cf49569412830f7544b044` после docs-only [PR #566](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/566), postmerge CI `test` SUCCESS. **Accepted:** общий v5 `NOT PASS`, G-02/G-03/G-06/G-07 `PARTIAL`, public rollout `BLOCKED`.
- Ранее K02 диалог диагностики показывал фразу `согласованы / нет данных`: код `client_access.py` использует её при `expiry_drift=False`, не различая наличие нужных данных и их отсутствие. Текущий L05 **вручную** сравнивает видимый срок одного клиента с Master и тем самым добавляет **отдельный** scoped evidence, а не меняет смысл исторического K02.

## Обезличенный stdout оператора

~~~text
L01: PASS
/subscription denied: YES
/paysupport denied: YES

L02: PASS
QR shown: YES

L03: PASS
Flags visible: YES
Toggle buttons visible: NO

L04: PASS
Sync mode all: YES
Master version shown: YES
Node version shown: YES

L05: PASS
Profile expiry shown: YES
Matches Master expiry: YES
~~~

## Scoped results

| ID | Что проверено | Факт и disposition | Что не доказано |
| --- | --- | --- | --- |
| **L01 / G-07** | Не включённый в allowlist и Admin identity вызывает `/subscription` и `/paysupport` | **PASS**, denied **YES/YES**. Оба пользовательских маршрута fail-closed в ручном Telegram UI. | Не проверены все старые или forged callbacks, чужие order/pre-checkout/URL/QR и другие identity; K01 `/start` отдельно уже проверялся и не повторялся. |
| **L02 / G-03** | Существующий разрешённый тестовый клиент открывает `Помощь → Как подключиться → QR подписки` | **PASS**, `QR shown=YES`; существующий QR виден в UI, без новой покупки/провижининга. | Не проверен QR content, сканирование, VPN import, cryptographic Stars-event→URL linkage, Node-side delivery. QR/URL в GitHub не выкладывать. |
| **L03 / G-07** | Role `Read-only` открывает Client Portal/Stars settings | **PASS**, flags visible **YES**, mutation/toggle buttons visible **NO**. | Только видимость кнопок для роли, не crafted `admin:settings:client:*:run` callback или полная server-side RBAC трасса. |
| **L04 / G-02 и #487** | На существующих Master/Node read-only проверить точный sync mode и наличие версий | **PASS**, `Sync mode all=YES`, `Master version shown=YES`, `Node version shown=YES`. Уточняет прежнее N01 `mode=YES` до фактического operator-reported `all`. | Не сообщены числовые версии, GUID, timestamp last successful sync или immutable inbound IDs; не проверены offline→online recovery, propagation после изменения срока/квоты, no-blind-replay. **#487 OPEN.** |
| **L05 / G-06 (expiry clarity), G-03** | У существующего клиента профиль в Telegram показывает срок, и он сравнен с Master 3x-ui | **PASS**, `Profile expiry shown=YES`, `Matches Master expiry=YES`. Отдельный ручной scoped cross-UI expiry equality для одного клиента; уменьшает неопределённость K02. | Нет timestamp с точностью до секунды, независимого API comparison, доказательства всех entitlements/refunds, provenance и lifetime reconciliation; K02 текст `согласованы / нет данных` остаётся неоднозначным для *других* клиентов. |

**Итог:** **5/5 scoped operator-reported UI PASS**, не полная приёмка G-02/G-03/G-06/G-07 и не доказательство end-to-end provider/recovery. Нет новых defects/failures, не закрывать issue только из-за PASS этих маршрутов. Никаких production state changes оператор не сообщил.

## Issue audit и следующий шаг

- **[#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) — OPEN / PARTIAL:** критерий версии/mode визуально частично подтверждён L04 (mode all, версии отображаются); собственные критерии требуют устойчивые Master/Node идентификаторы, точные версии, node-side evidence о конкретном inbound assignment и **offline** проверку сбоя/возврата, изменения срока/квоты/revoke, исключение blind replay. L04 не выполнит их автоматически. После L04 не провоцировать outage ради smoke.
- **[#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466) — OPEN/PENDING:** натуральный production `job_failed` и двухпроекционный Attention Center не возникали в L01–L05. Искусственно не создавать.
- **[#433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) — OPEN/PENDING:** новая 14-day refund/revoke policy не внедрена в rc.9; текущий QR/sync/expiry smoke не проверял refund postcondition.
- **[#564](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/564) — OPEN/PENDING:** UI-скрытие legacy `/create`/`/inbounds` не реализовывали; текущий L01–L05 его не тестирует.
- **#317, #342, #422** — `CLOSED` по ранее доказанному собственному scope; не reopen из-за этого пакета.
- **S05/G-09:** напоминание на 2026-10-13 21:03:16 EEST; естественное paid expiry **PENDING/NOT TESTED**, не изменять expiry вручную. G-10 `PENDING`; G-11 report `PENDING`, WAIVED W-01/W-02 не возобновлять.

## Checkpoint

Требуются audit + верх Roadmap + канонические строки G-02/G-03/G-06/G-07, docs-only PR, required CI `test`/`title`, squash merge, независимый `main` read-back, #487 Issue comment/closure audit и проверка статусов остальных tracked Issues. **Issue: N/A — только дата и фиксация фактически выполненного существующего production smoke, без нового самостоятельного bug/feature scope.** До merge и read-back **ROADMAP SYNC PENDING**.
