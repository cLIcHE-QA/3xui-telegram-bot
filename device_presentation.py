"""Provider-neutral, display-only OS labels and conservative device icons."""
from __future__ import annotations

import re


def _windows_os(os_name: str, os_version: str) -> str | None:
    """Нормализовать только доказанный Windows major, не выводить его из NT 10.0."""
    if not isinstance(os_name, str) or len(os_name) > 80:
        return None
    raw = os_name.strip()
    version = (os_version or "").strip()
    # 3x-ui sometimes separates "Windows" and "10_10.0.19045" between
    # deviceOs and osVersion. The marketing major must be explicit.
    split = re.fullmatch(
        r"(10|11|8(?:[.]1)?|7)_10[.]0(?:[.]([0-9]{4,6}))?",
        version, re.IGNORECASE,
    )
    if split:
        major, build = split.groups()
        stated = re.fullmatch(r"Windows(?:[ ]+(10|11|8(?:[.]1)?|7))?", raw, re.IGNORECASE)
        if stated and (stated.group(1) is None or stated.group(1) == major):
            return f"Windows {major}" + (f" (сборка {build})" if build else "")
        return None
    match = re.fullmatch(
        r"Windows[ ]+(10|11|8(?:[.]1)?|7)(?:[_ ]10[.]0(?:[.]([0-9]{4,6}))?)?",
        raw, re.IGNORECASE
    )
    if not match:
        return None
    major, build = match.groups()
    version = (os_version or "").strip()
    # Только явно согласованный build. Несовместимый osVersion — без догадок.
    if version and not re.fullmatch(r"[0-9]{1,5}(?:[.][0-9]{1,6}){0,3}", version):
        return None
    if version:
        vm = re.fullmatch(r"10[.]0(?:[.]([0-9]{4,6}))?", version)
        if vm:
            next_build = vm.group(1)
            if build and next_build and build != next_build:
                return None
            build = build or next_build
        elif version not in ("10", "11", "8", "8.1", "7"):
            # A proven build embedded in deviceOs has precedence over an unrelated
            # osVersion field; do not duplicate or invent an additional version.
            if not build:
                return None
    return f"Windows {major}" + (f" (сборка {build})" if build else "")


def display_os(os_name: str, os_version: str = "") -> str:
    """Never infer a version; do not duplicate it when upstream includes it in OS."""
    os_name = os_name or ""
    os_version = os_version or ""
    normalized_windows = _windows_os(os_name, os_version)
    if normalized_windows is not None:
        return normalized_windows
    if not os_name:
        return "ОС неизвестна"
    if not os_version:
        return os_name
    # A version already present in deviceOs should not be appended twice.
    if re.search(r"(?<![0-9A-Za-z])" + re.escape(os_version) + r"(?![0-9A-Za-z])", os_name, re.IGNORECASE):
        return os_name
    return f"{os_name} {os_version}"


def device_emoji(os_name: str, model: str = "", source_model: object = "") -> str:
    """Conservative visual hints only. Never used for ownership or provider writes."""
    os = (os_name or "").casefold().strip()
    name = (model or "").casefold().strip()
    # A verified desktop-shaped upstream label may be hidden by model normalization.
    # Use only its type prefix, never display or persist its hostname.
    if (isinstance(source_model, str) and len(source_model) <= 80
            and re.fullmatch(r"DESKTOP-[A-Za-z0-9]{4,32}(?:[_-](?:x86_64|amd64|x64|x86))?", source_model, re.IGNORECASE)
            and re.match(r"^windows(?=$|[ _0-9.])", os)):
        return "🖥️"
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
    if not isinstance(user_agent, str) or not 1 <= len(user_agent) <= 768:
        return ""
    if not user_agent.isascii() or any(ord(ch) < 32 or ord(ch) == 127 for ch in user_agent):
        return ""

    # A syntactically valid HTTP stack is not a VPN application.
    # Reject standalone transport/browser components before universal parsing.
    excluded = {"dalvik", "okhttp", "mozilla", "curl", "cfnetwork",
                "darwin", "python-requests", "go-http-client", "java",
                "android", "ios", "ipados", "macos", "windows", "linux"}
    first_token = user_agent.split("/", 1)[0].strip()
    if first_token.casefold() in excluded:
        return ""
    # Keep a strict bounded generic parser for unknown brands; accept only
    # explicitly understood composite formats, never arbitrary trailing fields.
    version = r"[0-9]{1,15}(?:[.][0-9]{1,15}){0,3}"
    dalvik = r" Dalvik/[0-9]{1,3}(?:[.][0-9]{1,3}){1,3}(?:[+][0-9A-Za-z-]{1,20})?"
    incy = re.fullmatch(
        rf"INCY/({version})/(android|windows [0-9]{{1,2}}){dalvik}",
        user_agent, re.IGNORECASE
    )
    if incy:
        return "Incy"
    # OneXray-specific secondary marker: do not mislabel the wrapper v2rayN
    # when both versioned components and the bounded iOS app marker agree.
    if re.fullmatch(
        rf"v2rayN/({version}) OneXray/({version}) "
        r"\(net[.]yuandev[.]onexray; build:[0-9]{1,8}; ios\)",
        user_agent, re.IGNORECASE
    ):
        return "OneXray"
    # Karing can report a list of protocol engines; they are NOT app names.
    # Require an exact known grammar, no key/value secrets or URLs.
    if re.fullmatch(
        rf"Karing/({version}) platform/ios;"
        rf"mihomo/({version});clash-verge;FLClash;"
        rf"mihomo[.]party/v({version}) \(clash[.]meta\);"
        rf"ClashMeta;v2ray;sing-box {version};NekoBox/Android/{version}"
        rf"(?: \(Preferences\)| \(Prefer ClashMeta Format\);HiddifyNext)?",
        user_agent, re.IGNORECASE
    ):
        return "Karing"
    # 3x-ui may supply an exactly 160-character cut of this established UA.
    # Recognize ONLY the cut of the full, independently validated Karing
    # fixture at the fixed "(Preferences)" terminus, never arbitrary prefixes.
    karing_prefix = re.fullmatch(
        rf"Karing/({version}) platform/ios;"
        rf"mihomo/({version});clash-verge;FLClash;"
        rf"mihomo[.]party/v({version}) \(clash[.]meta\);"
        rf"ClashMeta;v2ray;sing-box {version};NekoBox/Android/{version}",
        user_agent[: -len(" (Prefe")] if user_agent.endswith(" (Prefe") else "",
        re.IGNORECASE,
    )
    if len(user_agent) == 160 and user_agent.endswith(" (Prefe") and karing_prefix:
        return "Karing"
    # Versioned forms emitted by known VPN applications, with an optional
    # pre-release marker; never accept an unknown extra token or a URL.
    compatible = re.fullmatch(
        rf"(Happ|Incy|Shadowrocket|V2Box|v2rayNG|sing-box)/v?{version}"
        rf"(?:-(?:alpha|beta|rc)[0-9]{{0,4}})?",
        user_agent, re.IGNORECASE
    )
    if compatible:
        spellings = {"happ": "Happ", "incy": "Incy", "shadowrocket": "Shadowrocket",
                     "v2box": "V2Box", "v2rayng": "v2rayNG", "sing-box": "sing-box"}
        return spellings[compatible.group(1).casefold()]
    # A limited simple app-version preface, but no arbitrary suffix.
    if re.fullmatch(rf"[A-Za-z][A-Za-z0-9.-]{{1,47}}/v{version}", user_agent):
        return first_token

    # Reject ambiguous or secret-like tails instead of sanitizing them into a
    # deceptively plausible name. Do not expose the suffix to the UI.
    first, separator, suffix = user_agent.partition("/")
    if separator:
        # Универсальный безопасный формат: приложение/платформа/версия.
        # Название не зависит от списка известных VPN-клиентов; все три
        # компонента и отсутствие произвольного хвоста обязательны.
        platform = r"(?:android|ios|ipados|macos|windows|linux)"
        suffix_pattern = (
            rf"(?:{platform}/v?{version}(?:-(?:alpha|beta|rc)[0-9]{{0,4}})?"
            r"|[0-9]{1,15}(?:\.[0-9]{1,15}){0,3}"
            r"(?:/(?:ios|ipados|macos|android|windows)(?:/[0-9]{1,15})?)?"
            r"(?: CFNetwork/[0-9.]+ Darwin/[0-9.]+(?: [A-Za-z0-9,]+)?)?"
            r"|(?:ios|ipados|macos|android|windows|linux)(?: [0-9]{1,3}(?:\.[0-9]{1,3}){0,3})?)"
        )
        if not re.fullmatch(suffix_pattern, suffix, re.IGNORECASE):
            return ""

    # The dotted version must be a separate final field, not digits belonging
    # to a brand (V2Box, v2rayNG). Never strip punctuation inside the name.
    first = re.sub(r" [vV]?[0-9]{1,15}(?:\.[0-9]{1,15}){1,3}$", "", first)
    if not 2 <= len(first) <= 48 or first.casefold() in excluded:
        return ""
    # Allow multiword brands and internal hyphens/dots, but no markup,
    # URLs, key-value delimiters, or other untrusted formatting.
    atom = r"[A-Za-z][A-Za-z0-9]*(?:[.-][A-Za-z0-9]+)*"
    if not re.fullmatch(rf"{atom}(?: {atom}){{0,3}}", first):
        return ""
    # Compatibility-only display spelling for legacy clients; this is not an
    # allowlist: all other syntactically valid names remain accepted verbatim.
    legacy_spelling = {"happ": "Happ", "incy": "Incy", "shadowrocket": "Shadowrocket"}
    return legacy_spelling.get(first.casefold(), first)
