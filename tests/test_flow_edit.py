"""Regression for Issue #663: no production traffic."""
from __future__ import annotations
import asyncio
import copy
import json
import unittest
from types import SimpleNamespace
from flow_edit import FLOW_CHOICES, FlowEditRejected, discover_flow_targets, FlowConfirmation, pop_confirmation, read_target_outcome

class FakeMaster:
    def __init__(self):
        self.client = {"client":{"email":"qa@example.invalid","tgId":1001,"uuid":"fake-id","subId":"fake-sub","totalGB":1234,"expiryTime":150000,"limitIp":5,"limitHwid":6,"enable":True,"flow":""},"inboundIds":[1,2,3]}
        self.inbounds = {}
        for iid,node,proto,flow in [(1,11,"tcp","xtls-rprx-vision"),(2,11,"tcp","xtls-rprx-vision"),(3,12,"ws","")]:
            self.inbounds[iid] = {"id":iid,"nodeId":node,"tag":f"test-{iid}","protocol":"vless","streamSettings":json.dumps({"security":"reality" if proto=="tcp" else "none","network":proto}),"settings":json.dumps({"clients":[{"email":"qa@example.invalid","flow":flow}]})}
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

class ConfirmationTests(unittest.TestCase):
    def test_nonce_replay_and_expiry(self):
        c=FlowConfirmation(7,1001,"a"*16,11,1,"test-1","xtls-rprx-vision","","f"*64,100.)
        cache={7:c}
        self.assertIsNotNone(pop_confirmation(cache,7,1001,"a"*16,now=101.))
        self.assertIsNone(pop_confirmation(cache,7,1001,"a"*16,now=101.))
        self.assertIsNone(pop_confirmation({7:c},7,1001,"a"*16,now=191.))
