"""Version-management additions to XUIClient, isolated from legacy requests.

Contracts checked against MHSanaei/3x-ui commit
95f19b192f477b59cc368dcb7751bcf2e0180e5b (see docs/VERSIONS_UPDATES.md).
No mutation is retried, including on a timeout or a lost HTTP response.
"""
from __future__ import annotations

import json
import re
from typing import Any

import aiohttp

_TAG = re.compile(r"v?\d+(?:\.\d+){1,3}(?:-[A-Za-z0-9][A-Za-z0-9.-]*)?", re.ASCII)


class VersionAPIError(RuntimeError):
    def __init__(self, message: str, *, uncertain: bool = False, status: int = 0):
        super().__init__(message)
        self.uncertain = uncertain
        self.status = status


def valid_version(value: object) -> bool:
    # The bound also keeps Telegram callback_data below 64 UTF-8 bytes.
    return isinstance(value, str) and len(value) <= 24 and bool(_TAG.fullmatch(value))


def same_version(left: str, right: str) -> bool:
    return bool(left and right) and left.removeprefix("v") == right.removeprefix("v")


def version_order(value: str) -> tuple[int, ...]:
    if not valid_version(value) or "-" in value:
        return ()
    return tuple(int(part) for part in value.removeprefix("v").split("."))


class VersionAPIMixin:
    """Mixed into the existing client; uses its URL, token and TLS policy."""

    base_url: str
    token: str
    verify_tls: bool

    async def _version_request(
        self, method: str, path: str, *, timeout: float = 20,
        form: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        operation = path.rsplit("/", 1)[-1]
        mutation = method != "GET"
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as session:
                async with session.request(
                    method, self.base_url + path,
                    headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"},
                    data=form, ssl=None if self.verify_tls else False,
                    allow_redirects=False,
                ) as response:
                    if response.status >= 500:
                        raise VersionAPIError(
                            f"3x-ui {operation}: HTTP {response.status}; inspect panel logs.",
                            uncertain=mutation, status=response.status,
                        )
                    if response.status != 200:
                        raise VersionAPIError(
                            f"3x-ui {operation}: HTTP {response.status}; check API access.",
                            status=response.status,
                        )
                    # Do not reflect server bodies, URLs or credentials into Telegram/audit.
                    raw = await response.read()
                    if len(raw) > 2 * 1024 * 1024:
                        raise VersionAPIError("Oversized API response.", uncertain=mutation)
                    try:
                        payload = json.loads(raw)
                    except (ValueError, UnicodeError) as exc:
                        raise VersionAPIError("Invalid API response.", uncertain=mutation) from exc
                    if not isinstance(payload, dict) or payload.get("success") is not True:
                        rejected = isinstance(payload, dict) and payload.get("success") is False
                        raise VersionAPIError(
                            f"3x-ui {operation}: operation rejected; inspect panel logs."
                            if rejected else "API did not confirm the operation.",
                            uncertain=mutation and not rejected,
                        )
                    return payload
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise VersionAPIError(
                f"3x-ui {operation}: connection unavailable ({type(exc).__name__}).",
                uncertain=mutation,
            ) from exc

    async def get_panel_update_info(self) -> dict[str, Any]:
        data = await self._version_request("GET", "/panel/api/server/getPanelUpdateInfo")
        obj = data.get("obj")
        if not isinstance(obj, dict):
            raise VersionAPIError("Invalid panel update information.")
        return obj

    async def get_xray_versions(self) -> list[str]:
        data = await self._version_request("GET", "/panel/api/server/getXrayVersion")
        obj = data.get("obj")
        if not isinstance(obj, list):
            raise VersionAPIError("Invalid Xray versions response.")
        versions = list(dict.fromkeys(item for item in obj if valid_version(item)))
        if not versions:
            raise VersionAPIError("No supported Xray version tags were returned.")
        return versions

    async def version_status(self) -> dict[str, Any]:
        data = await self._version_request("GET", "/panel/api/server/status")
        obj = data.get("obj")
        if not isinstance(obj, dict):
            raise VersionAPIError("Invalid server status.")
        return obj

    async def install_xray(self, version: str) -> dict[str, Any]:
        if not valid_version(version):
            raise ValueError("A specific safe Xray version tag is required; 'latest' is not allowed.")
        return await self._version_request(
            "POST", f"/panel/api/server/installXray/{version}", timeout=180,
        )

    async def update_panel(self) -> dict[str, Any]:
        # Must be form data. Omitting dev follows the panel's own (possibly dev) channel.
        return await self._version_request(
            "POST", "/panel/api/server/updatePanel", timeout=90, form={"dev": "false"},
        )

    async def get_update_status(self) -> dict[str, Any]:
        data = await self._version_request("GET", "/panel/api/server/getUpdateStatus")
        obj = data.get("obj")
        if not isinstance(obj, dict):
            raise VersionAPIError("Invalid updater status.")
        return obj


async def latest_stable_panel(info: dict[str, Any]) -> str:
    """Use panel metadata on stable; never mistake a dev-channel tag for stable."""
    value = info.get("latestVersion")
    if info.get("channel", "stable") == "stable" and valid_version(value) and "-" not in value:
        return value
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(
                "https://api.github.com/repos/MHSanaei/3x-ui/releases/latest",
                headers={"Accept": "application/vnd.github+json", "User-Agent": "3xui-telegram-bot"},
                allow_redirects=False,
            ) as response:
                if response.status != 200:
                    raise VersionAPIError("Stable release lookup unavailable; update blocked.")
                release = await response.json()
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        raise VersionAPIError("Stable release lookup unavailable; update blocked.") from exc
    value = release.get("tag_name") if isinstance(release, dict) else None
    if (not valid_version(value) or "-" in value or release.get("prerelease") or release.get("draft")):
        raise VersionAPIError("No verified stable panel release; update blocked.")
    return value
