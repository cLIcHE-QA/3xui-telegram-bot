from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from admin_privileges import required_role_for_callback
from db import Database
from website_monitoring import (
    MonitorCheckExecution,
    WebsiteCheckOutcome,
    WebsiteMonitoringRepository,
)
_TEST_ENV = {
    "BOT_TOKEN": "123456789:offline-test-token",
    "PANEL_URL": "https://panel.example.invalid/base",
    "PANEL_API_TOKEN": "offline-panel-token",
    "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/sub/{sub_id}",
    "ALLOWED_TELEGRAM_IDS": "1",
    "ADMIN_TELEGRAM_IDS": "1",
    "NODE_BACKUP_TARGETS": "",
    "HOST_CONTROL_TARGETS": "",
    "DB_PATH": "/tmp/v4240-monitoring-test.sqlite3",
}
with patch.dict(os.environ, _TEST_ENV, clear=False):
    from website_monitoring_runtime import dispatch_monitor_notification


class FakeBot:
    def __init__(self):
        self.messages: list[tuple[int, str]] = []

    async def send_message(self, telegram_id: int, text: str, **kwargs):
        self.messages.append((telegram_id, text))


class V4240MonitoringUIRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "bot.sqlite3"
        await Database(str(self.path)).init()
        self.repo = WebsiteMonitoringRepository(str(self.path))

    async def asyncTearDown(self):
        self.tmp.cleanup()

    def test_rbac_contract_for_website_monitoring_callbacks(self):
        cases = {
            "admin:webmon": "read_only",
            "admin:webmon:list": "read_only",
            "admin:webmon:site:7": "read_only",
            "admin:webmon:incidents:7": "read_only",
            "admin:webmon:add": "support",
            "admin:webmon:add:cancel": "support",
            "admin:webmon:check:7": "support",
            "admin:webmon:pause:7": "support",
            "admin:webmon:alerts:7": "support",
            "admin:webmon:deleteask:7": "support",
            "admin:webmon:delete:7": "support",
            "admin:webmon:all": "admin",
            "admin:webmon:global:7": "admin",
            "admin:webmon:globaldeleteask:7": "admin",
            "admin:webmon:globaldelete:7": "admin",
            "admin:webdiag:site:7": "read_only",
            "admin:webdiag:site:7:http": "read_only",
        }
        for callback, role in cases.items():
            with self.subTest(callback=callback):
                self.assertEqual(required_role_for_callback(callback), role)

    def test_runtime_registers_router_and_scheduler(self):
        source = (Path(__file__).resolve().parents[1] / "app_runtime.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "from website_monitoring_admin import website_monitoring_router",
            source,
        )
        self.assertIn(
            "from website_monitoring_runtime import website_monitoring_loop",
            source,
        )
        self.assertIn("dp.include_router(website_monitoring_router)", source)
        self.assertIn(
            "website_monitoring_task = asyncio.create_task(website_monitoring_loop(bot))",
            source,
        )
        self.assertIn("website_monitoring_task,", source)

    def test_monitoring_navigation_has_canonical_entry(self):
        import admin_navigation

        buttons = {
            button.callback_data: button.text
            for row in admin_navigation.monitoring_menu().inline_keyboard
            for button in row
            if button.callback_data
        }
        self.assertEqual(buttons["admin:webmon"], "🌐 Мониторинг сайтов")

    async def test_unsubscribe_removes_orphan_target_only_after_last_watcher(self):
        item = await self.repo.add_watcher("https://example.org", 101)
        await self.repo.add_watcher("https://example.org", 202)

        self.assertTrue(await self.repo.remove_watcher(item.id, 101))
        self.assertIsNotNone(await self.repo.get_monitor(item.id))
        self.assertEqual(await self.repo.watchers(item.id), (202,))

        self.assertTrue(await self.repo.remove_watcher(item.id, 202))
        self.assertIsNone(await self.repo.get_monitor(item.id))

    async def test_notification_claim_prevents_duplicate_replay(self):
        # website_monitoring_runtime uses module-level repository. Patch it to
        # this isolated database so the delivery contract is deterministic.
        item = await self.repo.add_watcher("https://example.org", 101)
        incident_id = await self.repo.open_incident(
            item.id,
            WebsiteCheckOutcome(
                kind="failure",
                http_status=503,
                error_kind="http_status",
            ),
        )
        execution = MonitorCheckExecution(
            monitor_id=item.id,
            previous_state="up",
            final_state="down",
            outcome=WebsiteCheckOutcome(
                kind="failure",
                http_status=503,
                error_kind="http_status",
            ),
            incident_id=incident_id,
            notify_kind="opened",
        )
        bot = FakeBot()

        with patch("website_monitoring_runtime.repository", self.repo):
            first = await dispatch_monitor_notification(bot, execution)
            second = await dispatch_monitor_notification(bot, execution)

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(len(bot.messages), 1)
        self.assertIn("🚨 Сайт недоступен", bot.messages[0][1])

    async def test_notification_toggle_is_scoped_to_one_watcher(self):
        item = await self.repo.add_watcher("https://example.org", 101)
        await self.repo.add_watcher("https://example.org", 202)

        self.assertTrue(await self.repo.set_notifications_enabled(item.id, 101, False))
        self.assertFalse(await self.repo.notifications_enabled(item.id, 101))
        self.assertTrue(await self.repo.notifications_enabled(item.id, 202))
        self.assertEqual(await self.repo.watchers(item.id), (202,))


    async def test_pause_is_watcher_scoped_and_scheduler_skips_fully_paused_target(self):
        item = await self.repo.add_watcher("https://example.org", 101)
        await self.repo.add_watcher("https://example.org", 202)

        self.assertTrue(await self.repo.set_monitoring_enabled(item.id, 101, False))
        self.assertFalse(await self.repo.monitoring_enabled(item.id, 101))
        self.assertTrue(await self.repo.monitoring_enabled(item.id, 202))

        due = await self.repo.due_monitors(now=10**12)
        self.assertIn(item.id, {row.id for row in due})

        self.assertTrue(await self.repo.set_monitoring_enabled(item.id, 202, False))
        due = await self.repo.due_monitors(now=10**12)
        self.assertNotIn(item.id, {row.id for row in due})

        self.assertTrue(await self.repo.set_monitoring_enabled(item.id, 101, True))
        due = await self.repo.due_monitors(now=10**12)
        self.assertIn(item.id, {row.id for row in due})

    async def test_global_delete_removes_target_watchers_and_incidents(self):
        item = await self.repo.add_watcher("https://example.org", 101)
        await self.repo.add_watcher("https://example.org", 202)
        incident_id = await self.repo.open_incident(
            item.id,
            WebsiteCheckOutcome(
                kind="failure",
                http_status=503,
                error_kind="http_status",
            ),
        )
        await self.repo.record_notification(
            incident_id,
            101,
            kind="opened",
            sequence=0,
        )

        self.assertEqual(await self.repo.watcher_count(item.id), 2)
        self.assertTrue(await self.repo.delete_monitor_global(item.id))
        self.assertIsNone(await self.repo.get_monitor(item.id))
        self.assertEqual(await self.repo.watchers(item.id, enabled_only=False), ())

    def test_contextual_diagnostics_callbacks_keep_only_stable_monitor_id(self):
        source = (
            Path(__file__).resolve().parents[1] / "website_diagnostics_admin.py"
        ).read_text(encoding="utf-8")
        self.assertIn('callback_data=f"admin:webdiag:site:{monitor_id}:http"', source)
        self.assertIn('callback_data=f"admin:webmon:site:{monitor_id}"', source)
        self.assertNotIn('callback_data=f"admin:webdiag:site:{item.canonical_url}', source)


if __name__ == "__main__":
    unittest.main()
