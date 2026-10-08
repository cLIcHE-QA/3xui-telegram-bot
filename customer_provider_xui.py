from __future__ import annotations

import asyncio
import aiohttp

from customer_service import (
    CustomerDevice,
    CustomerProviderAccess,
    CustomerProviderUnavailable,
    CustomerTraffic,
)
from xui import XUIClient, XUIError


class XuiCustomerProvider:
    """3x-ui adapter behind the provider-neutral customer domain contract."""

    def __init__(self, xui: XUIClient):
        self.xui = xui

    async def access(self, email: str) -> CustomerProviderAccess:
        try:
            obj = await self.xui.get_client(email)
            client = obj.get("client", obj)
            if not isinstance(client, dict) or not isinstance(client.get("enable"), bool):
                raise CustomerProviderUnavailable("customer provider access state unavailable")
            return CustomerProviderAccess(
                enabled=client["enable"],
                expiry_time=int(client.get("expiryTime") or 0),
            )
        except (XUIError, aiohttp.ClientError, asyncio.TimeoutError, OSError, TypeError, ValueError) as exc:
            raise CustomerProviderUnavailable("customer provider unavailable") from exc

    async def traffic(self, email: str) -> CustomerTraffic:
        try:
            obj = await self.xui.get_client(email)
            client = obj.get("client", obj)
            traffic = await self.xui.traffic(email)
        except XUIError as exc:
            raise CustomerProviderUnavailable("customer provider unavailable") from exc
        return CustomerTraffic(
            up=int(traffic.get("up") or traffic.get("uplink") or 0),
            down=int(traffic.get("down") or traffic.get("downlink") or 0),
            total=int(client.get("totalGB") or 0),
        )

    async def devices(self, email: str) -> list[CustomerDevice]:
        try:
            items = await self.xui.client_hwids(email)
        except XUIError as exc:
            raise CustomerProviderUnavailable("customer provider unavailable") from exc

        result: list[CustomerDevice] = []
        for index, item in enumerate(items[:20], start=1):
            model = str(item.get("deviceModel") or "").strip()
            os_name = str(item.get("deviceOs") or "").strip()
            result.append(
                CustomerDevice(
                    title=model or os_name or f"Устройство #{index}",
                    os_name=os_name,
                    last_seen=int(item.get("lastSeen") or 0),
                )
            )
        return result
