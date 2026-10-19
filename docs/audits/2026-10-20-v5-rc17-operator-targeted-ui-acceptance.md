# v5.0.0-rc.17 — операторская targeted UI-приёмка #760, #470, #437

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-20 02:10 EEST (UTC+03:00); сообщение оператора 2026-10-19T23:10:14Z, deployment ранее сообщён 2026-10-19T22:58:08Z.
- **Окружение:** production controlled pilot, operator-reported Telegram UI; независимого VPS/Telegram read-back у агента нет.
- **Цель:** зафиксировать после `rc.17` только непроверенные исправление U8 и новые read-only экраны Orders/Support, без повторения прежних U1–U7/U9–U12/Z1–Z2.
- **Версия и immutable tag/SHA:** `v5.0.0-rc.17` / `0d5240c4799ba09952d74748a90a6a669894006d`; tag и публикация подтверждены GitHub REST, deployed identity — operator-reported.
- **Scope:** U8-1…U8-4 (4), S1…S8 (8), R1…R8 (8); оператор отметил все 20 пунктов `[x]`; без новых Stars purchases, refunds, provisioning, SQLite/3x-ui writes или restarts. Условные S3 (доступен pending без Payment), S6 (более восьми заказов), U8-4 (есть статус `🟡♾️`) требуют подтверждения фактической применимости; отметка сама по себе не доказывает наличие записей.
- **Фактический результат:** PARTIAL — все 20/20 пунктов отмечены оператором; U8 навигация и справочник — **operator-reported scoped PASS**; S1/S2/S4/S5/S7/S8 — operator-reported scoped PASS, S3/S6 и U8-4 имеют условную применимость, отдельные данные о ней не предоставлены (`PENDING/N/A` до уточнения). #437 полное acceptance PENDING из-за неопубликованного юридического § 9 (#707); G-11 PARTIAL/NO-GO.
- **Источник и evidence:** операторское сообщение 2026-10-19T23:10:14Z с отмеченными U8-1…U8-4, S1…S8, R1…R8; опубликованный GitHub Release `v5.0.0-rc.17`; Issues #760/#470/#437/#707; deployment evidence operator-reported.
- **Ограничения и остаточные риски:** independent VPS/container image и локальная DB/provider attestation отсутствуют; `[x]` означает отчёт оператора, не самостоятельную проверку всех постусловий агентом. Отсутствует независимое read-back о фактическом неизменении данных. Юридический `docs/legal-publication.json` имеет `publication_state=unpublished`. Условные S3/S6/U8-4 нельзя превращать в автоматический PASS. Предыдущие scoped PASS сохраняются без повторения, full v5 acceptance не подтверждён, public rollout BLOCKED.
- **Связанные Issues:** #760, #470, #437; #707 (зависимость § 9); #805 (правило checklist).
- **Решение по Issues:** #760: keep_open; #470: keep_open; #437: keep_open; #707: keep_open; #805: keep_open.
- **Следующий шаг:** подтвердить только применимость S3/S6/U8-4 без создания новых данных; сверить собственные acceptance критерии #760/#470/#437, зафиксировать scoped closure decisions, синхронизировать Roadmap в `main` через разрешённый merge/docs-only checkpoint; #707 остаётся отдельным legal-publication blocker. Повтор старых тестов запрещён без новой гипотезы.
- **Раздельные состояния:** merged=implementation PR #766/#799/#801 MERGED, docs PR #804 OPEN; published=GitHub Release rc.17 PASS; deployed=operator-reported rc.17; accepted=operator-reported scoped UI PASS с условными PENDING, full v5 PARTIAL/NO-GO.

## Матрица без повторов

| Scope | Отметки оператора | Доказанный результат |
| --- | --- | --- |
| U8-1…U8-3 | 3/3 `[x]` | operator-reported scoped PASS: цепочка Back, Все, Панель администратора |
| U8-4 | `[x]` | operator-reported отметка; `🟡♾️` только при наличии записи, применимость не уточнена |
| S1/S2/S4/S5/S7/S8 | 6/6 `[x]` | operator-reported scoped PASS в заявленной области |
| S3/S6 | 2/2 `[x]` | условные сценарии: проверяемость по текущим данным PENDING |
| R1…R8 | 8/8 `[x]` | operator-reported scoped PASS для read-only Support UI; фактический § 9 всё ещё unpublished |

**Security:** ни Issue, ни audit не содержит реальные Telegram IDs, subscription URLs, invoice payload или secrets.
