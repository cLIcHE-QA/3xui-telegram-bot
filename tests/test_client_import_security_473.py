"""Security boundaries for #473: no HTTP redirect/SSRF, bounded subTitle, owner-only."""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from client_deep_links import import_uri
from client_import_title import fetch_import_title, safe_import_title

URL = "https://sub.example.invalid/compat/owned-sub"


class ImportTitleSecurityTests(unittest.IsolatedAsyncioTestCase):
    def test_untrusted_titles_fail_closed(self):
        for raw in ("", " ", " bad", "bad ", ("bad" + chr(10) + "name"), ("bad" + chr(13) + "name"),
                    ("safe" + chr(0x202e) + "evil"), ("safe" + chr(0x200d) + "spoof"), "a" * 65,
                    "https://example.invalid/" + "x" * 44, None, 123):
            with self.subTest(value=repr(raw)):
                self.assertIsNone(safe_import_title(raw))
        self.assertEqual(safe_import_title("Название VPN"), "Название VPN")

    async def test_identity_and_proxy_port_are_strict(self):
        with patch("client_import_title.aiohttp.ClientSession") as session:
            for subid in ("", "../other", "other?format=info", "other/evil",
                          "other#fragment", ("bad" + chr(10) + "sub"), None):
                self.assertIsNone(await fetch_import_title(subid, proxy_port=8080))
            for port in (0, -1, 65536, True, "8080"):
                self.assertIsNone(await fetch_import_title("valid_id", proxy_port=port))
            session.assert_not_called()

    async def test_proxy_unavailable_returns_no_label(self):
        session = MagicMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        session.get.side_effect = aiohttp.ClientConnectionError("unavailable")
        with patch("client_import_title.aiohttp.ClientSession", return_value=session):
            self.assertIsNone(await fetch_import_title("valid_id", proxy_port=8080))
        args, kwargs = session.get.call_args
        self.assertEqual(args[0], "http://127.0.0.1:8080/compat/valid_id?format=info")
        self.assertFalse(kwargs["allow_redirects"])

    async def test_metadata_read_success_and_fail_closed_http_responses(self):
        # Проверяем реальный async context-manager contract, а не только
        # обработку ClientConnectionError через mock.
        import json
        response = MagicMock()
        response.__aenter__ = AsyncMock(return_value=response)
        response.__aexit__ = AsyncMock(return_value=None)
        response.status = 200
        response.headers = {"Content-Type": "application/json; charset=utf-8"}
        response.content.read = AsyncMock(
            return_value=json.dumps({"subTitle": "Тестовый VPN"}).encode(),
        )
        session = MagicMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        session.get.return_value = response
        with patch("client_import_title.aiohttp.ClientSession", return_value=session) as maker:
            self.assertEqual(
                await fetch_import_title("owner_sub", proxy_port=2086),
                "Тестовый VPN",
            )
            maker.assert_called_once()
            self.assertFalse(maker.call_args.kwargs["trust_env"])
        response.content.read.assert_awaited_with(8193)

        for status, content_type, raw in (
            (302, "application/json", b"{}"),
            (200, "text/html", b"<html></html>"),
            (200, "application/json", b"not-json"),
            (200, "application/json", b"[]" ),
            (200, "application/json", json.dumps({"subTitle": "bad\\nlabel"}).encode()),
            (200, "application/json", b"x" * 8193),
        ):
            with self.subTest(status=status, body=raw[:14]):
                response.status = status
                response.headers = {"Content-Type": content_type}
                response.content.read = AsyncMock(return_value=raw)
                with patch("client_import_title.aiohttp.ClientSession", return_value=session):
                    self.assertIsNone(
                        await fetch_import_title("owner_sub", proxy_port=2086),
                    )
                self.assertFalse(session.get.call_args.kwargs["allow_redirects"])

    async def test_foreign_chat_never_fetches_title(self):
        import client_access as ui
        call = SimpleNamespace(
            data="client:onboard:ios:shadowrocket",
            from_user=SimpleNamespace(id=42),
            message=SimpleNamespace(chat=SimpleNamespace(id=99, type="private")),
            answer=AsyncMock(), bot=SimpleNamespace(send_photo=AsyncMock()),
        )
        with patch.object(ui, "guard_callback", new=AsyncMock(return_value=True)), \
             patch.object(ui, "fetch_import_title", new=AsyncMock()) as title, \
             patch.object(ui, "_service") as service:
            await ui.onboarding_platform_cb(call)
        title.assert_not_awaited()
        service.assert_not_called()

    async def test_shadowrocket_owner_reads_only_read_access_false(self):
        import client_access as ui
        call = SimpleNamespace(
            data="client:onboard:ios:shadowrocket",
            from_user=SimpleNamespace(id=42),
            message=SimpleNamespace(chat=SimpleNamespace(id=42, type="private")),
            answer=AsyncMock(), bot=SimpleNamespace(send_photo=AsyncMock()),
        )
        service = SimpleNamespace(
            subscription_url=AsyncMock(return_value=URL),
            profile=AsyncMock(return_value=SimpleNamespace(sub_id="owned-sub")),
        )
        with patch.object(ui, "guard_callback", new=AsyncMock(return_value=True)), \
             patch.object(ui, "_service", return_value=service), \
             patch.object(ui, "fetch_import_title", new=AsyncMock(return_value="Мой VPN")) as title, \
             patch.object(ui, "render_callback", new=AsyncMock()) as render:
            await ui.onboarding_platform_cb(call)
        service.profile.assert_awaited_once_with(42, read_access=False)
        title.assert_awaited_once()
        menu = render.await_args.kwargs["reply_markup"]
        from base64 import b64encode
        expected = import_uri("shadowrocket", "ios", URL, title="Мой VPN")
        self.assertIn(expected, [b.copy_text.text for row in menu.inline_keyboard
                                 for b in row if b.copy_text])
        self.assertTrue(all("owned-sub" not in (b.callback_data or "")
                            for row in menu.inline_keyboard for b in row))


if __name__ == "__main__":
    unittest.main()
