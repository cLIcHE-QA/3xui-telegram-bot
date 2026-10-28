from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import asyncio
import importlib.util
import io
import json
import math
import os
import socket
from pathlib import Path
import subprocess
import sys
import tracemalloc
import unittest
from unittest.mock import patch

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/benchmark-panel-reads.py"
SPEC = importlib.util.spec_from_file_location("panel_read_baseline_972", SCRIPT)
bench = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bench
SPEC.loader.exec_module(bench)


class BaselineTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_read_paths_and_provider_fanout(self):
        for scenario in bench.SCENARIOS:
            with self.subTest(scenario=scenario):
                case = bench.Case(scenario, clients=3, requests=6, concurrency=3, delay_ms=0)
                result = await bench.measure(case)
                calls = 12 if scenario.startswith("traffic_") else 6
                self.assertEqual(result["calls"], calls)
                self.assertEqual(result["sessions"], calls)
                self.assertEqual(result["closed_sessions"], calls)
                expected = {"get": 6, "traffic": 6} if calls == 12 else {scenario: 6}
                self.assertEqual(result["calls_by_route"], expected)
                self.assertEqual(result["operations"], 6)
                self.assertEqual(result["peak_transport_active"], 3)
                self.assertEqual(result["peak_driver_active"], 3)
                self.assertEqual(result["driver_initial_backlog"], 3)
                self.assertEqual(result["distinct_addressed_owners"],
                                 6 if scenario == "traffic_unique" else 0 if scenario == "list" else 1)
                for name in ("wall_seconds", "cpu_seconds", "operation_p50_ms", "operation_p95_ms",
                             "operations_per_second", "api_calls_per_second"):
                    self.assertTrue(math.isfinite(result[name]))
                    self.assertGreaterEqual(result[name], 0)
                self.assertGreaterEqual(result["operation_p95_ms"], result["operation_p50_ms"])
                self.assertGreater(result["timed_python_heap_peak_bytes"], 0)
                self.assertGreater(result["process_peak_rss_bytes"], 0)
                self.assertFalse(tracemalloc.is_tracing())

    async def test_list_cost_scales_with_fixture_get_response_does_not(self):
        small = await bench.measure(bench.Case("list", 1, 2, 1, 0))
        large = await bench.measure(bench.Case("list", 100, 2, 1, 0))
        self.assertGreater(large["response_json_bytes"], small["response_json_bytes"] * 30)
        self.assertEqual(small["calls"], large["calls"])
        first = await bench.measure(bench.Case("get", 1, 2, 1, 0))
        last = await bench.measure(bench.Case("get", 100, 2, 1, 0))
        self.assertEqual(first["response_json_bytes"], last["response_json_bytes"])

    async def test_cancellation_closes_all_contexts_and_restores_transport(self):
        case = bench.Case("traffic_same", 1, 32, 8, 20)
        transport = bench.OfflineTransport(case)
        original_session = aiohttp.ClientSession
        with patch.object(bench, "OfflineTransport", return_value=transport):
            task = asyncio.create_task(bench.measure(case))
            for _ in range(100):
                if transport.active:
                    break
                await asyncio.sleep(0)
            self.assertGreater(transport.active, 0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(transport.active, 0)
        self.assertEqual(transport.sessions, transport.closed_sessions)
        self.assertIs(aiohttp.ClientSession, original_session)
        self.assertFalse(tracemalloc.is_tracing())

    async def test_parse_error_fails_without_partial_metrics_and_cleans_up(self):
        case = bench.Case("get", 1, 8, 4, 0)
        transport = bench.OfflineTransport(case)
        url = next(url for url, (kind, _) in transport.bodies.items() if kind == "get")
        transport.bodies[url] = ("get", "invalid offline JSON")
        original_session = aiohttp.ClientSession
        with patch.object(bench, "OfflineTransport", return_value=transport):
            with self.assertRaises(Exception):
                await bench.measure(case)
        self.assertEqual(transport.active, 0)
        self.assertEqual(transport.sessions, transport.closed_sessions)
        self.assertIs(aiohttp.ClientSession, original_session)
        self.assertFalse(tracemalloc.is_tracing())

    async def test_unreviewed_socket_path_is_denied_without_network(self):
        async def unexpected_read(*args):
            socket.socket()
            raise AssertionError("network guard did not run")

        with patch.object(bench.XUIClient, "get_client", unexpected_read):
            with self.assertRaisesRegex(RuntimeError, "network forbidden"):
                await bench.measure(bench.Case("get", 1, 1, 1, 0))
        self.assertFalse(tracemalloc.is_tracing())

    async def test_transport_denies_mutations_foreign_url_identity_auth_tls(self):
        transport = bench.OfflineTransport(bench.Case("get", 1, 1, 1, 0))
        url = next(iter(transport.bodies))
        headers = {"Authorization": "Bearer " + bench.TOKEN, "Accept": "application/json"}
        cases = [("POST", url, headers, None),
                 ("GET", "https://other.example.invalid/panel/api/clients/list", headers, None),
                 ("GET", bench.BASE + "/panel/api/clients/get/unknown", headers, None),
                 ("GET", url, {**headers, "Authorization": "Bearer foreign"}, None),
                 ("GET", url, headers, False)]
        async with transport.session(timeout=aiohttp.ClientTimeout(total=20)) as session:
            for method, target, auth, tls in cases:
                with self.subTest(method=method, target=target, tls=tls):
                    with self.assertRaises(ValueError):
                        session.request(method, target, headers=auth, ssl=tls)
        self.assertEqual(transport.calls, {})
        self.assertEqual(transport.sessions, transport.closed_sessions)
        with self.assertRaises(ValueError):
            transport.session(timeout=aiohttp.ClientTimeout(total=21))


class BaselineCLITests(unittest.TestCase):
    def test_limits_reject_invalid_or_unbounded_cases(self):
        for case in [bench.Case("mutation"), bench.Case("get", clients=0),
                     bench.Case("get", clients=10001), bench.Case("get", requests=257),
                     bench.Case("get", requests=1, concurrency=2),
                     bench.Case("get", concurrency=33), bench.Case("get", delay_ms=21),
                     bench.Case("get", delay_ms=-1), bench.Case("get", clients=True),
                     bench.Case("get", requests=3.5),
                     bench.Case("list", clients=10000, requests=33)]:
            with self.subTest(case=case):
                with self.assertRaises(ValueError):
                    case.validate()

    def test_invalid_cli_never_starts_worker_or_accepts_live_mode(self):
        options = [["--clients", "1", "1"], ["--clients", "1", "2", "3", "4"],
                   ["--scenario", "get", "get"], ["--worker"],
                   ["--url", "https://panel.example.invalid"], ["--token", "synthetic"],
                   ["--requests", "0"], ["--scenario", "delete"]]
        with patch.object(bench.subprocess, "run") as run:
            for argv in options:
                with self.subTest(argv=argv), redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as error:
                        bench.main(argv)
                    self.assertEqual(error.exception.code, 2)
            run.assert_not_called()

    def test_worker_failure_emits_no_partial_report(self):
        failure = subprocess.CompletedProcess([], 1, stdout="", stderr="offline error")
        output = io.StringIO()
        with patch.object(bench.subprocess, "run", return_value=failure), redirect_stdout(output):
            with self.assertRaisesRegex(RuntimeError, "no complete report"):
                bench.main(["--scenario", "get", "--clients", "1", "--requests", "1", "--concurrency", "1"])
        self.assertEqual(output.getvalue(), "")

    def test_cli_without_application_environment_has_complete_bounded_report(self):
        reply = subprocess.run([sys.executable, str(SCRIPT), "--clients", "1", "3",
                                "--scenario", "get", "traffic_same", "--requests", "2",
                                "--concurrency", "2", "--delay-ms", "0"],
                               cwd=ROOT, env={"PATH": os.defpath},
                               capture_output=True, text=True, timeout=30, check=True)
        report = json.loads(reply.stdout)
        self.assertEqual(report["schema"], 1)
        self.assertEqual(report["scope"], "offline_fake_transport_bot_json_only")
        self.assertEqual(len(report["cases"]), 4)
        self.assertEqual(report["limits"]["production_capacity"], "not_measured")
        self.assertEqual(report["limits"]["runtime_admission_queue"], "not_instrumented")
        self.assertEqual(len(report["provenance"]["git_head"]), 40)
        self.assertEqual(set(report["provenance"]["file_sha256"]),
                         {"xui.py", "customer_provider_xui.py", "customer_service.py",
                          "scripts/benchmark-panel-reads.py"})
        for result in report["cases"]:
            self.assertEqual(result["calls"], 4 if result["scenario"] == "traffic_same" else 2)
            self.assertEqual(result["sessions"], result["closed_sessions"])


if __name__ == "__main__":
    unittest.main()
