from __future__ import annotations

import asyncio
import re
import aiohttp

from customer_service import (
    CustomerDevice,
    CustomerDeviceInventory,
    CustomerProviderAccess,
    CustomerProviderUnavailable,
    CustomerTraffic,
)
from xui import XUIClient, XUIError


def _safe_device_label(raw: object) -> str:
    """Allow short model/OS labels, never opaque IDs, links or provider markup."""
    if not isinstance(raw, str):
        return ""
    value = " ".join(raw.split())
    if len(value) > 48 or not re.fullmatch(
        r"[a-zA-Zа-яА-ЯёЁ0-9 ._+()\-]{1,48}", value,
    ):
        return ""
    if re.search(r"[a-fA-F0-9]{16,}|[a-zA-Z0-9_-]{24,}", value):
        return ""
    return value


def _verified_device_id(value: object) -> int | None:
    if type(value) is int:
        result = value
    elif isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,18}", value):
        result = int(value)
    else:
        return None
    return result if 0 < result <= (2**63 - 1) else None


def _verified_timestamp(value: object) -> int:
    if type(value) is int:
        result = value
    elif isinstance(value, str) and re.fullmatch(r"[0-9]{1,15}", value):
        result = int(value)
    else:
        return 0
    return result if 0 < result <= 253402300799999 else 0


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
            raw_expiry = client.get("expiryTime")
            return CustomerProviderAccess(
                enabled=client["enable"],
                expiry_time=int(raw_expiry or 0),
                expiry_available=raw_expiry not in (None, ""),
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


    async def devices(self, email: str) -> CustomerDeviceInventory:
        """Read real HWID rows only; keep identity and quota uncertainty explicit."""
        try:
            items = await self.xui.client_hwids(email)
            if not isinstance(items, list) or len(items) > 1000:
                raise CustomerProviderUnavailable("invalid HWID inventory")
        except (XUIError, aiohttp.ClientError, asyncio.TimeoutError, OSError, TypeError, ValueError) as exc:
            raise CustomerProviderUnavailable("customer provider unavailable") from exc

        # This independent read must never invent a limit or erase a valid
        # HWID inventory when the upstream client record is unavailable.
        limit: int | None = None
        limit_state = "unknown"
        try:
            obj = await self.xui.get_client(email)
            client = obj.get("client", obj) if isinstance(obj, dict) else None
            if isinstance(client, dict) and client.get("email", email) == email:
                raw_limit = client.get("limitHwid")
                if type(raw_limit) is int or (
                    isinstance(raw_limit, str)
                    and bool(re.fullmatch(r"[0-9]{1,4}", raw_limit))
                ):
                    parsed = int(raw_limit)
                    if 0 <= parsed <= 1000:
                        limit = parsed if parsed > 0 else None
                        limit_state = "known" if parsed > 0 else "disabled"
        except (XUIError, aiohttp.ClientError, asyncio.TimeoutError, OSError, TypeError, ValueError):
            pass

        # Duplicate IDs are ambiguous even if the collision is outside the
        # visible first 100 entries. Neither can open a detail card.
        id_counts: dict[int, int] = {}
        for item in items:
            if not isinstance(item, dict):
                raise CustomerProviderUnavailable("invalid HWID inventory")
            device_id = _verified_device_id(item.get("id"))
            if device_id is not None:
                id_counts[device_id] = id_counts.get(device_id, 0) + 1

        result: list[CustomerDevice] = []
        for item in items[:100]:
            model = _safe_device_label(item.get("deviceModel"))
            os_name = _safe_device_label(item.get("deviceOs"))
            device_id = _verified_device_id(item.get("id"))
            if device_id is not None and id_counts[device_id] != 1:
                device_id = None
            result.append(CustomerDevice(
                title=model or os_name or "Устройство",
                os_name=os_name,
                last_seen=_verified_timestamp(item.get("lastSeen")),
                device_id=device_id,
            ))
        return CustomerDeviceInventory(
            devices=tuple(result),
            total=len(items),
            limit=limit,
            limit_state=limit_state,
            truncated=len(items) > 100,
        )
