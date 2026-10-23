# #473 — операторская проверка Happ/Shadowrocket и замечание к названию

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** 2026-10-23 14:27 UTC+03:00; сообщение пользователя 2026-10-23T11:27:38Z.
- **Окружение:** operator-reported client-side импорт iOS, Android и macOS; точные версии Happ/Shadowrocket и версии macOS не сообщены.
- **Цель:** записать результаты и исправить обнаруженную подмену названия подписки на VPN.
- **Версия и immutable tag/SHA:** draft [PR #882](https://github.com/cLIcHE-QA/3xui-telegram-bot/pull/882), base `db946755f2383352131a9520f40ee0ccf24018a9`; Published `v5.0.0-rc.18.10` tag `dae205ac82762723448f93827b981f89ae622231`, без #473.
- **Scope:** пользователь сообщил успешный импорт Happ/Shadowrocket для iOS/Android/macOS. На приложенном изображении видна группа `VPN` и шесть нод. Успех Shadowrocket на Android/macOS требует уточнения приложения и платформы, поскольку меню PR поддерживает Shadowrocket только на iOS. Скриншот не подтверждает отдельные VPN-connect/refresh на всех ОС.
- **Фактический результат:** PARTIAL по Issue #473: ручной импорт operator-reported PASS в заявленном scope; bug/UX finding — `remark=VPN` вместо title из 3x-ui, исправление в PR до отдельного regression smoke. Не end-to-end deployed bot PASS.
- **Источник и evidence:** [Issue #473](https://github.com/cLIcHE-QA/3xui-telegram-bot/issues/473), сообщение пользователя 2026-10-23T11:27:38Z со скриншотом; ссылки/токены/QR не перенесены.
- **Ограничения и остаточные риски:** локальный заголовок считывается read-only через `?format=info`; не проверены фактическая версия ПО, повторное импортирование с сохранением названия, client-side delete/duplicate behavior, опубликованный бот и security review.
- **Связанные Issues:** #473.
- **Решение по Issues:** #473: keep_open — CI, security review, Shadowrocket title regression smoke, бот end-to-end после отдельного релиза.
- **Следующий шаг:** проверить исправленный генератор, уточнить точные приложения/версии на Android и macOS и отдельным разрешением выполнить merge/release/deploy.
- **Раздельные состояния:** merged=NO; published=v5.0.0-rc.18.10; deployed=rc.18.10 operator-reported; accepted=operator-reported scoped import PASS, title regression PENDING, full v5 G-11 PARTIAL/NO-GO.
