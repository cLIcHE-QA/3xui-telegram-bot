# 3x-ui v3.10.0 — статическая совместимость pinned OpenAPI (2026-10-14)

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-14 17:07 UTC+03:00 (EEST; плановое решение оператора около 17:07 EEST; GitHub upstream release 2026-10-12 14:44:53Z)
- **Окружение:** GitHub read-only comparison официальных upstream tag `v3.9.0`/`v3.10.0`; изменение source manifest/docs в PR; изолированного интеграционного стенда или живого VPS read-back не было
- **Цель:** [#630](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/630), v3.9.0 → v3.10.0 compatibility gate до deployment Master/direct nodes и до rc.10 release-prep
- **Версия и immutable tag/SHA:** bot Published `v5.0.0-rc.9`, immutable tag SHA `13fdbe8bccfbe92cffc4117b79083bbdcad5a8db`; исходный protected main `2b6867785a7b9d65d4d870e982ab9546e6255d52`; upstream OpenAPI blob SHA `v3.9.0=298f96690c012a7fd80822aab9a91934c7dc4f79`, `v3.10.0=b50cb368f43bd54583189453ce96ceebc431b2a5`
- **Scope:** 55 из 55 используемых ботом объявленных операций `contracts/3xui/contract.json` сравнены по method/path, security, requestBody required/media/required fields и response 200/media/envelope; upstream tag имеет 184 paths в обеих версиях, upstream diff касается иных маршрутов/схем (MASQUE, Node event traffic и др.). Зафиксировать vendored exact schema, updated manifest/docs и required CI в PR; **нет** live Master/Node, TLS, VPN-client tests, SQL/provider mutation, migrations, panel service restart/backup/restore/deploy, релиза бота
- **Фактический результат:** PARTIAL — статический API surface compatibility 55/55 scoped PASS, неизвестных несовместимостей этих операций не обнаружено; runtime/staging/production contract acceptance **PENDING**
- **Источник и evidence:** upstream [release notes](https://github.com/MHSanaei/3x-ui/releases/tag/v3.10.0) и immutable [OpenAPI tag source](https://github.com/MHSanaei/3x-ui/blob/v3.10.0/frontend/public/openapi.json), [manifest](../../contracts/3xui/contract.json), [contract policy](../3XUI_OPENAPI_CONTRACT.md), [operator update runbook](../VERSIONS_UPDATES.md); CI run / merge SHA добавляются в PR provenance, не задним числом в audit
- **Ограничения и остаточные риски:** static compatibility доказывает только совпадение объявленных операций; Xray-core 26.10.10, изменённые xdns/udpHop/Shadowsocks-2022 stored configs, CA roots, systemd sandbox paths, MASQUE/XDRIVE (в бот не включались), Master↔Node sync и rollback после автоматических миграций требуют отдельного staging/approved production preflight. Upstream прямо требует upgrade каждой node. [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) не закрыт. Existing deployed 3x-ui `v3.9.0` лишь operator-reported, не независимый VPS proof. Не путать pinned schema main и published/deployed
- **Связанные Issues:** [#630](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/630) OPEN и [#487](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/487) OPEN
- **Следующий шаг:** полный CI/PR/squash + main/Issues readback для contract scope; затем отдельный approved staging 3x-ui `v3.10.0` Master/direct-node integration smoke, verified backups и production maintenance plan/approval. Не выполнять production upgrade без нового явного распоряжения
- **Раздельные состояния:** merged=bot protected main `2b6867785a7b9d65d4d870e982ab9546e6255d52` до docs/contract PR, merge PENDING; published=bot `rc.9` (tag SHA выше); deployed=bot rc.9 и 3x-ui v3.9.0 operator-reported only; accepted=static manifest comparison scoped PASS, 3x-ui v3.10.0 deployment/complete integration PENDING, overall v5 `CONDITIONAL / NO-GO`

## Матрица границ

| Объект | Факт | Status |
| --- | --- | --- |
| OpenAPI versions, declared methods | 55/55, same route/method/security/requests/responses | scoped PASS |
| Blob identity | immutable upstream Git blob SHA `b50cb368f43bd54583189453ce96ceebc431b2a5` | scoped PASS |
| CI contract and regression | required PR checks пока не выполнены при создании audit; ссылки в PR | PENDING |
| Runtime bot changes | `xui.py` / `version_api.py` не менялись | N/A |
| Staging v3.10.0 + direct nodes | не тестировались, в том числе data plane | PENDING |
| Production Master/Node upgrade | не выполнялся, отдельное разрешение | BLOCKED |
