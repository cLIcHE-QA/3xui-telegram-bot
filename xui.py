from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote
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

    async def delete_client(self, email: str) -> dict[str, Any]:
        return await self._request("POST", f"/panel/api/clients/del/{quote(email, safe='')}")

    async def sub_links(self, sub_id: str) -> list[str]:
        data = await self._request("GET", f"/panel/api/clients/subLinks/{quote(sub_id, safe='')}")
        return data.get("obj") or []

    async def traffic(self, email: str) -> dict[str, Any]:
        data = await self._request("GET", f"/panel/api/clients/traffic/{quote(email, safe='')}")
        return data.get("obj") or {}
