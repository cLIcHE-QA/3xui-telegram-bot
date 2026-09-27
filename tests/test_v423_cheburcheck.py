from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest.mock import patch

from admin_privileges import required_role_for_callback
from cheburcheck import CheburcheckError, normalize_target, parse_response
from admin_navigation import monitoring_menu
from config import load_settings


ROOT = Path(__file__).resolve().parents[1]


class V423CheburcheckTests(unittest.TestCase):
    def test_supported_targets_are_normalized(self):
        self.assertEqual(normalize_target("Example.ORG."), "example.org")
        self.assertEqual(normalize_target("1.1.1.1"), "1.1.1.1")
        self.assertEqual(normalize_target("2606:4700:4700::1111"), "2606:4700:4700::1111")
        self.assertEqual(normalize_target("1.1.1.7/24"), "1.1.1.0/24")
        self.assertEqual(normalize_target("AS13335"), "AS13335")

    def test_arbitrary_urls_private_targets_and_oversized_subnets_are_rejected(self):
        for value in (
            "https://example.org/path",
            "127.0.0.1",
            "10.0.0.0/8",
            "1.0.0.0/7",
            "2001:db8::1",
            "2001:4860::/16",
        ):
            with self.subTest(value=value):
                with self.assertRaises(CheburcheckError):
                    normalize_target(value)

    def test_upstream_response_contract_is_parsed(self):
        result = parse_response({
            "id": "fixture",
            "target": "example.org",
            "target_type": "Домен",
            "blocked": True,
            "rkn_domain": "example.org",
            "ips": ["93.184.216.34"],
            "reverse_lookup": [],
            "blocked_subnets": ["93.184.216.0/24"],
            "cdn_providers": {},
            "geo": {
                "asn": "AS15133",
                "country_code": "US",
                "organisation": "Example",
                "location": "United States",
            },
            "asn_info": None,
            "whitelist": None,
            "subnet_size": None,
            "complaints": [{"date": "2026-09-27", "count": 2}],
        })
        self.assertEqual(result.target, "example.org")
        self.assertEqual(result.target_type, "Домен")
        self.assertTrue(result.blocked)
        self.assertEqual(result.ips, ("93.184.216.34",))
        self.assertEqual(result.blocked_subnets, ("93.184.216.0/24",))
        self.assertEqual(result.asn, "AS15133")
        self.assertEqual(result.complaints[0].count, 2)

    def test_monitoring_navigation_and_rbac_are_read_only(self):
        callbacks = [
            button.callback_data
            for row in monitoring_menu().inline_keyboard
            for button in row
        ]
        self.assertIn("admin:cheburcheck", callbacks)
        for callback in (
            "admin:cheburcheck",
            "admin:cheburcheck:start",
            "admin:cheburcheck:cancel",
        ):
            self.assertEqual(required_role_for_callback(callback), "read_only")

    def test_runtime_and_ui_keep_cheburcheck_in_monitoring(self):
        runtime = (ROOT / "app_runtime.py").read_text(encoding="utf-8")
        ui = (ROOT / "cheburcheck_admin.py").read_text(encoding="utf-8")
        self.assertIn("dp.include_router(cheburcheck_router)", runtime)
        self.assertIn('callback_data="admin:section:monitoring"', ui)
        self.assertIn('Источник: Cheburcheck.', ui)
        self.assertNotIn("settings.cheburcheck_url", ui.split("def _home_text", 1)[1])

    def test_client_has_bounded_network_contract(self):
        source = (ROOT / "cheburcheck.py").read_text(encoding="utf-8")
        self.assertIn('f"{self.base_url}/api/v1/check"', source)
        self.assertIn('allow_redirects=False', source)
        self.assertIn('MAX_RESPONSE_BYTES = 256 * 1024', source)
        self.assertIn('MAX_CONCURRENCY = 4', source)
        self.assertIn('ClientTimeout(total=10, connect=3, sock_read=7)', source)
        self.assertNotIn('http://{target}', source)
        self.assertNotIn('https://{target}', source)

    def test_optional_configuration_is_safe(self):
        base = {
            "BOT_TOKEN": "123456:token",
            "PANEL_URL": "https://panel.example.invalid/base",
            "PANEL_API_TOKEN": "placeholder",
            "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/sub/{sub_id}",
            "ALLOWED_TELEGRAM_IDS": "1",
            "ADMIN_TELEGRAM_IDS": "1",
            "HOST_CONTROL_TARGETS": "",
            "NODE_BACKUP_TARGETS": "",
            "CHEBURCHECK_URL": "http://cheburcheck:8080",
            "CHEBURCHECK_VERIFY_TLS": "true",
        }
        with patch.dict(os.environ, base, clear=False):
            settings = load_settings()
        self.assertEqual(settings.cheburcheck_url, "http://cheburcheck:8080")

        insecure = dict(base)
        insecure["CHEBURCHECK_URL"] = "http://example.com"
        with patch.dict(os.environ, insecure, clear=False):
            with self.assertRaisesRegex(RuntimeError, "private/local"):
                load_settings()

        bad_tls = dict(base)
        bad_tls["CHEBURCHECK_URL"] = "https://cheburcheck.example.com"
        bad_tls["CHEBURCHECK_VERIFY_TLS"] = "false"
        with patch.dict(os.environ, bad_tls, clear=False):
            with self.assertRaisesRegex(RuntimeError, "forbidden"):
                load_settings()

    def test_attribution_and_pinned_revision_are_recorded(self):
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for text in (notices, readme):
            self.assertIn("LowderPlay/cheburcheck", text)
            self.assertIn("0bbd2be8ca4b8f9ded1407597654314fc2a900c6", text)
        self.assertIn("BSD 3-Clause License", notices)
        self.assertIn("Copyright (c) 2023, Ivan Evstratov", notices)


if __name__ == "__main__":
    unittest.main()
