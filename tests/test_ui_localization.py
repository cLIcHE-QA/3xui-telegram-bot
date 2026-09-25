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
