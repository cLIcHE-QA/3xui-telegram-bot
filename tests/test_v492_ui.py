"""v4.9.2 UI behavior: bot version visibility and bounded Reality fingerprint choices."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class V492UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.env = patch.dict(os.environ, {
            "BOT_TOKEN": "123456789:offline-test-token-not-used-for-network",
            "PANEL_URL": "https://panel.example.invalid/base",
            "PANEL_API_TOKEN": "offline-test-placeholder",
            "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/sub/{sub_id}",
            "ALLOWED_TELEGRAM_IDS": "1",
            "ADMIN_TELEGRAM_IDS": "1",
            "NODE_BACKUP_TARGETS": "",
            "DB_PATH": str(Path(cls.tmp.name) / "bot.sqlite3"),
            "BACKUP_DIR": str(Path(cls.tmp.name) / "backups"),
        })
        cls.env.start()

        import admin_shell
        import inbound_admin

        cls.shell = admin_shell
        cls.inbound = inbound_admin

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        cls.tmp.cleanup()

    @staticmethod
    def callback_values(markup):
        return [button.callback_data for row in markup.inline_keyboard for button in row]

    def test_system_section_shows_single_source_app_version(self):
        from version import APP_VERSION

        text = self.shell.system_section_text()
        self.assertIn(f"🤖 Бот: v{APP_VERSION}", text)

    def test_fingerprint_callbacks_require_admin_role(self):
        from admin_auth import required_role_for_callback

        self.assertEqual(required_role_for_callback("admin:inbound:editfp:7"), "admin")
        self.assertEqual(required_role_for_callback("admin:inbound:setfp:7:chrome"), "admin")

    def test_reality_fingerprints_match_3xui_select(self):
        self.assertEqual(
            self.inbound.REALITY_FINGERPRINTS,
            (
                "chrome",
                "firefox",
                "safari",
                "ios",
                "android",
                "edge",
                "360",
                "qq",
                "random",
                "randomized",
                "randomizednoalpn",
                "unsafe",
            ),
        )
        self.assertNotIn("fingerprint", self.inbound._FIELD_PROMPTS)

    def test_fingerprint_menu_marks_current_and_callback_fits_telegram_limit(self):
        iid = 9223372036854775807
        markup = self.inbound._fingerprint_menu(iid, "chrome")
        labels = [button.text for row in markup.inline_keyboard for button in row]
        callbacks = self.callback_values(markup)

        self.assertIn("✅ chrome", labels)
        self.assertIn("🪪 firefox", labels)
        self.assertIn(f"admin:inbound:setfp:{iid}:randomizednoalpn", callbacks)
        for callback in callbacks:
            self.assertLessEqual(len(callback.encode("utf-8")), 64)

    def test_edit_menu_uses_fingerprint_selector_not_text_input(self):
        markup = self.inbound._edit_menu({
            "id": 7,
            "streamSettings": {
                "security": "reality",
                "network": "tcp",
            },
        })
        callbacks = self.callback_values(markup)
        self.assertIn("admin:inbound:editfp:7", callbacks)
        self.assertNotIn("admin:inbound:editfield:7:fingerprint", callbacks)

    def test_set_reality_fingerprint_preserves_other_stream_settings(self):
        ib = {
            "streamSettings": {
                "security": "reality",
                "network": "tcp",
                "sockopt": {"tcpFastOpen": True},
                "realitySettings": {
                    "privateKey": "must-stay-private-and-unchanged",
                    "target": "example.com:443",
                    "serverNames": ["example.com"],
                    "settings": {
                        "fingerprint": "chrome",
                        "serverName": "example.com",
                        "spiderX": "/",
                    },
                },
            },
        }

        old = self.inbound._set_reality_fingerprint(ib, "firefox")
        stream = self.inbound._stream(ib)
        reality = self.inbound._json_obj(stream["realitySettings"])
        client = self.inbound._json_obj(reality["settings"])

        self.assertEqual(old, "chrome")
        self.assertEqual(client["fingerprint"], "firefox")
        self.assertEqual(client["serverName"], "example.com")
        self.assertEqual(client["spiderX"], "/")
        self.assertEqual(reality["privateKey"], "must-stay-private-and-unchanged")
        self.assertEqual(reality["target"], "example.com:443")
        self.assertEqual(stream["sockopt"], {"tcpFastOpen": True})

    def test_set_reality_fingerprint_rejects_arbitrary_value(self):
        ib = {
            "streamSettings": {
                "security": "reality",
                "realitySettings": {"settings": {"fingerprint": "chrome"}},
            },
        }
        with self.assertRaises(ValueError):
            self.inbound._set_reality_fingerprint(ib, "my-custom-browser")

    def test_set_reality_fingerprint_rejects_non_reality_inbound(self):
        ib = {
            "streamSettings": {
                "security": "tls",
                "realitySettings": {"settings": {"fingerprint": "chrome"}},
            },
        }
        with self.assertRaises(ValueError):
            self.inbound._set_reality_fingerprint(ib, "firefox")


if __name__ == "__main__":
    unittest.main()
