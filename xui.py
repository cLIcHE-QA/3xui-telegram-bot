from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote
import re
import aiohttp

class XUIError(RuntimeError):
    pass

@dataclass
class InboundOption:
    id: int
    remark: str
    tag: str
    protocol: str
    port: int
    enable: bool


@dataclass
class NodeInfo:
    id: int
    name: str
    address: str
    port: int
    base_path: str
    scheme: str
    enable: bool
    status: str
    cpu_pct: float
    mem_pct: float
    uptime_secs: int
    latency_ms: int
    inbound_count: int
    client_count: int
    active_count: int
    online_count: int
    depleted_count: int
    disabled_count: int
    panel_version: str
    xray_state: str
    xray_version: str
    xray_error: str
    last_heartbeat: int
    last_error: str
    config_dirty: bool
    transitive: bool
    has_api_token: bool

class XUIClient:
    def __init__(self, base_url: str, token: str, verify_tls: bool = True):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.verify_tls = verify_tls

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"
        headers["Accept"] = "application/json"
        if "json" in kwargs:
            headers["Content-Type"] = "application/json"

        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method, f"{self.base_url}{path}",
                headers=headers,
                ssl=None if self.verify_tls else False,
                **kwargs
            ) as resp:
                text = await resp.text()
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    raise XUIError(f"3x-ui returned HTTP {resp.status}: {text[:500]}")
                if resp.status >= 400:
                    raise XUIError(f"3x-ui HTTP {resp.status}: {data}")
                if isinstance(data, dict) and data.get("success") is False:
                    raise XUIError(data.get("msg") or str(data))
                return data

    async def server_status(self) -> dict[str, Any]:
        data = await self._request("GET", "/panel/api/server/status")
        return data.get("obj") or {}

    async def nodes_list(self) -> list[NodeInfo]:
        data = await self._request("GET", "/panel/api/nodes/list")
        return [self._parse_node(x) for x in (data.get("obj") or [])]

    async def node_get(self, node_id: int) -> NodeInfo:
        data = await self._request("GET", f"/panel/api/nodes/get/{int(node_id)}")
        obj = data.get("obj") or {}
        if not obj:
            raise XUIError(f"Node not found: {node_id}")
        return self._parse_node(obj)

    async def node_probe(self, node_id: int) -> NodeInfo | None:
        data = await self._request("POST", f"/panel/api/nodes/probe/{int(node_id)}")
        obj = data.get("obj") or {}
        if isinstance(obj, dict) and obj:
            return self._parse_node(obj)
        return None

    async def node_test(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = await self._request("POST", "/panel/api/nodes/test", json=payload)
        obj = data.get("obj") or {}
        return obj if isinstance(obj, dict) else {}

    async def node_add(self, payload: dict[str, Any]) -> NodeInfo:
        data = await self._request("POST", "/panel/api/nodes/add", json=payload)
        obj = data.get("obj") or {}
        if not isinstance(obj, dict) or not obj:
            raise XUIError("3x-ui did not return the created node")
        return self._parse_node(obj)

    @staticmethod
    def _parse_node(item: dict[str, Any]) -> NodeInfo:
        return NodeInfo(
            id=int(item.get("id") or 0),
            name=str(item.get("name") or item.get("remark") or "Node"),
            address=str(item.get("address") or ""),
            port=int(item.get("port") or 0),
            base_path=str(item.get("basePath") or "/"),
            scheme=str(item.get("scheme") or "https"),
            enable=bool(item.get("enable", True)),
            status=str(item.get("status") or "unknown").lower(),
            cpu_pct=float(item.get("cpuPct") or 0),
            mem_pct=float(item.get("memPct") or 0),
            uptime_secs=int(item.get("uptimeSecs") or 0),
            latency_ms=int(item.get("latencyMs") or 0),
            inbound_count=int(item.get("inboundCount") or 0),
            client_count=int(item.get("clientCount") or 0),
            active_count=int(item.get("activeCount") or 0),
            online_count=int(item.get("onlineCount") or 0),
            depleted_count=int(item.get("depletedCount") or 0),
            disabled_count=int(item.get("disabledCount") or 0),
            panel_version=str(item.get("panelVersion") or ""),
            xray_state=str(item.get("xrayState") or "unknown").lower(),
            xray_version=str(item.get("xrayVersion") or ""),
            xray_error=str(item.get("xrayError") or ""),
            last_heartbeat=int(item.get("lastHeartbeat") or 0),
            last_error=str(item.get("lastError") or ""),
            config_dirty=bool(item.get("configDirty", False)),
            transitive=bool(item.get("transitive", False)),
            has_api_token=bool(item.get("hasApiToken", False)),
        )

    async def download_database(self) -> tuple[bytes, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/octet-stream",
        }
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                f"{self.base_url}/panel/api/server/getDb",
                headers=headers,
                ssl=None if self.verify_tls else False,
                allow_redirects=True,
            ) as resp:
                body = await resp.read()
                if resp.status >= 400:
                    detail = body[:500].decode("utf-8", errors="replace")
                    raise XUIError(f"3x-ui DB backup HTTP {resp.status}: {detail}")
                disposition = resp.headers.get("Content-Disposition", "")
                match = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';]+)', disposition, re.I)
                filename = Path(match.group(1)).name if match else "x-ui.db"
                if not filename or filename in {".", ".."}:
                    filename = "x-ui.db"
                return body, filename

    async def inbound_options(self) -> list[InboundOption]:
        try:
            data = await self._request("GET", "/panel/api/inbounds/options")
            obj = data.get("obj") or []
            if obj:
                return [self._parse_option(x) for x in obj]
        except XUIError:
            pass
        data = await self._request("GET", "/panel/api/inbounds/list")
        return [self._parse_option(x) for x in (data.get("obj") or [])]

    @staticmethod
    def _parse_option(item: dict[str, Any]) -> InboundOption:
        return InboundOption(
            id=int(item["id"]),
            remark=str(item.get("remark") or f"Inbound {item['id']}"),
            tag=str(item.get("tag") or ""),
            protocol=str(item.get("protocol") or "").lower(),
            port=int(item.get("port") or 0),
            enable=bool(item.get("enable", True)),
        )

    async def get_client_by_tg_id(self, telegram_id: int) -> list[dict[str, Any]]:
        data = await self._request("GET", f"/panel/api/clients/get/tgId/{telegram_id}")
        return data.get("obj") or []

    async def get_client(self, email: str) -> dict[str, Any]:
        data = await self._request("GET", f"/panel/api/clients/get/{quote(email, safe='')}")
        obj = data.get("obj")
        if not obj:
            raise XUIError(f"Client not found: {email}")
        return obj

    async def create_client(self, **kwargs) -> dict[str, Any]:
        payload = {
            "client": {
                "email": kwargs["email"],
                "tgId": kwargs["telegram_id"],
                "subId": kwargs["sub_id"],
                "totalGB": kwargs["total_bytes"],
                "expiryTime": kwargs["expiry_time_ms"],
                "limitIp": kwargs["limit_ip"],
                "enable": True,
                "comment": kwargs["comment"],
                "flow": kwargs.get("flow", ""),
                "reset": 0,
            },
            "inboundIds": kwargs["inbound_ids"],
        }
        return await self._request("POST", "/panel/api/clients/add", json=payload)

    @staticmethod
    def _full_update_payload(client: dict[str, Any], **changes) -> dict[str, Any]:
        # 3x-ui update replaces the row; preserve all commonly used fields.
        payload = {
            "email": client.get("email", ""),
            "subId": client.get("subId", ""),
            "id": client.get("uuid") or client.get("id") or "",
            "password": client.get("password") or "",
            "auth": client.get("auth") or "",
            "flow": client.get("flow") or "",
            "security": client.get("security") or "auto",
            "totalGB": int(client.get("totalGB") or 0),
            "expiryTime": int(client.get("expiryTime") or 0),
            "limitIp": int(client.get("limitIp") or 0),
            "limitHwid": int(client.get("limitHwid") or 0),
            "tgId": int(client.get("tgId") or 0),
            "reset": int(client.get("reset") or 0),
            "resetDay": int(client.get("resetDay") or 0),
            "resetMax": int(client.get("resetMax") or 0),
            "trafficReset": client.get("trafficReset") or "never",
            "trafficResetDay": int(client.get("trafficResetDay") or 1),
            "group": client.get("group") or "",
            "comment": client.get("comment") or "",
            "enable": bool(client.get("enable", True)),
        }
        if isinstance(client.get("reverse"), dict) and client["reverse"].get("tag"):
            payload["reverse"] = {"tag": client["reverse"]["tag"]}
        payload.update(changes)
        return payload

    async def update_client(self, email: str, **changes) -> dict[str, Any]:
        obj = await self.get_client(email)
        client = obj.get("client", obj)
        payload = self._full_update_payload(client, **changes)
        return await self._request(
            "POST", f"/panel/api/clients/update/{quote(email, safe='')}", json=payload
        )

    async def attach_client(self, email: str, inbound_ids: list[int]) -> dict[str, Any]:
        if not inbound_ids:
            return {"success": True, "obj": {"attached": [], "skipped": []}}
        return await self._request(
            "POST",
            f"/panel/api/clients/{quote(email, safe='')}/attach",
            json={"inboundIds": inbound_ids},
        )

    async def bulk_attach_clients(self, emails: list[str], inbound_ids: list[int]) -> dict[str, Any]:
        if not emails or not inbound_ids:
            return {"success": True, "obj": {"attached": {}, "skipped": {}, "errors": {}}}
        return await self._request(
            "POST",
            "/panel/api/clients/bulkAttach",
            json={"emails": emails, "inboundIds": inbound_ids},
        )

    async def bulk_adjust_clients(
        self,
        emails: list[str],
        *,
        add_days: int = 0,
        add_bytes: int = 0,
        flow: str = "",
    ) -> dict[str, Any]:
        if not emails:
            return {"success": True, "obj": {"adjusted": 0, "skipped": {}}}
        payload: dict[str, Any] = {
            "emails": emails,
            "addDays": add_days,
            "addBytes": add_bytes,
        }
        if flow:
            payload["flow"] = flow
        return await self._request(
            "POST",
            "/panel/api/clients/bulkAdjust",
            json=payload,
        )

    async def delete_client(self, email: str) -> dict[str, Any]:
        return await self._request("POST", f"/panel/api/clients/del/{quote(email, safe='')}")

    async def sub_links(self, sub_id: str) -> list[str]:
        data = await self._request("GET", f"/panel/api/clients/subLinks/{quote(sub_id, safe='')}")
        return data.get("obj") or []

    async def traffic(self, email: str) -> dict[str, Any]:
        data = await self._request("GET", f"/panel/api/clients/traffic/{quote(email, safe='')}")
        return data.get("obj") or {}
