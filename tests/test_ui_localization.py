from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class OperationalUiLocalizationTests(unittest.TestCase):
    def test_monitoring_jobs_and_audit_are_localized(self):
        text = source("admin_observability.py")
        for needle in (
            '"📊 Трафик"',
            '"🟢 Клиенты в сети"',
            '"⚙️ Задания"',
            '"🧾 Журнал аудита"',
            'text="⬅ Мониторинг"',
            'text="⬅ Система"',
            '"успешно"',
            '"выполняется"',
            '"ℹ️ Это накопительные счётчики 3x-ui с момента последнего сброса, не «трафик за сегодня»."',
        ):
            self.assertIn(needle, text)
        for old in (
            '"📊 Traffic"',
            '"🟢 Online"',
            '"⚙️ Jobs"',
            '"🧾 Audit Log"',
            'text="⬅ Monitoring"',
            'text="⬅ System"',
            "последнего reset",
        ):
            self.assertNotIn(old, text)

    def test_logs_and_alerts_are_localized(self):
        text = source("logs_alerts.py")
        for needle in (
            '"Фоновое задание завершилось ошибкой"',
            '"Фоновое задание снова выполняется успешно"',
            '"📜 Журналы\\n\\n"',
            '"🚨 Оповещения"',
            '"Правила:"',
            'text="⬅ Журналы"',
            'text="⬅ Оповещения"',
        ):
            self.assertIn(needle, text)
        for old in (
            '"Background job failed"',
            '"Background job recovered"',
            '"📜 Logs\\n\\n"',
            '"🚨 Alerts"',
            'text="⬅ Logs"',
            'text="⬅ Alerts"',
        ):
            self.assertNotIn(old, text)

    def test_backup_health_and_readiness_are_localized(self):
        storage = source("storage_admin.py")
        system = source("system_admin.py")
        nodes = source("node_admin.py")

        self.assertIn("Резервные копии нод: не настроены", storage)
        self.assertIn("Полная резервная копия создана", storage)
        self.assertNotIn('"Backup нод: не настроен"', storage)

        self.assertIn("🟢 В сети · 3x-ui API", system)
        self.assertIn("💾 Резервная копия: ", system)
        self.assertIn("💽 Диск", system)
        self.assertNotIn("🟢 Online · 3x-ui API", system)

        self.assertIn("🧭 Готовность ноды", nodes)
        self.assertIn("Стабильная идентичность", nodes)
        self.assertIn("Привязки привилегированных каналов", nodes)
        self.assertNotIn("Node readiness", nodes)
        self.assertNotIn("Stable identity", nodes)

    def test_host_control_and_fleet_are_localized(self):
        host = source("host_control_ui.py")
        fleet = source("fleet_operations.py")
        nodes = source("advanced_nodes.py")

        for needle in (
            'text="▶ Запустить сервис"',
            'text="🔄 Перезапустить сервис"',
            'text="⏹ Остановить сервис"',
            'text="♻️ Перезапустить процесс панели"',
            '"🧩 Управление 3x-ui',
            '"⚪ Сервис: Host Control не настроен"',
        ):
            self.assertIn(needle, host)
        for old in (
            'text="▶ Start service"',
            'text="🔄 Restart service"',
            'text="⏹ Stop service"',
            'text="♻️ Restart Panel process"',
            '"🧩 3x-ui Control',
        ):
            self.assertNotIn(old, host)
        self.assertIn('f"STOP {target_name}"', host)

        for needle in (
            '"🌐 Операции с нодами\\n\\n"',
            '("🩺 Состояние нод", "admin:fleet:health")',
            '("🛠 Включить обслуживание", "admin:fleet:mt:e")',
            '("🚀 Контролируемое обновление", "admin:fleet:rollout")',
            '("🧾 Задания по нодам", "admin:fleet:jobs")',
            '"Состояние: {_plan_state_text',
        ):
            self.assertIn(needle, fleet)
        for old in (
            '"🌐 Fleet Operations\\n\\n"',
            '("🩺 Fleet Health", "admin:fleet:health")',
            '("🛠 Enter maintenance", "admin:fleet:mt:e")',
            '("🚀 Controlled rollout", "admin:fleet:rollout")',
            '("🧾 Fleet Jobs", "admin:fleet:jobs")',
        ):
            self.assertNotIn(old, fleet)

        self.assertIn("📡 Inbounds ·", nodes)
        self.assertIn("✏️ Переименование ноды", nodes)
        self.assertIn("💾 Снимок ноды", nodes)
        self.assertNotIn("✏️ Rename node", nodes)

    def test_versions_and_bot_updates_are_localized(self):
        versions = source("versions_updates.py")
        bot_updates = source("bot_updates.py")

        for needle in (
            '"⬅ Версии и обновления"',
            '"🧩 Версии и обновления | Бот',
            '("⬆️ Обновление 3x-ui",',
            '("⚡ Версии Xray",',
            '"📦 Текущая версия: ',
            '"🆕 Последняя стабильная: ',
            '"Резервная копия: {Path(op.backup)',
        ):
            self.assertIn(needle, versions)
        for old in (
            '"⬅ Versions & Updates"',
            '"🧩 Versions & Updates | Bot',
            '("⬆️ 3x-ui update",',
            '("⚡ Xray versions",',
            '"Current: ',
            '"Latest stable: ',
        ):
            self.assertNotIn(old, versions)
        self.assertIn('f"Введи точно: UNLOCK {nonce}"', versions)

        for needle in (
            '"🤖 Обновления бота"',
            '"🤖 Проверка обновления бота"',
            '"📦 Текущий релиз: ',
            '"🆕 Последний опубликованный: ',
            '("📜 История обновлений",',
            '("🔍 Проверить последний релиз",',
            '"Состояние: {_deploy_state_text',
        ):
            self.assertIn(needle, bot_updates)
        for old in (
            '"🤖 Bot Updates"',
            '"🤖 Bot Update preflight"',
            '"Current bot: ',
            '"Latest published: ',
            '("📜 Update history",',
            '("🔍 Preflight latest",',
        ):
            self.assertNotIn(old, bot_updates)
        self.assertIn('f"DOWNGRADE {release}"', bot_updates)
        self.assertIn('_DOWNGRADE_PHRASE_RE', bot_updates)

    def test_domain_ui_is_localized(self):
        users = source("advanced_users.py")
        catalog = source("catalog_admin.py")
        business = source("business_admin.py")
        inbounds = source("inbound_admin.py")

        for needle in (
            'text="⬅ Пользователи"',
            'text="💎 Тариф"',
            'text="🚀 Согласование"',
            'text="🔄 Сбросить трафик"',
            'text="✅ Включить"',
            'text="⛔ Отключить"',
            'text="📡 Синхронизировать Inbounds"',
            'f"⚙️ Массовые действия\\n\\nВыбрано: {len(selected)}"',
            'f"👥 Пользователи\\n\\nПользователи в БД бота: {len(users)}"',
            '"☑️ Массовые действия с пользователями\\n\\n"',
        ):
            self.assertIn(needle, users)
        for old in (
            'text="⬅ Users"',
            'text="💎 Plan"',
            'text="🚀 Provisioning"',
            'text="🔄 Reset traffic"',
            'text="✅ Enable"',
            'text="⛔ Disable"',
            'text="📡 Sync inbounds"',
            'f"⚙️ Bulk actions\\n\\nВыбрано: {len(selected)}"',
            '"👥 Users\\n\\n"',
            '"☑️ Bulk user actions\\n\\n"',
        ):
            self.assertNotIn(old, users)

        for needle in (
            '"💎 Тарифы\\n\\n"',
            '"🗂 Группы серверов\\n\\n"',
            '"🌐 Хосты\\n\\n"',
            'text="⬅ Тарифы"',
            'text="⬅ Группы серверов"',
            'text="⬅ Хосты"',
            '"Группа серверов: ',
        ):
            self.assertIn(needle, catalog)
        for old in (
            '"💎 Plans\\n\\n"',
            '"🗂 Server Groups\\n\\n"',
            '"🌐 Hosts\\n\\n"',
            'text="⬅ Plans"',
            'text="⬅ Server Groups"',
            'text="⬅ Hosts"',
        ):
            self.assertNotIn(old, catalog)

        for needle in (
            '"💳 Платежи\\n\\n"',
            '"🎟 Промокоды\\n\\n"',
            '"👮 Администраторы\\n\\n"',
            '"🔧 Настройки\\n\\n"',
            '"pending": "🟡 Ожидает"',
            '"paid": "🟢 Оплачен"',
            'text="⬅ Платежи"',
            'text="⬅ Промокоды"',
            'text="⬅ Администраторы"',
        ):
            self.assertIn(needle, business)
        for old in (
            '"💳 Payments\\n\\n"',
            '"🎟 Promo Codes\\n\\n"',
            '"👮 Administrators\\n\\n"',
            '"🔧 Settings\\n\\n"',
            '"pending": "🟡 Pending"',
            '"paid": "🟢 Paid"',
            'text="⬅ Payments"',
            'text="⬅ Promo Codes"',
            'text="⬅ Administrators"',
        ):
            self.assertNotIn(old, business)
        for role in ("Read-only", "Support", "Administrator", "Owner"):
            self.assertIn(role, business)

        for needle in (
            '"📡 Inbounds"',
            'text="👥 Клиенты"',
            'text="✏️ Изменить"',
            'text="📋 Клонировать"',
            'text="🧩 Сохранить шаблон"',
            '"🧩 Шаблоны Inbounds\\n\\n"',
        ):
            self.assertIn(needle, inbounds)
        for old in (
            'text="👥 Clients"',
            'text="✏️ Edit"',
            'text="📋 Clone"',
            'text="🧩 Save template"',
            '"🧩 Inbound Templates\\n\\n"',
        ):
            self.assertNotIn(old, inbounds)

    def test_domain_residual_copy_is_localized_and_machine_values_are_stable(self):
        users = source("advanced_users.py")
        catalog = source("catalog_admin.py")
        business = source("business_admin.py")
        client = source("client_access.py")
        provisioning = source("provisioning.py")
        privileges = source("admin_privileges.py")
        nodes = source("advanced_nodes.py")
        observability = source("admin_observability.py")

        for needle in (
            "административные метаданные. Лимиты 3x-ui не меняются автоматически.",
            'f"Не хватает: {len(missing)} · доступно сейчас: {len(actionable_missing)}"',
            'f"Лишних управляемых: {len(extra)}"',
            'f"Недоступные ноды: {\', \'.join(policy.unavailable_members)}"',
            'f"Подключены: {result.attached_ids or \'нет\'}"',
            'f"Отключены: {result.detached_ids or \'нет\'}"',
            'f"Всё ещё отсутствуют: {result.remaining_missing_ids or \'нет\'}"',
            '"Пользователи без тарифа/группы сохраняют режим совместимости «все управляемые Inbounds»."',
        ):
            self.assertIn(needle, users)
        for old in (
            "control-plane",
            "legacy all-managed",
            "Missing:",
            "actionable now",
            "Extra managed:",
            "Unavailable nodes:",
            "Attached:",
            "Detached:",
            "Still missing:",
            "Legacy-пользователи",
            "all-managed policy",
        ):
            self.assertNotIn(old, users)

        for needle in (
            'text=f"🗂 {group.name} · серверов: {len(members)}"',
            "(не обнаружена)",
            'f"⚠️ API нод: {nodes_error}"',
            'f"Политика Inbounds: {inbound_mode_text(mode)}"',
        ):
            self.assertIn(needle, catalog)
        for old in (" servers", "(not discovered)", "Nodes API:", "Inbound policy:", "managed Inbounds"):
            self.assertNotIn(old, catalog)

        for needle in (
            'text="🔐 Роли и права"',
            '"🔐 Роли и права"',
            '"Owner из локальной конфигурации — аварийный владелец',
            'f"Добавил: {f\'TG {rec.added_by}\' if rec.added_by else \'система\'}\\n"',
            '"Окружение (только чтение):\\n"',
        ):
            self.assertIn(needle, business)
        for old in (
            "Roles & Privileges",
            "ENV Owner",
            "Added by:",
            "Environment (read-only):",
            "runtime-настройки",
        ):
            self.assertNotIn(old, business)

        for needle in (
            '"Обзор и разделы /admin"',
            '"Резервные копии: просмотр"',
            '"Группы серверов: просмотр"',
            '"Роли и права: просмотр"',
            '"Оповещения: изменение правил"',
            '"Аварийное восстановление"',
            '"Совместимые административные маршруты"',
        ):
            self.assertIn(needle, privileges)
        for role in ("Read-only", "Support", "Administrator", "Owner"):
            self.assertIn(f'"{role}"', privileges)
        for old in (
            '"Dashboard и разделы /admin"',
            '"Backups: просмотр"',
            '"Plans: просмотр"',
            '"Payments: просмотр"',
            '"Promo Codes: просмотр"',
            '"Roles & Privileges: просмотр"',
            '"Runtime Settings: просмотр"',
            '"Monitoring/Logs/Audit/Jobs: просмотр"',
            '"Disaster Recovery"',
            '"Legacy admin compatibility routes"',
        ):
            self.assertNotIn(old, privileges)

        for needle in (
            '"целевых Inbounds. Попроси администратора проверить "',
            'provisioning_note = "Политика совместимости пробного доступа"',
            'f"📡 Inbounds: {\', \'.join(map(str, inbound_ids))}"',
            '"выполнить согласование позже."',
        ):
            self.assertIn(needle, client)
        for old in (
            "target Inbounds",
            "Legacy-политика пробного доступа",
            "выполнить reconcile позже",
        ):
            self.assertNotIn(old, client)

        for needle in (
            'warnings.append(f"API нод: {node_error[:180]}")',
            '"Недоступные ноды пропущены при безопасном согласовании."',
            'f"Группа серверов #{group_id} не найдена"',
            '"Режим «выбранные» включён, но Inbounds не выбраны."',
            '"Для выбранных серверов нет подходящих Inbounds согласования."',
            '"Недоступные ноды будут пропущены до следующего согласования."',
            '"Строгое согласование оставило бы клиента без Inbounds"',
            'f"Нода #{inbound.node_id}"',
        ):
            self.assertIn(needle, provisioning)
        for machine_value in ('"legacy-all-managed"', '"all_managed"', '"selected"'):
            self.assertIn(machine_value, provisioning)
        for old in (
            "Nodes API:",
            "safe provisioning",
            "Server Group #",
            "Selected-mode",
            "provisioning Inbounds",
            "следующего reconcile",
            "Strict reconcile",
            'f"Node #{inbound.node_id}"',
        ):
            self.assertNotIn(old, provisioning)

        for needle in (
            '"цель NODE_BACKUP всё ещё привязана к имени;',
            '"цель HOST_CONTROL всё ещё привязана к имени;',
            '"Master специально не раскрывает сохранённый токен node-sync."',
        ):
            self.assertIn(needle, nodes)
        for old in ("legacy NODE_BACKUP target", "legacy HOST_CONTROL target", "node-sync token"):
            self.assertNotIn(old, nodes)

        self.assertIn('"server_group.inbound": "изменение Inbounds согласования группы"', observability)
        self.assertIn('"user.plan.provision": "применение тарифа и согласование"', observability)
        self.assertNotIn("изменение provisioning inbound группы", observability)
        self.assertNotIn("применение тарифа и provisioning", observability)

    def test_disaster_recovery_ui_is_localized_but_confirmation_contract_is_stable(self):
        text = source("disaster_recovery.py")
        for needle in (
            '"🧯 Аварийное восстановление"',
            'text="⬅ Резервные копии"',
            'text="⬅ Восстановление"',
            'text="🕘 История восстановления"',
            '"Восстановление отменено. Данные не изменены."',
        ):
            self.assertIn(needle, text)
        for phrase in (
            'phrase="RESTORE BOT"',
            '"RESTORE XUI FORCE"',
            '"RESTORE XUI"',
            'phrase="RESTORE NODE"',
        ):
            self.assertIn(phrase, text)


    def test_final_repo_wide_localization_residuals(self):
        shell = source("admin_shell.py")
        inbounds = source("inbound_admin.py")
        node_admin = source("node_admin.py")
        node_ui = source("node_ui.py")
        advanced_nodes = source("advanced_nodes.py")
        users = source("advanced_users.py")
        host = source("host_control_ui.py")
        fleet = source("fleet_operations.py")
        versions = source("versions_updates.py")
        version_service = source("version_service.py")
        bot_updates = source("bot_updates.py")
        alerts = source("logs_alerts.py")
        catalog = source("catalog_admin.py")
        restore = source("disaster_recovery.py")
        style = source("docs/UI_STYLE.md")

        self.assertIn('f"⚠️ Статус клиентов в сети: {online_error}"', shell)
        self.assertIn('f"⚠️ API нод: {nodes_error}"', shell)
        self.assertNotIn('f"⚠️ Статус online: {online_error}"', shell)
        self.assertNotIn('f"⚠️ Nodes API: {nodes_error}"', shell)
        self.assertNotIn("runtime-настроек", shell)

        for needle in (
            'f"Сервер: {_node_label(node_id, nodes)}"',
            'f"Протокол: {ib.get(\'protocol\') or \'-\'}"',
            'f"Порт: {ib.get(\'port\') or 0}"',
            'f"Транспорт: {network}"',
            'f"Безопасность: {security}"',
        ):
            self.assertIn(needle, inbounds)
        for old in (
            'f"Server: {_node_label(node_id, nodes)}"',
            'f"Protocol: {ib.get(\'protocol\') or \'-\'}"',
            'f"Port: {ib.get(\'port\') or 0}"',
            'f"Transport: {network}"',
            'f"Security: {security}"',
        ):
            self.assertNotIn(old, inbounds)

        self.assertIn("Задержка API:", node_admin)
        self.assertIn('"legacy_name": "привязка по старому имени"', node_admin)
        self.assertNotIn("Ping API:", node_admin)
        self.assertNotIn('"legacy_name": "legacy name"', node_admin)
        for needle in (
            'f"🔗 Адрес: {endpoint}"',
            "🧭 Исходящий маршрут:",
            "📶 Задержка API:",
            "🕒 Последний сигнал:",
            '"verify": "проверять"',
            '"skip": "без проверки"',
            '"all": "все Inbounds"',
        ):
            self.assertIn(needle, node_ui)
        for old in ("Endpoint:", "Outbound bridge:", "Ping API:", "Последний heartbeat:"):
            self.assertNotIn(old, node_ui)

        self.assertIn("Старое действие больше не выполняет изменение напрямую.", advanced_nodes)
        self.assertIn("Сначала перенеси или удали Inbounds", advanced_nodes)
        self.assertNotIn("Старый callback больше не выполняет изменение напрямую.", advanced_nodes)
        self.assertNotIn("Сначала удали/detach Inbounds", advanced_nodes)

        self.assertIn("Затронуто записей: {affected}", users)
        self.assertNotIn("Трафик сброшен. affected=", users)

        self.assertIn("systemd сообщает, что сервис работает", host)
        self.assertNotIn("systemd сообщает running", host)

        for needle in (
            "нод с прямым подключением",
            "контрольной ноде",
            "Запустить контрольную ноду",
            "Контрольная нода:",
            "предварительная проверка обновления",
            "API прямого подключения недоступен",
            "Привязка Direct Admin=",
            "Привязка Host Control=",
            '"legacy_name": "привязка по старому имени"',
            "Прямое подключение:",
            "новую сессию операций с нодами",
        ):
            self.assertIn(needle, fleet)
        for old in (
            "Массовые изменения выполняются только для direct nodes",
            "Контролируемое обновление использует canary",
            "Запустить canary",
            "Canary:",
            "update preflight",
            "Direct API недоступен",
            "Direct привязка=",
            "Host привязка=",
            '"legacy_name": "legacy name"',
            " · Direct: ",
            " · Host: ",
            "новую fleet-сессию",
        ):
            self.assertNotIn(old, fleet)
        self.assertIn('"canary": pending[0] if pending else 0', fleet)
        self.assertIn('"canary_passed"', fleet)
        self.assertIn("admin:fleet:run:", fleet)

        self.assertIn("Полная резервная копия Master не прошла предварительную проверку", versions)
        self.assertIn("средство обновления на сервере завершило работу", versions)
        self.assertNotIn("Полная резервная копия Master не прошла preflight", versions)
        self.assertNotIn("updater на сервере", versions)

        for needle in (
            "Текущая версия неизвестна; обновление заблокировано.",
            "Есть незавершённая операция. Сначала проверь или отмени её.",
            "Не удалось проверить свежую резервную копию.",
            "Результат не подтверждён. Повторный запрос не отправлялся.",
            "Подключение к цели изменилось; требуется ручная проверка.",
        ):
            self.assertIn(needle, version_service)
        for old in (
            "Current version is unknown; update blocked.",
            "There is a pending operation. Check or cancel it first.",
            "Fresh backup could not be verified.",
            "Outcome not verified. No retry was sent.",
            "Target connection changed; manual verification required.",
        ):
            self.assertNotIn(old, version_service)

        for needle in (
            "Состояние Xray:",
            "Диск:",
            "Статус ноды:",
            "Статус: {_job_status_text",
            '"all": "Все"',
            '"warning": "Предупреждения"',
            '"error": "Ошибки"',
            "🔎 Фильтр: {_log_level_text(level)}",
        ):
            self.assertIn(needle, alerts)
        for old in (
            'value=f"state={xray_state}"',
            'value=f"state={state}"',
            'value=f"disk={pct:.1f}%"',
            'value=f"status={node.status}; enabled={node.enable}"',
            'value = f"status={run.status};',
            '+ "ALL", callback_data=',
            '+ "WARN+", callback_data=',
            '+ "ERROR", callback_data=',
            "Фильтр: {level.upper()}",
            'raise ValueError("unknown log source")',
        ):
            self.assertNotIn(old, alerts)

        self.assertIn("Имя хоста, IP или URL.", catalog)
        self.assertIn("Некорректное имя хоста/IP/URL.", catalog)
        self.assertNotIn("Hostname, IP или URL.", catalog)
        self.assertNotIn("Некорректный hostname/IP/URL.", catalog)

        for needle in (
            "Релиз отклонён на предварительной проверке",
            "Предварительная проверка завершилась ошибкой",
            "Deploy Agent с ограниченными полномочиями",
            "Автоматического отката или повтора изменения нет.",
        ):
            self.assertIn(needle, bot_updates)
        for old in (
            "Релиз/preflight отклонён",
            "Preflight завершился ошибкой",
            "restricted Deploy Agent",
            "Автоматического отката/повтора мутации нет.",
        ):
            self.assertNotIn(old, bot_updates)

        for needle in (
            "Предварительная проверка (без изменений)",
            "Перед любой опасной операцией выполняется предварительная проверка",
            "Это опасная операция.",
            "защитный снимок текущей БД бота",
            "Защитная копия текущего Master",
            "Защитная копия предыдущей БД",
        ):
            self.assertIn(needle, restore)
        for old in (
            "Проверка (dry-run / preflight)",
            "Это destructive-операция.",
            "rescue snapshot текущей БД бота",
            "Rescue-копия текущего Master",
            "Rescue-копия предыдущей БД",
        ):
            self.assertNotIn(old, restore)
        for phrase in ("RESTORE BOT", "RESTORE XUI", "RESTORE NODE"):
            self.assertIn(phrase, restore)

        observability = source("admin_observability.py")
        storage = source("storage_admin.py")
        self.assertIn("☁️ Последняя внешняя копия:", observability)
        self.assertNotIn("Последний внешний (off-site):", observability)
        self.assertIn("☁️ Внешняя копия: включена", storage)
        self.assertNotIn("Внешняя копия (off-site)", storage)

        for needle in ("💽 Диск", "⏱ Время работы", "💾 Резервная копия"):
            self.assertIn(needle, style)
        for old in ("💽 Disk", "⏱ Uptime", "💾 Backup"):
            self.assertNotIn(old, style)


    def test_operational_summary_emoji_contract(self):
        node_ui = source("node_ui.py")
        system = source("system_admin.py")
        observability = source("admin_observability.py")
        storage = source("storage_admin.py")
        versions = source("versions_updates.py")
        bot_updates = source("bot_updates.py")
        alerts = source("logs_alerts.py")
        fleet = source("fleet_operations.py")
        style = source("docs/UI_STYLE.md")
        roadmap = source("docs/ROADMAP.md")

        for needle in (
            "🔗 Адрес:",
            "🔐 Проверка TLS:",
            "🧭 Исходящий маршрут:",
            "📶 Задержка API:",
            "📊 Сеть:",
            "🕒 Последний сигнал:",
            "🧮 CPU:",
            "🧠 RAM:",
            "⏱ Время работы:",
            "🌐 Inbound",
            "👥 Клиент",
            "💾 Резервная копия",
        ):
            self.assertIn(needle, node_ui)

        for needle in (
            "🧮 CPU",
            "🧠 RAM",
            "📶 Задержка API: {node.latency_ms} ms",
            "👥 Клиентов",
            "🌐 Inbound",
            "⏱ Время работы",
        ):
            self.assertIn(needle, system)

        for needle in (
            "👥 Клиентов 3x-ui:",
            "👥 Пользователей бота:",
            "📊 Использовано:",
            "💾 Ежедневная резервная копия",
            "⏭ Следующий запуск:",
            "☁️ Последняя внешняя копия:",
        ):
            self.assertIn(needle, observability)

        for needle in (
            "🕘 Последняя:",
            "📦 Размер:",
            "🗄 Хранится полных копий:",
            "🗓 Ежедневно:",
            "📤 Отправка администраторам:",
            "🌍 Резервные копии нод:",
        ):
            self.assertIn(needle, storage)

        for needle in (
            "📦 3x-ui:",
            "⚡ Xray:",
            "⚙️ Операция:",
            "📦 Текущая версия:",
            "🆕 Последняя стабильная:",
        ):
            self.assertIn(needle, versions)

        for needle in (
            "📦 Текущий релиз:",
            "🤖 Бот:",
            "🆕 Последний опубликованный:",
            "🧩 Агент:",
            "🩺 Состояние:",
            "⚙️ Активная операция:",
        ):
            self.assertIn(needle, bot_updates)

        self.assertIn("🔎 Фильтр:", alerts)
        for needle in ("🟢 Здоровы:", "🛠 Обслуживание:", "🟡 Деградация:", "🔴 Не в сети:"):
            self.assertIn(needle, fleet)

        for needle in (
            "🔗 Адрес",
            "🔐 Проверка TLS",
            "🧭 Исходящий маршрут",
            "📶 Задержка API",
            "📊 Сеть",
            "🕒 Последний сигнал",
            "🔎",
        ):
            self.assertIn(needle, style)

        self.assertIn("##### Аудит emoji-префиксов в информационных текстах Telegram UI", roadmap)
        self.assertIn("Статус: ✅ Выполнено в `v4.20.1`.", roadmap)


if __name__ == "__main__":
    unittest.main()
