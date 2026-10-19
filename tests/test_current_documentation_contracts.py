"""Fail-closed документальные инварианты Client/UI/SQLite, независимо от RC и Issue.

Тесты проверяют соответствующие нормативные разделы, а не наличие отдельных
слов в исторических доказательствах. Сверка release states с Roadmap — в
tests/test_living_docs.py; локальные Markdown links — в общем semantic checker.
"""
from __future__ import annotations

import importlib.util
import re
import unittest
from collections import defaultdict
from pathlib import Path

from db_migrations import CURRENT_SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = re.compile(
    r"https://github[.]com/cLIcHE-QA/3xui-telegram-bot/blob/"
    r"([0-9a-f]{40})/(docs/[A-Z_]+[.]md)"
)
HEADINGS = re.compile(r"^## (.+?)\s*$", re.M)

# Значения описывают устойчивые safety-контракты, не конкретные release/Issue.
SECTIONS = {
    "docs/CLIENT_SETUP.md": {
        "Client Portal: тарифы и платежные ограничения": (
            "не преобразуется из RUB",
            "`admin_only`",
            "`manual_entitlements`",
            "без автоматического replay",
            "**не** открывает платёж",
            "`successful_payment` обрабатывается идемпотентно",
        ),
        "Переменные пилота и доступ": (
            "`ALLOWED_TELEGRAM_IDS`",
            "`CLIENT_PORTAL_ENABLED` | `false` запрещает клиентский UI, **не** выключает `/admin`",
            "`CLIENT_PAYMENT_ACCEPTANCE_ENABLED` | `false` блокирует **новые** Stars invoices",
            "DB `portal=false` запрещает также **старые inline callbacks**",
        ),
        "Действия при проблеме / rollback": (
            "`CLIENT_PAYMENT_ACCEPTANCE_ENABLED=false`",
            "`CLIENT_PORTAL_ENABLED=false`",
            "Не удаляйте существующие orders/payments/entitlements",
            "не выполняйте повторные refund/provisioning mutations",
        ),
        "Gate на публичный запуск": (
            "BLOCKED до полного PASS",
            "V5_PRODUCTION_ACCEPTANCE.md",
        ),
    },
    "docs/UI_STYLE.md": {
        "Ручные тарифы и статусы пользователей": (
            "`manual_entitlements.active`",
            "`unknown/in_flight` — `🟡♾️`",
            "действует **до пагинации**",
            "`⬅ Пользователи` → `admin:users`",
            "`⬅ Панель администратора` → `admin:home`",
            "отдельно разрешённого release/deploy",
        ),
        "Граница private chat для Admin Control Plane": (
            "только в личном чате",
            "group, supergroup или channel context",
            "должны блокироваться до rendering/business logic",
        ),
        "Навигация": (
            "двухшаговой",
            "только после явного подтверждения",
            "RBAC",
        ),
    },
    "docs/SQLITE_MIGRATIONS.md": {
        "Текущий контракт schema": (
            "schema **v" + str(CURRENT_SCHEMA_VERSION) + "**",
            "`manual_entitlements`",
            "**forward-only**",
            "`requires_backup=True`",
            "`PRAGMA quick_check`",
            "`DatabaseSchemaTooNewError`",
        ),
        "Источник истины": (
            "`MIGRATIONS` в `db_migrations.py`",
            "`requires_backup`",
        ),
        "Startup semantics": (
            "Startup блокируется fail-closed",
            "`running` или `failed`",
            "`PRAGMA quick_check`",
            "автоматически повторно не запускается",
        ),
        "Recovery copy для опасных migrations": (
            "обязана иметь `requires_backup=True`",
            "До записи `running`",
            "`PRAGMA quick_check`",
            "Если создать пригодную копию нельзя, migration не начинается",
        ),
        "Rollback": (
            "forward-only",
            "автоматических down migrations нет",
            "pre-migration recovery copy",
        ),
    },
}


def sections_by_heading(source: str) -> dict[str, list[str]]:
    """Отдельные ## секции; дубли не могут затереться при построении dict."""
    marks = list(HEADINGS.finditer(source))
    result: dict[str, list[str]] = defaultdict(list)
    for idx, match in enumerate(marks):
        end = marks[idx + 1].start() if idx + 1 < len(marks) else len(source)
        result[match.group(1)].append(source[match.end():end])
    return result


def living_contract_errors(path: str, source: str) -> list[str]:
    errors: list[str] = []
    intro = source.split("\n## ", 1)[0]
    if not source.startswith("# ") or "нормативн" not in intro.lower():
        errors.append("missing normative first section")

    sections = sections_by_heading(source)
    first_heading = HEADINGS.search(source)
    if first_heading is None or first_heading.group(1) != next(iter(SECTIONS[path])):
        errors.append("current contract must precede historical notes")

    for heading, fragments in SECTIONS[path].items():
        blocks = sections.get(heading, [])
        if len(blocks) != 1:
            errors.append(f"{path}: missing or duplicate normative section: {heading}")
            continue
        for fragment in fragments:
            if fragment not in blocks[0]:
                errors.append(f"{path}: critical rule lost in section {heading}: {fragment}")

    history = [part for name, blocks in sections.items()
               if name.startswith("Историческ") for part in blocks]
    matching = SNAPSHOT.findall(source)
    if not history or len(matching) != 1 or matching[0][1] != path:
        errors.append(f"{path}: exact immutable historical provenance missing")
    elif not any(SNAPSHOT.search(block) for block in history):
        errors.append(f"{path}: snapshot is not in historical section")

    if path.endswith("CLIENT_SETUP.md"):
        if source.count("**Текущий статус контролируемого пилота:**") != 1:
            errors.append("Client Setup must have exactly one current state")
    if re.search(r"(?m)^## (?:Operator-reported rc[.]|Published rc[.]|Release-prep)", source):
        errors.append("unscoped historical release checkpoint")
    if "**Published checkpoint" in intro:
        errors.append("historical release statement is in normative introduction")
    return errors


def semantic_checker():
    spec = importlib.util.spec_from_file_location(
        "docs_semantics_current_contracts", ROOT / "scripts/check-documentation-semantics.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CurrentDocumentationContractsTests(unittest.TestCase):
    def test_all_current_documents(self):
        for path in SECTIONS:
            with self.subTest(path=path):
                self.assertEqual(
                    living_contract_errors(path, (ROOT / path).read_text(encoding="utf-8")), []
                )

    def test_all_living_contracts_are_in_required_link_gate(self):
        sem = semantic_checker()
        self.assertTrue(set(SECTIONS).issubset(set(sem.CHECK_PATHS)))
        for path in SECTIONS:
            with self.subTest(path=path):
                self.assertEqual(sem.links_ok(ROOT, path), [])

    def test_wrong_section_cannot_be_rescued_by_word_elsewhere(self):
        for path, rules in SECTIONS.items():
            source = (ROOT / path).read_text(encoding="utf-8")
            heading, phrases = next(iter(rules.items()))
            anchor = phrases[0]
            self.assertEqual(source.count(anchor), 1, f"{path}: change fixture anchor")
            mutated = source.replace(anchor, "", 1) + "\n## Исторические слова\n\n" + anchor
            self.assertTrue(any("critical rule lost" in e
                                for e in living_contract_errors(path, mutated)))

    def test_safety_reversals_fail_closed(self):
        cases = (
            ("docs/CLIENT_SETUP.md", "не преобразуется из RUB", "автоматически преобразуется из RUB"),
            ("docs/CLIENT_SETUP.md", "**не** выключает `/admin`", "выключает `/admin`"),
            ("docs/CLIENT_SETUP.md", "без автоматического replay", "с автоматическим replay"),
            ("docs/UI_STYLE.md", "`⬅ Пользователи` → `admin:users`", "`⬅ Пользователи` → `admin:home`"),
            ("docs/SQLITE_MIGRATIONS.md", "обязана иметь `requires_backup=True`", "может иметь `requires_backup=True`"),
        )
        for path, before, after in cases:
            with self.subTest(path=path, before=before):
                source = (ROOT / path).read_text(encoding="utf-8")
                self.assertEqual(source.count(before), 1, "negative fixture must match exactly once")
                mutated = source.replace(before, after, 1)
                self.assertNotEqual(mutated, source)
                self.assertTrue(any("critical rule lost" in e
                                    for e in living_contract_errors(path, mutated)))

    def test_duplicate_section_and_wrong_snapshot_target_rejected(self):
        for path in SECTIONS:
            source = (ROOT / path).read_text(encoding="utf-8")
            marker = "## " + next(iter(SECTIONS[path]))
            self.assertEqual(source.count(marker + "\n"), 1)
            self.assertTrue(any("duplicate normative section" in e
                                for e in living_contract_errors(path, source + "\n" + marker + "\n")))
            modified = SNAPSHOT.sub(
                lambda m: m.group().replace(m.group(2), "docs/OTHER.md"),
                source, count=1
            )
            self.assertNotEqual(modified, source)
            self.assertTrue(any("provenance" in e
                                for e in living_contract_errors(path, modified)))

    def test_historical_checkpoint_cannot_be_reintroduced(self):
        for path in SECTIONS:
            source = (ROOT / path).read_text(encoding="utf-8")
            mutated = source + "\n## Release-prep v0.0.0 — устаревший checkpoint\n"
            self.assertIn("unscoped historical release checkpoint",
                          living_contract_errors(path, mutated))


if __name__ == "__main__":
    unittest.main()
