"""#473: fail-closed deep-link import и изоляция bearer URL."""
import base64
import unittest
from urllib.parse import quote
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from client_deep_links import IMPORT_CLIENTS, REQUIRED_TITLE_CLIENTS, import_uri

URL = "https://sub.example.invalid/compat/owned-sub"


class ImportURI473Tests(unittest.TestCase):
    def test_supported_platforms_have_bounded_documented_candidates(self):
        for client, spec in IMPORT_CLIENTS.items():
            for platform in spec.platforms:
                with self.subTest(client=client, platform=platform):
                    uri = import_uri(client, platform, URL, title="Тест VPN")
                    source = URL + "?flag=shadowrocket" if client == "shadowrocket" else URL
                    if client == "throne":
                        source += "#Тест VPN"
                    payload = (source if spec.encoding == "direct" else quote(source, safe="") if spec.encoding == "percent" else base64.b64encode(source.encode()).decode())
                    suffix = ("&name=" + quote("Тест VPN", safe="") if client in REQUIRED_TITLE_CLIENTS
                              else "?remark=" + quote("Тест VPN", safe="") if client == "shadowrocket"
                              else "#" + quote("Тест VPN", safe="") if client == "onexray" else "")
                    self.assertEqual(uri, spec.prefix + payload + suffix)
                    self.assertLessEqual(len(uri), 256)

    def test_full_os_matrix_includes_windows_and_linux(self):
        expected = {
            "ios": {"incy", "v2raytun", "happ", "v2box", "shadowrocket", "karing", "onexray"},
            "android": {"incy", "v2raytun", "happ", "v2box", "karing", "onexray", "throne"},
            "windows": {"incy", "v2raytun", "karing", "onexray", "throne"},
            "macos": {"incy", "v2raytun", "happ", "shadowrocket", "karing", "onexray", "throne"},
            "linux": {"incy", "karing", "onexray", "throne"},
        }
        for platform, apps in expected.items():
            actual = {app for app, spec in IMPORT_CLIENTS.items()
                      if platform in spec.platforms}
            self.assertEqual(actual, apps, platform)

    async def test_windows_linux_menu_only_shows_compatible_apps(self):
        import client_access as ui
        for platform, expected in (
            ("windows", {"Incy", "v2raytun", "Karing", "OneXray", "Throne"}),
            ("linux", {"Incy", "Karing", "OneXray", "Throne"}),
        ):
            with self.subTest(platform=platform):
                call = SimpleNamespace(
                    data=f"client:onboard:{platform}",
                    from_user=SimpleNamespace(id=42),
                    message=SimpleNamespace(chat=SimpleNamespace(id=42, type="private")),
                    answer=AsyncMock(), bot=SimpleNamespace(send_photo=AsyncMock()),
                )
                with patch.object(ui, "guard_callback", new=AsyncMock(return_value=True)), \
                     patch.object(ui, "render_callback", new=AsyncMock()) as render:
                    await ui.onboarding_platform_cb(call)
                markup = render.await_args.kwargs["reply_markup"]
                apps = {button.text.split(" · ")[0].removeprefix("🔗 ")
                        for row in markup.inline_keyboard for button in row
                        if button.text.startswith("🔗 ")}
                self.assertEqual(apps, expected)
                self.assertTrue(any(button.callback_data ==
                                    f"client:onboard:{platform}:manual"
                                    for row in markup.inline_keyboard for button in row))
                self.assertTrue(all("https://" not in (button.callback_data or "")
                                    for row in markup.inline_keyboard for button in row))

    def test_malformed_or_secret_ambiguous_url_falls_back(self):
        candidates = (
            None, "", "http://sub.example.invalid/a",
            "javascript:alert(1)", "file:///etc/passwd",
            "https://sub.example.invalid/a#fragment",
            "https://sub.example.invalid/a?x=1",
            "https://sub.example.invalid/a?",
            "https://user:pass@sub.example.invalid/a",
            "https://sub.example.invalid/a%2Fb",
            "https://sub.example.invalid\\@evil.example/a",
            "https://127.0.0.1/id", "https://localhost/id",
            "https://[::1]/id", "https://sub.example.invalid:99999/a",
            "https://sub.example.invalid/a\nmalicious",
            "https://sub.example.invalid/" + "a" * 400,
            "https://sub.example.invalid/a" + "\u202e",
        )
        for value in candidates:
            with self.subTest(value=str(value)[:35]):
                self.assertIsNone(import_uri("incy", "ios", value))
                self.assertIsNone(import_uri("v2raytun", "android", value))
        self.assertIsNone(import_uri("other", "ios", URL))
        self.assertIsNone(import_uri("incy", "unknown", URL))
        self.assertIsNone(import_uri("v2raytun", "linux", URL))
        self.assertIsNone(import_uri("shadowrocket", "android", URL))
        self.assertIsNotNone(import_uri("shadowrocket", "macos", URL))
        self.assertIsNotNone(import_uri("happ", "macos", URL))
        self.assertIsNone(import_uri("v2box", "ios", URL))
        self.assertIsNone(import_uri("karing", "ios", URL))
        self.assertIsNone(import_uri("v2box", "windows", URL))


    def test_encoded_clients_never_leak_raw_url_and_fail_closed_for_long_links(self):
        for app in ("v2box", "shadowrocket", "karing", "onexray", "throne"):
            platform = "ios" if app != "throne" else "macos"
            with self.subTest(app=app):
                uri = import_uri(app, platform, URL, title="Тест VPN")
                self.assertIsNotNone(uri)
                self.assertNotIn(URL, uri)
                self.assertIsNone(import_uri(app, platform, "https://example.invalid/" + "a" * 240, title="Тест VPN"))
        self.assertTrue(import_uri("happ", "ios", URL).startswith("happ://add/"))

    def test_shadowrocket_preserves_bounded_upstream_title(self):
        from client_import_title import safe_import_title
        self.assertEqual(
            import_uri("shadowrocket", "ios", URL, title="Cliché VPN"),
            "shadowrocket://add/sub://"
            + base64.b64encode((URL + "?flag=shadowrocket").encode()).decode()
            + "?remark=Clich%C3%A9%20VPN",
        )
        self.assertFalse(import_uri("shadowrocket", "ios", URL).endswith("remark=VPN"))
        self.assertIsNone(safe_import_title(("bad" + chr(10) + "name")))
        self.assertIsNone(safe_import_title("a" * 65))

    def test_security_matrix_all_supported_schemes_fail_closed(self):
        for app, spec in IMPORT_CLIENTS.items():
            platform = sorted(spec.platforms)[0]
            for invalid in ("http://example.invalid/id", "https://127.0.0.1/id",
                            "https://example.invalid/id?token=x", "https://u:p@example.invalid/id",
                            "https://example.invalid/%2e%2e"):
                with self.subTest(app=app, invalid=invalid):
                    self.assertIsNone(import_uri(app, platform, invalid))


class ImportUI473Tests(unittest.IsolatedAsyncioTestCase):
    def _call(self, data, *, chat_id=42, chat_type="private"):
        return SimpleNamespace(
            data=data, from_user=SimpleNamespace(id=42), answer=AsyncMock(),
            message=SimpleNamespace(chat=SimpleNamespace(id=chat_id, type=chat_type)),
            bot=SimpleNamespace(send_photo=AsyncMock()),
        )

    async def test_no_subscription_lookup_in_group_or_wrong_private_chat(self):
        import client_access as ui
        for chat_id, chat_type in ((42, "group"), (99, "private")):
            call = self._call("client:onboard:ios:incy", chat_id=chat_id, chat_type=chat_type)
            service = SimpleNamespace(subscription_url=AsyncMock())
            with patch.object(ui, "guard_callback", new=AsyncMock(return_value=True)), \
                 patch.object(ui, "_service", return_value=service):
                await ui.onboarding_platform_cb(call)
            service.subscription_url.assert_not_awaited()
            call.bot.send_photo.assert_not_awaited()

    async def test_copy_uri_private_owner_only_never_in_callback(self):
        import client_access as ui
        call = self._call("client:onboard:subscription:ios:incy")
        service = SimpleNamespace(subscription_url=AsyncMock(return_value=URL))
        with patch.object(ui, "guard_callback", new=AsyncMock(return_value=True)), \
             patch.object(ui, "_service", return_value=service), \
             patch.object(ui, "render_callback", new=AsyncMock()) as render:
            await ui.onboarding_platform_cb(call)
        service.subscription_url.assert_awaited_once_with(42)
        markup = render.await_args.kwargs["reply_markup"]
        copies = [button.copy_text.text for row in markup.inline_keyboard
                  for button in row if button.copy_text]
        self.assertEqual(copies, ["incy://import/" + URL, URL])
        callbacks = [button.callback_data for row in markup.inline_keyboard
                     for button in row if button.callback_data]
        self.assertTrue(all("owned" not in value and "https" not in value for value in callbacks))
        self.assertIn("client:onboard:subscription:ios:incy:qr", callbacks)
        call.bot.send_photo.assert_not_awaited()

    async def test_import_qr_only_private_and_local(self):
        import client_access as ui
        call = self._call("client:onboard:ios:v2raytun:qr")
        service = SimpleNamespace(subscription_url=AsyncMock(return_value=URL))
        with patch.object(ui, "guard_callback", new=AsyncMock(return_value=True)), \
             patch.object(ui, "_service", return_value=service), \
             patch.object(ui, "qr_png", return_value=b"fakepng") as qr:
            await ui.onboarding_platform_cb(call)
        qr.assert_called_once_with("v2raytun://import/" + URL)
        call.bot.send_photo.assert_awaited_once()
        self.assertEqual(call.bot.send_photo.await_args.args[0], 42)

    async def test_portal_disabled_and_malformed_callbacks_read_nothing(self):
        import client_access as ui
        service = SimpleNamespace(subscription_url=AsyncMock())
        off = SimpleNamespace(snapshot=AsyncMock(return_value=SimpleNamespace(portal_enabled=False)))
        call = self._call("client:onboard:ios:incy")
        with patch.object(ui, "feature_flags", off), patch.object(ui, "_service", return_value=service):
            await ui.onboarding_platform_cb(call)
        service.subscription_url.assert_not_awaited()
        for data in ("client:onboard:ios:javascript", "client:onboard:evil:incy",
                     "client:onboard:ios:incy:qr:extra"):
            call = self._call(data)
            with patch.object(ui, "guard_callback", new=AsyncMock(return_value=True)), \
                 patch.object(ui, "_service", return_value=service):
                await ui.onboarding_platform_cb(call)
        service.subscription_url.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
