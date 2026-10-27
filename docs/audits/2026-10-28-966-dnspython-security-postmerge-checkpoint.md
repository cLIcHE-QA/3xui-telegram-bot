# #966 — dependency/image security revalidation перед RC27

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-28 01:12 UTC+03:00
- **Окружение:** GitHub / CI / чистые временные CPython3.12 environments / offline fixtures; без production операций
- **Цель:** подтвердить устранение source/image dependency blocker текущего пакета #876 и сохранить собственный отложенный runtime scope #966.
- **Версия и immutable tag/SHA:** source main `90d016b141a6c64208d0a150025966120903c425`, APP_VERSION 5.0.0-rc.26; RC27 tag N/A — ещё не подготовлен/Published. Текущий Published RC26 `b2f7503387fc7bd8465e783c898a0697ec87c541`.
- **Scope:** минимальный dnspython floor/lock, clean hashed install, DNS wire/Answer API regression, full/required CI, image/license/SBOM/actionable gate и own Issue audit. Не фактический installed/deployed package или live DNS/Telegram outcome.
- **Фактический результат:** PASS
- **Источник и evidence:** [#968](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/968) exact head `96857a52cf68a5697b2658ae1e4d7c1385aa9d93`, squash `90d016b141a6c64208d0a150025966120903c425`, MERGED 2026-10-27T22:10:25Z. [Python40591816964](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40591816964)/job122497708223 SUCCESS, 1741/3 skipped за212.525s; [final title40592552051](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40592552051)/job122500216898 SUCCESS; actual CLEAN/test/title/audit подтверждены перед squash. [PR Supply-chain40591816948](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40591816948)/job122497708357 и [fresh main40592730799](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40592730799)/job122500820088 SUCCESS. Main Python40592730791/job122500819782 PENDING на момент01:12; required PR PASS не объявляется этим push результатом.
- **Ограничения и остаточные риски:** RC27/publication/main checkpoint ещё PENDING. #966 own acceptance6 требует отдельно разрешённого deployment и read-only installed dependency/image tag/SHA/DNS API/health outcome; DNS load/DoS и новые опасные mutations не нужны. #876 требует собственного emoji eligibility/IDs/deployment/targeted rendering/fallback. Source/image PASS не подтверждает устранение риска на VPS.
- **Связанные Issues:** #966, #876
- **Решение по Issues:** #966: keep_open, #876: keep_open
- **Следующий шаг:** required CI/merge/independent main read-back этого source/security checkpoint; затем отдельный RC27/release-scope/health/automatic publication/Issue checkpoint выбранной задачи #876 с обязательным prerequisite #966. После publication checkpoint — #482; runtime gates остаются в завершающем операторском блоке.
- **Раздельные состояния:** merged=#965/#968; published=RC26 `b2f7503387fc7bd8465e783c898a0697ec87c541`, RC27 PENDING; deployed=rc.18.10 `dae205ac82762723448f93827b981f89ae622231` operator-reported/schema15, independent read-back PENDING; accepted=source/build/security scoped PASS, #876/#966 runtime PENDING, G-11 PARTIAL/NO-GO/public rollout BLOCKED.

## Reproducible dependency review

Direct floor>=2.9,<3; exact lock2.9.0. Канонический pip-tools7.6.1 в отдельном чистом CPython3.12 с resolver=backtracking/generate-hashes/strip-extras сохранил все остальные pins/hashes/base image. Ручного редактирования transitive hashes не было. Официальные PyPI metadata: requires_python>=3.11, wheel/sdist не yanked; runtime уже3.12. License expression ISC прежнего dependency family, новой интеграции нет.

Два полных SHA-256 в generated lock совпали с official PyPI: universal wheel `9a4aedb833c3c1b49214d04d44d3032ab7a9135f7c1d29a549b4ff78fd82fda9`, sdist `b44dc6b18f07a8b1c56676a19fbfdb5209415b046a9cece286baafa87ff3f7f1`. В отдельном чистом runtime полный `--require-hashes` install и pip check PASS, installed dnspython2.9.0.

Локально targeted DNS/dependency/supply-chain22 PASS за0.033s; full1741/16 environment skips PASS за93.605s. Tests используют только documentation addresses/локальные wire packets и fake Resolver с настоящим dns.resolver.Answer API, без сети. Нормальный compressed wire roundtrip сохраняет A/AAAA/TTL; dns_summary сохраняет bounded types/timeout/partial NXDOMAIN/LifetimeTimeout/no-answer behavior. Первый hand-built Answer fixture исправлен через нормальный wire parse/index, production DNS код не менялся. Compileall/OpenAPI55/command catalog/living/language/semantics/governance/diff PASS.

## Actual scanner/license/SBOM evidence

PR artifact12773189951, digest `sha256:6af0baa6af682710d6a68a7eb7d62619ee5a989df1acace860f38c1dbe31eb43` независимо скачан: metadata.source_sha совпадает с exact head96857a5, lock SHA-256 `7ff99d772ca5807a23df68d8442707627e1f87a160813a7b7dcb448eab78633d` совпадает с файлом; container SBOM dnspython2.9.0/ISC, license inventory notice/ISC, CVE-2026-114605 отсутствует, actionable HIGH/CRITICAL0. Hashed install/pinned scanner/build/license/image/SBOM/actionable gate/upload SUCCESS.

Fresh main artifact12773538404 на source `90d016b141a6c64208d0a150025966120903c425`, digest `sha256:88b19f6daedeef3644f9ded48d13baff3e06db1eacb8741f93ed1ac87d5ff6a8`, SUCCESS. Independently прочитаны run/jobs/artifacts; PR head и source squash имеют одинаковый Git tree `e49554aa3a412d906797960ce85cfdac938d7b38`, код/lock/license review применим к обоим. Старый [FAIL40588425118](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40588425118) и [source/finding audit](2026-10-28-876-client-theme-postmerge-checkpoint.md) неизменны; новый PASS — revalidation, не ретроспективное стирание finding. Severity thresholds/CVE ignores/waivers не менялись.

## Own acceptance / дальнейшие состояния

Сверены критерии #966: floor/hash regeneration; offline DNS/full/required CI; fresh image gate; living docs/release-scope/main checkpoints; immutable RC/publication; собственный отложенный read-only deployed package/DNS/API/health. Первые source/build gates scoped PASS, publication и последний runtime outcome PENDING; Issue OPEN/keep_open. Критерий runtime уточнён в Issue до implementation PR согласно #930, не требует опасных дополнительных mutations или полного v5 acceptance.

#876 source UI/CAS/context/typed UTF-16/one-send guards покрыты общим full suite на новом lock. Реальные bot rights/IDs/physical Telegram/pilot не выполнялись, #876 OPEN/keep_open. В RC27 включаются #965 и необходимый #968 без release-scope exclusion; выбранная продуктовая задача остаётся #876. Следующая #482 начинается только после publication checkpoint/independent main read-back. Deployed, Published и Accepted различаются; прежние HWID scoped PASS/waived burst не повторяются.
