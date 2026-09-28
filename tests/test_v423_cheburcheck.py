from __future__ import annotations

import os
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from admin_privileges import required_role_for_callback
from cheburcheck import CheburcheckError, normalize_target, parse_response
from admin_navigation import monitoring_menu
from config import load_settings

_CHEBURCHECK_TEST_ENV = {
    "BOT_TOKEN": "123456789:offline-test-token",
    "PANEL_URL": "https://master.example.invalid/base",
    "PANEL_API_TOKEN": "offline-panel-token",
    "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/sub/{sub_id}",
    "ALLOWED_TELEGRAM_IDS": "1",
    "ADMIN_TELEGRAM_IDS": "1",
    "HOST_CONTROL_TARGETS": "",
    "NODE_BACKUP_TARGETS": "",
}
with patch.dict(os.environ, _CHEBURCHECK_TEST_ENV, clear=False):
    import cheburcheck_admin


ROOT = Path(__file__).resolve().parents[1]


class V423CheburcheckTests(unittest.IsolatedAsyncioTestCase):
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
            "admin:cheburcheck:master",
            "admin:cheburcheck:node:2",
            "admin:cheburcheck:host:3",
        ):
            self.assertEqual(required_role_for_callback(callback), "read_only")

    def test_runtime_and_ui_keep_cheburcheck_in_monitoring(self):
        runtime = (ROOT / "app_runtime.py").read_text(encoding="utf-8")
        ui = (ROOT / "cheburcheck_admin.py").read_text(encoding="utf-8")
        self.assertIn("dp.include_router(cheburcheck_router)", runtime)
        self.assertIn('callback_data="admin:section:monitoring"', ui)
        self.assertIn('Источник: Cheburcheck.', ui)
        self.assertNotIn("settings.cheburcheck_url", ui.split("def _home_text", 1)[1])

    def test_stored_targets_strip_paths_and_reject_local_names(self):
        self.assertEqual(
            cheburcheck_admin._stored_target("https://panel.example.org/base/path"),
            "panel.example.org",
        )
        self.assertEqual(
            cheburcheck_admin._stored_target("edge.example.org:2053"),
            "edge.example.org",
        )
        self.assertIsNone(cheburcheck_admin._stored_target("http://127.0.0.1:2053"))
        self.assertIsNone(cheburcheck_admin._stored_target("cheburcheck.internal"))

    async def test_discovery_uses_master_nodes_and_hosts_without_duplicates(self):
        node = SimpleNamespace(
            id=2,
            name="Edge-1",
            address="edge.example.org",
            transitive=False,
        )
        hosts = [
            SimpleNamespace(
                id=7,
                label="VPN",
                hostname="vpn.example.org",
                enabled=1,
            ),
            SimpleNamespace(
                id=8,
                label="Duplicate",
                hostname="edge.example.org",
                enabled=1,
            ),
        ]
        with patch.object(cheburcheck_admin.client, "base_url", "http://cheburcheck:8000"), \
             patch.object(cheburcheck_admin.xui, "nodes_list", new=AsyncMock(return_value=[node])), \
             patch.object(cheburcheck_admin.db, "list_hosts", new=AsyncMock(return_value=hosts)), \
             patch.object(
                 cheburcheck_admin,
                 "settings",
                 SimpleNamespace(
                     master_name="Master",
                     panel_url="https://master.example.org/base",
                 ),
             ):
            targets, warnings = await cheburcheck_admin.discover_targets()
        self.assertEqual(warnings, ())
        self.assertEqual(
            [item.target for item in targets],
            ["master.example.org", "edge.example.org", "vpn.example.org"],
        )
        self.assertEqual(
            [item.callback_data for item in targets],
            [
                "admin:cheburcheck:target:master",
                "admin:cheburcheck:target:node:2",
                "admin:cheburcheck:target:host:7",
            ],
        )

    def test_node_cards_expose_cheburcheck_shortcuts(self):
        from node_ui import master_detail_keyboard, node_detail_keyboard

        master_callbacks = [
            button.callback_data
            for row in master_detail_keyboard().inline_keyboard
            for button in row
        ]
        node_callbacks = [
            button.callback_data
            for row in node_detail_keyboard(2).inline_keyboard
            for button in row
        ]
        self.assertIn("admin:cheburcheck:master", master_callbacks)
        self.assertIn("admin:cheburcheck:node:2", node_callbacks)

    def test_per_admin_cooldown_blocks_only_rapid_repeat(self):
        cheburcheck_admin._last_request_at.clear()
        with patch.object(
            cheburcheck_admin.time,
            "monotonic",
            side_effect=[100.0, 101.0, 101.0, 102.1],
        ):
            self.assertTrue(cheburcheck_admin._consume_cooldown(1))
            self.assertFalse(cheburcheck_admin._consume_cooldown(1))
            self.assertTrue(cheburcheck_admin._consume_cooldown(2))
            self.assertTrue(cheburcheck_admin._consume_cooldown(1))
        self.assertEqual(cheburcheck_admin._MIN_REQUEST_INTERVAL_SECONDS, 2.0)

    def test_client_has_bounded_network_contract(self):
        source = (ROOT / "cheburcheck.py").read_text(encoding="utf-8")
        self.assertIn('f"{self.base_url}/api/v1/check"', source)
        self.assertIn('allow_redirects=False', source)
        self.assertIn('MAX_RESPONSE_BYTES = 1024 * 1024', source)
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
