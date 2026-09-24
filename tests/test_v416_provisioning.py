from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from provisioning import ProvisioningEngine, ProvisioningError
from xui import InboundOption, XUIError


class FakeProvisioningDB:
    def __init__(self):
        self.users = {
            1: SimpleNamespace(telegram_id=1, email="one@example.test", expiry_time=0),
            2: SimpleNamespace(telegram_id=2, email="two@example.test", expiry_time=0),
            3: SimpleNamespace(telegram_id=3, email="three@example.test", expiry_time=0),
        }
        self.profiles = {}
        self.plans = {}
        self.groups = {}
        self.members = {}
        self.modes = {}
        self.selected = {}
        self.expiry_updates = []
        self.group_updates = []

    async def get(self, telegram_id):
        return self.users.get(int(telegram_id))

    async def get_user_profile(self, telegram_id):
        return self.profiles.get(int(telegram_id))

    async def get_plan(self, plan_id):
        return self.plans.get(int(plan_id))

    async def get_server_group(self, group_id):
        return self.groups.get(int(group_id))

    async def list_server_group_members(self, group_id):
        return set(self.members.get(int(group_id), set()))

    async def get_server_group_inbound_mode(self, group_id):
        return self.modes.get(int(group_id), "all_managed")

    async def list_server_group_inbounds(self, group_id):
        return set(self.selected.get(int(group_id), set()))

    async def get_runtime_setting(self, key, default=None):
        return default

    async def update_expiry(self, telegram_id, expiry):
        self.expiry_updates.append((int(telegram_id), int(expiry)))
        self.users[int(telegram_id)].expiry_time = int(expiry)

    async def set_user_server_group(self, telegram_id, group_id):
        self.group_updates.append((int(telegram_id), int(group_id)))
        current = self.profiles.get(int(telegram_id))
        plan_id = getattr(current, "plan_id", None)
        self.profiles[int(telegram_id)] = SimpleNamespace(
            telegram_id=int(telegram_id),
            plan_id=plan_id,
            server_group_id=int(group_id),
        )


class FakeProvisioningXUI:
    def __init__(self, inbounds, *, nodes=None, client_ids=None):
        self._inbounds = list(inbounds)
        self._nodes = list(nodes or [])
        self.client_ids = {k: set(v) for k, v in (client_ids or {}).items()}
        self.attach_calls = []
        self.detach_calls = []
        self.update_calls = []
        self.flow_calls = []
        self.fail_for = set()

    async def inbound_options(self):
        return list(self._inbounds)

    async def nodes_list(self):
        return list(self._nodes)

    async def get_client(self, email):
        if email in self.fail_for:
            raise XUIError("synthetic client failure")
        return {"client": {"email": email}, "inboundIds": sorted(self.client_ids.get(email, set()))}

    async def attach_client(self, email, inbound_ids):
        self.attach_calls.append((email, list(inbound_ids)))
        self.client_ids.setdefault(email, set()).update(map(int, inbound_ids))

    async def detach_client(self, email, inbound_ids):
        self.detach_calls.append((email, list(inbound_ids)))
        self.client_ids.setdefault(email, set()).difference_update(map(int, inbound_ids))

    async def update_client(self, email, **fields):
        self.update_calls.append((email, dict(fields)))

    async def bulk_adjust_clients(self, emails, **fields):
        self.flow_calls.append((list(emails), dict(fields)))


def settings(**overrides):
    base = dict(
        inbound_ids=(),
        ignored_protocols=(),
        ignored_tags=(),
        allowed_ports=(),
        allowed_protocols=(),
        vless_flow="",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class ProvisioningRegressionTests(unittest.IsolatedAsyncioTestCase):
    def inbound(self, iid, *, node_id=None, enable=True):
        return InboundOption(
            id=iid,
            remark=f"in-{iid}",
            tag=f"tag-{iid}",
            protocol="vless",
            port=10000 + iid,
            enable=enable,
            node_id=node_id,
        )

    async def test_safe_reconcile_is_idempotent_and_never_detaches_extra(self):
        db = FakeProvisioningDB()
        xui = FakeProvisioningXUI(
            [self.inbound(10), self.inbound(11)],
            client_ids={"one@example.test": {10, 99}},
        )
        engine = ProvisioningEngine(db, xui, settings())

        first = await engine.sync_user(1, strict=False)
        self.assertEqual(first.attached_ids, [11])
        self.assertEqual(first.detached_ids, [])
        self.assertEqual(first.extra_ids, [])
        self.assertEqual(xui.attach_calls, [("one@example.test", [11])])
        self.assertEqual(xui.detach_calls, [])
        self.assertEqual(xui.client_ids["one@example.test"], {10, 11, 99})

        second = await engine.sync_user(1, strict=False)
        self.assertEqual(second.attached_ids, [])
        self.assertEqual(second.detached_ids, [])
        self.assertEqual(xui.attach_calls, [("one@example.test", [11])])
        self.assertEqual(xui.detach_calls, [])

    async def test_strict_reconcile_detaches_only_managed_extra(self):
        db = FakeProvisioningDB()
        group = SimpleNamespace(id=7, name="Selected", description="", created_at=0)
        db.groups[7] = group
        db.profiles[1] = SimpleNamespace(telegram_id=1, plan_id=None, server_group_id=7)
        db.members[7] = {"master"}
        db.modes[7] = "selected"
        db.selected[7] = {10}

        xui = FakeProvisioningXUI(
            [self.inbound(10), self.inbound(11)],
            client_ids={"one@example.test": {10, 11, 99}},
        )
        engine = ProvisioningEngine(db, xui, settings())

        result = await engine.sync_user(1, strict=True)
        self.assertEqual(result.attached_ids, [])
        self.assertEqual(result.detached_ids, [11])
        self.assertEqual(xui.detach_calls, [("one@example.test", [11])])
        self.assertEqual(xui.client_ids["one@example.test"], {10, 99})

    async def test_strict_reconcile_refuses_to_remove_last_attachment(self):
        db = FakeProvisioningDB()
        group = SimpleNamespace(id=7, name="Empty", description="", created_at=0)
        db.groups[7] = group
        db.profiles[1] = SimpleNamespace(telegram_id=1, plan_id=None, server_group_id=7)
        db.members[7] = {"master"}
        db.modes[7] = "selected"
        db.selected[7] = set()

        xui = FakeProvisioningXUI(
            [self.inbound(10)],
            client_ids={"one@example.test": {10}},
        )
        engine = ProvisioningEngine(db, xui, settings())

        with self.assertRaisesRegex(ProvisioningError, "без inbound"):
            await engine.sync_user(1, strict=True)
        self.assertEqual(xui.detach_calls, [])
        self.assertEqual(xui.client_ids["one@example.test"], {10})

    async def test_unavailable_node_is_desired_but_not_mutated_until_reconcile_later(self):
        db = FakeProvisioningDB()
        group = SimpleNamespace(id=7, name="EU", description="", created_at=0)
        db.groups[7] = group
        db.profiles[1] = SimpleNamespace(telegram_id=1, plan_id=None, server_group_id=7)
        db.members[7] = {"master", "node_2"}

        node = SimpleNamespace(id=2, enable=True, status="offline", transitive=False)
        xui = FakeProvisioningXUI(
            [self.inbound(10), self.inbound(20, node_id=2)],
            nodes=[node],
            client_ids={"one@example.test": set()},
        )
        engine = ProvisioningEngine(db, xui, settings())

        result = await engine.sync_user(1, strict=False)
        self.assertEqual(result.policy.desired_inbound_ids, [10, 20])
        self.assertEqual(result.policy.actionable_inbound_ids, [10])
        self.assertEqual(result.policy.unavailable_members, ["node_2"])
        self.assertEqual(result.attached_ids, [10])
        self.assertEqual(result.remaining_missing_ids, [20])
        self.assertEqual(xui.attach_calls, [("one@example.test", [10])])

    async def test_plan_limits_update_xui_and_control_plane_identity_without_rotating_subscription(self):
        db = FakeProvisioningDB()
        plan = SimpleNamespace(
            id=5,
            name="Premium",
            duration_days=30,
            traffic_gb=100,
            ip_limit=2,
            server_group_id=7,
            active=1,
        )
        group = SimpleNamespace(id=7, name="EU", description="", created_at=0)
        db.plans[5] = plan
        db.groups[7] = group
        db.profiles[1] = SimpleNamespace(telegram_id=1, plan_id=5, server_group_id=None)
        db.members[7] = {"master"}

        xui = FakeProvisioningXUI(
            [self.inbound(10)],
            client_ids={"one@example.test": set()},
        )
        engine = ProvisioningEngine(db, xui, settings())

        before_email = db.users[1].email
        result = await engine.sync_user(1, strict=False, apply_plan_limits=True)

        self.assertTrue(result.limits_applied)
        self.assertEqual(result.attached_ids, [10])
        self.assertEqual(db.users[1].email, before_email)
        self.assertEqual(db.group_updates, [(1, 7)])
        self.assertEqual(len(db.expiry_updates), 1)
        self.assertEqual(len(xui.update_calls), 1)
        email, fields = xui.update_calls[0]
        self.assertEqual(email, "one@example.test")
        self.assertEqual(fields["totalGB"], 100 * 1024**3)
        self.assertEqual(fields["limitIp"], 2)
        self.assertGreater(fields["expiryTime"], int(time.time() * 1000))

    async def test_batch_partial_failure_does_not_stop_other_users(self):
        db = FakeProvisioningDB()
        xui = FakeProvisioningXUI(
            [self.inbound(10)],
            client_ids={
                "one@example.test": set(),
                "two@example.test": set(),
                "three@example.test": set(),
            },
        )
        xui.fail_for.add("two@example.test")
        engine = ProvisioningEngine(db, xui, settings())

        result = await engine.provision_many([1, 2, 3])

        self.assertEqual(result["ok"], 2)
        self.assertEqual(set(result["failed"]), {2})
        self.assertIn("XUIError", result["failed"][2])
        self.assertEqual(result["attached"], 2)
        self.assertEqual(xui.client_ids["one@example.test"], {10})
        self.assertEqual(xui.client_ids["three@example.test"], {10})

    async def test_managed_filter_respects_protocol_port_id_and_api_tag_boundaries(self):
        xui = FakeProvisioningXUI(
            [
                self.inbound(10),
                InboundOption(11, "bad-port", "tag-11", "vless", 9999, True, None),
                InboundOption(12, "ignored", "api-internal", "vless", 10012, True, None),
                InboundOption(13, "trojan", "tag-13", "trojan", 10013, True, None),
            ],
            client_ids={"one@example.test": set()},
        )
        engine = ProvisioningEngine(
            FakeProvisioningDB(),
            xui,
            settings(
                inbound_ids=(10, 11, 12, 13),
                allowed_ports=(10010, 10012, 10013),
                allowed_protocols=("vless",),
            ),
        )

        policy = await engine.resolve_group(None)
        self.assertEqual(policy.managed_inbound_ids, [10])
        self.assertEqual(policy.desired_inbound_ids, [10])


if __name__ == "__main__":
    unittest.main()
