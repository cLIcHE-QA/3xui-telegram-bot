# #885 — актуализация HTTPS handoff и offline review

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-27 09:02 UTC+03:00
- **Окружение:** локальный Python3.12 / synthetic fixtures / ephemeral loopback HTTP, без Telegram/VPS/provider
- **Цель:** актуализировать #886 от Published rc.20, проверить owner/private, точный import payload, TTL/replay/HEAD и честный UI fallback до CI/merge.
- **Версия и immutable tag/SHA:** Published v5.0.0-rc.20 `929e9950a9d831ef72271f99b226a3315cfef709`; main checkpoint #935 `50788872fba87c7d1c5b78f45a430b902e3a5ffb`; прежний #886 head `432369d2484f48ce3cb2cb1d1ebe2fb1b340e33d`; новый PR head/CI PENDING до GitHub read-back.
- **Scope:** HTTPS ticket поверх существующего compatibility proxy; строгая привязка к owner URL/client/platform/title через import_uri, no-store HTML/CSP, Copy/QR/Back и синтетические negative tests. Это не новый auth/provider protocol или device acceptance.
- **Фактический результат:** PARTIAL
- **Источник и evidence:** [Issue #885](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/885), [PR #886](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/886); локальный targeted suite 29/29 PASS (#885 и #473), compileall запущен; полный suite и fresh required CI PENDING.
- **Ограничения и остаточные риски:** ticket является кратковременным bearer-like credential, HTTP не переаутентифицирует Telegram owner; process-local только один bot/proxy процесс, restart/другой worker теряют билет. Telegram/WebView может блокировать auto-open/custom schemes, real import/refresh/device outcome PENDING.
- **Связанные Issues:** #885
- **Решение по Issues:** #885: keep_open
- **Следующий шаг:** полный repository suite, свежий PR head/CI и substantive review, затем разрешённый squash merge, post-merge Roadmap checkpoint и отдельный rc.21 release-prep. Операторский deployment/device scope остаётся в конце пула #930.
- **Раздельные состояния:** merged=#885 NO; published=v5.0.0-rc.20 без #885; deployed=v5.0.0-rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported, independent VPS read-back PENDING; accepted=targeted offline 29/29 PASS, required CI/live PENDING, G-11 PARTIAL/NO-GO, public rollout BLOCKED.

## Review и границы

Старую ветку #886 обновили merge актуального main без force-push. Семь конфликтов release-state docs/checker разрешены каноническими main версиями, устаревшие изменения rc.19 projection не перенесены; собственный handoff код и UI сохранены. #935 publication checkpoint уже merged/main read-back PASS до начала этого scope.

В pre-merge review усилены проверки внутри scope #885: одного scheme prefix недостаточно, ticket создаётся только для точного существующего import_uri по тем же owner URL/platform/client/title. HEAD/POST/query и неканонический percent-encoded path не потребляют валидный ticket и не раскрывают URI; replay/expiry возвращают no-store/no-referrer отказ. При невалидном/отсутствующем template Copy/QR/Back сохраняются без отсутствующей кнопки или инструкции нажать её. Owner/private negative и фактический synthetic HTTP test подтверждают отсутствие provider fetch. Slash-команды и schema не менялись.

Первый targeted запуск соседних #473 UI tests без fake environment завершился ошибкой конфигурации до behavior; self-contained #885 UI fixture импортирует handler под явно синтетическим окружением, последующий общий targeted29 PASS. Найденный недействующий README anchor заменён устойчивой ссылкой на канонический Client Setup. Реальные токены, URL и данные не использовались.

Ticket TTL90/limit256 — ограничение доступа, не гарантия физического стирания Python памяти. Никто не обещает seamless WebView import или scoped device PASS по offline suite. До позднего rollout оператор проверяет TLS/no-log/no-store/CSP на действующем ingress и собственный targeted device/import/refresh; текущий PR не выполняет эти операции.
