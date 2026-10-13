# Шаблон аудита (копировать в новый датированный файл)

<!-- audit-schema: 1 -->
- **Дата/время и часовой пояс:** YYYY-MM-DD HH:MM UTC+03:00
- **Окружение:** CI / offline / production read-only / operator-reported
- **Цель:** конкретный gate и проверяемая гипотеза
- **Версия и immutable tag/SHA:** vX.Y.Z-rc.N / 40-символьный SHA (либо N/A с причиной)
- **Scope:** что именно проверялось; что намеренно не проверялось
- **Фактический результат:** PASS / PARTIAL / PENDING / FAIL / BLOCKED
- **Источник и evidence:** URL PR / CI run / job / обезличенный operator report
- **Ограничения и остаточные риски:** нет подтверждения для ...
- **Связанные Issues:** #NNN (либо N/A с причиной)
- **Следующий шаг:** конкретная проверка или блокер
- **Раздельные состояния:** merged=...; published=...; deployed=...; accepted=...
