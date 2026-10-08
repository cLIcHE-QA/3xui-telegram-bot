"""V5-A-009: admin Stars refund callback must resolve its runtime helper."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class StarsRefundAdminHandlerBindingTests(unittest.TestCase):
    def test_refund_handler_helper_is_explicitly_imported(self):
        """Catch the production NameError even when helper unit tests pass."""
        tree = ast.parse((ROOT / "business_admin.py").read_text(encoding="utf-8"))
        helper_imports = [
            node for node in tree.body
            if isinstance(node, ast.ImportFrom)
            and node.module == "stars_refund"
            and any(alias.name == "run_stars_refund" and alias.asname is None for alias in node.names)
        ]
        self.assertEqual(len(helper_imports), 1)

        handler = next(
            node for node in tree.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "stars_refund_run"
        )
        invocations = [
            node for node in ast.walk(handler)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "run_stars_refund"
        ]
        self.assertEqual(len(invocations), 1)
        arguments = {arg.arg for arg in invocations[0].keywords}
        self.assertEqual(arguments, {"payment_id", "requested_by"})

    def test_refund_binding_uses_existing_journaled_helper(self):
        from stars_refund import run_stars_refund
        self.assertTrue(callable(run_stars_refund))


if __name__ == "__main__":
    unittest.main()
