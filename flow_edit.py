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
MAX_EDIT_INBOUNDS = 256
MAX_EDIT_NODES = 64
# Finite read bounds; the UI paginates and cannot truncate unseen targets.
MAX_PARALLEL_INBOUND_READS = 8
MAX_DISCOVERY_SECONDS = 30.0
MAX_CALLBACK_ID = 2147483647
CONFIRM_TTL = 90.0

# Fixed, non-sensitive operator categories: never surface API payloads or client fields.
_PREFLIGHT_REASONS = {
    "Identity клиента не совпадает": "CLIENT_IDENTITY",
    "Telegram identity не совпадает": "CLIENT_IDENTITY",
    "Master UUID отсутствует": "CLIENT_IDENTITY",
    "Неполный общий record": "CLIENT_RECORD_MISSING",
    "Пустое обязательное значение общего record": "CLIENT_RECORD_NULL",
    "Общий record содержит непроверенные поля другого протокола": "CLIENT_RECORD_PROTOCOL",
    "Непроверенные поля WireGuard": "CLIENT_RECORD_PROTOCOL_WG",
    "Непроверенные поля MTProto": "CLIENT_RECORD_PROTOCOL_MTPROTO",
    "Непроверенные поля нескольких протоколов": "CLIENT_RECORD_PROTOCOL_MIXED",
    "Неопределённые поля другого протокола": "CLIENT_RECORD_PROTOCOL_UNKNOWN",
    "Непроверенные reverse settings": "CLIENT_RECORD_REVERSE",
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
    wg_verified: bool = False

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

def client_fingerprint(client: dict[str, Any], *, tunnel_ips: Any = None) -> str:
    # Include the shared record AND per-tunnel peer mapping: neither an
    # attachment/address change nor a shared-record edit can reuse a nonce.
    data = {"client": client, "tunnelAllowedIPs": tunnel_ips}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()

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
        raise FlowEditRejected("Пустое обязательное значение общего record")
    # Never inspect or serialize credential values beyond bounded emptiness checks.
    # Unknown types also fail closed, without leaking raw fields into errors.
    def _populated_protocol_field(value: Any) -> bool:
        if value is None or value == "" or value == "[]" or value == [] or value == 0:
            return False
        return True

    wg_fields = ("privateKey", "publicKey", "allowedIPs", "preSharedKey", "keepAlive", "forwardedPorts")
    mtproto_fields = ("secret", "adTag")
    wg_present = any(_populated_protocol_field(client[k]) for k in wg_fields)
    mtproto_present = any(_populated_protocol_field(client[k]) for k in mtproto_fields)
    if wg_present and mtproto_present:
        raise FlowEditRejected("Непроверенные поля нескольких протоколов")
    # A populated WG record is not unsafe by itself: it may be owned by a
    # legitimate WireGuard/AmneziaWG attachment on a different node.
    # Ownership must be proven from *all* attached inbounds before any edit.
    if mtproto_present:
        raise FlowEditRejected("Непроверенные поля MTProto")
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
    # An expanded fleet must not serialize up to 256 network reads with a
    # nine-second budget per inbound. Bound both concurrency and wall time;
    # cancellation/timeout fails closed and never makes a partial target list.
    sem = asyncio.Semaphore(MAX_PARALLEL_INBOUND_READS)

    async def read_inbound(iid: int) -> dict[str, Any]:
        async with sem:
            return await asyncio.wait_for(master.inbound_get(iid), timeout=9)

    ordered_ids = sorted(ids)
    async with asyncio.timeout(MAX_DISCOVERY_SECONDS):
        inbounds = await asyncio.gather(*(read_inbound(iid) for iid in ordered_ids))

    targets = []
    verified_wg_ids = set()
    wg_addresses = payload.get("tunnelAllowedIPs") if wg_present else None
    if wg_present and not isinstance(wg_addresses, dict):
        raise FlowEditRejected("Непроверенные поля WireGuard")

    for iid, inbound in zip(ordered_ids, inbounds):
        if not isinstance(inbound, dict) or inbound.get("id") != iid:
            raise FlowEditRejected("Inbound identity mismatch")
        protocol = inbound.get("protocol")
        if protocol in ("wireguard", "amneziawg") and wg_present:
            # The upstream GET exposes the *per-inbound* tunnel address;
            # one shared allowedIPs value cannot identify multiple peers.
            clients = _settings_obj(inbound.get("settings")).get("clients")
            if not isinstance(clients, list):
                raise FlowEditRejected("Непроверенные поля WireGuard")
            linked = [c for c in clients if isinstance(c, dict) and c.get("email") == email]
            if len(linked) != 1:
                raise FlowEditRejected("Непроверенные поля WireGuard")
            ips = linked[0].get("allowedIPs")
            if not isinstance(ips, list) or not ips or any(not isinstance(v, str) or not v for v in ips):
                raise FlowEditRejected("Непроверенные поля WireGuard")
            if wg_addresses.get(str(iid)) != ",".join(ips):
                raise FlowEditRejected("Непроверенные поля WireGuard")
            verified_wg_ids.add(iid)
        if protocol != "vless":
            # Hysteria2, WG/AWG, XHTTP and any other transport must never
            # become Flow targets as a side effect of fleet enumeration.
            continue
        stream = _settings_obj(inbound.get("streamSettings"))
        if stream.get("security") != "reality" or stream.get("network", "tcp") != "tcp":
            continue
        if inbound.get("disableFlow") is not False:
            continue
        tag = inbound.get("tag")
        if not isinstance(tag, str) or not tag:
            raise FlowEditRejected("Inbound tag не подтверждён")
        node_id = _node_id(inbound.get("nodeId"))
        if node_id == 0 and inbound.get("originNodeGuid"):
            raise FlowEditRejected("Inbound origin ноды не определён")
        targets.append(FlowTarget(node_id, iid, tag, _scoped_flow(inbound, email)))

    if wg_present and (
        not verified_wg_ids
        or set(wg_addresses) != {str(iid) for iid in verified_wg_ids}
    ):
        # No proven WG owner or a stale/extra tunnel attachment: fail closed.
        raise FlowEditRejected("Непроверенные поля WireGuard")
    if wg_present:
        # Service-level Go/SQLite tests show 3.10.0 clears shared WG fields
        # even on inbound-filtered VLESS update, while 3.10.2 preserves them.
        # This is not a semver >= gate: every later upstream revision needs
        # its own proof. Unknown/absent/malformed version is a hard denial.
        try:
            status = await asyncio.wait_for(master.server_status(), timeout=5)
        except (asyncio.TimeoutError, AttributeError, RuntimeError, ValueError) as exc:
            raise FlowEditRejected("Непроверенные поля WireGuard") from exc
        if not isinstance(status, dict) or status.get("panelVersion") not in ("3.10.2", "v3.10.2"):
            raise FlowEditRejected("Непроверенные поля WireGuard")
    if len({t.node_id for t in targets}) > MAX_EDIT_NODES:
        raise FlowEditRejected("Слишком много нод")
    if len({(t.node_id, t.inbound_tag) for t in targets}) != len(targets):
        raise FlowEditRejected("Неоднозначный tag")
    return FlowSnapshot(
        client, tuple(sorted(targets, key=lambda t: (t.node_id, t.inbound_id))),
        client_fingerprint(client, tunnel_ips=wg_addresses if wg_present else None), wg_verified=wg_present and bool(verified_wg_ids)
    )

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
