"""Provider-neutral, display-only OS labels and conservative device icons."""
from __future__ import annotations

import re


def display_os(os_name: str, os_version: str = "") -> str:
    """Never infer a version; do not duplicate it when upstream includes it in OS."""
    os_name = os_name or ""
    os_version = os_version or ""
    if not os_name:
        return "ОС неизвестна"
    if not os_version:
        return os_name
    # A version already present in deviceOs should not be appended twice.
    if re.search(r"(?<![0-9A-Za-z])" + re.escape(os_version) + r"(?![0-9A-Za-z])", os_name, re.IGNORECASE):
        return os_name
    return f"{os_name} {os_version}"


def device_emoji(os_name: str, model: str = "") -> str:
    """Conservative visual hints only. Never used for ownership or provider writes."""
    os = (os_name or "").casefold().strip()
    name = (model or "").casefold().strip()
    # Explicit form-factor in model takes precedence when OS is generic.
    if any(word in name for word in ("desktop", "imac", "mac mini", "mac pro", "workstation", "настольн")):
        return "🖥️"
    if any(word in name for word in ("laptop", "notebook", "macbook", "thinkpad", "chromebook", "ноутбук")):
        return "💻"
    if any(word in name for word in ("iphone", "ipad", "pixel", "galaxy", "smartphone", "tablet", "phone", "телефон", "планшет")):
        return "📱"
    if any(word in os for word in ("android", "ios", "ipados", "harmonyos")):
        return "📱"
    if any(word in os for word in ("windows", "macos", "mac os", "linux", "chrome os", "chromeos")):
        return "💻"
    return "🔹"


def recognized_vpn_app(user_agent: object) -> str:
    """Recognize an explicit standalone allowlisted client token; never return raw UA."""
    if not isinstance(user_agent, str) or not 1 <= len(user_agent) <= 128:
        return ""
    if not user_agent.isascii() or any(ord(ch) < 32 or ord(ch) == 127 for ch in user_agent):
        return ""
    # Only an application identifier followed by its optional numeric version.
    match = re.fullmatch(r"(Happ|Incy)(?:/[0-9]+(?:\.[0-9]+){0,3})?", user_agent, re.IGNORECASE)
    if not match:
        return ""
    return {"happ": "Happ", "incy": "Incy"}[match.group(1).casefold()]
