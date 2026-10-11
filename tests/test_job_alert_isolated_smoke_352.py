"""Offline #352 smoke: actual incident state machine with isolated SQLite and fake Telegram.

No production access, Telegram network calls, real scheduler runs or real tokens.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from alert_job_incidents import job_value
from db import Database


JOB_NAME = "qa.synthetic.job"
BASE = 1_791_700_000
SYNTHETIC_DETAILS = "SYNTHETIC_SECRET_NEVER_DISPLAY"


class IsolatedJobFailureNotificationSmoke(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory(prefix="qa352-")
        self.addCleanup(self.tempdir.cleanup)
        self.path = str(Path(self.tempdir.name) / "synthetic.sqlite3")
        self.database = Database(self.path)
        await self.database.init()
        self.assertTrue((await self.database.get_alert_rule("job_failed")).enabled)

        fake_env = {
            "BOT_TOKEN": "123456789:offline-qa352-token",
            "PANEL_URL": "https://panel.example.invalid/base",
            "PANEL_API_TOKEN": "offline-qa352-token",
            "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/sub/{sub_id}",
            "ALLOWED_TELEGRAM_IDS": "1",
            "ADMIN_TELEGRAM_IDS": "1",
        }
        with patch.dict(os.environ, fake_env, clear=False):
            import logs_alerts

        self.alerts = logs_alerts
        self.bot = SimpleNamespace(send_message=AsyncMock())
        for name, replacement in (
            ("db", self.database),
            ("_recipients", AsyncMock(return_value=[700001])),
            ("audit_system", AsyncMock()),
        ):
            active = patch.object(self.alerts, name, replacement)
            active.start()
            self.addCleanup(active.stop)

    async def _record_run(self, status: str, at: int):
        # All job_runs rows are synthetic, in the per-test temporary database.
        with patch("db.time.time", return_value=at):
            run_id = await self.database.start_job_run(
                name=JOB_NAME, trigger="qa_isolated", details=SYNTHETIC_DETAILS,
            )
            await self.database.finish_job_run(
                run_id, status=status, duration_ms=14, details=SYNTHETIC_DETAILS,
            )
        run = await self.database.last_job_run(JOB_NAME)
        self.assertEqual(run.id, run_id)
        self.assertEqual(run.status, status)
        return run

    async def _observe(self, run, at: int):
        payload = job_value(run.id, run.status, run.started_at, run.finished_at)
        # Patch the clock used by logs_alerts and the SQLite adapter.
        with patch.object(self.alerts.time, "time", return_value=at):
            await self.alerts._set_incident(
                self.bot, code="job_failed", target=JOB_NAME,
                active=run.status == "failed", value=payload, notify=True,
            )

    def _messages(self):
        return [call.args[1] for call in self.bot.send_message.await_args_list]

    async def test_01_new_failed_run_sends_new_error(self):
        failed = await self._record_run("failed", BASE)
        await self._observe(failed, BASE + 2)
        self.assertEqual(len(self._messages()), 1)
        message = self._messages()[0]
        self.assertIn("Новая ошибка фонового задания", message)
        self.assertIn(f"Job ID: #{failed.id}; статус: failed", message)
        self.assertIn(JOB_NAME, message)
        self.assertIn("MSK", message)
        self.assertNotIn(SYNTHETIC_DETAILS, message)
        state = await self.database.get_alert_state("job_failed", JOB_NAME)
        self.assertEqual((state.active, state.first_seen, state.last_notified), (1, BASE + 2, BASE + 2))

    async def test_02_same_run_is_reminder_not_new_even_after_reopen(self):
        failed = await self._record_run("failed", BASE)
        await self._observe(failed, BASE + 2)
        # Simulate restart by using a fresh Database instance at the same isolated file.
        with patch.object(self.alerts, "db", Database(self.path)):
            await self._observe(failed, BASE + 30)
            self.assertEqual(len(self._messages()), 1, "no duplicate alert inside cooldown")
            await self._observe(failed, BASE + 1_805)
        messages = self._messages()
        self.assertEqual(len(messages), 2)
        self.assertIn("Повторное напоминание", messages[1])
        self.assertIn(f"Job ID: #{failed.id}", messages[1])
        self.assertIn("Это напоминание об исходной ошибке, а не новый запуск.", messages[1])
        self.assertNotIn("Новая ошибка фонового задания", messages[1])
        state = await self.database.get_alert_state("job_failed", JOB_NAME)
        self.assertEqual(state.first_seen, BASE + 2)
        self.assertEqual(state.last_notified, BASE + 1_805)

    async def test_03_later_failed_run_bypasses_cooldown(self):
        previous = await self._record_run("failed", BASE)
        await self._observe(previous, BASE + 2)
        subsequent = await self._record_run("failed", BASE + 5)
        self.assertGreater(subsequent.id, previous.id)
        await self._observe(subsequent, BASE + 7)
        messages = self._messages()
        self.assertEqual(len(messages), 2, "new ID must alert without waiting for cooldown")
        self.assertIn("Новая ошибка фонового задания", messages[1])
        self.assertIn(f"Job ID: #{subsequent.id}", messages[1])
        self.assertNotIn(f"Job ID: #{previous.id}", messages[1])
        state = await self.database.get_alert_state("job_failed", JOB_NAME)
        self.assertEqual(state.first_seen, BASE + 7)
        self.assertEqual(state.last_notified, BASE + 7)
        runs = await self.database.list_job_runs(name=JOB_NAME)
        self.assertEqual([x.status for x in runs], ["failed", "failed"])

    async def test_04_success_sends_one_recovery_preserves_failed_history(self):
        failed = await self._record_run("failed", BASE)
        await self._observe(failed, BASE + 2)
        success = await self._record_run("success", BASE + 8)
        await self._observe(success, BASE + 10)
        messages = self._messages()
        self.assertEqual(len(messages), 2)
        self.assertIn("Восстановлено", messages[1])
        self.assertIn(f"Job ID: #{success.id}; статус: success", messages[1])
        self.assertIn(f"Исходная ошибка: job #{failed.id}", messages[1])
        self.assertIn("Исторический ошибочный запуск сохранён", messages[1])
        self.assertNotIn(SYNTHETIC_DETAILS, messages[1])
        await self._observe(success, BASE + 15)
        self.assertEqual(len(self._messages()), 2, "repeated success must not repeat recovery")
        self.assertEqual((await self.database.get_alert_state("job_failed", JOB_NAME)).active, 0)
        runs = await self.database.list_job_runs(name=JOB_NAME)
        self.assertEqual([(x.id, x.status) for x in runs],
                         [(success.id, "success"), (failed.id, "failed")])


if __name__ == "__main__":
    unittest.main()
