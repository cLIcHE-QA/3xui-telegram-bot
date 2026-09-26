"""Regression coverage for v4.21.2 DR/log viewer fixes."""
from __future__ import annotations

import unittest
from pathlib import Path

import logs_alerts


ROOT = Path(__file__).resolve().parents[1]


class V4212DrLogsTests(unittest.TestCase):
    def test_disaster_recovery_imports_ui_time_formatters(self):
        source = (ROOT / "disaster_recovery.py").read_text(encoding="utf-8")
        self.assertIn(
            "from ui_time import format_datetime, format_short_datetime",
            source,
        )
        self.assertIn("format_datetime(info.created_at)", source)
        self.assertIn("format_short_datetime(dt)", source)

    def test_excerpt_reports_visible_line_count(self):
        lines = [f"{i:03d} " + ("x" * 70) for i in range(200)]
        excerpt_50, visible_50 = logs_alerts._excerpt(lines[-50:], max_chars=3350)
        excerpt_200, visible_200 = logs_alerts._excerpt(lines[-200:], max_chars=3650)

        self.assertLessEqual(visible_50, 50)
        self.assertLessEqual(visible_200, 200)
        self.assertGreater(visible_200, visible_50)
        self.assertNotEqual(excerpt_50, excerpt_200)

    def test_log_ui_exposes_requested_and_visible_counts(self):
        source = (ROOT / "logs_alerts.py").read_text(encoding="utf-8")
        self.assertIn(
            'max_chars=3350 if count == 50 else 3650',
            source,
        )
        self.assertIn(
            "запрошено {count} · показано {visible_count}",
            source,
        )


if __name__ == "__main__":
    unittest.main()
