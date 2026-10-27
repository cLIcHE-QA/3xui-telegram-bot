# #874 — декомпозиция XL до source-only реализации

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-27 11:39 UTC+03:00
- **Окружение:** GitHub / repository read-only discovery; без runtime/Telegram/VPS операций
- **Цель:** разложить #874 XL на ограниченные самостоятельные scopes до implementation по #930 и отразить точный OPEN Issue set.
- **Версия и immutable tag/SHA:** inspected main `da5736566457e5ed9b3420efe98823b14857e997`; Published `v5.0.0-rc.23` immutable `110bfc4ce9131a366be7ca3503e22ee6349c7372`. Нового runtime/tag/Release нет.
- **Scope:** discovery существующих audience.py/SQLite migration framework/Client Portal и собственных критериев #874/#501; планирование дочерних source scopes и будущих RC. Не implementation/delivery acceptance.
- **Фактический результат:** PASS
- **Источник и evidence:** [эпик #874](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/874), созданные [#947](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/947)/[#948](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/948)/[#949](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/949), обновлённый план [#876](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/876), policy prerequisite [#501](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/501). GitHub main/release/Issue read-back: rc.23 prerelease=true/draft=false; [main CI40473293747](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40473293747)/[idempotent Publish40473580801](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40473580801) SUCCESS.
- **Ограничения и остаточные риски:** все source implementations/собственные CI/publication и runtime acceptance новых частей PENDING. Private ID в users/import/admin create не доказывает private chat или consent. Mandatory/optional/default policy #501 не определена; media/CTA allowlists и live pilot требуют собственных evidence/разрешения. Мок и default-off не заменяют pre-implementation prerequisite зависимой функции.
- **Связанные Issues:** #874, #947, #948, #949, #876
- **Решение по Issues:** #874: keep_open; #947: keep_open; #948: keep_open; #949: keep_open; #876: keep_open
- **Следующий шаг:** required CI/squash merge/main read-back этого planning checkpoint, Issue state reconciliation; затем только #947/source foundation. Операторские policy/allowlists/pilot шаги в завершающем блоке #930, независимая разработка не ждёт их.
- **Раздельные состояния:** merged=нового implementation нет; этот docs PR ещё PENDING; published=v5.0.0-rc.23, без #874; deployed=v5.0.0-rc.18.10 `dae205ac82762723448f93827b981f89ae622231` только operator-reported, independent VPS read-back PENDING; accepted=planning/discovery scoped PASS, own source/runtime scopes PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## Самостоятельные части

1. **#947 / M / план rc.24:** additive bot migration + drafts/revisions/private-contact provenance и bounded candidate dry-run. API не подключён к runtime, нет worker/UI/transport; ledger пуст без trusted observation, users не backfill. Candidate count не даёт permission/consent; доставка всех категорий DENY_ALL.
2. **#948 / L / план rc.25:** durable queue/scheduler/lease/per-recipient state и recovery через isolated transport. Unknown/lost response не replay; rate/429/403/stop/DST/concurrency/large bounded snapshot проверяются fixtures. Никакого app_runtime/polling/Bot API wiring, category policy DENY_ALL.
3. **#949 / L / план rc.26:** Owner-only private admin UI, trusted observation и default-off adapter/integration. Непроверенные category policy/media/CTA/allowlists остаются disabled; pilot/fan-out/paid broadcasts не включаются. Собственные UI/abuse/privacy/операторские prerequisites сохраняются.

Один самостоятельный дочерний scope — один RC; parent #874 не получает пустого Release и не закрывается публикацией части. #876 переносится с прежнего будущего rc.25 на план rc.27, собственный scope не расширен; числа не зарезервированы и проверяются actual release-prep. Реальные emoji IDs/eligibility/operator pilot по-прежнему отдельно в конце.

Обнаружено: в проекте нет campaign subsystem и durable client-private observation ledger; существующие User Groups/audience.py пригодны для локального candidate filter, но не подтверждают право отправить сообщение. SQLite schema v15 сохраняется этим docs-only PR; будущие migrations только через штатный forward-only framework. Исторические audits/старый Roadmap blob не переписывались; нет Telegram sends, provider/host writes, deployment или смены общих G-11 gates.
