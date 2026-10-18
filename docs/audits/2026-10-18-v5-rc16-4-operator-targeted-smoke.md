# v5.0.0-rc.16.4: операторская приёмка 59/60, search-status FAIL, commerce BLOCKED

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-18 21:36 UTC+03:00
- **Окружение:** production controlled pilot, operator-reported; независимого доступа к VPS/SQLite/3x-ui в этом аудите нет
- **Цель:** фиксация фактического deployment и 60 адресных проверок A1–Z5, точный defect #743 и безопасный commerce blocker при ручной выдаче; пересмотр Issues из rc.16.1/16.2/16.3
- **Версия и immutable tag/SHA:** `v5.0.0-rc.16.4` / `114de5af16adcde5e8d128cc5a55d58addc37e73`
- **Scope:** оператор сообщил `DEPLOY_OK`, запущенный container, `APP_VERSION=5.0.0-rc.16.4`, `DB=ok`, `3XUI_TCP=ok`, `Health=ok`, `RestartCount=0`, `DockerSubnet=172.19.0.0/16`, наличие pre-deploy backup (путь не публикуется); затем A1–A7, B1–B6, C1–C6, D1–D6, E1–E10, F1–F7, G1–G7, H1–H6, Z1–Z5; **M1–M8 не выполнялись**, V5-A-001…A-003 и G-11 не закрывались
- **Фактический результат:** PARTIAL — **59 PASS / 1 FAIL (C3)** из 60 targeted checks operator-reported; manual grant **BLOCKED** существующим `commerce_orders.created/awaiting_payment`, безопасный отказ #740 корректен; M1–M8 и полный v5 acceptance PENDING
- **Источник и evidence:** operator-reported сообщение `2026-10-18T18:13:09Z` (deploy/status) и `2026-10-18T18:36:23Z` (проверки и воспроизведение C3/commerce blocker); immutable [GitHub Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.16.4), [release PR #749](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/749), [release Publish workflow](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/39149899084); код [`advanced_users.py`](https://github.com/cLIcHE-QA/3xui-telegram-bot/blob/114de5af16adcde5e8d128cc5a55d58addc37e73/advanced_users.py) в search-ветке вычисляет `statuses = await _user_status_icons(users)`, но рисует literal `👤`, а list-ветка использует рассчитанный emoji
- **Ограничения и остаточные риски:** A5 и F6 отмечены PASS **только со слов оператора**, не являются независимым подтверждением backup restore или live injection; дефект C3 воспроизводится в поиске; `M1–M8`/3x-ui postcondition не получены; состояние конкретного незавершённого заказа/оплаты **не установлено**; не форсировать SQL status, не отменять/удалять заказ или повторять grant, пока read-only проверка не доказала terminal state. G-11 PARTIAL/NO-GO, public rollout BLOCKED
- **Связанные Issues:** #705, #730, #731, #740, #742, #743, #744, #745; предыдущие rc.16.1 #705 OPEN; rc.16.2 #691/#719/#721/#724 уже CLOSED/completed; rc.16.3 #734 уже CLOSED/completed, #730/#731 OPEN
- **Следующий шаг:** #743 исправить поисковый emoji, добавить тест не только на наличие helper, но и на реальный search button render; #745 отдельно доказать сохранение admin sort preference после штатного рестарта, без нового тестового restart без разрешения; #730/#705 — read-only разбор pending order/payment/entitlement и только отдельно разрешённый isolated M1–M8 после доказанного отсутствия blocker; #731 — определить первопричину старого B5; затем новые scoped checkpoints и финальный health
- **Раздельные состояния:** merged=PASS (PR #741/#746/#749/#750); published=PASS (`rc.16.4`, tag SHA как выше); deployed=operator-reported PASS (`rc.16.4`, basic A1–A7); accepted=PARTIAL (59/60, C3 FAIL, manual grant BLOCKED, M1–M8 PENDING, full v5 NOT PASS)

## Таблица всех 60 проверок

Все 59 PASS означают **operator-reported scoped PASS**. Нельзя экстраполировать один UI PASS на backend provider postcondition или на независимое production evidence; объединённые пункты требуют своих доказательств, если это прямо записано в Issue.

### A: Baseline

| ID | Итог | Operator-reported outcome |
| --- | --- | --- |
| A1 | **PASS** | Git tag / Git SHA / APP_VERSION соответствуют immutable rc.16.4 |
| A2 | **PASS** | Container running, RestartCount=0 |
| A3 | **PASS** | Health/DB/3XUI_TCP/DockerSubnet — OK |
| A4 | **PASS** | SQLite schema v15, PRAGMA quick_check и migration journal |
| A5 | **PASS** | Pre-deploy backup/deep validation/restore gate — со слов оператора; независимые artifacts не предоставлены |
| A6 | **PASS** | Portal/Stars flags, pilot allowlist и rate limits без непредусмотренных изменений |
| A7 | **PASS** | Критических логов/неожиданных provisioning или платёжных операций нет |

### B: Статусная грамматика

| ID | Итог | Operator-reported outcome |
| --- | --- | --- |
| B1 | **PASS** | Users enabled/disabled показывают 🟢/⚪ |
| B2 | **PASS** | Plans active/inactive показывают 🟢/⚪ |
| B3 | **PASS** | Inbounds и Administrators показывают 🟢/⚪ |
| B4 | **PASS** | 🟡 unknown, 🔴 error/offline, ⛔ warning различаются |
| B5 | **PASS** | enable не путается с online/expiry/blocked |
| B6 | **PASS** | Read-only/Support RBAC сохранён |

### C: Список/поиск пользователей

| ID | Итог | Operator-reported outcome |
| --- | --- | --- |
| C1 | **PASS** | Список пользователей показывает реальный enable из 3x-ui |
| C2 | **PASS** | Пагинация и Back обновляют статусы |
| C3 | **FAIL** | Поиск пользователя показывает 👤 вместо ожидаемых 🟢/⚪ — defect #743 |
| C4 | **PASS** | Один bounded clients/list на экран/поиск, без N+1/polling |
| C5 | **PASS** | Unknown/duplicate/API-error показывают 🟡 |
| C6 | **PASS** | Сохранены labels, Telegram identity, RBAC и отсутствие mutations |

### D: Master/Node навигация

| ID | Итог | Operator-reported outcome |
| --- | --- | --- |
| D1 | **PASS** | Back из Master 3x-ui к Master |
| D2 | **PASS** | Back/Cancel из Master Xray к Master |
| D3 | **PASS** | Back/Cancel к правильной direct Node |
| D4 | **PASS** | Origin сохраняется при страницах/вложенном UI |
| D5 | **PASS** | Вход из Система возвращает в Система |
| D6 | **PASS** | Error/retry origin, без update/restart/backup |

### E: RUB/Stars

| ID | Итог | Operator-reported outcome |
| --- | --- | --- |
| E1 | **PASS** | Есть сортировки RUB ↑/↓, Stars ↑/↓ и исходная |
| E2 | **PASS** | RUB integer ↑/↓ независимо от Stars |
| E3 | **PASS** | Stars integer ↑/↓ независимо от RUB |
| E4 | **PASS** | Отсутствующая цена последняя в обе стороны |
| E5 | **PASS** | Стабильный tie-breaker и limit 40 после сортировки |
| E6 | **PASS** | Нет изменений цен, сроков, visibility или платежей |
| E7 | **PASS** | Клиентские разрешённые Stars ↓ перед limit 20 |
| E8 | **PASS** | Не появляются недоступные планы |
| E9 | **PASS** | Admin preference не меняет клиентский checkout или валюту |
| E10 | **PASS** | Save preference/повторный вход/RBAC — PASS; отдельное доказательство сохранения после restart НЕ представлено |

### F: Commerce preflight

| ID | Итог | Operator-reported outcome |
| --- | --- | --- |
| F1 | **PASS** | created/awaiting_payment => понятная причина до confirm |
| F2 | **PASS** | pending/provisioning entitlement => отдельная причина |
| F3 | **PASS** | Выдача не начата, без локального/provider mutation |
| F4 | **PASS** | Чистый профиль не получает ложный blocker |
| F5 | **PASS** | unknown/in_flight — только read-only reconciliation |
| F6 | **PASS** | Fail-closed/race/stale nonce — operator-reported PASS с ограничением CI/evidence |
| F7 | **PASS** | Atomic commerce fence, отсутствие переписывания order/payment/entitlement |

### G: Бессрочный мастер

| ID | Итог | Operator-reported outcome |
| --- | --- | --- |
| G1 | **PASS** | ♾ срок сразу объясняет traffic=0/RUB=0/Stars=0/admin_only |
| G2 | **PASS** | IP=2, HWID=5 валидируются |
| G3 | **PASS** | 0/0 разрешены как unlimited; неверные значения отклоняются |
| G4 | **PASS** | Неприменимые шаги пропущены; preview корректен |
| G5 | **PASS** | Back/Cancel/stale confirmation безопасны |
| G6 | **PASS** | Legacy hwid_limit=NULL не перезаписывает provider |
| G7 | **PASS** | Manual-only, RBAC, одноразовый confirmation, hidden |

### H: Client Portal / purchase guards

| ID | Итог | Operator-reported outcome |
| --- | --- | --- |
| H1 | **PASS** | У разрешённого клиента без blocker видны активные Stars планы |
| H2 | **PASS** | При active/unknown ручной выдаче показана причина запрета покупки |
| H3 | **PASS** | All/groups/admin_only и include/exclude/старые callbacks безопасны |
| H4 | **PASS** | Без Stars/inactive/indefinite/invalid group отсутствует checkout |
| H5 | **PASS** | Terms/allowlist/Stars/backend payment guards сохранены |
| H6 | **PASS** | Read-only Stars и manual журналы; без создания оплат |

### Z: Финальный health

| ID | Итог | Operator-reported outcome |
| --- | --- | --- |
| Z1 | **PASS** | После smoke tag/SHA, APP_VERSION, container/restart/subnet OK |
| Z2 | **PASS** | После smoke Health/DB/3x-ui OK |
| Z3 | **PASS** | DB quick_check/journal, нет необъяснимого mismatch |
| Z4 | **PASS** | Логи, provisioning и журналы без новых критических отклонений |
| Z5 | **PASS** | Результаты отмечены, G-11 не повышен автоматически |

**Сверка:** изменять production state и финансовые журналы ради воспроизведения этих результатов не требовалось; все значения сохранены как operator-reported evidence, а не как независимые проверки.

## Подтверждённые findings и разграничение

1. **#743 / C3 FAIL:** `admin_users_search_message` (`advanced_users.py`) уже запрашивает `statuses`, но кнопка содержит буквальный `👤` вместо `statuses.get(user.email, '🟡')`; C1/C2/C4–C6 PASS не компенсируют C3. Issue OPEN, defect относится к существующему scope — отдельный дублирующий Issue не создаётся.
2. **#740 / F1–F7 PASS:** сообщение «Незавершённый заказ: сначала проверьте его статус в журнале платежей. Ручная выдача не начата» — ожидаемый безопасный preflight для `created/awaiting_payment`, а не подтверждение выполненного ручного grant. Если `entitlements.pending/provisioning`, показывается другой blocker. Atomic guard/unknown/no-replay сохраняются. Исправление UI может быть принято отдельно от разрешения конкретной задолженной операции.
3. **#730 / G1–G7 PASS, M1–M8 PENDING:** мастер и параметры bounded indefinite поддержаны по отчёту оператора, но реальные provider limits, one-shot grant и reconciliation ещё не подтверждены. Issue нельзя закрыть только по UI.
4. **#745 / E1–E10 PASS (scoped):** persistence после повторного входа входит в E10; отдельный **restart persistence** прямо требуется Issue и не доказан этим пакетом, поэтому Issue остаётся OPEN.
5. **#731/#705 / H1–H6 PASS (scoped):** клиентская видимость/защитные правила по сообщению оператора проверены, но исходная причина исторического B5 не доказана, а end-to-end manual grant/payment/entitlement и M1–M8 PENDING; не закрывать.
6. **Исторические rc.16.1/16.2/16.3:** #691/#719/#721/#724/#734 уже CLOSED/completed по прежним scoped operator-reported evidence. Не открывать повторно и не засчитывать им full v5 acceptance.
7. **Результат по issues rc.16.4:** по scoped closure-критериям подходят #740 (исправлен текст/защита), #742 (единые статусы), #744 (origin navigation). #743, #745, #730, #731, #705 остаются OPEN по указанным отдельным критериям.

## Безопасный read-only порядок разбора ручного blocker

В private /admin откройте журнал Stars/ручных платежей для этой allowlisted pilot identity и установите **точный** order со status `created/awaiting_payment`; read-only сопоставьте запись платежа/провайдера, `entitlements.pending/provisioning` и `manual_entitlements.in_flight/unknown/active`. `db.py:manual_grant_commerce_block_reason` сначала ищет `commerce_orders.status IN ('created','awaiting_payment')`, затем pending entitlement — вывод подсказки об order не означает `payment=paid`. При unknown остановитесь до reconciled terminal-state: никаких произвольных SQL `UPDATE/DELETE`, второго invoice/grant, blind replay или ручной подмены статуса. Новый confirm может быть **отдельной операцией** только после доказанной безопасной сверки; provider mutation и full M1–M8 согласуются отдельно.

## Дополнительный операторский checkpoint — 2026-10-18 21:59 EEST

Read-only SQLite подтвердил для пользователя с блокирующим алертом **один `commerce_orders.awaiting_payment` без `commerce_payments`**, pending/provisioning `entitlements` = 0; приватный Telegram ID в документацию не переносится. F1–F7 и Z1–Z5 остаются scoped operator-reported PASS; #740 CLOSED/completed, а будущий read-only интерфейс для order без payment уже учтён в [#470](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/470) (OPEN, target rc.17). Прямого изменения/отмены заказа не было. Оператор также сообщил **M1–M8 8/8 PASS** по manual grant и provider read-back, без независимого VPS evidence. **Не подтверждено, относятся ли M1–M8 к этому же пользователю с активным pending order или к отдельному чистому pilot-сценарию**; нельзя заявлять обход atomic fence или закрыть #730 без уточнения provenance. Full G-11 PARTIAL/NO-GO, public rollout BLOCKED.

## Closure addendum #745 — 2026-10-19 00:35 EEST

- **Окружение/источник:** deployed `v5.0.0-rc.16.4`, immutable SHA `114de5af16adcde5e8d128cc5a55d58addc37e73`, Telegram operator-reported после штатного Docker Compose restart; independent VPS read-back отсутствует.
- **До рестарта:** выбран `Stars ↓`; E1–E10 ранее operator-reported PASS.
- **После рестарта:** `#745: PASS`, выбранная сортировка сохранилась. `./scripts/deploy-release.sh --status`: Git tag и Git SHA соответствуют релизу, Container running, RestartCount=0, Bot version `5.0.0-rc.16.4`, Health/DB/3x-ui connectivity = ok, Docker subnet `172.19.0.0/16`.
- **Итог:** собственный scoped acceptance Issue [#745](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/745) **PASS; CLOSED/completed**. Общий 59/60 targeted A–Z не меняется: C3/#743 FAIL, #730 causal correlation PENDING, G-11 PARTIAL/NO-GO, public rollout BLOCKED; прошлые PENDING записи выше — исторические.
