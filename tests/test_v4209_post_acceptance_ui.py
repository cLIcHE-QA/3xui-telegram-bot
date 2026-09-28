"""Regression coverage for the v4.20.9 post-acceptance UI cleanup."""
from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _literal_text(node: ast.AST | None) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                parts.append("{}")
        return "".join(parts)
    return ""


class V4209PostAcceptanceUiTests(unittest.TestCase):
    def test_template_prompt_hides_internal_database_filename(self):
        text = source("inbound_admin.py")
        self.assertIn(
            "Введи имя шаблона. В шаблон попадёт конфигурация Inbound без клиентов.",
            text,
        )
        self.assertNotIn("он будет храниться в bot.sqlite3", text)

    def test_inbound_card_uses_compact_five_row_keyboard(self):
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

    def test_delete_entry_buttons_always_route_to_confirmation(self):
        offenders: list[str] = []
        for path in sorted(ROOT.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
                if name != "InlineKeyboardButton":
                    continue
                kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
                label = _literal_text(kwargs.get("text"))
                if "Удалить" not in label or "⚠️" in label:
                    continue
                callback = _literal_text(kwargs.get("callback_data"))
                if "deleteask" not in callback and "admindelask" not in callback and "devdelask" not in callback:
                    offenders.append(f"{path.name}:{node.lineno}:{label} -> {callback}")

        self.assertEqual(offenders, [])

    def test_delete_ask_handlers_do_not_execute_delete_mutations(self):
        offenders: list[str] = []
        for path in sorted(ROOT.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in tree.body:
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                is_delete_ask = "delete_ask" in node.name or node.name == "admin_del_ask"
                if not is_delete_ask:
                    continue
                for call in ast.walk(node):
                    if not isinstance(call, ast.Call):
                        continue
                    func = call.func
                    name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
                    if name.startswith("delete_") or name in {"inbound_delete", "node_delete"}:
                        offenders.append(f"{path.name}:{node.lineno}:{node.name} -> {name}")

        self.assertEqual(offenders, [])

    def test_deletion_confirmation_contract_is_documented(self):
        style = source("docs/UI_STYLE.md")
        self.assertIn("one-click delete не допускается", style)
        self.assertIn("первый клик только открывает отдельный confirmation screen", style)
        self.assertIn("mutation находится только за отдельным confirm callback/handler", style)


if __name__ == "__main__":
    unittest.main()
