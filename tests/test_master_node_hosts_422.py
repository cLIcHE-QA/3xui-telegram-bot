from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from admin_privileges import required_role_for_callback
from xui import XUIClient, XUIError

_TEST_ENV = {
    "BOT_TOKEN": "123456789:offline-token",
    "PANEL_URL": "https://master.example.invalid",
    "PANEL_API_TOKEN": "offline-token",
    "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/{sub_id}",
    "ALLOWED_TELEGRAM_IDS": "1",
    "ADMIN_TELEGRAM_IDS": "1",
    "HOST_CONTROL_TARGETS": "",
    "NODE_BACKUP_TARGETS": "",
}
with patch.dict(os.environ, _TEST_ENV, clear=False):
    import catalog_admin


def fake_call(data):
    return SimpleNamespace(data=data, answer=AsyncMock())


class MasterHostsReadOnlyTests(unittest.IsolatedAsyncioTestCase):
    def test_callbacks_read_only_rbac_and_untrusted_id_rejected(self):
        for callback in (
            "admin:hosts", "admin:hosts:local", "admin:hosts:xui:page:0",
            "admin:hosts:xui:detail:10:1",
        ):
            self.assertEqual(required_role_for_callback(callback), "read_only")
        self.assertEqual(required_role_for_callback("admin:hosts:discover"), "admin")
        self.assertIsNone(required_role_for_callback("admin:hosts:xui:detail:foo:1"))
        self.assertIsNone(required_role_for_callback("admin:hosts:xui:page:-1"))

    def test_guids_map_only_exact_master_id_and_support_shared_host(self):
        nodes = {"node-guid-1": "Netherlands", "node-guid-2": "Finland"}
        self.assertEqual(
            catalog_admin._xui_host_owner_labels(
                {"nodeGuids": ["node-guid-2", "node-guid-1"]}, nodes
            ),
            "Finland, Netherlands",
        )
        self.assertEqual(
            catalog_admin._xui_host_owner_labels(
                {"nodeGuids": ["unknown-guid"]}, nodes
            ),
            "нода не найдена в Master",
        )
        self.assertEqual(
            catalog_admin._xui_host_owner_labels(
                {"nodeGuids": []}, nodes
            ),
            "привязка к ноде не определена",
        )

    def test_inbound_names_and_safe_hosts(self):
        group = {
            "hosts": ["edge.example.org", "edge.example.org", "https://sub.example.org/secret"],
            "port": 443,
            "inboundIds": [5, 6],
        }
        self.assertEqual(
            catalog_admin._xui_host_safe_addresses(group),
            "edge.example.org:443, sub.example.org:443",
        )
        self.assertEqual(
            catalog_admin._xui_host_inbound_labels(
                group, {5: "NL Reality"}
            ),
            "NL Reality, inbound #6 (не обнаружен)",
        )
        self.assertEqual(
            catalog_admin._xui_host_inbound_labels(group, None),
            "метаданные inbound недоступны",
        )

    async def test_master_hosts_only_get_and_fail_closed_payload(self):
        client = XUIClient("https://master.example.invalid", "offline")
        client._request = AsyncMock(return_value={"obj": [{"groupId": "g1", "hosts": ["edge.example.org"]}]})
        self.assertEqual((await client.hosts_list())[0]["groupId"], "g1")
        client._request.assert_awaited_once_with("GET", "/panel/api/hosts/list")
        for payload in ({"obj": None}, {"obj": {}}, {"obj": [None]}):
            client._request.return_value = payload
            with self.assertRaises(XUIError):
                await client.hosts_list()

    def test_node_parser_preserves_guid_without_breaking_legacy(self):
        client = XUIClient("https://master.example.invalid", "offline")
        self.assertEqual(client._parse_node({"id": 1, "guid": "physical-1"}).guid, "physical-1")
        self.assertEqual(client._parse_node({"id": 1}).guid, "")

    async def test_master_hosts_ui_read_only_and_no_sqlite_upsert(self):
        call = fake_call("admin:hosts:xui:page:0")
        with patch.object(catalog_admin, "guard_call", AsyncMock(return_value=True)), patch.object(
            catalog_admin.xui, "hosts_list", AsyncMock(return_value=[
                {"groupId": "g1", "remark": "NL Reality", "nodeGuids": ["guid-1"]}
            ])
        ) as hosts, patch.object(
            catalog_admin, "render_callback", AsyncMock()
        ) as render, patch.object(
            catalog_admin.db, "upsert_host", AsyncMock()
        ) as upsert:
            await catalog_admin.hosts_xui_page(call)
            hosts.assert_awaited_once()
            upsert.assert_not_awaited()
            text = render.await_args.args[1]
            self.assertIn("Master API", text)
            buttons = render.await_args.kwargs["reply_markup"]
            self.assertIn("admin:hosts:xui:detail:0:0", {
                b.callback_data for row in buttons.inline_keyboard for b in row
            })

    async def test_master_hosts_api_unavailable_does_not_show_empty(self):
        call = fake_call("admin:hosts:xui:page:0")
        with patch.object(catalog_admin, "guard_call", AsyncMock(return_value=True)), patch.object(
            catalog_admin.xui, "hosts_list", AsyncMock(side_effect=XUIError("offline"))
        ), patch.object(
            catalog_admin, "render_callback", AsyncMock()
        ) as render:
            await catalog_admin.hosts_xui_page(call)
            self.assertIn("API недоступен", render.await_args.args[1])
            self.assertNotIn("Групп: 0", render.await_args.args[1])

    async def test_detail_joins_node_guid_and_inbound(self):
        call = fake_call("admin:hosts:xui:detail:0:0")
        nodes = [XUIClient._parse_node({"id": 12, "guid": "phys-12", "name": "Finland"})]
        options = [SimpleNamespace(id=51, remark="NL Hysteria2")]
        with patch.object(catalog_admin, "guard_call", AsyncMock(return_value=True)), patch.object(
            catalog_admin.xui, "hosts_list", AsyncMock(return_value=[{
                "remark": "NL UDP",
                "hosts": ["hy.example.org"], "port": 443,
                "nodeGuids": ["phys-12"], "inboundIds": [51]
            }])
        ), patch.object(
            catalog_admin.xui, "nodes_list", AsyncMock(return_value=nodes)
        ), patch.object(
            catalog_admin.xui, "inbound_options", AsyncMock(return_value=options)
        ), patch.object(catalog_admin, "render_callback", AsyncMock()) as render:
            await catalog_admin.hosts_xui_detail(call)
            content = render.await_args.args[1]
            self.assertIn("Finland", content)
            self.assertIn("NL Hysteria2", content)
            self.assertIn("hy.example.org:443", content)
            self.assertNotIn("всё работает", content)


if __name__ == "__main__":
    unittest.main()
