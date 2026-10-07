# v5 Client Portal Data Retention

Этот документ задаёт operational retention policy проекта для Client Portal v5. Он
нужен для privacy/data-minimization launch gate и не является юридической консультацией
или утверждением о применимом сроке хранения по законодательству конкретной страны.

## Принципы

1. Не хранить raw payment/webhook payload, токены, subscription URL или QR-изображения.
2. Хранить только поля, необходимые для payment integrity, entitlement/reconciliation,
   поддержки и расследования спорных операций.
3. Не удалять записи так, чтобы повторная доставка provider event могла создать второй
   платёж/entitlement либо потерять доказательство уже выполненного refund.
4. Доступ к bot SQLite/backup остаётся operator-only; customer UI читает только собственный
   account context.
5. Full Backup наследует тот же secret-bearing режим и отдельную backup-retention policy.

## Default retention для v5.0

### Пока customer account активен

Сохраняются:

- `users` / customer profile identity;
- активные и исторические `entitlements`;
- `commerce_orders` и `commerce_payments`;
- versioned `customer_terms_acceptance`;
- `stars_refund_operations`.

Это canonical audit/reconciliation ledger. Автоматический destructive purge этих таблиц
в первой версии v5.0 **не выполняется**.

### Payment webhook event journal

`payment_webhook_events` уже хранит только digest, нормализованные безопасные metadata
и processing/result state, а не raw payload.

Default operational target:

- applied/ignored events: **180 дней**;
- failed/uncertain events: **не удалять**, пока связанная проблема не закрыта оператором;
- записи, связанные с payment/order dispute или reconciliation finding, сохраняются вместе
  с соответствующим commerce ledger до закрытия finding.

Автоматический purge webhook journal не входит в первый canary: до отдельного
implementation PR удаление выполняется только контролируемым maintenance change с
предварительным backup и post-delete reconciliation.

### После прекращения customer relationship

Проектный default: customer-identifying данные могут быть очищены только отдельной
операторской процедурой после того, как:

1. нет active/pending/provisioning entitlement;
2. нет payment/refund/reconciliation finding;
3. истёк установленный оператором business/legal retention period;
4. создан проверенный backup;
5. purge не нарушает provider/payment idempotency.

Точный business/legal срок задаётся оператором deployment-а в соответствии с его
юрисдикцией и обязательствами. Repository не объявляет универсальный юридический срок.

## Что не должно попадать в retention store

Запрещено сохранять как часть customer/payment ledger:

- Telegram Bot token, Panel/API/Host Control/Deploy credentials;
- полный subscription URL или `sub_id` в payment/refund metadata;
- raw Telegram `SuccessfulPayment` object;
- raw webhook HTTP body;
- card/payment instrument details;
- QR PNG после отправки;
- произвольные support attachments без отдельной необходимости.

## Canary acceptance

До расширения allowlist оператор подтверждает:

- webhook journal действительно не содержит raw payload;
- customer/payment screens не раскрывают чужой Telegram/customer context;
- backup/recovery сохраняет ledger целостно;
- support/refund можно расследовать без shell-редактирования БД;
- retention policy согласована с реальными обязанностями deployment-а.

Policy review является closure для repository finding V5-A-004. Реальная production
retention/cleanup procedure остаётся operator responsibility и должна быть повторно
проверена перед broad public launch.
