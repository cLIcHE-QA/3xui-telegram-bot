"""Task-owned connector reuse for one two-read operation; no persistent pool.

Sessions remain per-request so cookies/default headers never cross reads.
No application configuration, tasks, timers or network activity at import.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
import weakref

import aiohttp


MAX_SCOPES = 64
MAX_READS = 2


class PanelReadScopeUnavailable(RuntimeError):
    """Definitive local refusal/cleanup failure, without private context."""


class _Scope:
    # No generated repr that could expose owner/config/credentials.
    __slots__ = ("owner", "task", "connector", "binding", "calls", "closed")

    def __init__(self, owner: object, task: asyncio.Task):
        self.owner = owner
        self.task = task
        self.connector: aiohttp.TCPConnector | None = None
        self.binding: tuple[str, str, bool] | None = None
        self.calls = 0
        self.closed = False

    def clear(self):
        self.closed = True
        self.owner = self.task = self.connector = self.binding = None
        self.calls = 0


_scope: ContextVar[_Scope | None] = ContextVar("panel_operation_read_scope", default=None)
# Values contain counts only, never loops, owners, tasks or connectors.
_counts: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


@asynccontextmanager
async def scoped_panel_reads(owner: object):
    """Own at most two same-task GET checkouts and close their connector."""
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    if task is None:
        raise PanelReadScopeUnavailable("panel read scope requires a task")
    previous = _scope.get()
    if previous is not None and not previous.closed and previous.task is task:
        raise PanelReadScopeUnavailable("panel read scope nesting denied")
    count = _counts.get(loop, 0)
    if count >= MAX_SCOPES:
        raise PanelReadScopeUnavailable("panel read scope capacity reached")
    state = _Scope(owner, task)
    _counts[loop] = count + 1
    token = _scope.set(state)
    cancelled = False
    try:
        yield
    except asyncio.CancelledError:
        cancelled = True
        raise
    finally:
        _scope.reset(token)
        connector = state.connector
        state.clear()  # Inherited child contexts cannot retain/reuse this owner.
        try:
            if connector is not None:
                try:
                    # The owned response has finished or was cancelled; no
                    # shared mutation/other operation can still use this socket.
                    await connector.close(abort_ssl=True)
                except Exception:
                    if not cancelled:
                        raise PanelReadScopeUnavailable("panel read scope cleanup unavailable") from None
        finally:
            remaining = _counts[loop] - 1
            if remaining:
                _counts[loop] = remaining
            else:
                del _counts[loop]


def scoped_session_kwargs(
    owner: object, binding: tuple[str, str, bool], method: str,
) -> dict:
    """Called after admission, using the same snapshot as URL/auth/TLS."""
    state = _scope.get()
    if (state is None or state.closed or state.owner is not owner
            or state.task is not asyncio.current_task() or method != "GET"):
        return {}
    if state.calls >= MAX_READS:
        raise PanelReadScopeUnavailable("panel read scope read limit reached")
    if state.binding is not None and state.binding != binding:
        raise PanelReadScopeUnavailable("panel read scope binding changed")
    if state.connector is None:
        try:
            connector = aiohttp.TCPConnector(limit=1, limit_per_host=1, use_dns_cache=False)
        except Exception:
            raise PanelReadScopeUnavailable("panel read scope transport unavailable") from None
        state.connector = connector
        state.binding = binding
    state.calls += 1
    return {"connector": state.connector, "connector_owner": False}


def read_scope_snapshot() -> dict[str, int]:
    """Aggregate current-loop diagnostics; no addresses, keys or identities."""
    return {"active_scopes": _counts.get(asyncio.get_running_loop(), 0)}
