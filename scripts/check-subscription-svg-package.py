#!/usr/bin/env python3
"""Проверка целостности операторского SVG-пакета без распаковки или публикации SVG."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

SVG_NS = "http://www.w3.org/2000/svg"
MAX_ARCHIVE_FILES = 80
MAX_UNCOMPRESSED = 4 * 1024 * 1024
MAX_SVG_BYTES = 256 * 1024
MAX_JSON_BYTES = 1024 * 1024
BANNED_XML = re.compile(rb"<!\s*(?:DOCTYPE|ENTITY)|<\?xml-stylesheet", re.IGNORECASE)
BANNED_TAGS = {"script", "foreignObject", "iframe", "image", "style", "animate", "set", "animateMotion", "animateTransform"}
EXTERNAL_REFERENCE = re.compile(r"(?:https?://|javascript:|data:|file:|url\(\s*[^#]|@import)", re.IGNORECASE)


class InvalidSvgPackage(ValueError):
    """Пакет не соответствует опубликованному инвентарю или безопасной форме."""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _svg_preflight(data: bytes, key: str) -> None:
    if len(data) > MAX_SVG_BYTES or BANNED_XML.search(data):
        raise InvalidSvgPackage(f"{key}: запрещённая XML-конструкция либо превышен лимит")
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise InvalidSvgPackage(f"{key}: некорректный XML") from exc
    if root.tag != f"{{{SVG_NS}}}svg":
        raise InvalidSvgPackage(f"{key}: корневой элемент не SVG")
    for elem in root.iter():
        if elem.tag.startswith("{"):
            namespace, local_name = elem.tag[1:].split("}", 1)
        else:
            namespace, local_name = "", elem.tag
        if namespace != SVG_NS or local_name in BANNED_TAGS:
            raise InvalidSvgPackage(f"{key}: запрещённый SVG-элемент")
        for name, value in elem.attrib.items():
            local_attr = name.split("}")[-1].lower()
            if local_attr.startswith("on") or local_attr in {"href", "style"}:
                raise InvalidSvgPackage(f"{key}: запрещённый SVG-атрибут")
            if EXTERNAL_REFERENCE.search(value):
                raise InvalidSvgPackage(f"{key}: внешняя ссылка/ресурс")


def verify_package(archive_path: Path, inventory_path: Path) -> dict[str, str | int]:
    """Проверить SHA JSON, ключи, копии SVG и состав ZIP. Ничего не извлекать."""
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise InvalidSvgPackage("Реестр SVG недоступен или повреждён") from exc
    assets = inventory.get("assets")
    if not isinstance(assets, list):
        raise InvalidSvgPackage("Отсутствует массив assets")
    source_assets = {item["key"]: item for item in assets if item.get("key") != "INCY"}
    if len(source_assets) != len(assets) - 1 or len(source_assets) + 1 != inventory.get("totals", {}).get("all"):
        raise InvalidSvgPackage("Реестр должен содержать уникальные ключи и отдельный INCY")
    for key in source_assets:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", key):
            raise InvalidSvgPackage("Недопустимый ключ SVG")
    required = {"svg/svgLibrary.json", "svg/manifest.json", "svg/README_REVIEW_ONLY.txt"}
    required.update(f"svg/icons/{key}.svg" for key in source_assets)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            files = [item for item in archive.infolist() if not item.is_dir()]
            paths = [item.filename for item in files]
            if len(files) > MAX_ARCHIVE_FILES or len(paths) != len(set(paths)) or set(paths) != required:
                raise InvalidSvgPackage("Список файлов ZIP не совпадает с ожидаемым")
            if any(
                PurePosixPath(item.filename).is_absolute()
                or ".." in PurePosixPath(item.filename).parts
                or (item.external_attr >> 16) & 0o170000 == 0o120000
                for item in files
            ):
                raise InvalidSvgPackage("Недопустимый путь или символическая ссылка")
            if sum(item.file_size for item in files) > MAX_UNCOMPRESSED:
                raise InvalidSvgPackage("Превышен лимит распакованного размера")
            if any(item.file_size > MAX_JSON_BYTES for item in files if item.filename.endswith(".json")):
                raise InvalidSvgPackage("Превышен лимит JSON")
            source_raw = archive.read("svg/svgLibrary.json")
            actual_source_sha = _digest(source_raw)
            if actual_source_sha != inventory.get("source_json_sha256"):
                raise InvalidSvgPackage("SHA-256 исходного svgLibrary не совпадает")
            source = json.loads(source_raw)
            if not isinstance(source, dict) or set(source) != {"svgLibrary"} or not isinstance(source["svgLibrary"], dict):
                raise InvalidSvgPackage("Структура svgLibrary некорректна")
            icons = source["svgLibrary"]
            if set(icons) != set(source_assets):
                raise InvalidSvgPackage("Набор ключей svgLibrary не совпадает с inventory")
            manifest = json.loads(archive.read("svg/manifest.json"))
            manifest_assets = manifest.get("assets", [])
            if not isinstance(manifest_assets, list) or len(manifest_assets) != len(source_assets):
                raise InvalidSvgPackage("Manifest содержит неверное число активов")
            by_key = {item.get("key"): item for item in manifest_assets if isinstance(item, dict)}
            if set(by_key) != set(source_assets):
                raise InvalidSvgPackage("Manifest не совпадает с ключами SVG")
            for key, info in source_assets.items():
                icon = icons[key]
                if not isinstance(icon, str):
                    raise InvalidSvgPackage(f"{key}: SVG должен быть строкой")
                data = archive.read(f"svg/icons/{key}.svg")
                if data != icon.encode("utf-8"):
                    raise InvalidSvgPackage(f"{key}: SVG не совпадает с JSON")
                digest = _digest(data)
                if not digest.startswith(info.get("sha256_prefix", "НЕВЕРНО")):
                    raise InvalidSvgPackage(f"{key}: fingerprint inventory не совпадает")
                if by_key[key].get("sha256") != digest or by_key[key].get("filename") != f"{key}.svg":
                    raise InvalidSvgPackage(f"{key}: manifest SHA/имя не совпадает")
                if by_key[key].get("category") != info.get("category"):
                    raise InvalidSvgPackage(f"{key}: категория manifest не совпадает")
                _svg_preflight(data, key)
    except (OSError, zipfile.BadZipFile, UnicodeError, json.JSONDecodeError) as exc:
        raise InvalidSvgPackage("Невозможно прочитать архив/JSON") from exc
    return {"source_sha256": actual_source_sha, "source_icons": len(source_assets), "separate_incy": 1,
            "integrity": "PASS", "static_xml_preflight": "PASS", "license_and_trademark": "PENDING"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Проверить локальный операторский SVG-пакет без публикации")
    parser.add_argument("--archive", required=True, type=Path, help="Локальный ZIP с svgLibrary.json")
    parser.add_argument("--inventory", type=Path, default=Path("docs/assets/subscription-svg-inventory.json"))
    args = parser.parse_args()
    try:
        result = verify_package(args.archive, args.inventory)
    except InvalidSvgPackage as exc:
        print(f"SVG INTEGRITY FAIL: {exc}", file=sys.stderr)
        return 1
    print("SVG INTEGRITY PASS: " + json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
