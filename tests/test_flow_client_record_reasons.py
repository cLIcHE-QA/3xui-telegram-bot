"""Безопасные категории preflight для #663: только offline fixtures."""
from __future__ import annotations
import unittest

from flow_edit import FlowEditRejected, discover_flow_targets, preflight_reason
from test_flow_edit import FakeMaster


class ClientRecordReasonTests(unittest.IsolatedAsyncioTestCase):
    async def check_reason(self, mutate, expected):
        master = FakeMaster()
        mutate(master.client["client"])
        with self.assertRaises(FlowEditRejected) as failure:
            await discover_flow_targets(master, "qa@example.invalid", 1001)
        self.assertEqual(preflight_reason(failure.exception), expected)
        self.assertEqual(master.writes, [])

    async def test_missing_required_field(self):
        await self.check_reason(lambda c: c.pop("resetWeekday"), "CLIENT_RECORD_MISSING")

    async def test_null_required_field(self):
        await self.check_reason(lambda c: c.__setitem__("limitIp", None), "CLIENT_RECORD_NULL")

    async def test_foreign_protocol_field(self):
        await self.check_reason(lambda c: c.__setitem__("privateKey", "fixture-sensitive"), "CLIENT_RECORD_PROTOCOL")

    async def test_nonempty_reverse(self):
        await self.check_reason(lambda c: c.__setitem__("reverse", '{"secret":"fixture-sensitive"}'), "CLIENT_RECORD_REVERSE")

    async def test_unknown_payload_details_never_leak(self):
        for message in ["secret-private-key", "Неполный общий record: secret-private-key"]:
            self.assertEqual(preflight_reason(FlowEditRejected(message)), "MASTER_VALIDATION")

    async def test_complete_client_remains_supported(self):
        master = FakeMaster()
        result = await discover_flow_targets(master, "qa@example.invalid", 1001)
        self.assertEqual(len(result.targets), 2)
        self.assertEqual(master.writes, [])


if __name__ == "__main__":
    unittest.main()
