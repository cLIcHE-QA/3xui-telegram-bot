# #887 — D3d one-time proofs для серверных сессий: post-merge checkpoint

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-26 08:09 Z (checkpoint после GitHub PR/main read-back; не утверждается как точное время merge)
- **Окружение:** GitHub PR Actions CI, read-only main/PR/source read-back; default-off offline/synthetic, без отдельной live staging среды
- **Цель:** проверить, что одноразовый D3d preflight опирается на проверенную D2a/D2b server-side session и не раскрывает реальный subscription URL
- **Версия и immutable tag/SHA:** PR #919 head `56ac900a1d77303b67c0504e17e4aff77a4f9173`; squash `main` SHA `489c358992d41f2b5e3d669651712e2a4bb14796`; Published `v5.0.0-rc.19` не включает D3d
- **Scope:** D2b `session_owner_from_cookie` переиспользует существующий session store; изолированный `SessionImportProofs` принимает session mode и cookie, получает owner из D2a `MiniAppSessions` или D2b `StandalonePilot`, повторно проверяет D3d policy, связывает SHA-256 proof digest с owner/session/mode, ограничивает TTL и rate/capacity. Synthetic negative tests покрывают unknown/wrong/revoked/expired session, cross-owner/cross-mode, replay, concurrent consume, flag/provider veto и ограничение запросов
- **Фактический результат:** PARTIAL — scope code/pre-merge tests PASS, issue-wide owner-bound subscription delivery и production acceptance PENDING
- **Источник и evidence:** [PR #919](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/919) и [Python checks](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40289771369), final [PR conventions](https://github.com/cLIcHE-QA/3xui-telegram-bot/actions/runs/40290129336) PASS на exact head; первоначальный PR conventions FAIL из-за незакрытого pre-CI checkbox исправлен после прохождения Python checks; post-merge push CI independently PENDING
- **Ограничения и остаточные риски:** нет HTTP route, подключения к runtime, ingress CSRF/origin/no-store/edge policy, atomic ledger для multi-worker, выдачи bearer URL, Copy/QR, реальных Telegram Bot API/устройств, версии клиента, staging DNS/TLS, VPS read-back. Process-local limits не подтверждают security реальной topology. `consume=true` — только preflight
- **Связанные Issues:** #887 OPEN/keep_open, #885 OPEN/keep_open, #473 и #497 остаются OPEN до собственных acceptance gates
- **Следующий шаг:** reviewed D2a/D2b ingress/session wiring и atomically stored one-time grants с origin/CSRF/rate/replay, отдельный серверный owner-bound URL endpoint с no-store и targeted IDOR negative tests; затем Copy/QR и физические WebView/device/staging проверки после операторского согласования
- **Раздельные состояния:** merged=PR #919 squash `489c358992d41f2b5e3d669651712e2a4bb14796`; published=`v5.0.0-rc.19` без D3d; deployed=`v5.0.0-rc.18.10` operator-reported, independent VPS read-back PENDING; accepted=offline scoped pre-merge CI PASS, full real import/G-11 PENDING/NO-GO

## Решение по Issues

- **#887: keep_open.** D3d one-use policy/source proof не создаёт URL или route; остаток — trusted ingress/session, shared atomic grants, real owner-bound delivery, reviewed client/version fallback, staging/device smoke. Следующий шаг — отдельный security-reviewed интеграционный PR и Roadmap checkpoint.
- **#885: keep_open.** HTTPS handoff #885 / draft PR #886 остаётся отдельным gate; D3d не заменяет его acceptance.
