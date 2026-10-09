"""Regression checks for repeat-vs-new background job incident alerts."""
from __future__ import annotations

from datetime import datetime, timezone
import unittest

from alert_job_incidents import job_incident_changed, job_incident_message, job_value


class JobIncidentTextTests(unittest.TestCase):
    def setUp(self):
        self.old = job_value(93, "failed", 1791507601, 1791507601)
        self.same = job_value(93, "failed", 1791507601, 1791507601)
        self.next = job_value(96, "failed", 1791594001, 1791594003)

    def test_same_run_is_reminder_even_after_restart(self):
        self.assertFalse(job_incident_changed(self.old, self.same))
        text = job_incident_message(
            "backup.offsite", self.same, kind="reminder", original_first_seen=1791507601
        )
        self.assertIn("Повторное напоминание", text)
        self.assertIn("Job ID: #93", text)
        self.assertIn("не новый запуск", text)

    def test_new_failed_run_triggers_new_notification_even_inside_cooldown(self):
        self.assertTrue(job_incident_changed(self.old, self.next))
        self.assertTrue(job_incident_changed("Статус: ошибка", self.next))
        text = job_incident_message("backup.offsite", self.next, kind="new")
        self.assertIn("Новая ошибка", text)
        self.assertIn("#96", text)

    def test_success_recovery_keeps_auditable_run_identity(self):
        recovery = job_value(95, "success", 1791549496, 1791549497)
        text = job_incident_message(
            "backup.offsite", recovery, kind="recovery", previous_value=self.old,
        )
        self.assertIn("Исходная ошибка: job #93", text)
        self.assertIn("Восстановлено", text)
        self.assertIn("Job ID: #95", text)
        self.assertIn("Исторический", text)

    def test_no_raw_job_details_or_tokens_rendered(self):
        text = job_incident_message("backup.offsite", self.old, kind="new")
        self.assertNotIn("source_sha256", text)
        self.assertNotIn("key=production", text)

    def test_operator_times_use_moscow_timezone(self):
        unix = int(datetime(2026, 10, 9, 2, 0, tzinfo=timezone.utc).timestamp())
        value = job_value(93, "failed", unix, unix)
        self.assertIn("09.10.2026 05:00:00 MSK", value)

    def test_legacy_and_empty_values_do_not_hide_new_failure(self):
        self.assertTrue(job_incident_changed("", self.old))
        self.assertFalse(job_incident_changed(self.old, "success"))

    def test_untrusted_status_is_normalized(self):
        self.assertIn("статус: unknown", job_value(42, "TOKEN-LEAK", 0, 0))


    def test_target_does_not_allow_message_breakout(self):
        text = job_incident_message("backup.offsite\nFAKE: TOKEN", self.old, kind="new")
        self.assertNotIn("\nFAKE:", text)


class AlertStatePersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_run_resets_first_seen_and_restart_preserves_it(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from db import Database

        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "test.sqlite3")
            database = Database(path)
            await database.init()
            with patch("db.time.time", return_value=1000):
                initial = await database.update_alert_state(
                    code="job_failed", target="backup.offsite", active=True,
                    value=job_value(93, "failed", 1000, 1000),
                    notified_at=1000,
                )
            self.assertEqual(initial.first_seen, 1000)
            with patch("db.time.time", return_value=1100):
                repeat = await database.update_alert_state(
                    code="job_failed", target="backup.offsite", active=True,
                    value=job_value(93, "failed", 1000, 1000),
                )
            self.assertEqual(repeat.first_seen, 1000)
            with patch("db.time.time", return_value=1200):
                latest = await database.update_alert_state(
                    code="job_failed", target="backup.offsite", active=True,
                    value=job_value(96, "failed", 1200, 1201),
                    reset_first_seen=True, notified_at=1200,
                )
            self.assertEqual(latest.first_seen, 1200)
            recovered = Database(path)
            persisted = await recovered.get_alert_state("job_failed", "backup.offsite")
            self.assertEqual(persisted.first_seen, 1200)
            self.assertIn("#96", persisted.last_value)
            self.assertEqual(persisted.last_notified, 1200)


if __name__ == "__main__":
    unittest.main()
