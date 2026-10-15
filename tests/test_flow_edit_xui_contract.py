"""3x-ui scoped update offline contract (#663)."""
import unittest
from unittest.mock import AsyncMock,patch
from pathlib import Path
from xui import XUIClient
from admin_privileges import required_role_for_callback

class ScopedXUITests(unittest.IsolatedAsyncioTestCase):
    async def test_query_and_preserved_fields(self):
        client=XUIClient("https://panel.example.invalid","fixture-token")
        rec={"email":"x@example.invalid","subId":"sub","uuid":"fake","tgId":123,"expiryTime":10000,"totalGB":45,"limitIp":2,"limitHwid":3,"enable":True,"flow":"xtls-rprx-vision"}
        with patch.object(client,"_mutation_request",new_callable=AsyncMock) as request:
            await client.update_client_inbound_flow(rec["email"],2,"",client=rec)
        request.assert_awaited_once()
        self.assertEqual(request.await_args.kwargs["params"],{"inboundIds":2})
        self.assertEqual(request.await_args.kwargs["json_payload"]["flow"],"")
        for k in ("subId","tgId","expiryTime","totalGB","limitIp","limitHwid","enable"):
            self.assertEqual(request.await_args.kwargs["json_payload"][k],rec[k])
    async def test_invalid_target_fails_closed(self):
        client=XUIClient("https://panel.example.invalid","fixture-token")
        with patch.object(client,"_mutation_request",new_callable=AsyncMock) as request:
            with self.assertRaises(ValueError):
                await client.update_client_inbound_flow("x@example.invalid",0,"",client={"email":"x@example.invalid"})
        request.assert_not_awaited()

class FlowPrivilegeTests(unittest.TestCase):
    def test_admin_callback_scope(self):
        self.assertEqual(required_role_for_callback("admin:u:flowedit:123"),"support")
        self.assertEqual(required_role_for_callback("admin:u:flowcommit:123:"+"a"*16),"support")
        self.assertEqual(required_role_for_callback("admin:u:flowcheck:123"),"read_only")
        self.assertIsNone(required_role_for_callback("admin:u:flowset:123:11:1:wrong"))
    def test_legacy_bulk_disabled(self):
        source=(Path(__file__).resolve().parents[1]/"advanced_users.py").read_text()
        region=source.split("async def user_flow_sync_run(",1)[1].split('F.data.startswith("admin:u:expiry:")',1)[0]
        self.assertNotIn("bulk_adjust_clients",region)
        self.assertIn("user.flow.legacy_blocked",region)
