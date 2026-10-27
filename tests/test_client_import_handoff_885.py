"""#885: защищённый переход из Telegram к импортирующему VPN-клиенту."""
import unittest
import importlib
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import aiohttp
from yarl import URL as RequestURL
from aiohttp.test_utils import make_mocked_request
from aiohttp import web

from client_import_handoff import (
    MAX_TICKETS, _TICKETS, consume_handoff, handoff_html, issue_handoff,
)
from client_deep_links import IMPORT_CLIENTS, import_uri
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
        link = issue_handoff(URL, client="incy", platform="ios", uri=uri, public_template=TEMPLATE)
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
                self.assertIsNone(issue_handoff(bad, client="happ", platform="ios", uri=uri, public_template=TEMPLATE))
        self.assertIsNone(issue_handoff(URL, client="happ", platform="ios", uri="https://evil.invalid", public_template=TEMPLATE))
        self.assertIsNone(issue_handoff(URL, client="unknown", platform="ios", uri=uri, public_template=TEMPLATE))
        self.assertIsNone(issue_handoff(URL, client="happ", platform="ios", uri=uri, public_template=""))

    def test_expired_and_capacity_fail_closed(self):
        uri = import_uri("incy", "ios", URL)
        with patch("client_import_handoff.time.monotonic", return_value=100):
            link = issue_handoff(URL, client="incy", platform="ios", uri=uri, public_template=TEMPLATE)
        with patch("client_import_handoff.time.monotonic", return_value=300):
            self.assertIsNone(consume_handoff(link.rsplit("/", 1)[-1]))
        with patch("client_import_handoff.time.monotonic", return_value=100):
            for _ in range(MAX_TICKETS):
                self.assertIsNotNone(issue_handoff(URL, client="incy", platform="ios", uri=uri, public_template=TEMPLATE))
            self.assertIsNone(issue_handoff(URL, client="incy", platform="ios", uri=uri, public_template=TEMPLATE))

    def test_payload_must_match_exact_owner_url_platform_and_title(self):
        foreign = import_uri("incy", "ios", URL.replace("owned-sub", "other-sub"))
        self.assertIsNone(issue_handoff(
            URL, client="incy", platform="ios", uri=foreign, public_template=TEMPLATE))
        self.assertIsNone(issue_handoff(
            URL, client="shadowrocket", platform="android",
            uri=import_uri("shadowrocket", "ios", URL), public_template=TEMPLATE))
        uri = import_uri("karing", "ios", URL, title="Тест VPN")
        for title in (None, "Другое имя"):
            self.assertIsNone(issue_handoff(
                URL, client="karing", platform="ios", uri=uri,
                title=title, public_template=TEMPLATE))
        self.assertFalse(_TICKETS)

    def test_every_supported_format_preserves_the_generated_payload(self):
        for client, spec in IMPORT_CLIENTS.items():
            for platform in spec.platforms:
                with self.subTest(client=client, platform=platform):
                    uri = import_uri(client, platform, URL, title="Тест VPN")
                    link = issue_handoff(
                        URL, client=client, platform=platform, uri=uri,
                        title="Тест VPN", public_template=TEMPLATE)
                    self.assertIsNotNone(link)
                    self.assertEqual(consume_handoff(link.rsplit("/", 1)[-1]), (client, uri))

    def test_malformed_inputs_and_template_fail_without_creating_ticket(self):
        uri = import_uri("incy", "ios", URL)
        for value in (None, "", False, b"invalid", "x" * 1000):
            self.assertIsNone(consume_handoff(value))
        for template in (None, "", "https:///compat/{sub_id}",
                         "https://user:pass@sub.example.invalid/compat/{sub_id}",
                         TEMPLATE + "?preview=1", TEMPLATE + "#fragment",
                         TEMPLATE + "/{sub_id}", TEMPLATE + "{sub_id.missing}"):
            self.assertIsNone(issue_handoff(
                URL, client="incy", platform="ios", uri=uri, public_template=template))
        self.assertFalse(_TICKETS)

    def test_html_escapes_user_supplied_content(self):
        page = handoff_html("incy", 'incy://import/<script>alert(1)</script>')
        self.assertNotIn('<script>alert(1)</script>', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertIn('rel="noreferrer"', page)


class HandoffProxy885Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        _TICKETS.clear()
        self.addCleanup(_TICKETS.clear)

    async def test_proxy_response_has_isolation_headers_and_no_redirect(self):
        uri = import_uri("incy", "ios", URL)
        link = issue_handoff(URL, client="incy", platform="ios", uri=uri, public_template=TEMPLATE)
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

    async def test_http_head_post_query_and_extra_path_never_consume_ticket(self):
        uri = import_uri("incy", "ios", URL)
        link = issue_handoff(URL, client="incy", platform="ios", uri=uri, public_template=TEMPLATE)
        path = "/compat/open/" + link.rsplit("/", 1)[-1]
        proxy = SubscriptionProxy(
            db=None, upstream_template="https://upstream.example.invalid/sub/{sub_id}",
            host="127.0.0.1", port=0)
        with patch.object(proxy, "_fetch", new=AsyncMock(side_effect=AssertionError("provider forbidden"))) as fetch:
            await proxy.start()
            self.addAsyncCleanup(proxy.stop)
            port = proxy.runner.addresses[0][1]
            base = f"http://127.0.0.1:{port}"
            async with aiohttp.ClientSession() as client:
                token = link.rsplit("/", 1)[-1]
                encoded_path = "/compat/open/%" + format(ord(token[0]), "02X") + token[1:]
                for method, target, expected in (
                    ("HEAD", path, 405), ("POST", path, 405),
                    ("GET", path + "?preview=1", 404), ("GET", path + "/extra", 404),
                    ("GET", encoded_path, 404),
                ):
                    async with client.request(method, RequestURL(base + target, encoded=True)) as response:
                        self.assertEqual(response.status, expected)
                        self.assertNotIn(uri, await response.text())
                async with client.get(base + path) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn(uri, await response.text())
                    self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
                    self.assertNotIn("Location", response.headers)
                async with client.get(base + path) as response:
                    self.assertEqual(response.status, 404)
                    self.assertEqual(response.headers["Cache-Control"], "no-store, private")
            fetch.assert_not_awaited()


class HandoffUI885Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        _TICKETS.clear()
        self.addCleanup(_TICKETS.clear)
        with patch.dict(os.environ, {
            "BOT_TOKEN": "123456789:offline-test-only",
            "PANEL_URL": "https://panel.example.invalid",
            "PANEL_API_TOKEN": "offline-only",
            "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/compat/{sub_id}",
            "ALLOWED_TELEGRAM_IDS": "100001", "ADMIN_TELEGRAM_IDS": "100001",
        }):
            self.ui = importlib.import_module("client_access")

    def call(self, *, chat_type="private", chat_id=100001):
        return SimpleNamespace(
            data="client:onboard:ios:incy", from_user=SimpleNamespace(id=100001),
            message=SimpleNamespace(chat=SimpleNamespace(type=chat_type, id=chat_id)),
            answer=AsyncMock(), bot=SimpleNamespace(send_photo=AsyncMock()))

    async def test_owner_handoff_contains_only_ticket_and_keeps_copy_qr_back(self):
        service = SimpleNamespace(subscription_url=AsyncMock(return_value=URL))
        with patch.object(self.ui, "guard_callback", new=AsyncMock(return_value=True)), \
             patch.object(self.ui, "settings", SimpleNamespace(compat_subscription_url_template=TEMPLATE)), \
             patch.object(self.ui, "_service", return_value=service), \
             patch.object(self.ui, "render_callback", new=AsyncMock()) as render:
            await self.ui.onboarding_platform_cb(self.call())
        service.subscription_url.assert_awaited_once_with(100001)
        buttons = [b for row in render.await_args.kwargs["reply_markup"].inline_keyboard for b in row]
        opens = [b for b in buttons if b.url]
        self.assertEqual(len(opens), 1)
        self.assertTrue(opens[0].url.startswith("https://sub.example.invalid/compat/open/"))
        self.assertNotIn("owned-sub", opens[0].url)
        self.assertTrue(any(b.copy_text for b in buttons))
        self.assertTrue(any(b.callback_data and b.callback_data.endswith(":qr") for b in buttons))
        self.assertTrue(any(b.text.startswith("⬅") for b in buttons))

    async def test_disabled_or_invalid_template_keeps_fallback_without_open_instruction(self):
        for template in ("", "https://evil.example.invalid/compat/{sub_id}"):
            with self.subTest(template=template):
                service = SimpleNamespace(subscription_url=AsyncMock(return_value=URL))
                with patch.object(self.ui, "guard_callback", new=AsyncMock(return_value=True)), \
                     patch.object(self.ui, "settings", SimpleNamespace(compat_subscription_url_template=template)), \
                     patch.object(self.ui, "_service", return_value=service), \
                     patch.object(self.ui, "render_callback", new=AsyncMock()) as render:
                    await self.ui.onboarding_platform_cb(self.call())
                self.assertNotIn("Нажмите «Открыть", render.await_args.args[1])
                buttons = [b for row in render.await_args.kwargs["reply_markup"].inline_keyboard for b in row]
                self.assertFalse(any(b.url for b in buttons))
                self.assertTrue(any(b.copy_text for b in buttons))
                self.assertFalse(_TICKETS)

    async def test_non_owner_context_never_mints_or_reads_subscription(self):
        for call in (self.call(chat_type="group"), self.call(chat_id=100002)):
            service = SimpleNamespace(subscription_url=AsyncMock())
            with patch.object(self.ui, "guard_callback", new=AsyncMock(return_value=True)), \
                 patch.object(self.ui, "issue_handoff") as issue, \
                 patch.object(self.ui, "_service", return_value=service):
                await self.ui.onboarding_platform_cb(call)
            issue.assert_not_called()
            service.subscription_url.assert_not_awaited()
