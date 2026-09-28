from __future__ import annotations

from dataclasses import replace
import os
from unittest.mock import patch
import unittest

from admin_privileges import required_role_for_callback
from cheburcheck import ProbeSummary, _probe_bucket, parse_response

_TEST_ENV = {
    "BOT_TOKEN": "123456789:offline-test-token",
    "PANEL_URL": "https://master.example.invalid/base",
    "PANEL_API_TOKEN": "offline-panel-token",
    "SUBSCRIPTION_URL_TEMPLATE": "https://sub.example.invalid/sub/{sub_id}",
    "ALLOWED_TELEGRAM_IDS": "1",
    "ADMIN_TELEGRAM_IDS": "1",
    "HOST_CONTROL_TARGETS": "",
    "NODE_BACKUP_TARGETS": "",
}
with patch.dict(os.environ, _TEST_ENV, clear=False):
    import cheburcheck_admin


def fixture_result():
    return parse_response({
        "id": "11111111-1111-1111-1111-111111111111",
        "target": "example.org",
        "target_type": "Домен",
        "blocked": False,
        "rkn_domain": None,
        "ips": ["93.184.216.34"],
        "reverse_lookup": [],
        "blocked_subnets": [],
        "cdn_providers": {
            "Cloudflare": [
                {"provider": "Cloudflare", "cidr": "104.16.0.0/13", "region": None},
                {"provider": "Cloudflare", "cidr": "172.64.0.0/13", "region": None},
                {"provider": "Cloudflare", "cidr": "188.114.96.0/20", "region": None},
            ]
        },
        "geo": {
            "asn": "AS12345",
            "organisation": "Example ISP",
            "location": "Москва",
        },
        "asn_info": {
            "asn": 12345,
            "prefixes": ["192.0.2.0/24", "198.51.100.0/24", "2001:db8::/32"],
            "blocked_prefixes": ["192.0.2.0/24", "198.51.100.0/24"],
        },
        "whitelist": None,
        "subnet_size": None,
        "complaints": [],
    })


class V4232CheburcheckTests(unittest.TestCase):
    def test_extended_check_contract_is_parsed_without_raw_payload(self):
        result = fixture_result()
        self.assertEqual(result.check_id, "11111111-1111-1111-1111-111111111111")
        self.assertEqual(len(result.cdn_providers), 1)
        self.assertEqual(result.cdn_providers[0].name, "Cloudflare")
        self.assertEqual(result.cdn_providers[0].network_count, 3)
        self.assertEqual(result.asn_blocked_prefix_count, 2)
        self.assertEqual(result.asn_prefix_count, 3)
        self.assertFalse(result.whitelist)

    def test_probe_verdicts_are_compacted_to_three_operator_buckets(self):
        self.assertEqual(_probe_bucket({"verdicts": ["ok"]}, is_static_cdn=False), "green")
        self.assertEqual(_probe_bucket({"verdicts": ["sni_block"]}, is_static_cdn=False), "red")
        self.assertEqual(_probe_bucket({"verdicts": ["whitelist"]}, is_static_cdn=False), "yellow")
        self.assertEqual(_probe_bucket({"verdicts": ["uncertain"]}, is_static_cdn=False), "yellow")
        self.assertEqual(
            _probe_bucket(
                {
                    "verdicts": ["ok"],
                    "cdn_unblocked": False,
                    "host_results": [{"host": "Blacklist"}],
                },
                is_static_cdn=True,
            ),
            "red",
        )

    def test_result_card_matches_compact_v4232_contract(self):
        result = replace(
            fixture_result(),
            probe_summary=ProbeSummary(
                online_probes=11,
                response_count=11,
                green=8,
                red=2,
                yellow=1,
            ),
        )
        text = cheburcheck_admin.result_text(result)
        self.assertIn("Цель: example.org", text)
        self.assertIn("Результат: 🟢 блокировка не обнаружена", text)
        self.assertIn("Сеть: Example ISP · AS12345 · Москва", text)
        self.assertIn("📋 Списки", text)
        self.assertIn("РКН: 🟢 не найден", text)
        self.assertIn("CDN: Cloudflare · 3 сети", text)
        self.assertIn("Исключение CDN: —", text)
        self.assertIn("ASN: 2 / 3 подсетей в списках", text)
        self.assertIn("🌍 Регионы: 11 ответов · 🟢 8 · 🔴 2 · 🟡 1", text)
        self.assertTrue(text.endswith("Источник: Cheburcheck."))
        for legacy in ("Reverse DNS:", "Заблокированные подсети:", "Жалобы за 14 дней:", "Тип:"):
            self.assertNotIn(legacy, text)

    def test_contextual_keyboards_do_not_cross_navigation_boundaries(self):
        monitoring = cheburcheck_admin._result_keyboard("monitoring")
        master = cheburcheck_admin._result_keyboard("master")
        node = cheburcheck_admin._result_keyboard("node-7")

        monitoring_callbacks = [
            button.callback_data for row in monitoring.inline_keyboard for button in row
        ]
        master_callbacks = [
            button.callback_data for row in master.inline_keyboard for button in row
        ]
        node_callbacks = [
            button.callback_data for row in node.inline_keyboard for button in row
        ]

        self.assertEqual(
            monitoring_callbacks,
            ["admin:cheburcheck:start:monitoring", "admin:cheburcheck"],
        )
        self.assertEqual(
            master_callbacks,
            ["admin:cheburcheck:start:master", "admin:master"],
        )
        self.assertEqual(
            node_callbacks,
            ["admin:cheburcheck:start:node-7", "admin:node:7"],
        )
        self.assertNotIn("admin:section:monitoring", master_callbacks)
        self.assertNotIn("admin:cheburcheck", node_callbacks)

    def test_new_context_callbacks_remain_read_only(self):
        for callback in (
            "admin:cheburcheck:target:master",
            "admin:cheburcheck:target:node:2",
            "admin:cheburcheck:target:host:3",
            "admin:cheburcheck:start:monitoring",
            "admin:cheburcheck:start:master",
            "admin:cheburcheck:start:node-2",
            "admin:cheburcheck:cancel:node-2",
        ):
            with self.subTest(callback=callback):
                self.assertEqual(required_role_for_callback(callback), "read_only")

    def test_probe_transport_is_bounded_and_uses_check_id_only(self):
        source = open(cheburcheck_admin.__file__.replace("cheburcheck_admin.py", "cheburcheck.py"), encoding="utf-8").read()
        self.assertIn('MAX_PROBE_RESPONSE_BYTES = 256 * 1024', source)
        self.assertIn('ClientTimeout(total=12, connect=3, sock_read=10)', source)
        self.assertIn('/api/v1/probe/{result.check_id}', source)
        self.assertIn('allow_redirects=False', source)


if __name__ == "__main__":
    unittest.main()
