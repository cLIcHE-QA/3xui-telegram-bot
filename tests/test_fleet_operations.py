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
        self.assertIn('"остановлено после ошибки"', text)
        self.assertIn("rollout_lock = asyncio.Lock()", text)

    def test_terminal_rollout_paths_create_parent_jobs(self):
        text = FLEET.read_text(encoding="utf-8")
        create_review = text[text.index("async def _create_rollout_review("):text.index("def _plan_status_icon(")]
        self.assertIn('if not pending:', create_review)
        self.assertIn("await _start_rollout_job(plan)", create_review)
        self.assertIn('await _finish_rollout_job(plan, "success")', create_review)

        rollout_run = text[text.index("async def rollout_run("):text.index("async def fleet_jobs(")]
        cancel_block = rollout_run[rollout_run.index('if action == "cancel":'):rollout_run.index('await _render_plan(call, plan, "⏹ Обновление остановлено оператором.')]
        self.assertIn("await _start_rollout_job(plan)", cancel_block)
        self.assertIn('await _finish_rollout_job(plan, "cancelled")', cancel_block)

    def test_rollout_job_summary_marks_already_current_as_skipped(self):
        text = FLEET.read_text(encoding="utf-8")
        finish_job = text[text.index("async def _finish_rollout_job("):text.index("async def _execute_rollout_node(")]
        self.assertIn("'skipped' if node_id in skipped else 'pending'", finish_job)

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
        import unicodedata

        tree = ast.parse(FLEET.read_text(encoding="utf-8"))
        bare = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Tuple) or len(node.elts) != 2:
                continue
            label, callback = node.elts
            if not (
                isinstance(label, ast.Constant)
                and isinstance(label.value, str)
                and isinstance(callback, ast.Constant)
                and isinstance(callback.value, str)
                and callback.value.startswith("admin:")
            ):
                continue
            value = label.value.strip()
            if not value or unicodedata.category(value[0]) not in {"So", "Sm"}:
                bare.append(value)
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
