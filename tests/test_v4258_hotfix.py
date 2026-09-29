from __future__ import annotations

import importlib
import os
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage


def load_module(name: str):
    env = {
        "BOT_TOKEN": "123456789:offline-v4258-token",
        "PANEL_URL": "https://panel.example.invalid/base",
        "PANEL_API_TOKEN": "offline-v4258-token",
        "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/sub/{sub_id}",
        "ALLOWED_TELEGRAM_IDS": "1",
        "ADMIN_TELEGRAM_IDS": "1",
        "DB_PATH": "/tmp/v4258-hotfix.sqlite3",
    }
    with patch.dict(os.environ, env, clear=False):
        return importlib.import_module(name)


def callbacks(markup):
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
    ]


class V4258HotfixTests(unittest.IsolatedAsyncioTestCase):
    def test_bug_issue_lifecycle_is_documented(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / "docs" / "GIT_WORKFLOW.md").read_text(encoding="utf-8")
        for needle in (
            "Закрытие bug-issue после исправления",
            "targeted verification подтверждает",
            "закрывается как `completed`",
            "Новый независимый finding",
        ):
            self.assertIn(needle, workflow)

    async def asyncSetUp(self):
        self.storage = MemoryStorage()

    async def make_state(self, user_id: int = 555) -> FSMContext:
        return FSMContext(
            storage=self.storage,
            key=StorageKey(bot_id=1, chat_id=user_id, user_id=user_id),
        )

    async def test_clone_target_cancel_returns_to_source_inbound(self):
        module = load_module("inbound_admin")
        render = AsyncMock()
        call = SimpleNamespace(
            data="admin:inbound:clone:37",
            answer=AsyncMock(),
        )
        with (
            patch.object(module, "guard", new=AsyncMock(return_value=True)),
            patch.object(module, "render_callback", new=render),
            patch.object(
                module,
                "xui",
                SimpleNamespace(nodes_list=AsyncMock(return_value=[])),
            ),
        ):
            await module.inbound_clone_start(call)

        markup = render.await_args.kwargs["reply_markup"]
        self.assertEqual(callbacks(markup)[-1], "admin:inbound:37")

    async def test_template_target_cancel_keeps_template_parent(self):
        module = load_module("inbound_admin")
        render = AsyncMock()
        call = SimpleNamespace(
            data="admin:inboundtemplate:deploy:91",
            answer=AsyncMock(),
        )
        with (
            patch.object(module, "guard", new=AsyncMock(return_value=True)),
            patch.object(module, "render_callback", new=render),
            patch.object(
                module,
                "xui",
                SimpleNamespace(nodes_list=AsyncMock(return_value=[])),
            ),
            patch.object(
                module,
                "db",
                SimpleNamespace(
                    get_inbound_template=AsyncMock(return_value=SimpleNamespace(id=91)),
                ),
            ),
        ):
            await module.template_deploy_start(call)

        markup = render.await_args.kwargs["reply_markup"]
        self.assertEqual(callbacks(markup)[-1], "admin:inboundtemplate:91")

    async def test_owner_self_demotion_requires_confirmation(self):
        module = load_module("business_admin")
        state = await self.make_state()
        rec = SimpleNamespace(
            telegram_id=555,
            role="owner",
            enabled=True,
            added_by=1,
            created_at=1,
        )
        db_mock = SimpleNamespace(
            get_administrator=AsyncMock(return_value=rec),
            upsert_administrator=AsyncMock(),
        )
        render = AsyncMock()
        audit = AsyncMock()
        call = SimpleNamespace(
            data="admin:administrator:role:555:read_only",
            from_user=SimpleNamespace(id=555),
            answer=AsyncMock(),
        )

        with (
            patch.object(module, "guard", new=AsyncMock(return_value=True)),
            patch.object(module, "db", db_mock),
            patch.object(module, "render_callback", new=render),
            patch.object(module, "audit_from_call", new=audit),
            patch.object(module.secrets, "token_hex", return_value="a1b2c3d4"),
        ):
            await module.administrator_role(call, state)

        db_mock.upsert_administrator.assert_not_awaited()
        audit.assert_not_awaited()
        self.assertEqual(
            await state.get_state(),
            module.AdministratorRoleStates.self_demote.state,
        )
        data = await state.get_data()
        self.assertEqual(data["administrator_self_role_actor"], 555)
        self.assertEqual(data["administrator_self_role_target"], 555)
        self.assertEqual(data["administrator_self_role_from"], "owner")
        self.assertEqual(data["administrator_self_role_to"], "read_only")
        self.assertEqual(data["administrator_self_role_nonce"], "a1b2c3d4")

        markup = render.await_args.kwargs["reply_markup"]
        values = callbacks(markup)
        self.assertIn(
            "admin:admsd:run:555:read_only:a1b2c3d4",
            values,
        )
        self.assertIn("admin:administrator:555", values)
        self.assertLessEqual(
            len("admin:admsd:run:555:read_only:a1b2c3d4".encode("utf-8")),
            64,
        )

    async def test_owner_self_demotion_stale_run_is_blocked(self):
        module = load_module("business_admin")
        state = await self.make_state()
        db_mock = SimpleNamespace(
            get_administrator=AsyncMock(),
            upsert_administrator=AsyncMock(),
        )
        audit = AsyncMock()
        render = AsyncMock()
        call = SimpleNamespace(
            data="admin:admsd:run:555:read_only:deadbeef",
            from_user=SimpleNamespace(id=555),
            answer=AsyncMock(),
        )

        with (
            patch.object(module, "guard", new=AsyncMock(return_value=True)),
            patch.object(module, "db", db_mock),
            patch.object(module, "audit_from_call", new=audit),
            patch.object(module, "render_callback", new=render),
        ):
            await module.administrator_self_role_run(call, state)

        db_mock.get_administrator.assert_not_awaited()
        db_mock.upsert_administrator.assert_not_awaited()
        audit.assert_not_awaited()
        render.assert_not_awaited()
        call.answer.assert_awaited_once()
        self.assertTrue(call.answer.await_args.kwargs["show_alert"])

    async def test_owner_self_demotion_confirm_mutates_once_and_clears_state(self):
        module = load_module("business_admin")
        state = await self.make_state()
        await state.set_state(module.AdministratorRoleStates.self_demote)
        await state.set_data({
            "administrator_self_role_actor": 555,
            "administrator_self_role_target": 555,
            "administrator_self_role_from": "owner",
            "administrator_self_role_to": "read_only",
            "administrator_self_role_nonce": "a1b2c3d4",
        })
        rec = SimpleNamespace(
            telegram_id=555,
            role="owner",
            enabled=True,
            added_by=1,
            created_at=1,
        )
        db_mock = SimpleNamespace(
            get_administrator=AsyncMock(return_value=rec),
            upsert_administrator=AsyncMock(),
        )
        audit = AsyncMock()
        render = AsyncMock()
        call = SimpleNamespace(
            data="admin:admsd:run:555:read_only:a1b2c3d4",
            from_user=SimpleNamespace(id=555),
            answer=AsyncMock(),
        )

        with (
            patch.object(module, "guard", new=AsyncMock(return_value=True)),
            patch.object(module, "db", db_mock),
            patch.object(module, "audit_from_call", new=audit),
            patch.object(module, "render_callback", new=render),
        ):
            await module.administrator_self_role_run(call, state)

        db_mock.upsert_administrator.assert_awaited_once_with(
            telegram_id=555,
            role="read_only",
            enabled=True,
            added_by=1,
        )
        audit.assert_awaited_once()
        self.assertIn("owner->read_only; self_demote=1", audit.await_args.kwargs["details"])
        self.assertIsNone(await state.get_state())
        self.assertEqual(await state.get_data(), {})
        markup = render.await_args.kwargs["reply_markup"]
        self.assertEqual(callbacks(markup), ["admin:home"])

    async def test_owner_self_demotion_cancel_clears_confirmation_and_returns_to_card(self):
        module = load_module("business_admin")
        state = await self.make_state()
        await state.set_state(module.AdministratorRoleStates.self_demote)
        await state.set_data({
            "administrator_self_role_actor": 555,
            "administrator_self_role_target": 555,
            "administrator_self_role_from": "owner",
            "administrator_self_role_to": "support",
            "administrator_self_role_nonce": "a1b2c3d4",
        })
        rec = SimpleNamespace(
            telegram_id=555,
            role="owner",
            enabled=True,
            added_by=1,
            created_at=1,
        )
        db_mock = SimpleNamespace(
            get_administrator=AsyncMock(return_value=rec),
            upsert_administrator=AsyncMock(),
        )
        render = AsyncMock()
        call = SimpleNamespace(
            data="admin:administrator:555",
            from_user=SimpleNamespace(id=555),
            answer=AsyncMock(),
        )

        with (
            patch.object(module, "guard", new=AsyncMock(return_value=True)),
            patch.object(module, "db", db_mock),
            patch.object(module, "render_callback", new=render),
        ):
            await module.administrator_detail(call, state)

        self.assertIsNone(await state.get_state())
        self.assertEqual(await state.get_data(), {})
        db_mock.upsert_administrator.assert_not_awaited()
        self.assertIn("👮 TG 555", render.await_args.args[1])

    async def test_owner_can_still_change_other_database_administrator_directly(self):
        module = load_module("business_admin")
        state = await self.make_state()
        rec = SimpleNamespace(
            telegram_id=777,
            role="admin",
            enabled=True,
            added_by=1,
            created_at=1,
        )
        db_mock = SimpleNamespace(
            get_administrator=AsyncMock(return_value=rec),
            upsert_administrator=AsyncMock(),
        )
        audit = AsyncMock()
        render = AsyncMock()
        call = SimpleNamespace(
            data="admin:administrator:role:777:support",
            from_user=SimpleNamespace(id=555),
            answer=AsyncMock(),
        )

        with (
            patch.object(module, "guard", new=AsyncMock(return_value=True)),
            patch.object(module, "db", db_mock),
            patch.object(module, "audit_from_call", new=audit),
            patch.object(module, "render_callback", new=render),
        ):
            await module.administrator_role(call, state)

        db_mock.upsert_administrator.assert_awaited_once_with(
            telegram_id=777,
            role="support",
            enabled=True,
            added_by=1,
        )
        audit.assert_awaited_once()
        self.assertIsNone(await state.get_state())

    async def test_local_break_glass_owner_remains_immutable(self):
        module = load_module("business_admin")
        state = await self.make_state(user_id=1)
        db_mock = SimpleNamespace(
            get_administrator=AsyncMock(),
            upsert_administrator=AsyncMock(),
        )
        call = SimpleNamespace(
            data="admin:administrator:role:1:read_only",
            from_user=SimpleNamespace(id=1),
            answer=AsyncMock(),
        )

        with (
            patch.object(module, "guard", new=AsyncMock(return_value=True)),
            patch.object(module, "db", db_mock),
        ):
            await module.administrator_role(call, state)

        db_mock.get_administrator.assert_not_awaited()
        db_mock.upsert_administrator.assert_not_awaited()
        call.answer.assert_awaited_once_with("Изменение запрещено.", show_alert=True)


if __name__ == "__main__":
    unittest.main()
