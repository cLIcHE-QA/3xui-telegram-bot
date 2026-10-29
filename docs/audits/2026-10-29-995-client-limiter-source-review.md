# Source review #995: bounded память клиентского limiter, часть #482-D

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-29 10:34 UTC+03:00
- **Окружение:** isolated tracked fixtures/пустой .env/synthetic identities и clock, unit-test loopback HTTP/TLS fixtures, без production/external network/Telegram операций
- **Цель:** ограничить retained keys и удалить истёкшие окна неактивных пользователей, сохранив per-user sliding-window/Owner reset guards.
- **Версия и immutable tag/SHA:** base main `27fc3d82c72564bbc961c8a2fcde562ccf5e06ea`; actual Published v5.0.0-rc.31 `e74aabf827e5683c3528f9bd49e701a1ac17812c` не содержит candidate. Source commit `a7356aff172fc84869862bc03e963b6c14535016`; source/test pair чиста относительно этого commit, metadata ещё не committed; SHA-256 ниже.
- **Scope:** pure process-local limiter + fake guard integration/regression/docs; не distributed quota, provider capacity или runtime acceptance.
- **Фактический результат:** PARTIAL
- **Источник и evidence:** pre-fix14 tests 1.408s FAIL3/errors12 на unchanged limiter base; default retention/cap fixtures действительно FAIL независимо от нового constructor arg. После fix targeted39 PASS0.507s, включая новые14 и existing sliding/Owner reset/legacy/private ownership/paid no-replay/concurrent customer tests. Full1796 PASS96.795s/skipped16, compileall/OpenAPI55/diff PASS на isolated synthetic Git fixture; required CI/main/release ещё PENDING.
- **Ограничения и остаточные риски:** инженерные caps не измеренная RAM/capacity/SLA; process-local, idle map bounded до следующего обращения. R995-01 installed/read PENDING после отдельного deployment; parent482 pooling/cache/прочие scopes и #984/#989 runtime отдельно. Deployed18.10 operator-reported/independent VPS PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.
- **Связанные Issues:** #995, #482
- **Решение по Issues:** #995: keep_open, #482: keep_open
- **Следующий шаг:** full standard checks/required CI/security review/source-main checkpoint → отдельный RC/release-scope/health/fresh image/immutable publication/main/own audit; runtime в завершающем операторском блоке930.
- **Раздельные состояния:** merged=995 ещё не merged; published=RC31 без995; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15; accepted=targeted offline scoped PASS, full/CI/release/runtime PENDING, G-11 PARTIAL/NO-GO.

## Восстановление и метод

Предыдущий пакет завершён: checkpoint994/main27fc3d82c72564bbc961c8a2fcde562ccf5e06ea, required1782/3/final title/CLEAN/main1782/3/publisher40834995130 и independent main/Issue/source/tag/notes read-back2026-10-29T07:23:23Z PASS. Own989 final audit: https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/989#issuecomment-6490622592. Новый Issue995 создан до реализации после OPEN search limiter/SlidingWindowRateLimiter; дубликат не найден, parent482/#984/#989/#887 имеют другой scope.

Префиксы expired windows удаляются по возрастанию последнего accepted monotonic timestamp. OrderedDict имеет один узел на retained key; нет heap/tombstone/event-copy auxiliary history. Rejected/has_bucket не переупорядочивают и не продлевают retention. Live lookup не сканирует все активные keys; в худшем случае expired sweep ограничен4096 retained keys, каждый удалённый bucket освобождается единожды. В bucket не более limit timestamps. Full capacity отвергает новый key до allocation, не вытесняет активных пользователей и не очищает их budget. Reset только target по прежнему Owner guard; никаких фоновых задач, async work, worker или новых timers.

Монотонное время берётся из доверенного process clock; optional now используется offline и не поступает из Telegram input. Existing limit/window normalization и int key normalization прежние; constructor max_keys default4096 положительно нормализуется. Это event-loop/process-local гарантия, не обещание thread-safe или multi-instance quota. При остановленном процессе карта сама не испаряется, но не превышает bounds.

## Наблюдаемые регрессии и trust boundary

Новые14 tests: purge100 idle IDs чужим allow/has_bucket, default4096 cap, full-map existing budget/no eviction, denial vs expiry order, refresh и exact boundary, target-only reset/inspection no-allocation,250 поколений churn по9 IDs,240 retained events под1992 rejected unique keys, partial expiry и5000 decisions против простого oracle. Actual traffic_cb pressure возвращает прежний refusal до customer service/render; portal OFF/outside allowlist не выделяют state. Existing Owner guard/nonce/replay и authenticated identity tests PASS в targeted39.

Первый targeted39 завершился1 setup error: direct module invocation не добавил tests/ в PYTHONPATH для существующей cross-test provisioning fixture. Исправлен только isolated runner environment, source/tests не менялись; repeated39 PASS0.507s. Исходный лог сохранён отдельно. Preexisting SyntaxWarning device_model_resolver.py:33 не относится к limiter и не исправлялся. Фикстуры не копируют production .env/БД/ignored data; никаких provider calls, Telegram sends, billing/refund, VPS/host/DB operations или real polling/listeners.

## Source identity и документация

SHA-256 source/test pair в source commit a7356aff172fc84869862bc03e963b6c14535016: {"client_rate_limit.py": "e5df175e7ba93661b49559649dea830e374e9af7d98e284f5d0929a84beaf206", "tests/test_client_rate_limit_memory_995.py": "fb5008fa9da2ac984d7beb79066c9e9667cb7e529285fc19920324cff0aa3eb8"}. Source/test pair проверена git diff против указанного source commit; candidate ещё не main или Published. Historical panel-read raw972/977/984/989 и5 measured sources не меняются; limiter не входит в эту измерительную пятёрку. Ни fake RPS, ни bounded retained event counts не трактуются как production latency/RAM bytes.

README/UI/Client Setup/Admin Setup/V5 acceptance/CHANGELOG/Roadmap/registry синхронизированы. Runtime labels/commands/callbacks и route filters не меняются, новых operator setup действий/env/schema/deps/credentials/портов нет. После будущего разрешённого deployment R995-01 installed tag/SHA/health и ordinary existing-owner read; не создавать live pressure/Owner reset ради acceptance. При едином итоговом RC можно совместить это read-only evidence с R989-01, явно оценив оба scopes.

Первый full1796 за97.495s: FAIL2/errors1/skipped16. Обнаружена placement ошибка новой UI-секции: она стояла перед требуемым первым нормативным разделом; перенесена после него без изменения contract/tests. Два CLI baseline/import checks требовали Git provenance, а copy-only synthetic fixture не имела .git; runner теперь создаёт отдельный локальный synthetic Git commit без production config/global identity/remote. Source/tests bytes прежние, прежний FAIL сохранён; повтор полного suite и стандартных gates PENDING.

## Завершённые локальные gates

Full1796 PASS96.795s/skipped16 2026-10-29T07:39:45.095479+00:00, compileall/OpenAPI55/diff PASS. Предыдущий FAIL1796/2/1 сохранён выше; UI-section placement исправлен, CLI Git-provenance tests выполнены в synthetic Git fixture. Targeted39 PASS0.507s, новые14 покрыты в full; source pair байтово неизменна после исправления runner/docs. Independent candidate GitHub reconciliation PASS Published31/ref82/assert43/active43. Language/living/semantics/governance gates выполняются на итоговом metadata commit, required CI/main/release/runtime ещё PENDING.

Security review: server-authenticated actor по-прежнему проходит существующие portal/allowlist guards до limiter; full-map отказ не выделяет key и не сбрасывает чужое живое окно. Owner reset/nonce/replay и paid-success/provisioning/ownership paths не менялись. Byte comparison против base main подтверждает неизменность13 protected runtime/config/schema/lock/guard files;5 historical panel-read measured hashes прежние. Ни generic host shell, ни Docker socket, tokens/domains/fallback/cache/retry/mutation policy не затрагиваются. Source memory cap доступен существующему trusted constructor, не определяется callback/payload; optional now не клиентский input.
