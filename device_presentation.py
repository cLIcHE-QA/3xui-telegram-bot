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
    # Verified actual OS takes precedence over an iPad model running a macOS app.
    if "macos" in os or "mac os" in os:
        if any(word in name for word in ("desktop", "imac", "mac mini", "mac pro", "workstation", "настольн")):
            return "🖥️"
        return "💻"
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
    """Recognize only a known first-token app; never propagate raw provider UA."""
    if not isinstance(user_agent, str) or not 1 <= len(user_agent) <= 256:
        return ""
    if not user_agent.isascii() or any(ord(ch) < 32 or ord(ch) == 127 for ch in user_agent):
        return ""
    # The literal app identifier is before the first slash, not anywhere in UA.
    # An unknown identifier must never become a trusted display name.
    prefix = user_agent.split("/", 1)[0]
    if not re.fullmatch(r"[A-Za-z]{2,32}", prefix):
        return ""
    known = {"happ": "Happ", "incy": "Incy", "shadowrocket": "Shadowrocket"}
    app = known.get(prefix.casefold(), "")
    if not app:
        return ""
    if "/" not in user_agent:
        return app
    # Validate the suffix shape; never display or trust its contents.
    suffix = user_agent.split("/", 1)[1]
    if not re.fullmatch(
        r"[0-9]+(?:\.[0-9]+){0,3}(?:/(?:ios|ipados|macos|android|windows)(?:/[0-9]+)?)?"
        r"(?: CFNetwork/[0-9.]+ Darwin/[0-9.]+(?: [A-Za-z0-9,]+)?)?",
        suffix, re.IGNORECASE,
    ):
        return ""
    return app
