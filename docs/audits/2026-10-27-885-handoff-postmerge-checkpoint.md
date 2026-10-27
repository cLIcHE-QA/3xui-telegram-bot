# #885 — HTTPS handoff: post-merge checkpoint

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-27 09:15 UTC+03:00
- **Окружение:** GitHub / CI / локальные synthetic Python3.12 unit/HTTP/UI fixtures
- **Цель:** подтвердить merge #886 и синхронизировать фактический implementation state #885 до rc.21 release-prep.
- **Версия и immutable tag/SHA:** #886 squash main `b10fe96faa78f55b78116da7de426f9863c59a83`; exact PR head `f42307dc5e552264ca1fd5bce930adf24ea50fdf`, base `50788872fba87c7d1c5b78f45a430b902e3a5ffb`; Published v5.0.0-rc.20 `929e9950a9d831ef72271f99b226a3315cfef709` без #885.
- **Scope:** owner/private ticket issuance, exact import_uri payload, TTL/replay/capacity, bounded in-memory storage, HTTP GET isolation и честный Telegram fallback; PR/main read-back. Не device/staging/production acceptance.
- **Фактический результат:** PASS
- **Источник и evidence:** [PR #886](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/886) MERGED, независимые PR/main read-back; [fresh Python40459129292](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40459129292) SUCCESS (1569 tests, 3 skipped), [final title40459503257](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40459503257) SUCCESS. Локально targeted29/full1569 (16 skipped), compileall/OpenAPI/catalog/docs/base diff PASS. Post-merge [main Python40459613878](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40459613878) SUCCESS на squash SHA; fresh [supply-chain40459701390](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40459701390) SUCCESS, независимо прочитано при подготовке checkpoint.
- **Ограничения и остаточные риски:** ticket — bearer-like URL, не новая HTTP owner-аутентификация; один bot/proxy process, restart/другой worker теряет ticket. Physical Telegram iOS/Android/desktop custom-scheme/auto-open/import/refresh и действующий TLS/log/cache/CSP ingress не проверены. Полный acceptance #885 не завершён.
- **Связанные Issues:** #885
- **Решение по Issues:** #885: keep_open
- **Следующий шаг:** required CI и merge этого docs-only checkpoint, независимый main read-back; затем rc.21 release-prep с единственным самостоятельным scope #885. Deployment/device шаги отложены в завершающий блок #930.
- **Раздельные состояния:** merged=#886 `b10fe96faa78f55b78116da7de426f9863c59a83`; published=v5.0.0-rc.20 без #885; deployed=v5.0.0-rc.18.10 `dae205ac82762723448f93827b981f89ae622231` только operator-reported, independent VPS read-back PENDING; accepted=offline/CI scoped PASS, own live #885 PENDING, G-11 PARTIAL/NO-GO, public rollout BLOCKED.

## Проверенные границы

Existing guard_callback и private chat owner проверяются до чтения subscription URL или mint. HTTP ticket содержит только 256-bit opaque random; TTL90/MAX256, process-local память, один успешный GET. Payload повторно сверяется с существующим import_uri для того же URL/client/platform/title, а не только со scheme prefix. HEAD/POST, query, encoded/noncanonical path, malformed/expired/replayed ticket не раскрывают URI; ошибочный запрос не списывает действующий ticket. HTML/CSP/hash/no-store/no-referrer, no third-party redirect и отсутствие provider fetch проверены synthetic HTTP/UI fixtures. Copy/QR/Back остаются при выключенном/невалидном template, без недоступной кнопки или инструкции нажать её.

Scope не меняет schema, slash-команды, dependency locks, provider mutations или privileged runtime. Старые release-state конфликты #886 разрешены актуальным main без force-push; предыдущий draft CI не принят за новый head. [Pre-merge audit](2026-10-27-885-handoff-premerge-review.md) сохранён как dated snapshot.

#885 остаётся OPEN/keep_open по собственному последнему acceptance criterion: отдельно разрешённый deployment и targeted device/client import/refresh с postcondition. #473 не закрывается транспортным улучшением. Служебный #935 publication checkpoint уже merged `50788872fba87c7d1c5b78f45a430b902e3a5ffb`, main [Python40457805336](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40457805336) и idempotent [Publish40458144165](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40458144165) SUCCESS; rc.20 tag не перемещался.
