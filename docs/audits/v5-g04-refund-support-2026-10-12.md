# G-04 — Stars refund / Support: операторский read-only результат 2026-10-12

## Дата, release и границы evidence

- **Время исполнения:** `G04_UTC=2026-10-12T15:32:16.295596+00:00` = **2026-10-12 18:32:16.295596 Europe/Helsinki (EEST, UTC+03)**. Результаты из терминала и отдельное подтверждение G04-5 `PASS` присланы оператором 2026-10-12 15:32:56 UTC. Прямого SSH-доступа у агента не было: **operator-supplied stdout и manual UI report**, не независимый VPS read-back или Telegram trace.
- **Окружение:** production Master VPS, существующие операции Telegram Stars внутри ограниченного pilot allowlist (только агрегаты, без приватных идентификаторов). Проверки G04-1…4: SQLite `file:/app/data/bot.sqlite3?mode=ro`, `PRAGMA query_only=ON`; G04-5: уже существующий клиентский интерфейс `🆘 Помощь → 💳 Поддержка по оплате` на разрешённом аккаунте.
- **GitHub baseline перед этим docs PR:** `main` `d88e1ddc5733cbe6c7b0850ee880e8d0ce95b287`, [PR #555](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/555) merged, [post-merge Python checks 38270706187](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/38270706187) **PASS**. **Published** immutable `v5.0.0-rc.9`, tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`. **Deployed** этот RC подтверждён операторским G-01 host/container read-back от 2026-10-12 17:36 EEST; G-04 identity повторно **не** считывал, независимой image/VPS attest нет. **Accepted** общий v5 **NOT PASS**.
- **Нет mutations:** не запускались новый refund/Stars purchase, manual provider retry, корректировка entitlement, отключение/удаление VPN, change flags, restart/deploy или правка БД. Это targeted examination **существующего** исторического refund scope.

## Операторский вывод

```text
G04_UTC= 2026-10-12T15:32:16.295596+00:00
G04-1 REFUND_POSTCONDITION: PASS success= 2 mismatch= 0
G04-2 REFUND_UNCERTAINTY: PASS unknown_or_inflight= 0 failed= 0
G04-3 REFUND_IDEMPOTENCY_JOURNAL: PASS duplicate_payment_operations= 0
G04-4 REFUNDED_ENTITLEMENT: REVIEW sample= 2 active_after_refund= 2 missing_entitlement= 0
G04: READ_ONLY_COMPLETE
G04-5: PASS
```

## Результат каждого subcheck: ожидание ↔ фактический outcome

| ID | Что проверено / ожидаемое | Фактическое evidence | Статус |
| --- | --- | --- | --- |
| G04-1 | `success` refund journal ↔ `commerce_payments.status='refunded'`, одинаковый owner/provider payment reference без показа этих полей | **2 успешных операции**, расхождений **0** | **PASS, scoped** |
| G04-2 | Не должно оставаться необъяснённых `unknown`/`in_flight` в выбранном pilot journal | **unknown/in_flight 0**, **failed 0** | **PASS, scoped**; теста реального ambiguous outcome и replay не было |
| G04-3 | У одного payment нет двух записей `stars_refund_operations` в pilot | **duplicate_payment_operations 0**; schema v13 дополнительно имеет `payment_id UNIQUE` | **PASS, scoped**; не доказательство idempotency при реальном повторном provider request |
| G04-4 | Определить фактическое состояние `entitlements` для `refunded` payments; не приписывать будущий revoke текущему `rc.9` | Выборка **2**; `active_after_refund=2`, `missing_entitlement=0`. **3x-ui provider access postcondition не проверялся** | **REVIEW (known policy/behavior gap)**, не трактовать автоматически как новый regression bug; full refund-access postcondition **PENDING** |
| G04-5 | Экран `🆘 Помощь → 💳 Поддержка по оплате` открывается, объясняет обращение и возвращает в помощь | Оператор сообщил **PASS**; screenshots/trace нет, обращения/возвраты не отправлялись | **PASS, operator-reported** |

**Суммарно:** **4 scoped PASS + 1 REVIEW**, **G-04 PARTIAL**, **V5-A-001 NOT PASS**, общий **v5 acceptance NOT PASS**. `G04-4` не превращать в PASS потому что G04-1/2/3 показывают исправный финансовый журнал. Прежние G-01/G-02/G-03 scoped 5/5 подтверждения сохраняются, но их gates остаются PARTIAL.

## Интерпретация active entitlement при refund

- Исходники опубликованного тега `v5.0.0-rc.9`: [`db.finish_stars_refund()`](../../db.py) при `success` ставит `commerce_payments.status='refunded'`, **не** корректирует `entitlements`, `users.expiry_time` или 3x-ui доступ; `stars_refund.py` явно сохраняет `unknown` без автоматического повтора.
- В [Issue #433](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/433) **OPEN** новая 14-дневная политика с пропорциональным вычетом периода и безопасным отзывом доступа **запланирована для будущего RC**, не реализована/не опубликована в текущем `rc.9`. Это объясняет две локальные `active` записи и образует **осознанный residual business-policy risk / PENDING**, но **не доказывает**, что именно эти два provider VPN доступа ещё активны: provider read в G-04 отсутствовал. Нет основания автоматически создавать дубликат #433 либо закрывать его.
- Связанные [#434](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/434) (client refund terms), [#436](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/436) (юридическая политика, отложена), [#437](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/437) (Admin Support reference) остаются **OPEN**, их реализации в `rc.9` нет. Проверка простого `/paysupport` не доказывает полноценный ticket/workflow.
- [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) OPEN node-sync; [#466](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/466) OPEN natural event; #342 и #422 CLOSED по своим отдельным фактически принятым smoke. Их состояния не изменять из-за G-04.
- **Остаётся PENDING:** provider/3x-ui read-only access postconditions для двух исторических refund без новой финансовой mutation, документирование/активация согласованной версии policy в будущем #433, сложные unknown/restart/retry tests только isolated; no customer-facing 14d promise до legal review. Ни full G-04, ни общую приёмку v5 нельзя считать закрытыми.
- **Следующий checkpoint:** обновить и **верхнюю сводку**, и таблицу `### 11 проверок текущей rc.9 перед следующим релизом` в каноническом `docs/ROADMAP.md`, включая backfill фактов G-01…G-03 из [audits G-01](v5-g01-production-baseline-2026-10-12.md), [G-02](v5-g02-targeted-reconciliation-2026-10-12.md), [G-03](v5-g03-stars-vpn-existing-pilot-2026-10-12.md). Провести PR с required `test`/`title`, squash merge и независимый GitHub read-back таблицы и Issue states. Не начинать G-05 до завершения checkpoint. W-01/W-02 остаются waived/inconclusive, не повторяются.
