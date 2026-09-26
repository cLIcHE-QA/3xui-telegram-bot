"""Regression coverage for the v4.20.10 compact Inbound keyboard follow-up."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class V42010InboundKeyboardTests(unittest.TestCase):
    def test_compact_five_row_inbound_keyboard_contract(self):
        text = source("inbound_admin.py")
        start = text.index("async def _inbound_card")
        end = text.index("@inbound_admin_router.callback_query", start)
        card = text[start:end]

        for left, right in (
            ('text="👥 Клиенты"', 'text="✏️ Изменить"'),
            ('text="🔄 Синхронизировать клиентов"', 'text="♻️ Сбросить трафик"'),
            ('text="📋 Клонировать"', 'text="🧩 Сохранить шаблон"'),
            ("text=toggle_text", 'text="🗑 Удалить"'),
        ):
            left_pos = card.index(left)
            right_pos = card.index(right)
            self.assertLess(left_pos, right_pos)

        self.assertIn('text="⬅ Inbounds"', card)
        self.assertNotIn('text="🗑 Удалить Inbound"', card)
        self.assertIn(
            'InlineKeyboardButton(text=toggle_text, callback_data=f"admin:inbound:toggle:{inbound_id}"),\n'
            '            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:inbound:deleteask:{inbound_id}"),',
            card,
        )

    def test_delete_confirmation_keeps_full_inbound_wording(self):
        text = source("inbound_admin.py")
        self.assertIn("🗑 Удалить Inbound #", text)
        self.assertIn("⚠️ Да, удалить Inbound", text)


if __name__ == "__main__":
    unittest.main()
