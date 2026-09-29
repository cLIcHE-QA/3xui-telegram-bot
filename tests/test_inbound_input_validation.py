"""Execute Inbound FSM validation paths without live Telegram or 3x-ui calls."""
from __future__ import annotations

import copy
import importlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage


class InboundInputValidationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = {
            "BOT_TOKEN": "123456789:offline-inbound-validation-token",
            "PANEL_URL": "https://panel.example.invalid/base",
            "PANEL_API_TOKEN": "offline-panel-token",
            "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/sub/{sub_id}",
            "ALLOWED_TELEGRAM_IDS": "1",
            "ADMIN_TELEGRAM_IDS": "1",
            "DB_PATH": str(Path(self.tmp.name) / "bot.sqlite3"),
        }
        with patch.dict(os.environ, env, clear=True):
            self.module = importlib.import_module("inbound_admin")
        self.storage = MemoryStorage()
        self.addAsyncCleanup(self.storage.close)
        self.source = {
            "id": 37,
            "remark": "Fixture",
            "port": 443,
            "protocol": "vless",
            "enable": True,
            "listen": "0.0.0.0",
            "total": 1024,
            "expiryTime": 123456,
            "nodeId": 9,
            "settings": {"clients": [{"email": "fixture@example.test"}]},
            "streamSettings": {"network": "tcp", "security": "tls"},
            "sniffing": {"enabled": True},
        }
        self.xui = SimpleNamespace(
            inbound_get=AsyncMock(return_value=self.source),
            inbound_add=AsyncMock(),
        )
        self.database = SimpleNamespace(
            create_inbound_template=AsyncMock(return_value=91),
            get_inbound_template=AsyncMock(
                return_value=SimpleNamespace(payload_json=json.dumps(self.source))
            ),
        )
        self.guard = AsyncMock(return_value=True)
        self.render = AsyncMock()
        self.audit = AsyncMock()
        self.port_free = AsyncMock(return_value=True)
        for name, value in (
            ("xui", self.xui),
            ("db", self.database),
            ("guard_message", self.guard),
            ("render_input", self.render),
            ("audit_from_message", self.audit),
            ("_port_free", self.port_free),
        ):
            replacement = patch.object(self.module, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)

    def reset_calls(self):
        for mock in (
            self.xui.inbound_get,
            self.xui.inbound_add,
            self.database.create_inbound_template,
            self.database.get_inbound_template,
            self.guard,
            self.render,
            self.audit,
            self.port_free,
        ):
            mock.reset_mock()

    async def make_state(self, kind, data):
        state = FSMContext(
            storage=self.storage,
            key=StorageKey(bot_id=1, chat_id=101, user_id=101),
        )
        await state.set_state(kind)
        await state.set_data(copy.deepcopy(data))
        return state

    def port_flows(self):
        return (
            (
                self.module.inbound_clone_port,
                self.module.InboundEditStates.clone_port,
                {"clone_inbound_id": 37, "clone_target_node": 2},
                "admin:inbound:37",
            ),
            (
                self.module.template_deploy_port,
                self.module.InboundEditStates.template_port,
                {"template_id": 91, "template_target_node": 2},
                "admin:inboundtemplate:91",
            ),
        )

    async def assert_validation(self, message, state, kind, data, text, callback):
        self.render.assert_awaited_once()
        args, kwargs = self.render.await_args
        self.assertEqual(args, (message, text))
        buttons = [
            button
            for row in kwargs["reply_markup"].inline_keyboard
            for button in row
        ]
        self.assertEqual([(button.text, button.callback_data) for button in buttons], [("✖ Отмена", callback)])
        self.assertEqual(await state.get_state(), kind.state)
        self.assertEqual(await state.get_data(), data)
        self.xui.inbound_add.assert_not_awaited()
        self.audit.assert_not_awaited()

    async def test_invalid_ports_keep_fsm_and_cancel_context_without_io(self):
        cases = (
            (None, "Нужен числовой порт."),
            ("", "Нужен числовой порт."),
            ("   ", "Нужен числовой порт."),
            ("abc", "Нужен числовой порт."),
            ("1.5", "Нужен числовой порт."),
            ("0", "Порт должен быть 1-65535."),
            ("-1", "Порт должен быть 1-65535."),
            ("65536", "Порт должен быть 1-65535."),
        )
        for handler, kind, data, callback in self.port_flows():
            for raw, text in cases:
                with self.subTest(handler=handler.__name__, raw=raw):
                    self.reset_calls()
                    state = await self.make_state(kind, data)
                    message = SimpleNamespace(text=raw)
                    await handler(message, state)
                    self.guard.assert_awaited_once_with(message, state)
                    await self.assert_validation(message, state, kind, data, text, callback)
                    self.port_free.assert_not_awaited()
                    self.xui.inbound_get.assert_not_awaited()
                    self.database.get_inbound_template.assert_not_awaited()
                    self.database.create_inbound_template.assert_not_awaited()

    async def test_invalid_template_names_keep_fsm_and_cancel_context_without_io(self):
        kind = self.module.InboundEditStates.template_name
        data = {"template_source_id": 37}
        for raw in (None, "", "   ", "x" * 65):
            with self.subTest(raw=raw):
                self.reset_calls()
                state = await self.make_state(kind, data)
                message = SimpleNamespace(text=raw)
                await self.module.inbound_template_save(message, state)
                await self.assert_validation(
                    message, state, kind, data,
                    "Имя должно быть от 1 до 64 символов.", "admin:inbound:37",
                )
                self.port_free.assert_not_awaited()
                self.xui.inbound_get.assert_not_awaited()
                self.database.get_inbound_template.assert_not_awaited()
                self.database.create_inbound_template.assert_not_awaited()

    async def test_occupied_ports_keep_fsm_without_creating_inbound(self):
        self.port_free.return_value = False
        for handler, kind, data, callback in self.port_flows():
            with self.subTest(handler=handler.__name__):
                self.reset_calls()
                state = await self.make_state(kind, data)
                message = SimpleNamespace(text="8443")
                await handler(message, state)
                await self.assert_validation(
                    message, state, kind, data,
                    "Этот порт уже занят на выбранном сервере.", callback,
                )
                self.port_free.assert_awaited_once_with(2, 8443)
                self.xui.inbound_get.assert_not_awaited()
                self.database.get_inbound_template.assert_not_awaited()
                self.database.create_inbound_template.assert_not_awaited()

    async def test_valid_port_boundaries_preserve_disabled_clientless_creation(self):
        original = copy.deepcopy(self.source)
        for handler, kind, data, _ in self.port_flows():
            node_key = "clone_target_node" if "clone_target_node" in data else "template_target_node"
            for node_id in (0, 2):
                for raw in ("1", "65535", " 8443 "):
                    with self.subTest(handler=handler.__name__, node_id=node_id, raw=raw):
                        self.reset_calls()
                        current_data = {**data, node_key: node_id}
                        state = await self.make_state(kind, current_data)
                        message = SimpleNamespace(text=raw)
                        await handler(message, state)
                        self.port_free.assert_awaited_once_with(node_id, int(raw))
                        self.xui.inbound_add.assert_awaited_once()
                        payload = self.xui.inbound_add.await_args.args[0]
                        self.assertEqual(payload["port"], int(raw))
                        self.assertIs(payload["enable"], False)
                        self.assertEqual(payload["settings"]["clients"], [])
                        self.assertEqual(payload["listen"], "")
                        if node_id:
                            self.assertEqual(payload["nodeId"], node_id)
                        else:
                            self.assertNotIn("nodeId", payload)
                        self.assertEqual(self.source, original)
                        self.audit.assert_awaited_once()
                        self.assertIsNone(await state.get_state())
                        self.assertEqual(await state.get_data(), {})
                        self.database.create_inbound_template.assert_not_awaited()
                        if "clone_inbound_id" in data:
                            self.xui.inbound_get.assert_awaited_once_with(37)
                            self.database.get_inbound_template.assert_not_awaited()
                            self.assertEqual(self.audit.await_args.kwargs["target_id"], "37")
                        else:
                            self.xui.inbound_get.assert_not_awaited()
                            self.database.get_inbound_template.assert_awaited_once_with(91)
                            self.assertEqual(self.audit.await_args.kwargs["target_id"], "91")

    async def test_valid_template_names_save_existing_safe_payload(self):
        original = copy.deepcopy(self.source)
        for raw in ("x", "x" * 64, "  Template  "):
            with self.subTest(raw=raw):
                self.reset_calls()
                state = await self.make_state(
                    self.module.InboundEditStates.template_name,
                    {"template_source_id": 37},
                )
                await self.module.inbound_template_save(SimpleNamespace(text=raw), state)
                self.xui.inbound_get.assert_awaited_once_with(37)
                self.database.create_inbound_template.assert_awaited_once()
                values = self.database.create_inbound_template.await_args.kwargs
                self.assertEqual(values["name"], raw.strip())
                self.assertEqual(values["source_inbound_id"], 37)
                self.assertEqual(values["protocol"], "vless")
                payload = json.loads(values["payload_json"])
                self.assertIs(payload["enable"], False)
                self.assertEqual(payload["settings"]["clients"], [])
                self.assertEqual(payload["total"], 0)
                self.assertEqual(payload["expiryTime"], 0)
                self.assertEqual(payload["listen"], "")
                self.assertEqual(self.source, original)
                self.xui.inbound_add.assert_not_awaited()
                self.audit.assert_awaited_once()
                self.assertIsNone(await state.get_state())
                self.assertEqual(await state.get_data(), {})

    async def test_duplicate_template_name_preserves_retry_and_cancel(self):
        self.database.create_inbound_template.side_effect = sqlite3.IntegrityError("duplicate")
        kind = self.module.InboundEditStates.template_name
        data = {"template_source_id": 37}
        state = await self.make_state(kind, data)
        message = SimpleNamespace(text="Template")
        await self.module.inbound_template_save(message, state)
        await self.assert_validation(
            message, state, kind, data,
            "Шаблон с таким именем уже существует.", "admin:inbound:37",
        )
        self.database.create_inbound_template.assert_awaited_once()

    async def test_valid_retry_after_invalid_port_reuses_original_context(self):
        for handler, kind, data, callback in self.port_flows():
            with self.subTest(handler=handler.__name__):
                self.reset_calls()
                state = await self.make_state(kind, data)
                invalid = SimpleNamespace(text="abc")
                await handler(invalid, state)
                await self.assert_validation(
                    invalid, state, kind, data, "Нужен числовой порт.", callback,
                )
                await handler(SimpleNamespace(text="8443"), state)
                self.xui.inbound_add.assert_awaited_once()
                self.port_free.assert_awaited_once_with(2, 8443)
                self.assertIsNone(await state.get_state())

    async def test_denied_guard_stops_before_reading_fsm_or_input(self):
        self.guard.return_value = False
        handlers = (
            self.module.inbound_clone_port,
            self.module.inbound_template_save,
            self.module.template_deploy_port,
        )
        for handler in handlers:
            with self.subTest(handler=handler.__name__):
                self.reset_calls()
                state = SimpleNamespace(get_data=AsyncMock())
                message = SimpleNamespace(text="abc")
                await handler(message, state)
                self.guard.assert_awaited_once_with(message, state)
                state.get_data.assert_not_awaited()
                self.render.assert_not_awaited()
                self.port_free.assert_not_awaited()
                self.xui.inbound_get.assert_not_awaited()
                self.xui.inbound_add.assert_not_awaited()
                self.database.get_inbound_template.assert_not_awaited()
                self.database.create_inbound_template.assert_not_awaited()
                self.audit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
