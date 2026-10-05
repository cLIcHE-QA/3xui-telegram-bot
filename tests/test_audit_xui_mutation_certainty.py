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

if __name__ == "__main__":
    unittest.main()
