# #989 — безопасный отказ клиентского traffic read, source review

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-28 21:19 UTC+03:00
- **Окружение:** изолированный tracked checkout CPython3.12 с точной source overlay; synthetic transport/DB/UI и временные loopback HTTP test fixtures полного suite, без внешней панели/Telegram/VPS
- **Цель:** воспроизвести и исправить provider-neutral error boundary traffic, сохранить успешные DTO/ownership/cancellation/no-replay contracts.
- **Версия и immutable tag/SHA:** source `3835a4ef6ed684aba683364b5eee8a8426c9349e`; target v5.0.0-rc.31 план, tag N/A — ещё не Published. Actual Published RC30 `7aa3514194675ae119a2e774e03da150025326b9` fix989 не содержит.
- **Scope:** pre-fix/post-fix offline regression, boundary/security review, clean tracked fixture full suite/compileall/OpenAPI, совместимость реального XUI read/session/admission и новые actual17 measurements/5 source hashes. Required PR/main/image/immutable RC31/publication и собственный installed/read outcome отдельно PENDING.
- **Фактический результат:** PASS
- **Источник и evidence:** [Issue #989](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/989), предыдущий publication988 main `1fdce02cc0913eee07b42998ba8fb77ce3524b08`/required+main1771/3/publisher/independent main read-back2026-10-28T18:08:44Z PASS; source diff/tests ниже. Новые [matrix15](2026-10-28-989-traffic-read-matrix.json) и [concurrency32x2](2026-10-28-989-traffic-read-concurrency32.json) имеют actual committed source3835/clean5 hashes; старые raw/audits неизменны.
- **Ограничения и остаточные риски:** source PASS не означает merge/release/deployment/runtime acceptance. R989-01 installed SHA/health/существующий owner traffic read PENDING до отдельного deployment; live failure/load не создавать. Parent482 pooling/cache/lifecycle/admin full-list/critical contexts/limiter и #984 R984-01…03 отдельно. Deployed18.10 operator-reported/independent VPS PENDING; G-11 PARTIAL/NO-GO/public rollout BLOCKED.
- **Связанные Issues:** #989, #482, #984
- **Решение по Issues:** #989: keep_open, #482: keep_open, #984: keep_open
- **Следующий шаг:** required CI/security/main checkpoint, отдельный release-prep RC31/release-scope/официальный health/автоматическая immutable публикация/own Issue audit и main read-back; до них следующая значимая задача не начинается.
- **Раздельные состояния:** merged=989 not yet, предыдущий988 main1fdce02; published=RC30 без989; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15, independent VPS PENDING; accepted=только проверенный offline source scope PASS, required/release/own runtime989 и parent482 PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## Discovery и pre-fix FAIL

Дубликаты OPEN Issues по traffic и CustomerProviderUnavailable проверены через GitHub API: parent482 и отдельные unrelated487/887/984, самостоятельного error-boundary child нет. До кода создан989 с собственным scope/acceptance; предыдущий988/source/publication/main/own984 audit завершён. Parent historical devices observation уточнён: devices/access уже ловят native transport errors, их runtime не переписывается.

На actual base1fdce02 до изменения adapter добавлены11 meaningful tests. Pre-fix11 завершились FAIL1.590s: failures2/errors34. Native ClientConnectionError/TimeoutError/OSError на каждом из двух awaits уходили мимо CustomerProviderUnavailable; malformed mapping/numeric conversions давали AttributeError/TypeError/ValueError/OverflowError. Existing XUIError normalization сохранял raw cause в обычном formatted traceback, две проверки этого границы тоже FAIL. Genuine DTO/aliases/нули/cancel/unexpected-runtime/devices guard cases были сохранены в том же наборе. Synthetic values явно фиктивные; payload production не читался.

Минимальный fix меняет только XuiCustomerProvider.traffic: mapping guards до использования данных, прежний DTO/int/aliases внутри try, узкий список ожидаемых transport/data exceptions и постоянный sanitized domain error from None. Нет blanket except Exception, cancellation сохраняет identity. Post-fix11 PASS1.341s, затем targeted94 PASS3.567s: новые11 плюс existing devices/delete/customer boundary/diagnostics/admission/strict no-config import/baseline/subscription-card cases.

## Полный suite и среда

Первое полное invocation в restricted sandbox завершилось FAIL:1782 tests/16 skipped за101.507s, failures2/errors120. Причина — PermissionError при bind127.0.0.1:0 существующих ephemeral HTTP fixtures, после setup errors появились unclosed synthetic session warnings. Это не объявлялось PASS и не исправлялось ослаблением source/tests/gates. Повтор с обычным разрешённым loopback test environment на тех же source bytes: **1782 tests/16 skipped PASS102.172s**, compileall и pinned OpenAPI55 PASS. Loopback fixtures не являются runtime polling/listeners, VPS/staging deploy или обращением к реальной панели; оригинальный ignored .env не копировался/не читался, credentials/env synthetic.

Изолированный fixture был tracked base1fd с точной source3835 provider/new-test overlay; Git-clean для него не заявляется. Fresh actual measurements ниже выполнялись последовательно после полного suite, на committed source3835 в основном checkout, measured_files_dirty=false. Standard Python без locked dependencies сначала дал ModuleNotFoundError aiohttp при --help benchmark; исправлен только interpreter на existing locked Python3.12 runtime. Нет установки дополнительных пакетов или изменения dependency floor.

## Security/compatibility reasoning

Actual adapter + CustomerPortalService + existing traffic_cb regression проходит от server-owned profile email до прежнего temporary-unavailable UI/Back. No-profile и rejected guard не выполняют provider reads, ошибки не дают успешный zero DTO. Успешные nested/direct records, up/down и uplink/downlink, missing-field defaults и настоящие нули совместимы. Malformed shapes и invalid/infinite numeric counters fail closed. Ошибка не раскрывает raw cause в стандартном traceback; это не утверждение об удалении внутреннего exception context из Python memory.

Integration использует настоящий XUIClient GET path с fixed fake ClientSession: сбой первого/второго read даёт ровно1/2 GET, все созданные sessions закрыты, aggregate admission active/targets=0, нет retries/mutations. Existing devices сохраняет inventory/verified IDs и unknown limit при независимом read failure. Mutation unknown/no-replay/device controls подтверждены существующими tests.

Сравнение AST всех adapter definitions после удаления только traffic совпало с base1fd. xui.py/version_api.py/panel_read_budget.py/provisioning.py/customer_service.py/client_access.py/requirements.lock/db_migrations.py byte-identical. Auth/TLS/routes/counters admission и authoritative mutation postconditions не меняются, нет новых schema/env/ports/cache/pooling/commands/credentials или междоменных fallback. Unexpected programming RuntimeError не превращается в ложный ожидаемый provider failure.

## Actual raw/provenance и пределы измерений

Matrix15 измерена2026-10-28T18:17:42.406623Z; separate concurrency32x2 —18:18:00.524235Z. Source3835/5 measured hashes clean; только customer_provider_xui.py получил новый SHA-256 `1946daed529dff1bb2ab0167e7fd7e9917c08a2339243c35b544460451474b4c`, остальные measured files прежние. Все17 cases совпали с source984 по scenario/volume/operations/driver concurrency/delay, calls/routes/JSON bytes/session/closed/backlog/transport+driver peak/owners. Реальный driver32 сохраняет peak transport6, остальные bounds прежние. Timing/CPU/RSS не объявляются byte-identical, performance improvement или panel/Xray capacity.

Для concurrency32 сначала был пропущен --delay-ms2 и получился1ms draft; он сохранён отдельно локально, в новый публикуемый raw вошёл повтор с правильными теми же параметрами64 requests/concurrency32/2ms. Исторические source984/972/977 raw не переписывались; новый source identity не маскируется старым hash. CLI по-прежнему fixed offline/fresh workers без network/config/DB/production mode.

## Documentation impact и собственный closure

Canonical API/README/operator diagnosis/Client/V5/CHANGELOG/Roadmap/registry обновлены для нового error contract. Operator setup/schema/deps/versionAPP30 прежние, RC31 только план. При source review обнаружен stale detail README: он ещё утверждал Actual Published29 без984, хотя верхний current projection и GitHub уже подтверждали RC30. Этот узкий current-state drift исправлен на фактический RC30/checkpoint988, без переписывания historical audit. Верхний CHANGELOG checkpoint тоже уточнён: publication988/main/own984 audit завершены, отложен именно runtime. Это docs sync уже отслеживаемого984, не второй самостоятельный runtime scope в будущем RC31.

Governance первоначально отклонил лишнюю пустую строку перед новой989 row как разрыв единой active table; исправлена только структура Markdown, затем governance/semantics/diff PASS. Source review не закрывает989: required CI/source/main/release/publication и R989-01 PENDING. #984 runtime R984-01…03 и parent482 остальные критерии остаются OPEN/keep_open. Реальные платежи/refund/provider/host/Bot sends/live load не выполнялись.
