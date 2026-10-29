# Postmerge checkpoint #995: source limiter memory и отдельный release/runtime остаток

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-29 10:55 UTC+03:00
- **Окружение:** GitHub required PR CI и read-only source/main API; production операции отсутствуют
- **Цель:** зафиксировать фактический source merge и отделить source/main CI, release/publication и runtime gates.
- **Версия и immutable tag/SHA:** source main `26302b7385a1f887274fc244c4ab1fda8707e1f1`; actual Published v5.0.0-rc.31 `e74aabf827e5683c3528f9bd49e701a1ac17812c` не содержит995; APP_VERSION31/schema17/lock прежние.
- **Scope:** source merge/required CI/11 changed blobs/13 protected identities/2 source-test hashes; не completed release, deployment или runtime acceptance.
- **Фактический результат:** PARTIAL
- **Источник и evidence:** [Source PR #996](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/996) MERGED `26302b7385a1f887274fc244c4ab1fda8707e1f1`, tested head e94edfdec245f4bdda15fe1807f617fb2e198e7d. [Required40837454202](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40837454202)/job123325482393 SUCCESS1796/3 за193.772s; final title40838114644/job123327633062 SUCCESS/actual CLEAN. Independent API read-back 2026-10-29T07:53:08.274787+00:00 подтвердил actual main/11 changed Git blobs exact,13 protected runtime/config/schema/lock/guards unchanged и2 raw source/test SHA-256 match. [Source main40838168222](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40838168222)/job123327811420 SUCCESS1796/3 за160.810s, idempotent publisher40838608515 SUCCESS; read-back2026-10-29T07:56:55Z.
- **Ограничения и остаточные риски:** этот docs checkpoint/required CI/merge/собственный main/read-back PENDING; отдельный RC/release-scope/health/fresh image/immutable publication/own audit PENDING. R995-01 installed/read, parent482 прочие scopes и #984/#989 runtime отдельно. Deployed18.10 operator-reported/independent VPS PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.
- **Связанные Issues:** #995, #482
- **Решение по Issues:** #995: keep_open, #482: keep_open
- **Следующий шаг:** завершить этот docs checkpoint/read-back, затем отдельный release-prep одной задачи995; никаких других значимых задач до source/main sync. Runtime в завершающем операторском блоке930.
- **Раздельные состояния:** merged=source996/main26302b7; published=RC31 без995; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15; accepted=source/required CI/read-back scoped PASS, docs checkpoint/release/runtime PENDING, full v5 NOT PASS.

## Source и история проверок

[Source review](2026-10-29-995-client-limiter-source-review.md) сохраняет pre-fix14 FAIL3/errors12 за1.408s, post-fix targeted39 PASS0.507s, full1796 PASS96.795s/skipped16/compileall/OpenAPI55/static. Initial runner imports/Git fixture, UI section placement и missing evidence link не скрыты; code/gates не ослаблялись. Первый title996 имел ожидаемый unchecked CI item; после фактического Python SUCCESS item отмечен, latest title SUCCESS/actual CLEAN, tested head не менялся.

Source commit a7356aff172fc84869862bc03e963b6c14535016 и final head e94edfdec245f4bdda15fe1807f617fb2e198e7d имеют те же runtime/test bytes, что actual squash main. Source hashes: {"client_rate_limit.py": "e5df175e7ba93661b49559649dea830e374e9af7d98e284f5d0929a84beaf206", "tests/test_client_rate_limit_memory_995.py": "fb5008fa9da2ac984d7beb79066c9e9667cb7e529285fc19920324cff0aa3eb8"}. Остальные13 protected files и5 historical panel-read measured sources прежние; old raw/audits не редактировались. Bound4096 keys/limit events — process-local инженерная защита; fake churn/5000 oracle decisions не production capacity/RAM bytes/SLA. Auth/Owner reset/private-owner/paid lifecycle/provider mutation-no-replay/TLS/schema/deps не менялись.

## Текущий оставшийся acceptance

#995 offline criteria1…4 выполнены. Criterion5 требует завершить docs checkpoint/main read-back; source/main CI отдельно PASS;6 отдельный RC/publication/own audit,7 R995-01 exact installed tag/SHA/health + ordinary existing-owner read после отдельного deployment. Не создавать live pressure/Telegram burst/новые IDs/Owner reset ради acceptance; эти boundaries доказаны offline. Можно совместить позднее read evidence с R989-01 на одном итоговом RC при явном outcome обоих scopes. #995 и parent482 OPEN/keep_open; #984/#989 собственные runtime outcomes отдельно. Никаких bot polling/listeners, VPS, payment/refund, Telegram sends, provider/host/production DB writes или ref deletion не было.

## Metadata review source checkpoint

Local metadata96 PASS1.699s на isolated tracked synthetic Git fixture. Source/main и publisher фактически PASS по указанному immutable26302b7, поздняя публикация31 не считается включением995. Этот docs-only change не меняет source/test hashes; требуются собственные required CI/merge/own main/read-back до release-prep.

Independent candidate reconciliation PASS Published31/ref82/assert43/active43; source/test pair byte identity unchanged vs verified actual source main26302b7. Эта docs сверка не является новым runtime scope.
