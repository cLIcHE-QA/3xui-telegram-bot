"""Bounded, credential-free admission for one panel in one asyncio loop.

The supported bot runtime has one event loop. These are process-local safety
caps, not a measurement of upstream capacity or a distributed rate limiter.
No sessions, tasks, network connections or application configuration are created.
"""
from __future__ import annotations

import asyncio
from collections import deque
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import ipaddress
from urllib.parse import urlsplit
from weakref import WeakKeyDictionary, WeakValueDictionary

MAX_ACTIVE = 8
MAX_NORMAL_ACTIVE = 6
MAX_WAITERS = 32
WAIT_SECONDS = 1.0
MAX_TARGETS = 64


class PanelReadUnavailable(RuntimeError):
    """Admission failed before HTTP; never carries target or caller data."""


_critical_task: ContextVar[asyncio.Task | None] = ContextVar("panel_critical_read_task", default=None)


@contextmanager
def critical_panel_reads():
    """Server-owned priority for this task only; not inherited by child tasks."""
    task = asyncio.current_task()
    if task is None:
        raise RuntimeError("critical panel reads require an asyncio task")
    token = _critical_task.set(task)
    try:
        yield
    finally:
        _critical_task.reset(token)


@dataclass
class _Waiter:
    future: asyncio.Future
    critical: bool
    deadline: float
    granted: bool = False


class _Budget:
    def __init__(self):
        self.active = 0
        self.normal_active = 0
        self.critical: deque[_Waiter] = deque()
        self.normal: deque[_Waiter] = deque()

    def _fits(self, critical: bool) -> bool:
        return self.active < MAX_ACTIVE and (critical or self.normal_active < MAX_NORMAL_ACTIVE)

    def _grant(self, critical: bool):
        self.active += 1
        if not critical:
            self.normal_active += 1

    def _drain(self):
        # At most MAX_WAITERS entries; cancelled tasks do not consume queue space.
        for queue in (self.critical, self.normal):
            live = [waiter for waiter in queue if not waiter.future.done()]
            queue.clear()
            queue.extend(live)
        now = asyncio.get_running_loop().time()
        while self.critical or self.normal:
            queue = self.critical if self.critical else self.normal
            waiter = queue[0]
            if waiter.deadline <= now:
                queue.popleft()
                waiter.future.set_exception(PanelReadUnavailable("panel read admission timed out"))
                continue
            if not self._fits(waiter.critical):
                break
            queue.popleft()
            self._grant(waiter.critical)
            waiter.granted = True
            waiter.future.set_result(None)

    async def acquire(self, *, critical: bool):
        self._drain()
        if self._fits(critical) and not self.critical and (critical or not self.normal):
            self._grant(critical)
            return
        if len(self.critical) + len(self.normal) >= MAX_WAITERS:
            raise PanelReadUnavailable("panel read admission queue is full")
        loop = asyncio.get_running_loop()
        waiter = _Waiter(loop.create_future(), critical, loop.time() + WAIT_SECONDS)
        queue = self.critical if critical else self.normal
        queue.append(waiter)
        try:
            await asyncio.wait_for(waiter.future, timeout=WAIT_SECONDS)
        except BaseException as exc:
            # A grant can race task cancellation/timeout after set_result and
            # before the awaiting task resumes. Return that permit exactly once.
            if waiter.granted:
                self.release(critical=critical)
            else:
                if waiter in queue:
                    queue.remove(waiter)
                if not waiter.future.done():
                    waiter.future.cancel()
                elif not waiter.future.cancelled():
                    waiter.future.exception()
                self._drain()
            if isinstance(exc, TimeoutError):
                raise PanelReadUnavailable("panel read admission timed out") from None
            raise

    def release(self, *, critical: bool):
        assert self.active > 0
        self.active -= 1
        if not critical:
            assert self.normal_active > 0
            self.normal_active -= 1
        self._drain()


# Neither idle budgets nor completed loops are retained. In-flight request
# frames own the budget strongly; the registry owns only weak references.
_registries: WeakKeyDictionary = WeakKeyDictionary()


def _target_key(base_url: str) -> bytes:
    try:
        parts = urlsplit(base_url)
        scheme = parts.scheme.casefold()
        port = parts.port if parts.port is not None else (443 if scheme == "https" else 80)
        host = (parts.hostname or "").casefold().rstrip(".")
        try:
            host = ipaddress.ip_address(host).compressed
        except ValueError:
            host = host.encode("idna").decode("ascii")
        target = (scheme, host, port, parts.path.rstrip("/"))
    except (TypeError, ValueError):
        raise PanelReadUnavailable("invalid panel read target") from None
    if scheme not in {"http", "https"} or not target[1]:
        raise PanelReadUnavailable("invalid panel read target")
    # Keys exclude credentials and are never emitted in diagnostics.
    return hashlib.sha256(repr(target).encode("utf-8")).digest()


def _budget_for(base_url: str) -> _Budget:
    loop = asyncio.get_running_loop()
    registry = _registries.get(loop)
    if registry is None:
        registry = WeakValueDictionary()
        _registries[loop] = registry
    key = _target_key(base_url)
    budget = registry.get(key)
    if budget is None:
        if len(registry) >= MAX_TARGETS:
            raise PanelReadUnavailable("panel read target admission is full")
        budget = _Budget()
        registry[key] = budget
    return budget


@asynccontextmanager
async def panel_read_slot(base_url: str):
    budget = _budget_for(base_url)
    owner = _critical_task.get()
    critical = owner is not None and asyncio.current_task() is owner
    acquired = False
    try:
        await budget.acquire(critical=critical)
        acquired = True
        yield
    finally:
        if acquired:
            budget.release(critical=critical)
        if budget.active == 0 and not budget.critical and not budget.normal:
            registry = _registries.get(asyncio.get_running_loop())
            key = _target_key(base_url)
            if registry is not None and registry.get(key) is budget:
                # Retire idle entries even if an exception traceback retains
                # the lease frame/budget. Such frames cannot exhaust target slots.
                registry.pop(key, None)


def read_budget_snapshot() -> dict[str, int]:
    """Process-internal aggregate counters; no URLs, identities or payloads."""
    registry = _registries.get(asyncio.get_running_loop())
    budgets = list(registry.values()) if registry is not None else []
    return {
        "targets": len(budgets),
        "active": sum(b.active for b in budgets),
        "normal_active": sum(b.normal_active for b in budgets),
        "waiting_critical": sum(len(b.critical) for b in budgets),
        "waiting_normal": sum(len(b.normal) for b in budgets),
    }
