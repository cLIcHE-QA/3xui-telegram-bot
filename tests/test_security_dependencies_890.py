"""Регрессия обновления Pillow/certifi и генерации QR в PNG/SVG."""

import io
import unittest
from importlib.metadata import version
from pathlib import Path

import certifi
import qrcode
import qrcode.image.svg
from PIL import Image


class TestDependencySecurity890(unittest.TestCase):
    def test_pinned_versions(self):
        self.assertEqual(version("Pillow"), "13.0.0")
        self.assertEqual(version("certifi"), "2026.10.19")

    def test_png_qrcode(self):
        qr = qrcode.QRCode(border=4, box_size=2)
        qr.add_data("https://example.invalid/compat/test-fixture")
        qr.make(fit=True)
        buf = io.BytesIO()
        qr.make_image(fill_color="black", back_color="white").save(buf, format="PNG")
        buf.seek(0)
        with Image.open(buf) as img:
            img.verify()
        buf.seek(0)
        with Image.open(buf) as img:
            self.assertEqual(img.format, "PNG")
            self.assertGreater(img.width, 10)
            self.assertEqual(img.width, img.height)

    def test_svg_qrcode(self):
        qr = qrcode.QRCode(image_factory=qrcode.image.svg.SvgPathImage)
        qr.add_data("https://example.invalid/compat/test-fixture")
        qr.make(fit=True)
        buf = io.BytesIO()
        qr.make_image().save(buf)
        svg = buf.getvalue().decode("utf-8")
        self.assertIn("<svg", svg)
        self.assertIn("<path", svg)
        self.assertNotIn("<script", svg.lower())

    def test_certifi_ca_bundle_exists(self):
        path = Path(certifi.where())
        self.assertTrue(path.is_file())
        self.assertGreater(path.stat().st_size, 100000)


if __name__ == "__main__":
    unittest.main()
