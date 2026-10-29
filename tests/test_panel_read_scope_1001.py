"""Ownership, bounds and lifecycle of operation-only read connectors."""
from __future__ import annotations

import asyncio
import gc
import weakref
import unittest
from unittest.mock import patch

import panel_read_scope as scope


BINDING = ("https://panel.example.invalid", "synthetic-scope-token", True)


class Owner:
    pass


class Connector:
    instances = []
    fail_close = False

    def __init__(self, **options):
        self.options = options
        self.closed = False
        self.abort = None
        self.instances.append(self)

    async def close(self, *, abort_ssl=False):
        self.closed = True
        self.abort = abort_ssl
        if self.fail_close:
            raise OSError("synthetic private close detail")


class ScopeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        Connector.instances = []
        Connector.fail_close = False
        self.patcher = patch.object(scope.aiohttp, "TCPConnector", Connector)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.owner = Owner()

    async def asyncTearDown(self):
        self.assertEqual(scope.read_scope_snapshot(), {"active_scopes": 0})
        self.assertNotIn(asyncio.get_running_loop(), scope._counts)

    async def test_scope_is_lazy_and_clears_private_owner_task_binding(self):
        async with scope.scoped_panel_reads(self.owner):
            state = scope._scope.get()
            self.assertEqual(Connector.instances, [])
            first = scope.scoped_session_kwargs(self.owner, BINDING, "GET")
            second = scope.scoped_session_kwargs(self.owner, BINDING, "GET")
            self.assertIs(first["connector"], second["connector"])
            self.assertIs(first["connector_owner"], False)
            self.assertEqual(first["connector"].options,
                             {"limit": 1, "limit_per_host": 1, "use_dns_cache": False})
        self.assertTrue(state.closed)
        self.assertIsNone(state.owner)
        self.assertIsNone(state.task)
        self.assertIsNone(state.binding)
        self.assertIsNone(state.connector)
        self.assertTrue(Connector.instances[0].closed)
        self.assertTrue(Connector.instances[0].abort)

    async def test_outside_scope_has_original_oneshot_options(self):
        self.assertEqual(scope.scoped_session_kwargs(self.owner, BINDING, "GET"), {})
        self.assertFalse(Connector.instances)

    async def test_foreign_owner_and_mutation_never_use_scoped_connector(self):
        async with scope.scoped_panel_reads(self.owner):
            self.assertEqual(scope.scoped_session_kwargs(Owner(), BINDING, "GET"), {})
            self.assertEqual(scope.scoped_session_kwargs(self.owner, BINDING, "POST"), {})
            self.assertEqual(scope.scoped_session_kwargs(self.owner, BINDING, "DELETE"), {})
            self.assertFalse(Connector.instances)
            scope.scoped_session_kwargs(self.owner, BINDING, "GET")
            scope.scoped_session_kwargs(self.owner, BINDING, "GET")

    async def test_third_checkout_is_refused_before_allocation(self):
        async with scope.scoped_panel_reads(self.owner):
            scope.scoped_session_kwargs(self.owner, BINDING, "GET")
            scope.scoped_session_kwargs(self.owner, BINDING, "GET")
            with self.assertRaisesRegex(scope.PanelReadScopeUnavailable, "read limit"):
                scope.scoped_session_kwargs(self.owner, BINDING, "GET")
        self.assertEqual(len(Connector.instances), 1)

    async def test_binding_change_is_sanitized_for_url_token_and_tls(self):
        alternatives = [("https://other.example.invalid", BINDING[1], True),
                        (BINDING[0], "other-synthetic-token", True),
                        (BINDING[0], BINDING[1], False)]
        for binding in alternatives:
            async with scope.scoped_panel_reads(self.owner):
                scope.scoped_session_kwargs(self.owner, BINDING, "GET")
                with self.assertRaises(scope.PanelReadScopeUnavailable) as caught:
                    scope.scoped_session_kwargs(self.owner, binding, "GET")
                self.assertEqual(str(caught.exception), "panel read scope binding changed")

    async def test_child_task_does_not_inherit_transport_but_can_own_its_scope(self):
        async with scope.scoped_panel_reads(self.owner):
            parent = scope.scoped_session_kwargs(self.owner, BINDING, "GET")["connector"]

            async def child():
                self.assertEqual(scope.scoped_session_kwargs(self.owner, BINDING, "GET"), {})
                async with scope.scoped_panel_reads(self.owner):
                    own = scope.scoped_session_kwargs(self.owner, BINDING, "GET")["connector"]
                    self.assertIsNot(own, parent)
                    self.assertEqual(scope.read_scope_snapshot()["active_scopes"], 2)
                self.assertTrue(own.closed)

            await asyncio.create_task(child())
            self.assertFalse(parent.closed)
            self.assertIs(scope.scoped_session_kwargs(self.owner, BINDING, "GET")["connector"], parent)

    async def test_late_inherited_child_cannot_retain_closed_owner(self):
        release = asyncio.Event()

        async def child():
            await release.wait()
            state = scope._scope.get()
            self.assertTrue(state.closed)
            self.assertIsNone(state.owner)
            self.assertIsNone(state.task)
            self.assertIsNone(state.binding)
            self.assertEqual(scope.scoped_session_kwargs(self.owner, BINDING, "GET"), {})

        async with scope.scoped_panel_reads(self.owner):
            scope.scoped_session_kwargs(self.owner, BINDING, "GET")
            task = asyncio.create_task(child())
        release.set()
        await task

    async def test_same_task_nesting_is_refused_without_corrupting_outer(self):
        async with scope.scoped_panel_reads(self.owner):
            outer = scope.scoped_session_kwargs(self.owner, BINDING, "GET")["connector"]
            with self.assertRaisesRegex(scope.PanelReadScopeUnavailable, "nesting"):
                async with scope.scoped_panel_reads(Owner()):
                    self.fail("nested scope entered")
            self.assertEqual(scope.read_scope_snapshot()["active_scopes"], 1)
            self.assertIs(scope.scoped_session_kwargs(self.owner, BINDING, "GET")["connector"], outer)

    async def test_capacity_64_is_refused_and_cancellation_releases_all_slots(self):
        entered = 0
        ready = asyncio.Event()
        hold = asyncio.Event()

        async def operation():
            nonlocal entered
            async with scope.scoped_panel_reads(Owner()):
                entered += 1
                if entered == scope.MAX_SCOPES:
                    ready.set()
                await hold.wait()

        tasks = [asyncio.create_task(operation()) for _ in range(64)]
        try:
            await asyncio.wait_for(ready.wait(), 2)
            with self.assertRaisesRegex(scope.PanelReadScopeUnavailable, "capacity"):
                async with scope.scoped_panel_reads(self.owner):
                    self.fail("capacity exceeded")
            self.assertEqual(scope.read_scope_snapshot()["active_scopes"], 64)
            self.assertFalse(Connector.instances)
        finally:
            for task in tasks:
                task.cancel()
            results = await asyncio.gather(*tasks, return_exceptions=True)
        self.assertTrue(all(isinstance(x, asyncio.CancelledError) for x in results))

    async def test_constructor_error_has_no_private_details_or_retained_slot(self):
        with patch.object(scope.aiohttp, "TCPConnector", side_effect=RuntimeError("private detail")):
            with self.assertRaises(scope.PanelReadScopeUnavailable) as caught:
                async with scope.scoped_panel_reads(self.owner):
                    scope.scoped_session_kwargs(self.owner, BINDING, "GET")
        self.assertEqual(str(caught.exception), "panel read scope transport unavailable")
        self.assertTrue(caught.exception.__suppress_context__)

    async def test_body_error_closes_transport_and_releases_slot(self):
        with self.assertRaisesRegex(ValueError, "synthetic parse"):
            async with scope.scoped_panel_reads(self.owner):
                scope.scoped_session_kwargs(self.owner, BINDING, "GET")
                raise ValueError("synthetic parse")
        self.assertTrue(Connector.instances[0].closed)

    async def test_close_error_is_sanitized_and_releases_slot(self):
        Connector.fail_close = True
        with self.assertRaises(scope.PanelReadScopeUnavailable) as caught:
            async with scope.scoped_panel_reads(self.owner):
                scope.scoped_session_kwargs(self.owner, BINDING, "GET")
        self.assertEqual(str(caught.exception), "panel read scope cleanup unavailable")
        self.assertTrue(Connector.instances[0].closed)

    async def test_cancellation_is_not_replaced_by_cleanup_exception(self):
        Connector.fail_close = True
        with self.assertRaises(asyncio.CancelledError):
            async with scope.scoped_panel_reads(self.owner):
                scope.scoped_session_kwargs(self.owner, BINDING, "GET")
                raise asyncio.CancelledError()
        self.assertTrue(Connector.instances[0].closed)

    async def test_retained_failure_state_does_not_retain_owner(self):
        owner = Owner()
        reference = weakref.ref(owner)
        async with scope.scoped_panel_reads(owner):
            state = scope._scope.get()
            scope.scoped_session_kwargs(owner, BINDING, "GET")
        del owner
        gc.collect()
        self.assertTrue(state.closed)
        self.assertIsNone(reference())


if __name__ == "__main__":
    unittest.main()
