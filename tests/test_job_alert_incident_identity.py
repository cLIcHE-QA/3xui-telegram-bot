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
        text = job_incident_message("backup.offsite", recovery, kind="recovery")
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


if __name__ == "__main__":
    unittest.main()
