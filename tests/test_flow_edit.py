"""Regression for Issue #663: no production traffic."""
from __future__ import annotations
import copy
import json
import unittest
from flow_edit import FLOW_CHOICES, FlowEditRejected, discover_flow_targets, FlowConfirmation, pop_confirmation, read_target_outcome

class FakeMaster:
    def __init__(self):
        self.client = {"client":{"email":"qa@example.invalid","tgId":1001,"uuid":"fake-id","subId":"fake-sub","password":"","auth":"","security":"auto","totalGB":1234,"expiryTime":150000,"limitIp":5,"limitHwid":6,"enable":True,"flow":"","group":"","comment":"","reset":0,"resetDay":0,"resetWeekday":4,"resetMax":0,"trafficReset":"never","trafficResetDay":1,"privateKey":"","publicKey":"","allowedIPs":"","preSharedKey":"","keepAlive":0,"forwardedPorts":"","secret":"","adTag":"","reverse":""},"inboundIds":[1,2,3]}
        self.inbounds = {}
        for iid,node,proto,flow in [(1,11,"tcp","xtls-rprx-vision"),(2,11,"tcp","xtls-rprx-vision"),(3,12,"ws","")]:
            self.inbounds[iid] = {"id":iid,"nodeId":node,"tag":f"test-{iid}","disableFlow":False,"protocol":"vless","streamSettings":json.dumps({"security":"reality" if proto=="tcp" else "none","network":proto}),"settings":json.dumps({"clients":[{"email":"qa@example.invalid","flow":flow}]})}
        self.writes=[]
    async def get_client(self,email):
        return copy.deepcopy(self.client)
    async def inbound_get(self,iid):
        return copy.deepcopy(self.inbounds[iid])
    async def update_client_inbound_flow(self,email,iid,flow,*,client):
        self.writes.append((iid,flow))
        val=json.loads(self.inbounds[iid]["settings"])
        val["clients"][0]["flow"]=flow
        self.inbounds[iid]["settings"]=json.dumps(val)

class FlowEditTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.master=FakeMaster()
    async def test_three_choices(self):
        self.assertEqual(FLOW_CHOICES,{"n":"","v":"xtls-rprx-vision","u":"xtls-rprx-vision-udp443"})
    async def test_scoped_discovery_excludes_non_reality(self):
        snap=await discover_flow_targets(self.master,"qa@example.invalid",1001)
        self.assertEqual([(t.node_id,t.inbound_id) for t in snap.targets],[(11,1),(11,2)])
        self.assertEqual(self.master.writes,[])
        with self.assertRaises(FlowEditRejected):
            snap.select(12,3)
    async def test_wrong_identity_fails_closed(self):
        with self.assertRaises(FlowEditRejected):
            await discover_flow_targets(self.master,"qa@example.invalid",999)
    async def test_ambiguous_binding_fails_closed(self):
        inbound=self.master.inbounds[1]
        inbound["settings"]=json.dumps({"clients":[{"email":"qa@example.invalid","flow":""},{"email":"qa@example.invalid","flow":""}]})
        with self.assertRaises(FlowEditRejected):
            await discover_flow_targets(self.master,"qa@example.invalid",1001)
    async def test_single_inbound_only(self):
        snap=await discover_flow_targets(self.master,"qa@example.invalid",1001)
        await self.master.update_client_inbound_flow("qa@example.invalid",1,"",client=snap.client)
        after=await discover_flow_targets(self.master,"qa@example.invalid",1001)
        self.assertEqual(after.select(11,1).current_flow,"")
        self.assertEqual(after.select(11,2).current_flow,"xtls-rprx-vision")
        self.assertEqual(len(self.master.writes),1)
    async def test_node_unavailable_not_pass(self):
        async def inspect(*_):
            return [],0
        result=await read_target_outcome(self.master,(),"qa@example.invalid",1001,11,1,"xtls-rprx-vision",inspect=inspect)
        self.assertEqual(result,("MATCH","UNKNOWN"))
    async def test_stale_fingerprint_changes(self):
        before=await discover_flow_targets(self.master,"qa@example.invalid",1001)
        self.master.client["client"]["expiryTime"]+=1
        after=await discover_flow_targets(self.master,"qa@example.invalid",1001)
        self.assertNotEqual(before.fingerprint,after.fingerprint)
    async def test_shared_flow_change_invalidates_confirmation(self):
        before=await discover_flow_targets(self.master,"qa@example.invalid",1001)
        self.master.client["client"]["flow"]="xtls-rprx-vision"
        after=await discover_flow_targets(self.master,"qa@example.invalid",1001)
        self.assertNotEqual(before.fingerprint, after.fingerprint)
    async def test_explicit_disable_flow_not_eligible(self):
        self.master.inbounds[1]["disableFlow"]=True
        snap=await discover_flow_targets(self.master,"qa@example.invalid",1001)
        with self.assertRaises(FlowEditRejected):
            snap.select(11,1)
    async def test_local_master_is_explicit(self):
        self.master.inbounds[1].pop("nodeId")
        snap=await discover_flow_targets(self.master,"qa@example.invalid",1001)
        self.assertEqual(snap.select(0,1).inbound_id,1)
        self.master.inbounds[1]["originNodeGuid"]="remote-origin"
        with self.assertRaises(FlowEditRejected):
            await discover_flow_targets(self.master,"qa@example.invalid",1001)
    async def test_invalid_node_id_fails_closed(self):
        self.master.inbounds[1]["nodeId"]=0
        with self.assertRaises(FlowEditRejected):
            await discover_flow_targets(self.master,"qa@example.invalid",1001)
    async def test_empty_reverse_and_omitted_inbound_flow(self):
        self.assertEqual(self.master.client["client"]["reverse"], "")
        inbound=self.master.inbounds[1]
        settings=json.loads(inbound["settings"])
        settings["clients"][0].pop("flow")
        inbound["settings"]=json.dumps(settings)
        snap=await discover_flow_targets(self.master,"qa@example.invalid",1001)
        self.assertEqual(snap.select(11,1).current_flow,"")
    async def test_nonempty_reverse_is_rejected(self):
        self.master.client["client"]["reverse"]='{"tag":"fixture"}'
        with self.assertRaises(FlowEditRejected):
            await discover_flow_targets(self.master,"qa@example.invalid",1001)
    async def test_incomplete_master_record_fails_closed(self):
        del self.master.client["client"]["resetWeekday"]
        with self.assertRaises(FlowEditRejected):
            await discover_flow_targets(self.master,"qa@example.invalid",1001)

class FleetPaginationTests(unittest.TestCase):
    def test_many_nodes_have_navigation(self):
        from flow_edit_routes import PAGE_SIZE, page_keyboard
        from flow_edit import MAX_EDIT_NODES, MAX_EDIT_INBOUNDS
        self.assertGreaterEqual(MAX_EDIT_NODES, 32)
        self.assertGreaterEqual(MAX_EDIT_INBOUNDS, 128)
        options = [(f"Node {i}", f"node:{i}") for i in range(40)]
        markup = page_keyboard(options, 2, route_prefix="admin:u:flowedit:1001", back=("Отмена", "cancel"))
        labels = [row[0].text for row in markup.inline_keyboard]
        self.assertEqual(labels[:PAGE_SIZE], [f"Node {i}" for i in range(16, 24)])
        self.assertIn("▶️ Далее", labels)
        self.assertIn("◀️ Назад", labels)
        self.assertEqual(labels[-1], "Отмена")
        with self.assertRaises(ValueError):
            page_keyboard(options, 5, route_prefix="x", back=("Back", "back"))


class ConfirmationTests(unittest.TestCase):
    def test_nonce_replay_and_expiry(self):
        c=FlowConfirmation(7,1001,"a"*16,11,1,"test-1","xtls-rprx-vision","","f"*64,100.)
        cache={7:c}
        self.assertIsNotNone(pop_confirmation(cache,7,1001,"a"*16,now=101.))
        self.assertIsNone(pop_confirmation(cache,7,1001,"a"*16,now=101.))
        self.assertIsNone(pop_confirmation({7:c},7,1001,"a"*16,now=191.))
