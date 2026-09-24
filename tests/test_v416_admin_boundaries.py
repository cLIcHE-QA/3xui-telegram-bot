from __future__ import annotations

import importlib
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from admin_privileges import ROLE_RANK, required_role_for_callback
from xui import XUIError


def load_module(name: str):
    env = {
        "BOT_TOKEN": "123456789:offline-v416-token",
        "PANEL_URL": "https://panel.example.invalid/base",
        "PANEL_API_TOKEN": "offline-v416-token",
        "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/sub/{sub_id}",
        "COMPAT_SUBSCRIPTION_URL_TEMPLATE": "https://public.example.invalid/compat/{sub_id}",
        "ALLOWED_TELEGRAM_IDS": "1",
        "ADMIN_TELEGRAM_IDS": "1",
        "DB_PATH": "/tmp/v416-admin-boundaries.sqlite3",
    }
    with patch.dict(os.environ, env, clear=False):
        return importlib.import_module(name)


class AdminBoundaryRegressionTests(unittest.IsolatedAsyncioTestCase):
    def test_sensitive_callbacks_do_not_drop_below_required_roles(self):
        cases = {
            "admin:u:planapplyrun:101": "support",
            "admin:u:planprovrun:101": "support",
            "admin:u:provrun:101:safe": "support",
            "admin:u:provrun:101:strict": "admin",
            "admin:u:subrotateask:101": "admin",
            "admin:u:subrotaterun:101": "admin",
            "admin:inbound:toggle:7": "admin",
            "admin:inbound:syncrun:7": "admin",
            "admin:inbound:resetrun:7": "admin",
            "admin:inbound:delete:7": "admin",
            "admin:payment:status:9:paid": "admin",
            "admin:promo:delete:5": "admin",
            "admin:administrator:delete:123": "owner",
            "admin:restore:bot:backup-1": "owner",
            "admin:restore:xui:backup-1": "owner",
            "admin:restore:node:backup-1:2": "owner",
        }
        for callback, expected in cases.items():
            with self.subTest(callback=callback):
                actual = required_role_for_callback(callback)
                self.assertEqual(actual, expected)
                self.assertGreaterEqual(ROLE_RANK[actual], ROLE_RANK[expected])

    def test_near_miss_sensitive_callbacks_fail_closed(self):
        values = (
            "admin:u:provrun:101:unsafe",
            "admin:restore:node:backup-1:not-a-node",
            "admin:administrator:delete",
            "admin:inboundtemplate:delete:not-a-number",
            "admin:payment:status",
            "admin:ver:unlock:not-a-valid-operation",
        )
        for value in values:
            with self.subTest(value=value):
                self.assertIsNone(required_role_for_callback(value))

    async def test_subscription_rotation_updates_local_identity_only_after_xui_success(self):
        module = load_module("advanced_users")
        rec = SimpleNamespace(
            telegram_id=101,
            email="user101@example.test",
            sub_id="old-sub",
            expiry_time=0,
        )
        db_mock = SimpleNamespace(
            get=AsyncMock(return_value=rec),
            get_by_sub_id=AsyncMock(return_value=None),
            update_sub_id=AsyncMock(),
        )
        xui_mock = SimpleNamespace(update_client=AsyncMock(side_effect=XUIError("offline")))
        call = SimpleNamespace(
            data="admin:u:subrotaterun:101",
            answer=AsyncMock(),
        )

        with (
            patch.object(module, "guard", new=AsyncMock(return_value=True)),
            patch.object(module, "db", db_mock),
            patch.object(module, "xui", xui_mock),
            patch.object(module, "audit_from_call", new=AsyncMock()),
            patch.object(module, "render_callback", new=AsyncMock()),
            patch.object(module.secrets, "token_urlsafe", return_value="new-sub-id"),
        ):
            await module.user_sub_rotate_run(call)

        xui_mock.update_client.assert_awaited_once_with("user101@example.test", subId="new-sub-id")
        db_mock.update_sub_id.assert_not_awaited()

    async def test_subscription_rotation_commits_local_identity_after_xui_success(self):
        module = load_module("advanced_users")
        rec = SimpleNamespace(
            telegram_id=101,
            email="user101@example.test",
            sub_id="old-sub",
            expiry_time=0,
        )
        db_mock = SimpleNamespace(
            get=AsyncMock(return_value=rec),
            get_by_sub_id=AsyncMock(return_value=None),
            update_sub_id=AsyncMock(),
        )
        xui_mock = SimpleNamespace(update_client=AsyncMock())
        call = SimpleNamespace(
            data="admin:u:subrotaterun:101",
            answer=AsyncMock(),
        )

        with (
            patch.object(module, "guard", new=AsyncMock(return_value=True)),
            patch.object(module, "db", db_mock),
            patch.object(module, "xui", xui_mock),
            patch.object(module, "audit_from_call", new=AsyncMock()),
            patch.object(module, "render_callback", new=AsyncMock()),
            patch.object(module.secrets, "token_urlsafe", return_value="new-sub-id"),
        ):
            await module.user_sub_rotate_run(call)

        xui_mock.update_client.assert_awaited_once_with("user101@example.test", subId="new-sub-id")
        db_mock.update_sub_id.assert_awaited_once_with(101, "new-sub-id")

    async def test_plan_apply_does_not_update_local_expiry_when_remote_mutation_fails(self):
        module = load_module("advanced_users")
        rec = SimpleNamespace(telegram_id=101, email="user101@example.test", expiry_time=0)
        profile = SimpleNamespace(plan_id=7, server_group_id=None)
        plan = SimpleNamespace(
            id=7,
            name="Premium",
            duration_days=30,
            traffic_gb=100,
            ip_limit=2,
            server_group_id=3,
        )
        db_mock = SimpleNamespace(
            get=AsyncMock(return_value=rec),
            get_user_profile=AsyncMock(return_value=profile),
            get_plan=AsyncMock(return_value=plan),
            update_expiry=AsyncMock(),
            set_user_server_group=AsyncMock(),
        )
        xui_mock = SimpleNamespace(update_client=AsyncMock(side_effect=XUIError("failed")))
        call = SimpleNamespace(
            data="admin:u:planapplyrun:101",
            answer=AsyncMock(),
        )

        with (
            patch.object(module, "guard", new=AsyncMock(return_value=True)),
            patch.object(module, "db", db_mock),
            patch.object(module, "xui", xui_mock),
            patch.object(module, "audit_from_call", new=AsyncMock()),
            patch.object(module, "render_callback", new=AsyncMock()),
        ):
            await module.user_plan_apply_run(call)

        db_mock.update_expiry.assert_not_awaited()
        db_mock.set_user_server_group.assert_not_awaited()

    def test_inbound_template_and_clone_payloads_never_copy_clients_or_enable_state(self):
        module = load_module("inbound_admin")
        inbound = {
            "id": 7,
            "enable": True,
            "remark": "Reality",
            "listen": "0.0.0.0",
            "port": 443,
            "protocol": "vless",
            "expiryTime": 123,
            "total": 456,
            "settings": {
                "clients": [
                    {"email": "secret@example.test", "id": "client-secret"}
                ],
                "decryption": "none",
            },
            "streamSettings": {
                "network": "xhttp",
                "security": "reality",
                "realitySettings": {
                    "settings": {"fingerprint": "chrome"},
                    "serverNames": ["example.com"],
                },
            },
            "sniffing": {"enabled": True},
            "nodeId": 2,
        }

        template = module._template_payload(inbound)
        self.assertFalse(template["enable"])
        self.assertEqual(template["settings"]["clients"], [])
        self.assertEqual(template["total"], 0)
        self.assertEqual(template["expiryTime"], 0)
        self.assertEqual(template["listen"], "")

        clone = module._clone_payload(inbound, port=8443, node_id=3)
        self.assertFalse(clone["enable"])
        self.assertEqual(clone["settings"]["clients"], [])
        self.assertEqual(clone["port"], 8443)
        self.assertEqual(clone["nodeId"], 3)

        master = module._deploy_payload(template, port=9443, node_id=None)
        self.assertFalse(master["enable"])
        self.assertEqual(master["settings"]["clients"], [])
        self.assertNotIn("nodeId", master)

    def test_reality_fingerprint_validation_is_fail_closed(self):
        module = load_module("inbound_admin")
        inbound = {
            "streamSettings": {
                "security": "reality",
                "realitySettings": {
                    "settings": {"fingerprint": "chrome"},
                },
            }
        }
        old = module._set_reality_fingerprint(inbound, "firefox")
        self.assertEqual(old, "chrome")
        self.assertEqual(module._reality_fingerprint(inbound), "firefox")

        with self.assertRaises(ValueError):
            module._set_reality_fingerprint(inbound, "made-up-browser")

        non_reality = {"streamSettings": {"security": "tls"}}
        with self.assertRaises(ValueError):
            module._set_reality_fingerprint(non_reality, "chrome")


if __name__ == "__main__":
    unittest.main()
