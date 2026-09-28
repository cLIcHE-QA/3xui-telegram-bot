"""Regression coverage for the v4.20.8 Inbound capitalization patch."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class V4208InboundCapitalizationTests(unittest.TestCase):
    def test_operator_facing_lowercase_inbound_copy_is_removed(self):
        inbound = source("inbound_admin.py")
        users = source("advanced_users.py")
        catalog = source("catalog_admin.py")

        for old in (
            "Изменение inbound",
            "Новое название inbound:",
            "Этот inbound не использует",
            "пользователей → inbound #",
            "этому inbound,",
            "для inbound #",
            "трафик inbound #",
            "Клонирование inbound",
            "конфигурация inbound без клиентов",
            "отключённый inbound без клиентов",
            "Новый inbound",
            "Удалить inbound #",
            "Удаление inbound",
            "Исходный inbound:",
            "удалить inbound",
        ):
            self.assertNotIn(old, inbound)

        for old in (
            "конкретного inbound.",
            "последний управляемый inbound.",
            "связей inbound:",
            "Целевые inbound ID:",
            "доступного inbound.",
        ):
            self.assertNotIn(old, users)

        self.assertNotIn("inbound-политику", catalog)

    def test_canonical_copy_is_present(self):
        inbound = source("inbound_admin.py")
        users = source("advanced_users.py")
        catalog = source("catalog_admin.py")

        for expected in (
            "✏️ Изменение Inbound",
            "Новое название Inbound:",
            "Этот Inbound не использует Reality.",
            "Синхронизация пользователей → Inbound #",
            "Обнулить общий трафик Inbound #",
            "📋 Клонирование Inbound",
            "Удаление Inbound необратимо.",
            "Исходный Inbound:",
        ):
            self.assertIn(expected, inbound)

        self.assertIn("конкретного Inbound.", users)
        self.assertIn("Целевые:", users)
        self.assertIn("серверы и политику Inbounds.", catalog)

    def test_technical_identifiers_remain_lowercase_and_stable(self):
        inbound = source("inbound_admin.py")
        users = source("advanced_users.py")
        style = source("docs/UI_STYLE.md")

        for technical in (
            'callback_data=f"admin:inbound:{iid}"',
            '"inbound.update"',
            'target_type="inbound"',
        ):
            self.assertIn(technical, inbound)
        self.assertIn('"user.inbound.toggle"', users)
        self.assertIn("audit action ids", style)
        self.assertIn("lowercase `inbound` как пользовательский термин", style)


if __name__ == "__main__":
    unittest.main()
