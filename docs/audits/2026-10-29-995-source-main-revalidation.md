# Revalidation source/main #995 перед отдельным RC32

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-29 11:19 UTC+03:00
- **Окружение:** GitHub required CI/main/idempotent publisher/read-only source/Issue/ref API; production операций нет
- **Цель:** завершить собственный source/main scope995, сохранив старый PARTIAL audit как историю и отдельные release/runtime gates.
- **Версия и immutable tag/SHA:** checkpoint main `03525851650a694a749750ed6be768286cf8fdaf`; actual Published v5.0.0-rc.31 `e74aabf827e5683c3528f9bd49e701a1ac17812c` без995. Candidate APP_VERSION32 — release-prep план, не Published.
- **Scope:** source/main/required test/title/CLEAN/metadata identities/Issue audit; не release/deployment/runtime outcome.
- **Фактический результат:** PASS
- **Источник и evidence:** [Source checkpoint997](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/997) MERGED `03525851650a694a749750ed6be768286cf8fdaf`, tested head4ffda1aa4cd583faa58cc078c2dc7260fb075df1; required40839143051/job123331008314 SUCCESS1796/3 за119.454s, final title40839909877/job123333493915 SUCCESS/actual CLEAN. [Own main40839977453](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40839977453)/job123333710605 SUCCESS1796/3 за130.398s, idempotent publisher40840384220 SUCCESS. Independent main9 docs/yellow995/registry/OPEN43/source2/protected13 read-back 2026-10-29T08:13:35.080912+00:00 PASS; separate immutable31/version/notes/unique992/old30-29/source5 read-back2026-10-29T08:13:46Z PASS.
- **Ограничения и остаточные риски:** own release32/CI/scope/official health/fresh release image/immutable publication/main/own audit и R995-01 PENDING. Parent482 pooling/lifecycle/cache/прочие critical contexts/admin full-list и #984/#989 runtime отдельно. Deployed18.10 operator-reported/independent VPS PENDING; G-11 PARTIAL/NO-GO/public rollout BLOCKED.
- **Связанные Issues:** #995, #482
- **Решение по Issues:** #995: keep_open, #482: keep_open
- **Следующий шаг:** отдельный release-prep32 с required CI/release-scope/official health/штатным immutable publisher; затем publication checkpoint/main/read-back/own audit. Runtime в завершающем операторском блоке930.
- **Раздельные состояния:** merged=source996/main26302b7/checkpoint997/main0352585; published=RC31 без995; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15; accepted=source/main scoped PASS, RC32/own runtime PENDING, full v5 NOT PASS.

## История и source identity

[Source review](2026-10-29-995-client-limiter-source-review.md) и [исходный postmerge checkpoint](2026-10-29-995-client-limiter-postmerge-checkpoint.md) остаются прежними, включая PARTIAL при ещё не завершённом own main. Pre-fix14 FAIL3/12; targeted39/full1796/16/compileall/OpenAPI55 и последующие required/main1796/3 доказаны отдельно. Initial fixture imports/Git provenance/UI section placement/missing evidence link сохранены, code/checkers/gates не ослаблялись. Source2 SHA-256: {"client_rate_limit.py": "e5df175e7ba93661b49559649dea830e374e9af7d98e284f5d0929a84beaf206", "tests/test_client_rate_limit_memory_995.py": "fb5008fa9da2ac984d7beb79066c9e9667cb7e529285fc19920324cff0aa3eb8"}; protected13 и исторические5 panel-read hashes неизменны. Caps4096/limit events — process-local bound, не RAM bytes/capacity/SLA/distributed quota.

[Own source/main audit](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/995#issuecomment-6491530154) подтверждает criteria1…5;6 release/publication и7 R995-01 остаются PENDING, OPEN/keep_open. Не создавать live pressure/Telegram burst/Owner reset ради приёмки. Новый release-prep меняет только APP_VERSION/docs; schema17/lock/deps/env/ports/операторские credentials и source/test pair прежние. Actual31 не содержит995, номер32 назначается только этим отдельным release-prep после проверки отсутствия remote32 ref. Ручные tags/releases/deployments/реальные бот-процессы не запускаются.

## Локальный release-prep32 review

Metadata96 PASS1.850s/compileall/OpenAPI55/diff на isolated tracked synthetic Git fixture. Release-scope PASS1/1 значимого PR996 since actual immutable31/e74, exclusions нет. Independent candidate reconciliation PASS Published31/ref82/assert43/active43. Runtime/test pair995 неизменна; новые version-specific tests не нужны, действующие dynamic tests читают APP_VERSION32. Preexisting SyntaxWarning device_model_resolver.py:33 не относится к release scope. Собственные release CI/official health/immutable publication ещё PENDING.
