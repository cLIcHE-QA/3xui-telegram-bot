# #887 — D3d owner eligibility preflight post-merge checkpoint

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-26 07:45 Z (время запроса оператора на merge; GitHub read-back после merge, отдельная точная метка CI здесь не утверждается)
- **Окружение:** GitHub PR CI, `main` GitHub read-back; isolated offline/source-only D3d, без live staging/production
- **Цель:** подтвердить D3d default-off policy preflight и status после squash merge, не принимать policy predicate за реальную server-side выдачу subscription URL
- **Версия и immutable tag/SHA:** PR #917 exact head `92db416817fc4061bc4c1144a6711ba75e4d77b8`; squash `main` SHA `7c9c1bcf64e203f5f9803611eca0740833b0eedd`; Published `v5.0.0-rc.19` без D3d
- **Scope:** `subscription_page_import_preflight.py` с явным default-off, проверкой trusted server-side owner ID, pilot allowlist, свежих flags/profile и active/active; `tests/test_subscription_page_import_preflight.py` c synthetic negative fixtures. No real bearer URL, owner session wiring, HTTP route или deployment
- **Фактический результат:** PARTIAL — pre-merge required `PR conventions` и `Python checks` PASS; squash MERGED, real import acceptance PENDING
- **Источник и evidence:** [PR #917](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/917) merged, exact-head GitHub Actions required checks PASS; независимый GitHub commit/main/file read-back на squash SHA. Post-merge push CI отдельно PENDING: PR-only lookup не даёт доказательства push runs
- **Ограничения и остаточные риски:** `permitted=true` не выдаёт URL; отсутствуют trusted D2a/D2b session binding, one-time grants, повторная owner revalidation при выдаче, edge throttling/replay controls, Copy/QR и iOS/Android/Telegram WebView device smoke; D2e staging и VPS read-back не проведены
- **Связанные Issues:** #887 OPEN / keep_open; #885 OPEN — независимый HTTPS handoff; #473/#497 требуют своих gates
- **Следующий шаг:** отдельно реализовать проверенную привязку identity к серверной сессии, bounded one-time grants и replay/IDOR/rate/no-store tests без live rollout; затем согласовать live staging и targeted physical-device acceptance
- **Раздельные состояния:** merged=PR #917 SHA `7c9c1bcf64e203f5f9803611eca0740833b0eedd`; published=`v5.0.0-rc.19` без D3d; deployed=`v5.0.0-rc.18.10` operator-reported без independent VPS read-back; accepted=offline code/CI scoped PASS, real import/G-11 PENDING

## Решение по Issues

- **#887: keep_open.** D3d policy preflight source-only; не подключён к доверенной сессии и не выдаёт URL. Остаток: one-time/owner-bound delivery, защита повторов, реальные Copy/QR, staging и device smoke; актуализация Roadmap после каждого gate.
- **#885: keep_open.** HTTPS handoff/PR #886 отдельная задача, D3d его не закрывает.
