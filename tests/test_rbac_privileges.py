from __future__ import annotations

import ast
from pathlib import Path
import unittest

from admin_privileges import (
    CALLBACK_RULES,
    PRIVILEGES,
    ROLE_RANK,
    declared_route_specs,
    privilege_for_callback,
    required_role_for_callback,
)


class RBACPrivilegesTests(unittest.TestCase):
    def test_permission_ids_are_unique_and_roles_are_valid(self):
        ids = [item.permission_id for item in PRIVILEGES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(ids)
        for item in PRIVILEGES:
            self.assertIn(item.minimum_role, ROLE_RANK)
            self.assertRegex(item.permission_id, r"^[a-z][a-z0-9_.]*$")

    def test_callback_rules_reference_known_permissions(self):
        ids = {item.permission_id for item in PRIVILEGES}
        self.assertTrue(CALLBACK_RULES)
        for rule in CALLBACK_RULES:
            self.assertIn(rule.permission_id, ids)
            self.assertIn(rule.kind, {"exact", "prefix", "regex"})
            self.assertTrue(rule.value)

    def test_representative_role_boundaries(self):
        cases = {
            "admin:home": "read_only",
            "adminuser:123": "read_only",
            "adminextend:123": "support",
            "admindel:123": "admin",
            "admin:backup:full": "admin",
            "admin:node:7": "read_only",
            "admin:nodectl:7:backup": "admin",
            "admin:inbound:7": "read_only",
            "admin:inbound:editfp:7": "admin",
            "admin:plans": "read_only",
            "admin:plan:toggle:2": "admin",
            "admin:payments": "read_only",
            "admin:payment:status:4:paid": "admin",
            "admin:administrators": "owner",
            "admin:privileges": "owner",
            "admin:settings": "read_only",
            "admin:alerts": "read_only",
            "admin:alerts:toggle:disk": "admin",
            "admin:restore": "owner",
            "admin:hostctl:n2": "read_only",
            "admin:hostctl:n2:sr:run": "admin",
            "admin:hostctl:n2:sp:run": "owner",
            "admin:fleet": "read_only",
            "admin:fleet:rollout": "admin",
            "admin:versions": "read_only",
            "admin:ver:run:0123456789abcdef": "admin",
            "admin:ver:unlock:0123456789abcdef": "owner",
            "admin:botupd": "owner",
            "admin:botupd:choose": "owner",
            "admin:botupd:pre:v4.19.0": "owner",
            "admin:botupd:run:v4.19.0": "owner",
            "admin:botupd:down:v4.18.0": "owner",
            "admin:botupd:op:0123456789abcdef0123456789abcdef": "owner",
        }
        for data, role in cases.items():
            with self.subTest(data=data):
                self.assertEqual(required_role_for_callback(data), role)

    def test_unknown_admin_callback_is_fail_closed(self):
        self.assertIsNone(privilege_for_callback("admin:new-dangerous-mutation"))
        self.assertIsNone(required_role_for_callback("admin:new-dangerous-mutation"))

    def test_literal_admin_routes_are_declared_in_catalog(self):
        root = Path(__file__).resolve().parents[1]
        files = (
            "bot.py",
            "node_admin.py",
            "system_admin.py",
            "storage_admin.py",
            "advanced_nodes.py",
            "advanced_users.py",
            "inbound_admin.py",
            "catalog_admin.py",
            "business_admin.py",
            "admin_observability.py",
            "disaster_recovery.py",
            "logs_alerts.py",
            "host_control_ui.py",
            "fleet_operations.py",
            "versions_updates.py",
            "bot_updates.py",
        )
        declared = declared_route_specs()
        missing: list[str] = []

        for name in files:
            tree = ast.parse((root / name).read_text(encoding="utf-8"), filename=name)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue

                # F.data.startswith("admin:...")
                if node.func.attr == "startswith" and node.args:
                    value = node.args[0]
                    if isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value.startswith("admin"):
                        if ("prefix", value.value) not in declared:
                            missing.append(f"{name}:{node.lineno}:prefix:{value.value}")
                    continue

                # F.data.regexp(r"^admin:...")
                if node.func.attr == "regexp" and node.args:
                    value = node.args[0]
                    if isinstance(value, ast.Constant) and isinstance(value.value, str) and "admin" in value.value:
                        if ("regex", value.value) not in declared:
                            missing.append(f"{name}:{node.lineno}:regex:{value.value}")
                    continue

                # F.data == "admin:..."
                if not isinstance(node.func, ast.Attribute) or node.func.attr != "callback_query":
                    continue
                for arg in node.args:
                    if not isinstance(arg, ast.Compare) or len(arg.ops) != 1 or not isinstance(arg.ops[0], ast.Eq):
                        continue
                    candidates = [arg.left, *arg.comparators]
                    for value in candidates:
                        if isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value.startswith("admin"):
                            if ("exact", value.value) not in declared:
                                missing.append(f"{name}:{node.lineno}:exact:{value.value}")

        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
