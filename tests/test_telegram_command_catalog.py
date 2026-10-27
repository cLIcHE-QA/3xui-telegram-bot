from __future__ import annotations

import importlib.util
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from admin_navigation import system_menu
from admin_privileges import required_role_for_callback
from telegram_commands import CATALOG_REVISION, COMMANDS, commands_help_text, validate_catalog

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("command_catalog_checker", ROOT / "scripts" / "check-telegram-command-catalog.py")
assert _spec and _spec.loader
_checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_checker)


class TelegramCommandCatalogTests(unittest.TestCase):
    def test_catalog_matches_real_handler_ast(self):
        validate_catalog()
        _checker.check_catalog(ROOT)
        self.assertEqual(set(x.name for x in COMMANDS),
                         {"admin", "start", "subscription", "paysupport", "create", "inbounds"})
        self.assertEqual({x.name for x in COMMANDS if x.status == "legacy"}, {"create", "inbounds"})
        self.assertEqual([x.name for x in COMMANDS if x.audience == "admin"], ["admin"])

    def test_aliases_command_start_and_multi_command_are_scanned(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sample.py"
            p.write_text(
                "from aiogram.filters import Command as Slash, CommandStart as Entry\n"
                "@router.message(Slash('first', 'second'))\n"
                "async def one(message): pass\n"
                "@router.message(Entry())\n"
                "async def two(message): pass\n", encoding="utf-8"
            )
            self.assertEqual(_checker.scan_module(p), {
                ("first", "sample.py", "one"),
                ("second", "sample.py", "one"),
                ("start", "sample.py", "two"),
            })

    def test_unknown_dynamic_registration_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sample.py"
            for source in (
                "from aiogram.filters import Command\n@router.message(Command(DYNAMIC))\nasync def one(m): pass\n",
                "from aiogram.filters import CommandStart\n@router.message(CommandStart(deep_link=True))\nasync def one(m): pass\n",
                "from aiogram.filters import Command\n@router.message(Command('x', variable))\nasync def one(m): pass\n",
            ):
                p.write_text(source, encoding="utf-8")
                with self.assertRaises(ValueError):
                    _checker.scan_module(p)

    def test_registry_drift_detects_removed_and_added_handlers(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "example.py"
            path.write_text(
                "from aiogram.filters import Command\n@router.message(Command('unexpected'))\nasync def handler(m): pass\n",
                encoding="utf-8"
            )
            found = _checker.scan_repository(root)
            declared = {(x.name, x.source, x.handler) for x in COMMANDS}
            self.assertNotEqual(found, declared)
            self.assertIn(("unexpected", "example.py", "handler"), found - declared)
            self.assertIn(("admin", "admin_shell.py", "admin"), declared - found)

    def test_help_ui_privilege_and_no_commands_are_executed(self):
        for role in ("read_only", "support", "admin", "owner"):
            buttons = {
                button.callback_data: button.text
                for row in system_menu(role).inline_keyboard for button in row
            }
            self.assertEqual(buttons["admin:commands"], "📚 Команды бота")
        self.assertEqual(required_role_for_callback("admin:commands"), "read_only")
        self.assertIsNone(required_role_for_callback("admin:commands:run"))
        text = commands_help_text()
        self.assertIn(f"Каталог: v{CATALOG_REVISION}", text)
        self.assertIn("CLIENT_PORTAL_ENABLED", text)
        self.assertIn("/admin", text)
        for name in ("start", "subscription", "paysupport"):
            self.assertIn(f"/{name} —", text)
        for name in ("create", "inbounds"):
            self.assertNotIn(f"/{name}", text)
        self.assertIn("Основной вход клиента: /start", text)
        self.assertNotIn("/help —", text)
        source = (ROOT / "admin_shell.py").read_text(encoding="utf-8")
        self.assertIn('F.data == "admin:commands"', source)
        self.assertIn('callback_data="admin:section:system"', source)
        self.assertIn('ok, role = await authorize_callback(db, settings, call)', source)

    def test_hidden_legacy_handlers_still_require_catalog_entries(self):
        # UI visibility must never shrink the authoritative AST audit set.
        with patch("telegram_commands.COMMANDS", tuple(x for x in COMMANDS if x.name != "create")):
            with self.assertRaisesRegex(ValueError, "unlisted=.*create"):
                _checker.check_catalog(ROOT)

    def test_invalid_hidden_status_is_not_silently_filtered_out(self):
        broken = tuple(replace(x, status="hidden") if x.name == "create" else x for x in COMMANDS)
        with patch("telegram_commands.COMMANDS", broken):
            with self.assertRaisesRegex(ValueError, "Invalid command metadata"):
                commands_help_text()


if __name__ == "__main__":
    unittest.main()
