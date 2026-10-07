from __future__ import annotations

import inspect
import unittest
from unittest.mock import AsyncMock, patch

import aiohttp

from xui import XUIClient


STATE_CHANGING_METHODS = (
    "node_update",
    "node_delete",
    "node_set_enable",
    "node_update_panels",
    "node_add",
    "restart_xray",
    "stop_xray",
    "restart_panel",
    "import_database",
    "inbound_add",
    "inbound_update",
    "inbound_set_enable",
    "inbound_delete",
    "inbound_reset_traffic",
    "create_client",
    "update_client",
    "attach_client",
    "detach_client",
    "bulk_attach_clients",
    "bulk_detach_clients",
    "bulk_enable_clients",
    "bulk_disable_clients",
    "bulk_reset_traffic",
    "bulk_adjust_clients",
    "delete_client",
    "delete_client_hwid",
)


class XuiMutationCertaintyAuditTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = XUIClient("https://panel.example.invalid", "offline-token")

    def test_all_state_changing_methods_use_explicit_mutation_boundary(self):
        for name in STATE_CHANGING_METHODS:
            with self.subTest(method=name):
                source = inspect.getsource(getattr(XUIClient, name))
                self.assertIn("_mutation_request(", source)
                self.assertNotIn("self._request(", source)

    def test_mutation_boundary_is_one_shot_and_rejects_redirects(self):
        source = inspect.getsource(XUIClient._mutation_request)
        self.assertIn("allow_redirects=False", source)
        self.assertNotIn("for attempt", source)
        self.assertNotIn("while True", source)
        self.assertIn("data_payload", source)

    async def test_import_database_uses_multipart_mutation_boundary(self):
        request = AsyncMock(return_value={"success": True})
        with patch.object(self.client, "_mutation_request", new=request):
            await self.client.import_database(b"SQLite format 3\x00payload", "x-ui.db")

        request.assert_awaited_once()
        args = request.await_args.args
        kwargs = request.await_args.kwargs
        self.assertEqual(args, ("/panel/api/server/importDB",))
        self.assertIsInstance(kwargs.get("data_payload"), aiohttp.FormData)
        self.assertNotIn("json_payload", kwargs)

    async def test_update_client_reads_then_dispatches_exactly_one_mutation(self):
        self.client.get_client = AsyncMock(return_value={
            "client": {
                "email": "user@example.test",
                "subId": "offline-sub",
                "tgId": 1,
                "enable": True,
            }
        })
        request = AsyncMock(return_value={"success": True})
        with patch.object(self.client, "_mutation_request", new=request):
            await self.client.update_client("user@example.test", enable=False)

        request.assert_awaited_once()
        self.assertEqual(
            request.await_args.args,
            ("/panel/api/clients/update/user%40example.test",),
        )
        self.assertFalse(request.await_args.kwargs["json_payload"]["enable"])

    def test_destructive_handlers_read_back_uncertain_outcomes_without_replay(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        cases = (
            ("advanced_users.py", "async def admin_del(call: CallbackQuery):", "await xui.clients_list()", "user.delete.unknown"),
            ("inbound_admin.py", "async def inbound_delete(call: CallbackQuery):", "await xui.inbounds_list(slim=True)", "inbound.delete.unknown"),
            ("advanced_nodes.py", "async def node_delete_run(call: CallbackQuery):", "await xui.nodes_list()", "node.delete.unknown"),
        )
        for filename, function_name, readback, audit_action in cases:
            with self.subTest(filename=filename):
                source = (root / filename).read_text(encoding="utf-8")
                block = source[source.index(function_name):]
                next_handler = block.find("\n@")
                if next_handler > 0:
                    block = block[:next_handler]
                self.assertIn("except XUIMutationError as exc:", block)
                self.assertIn("if exc.uncertain:", block)
                self.assertIn(readback, block)
                self.assertIn("mutation_not_retried=true", block)
                self.assertIn("readback=unavailable", block)
                self.assertIn(audit_action, block)
                self.assertEqual(block.count("delete_client(rec.email)") if filename == "advanced_users.py" else block.count("inbound_delete(iid)") if filename == "inbound_admin.py" else block.count("node_delete(node_id)"), 1)

    def test_disaster_recovery_records_uncertain_import_as_unknown(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1] / "disaster_recovery.py").read_text(encoding="utf-8")
        block = source[source.index("async def restore_confirm_message"):source.index("async def restore_export_env")]
        self.assertIn("except XUIMutationError as exc:", block)
        self.assertIn('status = "unknown" if exc.uncertain else "failed"', block)
        self.assertIn('audit_action = "restore.unknown" if exc.uncertain else "restore.failed"', block)
        self.assertIn("mutation_not_retried=true", block)
        self.assertIn("Не запускай restore повторно вслепую", block)



    def test_field_update_handlers_read_back_uncertain_outcomes_without_replay(self) -> None:
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        cases = (
            (
                "advanced_nodes.py",
                "async def node_rename_finish(message: Message, state: FSMContext):",
                "await xui.node_update(",
                "await xui.node_get_raw(node_id)",
                "node.rename.unknown",
            ),
            (
                "inbound_admin.py",
                "async def inbound_toggle(call: CallbackQuery):",
                "await xui.inbound_set_enable(iid, enabled)",
                "await xui.inbound_get(iid)",
                "readback=mismatch",
            ),
            (
                "advanced_users.py",
                "async def user_expiry_save(message: Message, state: FSMContext):",
                "await xui.update_client(rec.email, expiryTime=new_expiry)",
                "await xui.get_client(rec.email)",
                "user.expiry.set.unknown",
            ),
            (
                "advanced_users.py",
                "async def user_traffic_save(message: Message, state: FSMContext):",
                "await xui.update_client(rec.email, totalGB=total_bytes)",
                "await xui.get_client(rec.email)",
                "user.traffic_limit.set.unknown",
            ),
            (
                "advanced_users.py",
                "async def user_flow_sync_run(call: CallbackQuery):",
                "await xui.bulk_adjust_clients([rec.email], flow=settings.vless_flow)",
                "await xui.get_client(rec.email)",
                "user.flow.sync.unknown",
            ),
        )
        for filename, signature, mutation_call, readback_call, unknown_marker in cases:
            with self.subTest(filename=filename, signature=signature):
                source = (root / filename).read_text(encoding="utf-8")
                start = source.index(signature)
                next_handler = source.find("\n@", start)
                block = source[start:] if next_handler < 0 else source[start:next_handler]
                self.assertIn("except XUIMutationError as exc:", block)
                self.assertIn("if not exc.uncertain:", block)
                self.assertIn(readback_call, block)
                self.assertIn("mutation_not_retried=true", block)
                self.assertIn("readback=unavailable", block)
                self.assertIn(unknown_marker, block)
                self.assertEqual(block.count(mutation_call), 1)


    def test_phase4_create_bulk_and_provisioning_paths_preserve_unknown_without_replay(self) -> None:
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]

        users = (root / "advanced_users.py").read_text(encoding="utf-8")
        update_helper = users[
            users.index("async def _update_client_with_readback"):
            users.index("async def _membership_with_readback")
        ]
        self.assertIn("except XUIMutationError as exc:", update_helper)
        self.assertIn("await xui.get_client(email)", update_helper)
        self.assertIn("mutation_not_retried=true", update_helper)
        self.assertEqual(update_helper.count("await xui.update_client("), 1)

        membership_helper = users[
            users.index("async def _membership_with_readback"):
            users.index("async def _flow_with_readback")
        ]
        self.assertIn("except XUIMutationError as exc:", membership_helper)
        self.assertIn("await xui.get_client(email)", membership_helper)
        self.assertIn("mutation_not_retried=true", membership_helper)

        bulk = users[users.index("async def bulk_run(call: CallbackQuery"):]
        self.assertIn("except XUIMutationError as exc:", bulk)
        self.assertIn("users.bulk.{action}.unknown", bulk)
        self.assertIn("mutation_not_retried=true", bulk)
        self.assertIn('readback = "not_provable"', bulk)

        user_reset = users[
            users.index("async def user_reset_run(call: CallbackQuery):"):
            users.index("async def user_sub_rotate_ask", users.index("async def user_reset_run(call: CallbackQuery):"))
        ]
        self.assertIn("user.traffic.reset.unknown", user_reset)
        self.assertIn("readback=not_provable", user_reset)
        self.assertIn("mutation_not_retried=true", user_reset)

        inbound = (root / "inbound_admin.py").read_text(encoding="utf-8")
        add_helper = inbound[
            inbound.index("async def _inbound_add_with_readback"):
            inbound.index("def _visible", inbound.index("async def _inbound_add_with_readback"))
        ]
        self.assertIn("except XUIMutationError as exc:", add_helper)
        self.assertIn("await xui.inbounds_list(slim=True)", add_helper)
        self.assertIn("mutation_not_retried=true", add_helper)
        self.assertEqual(add_helper.count("await xui.inbound_add("), 1)

        inbound_reset = inbound[
            inbound.index("async def inbound_reset_run(call: CallbackQuery):"):
            inbound.index("async def _target_keyboard", inbound.index("async def inbound_reset_run(call: CallbackQuery):"))
        ]
        self.assertIn("inbound.reset_traffic.unknown", inbound_reset)
        self.assertIn("readback=not_provable", inbound_reset)
        self.assertEqual(inbound_reset.count("await xui.inbound_reset_traffic(iid)"), 1)

        node_admin = (root / "node_admin.py").read_text(encoding="utf-8")
        node_add = node_admin[node_admin.index("async def admin_node_add_save"):]
        self.assertIn("except XUIMutationError as exc:", node_add)
        self.assertIn("await xui.nodes_list()", node_add)
        self.assertIn("node.add.unknown", node_add)
        self.assertIn("mutation_not_retried=true", node_add)
        self.assertEqual(node_add.count("await xui.node_add(payload)"), 1)

        client_access = (root / "client_access.py").read_text(encoding="utf-8")
        self.assertNotIn("await xui.create_client(", client_access)
        self.assertNotIn("async def create_user", client_access)
        self.assertIn('F.data.in_({"create", "inbounds", "subscription"})', client_access)
        self.assertIn("Старый тестовый экран заменён личным кабинетом.", client_access)

        provisioning = (root / "provisioning.py").read_text(encoding="utf-8")
        sync = provisioning[
            provisioning.index("async def sync_user("):
            provisioning.index("async def provision_many(")
        ]
        self.assertIn("except XUIMutationError as exc:", sync)
        self.assertIn("ProvisioningUnknown", sync)
        self.assertIn("mutation_not_retried=true", provisioning)
        self.assertIn('"unknown": unknown', provisioning)

if __name__ == "__main__":
    unittest.main()
