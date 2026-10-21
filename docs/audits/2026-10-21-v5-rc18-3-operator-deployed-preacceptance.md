# Operator-reported deployment checkpoint v5.0.0-rc.18.3 — 21.10.2026

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-21 13:34 UTC+03:00 (момент получения отчёта; точное время deployment не указано)
- **Окружение:** production / operator-reported; только GitHub Release/tag проверены независимо через GitHub API
- **Цель:** зафиксировать заявленный production deployment опубликованного `rc.18.3` до отложенного targeted HWID smoke, не объявляя приёмку выполненной
- **Версия и immutable tag/SHA:** `v5.0.0-rc.18.3` / `4b7785557097b6b71324e8f53e9504ad898e43c4`
- **Scope:** по сообщению оператора: `Production=v5.0.0-rc.18.3`, `APP_VERSION=5.0.0-rc.18.3`, `GitSHA=4b7785557097b6b71324e8f53e9504ad898e43c4`, `DEPLOY_OK`, container `running`, `RestartCount=0`, `Health=ok`, `DB=ok`, `3XUI_TCP=ok`, наличие пути pre-deploy backup заявлено без раскрытия локального пути; никаких targeted Telegram HWID, DELETE, Stars, refund, load или full v5 acceptance проверок в этом отчёте нет
- **Фактический результат:** PARTIAL — scoped startup/deployment postconditions **PASS только по отчёту оператора**; targeted HWID acceptance и независимая production attestation **PENDING**
- **Источник и evidence:** сообщение оператора от 2026-10-21 10:34:16Z (13:34:16 UTC+03:00) в текущей беседе; независимый [GitHub Release](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.18.3) и `refs/tags/v5.0.0-rc.18.3` read-back подтвердили Published/tag SHA; [publication audit](2026-10-21-v5-rc18-3-published-github-checkpoint.md)
- **Ограничения и остаточные риски:** доказательство на VPS не получено независимо; `DB=ok` не эквивалентно доказанному `PRAGMA quick_check`, `3XUI_TCP=ok` не доказывает 3x-ui API/data-plane, backup path не подтверждает восстановимость. Новый `rc.18.4` ещё не определён по кейсам, не Merged/Published/Deployed. `rc.18.3` targeted HWID smoke намеренно отложен; G-11 PARTIAL/NO-GO, independent X2/X1/X3 provenance PENDING, public rollout BLOCKED
- **Связанные Issues:** #827, #830, #833, #834, #838 (все OPEN)
- **Решение по Issues:** #827: keep_open; #830: keep_open; #833: keep_open; #834: keep_open; #838: keep_open (deployed не является acceptance)
- **Следующий шаг:** зафиксировать новые кейсы для `rc.18.4` через Issue-first, выполнить code/tests/docs/PR/CI и отдельный release workflow только после определённого scope/разрешений; после deployment нового RC выдать единый полный targeted checklist по непроверенным критериям каждого Issue `rc.18.3` и `rc.18.4`, без повторов ранее принятых scoped PASS
- **Раздельные состояния:** merged=release-prep PR #841 / `4b7785557097b6b71324e8f53e9504ad898e43c4` (документационный deployment checkpoint ещё не merged); published=PASS / GitHub `v5.0.0-rc.18.3` / immutable SHA; deployed=operator-reported PASS для `rc.18.3`, независимый VPS read-back PENDING; accepted=PENDING для #827/#830/#833/#834/#838, full v5 NOT PASS / G-11 PARTIAL/NO-GO
