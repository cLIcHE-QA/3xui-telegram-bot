from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import aiohttp
import ssl

class XUIError(RuntimeError):
    pass

@dataclass
class Inbound:
    id: int
    remark: str
    protocol: str
    enable: bool

class XUIClient:
    def __init__(self, base_url: str, token: str, verify_tls: bool = True):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.verify_tls = verify_tls

    def _ssl(self):
        return None if self.verify_tls else False

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"
        headers["Accept"] = "application/json"
        if "json" in kwargs:
            headers["Content-Type"] = "application/json"

        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                ssl=self._ssl(),
                **kwargs,
            ) as resp:
                text = await resp.text()
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    raise XUIError(f"3x-ui returned HTTP {resp.status}: {text[:500]}")
                if resp.status >= 400:
                    raise XUIError(f"3x-ui HTTP {resp.status}: {data}")
                if data.get("success") is False:
                    raise XUIError(data.get("msg") or str(data))
                return data

    async def list_inbounds(self) -> list[Inbound]:
        data = await self._request("GET", "/panel/api/inbounds/list")
        result = []
        for item in data.get("obj") or []:
            result.append(Inbound(
                id=int(item["id"]),
                remark=str(item.get("remark") or f"Inbound {item['id']}"),
                protocol=str(item.get("protocol") or "").lower(),
                enable=bool(item.get("enable", True)),
            ))
        return result

    async def get_client_by_tg_id(self, telegram_id: int) -> list[dict[str, Any]]:
        data = await self._request(
            "GET",
            f"/panel/api/clients/get/tgId/{telegram_id}",
        )
        return data.get("obj") or []

    async def create_client(
        self,
        *,
        email: str,
        telegram_id: int,
        sub_id: str,
        inbound_ids: list[int],
        total_bytes: int,
        expiry_time_ms: int,
        limit_ip: int,
        comment: str,
    ) -> dict[str, Any]:
        payload = {
            "client": {
                "email": email,
                "tgId": telegram_id,
                "subId": sub_id,
                "totalGB": total_bytes,
                "expiryTime": expiry_time_ms,
                "limitIp": limit_ip,
                "enable": True,
                "comment": comment,
                "reset": 0,
            },
            "inboundIds": inbound_ids,
        }
        return await self._request(
            "POST",
            "/panel/api/clients/add",
            json=payload,
        )

    async def delete_client(self, email: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/panel/api/clients/del/{email}",
        )

    async def sub_links(self, sub_id: str) -> list[str]:
        data = await self._request(
            "GET",
            f"/panel/api/clients/subLinks/{sub_id}",
        )
        return data.get("obj") or []
