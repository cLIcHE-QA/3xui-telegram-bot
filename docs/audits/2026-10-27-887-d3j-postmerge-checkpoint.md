# #887 — D3h/D3i/D3j: post-merge checkpoint без активации

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-27 02:11 UTC+03:00 (Europe/Moscow)
- **Окружение:** GitHub / CI / локальный offline Python3.12 и Node24; только synthetic fixtures
- **Цель:** проверить фактическую интеграцию D3h/D3i через #929, устранить пересекающиеся PR и синхронизировать Roadmap перед начальным RC #930.
- **Версия и immutable tag/SHA:** main squash `97270d8e354e3615fa49f484a41c218badd3bfc6`; PR head `be168f6823ac83532212bfc88aa84e9f7c867b65`, base `4dc6ff1b702ffba01492c6e915dcb84435d92bb6`; Published v5.0.0-rc.19 / `d738dd970f2215adc346a919c7ed182abaf454b1`.
- **Scope:** default-off исходники client-attestation intake/readiness, browser GET/POST Origin/CSRF, ClipboardItem, отдельная synthetic staging factory/private SQLite и неустановленный ingress template. Нет реального device, staging или production acceptance.
- **Фактический результат:** PASS
- **Источник и evidence:** [#929](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/929) MERGED и независимые PR/main read-back; [Python checks40417112584](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40417112584), [frontend40417112587](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40417112587), [финальный title40417642925](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40417642925) SUCCESS. Post-merge [Python40417682192](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40417682192) и [frontend40417682373](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40417682373): SUCCESS, независимо проверено на squash SHA.
- **Ограничения и остаточные риски:** этот PASS — scoped offline/PR CI и merge read-back. Статические source guards не доказывают физическую аттестацию, безопасный реальный edge или все возможные уязвимости. Private JSON 1:1, client/version/device evidence, staging TLS/session topology и production acceptance PENDING. Нет оснований закрыть #887.
- **Связанные Issues:** #887
- **Решение по Issues:** #887: keep_open
- **Следующий шаг:** провести этот docs-only checkpoint через required checks, squash merge и main read-back; затем отдельный release-prep rc.20 с накопленным scope #887/#890. Реальные staging/device шаги остаются в завершающем операторском блоке #930.
- **Раздельные состояния:** merged=#929 `97270d8e354e3615fa49f484a41c218badd3bfc6`; published=v5.0.0-rc.19 без D3j; deployed=v5.0.0-rc.18.10 `dae205ac82762723448f93827b981f89ae622231`, только operator-reported, independent VPS read-back PENDING; accepted=D3j offline scoped PASS, physical/staging PENDING, G-11 PARTIAL/NO-GO, public rollout BLOCKED.

## Проверки и substantive review

CI на точном PR head: **1557 Python tests, 3 skipped**, compileall, OpenAPI, command catalog, container и documentation gates PASS. Frontend: **33 Node tests**, TypeScript/Vite build, **57 browser + opt-in 2/2/1 PASS**; это synthetic Chromium/WebKit, не устройства оператора. Локально targeted **29/29**, full **1557 PASS, 16 skipped** (Nginx отсутствует), Node33/TypeScript/build, Living Docs, semantics/governance/language и base diff-check PASS. EOF whitespace исправлен до финального CI; старые результаты другого head для merge не использовались.

Reviewed trust boundary: owner получается из действующей server-side session, eligibility/CSRF проверяются отдельно, proof хранится в digest ledger. Read-only GET допускает отсутствующий Origin, но отклоняет явно чужой; mutating POST требует точный Origin и session CSRF. Clipboard write начинается в исходном user click до fetch, смена selection/unmount запрещает устаревший вывод; QR object URL отзывается. Синтетическая factory требует отдельный loopback/private SQLite, synthetic service/flags и общий доверенный session clock. Неподключённый Nginx template имеет exact preflight routes и `/deliver 404`. Production `app_runtime`, D2d runner и privilege domains не расширены.

Offline readiness: `status=BLOCKED`, candidates=7, reviewed=0, frontend/server delivery OFF, staging delivery DENIED, live requests=0. Shipping UI/server allowlists пусты независимо от manifest; документационная запись не активирует выдачу URL.

## Дедупликация и сохранение истории

Все **8 кодовых patches #928** сохранены в интеграционном snapshot. Manifest #927 идентичен; все **11 исходных test-функций** сохранены (в интеграции их 13), validator адаптирован к D3i. После подтверждённого merge #929 [#927](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/927) и [#928](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/928) закрыты как superseded; независимый read-back: CLOSED, merged=false, исходные head SHA сохранены. Удаление refs не выполнялось.

Подробные прежние D2/D3 сводки доступны в [immutable Roadmap до checkpoint](https://github.com/cLIcHE-QA/3xui-telegram-bot/blob/97270d8e354e3615fa49f484a41c218badd3bfc6/docs/ROADMAP.md) и существующих датированных audits. Текущая сводка заменяет их одним компактным агрегатом актуального этапа; исходный 5803-строчный архив не изменён. Разрешение #930 подтверждено #931/#932; post-merge Python для #932 [40416879628](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40416879628) SUCCESS. #930 CLOSED/completed; runtime #887 OPEN/keep_open.
