"""Read-only, source-separated Reality Flow evidence for the admin user card.

Never substitute Master state for direct-node evidence. Only explicit stable
node_id bindings from existing node backup targets are eligible for a direct GET.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from xui import XUIClient, XUIError

MAX_NODE_CHECKS = 8
MAX_INBOUND_CHECKS = 32


@dataclass(frozen=True)
class FlowObservation:
    node_id: int
    inbound_tag: str
    master_flow: str
    node_flow: str | None
    state: str  # MATCH / MISMATCH / UNKNOWN
    reason: str = ""


def _settings_object(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            result = json.loads(value)
        except (ValueError, TypeError):
            return None
        return result if isinstance(result, dict) else None
    return None


def _reality_inbound(obj: dict[str, Any]) -> bool:
    if str(obj.get("protocol") or "").lower() != "vless":
        return False
    stream = _settings_object(obj.get("streamSettings"))
    if stream is None:
        return False
    return str(stream.get("security") or "").lower() == "reality" and str(
        stream.get("network") or "tcp"
    ).lower() == "tcp"


def _inbound_client_flow(inbound: dict[str, Any], email: str) -> tuple[bool, str | None]:
    settings = _settings_object(inbound.get("settings"))
    if settings is None or not isinstance(settings.get("clients"), list):
        return False, None
    for item in settings["clients"]:
        if isinstance(item, dict) and item.get("email") == email:
            value = item.get("flow")
            return True, value if isinstance(value, str) else None
    return False, None


def _node_tag_matches(inbounds: list[dict[str, Any]], node_id: int, master_tag: str) -> list[dict[str, Any]]:
    """Match one node-scoped tag or pinned v3.10.0 n<id>- alias, never fuzzy.

    Both aliases present (including exact plus alternate) are ambiguous.
    A non-positive node identity cannot authorize an alias.
    """
    if not isinstance(node_id, int) or isinstance(node_id, bool) or node_id <= 0:
        return []
    if not isinstance(master_tag, str) or not master_tag:
        return []
    prefix = f"n{node_id}-"
    alias = master_tag[len(prefix):] if master_tag.startswith(prefix) else prefix + master_tag
    tags = {master_tag}
    if alias and alias != master_tag:
        tags.add(alias)
    return [ib for ib in inbounds if isinstance(ib, dict) and ib.get("tag") in tags]


def _exact_target(targets: tuple, node_id: int):
    matches = [t for t in targets if getattr(t, "node_id", None) == node_id]
    return matches[0] if len(matches) == 1 else None


async def inspect_node_flow(
    master: XUIClient,
    targets: tuple,
    email: str,
    inbound_ids: list[int],
) -> tuple[list[FlowObservation], int]:
    """Return per-Reality-inbound independent direct GET observations.

    No write methods; no retry. Bounded work, exact tag mapping, no unsafe
    fallback from absent Node configuration to Master or name matching.
    """
    ids = sorted({i for i in inbound_ids if isinstance(i, int) and i > 0})
    omitted = max(0, len(ids) - MAX_INBOUND_CHECKS)
    ids = ids[:MAX_INBOUND_CHECKS]
    reality = []
    for inbound_id in ids:
        try:
            ib = await asyncio.wait_for(master.inbound_get(inbound_id), timeout=9)
        except (XUIError, asyncio.TimeoutError, ValueError, TypeError):
            # Cannot safely determine that this inbound is Reality; do not
            # report a checked node or a false MATCH.
            omitted += 1
            continue
        if not isinstance(ib, dict) or not _reality_inbound(ib):
            continue
        node_id = ib.get("nodeId")
        try:
            node_id = int(node_id) if node_id not in (None, "", 0, "0") else None
        except (TypeError, ValueError):
            node_id = None
        if not node_id or node_id <= 0:
            continue  # Local Master Reality inbound, not a direct node.
        tag = ib.get("tag")
        if not isinstance(tag, str) or not tag:
            omitted += 1
            continue
        found, master_flow = _inbound_client_flow(ib, email)
        if not found or master_flow is None:
            reality.append(FlowObservation(node_id, tag, master_flow or "", None, "UNKNOWN", "Master inbound: нет клиента/Flow"))
        else:
            reality.append(FlowObservation(node_id, tag, master_flow, None, "UNKNOWN"))

    node_ids = sorted({r.node_id for r in reality})
    selected = set(node_ids[:MAX_NODE_CHECKS])
    omitted += sum(1 for x in reality if x.node_id not in selected)
    gathered: dict[int, list[dict[str, Any]] | None] = {}
    limiter = asyncio.Semaphore(3)

    async def load_node(node_id: int) -> None:
        if not any(r.node_id == node_id and not r.reason for r in reality):
            return
        target = _exact_target(targets, node_id)
        if target is None:
            return
        async with limiter:
            try:
                node = XUIClient(target.panel_url, target.api_token, target.verify_tls)
                value = await asyncio.wait_for(node.inbounds_list(), timeout=10)
                if isinstance(value, list):
                    gathered[node_id] = value
            except (XUIError, asyncio.TimeoutError, ValueError, TypeError):
                gathered[node_id] = None

    await asyncio.gather(*(load_node(node_id) for node_id in selected))
    output = []
    for r in reality:
        if r.node_id not in selected:
            continue
        if r.reason:
            output.append(r)
            continue
        if _exact_target(targets, r.node_id) is None:
            output.append(FlowObservation(r.node_id, r.inbound_tag, r.master_flow, None, "UNKNOWN", "нет точной привязки node_id"))
            continue
        if r.node_id not in gathered or gathered[r.node_id] is None:
            output.append(FlowObservation(r.node_id, r.inbound_tag, r.master_flow, None, "UNKNOWN", "Direct API недоступен"))
            continue
        matches = _node_tag_matches(gathered[r.node_id], r.node_id, r.inbound_tag)
        if len(matches) != 1:
            output.append(FlowObservation(r.node_id, r.inbound_tag, r.master_flow, None, "UNKNOWN", "Node inbound tag не найден/неоднозначен"))
            continue
        found, actual = _inbound_client_flow(matches[0], email)
        if not found or actual is None:
            output.append(FlowObservation(r.node_id, r.inbound_tag, r.master_flow, None, "UNKNOWN", "Node client/Flow отсутствует"))
            continue
        state = "MATCH" if actual == r.master_flow else "MISMATCH"
        output.append(FlowObservation(r.node_id, r.inbound_tag, r.master_flow, actual, state))
    return output, omitted
