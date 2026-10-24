"""Негативные тесты локальной проверки SVG-источника без реальных брендовых файлов."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check-subscription-svg-package.py"
spec = importlib.util.spec_from_file_location("subscription_svg_package_checker", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class TestSubscriptionSvgPackage(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.icon = '<svg xmlns="http://www.w3.org/2000/svg"><path d="M1 1L2 2"/></svg>'
        self.key = "Example"

    @staticmethod
    def sha(raw):
        return hashlib.sha256(raw).hexdigest()

    def make_package(self, icon=None, source_icon=None, inventory_prefix=None, filenames=None):
        icon = self.icon if icon is None else icon
        source_icon = icon if source_icon is None else source_icon
        source_bytes = json.dumps({"svgLibrary": {self.key: source_icon}}, ensure_ascii=False).encode()
        icon_raw = icon.encode()
        digest = self.sha(icon_raw)
        inventory = {"source_json_sha256": self.sha(source_bytes), "totals": {"all": 2}, "assets": [
            {"key": self.key, "sha256_prefix": inventory_prefix or digest[:16], "category": "vpn_client"},
            {"key": "INCY", "sha256_prefix": "pending-canonicalization", "category": "vpn_client"},
        ]}
        self.inventory = self.root / "inventory.json"
        self.inventory.write_text(json.dumps(inventory))
        self.archive = self.root / "source.zip"
        entries = {"svg/svgLibrary.json": source_bytes, "svg/icons/Example.svg": icon_raw,
                   "svg/manifest.json": json.dumps({"assets": [{"key": self.key, "filename": "Example.svg",
                   "sha256": digest, "category": "vpn_client"}]}).encode(),
                   "svg/README_REVIEW_ONLY.txt": b"review only"}
        if filenames:
            entries.update(filenames)
        with zipfile.ZipFile(self.archive, "w") as z:
            for filename, raw in entries.items():
                z.writestr(filename, raw)
        return self.archive, self.inventory

    def test_valid_synthetic_archive(self):
        archive, inventory = self.make_package()
        result = checker.verify_package(archive, inventory)
        self.assertEqual(result["source_icons"], 1)
        self.assertEqual(result["integrity"], "PASS")
        self.assertEqual(result["license_and_trademark"], "PENDING")

    def test_changed_individual_svg_rejected(self):
        archive, inventory = self.make_package(icon=self.icon, source_icon=self.icon + " ")
        with self.assertRaisesRegex(checker.InvalidSvgPackage, "не совпадает с JSON"):
            checker.verify_package(archive, inventory)

    def test_wrong_inventory_hash_rejected(self):
        archive, inventory = self.make_package(inventory_prefix="0000000000000000")
        with self.assertRaisesRegex(checker.InvalidSvgPackage, "fingerprint"):
            checker.verify_package(archive, inventory)

    def test_extra_zip_entry_rejected(self):
        archive, inventory = self.make_package(filenames={"svg/icons/Surprise.svg": b"<svg/>"})
        with self.assertRaisesRegex(checker.InvalidSvgPackage, "Список файлов"):
            checker.verify_package(archive, inventory)

    def test_incy_is_not_part_of_private_archive(self):
        archive, inventory = self.make_package(filenames={"svg/icons/INCY.svg": b"<svg/>"})
        with self.assertRaisesRegex(checker.InvalidSvgPackage, "Список файлов"):
            checker.verify_package(archive, inventory)

    def test_script_svg_rejected_even_when_hash_matches(self):
        bad = '<svg xmlns="http://www.w3.org/2000/svg"><script>bad()</script></svg>'
        archive, inventory = self.make_package(icon=bad)
        with self.assertRaisesRegex(checker.InvalidSvgPackage, "запрещённый SVG-элемент"):
            checker.verify_package(archive, inventory)

    def test_external_svg_href_rejected(self):
        bad = '<svg xmlns="http://www.w3.org/2000/svg"><use href="https://example.org/a.svg#x"/></svg>'
        archive, inventory = self.make_package(icon=bad)
        with self.assertRaisesRegex(checker.InvalidSvgPackage, "запрещённый SVG-атрибут"):
            checker.verify_package(archive, inventory)

    def test_xml_doctype_rejected(self):
        bad = '<!DOCTYPE svg><svg xmlns="http://www.w3.org/2000/svg"/>'
        archive, inventory = self.make_package(icon=bad)
        with self.assertRaisesRegex(checker.InvalidSvgPackage, "запрещённая XML-конструкция"):
            checker.verify_package(archive, inventory)


if __name__ == "__main__":
    unittest.main()
