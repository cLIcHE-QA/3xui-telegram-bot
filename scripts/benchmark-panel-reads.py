#!/usr/bin/env python3
"""Полностью offline baseline разбора panel reads, без live transport/config/DB."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
import tracemalloc
from unittest.mock import patch
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import aiohttp
from customer_provider_xui import XuiCustomerProvider
from xui import XUIClient

BASE = "https://panel.example.invalid"
TOKEN = "offline-fixture-value"
SCENARIOS = ("get", "traffic", "list", "traffic_same", "traffic_unique")


@dataclass(frozen=True)
class Case:
    scenario: str
    clients: int = 1000
    requests: int = 32
    concurrency: int = 8
    delay_ms: int = 1

    def validate(self) -> None:
        if self.scenario not in SCENARIOS:
            raise ValueError("unknown offline scenario")
        for name, low, high in (("clients", 1, 10000), ("requests", 1, 256),
                                ("concurrency", 1, 32), ("delay_ms", 0, 20)):
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError("offline case outside bounded limits")
        if self.concurrency > self.requests:
            raise ValueError("concurrency exceeds request count")
        # Bound aggregate JSON decoding work as well as each fixture.
        if self.scenario == "list" and self.clients * self.requests > 320000:
            raise ValueError("offline list decoding work exceeds limit")


def email(index: int) -> str:
    return f"offline-{index:05d}@example.invalid"


def payload(value: object) -> str:
    return json.dumps({"success": True, "obj": value}, separators=(",", ":"))


class OfflineTransport:
    """Strict fixed-identity transport; every session/context must close."""

    def __init__(self, case: Case):
        case.validate()
        self.case = case
        self.calls: Counter[str] = Counter()
        self.sessions = self.closed_sessions = self.active = self.peak_active = 0
        self.response_bytes = 0
        self.bodies: dict[str, tuple[str, str]] = {}
        clients = []
        for index in range(max(case.clients, case.requests)):
            owner = email(index)
            client = {"email": owner, "enable": True, "expiryTime": 0,
                      "totalGB": 10737418240, "limitHwid": 5}
            traffic = {"up": 1048576, "down": 2097152}
            for kind, obj in (("get", {"client": client, "inboundIds": [1, 2]}),
                              ("traffic", traffic)):
                self.bodies[f"{BASE}/panel/api/clients/{kind}/{quote(owner, safe='')}"] = (
                    kind, payload(obj),
                )
            if index < case.clients:
                clients.append({**client, "traffic": traffic})
        self.bodies[BASE + "/panel/api/clients/list"] = ("list", payload(clients))

    def session(self, *, timeout: aiohttp.ClientTimeout, connector=None, connector_owner=True):
        if not isinstance(timeout, aiohttp.ClientTimeout) or timeout.total != 20:
            raise ValueError("unreviewed offline session contract")
        if connector is not None:
            if (not isinstance(connector, aiohttp.TCPConnector) or connector_owner is not False
                    or connector.closed or connector.limit != 1 or connector.limit_per_host != 1
                    or connector.use_dns_cache):
                raise ValueError("unreviewed offline scoped connector contract")
        elif connector_owner is not True:
            raise ValueError("unreviewed offline connector ownership")
        transport = self

        class Session:
            async def __aenter__(self):
                transport.sessions += 1
                return self

            async def __aexit__(self, *args):
                transport.closed_sessions += 1

            def request(self, method, url, *, headers, ssl):
                if (method != "GET" or url not in transport.bodies
                        or headers != {"Authorization": "Bearer " + TOKEN,
                                       "Accept": "application/json"} or ssl is not None):
                    raise ValueError("unreviewed offline request denied")
                kind, body = transport.bodies[url]
                return transport.response(kind, body)

        return Session()

    def response(self, kind: str, body: str):
        transport = self

        class Response:
            status = 200

            async def __aenter__(self):
                transport.calls[kind] += 1
                transport.active += 1
                transport.peak_active = max(transport.peak_active, transport.active)
                try:
                    await asyncio.sleep(transport.case.delay_ms / 1000)
                except BaseException:
                    transport.active -= 1
                    raise
                transport.response_bytes += len(body.encode("utf-8"))
                return self

            async def __aexit__(self, *args):
                transport.active -= 1

            async def text(self):
                return body

            async def json(self, *, content_type):
                if content_type is not None:
                    raise ValueError("unreviewed offline JSON contract")
                return json.loads(body)

        return Response()


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def no_network(*args, **kwargs):
    raise RuntimeError("network forbidden in offline baseline")


async def measure(case: Case) -> dict:
    case.validate()
    transport = OfflineTransport(case)  # Build/serialize fixtures outside timed phase.
    latencies: list[float] = []
    next_index = active_operations = peak_operations = 0
    pending = case.requests
    workers_count = min(case.requests, case.concurrency)

    async def worker():
        nonlocal next_index, active_operations, peak_operations, pending
        while next_index < case.requests:
            index = next_index
            next_index += 1
            pending -= 1
            active_operations += 1
            peak_operations = max(peak_operations, active_operations)
            started = time.perf_counter()
            try:
                owner = email(index if case.scenario == "traffic_unique" else 0)
                if case.scenario == "get":
                    result = await client.get_client(owner)
                    if result["client"]["email"] != owner:
                        raise ValueError("offline owner mismatch")
                elif case.scenario == "traffic":
                    result = await client.traffic(owner)
                    if result["down"] != 2097152:
                        raise ValueError("offline traffic mismatch")
                elif case.scenario == "list":
                    if len(await client.clients_list()) != case.clients:
                        raise ValueError("offline list mismatch")
                else:
                    result = await provider.traffic(owner)
                    if result.total != 10737418240 or result.up != 1048576:
                        raise ValueError("offline provider mismatch")
            finally:
                active_operations -= 1
            latencies.append((time.perf_counter() - started) * 1000)

    if tracemalloc.is_tracing():
        raise RuntimeError("isolated benchmark requires ownership of tracemalloc")
    tasks: list[asyncio.Task] = []
    with (patch("aiohttp.ClientSession", transport.session),
          patch("aiohttp.TCPConnector.connect", no_network),
          patch("socket.socket", no_network),
          patch("socket.create_connection", no_network),
          patch("socket.getaddrinfo", no_network)):
        client = XUIClient(BASE, TOKEN)
        provider = XuiCustomerProvider(client)
        tracemalloc.start()
        cpu_start, wall_start = time.process_time(), time.perf_counter()
        try:
            tasks = [asyncio.create_task(worker()) for _ in range(workers_count)]
            await asyncio.gather(*tasks)
            wall = time.perf_counter() - wall_start
            cpu = time.process_time() - cpu_start
            _, heap_peak = tracemalloc.get_traced_memory()
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            tracemalloc.stop()
    if (len(latencies) != case.requests or transport.active or pending
            or transport.closed_sessions != transport.sessions):
        raise RuntimeError("incomplete offline case")
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS gives bytes; Linux gives KiB. CLI uses a fresh process for each case.
    rss_bytes = int(rss if sys.platform == "darwin" else rss * 1024)
    calls = sum(transport.calls.values())
    return {
        "scenario": case.scenario, "fixture_clients": case.clients,
        "operations": len(latencies), "driver_concurrency": workers_count,
        "synthetic_delay_ms_per_request": case.delay_ms,
        "distinct_addressed_owners": (0 if case.scenario == "list" else
                                       case.requests if case.scenario == "traffic_unique" else 1),
        "calls_by_route": dict(transport.calls), "calls": calls,
        "sessions": transport.sessions, "closed_sessions": transport.closed_sessions,
        "response_json_bytes": transport.response_bytes,
        "fixture_json_bytes": sum(len(body.encode("utf-8")) for _, body in transport.bodies.values()),
        "peak_transport_active": transport.peak_active, "peak_driver_active": peak_operations,
        "driver_initial_backlog": max(0, case.requests - workers_count),
        "wall_seconds": wall, "cpu_seconds": cpu,
        "operation_p50_ms": percentile(latencies, .5),
        "operation_p95_ms": percentile(latencies, .95),
        "operations_per_second": len(latencies) / wall, "api_calls_per_second": calls / wall,
        "timed_python_heap_peak_bytes": heap_peak, "process_peak_rss_bytes": rss_bytes,
    }


def provenance() -> dict:
    files = ["xui.py", "customer_provider_xui.py", "customer_service.py", "panel_read_budget.py", "panel_read_scope.py",
             "scripts/benchmark-panel-reads.py"]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", *files],
                            cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return {"git_head": commit, "measured_files_dirty": bool(status.strip()),
            "file_sha256": {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in files},
            "python": platform.python_version(), "implementation": platform.python_implementation(),
            "os": platform.system(), "os_release": platform.release(),
            "architecture": platform.machine(), "logical_cpus": os.cpu_count()}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--clients", type=int, nargs="+", default=[1, 1000, 10000])
    p.add_argument("--requests", type=int, default=32)
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--delay-ms", type=int, default=1)
    p.add_argument("--scenario", choices=SCENARIOS, nargs="+", default=list(SCENARIOS))
    p.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    return p


def main(argv: list[str] | None = None) -> int:
    p = parser()
    args = p.parse_args(argv)
    if (len(args.clients) > 3 or len(args.scenario) > 5
            or len(set(args.clients)) != len(args.clients)
            or len(set(args.scenario)) != len(args.scenario)):
        p.error("offline matrix requires at most 3 unique sizes / 5 unique scenarios")
    cases = [Case(s, n, args.requests, args.concurrency, args.delay_ms)
             for n in args.clients for s in args.scenario]
    try:
        for case in cases:
            case.validate()
    except ValueError as exc:
        p.error(str(exc))
    if args.worker:
        if len(cases) != 1:
            p.error("offline worker requires exactly one case")
        result = asyncio.run(measure(cases[0]))
        print(json.dumps(result, sort_keys=True))
        return 0
    results = []
    for case in cases:
        command = [sys.executable, str(Path(__file__).resolve()), "--worker",
                   "--scenario", case.scenario, "--clients", str(case.clients),
                   "--requests", str(case.requests), "--concurrency", str(case.concurrency),
                   "--delay-ms", str(case.delay_ms)]
        reply = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60)
        if reply.returncode:
            raise RuntimeError("offline worker failed; no complete report")
        results.append(json.loads(reply.stdout))
    print(json.dumps({"schema": 1, "scope": "offline_fake_transport_bot_json_only",
                      "measured_at_utc": datetime.now(timezone.utc).isoformat(),
                      "provenance": provenance(), "cases": results,
                      "limits": {"production_capacity": "not_measured", "network_tls_xray": "not_measured",
                                 "runtime_admission_queue": "not_instrumented",
                                 "latency": "operation execution, excludes driver waiting; tracing enabled",
                                 "heap": "timed Python allocations, fixtures excluded",
                                 "rss": "fresh worker process lifetime peak, imports and fixtures included"}},
                     ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
