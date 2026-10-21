"""Безопасные read-only названия мобильных HWID на основе исходных таблиц #830."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re

from device_presentation import display_os, recognized_vpn_app

_DATA = Path(__file__).resolve().parent / "docs" / "device-identifiers"
_APPLE_ID = re.compile(r"(?:iPhone|iPad)[0-9]{1,3},[0-9]{1,3}")
_LABEL = re.compile(r"[A-Za-zА-Яа-яЁё0-9 ,._+()\-]{1,48}")
_ANDROID_CODE = re.compile(r"[A-Za-z0-9_.+\-]{2,48}")
_UNKNOWN = frozenset(("", "unknown", "unknown device", "неизвестно", "устройство", "device", "—", "-"))


def _safe(value: object) -> str:
    if not isinstance(value, str):
        return ""
    s = " ".join(value.split())
    return s if _LABEL.fullmatch(s) and not re.search(r"[a-fA-F0-9]{16,}|[A-Za-z0-9_-]{24,}", s) else ""


def _rows(filename: str):
    # Строки Markdown не меняются; индекс — производный, только в памяти процесса.
    with (_DATA / filename).open(encoding="utf-8") as source:
        for line in source:
            if not line.startswith("| "):
                continue
            fields = [f.strip().replace("{PIPE}", "|") for f in
                      line.strip().strip("|").replace("\|", "{PIPE}").split("|")]
            if len(fields) != 4 or fields[0] in ("Категория", "Retail Branding", "Производитель", ":---"):
                continue
            if fields[0].startswith(":"):
                continue
            yield fields


@lru_cache(maxsize=1)
def _apple() -> dict[str, str]:
    by_code: dict[str, set[str]] = {}
    for category, name, codes, _ in _rows("apple_all_identifiers.md"):
        if category not in ("iPhone", "iPad") or not _safe(name):
            continue
        for code in re.findall(r"`((?:iPhone|iPad)[0-9]+,[0-9]+)`", codes):
            by_code.setdefault(code, set()).add(name)
    return {code: next(iter(names)) for code, names in by_code.items() if len(names) == 1}


@lru_cache(maxsize=1)
def _android() -> dict[str, str]:
    by_code: dict[str, set[str]] = {}
    for brand, marketing, device, model in _rows("android_all_identifiers.md"):
        code = device.strip("`")
        candidate = _safe(marketing)
        if not _ANDROID_CODE.fullmatch(code) or not candidate:
            continue
        # Не используем название, совпадающее с неопределённым служебным кодом.
        by_code.setdefault(code.casefold(), set()).add(candidate)
    return {code: next(iter(names)) for code, names in by_code.items() if len(names) == 1}


_LINUX_DISTRO = re.compile(
    r"^(?:linux|ubuntu|debian|fedora|arch(?: linux)?|linux mint|mint|"
    r"opensuse(?: tumbleweed| leap)?|suse(?: linux)?|centos|rocky(?: linux)?|"
    r"almalinux|rhel|red hat enterprise linux|manjaro|kali(?: linux)?|"
    r"pop!_os|elementary os|gentoo|nixos|raspbian|raspberry pi os)"
    r"(?=$|[\s0-9._(])", re.IGNORECASE
)
_WIN_TECHNICAL = re.compile(
    r"^(?:desktop|laptop|win|windows)[-_][A-Za-z0-9]{4,32}(?:[_-](?:x86_64|amd64|x64|x86))?$",
    re.IGNORECASE
)
_ARCH_ONLY = re.compile(r"^(?:x86_64|amd64|x64|i386|i686|aarch64|arm64)$", re.IGNORECASE)
_OS_AS_MODEL = re.compile(
    r"^(?:windows(?:\s+(?:10|11|8(?:\.1)?|7))?(?:\s+(?:x86_64|amd64|x64|x86))?|"
    r"(?:linux|ubuntu|debian|fedora|arch linux|linux mint|mint)"
    r"(?:\s+[0-9][0-9A-Za-z.\-]*)?(?:\s+(?:x86_64|amd64|x64|aarch64))?)$",
    re.IGNORECASE
)


def _desktop_fallback(raw: str, os: str) -> str | None:
    """Обобщаем только явно техническую модель при подтверждённом семействе ОС."""
    o = os.casefold().strip()
    if re.match(r"^windows(?=$|[\s_0-9.])", o):
        group = "Windows"
    elif _LINUX_DISTRO.match(o):
        group = "Linux"
    else:
        return None
    normalized = raw.casefold()
    if (normalized in _UNKNOWN or _ARCH_ONLY.fullmatch(raw)
            or _OS_AS_MODEL.fullmatch(raw)
            or _WIN_TECHNICAL.fullmatch(raw)):
        return f"Устройство {group}"
    return None


def _platform(os_name: str) -> str:
    os_name = os_name.casefold().strip()
    if os_name.startswith("macos") or os_name.startswith("mac os"):
        return "mac"
    if os_name.startswith("ipados"):
        return "ipad"
    if os_name.startswith("ios"):
        return "iphone"
    if os_name.startswith("android"):
        return "android"
    return ""


def _ua_apple_code(raw: object) -> str:
    if not isinstance(raw, str) or recognized_vpn_app(raw) != "Shadowrocket":
        return ""
    # Только верифицируемый terminus Apple ID в известном форм-факторе UA.
    found = re.search(r" CFNetwork/[0-9.]+ Darwin/[0-9.]+ ((?:iPhone|iPad)[0-9]+,[0-9]+)$", raw)
    return found.group(1) if found else ""



def resolved_mobile_model_id(model: object, os_name: object, user_agent: object = None) -> str:
    """Только однозначный заявленный Apple ID для административной диагностики."""
    raw = _safe(model)
    platform = _platform(_safe(os_name))
    if platform not in ("iphone", "ipad"):
        return ""
    expected = "iPhone" if platform == "iphone" else "iPad"
    direct = raw if _APPLE_ID.fullmatch(raw) else ""
    ua_code = _ua_apple_code(user_agent)
    if direct and ua_code and direct != ua_code:
        return ""
    if direct:
        code = direct
    elif raw.casefold() in _UNKNOWN or raw.casefold() == expected.casefold():
        code = ua_code
    else:
        return ""
    return code if code.startswith(expected) and code in _apple() else ""



# Административная диагностика: не пересылаем без проверки произвольные
# строки, токены, управляющие символы и Telegram/HTML-разметку из 3x-ui.
_ADMIN_SOURCE_LABEL = re.compile(r"[A-Za-zА-Яа-яЁё0-9 ,._+()\\/-]{1,80}")
_ADMIN_OPAQUE_VALUE = re.compile(r"[A-Za-z0-9_-]{32,}")


def _safe_admin_source(value: object) -> str:
    if not isinstance(value, str):
        return ""
    label = value.strip()
    if not _ADMIN_SOURCE_LABEL.fullmatch(label) or _ADMIN_OPAQUE_VALUE.search(label):
        return ""
    return label


def admin_original_hwid_labels(
    source_model: object,
    source_os: object,
    display_model: str,
    *,
    model_id: str = "",
) -> tuple[str, str]:
    """Только дополнительные строки admin detail; никакого влияния на identity.

    Исходная ОС показывается при нормализации самой строки deviceOs, а не
    при обычном добавлении отдельного osVersion.
    """
    model = _safe_admin_source(source_model)
    os_name = _safe_admin_source(source_os)
    original_model = model if model and model != display_model and model != model_id else ""
    original_os = os_name if os_name and display_os(os_name) != os_name else ""
    return original_model, original_os


def display_device_model(model: object, os_name: object, user_agent: object = None) -> str:
    """Никаких изменений identity: результат предназначен исключительно для UI."""
    raw = _safe(model)
    os = _safe(os_name)
    platform = _platform(os)
    if not platform:
        return _desktop_fallback(raw, os) or raw or "Устройство"
    lowered = raw.casefold()
    unknown = lowered in _UNKNOWN
    if platform == "mac":
        if unknown or lowered in ("ipad", "iphone") or _APPLE_ID.fullmatch(raw):
            return "Mac (модель не определена)"
        return raw

    if platform in ("iphone", "ipad"):
        expected = "iPhone" if platform == "iphone" else "iPad"
        fallback = f"{expected} (модель не определена)" if lowered == expected.casefold() else (
            "Устройство iOS" if platform == "iphone" else "iPad (модель не определена)"
        )
        direct = raw if _APPLE_ID.fullmatch(raw) else ""
        ua_code = _ua_apple_code(user_agent)
        # Конфликт кодов не должен приводить к ложной точной модели.
        if direct and ua_code and direct != ua_code:
            return f"{expected} (модель не определена)"
        code = direct or (ua_code if unknown or lowered == expected.casefold() else "")
        if code and code.startswith(expected) and code in _apple():
            return _apple()[code]
        if direct:
            return f"{expected} (модель не определена)"
        if unknown or lowered in ("iphone", "ipad"):
            return fallback
        return raw

    if unknown or lowered == "android":
        return "Устройство Android"
    # Android device-коды неоднозначны, разрешено лишь одно коммерческое имя.
    lookup = _android().get(raw.casefold()) if _ANDROID_CODE.fullmatch(raw) else None
    return lookup or raw
