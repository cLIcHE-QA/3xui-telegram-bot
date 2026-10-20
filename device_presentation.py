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


ADMIN_DEVICE_PAGE_SIZE = 8


def admin_device_page_window(total: int, page: int) -> tuple[int, int, int]:
    """Clamp a read-only admin HWID page; never truncate the full inventory."""
    total = max(0, total)
    pages = max(1, (total + ADMIN_DEVICE_PAGE_SIZE - 1) // ADMIN_DEVICE_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    return page, pages, page * ADMIN_DEVICE_PAGE_SIZE


def recognized_vpn_app(user_agent: object) -> str:
    """Return a bounded display-only name claimed by an untrusted User-Agent.

    Neither the name nor the User-Agent authenticates a VPN application.
    """
    if not isinstance(user_agent, str) or not 1 <= len(user_agent) <= 256:
        return ""
    if not user_agent.isascii() or any(ord(ch) < 32 or ord(ch) == 127 for ch in user_agent):
        return ""

    # Reject ambiguous or secret-like tails instead of sanitizing them into a
    # deceptively plausible name. Do not expose the suffix to the UI.
    first, separator, suffix = user_agent.partition("/")
    if separator:
        suffix_pattern = (
            r"(?:[0-9]{1,15}(?:\\.[0-9]{1,15}){0,3}"
            r"(?:/(?:ios|ipados|macos|android|windows)(?:/[0-9]{1,15})?)?"
            r"(?: CFNetwork/[0-9.]+ Darwin/[0-9.]+(?: [A-Za-z0-9,]+)?)?"
            r"|(?:ios|ipados|macos|android|windows|linux)(?: [0-9]{1,3}(?:\\.[0-9]{1,3}){0,3})?)"
        )
        if not re.fullmatch(suffix_pattern, suffix, re.IGNORECASE):
            return ""

    # The dotted version must be a separate final field, not digits belonging
    # to a brand (V2Box, v2rayNG). Never strip punctuation inside the name.
    first = re.sub(r" [vV]?[0-9]{1,15}(?:\\.[0-9]{1,15}){1,3}$", "", first)
    if not 2 <= len(first) <= 48:
        return ""
    # Allow multiword brands and internal hyphens/dots, but no markup,
    # URLs, key-value delimiters, or other untrusted formatting.
    atom = r"[A-Za-z][A-Za-z0-9]*(?:[.-][A-Za-z0-9]+)*"
    if not re.fullmatch(rf"{atom}(?: {atom}){{0,3}}", first):
        return ""
    return first
