from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
import gc
import json
import unittest
import weakref
from unittest.mock import patch

import aiohttp

import panel_read_budget as admission
from customer_provider_xui import XuiCustomerProvider
from customer_service import CustomerProviderUnavailable
from version_api import VersionAPIError
from xui import XUIClient, XUIError, XUIMutationError


async def settle(predicate):
    # Scheduling barrier, not a timing/RPS assertion.
    for _ in range(100):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError("synthetic scheduling barrier not reached")


class AdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_reserved_slots_critical_fifo_and_normal_fifo(self):
        budget = admission._Budget()
        for _ in range(6):
            await budget.acquire(critical=False)
        order = []

        async def queued(name, critical):
            await budget.acquire(critical=critical)
            order.append(name)

        normal1 = asyncio.create_task(queued("normal1", False))
        normal2 = asyncio.create_task(queued("normal2", False))
        await settle(lambda: len(budget.normal) == 2)
        for _ in range(2):
            await budget.acquire(critical=True)
        critical1 = asyncio.create_task(queued("critical1", True))
        critical2 = asyncio.create_task(queued("critical2", True))
        await settle(lambda: len(budget.critical) == 2)
        self.assertEqual((budget.active, budget.normal_active), (8, 6))
        budget.release(critical=True)
        await critical1
        self.assertEqual(order, ["critical1"])
        budget.release(critical=True)
        await critical2
        self.assertEqual(order, ["critical1", "critical2"])
        budget.release(critical=False)
        await normal1
        budget.release(critical=False)
        await normal2
        self.assertEqual(order, ["critical1", "critical2", "normal1", "normal2"])
        self.assertEqual((budget.active, budget.normal_active), (8, 6))
        for _ in range(6):
            budget.release(critical=False)
        for _ in range(2):
            budget.release(critical=True)
        self.assertEqual(budget.active, 0)

    async def test_queue_cap_critical_reservation_and_cancel_cleanup(self):
        budget = admission._Budget()
        for _ in range(6):
            await budget.acquire(critical=False)
        waiters = [asyncio.create_task(budget.acquire(critical=False)) for _ in range(32)]
        await settle(lambda: len(budget.normal) == 32)
        with self.assertRaisesRegex(admission.PanelReadUnavailable, "queue is full"):
            await budget.acquire(critical=False)
        # Queue fullness does not consume the two unoccupied critical slots.
        await budget.acquire(critical=True)
        await budget.acquire(critical=True)
        with self.assertRaises(admission.PanelReadUnavailable):
            await budget.acquire(critical=True)
        for task in waiters:
            task.cancel()
        results = await asyncio.gather(*waiters, return_exceptions=True)
        self.assertTrue(all(isinstance(x, asyncio.CancelledError) for x in results))
        self.assertEqual(len(budget.normal) + len(budget.critical), 0)
        self.assertEqual((budget.active, budget.normal_active), (8, 6))
        for _ in range(6):
            budget.release(critical=False)
        for _ in range(2):
            budget.release(critical=True)

    async def test_timeout_and_expired_grant_do_not_acquire_permit(self):
        budget = admission._Budget()
        for _ in range(6):
            await budget.acquire(critical=False)
        with patch.object(admission, "WAIT_SECONDS", 0.01):
            with self.assertRaisesRegex(admission.PanelReadUnavailable, "timed out"):
                await budget.acquire(critical=False)
        self.assertEqual((budget.active, budget.normal_active, len(budget.normal)), (6, 6, 0))
        pending = asyncio.create_task(budget.acquire(critical=False))
        await settle(lambda: len(budget.normal) == 1)
        budget.normal[0].deadline = asyncio.get_running_loop().time() - 1
        budget.release(critical=False)
        with self.assertRaises(admission.PanelReadUnavailable):
            await pending
        self.assertEqual((budget.active, budget.normal_active, len(budget.normal)), (5, 5, 0))
        for _ in range(5):
            budget.release(critical=False)

    async def test_cancellation_after_grant_returns_permit_exactly_once(self):
        budget = admission._Budget()
        for _ in range(6):
            await budget.acquire(critical=False)
        pending = asyncio.create_task(budget.acquire(critical=False))
        await settle(lambda: len(budget.normal) == 1)
        budget.release(critical=False)  # Grants before the awaiting task resumes.
        self.assertEqual(budget.active, 6)
        pending.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await pending
        self.assertEqual((budget.active, budget.normal_active), (5, 5))
        for _ in range(5):
            budget.release(critical=False)

    async def test_same_target_shared_distinct_target_isolated_and_registry_bounded(self):
        first = admission._budget_for("HTTPS://PANEL.EXAMPLE.INVALID:443/")
        self.assertIs(first, admission._budget_for("https://panel.example.invalid"))
        self.assertIs(first, admission._budget_for("https://panel.example.invalid./?synthetic=1#synthetic"))
        self.assertIs(first, admission._budget_for("https://synthetic:synthetic@panel.example.invalid"))
        self.assertIsNot(first, admission._budget_for("https://panel.example.invalid/other-base"))
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(admission.panel_read_slot("https://panel.example.invalid"))
            for n in range(63):
                await stack.enter_async_context(admission.panel_read_slot(f"https://panel-{n}.example.invalid"))
            with self.assertRaisesRegex(admission.PanelReadUnavailable, "target admission is full"):
                async with admission.panel_read_slot("https://overflow.example.invalid"):
                    self.fail("registry overflow admitted")
            self.assertEqual(admission.read_budget_snapshot()["targets"], 64)
            self.assertEqual(admission.read_budget_snapshot()["active"], 64)
            self.assertTrue(all(isinstance(value, int) for value in admission.read_budget_snapshot().values()))
        self.assertEqual(admission.read_budget_snapshot()["targets"], 0)
        async with admission.panel_read_slot("https://overflow.example.invalid"):
            self.assertEqual(admission.read_budget_snapshot()["targets"], 1)
        for value in ("", "not-a-url", "https://panel.example.invalid:bad"):
            with self.assertRaises(admission.PanelReadUnavailable):
                admission._budget_for(value)

    async def test_idle_exception_tracebacks_do_not_exhaust_target_registry(self):
        retained_errors = []
        for n in range(admission.MAX_TARGETS + 1):
            try:
                async with admission.panel_read_slot(f"https://panel-{n}.example.invalid"):
                    raise ValueError("synthetic")
            except ValueError as exc:
                retained_errors.append(exc)
        self.assertEqual(len(retained_errors), admission.MAX_TARGETS + 1)
        self.assertEqual(admission.read_budget_snapshot()["targets"], 0)

    async def test_host_canonicalization_preserves_same_target_budget(self):
        unicode_host = admission._budget_for("https://пример.example.invalid")
        self.assertIs(unicode_host, admission._budget_for("https://xn--e1afmkfd.example.invalid:443/"))
        ipv6 = admission._budget_for("https://[2001:db8:0:0:0:0:0:1]")
        self.assertIs(ipv6, admission._budget_for("https://[2001:db8::1]:443/"))

    async def test_priority_scope_is_current_task_only_and_resets(self):
        target = "https://panel.example.invalid"
        child_gate = asyncio.Event()

        async def child():
            await child_gate.wait()
            async with admission.panel_read_slot(target):
                return admission.read_budget_snapshot()

        with admission.critical_panel_reads():
            async with admission.panel_read_slot(target):
                self.assertEqual(admission.read_budget_snapshot()["normal_active"], 0)
                inside = asyncio.create_task(child())
                child_gate.set()
                snapshot = await inside
                self.assertEqual((snapshot["active"], snapshot["normal_active"]), (2, 1))
                child_gate.clear()
                late = asyncio.create_task(child())
                with admission.critical_panel_reads():
                    self.assertIs(admission._critical_task.get(), asyncio.current_task())
        child_gate.set()
        late_snapshot = await late
        self.assertEqual(late_snapshot["normal_active"], 1)
        self.assertIsNone(admission._critical_task.get())
        async with admission.panel_read_slot(target):
            self.assertEqual(admission.read_budget_snapshot()["normal_active"], 1)

    async def test_error_cancellation_and_idle_budget_lifecycle(self):
        target = "https://panel.example.invalid"
        with self.assertRaises(ValueError):
            async with admission.panel_read_slot(target):
                raise ValueError("synthetic")
        self.assertEqual(admission.read_budget_snapshot()["active"], 0)
        entered = asyncio.Event()

        async def held():
            async with admission.panel_read_slot(target):
                entered.set()
                await asyncio.Future()

        task = asyncio.create_task(held())
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        del task
        await asyncio.sleep(0)
        gc.collect()
        self.assertEqual(admission.read_budget_snapshot(), {
            "targets": 0, "active": 0, "normal_active": 0,
            "waiting_critical": 0, "waiting_normal": 0,
        })


class RegistryLoopLifetimeTests(unittest.TestCase):
    def test_registry_does_not_retain_completed_loop(self):
        async def use():
            async with admission.panel_read_slot("https://panel.example.invalid"):
                self.assertEqual(admission.read_budget_snapshot()["active"], 1)
        loop = asyncio.new_event_loop()
        reference = weakref.ref(loop)
        loop.run_until_complete(use())
        loop.close()
        del loop
        gc.collect()
        self.assertIsNone(reference())


class _Transport:
    def __init__(self):
        self.release = asyncio.Event()
        self.created = 0
        self.closed = 0
        self.requests = []
        self.fail = None

    def session(self, *, timeout):
        owner = self
        owner.created += 1

        class Session:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                owner.closed += 1

            def request(self, method, url, **kwargs):
                owner.requests.append((method, url, timeout.total, kwargs))

                class Response:
                    status = 200
                    headers = {"Content-Disposition": 'attachment; filename="synthetic.db"'}

                    async def __aenter__(self):
                        if "held" in url:
                            await owner.release.wait()
                        if owner.fail == "connect":
                            raise aiohttp.ClientConnectionError("synthetic")
                        return self

                    async def __aexit__(self, *args):
                        pass

                    async def text(self):
                        return "{}"

                    async def json(self, **unused):
                        if owner.fail == "json":
                            raise ValueError("synthetic")
                        return {"success": True, "obj": {"client": {"enable": True}, "inboundIds": []}}

                    async def read(self):
                        if url.endswith("/getDb"):
                            return b"synthetic backup"
                        return json.dumps({"success": True, "obj": {"status": "synthetic"}}).encode()

                return Response()

            def get(self, url, **kwargs):
                return self.request("GET", url, **kwargs)

        return Session()


class ReadFamilyTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_read_families_share_instances_tokens_tls_and_critical_reserve(self):
        transport = _Transport()
        client = XUIClient("https://panel.example.invalid", "synthetic-a")
        other = XUIClient("HTTPS://PANEL.EXAMPLE.INVALID:443/", "synthetic-b", False)
        with patch.object(aiohttp, "ClientSession", transport.session):
            active = [asyncio.create_task((client if n % 2 else other).get_client(f"held{n}@example.invalid")) for n in range(6)]
            await settle(lambda: len(transport.requests) == 6)
            version = asyncio.create_task(other.version_status())
            binary = asyncio.create_task(client.download_database())
            await settle(lambda: admission.read_budget_snapshot()["waiting_normal"] == 2)
            self.assertEqual(transport.created, 6)
            from provisioning import ProvisioningEngine
            engine = ProvisioningEngine(None, client, None)
            await engine._authoritative_client("critical@example.invalid")
            self.assertEqual(transport.created, 7)
            self.assertEqual(admission.read_budget_snapshot()["active"], 6)
            self.assertIsNone(admission._critical_task.get())
            transport.release.set()
            await asyncio.gather(*active)
            self.assertEqual(await version, {"status": "synthetic"})
            self.assertEqual(await binary, (b"synthetic backup", "synthetic.db"))
        self.assertEqual(transport.created, transport.closed)
        self.assertEqual(admission.read_budget_snapshot()["active"], 0)
        for _, url, timeout, kwargs in transport.requests:
            is_other = url.startswith("https://panel.example.invalid:443/") or url.startswith("HTTPS://PANEL.EXAMPLE.INVALID:443/")
            self.assertEqual(kwargs["ssl"], False if is_other else None)
            self.assertEqual(kwargs["headers"]["Authorization"], "Bearer synthetic-b" if is_other else "Bearer synthetic-a")
            self.assertEqual(timeout, 60 if url.endswith("/getDb") else 20)

    async def test_saturation_fails_before_http_but_mutation_boundary_never_waits_or_replays(self):
        transport = _Transport()
        client = XUIClient("https://panel.example.invalid", "synthetic")
        with patch.object(aiohttp, "ClientSession", transport.session):
            active = [asyncio.create_task(client.get_client(f"held{n}@example.invalid")) for n in range(6)]
            await settle(lambda: transport.created == 6)
            queued = [asyncio.create_task(client.get_client("queued@example.invalid")) for _ in range(32)]
            await settle(lambda: admission.read_budget_snapshot()["waiting_normal"] == 32)
            for call in (client.download_database, lambda: client._request("POST", "/panel/api/clients/onlines")):
                with self.assertRaises(XUIError):
                    await call()
            with self.assertRaises(VersionAPIError) as caught:
                await client.version_status()
            self.assertFalse(caught.exception.uncertain)
            with self.assertRaises(CustomerProviderUnavailable):
                await XuiCustomerProvider(client).traffic("owner@example.invalid")
            self.assertEqual(transport.created, 6)
            await client._mutation_request("/panel/api/clients/update/owner", json_payload={"enable": False})
            await client.install_xray("v1.2.3")
            mutations = transport.requests[-2:]
            self.assertEqual([r[0] for r in mutations], ["POST", "POST"])
            self.assertTrue(all(r[3]["allow_redirects"] is False for r in mutations))
            self.assertEqual(transport.created, 8)
            for task in queued + active:
                task.cancel()
            await asyncio.gather(*queued, *active, return_exceptions=True)
        self.assertEqual(transport.created, transport.closed)
        self.assertEqual(admission.read_budget_snapshot()["active"], 0)

    async def test_read_transport_and_json_errors_release_admission(self):
        for failure in ("connect", "json"):
            with self.subTest(failure=failure):
                transport = _Transport()
                transport.fail = failure
                client = XUIClient("https://panel.example.invalid", "synthetic")
                with patch.object(aiohttp, "ClientSession", transport.session):
                    with self.assertRaises((aiohttp.ClientError, XUIError)):
                        await client.get_client("owner@example.invalid")
                self.assertEqual(transport.created, 1)
                self.assertEqual(transport.closed, 1)
                self.assertEqual(admission.read_budget_snapshot()["active"], 0)


class ProvisioningPriorityTests(unittest.IsolatedAsyncioTestCase):
    async def test_initial_read_failure_prevents_all_mutations(self):
        from provisioning import ProvisioningEngine
        from tests.test_v416_provisioning import FakeProvisioningDB, FakeProvisioningXUI, settings
        xui = FakeProvisioningXUI([])
        xui.fail_for.add("one@example.test")
        engine = ProvisioningEngine(FakeProvisioningDB(), xui, settings())
        with self.assertRaises(XUIError):
            await engine.sync_user(1)
        self.assertEqual(xui.attach_calls + xui.detach_calls + xui.update_calls + xui.flow_calls, [])
        self.assertIsNone(admission._critical_task.get())

    async def test_uncertain_or_final_readback_failure_stays_unknown_without_replaying(self):
        from provisioning import ProvisioningEngine, ProvisioningUnknown
        from tests.test_v416_provisioning import FakeProvisioningDB, FakeProvisioningXUI, settings
        from xui import InboundOption
        for uncertain in (False, True):
            for error in (XUIError, aiohttp.ClientConnectionError, TimeoutError, OSError):
                with self.subTest(uncertain=uncertain, error=error):
                    xui = FakeProvisioningXUI([InboundOption(10, "synthetic", "synthetic", "vless", 10010, True)])
                    db = FakeProvisioningDB()
                    if uncertain:
                        xui.uncertain_attach_after_commit.add("one@example.test")
                    original = xui.get_client
                    priorities = []

                    async def get(email):
                        priorities.append(admission._critical_task.get() is asyncio.current_task())
                        if len(priorities) > 1:
                            raise error("synthetic read unavailable")
                        return await original(email)

                    xui.get_client = get
                    engine = ProvisioningEngine(db, xui, settings())
                    with self.assertRaisesRegex(ProvisioningUnknown, "mutation_not_retried=true"):
                        await engine.sync_user(1)
                    self.assertEqual(priorities, [True, True])
                    self.assertEqual(xui.attach_calls, [("one@example.test", [10])])
                    self.assertEqual(xui.detach_calls + xui.update_calls + xui.flow_calls, [])
                    self.assertEqual(db.expiry_updates, [])
                    self.assertIsNone(admission._critical_task.get())


if __name__ == "__main__":
    unittest.main()
