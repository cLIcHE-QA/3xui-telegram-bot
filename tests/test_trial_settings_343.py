from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from db import Database
from trial_settings import parse_trial_setting, trial_limit_label
from xui import XUIClient


class TrialLimitsTests(unittest.IsolatedAsyncioTestCase):
    async def test_sqlite_persists_zero_and_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Database(str(Path(temp) / "test.db"))
            await db.init()
            for key in ("trial_traffic_gb", "trial_ip_limit"):
                await db.set_runtime_setting(key, "0", updated_by=7)
                raw = await db.get_runtime_setting(key)
                self.assertEqual(raw, "0")
                self.assertEqual(parse_trial_setting(key, raw, 9), 0)
                await db.delete_runtime_setting(key)
                self.assertEqual(parse_trial_setting(key, await db.get_runtime_setting(key), 9), 9)

    def test_limits_and_invalid_values(self):
        self.assertEqual(parse_trial_setting("trial_days", "1", 7), 1)
        self.assertEqual(parse_trial_setting("trial_days", "3650", 7), 3650)
        self.assertEqual(parse_trial_setting("trial_traffic_gb", "100000", 10), 100000)
        self.assertEqual(parse_trial_setting("trial_ip_limit", "1000", 2), 1000)
        self.assertEqual(parse_trial_setting("trial_ip_limit", 0, 2), 0)
        for key, invalid in (
            ("trial_days", "0"), ("trial_days", "-1"),
            ("trial_traffic_gb", "100001"), ("trial_ip_limit", "1001"),
            ("trial_ip_limit", ""), ("trial_ip_limit", " "),
            ("trial_traffic_gb", "abc"), ("trial_traffic_gb", "-1"),
            ("trial_ip_limit", True), ("trial_days", None if False else "1.0"),
        ):
            with self.subTest(key=key, invalid=invalid):
                with self.assertRaises(ValueError):
                    parse_trial_setting(key, invalid, 7)
        self.assertEqual(trial_limit_label("trial_traffic_gb", 0), "без лимита")
        self.assertEqual(trial_limit_label("trial_ip_limit", 0), "без лимита")

    async def test_runtime_reads_three_independent_values_no_masked_errors(self):
        import advanced_users
        defaults = SimpleNamespace(test_days=7, test_traffic_gb=10, test_ip_limit=2)
        async def read(key):
            return {"trial_days": "3", "trial_traffic_gb": "0", "trial_ip_limit": "0"}[key]
        with patch.object(advanced_users, "settings", defaults), patch.object(
            advanced_users.db, "get_runtime_setting", side_effect=read
        ):
            self.assertEqual(await advanced_users._trial_create_values(), (3, 0, 0))
        async def bad(key):
            return {"trial_days": "3", "trial_traffic_gb": "broken", "trial_ip_limit": "0"}[key]
        with patch.object(advanced_users, "settings", defaults), patch.object(
            advanced_users.db, "get_runtime_setting", side_effect=bad
        ):
            with self.assertRaises(ValueError):
                await advanced_users._trial_create_values()

    async def test_xui_wire_payload_preserves_zero(self):
        client = XUIClient("https://panel.example.invalid", "not-secret")
        client._mutation_request = AsyncMock(return_value={"success": True})
        await client.create_client(email="trial_1", telegram_id=1, sub_id="trial-id",
            total_bytes=0, expiry_time_ms=123, limit_ip=0, inbound_ids=[1],
            comment="test", flow="")
        payload = client._mutation_request.await_args.kwargs["json_payload"]["client"]
        self.assertEqual(payload["totalGB"], 0)
        self.assertEqual(payload["limitIp"], 0)

    def test_ui_and_trial_preview_are_read_only_to_existing_clients(self):
        root = Path(__file__).resolve().parents[1]
        ui = (root / "business_admin.py").read_text(encoding="utf-8")
        creation = (root / "advanced_users.py").read_text(encoding="utf-8")
        self.assertIn("0 = без лимита", ui)
        self.assertIn("существующие пользователи не изменяются", ui)
        self.assertIn("parse_trial_setting(key, raw, default)", creation)
        helper = creation.split("async def _trial_create_values", 1)[1].split("async def _create_user_context", 1)[0]
        self.assertNotIn("update_client(", helper)
        self.assertNotIn("create_client(", helper)


if __name__ == "__main__":
    unittest.main()
