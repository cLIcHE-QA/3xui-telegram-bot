#### Региональные проверки с помощью сети проб Cheburcheck

**Статус: ⬜ Отложено. Не является блокером `v4.23.3`, `v4.24.0` или обязательным условием перехода к `v5.0.0`.**

Текущий minimal self-hosted Cheburcheck runtime (`website + PostgreSQL`) достаточен для static list/ASN diagnostics, но не даёт реальных региональных результатов без подключённых Probe reporters. Bot начиная с `v4.23.3` должен честно показывать отсутствие active scanners и не эмулировать regional data.

Цель отложенного улучшения — добавить собственный controlled Probe fleet без смешения его lifecycle с Telegram-ботом.

Рекомендуемая реализация в два этапа:

1. **Pilot.**
   - добавить central RMQTT к существующему self-hosted Cheburcheck runtime;
   - связать `website` с broker через отдельный `MQTT_ADMIN_TOKEN`;
   - предоставить probes только authenticated MQTT over WebSocket/TLS endpoint;
   - зарегистрировать один controlled Probe reporter с отдельными `PROBE_ID` / `PROBE_TOKEN` и metadata `region / ASN / provider`;
   - запустить probe на отдельном Linux/Docker host с outbound-only connectivity к broker и только необходимым `NET_RAW` capability;
   - подтвердить end-to-end path: Telegram check → Cheburcheck probe task → MQTT → reporter result → SSE → compact regional summary.

2. **Fleet.**
   - после успешного pilot развернуть несколько независимых reporters в разных сетях/регионах; ориентир для полезного первого fleet — минимум 3–5 probes, а не несколько probes в одном дата-центре;
   - выбирать точки так, чтобы они измеряли действительно разные network paths/ISP/regions, а не только разные VPS одного provider-а;
   - добавить health/readiness для online/offline reporters, `last_connected_at`, версию probe и безопасный operational inventory;
   - определить lifecycle credential rotation/revocation для каждого reporter отдельно;
   - зафиксировать controlled update/rollback procedure для probe packages/images;
   - при необходимости расширять fleet постепенно, не меняя Telegram result contract.

Граница безопасности и эксплуатации:

- RMQTT не должен принимать anonymous/unrestricted clients;
- каждый reporter имеет отдельные ID/token; token не переиспользуется между probes и не совпадает с bot/3x-ui/Host Control/Deploy Agent credentials;
- broker/admin token и probe tokens не хранятся в Telegram, Git или bot SQLite;
- bot не получает shell/container control над RMQTT или Probe hosts и только читает Cheburcheck API/SSE;
- Probe hosts не требуют публичных inbound management ports для обычной работы; основной data path — исходящее WSS/MQTT соединение;
- capability `NET_RAW` выдаётся только probe process/container и не означает общий privileged/root runtime;
- отсутствие части fleet или timeout отдельных reporters не должно превращать static Cheburcheck verdict в ошибку;
- UI показывает только фактически полученные regional responses и явно различает `нет активных сканеров`, `нет ответов` и `regional upstream unavailable`;
- backup/recovery для broker config, reporter registry/tokens и probe deployment является отдельной infrastructure responsibility и не включается автоматически в Full Backup Telegram-бота.

Этот пункт считается отдельной infrastructure-задачей средней сложности. Сам probe runtime лёгкий, но production-ready fleet требует broker/TLS/auth, нескольких независимых точек наблюдения, credential lifecycle, monitoring и runbook'ов.

### Усиление правил сопровождения публичного репозитория

**Статус: ✅ Выполнено 2026-10-07. A-007 технически закрыт полностью.**

После перевода repository в public GitHub-side governance подтверждён двумя active rulesets.

Branch ruleset **Protect main release path** (ID `24575428`):

- PR обязателен;
- merge только `squash`;
- strict required checks `test` и `title`;
- deletion и non-fast-forward запрещены;
- linear history обязательна;
- bypass actors отсутствуют.

Tag ruleset **Protect release tags** (ID `24615100`):

- target: `refs/tags/v*`;
- применение правил: активно;
- `update`, `deletion` и `non_fast_forward` запрещены;
- bypass actors отсутствуют;
- `current_user_can_bypass=never`;
- creation новых release tags не запрещена, поэтому штатный release workflow сохраняет возможность публиковать новые `vX.Y.Z`.

После включения ruleset существующий `v4.26.8` по-прежнему указывает на `e096bf436425ea037399e290a5a54f54c729b352`.

A-007 больше не имеет residual accepted risk: branch и release-tag paths защищены GitHub-side enforcement, а release workflow остаётся единственным штатным способом публикации новых tags/releases.

### v5.0.0 — Client Portal — Клиентский портал

**Статус: 🟠 Опубликовано; acceptance отложен (controlled-canary `v5.0.0-rc.9`).** Backend foundation и pilot Client Portal опубликованы в immutable prerelease; production deployed `rc.9` подтверждён только оператором. Общий v5 acceptance **NOT PASS**, G-01…G-11 остаются `PARTIAL/PENDING`; stable `v5.0.0` не опубликован, публичный launch закрыт allowlist/launch-gates.

Рекомендуемый порядок первой реализации и фактический прогресс:

1. 🟡 customer ownership/auth boundary + feature flag/allowlist без публичного открытия — pilot boundary действует через существующий allowlist/admin policy; public signup, dedicated abuse/rate-limit policy и полный ownership audit ещё не завершены;
2. ✅ долговечные состояния Order / Payment / Entitlement и контракт миграций — PR #290–#294, schema v8, атомарное подтверждение, журнал webhook, сверка после рестарта и устойчивый checkout ID;
3. ✅ provider-neutral customer/subscription service boundary поверх текущего 3x-ui provisioning — `client_access.py` работает через `CustomerPortalService`, provider contract задан `CustomerAccessProvider`, а текущие 3x-ui reads изолированы в `customer_provider_xui.py`; Telegram handlers больше не импортируют `XUIClient`, `Database` или `CommerceService` напрямую;
4. ✅ read-only Client Portal skeleton: Профиль / Моя подписка / Трафик / Устройства / Помощь — PR #296; legacy `/create` / `/inbounds` больше не являются mutation-entrypoints;
5. 🟡 commerce flow + authenticated/idempotent payment event journal — backend journal/state machine и provider-neutral checkout foundation готовы; следующий production path использует native Telegram Stars (`XTR`) для цифровой подписки внутри бота: отдельная Stars-цена тарифа, pre-checkout ownership/amount validation и atomic `successful_payment → Payment confirmed → Order paid → Entitlement` реализуются; после #305 Terms acceptance, `/paysupport` и one-shot refund journal/операторский flow реализованы; остаются test/prod payment smoke и production acceptance;
6. ✅ entitlement → выдача доступа/сверка с правилами no-replay/unknown — PR #292/#295; очередь pending не повторяет `provisioning` при неопределённом результате;
7. 🟡 onboarding/QR UX и self-service diagnostics реализуются в #306: platform selection, local/private QR и read-only entitlement/provider diagnostics; client-specific deep-link остаётся отложен до стабильного безопасного import contract;
8. 🟡 отдельный v5 launch audit выполняется в #308: repository-verifiable ownership/payment/secret/rollback controls закреплены regression gate; production Stars acceptance, failure/restart canary и load/soak остаются release blockers; retention-policy disposition закрыт в `docs/DATA_RETENTION.md`;
9. ⬜ controlled canary rollout по описанному ниже gate;
10. ⬜ только после canary — расширение публичного доступа.

Фактическая v5 foundation-линия на 2026-10-07: #290–#303 уже в `main`, а #304 остаётся открытым draft PR.

После #302 core backend path уже собран сквозным каркасом: `Plan/Order → checkout boundary → Payment → authenticated webhook → Entitlement → Provisioning`. Для цифровой подписки внутри Telegram #304 переводит customer payment entrypoint на native Telegram Stars вместо внешнего PSP checkout. После merge production commerce блокируют уже не выбор PSP, а Stars acceptance: #305 закрывает Terms acceptance UX, `/paysupport` и one-shot refund workflow через Telegram Bot API; после него остаются test/prod payment smoke и controlled canary.

- #290 — commerce foundation;
- #291 — atomic `payment.confirmed → order paid → entitlement`;
- #292 — entitlement → safe provisioning;
- #293 — authenticated payment webhook gateway;
- #294 — payment-event restart reconciliation;
- #295 — durable entitlement fulfillment worker;
- #296 — pilot Client Portal shell;
- #297/#298 — subscription browser compatibility hotfixes, необходимые для корректной customer subscription page;
- #300 — отдельные nginx limits для `/compat/assets/`, подтверждённые на Safari/WebKit;
- #301 — provider-neutral customer service boundary: Client Portal больше не зависит напрямую от `XUIClient`/DB/Commerce;
- #302 — независимая от провайдера основа оплаты, schema v8, устойчивый checkout URL/idempotency и кнопка оплаты Telegram;
- #304 (текущий срез) — native Telegram Stars для цифровой подписки: schema v9, независимая Stars-цена тарифа, XTR invoice/pre-checkout/successful-payment lifecycle.

До перехода к public launch основными implementation-блокерами остаются production acceptance Telegram Stars (после #305 остаются test/prod smoke и acceptance возвратов), после #306 остаются client-specific deep-link при наличии стабильного import contract, production Stars smoke/acceptance, затем launch audit + controlled canary.

Отложенные tracks **не блокируют** базовый v5.0.0: multi-format subscriptions, Remnawave/provider-neutral multi-provider expansion и Cheburcheck Probe fleet могут идти отдельными subsequent tracks после стабилизации core Client Portal. При этом верхний customer/domain слой v5 сразу проектируется так, чтобы не зависеть напрямую от `XUIClient`.

`v5.0.0` открывает следующий продуктовый этап: `/start` становится основным пользовательским входом для клиентов.

Архитектурная граница:

~~~text
/start
└─ Client Portal

/admin
└─ Admin Control Plane
~~~

Client Portal и Admin Control Plane живут в одном Telegram-боте и одном репозитории, но имеют независимые navigation/authorization boundaries.

`/admin` никогда не становится публичным из-за открытия `/start`.

