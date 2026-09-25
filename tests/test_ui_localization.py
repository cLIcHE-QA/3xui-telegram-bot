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
        ):
            self.assertIn(needle, text)
        for old in (
            '"📊 Traffic"',
            '"🟢 Online"',
            '"⚙️ Jobs"',
            '"🧾 Audit Log"',
            'text="⬅ Monitoring"',
            'text="⬅ System"',
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
