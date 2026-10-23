"""#473: консервативный каталог URI импорта подписки для Client Portal.

URI содержит bearer subscription URL. Никогда не передавать его в HTTP redirect,
Telegram callback_data, текст логов или внешние QR-сервисы.
"""
from __future__ import annotations

import base64
import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import quote, urlsplit


@dataclass(frozen=True)
class ImportSpec:
    name: str
    prefix: str
    platforms: frozenset[str]
    encoding: str = "direct"
    suffix: str = ""


# Только URI импорта SUBSCRIPTION URL, не settings/route/single outbound.
# Источники: официальная документация Karing, OneXray, Throne,
# frontend/src/pages/sub/subPageModel.ts upstream MHSanaei/3x-ui для
# Happ/V2Box/Shadowrocket; Incy/v2raytun — адресная ручная проверка.
# Известная схема != подтверждение версии: docs/CLIENT_SETUP.md / Issue #473.
IMPORT_CLIENTS: dict[str, ImportSpec] = {
    "incy": ImportSpec(
        "Incy", "incy://import/",
        frozenset({"ios", "android", "windows", "macos", "linux"}),
    ),
    "v2raytun": ImportSpec(
        "v2raytun", "v2raytun://import/",
        frozenset({"ios", "android", "windows", "macos"}),
    ),
    "happ": ImportSpec(
        "Happ", "happ://add/",
        frozenset({"ios", "android"}),
    ),
    "v2box": ImportSpec(
        "V2Box", "v2box://install-sub?url=",
        frozenset({"ios", "android"}), "percent", "&name=VPN",
    ),
    "shadowrocket": ImportSpec(
        "Shadowrocket", "shadowrocket://add/sub://",
        frozenset({"ios"}), "base64", "?remark=VPN",
    ),
    "karing": ImportSpec(
        "Karing", "karing://install-config?url=",
        frozenset({"ios", "android", "windows", "macos", "linux"}),
        "percent", "&name=VPN",
    ),
    "onexray": ImportSpec(
        "OneXray", "onexray://onexray.com/sub/add?url=",
        frozenset({"ios", "android", "windows", "macos", "linux"}), "percent",
    ),
    "throne": ImportSpec(
        "Throne", "throne://addsub/",
        frozenset({"android", "windows", "macos", "linux"}), "base64",
    ),
}

# CopyTextButton: 1..256 characters, including wrapper scheme.
MAX_IMPORT_URI_LENGTH = 256
_DNS_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\Z")


def _safe_import_target(value: object) -> str | None:
    """Read-only URL validation; conservative fallback for ambiguous encodings."""
    if not isinstance(value, str) or not 1 <= len(value) <= 512:
        return None
    if any(ord(c) < 33 or ord(c) > 126 for c in value):
        return None
    # Nested URL query/fragment, percent-decoding, slash/backslash and userinfo
    # ambiguity must never be reinterpreted by a custom-scheme URL parser.
    if any(c in value for c in ("\\", "#", "%")):
        return None
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment or "@" in parsed.netloc):
            return None
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            return None
    except ValueError:
        return None

    hostname = parsed.hostname
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        # Reject local/single-label or malformed DNS names. No DNS resolution.
        labels = hostname.split(".")
        if len(labels) < 2 or not all(_DNS_LABEL.fullmatch(s) for s in labels):
            return None
        if labels[-1].isdigit() or hostname.endswith(".local"):
            return None
    else:
        if not address.is_global:
            return None
    return value


def import_uri(client: str, platform: str, subscription_url: object) -> str | None:
    """Return a documented candidate import URI, or fail closed to manual URL/QR."""
    spec = IMPORT_CLIENTS.get(client)
    if spec is None or platform not in spec.platforms:
        return None
    url = _safe_import_target(subscription_url)
    if url is None:
        return None
    # Encode *only* the already validated owner's URL, never callback input.
    # Base64 is transport encoding, NOT encryption. No provider-side fetch here.
    if spec.encoding == "direct":
        payload = url
    elif spec.encoding == "percent":
        payload = quote(url, safe="")
    elif spec.encoding == "base64":
        payload = base64.b64encode(url.encode("ascii")).decode("ascii")
    else:
        return None
    candidate = spec.prefix + payload + spec.suffix
    if len(candidate) > MAX_IMPORT_URI_LENGTH:
        return None
    return candidate
