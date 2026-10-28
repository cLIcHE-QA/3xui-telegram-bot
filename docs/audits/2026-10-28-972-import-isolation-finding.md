# #972 — own closure import gate FAIL, follow-up #977

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-28 10:48 UTC+03:00
- **Окружение:** локальный fresh CPython3.12 process без application environment, static code/import graph review, GitHub read-only evidence; без production операций
- **Цель:** проверить собственный criterion1 #972 перед completed: отсутствие config/app_runtime imports и implicit configuration input, а не только запуск CLI без обязательных env.
- **Версия и immutable tag/SHA:** Published v5.0.0-rc.28 `fad1fe6641f8fe190bd810ff51e04d91062c7ac7`; publication checkpoint main `fbb7c0cd11a9008244e5c3fdd91a1d06f0f894a2`, tool/provider/service files unchanged от Published tag.
- **Scope:** строгая import isolation development utility, transitive source graph и type-only usages. Не реальная утечка env contents, не production runtime/provider/DB/Telegram outcome и не повторный performance/load тест.
- **Фактический результат:** FAIL
- **Источник и evidence:** [Issue #972 criterion1](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/972), follow-up [#977](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/977) создан до кода, [publication #976](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/976) main/read-back PASS. Fresh-process runpy/sys.modules probe: app_runtime_imported=false, config_imported=true. Importer trace: provisioning requesting config.Settings. Повторный guarded probe с MetaPathFinder, установленным до module load: «Gate FAIL: attempted config import; blocked before module execution», exit2. Static customer_service.py/provisioning.py/config.py подтверждает graph/annotation-only dependencies/import-time load_dotenv. Значения env и содержимое конфигурации не инспектировались и не выводились.
- **Ограничения и остаточные риски:** старый CLI test с пустым env не доказывал отсутствия transitive imports/side effects. Counts/metrics/required CI/immutable publication сохраняют scoped historical PASS, но no-config acceptance FAIL; #972 не закрыт. Исправление только планируется; новый source/hash/regression/release нужен отдельно. Этот audit не устанавливает disclosure или production impact.
- **Связанные Issues:** #972, #977, #482
- **Решение по Issues:** #972: keep_open, #977: keep_open, #482: keep_open
- **Следующий шаг:** required finding checkpoint/CI/merge/independent main read-back, затем минимальный TYPE_CHECKING import repair #977 с fail-before-config regression/alias tests/full checks/new source baseline; отдельный immutable RC29 и повторный собственный closure audit972. Критерии не ослаблять, runtime/load/operator scopes482 позже.
- **Раздельные состояния:** merged=#973/#974/#975/#976, fix977 не реализован; published=RC28 `fad1fe6641f8fe190bd810ff51e04d91062c7ac7` immutable; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15, independent VPS read-back PENDING; accepted=publication scoped PASS, own import isolation FAIL/972 OPEN, parent budget/runtime PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## Что обнаружено / что остаётся доказанным

Publication #976 required Python40650461047/job122689083618 SUCCESS1751/3 за174.213s, final title40651008713/job122690802291 SUCCESS/actual CLEAN. Squash main `fbb7c0cd11a9008244e5c3fdd91a1d06f0f894a2` независимо fetched/read-back: Published28, active972/482 и registry keep_open, tag unchanged. Main40651215750/job122691465700 и idempotent publisher40651590504 затем SUCCESS. Эти факты остаются проверенными; они не доказывают дополнительный import gate.

Первоначальная CLI regression запускала tool без application environment и успешно получала report. Это проверяло отсутствие обязательных параметров/внешнего runtime, но не исключало implicit config import. Свежий собственный closure audit дополнил отрицательную проверку **до закрытия Issue**, обнаружил отличие от ожидаемого и сохранил #972 OPEN. Предыдущие [baseline](2026-10-28-972-panel-read-baseline.md), [source checkpoint](2026-10-28-972-panel-baseline-postmerge-checkpoint.md) и [publication audit](2026-10-28-rc28-publication-checkpoint.md) остаются историческими; ошибочное предположение о no-config scope исправляется этим новым finding/revalidation, не стиранием старых snapshots/notes/tag.

## Source/import evidence

Путь: benchmark-panel-reads → customer_provider_xui → customer_service → checkout_service/commerce → provisioning → config.Settings. В config module top level выполняется load_dotenv. Наличие этого побочного пути нарушает собственное no-config/no implicit env input обещание; app_runtime не импортируется, Bot/DB/provider listeners или запросы этой проверкой не запускались. Повторный import finder отклонил config **до исполнения module**, поэтому для воспроизведения defect не нужны реальные env values или файлы.

В CustomerPortalService CheckoutService/CheckoutSession/CommerceService/CommerceOrderRecord/Database/PlanRecord встречаются только в annotations; future annotations уже включены. Repository search не нашёл runtime get_type_hints или обращений к этим именам как customer_service runtime exports. Поэтому минимальный план — TYPE_CHECKING import guard без переноса DTO/error definitions, config stub, извлечения provider через AST/exec или замены реального runtime path в benchmark. Все DTO/error identities и behavioral call contracts проверяются regression до merge.

## Scope следующего fix

#977 — самостоятельный follow-up bug/RC29, не добавление новой product feature и не смена criteria972. Сначала сохранить этот finding checkpoint в main, затем доказать pre-fix fail-before-config и post-fix guarded import/CLI/worker/alias PASS в fresh process, полный suite и актуальные raw metrics/source hashes. Старый customer_service hash после изменения import layout не выдаётся за новый source; новый baseline snapshot добавляется отдельно.

До исправленного immutable RC не использовать старый tool как config-independent. Это development-tool import/contract defect; evidence содержит только публичные module names/контракт, без env contents/credentials/частных адресов. #972 criterion1 остаётся FAIL; child977/parent482 OPEN. Никаких permission waivers, secret rotation, deployment, network load или реальных Telegram/provider/host mutations для fix не требуется и не выполняется.
