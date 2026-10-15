"""Fail-closed discovery for one VLESS Reality Flow change."""
from __future__ import annotations
import asyncio
import hashlib
import json
import secrets
from dataclasses import dataclass
from typing import Any
from xui import SCOPED_FLOW_REQUIRED_CLIENT_FIELDS

FLOW_CHOICES = {"n": "", "v": "xtls-rprx-vision", "u": "xtls-rprx-vision-udp443"}
MAX_EDIT_INBOUNDS = 32
MAX_EDIT_NODES = 8
MAX_CALLBACK_ID = 2147483647
CONFIRM_TTL = 90.0

# Fixed, non-sensitive operator categories: never surface API payloads or client fields.
_PREFLIGHT_REASONS = {
    "Identity клиента не совпадает": "CLIENT_IDENTITY",
    "Telegram identity не совпадает": "CLIENT_IDENTITY",
    "Master UUID отсутствует": "CLIENT_IDENTITY",
    "Неполный общий record": "CLIENT_RECORD",
    "Общий record содержит непроверенные поля другого протокола": "CLIENT_RECORD",
    "Непроверенные reverse settings": "CLIENT_RECORD",
    "Некорректный ответ Master": "MASTER_RESPONSE",
    "Недопустимый список Inbounds": "INBOUND_MEMBERSHIP",
    "Некорректный Inbound ID": "INBOUND_MEMBERSHIP",
    "Дублированный Inbound ID": "INBOUND_MEMBERSHIP",
    "Inbound identity mismatch": "INBOUND_IDENTITY",
    "Нет проверенных настроек Inbound": "INBOUND_SETTINGS",
    "Некорректные настройки Inbound": "INBOUND_SETTINGS",
    "Список клиентов Inbound не подтверждён": "INBOUND_CLIENT",
    "Привязка клиента отсутствует или неоднозначна": "INBOUND_CLIENT",
    "Неизвестное значение Flow": "INBOUND_FLOW",
    "Inbound tag не подтверждён": "INBOUND_TAG",
    "Неоднозначный tag": "INBOUND_TAG",
    "Недопустимая identity ноды": "NODE_IDENTITY",
    "Inbound origin ноды не определён": "NODE_IDENTITY",
    "Слишком много нод": "BOUNDED_LIMIT",
}


def preflight_reason(exc: Exception) -> str:
    """Fail closed with a constant public diagnostic, never upstream details."""
    if isinstance(exc, FlowEditRejected):
        return _PREFLIGHT_REASONS.get(str(exc), "MASTER_VALIDATION")
    if isinstance(exc, asyncio.TimeoutError):
        return "UPSTREAM_TIMEOUT"
    return "MASTER_API_UNAVAILABLE"


class FlowEditRejected(ValueError):
    """Target or source evidence is unavailable or ambiguous."""

@dataclass(frozen=True)
class FlowTarget:
    node_id: int
    inbound_id: int
    inbound_tag: str
    current_flow: str

@dataclass(frozen=True)
class FlowSnapshot:
    client: dict[str, Any]
    targets: tuple[FlowTarget, ...]
    fingerprint: str

    def select(self, node_id: int, inbound_id: int) -> FlowTarget:
        found = [t for t in self.targets if (t.node_id, t.inbound_id) == (node_id, inbound_id)]
        if len(found) != 1:
            raise FlowEditRejected("Недоступный или неоднозначный Inbound")
        return found[0]

def _settings_obj(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise FlowEditRejected("Некорректные настройки Inbound") from exc
    if not isinstance(value, dict):
        raise FlowEditRejected("Нет проверенных настроек Inbound")
    return value

def _node_id(raw: Any) -> int:
    # Pinned v3.10.0 uses nodeId,omitempty: null/missing means local Master.
    # Explicit zero/empty/boolean must not be interpreted as a valid Node.
    if raw is None:
        return 0
    if isinstance(raw, bool) or not str(raw).isdigit():
        raise FlowEditRejected("Недопустимая identity ноды")
    value = int(raw)
    if not 0 < value <= MAX_CALLBACK_ID:
        raise FlowEditRejected("Недопустимая identity ноды")
    return value

def _scoped_flow(inbound: dict[str, Any], email: str) -> str:
    clients = _settings_obj(inbound.get("settings")).get("clients")
    if not isinstance(clients, list):
        raise FlowEditRejected("Список клиентов Inbound не подтверждён")
    found = [x for x in clients if isinstance(x, dict) and x.get("email") == email]
    if len(found) != 1:
        raise FlowEditRejected("Привязка клиента отсутствует или неоднозначна")
    # Upstream model.Client declares flow with omitempty: absent == none.
    flow = found[0].get("flow", "")
    if not isinstance(flow, str) or flow not in FLOW_CHOICES.values():
        raise FlowEditRejected("Неизвестное значение Flow")
    return flow

def client_fingerprint(client: dict[str, Any]) -> str:
    # Include shared Flow and all other fields: concurrent edits invalidate TTL confirmation.
    return hashlib.sha256(json.dumps(client, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()

async def discover_flow_targets(master: Any, email: str, tg_id: int) -> FlowSnapshot:
    payload = await asyncio.wait_for(master.get_client(email), timeout=12)
    if not isinstance(payload, dict):
        raise FlowEditRejected("Некорректный ответ Master")
    client = payload.get("client", payload)
    if not isinstance(client, dict) or client.get("email") != email:
        raise FlowEditRejected("Identity клиента не совпадает")
    if SCOPED_FLOW_REQUIRED_CLIENT_FIELDS.difference(client):
        raise FlowEditRejected("Неполный общий record")
    if not isinstance(client.get("uuid"), str) or not client["uuid"]:
        raise FlowEditRejected("Master UUID отсутствует")
    if any(client[k] is None for k in ("subId", "expiryTime", "totalGB", "limitIp", "limitHwid", "enable", "tgId")):
        raise FlowEditRejected("Неполный общий record")
    if any(client[k] not in ("", None, 0, "[]", []) for k in (
        "privateKey", "publicKey", "allowedIPs", "preSharedKey",
        "keepAlive", "forwardedPorts", "secret", "adTag"
    )):
        raise FlowEditRejected("Общий record содержит непроверенные поля другого протокола")
    # Pinned ClientRecord.reverse is a raw string, normally "". Never
    # coerce a non-empty reverse payload on an unrelated scoped update.
    if client["reverse"] not in ("", None):
        raise FlowEditRejected("Непроверенные reverse settings")
    try:
        valid_tg = int(client["tgId"]) == tg_id
    except (TypeError, ValueError):
        valid_tg = False
    if not valid_tg:
        raise FlowEditRejected("Telegram identity не совпадает")
    raw = payload.get("inboundIds")
    if not isinstance(raw, list) or len(raw) > MAX_EDIT_INBOUNDS:
        raise FlowEditRejected("Недопустимый список Inbounds")
    ids = []
    for value in raw:
        if isinstance(value, bool) or not str(value).isdigit() or not 0 < int(value) <= MAX_CALLBACK_ID:
            raise FlowEditRejected("Некорректный Inbound ID")
        ids.append(int(value))
    if len(ids) != len(set(ids)):
        raise FlowEditRejected("Дублированный Inbound ID")
    targets = []
    for iid in sorted(ids):
        inbound = await asyncio.wait_for(master.inbound_get(iid), timeout=9)
        if not isinstance(inbound, dict) or inbound.get("id") != iid:
            raise FlowEditRejected("Inbound identity mismatch")
        stream = _settings_obj(inbound.get("streamSettings"))
        if inbound.get("protocol") != "vless" or stream.get("security") != "reality" or stream.get("network", "tcp") != "tcp":
            continue
        # disableFlow is always an explicit boolean in pinned upstream; do
        # not offer an inbound where upstream policy suppresses client Flow.
        if inbound.get("disableFlow") is not False:
            continue
        tag = inbound.get("tag")
        if not isinstance(tag, str) or not tag:
            raise FlowEditRejected("Inbound tag не подтверждён")
        node_id = _node_id(inbound.get("nodeId"))
        # A remote origin with no stable Master nodeId is not local Master.
        if node_id == 0 and inbound.get("originNodeGuid"):
            raise FlowEditRejected("Inbound origin ноды не определён")
        targets.append(FlowTarget(node_id, iid, tag, _scoped_flow(inbound, email)))
    if len({t.node_id for t in targets}) > MAX_EDIT_NODES:
        raise FlowEditRejected("Слишком много нод")
    if len({(t.node_id, t.inbound_tag) for t in targets}) != len(targets):
        raise FlowEditRejected("Неоднозначный tag")
    return FlowSnapshot(client, tuple(sorted(targets, key=lambda t: (t.node_id, t.inbound_id))), client_fingerprint(client))

@dataclass(frozen=True)
class FlowConfirmation:
    actor: int
    tg_id: int
    nonce: str
    node_id: int
    inbound_id: int
    tag: str
    old_flow: str
    new_flow: str
    client_fingerprint: str
    issued_at: float

def pop_confirmation(challenges: dict[int, FlowConfirmation], actor: int, tg_id: int, nonce: str, *, now: float) -> FlowConfirmation | None:
    challenge = challenges.pop(actor, None)
    if not challenge or challenge.actor != actor or challenge.tg_id != tg_id or not secrets.compare_digest(challenge.nonce, nonce) or not 0 <= now - challenge.issued_at <= CONFIRM_TTL:
        return None
    return challenge

async def read_target_outcome(master: Any, targets: tuple, email: str, tg_id: int, node_id: int, inbound_id: int, expected_flow: str, *, inspect) -> tuple[str, str]:
    try:
        snap = await discover_flow_targets(master, email, tg_id)
        target = snap.select(node_id, inbound_id)
        master_result = "MATCH" if target.current_flow == expected_flow else "MISMATCH"
    except (FlowEditRejected, asyncio.TimeoutError, ValueError, TypeError, RuntimeError):
        return "UNKNOWN", "UNKNOWN"
    if node_id == 0:
        return master_result, "N/A"
    try:
        observations, omitted = await inspect(master, targets, email, [inbound_id])
        matches = [x for x in observations if x.node_id == node_id and x.inbound_tag == target.inbound_tag]
        if omitted or len(matches) != 1 or matches[0].node_flow is None:
            return master_result, "UNKNOWN"
        return master_result, "MATCH" if matches[0].node_flow == expected_flow else "MISMATCH"
    except (asyncio.TimeoutError, ValueError, TypeError, RuntimeError):
        return master_result, "UNKNOWN"
