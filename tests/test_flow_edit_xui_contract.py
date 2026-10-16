"""3x-ui scoped update offline contract (#663)."""
import unittest
from unittest.mock import AsyncMock,patch
from pathlib import Path
from xui import XUIClient
from admin_privileges import required_role_for_callback

class ScopedXUITests(unittest.IsolatedAsyncioTestCase):
    async def test_query_and_preserved_fields(self):
        client=XUIClient("https://panel.example.invalid","fixture-token")
        rec={"email":"x@example.invalid","subId":"sub","uuid":"fake","tgId":123,"expiryTime":10000,"totalGB":45,"limitIp":2,"limitHwid":3,"enable":True,"flow":"xtls-rprx-vision","password":"","auth":"","security":"auto","group":"","comment":"","reset":0,"resetDay":0,"resetWeekday":5,"resetMax":0,"trafficReset":"never","trafficResetDay":1,"privateKey":"","publicKey":"","allowedIPs":"","preSharedKey":"","keepAlive":0,"forwardedPorts":"","secret":"","adTag":"","reverse":""}
        with patch.object(client,"_mutation_request",new_callable=AsyncMock) as request:
            await client.update_client_inbound_flow(rec["email"],2,"",client=rec)
        request.assert_awaited_once()
        self.assertEqual(request.await_args.kwargs["params"],{"inboundIds":2})
        self.assertEqual(request.await_args.kwargs["json_payload"]["flow"],"")
        self.assertNotIn("reverse",request.await_args.kwargs["json_payload"])
        for k in ("subId","tgId","expiryTime","totalGB","limitIp","limitHwid","enable","resetWeekday","security","password","auth","comment","trafficReset"):
            self.assertEqual(request.await_args.kwargs["json_payload"][k],rec[k])
    async def test_other_protocol_fields_blocked_before_write(self):
        client=XUIClient("https://panel.example.invalid","fixture-token")
        fields={"email":"x@example.invalid","subId":"sub","uuid":"fake","tgId":123,"expiryTime":10000,"totalGB":45,"limitIp":2,"limitHwid":3,"enable":True,"flow":"xtls-rprx-vision","password":"","auth":"","security":"auto","group":"","comment":"","reset":0,"resetDay":0,"resetWeekday":0,"resetMax":0,"trafficReset":"never","trafficResetDay":1,"privateKey":"","publicKey":"","allowedIPs":"10.0.0.1/32","preSharedKey":"","keepAlive":0,"forwardedPorts":"","secret":"","adTag":"","reverse":""}
        with patch.object(client,"_mutation_request",new_callable=AsyncMock) as request:
            with self.assertRaises(ValueError):
                await client.update_client_inbound_flow(fields["email"],2,"",client=fields)
        request.assert_not_awaited()
    async def test_verified_awg_payload_omits_all_peer_secrets(self):
        client=XUIClient("https://panel.example.invalid","fixture-token")
        rec={"email":"qa@example.invalid","uuid":"fixture-uuid","subId":"fixture-sub",
             "password":"","auth":"", "security":"auto","flow":"","totalGB":12,
             "expiryTime":123456,"limitIp":1,"limitHwid":2,"tgId":42,"enable":True,
             "group":"","comment":"","reset":0,"resetDay":0,"resetWeekday":0,
             "resetMax":0,"trafficReset":"never","trafficResetDay":1,
             "privateKey":"test-key","publicKey":"test-pub","allowedIPs":"10.8.1.5/32",
             "preSharedKey":"test-psk","keepAlive":25,"forwardedPorts":"",
             "secret":"","adTag":"","reverse":""}
        with patch.object(client,"_mutation_request",new_callable=AsyncMock) as request:
            await client.update_client_inbound_flow(rec["email"],2,"xtls-rprx-vision",client=rec,wg_verified=True)
        payload=request.await_args.kwargs["json_payload"]
        for name in ("privateKey","publicKey","preSharedKey","allowedIPs","keepAlive","forwardedPorts"):
            self.assertNotIn(name,payload)
        self.assertEqual(request.await_args.kwargs["params"],{"inboundIds":2})

    async def test_nonempty_reverse_fails_without_mutation(self):
        from xui import SCOPED_FLOW_REQUIRED_CLIENT_FIELDS
        client=XUIClient("https://panel.example.invalid","fixture-token")
        record={key:"" for key in SCOPED_FLOW_REQUIRED_CLIENT_FIELDS}
        record.update({"email":"x@example.invalid","uuid":"fixture-uuid","reverse":'{"tag":"fixture"}'})
        with patch.object(client,"_mutation_request",new_callable=AsyncMock) as request:
            with self.assertRaisesRegex(ValueError,"reverse"):
                await client.update_client_inbound_flow(record["email"],2,"",client=record)
        request.assert_not_awaited()
    async def test_invalid_target_fails_closed(self):
        client=XUIClient("https://panel.example.invalid","fixture-token")
        with patch.object(client,"_mutation_request",new_callable=AsyncMock) as request:
            with self.assertRaises(ValueError):
                await client.update_client_inbound_flow("x@example.invalid",0,"",client={"email":"x@example.invalid"})
        request.assert_not_awaited()

class FlowPrivilegeTests(unittest.TestCase):
    def test_admin_callback_scope(self):
        self.assertEqual(required_role_for_callback("admin:u:flowedit:123:5"),"support")
        self.assertEqual(required_role_for_callback("admin:u:flowib:123:11:7"),"support")
        self.assertEqual(required_role_for_callback("admin:u:flowedit:123"),"support")
        self.assertEqual(required_role_for_callback("admin:u:flowcommit:123:"+"a"*16),"support")
        self.assertEqual(required_role_for_callback("admin:u:flowcheck:123"),"read_only")
        self.assertIsNone(required_role_for_callback("admin:u:flowset:123:11:1:wrong"))
    def test_legacy_bulk_disabled(self):
        source=(Path(__file__).resolve().parents[1]/"advanced_users.py").read_text()
        region=source.split("async def user_flow_sync_run(",1)[1].split('F.data.startswith("admin:u:expiry:")',1)[0]
        self.assertNotIn("bulk_adjust_clients",region)
        self.assertIn("user.flow.legacy_blocked",region)
