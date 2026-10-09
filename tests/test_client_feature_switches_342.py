from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from client_flags import ClientFeatureFlags, parse_override, parse_revision
from db import Database
from admin_privileges import required_role_for_callback


def env(portal=True, stars=True):
    return SimpleNamespace(client_portal_enabled=portal, client_payment_acceptance_enabled=stars)


class ClientFlagTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "bot.sqlite3"))
        await self.db.init()

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_default_env_veto_and_db_override(self):
        for portal_env, stars_env in ((True, True), (False, True), (True, False), (False, False)):
            sw = ClientFeatureFlags(self.db, env(portal_env, stars_env))
            state = await sw.snapshot()
            self.assertEqual(state.portal_enabled, portal_env)
            self.assertEqual(state.stars_enabled, portal_env and stars_env)
        self.assertTrue(await self.db.compare_and_set_feature_flag(
            key="client_portal_enabled", expected_revision=0, enabled=False, actor_id=101
        ))
        state = await ClientFeatureFlags(self.db, env()).snapshot()
        self.assertFalse(state.portal_enabled)
        self.assertFalse(state.stars_enabled)
        self.assertFalse((await ClientFeatureFlags(self.db, env(False, True)).snapshot()).portal_enabled)
        self.assertTrue(await self.db.compare_and_set_feature_flag(
            key="client_portal_enabled", expected_revision=1, enabled=True, actor_id=101
        ))
        self.assertFalse((await ClientFeatureFlags(self.db, env(False, True)).snapshot()).portal_enabled)
        self.assertTrue((await ClientFeatureFlags(self.db, env()).snapshot()).stars_enabled)

    async def test_cas_revision_audit_replay_and_restart(self):
        key = "client_payment_acceptance_enabled"
        self.assertTrue(await self.db.compare_and_set_feature_flag(
            key=key, expected_revision=0, enabled=False, actor_id=333, actor_username="Owner"
        ))
        self.assertFalse(await self.db.compare_and_set_feature_flag(
            key=key, expected_revision=0, enabled=True, actor_id=333
        ))
        restarted = Database(self.db.path)
        await restarted.init()
        state = await ClientFeatureFlags(restarted, env()).snapshot()
        self.assertFalse(state.stars_enabled)
        self.assertEqual(state.stars_revision, 1)
        self.assertTrue(await restarted.compare_and_set_feature_flag(
            key=key, expected_revision=1, enabled=True, actor_id=333
        ))
        self.assertTrue(await restarted.compare_and_set_feature_flag(
            key=key, expected_revision=2, enabled=False, actor_id=333
        ))
        self.assertFalse(await restarted.compare_and_set_feature_flag(
            key=key, expected_revision=1, enabled=False, actor_id=333
        ))
        with sqlite3.connect(self.db.path) as con:
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM audit_log WHERE action='client.feature.toggle'"
            ).fetchone()[0], 3)
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM runtime_settings WHERE key LIKE 'client_payment_acceptance_enabled%'"
            ).fetchone()[0], 2)

    async def test_invalid_state_or_db_unavailable_fail_closed(self):
        await self.db.set_runtime_setting("client_portal_enabled", "unexpected")
        state = await ClientFeatureFlags(self.db, env()).snapshot()
        self.assertFalse(state.available)
        self.assertFalse(state.portal_enabled)
        self.assertFalse(state.stars_enabled)
        await self.db.delete_runtime_setting("client_portal_enabled")
        await self.db.set_runtime_setting("client_portal_enabled:revision", "-1")
        self.assertFalse((await ClientFeatureFlags(self.db, env()).snapshot()).available)
        with patch.object(self.db, "get_feature_flag_records", side_effect=sqlite3.OperationalError("offline")):
            state = await ClientFeatureFlags(self.db, env()).snapshot()
        self.assertFalse(state.available)
        self.assertFalse(state.stars_enabled)
        for value in ("1", "TRUE", "", 0, True):
            with self.assertRaises(ValueError):
                parse_override(value)
        for value in ("-1", "bad", "2147483647"):
            with self.assertRaises(ValueError):
                parse_revision(value)

    async def test_stars_precheckout_denied_even_for_preexisting_invoice(self):
        import client_access
        flags = ClientFeatureFlags(self.db, env())
        await self.db.set_runtime_setting("client_payment_acceptance_enabled", "false")
        query = SimpleNamespace(from_user=SimpleNamespace(id=123), invoice_payload="stars:v1:1:123",
            currency="XTR", total_amount=1, answer=AsyncMock())
        with patch.object(client_access, "feature_flags", flags):
            await client_access.stars_pre_checkout(query)
        query.answer.assert_awaited_once_with(
            ok=False, error_message="Приём новых платежей временно отключён."
        )

    async def test_unauthorized_callback_never_maps_to_mutation(self):
        self.assertEqual(required_role_for_callback("admin:settings:client"), "read_only")
        for code in (
            "admin:settings:client:portal:ask:off:0",
            "admin:settings:client:portal:run:on:1",
            "admin:settings:client:stars:run:off:120",
        ):
            self.assertEqual(required_role_for_callback(code), "owner")
        self.assertIsNone(required_role_for_callback("admin:settings:client:portal:run:other:1"))

    def test_successful_payment_handler_has_no_switch_veto(self):
        source = (Path(__file__).resolve().parents[1] / "client_access.py").read_text(encoding="utf-8")
        handler = source.split("@client_access_router.message(F.successful_payment)", 1)[1].split(
            "\ndef onboarding_menu(", 1
        )[0]
        self.assertNotIn("feature_flags.snapshot", handler)
        self.assertNotIn("payment_acceptance_enabled()", handler)
        self.assertIn("confirm_stars_payment(", handler)


if __name__ == "__main__":
    unittest.main()
