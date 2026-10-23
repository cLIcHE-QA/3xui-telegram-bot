"""Read-only 3x-ui subscription display title for client-specific import links.

Use the already-running loopback compatibility proxy instead of contacting an
untrusted URL or persisting bearer credentials. 3x-ui ?format=info exposes
subTitle without HWID registration / subscription-fetch mutations.
"""
from __future__ import annotations

import asyncio
import json
import re
import unicodedata

import aiohttp

_SUB_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
MAX_INFO_BYTES = 8192


def safe_import_title(value: object) -> str | None:
    """Accept bounded Unicode branding, but reject controls and bidi spoofing."""
    if not isinstance(value, str):
        return None
    title = value.strip()
    if not title or len(title) > 64:
        return None
    if any(
        unicodedata.category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"}
        for char in title
    ):
        return None
    return title


async def fetch_import_title(sub_id: object, *, proxy_port: int) -> str | None:
    """Fetch only a locally owned subscriber's upstream title, never its URL.

    Endpoint is fixed to loopback: callers must first enforce Telegram owner,
    private chat, portal pilot and rate guards. Errors fail closed to no label.
    """
    if not isinstance(sub_id, str) or not _SUB_ID.fullmatch(sub_id):
        return None
    if not isinstance(proxy_port, int) or isinstance(proxy_port, bool):
        return None
    if not 1 <= proxy_port <= 65535:
        return None
    url = f"http://127.0.0.1:{proxy_port}/compat/{sub_id}?format=info"
    try:
        timeout = aiohttp.ClientTimeout(total=2.5)
        async with aiohttp.ClientSession(timeout=timeout, trust_env=False) as session:
            async with session.get(
                url, allow_redirects=False,
                headers={"Accept": "application/json"},
            ) as response:
                if response.status != 200:
                    return None
                if "application/json" not in response.headers.get("Content-Type", "").lower():
                    return None
                body = await response.content.read(MAX_INFO_BYTES + 1)
                if len(body) > MAX_INFO_BYTES:
                    return None
                info = json.loads(body.decode("utf-8"))
                if not isinstance(info, dict):
                    return None
                return safe_import_title(info.get("subTitle"))
    except (aiohttp.ClientError, asyncio.TimeoutError, UnicodeError, ValueError):
        return None
