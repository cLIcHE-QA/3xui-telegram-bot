"""Нормативный Admin entrypoint + полный проверяемый operator runbook."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = re.compile(r"https://github[.]com/cLIcHE-QA/3xui-telegram-bot/blob/[0-9a-f]{40}/docs/ADMIN_SETUP[.]md")
ORDER = ("## Перед началом:", "## Маршрут первоначальной установки", "## Definition of Done", "## Дополнительные операции", "## Исторические checkpoints")
STEPS = (
    "## 0. Что понадобится", "## 1. Сначала подготовь 3x-ui",
    "## 2. Базовая подготовка Master", "## 3. Получи release",
    "## 4. Создай local admin venv", "## 5. Настрой .env",
    "## 6. Firewall Master", "## 7. Первый запуск bot",
    "## 8. Host Control для Master", "## 9. Подготовь direct node",
    "## 10. Собери Host Control bundle", "## 11. Установи Host Control",
    "## 12. Настрой nginx", "## 13. Передай Host Control",
    "## 14. Подготовь три enrollment", "## 15. Guided bind",
    "## 16. Guided bind", "## 17. Readiness direct node",
    "## 18. Проверка Host Control", "## 19. Проверка Extended",
    "## 20. Проверка Full Backup", "## 21. Финальный health",
    "## 22. Удали временные", "## 23. Добавление следующих",
    "## 24. Обновления", "## 25. Security invariants",
    "## 26. Типичные ошибки", "## 27. Definition of Done",
)
SECURE = (
    "git checkout --detach", "VERIFY_TLS=true", "chmod 600 .env",
    "--check-only", "--apply", "Host Control Agent",
    "node-sync token", "direct-admin", "unknown",
    "NoNewPrivs", "quick_check", "schema_migrations",
    "RestartCount=0", "Full Backup", "read-only",
)

def errors(guide, procedure):
    problems = []
    positions = [guide.find(m) for m in ORDER]
    if any(x < 0 for x in positions) or positions != sorted(positions):
        problems.append("operator stage order")
    for marker in STEPS:
        if procedure.count(marker) != 1:
            problems.append("missing/duplicate step: "+marker)
    for word in SECURE:
        if word not in procedure:
            problems.append("missing safety contract: "+word)
    if not SNAPSHOT.search(guide) or not SNAPSHOT.search(procedure):
        problems.append("missing immutable original provenance")
    if "PARTIAL/NO-GO" not in guide or "public rollout BLOCKED" not in guide:
        problems.append("pilot guard missing")
    if "ADMIN_SETUP_PROCEDURES.md" not in guide:
        problems.append("entrypoint lost")
    if len(guide.splitlines()) > 125:
        problems.append("entrypoint accumulated detailed release history")
    return problems

class AdminRunbookContractTests(unittest.TestCase):
    def setUp(self):
        self.guide=(ROOT/"docs/ADMIN_SETUP.md").read_text(encoding="utf-8")
        self.procedure=(ROOT/"docs/ADMIN_SETUP_PROCEDURES.md").read_text(encoding="utf-8")
    def test_current(self):
        self.assertEqual(errors(self.guide,self.procedure),[])
    def test_stage_order_regression(self):
        changed=self.guide.replace("## Перед началом:", "## Исторические checkpoints",1)
        self.assertNotEqual(changed,self.guide)
        self.assertTrue(errors(changed,self.procedure))
    def test_procedure_missing_safety(self):
        for key in ("--check-only", "VERIFY_TLS=true", "schema_migrations"):
            with self.subTest(key=key):
                changed=self.procedure.replace(key,"REMOVED",1)
                self.assertNotEqual(changed,self.procedure)
                self.assertTrue(errors(self.guide,changed))
    def test_duplicate_step_and_history_provenance(self):
        changed=self.procedure+"\n## 7. Первый запуск bot\n"
        self.assertTrue(any("duplicate" in x for x in errors(self.guide,changed)))
        changed=SNAPSHOT.sub("unverified archive",self.guide)
        self.assertNotEqual(changed,self.guide)
        self.assertTrue(any("provenance" in x for x in errors(changed,self.procedure)))

if __name__ == "__main__":
    unittest.main()
