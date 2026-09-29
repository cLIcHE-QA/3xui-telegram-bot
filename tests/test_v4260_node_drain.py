from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from node_drain import (
    DrainPlanStore,
    NodeDrainBlocked,
    NodeDrainError,
    NodeDrainService,
)
from xui import InboundOption, XUIMutationError


class FakeDB:
    def __init__(self):
        self.users = {
            1: SimpleNamespace(telegram_id=1, email="one@example.test"),
            2: SimpleNamespace(telegram_id=2, email="two@example.test"),
        }
        self.profiles = {}
        self.groups = {}
        self.members = {}
        self.modes = {}
        self.selected = {}

    async def list_users(self):
        return list(self.users.values())

    async def get(self, telegram_id):
        return self.users.get(int(telegram_id))

    async def get_user_profile(self, telegram_id):
        return self.profiles.get(int(telegram_id))

    async def get_plan(self, plan_id):
        return None

    async def get_server_group(self, group_id):
        return self.groups.get(int(group_id))

    async def list_server_group_members(self, group_id):
        return set(self.members.get(int(group_id), set()))

    async def get_server_group_inbound_mode(self, group_id):
        return self.modes.get(int(group_id), "all_managed")

    async def list_server_group_inbounds(self, group_id):
        return set(self.selected.get(int(group_id), set()))


class FakeXUI:
    def __init__(self):
        self.nodes = [
            SimpleNamespace(id=2, name="Direct", enable=True, status="online", transitive=False),
            SimpleNamespace(id=3, name="Transit", enable=True, status="online", transitive=True),
        ]
        self.inbounds = [
            InboundOption(20, "target", "target", "vless", 1020, True, 2),
            InboundOption(10, "master", "master", "vless", 1010, True, None),
        ]
        self.client_ids = {
            "one@example.test": {20},
            "two@example.test": {20, 10},
        }
        self.calls = []
        self.uncertain_attach = False
        self.uncertain_detach = False

    async def node_get(self, node_id):
        for node in self.nodes:
            if node.id == int(node_id):
                return node
        raise RuntimeError("missing node")

    async def nodes_list(self):
        return list(self.nodes)

    async def inbound_options(self):
        return list(self.inbounds)

    async def get_client(self, email):
        return {"client": {"email": email}, "inboundIds": sorted(self.client_ids[email])}

    async def attach_client(self, email, inbound_ids):
        self.calls.append(("attach", email, list(inbound_ids)))
        self.client_ids[email].update(map(int, inbound_ids))
        if self.uncertain_attach:
            self.uncertain_attach = False
            raise XUIMutationError("uncertain attach", uncertain=True)
        return {"success": True}

    async def detach_client(self, email, inbound_ids):
        self.calls.append(("detach", email, list(inbound_ids)))
        self.client_ids[email].difference_update(map(int, inbound_ids))
        if self.uncertain_detach:
            self.uncertain_detach = False
            raise XUIMutationError("uncertain detach", uncertain=True)
        return {"success": True}


def settings():
    return SimpleNamespace(
        inbound_ids=(),
        ignored_protocols=(),
        ignored_tags=(),
        allowed_ports=(),
        allowed_protocols=(),
        vless_flow="",
    )


class NodeDrainTests(unittest.IsolatedAsyncioTestCase):
    async def test_review_marks_user_without_policy_alternative_as_blocker(self):
        db = FakeDB()
        xui = FakeXUI()
        xui.inbounds = [xui.inbounds[0]]
        service = NodeDrainService(db, xui, settings())

        review = await service.review(2)

        self.assertEqual(review.affected_users, 2)
        self.assertEqual(review.blockers, 2)
        self.assertTrue(all(item.blocker == "no_policy_alternative" for item in review.users))

    async def test_attach_happens_before_detach_and_preserves_working_inbound(self):
        db = FakeDB()
        xui = FakeXUI()
        service = NodeDrainService(db, xui, settings())

        result = await service.evacuate_user(2, 1)

        self.assertEqual(result["status"], "success")
        self.assertEqual(xui.calls[0][0], "attach")
        self.assertEqual(xui.calls[1][0], "detach")
        self.assertEqual(xui.client_ids["one@example.test"], {10})

    async def test_existing_alternative_detaches_without_extra_attach(self):
        db = FakeDB()
        xui = FakeXUI()
        service = NodeDrainService(db, xui, settings())

        result = await service.evacuate_user(2, 2)

        self.assertEqual(result["attached"], [])
        self.assertEqual(result["detached"], [20])
        self.assertEqual([call[0] for call in xui.calls], ["detach"])
        self.assertEqual(xui.client_ids["two@example.test"], {10})

    async def test_uncertain_mutations_use_readback_and_are_not_replayed(self):
        db = FakeDB()
        xui = FakeXUI()
        xui.uncertain_attach = True
        xui.uncertain_detach = True
        service = NodeDrainService(db, xui, settings())

        result = await service.evacuate_user(2, 1)

        self.assertEqual(result["status"], "success")
        self.assertEqual([call[0] for call in xui.calls], ["attach", "detach"])
        self.assertEqual(xui.client_ids["one@example.test"], {10})

    async def test_transitive_target_is_rejected(self):
        service = NodeDrainService(FakeDB(), FakeXUI(), settings())
        with self.assertRaisesRegex(NodeDrainError, "транзит"):
            await service.review(3)

    async def test_last_inbound_guard_blocks_detach_when_no_alternative(self):
        db = FakeDB()
        xui = FakeXUI()
        xui.inbounds = [xui.inbounds[0]]
        service = NodeDrainService(db, xui, settings())

        with self.assertRaises(NodeDrainBlocked):
            await service.evacuate_user(2, 1)
        self.assertEqual(xui.calls, [])
        self.assertEqual(xui.client_ids["one@example.test"], {20})

    async def test_plan_store_contains_only_stable_ids(self):
        db = FakeDB()
        xui = FakeXUI()
        service = NodeDrainService(db, xui, settings())
        review = await service.review(2)

        with tempfile.TemporaryDirectory() as tmp:
            store = DrainPlanStore(Path(tmp) / "fleet")
            plan = store.create(review, actor_id=99)
            loaded = store.get(plan["id"])

        self.assertEqual(loaded["node_id"], 2)
        self.assertEqual(loaded["actor"], 99)
        serialized = str(loaded)
        self.assertNotIn("@example.test", serialized)
        self.assertNotIn("sub_id", serialized)
        self.assertNotIn("subscription", serialized)


if __name__ == "__main__":
    unittest.main()
