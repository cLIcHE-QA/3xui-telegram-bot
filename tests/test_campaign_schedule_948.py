from datetime import datetime, timezone
import os
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfoNotFoundError

from campaign_schedule import MAX_SCHEDULE_AHEAD, parse_campaign_schedule
from service_campaigns import CampaignInvalid


class CampaignSchedule948Tests(unittest.TestCase):
    now = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp())

    def test_explicit_utc_and_iana_zone_have_frozen_utc_identity(self):
        utc = parse_campaign_schedule("2024-02-01T09:00", "UTC", now=self.now)
        msk = parse_campaign_schedule("2024-02-01T12:00", "Europe/Moscow", now=self.now)
        self.assertEqual(utc.due_at, msk.due_at)
        self.assertEqual(msk.local_time, "2024-02-01T12:00")
        self.assertEqual(msk.timezone, "Europe/Moscow")
        self.assertEqual(datetime.fromtimestamp(utc.due_at, timezone.utc).hour, 9)

    def test_ambiguous_fold_and_nonexistent_gap_are_rejected(self):
        for local in ("2024-03-10T02:30", "2024-11-03T01:30"):
            with self.subTest(local=local), self.assertRaises(CampaignInvalid):
                parse_campaign_schedule(local, "America/New_York", now=self.now)

    def test_unambiguous_instant_after_fold_is_accepted(self):
        value = parse_campaign_schedule("2024-11-03T02:30", "America/New_York", now=self.now)
        expected = int(datetime(2024, 11, 3, 7, 30, tzinfo=timezone.utc).timestamp())
        self.assertEqual(value.due_at, expected)

    def test_host_timezone_is_never_used_as_fallback(self):
        with patch.dict(os.environ, {"TZ": "America/Los_Angeles"}):
            a = parse_campaign_schedule("2024-02-01T09:00", "UTC", now=self.now)
        with patch.dict(os.environ, {"TZ": "Asia/Tokyo"}):
            b = parse_campaign_schedule("2024-02-01T09:00", "UTC", now=self.now)
        self.assertEqual(a, b)
        for key in ("", "localtime", "CET", "../private", "/etc/localtime", "posix/Europe/Moscow",
                    "right/UTC", "Not/AZone", "UTC\n", "x" * 101, None):
            with self.subTest(key=key), self.assertRaises(CampaignInvalid):
                parse_campaign_schedule("2024-02-01T09:00", key, now=self.now)

    def test_offset_seconds_whitespace_controls_and_invalid_dates_are_rejected(self):
        for value in ("2024-02-01T09:00Z", "2024-02-01T09:00+03:00", "2024-02-01T09:00:00",
                      "2024-02-01 09:00", "2024-2-1T09:00", "2024-02-30T09:00", "0000-01-01T00:00",
                      "2024-02-01T24:00", "2024-02-01T09:00\n", None):
            with self.subTest(value=value), self.assertRaises(CampaignInvalid):
                parse_campaign_schedule(value, "UTC", now=self.now)

    def test_past_exact_now_and_engine_horizon_are_rejected(self):
        for local in ("2023-12-31T23:59", "2024-01-01T00:00", "2025-01-02T00:00"):
            with self.subTest(local=local), self.assertRaises(CampaignInvalid):
                parse_campaign_schedule(local, "UTC", now=self.now)
        self.assertEqual(MAX_SCHEDULE_AHEAD, 366 * 86400)

    def test_missing_timezone_database_fails_closed_with_generic_error(self):
        with patch("campaign_schedule.ZoneInfo", side_effect=ZoneInfoNotFoundError("private-path")):
            with self.assertRaises(CampaignInvalid) as error:
                parse_campaign_schedule("2024-02-01T09:00", "UTC", now=self.now)
        self.assertNotIn("private-path", str(error.exception))

    def test_invalid_clock_is_not_coerced(self):
        for now in (True, False, 0, -1, 2**80, 1.5, float("nan"), float("inf"), "1"):
            with self.subTest(now=now), self.assertRaises(CampaignInvalid):
                parse_campaign_schedule("2024-02-01T09:00", "UTC", now=now)
