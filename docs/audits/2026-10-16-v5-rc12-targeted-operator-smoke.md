# v5.0.0-rc.12 — адресная операторская проверка после deployment (2026-10-16)

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-16 00:27 UTC+03:00 (EEST); время получения отчёта оператора 2026-10-15T21:27:19Z, точное время выполнения отдельных проверок неизвестно
- **Окружение:** operator-reported production Telegram UI, controlled v5 pilot; независимого доступа исполнителя к VPS, Node Panel, Xray, DB и Telegram не было
- **Цель:** rc.12 targeted A2 Reality Flow, A6 безопасный preflight, #679 origin-aware Back/Refresh, R1–R5 и D1–D7; разграничить позитивный сценарий и ещё не выполненные negative tests
- **Версия и immutable tag/SHA:** `v5.0.0-rc.12` / `a88fd6947f04d40570413e792cda7150e738abbd`, GitHub [Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.12) Published; deployment baseline operator-reported отдельно [зафиксирован](2026-10-15-v5-rc12-operator-deployment-checkpoint.md)
- **Scope:** A2.1–A2.8, A6.1–A6.9, N1–N7, R1–R5, D1–D7 по приватному отчёту. Read-only сравнение Master/Node #1 получило MATCH по Vision, но MISMATCH/UNKNOWN как отрицательные сценарии не воспроизводились; редактор Flow A6 заблокирован `CLIENT_RECORD`
- **Фактический результат:** PARTIAL — **A2.1/A2.2/A2.3/A2.4/A2.7/A2.8 operator-reported PASS**; Node #1 `MATCH · Master xtls-rprx-vision / Node xtls-rprx-vision`. **A2.5/A2.6 PENDING**: вместо отдельного mismatch/unknown оператор повторил «A2.4: MATCH», этот ответ не доказывает обработку отрицательных случаев. **A6.1/A6.2 BLOCKED**: `Master/Inbounds не подтверждены (CLIENT_RECORD); изменений нет`; A6.3 operator-reported отсутствие изменений при отказе (fail-closed, только scoped); A6.4–A6.9 BLOCKED; не запускался ни один Flow POST. **N1–N5/N7 PASS, N6 BLOCKED**; R1/R2/R4/R5 PASS, R3 BLOCKED; D1–D7 operator-reported PASS, детали SQL/image/backup и transaction journal не аттестованы независимо
- **Источник и evidence:** приватное сообщение оператора 2026-10-15T21:27:19Z, точная quoted ошибка `CLIENT_RECORD`, read-only Node #1 `MATCH`; [PR #678](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/678) / [#680](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/680), [deployment audit](2026-10-15-v5-rc12-operator-deployment-checkpoint.md). Отсутствуют независимые raw Telegram/Master/Node/SQL логи, и не публикуются personal/customer IDs
- **Ограничения и остаточные риски:** `MATCH` относится к одному наблюдению Node Panel, не к работающему Xray и не доказывает отрицательные исходы A2.5/A2.6, все Node Inbounds или исправление бага тарифа #648. `CLIENT_RECORD` охватывает несколько fail-closed условий в `flow_edit.py`: отсутствующие обязательные поля общего client record, `None` в обязательных полях или non-empty чужепротокольные поля; точное условие не известно. Нельзя ослаблять full-row preflight, раскрывать raw payload/credentials, делать blind retry или адресный Flow POST. D2/D4/D6 без независимо полученных SQLite/backup/journal доказательств остаются operator-reported scoped PASS. Полные v5 gates V5-A-001/002/003 и G-11 не закрыты
- **Связанные Issues:** [#659](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/659) — scoped positive Node MATCH, отрицательные сценарии и независимость Xray PENDING; [#663](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/663) — BLOCKED CLIENT_RECORD, A6.4–A6.9; [#679](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/679) — N1–N5/N7 PASS, N6 BLOCKED; [#648](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/648) — tariff reproducer не выполнялся; #649/#650 — R4/R1 PASS на rc.12, собственный closure audit отдельно
- **Следующий шаг:** сначала закрыть Roadmap sync PR с required CI и отдельного разрешения merge; затем безопасно классифицировать конкретный `CLIENT_RECORD` без выгрузки raw record/секретов и исправить только доказанный несовместимый формат при сохранении fail-closed. После отдельного одобренного release/deploy повторить A6 и N6/R3; A10 и опасный #648 reproducer — только по отдельному разрешению. A2.5/A2.6 — только при доступных безопасных offline/mocked негативных фикстурах, не ломать живую ноду
- **Раздельные состояния:** merged=PR #681, commit `a88fd6947f04d40570413e792cda7150e738abbd`; published=immutable prerelease `v5.0.0-rc.12` GitHub PASS; deployed=`v5.0.0-rc.12` operator-reported 2026-10-15T20:59:01Z, direct attestation PENDING; accepted=rc.12 A2 scoped positive MATCH и navigation N1–N5/N7 operator-reported PASS, A6 BLOCKED, G-11 PARTIAL/NO-GO

## Матрица

| Набор | Статус | Осталось |
| --- | --- | --- |
| A2.1/2/3/4/7/8 | PASS, operator-reported | Node #1 MATCH Vision/ Vision, bounded read-only; отсутствие Xray evidence |
| A2.5/6 | PENDING | Независимые negative MISMATCH/UNKNOWN не выполнены: ответ ссылается на A2.4 MATCH |
| A6.1/2 | BLOCKED / CLIENT_RECORD | Полный Master client record не прошёл fail-closed validation |
| A6.3 | PARTIAL | Заявлено отсутствие изменений при отказе, нет отдельного API mutation journal |
| A6.4–9 | BLOCKED | Выбор/варианты/confirmation/Cancel не открылись |
| N1–5, N7 | PASS, operator-reported | Контекстные Back/Refresh и RBAC позитивно проверены |
| N6 | BLOCKED | Зависит от успешного preflight редактора |
| R1/R2/R4/R5 | PASS, operator-reported | Трафик, baseline, navigation spot и VPN connectivity |
| R3 | BLOCKED | Зависит от редактора Flow |
| D1–D7 | PASS, operator-reported | Independent SQL/backup/journal evidence не предоставлен |
| v5 global acceptance | PARTIAL / NO-GO | G-11, V5-A-001/002/003, full rollback/DR и payment gates PENDING |

Данный аудит не изменяет production состояние и не разрешает новую мутацию.
