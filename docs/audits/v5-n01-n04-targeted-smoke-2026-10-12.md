# N01–N04 — точечный операторский smoke, 2026-10-12

## Источник и baseline

Оператор сообщил `PASS` для N01–N04 **2026-10-12 18:43:40 UTC (21:43:40 EEST)**; уточнил значения **2026-10-12 18:47:16 UTC (21:47:16 EEST)**. Время сообщения не является независимым временем выполнения. Production pilot: Master и direct Node 3x-ui, существующий тестовый клиент, клиентский Telegram-бот и Owner settings. Последний operator-reported deployed bot — `v5.0.0-rc.9`; опубликован immutable prerelease tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`. Repository baseline: protected main `6f197e2824386793cbd0e9ef33b9787ec3d098b6`. Ни нового deployed SHA, ни API-лога, ни скриншота не предоставлено. Все проверки — **операторские короткие наблюдения**, не регрессия.

## Результаты

| ID | Результат оператора | Вывод и границы |
| --- | --- | --- |
| **N01 / #487** | PASS; `Node online=YES`, `Sync mode=YES`, `Last sync status=NOW` | **Scoped PASS** для видимых UI-полей. `YES` не идентифицирует точное `inboundSyncMode`, а `NOW` — не timestamp; версии, GUID и подтверждённая история sync отсутствуют. |
| **N02 / #487** | PASS; `Client on Node=YES`, `Enabled matches=YES`, `Expiry matches=YES`, `Inbound matches=YES` | **Scoped PASS 4/4** по одному клиенту Master/Node. Не подтверждены immutable client/Node identity, точный membership, offline recovery или propagation после изменений. |
| **N03 / G-07** | PASS; legacy `/create` и `/inbounds` перенаправляют в личный кабинет | **Scoped PASS** безопасных переходов. Отдельно открыт [Issue #564](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/564) на скрытие устаревших команд из актуального интерфейса с сохранением backwards compatibility; не баг и не внедрённая функция. |
| **N04 / G-08** | PASS; `Stars effective=ON`, `Local config=ON`, `DB override=ON` | **Scoped PASS** read-only согласованного ON. OFF/ON emergency stop, pre-checkout и обработка уже оплаченного события не проверялись. |

**Итог:** четыре scoped operator-reported PASS, без заявленных production mutations. Нет нового Stars платежа, возврата, переключения флагов или рестарта. Общий G-02/G-07/G-08 **PARTIAL**, Issue #487 **OPEN**, Issue #564 **OPEN/PENDING**, общая v5 приёмка **NOT PASS**, public rollout **BLOCKED**. G-09 S05 остаётся запланированным на 2026-10-13 21:03:16 EEST и **PENDING/NOT TESTED**.

## Контекст legacy и остаток

Код `client_access.py` оставляет `Command("create", "inbounds")` и старые callback payload как защищённые non-mutating redirects. Каталог `telegram_commands.py` помечает оба названия `legacy`, но отображает их в пользовательском списке; `scripts/check-telegram-command-catalog.py` и соответствующие тесты требуют согласованности каталога и реальных handlers. Безопаснее убрать их из рекомендаций и сохранить обработку старых ссылок. Реализация — будущая самостоятельная работа по #564; текущий PR исключительно фиксирует evidence.

**Issue audit:** #487 открыт, т.к. недоказаны GUID, точный sync-mode, node-side provenance и offline recovery. #342 закрыт по собственной приёмке, но G-08 остаётся PARTIAL. #433 и #466 открыты, поскольку новая проверка не затрагивает refund/revoke или естественный job_failed. #317/#422 остаются CLOSED.

**Checkpoint:** top Roadmap и канонические строки G-02/G-07/G-08, отдельный docs PR, required `test`/`title`, squash, независимый main readback и Issue comments. До merge **ROADMAP SYNC: PENDING**.
