from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
PRELUDE = r'''
import contextlib, importlib.abc, io, json, runpy, sys
from pathlib import Path
from types import SimpleNamespace
root = Path(sys.argv[1])
sys.path.insert(0, str(root))
blocked = {"config", "app_runtime", "provisioning", "checkout_service", "commerce", "db", "dotenv"}
assert not blocked.intersection(sys.modules)
class DenyApplicationGraph(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] in blocked:
            raise ImportError("unneeded application import blocked before execution: " + fullname)
sys.meta_path.insert(0, DenyApplicationGraph())
tool = runpy.run_path(str(root / "scripts/benchmark-panel-reads.py"), run_name="isolated_benchmark")
'''


class PanelReadImportIsolation977Tests(unittest.TestCase):
    def fresh_process(self, code: str):
        reply = subprocess.run(
            [sys.executable, "-c", PRELUDE + "\n" + textwrap.dedent(code), str(ROOT)],
            cwd=ROOT, env={"PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(reply.returncode, 0, reply.stderr[-2500:])
        return json.loads(reply.stdout)

    def test_guarded_import_preserves_dto_error_aliases_and_service_injection(self):
        result = self.fresh_process('''
            import customer_provider_xui as adapter
            import customer_service as service
            aliases = ["CustomerTraffic", "CustomerProviderAccess", "CustomerDevice",
                       "CustomerDeviceInventory", "CustomerDeviceDeleteUnknown",
                       "CustomerDeviceDeleteRejected", "CustomerProviderUnavailable"]
            for name in aliases:
                assert getattr(adapter, name) is getattr(service, name)
                assert getattr(service, name).__module__ == "customer_service"
            assert service.CustomerTraffic(1, 2, 3) == adapter.CustomerTraffic(1, 2, 3)
            assert service.CustomerDeviceDeleteUnknown is adapter.CustomerDeviceDeleteUnknown
            instance = service.CustomerPortalService(
                SimpleNamespace(), SimpleNamespace(), SimpleNamespace(),
                subscription_url_template="https://sub.example.invalid/sub/{sub_id}",
            )
            assert instance.checkout is None
            assert not blocked.intersection(sys.modules)
            print(json.dumps({"aliases": aliases, "forbidden_modules": sorted(blocked.intersection(sys.modules))}))
        ''')
        self.assertEqual(result["forbidden_modules"], [])
        self.assertEqual(len(result["aliases"]), 7)

    def test_guarded_worker_runs_actual_provider_path_without_config_or_db(self):
        result = self.fresh_process('''
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = tool["main"](["--worker", "--scenario", "traffic_same", "--clients", "1",
                                     "--requests", "2", "--concurrency", "2", "--delay-ms", "0"])
            assert code == 0 and not blocked.intersection(sys.modules)
            print(json.dumps({"result": json.loads(output.getvalue()),
                              "forbidden_modules": sorted(blocked.intersection(sys.modules))}))
        ''')
        self.assertEqual(result["forbidden_modules"], [])
        self.assertEqual(result["result"]["calls_by_route"], {"get": 2, "traffic": 2})
        self.assertEqual(result["result"]["sessions"], 4)
        self.assertEqual(result["result"]["closed_sessions"], 4)

    def test_guarded_cli_matrix_finishes_without_application_environment(self):
        result = self.fresh_process('''
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = tool["main"](["--scenario", "get", "list", "traffic_same", "traffic_unique",
                                     "--clients", "1", "--requests", "2", "--concurrency", "2",
                                     "--delay-ms", "0"])
            assert code == 0 and not blocked.intersection(sys.modules)
            print(json.dumps({"report": json.loads(output.getvalue()),
                              "forbidden_modules": sorted(blocked.intersection(sys.modules))}))
        ''')
        self.assertEqual(result["forbidden_modules"], [])
        self.assertEqual(len(result["report"]["cases"]), 4)
        self.assertEqual(result["report"]["scope"], "offline_fake_transport_bot_json_only")
        for case in result["report"]["cases"]:
            self.assertEqual(case["calls"], 4 if case["scenario"].startswith("traffic_") else 2)
            self.assertEqual(case["sessions"], case["closed_sessions"])


if __name__ == "__main__":
    unittest.main()
