"""Регрессия security dependencies, локальных QR и DNS wire/API compatibility."""

import io
import unittest
from importlib.metadata import version
from pathlib import Path

import certifi
import dns.message
import dns.rrset
import qrcode
import qrcode.image.svg
from PIL import Image


class TestDependencySecurity890(unittest.TestCase):
    def test_pinned_versions(self):
        self.assertEqual(version("Pillow"), "13.0.0")
        self.assertEqual(version("certifi"), "2026.10.19")
        self.assertEqual(version("dnspython"), "2.9.0")

    def test_dns_compressed_wire_roundtrip_is_local_and_preserves_records(self):
        query = dns.message.make_query("fixture.example.invalid", "A")
        response = dns.message.make_response(query)
        response.answer.append(dns.rrset.from_text("fixture.example.invalid.", 60, "IN", "A", "192.0.2.1"))
        response.answer.append(dns.rrset.from_text("fixture.example.invalid.", 60, "IN", "AAAA", "2001:db8::1"))
        packet = response.to_wire()
        self.assertLess(len(packet), 512)
        parsed = dns.message.from_wire(packet)
        self.assertEqual(parsed.question[0].name.to_text(), "fixture.example.invalid.")
        self.assertEqual(parsed.answer[0][0].to_text(), "192.0.2.1")
        self.assertEqual(parsed.answer[1][0].to_text(), "2001:db8::1")
        self.assertTrue(all(record.ttl == 60 for record in parsed.answer))

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
