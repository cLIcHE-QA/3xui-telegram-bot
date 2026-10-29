# RC31 — публикация безопасного отказа client traffic read #989 / часть #482

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-28 22:11 UTC+03:00
- **Окружение:** GitHub required CI/main/publisher, isolated image build и read-only publication API; без production операций
- **Цель:** подтвердить immutable RC одной задачи989 и сохранить собственный отложенный installed/read acceptance, не закрывая parent482.
- **Версия и immutable tag/SHA:** v5.0.0-rc.31 `e74aabf827e5683c3528f9bd49e701a1ac17812c`, Published 2026-10-28T19:09:56Z, Release ID427082683; release992 tested head442ef4e1bcc005a2591b5c923d4834cab1fbd006.
- **Scope:** source/regression/security/required release CI/release-scope/official health/автоматическая публикация/immutable ref/version/notes/uniquePR/prerelease/source5 hashes/fresh release image. Не deployment/live failure/load или full v5 acceptance.
- **Фактический результат:** PASS
- **Источник и evidence:** [Release992](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/992) MERGED 2026-10-28T19:04:33Z; [required40749780492](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40749780492) SUCCESS ["Release scope: PASS, 1 PRs covered since v5.0.0-rc.30", "Ran 1782 tests in 218.638s", "OK (skipped=3)"], [final title40750799886](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40750799886) SUCCESS/actual CLEAN. [Main40750992534](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40750992534) SUCCESS ["Ran 1782 tests in 221.135s", "OK (skipped=3)"], [publisher40751764080](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40751764080) SUCCESS. Independent publication read-back 2026-10-28T19:11:06.687689+00:00 + отдельный connector Release/ref PASS.
- **Ограничения и остаточные риски:** этот publication checkpoint требует собственные required CI/merge/independent main read-back/own989 audit. R989-01 installed release/SHA/health/существующий private-owner traffic read PENDING до отдельного deployment; live failure/load не создавать. Parent482 другие scopes и #984 R984-01…03 отдельно; Deployed18.10 operator-reported/independent VPS PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.
- **Связанные Issues:** #989, #482
- **Решение по Issues:** #989: keep_open, #482: keep_open
- **Следующий шаг:** required CI/squash/independent main read-back publication checkpoint, own989 audit keep_open; затем следующий самостоятельный Issue-first scope482. R989-01 в завершающем операторском блоке930.
- **Раздельные состояния:** merged=source990/checkpoint991/release992; published=RC31 `e74aabf827e5683c3528f9bd49e701a1ac17812c`; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15, independent VPS PENDING; accepted=source/CI/image/immutable publication scoped PASS, own runtime989/984 и parent482 PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## Release path и immutable read-back

Release-scope локально и в required CI PASS1/1 since actual immutable30: единственный significant fix PR990 перечислен в canonical CHANGELOG31, exclusions нет. Local metadata96 PASS1.667s/compileall/OpenAPI55/language/living/semantics/governance/diff и independent reconciliation Published30/ref81/assert42/active42 PASS. Первый title был FAIL из-за unchecked code CI item; после фактического Python SUCCESS checklist обновлён, последний title SUCCESS/actual CLEAN. Gate не обходился.

Fresh official GitHub health непосредственно перед expected-head squash 2026-10-28T19:04:28.185650+00:00: Actions/Git Operations/API Requests/Pull Requests operational, unresolved0. Затем только штатный main Python и automatic Publish release; manual tags/releases/force-move/deployment не выполнялись. Проверены ref type=commit/SHA, raw APP_VERSION31, exact renderer canonical title/body, единственный merged release-prep992, prerelease=true/draft=false. Старые30 `7aa3514194675ae119a2e774e03da150025326b9` и29 `4422c8b5f1ff8d8a36343f9ef29becd213caab47` не изменились. Source5 SHA-256 на exact release совпали с raw989.

## Source/main и исходный FAIL

[Source review](2026-10-28-989-traffic-read-source-review.md) сохраняет pre-fix11 FAIL2/34, post-fix11/targeted94/full1782/16 и metadata96 PASS; native transport/malformed failures теперь дают constant sanitized domain error, не ложные нули. Успешные aliases/нули/DTO, cancellation/private-owner/Back и mutations/auth/TLS/admission прежние. Real XUI/fake Session tests подтверждают1/2 GET, закрытие sessions и aggregate budget; other adapter AST/XUI/domain/UI/lock/schema bytes unchanged.

[Source postmerge checkpoint](2026-10-28-989-traffic-read-postmerge-checkpoint.md) остаётся историческим PARTIAL: source990 main40745618678 FAIL на planned989 при уже MERGED990, publisher40745684867 SKIPPED. [Revalidation](2026-10-28-989-source-main-revalidation.md) фиксирует truthful checkpoint991 main5da950ac7389aeda58b34205688986f318bff7be, required1782/3/descendant main1782/3/reconciliation/idempotent publisher/read-back PASS. Старый FAIL не переименован и checkers/tests не ослаблялись; новый green main доказан отдельно до release-prep.

Actual17 new raw matrix15/driver32x2 на source3835/clean5 hashes сохраняют deterministic counts/routes/bytes/sessions/peaks/owners относительно984. Новый adapter hash1946daed529dff1bb2ab0167e7fd7e9917c08a2339243c35b544460451474b4c проверен на source/main/Release31; fake latency/CPU/RSS не panel/Xray capacity и не SLA. Historical972/977/984 raw/RC28 FAIL неизменны.

## Fresh release image и собственный acceptance

[Supply-chain40751063215](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40751063215) SUCCESS на exact release31 SHA. Artifact12843572563/digest `sha256:8e6bf0a5fad4a66c2a56dee5d136ac4c866148398e55fe3fc493b6c8b5d25121` независимо скачан и проверен; metadata.source_sha/lock `7ff99d772ca5807a23df68d8442707627e1f87a160813a7b7dcb448eab78633d`/base identity, SBOM dnspython2.9.0/ISC, Python/image actionable HIGH-CRITICAL0 и отсутствие CVE-2026-114605 подтверждены. Source image40745662736/artifact12841557023 был отдельным прежним source proof; этот release проверен заново, policy/deps не менялись.

Own989 criteria1…5 source выполнены; criterion6 immutable release состоялся, но последний publication checkpoint/Issue audit/main read-back ещё PENDING. Criterion7 R989-01 installed/read не доказан. #989 OPEN/keep_open; не создавать реальную недоступность панели/сети ради failure. Parent482 pooling/lifecycle/presentation cache/другие authoritative contexts/admin full-list/limiter/runtime и #984 R984-01…03 отдельно. Никаких Bot sends/Stars/refund/provider/host/VPS/production DB действий не было; G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## Продолжение checkpoint — 2026-10-29 (UTC+03:00)

Подготовленная 2026-10-28 публикационная сводка оставалась локальной: автоматическая проверка разрешений не выполнила команду подготовки PR из-за сообщения о workspace credits; фактический баланс не проверялся. После прямого указания оператора продолжить повторена штатная попытка без обхода review. Independent immutable publication read-back 2026-10-29T06:50:42.980433+00:00 подтвердил exact31/notes/version/unique992/source5 hashes, старые30/29 и Issue states. Local publication metadata96 PASS1.512s/compileall/OpenAPI55 относятся к уже подготовленному docs candidate; собственные PR CI/merge/main read-back и own989 audit ещё PENDING.

Local reconciliation 2026-10-29T06:52:14.402123+00:00: PASS Published31/referenced81/status42/active42; первый local запуск вернул UNKNOWN/URLError, повтор с системным SSL_CERT_FILE=/etc/ssl/cert.pem прошёл без изменения checker или TLS verification. Documentation semantics/governance/diff PASS. Versioned CHANGELOG sections и measured runtime5 hashes неизменны.
