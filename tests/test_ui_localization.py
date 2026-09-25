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

        self.assertIn("📡 Inbound'ы ·", nodes)
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
            '"Текущая версия: ',
            '"Последняя стабильная: ',
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
            '"Текущий релиз: ',
            '"Последний опубликованный: ',
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
            'text="📡 Синхронизировать inbound\'ы"',
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
            '"📡 Inbound\'ы"',
            'text="👥 Клиенты"',
            'text="✏️ Изменить"',
            'text="📋 Клонировать"',
            'text="🧩 Сохранить шаблон"',
            '"🧩 Шаблоны inbound\'ов\\n\\n"',
        ):
            self.assertIn(needle, inbounds)
        for old in (
            '"📡 Inbounds"',
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
            '"Пользователи без тарифа/группы сохраняют режим совместимости «все управляемые inbound\'ы»."',
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
            'f"Политика inbound\'ов: {inbound_mode_text(mode)}"',
        ):
            self.assertIn(needle, catalog)
        for old in (" servers", "(not discovered)", "Nodes API:", "Inbound policy:", "managed inbound'ы"):
            self.assertNotIn(old, catalog)

        for needle in (
            'text="🔐 Роли и права"',
            '"🔐 Роли и права"',
            '"Owner из .env — аварийный владелец',
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
            '"целевых inbound\'ов. Попроси администратора проверить "',
            'provisioning_note = "Политика совместимости пробного доступа"',
            'f"📡 Inbound\'ы: {\', \'.join(map(str, inbound_ids))}"',
            '"выполнить согласование позже."',
        ):
            self.assertIn(needle, client)
        for old in (
            "target inbound'ов",
            "Legacy-политика пробного доступа",
            "📡 Inbounds:",
            "выполнить reconcile позже",
        ):
            self.assertNotIn(old, client)

        for needle in (
            'warnings.append(f"API нод: {node_error[:180]}")',
            '"Недоступные ноды пропущены при безопасном согласовании."',
            'f"Группа серверов #{group_id} не найдена"',
            '"Режим «выбранные» включён, но inbound\'ы не выбраны."',
            '"Для выбранных серверов нет подходящих inbound\'ов согласования."',
            '"Недоступные ноды будут пропущены до следующего согласования."',
            '"Строгое согласование оставило бы клиента без inbound\'ов"',
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
            "provisioning inbound'ов",
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

        self.assertIn('"server_group.inbound": "изменение inbound\'ов согласования группы"', observability)
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


if __name__ == "__main__":
    unittest.main()
