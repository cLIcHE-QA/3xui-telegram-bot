# Адресная приёмка rc.16.2 и план следующего патч-RC

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-17 11:58:39 UTC+03:00 — операторский отчёт; документальный checkpoint 2026-10-17 12:28 UTC+03:00
- **Окружение:** production, operator-reported; GitHub read-back — отдельно
- **Цель:** сверить результаты S/A–I/Z с индивидуальными Issues #691/#705/#719/#721/#724, оценить B5, назначить реализацию #734/#730/#731 на план `v5.0.0-rc.16.3`
- **Версия и immutable tag/SHA:** Published `v5.0.0-rc.16.2`, `a95b43f2e3322c5d42ee74509727686bf9be5cf2`; docs base main `2c35796c23bd60a90136c75d25314341e4e8c9be`
- **Scope:** S1–S9; A1–A7 (A2=MATCH); B1–B8; C1–C7; D1–D6; E1–E4; F1–F8; G1–G7; H1–H8; I1–I4; Z1–Z4. Не проводилась независимая VPS/DB/image attestation, скриншоты и raw logs не передавались; отдельные V5-A-001/002/003 не проверялись.
- **Фактический результат:** **PARTIAL**: S1–S9, A1/A3–A7, B1–B4/B6–B8, C1–C7, D1–D6, E1–E4, F1–F8, G1–G7, H1–H8, I1–I4, Z1/Z2 — PASS со слов оператора; A2 — MATCH; **B5 BLOCKED**: «в клиентском портале сейчас пропали все тарифы». Z3=PARTIAL, Z4=B5.
- **Источник и evidence:** операторское сообщение 2026-10-17T08:58:39Z; immutable [Release rc.16.2](https://github.com/cLIcHE-QA/3xui-telegram-bot/releases/tag/v5.0.0-rc.16.2); [PR #727](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/727), [Roadmap PR #728](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/728); scoped comments и GitHub close #691/#719/#721/#724; [#731](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/731) для B5.
- **Ограничения и остаточные риски:** raw deployed runtime SHA не предоставлен, независимая attestation не проведена. В части B5 возможна действующая ручная выдача, конфигурация Stars/visibility или membership/groups; root cause **не установлен**, не утверждать, что исправление #731 окончательно устраняет исчезновение тарифов при любой причине. Условия User Groups `all/groups/admin_only` должны оставаться fail-closed; публичный rollout запрещён.
- **Связанные Issues:** #691/#719/#721/#724 — закрыты `completed` по собственному операторскому targeted PASS; #705 — OPEN/B5; #731 — OPEN; #730 и #734 — OPEN с новой политикой/UX; PR #729/#732/#733 — OPEN, required checks для каждого перед merge подтверждать заново.
- **Следующий шаг:** docs-only sync + CI/merge и независимый main read-back; затем отдельно разрешённые merge runtime PR, будущий `v5.0.0-rc.16.3` release/deployment и targeted B5/manual HWID/copy smoke; проверка post-health.
- **Раздельные состояния:** merged=только прошлые implementation PR для rc.16.2; published=immutable rc.16.2 PASS; deployed=rc.16.2 operator-reported; accepted=#691/#719/#721/#724 scoped PASS; #705/B5 PARTIAL/BLOCKED; G-11 PARTIAL/NO-GO.
