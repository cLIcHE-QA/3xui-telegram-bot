from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FLEET = ROOT / "fleet_operations.py"
DOC = ROOT / "docs" / "FLEET_OPERATIONS.md"


class FleetOperationsContractTests(unittest.TestCase):
    def test_router_has_read_only_health_and_guarded_mutations(self):
        text = FLEET.read_text(encoding="utf-8")
        self.assertIn('F.data == "admin:fleet:health"', text)
        self.assertIn('minimum="read_only"', text)
        self.assertIn('minimum="admin"', text)
        self.assertIn("MAX_MUTATION_TARGETS = 20", text)

    def test_rollout_reuses_existing_update_service(self):
        text = FLEET.read_text(encoding="utf-8")
        self.assertIn("service as update_service", text)
        self.assertIn("await update_service.prepare(", text)
        self.assertIn("await update_service.execute(", text)
        self.assertIn("allow_prepared_maintenance=True", text)
        self.assertNotIn(".update_panel(", text)
        self.assertNotIn(".install_xray(", text)

    def test_canary_and_stop_on_failure_are_explicit(self):
        text = FLEET.read_text(encoding="utf-8")
        self.assertIn('"canary": pending[0] if pending else 0', text)
        self.assertIn('"canary_passed"', text)
        self.assertIn('"not_touched"', text)
        self.assertIn('"stop-on-failure"', text)
        self.assertIn("rollout_lock = asyncio.Lock()", text)

    def test_restart_recovery_never_replays_mutations(self):
        text = FLEET.read_text(encoding="utf-8")
        self.assertIn("async def recover_fleet_operations()", text)
        self.assertIn('"interrupted"', text)
        self.assertIn("mutation_not_retried=true", text)
        recovery = text[text.index("async def recover_fleet_operations()"):]
        self.assertNotIn("update_service.execute(", recovery)
        self.assertNotIn("node_set_enable(", recovery)

    def test_rollout_requires_stable_privileged_bindings(self):
        text = FLEET.read_text(encoding="utf-8")
        self.assertIn('direct_binding == "node_id" and host_binding == "node_id"', text)
        self.assertIn('if not assessment["ready"]', text)

    def test_no_mass_stop_surface(self):
        text = FLEET.read_text(encoding="utf-8").lower()
        for forbidden in [
            "stop service",
            "stop xray",
            "host_control.execute",
            "action=stop",
        ]:
            self.assertNotIn(forbidden, text)

    def test_private_rollout_journal(self):
        text = FLEET.read_text(encoding="utf-8")
        self.assertIn("os.chmod(self.root, 0o700)", text)
        self.assertIn("os.chmod(tmp, 0o600)", text)

    def test_all_static_buttons_have_visual_prefix(self):
        tree = ast.parse(FLEET.read_text(encoding="utf-8"))
        labels = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Tuple) or len(node.elts) != 2:
                continue
            label = node.elts[0]
            if isinstance(label, ast.Constant) and isinstance(label.value, str):
                if label.value.startswith(("admin:", "fleet.")):
                    continue
                labels.append(label.value)
        bare = [
            value for value in labels
            if value and value[0].isalnum() and value not in {"3x-ui latest stable", "Xray Core"}
        ]
        self.assertEqual(bare, [])

    def test_scope_document_contains_safety_contract(self):
        text = DOC.read_text(encoding="utf-8")
        for required in [
            "Canary",
            "Stop-on-failure",
            "Restart / crash safety",
            "automatic retry",
            "mass `Stop service`",
            "rollout legacy-name privileged bindings",
        ]:
            self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
