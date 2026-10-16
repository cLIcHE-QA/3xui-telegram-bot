"""Presentation-only Flow labels and bounded, explicitly historical observations.

Never use these values as authentication, node identity, or mutation evidence.
"""
from __future__ import annotations

import re
import time
from collections import OrderedDict
from dataclasses import dataclass

FLOW_VIEW_TTL = 180
FLOW_VIEW_CAP = 128


@dataclass(frozen=True)
class LastFlowView:
    created: float
    text: str


_views: OrderedDict[int, LastFlowView] = OrderedDict()


def clean_label(value: object, fallback: str, *, limit: int = 42) -> str:
    if not isinstance(value, str):
        return fallback
    label = re.sub(r"[\\x00-\\x1f\\x7f\\u202a-\\u202e\\u2066-\\u2069]", " ", value)
    label = " ".join(label.split())
    return label[:limit] if label else fallback


def node_label(node_id: int, names: dict[int, str] | None = None) -> str:
    if node_id == 0:
        return "🖥 Master"
    name = clean_label((names or {}).get(node_id), "", limit=38)
    return f"🌐 {name} (#{node_id})" if name else f"🌐 Node #{node_id}"


def inbound_label(inbound_id: int, remark: object) -> str:
    name = clean_label(remark, "", limit=38)
    return f"{name} (#{inbound_id})" if name else f"Inbound #{inbound_id}"


async def load_node_names(master) -> dict[int, str]:
    """Best-effort presentation data only; no authority from names."""
    try:
        import asyncio
        items = await asyncio.wait_for(master.nodes_list(), timeout=5)
        names = {}
        for item in items[:64]:
            node_id = getattr(item, "id", None)
            if type(node_id) is int and node_id > 0 and node_id not in names:
                names[node_id] = getattr(item, "name", "")
        return names
    except (Exception,):
        return {}


def store_flow_view(tg_id: int, text: str, *, now: float | None = None) -> None:
    moment = time.monotonic() if now is None else now
    _views.pop(tg_id, None)
    _views[tg_id] = LastFlowView(moment, text[:300])
    while len(_views) > FLOW_VIEW_CAP:
        _views.popitem(last=False)


def last_flow_view(tg_id: int, *, now: float | None = None) -> str:
    moment = time.monotonic() if now is None else now
    item = _views.get(tg_id)
    if item is None:
        return "🌐 Flow Nodes: ⚪ не проверено"
    if moment - item.created > FLOW_VIEW_TTL or moment < item.created:
        _views.pop(tg_id, None)
        return "🌐 Flow Nodes: ⚪ не проверено"
    return "🌐 Flow Nodes (последняя проверка, не live): " + item.text
