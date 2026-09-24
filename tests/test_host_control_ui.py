from __future__ import annotations

import importlib
import inspect
import os
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import AsyncMock, patch

import aiohttp


class FakeDB:
    def __init__(self):
        self.start_job_run = AsyncMock(return_value=101)
        self.finish_job_run = AsyncMock()


class FakePanelClient:
    def __init__(self, *, xray_state: str = "running"):
        self.xray_state = xray_state
        self.stop_calls = 0
        self.restart_calls = 0
        self.panel_restart_calls = 0
        self.stop_error = None
        self.restart_error = None
        self.panel_restart_error = None

    async def server_status(self):
        return {"xray": {"state": self.xray_state}}

    async def stop_xray(self):
        self.stop_calls += 1
        if self.stop_error:
            raise self.stop_error
        return {"success": True}

    async def restart_xray(self):
        self.restart_calls += 1
        if self.restart_error:
            raise self.restart_error
        return {"success": True}

    async def restart_panel(self):
        self.panel_restart_calls += 1
        if self.panel_restart_error:
            raise self.panel_restart_error
        return {"success": True}


class HostControlStartupRecoveryContractTests(unittest.TestCase):
    def test_startup_runs_control_recovery_before_generic_stale_cleanup(self):
        source = (Path(__file__).resolve().parents[1] / "bot.py").read_text(encoding="utf-8")
        import_at = source.index(
            "from host_control_ui import host_control_router, recover_control_jobs"
        )
        main_at = source.index("async def main():")
        recover_at = source.index("await recover_control_jobs()", main_at)
        stale_at = source.index("await db.fail_stale_job_runs()", main_at)
        polling_at = source.index("await dp.start_polling(bot)", main_at)

        self.assertLess(import_at, main_at)
        self.assertLess(recover_at, stale_at)
        self.assertLess(stale_at, polling_at)

    def test_recovery_uses_read_only_lookup_and_never_replays_mutation(self):
        import host_control_ui

        source = inspect.getsource(host_control_ui.recover_control_jobs)
        self.assertIn("await client.get_operation(operation_id)", source)
        self.assertNotIn(".execute(", source)
        self.assertNotIn("await client.execute", source)
        self.assertIn("mutation_not_retried=true", source)


class HostControlUITests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.env = patch.dict(
            os.environ,
            {
                "BOT_TOKEN": "123456789:offline-test-token-not-used-for-network",
                "PANEL_URL": "https://panel.example.invalid/base",
                "PANEL_API_TOKEN": "offline-test-placeholder",
                "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/sub/{sub_id}",
                "ALLOWED_TELEGRAM_IDS": "1",
                "ADMIN_TELEGRAM_IDS": "1",
                "NODE_BACKUP_TARGETS": "",
                "HOST_CONTROL_TARGETS": "",
                "DB_PATH": str(Path(cls.tmp.name) / "bot.sqlite3"),
                "BACKUP_DIR": str(Path(cls.tmp.name) / "backups"),
            },
            clear=False,
        )
        cls.env.start()
        cls.ui = importlib.import_module("host_control_ui")

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("host_control_ui", None)
        cls.env.stop()
        cls.tmp.cleanup()

    def target(self, panel=None):
        return self.ui.ControlTarget(
            key="n2",
            name="Finland",
            back_callback="admin:node:2",
            panel_client=panel if panel is not None else object(),
            host_target=object(),
            node_id=2,
        )

    @staticmethod
    def callbacks(markup):
        return {
            button.callback_data
            for row in markup.inline_keyboard
            for button in row
            if button.callback_data
        }

    def test_read_only_has_no_mutation_buttons(self):
        callbacks = self.callbacks(self.ui._screen_keyboard(self.target(), "read_only", True))
        self.assertEqual(callbacks, {"admin:node:2"})

    def test_admin_cannot_stop_service_or_xray(self):
        callbacks = self.callbacks(self.ui._screen_keyboard(self.target(), "admin", True))
        self.assertIn("admin:hostctl:n2:ss:ask", callbacks)
        self.assertIn("admin:hostctl:n2:sr:ask", callbacks)
        self.assertIn("admin:hostctl:n2:pr:ask", callbacks)
        self.assertIn("admin:hostctl:n2:xr:ask", callbacks)
        self.assertNotIn("admin:hostctl:n2:sp:ask", callbacks)
        self.assertNotIn("admin:hostctl:n2:xs:ask", callbacks)

    def test_owner_gets_destructive_stop_buttons(self):
        callbacks = self.callbacks(self.ui._screen_keyboard(self.target(), "owner", True))
        self.assertIn("admin:hostctl:n2:sp:ask", callbacks)
        self.assertIn("admin:hostctl:n2:xs:ask", callbacks)

    def test_stop_service_confirmation_is_consumed_before_dispatch(self):
        source = inspect.getsource(self.ui.host_control_stop_phrase)
        clear_at = source.index("await state.clear()")
        dispatch_at = source.index("_run_service_action(target, \"stop\"")
        self.assertLess(clear_at, dispatch_at)
        self.assertIn('f"STOP {target_name}"', source)

    async def test_unknown_xray_state_does_not_confirm_stop(self):
        panel = FakePanelClient(xray_state="unknown")
        fake_db = FakeDB()
        target = self.target(panel)
        with (
            patch.object(self.ui, "db", fake_db),
            patch.object(self.ui.asyncio, "sleep", new=AsyncMock()),
        ):
            message, success, details = await self.ui._run_xray_action(target, "stop", 1)

        self.assertFalse(success)
        self.assertIn("не подтверждён", message)
        self.assertIn("result=uncertain", details)
        self.assertEqual(panel.stop_calls, 1)

    async def test_lost_xray_stop_response_is_never_retried(self):
        panel = FakePanelClient(xray_state="running")
        panel.stop_error = aiohttp.ClientConnectionError("lost")
        fake_db = FakeDB()
        target = self.target(panel)
        with patch.object(self.ui, "db", fake_db):
            message, success, details = await self.ui._run_xray_action(target, "stop", 1)

        self.assertFalse(success)
        self.assertIn("НЕ отправлялся", message)
        self.assertIn("lost_response", details)
        self.assertEqual(panel.stop_calls, 1)

    async def test_definite_native_xray_rejection_is_failed(self):
        from xui import XUIMutationError

        panel = FakePanelClient(xray_state="running")
        panel.stop_error = XUIMutationError(
            "forbidden",
            code="http_403",
            uncertain=False,
        )
        fake_db = FakeDB()
        target = self.target(panel)
        with patch.object(self.ui, "db", fake_db):
            message, success, details = await self.ui._run_xray_action(target, "stop", 1)

        self.assertFalse(success)
        self.assertIn("отклонил", message)
        self.assertIn("result=failed", details)
        self.assertEqual(panel.stop_calls, 1)

    async def test_uncertain_native_xray_rejection_is_not_retried(self):
        from xui import XUIMutationError

        panel = FakePanelClient(xray_state="running")
        panel.restart_error = XUIMutationError(
            "upstream",
            code="http_502",
            uncertain=True,
        )
        fake_db = FakeDB()
        target = self.target(panel)
        with patch.object(self.ui, "db", fake_db):
            message, success, details = await self.ui._run_xray_action(target, "restart", 1)

        self.assertFalse(success)
        self.assertIn("НЕ отправлялся", message)
        self.assertIn("result=uncertain", details)
        self.assertEqual(panel.restart_calls, 1)

    async def test_lost_panel_restart_response_is_never_retried(self):
        panel = FakePanelClient()
        panel.panel_restart_error = aiohttp.ClientConnectionError("lost")
        fake_db = FakeDB()
        target = self.target(panel)
        with (
            patch.object(self.ui, "db", fake_db),
            patch.object(
                self.ui,
                "_verify_uncertain_panel_restart",
                new=AsyncMock(return_value=False),
            ),
        ):
            message, success, details = await self.ui._run_panel_restart(target, 1)

        self.assertFalse(success)
        self.assertIn("НЕ отправлялся", message)
        self.assertIn("result=uncertain", details)
        self.assertEqual(panel.panel_restart_calls, 1)


if __name__ == "__main__":
    unittest.main()
