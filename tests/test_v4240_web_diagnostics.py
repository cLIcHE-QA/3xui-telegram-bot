from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from website_diagnostics import (
    DnsRecord,
    WebsiteDiagnosticsError,
    _robots_root_disallowed,
    detect_cms,
    format_url_list,
    normalize_domain,
    pagespeed_summary,
    qr_png,
    seo_summary,
    sitemap_urls,
    whois_summary,
)
from website_monitoring import SafeHttpResponse


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def fetch(self, url, *, max_body_bytes):
        self.calls.append((url, max_body_bytes))
        if not self.responses:
            raise AssertionError("unexpected fetch")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def response(url: str, *, status: int = 200, body: bytes = b"", headers=None, redirects=()):
    return SafeHttpResponse(
        requested_url=url,
        final_url=url,
        status=status,
        latency_ms=123,
        headers=headers or {},
        body=body,
        redirects=tuple(redirects),
    )


class WebsiteDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    def test_normalize_domain_is_idna_and_rejects_local(self):
        self.assertEqual(normalize_domain("https://Example.COM/path"), "example.com")
        self.assertEqual(normalize_domain("пример.рф"), "xn--e1afmkfd.xn--p1ai")
        for value in ("localhost", "printer.local", "bad/domain", "user@example.com"):
            with self.subTest(value=value), self.assertRaises(WebsiteDiagnosticsError):
                normalize_domain(value)

    def test_cms_detection_is_best_effort(self):
        self.assertEqual(
            detect_cms(b'<link href="/wp-content/theme.css">'),
            "WordPress",
        )
        self.assertEqual(detect_cms(b"<html>plain</html>"), "не определена")

    def test_robots_root_disallow_requires_wildcard_group(self):
        self.assertTrue(_robots_root_disallowed("User-agent: *\nDisallow: /\n"))
        self.assertFalse(_robots_root_disallowed("User-agent: Googlebot\nDisallow: /\n"))
        self.assertFalse(_robots_root_disallowed("User-agent: *\nDisallow: /private\n"))

    def test_url_list_is_local_deduplicated_and_bounded(self):
        values = format_url_list(
            "example.org\nhttps://example.org/\nhttps://other.example/path#x\nnot a url"
        )
        self.assertEqual(
            values,
            (
                "https://example.org/",
                "https://other.example/path",
                "https://not a url/",
            ),
        )

    def test_qr_is_local_png_and_bounded(self):
        data = qr_png("https://example.org/")
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        with self.assertRaises(WebsiteDiagnosticsError):
            qr_png("")
        with self.assertRaises(WebsiteDiagnosticsError):
            qr_png("x" * 2049)

    async def test_whois_rdap_extracts_age_registrar_and_expiry(self):
        payload = {
            "events": [
                {"eventAction": "registration", "eventDate": "2020-01-01T00:00:00Z"},
                {"eventAction": "expiration", "eventDate": "2030-01-01T00:00:00Z"},
            ],
            "status": ["active"],
            "entities": [{
                "roles": ["registrar"],
                "vcardArray": ["vcard", [["fn", {}, "text", "Example Registrar"]]],
            }],
        }
        client = FakeClient([
            response(
                "https://rdap.org/domain/example.org",
                body=json.dumps(payload).encode(),
            )
        ])
        with patch("website_diagnostics.datetime") as dt:
            dt.now.return_value = __import__("datetime").datetime(2026, 1, 1, tzinfo=__import__("datetime").timezone.utc)
            dt.fromisoformat.side_effect = __import__("datetime").datetime.fromisoformat
            result = await whois_summary("example.org", client)
        self.assertEqual(result.registrar, "Example Registrar")
        self.assertEqual(result.expires_at, "2030-01-01T00:00:00Z")
        self.assertGreater(result.age_days or 0, 2000)

    async def test_seo_summary_combines_header_meta_and_robots(self):
        page_body = b'<meta name="robots" content="noindex,follow">'
        client = FakeClient([
            response(
                "https://example.org/",
                body=page_body,
                headers={"x-robots-tag": "noindex"},
            ),
            response(
                "https://example.org/robots.txt",
                body=b"User-agent: *\nDisallow: /\n",
            ),
        ])
        result = await seo_summary("https://example.org/", client)
        self.assertTrue(result.meta_noindex)
        self.assertTrue(result.header_noindex)
        self.assertTrue(result.robots_txt_available)
        self.assertTrue(result.root_disallowed)

    async def test_sitemap_parser_is_recursive_and_deduplicated(self):
        index = b"""<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <sitemap><loc>https://example.org/a.xml</loc></sitemap>
          <sitemap><loc>https://example.org/b.xml</loc></sitemap>
        </sitemapindex>"""
        child_a = b"""<urlset><url><loc>https://example.org/a</loc></url></urlset>"""
        child_b = b"""<urlset><url><loc>https://example.org/a</loc></url><url><loc>https://example.org/b</loc></url></urlset>"""
        client = FakeClient([
            response("https://example.org/sitemap.xml", body=index),
            response("https://example.org/a.xml", body=child_a),
            response("https://example.org/b.xml", body=child_b),
        ])
        result = await sitemap_urls("https://example.org/", client)
        self.assertEqual(result, ("https://example.org/a", "https://example.org/b"))

    async def test_pagespeed_is_disabled_without_key_and_bounded_with_key(self):
        client = FakeClient([])
        disabled = await pagespeed_summary("https://example.org", client, api_key="")
        self.assertFalse(disabled.enabled)
        self.assertEqual(client.calls, [])

        payload = {
            "lighthouseResult": {"categories": {"performance": {"score": 0.91}}},
            "loadingExperience": {"overall_category": "FAST"},
        }
        client = FakeClient([
            response("https://www.googleapis.com/pagespeedonline/v5/runPagespeed", body=json.dumps(payload).encode())
        ])
        enabled = await pagespeed_summary(
            "https://example.org",
            client,
            api_key="fake-test-key",
        )
        self.assertTrue(enabled.enabled)
        self.assertEqual(enabled.performance_score, 91)
        self.assertEqual(enabled.category, "FAST")
        self.assertIn("www.googleapis.com/pagespeedonline/v5/runPagespeed", client.calls[0][0])

    async def test_dns_summary_uses_system_resolver_and_bounds_records(self):
        class Answer:
            rrset = True
            def __iter__(self):
                return iter([type("R", (), {"to_text": lambda self: "93.184.216.34"})()])

        class Resolver:
            lifetime = 0
            timeout = 0
            def resolve(self, domain, record_type, raise_on_no_answer=False):
                if record_type == "A":
                    return Answer()
                raise Exception("no answer")

        with patch("website_diagnostics.dns.resolver.Resolver", return_value=Resolver()):
            result = await __import__("website_diagnostics").dns_summary("example.org")
        self.assertIn(DnsRecord("A", "93.184.216.34"), result)


if __name__ == "__main__":
    unittest.main()
