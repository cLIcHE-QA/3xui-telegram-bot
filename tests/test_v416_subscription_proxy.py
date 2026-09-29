from __future__ import annotations

import base64
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiohttp
from aiohttp import web

from subscription_proxy import (
    SubscriptionProxy,
    _try_decode_subscription,
    convert_vpn_to_amneziawg,
    filter_incy_desktop_awg,
    remove_shadowrocket_xhttp_reality_fp,
)


class SubscriptionProxyRegressionTests(unittest.IsolatedAsyncioTestCase):
    def request(self, sub_id="known", *, query=None, headers=None):
        return SimpleNamespace(
            match_info={"sub_id": sub_id},
            query=dict(query or {}),
            headers=dict(headers or {}),
        )

    def test_plain_and_base64_subscription_detection(self):
        plain = "vless://abc@example.test:443?type=tcp#one\nvpn://payload#awg"
        decoded, wrapped = _try_decode_subscription(plain.encode())
        self.assertEqual(decoded, plain)
        self.assertFalse(wrapped)

        body = base64.b64encode(plain.encode())
        decoded, wrapped = _try_decode_subscription(body)
        self.assertEqual(decoded, plain)
        self.assertTrue(wrapped)

        decoded, wrapped = _try_decode_subscription(b"not a subscription")
        self.assertEqual(decoded, "not a subscription")
        self.assertFalse(wrapped)

    def test_awg_conversion_is_selective_and_preserves_other_links(self):
        text = (
            "vless://abc@example.test:443?type=tcp#vless\n"
            "vpn://YWJjZA#Finland\n"
            "trojan://secret@example.test:443#trojan"
        )
        converted = convert_vpn_to_amneziawg(text)
        self.assertIn("vless://abc@example.test:443?type=tcp#vless", converted)
        self.assertIn("amneziawg://YWJjZA#Finland", converted)
        self.assertIn("trojan://secret@example.test:443#trojan", converted)
        self.assertNotIn("\nvpn://", "\n" + converted)

    def test_awg_conversion_derives_remark_from_embedded_config(self):
        conf = "[Interface]\nPrivateKey=x\n# Name=Finland AWG\n[Peer]\nPublicKey=y\n"
        payload = base64.urlsafe_b64encode(conf.encode()).decode().rstrip("=")
        converted = convert_vpn_to_amneziawg(f"vpn://{payload}")
        self.assertTrue(converted.startswith("amneziawg://"))
        self.assertTrue(converted.endswith("#Finland%20AWG"))

    def test_incy_desktop_filters_awg_entries_only(self):
        text = (
            "vpn://YWJjZA#AWG\n"
            "amneziawg://ZWVmZw#AWG2\n"
            "awg://aGlqaw#AWG3\n"
            "vless://id@example.test:443?type=tcp#VLESS"
        )
        filtered = filter_incy_desktop_awg(text)
        self.assertNotIn("vpn://", filtered)
        self.assertNotIn("amneziawg://", filtered)
        self.assertNotIn("awg://", filtered)
        self.assertIn("vless://id@example.test:443?type=tcp#VLESS", filtered)

    def test_shadowrocket_removes_fp_only_for_vless_xhttp_reality(self):
        xhttp = (
            "vless://id@example.test:443?"
            "type=xhttp&security=reality&fp=chrome&sni=example.com#xhttp"
        )
        tcp = (
            "vless://id@example.test:443?"
            "type=tcp&security=reality&fp=chrome&sni=example.com#tcp"
        )
        converted = remove_shadowrocket_xhttp_reality_fp(xhttp + "\n" + tcp)
        first, second = converted.splitlines()
        self.assertNotIn("fp=", first)
        self.assertIn("sni=example.com", first)
        self.assertIn("fp=chrome", second)

    async def test_invalid_or_unknown_sub_id_never_reaches_upstream(self):
        db = SimpleNamespace(get_by_sub_id=AsyncMock(return_value=None))
        proxy = SubscriptionProxy(
            db,
            "https://upstream.example.invalid/sub/{sub_id}",
            "https://public.example.invalid/compat/{sub_id}",
        )
        proxy._fetch = AsyncMock()

        with self.assertRaises(web.HTTPNotFound):
            await proxy.subscription(self.request(""))
        with self.assertRaises(web.HTTPNotFound):
            await proxy.subscription(self.request("x" * 129))
        with self.assertRaises(web.HTTPNotFound):
            await proxy.subscription(self.request("unknown"))

        proxy._fetch.assert_not_awaited()

    async def test_raw_base64_response_preserves_wrapping_and_converts_only_awg(self):
        db = SimpleNamespace(get_by_sub_id=AsyncMock(return_value=object()))
        proxy = SubscriptionProxy(
            db,
            "https://upstream.example.invalid/sub/{sub_id}",
            "https://public.example.invalid/compat/{sub_id}",
        )
        plain = "vpn://YWJjZA#AWG\nvless://id@example.test:443?type=tcp#VLESS"
        upstream_body = base64.b64encode(plain.encode())
        proxy._fetch = AsyncMock(
            return_value=(
                200,
                upstream_body,
                {
                    "subscription-userinfo": "upload=1; download=2",
                    "Content-Type": "application/octet-stream",
                    "X-Secret": "must-not-pass",
                },
            )
        )

        response = await proxy.subscription(self.request("known"))
        decoded = base64.b64decode(response.body).decode()

        self.assertIn("amneziawg://YWJjZA#AWG", decoded)
        self.assertIn("vless://id@example.test:443?type=tcp#VLESS", decoded)
        self.assertEqual(response.headers["subscription-userinfo"], "upload=1; download=2")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertNotIn("X-Secret", response.headers)

    async def test_plain_mode_decodes_base64_without_changing_default_path(self):
        db = SimpleNamespace(get_by_sub_id=AsyncMock(return_value=object()))
        proxy = SubscriptionProxy(db, "https://upstream.example.invalid/sub/{sub_id}")
        plain = (
            "vless://id@example.test:443?type=tcp&security=reality#one\n"
            "vless://id2@example.test:443?type=xhttp&security=reality#two"
        )
        upstream_body = base64.b64encode(plain.encode())
        proxy._fetch = AsyncMock(return_value=(200, upstream_body, {}))

        default = await proxy.subscription(
            self.request("known", query={"client": "keep"})
        )
        self.assertEqual(default.body, upstream_body)
        self.assertEqual(
            proxy._fetch.await_args.kwargs["params"],
            [("client", "keep")],
        )

        plain_response = await proxy.subscription(
            self.request(
                "known",
                query={"plain": "1", "client": "keep"},
                headers={
                    "Accept": "text/html,application/xhtml+xml",
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 Mobile/22H340 Safari/604.1",
                },
            )
        )
        self.assertEqual(plain_response.body.decode(), plain)
        self.assertEqual(
            proxy._fetch.await_args.kwargs["params"],
            [("client", "keep")],
        )
        self.assertTrue(plain_response.headers["Content-Type"].startswith("text/plain"))
        self.assertEqual(
            proxy._fetch.await_args.kwargs["headers"]["Accept"],
            "text/plain",
        )

    async def test_plain_mode_keeps_hwid_forwarding_and_no_synthetic_identity(self):
        db = SimpleNamespace(get_by_sub_id=AsyncMock(return_value=object()))
        proxy = SubscriptionProxy(db, "https://upstream.example.invalid/sub/{sub_id}")
        upstream_body = base64.b64encode(b"vless://id@example.test:443")
        proxy._fetch = AsyncMock(return_value=(200, upstream_body, {}))

        response = await proxy.subscription(
            self.request(
                "known",
                query={"plain": "true"},
                headers={"User-Agent": "Streisand-Test/1.0", "X-HWID": "device-01"},
            )
        )
        self.assertEqual(response.body, b"vless://id@example.test:443")
        forwarded = proxy._fetch.await_args.kwargs["headers"]
        self.assertEqual(forwarded["X-HWID"], "device-01")
        self.assertNotIn("plain", dict(proxy._fetch.await_args.kwargs["params"]))

    async def test_raw_client_forwards_reviewed_hwid_headers_only(self):
        db = SimpleNamespace(get_by_sub_id=AsyncMock(return_value=object()))
        proxy = SubscriptionProxy(db, "https://upstream.example.invalid/sub/{sub_id}")
        proxy._fetch = AsyncMock(return_value=(200, b"vless://id@example.test:443", {}))
        headers = {
            "User-Agent": "HWID-Test/1.0",
            "X-HWID": "device-01",
            "X-Device-OS": "Linux",
            "X-Ver-OS": "test",
            "X-Device-Model": "Acceptance-Smoke",
            "X-Unreviewed-Secret": "must-not-forward",
        }

        await proxy.subscription(self.request("known", headers=headers))

        kwargs = proxy._fetch.await_args.kwargs
        forwarded = kwargs["headers"]
        self.assertEqual(forwarded["X-HWID"], "device-01")
        self.assertEqual(forwarded["X-Device-OS"], "Linux")
        self.assertEqual(forwarded["X-Ver-OS"], "test")
        self.assertEqual(forwarded["X-Device-Model"], "Acceptance-Smoke")
        self.assertNotIn("X-Unreviewed-Secret", forwarded)

    async def test_shadowrocket_path_strips_only_affected_fingerprint_after_awg_conversion(self):
        db = SimpleNamespace(get_by_sub_id=AsyncMock(return_value=object()))
        proxy = SubscriptionProxy(db, "https://upstream.example.invalid/sub/{sub_id}")
        body = (
            "vpn://YWJjZA#AWG\n"
            "vless://id@example.test:443?type=xhttp&security=reality&fp=chrome#xhttp\n"
            "vless://id@example.test:443?type=tcp&security=reality&fp=chrome#tcp"
        ).encode()
        proxy._fetch = AsyncMock(return_value=(200, body, {}))

        response = await proxy.subscription(
            self.request("known", headers={"User-Agent": "Shadowrocket/2.2"})
        )
        text = response.body.decode()
        lines = text.splitlines()

        self.assertTrue(lines[0].startswith("amneziawg://"))
        self.assertNotIn("fp=", lines[1])
        self.assertIn("fp=chrome", lines[2])

    async def test_incy_desktop_uses_documented_platform_ua_and_mobile_keeps_awg(self):
        db = SimpleNamespace(get_by_sub_id=AsyncMock(return_value=object()))
        proxy = SubscriptionProxy(db, "https://upstream.example.invalid/sub/{sub_id}")
        body = b"vpn://YWJjZA#AWG\nvless://id@example.test:443?type=tcp#VLESS"
        proxy._fetch = AsyncMock(return_value=(200, body, {}))

        desktop = await proxy.subscription(
            self.request("known", headers={"User-Agent": "INCY/1.2.3/Windows"})
        )
        self.assertNotIn(b"vpn://", desktop.body)
        self.assertNotIn(b"amneziawg://", desktop.body)
        self.assertIn(b"vless://", desktop.body)

        mac_desktop = await proxy.subscription(
            self.request(
                "known",
                headers={"User-Agent": "INCY/3.8.8/mac os x Dalvik/21.0.12.1+1-LTS"},
            )
        )
        self.assertNotIn(b"vpn://", mac_desktop.body)
        self.assertNotIn(b"amneziawg://", mac_desktop.body)
        self.assertIn(b"vless://", mac_desktop.body)

        mobile = await proxy.subscription(
            self.request("known", headers={"User-Agent": "INCY/1.2.3/Android"})
        )
        self.assertIn(b"amneziawg://YWJjZA#AWG", mobile.body)

    async def test_hwid_rejections_preserve_404_and_diagnostic_headers(self):
        db = SimpleNamespace(get_by_sub_id=AsyncMock(return_value=object()))
        proxy = SubscriptionProxy(db, "https://upstream.example.invalid/sub/{sub_id}")

        proxy._fetch = AsyncMock(return_value=(
            404,
            b"",
            {
                "X-Hwid-Active": "true",
                "X-Hwid-Limit": "true",
                "X-Hwid-Max-Devices-Reached": "true",
            },
        ))
        response = await proxy.subscription(self.request("known"))
        self.assertEqual(response.status, 404)
        self.assertEqual(response.headers["X-Hwid-Active"], "true")
        self.assertEqual(response.headers["X-Hwid-Max-Devices-Reached"], "true")
        self.assertIn(b"hwid_max_devices_reached", response.body)

        proxy._fetch = AsyncMock(return_value=(
            404,
            b"",
            {"X-Hwid-Active": "true", "X-Hwid-Not-Supported": "true"},
        ))
        response = await proxy.subscription(self.request("known"))
        self.assertEqual(response.status, 404)
        self.assertEqual(response.headers["X-Hwid-Not-Supported"], "true")
        self.assertIn(b"hwid_not_supported", response.body)

    async def test_generic_upstream_404_stays_gateway_error(self):
        db = SimpleNamespace(get_by_sub_id=AsyncMock(return_value=object()))
        proxy = SubscriptionProxy(db, "https://upstream.example.invalid/sub/{sub_id}")
        proxy._fetch = AsyncMock(return_value=(404, b"", {}))
        with self.assertRaises(web.HTTPBadGateway):
            await proxy.subscription(self.request("known"))

    async def test_proxy_never_synthesizes_hwid(self):
        db = SimpleNamespace(get_by_sub_id=AsyncMock(return_value=object()))
        proxy = SubscriptionProxy(db, "https://upstream.example.invalid/sub/{sub_id}")
        proxy._fetch = AsyncMock(return_value=(200, b"vless://id@example.test:443", {}))

        await proxy.subscription(self.request("known", headers={"User-Agent": "Shadowrocket/2.2"}))
        forwarded = proxy._fetch.await_args.kwargs["headers"]
        self.assertNotIn("X-HWID", forwarded)

    async def test_upstream_network_and_http_failures_are_bad_gateway(self):
        db = SimpleNamespace(get_by_sub_id=AsyncMock(return_value=object()))
        proxy = SubscriptionProxy(db, "https://upstream.example.invalid/sub/{sub_id}")

        proxy._fetch = AsyncMock(side_effect=aiohttp.ClientConnectionError("offline"))
        with self.assertRaises(web.HTTPBadGateway):
            await proxy.subscription(self.request("known"))

        proxy._fetch = AsyncMock(return_value=(503, b"down", {}))
        with self.assertRaises(web.HTTPBadGateway):
            await proxy.subscription(self.request("known"))

    async def test_info_mode_is_passthrough_not_subscription_rewrite(self):
        db = SimpleNamespace(get_by_sub_id=AsyncMock(return_value=object()))
        proxy = SubscriptionProxy(db, "https://upstream.example.invalid/sub/{sub_id}")
        body = b'{"status":"ok","url":"vpn://must-stay-native"}'
        proxy._fetch = AsyncMock(
            return_value=(200, body, {"Content-Type": "application/json"})
        )

        response = await proxy.subscription(
            self.request("known", query={"format": "info"}, headers={"Accept": "application/json"})
        )
        self.assertEqual(response.body, body)
        self.assertTrue(response.headers["Content-Type"].startswith("application/json"))

    async def test_asset_path_traversal_is_rejected_without_fetch(self):
        db = SimpleNamespace(get_by_sub_id=AsyncMock())
        proxy = SubscriptionProxy(db, "https://upstream.example.invalid/sub/{sub_id}")
        proxy._fetch = AsyncMock()
        request = SimpleNamespace(
            match_info={"tail": "../secret"},
            headers={},
        )
        with self.assertRaises(web.HTTPNotFound):
            await proxy.asset(request)
        proxy._fetch.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
