"""Проверки неизменности переданных справочников HWID (Issue #830).

Справочники — исходные данные, а не runtime lookup. Нельзя молча
нормализовать строки или угадывать модель по неоднозначному Device ID.
"""

from collections import defaultdict
from hashlib import sha256
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
CATALOGS = ROOT / "docs" / "device-identifiers"
ANDROID_SHA256 = "43da9e8170e4df1a7fe931d441b7d5b2e183f6d407b757f90cf0250029d37970"
APPLE_SHA256 = "ceba373b75ee23a7bc3c9d8f915279a250e5c827f00fe98b03f9acfd8e86f47c"


def rows(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ") or line.startswith(("| Производитель", "| Категория", "| :")):
            continue
        # Изначальный Android Markdown содержит экранированный pipe в названии.
        parts = [part.strip().replace("{{PIPE}}", "|") for part in line.strip().strip("|").replace(chr(92) + "|", "{{PIPE}}").split("|")]
        if len(parts) != 4:
            raise AssertionError(f"Некорректная строка справочника: {line[:100]}")
        yield parts


class DeviceIdentifierCatalogTest(unittest.TestCase):
    def test_original_files_unchanged(self):
        for name, expected in (
            ("android_all_identifiers.md", ANDROID_SHA256),
            ("apple_all_identifiers.md", APPLE_SHA256),
        ):
            with self.subTest(name=name):
                payload = (CATALOGS / name).read_bytes()
                self.assertEqual(sha256(payload).hexdigest(), expected)
                self.assertFalse(payload.startswith(bytes([0xef, 0xbb, 0xbf])))
                self.assertTrue(payload.endswith(bytes([10])))

    def test_android_rows_and_ambiguous_device_ids(self):
        catalog = list(rows(CATALOGS / "android_all_identifiers.md"))
        self.assertEqual(len(catalog), 54217)
        self.assertTrue(any(device == "`oriole`" and model == "Pixel 6" for _, _, device, model in catalog))
        by_device = defaultdict(set)
        for brand, marketed, device, model in catalog:
            by_device[device].add((brand, marketed, model))
        # У одного Device ID могут быть разные коммерческие названия.
        self.assertTrue(any(len({x[1] for x in variants}) > 1 for variants in by_device.values()))

    def test_apple_mobile_identifiers_without_rewriting_source(self):
        catalog = list(rows(CATALOGS / "apple_all_identifiers.md"))
        mapping = {}
        for category, marketed, codes, _ in catalog:
            if category not in ("iPhone", "iPad"):
                continue
            for code in re.findall(r"`(iPhone[0-9]+,[0-9]+|iPad[0-9]+,[0-9]+)`", codes):
                self.assertNotIn(code, mapping)
                mapping[code] = marketed
        self.assertEqual(mapping["iPhone18,1"], "iPhone 17 Pro")
        self.assertGreater(len(mapping), 100)


if __name__ == "__main__":
    unittest.main()
