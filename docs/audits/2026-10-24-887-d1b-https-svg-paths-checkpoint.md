# D1b #887 — checkpoint статических SVG-путей на HTTPS admin origin

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-24 18:57 UTC+03:00 (начало проверки)
- **Окружение:** GitHub connector, исходники Draft PR #896, offline path contract и synthetic Nginx-тесты; VPS, DNS, production-сертификаты и работающий listener не применялись
- **Цель:** устранить расхождение между `SafeSvgIcon` и закрытым Nginx ingress без предоставления публичного доступа к произвольным `/client-icons/`
- **Версия и immutable tag/SHA:** base `main` `f8ff9a18125e24813f9974531e5257d0f8258534`; исходный D1b head `3062534eff34ffa089d2721f4b7aa6cab444cb8f`; Published `v5.0.0-rc.19` `d738dd970f2215adc346a919c7ed182abaf454b1` (без D1b)
- **Scope:** read-back всех 39 SVG в `public/client-icons/library/` и точного `public/client-icons/incy.svg`, Nginx exact/regex locations и отрицательные пути `INCY-LICENSE.txt`, `incy-monochrome.svg`, `.map`, скрытые файлы, path suffix. `nginx -t` с synthetic cert не отключён. `app_runtime`, `/compat/`, admin API, реальные TLS ключи и production не изменены
- **Фактический результат:** PARTIAL — несовместимость подтверждена по GitHub source, исправление и тест находятся в Draft PR; required `test/title`, специализированный `frontend-model` и независимый GitHub read-back нового head ещё требуют подтверждения. Не объявлять VPS/TLS PASS
- **Источник и evidence:** [PR #896](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/896), [Issue #887](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/887), `web/subscription-page/src/staticSvgPaths.ts`, `deploy/subpage-admin/nginx-d1b-admin.conf.example`, `tests/test_d1b_https_edge_contract.py`, [предыдущий audit](2026-10-24-887-d1b-hermetic-recovery-https-edge-checkpoint.md)
- **Ограничения и остаточные риски:** статический контракт и `nginx -t` не доказывают HTTP 200 на реальном HTTPS origin, SNI/Host/Origin, rate-limits, независимый DR, key custody, HA, deployment, публикацию страниц или device/WebView acceptance. Example не одобряет production
- **Связанные Issues:** #887: keep_open (PARTIAL/PENDING); #885 и #890 — отдельные OPEN, вне этого scope
- **Следующий шаг:** подтвердить `test/title/frontend-model` на exact PR head, независимо прочитать файлы/refs/CI, сохранить PR Draft. Реальный VPS smoke только после отдельного разрешения; Roadmap sync после разрешённого merge
- **Раздельные состояния:** merged=D0/D1a в `main`, D1b Draft NOT MERGED; published=`v5.0.0-rc.19` immutable; deployed=`v5.0.0-rc.18.10` только operator-reported, независимый VPS read-back PENDING; accepted=path-contract offline PARTIAL до нового CI, полный #887 PENDING, G-11 PARTIAL/NO-GO
