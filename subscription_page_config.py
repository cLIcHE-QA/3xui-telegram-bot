"""Lossless parsing of operator-provided Subscription Page v1 configs.

Never commit a real operator export. Parsing does not authorize URL/SVG execution.
"""
from __future__ import annotations
import copy
import json
from typing import Any

LANGUAGES = ("en", "ru", "zh", "fa", "fr")
PLATFORMS = ("ios", "linux", "macos", "android", "appleTV", "windows", "androidTV")
LAYOUTS = frozenset(("expanded", "collapsed", "cards", "hidden"))
GUIDE_LAYOUTS = frozenset(("cards", "timeline", "accordion", "minimal"))
BUTTON_TYPES = frozenset(("external", "subscriptionLink", "copyButton"))
ROOT_KEYS = frozenset(("locales", "version", "uiConfig", "platforms", "svgLibrary",
                       "baseSettings", "baseTranslations", "brandingSettings"))
MAX_BYTES = 1024 * 1024


class InvalidSubscriptionConfig(ValueError):
    """Unsupported or malformed operator config; fail closed."""


def _object(value: Any, name: str) -> dict:
    if not isinstance(value, dict):
        raise InvalidSubscriptionConfig(f"{name} must be an object")
    return value


def _localized(value: Any, locales: list[str], path: str) -> None:
    obj = _object(value, path)
    if not all(lang in obj and isinstance(obj[lang], str) for lang in locales):
        raise InvalidSubscriptionConfig(f"{path}: missing locale or non-string text")


def parse_config(data: bytes | str) -> dict:
    """Validate safely, without rewriting strings, ordering, URLs or SVG markup."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    if len(data) > MAX_BYTES:
        raise InvalidSubscriptionConfig("JSON file is too large")
    try:
        doc = json.loads(data)
    except (UnicodeError, ValueError) as exc:
        raise InvalidSubscriptionConfig("Malformed JSON") from exc
    root = _object(doc, "config")
    if root.keys() != ROOT_KEYS:
        raise InvalidSubscriptionConfig("Unexpected root fields")
    if root["version"] != "1":
        raise InvalidSubscriptionConfig("Unsupported config version")
    locales = root["locales"]
    if not isinstance(locales, list) or not locales or len(locales) != len(set(locales)):
        raise InvalidSubscriptionConfig("Invalid locales")
    if not all(lang in LANGUAGES for lang in locales):
        raise InvalidSubscriptionConfig("Unsupported locale")
    ui = _object(root["uiConfig"], "uiConfig")
    if ui.get("subscriptionInfoBlockType") not in LAYOUTS or ui.get("installationGuidesBlockType") not in GUIDE_LAYOUTS:
        raise InvalidSubscriptionConfig("Invalid layout")
    base = _object(root["baseSettings"], "baseSettings")
    if not isinstance(base.get("showConnectionKeys"), bool) or not isinstance(base.get("hideGetLinkButton"), bool):
        raise InvalidSubscriptionConfig("Visibility controls must be booleans")
    _object(root["brandingSettings"], "brandingSettings")
    translations = _object(root["baseTranslations"], "baseTranslations")
    for key, value in translations.items():
        _localized(value, locales, f"baseTranslations.{key}")
    _object(root["svgLibrary"], "svgLibrary")
    for key, svg in root["svgLibrary"].items():
        if not isinstance(key, str) or not isinstance(svg, str):
            raise InvalidSubscriptionConfig("Invalid SVG library entry")
    platforms = _object(root["platforms"], "platforms")
    if any(k not in PLATFORMS for k in platforms):
        raise InvalidSubscriptionConfig("Unknown platform")
    for key, platform in platforms.items():
        apps = _object(platform, f"platforms.{key}").get("apps")
        if not isinstance(apps, list):
            raise InvalidSubscriptionConfig("Invalid apps")
        for app in apps:
            a = _object(app, "app")
            if not isinstance(a.get("name"), str) or not isinstance(a.get("blocks"), list):
                raise InvalidSubscriptionConfig("Invalid app fields")
            for block in a["blocks"]:
                bl = _object(block, "block")
                _localized(bl.get("title"), locales, "block.title")
                _localized(bl.get("description"), locales, "block.description")
                buttons = bl.get("buttons")
                if not isinstance(buttons, list):
                    raise InvalidSubscriptionConfig("Invalid buttons")
                for button in buttons:
                    bt = _object(button, "button")
                    if bt.get("type") not in BUTTON_TYPES or not isinstance(bt.get("link"), str):
                        raise InvalidSubscriptionConfig("Invalid button")
                    _localized(bt.get("text"), locales, "button.text")
    return copy.deepcopy(root)


def config_summary(doc: dict) -> dict:
    """Structural metadata only: no URLs, user content, raw SVG or tokens."""
    apps = [a for p in doc["platforms"].values() for a in p["apps"]]
    blocks = [x for a in apps for x in a["blocks"]]
    buttons = [x for block in blocks for x in block["buttons"]]
    return {
        "languages": len(doc["locales"]),
        "platforms": len(doc["platforms"]),
        "app_slots": len(apps),
        "unique_apps": len(set(a["name"] for a in apps)),
        "blocks": len(blocks),
        "buttons": len(buttons),
        "svg_icons": len(doc["svgLibrary"]),
    }


def serialize_config(doc: dict) -> str:
    """Order-preserving JSON serialization; equality uses parsed objects."""
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
