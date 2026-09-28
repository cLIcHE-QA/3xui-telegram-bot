from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import AsyncMock

from admin_privileges import required_role_for_callback
from xui import DEFAULT_HWID_LIMIT, XUIClient


ROOT = Path(__file__).resolve().parents[1]


class V4250UserCreateTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_client_uses_single_no_retry_mutation_request(self):
        client = XUIClient("https://panel.example.invalid", "token")
        client._mutation_request = AsyncMock(return_value={"success": True})
        await client.create_client(
            email="tg_101",
            telegram_id=101,
            sub_id="sub-id",
            inbound_ids=[1, 2],
            total_bytes=1024,
            expiry_time_ms=123456,
            limit_ip=2,
            comment="created",
            flow="xtls-rprx-vision",
        )
        client._mutation_request.assert_awaited_once()
        args, kwargs = client._mutation_request.await_args
        self.assertEqual(args, ("/panel/api/clients/add",))
        payload = kwargs["json_payload"]
        self.assertEqual(payload["client"]["email"], "tg_101")
        self.assertEqual(payload["client"]["tgId"], 101)
        self.assertEqual(payload["client"]["subId"], "sub-id")
        self.assertEqual(payload["client"]["limitHwid"], DEFAULT_HWID_LIMIT)
        self.assertEqual(payload["inboundIds"], [1, 2])

    def test_create_email_not_found_normalizes_production_response(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        helper = source.split("async def _email_available", 1)[1].split(
            "async def _trial_create_values", 1
        )[0]
        self.assertIn('message.lower() == "obtain (record not found)"', helper)
        self.assertIn('message.startswith("Client not found:")', helper)

    def test_create_preview_and_run_use_default_hwid_limit(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        self.assertIn('f"HWID limit: {DEFAULT_HWID_LIMIT}"', source)
        self.assertIn("limit_hwid=DEFAULT_HWID_LIMIT", source)

    def test_create_callbacks_require_support(self):
        callbacks = (
            "admin:users:create",
            "admin:users:create:email-default",
            "admin:users:create:email-custom",
            "admin:users:create:display-skip",
            "admin:users:create:plans",
            "admin:users:create:plan-compat",
            "admin:users:create:plan:7",
            "admin:users:create:run",
            "admin:users:create:recover:101",
        )
        for callback in callbacks:
            with self.subTest(callback=callback):
                self.assertEqual(required_role_for_callback(callback), "support")

    def test_user_list_shows_create_only_for_support_roles(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        view = source.split("async def _users_page_view", 1)[1].split(
            '@advanced_users_router.callback_query(F.data == "admin:users")',
            1,
        )[0]
        self.assertIn('text="➕ Создать"', view)
        self.assertIn('callback_data="admin:users:create"', view)
        self.assertIn('if role in {"support", "admin", "owner"}:', view)

    def test_create_flow_has_no_partial_create_action(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        self.assertNotIn("💾 Только создать", source)
        self.assertIn("Целевые Inbounds", source)
        self.assertIn('callback_data="admin:users:create:run"', source)

    def test_create_mutation_is_single_and_local_write_follows_remote_proof(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        run = source.split(
            '@advanced_users_router.callback_query(F.data == "admin:users:create:run")',
            1,
        )[1].split(
            '@advanced_users_router.callback_query(F.data.regexp(r"^admin:users:create:recover:',
            1,
        )[0]
        self.assertEqual(run.count("await xui.create_client("), 1)
        self.assertIn("except XUIMutationError as exc:", run)
        self.assertIn("if not exc.uncertain:", run)
        self.assertIn("await xui.get_client_by_tg_id(tg_id)", run)
        self.assertIn("mutation_not_retried=true", run)
        self.assertGreater(run.index("await db.put("), run.index("await xui.create_client("))

    def test_recovery_is_read_only_against_panel(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        recovery = source.split(
            '@advanced_users_router.callback_query(F.data.regexp(r"^admin:users:create:recover:',
            1,
        )[1].split(
            '@advanced_users_router.callback_query(F.data == "admin:users:search")',
            1,
        )[0]
        self.assertIn("await xui.get_client_by_tg_id(tg_id)", recovery)
        self.assertNotIn("create_client(", recovery)
        self.assertIn("explicit_recovery=true", recovery)

    def test_create_audit_does_not_store_subscription_secret(self):
        source = (ROOT / "advanced_users.py").read_text(encoding="utf-8")
        run = source.split(
            '@advanced_users_router.callback_query(F.data == "admin:users:create:run")',
            1,
        )[1].split(
            '@advanced_users_router.callback_query(F.data.regexp(r"^admin:users:create:recover:',
            1,
        )[0]
        audit_tail = run.split('"user.create"', 1)[1]
        self.assertNotIn("sub_id=", audit_tail)
        self.assertNotIn("sub_url(", audit_tail)


if __name__ == "__main__":
    unittest.main()
