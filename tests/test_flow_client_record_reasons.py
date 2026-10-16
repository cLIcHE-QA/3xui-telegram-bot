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
        await self.check_reason(lambda c: c.__setitem__("privateKey", "fixture-sensitive"), "CLIENT_RECORD_PROTOCOL_WG")

    async def test_wireguard_group_is_blocked(self):
        for key, value in (
            ("privateKey", "fixture-private"),
            ("publicKey", "fixture-public"),
            ("allowedIPs", "10.0.0.0/24"),
            ("preSharedKey", "fixture-psk"),
            ("keepAlive", 25),
            ("forwardedPorts", '[{"port":8443}]'),
        ):
            with self.subTest(field=key):
                await self.check_reason(lambda c, k=key, v=value: c.__setitem__(k, v), "CLIENT_RECORD_PROTOCOL_WG")

    async def test_mtproto_group_is_blocked(self):
        for key in ("secret", "adTag"):
            with self.subTest(field=key):
                await self.check_reason(lambda c, k=key: c.__setitem__(k, "fixture-sensitive"), "CLIENT_RECORD_PROTOCOL_MTPROTO")

    async def test_both_groups_are_blocked(self):
        def mutate(client):
            client["privateKey"] = "fixture-private"
            client["secret"] = "fixture-secret"
        await self.check_reason(mutate, "CLIENT_RECORD_PROTOCOL_MIXED")

    async def test_empty_protocol_fields_are_preserved(self):
        master = FakeMaster()
        client = master.client["client"]
        for k in ("privateKey", "publicKey", "allowedIPs", "preSharedKey", "forwardedPorts", "secret", "adTag"):
            client[k] = ""
        client["keepAlive"] = 0
        result = await discover_flow_targets(master, "qa@example.invalid", 1001)
        self.assertEqual(len(result.targets), 2)
        self.assertEqual(master.writes, [])

    async def test_legacy_empty_list_spellings_do_not_block(self):
        master = FakeMaster()
        master.client["client"]["allowedIPs"] = "[]"
        master.client["client"]["forwardedPorts"] = []
        snap = await discover_flow_targets(master, "qa@example.invalid", 1001)
        self.assertEqual(len(snap.targets), 2)
        self.assertEqual(master.writes, [])

    async def test_unknown_diagnostics_never_leak_credentials(self):
        secret = "fake-sensitive-payload"
        self.assertEqual(preflight_reason(FlowEditRejected(secret)), "MASTER_VALIDATION")
        for reason in ("Непроверенные поля WireGuard", "Непроверенные поля MTProto", "Непроверенные поля нескольких протоколов"):
            code = preflight_reason(FlowEditRejected(reason))
            self.assertNotIn(secret, code)
            self.assertTrue(code.startswith("CLIENT_RECORD_PROTOCOL_"))

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
