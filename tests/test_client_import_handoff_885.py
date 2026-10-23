"""#885: защищённый переход из Telegram к импортирующему VPN-клиенту."""
import unittest
from unittest.mock import patch
from aiohttp.test_utils import make_mocked_request
from aiohttp import web

from client_import_handoff import (
    MAX_TICKETS, _TICKETS, consume_handoff, handoff_html, issue_handoff,
)
from client_deep_links import import_uri
from subscription_proxy import SubscriptionProxy

URL = "https://sub.example.invalid/compat/owned-sub"
TEMPLATE = "https://sub.example.invalid/compat/{sub_id}"


class Handoff885Tests(unittest.TestCase):
    def setUp(self):
        _TICKETS.clear()

    def tearDown(self):
        _TICKETS.clear()

    def test_ticket_contains_no_bearer_and_is_one_time(self):
        uri = import_uri("incy", "ios", URL)
        link = issue_handoff(URL, client="incy", uri=uri, public_template=TEMPLATE)
        self.assertTrue(link.startswith("https://sub.example.invalid/compat/open/"))
        self.assertNotIn("owned-sub", link)
        self.assertNotIn("incy://", link)
        token = link.rsplit("/", 1)[-1]
        self.assertEqual(consume_handoff(token), ("incy", uri))
        self.assertIsNone(consume_handoff(token))

    def test_rejects_foreign_url_or_invalid_scheme(self):
        uri = import_uri("happ", "ios", URL)
        for bad in (
            "http://sub.example.invalid/compat/owned-sub",
            "https://evil.invalid/compat/owned-sub",
            "https://sub.example.invalid/compat/owned-sub?view=html",
            "https://sub.example.invalid/compat/../../evil",
            "https://sub.example.invalid/other/owned-sub",
            "https://sub.example.invalid/compat/owned-sub#leak",
        ):
            with self.subTest(bad=bad):
                self.assertIsNone(issue_handoff(bad, client="happ", uri=uri, public_template=TEMPLATE))
        self.assertIsNone(issue_handoff(URL, client="happ", uri="https://evil.invalid", public_template=TEMPLATE))
        self.assertIsNone(issue_handoff(URL, client="unknown", uri=uri, public_template=TEMPLATE))
        self.assertIsNone(issue_handoff(URL, client="happ", uri=uri, public_template=""))

    def test_expired_and_capacity_fail_closed(self):
        uri = import_uri("incy", "ios", URL)
        with patch("client_import_handoff.time.monotonic", return_value=100):
            link = issue_handoff(URL, client="incy", uri=uri, public_template=TEMPLATE)
        with patch("client_import_handoff.time.monotonic", return_value=300):
            self.assertIsNone(consume_handoff(link.rsplit("/", 1)[-1]))
        with patch("client_import_handoff.time.monotonic", return_value=100):
            for _ in range(MAX_TICKETS):
                self.assertIsNotNone(issue_handoff(URL, client="incy", uri=uri, public_template=TEMPLATE))
            self.assertIsNone(issue_handoff(URL, client="incy", uri=uri, public_template=TEMPLATE))

    def test_html_escapes_user_supplied_content(self):
        page = handoff_html("incy", 'incy://import/<script>alert(1)</script>')
        self.assertNotIn('<script>alert(1)</script>', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertIn('rel="noreferrer"', page)


class HandoffProxy885Tests(unittest.IsolatedAsyncioTestCase):
    async def test_proxy_response_has_isolation_headers_and_no_redirect(self):
        uri = import_uri("incy", "ios", URL)
        link = issue_handoff(URL, client="incy", uri=uri, public_template=TEMPLATE)
        token = link.rsplit("/", 1)[-1]
        proxy = SubscriptionProxy(db=None, upstream_template="https://example.invalid/sub/{sub_id}")
        request = make_mocked_request("GET", "/compat/open/" + token, match_info={"ticket": token})
        response = await proxy.handoff(request)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(response.headers["Cache-Control"], "no-store, private")
        self.assertIn("default-src 'none'", response.headers["Content-Security-Policy"])
        self.assertIn("script-src 'sha256-", response.headers["Content-Security-Policy"])
        self.assertNotIn("Location", response.headers)
        with self.assertRaises(web.HTTPNotFound):
            await proxy.handoff(request)
